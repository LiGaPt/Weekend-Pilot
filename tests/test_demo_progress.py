from __future__ import annotations

from importlib import import_module
from uuid import uuid4

import pytest

from backend.app.models.runtime import AgentRun, ToolEvent


_PROGRESS_LABELS = {
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

_GENERIC_SUMMARIES = {
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


def _load_progress_module():
    try:
        return import_module("backend.app.demo.progress")
    except ModuleNotFoundError as exc:
        pytest.fail(f"progress module is missing: {exc}")


def _run(
    *,
    status: str,
    metadata_json: dict[str, object] | None = None,
    tool_profile: str = "mock_world",
) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        user_id=None,
        session_id=None,
        case_id="demo-progress-test",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile=tool_profile,
        world_profile="family_afternoon",
        failure_profile=None,
        status=status,
        metadata_json=metadata_json or {},
    )


def _tool_event(
    run_id,
    *,
    sequence: int,
    provider: str = "mock_world",
    category: str | None = None,
    canonical_category: str | None = None,
    response_json: dict[str, object] | None = None,
) -> ToolEvent:
    payload: dict[str, object] = {}
    if category is not None:
        payload["category"] = category
    if canonical_category is not None:
        payload["canonical_category"] = canonical_category
    return ToolEvent(
        event_id=uuid4(),
        run_id=run_id,
        tool_name="search_poi",
        tool_type="read",
        provider=provider,
        request_json={"payload": payload, "event_sequence": sequence},
        response_json=response_json if response_json is not None else {"results": []},
        error_json=None,
        status="succeeded",
        cache_hit=False,
        latency_ms=3,
        langsmith_trace_id=None,
    )


def _step(stage: str, status: str, summary: str) -> dict[str, str]:
    return {
        "stage": stage,
        "label": _PROGRESS_LABELS[stage],
        "status": status,
        "summary": summary,
    }


def _assert_progress(
    result,
    *,
    current_stage: str,
    stage_history: list[str],
    current_label: str,
    steps: list[dict[str, str]],
) -> None:
    assert result.schema_version == "public_demo_progress_v1"
    assert result.current_stage == current_stage
    assert result.current_label == current_label
    assert result.stage_history == stage_history
    assert [step.model_dump(mode="json") for step in result.steps] == steps


def test_build_demo_progress_summary_for_confirmation_run() -> None:
    progress = _load_progress_module()
    run = _run(
        status="awaiting_confirmation",
        metadata_json={
            "demo": {
                "initial_node_history": [
                    "initialize",
                    "parse_intent",
                    "load_memory",
                    "generate_queries",
                    "pre_flight_check_availability",
                    "logical_planner_agent",
                    "route_and_time_engine",
                    "semantic_validator",
                    "final_review",
                    "present_to_user",
                    "wait_confirmation",
                ],
                "continuation_history": [],
            }
        },
    )
    tool_events = [
        _tool_event(
            run.run_id,
            sequence=1,
            category="activity",
            response_json={"results": [{}, {}, {}, {}, {}]},
        ),
        _tool_event(
            run.run_id,
            sequence=2,
            category="dining",
            response_json={"candidate_count": 5},
        ),
    ]

    result = progress.build_demo_progress_summary(run, tool_events, plan_count=2)

    _assert_progress(
        result,
        current_stage="ready_for_confirmation",
        current_label="\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
        stage_history=[
            "understanding_request",
            "planning_queries",
            "searching_activities",
            "searching_dining",
            "checking_availability",
            "building_itinerary",
            "checking_route_time",
            "reviewing_plan",
            "ready_for_confirmation",
        ],
        steps=[
            _step(
                "understanding_request",
                "completed",
                _GENERIC_SUMMARIES["understanding_request"],
            ),
            _step(
                "planning_queries",
                "completed",
                _GENERIC_SUMMARIES["planning_queries"],
            ),
            _step("searching_activities", "completed", "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8"),
            _step("searching_dining", "completed", "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385"),
            _step(
                "checking_availability",
                "completed",
                _GENERIC_SUMMARIES["checking_availability"],
            ),
            _step("building_itinerary", "completed", "\u5df2\u751f\u6210 2 \u4e2a\u5019\u9009\u65b9\u6848"),
            _step(
                "checking_route_time",
                "completed",
                _GENERIC_SUMMARIES["checking_route_time"],
            ),
            _step("reviewing_plan", "completed", _GENERIC_SUMMARIES["reviewing_plan"]),
            _step("ready_for_confirmation", "current", _GENERIC_SUMMARIES["ready_for_confirmation"]),
        ],
    )


def test_build_demo_progress_summary_for_early_clarification_run() -> None:
    progress = _load_progress_module()
    run = _run(
        status="awaiting_clarification",
        metadata_json={
            "demo": {
                "initial_node_history": ["initialize", "parse_intent", "load_memory", "generate_queries"],
                "continuation_history": [],
            }
        },
    )

    result = progress.build_demo_progress_summary(run, [])

    _assert_progress(
        result,
        current_stage="planning_queries",
        current_label="\u6b63\u5728\u89c4\u5212\u67e5\u8be2",
        stage_history=["understanding_request", "planning_queries"],
        steps=[
            _step("understanding_request", "completed", _GENERIC_SUMMARIES["understanding_request"]),
            _step("planning_queries", "current", _GENERIC_SUMMARIES["planning_queries"]),
        ],
    )


def test_build_demo_progress_summary_falls_back_to_generic_search_copy_when_counts_are_missing() -> None:
    progress = _load_progress_module()
    run = _run(
        status="awaiting_clarification",
        metadata_json={
            "demo": {
                "initial_node_history": [
                    "initialize",
                    "parse_intent",
                    "load_memory",
                    "generate_queries",
                    "pre_flight_check_availability",
                    "logical_planner_agent",
                    "route_and_time_engine",
                    "semantic_validator",
                    "apply_recovery",
                ],
                "continuation_history": [],
            }
        },
    )
    tool_events = [
        _tool_event(
            run.run_id,
            sequence=1,
            category="activity",
            response_json={"results": {"unexpected": True}},
        ),
        _tool_event(
            run.run_id,
            sequence=2,
            category="dining",
            response_json={"candidate_count": "unknown"},
        ),
    ]

    result = progress.build_demo_progress_summary(run, tool_events)

    _assert_progress(
        result,
        current_stage="reviewing_plan",
        current_label="\u6b63\u5728\u590d\u6838\u65b9\u6848",
        stage_history=[
            "understanding_request",
            "planning_queries",
            "searching_activities",
            "searching_dining",
            "checking_availability",
            "building_itinerary",
            "checking_route_time",
            "reviewing_plan",
        ],
        steps=[
            _step("understanding_request", "completed", _GENERIC_SUMMARIES["understanding_request"]),
            _step("planning_queries", "completed", _GENERIC_SUMMARIES["planning_queries"]),
            _step("searching_activities", "completed", _GENERIC_SUMMARIES["searching_activities"]),
            _step("searching_dining", "completed", _GENERIC_SUMMARIES["searching_dining"]),
            _step("checking_availability", "completed", _GENERIC_SUMMARIES["checking_availability"]),
            _step("building_itinerary", "completed", _GENERIC_SUMMARIES["building_itinerary"]),
            _step("checking_route_time", "completed", _GENERIC_SUMMARIES["checking_route_time"]),
            _step("reviewing_plan", "current", _GENERIC_SUMMARIES["reviewing_plan"]),
        ],
    )


def test_build_demo_progress_summary_for_completed_confirmed_run() -> None:
    progress = _load_progress_module()
    run = _run(
        status="completed",
        metadata_json={
            "demo": {
                "initial_node_history": [
                    "initialize",
                    "parse_intent",
                    "load_memory",
                    "generate_queries",
                    "pre_flight_check_availability",
                    "logical_planner_agent",
                    "route_and_time_engine",
                    "semantic_validator",
                    "final_review",
                    "present_to_user",
                    "wait_confirmation",
                ],
                "continuation_history": [
                    "confirm_plan",
                    "saga_execution_engine",
                    "generate_summary_message",
                ],
            }
        },
    )

    result = progress.build_demo_progress_summary(
        run,
        [],
        plan_count=1,
        action_count=2,
        execution_status="succeeded",
        feedback_status="completed",
    )

    _assert_progress(
        result,
        current_stage="executing_confirmed_actions",
        current_label="\u5df2\u786e\u8ba4\uff0c\u6b63\u5728\u6267\u884c\u52a8\u4f5c",
        stage_history=[
            "understanding_request",
            "planning_queries",
            "checking_availability",
            "building_itinerary",
            "checking_route_time",
            "reviewing_plan",
            "ready_for_confirmation",
            "executing_confirmed_actions",
        ],
        steps=[
            _step("understanding_request", "completed", _GENERIC_SUMMARIES["understanding_request"]),
            _step("planning_queries", "completed", _GENERIC_SUMMARIES["planning_queries"]),
            _step("checking_availability", "completed", _GENERIC_SUMMARIES["checking_availability"]),
            _step("building_itinerary", "completed", "\u5df2\u751f\u6210 1 \u4e2a\u5019\u9009\u65b9\u6848"),
            _step("checking_route_time", "completed", _GENERIC_SUMMARIES["checking_route_time"]),
            _step("reviewing_plan", "completed", _GENERIC_SUMMARIES["reviewing_plan"]),
            _step("ready_for_confirmation", "completed", _GENERIC_SUMMARIES["ready_for_confirmation"]),
            _step("executing_confirmed_actions", "current", "\u5df2\u5f00\u59cb\u6267\u884c 2 \u4e2a\u786e\u8ba4\u52a8\u4f5c"),
        ],
    )


def test_build_demo_progress_summary_for_declined_run_stays_waiting_for_confirmation() -> None:
    progress = _load_progress_module()
    run = _run(
        status="declined",
        metadata_json={
            "demo": {
                "initial_node_history": [
                    "initialize",
                    "parse_intent",
                    "load_memory",
                    "generate_queries",
                    "pre_flight_check_availability",
                    "logical_planner_agent",
                    "route_and_time_engine",
                    "semantic_validator",
                    "final_review",
                    "present_to_user",
                    "wait_confirmation",
                ],
                "continuation_history": ["decline_plan"],
            }
        },
    )

    result = progress.build_demo_progress_summary(run, [], plan_count=2)

    _assert_progress(
        result,
        current_stage="ready_for_confirmation",
        current_label="\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
        stage_history=[
            "understanding_request",
            "planning_queries",
            "checking_availability",
            "building_itinerary",
            "checking_route_time",
            "reviewing_plan",
            "ready_for_confirmation",
        ],
        steps=[
            _step("understanding_request", "completed", _GENERIC_SUMMARIES["understanding_request"]),
            _step("planning_queries", "completed", _GENERIC_SUMMARIES["planning_queries"]),
            _step("checking_availability", "completed", _GENERIC_SUMMARIES["checking_availability"]),
            _step("building_itinerary", "completed", "\u5df2\u751f\u6210 2 \u4e2a\u5019\u9009\u65b9\u6848"),
            _step("checking_route_time", "completed", _GENERIC_SUMMARIES["checking_route_time"]),
            _step("reviewing_plan", "completed", _GENERIC_SUMMARIES["reviewing_plan"]),
            _step("ready_for_confirmation", "current", "\u5df2\u8bb0\u5f55\u672c\u6b21\u6682\u4e0d\u786e\u8ba4"),
        ],
    )


def test_build_demo_progress_summary_falls_back_safely_for_malformed_metadata() -> None:
    progress = _load_progress_module()
    run = _run(
        status="awaiting_confirmation",
        metadata_json={
            "demo": {
                "initial_node_history": "oops",
                "continuation_history": {"unexpected": True},
            }
        },
    )
    tool_events = [
        _tool_event(
            run.run_id,
            sequence=1,
            category="activity",
            response_json={"results": {"unexpected": True}},
        )
    ]

    result = progress.build_demo_progress_summary(run, tool_events)

    assert result.schema_version == "public_demo_progress_v1"
    assert result.current_stage == "ready_for_confirmation"
    assert result.current_label == "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d"
    assert result.stage_history
    assert result.stage_history[-1] == "ready_for_confirmation"
    assert [step.stage for step in result.steps] == result.stage_history
    assert result.steps[-1].status == "current"
    assert result.steps[-1].summary
    assert set(result.stage_history) <= {
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
        "checking_availability",
        "building_itinerary",
        "checking_route_time",
        "reviewing_plan",
        "ready_for_confirmation",
        "executing_confirmed_actions",
    }
