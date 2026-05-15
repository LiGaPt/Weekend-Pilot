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
    def initialize_run(self, state):
        return self._append(state, "initialize_run")

    def parse_intent(self, state):
        return self._append(state, "parse_intent")

    def load_memory(self, state):
        return self._append(state, "load_memory")

    def build_query_plan(self, state):
        return self._append(state, "build_query_plan")

    def collect_candidates(self, state):
        return self._append(state, "collect_candidates")

    def enrich_candidates(self, state):
        return self._append(state, "enrich_candidates")

    def generate_itinerary(self, state):
        return self._append(state, "generate_itinerary")

    def final_review(self, state):
        return self._append(state, "final_review")

    def persist_and_select_plan(self, state):
        return self._append(state, "persist_and_select_plan")

    def wait_confirmation(self, state):
        updates = self._append(state, "wait_confirmation")
        if state.get("auto_confirm"):
            updates["status"] = "completed"
        else:
            updates["status"] = "awaiting_confirmation"
        return updates

    def execute(self, state):
        return self._append(state, "execute")

    def write_feedback(self, state):
        return self._append(state, "write_feedback")

    def record_observability(self, state):
        return self._append(state, "record_observability")

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
    assert route_after_confirmation({"status": "completed", "auto_confirm": True}) == "execute"


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
