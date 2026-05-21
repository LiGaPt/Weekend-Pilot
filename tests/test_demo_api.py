from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.demo.schemas import DemoReplanRunRequest, DemoRunSummary, DemoStartRunRequest
from backend.app.demo.service import sanitize_demo_payload
from backend.app.main import create_app


def test_create_app_includes_demo_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/demo/runs" in paths
    assert "/demo/runs/{run_id}" in paths
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


def test_replan_request_rejects_empty_user_input() -> None:
    with pytest.raises(ValidationError):
        DemoReplanRunRequest(user_input="")


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
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["run_id"] == str(run_id)
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
            selected_plan_id=None,
            plans=[],
            action_count=0,
            execution_status=None,
            feedback_status=None,
            error=None,
        )


def test_demo_plan_preview_requires_action_manifest() -> None:
    with pytest.raises(ValidationError):
        DemoRunSummary.model_validate(
            {
                "run_id": str(uuid4()),
                "status": "awaiting_confirmation",
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
            }
        )
