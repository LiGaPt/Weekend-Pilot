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
BASELINE_CASE_IDS = {
    "family_afternoon_v1",
    "family_indoor_light_meal_v1",
    "family_outdoor_quick_dinner_v1",
    "family_memory_override_v1",
    "family_citywalk_addon_v1",
    "solo_afternoon_v1",
}
EXPANDED_CASE_IDS = {
    "couple_afternoon_v1",
    "friends_gathering_v1",
    "rainy_day_fallback_v1",
    "budget_lite_v1",
}
RECOVERY_CASE_IDS = {
    "family_route_failure_v1",
    "family_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1",
}
MEMORY_GOVERNANCE_CASE_IDS = {
    "family_memory_override_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
}
MEMORY_GOVERNANCE_TOOL_PROFILE_COUNTS = {"mock_world": 3}
CONVERSATION_CONTINUATION_CASE_IDS = {
    "solo_clarification_continuation_v1",
    "family_replan_version_continuation_v1",
}
CONVERSATION_CONTINUATION_TOOL_PROFILE_COUNTS = {"mock_world": 2}
DEFAULT_CASE_IDS = {
    "family_afternoon_v1",
    "family_indoor_light_meal_v1",
    "family_outdoor_quick_dinner_v1",
    "family_memory_override_v1",
    "family_citywalk_addon_v1",
    "solo_afternoon_v1",
    "couple_afternoon_v1",
    "friends_gathering_v1",
    "rainy_day_fallback_v1",
    "budget_lite_v1",
}
RELEASE_GATE_V1_CASE_IDS = {
    *DEFAULT_CASE_IDS,
    "family_route_failure_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
    "solo_clarification_continuation_v1",
    "family_replan_version_continuation_v1",
}
DEFAULT_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 5,
    "friends": 1,
    "mixed": 1,
    "solo": 1,
    "unknown": 1,
}
DEFAULT_LEVEL_COUNTS = {"L1": 3, "L2": 7}
DEFAULT_TOOL_PROFILE_COUNTS = {"mock_world": 10}
DEFAULT_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 5,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 1,
}
RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 9,
    "friends": 1,
    "mixed": 1,
    "solo": 2,
    "unknown": 1,
}
RELEASE_GATE_V1_LEVEL_COUNTS = {"L1": 3, "L2": 8, "L3": 4}
RELEASE_GATE_V1_TOOL_PROFILE_COUNTS = {"mock_world": 15}
RELEASE_GATE_V1_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 9,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 2,
}
DEFAULT_FAILURE_MODE_COUNTS = {"none": 10}
RELEASE_GATE_V1_FAILURE_MODE_COUNTS = {"none": 14, "route_unavailable": 1}
MEMORY_GOVERNANCE_SCENARIO_BUCKET_COUNTS = {"family": 3}
MEMORY_GOVERNANCE_FAILURE_MODE_COUNTS = {"none": 3}
MEMORY_GOVERNANCE_CONSTRAINT_TAG_COUNTS = {
    "child_friendly": 3,
    "indoor_activity": 2,
    "light_meal": 2,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
}
CONVERSATION_CONTINUATION_SCENARIO_BUCKET_COUNTS = {"family": 1, "solo": 1}
CONVERSATION_CONTINUATION_FAILURE_MODE_COUNTS = {"none": 2}
CONVERSATION_CONTINUATION_CONSTRAINT_TAG_COUNTS = {
    "child_friendly": 1,
    "clarification_turn": 1,
    "conversation_continuation": 2,
    "light_activity": 1,
    "light_meal": 2,
    "plan_versioning": 1,
    "replan_turn": 1,
}
BASELINE_SCENARIO_BUCKET_COUNTS = {"family": 5, "solo": 1}
BASELINE_FAILURE_MODE_COUNTS = {"none": 6}
BASELINE_CONSTRAINT_TAG_COUNTS = {
    "addon_optional": 1,
    "child_friendly": 5,
    "citywalk": 1,
    "indoor_activity": 2,
    "light_activity": 1,
    "light_meal": 4,
    "memory_override": 1,
    "outdoor_activity": 1,
    "quick_dinner": 1,
}
EXPANDED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "friends": 1,
    "mixed": 1,
    "unknown": 1,
}
EXPANDED_FAILURE_MODE_COUNTS = {"none": 4}
EXPANDED_TOOL_PROFILE_COUNTS = {"mock_world": 4}
EXPANDED_CONSTRAINT_TAG_COUNTS = {
    "budget_limited": 1,
    "casual_dining": 1,
    "citywalk": 1,
    "date_friendly": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 1,
    "light_meal": 1,
    "outdoor_activity": 1,
    "quick_meal": 1,
    "rainy_day": 1,
}
RECOVERY_SCENARIO_BUCKET_COUNTS = {"family": 2, "mixed": 1}
RECOVERY_FAILURE_MODE_COUNTS = {
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
}
RECOVERY_TOOL_PROFILE_COUNTS = {"mock_world": 3}
RECOVERY_CONSTRAINT_TAG_COUNTS = {
    "bad_weather": 1,
    "child_friendly": 2,
    "composite_failure": 2,
    "dining_unavailable": 1,
    "light_meal": 1,
    "rainy_day": 1,
    "ticket_sold_out": 1,
}
DEFAULT_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 5,
    "citywalk": 2,
    "date_friendly": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 3,
    "light_activity": 1,
    "light_meal": 5,
    "memory_override": 1,
    "outdoor_activity": 2,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
}
RELEASE_GATE_V1_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 9,
    "citywalk": 2,
    "clarification_turn": 1,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "failure_injected": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 4,
    "light_activity": 2,
    "light_meal": 9,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
    "outdoor_activity": 2,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
    "replan_turn": 1,
    "route_failure": 1,
}
RELEASE_GATE_V1_CONSTRAINT_TAG_COUNTS = {
    "addon_optional": 1,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 9,
    "citywalk": 2,
    "clarification_turn": 1,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 4,
    "light_activity": 2,
    "light_meal": 9,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
    "outdoor_activity": 2,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
    "replan_turn": 1,
}
DEFAULT_CONSTRAINT_TAG_COUNTS = {
    "addon_optional": 1,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 5,
    "citywalk": 2,
    "date_friendly": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 3,
    "light_activity": 1,
    "light_meal": 5,
    "memory_override": 1,
    "outdoor_activity": 2,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
}
ALL_REGISTERED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 10,
    "friends": 1,
    "mixed": 2,
    "solo": 2,
    "unknown": 1,
}
ALL_REGISTERED_LEVEL_COUNTS = {"L1": 3, "L2": 8, "L3": 4, "L5": 2}
ALL_REGISTERED_TOOL_PROFILE_COUNTS = {"mock_world": 17}
ALL_REGISTERED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 10,
    "friends_gathering": 1,
    "rainy_day_fallback": 2,
    "solo_afternoon": 2,
}
ALL_REGISTERED_FAILURE_MODE_COUNTS = {
    "none": 14,
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
}
ALL_REGISTERED_TAG_COUNTS = {
    "addon_optional": 1,
    "bad_weather": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 10,
    "citywalk": 2,
    "clarification_turn": 1,
    "composite_failure": 2,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "dining_unavailable": 1,
    "failure_injected": 3,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 4,
    "light_activity": 2,
    "light_meal": 9,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
    "outdoor_activity": 2,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 2,
    "replan_turn": 1,
    "route_failure": 2,
    "ticket_sold_out": 1,
}
ALL_REGISTERED_CONSTRAINT_TAG_COUNTS = {
    "addon_optional": 1,
    "bad_weather": 1,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 10,
    "citywalk": 2,
    "clarification_turn": 1,
    "composite_failure": 2,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "dining_unavailable": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 4,
    "light_activity": 2,
    "light_meal": 9,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
    "outdoor_activity": 2,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 2,
    "replan_turn": 1,
    "ticket_sold_out": 1,
}
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
    assert all(score.name != "conversation_path" for score in result.scores)
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


def test_benchmark_harness_records_memory_policy_for_override_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("family_memory_override_v1")
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
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_score = next(score for score in result.scores if score.name == "memory_governance")

    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["policy_version"] == "memory_query_policy_v1"
    assert sorted(memory_policy["user_override_dimensions"]) == [
        "activity_preferences",
        "dining_preferences",
    ]
    assert memory_policy["dimension_outcomes"] == [
        {
            "dimension": "activity_preferences",
            "winner_source": "user_input",
            "winner_memory_key": None,
            "winner_tier": None,
            "effective_values": ["child_friendly", "indoor"],
            "suppressed_memory_keys": ["activity_style"],
        },
        {
            "dimension": "dining_preferences",
            "winner_source": "user_input",
            "winner_memory_key": None,
            "winner_tier": None,
            "effective_values": ["lighter_options"],
            "suppressed_memory_keys": ["spouse_lighter_meals"],
        },
    ]
    assert [decision["outcome"] for decision in memory_policy["memory_decisions"]] == [
        "suppressed_user_override",
        "suppressed_user_override",
    ]
    assert memory_score.passed is True
    assert memory_score.details["observed_dimension_sources"] == {
        "activity_preferences": "user_input",
        "dining_preferences": "user_input",
    }


def test_benchmark_harness_records_memory_policy_for_advisory_fill_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("family_memory_advisory_fill_v1")
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
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_score = next(score for score in result.scores if score.name == "memory_governance")

    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["policy_version"] == "memory_query_policy_v1"
    assert memory_policy["advisory_memory_keys"] == ["spouse_lighter_meals"]
    assert memory_policy["downgraded_low_confidence_keys"] == ["spouse_lighter_meals"]
    assert memory_policy["dimension_outcomes"] == [
        {
            "dimension": "dining_preferences",
            "winner_source": "memory",
            "winner_memory_key": "spouse_lighter_meals",
            "winner_tier": "advisory",
            "effective_values": ["lighter_options"],
            "suppressed_memory_keys": [],
        }
    ]
    assert memory_policy["memory_decisions"] == [
        {
            "memory_key": "spouse_lighter_meals",
            "dimension": "dining_preferences",
            "normalized_value": "lighter_options",
            "confidence": "0.7000",
            "tier": "advisory",
            "expired": False,
            "outcome": "applied_advisory",
        }
    ]
    assert memory_score.passed is True
    assert memory_score.details["observed_dimension_tiers"] == {
        "dining_preferences": "advisory",
    }


def test_benchmark_harness_records_memory_policy_for_expired_advisory_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("family_memory_expired_advisory_v1")
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
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_score = next(score for score in result.scores if score.name == "memory_governance")

    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["policy_version"] == "memory_query_policy_v1"
    assert memory_policy["advisory_memory_keys"] == ["activity_style"]
    assert memory_policy["downgraded_expired_keys"] == ["activity_style"]
    assert memory_policy["dimension_outcomes"] == [
        {
            "dimension": "activity_preferences",
            "winner_source": "memory",
            "winner_memory_key": "activity_style",
            "winner_tier": "advisory",
            "effective_values": ["child_friendly", "indoor"],
            "suppressed_memory_keys": [],
        }
    ]
    assert memory_policy["memory_decisions"] == [
        {
            "memory_key": "activity_style",
            "dimension": "activity_preferences",
            "normalized_value": "indoor",
            "confidence": "1.0000",
            "tier": "advisory",
            "expired": True,
            "outcome": "applied_advisory",
        }
    ]
    assert memory_score.passed is True
    assert memory_score.details["observed_dimension_tiers"] == {
        "activity_preferences": "advisory",
    }


def test_benchmark_harness_runs_solo_clarification_continuation_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("solo_clarification_continuation_v1")
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
    assert result.feedback_status == "completed"
    assert result.tool_event_count >= case.expected.min_tool_event_count
    assert result.action_count >= case.expected.min_action_count
    assert [score.name for score in result.scores].count("conversation_path") == 1
    assert [(step.mode, step.status, step.version_label) for step in result.conversation_trace] == [
        ("start", "awaiting_clarification", "v1"),
        ("clarify", "awaiting_confirmation", "v1"),
        ("confirm", "completed", "v1"),
    ]
    assert result.conversation_turn_types == [
        "user_request",
        "assistant_clarification_request",
        "user_clarification_reply",
        "assistant_plan_options",
    ]
    trace_run_ids = [step.run_id for step in result.conversation_trace if step.run_id is not None]
    assert len(trace_run_ids) == 3
    assert len({*trace_run_ids}) == 2
    assert result.report_path is not None

    report_payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report_payload["conversation_trace"] == [
        {
            "mode": "start",
            "source_run_id": None,
            "run_id": str(result.conversation_trace[0].run_id),
            "status": "awaiting_clarification",
            "version_label": "v1",
        },
        {
            "mode": "clarify",
            "source_run_id": str(result.conversation_trace[1].source_run_id),
            "run_id": str(result.conversation_trace[1].run_id),
            "status": "awaiting_confirmation",
            "version_label": "v1",
        },
        {
            "mode": "confirm",
            "source_run_id": str(result.conversation_trace[2].source_run_id),
            "run_id": str(result.conversation_trace[2].run_id),
            "status": "completed",
            "version_label": "v1",
        },
    ]
    assert report_payload["conversation_turn_types"] == result.conversation_turn_types
    serialized_report = json.dumps(report_payload, sort_keys=True)
    assert "session_id" not in serialized_report
    assert "payload_json" not in serialized_report
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized_report


def test_benchmark_harness_runs_family_replan_version_continuation_case(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("family_replan_version_continuation_v1")
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
    assert result.feedback_status == "completed"
    assert result.tool_event_count >= case.expected.min_tool_event_count
    assert result.action_count >= case.expected.min_action_count
    assert [score.name for score in result.scores].count("conversation_path") == 1
    assert [(step.mode, step.status, step.version_label) for step in result.conversation_trace] == [
        ("start", "awaiting_confirmation", "v1"),
        ("replan", "awaiting_confirmation", "v2"),
        ("confirm", "completed", "v2"),
    ]
    assert result.conversation_turn_types == [
        "user_request",
        "assistant_plan_options",
        "user_follow_up",
        "assistant_replan_options",
    ]
    trace_run_ids = [step.run_id for step in result.conversation_trace if step.run_id is not None]
    assert len(trace_run_ids) == 3
    assert len({*trace_run_ids}) == 2
    assert result.report_path is not None

    report_payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report_payload["conversation_trace"] == [
        {
            "mode": "start",
            "source_run_id": None,
            "run_id": str(result.conversation_trace[0].run_id),
            "status": "awaiting_confirmation",
            "version_label": "v1",
        },
        {
            "mode": "replan",
            "source_run_id": str(result.conversation_trace[1].source_run_id),
            "run_id": str(result.conversation_trace[1].run_id),
            "status": "awaiting_confirmation",
            "version_label": "v2",
        },
        {
            "mode": "confirm",
            "source_run_id": str(result.conversation_trace[2].source_run_id),
            "run_id": str(result.conversation_trace[2].run_id),
            "status": "completed",
            "version_label": "v2",
        },
    ]
    assert report_payload["conversation_turn_types"] == result.conversation_turn_types
    serialized_report = json.dumps(report_payload, sort_keys=True)
    assert "session_id" not in serialized_report
    assert "payload_json" not in serialized_report
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized_report


@pytest.mark.parametrize(
    (
        "suite_id",
        "expected_case_ids",
        "expected_case_count",
        "tool_profile_counts",
        "scenario_counts",
        "failure_mode_counts",
        "constraint_tag_counts",
    ),
    [
        (
            "baseline",
            BASELINE_CASE_IDS,
            6,
            {"mock_world": 6},
            BASELINE_SCENARIO_BUCKET_COUNTS,
            BASELINE_FAILURE_MODE_COUNTS,
            BASELINE_CONSTRAINT_TAG_COUNTS,
        ),
        (
            "expanded",
            EXPANDED_CASE_IDS,
            4,
            EXPANDED_TOOL_PROFILE_COUNTS,
            EXPANDED_SCENARIO_BUCKET_COUNTS,
            EXPANDED_FAILURE_MODE_COUNTS,
            EXPANDED_CONSTRAINT_TAG_COUNTS,
        ),
        (
            "recovery_focused",
            RECOVERY_CASE_IDS,
            3,
            RECOVERY_TOOL_PROFILE_COUNTS,
            RECOVERY_SCENARIO_BUCKET_COUNTS,
            RECOVERY_FAILURE_MODE_COUNTS,
            RECOVERY_CONSTRAINT_TAG_COUNTS,
        ),
        (
            "memory_governance",
            MEMORY_GOVERNANCE_CASE_IDS,
            3,
            MEMORY_GOVERNANCE_TOOL_PROFILE_COUNTS,
            MEMORY_GOVERNANCE_SCENARIO_BUCKET_COUNTS,
            MEMORY_GOVERNANCE_FAILURE_MODE_COUNTS,
            MEMORY_GOVERNANCE_CONSTRAINT_TAG_COUNTS,
        ),
        (
            "conversation_continuations",
            CONVERSATION_CONTINUATION_CASE_IDS,
            2,
            CONVERSATION_CONTINUATION_TOOL_PROFILE_COUNTS,
            CONVERSATION_CONTINUATION_SCENARIO_BUCKET_COUNTS,
            CONVERSATION_CONTINUATION_FAILURE_MODE_COUNTS,
            CONVERSATION_CONTINUATION_CONSTRAINT_TAG_COUNTS,
        ),
        (
            "release_gate_v1",
            RELEASE_GATE_V1_CASE_IDS,
            15,
            RELEASE_GATE_V1_TOOL_PROFILE_COUNTS,
            RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS,
            RELEASE_GATE_V1_FAILURE_MODE_COUNTS,
            RELEASE_GATE_V1_CONSTRAINT_TAG_COUNTS,
        ),
    ],
)
def test_benchmark_harness_runs_named_mock_world_suite(
    suite_id: str,
    expected_case_ids: set[str],
    expected_case_count: int,
    tool_profile_counts: dict[str, int],
    scenario_counts: dict[str, int],
    failure_mode_counts: dict[str, int],
    constraint_tag_counts: dict[str, int],
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    report = harness.run_suite(suite_id)

    assert {result.case_id for result in report.case_results} == expected_case_ids
    assert len(report.case_results) == expected_case_count
    assert report.run_status == "passed"
    assert report.passed_count == expected_case_count
    assert report.failed_count == 0
    assert report.error_count == 0
    assert report.report_path is not None
    assert report.report_path.endswith(f"suite-{suite_id}-run-report.json")
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.suite_id == suite_id
    assert report.benchmark_summary.suite_title is not None
    assert report.benchmark_summary.matrix_summary is not None
    assert report.benchmark_summary.matrix_summary.tool_profile_counts == tool_profile_counts
    assert report.benchmark_summary.outcome_rollup is not None
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes,
        scenario_counts,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.constraint_tag_outcomes,
        constraint_tag_counts,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.failure_mode_outcomes,
        failure_mode_counts,
    )

    suite_payload = json.loads(Path(report.report_path).read_text(encoding="utf-8"))
    assert suite_payload["benchmark_summary"]["suite_id"] == suite_id
    assert suite_payload["benchmark_summary"]["suite_title"]
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == tool_profile_counts
    assert suite_payload["benchmark_summary"]["outcome_rollup"]["schema_version"] == (
        "weekendpilot_benchmark_outcome_rollup_v1"
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["scenario_bucket_outcomes"],
        scenario_counts,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["constraint_tag_outcomes"],
        constraint_tag_counts,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["failure_mode_outcomes"],
        failure_mode_counts,
    )
    serialized_suite = json.dumps(suite_payload, sort_keys=True)
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized_suite


def test_benchmark_harness_runs_release_gate_v1_suite(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    report = harness.run_suite("release_gate_v1")

    assert {result.case_id for result in report.case_results} == RELEASE_GATE_V1_CASE_IDS
    assert len(report.case_results) == 15
    assert report.run_status == "passed"
    assert report.passed_count == 15
    assert report.failed_count == 0
    assert report.error_count == 0
    assert report.report_path is not None
    assert report.report_path.endswith("suite-release_gate_v1-run-report.json")
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.suite_id == "release_gate_v1"
    assert report.benchmark_summary.matrix_summary is not None
    assert report.benchmark_summary.matrix_summary.scenario_bucket_counts == RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS
    assert report.benchmark_summary.matrix_summary.level_counts == RELEASE_GATE_V1_LEVEL_COUNTS
    assert report.benchmark_summary.matrix_summary.tool_profile_counts == RELEASE_GATE_V1_TOOL_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.world_profile_counts == RELEASE_GATE_V1_WORLD_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.failure_mode_counts == RELEASE_GATE_V1_FAILURE_MODE_COUNTS
    assert report.benchmark_summary.matrix_summary.tag_counts == RELEASE_GATE_V1_TAG_COUNTS
    assert report.benchmark_summary.outcome_rollup is not None
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes,
        RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.constraint_tag_outcomes,
        RELEASE_GATE_V1_CONSTRAINT_TAG_COUNTS,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.failure_mode_outcomes,
        RELEASE_GATE_V1_FAILURE_MODE_COUNTS,
    )

    suite_payload = json.loads(Path(report.report_path).read_text(encoding="utf-8"))
    assert suite_payload["benchmark_summary"]["suite_id"] == "release_gate_v1"
    assert suite_payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == (
        RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["level_counts"] == RELEASE_GATE_V1_LEVEL_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == (
        RELEASE_GATE_V1_TOOL_PROFILE_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["world_profile_counts"] == (
        RELEASE_GATE_V1_WORLD_PROFILE_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == (
        RELEASE_GATE_V1_FAILURE_MODE_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tag_counts"] == RELEASE_GATE_V1_TAG_COUNTS
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["scenario_bucket_outcomes"],
        RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["constraint_tag_outcomes"],
        RELEASE_GATE_V1_CONSTRAINT_TAG_COUNTS,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["failure_mode_outcomes"],
        RELEASE_GATE_V1_FAILURE_MODE_COUNTS,
    )


def test_benchmark_harness_runs_default_mock_world_suite(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    report = harness.run_suite("default")

    assert {result.case_id for result in report.case_results} == DEFAULT_CASE_IDS
    assert len(report.case_results) == 10
    assert report.run_status == "passed"
    assert report.passed_count == 10
    assert report.failed_count == 0
    assert report.error_count == 0
    assert report.report_path is not None
    assert report.report_path.endswith("suite-default-run-report.json")
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.suite_id == "default"
    assert report.benchmark_summary.run_status == "passed"
    assert report.benchmark_summary.case_count == 10
    assert report.benchmark_summary.matrix_summary is not None
    assert report.benchmark_summary.matrix_summary.scenario_bucket_counts == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert report.benchmark_summary.matrix_summary.level_counts == DEFAULT_LEVEL_COUNTS
    assert report.benchmark_summary.matrix_summary.tool_profile_counts == DEFAULT_TOOL_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.world_profile_counts == DEFAULT_WORLD_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.failure_mode_counts == DEFAULT_FAILURE_MODE_COUNTS
    assert report.benchmark_summary.matrix_summary.tag_counts == DEFAULT_TAG_COUNTS
    assert report.benchmark_summary.outcome_rollup is not None
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes,
        DEFAULT_SCENARIO_BUCKET_COUNTS,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.constraint_tag_outcomes,
        DEFAULT_CONSTRAINT_TAG_COUNTS,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.failure_mode_outcomes,
        DEFAULT_FAILURE_MODE_COUNTS,
    )
    assert report.benchmark_timing_summary is not None
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
    assert suite_payload["benchmark_summary"]["suite_id"] == "default"
    assert suite_payload["benchmark_summary"]["run_status"] == "passed"
    assert suite_payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["level_counts"] == DEFAULT_LEVEL_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == DEFAULT_TOOL_PROFILE_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["world_profile_counts"] == DEFAULT_WORLD_PROFILE_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == DEFAULT_FAILURE_MODE_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tag_counts"] == DEFAULT_TAG_COUNTS
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["scenario_bucket_outcomes"],
        DEFAULT_SCENARIO_BUCKET_COUNTS,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["constraint_tag_outcomes"],
        DEFAULT_CONSTRAINT_TAG_COUNTS,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["failure_mode_outcomes"],
        DEFAULT_FAILURE_MODE_COUNTS,
    )
    assert suite_payload["benchmark_timing_summary"]["schema_version"] == "benchmark_timing_summary_v1"
    assert suite_payload["benchmark_timing_summary"]["case_count"] == 10
    assert suite_payload["benchmark_timing_summary"]["overall_total_duration_ms"]["sample_count"] == 10
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
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    report = harness.run_suite("all_registered")

    assert len(report.case_results) == 17
    assert report.run_status == "passed"
    assert report.passed_count == 17
    assert report.failed_count == 0
    assert report.error_count == 0
    assert report.report_path is not None
    assert report.report_path.endswith("suite-all_registered-run-report.json")
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.suite_id == "all_registered"
    assert report.benchmark_summary.matrix_summary is not None
    assert report.benchmark_summary.matrix_summary.scenario_bucket_counts == ALL_REGISTERED_SCENARIO_BUCKET_COUNTS
    assert report.benchmark_summary.matrix_summary.level_counts == ALL_REGISTERED_LEVEL_COUNTS
    assert report.benchmark_summary.matrix_summary.tool_profile_counts == ALL_REGISTERED_TOOL_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.world_profile_counts == ALL_REGISTERED_WORLD_PROFILE_COUNTS
    assert report.benchmark_summary.matrix_summary.failure_mode_counts == ALL_REGISTERED_FAILURE_MODE_COUNTS
    assert report.benchmark_summary.matrix_summary.tag_counts == ALL_REGISTERED_TAG_COUNTS
    assert report.benchmark_summary.outcome_rollup is not None
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes,
        ALL_REGISTERED_SCENARIO_BUCKET_COUNTS,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.constraint_tag_outcomes,
        ALL_REGISTERED_CONSTRAINT_TAG_COUNTS,
    )
    _assert_rollup_counts(
        report.benchmark_summary.outcome_rollup.failure_mode_outcomes,
        ALL_REGISTERED_FAILURE_MODE_COUNTS,
    )

    suite_payload = json.loads(Path(report.report_path).read_text(encoding="utf-8"))
    assert suite_payload["benchmark_summary"]["suite_id"] == "all_registered"
    assert suite_payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == (
        ALL_REGISTERED_SCENARIO_BUCKET_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["level_counts"] == ALL_REGISTERED_LEVEL_COUNTS
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == (
        ALL_REGISTERED_TOOL_PROFILE_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["world_profile_counts"] == (
        ALL_REGISTERED_WORLD_PROFILE_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == (
        ALL_REGISTERED_FAILURE_MODE_COUNTS
    )
    assert suite_payload["benchmark_summary"]["matrix_summary"]["tag_counts"] == ALL_REGISTERED_TAG_COUNTS
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["scenario_bucket_outcomes"],
        ALL_REGISTERED_SCENARIO_BUCKET_COUNTS,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["constraint_tag_outcomes"],
        ALL_REGISTERED_CONSTRAINT_TAG_COUNTS,
    )
    _assert_rollup_counts(
        suite_payload["benchmark_summary"]["outcome_rollup"]["failure_mode_outcomes"],
        ALL_REGISTERED_FAILURE_MODE_COUNTS,
    )


def test_benchmark_harness_runs_route_failure_case_as_expected_safe_stop(
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case("family_route_failure_v1")
    assert [item.case_id for item in load_failure_benchmark_cases()] == [
        "family_route_failure_v1",
        "family_route_and_dining_unavailable_v1",
        "rainy_day_ticket_sold_out_v1",
    ]
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
    assert result.failure_chain_summary is not None
    assert result.failure_chain_summary.profile_id == "route_unavailable_v0"
    assert result.failure_chain_summary.injected_effects == ["check_route:route_infeasible:failed"]
    assert result.failure_chain_summary.recovery_actions == ["stop_safely"]
    assert result.failure_chain_summary.bounded is True

    report_payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report_payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
    assert report_payload["run_summary"]["workflow_status"] == "failed"
    assert report_payload["workflow_timing_summary"]["schema_version"] == "workflow_timing_summary_v1"
    assert report_payload["failure_chain_summary"]["profile_id"] == "route_unavailable_v0"
    serialized_report = json.dumps(report_payload, sort_keys=True)
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized_report


@pytest.mark.parametrize(
    ("case_id", "expected_profile", "expected_effects"),
    [
        (
            "family_route_and_dining_unavailable_v1",
            "route_and_dining_unavailable_v0",
            [
                "check_queue:dining_unavailable:succeeded",
                "check_table_availability:dining_unavailable:succeeded",
                "check_route:route_infeasible:failed",
            ],
        ),
        (
            "rainy_day_ticket_sold_out_v1",
            "ticket_sold_out_and_bad_weather_v0",
            [
                "check_weather:bad_weather:succeeded",
                "check_ticket_availability:ticket_sold_out:succeeded",
            ],
        ),
    ],
)
def test_benchmark_harness_runs_composite_failure_case_as_bounded_safe_stop(
    case_id: str,
    expected_profile: str,
    expected_effects: list[str],
    db_session: Session,
    redis_runtime,
    harness_paths,
) -> None:
    cache, rate_limiter = redis_runtime
    trace_path, report_dir = harness_paths
    case = load_benchmark_case(case_id)
    harness = BenchmarkHarness(
        db_session,
        cache,
        rate_limiter,
        report_dir=report_dir,
        trace_buffer_path=trace_path,
    )

    result = harness.run_case(case)

    assert result.status == "passed"
    assert result.workflow_status == "failed"
    assert result.action_count == 0
    assert result.failure_chain_summary is not None
    assert result.failure_chain_summary.profile_id == expected_profile
    assert result.failure_chain_summary.injected_effects == expected_effects
    assert result.failure_chain_summary.recovery_actions == ["stop_safely"]
    assert result.failure_chain_summary.attempt_count == 1
    assert result.failure_chain_summary.max_attempts == 2
    assert result.failure_chain_summary.bounded is True

    action_count = db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == result.run_id)
    )
    assert action_count == 0

    tool_events = db_session.scalars(select(ToolEvent).where(ToolEvent.run_id == result.run_id)).all()
    injected_events = [
        event
        for event in tool_events
        if isinstance(event.error_json, dict)
        and event.error_json.get("error_type") in {"failure_injected", "failure_injected_response"}
    ]
    assert len(injected_events) >= len(expected_effects)

    report_payload = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report_payload["failure_chain_summary"]["profile_id"] == expected_profile
    assert report_payload["failure_chain_summary"]["injected_effects"] == expected_effects
    assert report_payload["failure_chain_summary"]["recovery_actions"] == ["stop_safely"]


def _assert_rollup_counts(bucket_map, expected_case_counts: dict[str, int]) -> None:
    assert set(bucket_map) == set(expected_case_counts)
    for bucket, expected_count in expected_case_counts.items():
        payload = bucket_map[bucket]
        if isinstance(payload, dict):
            case_count = payload["case_count"]
            passed_count = payload["passed_count"]
            failed_count = payload["failed_count"]
            error_count = payload["error_count"]
            pass_rate = payload["pass_rate"]
        else:
            case_count = payload.case_count
            passed_count = payload.passed_count
            failed_count = payload.failed_count
            error_count = payload.error_count
            pass_rate = payload.pass_rate

        assert case_count == expected_count
        assert passed_count == expected_count
        assert failed_count == 0
        assert error_count == 0
        assert pass_rate == 1.0
