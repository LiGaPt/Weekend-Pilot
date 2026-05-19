from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agents import (
    AgentInvocationContext,
    AgentResult,
    sanitized_agent_payload,
)
from backend.app.agents.factory import build_agent_adapters
from backend.app.confirmation import HumanConfirmationService
from backend.app.core.config import get_settings
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicQueryPlanner,
    QueryPlanExecutor,
)
from backend.app.plans import ReviewedPlanPersistenceService
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    MemoryItemRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.tool_gateway import ToolGateway
from backend.app.workflow.dependencies import WeekendPilotWorkflowDependencies
from backend.app.workflow.errors import WorkflowError
from backend.app.workflow.recovery import RecoveryAttempt, resolve_recovery_route
from backend.app.workflow.state import (
    CandidateBlackboard,
    CandidateBlackboardEntry,
    RouteTimeSummary,
    WeekendPilotWorkflowState,
    WorkflowMemoryRecord,
)
from backend.app.workflow.timing import WorkflowTimingSummary


_RECOVERY_SENSITIVE_FRAGMENTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
    "tool_event_id",
    "action_id",
    "traceback",
)


class WeekendPilotWorkflowNodes:
    workflow_version = "recovery_routing_v0"

    def __init__(self, dependencies: WeekendPilotWorkflowDependencies) -> None:
        self.dependencies = dependencies
        self.session = dependencies.session
        self.repositories = _Repositories(self.session)
        self.gateway = ToolGateway(
            registry=build_mock_world_registry(),
            tool_events=self.repositories.tool_events,
            action_ledger=self.repositories.action_ledger,
            cache=dependencies.cache,
            rate_limiter=dependencies.rate_limiter,
            failure_injector=dependencies.failure_injector,
        )
        self.recorder = ObservabilityRecorder(
            runs=self.repositories.runs,
            tool_events=self.repositories.tool_events,
            action_ledger=self.repositories.action_ledger,
            plans=self.repositories.plans,
            local_buffer=LocalTraceBuffer(self._trace_path(dependencies.trace_buffer_path)),
        )
        settings = dependencies.settings or get_settings()
        agents = build_agent_adapters(settings, llm_client=dependencies.llm_client)
        self.supervisor_agent = agents.supervisor
        self.discovery_agent = agents.discovery
        self.dining_agent = agents.dining
        self.itinerary_planner_agent = agents.itinerary_planner
        self.validator_recovery_agent = agents.validator_recovery

    def initialize(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        user = self._get_or_create_user(
            external_user_id=state.get("external_user_id"),
            display_name=state.get("display_name"),
        )
        run = self.repositories.runs.create(
            user_id=user.user_id,
            case_id=state.get("case_id"),
            agent_version=self._required_text(state, "agent_version"),
            prompt_version=self._required_text(state, "prompt_version"),
            tool_profile=self._required_text(state, "tool_profile"),
            world_profile=self._required_text(state, "world_profile"),
            failure_profile=state.get("failure_profile"),
            status="running",
            metadata_json={
                "workflow": {
                    "workflow_version": self.workflow_version,
                    "source": "langgraph-workflow",
                    "auto_confirm": bool(state.get("auto_confirm")),
                    "selected_plan_index": int(state.get("selected_plan_index") or 0),
                }
            },
        )
        trace_context = self.recorder.build_context(run.run_id)
        return self._updates(
            state,
            "initialize",
            run_id=run.run_id,
            user_id=user.user_id,
            trace_id=trace_context.trace_id,
            trace_context=trace_context,
        )

    def parse_intent(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        intent = DeterministicIntentParser().parse(self._required_text(state, "user_input"))
        return self._updates(state, "parse_intent", parsed_intent=intent)

    def load_memory(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        user_id = self._required_uuid(state, "user_id")
        memories = [
            self._memory_record(memory)
            for memory in self.repositories.memory.list_active_for_user(user_id)
        ]
        return self._updates(state, "load_memory", active_memories=memories)

    def generate_queries(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        query_plan = DeterministicQueryPlanner().build(
            self._required_value(state, "parsed_intent"),
            provider_profile=self._required_text(state, "tool_profile"),
        )
        agent_result, assignment_plan = self.supervisor_agent.assign(
            query_plan,
            context=self._agent_context(state, "supervisor"),
        )
        agent_results = self._append_agent_result(state, agent_result)
        self._persist_agent_metadata(self._required_uuid(state, "run_id"), agent_results)
        return self._updates(
            state,
            "generate_queries",
            query_plan=query_plan,
            supervisor_assignment_plan=assignment_plan,
            agent_results=agent_results,
        )

    def execute_searches(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        collection = QueryPlanExecutor(self.gateway).execute_initial_calls(
            self._required_value(state, "query_plan"),
            self._required_uuid(state, "run_id"),
            langsmith_trace_id=state.get("trace_id"),
        )
        return self._updates(state, "execute_searches", candidate_collection=collection)

    def populate_candidate_blackboard(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        blackboard = self._candidate_blackboard(self._required_value(state, "candidate_collection"))
        return self._updates(
            state,
            "populate_candidate_blackboard",
            candidate_blackboard=blackboard,
        )

    def pre_flight_check_availability(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        enrichment = CandidateEnricher(self.gateway).enrich(
            self._required_value(state, "query_plan"),
            self._required_value(state, "candidate_collection"),
            langsmith_trace_id=state.get("trace_id"),
        )
        blackboard = self._screen_candidate_blackboard(
            self._required_value(state, "candidate_blackboard"),
            enrichment,
        )
        discovery_result = self.discovery_agent.summarize(
            self._required_value(state, "query_plan"),
            self._required_value(state, "candidate_collection"),
            enrichment,
            context=self._agent_context(state, "discovery"),
        )
        dining_result = self.dining_agent.summarize(
            self._required_value(state, "query_plan"),
            self._required_value(state, "candidate_collection"),
            enrichment,
            context=self._agent_context(state, "dining"),
        )
        agent_results = self._append_agent_result(state, discovery_result, dining_result)
        self._persist_agent_metadata(self._required_uuid(state, "run_id"), agent_results)
        return self._updates(
            state,
            "pre_flight_check_availability",
            enrichment_result=enrichment,
            candidate_blackboard=blackboard,
            agent_results=agent_results,
        )

    def logical_planner_agent(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        agent_result, drafts = self.itinerary_planner_agent.generate(
            self._required_value(state, "query_plan"),
            self._required_value(state, "enrichment_result"),
            context=self._agent_context(state, "itinerary_planner"),
        )
        agent_results = self._append_agent_result(state, agent_result)
        self._persist_agent_metadata(self._required_uuid(state, "run_id"), agent_results)
        return self._updates(
            state,
            "logical_planner_agent",
            itinerary_drafts=drafts,
            agent_results=agent_results,
        )

    def route_and_time_engine(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        summary = self._route_time_summary(
            self._required_value(state, "enrichment_result"),
            self._required_value(state, "itinerary_drafts"),
        )
        return self._updates(
            state,
            "route_and_time_engine",
            route_time_summary=summary,
        )

    def semantic_validator(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        run_id = self._required_uuid(state, "run_id")
        agent_result, review, recovery_decision = self.validator_recovery_agent.review(
            self._required_value(state, "query_plan"),
            self._required_value(state, "enrichment_result"),
            self._required_value(state, "itinerary_drafts"),
            pre_confirmation_action_count=self._action_count(run_id),
            context=self._agent_context(state, "validator_recovery"),
        )
        agent_results = self._append_agent_result(state, agent_result)
        self._persist_agent_metadata(run_id, agent_results)
        return self._updates(
            state,
            "semantic_validator",
            final_review_result=review,
            recovery_decision=recovery_decision,
            agent_results=agent_results,
        )

    def apply_recovery(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        run_id = self._required_uuid(state, "run_id")
        attempts = self._recovery_attempts(state)
        route_result = resolve_recovery_route(
            state.get("recovery_decision"),
            attempt_count=len(attempts),
            max_attempts=int(state.get("max_recovery_attempts") or 1),
        )
        updated_attempts = [*attempts]
        if route_result.attempt is not None:
            updated_attempts.append(route_result.attempt)

        self._persist_recovery_metadata(
            run_id,
            updated_attempts,
            int(state.get("max_recovery_attempts") or 1),
        )
        if route_result.route_to in {"generate_queries", "execute_searches", "logical_planner_agent"}:
            return self._updates(
                state,
                "apply_recovery",
                recovery_attempts=updated_attempts,
                active_recovery_route=route_result.route_to,
            )

        self.repositories.runs.update_status(run_id, "failed")
        return self._updates(
            state,
            "apply_recovery",
            status="failed",
            recovery_attempts=updated_attempts,
            active_recovery_route=None,
            error_json=self._recovery_error_json(route_result),
        )

    def final_review(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        review = self._required_value(state, "final_review_result")
        run_id = self._required_uuid(state, "run_id")
        if review.safe_to_present:
            return self._updates(state, "final_review")

        error_type = review.errors[0].check_name if review.errors else "final_review_blocked"
        return self._fail(
            state,
            "final_review",
            run_id,
            error_type,
            "Final review blocked presentation for this run.",
        )

    def present_to_user(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        if state.get("status") in {"failed", "error"}:
            return self._updates(state, "present_to_user")

        review = self._required_value(state, "final_review_result")
        drafts = self._required_value(state, "itinerary_drafts")
        run_id = self._required_uuid(state, "run_id")
        persistence = ReviewedPlanPersistenceService(self.repositories.plans)
        persisted = persistence.persist_reviewed_drafts(review, drafts)
        persisted_plans = list(persisted.persisted_plans)

        if not review.safe_to_present:
            return self._fail(
                state,
                "present_to_user",
                run_id,
                "final_review_blocked",
                "Final review blocked presentation for this run.",
                persisted_plans=persisted_plans,
            )
        if not persisted_plans:
            return self._fail(
                state,
                "present_to_user",
                run_id,
                "no_persisted_plans",
                "No safe reviewed plans were persisted for this run.",
                persisted_plans=persisted_plans,
            )

        selected_plan_index = int(state.get("selected_plan_index") or 0)
        if selected_plan_index >= len(persisted_plans):
            return self._fail(
                state,
                "present_to_user",
                run_id,
                "selected_plan_index_out_of_range",
                "Selected plan index is outside the persisted plan list.",
                persisted_plans=persisted_plans,
                selected_plan_index=selected_plan_index,
                persisted_plan_count=len(persisted_plans),
            )

        selected = persistence.select_plan(run_id, persisted_plans[selected_plan_index].plan_id)
        return self._updates(
            state,
            "present_to_user",
            persisted_plans=persisted_plans,
            selected_plan_id=selected.plan_id,
        )

    def wait_confirmation(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        status = state.get("status")
        run_id = self._required_uuid(state, "run_id")
        if status in {"failed", "error"}:
            return self._updates(state, "wait_confirmation")

        selected_plan_id = self._required_uuid(state, "selected_plan_id")
        if not state.get("auto_confirm"):
            self.repositories.runs.update_status(run_id, "awaiting_confirmation")
            self._persist_agent_metadata(run_id, self._agent_results(state))
            return self._updates(
                state,
                "wait_confirmation",
                status="awaiting_confirmation",
                action_count=self._action_count(run_id),
            )

        confirmation = HumanConfirmationService(self.repositories.plans).confirm_plan(
            run_id,
            selected_plan_id,
            confirmed_by="workflow",
            source="langgraph-workflow",
        )
        return self._updates(
            state,
            "wait_confirmation",
            confirmation_result=confirmation,
        )

    def saga_execution_engine(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        run_id = self._required_uuid(state, "run_id")
        execution = DeterministicExecutionWorkflow(
            self.repositories.plans,
            self.gateway,
        ).execute_confirmed_plan(
            run_id,
            self._required_uuid(state, "selected_plan_id"),
            langsmith_trace_id=state.get("trace_id"),
        )
        return self._updates(
            state,
            "saga_execution_engine",
            execution_result=execution,
            execution_status=execution.status,
            action_count=self._action_count(run_id),
        )

    def generate_summary_message(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        feedback = DeterministicFeedbackWriter(
            plans=self.repositories.plans,
            runs=self.repositories.runs,
        ).write_execution_feedback(
            self._required_uuid(state, "run_id"),
            self._required_uuid(state, "selected_plan_id"),
        )
        workflow_status = "completed" if feedback.status == "completed" else "failed"
        return self._updates(
            state,
            "generate_summary_message",
            feedback_result=feedback,
            feedback_status=feedback.status,
            status=workflow_status,
        )

    def persist_workflow_timing_summary(
        self,
        run_id: UUID,
        summary: WorkflowTimingSummary,
    ) -> None:
        run = self.repositories.runs.get_by_id(run_id)
        if run is None:
            return
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict):
            workflow = {}
        workflow["timing"] = summary.model_dump(mode="json")
        metadata["workflow"] = workflow
        self.repositories.runs.update_metadata_json(run_id, metadata)

    def _get_or_create_user(self, external_user_id: str | None, display_name: str | None):
        if external_user_id:
            existing = self.repositories.users.get_by_external_id(external_user_id)
            if existing is not None:
                return existing
        return self.repositories.users.create(
            external_id=external_user_id,
            display_name=display_name,
        )

    def _updates(
        self,
        state: WeekendPilotWorkflowState,
        node_name: str,
        **updates: Any,
    ) -> dict[str, Any]:
        return {
            "node_history": [*state.get("node_history", []), node_name],
            **updates,
        }

    def _agent_context(
        self,
        state: WeekendPilotWorkflowState,
        role: str,
    ) -> AgentInvocationContext:
        return AgentInvocationContext(
            run_id=self._required_uuid(state, "run_id"),
            trace_id=state.get("trace_id"),
            role=role,
            agent_version=self._required_text(state, "agent_version"),
            prompt_version=self._required_text(state, "prompt_version"),
            tool_profile=self._required_text(state, "tool_profile"),
            world_profile=self._required_text(state, "world_profile"),
        )

    def _append_agent_result(
        self,
        state: WeekendPilotWorkflowState,
        *results: AgentResult,
    ) -> list[AgentResult]:
        return [*self._agent_results(state), *results]

    def _agent_results(self, state: WeekendPilotWorkflowState) -> list[AgentResult]:
        parsed = []
        for result in state.get("agent_results", []) or []:
            if isinstance(result, AgentResult):
                parsed.append(result)
            elif isinstance(result, dict):
                parsed.append(AgentResult.model_validate(result))
        return parsed

    def _persist_agent_metadata(self, run_id: UUID, agent_results: list[AgentResult]) -> None:
        run = self.repositories.runs.get_by_id(run_id)
        if run is None:
            return
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        metadata["agents"] = sanitized_agent_payload(agent_results)
        self.repositories.runs.update_metadata_json(run_id, metadata)

    def _persist_recovery_metadata(
        self,
        run_id: UUID,
        recovery_attempts: list[RecoveryAttempt],
        max_attempts: int,
    ) -> None:
        run = self.repositories.runs.get_by_id(run_id)
        if run is None:
            return
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict):
            workflow = {}
        workflow["workflow_version"] = self.workflow_version
        workflow["recovery"] = self._sanitize_recovery_metadata({
            "attempt_count": len(recovery_attempts),
            "max_attempts": max_attempts,
            "attempts": [attempt.model_dump(mode="json") for attempt in recovery_attempts],
        })
        metadata["workflow"] = workflow
        self.repositories.runs.update_metadata_json(run_id, metadata)

    def _fail(
        self,
        state: WeekendPilotWorkflowState,
        node_name: str,
        run_id: UUID,
        error_type: str,
        message: str,
        **details: Any,
    ) -> dict[str, Any]:
        self.repositories.runs.update_status(run_id, "failed")
        error_json = {
            "error_type": error_type,
            "message": message,
            "details": self._jsonable(details),
        }
        return self._updates(
            state,
            node_name,
            status="failed",
            error_json=error_json,
            **details,
        )

    def _action_count(self, run_id: UUID) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id)
            )
            or 0
        )

    def _record_observability_error(
        self,
        state: WeekendPilotWorkflowState,
        error_json: dict[str, Any],
    ) -> None:
        run_id = state.get("run_id")
        if run_id is None:
            return
        run = self.repositories.runs.get_by_id(run_id)
        if run is None:
            return
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        metadata["observability"] = {
            "trace_id": state.get("trace_id"),
            "status": "observability_failed",
            "error": error_json,
        }
        self.repositories.runs.update_metadata_json(run_id, metadata)

    def _trace_path(self, trace_buffer_path: Path | str | None) -> Path:
        if trace_buffer_path is not None:
            return Path(trace_buffer_path)
        return Path("var/traces") / f"weekendpilot-{uuid4()}.jsonl"

    def _memory_record(self, memory: Any) -> WorkflowMemoryRecord:
        return WorkflowMemoryRecord(
            memory_id=memory.memory_id,
            memory_type=memory.memory_type,
            key=memory.key,
            value_json=deepcopy(memory.value_json),
            text=memory.text,
            confidence=str(memory.confidence),
            source_run_id=memory.source_run_id,
            source_langsmith_trace_id=memory.source_langsmith_trace_id,
            expires_at=memory.expires_at.isoformat() if memory.expires_at else None,
            status=memory.status,
        )

    def _candidate_blackboard(self, collection: Any) -> CandidateBlackboard:
        return CandidateBlackboard(
            activity_candidates=[
                CandidateBlackboardEntry(candidate=candidate)
                for candidate in collection.activity_candidates
            ],
            dining_candidates=[
                CandidateBlackboardEntry(candidate=candidate)
                for candidate in collection.dining_candidates
            ],
            other_candidates=[
                CandidateBlackboardEntry(candidate=candidate)
                for candidate in collection.other_candidates
            ],
        )

    def _screen_candidate_blackboard(
        self,
        blackboard: CandidateBlackboard,
        enrichment: Any,
    ) -> CandidateBlackboard:
        enriched_by_id = {
            item.candidate.candidate_id: item
            for item in [
                *enrichment.enriched_activity_candidates,
                *enrichment.enriched_dining_candidates,
                *enrichment.enriched_other_candidates,
            ]
        }

        def screen(entry: CandidateBlackboardEntry) -> CandidateBlackboardEntry:
            enriched = enriched_by_id.get(entry.candidate.candidate_id)
            if enriched is None:
                return entry
            failed_codes = [
                self._tool_failure_code(tool_result.error_json)
                for tool_result in enriched.failed_tool_results
            ]
            failed_codes = [code for code in failed_codes if code]
            return entry.model_copy(
                update={
                    "suitability_status": "screened_out" if failed_codes else "screened_in",
                    "evidence_tool_names": [
                        tool_result.tool_name for tool_result in enriched.tool_results
                    ],
                    "risk_codes": failed_codes,
                }
            )

        activity = [screen(entry) for entry in blackboard.activity_candidates]
        dining = [screen(entry) for entry in blackboard.dining_candidates]
        other = [screen(entry) for entry in blackboard.other_candidates]
        return CandidateBlackboard(
            activity_candidates=activity,
            dining_candidates=dining,
            other_candidates=other,
            screened_candidate_ids=[
                entry.candidate.candidate_id
                for entry in [*activity, *dining, *other]
                if entry.suitability_status == "screened_in"
            ],
        )

    def _route_time_summary(self, enrichment: Any, drafts: Any) -> RouteTimeSummary:
        feasible_count = sum(1 for draft in drafts.drafts if draft.feasibility.is_feasible)
        return RouteTimeSummary(
            route_count=len(enrichment.route_matrix),
            feasible_draft_count=feasible_count,
            infeasible_draft_count=max(len(drafts.drafts) - feasible_count, 0),
            route_matrix=list(enrichment.route_matrix),
        )

    def _tool_failure_code(self, error_json: dict[str, Any] | None) -> str | None:
        if not isinstance(error_json, dict):
            return None
        code = error_json.get("error_type") or error_json.get("code")
        return str(code) if code else None

    def _recovery_attempts(self, state: WeekendPilotWorkflowState) -> list[RecoveryAttempt]:
        attempts = []
        for attempt in state.get("recovery_attempts", []) or []:
            if isinstance(attempt, RecoveryAttempt):
                attempts.append(attempt)
            elif isinstance(attempt, dict):
                attempts.append(RecoveryAttempt.model_validate(attempt))
        return attempts

    def _recovery_error_json(self, route_result: Any) -> dict[str, Any]:
        attempt = route_result.attempt
        details = (
            self._sanitize_recovery_metadata(attempt.model_dump(mode="json"))
            if attempt is not None
            else {}
        )
        return {
            "error_type": route_result.error_type or "recovery_stopped",
            "message": route_result.message or "Recovery stopped safely.",
            "details": details,
        }

    def _sanitize_recovery_metadata(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized = {}
            for key, child in value.items():
                if isinstance(key, str) and self._is_sensitive_recovery_text(key):
                    continue
                sanitized[key] = self._sanitize_recovery_metadata(child)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_recovery_metadata(item) for item in value]
        if isinstance(value, str) and self._is_sensitive_recovery_text(value):
            return "[redacted]"
        return value

    def _is_sensitive_recovery_text(self, value: str) -> bool:
        normalized = value.casefold()
        return any(fragment in normalized for fragment in _RECOVERY_SENSITIVE_FRAGMENTS)

    def _required_uuid(self, state: WeekendPilotWorkflowState, key: str) -> UUID:
        value = state.get(key)
        if not isinstance(value, UUID):
            raise WorkflowError(f"Workflow state is missing UUID field {key!r}.")
        return value

    def _required_text(self, state: WeekendPilotWorkflowState, key: str) -> str:
        value = state.get(key)
        if not isinstance(value, str) or not value:
            raise WorkflowError(f"Workflow state is missing text field {key!r}.")
        return value

    def _required_value(self, state: WeekendPilotWorkflowState, key: str) -> Any:
        value = state.get(key)
        if value is None:
            raise WorkflowError(f"Workflow state is missing field {key!r}.")
        return value

    def _error_json(self, error_type: str, message: str, exc: Exception) -> dict[str, Any]:
        return {
            "error_type": error_type,
            "message": message,
            "exception_type": type(exc).__name__,
        }

    def _jsonable(self, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: self._jsonable(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        return value


class _Repositories:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)
        self.runs = AgentRunRepository(session)
        self.memory = MemoryItemRepository(session)
        self.tool_events = ToolEventRepository(session)
        self.action_ledger = ActionLedgerRepository(session)
        self.plans = PlanRepository(session)
