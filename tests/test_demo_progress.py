from __future__ import annotations

from importlib import import_module
from uuid import uuid4

import pytest

from backend.app.models.runtime import AgentRun, ToolEvent


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
        response_json={"results": []},
        error_json=None,
        status="succeeded",
        cache_hit=False,
        latency_ms=3,
        langsmith_trace_id=None,
    )


def _assert_progress(result, *, current_stage: str, stage_history: list[str], current_label: str) -> None:
    assert result.schema_version == "public_demo_progress_v1"
    assert result.current_stage == current_stage
    assert result.current_label == current_label
    assert result.stage_history == stage_history


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
        _tool_event(run.run_id, sequence=1, category="activity"),
        _tool_event(run.run_id, sequence=2, category="dining"),
    ]

    result = progress.build_demo_progress_summary(run, tool_events)

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
    )


def test_build_demo_progress_summary_for_recovery_clarification_run() -> None:
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
        _tool_event(run.run_id, sequence=1, category="activity"),
        _tool_event(run.run_id, sequence=2, category="dining"),
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

    result = progress.build_demo_progress_summary(run, [])

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

    result = progress.build_demo_progress_summary(run, [])

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
    tool_events = [_tool_event(run.run_id, sequence=1, category="activity")]

    result = progress.build_demo_progress_summary(run, tool_events)

    assert result.schema_version == "public_demo_progress_v1"
    assert result.current_stage == "ready_for_confirmation"
    assert result.current_label == "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d"
    assert result.stage_history
    assert result.stage_history[-1] == "ready_for_confirmation"
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
