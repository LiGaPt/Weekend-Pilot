from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from backend.app.demo.schemas import (
    DemoProgressStage,
    DemoProgressStepStatus,
    DemoProgressStepSummary,
    DemoProgressSummary,
)
from backend.app.models.runtime import AgentRun, ToolEvent


PUBLIC_DEMO_PROGRESS_SCHEMA_VERSION = "public_demo_progress_v1"

DEMO_PROGRESS_LABELS: dict[DemoProgressStage, str] = {
    "understanding_request": "\u6b63\u5728\u7406\u89e3\u9700\u6c42",
    "planning_queries": "\u6b63\u5728\u89c4\u5212\u67e5\u8be2",
    "searching_activities": "\u6b63\u5728\u67e5\u8be2\u6e38\u73a9\u5730\u70b9",
    "searching_dining": "\u6b63\u5728\u67e5\u8be2\u9910\u5385",
    "checking_availability": "\u6b63\u5728\u68c0\u67e5\u8425\u4e1a\u4e0e\u53ef\u7528\u6027",
    "building_itinerary": "\u6b63\u5728\u7ec4\u5408\u884c\u7a0b",
    "checking_route_time": "\u6b63\u5728\u8ba1\u7b97\u8def\u7ebf\u4e0e\u65f6\u95f4",
    "reviewing_plan": "\u6b63\u5728\u590d\u6838\u65b9\u6848",
    "ready_for_confirmation": "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
    "executing_confirmed_actions": "\u5df2\u786e\u8ba4\uff0c\u6b63\u5728\u6267\u884c\u52a8\u4f5c",
}

DEMO_PROGRESS_GENERIC_SUMMARIES: dict[DemoProgressStage, str] = {
    "understanding_request": "\u5df2\u7406\u89e3\u51fa\u884c\u76ee\u6807\u4e0e\u6838\u5fc3\u7ea6\u675f",
    "planning_queries": "\u5df2\u6574\u7406\u6d3b\u52a8\u4e0e\u9910\u996e\u67e5\u8be2\u65b9\u5411",
    "searching_activities": "\u5df2\u5b8c\u6210\u6d3b\u52a8\u5019\u9009\u67e5\u627e",
    "searching_dining": "\u5df2\u5b8c\u6210\u9910\u5385\u5019\u9009\u67e5\u627e",
    "checking_availability": "\u5df2\u5b8c\u6210\u8425\u4e1a\u4e0e\u53ef\u7528\u6027\u68c0\u67e5",
    "building_itinerary": "\u5df2\u751f\u6210\u5019\u9009\u65b9\u6848",
    "checking_route_time": "\u5df2\u5b8c\u6210\u8def\u7ebf\u4e0e\u65f6\u95f4\u6d4b\u7b97",
    "reviewing_plan": "\u5df2\u5b8c\u6210\u63a8\u8350\u65b9\u6848\u590d\u6838",
    "ready_for_confirmation": "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
    "executing_confirmed_actions": "\u5df2\u5f00\u59cb\u6267\u884c\u786e\u8ba4\u52a8\u4f5c",
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
    plan_count: int | None = None,
    action_count: int | None = None,
    execution_status: str | None = None,
    feedback_status: str | None = None,
) -> DemoProgressSummary:
    node_history = _string_list(_demo_value(run, "initial_node_history"))
    continuation_history = _string_list(_demo_value(run, "continuation_history"))
    search_stages, search_counts = _search_progress_evidence(tool_events or [])
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
        steps=_build_steps(
            stage_history,
            run_status=run.status,
            search_counts=search_counts,
            plan_count=plan_count,
            action_count=action_count,
        ),
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


def _search_progress_evidence(
    tool_events: Sequence[ToolEvent],
) -> tuple[list[DemoProgressStage], dict[str, int]]:
    stages: list[DemoProgressStage] = []
    counts: dict[str, int] = {}
    for event in tool_events:
        if getattr(event, "tool_name", None) != "search_poi":
            continue
        payload = _payload_dict(getattr(event, "request_json", None))
        category = payload.get("category")
        canonical_category = payload.get("canonical_category")
        resolved = (
            category
            if isinstance(category, str)
            else canonical_category
            if isinstance(canonical_category, str)
            else None
        )
        if resolved == "activity":
            _append_unique(stages, "searching_activities")
            count = _result_count(getattr(event, "response_json", None))
            if count is not None:
                counts["activity"] = count
        elif resolved == "dining":
            _append_unique(stages, "searching_dining")
            count = _result_count(getattr(event, "response_json", None))
            if count is not None:
                counts["dining"] = count
    return stages, counts


def _build_steps(
    stage_history: Sequence[DemoProgressStage],
    *,
    run_status: str,
    search_counts: dict[str, int],
    plan_count: int | None,
    action_count: int | None,
) -> list[DemoProgressStepSummary]:
    steps: list[DemoProgressStepSummary] = []
    for index, stage in enumerate(stage_history):
        status: DemoProgressStepStatus = "current" if index == len(stage_history) - 1 else "completed"
        steps.append(
            DemoProgressStepSummary(
                stage=stage,
                label=DEMO_PROGRESS_LABELS[stage],
                status=status,
                summary=_summary_for_stage(
                    stage,
                    run_status=run_status,
                    search_counts=search_counts,
                    plan_count=plan_count,
                    action_count=action_count,
                ),
            )
        )
    return steps


def _summary_for_stage(
    stage: DemoProgressStage,
    *,
    run_status: str,
    search_counts: dict[str, int],
    plan_count: int | None,
    action_count: int | None,
) -> str:
    if stage == "searching_activities":
        count = search_counts.get("activity")
        if count is not None:
            return f"\u5df2\u627e\u5230 {count} \u4e2a\u6d3b\u52a8"
    elif stage == "searching_dining":
        count = search_counts.get("dining")
        if count is not None:
            return f"\u5df2\u627e\u5230 {count} \u4e2a\u9910\u5385"
    elif stage == "building_itinerary":
        if plan_count is not None and plan_count > 0:
            return f"\u5df2\u751f\u6210 {plan_count} \u4e2a\u5019\u9009\u65b9\u6848"
    elif stage == "ready_for_confirmation" and run_status == "declined":
        return "\u5df2\u8bb0\u5f55\u672c\u6b21\u6682\u4e0d\u786e\u8ba4"
    elif stage == "executing_confirmed_actions":
        if action_count is not None and action_count > 0:
            return f"\u5df2\u5f00\u59cb\u6267\u884c {action_count} \u4e2a\u786e\u8ba4\u52a8\u4f5c"
    return DEMO_PROGRESS_GENERIC_SUMMARIES[stage]


def _result_count(response_json: Any) -> int | None:
    if not isinstance(response_json, dict):
        return None
    results = response_json.get("results")
    if isinstance(results, list):
        return len(results)
    candidate_count = response_json.get("candidate_count")
    if isinstance(candidate_count, int):
        return candidate_count
    return None


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
