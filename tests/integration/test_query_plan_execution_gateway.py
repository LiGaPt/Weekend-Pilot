from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.planning import DeterministicIntentParser, DeterministicQueryPlanner, QueryPlanExecutor
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway


TEST_PREFIX = "weekendpilot:test:query-plan-execution"


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
        external_id=f"query-execution-user-{uuid4()}",
        display_name="Query Execution Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-query-plan-execution",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "query-plan-execution-test"},
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


def test_query_plan_executor_collects_mock_world_candidates_through_gateway(
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

    result = QueryPlanExecutor(gateway).execute_initial_calls(plan, run.run_id)

    assert result.run_id == run.run_id
    assert result.provider_profile == "mock_world"
    assert result.activity_candidates
    assert result.dining_candidates
    assert result.weather is not None
    assert all(tool_result.status in {"succeeded", "cached"} for tool_result in result.tool_results)
    assert len(result.tool_results) == len(plan.initial_tool_calls)
    assert result.failed_tool_results == []
    assert {candidate.provider for candidate in result.activity_candidates + result.dining_candidates} == {
        "mock_world"
    }
    assert all(candidate.tool_event_id is not None for candidate in result.activity_candidates)

    tool_event_count = db_session.scalar(
        select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run.run_id)
    )
    action_ledger_count = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run.run_id)
    )
    assert tool_event_count == len(plan.initial_tool_calls)
    assert action_ledger_count == 0
