from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.benchmark import BenchmarkHarness, load_benchmark_case, load_default_benchmark_cases
from backend.app.benchmark.replay import BenchmarkReplayHarness
from backend.app.db.session import SessionLocal
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


TEST_PREFIX = "weekendpilot:test:benchmark-replay"
FORBIDDEN_REPORT_TEXT = (
    "action_id",
    "tool_event_id",
    "api_key",
    "token",
    "secret",
    "authorization",
    "debug_trace",
)


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


@pytest.fixture()
def replay_paths():
    suffix = str(uuid4())
    trace_path = Path("var/test-traces") / suffix / "weekendpilot-traces.jsonl"
    report_dir = Path("var/test-benchmarks") / suffix
    replay_report_dir = Path("var/test-benchmark-replays") / suffix
    try:
        yield trace_path, report_dir, replay_report_dir
    finally:
        if trace_path.exists():
            trace_path.unlink()
        if trace_path.parent.exists():
            trace_path.parent.rmdir()
        for directory in (report_dir, replay_report_dir):
            for path in sorted(directory.glob("*"), reverse=True) if directory.exists() else []:
                path.unlink()
            if directory.exists():
                directory.rmdir()


def test_replay_happy_path_benchmark_report(
    db_session: Session,
    redis_runtime,
    replay_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir, replay_report_dir = replay_paths
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )
    source = harness.run_case(load_default_benchmark_cases()[0])
    replay = BenchmarkReplayHarness(harness, replay_report_dir=replay_report_dir)

    result = replay.replay_report(source.report_path)

    assert result.status == "passed"
    assert result.source.workflow_status == "completed"
    assert result.replay.workflow_status == "completed"
    assert result.source.observed_tool_names == result.replay.observed_tool_names
    assert result.source.action_count == result.replay.action_count
    assert result.replay_report_path is not None
    assert Path(result.replay_report_path).exists()
    _assert_sanitized_report(Path(result.replay_report_path))


def test_replay_route_failure_benchmark_report(
    db_session: Session,
    redis_runtime,
    replay_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir, replay_report_dir = replay_paths
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )
    source = harness.run_case(load_benchmark_case("family_route_failure_v1"))
    replay = BenchmarkReplayHarness(harness, replay_report_dir=replay_report_dir)

    result = replay.replay_report(source.report_path)

    assert result.status == "passed"
    assert result.source.workflow_status == "failed"
    assert result.replay.workflow_status == "failed"
    assert result.source.action_count == 0
    assert result.replay.action_count == 0
    assert result.source.injected_failure_count >= 1
    assert result.replay.injected_failure_count >= 1
    assert "stop_safely" in result.source.recovery_actions
    assert "stop_safely" in result.replay.recovery_actions
    assert result.replay_report_path is not None
    _assert_sanitized_report(Path(result.replay_report_path))


def _assert_sanitized_report(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized
