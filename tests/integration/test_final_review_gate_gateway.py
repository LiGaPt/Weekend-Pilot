from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicItineraryGenerator,
    DeterministicQueryPlanner,
    QueryPlanExecutor,
)
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.review import FinalReviewGate
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway


TEST_PREFIX = "weekendpilot:test:final-review-gate"


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


def create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"final-review-gate-user-{uuid4()}",
        display_name="Final Review Gate Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-final-review-gate",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "final-review-gate-test"},
    )


def build_gateway(
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


def test_final_review_gate_approves_mock_world_drafts_without_side_effects(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    run = create_run(db_session)
    gateway = build_gateway(db_session, cache, rate_limiter)
    intent = DeterministicIntentParser().parse(
        "This afternoon I want to go out with my wife and child for a few hours. "
        "Not too far. My child is 5, and my wife is trying to eat lighter."
    )
    plan = DeterministicQueryPlanner().build(intent, provider_profile="mock_world")
    collection = QueryPlanExecutor(gateway).execute_initial_calls(plan, run.run_id)
    enrichment = CandidateEnricher(gateway).enrich(plan, collection)
    drafts = DeterministicItineraryGenerator().generate(plan, enrichment)

    action_ledger_count_before = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run.run_id)
    )
    tool_event_count_before = db_session.scalar(
        select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run.run_id)
    )

    result = FinalReviewGate().review(
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=action_ledger_count_before,
    )

    assert result.decision in {"approved", "approved_with_warnings"}
    assert result.safe_to_present is True
    assert any(reviewed.safe_to_present for reviewed in result.reviewed_drafts)
    assert all(not reviewed.errors for reviewed in result.reviewed_drafts if reviewed.safe_to_present)

    tool_event_count_after = db_session.scalar(
        select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run.run_id)
    )
    action_ledger_count_after = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run.run_id)
    )
    assert tool_event_count_after == tool_event_count_before
    assert action_ledger_count_after == action_ledger_count_before == 0
