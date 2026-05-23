from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from backend.app.agents import RecoveryDecision
from backend.app.workflow.state import V1_WORKFLOW_NODE_NAMES, WeekendPilotWorkflowState
from backend.app.workflow.timing import append_workflow_timing_record, summarize_workflow_timing

if TYPE_CHECKING:
    from backend.app.workflow.nodes import WeekendPilotWorkflowNodes


REQUIRED_NODE_NAMES = V1_WORKFLOW_NODE_NAMES


def build_weekend_pilot_graph(nodes: WeekendPilotWorkflowNodes):
    graph = StateGraph(WeekendPilotWorkflowState)

    graph.add_node("initialize", _timed_node("initialize", nodes.initialize, nodes))
    graph.add_node("parse_intent", _timed_node("parse_intent", nodes.parse_intent, nodes))
    graph.add_node("load_memory", _timed_node("load_memory", nodes.load_memory, nodes))
    graph.add_node("generate_queries", _timed_node("generate_queries", nodes.generate_queries, nodes))
    graph.add_node("execute_searches", _timed_node("execute_searches", nodes.execute_searches, nodes))
    graph.add_node(
        "populate_candidate_blackboard",
        _timed_node("populate_candidate_blackboard", nodes.populate_candidate_blackboard, nodes),
    )
    graph.add_node(
        "pre_flight_check_availability",
        _timed_node("pre_flight_check_availability", nodes.pre_flight_check_availability, nodes),
    )
    graph.add_node(
        "logical_planner_agent",
        _timed_node("logical_planner_agent", nodes.logical_planner_agent, nodes),
    )
    graph.add_node("route_and_time_engine", _timed_node("route_and_time_engine", nodes.route_and_time_engine, nodes))
    graph.add_node("semantic_validator", _timed_node("semantic_validator", nodes.semantic_validator, nodes))
    graph.add_node("apply_recovery", _timed_node("apply_recovery", nodes.apply_recovery, nodes))
    graph.add_node("final_review", _timed_node("final_review", nodes.final_review, nodes))
    graph.add_node("present_to_user", _timed_node("present_to_user", nodes.present_to_user, nodes))
    graph.add_node("wait_confirmation", _timed_node("wait_confirmation", nodes.wait_confirmation, nodes))
    graph.add_node(
        "saga_execution_engine",
        _timed_node("saga_execution_engine", nodes.saga_execution_engine, nodes),
    )
    graph.add_node(
        "generate_summary_message",
        _timed_node("generate_summary_message", nodes.generate_summary_message, nodes),
    )

    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "parse_intent")
    graph.add_edge("parse_intent", "load_memory")
    graph.add_edge("load_memory", "generate_queries")
    graph.add_conditional_edges(
        "generate_queries",
        route_after_query_generation,
        {
            "execute_searches": "execute_searches",
            "awaiting_clarification": END,
            "failed": END,
            "error": END,
        },
    )
    graph.add_edge("execute_searches", "populate_candidate_blackboard")
    graph.add_edge("populate_candidate_blackboard", "pre_flight_check_availability")
    graph.add_edge("pre_flight_check_availability", "logical_planner_agent")
    graph.add_edge("logical_planner_agent", "route_and_time_engine")
    graph.add_edge("route_and_time_engine", "semantic_validator")
    graph.add_conditional_edges(
        "semantic_validator",
        route_after_validation,
        {
            "final_review": "final_review",
            "apply_recovery": "apply_recovery",
        },
    )
    graph.add_conditional_edges(
        "apply_recovery",
        route_after_recovery,
        {
            "generate_queries": "generate_queries",
            "execute_searches": "execute_searches",
            "logical_planner_agent": "logical_planner_agent",
            "awaiting_clarification": END,
            "failed": END,
            "error": END,
        },
    )
    graph.add_edge("final_review", "present_to_user")
    graph.add_edge("present_to_user", "wait_confirmation")
    graph.add_conditional_edges(
        "wait_confirmation",
        route_after_confirmation,
        {
            "awaiting_confirmation": END,
            "failed": END,
            "error": END,
            "saga_execution_engine": "saga_execution_engine",
        },
    )
    graph.add_edge("saga_execution_engine", "generate_summary_message")
    graph.add_edge("generate_summary_message", END)

    return graph.compile()


def route_after_query_generation(state: WeekendPilotWorkflowState | dict[str, Any]) -> str:
    status = _state_value(state, "status")
    if status == "awaiting_clarification":
        return "awaiting_clarification"
    if status == "failed":
        return "failed"
    if status == "error":
        return "error"
    return "execute_searches"


def route_after_validation(state: WeekendPilotWorkflowState | dict[str, Any]) -> str:
    decision = _state_value(state, "recovery_decision")
    if isinstance(decision, dict):
        decision = RecoveryDecision.model_validate(decision)
    if isinstance(decision, RecoveryDecision) and (
        decision.verdict == "passed" or decision.recovery_action == "none"
    ):
        return "final_review"
    return "apply_recovery"


def route_after_recovery(state: WeekendPilotWorkflowState | dict[str, Any]) -> str:
    status = _state_value(state, "status")
    if status == "error":
        return "error"
    if status == "awaiting_clarification":
        return "awaiting_clarification"
    if status == "failed":
        return "failed"
    route = _state_value(state, "active_recovery_route")
    if route in {"generate_queries", "execute_searches", "logical_planner_agent"}:
        return route
    return "failed"


def route_after_confirmation(state: WeekendPilotWorkflowState | dict[str, Any]) -> str:
    status = _state_value(state, "status")
    if status == "awaiting_confirmation":
        return "awaiting_confirmation"
    if status == "failed":
        return "failed"
    if status == "error":
        return "error"
    return "saga_execution_engine"


def _state_value(state: WeekendPilotWorkflowState | dict[str, Any], key: str) -> Any:
    if isinstance(state, dict):
        return state.get(key)
    return getattr(state, key, None)


def _timed_node(node_name: str, handler, nodes: "WeekendPilotWorkflowNodes"):
    def wrapped(state: WeekendPilotWorkflowState | dict[str, Any]) -> dict[str, Any]:
        started_at = time.perf_counter()
        updates = handler(state)
        duration_ms = max(1, round((time.perf_counter() - started_at) * 1000))
        records = append_workflow_timing_record(
            _state_value(state, "workflow_stage_timings") or [],
            node_name=node_name,
            duration_ms=duration_ms,
        )
        summary = summarize_workflow_timing(records, V1_WORKFLOW_NODE_NAMES)
        run_id = None
        if isinstance(updates, dict):
            run_id = updates.get("run_id")
        if run_id is None:
            run_id = _state_value(state, "run_id")
        if run_id is not None and hasattr(nodes, "persist_workflow_timing_summary"):
            try:
                nodes.persist_workflow_timing_summary(run_id, summary)
            except Exception:
                pass
        return {
            **updates,
            "workflow_stage_timings": [record.model_dump(mode="json") for record in records],
            "workflow_timing_summary": summary.model_dump(mode="json"),
        }

    return wrapped
