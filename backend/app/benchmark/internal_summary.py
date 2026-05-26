from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from backend.app.benchmark.release_gate import LATEST_REPORT_FILENAME, RELEASE_GATE_SUITE_ID
from backend.app.benchmark.schemas import BenchmarkRunReport


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LATEST_RELEASE_GATE_REPORT_PATH = REPO_ROOT / "var" / "formal-benchmarks" / LATEST_REPORT_FILENAME
DEFAULT_LATEST_RELEASE_GATE_REPORT_LABEL = Path("var") / "formal-benchmarks" / LATEST_REPORT_FILENAME
INTERNAL_BENCHMARK_SUMMARY_SCHEMA_VERSION = "weekendpilot_internal_benchmark_summary_v1"


class ReleaseGateBenchmarkSummaryMatrix(BaseModel):
    level_counts: dict[str, int] = Field(default_factory=dict)
    tool_profile_counts: dict[str, int] = Field(default_factory=dict)
    failure_mode_counts: dict[str, int] = Field(default_factory=dict)
    tag_counts: dict[str, int] = Field(default_factory=dict)


class ReleaseGateBenchmarkSummary(BaseModel):
    schema_version: str = INTERNAL_BENCHMARK_SUMMARY_SCHEMA_VERSION
    suite_id: str
    suite_title: str
    run_status: str
    case_count: int
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
    matrix_summary: ReleaseGateBenchmarkSummaryMatrix
    report_path: str


class ReleaseGateBenchmarkSummaryError(RuntimeError):
    """Raised when the internal release-gate summary cannot be loaded."""


class ReleaseGateBenchmarkSummaryNotFoundError(ReleaseGateBenchmarkSummaryError):
    """Raised when the latest release-gate artifact is missing."""


class ReleaseGateBenchmarkSummaryInvalidError(ReleaseGateBenchmarkSummaryError):
    """Raised when the latest release-gate artifact is malformed."""


def load_latest_release_gate_summary(
    report_path: Path | str | None = None,
    *,
    report_label: str | None = None,
) -> ReleaseGateBenchmarkSummary:
    path = Path(report_path) if report_path is not None else DEFAULT_LATEST_RELEASE_GATE_REPORT_PATH
    label = report_label or DEFAULT_LATEST_RELEASE_GATE_REPORT_LABEL.as_posix()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseGateBenchmarkSummaryNotFoundError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark summary was not found."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark report is malformed."
        ) from exc
    except OSError as exc:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark report could not be read."
        ) from exc

    try:
        report = BenchmarkRunReport.model_validate(payload)
    except ValidationError as exc:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark report is invalid."
        ) from exc

    summary = report.benchmark_summary
    if summary is None:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark report does not include benchmark_summary."
        )
    if summary.suite_id != RELEASE_GATE_SUITE_ID:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest benchmark summary is not for {RELEASE_GATE_SUITE_ID}."
        )
    if summary.suite_title is None:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark summary is missing suite_title."
        )
    if summary.matrix_summary is None:
        raise ReleaseGateBenchmarkSummaryInvalidError(
            f"Latest {RELEASE_GATE_SUITE_ID} benchmark summary is missing matrix_summary."
        )

    return ReleaseGateBenchmarkSummary(
        suite_id=summary.suite_id,
        suite_title=summary.suite_title,
        run_status=summary.run_status,
        case_count=summary.case_count,
        passed_count=summary.passed_count,
        failed_count=summary.failed_count,
        error_count=summary.error_count,
        overall_score=summary.overall_score,
        matrix_summary=ReleaseGateBenchmarkSummaryMatrix(
            level_counts=dict(summary.matrix_summary.level_counts),
            tool_profile_counts=dict(summary.matrix_summary.tool_profile_counts),
            failure_mode_counts=dict(summary.matrix_summary.failure_mode_counts),
            tag_counts=dict(summary.matrix_summary.tag_counts),
        ),
        report_path=label,
    )
