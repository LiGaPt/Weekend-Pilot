from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.fixtures import load_benchmark_case
from backend.app.benchmark.harness import BenchmarkHarness
from backend.app.benchmark.reporting import write_recovery_review_report
from backend.app.benchmark.replay import BenchmarkReplayHarness
from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkReplayCaseResult,
    RecoveryReplayReviewCaseRunSummary,
    RecoveryReplayReviewCheck,
    RecoveryReplayReviewReplaySource,
    RecoveryReplayReviewResult,
    RecoveryReplayReviewRunReport,
    RecoveryReplayReviewSummary,
    RecoveryReplaySummary,
)
from backend.app.benchmark.suites import canonical_benchmark_suite_id, load_benchmark_suite
from backend.app.db.session import SessionLocal, engine
from backend.app.observability import sanitize_trace_payload
from backend.app.observability.service import InternalObservabilityService
from backend.app.observability.schemas import InternalObservabilityRunSummary
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


CANONICAL_CASE_ID = "family_route_failure_v1"
REVIEW_TRACE_FILENAME = "review-traces.jsonl"
REVIEW_FILENAME = "recovery-review.json"
RUN_REPORT_FILENAME = "recovery-review-run.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "var" / "recovery-reviews"
CHECK_BENCHMARK_FAILURE_PATH = "benchmark_failure_path"
CHECK_REPLAY_MATCHES_SOURCE_REPORT = "replay_matches_source_report"
CHECK_OBSERVABILITY_LINKS_SOURCE_REPORT = "observability_links_source_report"
_SENSITIVE_TEXT_PARTS = (
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
    "traceback",
    "stack trace",
    "stack_trace",
)
_FORBIDDEN_KEY_PARTS = (
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
    "action_id",
    "tool_event_id",
    "traceback",
    "stack_trace",
    "stack trace",
)


class RecoveryReplayReviewError(RuntimeError):
    """Raised when the recovery replay review cannot finish successfully."""


def run_recovery_replay_review(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> RecoveryReplayReviewResult:
    report = run_generic_recovery_replay_review(
        output_root=output_root,
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    if len(report.case_results) != 1:
        raise RecoveryReplayReviewError("Expected exactly one case result for canonical recovery replay review.")

    review_artifact_path = Path(report.case_results[0].review_artifact_path)
    try:
        payload = json.loads(review_artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryReplayReviewError(f"Could not read recovery review artifact: {review_artifact_path}") from exc
    return RecoveryReplayReviewResult.model_validate(payload)


def run_generic_recovery_replay_review(
    *,
    case_id: str | None = None,
    suite_id: str | None = None,
    output_root: Path | str | None = None,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> RecoveryReplayReviewRunReport:
    selected_cases, selection_mode, canonical_suite_id = _resolve_selected_cases(case_id=case_id, suite_id=suite_id)
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    _bootstrap_runtime(
        start_services=start_services,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )

    run_directory = root / f"recovery-review-{uuid4()}"
    run_directory.mkdir(parents=True, exist_ok=False)

    passed_count = 0
    failed_count = 0
    error_count = 0
    case_summaries: list[RecoveryReplayReviewCaseRunSummary] = []

    for selected_case in selected_cases:
        case_run_dir = run_directory if selection_mode == "case" else run_directory / "cases" / selected_case.case_id
        case_run_dir.mkdir(parents=True, exist_ok=True)
        result = _run_single_case_review(
            selected_case,
            case_run_dir=case_run_dir,
            root=root,
        )
        review_artifact_path = str(case_run_dir / REVIEW_FILENAME)
        case_summaries.append(
            RecoveryReplayReviewCaseRunSummary(
                case_id=result.case_id,
                status=result.status,
                review_artifact_path=review_artifact_path,
                latest_review_path=result.latest_review_path,
            )
        )
        if result.status == "passed":
            passed_count += 1
        elif result.status == "failed":
            failed_count += 1
        else:
            error_count += 1

    if error_count:
        status = "error"
    elif failed_count:
        status = "failed"
    else:
        status = "passed"

    report = RecoveryReplayReviewRunReport(
        status=status,
        selection_mode=selection_mode,
        case_id=selected_cases[0].case_id if selection_mode == "case" else None,
        suite_id=canonical_suite_id if selection_mode == "suite" else None,
        requested_case_ids=[item.case_id for item in selected_cases],
        run_directory=str(run_directory),
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        case_results=case_summaries,
    )

    report_path = run_directory / RUN_REPORT_FILENAME
    _write_json_report(report.model_dump(mode="json"), report_path)
    return report.model_copy(update={"report_path": str(report_path)})


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        case_id, suite_id, output_root, start_services = _parse_args(args)
        if case_id is None and suite_id is None:
            result = run_recovery_replay_review(
                output_root=output_root,
                start_services=start_services,
            )
            if result.status != "passed":
                print(_format_failure_summary(result), file=sys.stderr)
                return 1
            print(_format_success_summary(result))
            return 0

        report = run_generic_recovery_replay_review(
            case_id=case_id,
            suite_id=suite_id,
            output_root=output_root,
            start_services=start_services,
        )
    except RecoveryReplayReviewError as exc:
        print(f"Recovery replay review failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Recovery replay review failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if report.status != "passed":
        print(_format_run_failure_summary(report), file=sys.stderr)
        return 1

    print(_format_run_success_summary(report))
    return 0


def _parse_args(args: list[str]) -> tuple[str | None, str | None, Path | None, bool]:
    case_id: str | None = None
    suite_id: str | None = None
    output_root: Path | None = None
    start_services = True
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--case-id":
            index += 1
            case_id = args[index] if index < len(args) else None
        elif token == "--suite-id":
            index += 1
            suite_id = args[index] if index < len(args) else None
        elif token == "--output-root":
            index += 1
            output_root = Path(args[index]) if index < len(args) else None
        elif token == "--no-start-services":
            start_services = False
        else:
            raise RecoveryReplayReviewError(f"Unknown argument: {token}")
        index += 1

    if case_id and suite_id:
        raise RecoveryReplayReviewError("--case-id and --suite-id cannot be used together.")
    if args and ((case_id is None and "--case-id" in args) or (suite_id is None and "--suite-id" in args)):
        raise RecoveryReplayReviewError(
            "Usage: [--case-id <case_id> | --suite-id <suite_id>] [--output-root <path>] [--no-start-services]"
        )
    return case_id, suite_id, output_root, start_services


def _resolve_selected_cases(
    *,
    case_id: str | None,
    suite_id: str | None,
) -> tuple[list[BenchmarkCase], str, str | None]:
    if case_id is not None and suite_id is not None:
        raise RecoveryReplayReviewError("--case-id and --suite-id cannot be used together.")

    if suite_id is not None:
        canonical_suite_id = canonical_benchmark_suite_id(suite_id)
        if canonical_suite_id != "recovery_focused":
            raise RecoveryReplayReviewError(f"Unsupported suite_id: {suite_id!r}. v0 supports only 'recovery_focused' or 'failures'.")
        cases = load_benchmark_suite(canonical_suite_id)
        if not cases:
            raise RecoveryReplayReviewError(f"Recovery replay suite {canonical_suite_id!r} is empty.")
        for item in cases:
            _validate_recovery_capable_case(item)
        return cases, "suite", canonical_suite_id

    selected_case_id = case_id or CANONICAL_CASE_ID
    selected_case = load_benchmark_case(selected_case_id)
    _validate_recovery_capable_case(selected_case)
    return [selected_case], "case", None


def _validate_recovery_capable_case(case: BenchmarkCase) -> None:
    if not case.failure_profile:
        raise RecoveryReplayReviewError(f"Case {case.case_id!r} is not recovery-capable: missing failure_profile.")
    if case.expected.expected_workflow_status != "failed":
        raise RecoveryReplayReviewError(f"Case {case.case_id!r} is not recovery-capable: expected_workflow_status must be 'failed'.")
    if not case.expected.expected_recovery_action:
        raise RecoveryReplayReviewError(f"Case {case.case_id!r} is not recovery-capable: expected_recovery_action is required.")
    if case.expected.min_action_count != 0:
        raise RecoveryReplayReviewError(f"Case {case.case_id!r} is not recovery-capable: min_action_count must be 0.")


def _run_single_case_review(
    case: BenchmarkCase,
    *,
    case_run_dir: Path,
    root: Path,
) -> RecoveryReplayReviewResult:
    trace_buffer_path = case_run_dir / REVIEW_TRACE_FILENAME
    latest_review_path = root / f"latest-{case.case_id}-review.json"

    session = None
    redis_client = None
    source_result: BenchmarkCaseResult | None = None
    replay_result: BenchmarkReplayCaseResult | None = None
    observability_summary: InternalObservabilityRunSummary | None = None
    orchestration_error: str | None = None

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
            report_dir=case_run_dir,
            trace_buffer_path=trace_buffer_path,
        )

        source_result = harness.run_case(case)
        if source_result.run_id is None:
            orchestration_error = "Benchmark case did not return a run_id."
        elif not source_result.report_path:
            orchestration_error = "Benchmark case did not return a report_path."
        else:
            replay_harness = BenchmarkReplayHarness(
                harness,
                replay_report_dir=case_run_dir / "replays",
            )
            replay_result = replay_harness.replay_report(source_result.report_path)
            try:
                observability_summary = InternalObservabilityService(session).get_run_summary(source_result.run_id)
            except Exception as exc:  # pragma: no cover
                orchestration_error = f"Internal observability lookup failed: {_sanitize_text(str(exc))}"
    except BenchmarkHarnessError as exc:
        orchestration_error = _sanitize_text(str(exc))
    except Exception as exc:  # pragma: no cover
        orchestration_error = f"{type(exc).__name__}: {_sanitize_text(str(exc))}"
    finally:
        _close_quietly(session)
        _close_quietly(redis_client)

    benchmark_check, expected_signature = _benchmark_failure_path_check(case, source_result, orchestration_error)
    replay_check = _replay_matches_source_report_check(
        case,
        replay_result,
        expected_failure_signature=expected_signature,
        orchestration_error=orchestration_error,
    )
    observability_check, recovery_review = _observability_links_source_report_check(
        case,
        summary=observability_summary,
        source_report_path=getattr(source_result, "report_path", None),
        source_failure_chain_summary=getattr(source_result, "failure_chain_summary", None),
        orchestration_error=orchestration_error,
    )
    checks = [benchmark_check, replay_check, observability_check]

    result = RecoveryReplayReviewResult(
        status=_derive_status(checks, orchestration_error),
        case_id=case.case_id,
        run_id=getattr(source_result, "run_id", None),
        run_directory=str(case_run_dir),
        source_report_path=getattr(source_result, "report_path", None),
        replay_report_path=getattr(replay_result, "replay_report_path", None),
        latest_review_path=str(latest_review_path),
        checks=checks,
        failure_chain_summary=getattr(source_result, "failure_chain_summary", None),
        replay_summary=_build_replay_summary(replay_result),
        recovery_review=recovery_review,
    )

    try:
        review_artifact_path = Path(write_recovery_review_report(result, case_run_dir, filename=REVIEW_FILENAME))
    except BenchmarkHarnessError as exc:
        raise RecoveryReplayReviewError(str(exc)) from exc

    if result.status == "passed":
        copy_error = _refresh_latest_alias(review_artifact_path, latest_review_path)
        if copy_error is not None:
            raise RecoveryReplayReviewError(copy_error)

    return result


def _build_replay_summary(replay_result: BenchmarkReplayCaseResult | None) -> RecoveryReplaySummary:
    if replay_result is None:
        return RecoveryReplaySummary()

    signature = list(replay_result.source.failure_chain_signature)
    if not signature:
        signature = list(replay_result.replay.failure_chain_signature)

    return RecoveryReplaySummary(
        status=replay_result.status,
        mismatch_count=len(replay_result.mismatches),
        failure_chain_signature=signature,
    )


def _build_recovery_review_summary(
    summary: InternalObservabilityRunSummary | None,
) -> RecoveryReplayReviewSummary | None:
    if summary is None or summary.recovery_path_summary is None:
        return None

    replay_source = None
    if summary.recovery_path_summary.replay_source is not None:
        replay_source = RecoveryReplayReviewReplaySource(
            case_id=summary.recovery_path_summary.replay_source.case_id,
            benchmark_report_path=summary.recovery_path_summary.replay_source.benchmark_report_path,
        )

    recovery_actions = [
        attempt.recovery_action
        for attempt in summary.recovery_path_summary.attempts
        if isinstance(attempt.recovery_action, str)
    ]
    benchmark_report_path = None
    if summary.benchmark_artifact_summary is not None:
        benchmark_report_path = summary.benchmark_artifact_summary.report_path

    return RecoveryReplayReviewSummary(
        benchmark_report_path=benchmark_report_path,
        attempt_count=summary.recovery_path_summary.attempt_count,
        max_attempts=summary.recovery_path_summary.max_attempts,
        recovery_actions=recovery_actions,
        replay_source=replay_source,
    )


def _benchmark_failure_path_check(
    case: BenchmarkCase,
    source_result: BenchmarkCaseResult | None,
    orchestration_error: str | None,
) -> tuple[RecoveryReplayReviewCheck, list[str]]:
    if source_result is None:
        detail = "Source benchmark did not complete."
        if orchestration_error:
            detail = f"{detail} {orchestration_error}"
        return (
            RecoveryReplayReviewCheck(
                name=CHECK_BENCHMARK_FAILURE_PATH,
                passed=False,
                detail=detail,
            ),
            [],
        )

    summary = source_result.failure_chain_summary
    failure_reasons: list[str] = []
    expected_signature = list(summary.injected_effects) if summary is not None else []
    if source_result.status != "passed":
        failure_reasons.append(f"benchmark status={source_result.status!r}")
    if source_result.workflow_status != case.expected.expected_workflow_status:
        failure_reasons.append(f"workflow_status={source_result.workflow_status!r}")
    if source_result.action_count != 0:
        failure_reasons.append(f"action_count={source_result.action_count}")
    if summary is None:
        failure_reasons.append("failure_chain_summary missing")
    else:
        expected_signature = list(summary.injected_effects)
        if summary.profile_id != case.failure_profile:
            failure_reasons.append(f"profile_id={summary.profile_id!r}")
        if not summary.injected_effects:
            failure_reasons.append("injected_effects missing")
        elif _observed_injected_failure_count(source_result, summary) < case.expected.min_injected_failure_count:
            failure_reasons.append(
                f"injected_effects_count={_observed_injected_failure_count(source_result, summary)} expected>={case.expected.min_injected_failure_count}"
            )
        if list(summary.recovery_actions) != [case.expected.expected_recovery_action]:
            failure_reasons.append(f"recovery_actions={list(summary.recovery_actions)!r}")
        if summary.bounded is not True:
            failure_reasons.append(f"bounded={summary.bounded!r}")

    if not failure_reasons:
        return (
            RecoveryReplayReviewCheck(
                name=CHECK_BENCHMARK_FAILURE_PATH,
                passed=True,
                detail="Benchmark passed while workflow failed safely with zero actions.",
            ),
            expected_signature,
        )

    return (
        RecoveryReplayReviewCheck(
            name=CHECK_BENCHMARK_FAILURE_PATH,
            passed=False,
            detail="Source benchmark drifted: " + "; ".join(failure_reasons),
        ),
        expected_signature,
    )


def _observed_injected_failure_count(source_result: BenchmarkCaseResult, summary: Any) -> int:
    observed_count = len(getattr(summary, "injected_effects", []) or [])
    for score in getattr(source_result, "scores", []):
        if getattr(score, "name", None) != "failure_injection":
            continue
        details = getattr(score, "details", None) or {}
        injected_count = details.get("injected_failure_count")
        if isinstance(injected_count, int):
            observed_count = max(observed_count, injected_count)
    return observed_count


def _replay_matches_source_report_check(
    case: BenchmarkCase,
    replay_result: BenchmarkReplayCaseResult | None,
    *,
    expected_failure_signature: list[str],
    orchestration_error: str | None,
) -> RecoveryReplayReviewCheck:
    if replay_result is None:
        detail = "Replay did not complete."
        if orchestration_error:
            detail = f"{detail} {orchestration_error}"
        return RecoveryReplayReviewCheck(
            name=CHECK_REPLAY_MATCHES_SOURCE_REPORT,
            passed=False,
            detail=detail,
        )

    failure_reasons: list[str] = []
    if replay_result.status != "passed":
        failure_reasons.append(f"status={replay_result.status!r}")
    if replay_result.mismatches:
        failure_reasons.append(
            "mismatches=" + ",".join(str(item.field) for item in replay_result.mismatches)
        )
    if replay_result.replay_benchmark_status != "passed":
        failure_reasons.append(f"replay_benchmark_status={replay_result.replay_benchmark_status!r}")
    if replay_result.source.workflow_status != case.expected.expected_workflow_status:
        failure_reasons.append(f"source.workflow_status={replay_result.source.workflow_status!r}")
    if replay_result.replay.workflow_status != case.expected.expected_workflow_status:
        failure_reasons.append(f"replay.workflow_status={replay_result.replay.workflow_status!r}")
    if list(replay_result.source.failure_chain_signature) != expected_failure_signature:
        failure_reasons.append(
            "source.failure_chain_signature="
            + repr(list(replay_result.source.failure_chain_signature))
        )
    if list(replay_result.replay.failure_chain_signature) != expected_failure_signature:
        failure_reasons.append(
            "replay.failure_chain_signature="
            + repr(list(replay_result.replay.failure_chain_signature))
        )

    if not failure_reasons:
        return RecoveryReplayReviewCheck(
            name=CHECK_REPLAY_MATCHES_SOURCE_REPORT,
            passed=True,
            detail="Replay passed with zero mismatches against the written source report.",
        )

    return RecoveryReplayReviewCheck(
        name=CHECK_REPLAY_MATCHES_SOURCE_REPORT,
        passed=False,
        detail="Replay drifted from source report: " + "; ".join(failure_reasons),
    )


def _observability_links_source_report_check(
    case: BenchmarkCase,
    *,
    summary: InternalObservabilityRunSummary | None,
    source_report_path: str | None,
    source_failure_chain_summary: Any,
    orchestration_error: str | None,
) -> tuple[RecoveryReplayReviewCheck, RecoveryReplayReviewSummary | None]:
    recovery_review = _build_recovery_review_summary(summary)
    if summary is None:
        detail = "Internal observability summary was not available."
        if orchestration_error:
            detail = f"{detail} {orchestration_error}"
        return (
            RecoveryReplayReviewCheck(
                name=CHECK_OBSERVABILITY_LINKS_SOURCE_REPORT,
                passed=False,
                detail=detail,
            ),
            recovery_review,
        )

    benchmark_artifact = summary.benchmark_artifact_summary
    recovery_path = summary.recovery_path_summary
    failure_reasons: list[str] = []
    if benchmark_artifact is None:
        failure_reasons.append("benchmark_artifact_summary missing")
    else:
        if benchmark_artifact.case_id != case.case_id:
            failure_reasons.append(f"benchmark_artifact_summary.case_id={benchmark_artifact.case_id!r}")
        if benchmark_artifact.report_path != source_report_path:
            failure_reasons.append(
                "benchmark_artifact_summary.report_path="
                + repr(benchmark_artifact.report_path)
            )

    if recovery_path is None:
        failure_reasons.append("recovery_path_summary missing")
    else:
        if recovery_path.attempt_count < 1:
            failure_reasons.append(f"attempt_count={recovery_path.attempt_count}")
        expected_max_attempts = getattr(source_failure_chain_summary, "max_attempts", None)
        if expected_max_attempts is not None and recovery_path.max_attempts != expected_max_attempts:
            failure_reasons.append(f"max_attempts={recovery_path.max_attempts}")
        if not recovery_path.attempts:
            failure_reasons.append("attempts missing")
        else:
            final_attempt = recovery_path.attempts[-1]
            if final_attempt.recovery_action != case.expected.expected_recovery_action:
                failure_reasons.append(f"final_attempt.recovery_action={final_attempt.recovery_action!r}")
            if case.expected.expected_recovery_action == "stop_safely" and final_attempt.status != "stopped":
                failure_reasons.append(f"final_attempt.status={final_attempt.status!r}")
        replay_source = recovery_path.replay_source
        if replay_source is None:
            failure_reasons.append("replay_source missing")
        else:
            if replay_source.case_id != case.case_id:
                failure_reasons.append(f"replay_source.case_id={replay_source.case_id!r}")
            if replay_source.benchmark_report_path != source_report_path:
                failure_reasons.append(
                    "replay_source.benchmark_report_path="
                    + repr(replay_source.benchmark_report_path)
                )

    if not failure_reasons:
        return (
            RecoveryReplayReviewCheck(
                name=CHECK_OBSERVABILITY_LINKS_SOURCE_REPORT,
                passed=True,
                detail="Internal benchmark and recovery metadata both point to the same source report path.",
            ),
            recovery_review,
        )

    return (
        RecoveryReplayReviewCheck(
            name=CHECK_OBSERVABILITY_LINKS_SOURCE_REPORT,
            passed=False,
            detail="Observability metadata drifted from source report: " + "; ".join(failure_reasons),
        ),
        recovery_review,
    )


def _derive_status(
    checks: list[RecoveryReplayReviewCheck],
    orchestration_error: str | None,
) -> str:
    if orchestration_error is not None:
        return "error"
    if all(check.passed for check in checks):
        return "passed"
    return "failed"


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
        raise RecoveryReplayReviewError(f"{error_context} Could not run: {' '.join(command)}") from exc

    if completed.returncode == 0:
        return

    details = _format_subprocess_details(completed.stdout, completed.stderr)
    message = f"{error_context} Command failed: {' '.join(command)}"
    if details:
        message = f"{message}. {details}"
    raise RecoveryReplayReviewError(message)


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
    raise RecoveryReplayReviewError(
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
    raise RecoveryReplayReviewError(
        f"Redis readiness timed out after {timeout_seconds:.1f}s" + _format_last_error(last_error)
    )


def _refresh_latest_alias(review_artifact_path: Path, latest_review_path: Path) -> str | None:
    temp_path = latest_review_path.with_name(f"{latest_review_path.name}.tmp")
    try:
        latest_review_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(review_artifact_path, temp_path)
        temp_path.replace(latest_review_path)
        return None
    except OSError:
        return f"Could not refresh latest review alias: {latest_review_path}"
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _write_json_report(payload: dict[str, Any], report_path: Path) -> None:
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = _drop_forbidden_keys(sanitize_trace_payload(payload))
        report_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        raise RecoveryReplayReviewError(f"Could not write recovery review run report: {report_path}") from exc


def _drop_forbidden_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_forbidden_keys(item)
            for key, item in value.items()
            if not any(part in str(key).casefold() for part in _FORBIDDEN_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_drop_forbidden_keys(item) for item in value]
    return value


def _format_success_summary(result: RecoveryReplayReviewResult) -> str:
    return "\n".join(
        [
            "Recovery replay review passed.",
            f"Case: {result.case_id}",
            f"Run ID: {result.run_id}",
            f"Run directory: {result.run_directory}",
            f"Source report: {result.source_report_path}",
            f"Replay report: {result.replay_report_path}",
            f"Review artifact: {Path(result.run_directory) / REVIEW_FILENAME}",
            f"Latest review: {result.latest_review_path}",
        ]
    )


def _format_failure_summary(result: RecoveryReplayReviewResult) -> str:
    lines = [
        "Recovery replay review failed.",
        f"Case: {result.case_id}",
        f"Run ID: {result.run_id}",
        f"Status: {result.status}",
        f"Run directory: {result.run_directory}",
        f"Source report: {result.source_report_path}",
        f"Replay report: {result.replay_report_path}",
        f"Review artifact: {Path(result.run_directory) / REVIEW_FILENAME}",
        f"Latest review: {result.latest_review_path}",
        "Checks:",
    ]
    lines.extend(
        f"- {check.name}: {'passed' if check.passed else 'failed'} - {check.detail}"
        for check in result.checks
    )
    return "\n".join(lines)


def _format_run_success_summary(report: RecoveryReplayReviewRunReport) -> str:
    lines = [
        "Generic recovery replay review passed.",
        f"Selection mode: {report.selection_mode}",
    ]
    if report.case_id is not None:
        lines.append(f"Case: {report.case_id}")
    if report.suite_id is not None:
        lines.append(f"Suite: {report.suite_id}")
    lines.extend(
        [
            f"Run directory: {report.run_directory}",
            f"Run report: {report.report_path}",
            f"Passed: {report.passed_count}",
            f"Failed: {report.failed_count}",
            f"Errored: {report.error_count}",
        ]
    )
    lines.extend(
        f"- {item.case_id}: {item.status} ({item.review_artifact_path})"
        for item in report.case_results
    )
    return "\n".join(lines)


def _format_run_failure_summary(report: RecoveryReplayReviewRunReport) -> str:
    lines = [
        "Generic recovery replay review failed.",
        f"Selection mode: {report.selection_mode}",
    ]
    if report.case_id is not None:
        lines.append(f"Case: {report.case_id}")
    if report.suite_id is not None:
        lines.append(f"Suite: {report.suite_id}")
    lines.extend(
        [
            f"Status: {report.status}",
            f"Run directory: {report.run_directory}",
            f"Run report: {report.report_path}",
            f"Passed: {report.passed_count}",
            f"Failed: {report.failed_count}",
            f"Errored: {report.error_count}",
        ]
    )
    lines.extend(
        f"- {item.case_id}: {item.status} ({item.review_artifact_path})"
        for item in report.case_results
    )
    return "\n".join(lines)


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


def _sanitize_text(value: str) -> str:
    sanitized = value
    for fragment in _SENSITIVE_TEXT_PARTS:
        sanitized = sanitized.replace(fragment, "[redacted]")
        sanitized = sanitized.replace(fragment.upper(), "[redacted]")
        sanitized = sanitized.replace(fragment.title(), "[redacted]")
    return sanitized


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()
