from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolDefinition, ToolGateway, ToolGatewayRequest, ToolRateLimit, ToolRegistry


TEST_PREFIX = "weekendpilot:test:gateway"


class FakeProvider:
    name = "fake"

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool_name, payload))
        if self.should_fail:
            raise RuntimeError("fake provider failed")
        return {
            "tool_name": tool_name,
            "payload": payload,
            "call_count": len(self.calls),
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


def create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"gateway-user-{uuid4()}",
        display_name="Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="fake",
        world_profile="test",
        failure_profile=None,
        status="running",
        metadata_json={"source": "tool-gateway-test"},
    )


def build_gateway(
    session: Session,
    definition: ToolDefinition,
    provider: FakeProvider,
    cache: JsonRedisCache,
    rate_limiter: FixedWindowRateLimiter,
) -> ToolGateway:
    registry = ToolRegistry()
    registry.register_tool(definition)
    registry.register_provider(provider)
    return ToolGateway(
        registry=registry,
        tool_events=ToolEventRepository(session),
        action_ledger=ActionLedgerRepository(session),
        cache=cache,
        rate_limiter=rate_limiter,
    )


def test_read_tool_logs_event_and_returns_provider_response(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider()
    gateway = build_gateway(
        db_session,
        ToolDefinition(name="search_poi", tool_type="read", default_provider="fake"),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="search_poi",
            payload={"query": "museum"},
        )
    )

    assert result.status == "succeeded"
    assert result.response_json == {
        "tool_name": "search_poi",
        "payload": {"query": "museum"},
        "call_count": 1,
    }
    assert result.tool_event_id is not None
    assert provider.calls == [("search_poi", {"query": "museum"})]

    events = ToolEventRepository(db_session).list_for_run(run.run_id)
    assert len(events) == 1
    assert events[0].status == "succeeded"
    assert events[0].request_json["payload"] == {"query": "museum"}


def test_cacheable_read_tool_uses_redis_cache_on_second_call(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider()
    gateway = build_gateway(
        db_session,
        ToolDefinition(
            name="check_weather",
            tool_type="read",
            default_provider="fake",
            cache_ttl_seconds=60,
        ),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)
    request = ToolGatewayRequest(
        run_id=run.run_id,
        tool_name="check_weather",
        payload={"location": "shanghai"},
    )

    first = gateway.invoke(request)
    second = gateway.invoke(request)

    assert first.status == "succeeded"
    assert second.status == "cached"
    assert second.cache_hit is True
    assert second.response_json == first.response_json
    assert len(provider.calls) == 1
    statuses = [event.status for event in ToolEventRepository(db_session).list_for_run(run.run_id)]
    assert sorted(statuses) == ["cached", "succeeded"]


def test_rate_limited_tool_blocks_provider_call(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider()
    gateway = build_gateway(
        db_session,
        ToolDefinition(
            name="search_poi",
            tool_type="read",
            default_provider="fake",
            rate_limit=ToolRateLimit(limit=1, window_seconds=60),
        ),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)
    request = ToolGatewayRequest(
        run_id=run.run_id,
        tool_name="search_poi",
        payload={"query": "museum"},
    )

    first = gateway.invoke(request)
    second = gateway.invoke(request)

    assert first.status == "succeeded"
    assert second.status == "rate_limited"
    assert second.error_json["code"] == "rate_limited"
    assert len(provider.calls) == 1


def test_write_tool_is_blocked_before_confirmation(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider()
    gateway = build_gateway(
        db_session,
        ToolDefinition(name="reserve_restaurant", tool_type="write", default_provider="fake"),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="reserve_restaurant",
            payload={"party_size": 3},
            target_id="restaurant-1",
            idempotency_key=f"reserve-{uuid4()}",
        )
    )

    assert result.status == "blocked"
    assert result.error_json["code"] == "write_not_confirmed"
    assert result.action_id is None
    assert provider.calls == []
    assert ActionLedgerRepository(db_session).get_by_idempotency_key(result.idempotency_key) is None


def test_confirmed_write_creates_and_updates_action_ledger(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider()
    gateway = build_gateway(
        db_session,
        ToolDefinition(name="reserve_restaurant", tool_type="write", default_provider="fake"),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)
    idempotency_key = f"reserve-{uuid4()}"

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="reserve_restaurant",
            payload={"party_size": 3},
            user_confirmed=True,
            target_id="restaurant-1",
            idempotency_key=idempotency_key,
        )
    )

    assert result.status == "succeeded"
    assert result.action_id is not None
    action = ActionLedgerRepository(db_session).get_by_idempotency_key(idempotency_key)
    assert action.status == "succeeded"
    assert action.response_json == result.response_json
    assert action.error_json is None


def test_duplicate_write_idempotency_key_replays_existing_action(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider()
    gateway = build_gateway(
        db_session,
        ToolDefinition(name="reserve_restaurant", tool_type="write", default_provider="fake"),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)
    idempotency_key = f"reserve-{uuid4()}"
    request = ToolGatewayRequest(
        run_id=run.run_id,
        tool_name="reserve_restaurant",
        payload={"party_size": 3},
        user_confirmed=True,
        target_id="restaurant-1",
        idempotency_key=idempotency_key,
    )

    first = gateway.invoke(request)
    second = gateway.invoke(request)

    assert first.status == "succeeded"
    assert second.status == "idempotent_replay"
    assert second.action_id == first.action_id
    assert second.response_json == first.response_json
    assert len(provider.calls) == 1


def test_provider_exception_writes_failed_event_and_failed_ledger_for_write(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    provider = FakeProvider(should_fail=True)
    gateway = build_gateway(
        db_session,
        ToolDefinition(name="reserve_restaurant", tool_type="write", default_provider="fake"),
        provider,
        cache,
        rate_limiter,
    )
    run = create_run(db_session)
    idempotency_key = f"reserve-{uuid4()}"

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="reserve_restaurant",
            payload={"party_size": 3},
            user_confirmed=True,
            target_id="restaurant-1",
            idempotency_key=idempotency_key,
        )
    )

    assert result.status == "failed"
    assert result.error_json["code"] == "provider_error"
    action = ActionLedgerRepository(db_session).get_by_idempotency_key(idempotency_key)
    assert action.status == "failed"
    assert action.error_json == result.error_json
    events = ToolEventRepository(db_session).list_for_run(run.run_id)
    assert events[-1].status == "failed"
