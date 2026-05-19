from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.confirmation import HumanConfirmationService, PlanConfirmationError
from backend.app.execution import DeterministicExecutionWorkflow, ExecutionWorkflowError
from backend.app.feedback import DeterministicFeedbackWriter, FeedbackWriterError
from backend.app.models.runtime import ActionLedger, AgentRun, Plan
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder, RunTraceContext
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache
from backend.app.tool_gateway import ToolGateway
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowRunner,
)
from backend.app.demo.schemas import (
    DemoConfirmRunRequest,
    DemoDeclineRunRequest,
    DemoPlanPreview,
    DemoRunSummary,
    DemoStartRunRequest,
)


DEMO_API_VERSION = "web_demo_api_v1"
_FORBIDDEN_KEY_FRAGMENTS = (
    "action_id",
    "tool_event_id",
    "event_id",
    "idempotency_key",
    "confirmation_id",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
)


class DemoServiceError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def sanitize_demo_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return sanitize_demo_payload(value.model_dump(mode="json"))
    if isinstance(value, dict):
        sanitized = {}
        for key, child in value.items():
            if isinstance(key, str) and _is_forbidden_key(key):
                continue
            sanitized[key] = sanitize_demo_payload(child)
        return sanitized
    if isinstance(value, list):
        return [sanitize_demo_payload(item) for item in value]
    return value


def _is_forbidden_key(key: str) -> bool:
    normalized = key.casefold()
    return any(fragment in normalized for fragment in _FORBIDDEN_KEY_FRAGMENTS)


class DemoWorkflowService:
    def __init__(
        self,
        session: Session,
        cache: JsonRedisCache,
        rate_limiter: FixedWindowRateLimiter,
        trace_buffer_path: str | Path | None,
    ) -> None:
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.trace_buffer_path = trace_buffer_path

    def start_run(self, request: DemoStartRunRequest) -> DemoRunSummary:
        runner = WeekendPilotWorkflowRunner(
            WeekendPilotWorkflowDependencies(
                session=self.session,
                cache=self.cache,
                rate_limiter=self.rate_limiter,
                trace_buffer_path=self.trace_buffer_path,
            )
        )
        result = runner.run(
            WeekendPilotWorkflowRequest(
                user_input=request.user_input,
                external_user_id=request.external_user_id,
                display_name=request.display_name,
                case_id=request.case_id,
                tool_profile="mock_world",
                world_profile="family_afternoon",
                agent_version="agent-v1",
                prompt_version="prompt-v1",
                auto_confirm=False,
                selected_plan_index=request.selected_plan_index,
            )
        )
        if result.run_id is None:
            raise DemoServiceError(500, "Demo workflow did not create a run.")

        runs = AgentRunRepository(self.session)
        run = runs.get_by_id(result.run_id)
        if run is None:
            raise DemoServiceError(500, "Demo workflow run disappeared.")

        metadata = self._metadata(run)
        metadata["demo"] = {
            "api_version": DEMO_API_VERSION,
            "trace_id": result.trace_id,
            "initial_status": result.status,
            "initial_node_history": list(result.node_history),
            "initial_error": sanitize_demo_payload(result.error_json),
            "continuation_history": [],
        }
        runs.update_metadata_json(result.run_id, metadata)
        self.session.commit()
        return self.build_summary(result.run_id)

    def get_run(self, run_id: UUID) -> DemoRunSummary:
        return self.build_summary(run_id)

    def confirm_run(self, run_id: UUID, request: DemoConfirmRunRequest) -> DemoRunSummary:
        runs = AgentRunRepository(self.session)
        run = self._load_run(runs, run_id)
        plan = self._resolve_plan(run_id, request.plan_id)

        if self._has_execution_and_feedback(plan):
            return self.build_summary(run_id)
        if plan.status == "declined":
            raise DemoServiceError(409, "Declined plans cannot be confirmed.")

        trace_id = self._trace_id(run)
        plans = PlanRepository(self.session)
        try:
            HumanConfirmationService(plans).confirm_plan(
                run_id,
                plan.plan_id,
                confirmed_by=request.confirmed_by,
                source="web-demo-api",
            )
            self._append_continuation_history(run_id, ["confirm_plan"])

            gateway = self._gateway()
            execution = DeterministicExecutionWorkflow(plans, gateway).execute_confirmed_plan(
                run_id,
                plan.plan_id,
                langsmith_trace_id=trace_id,
            )
            self._append_continuation_history(run_id, ["saga_execution_engine"])

            DeterministicFeedbackWriter(
                plans=plans,
                runs=runs,
            ).write_execution_feedback(run_id, plan.plan_id)
            self._append_continuation_history(run_id, ["generate_summary_message"])
            self._record_observability(run_id, trace_id)

            if execution.status not in {"succeeded", "partially_succeeded", "failed", "skipped"}:
                raise DemoServiceError(500, "Demo execution returned an unsupported status.")
        except PlanConfirmationError as exc:
            raise DemoServiceError(409, str(exc)) from exc
        except (ExecutionWorkflowError, FeedbackWriterError) as exc:
            raise DemoServiceError(409, str(exc)) from exc

        self.session.commit()
        return self.build_summary(run_id)

    def decline_run(self, run_id: UUID, request: DemoDeclineRunRequest) -> DemoRunSummary:
        runs = AgentRunRepository(self.session)
        self._load_run(runs, run_id)
        plan = self._resolve_plan(run_id, request.plan_id)
        if plan.status in {"confirmed", "executed", "partially_executed", "execution_failed", "execution_skipped"}:
            raise DemoServiceError(409, "Confirmed or executed plans cannot be declined.")

        try:
            HumanConfirmationService(PlanRepository(self.session)).decline_plan(
                run_id,
                plan.plan_id,
                declined_by=request.declined_by,
                source="web-demo-api",
                reason=request.reason,
            )
        except PlanConfirmationError as exc:
            raise DemoServiceError(409, str(exc)) from exc

        runs.update_status(run_id, "declined")
        self._append_continuation_history(run_id, ["decline_plan"])
        self.session.commit()
        return self.build_summary(run_id)

    def build_summary(self, run_id: UUID) -> DemoRunSummary:
        runs = AgentRunRepository(self.session)
        run = self._load_run(runs, run_id)
        plans = PlanRepository(self.session)
        selected_plan = plans.get_selected_for_run(run_id)
        plan_rows = plans.list_for_run(run_id)
        selected_plan_json = self._plan_json(selected_plan) if selected_plan is not None else {}
        execution = selected_plan_json.get("execution") if isinstance(selected_plan_json, dict) else None
        feedback = selected_plan_json.get("feedback") if isinstance(selected_plan_json, dict) else None

        return DemoRunSummary(
            run_id=run.run_id,
            status=run.status,
            selected_plan_id=selected_plan.plan_id if selected_plan is not None else None,
            plans=[self._plan_preview(plan) for plan in plan_rows],
            action_count=self._action_count(run_id),
            execution_status=execution.get("status") if isinstance(execution, dict) else None,
            feedback_status=feedback.get("status") if isinstance(feedback, dict) else None,
            error=self._error(run),
        )

    def _gateway(self) -> ToolGateway:
        return ToolGateway(
            registry=build_mock_world_registry(),
            tool_events=ToolEventRepository(self.session),
            action_ledger=ActionLedgerRepository(self.session),
            cache=self.cache,
            rate_limiter=self.rate_limiter,
        )

    def _resolve_plan(self, run_id: UUID, requested_plan_id: UUID | None) -> Plan:
        plans = PlanRepository(self.session)
        if requested_plan_id is None:
            selected = plans.get_selected_for_run(run_id)
            if selected is None:
                raise DemoServiceError(409, "Run does not have a selected plan.")
            return selected

        plan = plans.get_by_id(requested_plan_id)
        if plan is None or plan.run_id != run_id:
            raise DemoServiceError(404, "Plan was not found for this run.")
        if plan.selected:
            return plan
        if plan.status != "reviewed":
            raise DemoServiceError(409, "Requested plan cannot be selected for confirmation.")

        selected = plans.select_for_run(run_id, requested_plan_id)
        if selected is None:
            raise DemoServiceError(404, "Plan was not found for this run.")
        return selected

    def _record_observability(self, run_id: UUID, trace_id: str | None) -> None:
        if trace_id is None:
            self._record_observability_failure(run_id, "missing_trace_id", "Run has no trace ID.")
            return

        runs = AgentRunRepository(self.session)
        run = self._load_run(runs, run_id)
        context = RunTraceContext(
            run_id=run.run_id,
            trace_id=trace_id,
            project_name="weekend-pilot",
            agent_version=run.agent_version,
            prompt_version=run.prompt_version,
            tool_profile=run.tool_profile,
            world_profile=run.world_profile,
            failure_profile=run.failure_profile,
            case_id=run.case_id,
            metadata=deepcopy(self._metadata(run)),
        )
        recorder = ObservabilityRecorder(
            runs=runs,
            tool_events=ToolEventRepository(self.session),
            action_ledger=ActionLedgerRepository(self.session),
            plans=PlanRepository(self.session),
            local_buffer=LocalTraceBuffer(self._trace_path(run_id)),
        )
        try:
            recorder.record_run_summary(context)
        except Exception as exc:
            self._record_observability_failure(
                run_id,
                "observability_failed",
                str(exc),
                exception_type=type(exc).__name__,
            )

    def _record_observability_failure(
        self,
        run_id: UUID,
        code: str,
        message: str,
        **details: Any,
    ) -> None:
        runs = AgentRunRepository(self.session)
        run = runs.get_by_id(run_id)
        if run is None:
            return
        metadata = self._metadata(run)
        metadata["observability"] = sanitize_demo_payload(
            {
                "status": "observability_failed",
                "error": {
                    "code": code,
                    "message": message,
                    **details,
                },
            }
        )
        runs.update_metadata_json(run_id, metadata)

    def _append_continuation_history(self, run_id: UUID, steps: list[str]) -> None:
        runs = AgentRunRepository(self.session)
        run = runs.get_by_id(run_id)
        if run is None:
            return
        metadata = self._metadata(run)
        demo = metadata.get("demo")
        if not isinstance(demo, dict):
            demo = {}
        history = demo.get("continuation_history")
        if not isinstance(history, list):
            history = []
        demo["continuation_history"] = [*history, *steps]
        metadata["demo"] = demo
        runs.update_metadata_json(run_id, metadata)

    def _plan_preview(self, plan: Plan) -> DemoPlanPreview:
        plan_json = self._plan_json(plan)
        draft = plan_json.get("draft") if isinstance(plan_json.get("draft"), dict) else {}
        confirmation = plan_json.get("confirmation")
        execution = plan_json.get("execution")
        feedback = plan_json.get("feedback")
        return DemoPlanPreview(
            plan_id=plan.plan_id,
            status=plan.status,
            selected=plan.selected,
            title=self._text_or_none(draft.get("title")),
            summary=self._text_or_none(draft.get("summary")),
            activity=sanitize_demo_payload(draft.get("activity")) if draft.get("activity") is not None else None,
            dining=sanitize_demo_payload(draft.get("dining")) if draft.get("dining") is not None else None,
            timeline=sanitize_demo_payload(draft.get("timeline") or []),
            route=sanitize_demo_payload(draft.get("route")) if draft.get("route") is not None else None,
            feasibility=(
                sanitize_demo_payload(draft.get("feasibility"))
                if draft.get("feasibility") is not None
                else None
            ),
            proposed_actions=sanitize_demo_payload(draft.get("proposed_actions") or []),
            confirmation=sanitize_demo_payload(confirmation) if isinstance(confirmation, dict) else None,
            execution=sanitize_demo_payload(execution) if isinstance(execution, dict) else None,
            feedback=sanitize_demo_payload(feedback) if isinstance(feedback, dict) else None,
        )

    def _load_run(self, runs: AgentRunRepository, run_id: UUID) -> AgentRun:
        run = runs.get_by_id(run_id)
        if run is None:
            raise DemoServiceError(404, "Demo run was not found.")
        return run

    def _has_execution_and_feedback(self, plan: Plan) -> bool:
        plan_json = self._plan_json(plan)
        return isinstance(plan_json.get("execution"), dict) and isinstance(plan_json.get("feedback"), dict)

    def _plan_json(self, plan: Plan | None) -> dict[str, Any]:
        if plan is None or not isinstance(plan.plan_json, dict):
            return {}
        return plan.plan_json

    def _metadata(self, run: AgentRun) -> dict[str, Any]:
        return deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}

    def _trace_id(self, run: AgentRun) -> str | None:
        metadata = self._metadata(run)
        demo = metadata.get("demo")
        if isinstance(demo, dict) and isinstance(demo.get("trace_id"), str):
            return demo["trace_id"]
        observability = metadata.get("observability")
        if isinstance(observability, dict) and isinstance(observability.get("trace_id"), str):
            return observability["trace_id"]
        return None

    def _error(self, run: AgentRun) -> dict[str, Any] | None:
        metadata = self._metadata(run)
        demo = metadata.get("demo")
        if isinstance(demo, dict) and isinstance(demo.get("initial_error"), dict):
            return sanitize_demo_payload(demo["initial_error"])
        return None

    def _action_count(self, run_id: UUID) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id)
            )
            or 0
        )

    def _trace_path(self, run_id: UUID) -> Path:
        if self.trace_buffer_path is not None:
            return Path(self.trace_buffer_path)
        return Path("var/traces") / f"weekendpilot-demo-{run_id}.jsonl"

    def _text_or_none(self, value: Any) -> str | None:
        return value if isinstance(value, str) else None
