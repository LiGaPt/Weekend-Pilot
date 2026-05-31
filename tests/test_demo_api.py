from __future__ import annotations

from uuid import uuid4

import backend.app.demo.schemas as demo_schemas
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.demo.schemas import (
    DemoReplanRunRequest,
    DemoRunStreamErrorEvent,
    DemoRunStreamProgressEvent,
    DemoRunStreamSummaryEvent,
    DemoRunSummary,
    DemoStartRunRequest,
)
from backend.app.demo.service import sanitize_demo_payload
from backend.app.main import create_app


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

_PROGRESS_SUMMARIES = {
    "understanding_request": "\u5df2\u7406\u89e3\u51fa\u884c\u76ee\u6807\u4e0e\u6838\u5fc3\u7ea6\u675f",
    "planning_queries": "\u5df2\u6574\u7406\u6d3b\u52a8\u4e0e\u9910\u996e\u67e5\u8be2\u65b9\u5411",
    "searching_activities": "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8",
    "searching_dining": "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385",
    "checking_availability": "\u5df2\u5b8c\u6210\u8425\u4e1a\u4e0e\u53ef\u7528\u6027\u68c0\u67e5",
    "building_itinerary": "\u5df2\u751f\u6210 2 \u4e2a\u5019\u9009\u65b9\u6848",
    "checking_route_time": "\u5df2\u5b8c\u6210\u8def\u7ebf\u4e0e\u65f6\u95f4\u6d4b\u7b97",
    "reviewing_plan": "\u5df2\u5b8c\u6210\u63a8\u8350\u65b9\u6848\u590d\u6838",
    "ready_for_confirmation": "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
    "executing_confirmed_actions": "\u5df2\u5f00\u59cb\u6267\u884c 2 \u4e2a\u786e\u8ba4\u52a8\u4f5c",
}


def _step(stage: str, status: str, summary: str | None = None) -> dict[str, str]:
    return {
        "stage": stage,
        "label": _PROGRESS_LABELS[stage],
        "status": status,
        "summary": summary or _PROGRESS_SUMMARIES[stage],
    }


def _progress(
    current_stage: str = "ready_for_confirmation",
    *,
    stage_history: list[str] | None = None,
) -> dict[str, object]:
    history = stage_history or [current_stage]
    steps = [
        _step(stage, "current" if index == len(history) - 1 else "completed")
        for index, stage in enumerate(history)
    ]
    return {
        "schema_version": "public_demo_progress_v1",
        "current_stage": current_stage,
        "current_label": _PROGRESS_LABELS[current_stage],
        "stage_history": history,
        "steps": steps,
    }


def test_create_app_includes_demo_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/demo/runs" in paths
    assert "/demo/runs/stream" in paths
    assert "/demo/runs/{run_id}" in paths
    assert "/demo/runs/{run_id}/clarify" in paths
    assert "/demo/runs/{run_id}/replan" in paths
    assert "/demo/runs/{run_id}/confirm" in paths
    assert "/demo/runs/{run_id}/decline" in paths
    assert "/internal/runs/{run_id}/observability" in paths


def test_cors_preflight_allows_vite_localhost_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/demo/runs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_start_request_rejects_empty_user_input() -> None:
    with pytest.raises(ValidationError):
        DemoStartRunRequest(user_input="")


def test_start_request_defaults_read_profile_to_mock_world() -> None:
    request = DemoStartRunRequest(user_input="Family afternoon")

    assert request.read_profile == "mock_world"


def test_replan_request_rejects_empty_user_input() -> None:
    with pytest.raises(ValidationError):
        DemoReplanRunRequest(user_input="")


def test_clarify_request_rejects_empty_user_input() -> None:
    assert hasattr(demo_schemas, "DemoClarifyRunRequest")
    with pytest.raises(ValidationError):
        demo_schemas.DemoClarifyRunRequest(user_input="")


def test_sanitizer_removes_internal_and_sensitive_keys() -> None:
    payload = {
        "ok": True,
        "action_id": "internal-action",
        "tool_event_id": "internal-tool-event",
        "event_id": "internal-event",
        "idempotency_key": "internal-key",
        "api_key": "secret",
        "token": "secret",
        "secret": "secret",
        "authorization": "Bearer secret",
        "prompt": "raw prompt",
        "debug_trace": {"step": "private"},
        "nested": [
            {
                "name": "safe",
                "action_id": "nested-internal-action",
                "access_token": "nested-secret",
            }
        ],
    }

    sanitized = sanitize_demo_payload(payload)

    assert sanitized == {"ok": True, "nested": [{"name": "safe"}]}


def test_demo_run_summary_serializes_minimal_web_safe_payload() -> None:
    run_id = uuid4()
    plan_id = uuid4()

    summary = DemoRunSummary(
        run_id=run_id,
        status="awaiting_confirmation",
        read_profile="mock_world",
        selected_plan_id=plan_id,
        plan_version={
            "version_number": 1,
            "version_label": "v1",
            "source_run_id": None,
            "source_selected_plan_id": None,
        },
        plans=[
            {
                "plan_id": plan_id,
                "status": "selected",
                "selected": True,
                "title": "Family-friendly afternoon",
                "summary": "A short family outing with a lighter dinner option.",
                "action_manifest": {
                    "source": "proposed_actions",
                    "action_count": 1,
                    "actions": [
                        {
                            "action_ref": "draft_1_action_1",
                            "execution_order": 1,
                            "action_type": "reserve_restaurant",
                            "target_id": "restaurant_light_001",
                            "payload_preview": {"party_size": 3},
                            "reason": "Confirm to lock dinner seating.",
                        }
                    ],
                },
            }
        ],
        action_count=0,
        execution_status=None,
        feedback_status=None,
        error=None,
        progress=_progress(
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
            ]
        ),
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["run_id"] == str(run_id)
    assert dumped["read_profile"] == "mock_world"
    assert dumped["selected_plan_id"] == str(plan_id)
    assert dumped["plan_version"] == {
        "version_number": 1,
        "version_label": "v1",
        "source_run_id": None,
        "source_selected_plan_id": None,
    }
    assert dumped["plans"][0]["plan_id"] == str(plan_id)
    assert dumped["plans"][0]["action_manifest"] == {
        "source": "proposed_actions",
        "action_count": 1,
        "actions": [
            {
                "action_ref": "draft_1_action_1",
                "execution_order": 1,
                "action_type": "reserve_restaurant",
                "target_id": "restaurant_light_001",
                "payload_preview": {"party_size": 3},
                "reason": "Confirm to lock dinner seating.",
            }
        ],
    }
    assert dumped["progress"] == {
        "schema_version": "public_demo_progress_v1",
        "current_stage": "ready_for_confirmation",
        "current_label": "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
        "stage_history": [
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
        "steps": [
            _step("understanding_request", "completed"),
            _step("planning_queries", "completed"),
            _step("searching_activities", "completed"),
            _step("searching_dining", "completed"),
            _step("checking_availability", "completed"),
            _step("building_itinerary", "completed"),
            _step("checking_route_time", "completed"),
            _step("reviewing_plan", "completed"),
            _step("ready_for_confirmation", "current", "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d"),
        ],
    }
    assert "trace_id" not in dumped
    assert "session_id" not in dumped
    assert "conversation" not in dumped
    assert "tool_event_count" not in dumped
    assert "node_history" not in dumped
    assert "observability_status" not in dumped
    assert "agent_roles" not in dumped


def test_demo_run_summary_requires_plan_version() -> None:
    with pytest.raises(ValidationError):
        DemoRunSummary(
            run_id=uuid4(),
            status="awaiting_confirmation",
            read_profile="mock_world",
            selected_plan_id=None,
            plans=[],
            action_count=0,
            execution_status=None,
            feedback_status=None,
            error=None,
            progress=_progress(),
        )


def test_demo_run_summary_serializes_clarification_payload() -> None:
    summary = DemoRunSummary(
        run_id=uuid4(),
        status="awaiting_clarification",
        read_profile="mock_world",
        selected_plan_id=None,
        plan_version={
            "version_number": 1,
            "version_label": "v1",
            "source_run_id": None,
            "source_selected_plan_id": None,
        },
        plans=[],
        action_count=0,
        execution_status=None,
        feedback_status=None,
        error=None,
        progress=_progress(
            "planning_queries",
            stage_history=["understanding_request", "planning_queries"],
        ),
        clarification={
            "prompt": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
            "missing_fields": ["scenario_or_participants", "time_window"],
        },
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["clarification"] == {
        "prompt": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
        "missing_fields": ["scenario_or_participants", "time_window"],
    }


def test_demo_run_summary_serializes_recovery_clarification_payload() -> None:
    summary = DemoRunSummary(
        run_id=uuid4(),
        status="awaiting_clarification",
        read_profile="mock_world",
        selected_plan_id=None,
        plan_version={
            "version_number": 1,
            "version_label": "v1",
            "source_run_id": None,
            "source_selected_plan_id": None,
        },
        plans=[],
        action_count=0,
        execution_status=None,
        feedback_status=None,
        error=None,
        progress=_progress(
            "reviewing_plan",
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
        ),
        clarification={
            "prompt": (
                "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
                "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
                "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
            ),
            "missing_fields": ["distance_flexibility"],
        },
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["clarification"] == {
        "prompt": (
            "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
            "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
            "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
        ),
        "missing_fields": ["distance_flexibility"],
    }


def test_demo_run_summary_allows_null_clarification_for_non_clarification_runs() -> None:
    summary = DemoRunSummary(
        run_id=uuid4(),
        status="awaiting_confirmation",
        read_profile="mock_world",
        selected_plan_id=None,
        plan_version={
            "version_number": 1,
            "version_label": "v1",
            "source_run_id": None,
            "source_selected_plan_id": None,
        },
        plans=[],
        action_count=0,
        execution_status=None,
        feedback_status=None,
        error=None,
        progress=_progress(),
        clarification=None,
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["clarification"] is None


def test_demo_plan_preview_requires_action_manifest() -> None:
    with pytest.raises(ValidationError):
        DemoRunSummary.model_validate(
            {
                "run_id": str(uuid4()),
                "status": "awaiting_confirmation",
                "read_profile": "mock_world",
                "selected_plan_id": None,
                "plan_version": {
                    "version_number": 1,
                    "version_label": "v1",
                    "source_run_id": None,
                    "source_selected_plan_id": None,
                },
                "plans": [
                    {
                        "plan_id": str(uuid4()),
                        "status": "selected",
                        "selected": True,
                    }
                ],
                "action_count": 0,
                "execution_status": None,
                "feedback_status": None,
                "error": None,
                "progress": _progress(),
            }
        )


def test_demo_run_stream_event_models_validate_public_payloads() -> None:
    summary = DemoRunSummary.model_validate(
        {
            "run_id": str(uuid4()),
            "status": "awaiting_confirmation",
            "read_profile": "mock_world",
            "selected_plan_id": None,
            "plan_version": {
                "version_number": 1,
                "version_label": "v1",
                "source_run_id": None,
                "source_selected_plan_id": None,
            },
            "plans": [],
            "action_count": 0,
            "execution_status": None,
            "feedback_status": None,
            "error": None,
            "clarification": None,
            "progress": _progress(),
        }
    )

    progress_event = DemoRunStreamProgressEvent.model_validate(
        {
            "event_index": 1,
            "run_id": str(uuid4()),
            "progress": _progress(),
        }
    )
    summary_event = DemoRunStreamSummaryEvent(event_index=2, summary=summary)
    error_event = DemoRunStreamErrorEvent.model_validate(
        {
            "event_index": 3,
            "run_id": None,
            "message": "AMAP read path is not configured for this environment.",
        }
    )

    assert progress_event.event_index == 1
    assert progress_event.progress.current_stage == "ready_for_confirmation"
    assert summary_event.summary.run_id == summary.run_id
    assert error_event.message == "AMAP read path is not configured for this environment."
