from __future__ import annotations

import json
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

import pytest

from backend.app.benchmark import load_benchmark_case, load_default_benchmark_cases
from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.graders import (
    combine_scores,
    grade_trajectory,
)
from backend.app.benchmark.reporting import write_case_report
from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkExpectedOutcome,
    BenchmarkScore,
)


def test_default_fixture_loads_as_benchmark_case() -> None:
    cases = load_default_benchmark_cases()

    assert len(cases) == 1
    assert isinstance(cases[0], BenchmarkCase)
    assert cases[0].case_id == "family_afternoon_v1"
    assert cases[0].tool_profile == "mock_world"


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
