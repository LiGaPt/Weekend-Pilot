from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.confirmation import HumanConfirmationService, PlanConfirmationError
from backend.app.db.session import SessionLocal
from backend.app.repositories import AgentRunRepository, PlanRepository, UserRepository


@pytest.fixture()
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"human-confirmation-user-{uuid4()}",
        display_name="Human Confirmation Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-human-confirmation",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "human-confirmation-test"},
    )


def _action(
    action_ref: str = "draft_1_action_1",
    action_type: str = "reserve_restaurant",
    target_id: str = "dining_draft_1",
    **overrides,
) -> dict:
    action = {
        "action_ref": action_ref,
        "action_type": action_type,
        "target_id": target_id,
        "payload": {"party_size": 3},
        "requires_confirmation": True,
        "reason": "Table availability is available.",
    }
    action.update(overrides)
    return action


def _reviewed_plan_json(
    run_id: UUID,
    *,
    safe_to_present: bool = True,
    actions: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": "reviewed_plan_v1",
        "persistence_version": "reviewed_plan_persistence_v1",
        "run_id": str(run_id),
        "provider_profile": "mock_world",
        "draft_id": "draft_1",
        "status": "reviewed",
        "safe_to_present": safe_to_present,
        "review_decision": "approved",
        "draft": {
            "draft_id": "draft_1",
            "status": "draft",
            "title": "Plan draft_1",
            "summary": "A reviewed family afternoon plan.",
            "activity": {"candidate_id": "activity_draft_1"},
            "dining": {"candidate_id": "dining_draft_1"},
            "proposed_actions": [_action()] if actions is None else actions,
        },
        "reviewed_draft": {
            "draft_id": "draft_1",
            "decision": "approved",
            "safe_to_present": safe_to_present,
            "checks": [],
            "errors": [],
            "warnings": [],
        },
        "final_review": {
            "decision": "approved",
            "safe_to_present": safe_to_present,
            "gate_version": "test-gate",
        },
        "source_versions": {
            "generator_version": "test-generator",
            "gate_version": "test-gate",
            "persistence_version": "reviewed_plan_persistence_v1",
        },
    }


def _create_plan(
    session: Session,
    *,
    run_id: UUID | None = None,
    status: str = "selected",
    selected: bool = True,
    plan_json: dict | None = None,
):
    if run_id is None:
        run_id = _create_run(session).run_id
    return PlanRepository(session).create(
        run_id=run_id,
        status=status,
        selected=selected,
        plan_json=_reviewed_plan_json(run_id) if plan_json is None else plan_json,
    )


def test_plan_repository_update_plan_json_and_get_selected_for_run(db_session: Session) -> None:
    run = _create_run(db_session)
    repo = PlanRepository(db_session)
    selected = repo.create(
        run_id=run.run_id,
        status="selected",
        selected=True,
        plan_json=_reviewed_plan_json(run.run_id),
    )

    assert repo.get_selected_for_run(run.run_id) is selected

    updated_json = {**selected.plan_json, "confirmation": {"status": "confirmed"}}
    updated = repo.update_plan_json(selected.plan_id, updated_json)

    assert updated is selected
    assert selected.plan_json["confirmation"] == {"status": "confirmed"}


def test_selected_reviewed_plan_can_be_confirmed(db_session: Session) -> None:
    plan = _create_plan(db_session)
    timestamp = datetime(2026, 5, 14, 9, 30, tzinfo=UTC)

    result = HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        plan.run_id,
        plan.plan_id,
        confirmed_by="user",
        source="cli",
        confirmed_at=timestamp,
    )

    expected_confirmation_id = f"confirmation:{plan.run_id}:{plan.plan_id}"
    expected_key = f"confirm:{plan.run_id}:{plan.plan_id}:draft_1_action_1"
    assert result.status == "confirmed"
    assert result.confirmation_id == expected_confirmation_id
    assert result.selected is True
    assert result.service_version == "human_confirmation_v1"
    assert len(result.confirmed_actions) == 1
    assert result.confirmed_actions[0].idempotency_key == expected_key
    assert result.confirmed_actions[0].user_confirmed is True

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    assert row.status == "confirmed"
    assert row.selected is True
    assert row.plan_json["confirmation"] == {
        "schema_version": "human_confirmation_v1",
        "confirmation_id": expected_confirmation_id,
        "status": "confirmed",
        "confirmed_by": "user",
        "source": "cli",
        "confirmed_at": timestamp.isoformat(),
        "action_count": 1,
        "service_version": "human_confirmation_v1",
    }
    assert row.plan_json["confirmed_actions"][0]["idempotency_key"] == expected_key
    assert row.plan_json["confirmed_actions"][0]["tool_name"] == "reserve_restaurant"
    assert row.plan_json["confirmed_actions"][0]["target_id"] == "dining_draft_1"
    assert "idempotency_key" not in row.plan_json["draft"]["proposed_actions"][0]
    assert "confirmation_id" not in row.plan_json["draft"]["proposed_actions"][0]
    assert "action_id" not in row.plan_json["draft"]["proposed_actions"][0]


def test_confirm_plan_is_idempotent_for_confirmed_plan(db_session: Session) -> None:
    plan = _create_plan(db_session)
    service = HumanConfirmationService(PlanRepository(db_session))
    first = service.confirm_plan(
        plan.run_id,
        plan.plan_id,
        confirmed_by="first-user",
        source="cli",
        confirmed_at=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
    )

    second = service.confirm_plan(
        plan.run_id,
        plan.plan_id,
        confirmed_by="second-user",
        source="web",
        confirmed_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
    )

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    assert second == first
    assert row.plan_json["confirmation"]["confirmed_by"] == "first-user"
    assert row.plan_json["confirmation"]["source"] == "cli"


def test_selected_reviewed_plan_can_be_declined_and_redeclined(db_session: Session) -> None:
    plan = _create_plan(db_session)
    service = HumanConfirmationService(PlanRepository(db_session))
    timestamp = datetime(2026, 5, 14, 9, 45, tzinfo=UTC)

    first = service.decline_plan(
        plan.run_id,
        plan.plan_id,
        declined_by="user",
        source="cli",
        declined_at=timestamp,
        reason="user_declined",
    )
    second = service.decline_plan(
        plan.run_id,
        plan.plan_id,
        declined_by="other-user",
        source="web",
        declined_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        reason="changed_mind",
    )

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    assert second == first
    assert first.status == "declined"
    assert first.confirmed_actions == []
    assert row.status == "declined"
    assert row.selected is True
    assert row.plan_json["confirmation"] == {
        "schema_version": "human_confirmation_v1",
        "confirmation_id": f"confirmation:{plan.run_id}:{plan.plan_id}",
        "status": "declined",
        "declined_by": "user",
        "source": "cli",
        "declined_at": timestamp.isoformat(),
        "reason": "user_declined",
        "action_count": 0,
        "service_version": "human_confirmation_v1",
    }
    assert row.plan_json["confirmed_actions"] == []


def test_confirming_declined_and_declining_confirmed_plan_raise(db_session: Session) -> None:
    service = HumanConfirmationService(PlanRepository(db_session))
    declined = _create_plan(db_session)
    confirmed = _create_plan(db_session)

    service.decline_plan(declined.run_id, declined.plan_id, declined_by="user")
    service.confirm_plan(confirmed.run_id, confirmed.plan_id, confirmed_by="user")

    with pytest.raises(PlanConfirmationError):
        service.confirm_plan(declined.run_id, declined.plan_id, confirmed_by="user")

    with pytest.raises(PlanConfirmationError):
        service.decline_plan(confirmed.run_id, confirmed.plan_id, declined_by="user")


def test_missing_wrong_run_unselected_unsafe_and_malformed_plans_raise(db_session: Session) -> None:
    service = HumanConfirmationService(PlanRepository(db_session))
    run = _create_run(db_session)
    other_run = _create_run(db_session)
    plan = _create_plan(db_session, run_id=run.run_id)
    unselected = _create_plan(db_session, selected=False, status="reviewed")
    unsafe = _create_plan(
        db_session,
        plan_json=_reviewed_plan_json(run.run_id, safe_to_present=False),
    )
    malformed = _create_plan(db_session, plan_json={"schema_version": "reviewed_plan_v1"})

    with pytest.raises(PlanConfirmationError):
        service.confirm_plan(run.run_id, uuid4(), confirmed_by="user")
    with pytest.raises(PlanConfirmationError):
        service.confirm_plan(other_run.run_id, plan.plan_id, confirmed_by="user")
    with pytest.raises(PlanConfirmationError):
        service.confirm_plan(unselected.run_id, unselected.plan_id, confirmed_by="user")
    with pytest.raises(PlanConfirmationError):
        service.confirm_plan(unsafe.run_id, unsafe.plan_id, confirmed_by="user")
    with pytest.raises(PlanConfirmationError):
        service.confirm_plan(malformed.run_id, malformed.plan_id, confirmed_by="user")


@pytest.mark.parametrize(
    "actions",
    [
        [{"not": "an action"}],
        [_action(requires_confirmation=False)],
        [_action(action_type="search_poi")],
        [_action(payload="bad-payload")],
        [_action(idempotency_key="pre-confirmation-key")],
        [_action(payload={"nested": {"confirmation_id": "existing-confirmation"}})],
        [_action(payload={"items": [{"action_id": "existing-action"}]})],
        ["not-an-object"],
        [_action(action_ref="x" * 220)],
    ],
)
def test_confirm_rejects_malformed_proposed_actions(db_session: Session, actions: list[dict]) -> None:
    run = _create_run(db_session)
    plan = _create_plan(db_session, run_id=run.run_id, plan_json=_reviewed_plan_json(run.run_id, actions=actions))

    with pytest.raises(PlanConfirmationError):
        HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
            plan.run_id,
            plan.plan_id,
            confirmed_by="user",
        )


def test_plan_with_zero_proposed_actions_can_be_confirmed(db_session: Session) -> None:
    run = _create_run(db_session)
    plan = _create_plan(db_session, run_id=run.run_id, plan_json=_reviewed_plan_json(run.run_id, actions=[]))

    result = HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        plan.run_id,
        plan.plan_id,
        confirmed_by="user",
    )

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    assert result.status == "confirmed"
    assert result.confirmed_actions == []
    assert row.plan_json["confirmed_actions"] == []
    assert row.plan_json["confirmation"]["action_count"] == 0


def test_confirmation_service_and_repository_do_not_self_commit() -> None:
    session = SessionLocal()
    try:
        run = _create_run(session)
        plan = _create_plan(session, run_id=run.run_id, plan_json=_reviewed_plan_json(run.run_id))
        run_id = run.run_id
        plan_id = plan.plan_id

        HumanConfirmationService(PlanRepository(session)).confirm_plan(
            run_id,
            plan_id,
            confirmed_by="user",
        )
        session.rollback()
    finally:
        session.close()

    verification_session = SessionLocal()
    try:
        assert AgentRunRepository(verification_session).get_by_id(run_id) is None
        assert PlanRepository(verification_session).get_by_id(plan_id) is None
    finally:
        verification_session.close()
