from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ConversationSessionRepository,
    ConversationTurnRepository,
    MemoryItemRepository,
    ToolEventRepository,
    UserRepository,
)


@pytest.fixture
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def create_user(session: Session):
    return UserRepository(session).create(
        external_id=f"user-{uuid4()}",
        display_name="Weekend Pilot Tester",
    )


def create_run(session: Session, user_id):
    return AgentRunRepository(session).create(
        user_id=user_id,
        case_id="case-family-afternoon",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock",
        world_profile="family-demo",
        failure_profile=None,
        status="running",
        metadata_json={"source": "test"},
    )


def test_user_repository_creates_and_gets_user_by_external_id(db_session: Session) -> None:
    repo = UserRepository(db_session)
    external_id = f"user-{uuid4()}"

    user = repo.create(external_id=external_id, display_name="Alice")

    assert user.user_id is not None
    assert repo.get_by_id(user.user_id) is user
    assert repo.get_by_external_id(external_id) is user
    assert repo.get_by_external_id("missing-user") is None


def test_agent_run_repository_creates_gets_and_updates_status(db_session: Session) -> None:
    user = create_user(db_session)
    repo = AgentRunRepository(db_session)

    run = repo.create(
        user_id=user.user_id,
        case_id="case-001",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock",
        world_profile="default",
        failure_profile="none",
        status="running",
        metadata_json={"case": "001"},
    )

    assert run.run_id is not None
    assert repo.get_by_id(run.run_id) is run
    updated = repo.update_status(run.run_id, "completed")
    assert updated is run
    assert updated.status == "completed"
    assert repo.update_status(uuid4(), "failed") is None


def test_agent_run_repository_updates_session_link(db_session: Session) -> None:
    user = create_user(db_session)
    session_row = ConversationSessionRepository(db_session).create(
        user_id=user.user_id,
        channel="web_demo",
        status="active",
        metadata_json={"source": "test"},
    )
    run = create_run(db_session, user.user_id)

    updated = AgentRunRepository(db_session).update_session_id(run.run_id, session_row.session_id)

    assert updated is run
    assert updated.session_id == session_row.session_id
    assert AgentRunRepository(db_session).update_session_id(uuid4(), session_row.session_id) is None


def test_conversation_repositories_create_and_list_session_turns(db_session: Session) -> None:
    user = create_user(db_session)
    run = create_run(db_session, user.user_id)
    sessions = ConversationSessionRepository(db_session)
    turns = ConversationTurnRepository(db_session)

    session_row = sessions.create(
        user_id=user.user_id,
        channel="web_demo",
        status="active",
        metadata_json={"source": "test"},
    )
    first = turns.append(
        session_id=session_row.session_id,
        run_id=run.run_id,
        speaker_role="user",
        turn_type="user_request",
        content_text="Start planning",
        payload_json={},
    )
    second = turns.append(
        session_id=session_row.session_id,
        run_id=run.run_id,
        speaker_role="assistant",
        turn_type="assistant_plan_options",
        content_text="Here are the plan options.",
        payload_json={"plan_count": 1},
    )

    assert sessions.get_by_id(session_row.session_id) is session_row
    assert sessions.list_for_user(user.user_id) == [session_row]
    assert first.turn_index == 1
    assert second.turn_index == 2
    assert turns.get_by_id(first.turn_id) is first
    assert turns.list_for_session(session_row.session_id) == [first, second]
    assert turns.list_for_run(run.run_id) == [first, second]


def test_memory_item_repository_creates_and_lists_active_memory(db_session: Session) -> None:
    user = create_user(db_session)
    run = create_run(db_session, user.user_id)
    repo = MemoryItemRepository(db_session)

    active = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="diet",
        value_json={"value": "light"},
        text="Prefers lighter meals.",
        confidence=Decimal("0.9000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-active",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        status="active",
    )
    expired = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="expired",
        value_json={"value": "old"},
        text="Expired memory.",
        confidence=Decimal("0.7000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-expired",
        expires_at=datetime.now(UTC) - timedelta(days=1),
        status="active",
    )
    explicit_expired = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="explicit-expired",
        value_json={"value": "very old"},
        text="Explicitly expired memory.",
        confidence=Decimal("0.7000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-explicit-expired",
        expires_at=None,
        status="expired",
    )
    archived = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="archived",
        value_json={"value": "archived"},
        text="Archived memory.",
        confidence=Decimal("0.7000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-archived",
        expires_at=None,
        status="archived",
    )
    repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="candidate",
        value_json={"value": "candidate"},
        text="Candidate memory.",
        confidence=Decimal("0.7000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-candidate",
        expires_at=None,
        status="candidate",
    )
    repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="disabled",
        value_json={"value": "disabled"},
        text="Disabled memory.",
        confidence=Decimal("0.7000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-disabled",
        expires_at=None,
        status="disabled",
    )
    repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="ignored",
        value_json={"value": "ignored"},
        text="Ignored memory.",
        confidence=Decimal("0.7000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id="trace-ignored",
        expires_at=None,
        status="ignored",
    )

    assert repo.get_by_id(active.memory_id) is active
    assert archived.status == "ignored"
    assert repo.list_active_for_user(user.user_id) == [active]
    assert {item.memory_id for item in repo.list_governable_for_user(user.user_id)} == {
        active.memory_id,
        expired.memory_id,
        explicit_expired.memory_id,
    }
    assert repo.list_active_for_user(uuid4()) == []
    assert repo.list_governable_for_user(uuid4()) == []


def test_memory_item_repository_list_for_user_returns_all_rows_in_creation_order(db_session: Session) -> None:
    user = create_user(db_session)
    run = create_run(db_session, user.user_id)
    repo = MemoryItemRepository(db_session)

    first = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="first",
        value_json={"preference": "indoor"},
        text="first",
        confidence=Decimal("0.9000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="active",
    )
    second = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="second",
        value_json={"preference": "outdoor"},
        text="second",
        confidence=Decimal("0.9000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="disabled",
    )

    rows = repo.list_for_user(user.user_id)
    expected_rows = sorted([first, second], key=lambda row: (row.created_at, row.memory_id))
    assert [row.memory_id for row in rows] == [row.memory_id for row in expected_rows]
    assert [row.status for row in rows] == [row.status for row in expected_rows]
    assert [row.metadata_json for row in rows] == [{}, {}]


def test_memory_item_repository_update_status_and_metadata_persists_governance_audit(db_session: Session) -> None:
    user = create_user(db_session)
    run = create_run(db_session, user.user_id)
    repo = MemoryItemRepository(db_session)
    memory = repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="controlled",
        value_json={"preference": "indoor"},
        text="controlled",
        confidence=Decimal("0.9000"),
        source_run_id=run.run_id,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="active",
    )
    original_updated_at = memory.updated_at

    updated = repo.update_status_and_metadata(
        memory.memory_id,
        status="disabled",
        metadata_json={
            "governance": {
                "control_events": [
                    {
                        "schema_version": "memory_user_control_v0",
                        "action": "disable",
                        "from_status": "active",
                        "to_status": "disabled",
                        "actor": "user",
                        "source": "internal_memory_api_v0",
                        "reason": "user_requested_control",
                        "acted_at": "2026-06-16T10:15:00+00:00",
                    }
                ]
            }
        },
    )

    assert updated is not None
    assert updated.status == "disabled"
    assert updated.metadata_json["governance"]["control_events"][0]["action"] == "disable"
    assert updated.updated_at >= original_updated_at


def test_tool_event_repository_creates_gets_and_lists_by_run(db_session: Session) -> None:
    user = create_user(db_session)
    run = create_run(db_session, user.user_id)
    other_run = create_run(db_session, user.user_id)
    repo = ToolEventRepository(db_session)

    event = repo.create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="mock_world",
        request_json={"query": "museum"},
        response_json={"results": []},
        error_json=None,
        status="succeeded",
        cache_hit=False,
        latency_ms=42,
        langsmith_trace_id="trace-tool",
    )
    repo.create(
        run_id=other_run.run_id,
        tool_name="check_weather",
        tool_type="read",
        provider="mock_world",
        request_json={},
        response_json={"weather": "clear"},
        error_json=None,
        status="succeeded",
        cache_hit=True,
        latency_ms=10,
        langsmith_trace_id=None,
    )

    assert repo.get_by_id(event.event_id) is event
    assert repo.list_for_run(run.run_id) == [event]
    assert repo.list_for_run(uuid4()) == []


def test_action_ledger_repository_creates_gets_and_updates_status(db_session: Session) -> None:
    user = create_user(db_session)
    run = create_run(db_session, user.user_id)
    repo = ActionLedgerRepository(db_session)
    idempotency_key = f"reserve-{uuid4()}"

    action = repo.create(
        run_id=run.run_id,
        action_type="reserve_restaurant",
        target_id="restaurant-123",
        idempotency_key=idempotency_key,
        status="pending",
        request_json={"party_size": 3},
    )

    assert repo.get_by_id(action.action_id) is action
    assert repo.get_by_idempotency_key(idempotency_key) is action

    updated = repo.update_status(
        action.action_id,
        "succeeded",
        response_json={"confirmation": "ok"},
    )
    assert updated is action
    assert updated.status == "succeeded"
    assert updated.response_json == {"confirmation": "ok"}
    assert updated.error_json is None
    assert repo.update_status(uuid4(), "failed", error_json={"code": "missing"}) is None


def test_repositories_do_not_self_commit() -> None:
    external_id = f"rollback-user-{uuid4()}"
    idempotency_key = f"rollback-action-{uuid4()}"

    session = SessionLocal()
    try:
        user = UserRepository(session).create(
            external_id=external_id,
            display_name="Rollback User",
        )
        run = create_run(session, user.user_id)
        conversation_session = ConversationSessionRepository(session).create(
            user_id=user.user_id,
            channel="web_demo",
            status="active",
            metadata_json={"source": "rollback-test"},
        )
        AgentRunRepository(session).update_session_id(run.run_id, conversation_session.session_id)
        turn = ConversationTurnRepository(session).append(
            session_id=conversation_session.session_id,
            run_id=run.run_id,
            speaker_role="user",
            turn_type="user_request",
            content_text="Not committed",
            payload_json={},
        )
        memory = MemoryItemRepository(session).create(
            user_id=user.user_id,
            memory_type="preference",
            key="rollback-memory",
            value_json={"value": "not committed"},
            text=None,
            confidence=Decimal("0.5000"),
            source_run_id=run.run_id,
            source_langsmith_trace_id=None,
            expires_at=None,
            status="active",
        )
        event = ToolEventRepository(session).create(
            run_id=run.run_id,
            tool_name="search_poi",
            tool_type="read",
            provider="mock_world",
            request_json={},
            response_json={},
            error_json=None,
            status="succeeded",
            cache_hit=False,
            latency_ms=None,
            langsmith_trace_id=None,
        )
        action = ActionLedgerRepository(session).create(
            run_id=run.run_id,
            action_type="join_queue",
            target_id="queue-rollback",
            idempotency_key=idempotency_key,
            status="pending",
            request_json={},
        )
        user_id = user.user_id
        run_id = run.run_id
        conversation_session_id = conversation_session.session_id
        turn_id = turn.turn_id
        memory_id = memory.memory_id
        event_id = event.event_id
        action_id = action.action_id
        session.rollback()
    finally:
        session.close()

    verification_session = SessionLocal()
    try:
        assert UserRepository(verification_session).get_by_external_id(external_id) is None
        assert UserRepository(verification_session).get_by_id(user_id) is None
        assert AgentRunRepository(verification_session).get_by_id(run_id) is None
        assert ConversationSessionRepository(verification_session).get_by_id(conversation_session_id) is None
        assert ConversationTurnRepository(verification_session).get_by_id(turn_id) is None
        assert MemoryItemRepository(verification_session).get_by_id(memory_id) is None
        assert ToolEventRepository(verification_session).get_by_id(event_id) is None
        assert ActionLedgerRepository(verification_session).get_by_id(action_id) is None
        assert ActionLedgerRepository(verification_session).get_by_idempotency_key(idempotency_key) is None
    finally:
        verification_session.close()
