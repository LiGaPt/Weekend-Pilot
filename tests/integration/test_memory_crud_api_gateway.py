from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
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
        external_id=f"memory-crud-api-user-{uuid4()}",
        display_name="Memory CRUD API Tester",
    )
    run = AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-memory-crud-api",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "memory-crud-api-test"},
    )
    return user, run


def _seed_memory(session: Session, *, user_id, run_id, key="activity_style", status="active"):
    return MemoryItemRepository(session).create(
        user_id=user_id,
        memory_type="preference",
        key=key,
        value_json={"preference": "indoor"},
        text="indoor",
        confidence=Decimal("0.9000"),
        source_run_id=run_id,
        source_langsmith_trace_id="trace-1",
        expires_at=None,
        status=status,
    )


def test_memory_create_and_detail_routes_return_created_item(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)
    db_session.commit()

    create_response = memory_client.post(
        f"/internal/users/{user.user_id}/memory",
        json={
            "memory_type": "preference",
            "key": "activity_style",
            "value_json": {"preference": "indoor"},
            "text": "indoor",
            "confidence": "0.9000",
            "status": "active",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "source_run_id": str(run.run_id),
            "source_langsmith_trace_id": "trace-memory-create",
            "reason": "manual_memory_seed",
        },
    )

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["operation"] == "create"
    assert payload["item"]["value_json"] == {"preference": "indoor"}
    assert payload["item"]["text"] is None
    assert payload["item"]["governance_audit"]["audit_status"] == "trusted"
    memory_id = payload["item"]["memory_id"]

    detail_response = memory_client.get(f"/internal/users/{user.user_id}/memory/{memory_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["memory_id"] == memory_id
    assert detail_payload["governance_audit"]["normalized_value"] == "indoor"


def test_memory_update_route_updates_mutable_fields(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)
    db_session.commit()

    response = memory_client.patch(
        f"/internal/users/{user.user_id}/memory/{memory.memory_id}",
        json={
            "value_json": {"preference": "outdoor"},
            "text": "outdoor",
            "confidence": "0.7000",
            "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": "user_refined_preference",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation"] == "update"
    assert payload["item"]["value_json"] == {"preference": "outdoor"}
    assert payload["item"]["text"] is None
    assert payload["item"]["governance_audit"]["audit_status"] == "advisory"
    assert payload["item"]["metadata_json"]["governance"]["minimization_events"][0]["action"] == "update"


def test_memory_delete_route_logically_suppresses_row(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)
    db_session.commit()

    response = memory_client.request(
        "DELETE",
        f"/internal/users/{user.user_id}/memory/{memory.memory_id}",
        json={"reason": "remove_from_future_planning"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation"] == "suppress"
    assert payload["item"]["status"] == "ignored"


def test_memory_create_route_rejects_duplicate_user_memory_key(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)
    _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)
    db_session.commit()

    response = memory_client.post(
        f"/internal/users/{user.user_id}/memory",
        json={
            "memory_type": "preference",
            "key": "activity_style",
            "value_json": {"preference": "indoor"},
            "text": "indoor",
            "confidence": "0.9000",
            "status": "active",
            "expires_at": None,
            "source_run_id": str(run.run_id),
            "source_langsmith_trace_id": None,
            "reason": "duplicate_seed",
        },
    )

    assert response.status_code == 409


def test_memory_crud_routes_return_404_for_cross_user_or_missing_row(memory_client: TestClient, db_session: Session) -> None:
    owner, run = _create_user_and_run(db_session)
    other_user, _ = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=owner.user_id, run_id=run.run_id)
    db_session.commit()

    cross_user = memory_client.get(f"/internal/users/{other_user.user_id}/memory/{memory.memory_id}")
    missing = memory_client.patch(
        f"/internal/users/{owner.user_id}/memory/{uuid4()}",
        json={
            "value_json": {"preference": "outdoor"},
            "text": "outdoor",
            "confidence": "0.7000",
            "expires_at": None,
            "reason": "missing",
        },
    )

    assert cross_user.status_code == 404
    assert missing.status_code == 404


def test_memory_create_route_rejects_invalid_payload(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)

    response = memory_client.post(
        f"/internal/users/{user.user_id}/memory",
        json={
            "memory_type": "preference",
            "key": "activity_style",
            "value_json": {"preference": "museum"},
            "text": "museum",
            "confidence": "0.9000",
            "status": "active",
            "expires_at": None,
            "source_run_id": str(run.run_id),
            "source_langsmith_trace_id": None,
            "reason": "invalid",
        },
    )

    assert response.status_code in {400, 422}


def test_memory_detail_route_reports_non_governable_candidate_audit(memory_client: TestClient, db_session: Session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, status="candidate")
    db_session.commit()

    response = memory_client.get(f"/internal/users/{user.user_id}/memory/{memory.memory_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance_audit"]["audit_status"] == "not_governable"
    assert payload["governance_audit"]["audit_reason"] == "non_governable_lifecycle"
