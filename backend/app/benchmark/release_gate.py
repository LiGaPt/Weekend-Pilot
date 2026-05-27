from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from backend.app.benchmark import BenchmarkHarness
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal, engine
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


RELEASE_GATE_SUITE_ID = "release_gate_v1"
RELEASE_GATE_TRACE_FILENAME = "release-gate-traces.jsonl"
LATEST_REPORT_FILENAME = f"latest-{RELEASE_GATE_SUITE_ID}-run-report.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "var" / "formal-benchmarks"
EXPECTED_LEVEL_COUNTS = {"L1": 3, "L2": 8, "L3": 4}
EXPECTED_TOOL_PROFILE_COUNTS = {"mock_world": 15}
EXPECTED_FAILURE_MODE_COUNTS = {"none": 14, "route_unavailable": 1}
EXPECTED_CASE_COUNT = 15
EXPECTED_PASSED_COUNT = 15
EXPECTED_FAILED_COUNT = 0
EXPECTED_ERROR_COUNT = 0
EXPECTED_OVERALL_SCORE = 1.0


class BenchmarkReleaseGateError(RuntimeError):
    """Raised when the benchmark release gate cannot finish successfully."""


@dataclass(frozen=True)
class BenchmarkReleaseGateResult:
    gate_id: str
    suite_id: str | None
    release_blocked: bool
    blocking_failures: list[str]
    run_status: str
    case_count: int
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
    run_directory: Path
    suite_report_path: Path
    latest_report_path: Path
    trace_buffer_path: Path
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    p99_duration_ms: int | None = None


def run_benchmark_release_gate(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> BenchmarkReleaseGateResult:
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    _bootstrap_runtime(
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )

    run_directory = root / f"release-gate-v1-{uuid4()}"
    run_directory.mkdir(parents=True, exist_ok=False)
    trace_buffer_path = run_directory / RELEASE_GATE_TRACE_FILENAME
    latest_report_path = root / LATEST_REPORT_FILENAME
    workflow_settings = _build_release_gate_workflow_settings()

    session = None
    redis_client = None
    try:
        session = SessionLocal()
        redis_client = get_redis_client()
        keys = RedisKeyBuilder.from_settings()
        cache = JsonRedisCache(redis_client, keys)
        rate_limiter = FixedWindowRateLimiter(redis_client, keys)
        harness = BenchmarkHarness(
            session,
            cache,
            rate_limiter,
            report_dir=run_directory,
            trace_buffer_path=trace_buffer_path,
            workflow_settings=workflow_settings,
        )
        report = harness.run_suite(RELEASE_GATE_SUITE_ID)
        return _finalize_release_gate_result(
            report=report,
            run_directory=run_directory,
            latest_report_path=latest_report_path,
            trace_buffer_path=trace_buffer_path,
        )
    finally:
        _close_quietly(session)
        _close_quietly(redis_client)


def main() -> int:
    try:
        result = run_benchmark_release_gate()
    except BenchmarkReleaseGateError as exc:
        print(f"Benchmark release gate failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Benchmark release gate failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if result.release_blocked:
        print(_format_failure_summary(result), file=sys.stderr)
        return 1

    print(_format_success_summary(result))
    return 0


def _bootstrap_runtime(
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> None:
    if start_services:
        _run_subprocess(
            ["docker", "compose", "up", "-d", "postgres", "redis"],
            error_context="Could not start postgres and redis.",
        )
    _wait_for_postgres(timeout_seconds=timeout_seconds, poll_interval_seconds=poll_interval_seconds)
    _wait_for_redis(timeout_seconds=timeout_seconds, poll_interval_seconds=poll_interval_seconds)
    _run_subprocess(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        error_context="Alembic upgrade failed.",
    )


def _build_release_gate_workflow_settings(source: Settings | None = None) -> Settings:
    settings = source if source is not None else get_settings()
    return settings.model_copy(
        update={
            "llm_enabled": False,
            "llm_api_key": None,
            "llm_base_url": None,
            "llm_model_id": None,
            "langsmith_tracing": False,
            "langchain_tracing_v2": False,
            "langsmith_api_key": None,
            "langsmith_endpoint": None,
        }
    )


def _run_subprocess(command: list[str], *, error_context: str) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise BenchmarkReleaseGateError(f"{error_context} Could not run: {' '.join(command)}") from exc

    if completed.returncode == 0:
        return

    details = _format_subprocess_details(completed.stdout, completed.stderr)
    message = f"{error_context} Command failed: {' '.join(command)}"
    if details:
        message = f"{message}. {details}"
    raise BenchmarkReleaseGateError(message)


def _wait_for_postgres(*, timeout_seconds: float, poll_interval_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - exercised in integration/bootstrap flows
            last_error = exc
            time.sleep(poll_interval_seconds)
    raise BenchmarkReleaseGateError(
        f"PostgreSQL readiness timed out after {timeout_seconds:.1f}s" + _format_last_error(last_error)
    )


def _wait_for_redis(*, timeout_seconds: float, poll_interval_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        client = None
        try:
            client = get_redis_client()
            client.ping()
            return
        except Exception as exc:  # pragma: no cover - exercised in integration/bootstrap flows
            last_error = exc
            time.sleep(poll_interval_seconds)
        finally:
            _close_quietly(client)
    raise BenchmarkReleaseGateError(
        f"Redis readiness timed out after {timeout_seconds:.1f}s" + _format_last_error(last_error)
    )


def _finalize_release_gate_result(
    *,
    report: Any,
    run_directory: Path,
    latest_report_path: Path,
    trace_buffer_path: Path,
) -> BenchmarkReleaseGateResult:
    summary = getattr(report, "benchmark_summary", None)
    suite_id = getattr(summary, "suite_id", None)
    run_status = str(getattr(report, "run_status", ""))
    case_count = int(getattr(summary, "case_count", 0) or 0)
    passed_count = int(getattr(summary, "passed_count", 0) or 0)
    failed_count = int(getattr(summary, "failed_count", getattr(report, "failed_count", 0)) or 0)
    error_count = int(getattr(summary, "error_count", getattr(report, "error_count", 0)) or 0)
    overall_score = float(getattr(summary, "overall_score", getattr(report, "overall_score", 0.0)) or 0.0)
    report_path_value = getattr(report, "report_path", None)
    suite_report_path = (
        Path(report_path_value)
        if report_path_value
        else run_directory / f"suite-{RELEASE_GATE_SUITE_ID}-run-report.json"
    )

    blocking_failures: list[str] = []
    if suite_id != RELEASE_GATE_SUITE_ID:
        blocking_failures.append(f"Expected suite_id={RELEASE_GATE_SUITE_ID!r}, got {suite_id!r}.")
    if run_status != "passed":
        blocking_failures.append(f"Expected run_status='passed', got {run_status!r}.")
    if case_count != EXPECTED_CASE_COUNT:
        blocking_failures.append(f"Expected case_count={EXPECTED_CASE_COUNT}, got {case_count}.")
    if passed_count != EXPECTED_PASSED_COUNT:
        blocking_failures.append(f"Expected passed_count={EXPECTED_PASSED_COUNT}, got {passed_count}.")
    if failed_count != EXPECTED_FAILED_COUNT:
        blocking_failures.append(f"Expected failed_count={EXPECTED_FAILED_COUNT}, got {failed_count}.")
    if error_count != EXPECTED_ERROR_COUNT:
        blocking_failures.append(f"Expected error_count={EXPECTED_ERROR_COUNT}, got {error_count}.")
    if overall_score != EXPECTED_OVERALL_SCORE:
        blocking_failures.append(f"Expected overall_score={EXPECTED_OVERALL_SCORE}, got {overall_score}.")
    if not report_path_value:
        blocking_failures.append("Benchmark suite did not return a report_path.")
    elif not suite_report_path.exists():
        blocking_failures.append(f"Suite report does not exist: {suite_report_path}")

    matrix_summary = getattr(summary, "matrix_summary", None)
    level_counts = _coerce_count_map(getattr(matrix_summary, "level_counts", None))
    tool_profile_counts = _coerce_count_map(getattr(matrix_summary, "tool_profile_counts", None))
    failure_mode_counts = _coerce_count_map(getattr(matrix_summary, "failure_mode_counts", None))

    if level_counts != EXPECTED_LEVEL_COUNTS:
        blocking_failures.append(f"Expected level_counts={EXPECTED_LEVEL_COUNTS}, got {level_counts}.")
    if tool_profile_counts != EXPECTED_TOOL_PROFILE_COUNTS:
        blocking_failures.append(
            f"Expected tool_profile_counts={EXPECTED_TOOL_PROFILE_COUNTS}, got {tool_profile_counts}."
        )
    if failure_mode_counts != EXPECTED_FAILURE_MODE_COUNTS:
        blocking_failures.append(
            f"Expected failure_mode_counts={EXPECTED_FAILURE_MODE_COUNTS}, got {failure_mode_counts}."
        )

    if not blocking_failures:
        copy_error = _refresh_latest_alias(suite_report_path, latest_report_path)
        if copy_error is not None:
            blocking_failures.append(copy_error)

    timing_summary = getattr(report, "benchmark_timing_summary", None)
    total_duration = getattr(timing_summary, "overall_total_duration_ms", None)

    return BenchmarkReleaseGateResult(
        gate_id=RELEASE_GATE_SUITE_ID,
        suite_id=suite_id,
        release_blocked=bool(blocking_failures),
        blocking_failures=blocking_failures,
        run_status=run_status,
        case_count=case_count,
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        overall_score=overall_score,
        run_directory=run_directory,
        suite_report_path=suite_report_path,
        latest_report_path=latest_report_path,
        trace_buffer_path=trace_buffer_path,
        p50_duration_ms=_coerce_optional_int(getattr(total_duration, "p50_ms", None)),
        p95_duration_ms=_coerce_optional_int(getattr(total_duration, "p95_ms", None)),
        p99_duration_ms=_coerce_optional_int(getattr(total_duration, "p99_ms", None)),
    )


def _refresh_latest_alias(suite_report_path: Path, latest_report_path: Path) -> str | None:
    temp_path = latest_report_path.with_name(f"{latest_report_path.name}.tmp")
    try:
        latest_report_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(suite_report_path, temp_path)
        temp_path.replace(latest_report_path)
        return None
    except OSError:
        return f"Could not refresh latest report alias: {latest_report_path}"
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _format_success_summary(result: BenchmarkReleaseGateResult) -> str:
    return "\n".join(
        [
            "Benchmark release gate passed.",
            f"Gate: {result.gate_id}",
            f"Suite: {result.suite_id}",
            (
                f"Cases: {result.case_count} "
                f"({result.passed_count} passed, {result.failed_count} failed, {result.error_count} error)"
            ),
            f"Overall score: {result.overall_score}",
            (
                "Timing: "
                f"p50={_format_duration(result.p50_duration_ms)}, "
                f"p95={_format_duration(result.p95_duration_ms)}, "
                f"p99={_format_duration(result.p99_duration_ms)}"
            ),
            f"Run directory: {result.run_directory}",
            f"Suite report: {result.suite_report_path}",
            f"Latest report: {result.latest_report_path}",
        ]
    )


def _format_failure_summary(result: BenchmarkReleaseGateResult) -> str:
    lines = [
        "Benchmark release gate failed.",
        f"Gate: {result.gate_id}",
        f"Suite: {result.suite_id}",
        (
            f"Cases: {result.case_count} "
            f"({result.passed_count} passed, {result.failed_count} failed, {result.error_count} error)"
        ),
        f"Overall score: {result.overall_score}",
        (
            "Timing: "
            f"p50={_format_duration(result.p50_duration_ms)}, "
            f"p95={_format_duration(result.p95_duration_ms)}, "
            f"p99={_format_duration(result.p99_duration_ms)}"
        ),
        f"Run directory: {result.run_directory}",
        f"Suite report: {result.suite_report_path}",
        f"Latest report: {result.latest_report_path}",
        "Blocking failures:",
    ]
    lines.extend(f"- {failure}" for failure in result.blocking_failures)
    return "\n".join(lines)


def _format_duration(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value}ms"


def _coerce_count_map(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(key): int(count) for key, count in value.items()}
    return {}


def _format_subprocess_details(stdout: str, stderr: str) -> str:
    parts: list[str] = []
    if stdout.strip():
        parts.append(f"stdout={stdout.strip()[-300:]}")
    if stderr.strip():
        parts.append(f"stderr={stderr.strip()[-300:]}")
    return "; ".join(parts)


def _format_last_error(error: Exception | None) -> str:
    if error is None:
        return "."
    return f": {type(error).__name__}: {error}"


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()
