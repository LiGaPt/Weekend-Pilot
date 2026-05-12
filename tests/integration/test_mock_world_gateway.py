from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway, ToolGatewayRequest


TEST_PREFIX = "weekendpilot:test:mock-world"


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
        external_id=f"mock-world-user-{uuid4()}",
        display_name="Mock World Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-mock-world-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "mock-world-gateway-test"},
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


def test_search_poi_through_gateway_succeeds_and_writes_tool_event(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    gateway = build_gateway(db_session, cache, rate_limiter)
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="search_poi",
            payload={"category": "activity", "limit": 1},
        )
    )

    assert result.status == "succeeded"
    assert result.provider == "mock_world"
    assert result.response_json["results"][0]["poi_id"] == "activity_museum_001"

    events = ToolEventRepository(db_session).list_for_run(run.run_id)
    assert len(events) == 1
    assert events[0].tool_name == "search_poi"
    assert events[0].provider == "mock_world"
    assert events[0].status == "succeeded"


def test_check_weather_through_gateway_is_cached_on_second_call(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    gateway = build_gateway(db_session, cache, rate_limiter)
    run = create_run(db_session)
    request = ToolGatewayRequest(
        run_id=run.run_id,
        tool_name="check_weather",
        payload={"location": "Xuhui", "date": "2026-05-16"},
    )

    first = gateway.invoke(request)
    second = gateway.invoke(request)

    assert first.status == "succeeded"
    assert second.status == "cached"
    assert second.cache_hit is True
    assert second.response_json == first.response_json
    statuses = [event.status for event in ToolEventRepository(db_session).list_for_run(run.run_id)]
    assert sorted(statuses) == ["cached", "succeeded"]


def test_unconfirmed_reserve_restaurant_is_blocked_before_provider_execution(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    gateway = build_gateway(db_session, cache, rate_limiter)
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="reserve_restaurant",
            payload={
                "restaurant_id": "missing_restaurant",
                "party_size": 3,
                "time_slot": "18:00",
            },
            target_id="missing_restaurant",
            idempotency_key=f"reserve-{uuid4()}",
        )
    )

    assert result.status == "blocked"
    assert result.error_json["code"] == "write_not_confirmed"
    assert result.action_id is None


def test_confirmed_reserve_restaurant_creates_action_ledger_row(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    gateway = build_gateway(db_session, cache, rate_limiter)
    run = create_run(db_session)
    idempotency_key = f"reserve-{uuid4()}"

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="reserve_restaurant",
            payload={
                "restaurant_id": "restaurant_light_001",
                "party_size": 3,
                "time_slot": "18:00",
            },
            user_confirmed=True,
            target_id="restaurant_light_001",
            idempotency_key=idempotency_key,
        )
    )

    assert result.status == "succeeded"
    assert result.action_id is not None
    assert result.response_json["confirmation"]["confirmation_id"] == (
        "mock-confirmation-reserve_restaurant-restaurant_light_001-18:00"
    )
    action = ActionLedgerRepository(db_session).get_by_idempotency_key(idempotency_key)
    assert action.status == "succeeded"
    assert action.response_json == result.response_json


def test_duplicate_idempotency_key_replays_without_duplicate_provider_effect(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    gateway = build_gateway(db_session, cache, rate_limiter)
    run = create_run(db_session)
    idempotency_key = f"reserve-{uuid4()}"
    request = ToolGatewayRequest(
        run_id=run.run_id,
        tool_name="reserve_restaurant",
        payload={
            "restaurant_id": "restaurant_light_001",
            "party_size": 3,
            "time_slot": "18:00",
        },
        user_confirmed=True,
        target_id="restaurant_light_001",
        idempotency_key=idempotency_key,
    )

    first = gateway.invoke(request)
    second = gateway.invoke(request)

    assert first.status == "succeeded"
    assert second.status == "idempotent_replay"
    assert second.action_id == first.action_id
    assert second.response_json == first.response_json
    action_count = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.idempotency_key == idempotency_key)
    )
    assert action_count == 1


def test_invalid_poi_id_becomes_failed_gateway_result_and_failed_tool_event(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    gateway = build_gateway(db_session, cache, rate_limiter)
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="get_poi_detail",
            payload={"poi_id": "missing"},
        )
    )

    assert result.status == "failed"
    assert result.error_json["code"] == "provider_error"
    assert result.error_json["details"]["exception_type"] == "MockWorldError"
    events = ToolEventRepository(db_session).list_for_run(run.run_id)
    assert events[-1].status == "failed"
    assert events[-1].error_json == result.error_json
