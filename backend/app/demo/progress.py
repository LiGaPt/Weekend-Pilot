from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from backend.app.demo.schemas import DemoProgressSummary, DemoProgressStage
from backend.app.models.runtime import AgentRun, ToolEvent


PUBLIC_DEMO_PROGRESS_SCHEMA_VERSION = "public_demo_progress_v1"

DEMO_PROGRESS_LABELS: dict[DemoProgressStage, str] = {
    "understanding_request": "正在理解需求",
    "planning_queries": "正在规划查询",
    "searching_activities": "正在查询游玩地点",
    "searching_dining": "正在查询餐厅",
    "checking_availability": "正在检查营业与可用性",
    "building_itinerary": "正在组合行程",
    "checking_route_time": "正在计算路线与时间",
    "reviewing_plan": "正在复核方案",
    "ready_for_confirmation": "推荐方案已准备好",
    "executing_confirmed_actions": "已确认，正在执行动作",
}

_NODE_STAGE_MAP: dict[str, DemoProgressStage] = {
    "initialize": "understanding_request",
    "parse_intent": "understanding_request",
    "load_memory": "understanding_request",
    "generate_queries": "planning_queries",
    "pre_flight_check_availability": "checking_availability",
    "logical_planner_agent": "building_itinerary",
    "route_and_time_engine": "checking_route_time",
    "semantic_validator": "reviewing_plan",
    "apply_recovery": "reviewing_plan",
    "final_review": "reviewing_plan",
    "present_to_user": "reviewing_plan",
    "wait_confirmation": "ready_for_confirmation",
}

_SEARCH_INSERTION_STAGES = {
    "checking_availability",
    "building_itinerary",
    "checking_route_time",
    "reviewing_plan",
    "ready_for_confirmation",
}

_EXECUTION_HISTORY_STEPS = {
    "confirm_plan",
    "saga_execution_engine",
    "generate_summary_message",
}

_EXECUTION_STATUSES = {"succeeded", "partially_succeeded", "failed", "skipped"}
_FEEDBACK_STATUSES = {"completed", "partially_completed", "failed", "skipped"}


def build_demo_progress_summary(
    run: AgentRun,
    tool_events: Sequence[ToolEvent] | None,
    *,
    execution_status: str | None = None,
    feedback_status: str | None = None,
) -> DemoProgressSummary:
    node_history = _string_list(_demo_value(run, "initial_node_history"))
    continuation_history = _string_list(_demo_value(run, "continuation_history"))
    search_stages = _search_stages(tool_events or [])
    stage_history = _stage_history(node_history, search_stages)
    current_stage = _current_stage(
        run.status,
        node_history,
        continuation_history,
        stage_history,
        execution_status=execution_status,
        feedback_status=feedback_status,
    )
    _append_unique(stage_history, current_stage)
    return DemoProgressSummary(
        schema_version=PUBLIC_DEMO_PROGRESS_SCHEMA_VERSION,
        current_stage=current_stage,
        current_label=DEMO_PROGRESS_LABELS[current_stage],
        stage_history=stage_history,
    )


def _stage_history(
    node_history: Sequence[str],
    search_stages: Sequence[DemoProgressStage],
) -> list[DemoProgressStage]:
    history: list[DemoProgressStage] = []
    inserted_search = False
    for node_name in node_history:
        stage = _NODE_STAGE_MAP.get(node_name)
        if stage is None:
            continue
        if not inserted_search and search_stages and stage in _SEARCH_INSERTION_STAGES:
            _extend_unique(history, search_stages)
            inserted_search = True
        _append_unique(history, stage)
    if search_stages and not inserted_search:
        _extend_unique(history, search_stages)
    return history


def _current_stage(
    run_status: str,
    node_history: Sequence[str],
    continuation_history: Sequence[str],
    stage_history: Sequence[DemoProgressStage],
    *,
    execution_status: str | None,
    feedback_status: str | None,
) -> DemoProgressStage:
    if _did_execute(continuation_history, run_status, execution_status, feedback_status):
        return "executing_confirmed_actions"
    if run_status == "declined":
        return "ready_for_confirmation"
    if "wait_confirmation" in node_history or run_status == "awaiting_confirmation":
        return "ready_for_confirmation"
    if stage_history:
        return stage_history[-1]
    return _fallback_stage(run_status, execution_status=execution_status, feedback_status=feedback_status)


def _fallback_stage(
    run_status: str,
    *,
    execution_status: str | None,
    feedback_status: str | None,
) -> DemoProgressStage:
    if _did_execute([], run_status, execution_status, feedback_status):
        return "executing_confirmed_actions"
    if run_status in {"awaiting_confirmation", "declined"}:
        return "ready_for_confirmation"
    if run_status == "awaiting_clarification":
        return "planning_queries"
    return "understanding_request"


def _did_execute(
    continuation_history: Sequence[str],
    run_status: str,
    execution_status: str | None,
    feedback_status: str | None,
) -> bool:
    if any(step in _EXECUTION_HISTORY_STEPS for step in continuation_history):
        return True
    if execution_status in _EXECUTION_STATUSES:
        return True
    if feedback_status in _FEEDBACK_STATUSES:
        return True
    return run_status in {"completed", "partially_completed", "skipped"}


def _search_stages(tool_events: Sequence[ToolEvent]) -> list[DemoProgressStage]:
    stages: list[DemoProgressStage] = []
    for event in tool_events:
        if getattr(event, "tool_name", None) != "search_poi":
            continue
        payload = _payload_dict(getattr(event, "request_json", None))
        category = payload.get("category")
        canonical_category = payload.get("canonical_category")
        resolved = category if isinstance(category, str) else canonical_category if isinstance(canonical_category, str) else None
        if resolved == "activity":
            _append_unique(stages, "searching_activities")
        elif resolved == "dining":
            _append_unique(stages, "searching_dining")
    return stages


def _payload_dict(request_json: Any) -> dict[str, Any]:
    if not isinstance(request_json, dict):
        return {}
    payload = request_json.get("payload")
    return payload if isinstance(payload, dict) else {}


def _demo_value(run: AgentRun, key: str) -> Any:
    metadata = run.metadata_json if isinstance(run.metadata_json, dict) else {}
    demo = metadata.get("demo")
    if not isinstance(demo, dict):
        return None
    return demo.get(key)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _extend_unique(items: list[DemoProgressStage], values: Iterable[DemoProgressStage]) -> None:
    for value in values:
        _append_unique(items, value)


def _append_unique(items: list[DemoProgressStage], value: DemoProgressStage) -> None:
    if value not in items:
        items.append(value)
