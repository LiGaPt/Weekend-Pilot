from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.providers.amap import AMapProvider
from backend.app.providers.amap.errors import AMapProviderError
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway, ToolGatewayRequest, build_default_registry


TEST_PREFIX = "weekendpilot:test:amap"


class FakeAMapClient:
    def __init__(self, responses: dict[str, dict[str, Any]], should_fail: bool = False) -> None:
        self.responses = responses
        self.should_fail = should_fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, params))
        if self.should_fail:
            raise AMapProviderError("AMAP provider request failed.")
        return self.responses[path]


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
        external_id=f"amap-user-{uuid4()}",
        display_name="AMAP Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-amap-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="amap",
        world_profile="test",
        failure_profile=None,
        status="running",
        metadata_json={"source": "amap-gateway-test"},
    )


def build_gateway(
    session: Session,
    provider: AMapProvider,
    cache: JsonRedisCache,
    rate_limiter: FixedWindowRateLimiter,
) -> ToolGateway:
    registry = build_default_registry(default_provider="amap")
    registry.register_provider(provider)
    return ToolGateway(
        registry=registry,
        tool_events=ToolEventRepository(session),
        action_ledger=ActionLedgerRepository(session),
        cache=cache,
        rate_limiter=rate_limiter,
    )


def test_search_poi_through_gateway_writes_tool_event(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    client = FakeAMapClient(
        {
            "/v3/place/text": {
                "status": "1",
                "pois": [
                    {
                        "id": "B001",
                        "name": "Shanghai Museum",
                        "type": "Science;Museum",
                        "address": "201 Renmin Ave",
                        "location": "121.475,31.228",
                        "cityname": "Shanghai",
                    }
                ],
            }
        }
    )
    gateway = build_gateway(db_session, AMapProvider(client), cache, rate_limiter)
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="search_poi",
            payload={"keywords": "family museum", "city": "Shanghai", "page_size": 1},
        )
    )

    assert result.status == "succeeded"
    assert result.provider == "amap"
    assert result.response_json["results"][0]["source"] == "amap"
    assert client.calls == [
        (
            "/v3/place/text",
            {
                "keywords": "family museum",
                "city": "Shanghai",
                "offset": 1,
            },
        )
    ]

    events = ToolEventRepository(db_session).list_for_run(run.run_id)
    assert len(events) == 1
    assert events[0].status == "succeeded"
    assert events[0].provider == "amap"
    assert events[0].request_json["payload"]["keywords"] == "family museum"


def test_check_weather_through_gateway_can_use_redis_cache(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    client = FakeAMapClient(
        {
            "/v3/weather/weatherInfo": {
                "status": "1",
                "lives": [
                    {
                        "city": "Shanghai",
                        "weather": "Sunny",
                        "temperature": "25",
                        "winddirection": "Southeast",
                        "windpower": "3",
                        "reporttime": "2026-05-12 10:00:00",
                    }
                ],
            }
        }
    )
    gateway = build_gateway(db_session, AMapProvider(client), cache, rate_limiter)
    run = create_run(db_session)
    request = ToolGatewayRequest(
        run_id=run.run_id,
        tool_name="check_weather",
        payload={"city": "310000"},
    )

    first = gateway.invoke(request)
    second = gateway.invoke(request)

    assert first.status == "succeeded"
    assert second.status == "cached"
    assert second.cache_hit is True
    assert second.response_json == first.response_json
    assert len(client.calls) == 1

    statuses = [event.status for event in ToolEventRepository(db_session).list_for_run(run.run_id)]
    assert sorted(statuses) == ["cached", "succeeded"]


def test_amap_provider_error_becomes_failed_gateway_result(db_session: Session, redis_runtime) -> None:
    cache, rate_limiter = redis_runtime
    client = FakeAMapClient({}, should_fail=True)
    gateway = build_gateway(db_session, AMapProvider(client), cache, rate_limiter)
    run = create_run(db_session)

    result = gateway.invoke(
        ToolGatewayRequest(
            run_id=run.run_id,
            tool_name="check_weather",
            payload={"city": "310000"},
        )
    )

    assert result.status == "failed"
    assert result.error_json["code"] == "provider_error"
    assert result.error_json["details"]["exception_type"] == "AMapProviderError"
    events = ToolEventRepository(db_session).list_for_run(run.run_id)
    assert events[-1].status == "failed"
    assert events[-1].error_json == result.error_json
