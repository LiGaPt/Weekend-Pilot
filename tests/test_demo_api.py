from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.demo.schemas import DemoRunSummary, DemoStartRunRequest
from backend.app.demo.service import sanitize_demo_payload
from backend.app.main import create_app


def test_create_app_includes_demo_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/demo/runs" in paths
    assert "/demo/runs/{run_id}" in paths
    assert "/demo/runs/{run_id}/confirm" in paths
    assert "/demo/runs/{run_id}/decline" in paths


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
        trace_id="trace-123",
        status="awaiting_confirmation",
        selected_plan_id=plan_id,
        plans=[
            {
                "plan_id": plan_id,
                "status": "selected",
                "selected": True,
                "title": "徐汇亲子轻松下午",
                "summary": "一条适合亲子出行和清淡晚餐的方案。",
            }
        ],
        node_history=["initialize_run", "wait_confirmation"],
        tool_event_count=3,
        action_count=0,
        execution_status=None,
        feedback_status=None,
        observability_status=None,
        agent_roles=["supervisor", "discovery"],
        error=None,
    )

    dumped = summary.model_dump(mode="json")

    assert dumped["run_id"] == str(run_id)
    assert dumped["selected_plan_id"] == str(plan_id)
    assert dumped["plans"][0]["plan_id"] == str(plan_id)
