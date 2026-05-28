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
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway


TEST_PREFIX = "weekendpilot:test:itinerary-generation"
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
        external_id=f"itinerary-generation-user-{uuid4()}",
        display_name="Itinerary Generation Tester",
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
        metadata_json={"source": "itinerary-generation-test"},
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
def test_itinerary_generator_builds_mock_world_drafts_without_write_side_effects(
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
    tool_event_count_before = db_session.scalar(
        select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run.run_id)
    )

    result = DeterministicItineraryGenerator().generate(plan, enrichment)

    assert result.run_id == run.run_id
    assert result.provider_profile == "mock_world"
    assert run.world_profile == expected_world_profile
    assert result.drafts
    first_draft = result.drafts[0]
    assert first_draft.activity.candidate_id == expected_activity_id
    assert first_draft.dining.candidate_id == expected_dining_id
    assert first_draft.route is not None
    assert first_draft.timeline
    assert first_draft.proposed_actions
    assert first_draft.feasibility.is_feasible is True
    assert all(action.requires_confirmation for action in first_draft.proposed_actions)
    assert not any("idempotency_key" in action.payload for action in first_draft.proposed_actions)
    assert len(enrichment.route_matrix) == (
        len(enrichment.enriched_activity_candidates) * len(enrichment.enriched_dining_candidates)
    )
    assert any(entry.status not in {"succeeded", "cached"} for entry in enrichment.route_matrix)

    tool_event_count_after = db_session.scalar(
        select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run.run_id)
    )
    action_ledger_count = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run.run_id)
    )
    assert tool_event_count_after == tool_event_count_before
    assert action_ledger_count == 0
