from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.benchmark import BenchmarkHarness, load_benchmark_case
from backend.app.confirmation import HumanConfirmationService
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal
from backend.app.db.session import get_db
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.main import create_app
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicItineraryGenerator,
    DeterministicQueryPlanner,
    QueryPlanExecutor,
)
from backend.app.plans import ReviewedPlanPersistenceService
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.review import FinalReviewGate
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway


TEST_PREFIX = "weekendpilot:test:observability-gateway"


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
def trace_path():
    directory = Path("var/test-traces") / str(uuid4())
    path = directory / "weekendpilot-traces.jsonl"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()
        if directory.exists():
            directory.rmdir()


@pytest.fixture()
def benchmark_paths():
    directory = Path("var/test-benchmarks") / str(uuid4())
    report_dir = directory / "benchmarks"
    trace_path = directory / "benchmarks-trace.jsonl"
    try:
        yield report_dir, trace_path
    finally:
        for path in sorted(directory.rglob("*"), reverse=True) if directory.exists() else []:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if directory.exists():
            directory.rmdir()


def _create_run(
    session: Session,
    *,
    tool_profile: str = "mock_world",
    world_profile: str = "family_afternoon",
):
    user = UserRepository(session).create(
        external_id=f"observability-gateway-user-{uuid4()}",
        display_name="Observability Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-observability-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile=tool_profile,
        world_profile=world_profile,
        failure_profile=None,
        status="running",
        metadata_json={"source": "observability-gateway-test", "api_key": "must-redact"},
    )


def _build_gateway(
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


def _count_rows(session: Session, model, run_id):
    return session.scalar(select(func.count()).select_from(model).where(model.run_id == run_id))


def test_full_mock_world_flow_populates_tool_event_trace_ids_and_records_summary(
    db_session: Session,
    redis_runtime,
    trace_path,
) -> None:
    cache, rate_limiter = redis_runtime
    run = _create_run(db_session)
    gateway = _build_gateway(db_session, cache, rate_limiter)
    recorder = ObservabilityRecorder(
        runs=AgentRunRepository(db_session),
        tool_events=ToolEventRepository(db_session),
        action_ledger=ActionLedgerRepository(db_session),
        plans=PlanRepository(db_session),
        local_buffer=LocalTraceBuffer(trace_path),
    )
    trace_context = recorder.build_context(run.run_id)

    intent = DeterministicIntentParser().parse(
        "This afternoon I want to go out with my wife and child for a few hours. "
        "Not too far. My child is 5, and my wife is trying to eat lighter."
    )
    query_plan = DeterministicQueryPlanner().build(intent, provider_profile="mock_world")
    collection = QueryPlanExecutor(gateway).execute_initial_calls(
        query_plan,
        run.run_id,
        langsmith_trace_id=trace_context.trace_id,
    )
    enrichment = CandidateEnricher(gateway).enrich(
        query_plan,
        collection,
        langsmith_trace_id=trace_context.trace_id,
    )
    drafts = DeterministicItineraryGenerator().generate(query_plan, enrichment)
    review = FinalReviewGate().review(
        query_plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=_count_rows(db_session, ActionLedger, run.run_id),
    )
    assert review.safe_to_present is True

    persistence = ReviewedPlanPersistenceService(PlanRepository(db_session))
    persisted = persistence.persist_reviewed_drafts(review, drafts)
    selected = persistence.select_plan(run.run_id, persisted.persisted_plans[0].plan_id)
    HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        run.run_id,
        selected.plan_id,
        confirmed_by="user",
        source="integration-test",
    )

    execution = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        run.run_id,
        selected.plan_id,
        langsmith_trace_id=trace_context.trace_id,
    )
    assert execution.status == "succeeded"
    feedback = DeterministicFeedbackWriter(
        plans=PlanRepository(db_session),
        runs=AgentRunRepository(db_session),
    ).write_execution_feedback(run.run_id, selected.plan_id)
    assert feedback.status == "completed"

    result = recorder.record_run_summary(trace_context)

    trace_ids = set(
        db_session.scalars(select(ToolEvent.langsmith_trace_id).where(ToolEvent.run_id == run.run_id)).all()
    )
    assert trace_ids == {trace_context.trace_id}
    assert result.local_buffer_written is True
    row = AgentRunRepository(db_session).get_by_id(run.run_id)
    assert row is not None
    assert row.metadata_json["observability"]["trace_id"] == trace_context.trace_id
    assert row.metadata_json["observability"]["langsmith"]["enabled"] is False
    assert row.metadata_json["summary"]["schema_version"] == "weekendpilot_run_summary_v1"
    assert row.metadata_json["summary"]["trace_id"] == trace_context.trace_id

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["trace_id"] == trace_context.trace_id
    assert payload["tool_event_count"] > 0
    assert payload["action_count"] == len(execution.action_results)
    assert payload["feedback_status"] == "completed"
    assert payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
    assert payload["run_summary"]["trace_id"] == trace_context.trace_id
    serialized = json.dumps(payload, sort_keys=True)
    assert "must-redact" not in serialized
    assert "api_key" in serialized
    assert "action_id" not in serialized
    assert "tool_event_id" not in serialized


@pytest.fixture()
def observability_client(redis_runtime, trace_path: Path):
    app = create_app()
    settings = Settings(
        app_env=f"test-internal-observability-{uuid4()}",
        local_trace_buffer_path=str(trace_path),
        langsmith_tracing=False,
    )

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_internal_observability_route_returns_sanitized_run_summary(
    db_session: Session,
    observability_client: TestClient,
) -> None:
    run = _create_run(db_session)
    AgentRunRepository(db_session).update_metadata_json(
        run.run_id,
        {
            "workflow": {
                "timing": {
                    "schema_version": "workflow_timing_summary_v1",
                    "total_duration_ms": 25,
                    "stage_count": 1,
                    "stages": [
                        {
                            "node_name": "initialize",
                            "attempt_count": 1,
                            "total_duration_ms": 25,
                        }
                    ],
                }
            },
            "observability": {
                "trace_id": "trace-internal",
                "status": "completed",
                "local_buffer": {
                    "written": True,
                    "error": {"token": "hide-me", "message": "none"},
                },
                "langsmith": {
                    "enabled": False,
                    "posted": False,
                    "error": None,
                },
            },
            "agents": {"results": [{"role": "supervisor"}, {"role": "discovery"}]},
            "demo": {"trace_id": "trace-demo", "initial_node_history": ["initialize", "wait_confirmation"]},
        },
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="mock_world",
        request_json={"query": "museum"},
        response_json={"candidate_count": 2},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=10,
        langsmith_trace_id="trace-internal",
    )
    ActionLedgerRepository(db_session).create(
        run_id=run.run_id,
        action_type="reserve_restaurant",
        target_id="green-table",
        idempotency_key=f"reserve:{run.run_id}",
        status="succeeded",
        request_json={"foo": "bar"},
        response_json={"result": "ok"},
        error_json=None,
    )
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{run.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == str(run.run_id)
    assert payload["trace_id"] == "trace-demo"
    assert payload["tool_event_count"] == 1
    assert payload["action_count"] == 1
    assert payload["agent_roles"] == ["supervisor", "discovery"]
    assert payload["tool_event_summaries"] == [
        {
            "tool_name": "search_poi",
            "tool_type": "read",
            "provider": "mock_world",
            "status": "completed",
            "cache_hit": False,
            "latency_ms": 10,
            "created_at": payload["tool_event_summaries"][0]["created_at"],
            "request_preview": {"query": "museum", "event_sequence": 1},
            "response_preview": {"candidate_count": 2},
            "error_preview": None,
        }
    ]
    assert payload["action_ledger_summaries"] == [
        {
            "action_type": "reserve_restaurant",
            "target_id": "green-table",
            "status": "succeeded",
            "created_at": payload["action_ledger_summaries"][0]["created_at"],
            "updated_at": payload["action_ledger_summaries"][0]["updated_at"],
            "request_preview": {"foo": "bar"},
            "response_preview": {"result": "ok"},
            "error_preview": None,
        }
    ]
    assert payload["workflow_timing_summary"]["total_duration_ms"] == 25
    assert payload["observability_summary"]["trace_id"] == "trace-internal"
    assert payload["observability_summary"]["local_buffer_error"] == {
        "token": "[REDACTED]",
        "message": "none",
    }
    assert payload["preview_diagnostics"] is None
    serialized = json.dumps(payload, sort_keys=True)
    assert "idempotency_key" not in serialized
    assert "tool_event_id" not in serialized
    assert "action_id" not in serialized


def test_internal_observability_route_returns_404_for_missing_run(
    observability_client: TestClient,
) -> None:
    response = observability_client.get(f"/internal/runs/{uuid4()}/observability")

    assert response.status_code == 404


def test_internal_observability_route_returns_benchmark_artifact_summary_for_benchmark_run(
    db_session: Session,
    redis_runtime,
    observability_client: TestClient,
    benchmark_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    report_dir, trace_file = benchmark_paths
    case = load_benchmark_case("solo_afternoon_v1")
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_file,
    )

    result = harness.run_case(case)
    assert result.run_id is not None
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{result.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmark_artifact_summary"] is not None
    assert payload["benchmark_artifact_summary"]["case_id"] == "solo_afternoon_v1"
    assert payload["benchmark_artifact_summary"]["registered_suite_ids"] == [
        "baseline",
        "default",
        "release_gate_v1",
        "all_registered",
    ]
    assert payload["benchmark_artifact_summary"]["benchmark_status"] == result.status
    assert payload["benchmark_artifact_summary"]["report_path"] == result.report_path
    assert payload["benchmark_artifact_summary"]["taxonomy"]["scenario_bucket"] == "solo"
    assert payload["benchmark_artifact_summary"]["score_summaries"]


def test_internal_observability_route_returns_amap_preview_diagnostics(
    db_session: Session,
    observability_client: TestClient,
) -> None:
    run = _create_run(
        db_session,
        tool_profile="amap",
        world_profile="amap_shanghai_live",
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="amap",
        request_json={"query": "museum"},
        response_json={"candidate_count": 2},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=10,
        langsmith_trace_id="trace-internal-amap",
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="check_route",
        tool_type="read",
        provider="amap",
        request_json={"origin": "a", "destination": "b"},
        response_json=None,
        error_json={"error_type": "rate_limited", "api_key": "hide-me"},
        status="failed",
        cache_hit=False,
        latency_ms=12,
        langsmith_trace_id="trace-internal-amap",
    )
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{run.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_profile"] == "amap"
    assert payload["world_profile"] == "amap_shanghai_live"
    assert payload["preview_diagnostics"] == {
        "schema_version": "weekendpilot_preview_diagnostics_v1",
        "read_profile": "amap",
        "mode": "read_only_preview",
        "confirmation_allowed": False,
        "confirmation_block_reason": "AMAP read-only demo runs cannot be confirmed.",
        "benchmark_eligible": False,
        "benchmark_block_reason": "Canonical benchmark suites support Mock World only.",
        "observed_provider_names": ["amap"],
        "provider_event_count": 2,
        "write_tool_event_count": 0,
        "provider_error_types": ["rate_limited"],
        "cross_provider_fallback_detected": False,
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert "action_id" not in serialized
    assert "tool_event_id" not in serialized
    assert "idempotency_key" not in serialized


def test_internal_observability_route_returns_recovery_path_summary_for_recovery_run(
    db_session: Session,
    redis_runtime,
    observability_client: TestClient,
    benchmark_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    report_dir, trace_file = benchmark_paths
    case = load_benchmark_case("family_route_failure_v1")
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_file,
    )

    result = harness.run_case(case)
    assert result.run_id is not None
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{result.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recovery_path_summary"] is not None
    assert payload["recovery_path_summary"]["attempt_count"] == 1
    assert payload["recovery_path_summary"]["max_attempts"] == 2
    assert payload["recovery_path_summary"]["attempts"][0]["recovery_action"] == "stop_safely"
    assert payload["recovery_path_summary"]["attempts"][0]["status"] == "stopped"
    assert payload["recovery_path_summary"]["attempts"][0]["error_type"] == "draft_exists"
    assert payload["recovery_path_summary"]["replay_source"] == {
        "case_id": "family_route_failure_v1",
        "benchmark_report_path": result.report_path,
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert "action_id" not in serialized
    assert "tool_event_id" not in serialized
    assert "idempotency_key" not in serialized
