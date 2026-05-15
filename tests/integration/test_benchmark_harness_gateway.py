from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.benchmark import BenchmarkHarness, load_default_benchmark_cases
from backend.app.db.session import SessionLocal
from backend.app.models.runtime import AgentRun, ToolEvent
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


TEST_PREFIX = "weekendpilot:test:benchmark-harness"


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
def harness_paths():
    suffix = str(uuid4())
    trace_path = Path("var/test-traces") / suffix / "weekendpilot-traces.jsonl"
    report_dir = Path("var/test-benchmarks") / suffix
    try:
        yield trace_path, report_dir
    finally:
        if trace_path.exists():
            trace_path.unlink()
        if trace_path.parent.exists():
            trace_path.parent.rmdir()
        for path in sorted(report_dir.glob("*"), reverse=True) if report_dir.exists() else []:
            path.unlink()
        if report_dir.exists():
            report_dir.rmdir()


def test_benchmark_harness_runs_full_mock_world_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_default_benchmark_cases()[0]
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    result = harness.run_case(case)

    assert result.status == "passed"
    assert result.run_id is not None
    assert result.trace_id is not None
    assert result.tool_event_count >= case.expected.min_tool_event_count
    assert result.action_count >= case.expected.min_action_count
    assert result.feedback_status == "completed"
    assert result.report_path is not None

    report_path = Path(result.report_path)
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["case_id"] == case.case_id
    assert report_payload["status"] == "passed"

    serialized_report = json.dumps(report_payload, sort_keys=True)
    for forbidden in ("action_id", "tool_event_id", "api_key", "token", "secret", "debug_trace"):
        assert forbidden not in serialized_report

    trace_ids = set(
        db_session.scalars(select(ToolEvent.langsmith_trace_id).where(ToolEvent.run_id == result.run_id)).all()
    )
    assert trace_ids == {result.trace_id}

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.case_id == case.case_id
    assert run.metadata_json["benchmark"]["case_id"] == case.case_id
    assert run.metadata_json["benchmark"]["benchmark_harness_version"] == "locallife_bench_harness_v0"
    assert run.metadata_json["observability"]["trace_id"] == result.trace_id
