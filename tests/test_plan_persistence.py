from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.planning import (
    FeasibilitySummary,
    ItineraryCandidateRef,
    ItineraryDraft,
    ItineraryDraftResult,
    ItineraryRouteRef,
    ProposedAction,
    TimelineItem,
)
from backend.app.plans import (
    PlanPersistenceError,
    PlanSelectionError,
    ReviewedPlanPersistenceService,
)
from backend.app.repositories import AgentRunRepository, PlanRepository, UserRepository
from backend.app.review import FinalReviewResult, ReviewCheck, ReviewedDraft


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
        external_id=f"plan-persistence-user-{uuid4()}",
        display_name="Plan Persistence Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-plan-persistence",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "plan-persistence-test"},
    )


def _candidate_ref(candidate_id: str, *, category: str) -> ItineraryCandidateRef:
    return ItineraryCandidateRef(
        candidate_id=candidate_id,
        name=candidate_id,
        category=category,
        provider="mock_world",
        address=f"{candidate_id} address",
        tags=["child_friendly"],
        evidence={"source": "test"},
    )


def _draft(draft_id: str = "draft_1") -> ItineraryDraft:
    return ItineraryDraft(
        draft_id=draft_id,
        title=f"Plan {draft_id}",
        summary="A reviewed family afternoon plan.",
        activity=_candidate_ref(f"activity_{draft_id}", category="activity"),
        dining=_candidate_ref(f"dining_{draft_id}", category="dining"),
        route=ItineraryRouteRef(
            origin_candidate_id=f"activity_{draft_id}",
            destination_candidate_id=f"dining_{draft_id}",
            provider="mock_world",
            mode="walking",
            distance_meters=900,
            duration_minutes=12,
            summary="Short walk",
        ),
        timeline=[
            TimelineItem(
                sequence=1,
                item_type="activity",
                title="Activity",
                candidate_id=f"activity_{draft_id}",
                duration_minutes=120,
                start_label="13:30",
                end_label="15:30",
            ),
            TimelineItem(
                sequence=2,
                item_type="dining",
                title="Dinner",
                candidate_id=f"dining_{draft_id}",
                duration_minutes=90,
                start_label="17:00",
                end_label="18:30",
            ),
        ],
        proposed_actions=[
            ProposedAction(
                action_ref=f"reserve_{draft_id}",
                action_type="reserve_restaurant",
                target_id=f"dining_{draft_id}",
                payload={"party_size": 3},
                reason="Reserve after user confirmation.",
            )
        ],
        feasibility=FeasibilitySummary(
            is_feasible=True,
            reasons=["activity_selected", "dining_selected"],
            total_duration_minutes=240,
            route_duration_minutes=12,
        ),
        evidence={"planner_version": "test-planner"},
    )


def _drafts(run_id: UUID, drafts: list[ItineraryDraft]) -> ItineraryDraftResult:
    return ItineraryDraftResult(
        run_id=run_id,
        provider_profile="mock_world",
        drafts=drafts,
        generator_version="test-generator",
    )


def _check(draft_id: str | None = None) -> ReviewCheck:
    return ReviewCheck(
        check_name="test_check",
        status="passed",
        severity="info",
        message="Reviewed in test.",
        draft_id=draft_id,
    )


def _reviewed_draft(
    draft_id: str = "draft_1",
    *,
    decision: str = "approved",
    safe_to_present: bool = True,
) -> ReviewedDraft:
    check = _check(draft_id)
    return ReviewedDraft(
        draft_id=draft_id,
        decision=decision,
        safe_to_present=safe_to_present,
        checks=[check],
        errors=[] if safe_to_present else [check.model_copy(update={"status": "failed", "severity": "error"})],
        warnings=[],
    )


def _review(
    run_id: UUID,
    reviewed_drafts: list[ReviewedDraft],
    *,
    provider_profile: str = "mock_world",
    decision: str = "approved",
    safe_to_present: bool = True,
) -> FinalReviewResult:
    return FinalReviewResult(
        run_id=run_id,
        provider_profile=provider_profile,
        decision=decision,
        safe_to_present=safe_to_present,
        reviewed_drafts=reviewed_drafts,
        checks=[_check()],
        errors=[],
        warnings=[],
        gate_version="test-gate",
    )


def test_plan_repository_creates_gets_lists_and_finds_by_draft_id(db_session: Session) -> None:
    run = _create_run(db_session)
    repo = PlanRepository(db_session)

    plan = repo.create(
        run_id=run.run_id,
        status="reviewed",
        selected=False,
        plan_json={"draft_id": "draft_1", "safe_to_present": True},
    )

    assert plan.plan_id is not None
    assert repo.get_by_id(plan.plan_id) is plan
    assert repo.list_for_run(run.run_id) == [plan]
    assert repo.find_by_run_and_draft_id(run.run_id, "draft_1") is plan
    assert repo.find_by_run_and_draft_id(run.run_id, "missing") is None


def test_plan_repository_select_for_run_marks_exactly_one_selected(db_session: Session) -> None:
    run = _create_run(db_session)
    repo = PlanRepository(db_session)
    first = repo.create(run.run_id, "reviewed", {"draft_id": "draft_1"})
    second = repo.create(run.run_id, "reviewed", {"draft_id": "draft_2"})

    selected_first = repo.select_for_run(run.run_id, first.plan_id)
    assert selected_first is first
    state = {plan.plan_id: (plan.status, plan.selected) for plan in repo.list_for_run(run.run_id)}
    assert state == {
        first.plan_id: ("selected", True),
        second.plan_id: ("reviewed", False),
    }

    selected_second = repo.select_for_run(run.run_id, second.plan_id)
    assert selected_second is second
    state = {plan.plan_id: (plan.status, plan.selected) for plan in repo.list_for_run(run.run_id)}
    assert state == {
        first.plan_id: ("reviewed", False),
        second.plan_id: ("selected", True),
    }


def test_plan_repository_does_not_self_commit() -> None:
    session = SessionLocal()
    try:
        run = _create_run(session)
        plan = PlanRepository(session).create(
            run_id=run.run_id,
            status="reviewed",
            plan_json={"draft_id": "rollback_draft"},
        )
        run_id = run.run_id
        plan_id = plan.plan_id
        session.rollback()
    finally:
        session.close()

    verification_session = SessionLocal()
    try:
        assert AgentRunRepository(verification_session).get_by_id(run_id) is None
        assert PlanRepository(verification_session).get_by_id(plan_id) is None
    finally:
        verification_session.close()


def test_service_persists_safe_reviewed_drafts_with_plan_json_contract(db_session: Session) -> None:
    run = _create_run(db_session)
    draft = _draft("draft_1")
    service = ReviewedPlanPersistenceService(PlanRepository(db_session))

    result = service.persist_reviewed_drafts(
        _review(run.run_id, [_reviewed_draft("draft_1")], decision="approved_with_warnings"),
        _drafts(run.run_id, [draft]),
    )

    assert len(result.persisted_plans) == 1
    persisted = result.persisted_plans[0]
    assert persisted.run_id == run.run_id
    assert persisted.draft_id == "draft_1"
    assert persisted.status == "reviewed"
    assert persisted.selected is False
    assert persisted.safe_to_present is True
    assert persisted.review_decision == "approved"
    assert persisted.persistence_status == "created"
    assert result.skipped_drafts == []
    assert result.service_version == "reviewed_plan_persistence_v1"

    row = PlanRepository(db_session).get_by_id(persisted.plan_id)
    assert row is not None
    assert row.status == "reviewed"
    assert row.selected is False
    assert row.plan_json["schema_version"] == "reviewed_plan_v1"
    assert row.plan_json["persistence_version"] == "reviewed_plan_persistence_v1"
    assert row.plan_json["run_id"] == str(run.run_id)
    assert row.plan_json["provider_profile"] == "mock_world"
    assert row.plan_json["draft_id"] == "draft_1"
    assert row.plan_json["status"] == "reviewed"
    assert row.plan_json["draft"] == draft.model_dump(mode="json")
    assert row.plan_json["reviewed_draft"]["draft_id"] == "draft_1"
    assert row.plan_json["final_review"] == {
        "decision": "approved_with_warnings",
        "safe_to_present": True,
        "gate_version": "test-gate",
    }
    assert row.plan_json["source_versions"] == {
        "generator_version": "test-generator",
        "gate_version": "test-gate",
        "persistence_version": "reviewed_plan_persistence_v1",
    }


def test_service_skips_unsafe_missing_and_globally_blocked_drafts(db_session: Session) -> None:
    run = _create_run(db_session)
    service = ReviewedPlanPersistenceService(PlanRepository(db_session))

    result = service.persist_reviewed_drafts(
        _review(
            run.run_id,
            [
                _reviewed_draft("draft_1", decision="blocked", safe_to_present=False),
                _reviewed_draft("missing_draft"),
            ],
        ),
        _drafts(run.run_id, [_draft("draft_1")]),
    )
    assert [(skipped.draft_id, skipped.reason) for skipped in result.skipped_drafts] == [
        ("draft_1", "not_safe_to_present"),
        ("missing_draft", "draft_not_found"),
    ]
    assert result.persisted_plans == []

    blocked = service.persist_reviewed_drafts(
        _review(
            run.run_id,
            [_reviewed_draft("draft_1")],
            decision="blocked",
            safe_to_present=False,
        ),
        _drafts(run.run_id, [_draft("draft_1")]),
    )
    assert [(skipped.draft_id, skipped.reason) for skipped in blocked.skipped_drafts] == [
        ("draft_1", "review_blocked"),
    ]
    assert blocked.persisted_plans == []
    assert PlanRepository(db_session).list_for_run(run.run_id) == []


def test_service_is_idempotent_for_same_run_and_draft(db_session: Session) -> None:
    run = _create_run(db_session)
    service = ReviewedPlanPersistenceService(PlanRepository(db_session))
    review = _review(run.run_id, [_reviewed_draft("draft_1")])
    drafts = _drafts(run.run_id, [_draft("draft_1")])

    created = service.persist_reviewed_drafts(review, drafts)
    existing = service.persist_reviewed_drafts(review, drafts)

    assert len(PlanRepository(db_session).list_for_run(run.run_id)) == 1
    assert existing.persisted_plans[0].plan_id == created.persisted_plans[0].plan_id
    assert existing.persisted_plans[0].persistence_status == "already_exists"


def test_service_select_plan_returns_selected_plan(db_session: Session) -> None:
    run = _create_run(db_session)
    service = ReviewedPlanPersistenceService(PlanRepository(db_session))
    result = service.persist_reviewed_drafts(
        _review(run.run_id, [_reviewed_draft("draft_1"), _reviewed_draft("draft_2")]),
        _drafts(run.run_id, [_draft("draft_1"), _draft("draft_2")]),
    )

    selected = service.select_plan(run.run_id, result.persisted_plans[1].plan_id)

    assert selected.draft_id == "draft_2"
    assert selected.status == "selected"
    assert selected.selected is True
    plans = PlanRepository(db_session).list_for_run(run.run_id)
    assert [plan.selected for plan in plans].count(True) == 1
    state = {plan.plan_json["draft_id"]: (plan.status, plan.selected) for plan in plans}
    assert state == {
        "draft_1": ("reviewed", False),
        "draft_2": ("selected", True),
    }


def test_service_select_missing_or_wrong_run_plan_raises(db_session: Session) -> None:
    run = _create_run(db_session)
    other_run = _create_run(db_session)
    repo = PlanRepository(db_session)
    service = ReviewedPlanPersistenceService(repo)
    plan = repo.create(run.run_id, "reviewed", {"draft_id": "draft_1"})

    with pytest.raises(PlanSelectionError):
        service.select_plan(run.run_id, uuid4())

    with pytest.raises(PlanSelectionError):
        service.select_plan(other_run.run_id, plan.plan_id)


def test_service_rejects_mismatched_review_and_draft_metadata(db_session: Session) -> None:
    run = _create_run(db_session)
    other_run = _create_run(db_session)
    service = ReviewedPlanPersistenceService(PlanRepository(db_session))

    with pytest.raises(PlanPersistenceError):
        service.persist_reviewed_drafts(
            _review(run.run_id, [_reviewed_draft("draft_1")]),
            _drafts(other_run.run_id, [_draft("draft_1")]),
        )

    with pytest.raises(PlanPersistenceError):
        service.persist_reviewed_drafts(
            _review(run.run_id, [_reviewed_draft("draft_1")], provider_profile="amap"),
            _drafts(run.run_id, [_draft("draft_1")]),
        )
