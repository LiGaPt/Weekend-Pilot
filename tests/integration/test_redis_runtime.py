from __future__ import annotations

import time
from uuid import uuid4

import pytest

from backend.app.runtime import (
    FixedWindowRateLimiter,
    JsonRedisCache,
    RedisKeyBuilder,
    RedisLockManager,
    RedisProgressStream,
    get_redis_client,
)


TEST_PREFIX = "weekendpilot:test"


def wait_until(condition, timeout_seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


@pytest.fixture()
def redis_runtime():
    client = get_redis_client()
    client.ping()
    builder = RedisKeyBuilder(prefix=TEST_PREFIX)

    def cleanup() -> None:
        keys = list(client.scan_iter(f"{TEST_PREFIX}:*"))
        if keys:
            client.delete(*keys)

    cleanup()
    try:
        yield client, builder
    finally:
        cleanup()


def test_json_cache_stores_reads_deletes_and_expires_values(redis_runtime) -> None:
    client, builder = redis_runtime
    cache = JsonRedisCache(client, builder)
    value = {
        "family": {"child_age": 5, "diet": "light"},
        "candidates": ["museum", "garden"],
    }

    cache.set_json("plan-preview", value, ttl_seconds=30)

    assert cache.get_json("plan-preview") == value
    assert cache.delete("plan-preview") == 1
    assert cache.get_json("plan-preview") is None

    cache.set_json("short-lived", {"ok": True}, ttl_seconds=1)
    assert cache.get_json("short-lived") == {"ok": True}
    assert wait_until(lambda: cache.get_json("short-lived") is None)


def test_lock_manager_acquires_conflicts_and_releases_by_matching_token(redis_runtime) -> None:
    client, builder = redis_runtime
    locks = RedisLockManager(client, builder)

    token = locks.acquire("reservation:restaurant-1", ttl_seconds=30)

    assert isinstance(token, str)
    assert token
    assert locks.acquire("reservation:restaurant-1", ttl_seconds=30) is None
    assert locks.release("reservation:restaurant-1", "wrong-token") is False
    assert locks.release("reservation:restaurant-1", token) is True
    assert locks.acquire("reservation:restaurant-1", ttl_seconds=30) is not None


def test_lock_manager_allows_reacquire_after_expiration(redis_runtime) -> None:
    client, builder = redis_runtime
    locks = RedisLockManager(client, builder)

    assert locks.acquire("short-lock", ttl_seconds=1) is not None
    assert locks.acquire("short-lock", ttl_seconds=1) is None

    assert wait_until(lambda: locks.acquire("short-lock", ttl_seconds=1) is not None)


def test_fixed_window_rate_limiter_allows_until_limit_then_denies(redis_runtime) -> None:
    client, builder = redis_runtime
    limiter = FixedWindowRateLimiter(client, builder)

    first = limiter.allow("search-poi", limit=2, window_seconds=30)
    second = limiter.allow("search-poi", limit=2, window_seconds=30)
    third = limiter.allow("search-poi", limit=2, window_seconds=30)

    assert first.allowed is True
    assert first.remaining == 1
    assert 0 < first.reset_after_seconds <= 30
    assert second.allowed is True
    assert second.remaining == 0
    assert 0 < second.reset_after_seconds <= 30
    assert third.allowed is False
    assert third.remaining == 0
    assert 0 < third.reset_after_seconds <= 30


def test_progress_stream_appends_and_reads_events_in_order(redis_runtime) -> None:
    client, builder = redis_runtime
    stream = RedisProgressStream(client, builder)
    run_id = f"run-{uuid4()}"

    first_id = stream.append(run_id, "planning_started", {"step": 1})
    second_id = stream.append(run_id, "candidate_found", {"poi_id": "poi-1"})

    events = stream.read(run_id)
    assert [event.event_id for event in events] == [first_id, second_id]
    assert [event.event_type for event in events] == ["planning_started", "candidate_found"]
    assert [event.payload for event in events] == [{"step": 1}, {"poi_id": "poi-1"}]

    events_after_first = stream.read(run_id, last_id=first_id)
    assert [event.event_id for event in events_after_first] == [second_id]


def test_progress_stream_read_with_no_events_returns_empty_list(redis_runtime) -> None:
    client, builder = redis_runtime
    stream = RedisProgressStream(client, builder)

    assert stream.read(f"run-{uuid4()}") == []
