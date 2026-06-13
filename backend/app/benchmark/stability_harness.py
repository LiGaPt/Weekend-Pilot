from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.formal_verification import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    REPO_ROOT,
    _bootstrap_runtime,
)
from backend.app.benchmark.schemas import (
    BenchmarkStabilityAttemptSummary,
    BenchmarkStabilityPassKReport,
    BenchmarkStabilityWindowSummary,
)
from backend.app.benchmark.v2_integrity_gate import run_benchmark_v2_integrity_gate


SUPPORTED_SUITE_ID = "v2_integrity"
WINDOW_SIZE = 4
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "var" / "formal-benchmarks" / "stability"
LATEST_REPORT_FILENAME = "latest-v2_integrity-passk-v0-report.json"


class BenchmarkStabilityHarnessError(RuntimeError):
    """Raised when the benchmark stability harness cannot finish successfully."""


def run_benchmark_stability_passk(
    suite_id: str,
    runs: int,
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> BenchmarkStabilityPassKReport:
    if suite_id != SUPPORTED_SUITE_ID:
        raise BenchmarkStabilityHarnessError(f"Unsupported suite_id: {suite_id!r}. v0 supports only 'v2_integrity'.")
    if runs < WINDOW_SIZE:
        raise BenchmarkStabilityHarnessError("Stability harness v0 requires at least 4 runs.")

    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    run_directory = root / f"stability-{suite_id}-{uuid4()}"
    run_directory.mkdir(parents=True, exist_ok=False)
    latest_report_path = root / LATEST_REPORT_FILENAME

    _bootstrap_runtime(
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )

    attempts: list[BenchmarkStabilityAttemptSummary] = []
    success_count = 0
    failure_count = 0
    error_count = 0
    gate_id: str | None = None

    for attempt_index in range(1, runs + 1):
        attempt_dir = run_directory / f"attempt-{attempt_index:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=False)
        try:
            result = run_benchmark_v2_integrity_gate(
                output_root=attempt_dir,
                start_services=False,
                refresh_latest_alias=False,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
            gate_id = gate_id or result.gate_id
            status = _attempt_status_from_gate_result(result.release_blocked, result.run_status)
            normalized_suite_report_path = _materialize_attempt_suite_report(
                attempt_dir=attempt_dir,
                suite_report_path=result.suite_report_path,
            )
            relative_suite_report_path = normalized_suite_report_path.relative_to(run_directory).as_posix()
            attempts.append(
                BenchmarkStabilityAttemptSummary(
                    attempt_index=attempt_index,
                    status=status,
                    release_blocked=result.release_blocked,
                    run_status=result.run_status,
                    overall_score=result.overall_score,
                    suite_report_path=relative_suite_report_path,
                    blocking_failures=list(result.blocking_failures),
                )
            )
        except Exception as exc:
            attempts.append(
                BenchmarkStabilityAttemptSummary(
                    attempt_index=attempt_index,
                    status="error",
                    release_blocked=True,
                    run_status="error",
                    overall_score=0.0,
                    suite_report_path=f"attempt-{attempt_index:03d}/suite-v2_integrity-run-report.json",
                    blocking_failures=[f"{type(exc).__name__}: {exc}"],
                )
            )

    for attempt in attempts:
        if attempt.status == "passed":
            success_count += 1
        elif attempt.status == "failed":
            failure_count += 1
        else:
            error_count += 1

    windows = _build_windows(attempts)
    window_count = len(windows)
    discarded_tail_run_count = len(attempts) % WINDOW_SIZE
    success_at_1 = round(success_count / len(attempts), 4)
    pass_at_4 = round(sum(1 for window in windows if window.any_success) / window_count, 4) if window_count else 0.0
    pass_pow_4 = round(sum(1 for window in windows if window.all_success) / window_count, 4) if window_count else 0.0

    report = BenchmarkStabilityPassKReport(
        suite_id=suite_id,
        gate_id=gate_id or "v2_integrity_gate",
        requested_run_count=runs,
        executed_run_count=len(attempts),
        window_size=WINDOW_SIZE,
        window_count=window_count,
        discarded_tail_run_count=discarded_tail_run_count,
        success_count=success_count,
        failure_count=failure_count,
        error_count=error_count,
        success_at_1=success_at_1,
        pass_at_4=pass_at_4,
        pass_pow_4=pass_pow_4,
        attempts=attempts,
        windows=windows,
    )
    report_path = run_directory / f"stability-{suite_id}-passk-v0-report.json"
    _write_report(report_path, report)
    _write_report(latest_report_path, report.model_copy(update={"report_path": str(report_path), "latest_report_path": str(latest_report_path)}))
    return report.model_copy(update={"report_path": str(report_path), "latest_report_path": str(latest_report_path)})


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        suite_id, runs, output_root, start_services = _parse_args(args)
        report = run_benchmark_stability_passk(
            suite_id,
            runs,
            output_root=output_root,
            start_services=start_services,
        )
    except BenchmarkStabilityHarnessError as exc:
        print(f"Benchmark stability harness failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Benchmark stability harness failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(_format_success_summary(report))
    return 0


def _parse_args(args: list[str]) -> tuple[str, int, Path | None, bool]:
    suite_id: str | None = None
    runs: int | None = None
    output_root: Path | None = None
    start_services = True
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--suite":
            index += 1
            suite_id = args[index] if index < len(args) else None
        elif token == "--runs":
            index += 1
            runs = int(args[index]) if index < len(args) else None
        elif token == "--output-root":
            index += 1
            output_root = Path(args[index]) if index < len(args) else None
        elif token == "--no-start-services":
            start_services = False
        else:
            raise BenchmarkStabilityHarnessError(f"Unknown argument: {token}")
        index += 1

    if suite_id is None or runs is None:
        raise BenchmarkStabilityHarnessError("Usage: --suite <suite_id> --runs <count> [--output-root <path>] [--no-start-services]")
    return suite_id, runs, output_root, start_services


def _attempt_status_from_gate_result(release_blocked: bool, run_status: str) -> str:
    if release_blocked:
        return "failed" if run_status != "error" else "error"
    return "passed"


def _build_windows(attempts: list[BenchmarkStabilityAttemptSummary]) -> list[BenchmarkStabilityWindowSummary]:
    windows: list[BenchmarkStabilityWindowSummary] = []
    full_window_count = len(attempts) // WINDOW_SIZE
    for window_index in range(full_window_count):
        start = window_index * WINDOW_SIZE
        group = attempts[start : start + WINDOW_SIZE]
        success_count = sum(1 for attempt in group if attempt.status == "passed")
        windows.append(
            BenchmarkStabilityWindowSummary(
                window_index=window_index + 1,
                attempt_indexes=[attempt.attempt_index for attempt in group],
                any_success=success_count > 0,
                all_success=success_count == WINDOW_SIZE,
                success_count=success_count,
            )
        )
    return windows


def _write_report(path: Path, report: BenchmarkStabilityPassKReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _materialize_attempt_suite_report(*, attempt_dir: Path, suite_report_path: Path) -> Path:
    destination = attempt_dir / "suite-v2_integrity-run-report.json"
    if suite_report_path.resolve() == destination.resolve():
        return destination
    shutil.copyfile(suite_report_path, destination)
    return destination


def _format_success_summary(report: BenchmarkStabilityPassKReport) -> str:
    return "\n".join(
        [
            "Benchmark stability harness passed.",
            f"Suite: {report.suite_id}",
            f"Runs: {report.executed_run_count}",
            f"Success@1: {report.success_at_1}",
            f"Pass@4: {report.pass_at_4}",
            f"Pass^4: {report.pass_pow_4}",
            f"Report: {report.report_path}",
            f"Latest: {report.latest_report_path}",
        ]
    )
