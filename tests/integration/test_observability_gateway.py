from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import backend.app.observability.service as observability_service
from backend.app.benchmark import BenchmarkHarness, load_benchmark_case
from backend.app.benchmark import internal_summary as internal_benchmark_summary
from backend.app.confirmation import HumanConfirmationService
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal
from backend.app.db.session import get_db
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.main import create_app
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder
from backend.app.observability import integrity_summary as integrity_summary_module
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


@pytest.fixture()
def release_gate_summary_dir():
    directory = Path("var/test-release-gate-summary") / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    try:
        yield directory
    finally:
        for path in sorted(directory.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if directory.exists():
            directory.rmdir()


@pytest.fixture()
def integrity_summary_dir():
    directory = Path("var/test-system-integrity-summary-gateway") / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    try:
        yield directory
    finally:
        for path in sorted(directory.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if directory.exists():
            directory.rmdir()


@pytest.fixture()
def recovery_review_alias_dir():
    directory = Path("var/test-recovery-review-aliases-gateway") / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    try:
        yield directory
    finally:
        for path in sorted(directory.rglob("*"), reverse=True):
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
    assert payload["selected_plan_review"] is None
    assert payload["run_summary"] == {
        "schema_version": "weekendpilot_internal_run_summary_v1",
        "run_id": str(run.run_id),
        "trace_id": "trace-demo",
        "workflow_status": "running",
        "selected_plan_id": None,
        "plan_status": None,
        "execution_status": None,
        "feedback_status": None,
        "stage_timing": {
            "present": True,
            "total_duration_ms": 25,
            "stage_count": 1,
            "slowest_stage_name": "initialize",
            "slowest_stage_duration_ms": 25,
        },
        "tool_events": {
            "total_count": 1,
            "read_count": 1,
            "write_count": 0,
            "status_counts": {"completed": 1},
            "provider_counts": {"mock_world": 1},
            "latest_event": {
                "tool_name": "search_poi",
                "tool_type": "read",
                "provider": "mock_world",
                "status": "completed",
                "latency_ms": 10,
                "created_at": payload["run_summary"]["tool_events"]["latest_event"]["created_at"],
            },
        },
        "recovery": {
            "entered_recovery": False,
            "attempt_count": 0,
            "max_attempts": 0,
            "terminal_action": None,
            "terminal_status": None,
            "latest_error_type": None,
            "replay_case_id": None,
        },
    }
    assert payload["preview_diagnostics"] is None
    serialized = json.dumps(payload, sort_keys=True)
    assert "idempotency_key" not in serialized
    assert "tool_event_id" not in serialized
    assert "action_id" not in serialized


def test_internal_observability_route_returns_selected_plan_review(
    db_session: Session,
    observability_client: TestClient,
) -> None:
    run = _create_run(db_session)
    selected = PlanRepository(db_session).create(
        run_id=run.run_id,
        status="selected",
        selected=True,
        plan_json={
            "title": "Family Afternoon Plan",
            "summary": "Indoor activity first, then a lighter dinner nearby.",
            "activity": {
                "name": "Family Science Center",
                "category": "activity",
                "address": "100 Science Road",
            },
            "dining": {
                "name": "Light Table",
                "category": "dining",
                "address": "8 Dinner Street",
            },
            "timeline": [
                {
                    "sequence": 1,
                    "title": "Indoor activity",
                    "start_label": "14:00",
                    "end_label": "16:00",
                    "duration_minutes": 120,
                }
            ],
            "route": {
                "mode": "driving",
                "distance_meters": 3200,
                "duration_minutes": 18,
                "summary": "A short drive keeps the afternoon easy.",
            },
            "feasibility": {
                "is_feasible": True,
                "reasons": ["Fits the requested afternoon window."],
                "warnings": [],
                "total_duration_minutes": 270,
                "route_duration_minutes": 18,
                "queue_wait_minutes": 5,
            },
            "action_manifest": {
                "source": "proposed_actions",
                "action_count": 1,
                "actions": [
                    {
                        "action_ref": "draft_1_action_1",
                        "execution_order": 1,
                        "action_type": "reserve_restaurant",
                        "target_id": "restaurant_light_001",
                        "payload_preview": {"party_size": 3},
                        "reason": "Lock dinner seating after confirmation.",
                    }
                ],
            },
        },
    )
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{run.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_plan_review"] == {
        "plan_id": str(selected.plan_id),
        "status": "selected",
        "title": "Family Afternoon Plan",
        "summary": "Indoor activity first, then a lighter dinner nearby.",
        "activity": {
            "name": "Family Science Center",
            "category": "activity",
            "address": "100 Science Road",
        },
        "dining": {
            "name": "Light Table",
            "category": "dining",
            "address": "8 Dinner Street",
        },
        "timeline": [
            {
                "sequence": 1,
                "title": "Indoor activity",
                "start_label": "14:00",
                "end_label": "16:00",
                "duration_minutes": 120,
            }
        ],
        "route": {
            "mode": "driving",
            "distance_meters": 3200,
            "duration_minutes": 18,
            "summary": "A short drive keeps the afternoon easy.",
        },
        "feasibility": {
            "is_feasible": True,
            "reasons": ["Fits the requested afternoon window."],
            "warnings": [],
            "total_duration_minutes": 270,
            "route_duration_minutes": 18,
            "queue_wait_minutes": 5,
        },
        "action_manifest": {
            "source": "proposed_actions",
            "action_count": 1,
            "actions": [
                {
                    "action_ref": "draft_1_action_1",
                    "execution_order": 1,
                    "action_type": "reserve_restaurant",
                    "target_id": "[REDACTED]",
                    "payload_preview": {"party_size": 3},
                    "reason": "Lock dinner seating after confirmation.",
                }
            ],
        },
    }


def test_internal_observability_route_returns_404_for_missing_run(
    observability_client: TestClient,
) -> None:
    response = observability_client.get(f"/internal/runs/{uuid4()}/observability")

    assert response.status_code == 404


def test_release_gate_benchmark_summary_route_returns_latest_summary(
    observability_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    release_gate_summary_dir: Path,
) -> None:
    report_path = release_gate_summary_dir / "latest-release_gate_v1-run-report.json"
    report_path.write_text(json.dumps(_build_release_gate_summary_report()), encoding="utf-8")
    monkeypatch.setattr(internal_benchmark_summary, "DEFAULT_LATEST_RELEASE_GATE_REPORT_PATH", report_path)

    response = observability_client.get("/internal/benchmarks/release-gate-v1/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "schema_version": "weekendpilot_internal_benchmark_summary_v1",
        "suite_id": "release_gate_v1",
        "suite_title": "Benchmark release gate v1",
        "run_status": "passed",
        "case_count": 15,
        "passed_count": 15,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "matrix_summary": {
            "level_counts": {"L1": 3, "L2": 8, "L3": 4},
            "tool_profile_counts": {"mock_world": 15},
            "failure_mode_counts": {"none": 14, "route_unavailable": 1},
            "tag_counts": {
                "memory_advisory": 1,
                "memory_expired": 1,
                "memory_governance": 2,
                "memory_override": 1,
            },
        },
        "benchmark_timing_summary_present": True,
        "benchmark_timing_summary": {
            "schema_version": "benchmark_timing_summary_v1",
            "case_count": 15,
            "overall_total_duration_ms": {
                "sample_count": 15,
                "min_ms": 320,
                "p50_ms": 390,
                "p95_ms": 424,
                "p99_ms": 424,
                "max_ms": 424,
                "mean_ms": 387.8,
            },
            "stages": [
                {
                    "node_name": "pre_flight_check_availability",
                    "sample_count": 15,
                    "retry_case_count": 0,
                    "min_ms": 12,
                    "p50_ms": 20,
                    "p95_ms": 36,
                    "p99_ms": 36,
                    "max_ms": 36,
                    "mean_ms": 19.6,
                }
            ],
        },
        "report_path": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
    }


def test_release_gate_benchmark_summary_route_degrades_when_timing_summary_is_missing(
    observability_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    release_gate_summary_dir: Path,
) -> None:
    report_path = release_gate_summary_dir / "latest-release_gate_v1-run-report.json"
    payload = _build_release_gate_summary_report()
    payload["benchmark_summary"].pop("benchmark_timing_summary", None)
    payload.pop("benchmark_timing_summary", None)
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(internal_benchmark_summary, "DEFAULT_LATEST_RELEASE_GATE_REPORT_PATH", report_path)

    response = observability_client.get("/internal/benchmarks/release-gate-v1/summary")

    assert response.status_code == 200
    degraded_payload = response.json()
    assert degraded_payload["benchmark_timing_summary_present"] is False
    assert degraded_payload["benchmark_timing_summary"] is None


def test_release_gate_benchmark_summary_route_returns_404_when_latest_report_is_missing(
    observability_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    release_gate_summary_dir: Path,
) -> None:
    monkeypatch.setattr(
        internal_benchmark_summary,
        "DEFAULT_LATEST_RELEASE_GATE_REPORT_PATH",
        release_gate_summary_dir / "missing-release_gate_v1-run-report.json",
    )

    response = observability_client.get("/internal/benchmarks/release-gate-v1/summary")

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Latest release_gate_v1 benchmark summary was not found. "
            "Run python scripts/run_benchmark_release_gate.py first."
        )
    }


def test_system_integrity_summary_route_returns_ready_summary(
    observability_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    integrity_summary_dir: Path,
) -> None:
    _write_integrity_summary_files(integrity_summary_dir)
    monkeypatch.setattr(
        integrity_summary_module,
        "EVIDENCE_PATHS",
        {
            key: integrity_summary_dir / relative_path
            for key, relative_path in integrity_summary_module.EVIDENCE_PATHS.items()
        },
    )

    response = observability_client.get("/internal/system/integrity-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["benchmark_summary"]["release_blocked"] is False
    assert payload["formal_verification_summary"]["status"] == "ready"
    assert payload["formal_verification_summary"]["case_count"] == 30
    assert payload["safe_stop_summary"]["status"] == "ready"
    assert payload["safe_stop_summary"]["gate_id"] == "safe_stop_gate_v1"
    assert payload["safe_stop_summary"]["case_count"] == 8
    assert payload["stability_summary"]["pass_pow_4"] == 1.0
    assert payload["memory_governance_summary"]["memory_case_count"] == 2
    assert payload["recovery_replay_summary"]["passed_check_count"] == 3
    assert payload["redaction_summary"]["internal_only"] is True
    assert any(item["evidence_id"] == "v2_integrity_gate" for item in payload["evidence_paths"])
    assert any(item["evidence_id"] == "safe_stop_gate_v1" for item in payload["evidence_paths"])


def test_system_integrity_summary_route_returns_degraded_summary_when_stability_missing(
    observability_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    integrity_summary_dir: Path,
) -> None:
    _write_integrity_summary_files(integrity_summary_dir, include_stability=False)
    monkeypatch.setattr(
        integrity_summary_module,
        "EVIDENCE_PATHS",
        {
            key: integrity_summary_dir / relative_path
            for key, relative_path in integrity_summary_module.EVIDENCE_PATHS.items()
        },
    )

    response = observability_client.get("/internal/system/integrity-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["stability_summary"]["status"] == "missing"


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


def _build_release_gate_summary_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [],
        "passed_count": 15,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "release_gate_v1",
            "suite_title": "Benchmark release gate v1",
            "run_status": "passed",
            "case_count": 15,
            "passed_count": 15,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "benchmark_timing_summary": {
                "schema_version": "benchmark_timing_summary_v1",
                "case_count": 15,
                "overall_total_duration_ms": {
                    "sample_count": 15,
                    "min_ms": 320,
                    "p50_ms": 390,
                    "p95_ms": 424,
                    "p99_ms": 424,
                    "max_ms": 424,
                    "mean_ms": 387.8,
                },
                "stages": [
                    {
                        "node_name": "pre_flight_check_availability",
                        "sample_count": 15,
                        "retry_case_count": 0,
                        "min_ms": 12,
                        "p50_ms": 20,
                        "p95_ms": 36,
                        "p99_ms": 36,
                        "max_ms": 36,
                        "mean_ms": 19.6,
                    }
                ],
            },
            "matrix_summary": {
                "schema_version": "weekendpilot_benchmark_case_matrix_v1",
                "case_count": 15,
                "level_counts": {"L1": 3, "L2": 8, "L3": 4},
                "tool_profile_counts": {"mock_world": 15},
                "failure_mode_counts": {"none": 14, "route_unavailable": 1},
                "tag_counts": {
                    "memory_advisory": 1,
                    "memory_expired": 1,
                    "memory_governance": 2,
                    "memory_override": 1,
                },
            },
        },
        "benchmark_timing_summary": {
            "schema_version": "benchmark_timing_summary_v1",
            "case_count": 15,
            "overall_total_duration_ms": {
                "sample_count": 15,
                "min_ms": 320,
                "p50_ms": 390,
                "p95_ms": 424,
                "p99_ms": 424,
                "max_ms": 424,
                "mean_ms": 387.8,
            },
            "stages": [
                {
                    "node_name": "pre_flight_check_availability",
                    "sample_count": 15,
                    "retry_case_count": 0,
                    "min_ms": 12,
                    "p50_ms": 20,
                    "p95_ms": 36,
                    "p99_ms": 36,
                    "max_ms": 36,
                    "mean_ms": 19.6,
                }
            ],
        },
        "report_path": "E:/tmp/suite-release_gate_v1-run-report.json",
    }


def _write_integrity_summary_files(root: Path, *, include_stability: bool = True) -> None:
    _write_json(root / "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json", _build_v2_gate_report())
    _write_json(root / "var/formal-benchmarks/latest-all_registered-run-report.json", _build_all_registered_report())
    _write_json(root / "var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json", _build_safe_stop_report())
    if include_stability:
        _write_json(
            root / "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
            _build_stability_report(),
        )
    _write_json(
        root / "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        _build_recovery_review(),
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_v2_gate_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [],
        "passed_count": 20,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "v2_integrity",
            "suite_title": "V2 integrity",
            "run_status": "passed",
            "case_count": 20,
            "passed_count": 20,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "benchmark_timing_summary": {
                "schema_version": "benchmark_timing_summary_v1",
                "case_count": 20,
                "overall_total_duration_ms": {
                    "sample_count": 20,
                    "min_ms": 320,
                    "p50_ms": 390,
                    "p95_ms": 424,
                    "p99_ms": 424,
                    "max_ms": 424,
                    "mean_ms": 388.4,
                },
                "stages": [],
            },
        },
        "v2_integrity_gate_evaluation": {
            "schema_version": "weekendpilot_v2_integrity_gate_evaluation_v1",
            "gate_id": "v2_integrity_gate",
            "suite_id": "v2_integrity",
            "release_blocked": False,
            "blocking_failures": [],
            "coverage_thresholds": {},
            "observed_coverage": {
                "integrity_coverage_summary": {
                    "case_count": 20,
                    "memory_case_count": 6,
                    "recovery_case_count": 6,
                    "continuation_case_count": 2,
                    "robustness_case_count": 4,
                    "l4_case_count": 2,
                },
                "memory_mode_counts": {"none": 12, "override_guarded": 1},
                "conversation_mode_counts": {"single_turn": 15, "replan_versioned": 2, "clarification": 1},
                "failure_mode_counts": {"none": 12, "route_unavailable": 1},
            },
        },
    }


def _build_stability_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_stability_passk_v1",
        "metric_version": "passk_v0",
        "suite_id": "v2_integrity",
        "gate_id": "v2_integrity_gate",
        "requested_run_count": 4,
        "executed_run_count": 4,
        "window_size": 4,
        "window_count": 1,
        "discarded_tail_run_count": 0,
        "success_count": 4,
        "failure_count": 0,
        "error_count": 0,
        "success_at_1": 1.0,
        "pass_at_4": 1.0,
        "pass_pow_4": 1.0,
        "attempts": [],
        "windows": [],
    }


def _build_all_registered_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [
            {
                "schema_version": "weekendpilot_benchmark_case_result_v1",
                "case_id": "family_memory_override_v1",
                "status": "passed",
                "overall_score": 1.0,
                "tool_event_count": 5,
                "action_count": 0,
                "scores": [
                    {
                        "name": "memory_governance",
                        "score": 1.0,
                        "passed": True,
                        "reason": "ok",
                        "details": {},
                    }
                ],
            },
            {
                "schema_version": "weekendpilot_benchmark_case_result_v1",
                "case_id": "family_memory_advisory_fill_v1",
                "status": "passed",
                "overall_score": 1.0,
                "tool_event_count": 5,
                "action_count": 0,
                "scores": [
                    {
                        "name": "memory_governance",
                        "score": 1.0,
                        "passed": True,
                        "reason": "ok",
                        "details": {},
                    }
                ],
            },
        ],
        "passed_count": 30,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "all_registered",
            "suite_title": "All registered",
            "run_status": "passed",
            "case_count": 30,
            "passed_count": 30,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
        },
    }


def _build_safe_stop_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [],
        "passed_count": 8,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "recovery_focused",
            "suite_title": "Safe stop gate",
            "run_status": "passed",
            "case_count": 8,
            "passed_count": 8,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
        },
        "safe_stop_gate_evaluation": {
            "schema_version": "weekendpilot_safe_stop_gate_evaluation_v1",
            "gate_id": "safe_stop_gate_v1",
            "suite_id": "recovery_focused",
            "release_blocked": False,
            "blocking_failures": [],
        },
    }


def _build_recovery_review() -> dict:
    return {
        "schema_version": "weekendpilot_recovery_replay_review_v1",
        "status": "passed",
        "case_id": "family_route_failure_v1",
        "run_id": None,
        "run_directory": "var/recovery-reviews/recovery-review-123",
        "source_report_path": "var/formal-benchmarks/family-route.json",
        "replay_report_path": "var/recovery-reviews/replay-family-route.json",
        "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        "checks": [
            {"name": "a", "passed": True, "detail": "ok"},
            {"name": "b", "passed": True, "detail": "ok"},
            {"name": "c", "passed": True, "detail": "ok"},
        ],
        "failure_chain_summary": None,
        "replay_summary": {
            "status": "passed",
            "mismatch_count": 0,
            "failure_chain_signature": ["route_unavailable"],
        },
        "recovery_review": {
            "benchmark_report_path": "var/formal-benchmarks/family-route.json",
            "attempt_count": 1,
            "max_attempts": 2,
            "recovery_actions": ["stop_safely"],
            "replay_source": {
                "case_id": "family_route_failure_v1",
                "benchmark_report_path": "var/formal-benchmarks/family-route.json",
            },
        },
    }


def _write_recovery_review_alias(path: Path, *, source_report_path: str, replay_report_path: str, case_id: str) -> None:
    payload = _build_recovery_review()
    payload["case_id"] = case_id
    payload["source_report_path"] = source_report_path
    payload["replay_report_path"] = replay_report_path
    payload["latest_review_path"] = path.as_posix()
    payload["recovery_review"]["benchmark_report_path"] = source_report_path
    payload["recovery_review"]["replay_source"]["benchmark_report_path"] = source_report_path
    path.write_text(json.dumps(payload), encoding="utf-8")


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
    assert payload["run_summary"]["recovery"] == {
        "entered_recovery": True,
        "attempt_count": 1,
        "max_attempts": 2,
        "terminal_action": "stop_safely",
        "terminal_status": "stopped",
        "latest_error_type": "draft_exists",
        "replay_case_id": "family_route_failure_v1",
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert "action_id" not in serialized
    assert "tool_event_id" not in serialized
    assert "idempotency_key" not in serialized


def test_internal_observability_route_returns_recovery_replay_link_summary_for_matching_alias(
    db_session: Session,
    redis_runtime,
    observability_client: TestClient,
    benchmark_paths,
    monkeypatch: pytest.MonkeyPatch,
    recovery_review_alias_dir: Path,
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
    alias_path = recovery_review_alias_dir / "latest-family_route_failure_v1-review.json"
    _write_recovery_review_alias(
        alias_path,
        source_report_path=result.report_path,
        replay_report_path="var/recovery-reviews/recovery-review-123/replays/family_route_failure_v1.json",
        case_id=case.case_id,
    )
    monkeypatch.setattr(observability_service, "_latest_recovery_review_alias_path", lambda current_case_id: alias_path)
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{result.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recovery_replay_link_summary"] == {
        "status": "matched",
        "case_id": "family_route_failure_v1",
        "source_report_path": result.report_path,
        "latest_review_path": alias_path.as_posix(),
        "review_artifact_path": "var/recovery-reviews/recovery-review-123/recovery-review.json",
        "replay_report_path": "var/recovery-reviews/recovery-review-123/replays/family_route_failure_v1.json",
        "review_status": "passed",
        "check_count": 3,
        "passed_check_count": 3,
        "failed_check_count": 0,
        "mismatch_reason": None,
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert "api_key" not in serialized
    assert "token" not in serialized
    assert "action_id" not in serialized
    assert "tool_event_id" not in serialized


def test_internal_observability_route_returns_missing_recovery_replay_link_summary_without_failing(
    db_session: Session,
    redis_runtime,
    observability_client: TestClient,
    benchmark_paths,
    monkeypatch: pytest.MonkeyPatch,
    recovery_review_alias_dir: Path,
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
    alias_path = recovery_review_alias_dir / "latest-family_route_failure_v1-review.json"
    monkeypatch.setattr(observability_service, "_latest_recovery_review_alias_path", lambda current_case_id: alias_path)
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{result.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recovery_replay_link_summary"] == {
        "status": "missing",
        "case_id": "family_route_failure_v1",
        "source_report_path": result.report_path,
        "latest_review_path": alias_path.as_posix(),
        "review_artifact_path": None,
        "replay_report_path": None,
        "review_status": None,
        "check_count": None,
        "passed_check_count": None,
        "failed_check_count": None,
        "mismatch_reason": "latest recovery review alias was not found",
    }


def test_internal_observability_route_returns_degraded_run_summary_without_timing_or_recovery(
    db_session: Session,
    observability_client: TestClient,
) -> None:
    run = _create_run(db_session)
    db_session.commit()

    response = observability_client.get(f"/internal/runs/{run.run_id}/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_summary"] == {
        "schema_version": "weekendpilot_internal_run_summary_v1",
        "run_id": str(run.run_id),
        "trace_id": None,
        "workflow_status": "running",
        "selected_plan_id": None,
        "plan_status": None,
        "execution_status": None,
        "feedback_status": None,
        "stage_timing": {
            "present": False,
            "total_duration_ms": None,
            "stage_count": None,
            "slowest_stage_name": None,
            "slowest_stage_duration_ms": None,
        },
        "tool_events": {
            "total_count": 0,
            "read_count": 0,
            "write_count": 0,
            "status_counts": {},
            "provider_counts": {},
            "latest_event": None,
        },
        "recovery": {
            "entered_recovery": False,
            "attempt_count": 0,
            "max_attempts": 0,
            "terminal_action": None,
            "terminal_status": None,
            "latest_error_type": None,
            "replay_case_id": None,
        },
    }
