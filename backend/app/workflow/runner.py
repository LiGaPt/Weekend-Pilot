from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from backend.app.agents import AgentResult
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.providers.mock_world.loader import SUPPORTED_PROFILES
from backend.app.workflow.dependencies import WeekendPilotWorkflowDependencies
from backend.app.workflow.graph import build_weekend_pilot_graph
from backend.app.workflow.nodes import WeekendPilotWorkflowNodes
from backend.app.workflow.schemas import (
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowResult,
    WorkflowStatus,
)
from backend.app.workflow.state import CandidateBlackboard, RouteTimeSummary, WeekendPilotWorkflowState
from backend.app.workflow.timing import WorkflowTimingSummary


AMAP_WORLD_PROFILE = "amap_shanghai_live"
AMAP_UNSUPPORTED_MESSAGE = (
    "WeekendPilot workflow supports AMAP only as a read-only pre-confirmation preview path."
)


class WeekendPilotWorkflowRunner:
    def __init__(self, dependencies: WeekendPilotWorkflowDependencies) -> None:
        self.dependencies = dependencies

    def run(self, request: WeekendPilotWorkflowRequest) -> WeekendPilotWorkflowResult:
        unsupported = self._unsupported_profile_result(request)
        if unsupported is not None:
            return unsupported

        try:
            dependencies = self._scoped_dependencies(
                tool_profile=request.tool_profile,
                world_profile=request.world_profile,
            )
            nodes = WeekendPilotWorkflowNodes(dependencies)
            graph = build_weekend_pilot_graph(nodes)
            final_state = graph.invoke(self._initial_state(request))
            final_state = self._record_observability(nodes, final_state)
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

    def stream(
        self,
        request: WeekendPilotWorkflowRequest,
    ) -> Iterator[WeekendPilotWorkflowState | dict[str, Any]]:
        unsupported = self._unsupported_profile_result(request)
        initial_state = self._initial_state(request)
        if unsupported is not None:
            yield self._stream_error_state(initial_state, unsupported.error_json or {})
            return

        last_state: WeekendPilotWorkflowState | dict[str, Any] = initial_state
        try:
            dependencies = self._scoped_dependencies(
                tool_profile=request.tool_profile,
                world_profile=request.world_profile,
            )
            nodes = WeekendPilotWorkflowNodes(dependencies)
            graph = build_weekend_pilot_graph(nodes)
            for state in graph.stream(initial_state, stream_mode="values"):
                last_state = state
                yield state
        except Exception as exc:
            yield self._stream_error_state(
                last_state,
                {
                    "error_type": "workflow_exception",
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                },
            )

    def result_from_stream_state(
        self,
        state: WeekendPilotWorkflowState | dict[str, Any],
    ) -> WeekendPilotWorkflowResult:
        if state.get("status") == "error":
            return self._to_result(state)
        scoped_dependencies = self._scoped_dependencies(
            tool_profile=self._text_or_none(state.get("tool_profile")),
            world_profile=self._text_or_none(state.get("world_profile")),
        )
        nodes = WeekendPilotWorkflowNodes(scoped_dependencies)
        final_state = self._record_observability(nodes, state)
        return self._to_result(final_state)

    def _unsupported_profile_result(
        self,
        request: WeekendPilotWorkflowRequest,
    ) -> WeekendPilotWorkflowResult | None:
        if request.tool_profile == "mock_world":
            if request.world_profile in SUPPORTED_PROFILES:
                return None
            message = (
                "WeekendPilot workflow supports only "
                "tool_profile='mock_world' with a supported Mock World profile."
            )
        elif request.tool_profile == "amap":
            if request.world_profile == AMAP_WORLD_PROFILE and request.auto_confirm is False:
                return None
            message = AMAP_UNSUPPORTED_MESSAGE
        else:
            message = (
                "WeekendPilot workflow supports only "
                "tool_profile='mock_world' with a supported Mock World profile."
            )

        return WeekendPilotWorkflowResult(
            run_id=None,
            trace_id=None,
            status="error",
            error_json={
                "error_type": "unsupported_profile",
                "message": message,
                "tool_profile": request.tool_profile,
                "world_profile": request.world_profile,
                "auto_confirm": request.auto_confirm,
            },
        )

    def _scoped_dependencies(
        self,
        *,
        tool_profile: str | None,
        world_profile: str | None,
    ) -> WeekendPilotWorkflowDependencies:
        update: dict[str, Any] = {}
        if tool_profile is not None:
            update["tool_profile"] = tool_profile
        if world_profile is not None:
            update["world_profile"] = world_profile
        return self.dependencies.model_copy(update=update)

    def _initial_state(self, request: WeekendPilotWorkflowRequest) -> WeekendPilotWorkflowState:
        return WeekendPilotWorkflowState(
            user_input=request.user_input,
            external_user_id=request.external_user_id,
            display_name=request.display_name,
            existing_user_id=request.existing_user_id,
            session_id=request.session_id,
            case_id=request.case_id,
            agent_version=request.agent_version,
            prompt_version=request.prompt_version,
            tool_profile=request.tool_profile,
            world_profile=request.world_profile,
            failure_profile=request.failure_profile,
            auto_confirm=request.auto_confirm,
            selected_plan_index=request.selected_plan_index,
            intent_override=request.intent_override,
            run_id=None,
            user_id=None,
            trace_id=None,
            selected_plan_id=None,
            active_memories=[],
            candidate_blackboard=CandidateBlackboard(),
            route_time_summary=RouteTimeSummary(),
            workflow_stage_timings=[],
            workflow_timing_summary=None,
            agent_results=[],
            recovery_attempts=[],
            max_recovery_attempts=2,
            search_expansion_level=0,
            excluded_candidate_pairs=[],
            active_recovery_route=None,
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
            workflow_timing_summary=self._workflow_timing_summary(state.get("workflow_timing_summary")),
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
        if value in {"awaiting_clarification", "awaiting_confirmation", "completed", "failed", "error"}:
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

    def _workflow_timing_summary(self, value: Any) -> WorkflowTimingSummary | None:
        if isinstance(value, WorkflowTimingSummary):
            return value
        if isinstance(value, dict):
            return WorkflowTimingSummary.model_validate(value)
        return None

    def _record_observability(
        self,
        nodes: WeekendPilotWorkflowNodes,
        state: WeekendPilotWorkflowState | dict[str, Any],
    ) -> WeekendPilotWorkflowState | dict[str, Any]:
        if not isinstance(state, dict):
            return state
        if state.get("status") not in {"awaiting_clarification", "awaiting_confirmation", "completed", "failed"}:
            return state
        context = state.get("trace_context")
        if context is None:
            return state
        try:
            observability = nodes.recorder.record_run_summary(context)
        except Exception as exc:
            error_json = {
                "error_type": "observability_failed",
                "message": str(exc),
                "exception_type": type(exc).__name__,
            }
            nodes._record_observability_error(state, error_json)
            existing_error = state.get("error_json")
            if isinstance(existing_error, dict):
                merged_error = deepcopy(existing_error)
            else:
                merged_error = {"observability": error_json}
            return {
                **state,
                "observability_status": "observability_failed",
                "error_json": merged_error,
            }
        return {
            **state,
            "observability_result": observability,
            "observability_status": (
                "recorded" if observability.local_buffer_written else observability.status
            ),
        }

    def _stream_error_state(
        self,
        state: WeekendPilotWorkflowState | dict[str, Any],
        error_json: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            **state,
            "status": "error",
            "error_json": error_json,
        }
