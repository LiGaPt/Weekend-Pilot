from __future__ import annotations

import json
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
from backend.app.benchmark.schemas import BenchmarkRunReport
from backend.app.db.session import SessionLocal, engine
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


SAFE_STOP_GATE_ID = "safe_stop_gate_v1"
SAFE_STOP_SUITE_ID = "recovery_focused"
SAFE_STOP_TRACE_FILENAME = "safe-stop-gate-traces.jsonl"
LATEST_REPORT_FILENAME = f"latest-{SAFE_STOP_GATE_ID}-run-report.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "var" / "formal-benchmarks"
EXPECTED_FAILURE_MODE_COUNTS = {
    "route_unavailable": 1,
    "route_and_dining_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 1,
    "queue_closed_and_budget_constraint": 1,
    "table_unavailable_and_replan_required": 1,
}


class BenchmarkSafeStopGateError(RuntimeError):
    """Raised when the safe-stop gate cannot finish successfully."""


@dataclass(frozen=True)
class BenchmarkSafeStopGateResult:
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
    zero_action_case_count: int
    bounded_case_count: int
    terminal_safe_stop_case_count: int
    multistep_recovery_case_count: int
    failure_mode_counts: dict[str, int]


def run_benchmark_safe_stop_gate(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> BenchmarkSafeStopGateResult:
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    latest_report_path = root / LATEST_REPORT_FILENAME
    suite_result = run_safe_stop_verification(
        output_root=root,
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    raw_payload, report = _load_suite_report(suite_result.suite_report_path)
    summary = report.benchmark_summary
    suite_id = summary.suite_id if summary is not None else suite_result.suite_id
    run_status = report.run_status
    case_count = summary.case_count if summary is not None else suite_result.case_count
    passed_count = summary.passed_count if summary is not None else suite_result.passed_count
    failed_count = summary.failed_count if summary is not None else suite_result.failed_count
    error_count = summary.error_count if summary is not None else suite_result.error_count
    overall_score = summary.overall_score if summary is not None else suite_result.overall_score

    blocking_failures: list[str] = []
    zero_action_case_count = 0
    bounded_case_count = 0
    terminal_safe_stop_case_count = 0
    multistep_recovery_case_count = 0
    failure_mode_counts: dict[str, int] = {}

    if suite_id != SAFE_STOP_SUITE_ID:
        blocking_failures.append(f"Expected suite_id={SAFE_STOP_SUITE_ID!r}, got {suite_id!r}.")
    if run_status != "passed":
        blocking_failures.append(f"Expected run_status='passed', got {run_status!r}.")
    if case_count != 6:
        blocking_failures.append(f"Expected case_count=6, got {case_count}.")
    if passed_count != 6:
        blocking_failures.append(f"Expected passed_count=6, got {passed_count}.")
    if failed_count != 0:
        blocking_failures.append(f"Expected failed_count=0, got {failed_count}.")
    if error_count != 0:
        blocking_failures.append(f"Expected error_count=0, got {error_count}.")

    case_results = getattr(report, "case_results", [])
    for case_result in case_results:
        case_id = getattr(case_result, "case_id", "<unknown>")
        taxonomy = getattr(case_result, "taxonomy", None)
        failure_mode = getattr(taxonomy, "failure_mode", None) or "none"
        failure_mode_counts[failure_mode] = failure_mode_counts.get(failure_mode, 0) + 1

        if getattr(case_result, "workflow_status", None) != "failed":
            blocking_failures.append(f"Case {case_id} workflow_status was not 'failed'.")
        if int(getattr(case_result, "action_count", 0) or 0) == 0:
            zero_action_case_count += 1
        else:
            blocking_failures.append(f"Case {case_id} executed write actions.")

        failure_chain_summary = getattr(case_result, "failure_chain_summary", None)
        if failure_chain_summary is None:
            blocking_failures.append(f"Case {case_id} is missing failure_chain_summary.")
            continue

        if bool(getattr(failure_chain_summary, "bounded", False)):
            bounded_case_count += 1
        else:
            blocking_failures.append(f"Case {case_id} did not end with a bounded recovery chain.")

        recovery_actions = list(getattr(failure_chain_summary, "recovery_actions", []) or [])
        if recovery_actions and recovery_actions[-1] == "stop_safely":
            terminal_safe_stop_case_count += 1
        else:
            blocking_failures.append(f"Case {case_id} did not terminate with stop_safely.")

        if len(recovery_actions) > 1:
            multistep_recovery_case_count += 1

    if zero_action_case_count != 6:
        blocking_failures.append(f"Expected zero_action_case_count=6, got {zero_action_case_count}.")
    if bounded_case_count != 6:
        blocking_failures.append(f"Expected bounded_case_count=6, got {bounded_case_count}.")
    if terminal_safe_stop_case_count != 6:
        blocking_failures.append(
            f"Expected terminal_safe_stop_case_count=6, got {terminal_safe_stop_case_count}."
        )

    multistep_case = next(
        (
            item
            for item in case_results
            if list(getattr(getattr(item, "failure_chain_summary", None), "recovery_actions", []) or [])[-1:]
            == ["stop_safely"]
            and "replace_candidate"
            in list(getattr(getattr(item, "failure_chain_summary", None), "recovery_actions", []) or [])
        ),
        None,
    )
    if multistep_case is None:
        blocking_failures.append(
            "Expected at least one recovery case to include replace_candidate before terminal stop_safely."
        )

    if multistep_recovery_case_count < 1:
        blocking_failures.append(
            f"Expected multistep_recovery_case_count>=1, got {multistep_recovery_case_count}."
        )

    for failure_mode, expected_count in EXPECTED_FAILURE_MODE_COUNTS.items():
        observed = failure_mode_counts.get(failure_mode, 0)
        if observed != expected_count:
            blocking_failures.append(
                f"Expected failure_mode_counts['{failure_mode}']=={expected_count}, got {observed}."
            )

    evaluation_payload = _build_safe_stop_gate_evaluation(
        suite_id=suite_id,
        release_blocked=bool(blocking_failures),
        blocking_failures=blocking_failures,
        zero_action_case_count=zero_action_case_count,
        bounded_case_count=bounded_case_count,
        terminal_safe_stop_case_count=terminal_safe_stop_case_count,
        multistep_recovery_case_count=multistep_recovery_case_count,
        failure_mode_counts=failure_mode_counts,
    )

    report_enriched = False
    enrichment_error = _write_safe_stop_gate_evaluation(suite_result.suite_report_path, evaluation_payload)
    if enrichment_error is not None:
        blocking_failures.append(enrichment_error)
    else:
        report_enriched = True

    if not blocking_failures:
        alias_error = _refresh_latest_alias(suite_result.suite_report_path, latest_report_path)
        if alias_error is not None:
            blocking_failures.append(alias_error)

    if report_enriched and blocking_failures != evaluation_payload["blocking_failures"]:
        final_payload = _build_safe_stop_gate_evaluation(
            suite_id=suite_id,
            release_blocked=bool(blocking_failures),
            blocking_failures=blocking_failures,
            zero_action_case_count=zero_action_case_count,
            bounded_case_count=bounded_case_count,
            terminal_safe_stop_case_count=terminal_safe_stop_case_count,
            multistep_recovery_case_count=multistep_recovery_case_count,
            failure_mode_counts=failure_mode_counts,
        )
        follow_up_error = _write_safe_stop_gate_evaluation(suite_result.suite_report_path, final_payload)
        if follow_up_error is not None:
            blocking_failures.append(follow_up_error)

    return BenchmarkSafeStopGateResult(
        gate_id=SAFE_STOP_GATE_ID,
        suite_id=suite_id,
        release_blocked=bool(blocking_failures),
        blocking_failures=blocking_failures,
        run_status=run_status,
        case_count=case_count,
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        overall_score=overall_score,
        run_directory=suite_result.run_directory,
        suite_report_path=suite_result.suite_report_path,
        latest_report_path=latest_report_path,
        zero_action_case_count=zero_action_case_count,
        bounded_case_count=bounded_case_count,
        terminal_safe_stop_case_count=terminal_safe_stop_case_count,
        multistep_recovery_case_count=multistep_recovery_case_count,
        failure_mode_counts=failure_mode_counts,
    )


def run_safe_stop_verification(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> Any:
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    _bootstrap_runtime(
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    run_directory = root / f"safe-stop-gate-{uuid4()}"
    run_directory.mkdir(parents=True, exist_ok=False)
    trace_buffer_path = run_directory / SAFE_STOP_TRACE_FILENAME
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
        report = harness.run_suite(SAFE_STOP_SUITE_ID)
        report_path_value = getattr(report, "report_path", None)
        if not report_path_value:
            raise BenchmarkSafeStopGateError("Recovery suite did not return a report_path.")
        return type(
            "SafeStopVerificationResult",
            (),
            {
                "suite_id": SAFE_STOP_SUITE_ID,
                "run_status": str(getattr(report, "run_status", "")),
                "case_count": int(getattr(report, "passed_count", 0) or 0)
                + int(getattr(report, "failed_count", 0) or 0)
                + int(getattr(report, "error_count", 0) or 0),
                "passed_count": int(getattr(report, "passed_count", 0) or 0),
                "failed_count": int(getattr(report, "failed_count", 0) or 0),
                "error_count": int(getattr(report, "error_count", 0) or 0),
                "overall_score": float(getattr(report, "overall_score", 0.0) or 0.0),
                "run_directory": run_directory,
                "suite_report_path": Path(report_path_value),
                "trace_buffer_path": trace_buffer_path,
            },
        )()
    finally:
        _close_quietly(session)
        _close_quietly(redis_client)


def main() -> int:
    try:
        result = run_benchmark_safe_stop_gate()
    except BenchmarkSafeStopGateError as exc:
        print(f"Benchmark safe-stop gate failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Benchmark safe-stop gate failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if result.release_blocked:
        print(_format_failure_summary(result), file=sys.stderr)
        return 1

    print(_format_success_summary(result))
    return 0


def _load_suite_report(suite_report_path: Path) -> tuple[dict[str, Any], BenchmarkRunReport]:
    try:
        raw_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkSafeStopGateError(f"Could not read suite report: {suite_report_path}") from exc
    try:
        report = BenchmarkRunReport.model_validate(raw_payload)
    except Exception as exc:
        raise BenchmarkSafeStopGateError(f"Could not validate suite report: {suite_report_path}") from exc
    return raw_payload, report


def _build_safe_stop_gate_evaluation(
    *,
    suite_id: str | None,
    release_blocked: bool,
    blocking_failures: list[str],
    zero_action_case_count: int,
    bounded_case_count: int,
    terminal_safe_stop_case_count: int,
    multistep_recovery_case_count: int,
    failure_mode_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": "weekendpilot_safe_stop_gate_evaluation_v1",
        "gate_id": SAFE_STOP_GATE_ID,
        "suite_id": suite_id,
        "release_blocked": release_blocked,
        "blocking_failures": list(blocking_failures),
        "zero_action_case_count": zero_action_case_count,
        "bounded_case_count": bounded_case_count,
        "terminal_safe_stop_case_count": terminal_safe_stop_case_count,
        "multistep_recovery_case_count": multistep_recovery_case_count,
        "failure_mode_counts": dict(failure_mode_counts),
    }


def _write_safe_stop_gate_evaluation(suite_report_path: Path, evaluation: dict[str, Any]) -> str | None:
    temp_path = suite_report_path.with_name(f"{suite_report_path.name}.tmp")
    try:
        payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        payload["safe_stop_gate_evaluation"] = evaluation
        suite_report_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(suite_report_path)
        return None
    except (OSError, json.JSONDecodeError):
        return f"Could not enrich safe-stop gate report: {suite_report_path}"
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


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


def _format_success_summary(result: BenchmarkSafeStopGateResult) -> str:
    return "\n".join(_build_summary_lines(result, heading="Benchmark safe-stop gate passed."))


def _format_failure_summary(result: BenchmarkSafeStopGateResult) -> str:
    lines = _build_summary_lines(result, heading="Benchmark safe-stop gate failed.")
    lines.append("Blocking failures:")
    lines.extend(f"- {failure}" for failure in result.blocking_failures)
    return "\n".join(lines)


def _build_summary_lines(result: BenchmarkSafeStopGateResult, *, heading: str) -> list[str]:
    return [
        heading,
        f"Gate: {result.gate_id}",
        f"Suite: {result.suite_id}",
        (
            f"Cases: {result.case_count} "
            f"({result.passed_count} passed, {result.failed_count} failed, {result.error_count} error)"
        ),
        f"Overall score: {result.overall_score}",
        f"zero_action_case_count: {result.zero_action_case_count}",
        f"bounded_case_count: {result.bounded_case_count}",
        f"terminal_safe_stop_case_count: {result.terminal_safe_stop_case_count}",
        f"multistep_recovery_case_count: {result.multistep_recovery_case_count}",
        f"Run directory: {result.run_directory}",
        f"Suite report: {result.suite_report_path}",
        f"Latest report: {result.latest_report_path}",
    ]


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
        raise BenchmarkSafeStopGateError(f"{error_context} Could not run: {' '.join(command)}") from exc
    if completed.returncode == 0:
        return
    details = _format_subprocess_details(completed.stdout, completed.stderr)
    message = f"{error_context} Command failed: {' '.join(command)}"
    if details:
        message = f"{message}. {details}"
    raise BenchmarkSafeStopGateError(message)


def _wait_for_postgres(*, timeout_seconds: float, poll_interval_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep(poll_interval_seconds)
    raise BenchmarkSafeStopGateError(
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
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep(poll_interval_seconds)
        finally:
            _close_quietly(client)
    raise BenchmarkSafeStopGateError(
        f"Redis readiness timed out after {timeout_seconds:.1f}s" + _format_last_error(last_error)
    )


def _format_subprocess_details(stdout: str | None, stderr: str | None) -> str:
    details: list[str] = []
    if stdout:
        details.append(f"stdout={stdout.strip()}")
    if stderr:
        details.append(f"stderr={stderr.strip()}")
    return "; ".join(details)


def _format_last_error(last_error: Exception | None) -> str:
    if last_error is None:
        return ""
    return f" Last error: {type(last_error).__name__}: {last_error}"


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        close = getattr(resource, "close", None)
        if callable(close):
            close()
    except Exception:
        pass
