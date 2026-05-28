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


TEST_PREFIX = "weekendpilot:test:candidate-enrichment"
CANONICAL_CASES = [
    pytest.param(
        "family_afternoon_v1",
        "family_afternoon",
        "activity_museum_001",
        "restaurant_light_001",
        5,
        5,
        id="family_afternoon",
    ),
    pytest.param(
        "solo_afternoon_v1",
        "solo_afternoon",
        "activity_gallery_001",
        "restaurant_light_001",
        4,
        4,
        id="solo_afternoon",
    ),
    pytest.param(
        "couple_afternoon_v1",
        "couple_afternoon",
        "activity_citywalk_201",
        "restaurant_light_201",
        4,
        4,
        id="couple_afternoon",
    ),
    pytest.param(
        "friends_gathering_v1",
        "friends_gathering",
        "activity_lawn_301",
        "restaurant_yard_301",
        4,
        4,
        id="friends_gathering",
    ),
    pytest.param(
        "rainy_day_fallback_v1",
        "rainy_day_fallback",
        "activity_market_401",
        "restaurant_soup_401",
        4,
        4,
        id="rainy_day_fallback",
    ),
    pytest.param(
        "budget_lite_v1",
        "budget_lite",
        "activity_park_501",
        "restaurant_bento_501",
        4,
        4,
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
        external_id=f"candidate-enrichment-user-{uuid4()}",
        display_name="Candidate Enrichment Tester",
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
        metadata_json={"source": "candidate-enrichment-test"},
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


def _activity_is_unusable(candidate) -> bool:
    ticket = candidate.ticket_availability
    return isinstance(ticket, dict) and ticket.get("available") is False


def _dining_is_unusable(candidate) -> bool:
    table = candidate.table_availability
    queue = candidate.queue
    table_available = table.get("available") if isinstance(table, dict) else None
    queue_status = queue.get("status") if isinstance(queue, dict) else None
    return table_available is False or (queue_status is not None and queue_status != "open")


@pytest.mark.parametrize(
    (
        "case_id",
        "expected_world_profile",
        "expected_activity_id",
        "expected_dining_id",
        "minimum_activity_count",
        "minimum_dining_count",
    ),
    CANONICAL_CASES,
)
def test_candidate_enricher_builds_mock_world_evidence_through_gateway(
    case_id: str,
    expected_world_profile: str,
    expected_activity_id: str,
    expected_dining_id: str,
    minimum_activity_count: int,
    minimum_dining_count: int,
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

    result = CandidateEnricher(gateway).enrich(plan, collection)

    assert result.run_id == run.run_id
    assert result.provider_profile == "mock_world"
    assert run.world_profile == expected_world_profile
    assert collection.provider_profile == "mock_world"
    assert len(collection.activity_candidates) >= minimum_activity_count
    assert len(collection.dining_candidates) >= minimum_dining_count
    assert result.enriched_activity_candidates
    assert result.enriched_dining_candidates
    assert len(result.enriched_activity_candidates) == 3
    assert len(result.enriched_dining_candidates) == 3
    assert any(
        candidate.poi_detail and candidate.opening_hours
        for candidate in result.enriched_activity_candidates
    )
    assert any(
        candidate.queue or candidate.table_availability
        for candidate in result.enriched_dining_candidates
    )
    assert result.route_matrix
    assert len(result.route_matrix) == (
        len(result.enriched_activity_candidates) * len(result.enriched_dining_candidates)
    )
    assert (
        any(_activity_is_unusable(candidate) for candidate in result.enriched_activity_candidates)
        or any(_dining_is_unusable(candidate) for candidate in result.enriched_dining_candidates)
    )
    assert any(entry.status in {"succeeded", "cached"} for entry in result.route_matrix)
    assert any(entry.status not in {"succeeded", "cached"} for entry in result.route_matrix)
    assert any(
        entry.origin_candidate_id == expected_activity_id
        and entry.destination_candidate_id == expected_dining_id
        and entry.status in {"succeeded", "cached"}
        for entry in result.route_matrix
    )
    assert all(entry.origin_candidate_id and entry.destination_candidate_id for entry in result.route_matrix)
    assert all(
        entry.status in {"succeeded", "cached"} or entry.error_json
        for entry in result.route_matrix
    )

    tool_event_count = db_session.scalar(
        select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run.run_id)
    )
    action_ledger_count = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run.run_id)
    )
    assert tool_event_count >= len(collection.tool_results) + len(result.tool_results)
    assert action_ledger_count == 0
