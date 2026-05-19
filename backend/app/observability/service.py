from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.runtime import ActionLedger, AgentRun, Plan, ToolEvent
from backend.app.observability.redaction import sanitize_trace_payload
from backend.app.observability.schemas import (
    InternalObservabilityRunSummary,
    InternalObservabilitySummary,
)
from backend.app.observability.summary import RunSummary, load_run_summary
from backend.app.repositories import AgentRunRepository, PlanRepository
from backend.app.workflow.timing import WorkflowTimingSummary


class InternalObservabilityRunNotFoundError(LookupError):
    """Raised when an internal observability run cannot be found."""


class InternalObservabilityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_summary(self, run_id: UUID) -> InternalObservabilityRunSummary:
        run = AgentRunRepository(self.session).get_by_id(run_id)
        if run is None:
            raise InternalObservabilityRunNotFoundError(f"Run {run_id} was not found.")

        selected_plan = PlanRepository(self.session).get_selected_for_run(run_id)
        selected_plan_json = self._plan_json(selected_plan)
        metadata = self._metadata(run)
        canonical_summary = load_run_summary(metadata)

        return InternalObservabilityRunSummary(
            run_id=run.run_id,
            status=run.status,
            trace_id=self._trace_id(metadata, canonical_summary),
            case_id=run.case_id,
            agent_version=run.agent_version,
            prompt_version=run.prompt_version,
            tool_profile=run.tool_profile,
            world_profile=run.world_profile,
            failure_profile=run.failure_profile,
            created_at=run.created_at,
            updated_at=run.updated_at,
            tool_event_count=self._tool_event_count(run.run_id, canonical_summary),
            action_count=self._action_count(run.run_id, canonical_summary),
            execution_status=self._execution_status(selected_plan_json, canonical_summary),
            feedback_status=self._feedback_status(selected_plan_json, canonical_summary),
            observability_status=self._observability_status(metadata),
            agent_roles=self._agent_roles(metadata, canonical_summary),
            node_history=self._node_history(metadata),
            workflow_timing_summary=self._workflow_timing_summary(metadata, canonical_summary),
            observability_summary=self._observability_summary(metadata),
        )

    def _metadata(self, run: AgentRun) -> dict[str, Any]:
        return deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}

    def _plan_json(self, plan: Plan | None) -> dict[str, Any]:
        if plan is None or not isinstance(plan.plan_json, dict):
            return {}
        return deepcopy(plan.plan_json)

    def _trace_id(self, metadata: dict[str, Any], canonical_summary: RunSummary | None) -> str | None:
        if canonical_summary is not None:
            return canonical_summary.trace_id
        demo = metadata.get("demo")
        if isinstance(demo, dict) and isinstance(demo.get("trace_id"), str):
            return demo["trace_id"]
        observability = metadata.get("observability")
        if isinstance(observability, dict) and isinstance(observability.get("trace_id"), str):
            return observability["trace_id"]
        return None

    def _node_history(self, metadata: dict[str, Any]) -> list[str]:
        demo = metadata.get("demo")
        if not isinstance(demo, dict):
            return []
        initial = demo.get("initial_node_history")
        continuation = demo.get("continuation_history")
        return [
            item
            for item in [
                *(initial if isinstance(initial, list) else []),
                *(continuation if isinstance(continuation, list) else []),
            ]
            if isinstance(item, str)
        ]

    def _agent_roles(self, metadata: dict[str, Any], canonical_summary: RunSummary | None) -> list[str]:
        if canonical_summary is not None:
            return list(canonical_summary.agent_roles)
        agents = metadata.get("agents")
        if not isinstance(agents, dict):
            return []
        results = agents.get("results")
        if not isinstance(results, list):
            return []
        return [
            result["role"]
            for result in results
            if isinstance(result, dict) and isinstance(result.get("role"), str)
        ]

    def _workflow_timing_summary(
        self,
        metadata: dict[str, Any],
        canonical_summary: RunSummary | None,
    ) -> WorkflowTimingSummary | None:
        if canonical_summary is not None:
            timing = canonical_summary.workflow_timing_summary
            if isinstance(timing, dict):
                try:
                    return WorkflowTimingSummary.model_validate(timing)
                except ValidationError:
                    return None
            return None
        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict) or not isinstance(workflow.get("timing"), dict):
            return None
        try:
            return WorkflowTimingSummary.model_validate(workflow["timing"])
        except ValidationError:
            return None

    def _observability_summary(self, metadata: dict[str, Any]) -> InternalObservabilitySummary:
        observability = metadata.get("observability")
        if not isinstance(observability, dict):
            return InternalObservabilitySummary()

        local_buffer = observability.get("local_buffer")
        langsmith = observability.get("langsmith")
        local_buffer_error = (
            sanitize_trace_payload(local_buffer.get("error"))
            if isinstance(local_buffer, dict) and isinstance(local_buffer.get("error"), dict)
            else None
        )
        langsmith_error = (
            sanitize_trace_payload(langsmith.get("error"))
            if isinstance(langsmith, dict) and langsmith.get("error") is not None
            else None
        )

        return InternalObservabilitySummary(
            trace_id=observability.get("trace_id") if isinstance(observability.get("trace_id"), str) else None,
            status=observability.get("status") if isinstance(observability.get("status"), str) else None,
            local_buffer_written=(
                local_buffer.get("written")
                if isinstance(local_buffer, dict) and isinstance(local_buffer.get("written"), bool)
                else None
            ),
            langsmith_enabled=(
                langsmith.get("enabled")
                if isinstance(langsmith, dict) and isinstance(langsmith.get("enabled"), bool)
                else None
            ),
            langsmith_posted=(
                langsmith.get("posted")
                if isinstance(langsmith, dict) and isinstance(langsmith.get("posted"), bool)
                else None
            ),
            local_buffer_error=local_buffer_error,
            langsmith_error=langsmith_error,
        )

    def _execution_status(
        self,
        selected_plan_json: dict[str, Any],
        canonical_summary: RunSummary | None,
    ) -> str | None:
        if canonical_summary is not None:
            return canonical_summary.execution_status
        execution = selected_plan_json.get("execution")
        return execution.get("status") if isinstance(execution, dict) and isinstance(execution.get("status"), str) else None

    def _feedback_status(
        self,
        selected_plan_json: dict[str, Any],
        canonical_summary: RunSummary | None,
    ) -> str | None:
        if canonical_summary is not None:
            return canonical_summary.feedback_status
        feedback = selected_plan_json.get("feedback")
        return feedback.get("status") if isinstance(feedback, dict) and isinstance(feedback.get("status"), str) else None

    def _observability_status(self, metadata: dict[str, Any]) -> str | None:
        observability = metadata.get("observability")
        return (
            observability.get("status")
            if isinstance(observability, dict) and isinstance(observability.get("status"), str)
            else None
        )

    def _tool_event_count(self, run_id: UUID, canonical_summary: RunSummary | None) -> int:
        if canonical_summary is not None:
            return canonical_summary.tool_event_count
        return int(
            self.session.scalar(select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run_id))
            or 0
        )

    def _action_count(self, run_id: UUID, canonical_summary: RunSummary | None) -> int:
        if canonical_summary is not None:
            return canonical_summary.action_count
        return int(
            self.session.scalar(select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id))
            or 0
        )
