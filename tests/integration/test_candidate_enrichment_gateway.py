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
        external_id=f"candidate-enrichment-user-{uuid4()}",
        display_name="Candidate Enrichment Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-candidate-enrichment",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "candidate-enrichment-test"},
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


def test_candidate_enricher_builds_mock_world_evidence_through_gateway(
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

    result = CandidateEnricher(gateway).enrich(plan, collection)

    assert result.run_id == run.run_id
    assert result.provider_profile == "mock_world"
    assert result.enriched_activity_candidates
    assert result.enriched_dining_candidates
    assert any(
        candidate.poi_detail and candidate.opening_hours
        for candidate in result.enriched_activity_candidates
    )
    assert any(
        candidate.queue or candidate.table_availability
        for candidate in result.enriched_dining_candidates
    )
    assert result.route_matrix
    assert any(entry.status in {"succeeded", "cached"} for entry in result.route_matrix)
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
