from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.benchmark.internal_summary import (
    ReleaseGateBenchmarkSummaryInvalidError,
    ReleaseGateBenchmarkSummaryNotFoundError,
    load_latest_release_gate_summary,
)


@pytest.fixture()
def report_directory() -> Path:
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


def test_load_latest_release_gate_summary_reads_compact_summary(report_directory: Path) -> None:
    report_path = report_directory / "latest-release-gate.json"
    report_path.write_text(json.dumps(_build_release_gate_report()), encoding="utf-8")

    summary = load_latest_release_gate_summary(report_path, report_label="var/formal-benchmarks/latest-release_gate_v1-run-report.json")

    assert summary.schema_version == "weekendpilot_internal_benchmark_summary_v1"
    assert summary.suite_id == "release_gate_v1"
    assert summary.suite_title == "Benchmark release gate v1"
    assert summary.run_status == "passed"
    assert summary.case_count == 15
    assert summary.passed_count == 15
    assert summary.failed_count == 0
    assert summary.error_count == 0
    assert summary.overall_score == 1.0
    assert summary.matrix_summary.level_counts == {"L1": 3, "L2": 8, "L3": 4}
    assert summary.matrix_summary.tool_profile_counts == {"mock_world": 15}
    assert summary.matrix_summary.failure_mode_counts == {"none": 14, "route_unavailable": 1}
    assert summary.matrix_summary.tag_counts["memory_governance"] == 2
    assert summary.report_path == "var/formal-benchmarks/latest-release_gate_v1-run-report.json"


def test_load_latest_release_gate_summary_raises_for_missing_report(report_directory: Path) -> None:
    with pytest.raises(ReleaseGateBenchmarkSummaryNotFoundError):
        load_latest_release_gate_summary(report_directory / "missing.json")


def test_load_latest_release_gate_summary_raises_for_malformed_report(report_directory: Path) -> None:
    report_path = report_directory / "broken.json"
    report_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ReleaseGateBenchmarkSummaryInvalidError):
        load_latest_release_gate_summary(report_path)


def test_load_latest_release_gate_summary_raises_when_benchmark_summary_is_missing(report_directory: Path) -> None:
    report_path = report_directory / "missing-summary.json"
    payload = _build_release_gate_report()
    payload["benchmark_summary"] = None
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseGateBenchmarkSummaryInvalidError):
        load_latest_release_gate_summary(report_path)


def _build_release_gate_report() -> dict:
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
        "report_path": str(tmp_path_placeholder()),
    }


def tmp_path_placeholder() -> Path:
    return Path("var/formal-benchmarks/release-gate-v1-placeholder/suite-release_gate_v1-run-report.json")
