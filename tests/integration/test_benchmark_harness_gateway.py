from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.benchmark import (
    BenchmarkHarness,
    load_benchmark_case,
    load_benchmark_suite,
    load_default_benchmark_cases,
    load_failure_benchmark_cases,
)
from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, AgentRun, ToolEvent
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


TEST_PREFIX = "weekendpilot:test:benchmark-harness"
EXPECTED_AGENT_ROLES = {
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
}
DEFAULT_CASE_IDS = {
    "family_afternoon_v1",
    "family_indoor_light_meal_v1",
    "family_outdoor_quick_dinner_v1",
    "family_memory_override_v1",
    "family_citywalk_addon_v1",
    "solo_afternoon_v1",
}
DEFAULT_SCENARIO_BUCKET_COUNTS = {"family": 5, "solo": 1}
DEFAULT_LEVEL_COUNTS = {"L1": 3, "L2": 3}
DEFAULT_WORLD_PROFILE_COUNTS = {"family_afternoon": 5, "solo_afternoon": 1}
DEFAULT_FAILURE_MODE_COUNTS = {"none": 6}
DEFAULT_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "child_friendly": 5,
    "citywalk": 1,
    "indoor_activity": 2,
    "light_activity": 1,
    "light_meal": 4,
    "memory_override": 1,
    "outdoor_activity": 1,
    "quick_dinner": 1,
}
ALL_REGISTERED_SCENARIO_BUCKET_COUNTS = {"family": 6, "solo": 1}
ALL_REGISTERED_LEVEL_COUNTS = {"L1": 3, "L2": 4}
ALL_REGISTERED_WORLD_PROFILE_COUNTS = {"family_afternoon": 6, "solo_afternoon": 1}
ALL_REGISTERED_FAILURE_MODE_COUNTS = {"none": 6, "route_unavailable": 1}
FORBIDDEN_REPORT_TEXT = ("action_id", "tool_event_id", "api_key", "token", "secret", "debug_trace")


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
    assert result.run_summary is not None
    assert result.run_summary.workflow_status == "completed"
    assert result.run_summary.prompt_version == "prompt-v1"
    assert result.feedback_status == "completed"
    assert result.workflow_status == "completed"
    assert result.workflow_timing_summary is not None
    assert result.taxonomy is not None
    assert result.taxonomy.scenario_bucket == "family"
    assert "initialize" in result.workflow_node_history
    assert "generate_summary_message" in result.workflow_node_history
    assert set(result.agent_roles) == EXPECTED_AGENT_ROLES
    assert result.report_path is not None

    report_path = Path(result.report_path)
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["case_id"] == case.case_id
    assert report_payload["status"] == "passed"
    assert report_payload["taxonomy"]["scenario_bucket"] == "family"
    assert report_payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
    assert report_payload["run_summary"]["workflow_status"] == "completed"
    assert report_payload["workflow_status"] == "completed"
    assert report_payload["workflow_timing_summary"]["schema_version"] == "workflow_timing_summary_v1"
    assert "initialize" in report_payload["workflow_node_history"]
    assert "generate_summary_message" in report_payload["workflow_node_history"]
    assert set(report_payload["agent_roles"]) == EXPECTED_AGENT_ROLES

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
    assert run.metadata_json["benchmark"]["taxonomy"]["scenario_bucket"] == "family"
    assert run.metadata_json["benchmark"]["workflow_backed"] is True
    assert run.metadata_json["workflow"]["source"] == "langgraph-workflow"
    assert run.metadata_json["workflow"]["timing"]["schema_version"] == "workflow_timing_summary_v1"
    assert "agents" in run.metadata_json
    assert {entry["role"] for entry in run.metadata_json["agents"]["results"]} == EXPECTED_AGENT_ROLES
    assert "observability" in run.metadata_json
    assert run.metadata_json["observability"]["trace_id"] == result.trace_id


def test_benchmark_harness_runs_solo_afternoon_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("solo_afternoon_v1")
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    result = harness.run_case(case)

    assert result.status == "passed"
    assert result.workflow_status == "completed"
    assert result.run_summary is not None
    assert result.run_summary.world_profile == "solo_afternoon"
    assert result.taxonomy is not None
    assert result.taxonomy.scenario_bucket == "solo"
    assert result.report_path is not None
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    artifact_summary = run.metadata_json["benchmark"]["artifact_summary"]
    assert artifact_summary["schema_version"] == "weekendpilot_benchmark_artifact_summary_v1"
    assert artifact_summary["benchmark_status"] == result.status
    assert artifact_summary["overall_score"] == result.overall_score
    assert artifact_summary["workflow_status"] == result.workflow_status
    assert artifact_summary["tool_event_count"] == result.tool_event_count
    assert artifact_summary["action_count"] == result.action_count
    assert artifact_summary["report_path"] == result.report_path
    assert len(artifact_summary["score_summaries"]) == len(result.scores)
    assert artifact_summary["score_summaries"][0]["name"] == result.scores[0].name
    assert "details" not in artifact_summary["score_summaries"][0]


def test_benchmark_harness_runs_default_mock_world_suite(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    cases = load_default_benchmark_cases()
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    report = harness.run_cases(cases)

    assert {result.case_id for result in report.case_results} == DEFAULT_CASE_IDS
    assert len(report.case_results) == 6
    assert report.run_status == "passed"
    assert report.passed_count == 6
    assert report.failed_count == 0
    assert report.error_count == 0
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.run_status == "passed"
    assert report.benchmark_summary.case_count == len(cases)
    assert report.benchmark_summary.matrix_summary is not None
    assert report.benchmark_summary.matrix_summary.scenario_bucket_counts == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert report.benchmark_summary.matrix_summary.level_counts == DEFAULT_LEVEL_COUNTS
    assert report.benchmark_summary.matrix_summary.world_profile_counts == DEFAULT_WORLD_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.failure_mode_counts == DEFAULT_FAILURE_MODE_COUNTS
    assert report.benchmark_summary.matrix_summary.tag_counts == DEFAULT_TAG_COUNTS
    assert report.benchmark_timing_summary is not None
    assert report.report_path is not None
    assert Path(report.report_path).exists()

    for result in report.case_results:
        assert result.status == "passed"
        assert result.run_id is not None
        assert result.trace_id is not None
        assert result.workflow_status == "completed"
        assert result.workflow_timing_summary is not None
        assert result.run_summary is not None
        assert result.taxonomy is not None
        assert result.feedback_status == "completed"
        assert set(result.agent_roles) == EXPECTED_AGENT_ROLES
        assert result.report_path is not None

        report_path = Path(result.report_path)
        assert report_path.exists()
        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_payload["case_id"] == result.case_id
        assert report_payload["status"] == "passed"
        assert report_payload["taxonomy"]["suite"] == "locallife_bench_v1"
        assert report_payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
        serialized_report = json.dumps(report_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized_report

        run = db_session.get(AgentRun, result.run_id)
        assert run is not None
        assert run.case_id == result.case_id
        assert run.metadata_json["benchmark"]["case_id"] == result.case_id
        assert run.metadata_json["benchmark"]["taxonomy"]["suite"] == "locallife_bench_v1"
        assert run.metadata_json["workflow"]["source"] == "langgraph-workflow"
        assert run.metadata_json["workflow"]["timing"]["schema_version"] == "workflow_timing_summary_v1"
        assert {entry["role"] for entry in run.metadata_json["agents"]["results"]} == EXPECTED_AGENT_ROLES
        assert run.metadata_json["observability"]["trace_id"] == result.trace_id

    suite_payload = json.loads(Path(report.report_path).read_text(encoding="utf-8"))
    assert suite_payload["report_path"] == report.report_path
    assert suite_payload["benchmark_summary"]["schema_version"] == "weekendpilot_benchmark_summary_v1"
    assert suite_payload["benchmark_summary"]["run_status"] == "passed"
    assert suite_payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["level_counts"] == DEFAULT_LEVEL_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["world_profile_counts"] == DEFAULT_WORLD_PROFILE_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == DEFAULT_FAILURE_MODE_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tag_counts"] == DEFAULT_TAG_COUNTS
    assert suite_payload["benchmark_timing_summary"]["schema_version"] == "benchmark_timing_summary_v1"
    assert suite_payload["benchmark_timing_summary"]["case_count"] == len(cases)
    assert suite_payload["benchmark_timing_summary"]["overall_total_duration_ms"]["sample_count"] == len(cases)
    assert suite_payload["benchmark_timing_summary"]["stages"]
    serialized_suite = json.dumps(suite_payload, sort_keys=True)
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized_suite


def test_benchmark_harness_runs_all_registered_suite(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    cases = load_benchmark_suite("all_registered")
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    report = harness.run_cases(cases)

    assert len(report.case_results) == 7
    assert report.run_status == "passed"
    assert report.passed_count == 7
    assert report.failed_count == 0
    assert report.error_count == 0
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.matrix_summary is not None
    assert report.benchmark_summary.matrix_summary.scenario_bucket_counts == ALL_REGISTERED_SCENARIO_BUCKET_COUNTS
    assert report.benchmark_summary.matrix_summary.level_counts == ALL_REGISTERED_LEVEL_COUNTS
    assert report.benchmark_summary.matrix_summary.world_profile_counts == ALL_REGISTERED_WORLD_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.failure_mode_counts == ALL_REGISTERED_FAILURE_MODE_COUNTS


def test_benchmark_harness_runs_route_failure_case_as_expected_safe_stop(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("family_route_failure_v1")
    assert [item.case_id for item in load_failure_benchmark_cases()] == ["family_route_failure_v1"]
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
    assert result.workflow_status == "failed"
    assert result.workflow_timing_summary is not None
    assert result.run_summary is not None
    assert result.run_summary.workflow_status == "failed"
    assert result.action_count == 0
    assert "apply_recovery" in result.workflow_node_history
    assert "saga_execution_engine" not in result.workflow_node_history
    assert result.report_path is not None

    action_count = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == result.run_id)
    )
    assert action_count == 0

    tool_events = db_session.scalars(select(ToolEvent).where(ToolEvent.run_id == result.run_id)).all()
    injected_events = [
        event
        for event in tool_events
        if event.tool_name == "check_route"
        and isinstance(event.error_json, dict)
        and event.error_json.get("error_type") == "failure_injected"
    ]
    assert injected_events
    assert all(event.status == "failed" for event in injected_events)

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.failure_profile == "route_unavailable_v0"
    assert run.metadata_json["benchmark"]["failure_profile"] == "route_unavailable_v0"
    assert run.metadata_json["benchmark"]["failure_profile_metadata"]["profile_id"] == "route_unavailable_v0"
    assert run.metadata_json["workflow"]["timing"]["schema_version"] == "workflow_timing_summary_v1"
    recovery = run.metadata_json["workflow"]["recovery"]
    assert recovery["attempts"][0]["recovery_action"] == "stop_safely"
    assert recovery["attempts"][0]["status"] == "stopped"

    report_payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report_payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
    assert report_payload["run_summary"]["workflow_status"] == "failed"
    assert report_payload["workflow_timing_summary"]["schema_version"] == "workflow_timing_summary_v1"
    serialized_report = json.dumps(report_payload, sort_keys=True)
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized_report
