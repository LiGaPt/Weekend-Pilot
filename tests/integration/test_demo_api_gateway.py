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
from backend.app.models.runtime import ActionLedger, AgentRun, ConversationSession, ConversationTurn, ToolEvent, User
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


def _load_run(session: Session, run_id: UUID) -> AgentRun:
    run = session.get(AgentRun, run_id)
    assert run is not None
    return run


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


def _assert_plan_version(
    payload: dict[str, object],
    *,
    version_number: int,
    source_run_id: str | None,
    source_selected_plan_id: str | None,
) -> None:
    assert payload["plan_version"] == {
        "version_number": version_number,
        "version_label": f"v{version_number}",
        "source_run_id": source_run_id,
        "source_selected_plan_id": source_selected_plan_id,
    }


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
    _assert_plan_version(
        start_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    assert start_body["plans"][0]["confirmation"] is None
    run_id = UUID(start_body["run_id"])

    db = SessionLocal()
    try:
        assert _count_actions(db, run_id) == 0
        run = _load_run(db, run_id)
        assert run.session_id is not None
        conversation_session = db.get(ConversationSession, run.session_id)
        assert conversation_session is not None
        assert conversation_session.user_id == run.user_id
        assert conversation_session.channel == "web_demo"
        assert conversation_session.status == "active"
        assert conversation_session.metadata_json == {
            "source": "demo_api_v1",
            "case_id": case_ids[0],
            "selected_plan_index": 0,
        }
        turns = list(
            db.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == run.session_id)
                .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
            ).all()
        )
        assert len(turns) == 2
        assert turns[0].turn_index == 1
        assert turns[0].speaker_role == "user"
        assert turns[0].turn_type == "user_request"
        assert turns[0].content_text == USER_INPUT
        assert turns[0].payload_json == {}
        assert turns[1].turn_index == 2
        assert turns[1].speaker_role == "assistant"
        assert turns[1].turn_type == "assistant_plan_options"
        assert isinstance(turns[1].content_text, str)
        assert turns[1].content_text
        assert turns[1].payload_json == {
            "selected_plan_id": start_body["selected_plan_id"],
            "plan_ids": [plan["plan_id"] for plan in start_body["plans"]],
            "plan_count": len(start_body["plans"]),
            "run_status": "awaiting_confirmation",
        }
        assert "draft" not in turns[1].payload_json
        assert "plan_json" not in turns[1].payload_json
    finally:
        db.close()

    status_response = test_client.get(f"/demo/runs/{run_id}")

    assert status_response.status_code == 200
    status_body = status_response.json()
    _assert_public_run_redaction(status_body)
    assert status_body["run_id"] == str(run_id)
    assert status_body["selected_plan_id"] == start_body["selected_plan_id"]
    assert status_body["action_count"] == 0
    _assert_plan_version(
        status_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )

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
    _assert_plan_version(
        confirm_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
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
    _assert_plan_version(
        payload,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )
    assert "trace_id" not in payload
    assert "tool_event_count" not in payload
    assert "node_history" not in payload
    assert "observability_status" not in payload
    assert "agent_roles" not in payload
    assert "workflow_timing_summary" not in payload
    _assert_no_forbidden_keys(payload)


def test_demo_run_replan_reuses_session_and_returns_new_run(client) -> None:
    test_client, case_ids, external_user_ids = client
    start_response = test_client.post("/demo/runs", json=_start_payload(case_ids, external_user_ids))

    assert start_response.status_code == 200
    source_body = start_response.json()
    source_run_id = UUID(source_body["run_id"])
    source_selected_plan_id = source_body["selected_plan_id"]
    _assert_plan_version(
        source_body,
        version_number=1,
        source_run_id=None,
        source_selected_plan_id=None,
    )

    replan_response = test_client.post(
        f"/demo/runs/{source_run_id}/replan",
        json={
            "user_input": "Keep it nearby, but make dinner lighter and stay flexible.",
            "selected_plan_index": 0,
        },
    )

    assert replan_response.status_code == 200
    replan_body = replan_response.json()
    _assert_no_forbidden_keys(replan_body)
    _assert_public_run_redaction(replan_body)
    assert UUID(replan_body["run_id"]) != source_run_id
    assert replan_body["status"] == "awaiting_confirmation"
    assert "session_id" not in replan_body
    assert "conversation" not in replan_body
    _assert_plan_version(
        replan_body,
        version_number=2,
        source_run_id=str(source_run_id),
        source_selected_plan_id=source_selected_plan_id,
    )

    second_replan_response = test_client.post(
        f"/demo/runs/{replan_body['run_id']}/replan",
        json={
            "user_input": "Keep it nearby again, but reduce walking even more.",
            "selected_plan_index": 0,
        },
    )

    assert second_replan_response.status_code == 200
    second_replan_body = second_replan_response.json()
    _assert_no_forbidden_keys(second_replan_body)
    _assert_public_run_redaction(second_replan_body)
    assert second_replan_body["run_id"] not in {str(source_run_id), replan_body["run_id"]}
    _assert_plan_version(
        second_replan_body,
        version_number=3,
        source_run_id=replan_body["run_id"],
        source_selected_plan_id=replan_body["selected_plan_id"],
    )

    status_response = test_client.get(f"/demo/runs/{source_run_id}")
    assert status_response.status_code == 200
    source_after = status_response.json()
    assert source_after["run_id"] == str(source_run_id)
    assert source_after["status"] == source_body["status"]
    assert source_after["selected_plan_id"] == source_selected_plan_id
    assert source_after["plan_version"] == source_body["plan_version"]

    first_replan_status_response = test_client.get(f"/demo/runs/{replan_body['run_id']}")
    assert first_replan_status_response.status_code == 200
    first_replan_after = first_replan_status_response.json()
    assert first_replan_after["run_id"] == replan_body["run_id"]
    assert first_replan_after["selected_plan_id"] == replan_body["selected_plan_id"]
    assert first_replan_after["plan_version"] == replan_body["plan_version"]

    db = SessionLocal()
    try:
        source_run = _load_run(db, source_run_id)
        replan_run = _load_run(db, UUID(replan_body["run_id"]))
        second_replan_run = _load_run(db, UUID(second_replan_body["run_id"]))
        assert replan_run.user_id == source_run.user_id
        assert replan_run.session_id == source_run.session_id
        assert second_replan_run.user_id == source_run.user_id
        assert second_replan_run.session_id == source_run.session_id
        turns = list(
            db.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.session_id == source_run.session_id)
                .order_by(ConversationTurn.turn_index, ConversationTurn.turn_id)
            ).all()
        )
        assert [turn.turn_type for turn in turns] == [
            "user_request",
            "assistant_plan_options",
            "user_follow_up",
            "assistant_replan_options",
            "user_follow_up",
            "assistant_replan_options",
        ]
        assert turns[2].run_id == replan_run.run_id
        assert turns[2].payload_json == {
            "mode": "replan",
            "source_run_id": str(source_run.run_id),
            "source_selected_plan_id": source_selected_plan_id,
        }
        assert turns[3].run_id == replan_run.run_id
        assert turns[3].payload_json == {
            "mode": "replan",
            "source_run_id": str(source_run.run_id),
            "selected_plan_id": replan_body["selected_plan_id"],
            "plan_ids": [plan["plan_id"] for plan in replan_body["plans"]],
            "plan_count": len(replan_body["plans"]),
            "run_status": "awaiting_confirmation",
        }
        assert turns[4].run_id == second_replan_run.run_id
        assert turns[4].payload_json == {
            "mode": "replan",
            "source_run_id": str(replan_run.run_id),
            "source_selected_plan_id": replan_body["selected_plan_id"],
        }
        assert turns[5].run_id == second_replan_run.run_id
        assert turns[5].payload_json == {
            "mode": "replan",
            "source_run_id": str(replan_run.run_id),
            "selected_plan_id": second_replan_body["selected_plan_id"],
            "plan_ids": [plan["plan_id"] for plan in second_replan_body["plans"]],
            "plan_count": len(second_replan_body["plans"]),
            "run_status": "awaiting_confirmation",
        }
        assert "draft" not in turns[3].payload_json
        assert "plan_json" not in turns[3].payload_json
        assert "draft" not in turns[5].payload_json
        assert "plan_json" not in turns[5].payload_json
        assert isinstance(replan_run.metadata_json, dict)
        assert replan_run.metadata_json["demo"]["conversation"]["mode"] == "follow_up_replan_v0"
        assert replan_run.metadata_json["demo"]["conversation"]["source_run_id"] == str(source_run.run_id)
        assert replan_run.metadata_json["demo"]["conversation"]["source_selected_plan_id"] == source_selected_plan_id
        assert source_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 1,
            "source_run_id": None,
            "source_selected_plan_id": None,
        }
        assert replan_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 2,
            "source_run_id": str(source_run.run_id),
            "source_selected_plan_id": source_selected_plan_id,
        }
        assert second_replan_run.metadata_json["demo"]["plan_version"] == {
            "version_number": 3,
            "source_run_id": str(replan_run.run_id),
            "source_selected_plan_id": replan_body["selected_plan_id"],
        }
    finally:
        db.close()
