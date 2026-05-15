from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from backend.app.workflow.schemas import WeekendPilotWorkflowState

if TYPE_CHECKING:
    from backend.app.workflow.nodes import WeekendPilotWorkflowNodes


REQUIRED_NODE_NAMES = (
    "initialize_run",
    "parse_intent",
    "load_memory",
    "build_query_plan",
    "collect_candidates",
    "enrich_candidates",
    "generate_itinerary",
    "final_review",
    "persist_and_select_plan",
    "wait_confirmation",
    "execute",
    "write_feedback",
    "record_observability",
)


def build_weekend_pilot_graph(nodes: WeekendPilotWorkflowNodes):
    graph = StateGraph(WeekendPilotWorkflowState)

    graph.add_node("initialize_run", nodes.initialize_run)
    graph.add_node("parse_intent", nodes.parse_intent)
    graph.add_node("load_memory", nodes.load_memory)
    graph.add_node("build_query_plan", nodes.build_query_plan)
    graph.add_node("collect_candidates", nodes.collect_candidates)
    graph.add_node("enrich_candidates", nodes.enrich_candidates)
    graph.add_node("generate_itinerary", nodes.generate_itinerary)
    graph.add_node("final_review", nodes.final_review)
    graph.add_node("persist_and_select_plan", nodes.persist_and_select_plan)
    graph.add_node("wait_confirmation", nodes.wait_confirmation)
    graph.add_node("execute", nodes.execute)
    graph.add_node("write_feedback", nodes.write_feedback)
    graph.add_node("record_observability", nodes.record_observability)

    graph.add_edge(START, "initialize_run")
    graph.add_edge("initialize_run", "parse_intent")
    graph.add_edge("parse_intent", "load_memory")
    graph.add_edge("load_memory", "build_query_plan")
    graph.add_edge("build_query_plan", "collect_candidates")
    graph.add_edge("collect_candidates", "enrich_candidates")
    graph.add_edge("enrich_candidates", "generate_itinerary")
    graph.add_edge("generate_itinerary", "final_review")
    graph.add_edge("final_review", "persist_and_select_plan")
    graph.add_edge("persist_and_select_plan", "wait_confirmation")
    graph.add_conditional_edges(
        "wait_confirmation",
        route_after_confirmation,
        {
            "awaiting_confirmation": END,
            "failed": END,
            "error": END,
            "execute": "execute",
        },
    )
    graph.add_edge("execute", "write_feedback")
    graph.add_edge("write_feedback", "record_observability")
    graph.add_edge("record_observability", END)

    return graph.compile()


def route_after_confirmation(state: WeekendPilotWorkflowState | dict[str, Any]) -> str:
    status = _state_value(state, "status")
    if status == "awaiting_confirmation":
        return "awaiting_confirmation"
    if status == "failed":
        return "failed"
    if status == "error":
        return "error"
    return "execute"


def _state_value(state: WeekendPilotWorkflowState | dict[str, Any], key: str) -> Any:
    if isinstance(state, dict):
        return state.get(key)
    return getattr(state, key, None)
