from __future__ import annotations

from typing import Any, cast

from backend.app.agents import RecoveryDecision
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowResult,
    WeekendPilotWorkflowRunner,
    WorkflowError,
)
from backend.app.workflow.graph import (
    REQUIRED_NODE_NAMES,
    build_weekend_pilot_graph,
    route_after_confirmation,
    route_after_recovery,
    route_after_validation,
)
from backend.app.workflow.recovery import resolve_recovery_route


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
        updates = self._append(state, "semantic_validator")
        updates["recovery_decision"] = state.get("recovery_decision") or RecoveryDecision(
            verdict="passed",
            recovery_action="none",
            retry_budget=0,
            reason="safe",
        )
        return updates

    def apply_recovery(self, state):
        updates = self._append(state, "apply_recovery")
        decision = state.get("recovery_decision")
        if decision is None:
            updates["status"] = "failed"
            return updates
        if decision.recovery_action == "retry":
            updates["active_recovery_route"] = "execute_searches"
            updates["recovery_decision"] = RecoveryDecision(
                verdict="passed",
                recovery_action="none",
                retry_budget=0,
                reason="safe after retry",
            )
        elif decision.recovery_action == "expand_search_radius":
            updates["active_recovery_route"] = "generate_queries"
            updates["recovery_decision"] = RecoveryDecision(
                verdict="passed",
                recovery_action="none",
                retry_budget=0,
                reason="safe after expanded search",
            )
        elif decision.recovery_action == "replace_candidate":
            updates["active_recovery_route"] = "logical_planner_agent"
            updates["recovery_decision"] = RecoveryDecision(
                verdict="passed",
                recovery_action="none",
                retry_budget=0,
                reason="safe after replacement",
            )
        else:
            updates["status"] = "failed"
        return updates

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


def test_validation_route_continues_to_final_review_for_passed_decision() -> None:
    assert route_after_validation(
        {
            "recovery_decision": RecoveryDecision(
                verdict="passed",
                recovery_action="none",
                retry_budget=0,
                reason="safe",
            )
        }
    ) == "final_review"


def test_validation_route_enters_recovery_for_failed_decision() -> None:
    assert route_after_validation(
        {
            "recovery_decision": RecoveryDecision(
                verdict="failed",
                error_type="route_infeasible",
                recovery_action="retry",
                route_to="execute_searches",
                retry_budget=1,
                reason="try reads again",
            )
        }
    ) == "apply_recovery"


def test_recovery_route_resolver_retries_to_execute_searches() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="route_infeasible",
            recovery_action="retry",
            retry_budget=1,
            reason="retry reads",
        ),
        attempt_count=0,
        max_attempts=1,
    )

    assert result.route_to == "execute_searches"
    assert result.error_type is None
    assert result.attempt is not None
    assert result.attempt.retry_budget_before == 1
    assert result.attempt.retry_budget_after == 0
    assert result.attempt.status == "routed"


def test_recovery_route_resolver_expands_search_to_generate_queries() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="empty_result",
            recovery_action="expand_search_radius",
            retry_budget=1,
            reason="expand search",
        ),
        attempt_count=0,
        max_attempts=1,
    )

    assert result.route_to == "generate_queries"
    assert result.attempt is not None
    assert result.attempt.status == "routed"


def test_recovery_route_resolver_replaces_candidate_to_logical_planner() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="plan_invalid",
            recovery_action="replace_candidate",
            retry_budget=1,
            reason="replace candidate",
        ),
        attempt_count=0,
        max_attempts=1,
    )

    assert result.route_to == "logical_planner_agent"
    assert result.attempt is not None
    assert result.attempt.status == "routed"


def test_recovery_route_resolver_stops_for_ask_user() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="user_input_error",
            recovery_action="ask_user",
            retry_budget=1,
            reason="need clarification",
        ),
        attempt_count=0,
        max_attempts=1,
    )

    assert result.route_to == "failed"
    assert result.error_type == "recovery_requires_user_input"
    assert result.attempt is not None
    assert result.attempt.status == "stopped"


def test_recovery_route_resolver_stops_when_budget_exhausted() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="route_infeasible",
            recovery_action="retry",
            retry_budget=0,
            reason="no budget",
        ),
        attempt_count=0,
        max_attempts=1,
    )

    assert result.route_to == "failed"
    assert result.error_type == "recovery_budget_exhausted"
    assert result.attempt is not None
    assert result.attempt.status == "stopped"


def test_recovery_route_resolver_stops_when_attempt_limit_reached() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="route_infeasible",
            recovery_action="retry",
            retry_budget=1,
            reason="too many attempts",
        ),
        attempt_count=1,
        max_attempts=1,
    )

    assert result.route_to == "failed"
    assert result.error_type == "recovery_attempt_limit_exceeded"


def test_recovery_route_resolver_rejects_unsupported_route() -> None:
    result = resolve_recovery_route(
        RecoveryDecision(
            verdict="failed",
            error_type="route_infeasible",
            recovery_action="retry",
            route_to="saga_execution_engine",
            retry_budget=1,
            reason="unsafe route",
        ),
        attempt_count=0,
        max_attempts=1,
    )

    assert result.route_to == "failed"
    assert result.error_type == "unsupported_recovery_route"


def test_recovery_graph_route_never_jumps_to_execution() -> None:
    assert route_after_recovery({"active_recovery_route": "saga_execution_engine"}) == "failed"


def test_graph_retry_recovery_loops_through_read_path_then_confirmation() -> None:
    graph = build_weekend_pilot_graph(cast(Any, _StubNodes()))
    decision = RecoveryDecision(
        verdict="failed",
        error_type="route_infeasible",
        recovery_action="retry",
        route_to="execute_searches",
        retry_budget=1,
        reason="retry reads",
    )

    result = graph.invoke({"node_history": [], "auto_confirm": False, "recovery_decision": decision})

    assert result["node_history"].count("execute_searches") >= 2
    assert result["node_history"].count("apply_recovery") == 1
    assert "saga_execution_engine" not in result["node_history"]
    assert result["status"] == "awaiting_confirmation"
    assert result["workflow_timing_summary"]["schema_version"] == "workflow_timing_summary_v1"
    assert result["workflow_timing_summary"]["total_duration_ms"] >= 1
    stage_entries = {
        entry["node_name"]: entry for entry in result["workflow_timing_summary"]["stages"]
    }
    assert stage_entries["execute_searches"]["attempt_count"] >= 2
    assert stage_entries["execute_searches"]["total_duration_ms"] >= 2
    assert result["workflow_timing_summary"]["stage_count"] == len(
        result["workflow_timing_summary"]["stages"]
    )


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
