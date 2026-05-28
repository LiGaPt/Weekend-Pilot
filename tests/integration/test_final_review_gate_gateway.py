from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.benchmark import load_benchmark_case
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
CANONICAL_CASES = [
    pytest.param(
        "family_afternoon_v1",
        "family_afternoon",
        "activity_museum_001",
        "restaurant_light_001",
        id="family_afternoon",
    ),
    pytest.param(
        "solo_afternoon_v1",
        "solo_afternoon",
        "activity_gallery_001",
        "restaurant_light_001",
        id="solo_afternoon",
    ),
    pytest.param(
        "couple_afternoon_v1",
        "couple_afternoon",
        "activity_citywalk_201",
        "restaurant_light_201",
        id="couple_afternoon",
    ),
    pytest.param(
        "friends_gathering_v1",
        "friends_gathering",
        "activity_lawn_301",
        "restaurant_yard_301",
        id="friends_gathering",
    ),
    pytest.param(
        "rainy_day_fallback_v1",
        "rainy_day_fallback",
        "activity_market_401",
        "restaurant_soup_401",
        id="rainy_day_fallback",
    ),
    pytest.param(
        "budget_lite_v1",
        "budget_lite",
        "activity_park_501",
        "restaurant_bento_501",
        id="budget_lite",
    ),
]


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


def create_run(session: Session, *, case_id: str, world_profile: str):
    user = UserRepository(session).create(
        external_id=f"final-review-gate-user-{uuid4()}",
        display_name="Final Review Gate Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id=case_id,
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile=world_profile,
        failure_profile=None,
        status="running",
        metadata_json={"source": "final-review-gate-test"},
    )


def build_gateway(
    session: Session,
    cache: JsonRedisCache,
    rate_limiter: FixedWindowRateLimiter,
    *,
    world_profile: str = "family_afternoon",
) -> ToolGateway:
    return ToolGateway(
        registry=build_mock_world_registry(world_profile),
        tool_events=ToolEventRepository(session),
        action_ledger=ActionLedgerRepository(session),
        cache=cache,
        rate_limiter=rate_limiter,
    )


@pytest.mark.parametrize(
    ("case_id", "expected_world_profile", "expected_activity_id", "expected_dining_id"),
    CANONICAL_CASES,
)
def test_final_review_gate_approves_mock_world_drafts_without_side_effects(
    case_id: str,
    expected_world_profile: str,
    expected_activity_id: str,
    expected_dining_id: str,
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    case = load_benchmark_case(case_id)
    run = create_run(
        db_session,
        case_id=case.case_id,
        world_profile=case.world_profile,
    )
    gateway = build_gateway(
        db_session,
        cache,
        rate_limiter,
        world_profile=case.world_profile,
    )
    intent = DeterministicIntentParser().parse(case.user_input)
    plan = DeterministicQueryPlanner().build(intent, provider_profile=case.tool_profile)
    collection = QueryPlanExecutor(gateway).execute_initial_calls(plan, run.run_id)
    enrichment = CandidateEnricher(gateway).enrich(plan, collection)
    drafts = DeterministicItineraryGenerator().generate(plan, enrichment)
    first_draft = drafts.drafts[0]

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

    assert run.world_profile == expected_world_profile
    assert first_draft.activity.candidate_id == expected_activity_id
    assert first_draft.dining.candidate_id == expected_dining_id
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
