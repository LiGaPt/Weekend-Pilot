from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.db.session import SessionLocal
from backend.app.memory_control import (
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryUserControlService,
)
from backend.app.repositories import AgentRunRepository, MemoryItemRepository, UserRepository


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _create_user_and_run(session):
    user = UserRepository(session).create(
        external_id=f"memory-crud-user-{uuid4()}",
        display_name="Memory CRUD Tester",
    )
    run = AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-memory-crud",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "memory-crud-test"},
    )
    return user, run


def _seed_memory(
    session,
    *,
    user_id,
    run_id,
    key="activity_style",
    status="active",
    value_json=None,
    text="indoor",
    confidence=Decimal("0.9000"),
    expires_at=None,
    metadata_json=None,
):
    return MemoryItemRepository(session).create(
        user_id=user_id,
        memory_type="preference",
        key=key,
        value_json=value_json or {"preference": "indoor"},
        text=text,
        confidence=confidence,
        source_run_id=run_id,
        source_langsmith_trace_id="trace-1",
        expires_at=expires_at,
        status=status,
        metadata_json=metadata_json,
    )


def test_memory_create_persists_supported_row_and_governance_event(db_session) -> None:
    user, run = _create_user_and_run(db_session)

    response = MemoryUserControlService(db_session).create_item(
        user.user_id,
        MemoryCreateRequest(
            memory_type="preference",
            key="activity_style",
            value_json={"preference": "indoor"},
            text="indoor",
            confidence=Decimal("0.9000"),
            status="active",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            source_run_id=run.run_id,
            source_langsmith_trace_id="trace-memory-create",
            reason="manual_memory_seed",
        ),
    )

    assert response.operation == "create"
    assert response.applied is True
    assert response.item.memory_type == "preference"
    assert response.item.key == "activity_style"
    assert response.item.status == "active"
    assert response.item.value_json == {"preference": "indoor"}
    assert response.item.text is None
    assert response.item.source_run_id == run.run_id
    assert response.item.source_langsmith_trace_id == "trace-memory-create"
    assert response.item.governance_audit.audit_status == "trusted"
    assert response.item.governance_audit.normalized_value == "indoor"
    control_events = response.item.metadata_json["governance"]["control_events"]
    assert control_events[0]["schema_version"] == "memory_crud_governance_v0"
    assert control_events[0]["action"] == "create"
    assert control_events[0]["from_status"] is None
    assert control_events[0]["to_status"] == "active"
    assert control_events[0]["changed_fields"] == [
        "memory_type",
        "key",
        "value_json",
        "text",
        "confidence",
        "status",
        "expires_at",
        "source_run_id",
        "source_langsmith_trace_id",
    ]
    minimization_events = response.item.metadata_json["governance"]["minimization_events"]
    assert minimization_events[0]["schema_version"] == "memory_audit_minimization_v0"
    assert minimization_events[0]["action"] == "create"
    assert minimization_events[0]["normalized_value"] == "indoor"
    assert minimization_events[0]["dropped_text"] is True
    assert minimization_events[0]["dropped_value_keys"] == []


def test_memory_create_rejects_duplicate_user_memory_key(db_session) -> None:
    user, run = _create_user_and_run(db_session)
    _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)

    with pytest.raises(Exception, match="already exists|Duplicate|exists"):
        MemoryUserControlService(db_session).create_item(
            user.user_id,
            MemoryCreateRequest(
                memory_type="preference",
                key="activity_style",
                value_json={"preference": "indoor"},
                text="indoor",
                confidence=Decimal("0.9000"),
                status="active",
                expires_at=None,
                source_run_id=run.run_id,
                source_langsmith_trace_id="trace-duplicate",
                reason="duplicate_seed",
            ),
        )


def test_memory_create_rejects_unsupported_value(db_session) -> None:
    user, run = _create_user_and_run(db_session)

    with pytest.raises(Exception, match="Unsupported|Invalid|normalize"):
        MemoryUserControlService(db_session).create_item(
            user.user_id,
            MemoryCreateRequest(
                memory_type="preference",
                key="activity_style",
                value_json={"preference": "museum"},
                text="museum",
                confidence=Decimal("0.9000"),
                status="active",
                expires_at=None,
                source_run_id=run.run_id,
                source_langsmith_trace_id=None,
                reason="invalid_value",
            ),
        )


def test_memory_get_and_update_item_preserve_identity_and_provenance(db_session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)
    service = MemoryUserControlService(db_session)

    detail = service.get_item(user.user_id, memory.memory_id)
    assert detail.memory_id == memory.memory_id
    assert detail.source_run_id == run.run_id

    response = service.update_item(
        user.user_id,
        memory.memory_id,
        MemoryUpdateRequest(
            value_json={"preference": "outdoor"},
            text="outdoor",
            confidence=Decimal("0.7000"),
            expires_at=datetime.now(UTC) + timedelta(days=1),
            reason="user_refined_preference",
        ),
    )

    assert response.operation == "update"
    assert response.applied is True
    assert response.item.memory_id == memory.memory_id
    assert response.item.key == "activity_style"
    assert response.item.source_run_id == run.run_id
    assert response.item.source_langsmith_trace_id == "trace-1"
    assert response.item.status == "active"
    assert response.item.value_json == {"preference": "outdoor"}
    assert response.item.text is None
    assert response.item.governance_audit.audit_status == "advisory"
    assert response.item.governance_audit.audit_reason == "low_confidence_downgraded_to_advisory"
    event = response.item.metadata_json["governance"]["control_events"][0]
    assert event["action"] == "update"
    assert sorted(event["changed_fields"]) == ["confidence", "expires_at", "text", "value_json"]
    minimization_event = response.item.metadata_json["governance"]["minimization_events"][0]
    assert minimization_event["action"] == "update"
    assert minimization_event["normalized_value"] == "outdoor"
    assert minimization_event["dropped_text"] is True
    assert minimization_event["dropped_value_keys"] == []


def test_memory_update_drops_extra_value_json_keys_and_tracks_them(db_session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)

    response = MemoryUserControlService(db_session).update_item(
        user.user_id,
        memory.memory_id,
        MemoryUpdateRequest(
            value_json={"preference": "outdoor", "address": "hidden", "note": "drop"},
            text="outdoor",
            confidence=Decimal("0.9000"),
            expires_at=None,
            reason="minimize_manual_memory",
        ),
    )

    assert response.item.value_json == {"preference": "outdoor"}
    assert response.item.text is None
    minimization_event = response.item.metadata_json["governance"]["minimization_events"][0]
    assert minimization_event["dropped_value_keys"] == ["address", "note"]


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("activate", "active"),
        ("disable", "disabled"),
        ("suppress", "ignored"),
        ("expire", "expired"),
        ("mark_candidate", "candidate"),
    ],
)
def test_memory_control_actions_map_to_expected_statuses(db_session, action: str, expected_status: str) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, status="active")

    response = MemoryUserControlService(db_session).apply_action(
        user.user_id,
        memory.memory_id,
        action,
        "state_change",
    )

    assert response.operation == action
    assert response.item.status == expected_status


def test_memory_delete_logically_suppresses_row(db_session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)

    response = MemoryUserControlService(db_session).delete_item(
        user.user_id,
        memory.memory_id,
        "remove_from_future_planning",
    )

    assert response.operation == "suppress"
    assert response.applied is True
    assert response.item.status == "ignored"
    assert response.item.lifecycle_state == "ignored"
