from __future__ import annotations

from typing import Any, cast

from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowResult,
    WeekendPilotWorkflowRunner,
    WorkflowError,
)
from backend.app.workflow.graph import REQUIRED_NODE_NAMES, build_weekend_pilot_graph, route_after_confirmation


class _StubNodes:
    def initialize(self, state):
        return self._append(state, "initialize")

    def parse_intent(self, state):
        return self._append(state, "parse_intent")

    def load_memory(self, state):
        return self._append(state, "load_memory")

    def generate_queries(self, state):
        return self._append(state, "generate_queries")

    def execute_searches(self, state):
        return self._append(state, "execute_searches")

    def populate_candidate_blackboard(self, state):
        return self._append(state, "populate_candidate_blackboard")

    def pre_flight_check_availability(self, state):
        return self._append(state, "pre_flight_check_availability")

    def logical_planner_agent(self, state):
        return self._append(state, "logical_planner_agent")

    def route_and_time_engine(self, state):
        return self._append(state, "route_and_time_engine")

    def semantic_validator(self, state):
        return self._append(state, "semantic_validator")

    def final_review(self, state):
        return self._append(state, "final_review")

    def present_to_user(self, state):
        return self._append(state, "present_to_user")

    def wait_confirmation(self, state):
        updates = self._append(state, "wait_confirmation")
        if state.get("auto_confirm"):
            updates["status"] = "completed"
        else:
            updates["status"] = "awaiting_confirmation"
        return updates

    def saga_execution_engine(self, state):
        return self._append(state, "saga_execution_engine")

    def generate_summary_message(self, state):
        return self._append(state, "generate_summary_message")

    def _append(self, state, name: str):
        return {"node_history": [*state.get("node_history", []), name]}


def test_workflow_public_exports_import_cleanly() -> None:
    assert WeekendPilotWorkflowRequest is not None
    assert WeekendPilotWorkflowResult is not None
    assert WeekendPilotWorkflowRunner is not None
    assert WeekendPilotWorkflowDependencies is not None
    assert issubclass(WorkflowError, RuntimeError)


def test_graph_compiles_and_exposes_expected_nodes() -> None:
    graph = build_weekend_pilot_graph(cast(Any, _StubNodes()))

    compiled_graph = graph.get_graph()

    assert set(REQUIRED_NODE_NAMES).issubset(set(compiled_graph.nodes))


def test_confirmation_route_stops_when_awaiting_confirmation() -> None:
    assert route_after_confirmation({"status": "awaiting_confirmation"}) == "awaiting_confirmation"


def test_confirmation_route_continues_to_execute_when_confirmed() -> None:
    assert route_after_confirmation({"status": "completed", "auto_confirm": True}) == "saga_execution_engine"


def test_unsupported_profile_result_is_typed_and_does_not_raise() -> None:
    runner = WeekendPilotWorkflowRunner(cast(WeekendPilotWorkflowDependencies, object()))
    request = WeekendPilotWorkflowRequest.model_construct(
        user_input="Plan a family afternoon.",
        external_user_id=None,
        display_name=None,
        case_id=None,
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="amap",
        world_profile="family_afternoon",
        failure_profile=None,
        auto_confirm=False,
        selected_plan_index=0,
    )

    result = runner.run(request)

    assert isinstance(result, WeekendPilotWorkflowResult)
    assert result.status == "error"
    assert result.error_json is not None
    assert result.error_json["error_type"] == "unsupported_profile"
