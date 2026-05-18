from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.app.models.runtime import ActionLedger
from backend.app.observability.errors import ObservabilityError
from backend.app.observability.langsmith_recorder import LangSmithRecorder
from backend.app.observability.local_buffer import LocalTraceBuffer
from backend.app.observability.redaction import sanitize_trace_payload
from backend.app.observability.schemas import RunTraceContext, TraceRecordResult
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
)


class ObservabilityRecorder:
    recorder_version = "observability_recorder_v1"
    schema_version = "weekendpilot_trace_v1"

    def __init__(
        self,
        runs: AgentRunRepository,
        tool_events: ToolEventRepository,
        action_ledger: ActionLedgerRepository,
        plans: PlanRepository,
        local_buffer: LocalTraceBuffer,
        langsmith: LangSmithRecorder | None = None,
    ) -> None:
        self.runs = runs
        self.tool_events = tool_events
        self.action_ledger = action_ledger
        self.plans = plans
        self.local_buffer = local_buffer
        self.langsmith = langsmith

    def build_context(self, run_id: UUID) -> RunTraceContext:
        run = self.runs.get_by_id(run_id)
        if run is None:
            raise ObservabilityError(f"Agent run {run_id} does not exist.")

        metadata = run.metadata_json if isinstance(run.metadata_json, dict) else {}
        return RunTraceContext(
            run_id=run.run_id,
            trace_id=str(uuid4()),
            project_name="weekend-pilot",
            agent_version=run.agent_version,
            prompt_version=run.prompt_version,
            tool_profile=run.tool_profile,
            world_profile=run.world_profile,
            failure_profile=run.failure_profile,
            case_id=run.case_id,
            metadata=deepcopy(metadata),
        )

    def record_run_summary(self, context: RunTraceContext) -> TraceRecordResult:
        run = self.runs.get_by_id(context.run_id)
        if run is None:
            raise ObservabilityError(f"Agent run {context.run_id} does not exist.")

        payload = self._summary_payload(context)
        local_result = self.local_buffer.write(payload)
        langsmith_status = (
            self.langsmith.post_summary(payload)
            if self.langsmith is not None
            else None
        )
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        metadata["observability"] = sanitize_trace_payload(
            {
                "schema_version": self.schema_version,
                "recorder_version": self.recorder_version,
                "trace_id": context.trace_id,
                "status": (
                    "observability_failed"
                    if local_result.status == "failed" or (langsmith_status and langsmith_status.error)
                    else "completed"
                ),
                "local_buffer": {
                    "written": local_result.local_buffer_written,
                    "path": local_result.local_buffer_path,
                    "error": local_result.error_json,
                },
                "langsmith": {
                    "enabled": langsmith_status.enabled if langsmith_status else False,
                    "posted": langsmith_status.posted if langsmith_status else False,
                    "error": langsmith_status.error if langsmith_status else None,
                },
            }
        )
        self.runs.update_metadata_json(context.run_id, metadata)

        return TraceRecordResult(
            run_id=context.run_id,
            trace_id=context.trace_id,
            status=metadata["observability"]["status"],
            local_buffer_written=local_result.local_buffer_written,
            local_buffer_path=local_result.local_buffer_path,
            langsmith_enabled=langsmith_status.enabled if langsmith_status else False,
            langsmith_posted=langsmith_status.posted if langsmith_status else False,
            error_json=local_result.error_json,
            recorder_version=self.recorder_version,
        )

    def _summary_payload(self, context: RunTraceContext) -> dict[str, Any]:
        tool_events = self.tool_events.list_for_run(context.run_id)
        action_count = self._action_count(context.run_id)
        selected_plan = self.plans.get_selected_for_run(context.run_id)
        plan_json = selected_plan.plan_json if selected_plan is not None and isinstance(selected_plan.plan_json, dict) else {}
        feedback = plan_json.get("feedback") if isinstance(plan_json, dict) else None
        run = self.runs.get_by_id(context.run_id)
        metadata = (
            deepcopy(run.metadata_json)
            if run is not None and isinstance(run.metadata_json, dict)
            else deepcopy(context.metadata)
        )

        return sanitize_trace_payload(
            {
                "schema_version": self.schema_version,
                "recorder_version": self.recorder_version,
                "trace_id": context.trace_id,
                "run_id": str(context.run_id),
                "project_name": context.project_name,
                "status": self._run_status(context.run_id),
                "tool_event_count": len(tool_events),
                "action_count": action_count,
                "plan_status": selected_plan.status if selected_plan is not None else None,
                "feedback_status": feedback.get("status") if isinstance(feedback, dict) else None,
                "langsmith": {
                    "enabled": self.langsmith.enabled if self.langsmith is not None else False,
                    "posted": False,
                    "error": None,
                },
                "metadata": metadata,
            }
        )

    def _run_status(self, run_id: UUID) -> str | None:
        run = self.runs.get_by_id(run_id)
        return run.status if run is not None else None

    def _action_count(self, run_id: UUID) -> int:
        statement = select(ActionLedger).where(ActionLedger.run_id == run_id)
        return len(list(self.action_ledger.session.scalars(statement).all()))
