from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from backend.app.agents import AgentResult
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.workflow.dependencies import WeekendPilotWorkflowDependencies
from backend.app.workflow.graph import build_weekend_pilot_graph
from backend.app.workflow.nodes import WeekendPilotWorkflowNodes
from backend.app.workflow.schemas import (
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowResult,
    WorkflowStatus,
)
from backend.app.workflow.state import CandidateBlackboard, RouteTimeSummary, WeekendPilotWorkflowState


class WeekendPilotWorkflowRunner:
    def __init__(self, dependencies: WeekendPilotWorkflowDependencies) -> None:
        self.dependencies = dependencies

    def run(self, request: WeekendPilotWorkflowRequest) -> WeekendPilotWorkflowResult:
        unsupported = self._unsupported_profile_result(request)
        if unsupported is not None:
            return unsupported

        try:
            nodes = WeekendPilotWorkflowNodes(self.dependencies)
            graph = build_weekend_pilot_graph(nodes)
            final_state = graph.invoke(self._initial_state(request))
            return self._to_result(final_state)
        except Exception as exc:
            return WeekendPilotWorkflowResult(
                run_id=None,
                trace_id=None,
                status="error",
                error_json={
                    "error_type": "workflow_exception",
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                },
            )

    def _unsupported_profile_result(
        self,
        request: WeekendPilotWorkflowRequest,
    ) -> WeekendPilotWorkflowResult | None:
        if request.tool_profile == "mock_world" and request.world_profile == "family_afternoon":
            return None

        return WeekendPilotWorkflowResult(
            run_id=None,
            trace_id=None,
            status="error",
            error_json={
                "error_type": "unsupported_profile",
                "message": (
                    "WeekendPilot workflow supports only "
                    "tool_profile='mock_world' and world_profile='family_afternoon'."
                ),
                "tool_profile": request.tool_profile,
                "world_profile": request.world_profile,
            },
        )

    def _initial_state(self, request: WeekendPilotWorkflowRequest) -> WeekendPilotWorkflowState:
        return WeekendPilotWorkflowState(
            user_input=request.user_input,
            external_user_id=request.external_user_id,
            display_name=request.display_name,
            case_id=request.case_id,
            agent_version=request.agent_version,
            prompt_version=request.prompt_version,
            tool_profile=request.tool_profile,
            world_profile=request.world_profile,
            failure_profile=request.failure_profile,
            auto_confirm=request.auto_confirm,
            selected_plan_index=request.selected_plan_index,
            run_id=None,
            user_id=None,
            trace_id=None,
            selected_plan_id=None,
            active_memories=[],
            candidate_blackboard=CandidateBlackboard(),
            route_time_summary=RouteTimeSummary(),
            agent_results=[],
            persisted_plans=[],
            node_history=[],
            tool_event_count=0,
            action_count=0,
            execution_status=None,
            feedback_status=None,
            observability_status=None,
            error_json=None,
        )

    def _to_result(self, state: WeekendPilotWorkflowState | dict[str, Any]) -> WeekendPilotWorkflowResult:
        run_id = self._uuid_or_none(state.get("run_id"))
        status = self._status_or_error(state.get("status"))
        return WeekendPilotWorkflowResult(
            run_id=run_id,
            trace_id=self._text_or_none(state.get("trace_id")),
            status=status,
            selected_plan_id=self._uuid_or_none(state.get("selected_plan_id")),
            node_history=list(state.get("node_history") or []),
            tool_event_count=self._tool_event_count(run_id),
            action_count=self._action_count(run_id),
            execution_status=self._text_or_none(state.get("execution_status")),
            feedback_status=self._text_or_none(state.get("feedback_status")),
            observability_status=self._text_or_none(state.get("observability_status")),
            agent_results=self._agent_results(state.get("agent_results")),
            error_json=state.get("error_json") if isinstance(state.get("error_json"), dict) else None,
        )

    def _tool_event_count(self, run_id: UUID | None) -> int:
        if run_id is None:
            return 0
        return int(
            self.dependencies.session.scalar(
                select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run_id)
            )
            or 0
        )

    def _action_count(self, run_id: UUID | None) -> int:
        if run_id is None:
            return 0
        return int(
            self.dependencies.session.scalar(
                select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id)
            )
            or 0
        )

    def _status_or_error(self, value: Any) -> WorkflowStatus:
        if value in {"awaiting_confirmation", "completed", "failed", "error"}:
            return value
        return "error"

    def _uuid_or_none(self, value: Any) -> UUID | None:
        return value if isinstance(value, UUID) else None

    def _text_or_none(self, value: Any) -> str | None:
        return value if isinstance(value, str) else None

    def _agent_results(self, value: Any) -> list[AgentResult]:
        results = []
        if not isinstance(value, list):
            return results
        for item in value:
            if isinstance(item, AgentResult):
                results.append(item)
            elif isinstance(item, dict):
                results.append(AgentResult.model_validate(item))
        return results
