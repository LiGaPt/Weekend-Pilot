from __future__ import annotations

import json
from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.benchmark import (
    load_benchmark_case,
    load_default_benchmark_cases,
    load_failure_benchmark_cases,
)
from backend.app.benchmark.errors import BenchmarkHarnessError
import backend.app.benchmark.graders as benchmark_graders
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
)
from backend.app.benchmark.timing import summarize_benchmark_timing
from backend.app.workflow.timing import WorkflowStageTimingEntry, WorkflowTimingSummary
from backend.app.workflow.state import V1_WORKFLOW_NODE_NAMES


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
)
FAILURE_CASE_IDS = ("family_route_failure_v1",)
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


def test_default_fixtures_load_as_ordered_benchmark_cases() -> None:
    cases = load_default_benchmark_cases()

    assert [case.case_id for case in cases] == list(DEFAULT_CASE_IDS)
    assert len(cases) == 6
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


def test_default_fixtures_can_be_loaded_individually() -> None:
    for case_id in DEFAULT_CASE_IDS:
        case = load_benchmark_case(case_id)

        assert isinstance(case, BenchmarkCase)
        assert case.case_id == case_id


def test_default_fixtures_use_supported_mock_world_profiles() -> None:
    cases = load_default_benchmark_cases()

    assert {case.tool_profile for case in cases} == {"mock_world"}
    assert {case.world_profile for case in cases} == {"family_afternoon", "solo_afternoon"}


def test_default_fixtures_include_v1_metadata_and_expected_tools() -> None:
    cases = load_default_benchmark_cases()

    for case in cases:
        assert case.metadata["suite"] == "locallife_bench_v1"
        assert case.metadata["level"] in {"L1", "L2"}
        assert isinstance(case.metadata["focus"], str)
        assert case.metadata["focus"]
        assert set(case.expected.required_tool_names) == REQUIRED_CASE_TOOL_NAMES
        assert case.expected.expected_execution_status == "succeeded"
        assert case.expected.expected_feedback_status == "completed"


def test_solo_afternoon_fixture_uses_expected_profile_and_focus() -> None:
    case = load_benchmark_case("solo_afternoon_v1")

    assert case.tool_profile == "mock_world"
    assert case.world_profile == "solo_afternoon"
    assert case.metadata["focus"] == "baseline_solo_afternoon"


def test_unknown_case_raises_benchmark_harness_error() -> None:
    with pytest.raises(BenchmarkHarnessError):
        load_benchmark_case("missing_case")


def test_trajectory_grader_passes_when_required_tools_are_present() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
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
        assert payload["benchmark_summary"]["benchmark_timing_summary"]["case_count"] == 1
    finally:
        _cleanup_report_dir(report_dir)


def _benchmark_case() -> BenchmarkCase:
    return BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=2,
        ),
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
        rmtree(path)
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    var_dir = parent.parent
    if var_dir.exists() and not any(var_dir.iterdir()):
        var_dir.rmdir()
