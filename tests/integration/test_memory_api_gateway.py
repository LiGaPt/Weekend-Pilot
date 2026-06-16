from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal, get_db
from backend.app.main import create_app
from backend.app.repositories import AgentRunRepository, MemoryItemRepository, UserRepository


@pytest.fixture()
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def memory_client():
    app = create_app()

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_user_and_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"memory-api-user-{uuid4()}",
        display_name="Memory API Tester",
    )
    run = AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-memory-api",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "memory-api-test"},
    )
    return user, run


def _seed_memory(session: Session, *, user_id, run_id, key: str, status: str):
    return MemoryItemRepository(session).create(
        user_id=user_id,
        memory_type="preference",
        key=key,
        value_json={"preference": key},
        text=key,
        confidence=Decimal("0.9000"),
        source_run_id=run_id,
        source_langsmith_trace_id="trace-1",
        expires_at=None,
        status=status,
    )


def test_memory_list_route_returns_all_user_rows(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)
    first = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="active", status="active")
    second = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="disabled", status="disabled")
    db_session.commit()

    response = memory_client.get(f"/internal/users/{user.user_id}/memory")
    expected_rows = sorted([first, second], key=lambda row: (row.created_at, row.memory_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "memory_user_control_list_v0"
    assert payload["user_id"] == str(user.user_id)
    assert [item["key"] for item in payload["items"]] == [row.key for row in expected_rows]
    assert [item["lifecycle_state"] for item in payload["items"]] == [row.status for row in expected_rows]


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("disable", "disabled"),
        ("suppress", "ignored"),
    ],
)
def test_memory_control_route_updates_row_and_reports_audit_event(
    memory_client: TestClient,
    db_session: Session,
    action: str,
    expected_status: str,
) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key=action, status="active")
    db_session.commit()

    response = memory_client.post(
        f"/internal/users/{user.user_id}/memory/{memory.memory_id}/control",
        json={"action": action, "reason": "user_requested_control"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "memory_user_control_item_v0"
    assert payload["operation"] == action
    assert payload["applied"] is True
    assert payload["item"]["status"] == expected_status
    assert payload["item"]["lifecycle_state"] == expected_status
    assert payload["item"]["metadata_json"]["governance"]["control_events"][0]["action"] == action


def test_memory_control_route_is_idempotent_for_matching_status(
    memory_client: TestClient,
    db_session: Session,
) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="disabled", status="disabled")
    db_session.commit()

    response = memory_client.post(
        f"/internal/users/{user.user_id}/memory/{memory.memory_id}/control",
        json={"action": "disable", "reason": "duplicate"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is False
    assert payload["item"]["status"] == "disabled"
    assert payload["item"]["metadata_json"] == {}


def test_memory_control_route_returns_404_for_cross_user_or_missing_row(
    memory_client: TestClient,
    db_session: Session,
) -> None:
    owner, run = _create_user_and_run(db_session)
    other_user, _ = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=owner.user_id, run_id=run.run_id, key="owner", status="active")
    db_session.commit()

    cross_user = memory_client.post(
        f"/internal/users/{other_user.user_id}/memory/{memory.memory_id}/control",
        json={"action": "disable", "reason": "wrong-user"},
    )
    missing = memory_client.post(
        f"/internal/users/{owner.user_id}/memory/{uuid4()}/control",
        json={"action": "disable", "reason": "missing"},
    )

    assert cross_user.status_code == 404
    assert missing.status_code == 404


def test_memory_control_route_rejects_invalid_action(
    memory_client: TestClient,
    db_session: Session,
) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="active", status="active")
    db_session.commit()

    response = memory_client.post(
        f"/internal/users/{user.user_id}/memory/{memory.memory_id}/control",
        json={"action": "delete", "reason": "invalid"},
    )

    assert response.status_code == 422
