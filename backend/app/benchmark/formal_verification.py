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
from backend.app.db.session import SessionLocal, engine
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


FORMAL_SUITE_ID = "all_registered"
FORMAL_TRACE_FILENAME = "formal-traces.jsonl"
LATEST_REPORT_FILENAME = f"latest-{FORMAL_SUITE_ID}-run-report.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "var" / "formal-benchmarks"


class FormalVerificationError(RuntimeError):
    """Raised when the formal verification run cannot finish successfully."""


@dataclass(frozen=True)
class FormalVerificationResult:
    suite_id: str
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


def run_formal_verification(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> FormalVerificationResult:
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    _bootstrap_runtime(
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )

    run_directory = root / f"formal-{uuid4()}"
    run_directory.mkdir(parents=True, exist_ok=False)
    trace_buffer_path = run_directory / FORMAL_TRACE_FILENAME
    latest_report_path = root / LATEST_REPORT_FILENAME

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
        )
        report = harness.run_suite(FORMAL_SUITE_ID)
        return _finalize_success(
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
        result = run_formal_verification()
    except FormalVerificationError as exc:
        print(f"Formal verification failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Formal verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
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
        raise FormalVerificationError(f"{error_context} Could not run: {' '.join(command)}") from exc

    if completed.returncode == 0:
        return

    details = _format_subprocess_details(completed.stdout, completed.stderr)
    message = f"{error_context} Command failed: {' '.join(command)}"
    if details:
        message = f"{message}. {details}"
    raise FormalVerificationError(message)


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
    raise FormalVerificationError(
        f"PostgreSQL readiness timed out after {timeout_seconds:.1f}s"
        + _format_last_error(last_error)
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
    raise FormalVerificationError(
        f"Redis readiness timed out after {timeout_seconds:.1f}s"
        + _format_last_error(last_error)
    )


def _finalize_success(
    *,
    report: Any,
    run_directory: Path,
    latest_report_path: Path,
    trace_buffer_path: Path,
) -> FormalVerificationResult:
    summary = getattr(report, "benchmark_summary", None)
    suite_id = getattr(summary, "suite_id", None)
    run_status = str(getattr(report, "run_status", ""))
    failed_count = int(getattr(report, "failed_count", 0) or 0)
    error_count = int(getattr(report, "error_count", 0) or 0)
    report_path_value = getattr(report, "report_path", None)

    if suite_id != FORMAL_SUITE_ID:
        raise FormalVerificationError(f"Unexpected suite ID: {suite_id!r}")
    if run_status != "passed":
        raise FormalVerificationError(f"Benchmark suite returned run_status={run_status!r}.")
    if failed_count != 0:
        raise FormalVerificationError(f"Benchmark suite reported failed_count={failed_count}.")
    if error_count != 0:
        raise FormalVerificationError(f"Benchmark suite reported error_count={error_count}.")
    if not report_path_value:
        raise FormalVerificationError("Benchmark suite did not return a report_path.")

    suite_report_path = Path(report_path_value)
    if not suite_report_path.exists():
        raise FormalVerificationError(f"Suite report does not exist: {suite_report_path}")

    try:
        latest_report_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(suite_report_path, latest_report_path)
    except OSError as exc:
        raise FormalVerificationError(f"Could not refresh latest report alias: {latest_report_path}") from exc

    case_count = int(getattr(summary, "case_count", 0) or 0)
    passed_count = int(getattr(summary, "passed_count", 0) or 0)
    overall_score = float(getattr(summary, "overall_score", getattr(report, "overall_score", 0.0)) or 0.0)
    timing_summary = getattr(report, "benchmark_timing_summary", None)
    total_duration = getattr(timing_summary, "overall_total_duration_ms", None)

    return FormalVerificationResult(
        suite_id=FORMAL_SUITE_ID,
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
    )


def _format_success_summary(result: FormalVerificationResult) -> str:
    return "\n".join(
        [
            "Formal verification passed.",
            f"Suite: {result.suite_id}",
            (
                f"Cases: {result.case_count} "
                f"({result.passed_count} passed, {result.failed_count} failed, {result.error_count} error)"
            ),
            f"Overall score: {result.overall_score}",
            f"Timing: p50={_format_duration(result.p50_duration_ms)}, p95={_format_duration(result.p95_duration_ms)}",
            f"Run directory: {result.run_directory}",
            f"Suite report: {result.suite_report_path}",
            f"Latest report: {result.latest_report_path}",
        ]
    )


def _format_duration(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value}ms"


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
