from __future__ import annotations

import json
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

import pytest

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.replay import BenchmarkReplayHarness, stable_replay_summary
from backend.app.benchmark.reporting import write_case_report
from backend.app.benchmark.schemas import BenchmarkCaseResult, BenchmarkScore
from backend.app.workflow.timing import WorkflowStageTimingEntry, WorkflowTimingSummary


FORBIDDEN_REPORT_TEXT = (
    "action_id",
    "tool_event_id",
    "api_key",
    "token",
    "secret",
    "authorization",
    "debug_trace",
)


class FakeBenchmarkHarness:
    def __init__(self, *results: BenchmarkCaseResult | Exception) -> None:
        self.results = list(results)
        self.case_ids: list[str] = []

    def run_case(self, case):
        self.case_ids.append(case.case_id)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture()
def unit_report_dir():
    path = Path("var/test-benchmark-replays") / f"unit-{uuid4()}"
    try:
        yield path
    finally:
        if path.exists():
            rmtree(path)
        parent = path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        var_dir = parent.parent
        if var_dir.exists() and not any(var_dir.iterdir()):
            var_dir.rmdir()


def test_stable_summary_extracts_replay_fields() -> None:
    result = _case_result(
        workflow_status="failed",
        action_count=0,
        injected_failure_count=2,
        recovery_actions=["stop_safely"],
    )

    summary = stable_replay_summary(result)

    assert summary.status == "passed"
    assert summary.workflow_status == "failed"
    assert summary.observed_tool_names == ["check_route", "search_poi"]
    assert summary.action_count == 0
    assert summary.injected_failure_count == 2
    assert summary.recovery_actions == ["stop_safely"]


def test_replay_result_passes_for_matching_stable_fields(unit_report_dir: Path) -> None:
    source = _case_result(run_id=uuid4(), trace_id="source-trace", report_path="source.json")
    replayed = _case_result(run_id=uuid4(), trace_id="replay-trace", report_path="replay.json")
    fake_harness = FakeBenchmarkHarness(replayed)
    replay = BenchmarkReplayHarness(fake_harness, replay_report_dir=unit_report_dir)

    result = replay.replay_result(source)

    assert fake_harness.case_ids == ["family_afternoon_v1"]
    assert result.status == "passed"
    assert result.mismatches == []
    assert result.source == stable_replay_summary(source)
    assert result.replay == stable_replay_summary(replayed)
    assert result.replay_benchmark_status == "passed"
    assert result.replay_report_path is not None
    assert Path(result.replay_report_path).exists()


def test_replay_result_fails_with_explicit_mismatches(unit_report_dir: Path) -> None:
    source = _case_result(workflow_status="completed", action_count=2)
    replayed = _case_result(workflow_status="failed", action_count=0)
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(replayed), replay_report_dir=unit_report_dir)

    result = replay.replay_result(source)

    assert result.status == "failed"
    assert [(item.field, item.source, item.replay) for item in result.mismatches] == [
        ("workflow_status", "completed", "failed"),
        ("action_count", 2, 0),
    ]


def test_replay_result_ignores_unstable_identifiers_and_paths(unit_report_dir: Path) -> None:
    source = _case_result(run_id=uuid4(), trace_id="source-trace", report_path="source.json")
    replayed = _case_result(run_id=uuid4(), trace_id="replay-trace", report_path="replay.json")
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(replayed), replay_report_dir=unit_report_dir)

    result = replay.replay_result(source)

    assert result.status == "passed"
    serialized = Path(result.replay_report_path).read_text(encoding="utf-8")
    assert "source-trace" not in serialized
    assert "replay-trace" not in serialized


def test_replay_result_ignores_additive_workflow_timing_summary(unit_report_dir: Path) -> None:
    source = _case_result(
        workflow_timing_summary=WorkflowTimingSummary(
            total_duration_ms=120,
            stage_count=1,
            stages=[
                WorkflowStageTimingEntry(
                    node_name="execute_searches",
                    attempt_count=1,
                    total_duration_ms=40,
                )
            ],
        )
    )
    replayed = _case_result(
        workflow_timing_summary=WorkflowTimingSummary(
            total_duration_ms=999,
            stage_count=1,
            stages=[
                WorkflowStageTimingEntry(
                    node_name="execute_searches",
                    attempt_count=3,
                    total_duration_ms=333,
                )
            ],
        )
    )
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(replayed), replay_report_dir=unit_report_dir)

    result = replay.replay_result(source)

    assert result.status == "passed"
    assert result.mismatches == []


def test_replay_result_ignores_additive_run_summary(unit_report_dir: Path) -> None:
    source = _case_result(
        run_summary={
            "schema_version": "weekendpilot_run_summary_v1",
            "run_id": str(uuid4()),
            "trace_id": "source-trace",
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
            "action_count": 2,
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
        }
    )
    replayed = _case_result(
        run_summary={
            "schema_version": "weekendpilot_run_summary_v1",
            "run_id": str(uuid4()),
            "trace_id": "replay-trace",
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
            "action_count": 2,
            "agent_roles": ["supervisor", "discovery"],
            "workflow_timing_summary": {
                "schema_version": "workflow_timing_summary_v1",
                "total_duration_ms": 999,
                "stage_count": 1,
                "stages": [
                    {
                        "node_name": "initialize",
                        "attempt_count": 1,
                        "total_duration_ms": 999,
                    }
                ],
            },
            "error": None,
        }
    )
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(replayed), replay_report_dir=unit_report_dir)

    result = replay.replay_result(source)

    assert result.status == "passed"
    assert result.mismatches == []


def test_replay_report_loads_case_report_from_disk(unit_report_dir: Path) -> None:
    source = _case_result()
    source_report = Path(write_case_report(source, unit_report_dir / "source"))
    replayed = _case_result()
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(replayed), replay_report_dir=unit_report_dir / "replays")

    result = replay.replay_report(source_report)

    assert result.status == "passed"
    assert result.benchmark_report_path == str(source_report)
    assert Path(result.replay_report_path).exists()


def test_replay_report_rejects_missing_and_malformed_source_reports(unit_report_dir: Path) -> None:
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(_case_result()), replay_report_dir=unit_report_dir)

    with pytest.raises(BenchmarkHarnessError, match="not found"):
        replay.replay_report(unit_report_dir / "missing.json")

    unit_report_dir.mkdir(parents=True, exist_ok=True)
    malformed = unit_report_dir / "malformed.json"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(BenchmarkHarnessError, match="malformed"):
        replay.replay_report(malformed)


def test_replay_result_returns_error_for_benchmark_execution_exception(unit_report_dir: Path) -> None:
    replay = BenchmarkReplayHarness(
        FakeBenchmarkHarness(RuntimeError("provider token leaked")),
        replay_report_dir=unit_report_dir,
    )

    result = replay.replay_result(_case_result())

    assert result.status == "error"
    assert result.failure_reasons == ["RuntimeError: provider [redacted] leaked"]
    assert result.replay_benchmark_status == "error"
    assert Path(result.replay_report_path).exists()


def test_replay_results_aggregate_counts(unit_report_dir: Path) -> None:
    sources = [
        _case_result(case_id="family_afternoon_v1", action_count=2),
        _case_result(case_id="family_afternoon_v1", action_count=2),
        _case_result(case_id="family_afternoon_v1", action_count=2),
    ]
    replayed = [
        _case_result(action_count=2),
        _case_result(action_count=0),
        RuntimeError("boom"),
    ]
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(*replayed), replay_report_dir=unit_report_dir)

    report = replay.replay_results(sources)

    assert report.run_status == "error"
    assert report.passed_count == 1
    assert report.failed_count == 1
    assert report.error_count == 1


def test_replay_report_output_excludes_forbidden_text(unit_report_dir: Path) -> None:
    source = _case_result(
        extra_trajectory_details={
            "action_id": "do-not-write",
            "tool_event_id": "do-not-write",
            "api_key": "do-not-write",
            "token": "do-not-write",
            "secret": "do-not-write",
            "authorization": "do-not-write",
            "debug_trace": "do-not-write",
        }
    )
    replay = BenchmarkReplayHarness(FakeBenchmarkHarness(_case_result()), replay_report_dir=unit_report_dir)

    result = replay.replay_result(source)

    serialized = json.dumps(
        json.loads(Path(result.replay_report_path).read_text(encoding="utf-8")),
        sort_keys=True,
    )
    for forbidden in FORBIDDEN_REPORT_TEXT:
        assert forbidden not in serialized
    assert "do-not-write" not in serialized


def _case_result(
    *,
    case_id: str = "family_afternoon_v1",
    status: str = "passed",
    workflow_status: str = "completed",
    action_count: int = 2,
    injected_failure_count: int = 0,
    recovery_actions: list[str] | None = None,
    run_id=None,
    trace_id: str | None = None,
    report_path: str | None = None,
    workflow_timing_summary: WorkflowTimingSummary | None = None,
    run_summary: dict | None = None,
    extra_trajectory_details: dict | None = None,
) -> BenchmarkCaseResult:
    trajectory_details = {
        "observed_tool_names": ["search_poi", "check_route"],
        **(extra_trajectory_details or {}),
    }
    scores = [
        BenchmarkScore(
            name="workflow_path",
            score=1.0,
            passed=True,
            reason="ok",
            details={"workflow_status": workflow_status},
        ),
        BenchmarkScore(
            name="trajectory",
            score=1.0,
            passed=True,
            reason="ok",
            details=trajectory_details,
        ),
        BenchmarkScore(
            name="failure_injection",
            score=1.0,
            passed=True,
            reason="ok",
            details={"injected_failure_count": injected_failure_count},
        ),
    ]
    if recovery_actions is not None:
        scores.append(
            BenchmarkScore(
                name="recovery_expectation",
                score=1.0,
                passed=True,
                reason="ok",
                details={"observed_recovery_actions": recovery_actions},
            )
        )
    return BenchmarkCaseResult(
        case_id=case_id,
        status=status,
        run_id=run_id,
        trace_id=trace_id,
        scores=scores,
        overall_score=1.0,
        tool_event_count=8,
        action_count=action_count,
        workflow_status=workflow_status,
        workflow_timing_summary=workflow_timing_summary,
        run_summary=run_summary,
        report_path=report_path,
    )
