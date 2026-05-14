from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.confirmation import HumanConfirmationService
from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, Plan, ToolEvent
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicItineraryGenerator,
    DeterministicQueryPlanner,
    QueryPlanExecutor,
)
from backend.app.plans import ReviewedPlanPersistenceService
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.review import FinalReviewGate
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway


TEST_PREFIX = "weekendpilot:test:human-confirmation"
WRITE_TOOLS = {
    "join_queue",
    "reserve_restaurant",
    "book_ticket",
    "order_addon",
    "send_message",
}


@pytest.fixture()
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def redis_runtime():
    client = get_redis_client()
    client.ping()
    keys = RedisKeyBuilder(prefix=f"{TEST_PREFIX}:{uuid4()}")

    def cleanup() -> None:
        redis_keys = list(client.scan_iter(f"{keys.prefix}:*"))
        if redis_keys:
            client.delete(*redis_keys)

    cleanup()
    try:
        yield JsonRedisCache(client, keys), FixedWindowRateLimiter(client, keys)
    finally:
        cleanup()


def _create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"human-confirmation-gateway-user-{uuid4()}",
        display_name="Human Confirmation Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-human-confirmation-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "human-confirmation-gateway-test"},
    )


def _build_gateway(
    session: Session,
    cache: JsonRedisCache,
    rate_limiter: FixedWindowRateLimiter,
) -> ToolGateway:
    return ToolGateway(
        registry=build_mock_world_registry(),
        tool_events=ToolEventRepository(session),
        action_ledger=ActionLedgerRepository(session),
        cache=cache,
        rate_limiter=rate_limiter,
    )


def _count_rows(session: Session, model, run_id):
    return session.scalar(select(func.count()).select_from(model).where(model.run_id == run_id))


def test_human_confirmation_keeps_gateway_path_read_only(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    run = _create_run(db_session)
    gateway = _build_gateway(db_session, cache, rate_limiter)
    intent = DeterministicIntentParser().parse(
        "This afternoon I want to go out with my wife and child for a few hours. "
        "Not too far. My child is 5, and my wife is trying to eat lighter."
    )
    plan = DeterministicQueryPlanner().build(intent, provider_profile="mock_world")
    collection = QueryPlanExecutor(gateway).execute_initial_calls(plan, run.run_id)
    enrichment = CandidateEnricher(gateway).enrich(plan, collection)
    drafts = DeterministicItineraryGenerator().generate(plan, enrichment)
    action_ledger_count_before_review = _count_rows(db_session, ActionLedger, run.run_id)
    review = FinalReviewGate().review(
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=action_ledger_count_before_review,
    )
    assert review.safe_to_present is True

    persistence = ReviewedPlanPersistenceService(PlanRepository(db_session))
    persisted = persistence.persist_reviewed_drafts(review, drafts)
    assert persisted.persisted_plans

    selected = persistence.select_plan(run.run_id, persisted.persisted_plans[0].plan_id)
    selected_row = PlanRepository(db_session).get_by_id(selected.plan_id)
    assert selected_row is not None
    proposed_action_count = len(selected_row.plan_json["draft"].get("proposed_actions") or [])

    action_ledger_count_before = _count_rows(db_session, ActionLedger, run.run_id)
    tool_event_count_before = _count_rows(db_session, ToolEvent, run.run_id)

    result = HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        run.run_id,
        selected.plan_id,
        confirmed_by="user",
        source="integration-test",
    )

    assert result.status == "confirmed"
    assert result.selected is True
    if proposed_action_count:
        assert len(result.confirmed_actions) == proposed_action_count
    for action in result.confirmed_actions:
        assert action.user_confirmed is True
        assert action.idempotency_key
        assert action.tool_name in WRITE_TOOLS
        assert action.target_id

    confirmed_row = PlanRepository(db_session).get_by_id(selected.plan_id)
    assert confirmed_row is not None
    assert confirmed_row.status == "confirmed"
    assert confirmed_row.selected is True
    assert confirmed_row.plan_json["confirmation"]["status"] == "confirmed"
    assert len(confirmed_row.plan_json["confirmed_actions"]) == len(result.confirmed_actions)
    assert db_session.scalar(
        select(func.count()).select_from(Plan).where(Plan.run_id == run.run_id, Plan.selected.is_(True))
    ) == 1
    assert _count_rows(db_session, ActionLedger, run.run_id) == action_ledger_count_before == 0
    assert _count_rows(db_session, ToolEvent, run.run_id) == tool_event_count_before
