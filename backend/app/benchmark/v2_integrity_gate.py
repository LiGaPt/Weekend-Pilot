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
from backend.app.benchmark.formal_verification import FormalVerificationResult
from backend.app.benchmark.schemas import BenchmarkRunReport
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal, engine
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


V2_INTEGRITY_GATE_ID = "v2_integrity_gate"
V2_INTEGRITY_SUITE_ID = "v2_integrity"
V2_INTEGRITY_TRACE_FILENAME = "v2-integrity-gate-traces.jsonl"
LATEST_REPORT_FILENAME = f"latest-{V2_INTEGRITY_GATE_ID}-run-report.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "var" / "formal-benchmarks"
MINIMUM_CASE_COUNT = 20
MINIMUM_MEMORY_CASE_COUNT = 6
MINIMUM_RECOVERY_CASE_COUNT = 8
MINIMUM_CONTINUATION_CASE_COUNT = 2
MINIMUM_ROBUSTNESS_CASE_COUNT = 4
MINIMUM_L4_CASE_COUNT = 1
EXPECTED_MEMORY_MODE_COUNTS = {
    "advisory_fill": 1,
    "candidate_not_auto_active": 1,
    "disabled_ignored": 1,
    "expired_advisory": 1,
    "none": 14,
    "override_guarded": 1,
    "sensitive_minimization": 1,
}
EXPECTED_CONVERSATION_MODE_COUNTS = {
    "clarification": 1,
    "replan_versioned": 2,
    "single_turn": 17,
}
EXPECTED_FAILURE_MODE_COUNTS = {
    "none": 12,
    "queue_closed_and_budget_constraint": 1,
    "route_and_dining_unavailable": 2,
    "route_unavailable": 1,
    "table_unavailable_and_replan_required": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 2,
}
EXPECTED_TOOL_PROFILE_COUNTS = {"mock_world": 20}


class BenchmarkV2IntegrityGateError(RuntimeError):
    """Raised when the benchmark v2 integrity gate cannot finish successfully."""


@dataclass(frozen=True)
class BenchmarkV2IntegrityGateResult:
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
    integrity_coverage_summary: dict[str, int]
    memory_mode_counts: dict[str, int]
    conversation_mode_counts: dict[str, int]
    failure_mode_counts: dict[str, int]
    trace_buffer_path: Path | None = None


def run_benchmark_v2_integrity_gate(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    refresh_latest_alias: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> BenchmarkV2IntegrityGateResult:
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    latest_report_path = root / LATEST_REPORT_FILENAME

    try:
        suite_result = run_formal_verification(
            output_root=root,
            start_services=start_services,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except Exception as exc:
        raise BenchmarkV2IntegrityGateError(f"V2 integrity suite run failed: {exc}") from exc

    raw_payload, report = _load_suite_report(suite_result.suite_report_path)
    return _finalize_v2_integrity_gate_result(
        raw_payload=raw_payload,
        report=report,
        run_directory=suite_result.run_directory,
        suite_report_path=suite_result.suite_report_path,
        latest_report_path=latest_report_path,
        trace_buffer_path=suite_result.trace_buffer_path,
        refresh_latest_alias=refresh_latest_alias,
    )


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

    run_directory = root / f"v2-integrity-gate-{uuid4()}"
    run_directory.mkdir(parents=True, exist_ok=False)
    trace_buffer_path = run_directory / V2_INTEGRITY_TRACE_FILENAME
    workflow_settings = _build_v2_integrity_workflow_settings()

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
        report = harness.run_suite(V2_INTEGRITY_SUITE_ID)
        report_path_value = getattr(report, "report_path", None)
        if not report_path_value:
            raise BenchmarkV2IntegrityGateError("Benchmark suite did not return a report_path.")
        return FormalVerificationResult(
            suite_id=V2_INTEGRITY_SUITE_ID,
            run_status=str(getattr(report, "run_status", "")),
            case_count=int(getattr(report, "passed_count", 0) or 0)
            + int(getattr(report, "failed_count", 0) or 0)
            + int(getattr(report, "error_count", 0) or 0),
            passed_count=int(getattr(report, "passed_count", 0) or 0),
            failed_count=int(getattr(report, "failed_count", 0) or 0),
            error_count=int(getattr(report, "error_count", 0) or 0),
            overall_score=float(getattr(report, "overall_score", 0.0) or 0.0),
            run_directory=run_directory,
            suite_report_path=Path(report_path_value),
            latest_report_path=Path(report_path_value),
            trace_buffer_path=trace_buffer_path,
        )
    finally:
        _close_quietly(session)
        _close_quietly(redis_client)


def main() -> int:
    try:
        result = run_benchmark_v2_integrity_gate()
    except BenchmarkV2IntegrityGateError as exc:
        print(f"Benchmark v2 integrity gate failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Benchmark v2 integrity gate failed: {type(exc).__name__}: {exc}", file=sys.stderr)
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


def _build_v2_integrity_workflow_settings(source: Settings | None = None) -> Settings:
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
        raise BenchmarkV2IntegrityGateError(f"{error_context} Could not run: {' '.join(command)}") from exc

    if completed.returncode == 0:
        return

    details = _format_subprocess_details(completed.stdout, completed.stderr)
    message = f"{error_context} Command failed: {' '.join(command)}"
    if details:
        message = f"{message}. {details}"
    raise BenchmarkV2IntegrityGateError(message)


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
    raise BenchmarkV2IntegrityGateError(
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
    raise BenchmarkV2IntegrityGateError(
        f"Redis readiness timed out after {timeout_seconds:.1f}s" + _format_last_error(last_error)
    )


def _finalize_v2_integrity_gate_result(
    *,
    raw_payload: dict[str, Any],
    report: Any,
    run_directory: Path,
    suite_report_path: Path,
    latest_report_path: Path,
    trace_buffer_path: Path,
    refresh_latest_alias: bool,
) -> BenchmarkV2IntegrityGateResult:
    summary = getattr(report, "benchmark_summary", None)
    suite_id = getattr(summary, "suite_id", None)
    run_status = str(getattr(report, "run_status", ""))
    case_count = int(getattr(summary, "case_count", 0) or 0)
    passed_count = int(getattr(summary, "passed_count", 0) or 0)
    failed_count = int(getattr(summary, "failed_count", getattr(report, "failed_count", 0)) or 0)
    error_count = int(getattr(summary, "error_count", getattr(report, "error_count", 0)) or 0)
    overall_score = float(getattr(summary, "overall_score", getattr(report, "overall_score", 0.0)) or 0.0)
    blocking_failures: list[str] = []
    integrity_summary = {}
    memory_mode_counts = {}
    conversation_mode_counts = {}
    failure_mode_counts = {}
    matrix_summary = None

    if suite_id != V2_INTEGRITY_SUITE_ID:
        blocking_failures.append(f"Expected suite_id={V2_INTEGRITY_SUITE_ID!r}, got {suite_id!r}.")
    if run_status != "passed":
        blocking_failures.append(f"Expected run_status='passed', got {run_status!r}.")
    if case_count < MINIMUM_CASE_COUNT:
        blocking_failures.append(f"Expected case_count>={MINIMUM_CASE_COUNT}, got {case_count}.")
    if passed_count != case_count:
        blocking_failures.append(f"Expected passed_count={case_count}, got {passed_count}.")
    if failed_count != 0:
        blocking_failures.append(f"Expected failed_count=0, got {failed_count}.")
    if error_count != 0:
        blocking_failures.append(f"Expected error_count=0, got {error_count}.")

    if summary is None:
        blocking_failures.append("Missing benchmark_summary.")
    else:
        matrix_summary = summary.matrix_summary
        v2_taxonomy_summary = summary.v2_taxonomy_summary
        integrity_model = getattr(summary, "integrity_coverage_summary", None)

        if matrix_summary is None:
            blocking_failures.append("Missing benchmark_summary.matrix_summary.")
        else:
            tool_profile_counts = _coerce_count_map(matrix_summary.tool_profile_counts)
            if tool_profile_counts != {"mock_world": case_count}:
                blocking_failures.append(
                    f"Expected matrix_summary.tool_profile_counts={{'mock_world': {case_count}}}, got {tool_profile_counts}."
                )

        if v2_taxonomy_summary is None:
            blocking_failures.append("Missing benchmark_summary.v2_taxonomy_summary.")
        else:
            memory_mode_counts = _coerce_count_map(v2_taxonomy_summary.memory_mode_counts)
            conversation_mode_counts = _coerce_count_map(v2_taxonomy_summary.conversation_mode_counts)
            failure_mode_counts = _coerce_count_map(v2_taxonomy_summary.failure_mode_counts)

        if integrity_model is None:
            blocking_failures.append("Missing benchmark_summary.integrity_coverage_summary.")
        else:
            integrity_payload = integrity_model.model_dump(mode="json")
            integrity_payload.pop("schema_version", None)
            integrity_summary = _coerce_count_map(integrity_payload)

    blocking_failures.extend(
        _evaluate_minimums(
            "integrity_coverage_summary",
            integrity_summary,
            {
                "case_count": MINIMUM_CASE_COUNT,
                "memory_case_count": MINIMUM_MEMORY_CASE_COUNT,
                "recovery_case_count": MINIMUM_RECOVERY_CASE_COUNT,
                "continuation_case_count": MINIMUM_CONTINUATION_CASE_COUNT,
                "robustness_case_count": MINIMUM_ROBUSTNESS_CASE_COUNT,
                "l4_case_count": MINIMUM_L4_CASE_COUNT,
            },
        )
    )
    blocking_failures.extend(
        _evaluate_minimums("memory_mode_counts", memory_mode_counts, EXPECTED_MEMORY_MODE_COUNTS)
    )
    blocking_failures.extend(
        _evaluate_minimums("conversation_mode_counts", conversation_mode_counts, EXPECTED_CONVERSATION_MODE_COUNTS)
    )
    blocking_failures.extend(
        _evaluate_minimums("failure_mode_counts", failure_mode_counts, EXPECTED_FAILURE_MODE_COUNTS)
    )
    if matrix_summary is not None:
        tool_profile_counts = _coerce_count_map(matrix_summary.tool_profile_counts)
        if tool_profile_counts != EXPECTED_TOOL_PROFILE_COUNTS:
            blocking_failures.append(
                f"Expected matrix_summary.tool_profile_counts={EXPECTED_TOOL_PROFILE_COUNTS}, got {tool_profile_counts}."
            )

    evaluation_payload = _build_v2_integrity_gate_evaluation(
        suite_id=suite_id,
        release_blocked=bool(blocking_failures),
        blocking_failures=blocking_failures,
        integrity_coverage_summary=integrity_summary,
        memory_mode_counts=memory_mode_counts,
        conversation_mode_counts=conversation_mode_counts,
        failure_mode_counts=failure_mode_counts,
    )

    report_enriched = False
    enrichment_error = _write_v2_integrity_gate_evaluation(suite_report_path, evaluation_payload)
    if enrichment_error is not None:
        blocking_failures.append(enrichment_error)
    else:
        report_enriched = True

    if refresh_latest_alias and not blocking_failures:
        alias_error = _refresh_latest_alias(suite_report_path, latest_report_path)
        if alias_error is not None:
            blocking_failures.append(alias_error)

    if report_enriched and blocking_failures != evaluation_payload["blocking_failures"]:
        final_payload = _build_v2_integrity_gate_evaluation(
            suite_id=suite_id,
            release_blocked=bool(blocking_failures),
            blocking_failures=blocking_failures,
            integrity_coverage_summary=integrity_summary,
            memory_mode_counts=memory_mode_counts,
            conversation_mode_counts=conversation_mode_counts,
            failure_mode_counts=failure_mode_counts,
        )
        follow_up_error = _write_v2_integrity_gate_evaluation(suite_report_path, final_payload)
        if follow_up_error is not None:
            blocking_failures.append(follow_up_error)

    return BenchmarkV2IntegrityGateResult(
        gate_id=V2_INTEGRITY_GATE_ID,
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
        integrity_coverage_summary=integrity_summary,
        memory_mode_counts=memory_mode_counts,
        conversation_mode_counts=conversation_mode_counts,
        failure_mode_counts=failure_mode_counts,
    )


def _build_v2_integrity_gate_evaluation(
    *,
    suite_id: str | None,
    release_blocked: bool,
    blocking_failures: list[str],
    integrity_coverage_summary: dict[str, int],
    memory_mode_counts: dict[str, int],
    conversation_mode_counts: dict[str, int],
    failure_mode_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": "weekendpilot_v2_integrity_gate_evaluation_v1",
        "gate_id": V2_INTEGRITY_GATE_ID,
        "suite_id": suite_id,
        "release_blocked": release_blocked,
        "blocking_failures": list(blocking_failures),
        "coverage_thresholds": {
            "minimum_case_count": MINIMUM_CASE_COUNT,
            "minimum_memory_case_count": MINIMUM_MEMORY_CASE_COUNT,
            "minimum_recovery_case_count": MINIMUM_RECOVERY_CASE_COUNT,
            "minimum_continuation_case_count": MINIMUM_CONTINUATION_CASE_COUNT,
            "minimum_robustness_case_count": MINIMUM_ROBUSTNESS_CASE_COUNT,
            "minimum_l4_case_count": MINIMUM_L4_CASE_COUNT,
            "memory_mode_minimums": dict(EXPECTED_MEMORY_MODE_COUNTS),
            "conversation_mode_minimums": dict(EXPECTED_CONVERSATION_MODE_COUNTS),
            "failure_mode_minimums": dict(EXPECTED_FAILURE_MODE_COUNTS),
            "tool_profile_counts": dict(EXPECTED_TOOL_PROFILE_COUNTS),
        },
        "observed_coverage": {
            "integrity_coverage_summary": dict(integrity_coverage_summary),
            "memory_mode_counts": dict(memory_mode_counts),
            "conversation_mode_counts": dict(conversation_mode_counts),
            "failure_mode_counts": dict(failure_mode_counts),
        },
    }


def _load_suite_report(suite_report_path: Path) -> tuple[dict[str, Any], BenchmarkRunReport]:
    try:
        raw_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkV2IntegrityGateError(f"Could not read suite report: {suite_report_path}") from exc

    try:
        report = BenchmarkRunReport.model_validate(raw_payload)
    except Exception as exc:
        raise BenchmarkV2IntegrityGateError(f"Could not validate suite report: {suite_report_path}") from exc

    return raw_payload, report


def _write_v2_integrity_gate_evaluation(suite_report_path: Path, evaluation: dict[str, Any]) -> str | None:
    temp_path = suite_report_path.with_name(f"{suite_report_path.name}.tmp")
    try:
        payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        payload["v2_integrity_gate_evaluation"] = evaluation
        suite_report_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(suite_report_path)
        return None
    except (OSError, json.JSONDecodeError):
        return f"Could not enrich v2 integrity gate report: {suite_report_path}"
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


def _format_success_summary(result: BenchmarkV2IntegrityGateResult) -> str:
    return "\n".join(_build_summary_lines(result, heading="Benchmark v2 integrity gate passed."))


def _format_failure_summary(result: BenchmarkV2IntegrityGateResult) -> str:
    lines = _build_summary_lines(result, heading="Benchmark v2 integrity gate failed.")
    lines.append("Blocking failures:")
    lines.extend(f"- {failure}" for failure in result.blocking_failures)
    return "\n".join(lines)


def _build_summary_lines(result: BenchmarkV2IntegrityGateResult, *, heading: str) -> list[str]:
    lines = [
        heading,
        f"Gate: {result.gate_id}",
        f"Suite: {result.suite_id}",
        (
            f"Cases: {result.case_count} "
            f"({result.passed_count} passed, {result.failed_count} failed, {result.error_count} error)"
        ),
        f"Overall score: {result.overall_score}",
    ]
    for key in (
        "case_count",
        "memory_case_count",
        "recovery_case_count",
        "continuation_case_count",
        "robustness_case_count",
        "l4_case_count",
    ):
        lines.append(f"{key}: {result.integrity_coverage_summary.get(key)}")
    lines.extend(
        [
            f"Run directory: {result.run_directory}",
            f"Suite report: {result.suite_report_path}",
            f"Latest report: {result.latest_report_path}",
        ]
    )
    return lines


def _evaluate_minimums(
    label: str,
    observed_counts: dict[str, int],
    required_counts: dict[str, int],
) -> list[str]:
    failures: list[str] = []
    for key, minimum in required_counts.items():
        observed = int(observed_counts.get(key, 0))
        if observed < minimum:
            failures.append(f"Expected {label}['{key}']>={minimum}, got {observed}.")
    return failures


def _coerce_count_map(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(key): int(count) for key, count in value.items()}
    if hasattr(value, "model_dump"):
        return _coerce_count_map(value.model_dump(mode="json"))
    return {}


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


if __name__ == "__main__":
    raise SystemExit(main())
