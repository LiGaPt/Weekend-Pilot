from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.db.session import SessionLocal
from backend.app.memory_control import MemoryUserControlService
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
        external_id=f"memory-control-user-{uuid4()}",
        display_name="Memory Control Tester",
    )
    run = AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-memory-control",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "memory-control-test"},
    )
    return user, run


def _seed_memory(
    session,
    *,
    user_id,
    run_id,
    status="active",
    key="activity_style",
    expires_at=None,
    metadata_json=None,
):
    return MemoryItemRepository(session).create(
        user_id=user_id,
        memory_type="preference",
        key=key,
        value_json={"preference": "indoor"},
        text="prefers indoor",
        confidence=Decimal("0.9000"),
        source_run_id=run_id,
        source_langsmith_trace_id="trace-1",
        expires_at=expires_at,
        status=status,
        metadata_json=metadata_json,
    )


def test_memory_user_control_action_contract_is_strict() -> None:
    from backend.app.memory_control.schemas import MemoryUserControlAction

    assert MemoryUserControlAction.__args__ == ("disable", "suppress")


def test_memory_user_control_list_includes_all_lifecycle_states(db_session) -> None:
    user, run = _create_user_and_run(db_session)
    now = datetime.now(UTC)
    active = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="active", status="active")
    expired = _seed_memory(
        db_session,
        user_id=user.user_id,
        run_id=run.run_id,
        key="expired-derived",
        status="active",
        expires_at=now - timedelta(minutes=5),
    )
    candidate = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="candidate", status="candidate")
    disabled = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="disabled", status="disabled")
    ignored = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id, key="ignored", status="ignored")

    response = MemoryUserControlService(db_session).list_items(user.user_id)
    expected_rows = sorted(
        [active, expired, candidate, disabled, ignored],
        key=lambda row: (row.created_at, row.memory_id),
    )

    assert response.schema_version == "memory_user_control_list_v0"
    assert [item.key for item in response.items] == [row.key for row in expected_rows]
    assert [item.lifecycle_state for item in response.items] == [
        "expired" if row.key == "expired-derived" else row.status for row in expected_rows
    ]


@pytest.mark.parametrize(
    ("action", "target_status"),
    [
        ("disable", "disabled"),
        ("suppress", "ignored"),
    ],
)
def test_memory_user_control_applies_status_and_appends_governance_event(
    db_session,
    action: str,
    target_status: str,
) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(db_session, user_id=user.user_id, run_id=run.run_id)

    response = MemoryUserControlService(db_session).apply_action(
        user.user_id,
        memory.memory_id,
        action,
        "user_requested_control",
    )

    assert response.applied is True
    assert response.operation == action
    assert response.item.status == target_status
    assert response.item.lifecycle_state == target_status
    assert response.item.value_json == {"preference": "indoor"}
    assert response.item.text == "prefers indoor"
    control_events = response.item.metadata_json["governance"]["control_events"]
    assert len(control_events) == 1
    assert control_events[0] == {
        "schema_version": "memory_user_control_v0",
        "action": action,
        "from_status": "active",
        "to_status": target_status,
        "actor": "user",
        "source": "internal_memory_api_v0",
        "reason": "user_requested_control",
        "acted_at": control_events[0]["acted_at"],
    }


@pytest.mark.parametrize(
    ("action", "starting_status"),
    [
        ("disable", "disabled"),
        ("suppress", "ignored"),
    ],
)
def test_memory_user_control_is_idempotent_for_matching_target_status(
    db_session,
    action: str,
    starting_status: str,
) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(
        db_session,
        user_id=user.user_id,
        run_id=run.run_id,
        status=starting_status,
        metadata_json={
            "governance": {
                "control_events": [
                    {
                        "schema_version": "memory_user_control_v0",
                        "action": action,
                        "from_status": "active",
                        "to_status": starting_status,
                        "actor": "user",
                        "source": "internal_memory_api_v0",
                        "reason": "first",
                        "acted_at": "2026-06-16T10:15:00+00:00",
                    }
                ]
            }
        },
    )

    response = MemoryUserControlService(db_session).apply_action(
        user.user_id,
        memory.memory_id,
        action,
        "duplicate",
    )

    assert response.applied is False
    assert response.item.status == starting_status
    assert response.item.metadata_json["governance"]["control_events"] == memory.metadata_json["governance"]["control_events"]


def test_memory_user_control_rebuilds_malformed_metadata_json(db_session) -> None:
    user, run = _create_user_and_run(db_session)
    memory = _seed_memory(
        db_session,
        user_id=user.user_id,
        run_id=run.run_id,
        metadata_json=["invalid"],
    )

    response = MemoryUserControlService(db_session).apply_action(
        user.user_id,
        memory.memory_id,
        "disable",
        None,
    )

    control_events = response.item.metadata_json["governance"]["control_events"]
    assert len(control_events) == 1
    assert control_events[0]["reason"] is None
