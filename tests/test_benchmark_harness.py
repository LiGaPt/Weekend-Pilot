from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.benchmark import (
    BenchmarkHarness,
    load_benchmark_case,
    load_benchmark_suite,
    load_default_benchmark_cases,
    load_failure_benchmark_cases,
)
from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.failure_chain import build_failure_chain_summary
import backend.app.benchmark.graders as benchmark_graders
import backend.app.benchmark.harness as benchmark_harness
from backend.app.benchmark.graders import (
    combine_scores,
    grade_execution_safety,
    grade_failure_injection,
    grade_feedback,
    grade_recovery_expectation,
    grade_trajectory,
    grade_workflow_path,
)
from backend.app.benchmark.reporting import write_case_report, write_run_report
from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkExpectedOutcome,
    BenchmarkRunReport,
    BenchmarkScore,
    BenchmarkSuiteDescription,
    BenchmarkSummary,
)
from backend.app.benchmark.matrix import build_case_matrix_summary
from backend.app.benchmark.timing import summarize_benchmark_timing
from backend.app.workflow.timing import WorkflowStageTimingEntry, WorkflowTimingSummary
from backend.app.workflow.state import V1_WORKFLOW_NODE_NAMES


def _taxonomy_payload(
    *,
    scenario_bucket: str = "unknown",
    level: str = "L1",
    tags: list[str] | None = None,
    failure_mode: str | None = None,
) -> dict[str, object]:
    return {
        "suite": "locallife_bench_v1",
        "scenario_bucket": scenario_bucket,
        "level": level,
        "tags": tags or ["baseline"],
        "failure_mode": failure_mode,
    }


REQUIRED_WORKFLOW_NODES = V1_WORKFLOW_NODE_NAMES
REQUIRED_AGENT_ROLES = (
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
)
DEFAULT_CASE_IDS = (
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
)
FAILURE_CASE_IDS = (
    "family_route_failure_v1",
    "family_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1",
)
REQUIRED_CASE_TOOL_NAMES = {
    "search_poi",
    "check_weather",
    "get_poi_detail",
    "check_opening_hours",
    "check_queue",
    "check_table_availability",
    "check_ticket_availability",
    "check_route",
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
DEFAULT_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 5,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 1,
}
DEFAULT_FAILURE_MODE_COUNTS = {"none": 10}
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
ALL_REGISTERED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 7,
    "friends": 1,
    "mixed": 2,
    "solo": 1,
    "unknown": 1,
}
ALL_REGISTERED_LEVEL_COUNTS = {"L1": 3, "L2": 8, "L5": 2}
ALL_REGISTERED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 7,
    "friends_gathering": 1,
    "rainy_day_fallback": 2,
    "solo_afternoon": 1,
}
ALL_REGISTERED_FAILURE_MODE_COUNTS = {
    "none": 10,
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
    "child_friendly": 7,
    "citywalk": 2,
    "composite_failure": 2,
    "date_friendly": 1,
    "dining_unavailable": 1,
    "failure_injected": 3,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 3,
    "light_activity": 1,
    "light_meal": 6,
    "memory_override": 1,
    "outdoor_activity": 2,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 2,
    "route_failure": 2,
    "ticket_sold_out": 1,
}
EXPECTED_TAXONOMY_BY_CASE = {
    "family_afternoon_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L1",
        tags=["baseline", "child_friendly", "light_meal"],
    ),
    "family_indoor_light_meal_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "indoor_activity", "light_meal"],
    ),
    "family_outdoor_quick_dinner_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "outdoor_activity", "quick_dinner"],
    ),
    "family_memory_override_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "indoor_activity", "light_meal", "memory_override"],
    ),
    "family_citywalk_addon_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L1",
        tags=["addon_optional", "child_friendly", "citywalk"],
    ),
    "solo_afternoon_v1": _taxonomy_payload(
        scenario_bucket="solo",
        level="L1",
        tags=["baseline", "light_activity", "light_meal"],
    ),
    "couple_afternoon_v1": _taxonomy_payload(
        scenario_bucket="couple",
        level="L2",
        tags=["citywalk", "date_friendly", "light_meal"],
    ),
    "friends_gathering_v1": _taxonomy_payload(
        scenario_bucket="friends",
        level="L2",
        tags=["casual_dining", "friends_group", "outdoor_activity"],
    ),
    "rainy_day_fallback_v1": _taxonomy_payload(
        scenario_bucket="mixed",
        level="L2",
        tags=["fallback", "indoor_activity", "rainy_day"],
    ),
    "budget_lite_v1": _taxonomy_payload(
        scenario_bucket="unknown",
        level="L2",
        tags=["budget_limited", "free_activity", "quick_meal"],
    ),
    "family_route_failure_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "failure_injected", "light_meal", "route_failure"],
        failure_mode="route_unavailable",
    ),
    "family_route_and_dining_unavailable_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L5",
        tags=[
            "child_friendly",
            "composite_failure",
            "dining_unavailable",
            "failure_injected",
            "route_failure",
        ],
        failure_mode="route_and_dining_unavailable",
    ),
    "rainy_day_ticket_sold_out_v1": _taxonomy_payload(
        scenario_bucket="mixed",
        level="L5",
        tags=[
            "bad_weather",
            "composite_failure",
            "failure_injected",
            "rainy_day",
            "ticket_sold_out",
        ],
        failure_mode="ticket_sold_out_and_bad_weather",
    ),
}


def test_default_fixtures_load_as_ordered_benchmark_cases() -> None:
    cases = load_default_benchmark_cases()

    assert [case.case_id for case in cases] == list(DEFAULT_CASE_IDS)
    assert len(cases) == 10
    assert all(isinstance(case, BenchmarkCase) for case in cases)


def test_failure_fixtures_are_loadable_but_not_default() -> None:
    default_cases = load_default_benchmark_cases()
    failure_cases = load_failure_benchmark_cases()

    assert [case.case_id for case in failure_cases] == list(FAILURE_CASE_IDS)
    assert {case.case_id for case in default_cases}.isdisjoint(FAILURE_CASE_IDS)

    case = load_benchmark_case("family_route_failure_v1")
    assert case.case_id == "family_route_failure_v1"
    assert case.failure_profile == "route_unavailable_v0"
    assert case.expected.expected_workflow_status == "failed"
    assert case.expected.expected_error_type == "recovery_stopped"
    assert case.expected.expected_recovery_action == "stop_safely"
    assert case.expected.min_injected_failure_count == 1

    composite_case = load_benchmark_case("family_route_and_dining_unavailable_v1")
    assert composite_case.failure_profile == "route_and_dining_unavailable_v0"
    assert composite_case.expected.min_injected_failure_count == 3
    assert composite_case.expected.expected_workflow_status == "failed"
    assert composite_case.expected.expected_execution_status is None
    assert composite_case.expected.expected_feedback_status is None

    rainy_case = load_benchmark_case("rainy_day_ticket_sold_out_v1")
    assert rainy_case.failure_profile == "ticket_sold_out_and_bad_weather_v0"
    assert rainy_case.expected.min_injected_failure_count == 3
    assert rainy_case.expected.expected_recovery_action == "stop_safely"


def test_default_fixtures_can_be_loaded_individually() -> None:
    for case_id in DEFAULT_CASE_IDS:
        case = load_benchmark_case(case_id)

        assert isinstance(case, BenchmarkCase)
        assert case.case_id == case_id


def test_default_and_failure_fixtures_expose_expected_taxonomy() -> None:
    case_ids = [*DEFAULT_CASE_IDS, *FAILURE_CASE_IDS]

    for case_id in case_ids:
        case = load_benchmark_case(case_id)

        assert case.taxonomy.model_dump(mode="json") == EXPECTED_TAXONOMY_BY_CASE[case_id]


def test_default_fixtures_use_supported_mock_world_profiles() -> None:
    cases = load_default_benchmark_cases()

    assert {case.tool_profile for case in cases} == {"mock_world"}
    assert {case.world_profile for case in cases} == {
        "budget_lite",
        "couple_afternoon",
        "family_afternoon",
        "friends_gathering",
        "rainy_day_fallback",
        "solo_afternoon",
    }


def test_default_case_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_default_benchmark_cases())

    assert summary.case_count == 10
    assert summary.scenario_bucket_counts == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert summary.level_counts == DEFAULT_LEVEL_COUNTS
    assert summary.world_profile_counts == DEFAULT_WORLD_PROFILE_COUNTS
    assert summary.failure_mode_counts == DEFAULT_FAILURE_MODE_COUNTS
    assert summary.tag_counts == DEFAULT_TAG_COUNTS


def test_all_registered_case_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_benchmark_suite("all_registered"))

    assert summary.case_count == 13
    assert summary.scenario_bucket_counts == ALL_REGISTERED_SCENARIO_BUCKET_COUNTS
    assert summary.level_counts == ALL_REGISTERED_LEVEL_COUNTS
    assert summary.world_profile_counts == ALL_REGISTERED_WORLD_PROFILE_COUNTS
    assert summary.failure_mode_counts == ALL_REGISTERED_FAILURE_MODE_COUNTS
    assert summary.tag_counts == ALL_REGISTERED_TAG_COUNTS


def test_default_fixtures_include_v1_metadata_and_expected_tools() -> None:
    cases = load_default_benchmark_cases()

    for case in cases:
        assert case.taxonomy.suite == "locallife_bench_v1"
        assert case.taxonomy.level in {"L1", "L2"}
        assert "suite" not in case.metadata
        assert "level" not in case.metadata
        assert isinstance(case.metadata["focus"], str)
        assert case.metadata["focus"]
        assert set(case.expected.required_tool_names) == REQUIRED_CASE_TOOL_NAMES
        assert case.expected.expected_execution_status == "succeeded"
        assert case.expected.expected_feedback_status == "completed"


def test_build_failure_chain_summary_deduplicates_effects_and_marks_bounded() -> None:
    summary = build_failure_chain_summary(
        failure_profile="route_and_dining_unavailable_v0",
        tool_events=[
            SimpleNamespace(
                tool_name="check_queue",
                status="succeeded",
                error_json={
                    "error_type": "failure_injected_response",
                    "details": {"effect_type": "dining_unavailable"},
                },
            ),
            SimpleNamespace(
                tool_name="check_queue",
                status="succeeded",
                error_json={
                    "error_type": "failure_injected_response",
                    "details": {"effect_type": "dining_unavailable"},
                },
            ),
            SimpleNamespace(
                tool_name="check_table_availability",
                status="succeeded",
                error_json={
                    "error_type": "failure_injected_response",
                    "details": {"effect_type": "dining_unavailable"},
                },
            ),
            SimpleNamespace(
                tool_name="check_route",
                status="failed",
                error_json={
                    "error_type": "failure_injected",
                    "details": {"effect_type": "route_infeasible"},
                },
            ),
        ],
        run_metadata={
            "workflow": {
                "recovery": {
                    "attempt_count": 1,
                    "max_attempts": 2,
                    "attempts": [
                        {"recovery_action": "stop_safely", "status": "stopped"},
                    ],
                }
            }
        },
        workflow_status="failed",
    )

    assert summary.profile_id == "route_and_dining_unavailable_v0"
    assert summary.injected_effects == [
        "check_queue:dining_unavailable:succeeded",
        "check_table_availability:dining_unavailable:succeeded",
        "check_route:route_infeasible:failed",
    ]
    assert summary.recovery_actions == ["stop_safely"]
    assert summary.attempt_count == 1
    assert summary.max_attempts == 2
    assert summary.bounded is True
    assert summary.terminal_workflow_status == "failed"


@pytest.mark.parametrize(
    ("case_id", "world_profile", "scenario_bucket", "tags", "focus"),
    [
        (
            "solo_afternoon_v1",
            "solo_afternoon",
            "solo",
            ["baseline", "light_activity", "light_meal"],
            "baseline_solo_afternoon",
        ),
        (
            "couple_afternoon_v1",
            "couple_afternoon",
            "couple",
            ["citywalk", "date_friendly", "light_meal"],
            "baseline_couple_citywalk",
        ),
        (
            "friends_gathering_v1",
            "friends_gathering",
            "friends",
            ["casual_dining", "friends_group", "outdoor_activity"],
            "friends_group_hangout",
        ),
        (
            "rainy_day_fallback_v1",
            "rainy_day_fallback",
            "mixed",
            ["fallback", "indoor_activity", "rainy_day"],
            "rainy_day_indoor_fallback",
        ),
        (
            "budget_lite_v1",
            "budget_lite",
            "unknown",
            ["budget_limited", "free_activity", "quick_meal"],
            "budget_lite_low_cost_route",
        ),
    ],
)
def test_fixture_uses_expected_profile_taxonomy_and_focus(
    case_id: str,
    world_profile: str,
    scenario_bucket: str,
    tags: list[str],
    focus: str,
) -> None:
    case = load_benchmark_case(case_id)

    assert case.tool_profile == "mock_world"
    assert case.world_profile == world_profile
    assert case.taxonomy.scenario_bucket == scenario_bucket
    assert case.taxonomy.tags == tags
    assert case.metadata["focus"] == focus


def test_unknown_case_raises_benchmark_harness_error() -> None:
    with pytest.raises(BenchmarkHarnessError):
        load_benchmark_case("missing_case")


def test_benchmark_case_rejects_duplicate_and_malformed_taxonomy_tags() -> None:
    payload = {
        "case_id": "case",
        "title": "Case",
        "user_input": "Plan an afternoon.",
        "expected": {
            "required_tool_names": ["search_poi"],
            "min_tool_event_count": 1,
            "min_action_count": 1,
        },
        "taxonomy": _taxonomy_payload(
            scenario_bucket="unknown",
            level="L1",
            tags=["baseline", "baseline"],
        ),
    }
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(payload)

    payload["taxonomy"] = _taxonomy_payload(
        scenario_bucket="unknown",
        level="L1",
        tags=["bad-tag"],
    )
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(payload)


def test_trajectory_grader_passes_when_required_tools_are_present() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi", "check_route"],
            min_tool_event_count=2,
            min_action_count=1,
        ),
    )
    tool_events = [
        type("ToolEventStub", (), {"tool_name": "search_poi"})(),
        type("ToolEventStub", (), {"tool_name": "check_route"})(),
    ]

    score = grade_trajectory(case, tool_events)

    assert score.passed is True
    assert score.score == 1.0


def test_trajectory_grader_fails_when_required_tool_is_missing() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi", "check_route"],
            min_tool_event_count=2,
            min_action_count=1,
        ),
    )
    tool_events = [type("ToolEventStub", (), {"tool_name": "search_poi"})()]

    score = grade_trajectory(case, tool_events)

    assert score.passed is False
    assert score.score == 0.0
    assert "check_route" in score.reason


def test_combine_scores_returns_failed_status_when_one_score_fails() -> None:
    status, overall, reasons = combine_scores(
        [
            BenchmarkScore(name="one", score=1.0, passed=True, reason="ok"),
            BenchmarkScore(name="two", score=0.0, passed=False, reason="missing"),
        ]
    )

    assert status == "failed"
    assert overall == 0.5
    assert reasons == ["missing"]


def test_workflow_path_grader_passes_for_completed_required_nodes() -> None:
    grader = getattr(benchmark_graders, "grade_workflow_path", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(status="completed", node_history=list(REQUIRED_WORKFLOW_NODES))

    score = grader(workflow_result)

    assert score.name == "workflow_path"
    assert score.passed is True
    assert score.score == 1.0


def test_workflow_path_grader_passes_for_expected_safe_stop_failure() -> None:
    case = BenchmarkCase(
        case_id="family_route_failure_v1",
        title="Route failure",
        user_input="Plan an afternoon.",
        failure_profile="route_unavailable_v0",
        taxonomy=_taxonomy_payload(failure_mode="route_unavailable"),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_workflow_status="failed",
            expected_execution_status=None,
            expected_feedback_status=None,
            expected_error_type="recovery_stopped",
        ),
    )
    workflow_result = SimpleNamespace(
        status="failed",
        error_json={"error_type": "recovery_stopped"},
        node_history=["initialize", "apply_recovery"],
    )

    score = grade_workflow_path(workflow_result, case)

    assert score.name == "workflow_path"
    assert score.passed is True
    assert score.score == 1.0
    assert score.details["expected_workflow_status"] == "failed"


def test_workflow_path_grader_fails_when_required_node_missing() -> None:
    grader = getattr(benchmark_graders, "grade_workflow_path", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(status="completed", node_history=["initialize"])

    score = grader(workflow_result)

    assert score.name == "workflow_path"
    assert score.passed is False
    assert "generate_summary_message" in score.reason


def test_agent_coverage_grader_passes_for_all_required_roles() -> None:
    grader = getattr(benchmark_graders, "grade_agent_coverage", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(
        agent_results=[SimpleNamespace(role=role) for role in REQUIRED_AGENT_ROLES]
    )

    score = grader(workflow_result)

    assert score.name == "agent_coverage"
    assert score.passed is True
    assert score.score == 1.0


def test_agent_coverage_grader_fails_when_role_missing() -> None:
    grader = getattr(benchmark_graders, "grade_agent_coverage", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(agent_results=[SimpleNamespace(role="supervisor")])

    score = grader(workflow_result)

    assert score.name == "agent_coverage"
    assert score.passed is False
    assert "validator_recovery" in score.reason


def test_execution_safety_grader_accepts_persisted_execution_metadata_dict() -> None:
    case = _benchmark_case()
    execution = {
        "status": "succeeded",
        "action_results": [
            {"tool_name": "reserve_restaurant"},
            {"tool_name": "book_ticket"},
        ],
    }

    score = grade_execution_safety(case, execution)

    assert score.passed is True
    assert score.details["execution_status"] == "succeeded"
    assert score.details["write_tools"] == ["reserve_restaurant", "book_ticket"]


def test_execution_safety_grader_accepts_absent_execution_when_expected_is_none() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_execution_status=None,
        ),
    )

    score = grade_execution_safety(case, None)

    assert score.passed is True
    assert score.details["execution_status"] is None


def test_feedback_grader_accepts_persisted_feedback_metadata_dict() -> None:
    case = _benchmark_case()
    feedback = {
        "status": "completed",
        "headline": "安排已完成",
        "message": "安排已完成：2项操作已完成，0项需要处理。",
        "next_steps": ["按确认后的时间出发，出门前再看一眼天气和路况。"],
    }

    score = grade_feedback(case, feedback)

    assert score.passed is True
    assert score.details["feedback_status"] == "completed"


def test_feedback_grader_accepts_absent_feedback_when_expected_is_none() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_feedback_status=None,
        ),
    )

    score = grade_feedback(case, None)

    assert score.passed is True
    assert score.details["feedback_status"] is None


def test_failure_injection_grader_requires_injected_failures() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            min_injected_failure_count=1,
        ),
    )
    tool_events = [
        SimpleNamespace(
            tool_name="check_route",
            status="failed",
            error_json={
                "error_type": "failure_injected",
                "details": {"profile_id": "route_unavailable_v0"},
            },
        )
    ]

    score = grade_failure_injection(case, tool_events)

    assert score.passed is True
    assert score.details["injected_failure_count"] == 1


def test_recovery_expectation_grader_accepts_expected_recovery_action() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_recovery_action="stop_safely",
        ),
    )
    run_metadata = {
        "workflow": {
            "recovery": {
                "attempts": [
                    {
                        "recovery_action": "stop_safely",
                        "status": "stopped",
                    }
                ]
            }
        }
    }

    score = grade_recovery_expectation(case, run_metadata)

    assert score.passed is True
    assert score.details["observed_recovery_actions"] == ["stop_safely"]


def test_report_writer_creates_parent_directory_and_json_file() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="passed",
        scores=[],
        overall_score=1.0,
        tool_event_count=8,
        action_count=1,
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir / "nested"))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_path.name == "family_afternoon_v1.json"
        assert payload["case_id"] == "family_afternoon_v1"
        assert payload["report_path"] == str(report_path)
    finally:
        _cleanup_report_dir(report_dir)


def test_report_writer_output_excludes_raw_ids_and_sensitive_keys() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="failed",
        scores=[
            BenchmarkScore(
                name="safety",
                score=0.0,
                passed=False,
                reason="bad",
                details={
                    "action_id": "do-not-write",
                    "tool_event_id": "do-not-write",
                    "api_key": "do-not-write",
                    "token": "do-not-write",
                    "secret": "do-not-write",
                    "debug_trace": "do-not-write",
                },
            )
        ],
        overall_score=0.0,
        tool_event_count=1,
        action_count=1,
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        serialized = report_path.read_text(encoding="utf-8")
        assert "do-not-write" not in serialized
        assert "action_id" not in serialized
        assert "tool_event_id" not in serialized
        assert "api_key" not in serialized
        assert "token" not in serialized
        assert "secret" not in serialized
        assert "debug_trace" not in serialized
    finally:
        _cleanup_report_dir(report_dir)


def test_report_writer_includes_workflow_fields_and_agent_roles() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="passed",
        scores=[],
        overall_score=1.0,
        tool_event_count=8,
        action_count=1,
        workflow_status="completed",
        workflow_node_history=list(REQUIRED_WORKFLOW_NODES),
        agent_roles=list(REQUIRED_AGENT_ROLES),
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["workflow_status"] == "completed"
        assert payload["workflow_node_history"] == list(REQUIRED_WORKFLOW_NODES)
        assert payload["agent_roles"] == list(REQUIRED_AGENT_ROLES)
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_workflow_timing_summary() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="passed",
        scores=[],
        overall_score=1.0,
        tool_event_count=8,
        action_count=1,
        workflow_timing_summary=_workflow_timing_summary(
            total_duration_ms=120,
            stages=[
                WorkflowStageTimingEntry(
                    node_name="initialize",
                    attempt_count=1,
                    total_duration_ms=5,
                ),
                WorkflowStageTimingEntry(
                    node_name="execute_searches",
                    attempt_count=2,
                    total_duration_ms=40,
                ),
            ],
        ),
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["workflow_timing_summary"]["schema_version"] == "workflow_timing_summary_v1"
        assert payload["workflow_timing_summary"]["stages"][1]["attempt_count"] == 2
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_run_summary_envelope() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "family_afternoon_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "run_summary": {
                "schema_version": "weekendpilot_run_summary_v1",
                "run_id": str(uuid4()),
                "trace_id": "trace-1",
                "case_id": "family_afternoon_v1",
                "agent_version": "agent-v1",
                "prompt_version": "prompt-v1",
                "tool_profile": "mock_world",
                "world_profile": "family_afternoon",
                "failure_profile": None,
                "workflow_status": "completed",
                "selected_plan_id": str(uuid4()),
                "plan_status": "selected",
                "execution_status": "succeeded",
                "feedback_status": "completed",
                "tool_event_count": 8,
                "action_count": 1,
                "agent_roles": ["supervisor", "discovery"],
                "workflow_timing_summary": {
                    "schema_version": "workflow_timing_summary_v1",
                    "total_duration_ms": 120,
                    "stage_count": 1,
                    "stages": [
                        {
                            "node_name": "initialize",
                            "attempt_count": 1,
                            "total_duration_ms": 120,
                        }
                    ],
                },
                "error": None,
            },
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
        assert payload["run_summary"]["workflow_status"] == "completed"
        assert payload["run_summary"]["workflow_timing_summary"]["total_duration_ms"] == 120
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_taxonomy() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "solo_afternoon_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "taxonomy": _taxonomy_payload(
                scenario_bucket="solo",
                level="L1",
                tags=["baseline", "light_activity", "light_meal"],
            ),
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["taxonomy"]["suite"] == "locallife_bench_v1"
        assert payload["taxonomy"]["scenario_bucket"] == "solo"
        assert payload["taxonomy"]["tags"] == ["baseline", "light_activity", "light_meal"]
    finally:
        _cleanup_report_dir(report_dir)


def test_benchmark_timing_summary_uses_nearest_rank_percentiles_and_stage_order() -> None:
    results = [
        BenchmarkCaseResult(
            case_id=f"case-{index}",
            status="passed",
            scores=[],
            overall_score=1.0,
            tool_event_count=8,
            action_count=1,
            workflow_timing_summary=summary,
        )
        for index, summary in enumerate(
            [
                _workflow_timing_summary(
                    total_duration_ms=100,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="logical_planner_agent",
                            attempt_count=1,
                            total_duration_ms=20,
                        ),
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=30,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=120,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=35,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=140,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=2,
                            total_duration_ms=40,
                        ),
                        WorkflowStageTimingEntry(
                            node_name="logical_planner_agent",
                            attempt_count=1,
                            total_duration_ms=22,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=160,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="logical_planner_agent",
                            attempt_count=1,
                            total_duration_ms=24,
                        ),
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=45,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=300,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=60,
                        ),
                    ],
                ),
            ]
        )
    ]

    summary = summarize_benchmark_timing(results)

    assert summary.schema_version == "benchmark_timing_summary_v1"
    assert summary.case_count == 5
    assert summary.overall_total_duration_ms is not None
    assert summary.overall_total_duration_ms.sample_count == 5
    assert summary.overall_total_duration_ms.min_ms == 100
    assert summary.overall_total_duration_ms.p50_ms == 140
    assert summary.overall_total_duration_ms.p95_ms == 300
    assert summary.overall_total_duration_ms.p99_ms == 300
    assert summary.overall_total_duration_ms.max_ms == 300
    assert summary.overall_total_duration_ms.mean_ms == 164.0
    assert [entry.node_name for entry in summary.stages[:2]] == [
        "execute_searches",
        "logical_planner_agent",
    ]
    execute_searches = summary.stages[0]
    assert execute_searches.sample_count == 5
    assert execute_searches.retry_case_count == 1
    assert execute_searches.min_ms == 30
    assert execute_searches.p50_ms == 40
    assert execute_searches.p95_ms == 60
    assert execute_searches.p99_ms == 60
    assert execute_searches.max_ms == 60
    assert execute_searches.mean_ms == 42.0


def test_run_report_writer_creates_suite_report_with_timing_summary() -> None:
    result = BenchmarkRunReport(
        run_status="passed",
        case_results=[],
        passed_count=1,
        failed_count=0,
        error_count=0,
        overall_score=1.0,
        benchmark_timing_summary=summarize_benchmark_timing(
            [
                BenchmarkCaseResult(
                    case_id="family_afternoon_v1",
                    status="passed",
                    scores=[],
                    overall_score=1.0,
                    tool_event_count=8,
                    action_count=1,
                    workflow_timing_summary=_workflow_timing_summary(
                        total_duration_ms=120,
                        stages=[
                            WorkflowStageTimingEntry(
                                node_name="execute_searches",
                                attempt_count=1,
                                total_duration_ms=40,
                            )
                        ],
                    ),
                )
            ]
        ),
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_run_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_path.name == "run-report.json"
        assert payload["report_path"] == str(report_path)
        assert payload["benchmark_timing_summary"]["schema_version"] == "benchmark_timing_summary_v1"
        assert payload["benchmark_timing_summary"]["overall_total_duration_ms"]["sample_count"] == 1
    finally:
        _cleanup_report_dir(report_dir)


def test_run_report_writer_includes_benchmark_summary_envelope() -> None:
    result = BenchmarkRunReport.model_validate(
        {
            "run_status": "passed",
            "case_results": [],
            "passed_count": 1,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "benchmark_timing_summary": {
                "schema_version": "benchmark_timing_summary_v1",
                "case_count": 1,
                "overall_total_duration_ms": {
                    "sample_count": 1,
                    "min_ms": 120,
                    "p50_ms": 120,
                    "p95_ms": 120,
                    "p99_ms": 120,
                    "max_ms": 120,
                    "mean_ms": 120.0,
                },
                "stages": [],
            },
            "benchmark_summary": {
                "schema_version": "weekendpilot_benchmark_summary_v1",
                "run_status": "passed",
                "case_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "error_count": 0,
                "overall_score": 1.0,
                "matrix_summary": {
                    "schema_version": "weekendpilot_benchmark_case_matrix_v1",
                    "case_count": 1,
                    "scenario_bucket_counts": {"family": 1},
                    "level_counts": {"L1": 1},
                    "world_profile_counts": {"family_afternoon": 1},
                    "failure_mode_counts": {"none": 1},
                    "tag_counts": {"baseline": 1},
                },
                "benchmark_timing_summary": {
                    "schema_version": "benchmark_timing_summary_v1",
                    "case_count": 1,
                    "overall_total_duration_ms": {
                        "sample_count": 1,
                        "min_ms": 120,
                        "p50_ms": 120,
                        "p95_ms": 120,
                        "p99_ms": 120,
                        "max_ms": 120,
                        "mean_ms": 120.0,
                    },
                    "stages": [],
                },
            },
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_run_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["benchmark_summary"]["schema_version"] == "weekendpilot_benchmark_summary_v1"
        assert payload["benchmark_summary"]["case_count"] == 1
        assert payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == {"family": 1}
        assert payload["benchmark_summary"]["benchmark_timing_summary"]["case_count"] == 1
    finally:
        _cleanup_report_dir(report_dir)


def test_benchmark_summary_schema_includes_suite_and_outcome_rollup_fields() -> None:
    assert "suite_id" in BenchmarkSummary.model_fields
    assert "suite_title" in BenchmarkSummary.model_fields
    assert "outcome_rollup" in BenchmarkSummary.model_fields


def test_run_cases_includes_additive_outcome_rollup_for_ad_hoc_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = [
        BenchmarkCase(
            case_id="family-pass",
            title="Family pass",
            user_input="Plan a family outing.",
            taxonomy=_taxonomy_payload(
                scenario_bucket="family",
                level="L1",
                tags=["baseline", "child_friendly", "light_meal"],
            ),
            expected=BenchmarkExpectedOutcome(
                required_tool_names=["search_poi"],
                min_tool_event_count=1,
                min_action_count=1,
            ),
        ),
        BenchmarkCase(
            case_id="solo-fail",
            title="Solo fail",
            user_input="Plan a solo outing.",
            taxonomy=_taxonomy_payload(
                scenario_bucket="solo",
                level="L1",
                tags=["baseline", "light_activity"],
            ),
            expected=BenchmarkExpectedOutcome(
                required_tool_names=["search_poi"],
                min_tool_event_count=1,
                min_action_count=1,
            ),
        ),
    ]
    result_map = {
        "family-pass": _benchmark_case_result(cases[0], status="passed"),
        "solo-fail": _benchmark_case_result(cases[1], status="failed"),
    }
    report_dir = _unit_report_dir()
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None, report_dir=report_dir)

    monkeypatch.setattr(harness, "run_case", lambda case: result_map[case.case_id])

    try:
        report = harness.run_cases(cases)

        assert report.report_path is not None
        assert report.report_path.endswith("run-report.json")
        assert report.benchmark_summary is not None
        assert report.benchmark_summary.suite_id is None
        assert report.benchmark_summary.suite_title is None
        assert report.benchmark_summary.outcome_rollup is not None
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["family"].case_count == 1
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["family"].passed_count == 1
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["family"].pass_rate == 1.0
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["solo"].failed_count == 1
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["solo"].pass_rate == 0.0
        assert "baseline" not in report.benchmark_summary.outcome_rollup.constraint_tag_outcomes
        assert report.benchmark_summary.outcome_rollup.constraint_tag_outcomes["child_friendly"].passed_count == 1
        assert report.benchmark_summary.outcome_rollup.constraint_tag_outcomes["light_activity"].failed_count == 1
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].case_count == 2
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].passed_count == 1
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].failed_count == 1
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].pass_rate == 0.5
    finally:
        _cleanup_report_dir(report_dir)


def test_run_suite_uses_canonical_suite_report_filename_and_normalizes_failures_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = BenchmarkCase(
        case_id="family_route_failure_v1",
        title="Recovery case",
        user_input="Plan around the route failure.",
        failure_profile="route_unavailable_v0",
        taxonomy=_taxonomy_payload(
            scenario_bucket="family",
            level="L2",
            tags=["child_friendly", "failure_injected", "light_meal", "route_failure"],
            failure_mode="route_unavailable",
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_workflow_status="failed",
            expected_execution_status=None,
            expected_feedback_status=None,
            expected_error_type="recovery_stopped",
        ),
    )
    suite_description = BenchmarkSuiteDescription(
        suite_id="recovery_focused",
        title="Recovery focused benchmark suite",
        description="Recovery-only suite",
        case_ids=[case.case_id],
        case_count=1,
        matrix_summary=build_case_matrix_summary([case]),
    )
    report_dir = _unit_report_dir()
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None, report_dir=report_dir)
    captured: dict[str, str] = {}
    run_suite = getattr(harness, "run_suite", None)

    assert callable(run_suite)

    monkeypatch.setattr(benchmark_harness, "load_benchmark_suite", lambda suite_id: [case])
    monkeypatch.setattr(benchmark_harness, "list_benchmark_suites", lambda: [suite_description])
    monkeypatch.setattr(
        benchmark_harness,
        "write_run_report",
        lambda result, directory, filename="run-report.json": captured.setdefault(
            "report_path",
            str(Path(directory) / filename),
        ),
    )
    monkeypatch.setattr(
        harness,
        "run_case",
        lambda benchmark_case: _benchmark_case_result(
            benchmark_case,
            status="passed",
            workflow_status="failed",
        ),
    )

    report = run_suite("failures")

    assert report.report_path is not None
    assert report.report_path.endswith("suite-recovery_focused-run-report.json")
    assert captured["report_path"].endswith("suite-recovery_focused-run-report.json")
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.suite_id == "recovery_focused"
    assert report.benchmark_summary.suite_title == "Recovery focused benchmark suite"
    assert report.benchmark_summary.outcome_rollup is not None
    assert set(report.benchmark_summary.outcome_rollup.constraint_tag_outcomes) == {
        "child_friendly",
        "light_meal",
    }
    assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["route_unavailable"].case_count == 1
    assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["route_unavailable"].passed_count == 1
    assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["route_unavailable"].pass_rate == 1.0


def _benchmark_case() -> BenchmarkCase:
    return BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=2,
        ),
    )


def _benchmark_case_result(
    case: BenchmarkCase,
    *,
    status: str,
    workflow_status: str = "completed",
) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        case_id=case.case_id,
        status=status,
        taxonomy=case.taxonomy,
        scores=[],
        overall_score=1.0 if status == "passed" else 0.0,
        tool_event_count=max(case.expected.min_tool_event_count, 1),
        action_count=max(case.expected.min_action_count, 0),
        workflow_status=workflow_status,
    )


def _workflow_timing_summary(
    *,
    total_duration_ms: int,
    stages: list[WorkflowStageTimingEntry],
) -> WorkflowTimingSummary:
    return WorkflowTimingSummary(
        total_duration_ms=total_duration_ms,
        stage_count=len(stages),
        stages=stages,
    )


def _unit_report_dir() -> Path:
    return Path("var/test-benchmarks") / f"unit-{uuid4()}"


def _cleanup_report_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    var_dir = parent.parent
    if var_dir.exists() and not any(var_dir.iterdir()):
        var_dir.rmdir()
