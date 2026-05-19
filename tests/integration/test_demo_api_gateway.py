from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal, get_db
from backend.app.models.runtime import ActionLedger, AgentRun, ToolEvent, User
from backend.app.runtime import get_redis_client
from backend.app.main import create_app


TEST_PREFIX = "demo-api-gateway"
USER_INPUT = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
)
FORBIDDEN_RESPONSE_KEYS = {
    "action_id",
    "tool_event_id",
    "event_id",
    "idempotency_key",
    "api_key",
    "token",
    "secret",
    "authorization",
    "prompt",
    "debug_trace",
}
REDACTED_PUBLIC_RUN_FIELDS = {
    "trace_id",
    "tool_event_count",
    "node_history",
    "observability_status",
    "agent_roles",
}


@pytest.fixture()
def redis_client() -> Redis:
    client = get_redis_client()
    client.ping()
    return client


@pytest.fixture()
def trace_path() -> Path:
    directory = Path("var/test-traces") / str(uuid4())
    path = directory / "weekendpilot-traces.jsonl"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()
        if directory.exists():
            directory.rmdir()


@pytest.fixture()
def client(redis_client: Redis, trace_path: Path):
    app = create_app()
    case_ids: list[str] = []
    external_user_ids: list[str] = []
    settings = Settings(
        app_env=f"test-demo-api-{uuid4()}",
        local_trace_buffer_path=str(trace_path),
        langsmith_tracing=False,
    )

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client, case_ids, external_user_ids

    app.dependency_overrides.clear()
    cleanup = SessionLocal()
    try:
        if case_ids:
            cleanup.execute(delete(AgentRun).where(AgentRun.case_id.in_(case_ids)))
        if external_user_ids:
            cleanup.execute(delete(User).where(User.external_id.in_(external_user_ids)))
        cleanup.commit()
    finally:
        cleanup.close()


def _start_payload(case_ids: list[str], external_user_ids: list[str]) -> dict[str, str]:
    suffix = str(uuid4())
    case_id = f"{TEST_PREFIX}-{suffix}"
    external_user_id = f"{TEST_PREFIX}-user-{suffix}"
    case_ids.append(case_id)
    external_user_ids.append(external_user_id)
    return {
        "user_input": USER_INPUT,
        "external_user_id": external_user_id,
        "display_name": "Web Demo Gateway Tester",
        "case_id": case_id,
    }


def _count_actions(session: Session, run_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id)
        )
        or 0
    )


def _demo_trace_id(session: Session, run_id: UUID) -> str | None:
    run = session.get(AgentRun, run_id)
    if run is None or not isinstance(run.metadata_json, dict):
        return None
    demo = run.metadata_json.get("demo")
    if not isinstance(demo, dict):
        return None
    trace_id = demo.get("trace_id")
    return trace_id if isinstance(trace_id, str) else None


def _assert_no_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        forbidden = FORBIDDEN_RESPONSE_KEYS.intersection(value)
        assert forbidden == set()
        for child in value.values():
            _assert_no_forbidden_keys(child)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def _assert_public_run_redaction(payload: dict[str, object]) -> None:
    for key in REDACTED_PUBLIC_RUN_FIELDS:
        assert key not in payload


def test_demo_run_start_status_confirm_and_idempotent_replay(client) -> None:
    test_client, case_ids, external_user_ids = client

    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    start_body = start_response.json()
    _assert_no_forbidden_keys(start_body)
    _assert_public_run_redaction(start_body)
    assert start_body["status"] == "awaiting_confirmation"
    assert start_body["action_count"] == 0
    assert start_body["plans"]
    assert start_body["selected_plan_id"]
    assert start_body["plans"][0]["confirmation"] is None
    run_id = UUID(start_body["run_id"])

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
    finally:
        db.close()

    status_response = test_client.get(f"/demo/runs/{run_id}")

    assert status_response.status_code == 200
    status_body = status_response.json()
    _assert_public_run_redaction(status_body)
    assert status_body["run_id"] == str(run_id)
    assert status_body["selected_plan_id"] == start_body["selected_plan_id"]
    assert status_body["action_count"] == 0

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    _assert_no_forbidden_keys(confirm_body)
    _assert_public_run_redaction(confirm_body)
    assert confirm_body["run_id"] == str(run_id)
    assert confirm_body["status"] == "completed"
    assert confirm_body["action_count"] > 0
    assert confirm_body["feedback_status"] == "completed"
    selected = next(plan for plan in confirm_body["plans"] if plan["selected"])
    assert selected["confirmation"]["status"] == "confirmed"
    assert selected["execution"]["status"] == "succeeded"
    assert selected["feedback"]["status"] == "completed"

    db = SessionLocal()
    try:
        first_action_count = _count_actions(db, run_id)
        demo_trace_id = _demo_trace_id(db, run_id)
        write_trace_ids = set(
            db.scalars(
                select(ToolEvent.langsmith_trace_id).where(
                    ToolEvent.run_id == run_id,
                    ToolEvent.tool_type == "write",
                )
            ).all()
        )
        assert first_action_count == confirm_body["action_count"]
        assert demo_trace_id is not None
        assert write_trace_ids == {demo_trace_id}
    finally:
        db.close()

    second_confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert second_confirm_response.status_code == 200
    second_confirm_body = second_confirm_response.json()
    assert second_confirm_body["action_count"] == confirm_body["action_count"]

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == first_action_count
    finally:
        db.close()


def test_demo_run_decline_creates_no_actions_and_blocks_later_confirm(client) -> None:
    test_client, case_ids, external_user_ids = client
    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))
    assert start_response.status_code == 200
    run_id = start_response.json()["run_id"]

    decline_response = test_client.post(
        f"/demo/runs/{run_id}/decline",
        json={"declined_by": "web-demo-user", "reason": "用户选择暂不继续。"},
    )

    assert decline_response.status_code == 200
    decline_body = decline_response.json()
    assert decline_body["status"] == "declined"
    assert decline_body["action_count"] == 0
    selected = next(plan for plan in decline_body["plans"] if plan["selected"])
    assert selected["confirmation"]["status"] == "declined"

    db = SessionLocal()
    try:
        assert _count_actions(db, UUID(run_id)) == 0
    finally:
        db.close()

    confirm_response = test_client.post(
        f"/demo/runs/{run_id}/confirm",
        json={"confirmed_by": "web-demo-user"},
    )

    assert confirm_response.status_code == 409


def test_demo_run_unknown_run_returns_404(client) -> None:
    test_client, _, _ = client

    response = test_client.get(f"/demo/runs/{uuid4()}")

    assert response.status_code == 404


def test_demo_run_status_route_keeps_public_shape_after_internal_route_addition(client) -> None:
    test_client, case_ids, external_user_ids = client
    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    run_id = start_response.json()["run_id"]

    status_response = test_client.get(f"/demo/runs/{run_id}")

    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["run_id"] == run_id
    assert "plans" in payload
    assert "trace_id" not in payload
    assert "tool_event_count" not in payload
    assert "node_history" not in payload
    assert "observability_status" not in payload
    assert "agent_roles" not in payload
    assert "workflow_timing_summary" not in payload
    _assert_no_forbidden_keys(payload)
