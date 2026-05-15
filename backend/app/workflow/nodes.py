from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.confirmation import HumanConfirmationService
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicItineraryGenerator,
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
from backend.app.review import FinalReviewGate
from backend.app.tool_gateway import ToolGateway
from backend.app.workflow.dependencies import WeekendPilotWorkflowDependencies
from backend.app.workflow.errors import WorkflowError
from backend.app.workflow.schemas import WeekendPilotWorkflowState


class WeekendPilotWorkflowNodes:
    workflow_version = "langgraph_workflow_skeleton_v1"

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
        )
        self.recorder = ObservabilityRecorder(
            runs=self.repositories.runs,
            tool_events=self.repositories.tool_events,
            action_ledger=self.repositories.action_ledger,
            plans=self.repositories.plans,
            local_buffer=LocalTraceBuffer(self._trace_path(dependencies.trace_buffer_path)),
        )

    def initialize_run(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
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
            "initialize_run",
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
            self._memory_json(memory)
            for memory in self.repositories.memory.list_active_for_user(user_id)
        ]
        return self._updates(state, "load_memory", active_memories=memories)

    def build_query_plan(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        query_plan = DeterministicQueryPlanner().build(
            self._required_value(state, "parsed_intent"),
            provider_profile=self._required_text(state, "tool_profile"),
        )
        return self._updates(state, "build_query_plan", query_plan=query_plan)

    def collect_candidates(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        collection = QueryPlanExecutor(self.gateway).execute_initial_calls(
            self._required_value(state, "query_plan"),
            self._required_uuid(state, "run_id"),
            langsmith_trace_id=state.get("trace_id"),
        )
        return self._updates(state, "collect_candidates", candidate_collection=collection)

    def enrich_candidates(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        enrichment = CandidateEnricher(self.gateway).enrich(
            self._required_value(state, "query_plan"),
            self._required_value(state, "candidate_collection"),
            langsmith_trace_id=state.get("trace_id"),
        )
        return self._updates(state, "enrich_candidates", enrichment_result=enrichment)

    def generate_itinerary(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        drafts = DeterministicItineraryGenerator().generate(
            self._required_value(state, "query_plan"),
            self._required_value(state, "enrichment_result"),
        )
        return self._updates(state, "generate_itinerary", itinerary_drafts=drafts)

    def final_review(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        run_id = self._required_uuid(state, "run_id")
        review = FinalReviewGate().review(
            self._required_value(state, "query_plan"),
            self._required_value(state, "enrichment_result"),
            self._required_value(state, "itinerary_drafts"),
            pre_confirmation_action_count=self._action_count(run_id),
        )
        return self._updates(state, "final_review", final_review_result=review)

    def persist_and_select_plan(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        review = self._required_value(state, "final_review_result")
        drafts = self._required_value(state, "itinerary_drafts")
        run_id = self._required_uuid(state, "run_id")
        persistence = ReviewedPlanPersistenceService(self.repositories.plans)
        persisted = persistence.persist_reviewed_drafts(review, drafts)
        persisted_plans = list(persisted.persisted_plans)

        if not review.safe_to_present:
            return self._fail(
                state,
                "persist_and_select_plan",
                run_id,
                "final_review_blocked",
                "Final review blocked presentation for this run.",
                persisted_plans=persisted_plans,
            )
        if not persisted_plans:
            return self._fail(
                state,
                "persist_and_select_plan",
                run_id,
                "no_persisted_plans",
                "No safe reviewed plans were persisted for this run.",
                persisted_plans=persisted_plans,
            )

        selected_plan_index = int(state.get("selected_plan_index") or 0)
        if selected_plan_index >= len(persisted_plans):
            return self._fail(
                state,
                "persist_and_select_plan",
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
            "persist_and_select_plan",
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

    def execute(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
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
            "execute",
            execution_result=execution,
            execution_status=execution.status,
            action_count=self._action_count(run_id),
        )

    def write_feedback(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
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
            "write_feedback",
            feedback_result=feedback,
            feedback_status=feedback.status,
            status=workflow_status,
        )

    def record_observability(self, state: WeekendPilotWorkflowState) -> dict[str, Any]:
        try:
            observability = self.recorder.record_run_summary(
                self._required_value(state, "trace_context")
            )
        except Exception as exc:
            error_json = self._error_json("observability_failed", str(exc), exc)
            self._record_observability_error(state, error_json)
            return self._updates(
                state,
                "record_observability",
                observability_status="observability_failed",
                error_json=state.get("error_json") or {"observability": error_json},
            )

        status = "recorded" if observability.local_buffer_written else observability.status
        return self._updates(
            state,
            "record_observability",
            observability_result=observability,
            observability_status=status,
        )

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

    def _memory_json(self, memory: Any) -> dict[str, Any]:
        return {
            "memory_id": str(memory.memory_id),
            "memory_type": memory.memory_type,
            "key": memory.key,
            "value_json": deepcopy(memory.value_json),
            "text": memory.text,
            "confidence": str(memory.confidence),
            "source_run_id": str(memory.source_run_id) if memory.source_run_id else None,
            "source_langsmith_trace_id": memory.source_langsmith_trace_id,
            "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
            "status": memory.status,
        }

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
