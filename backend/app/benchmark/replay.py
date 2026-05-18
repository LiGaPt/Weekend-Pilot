from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from pydantic import ValidationError

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.fixtures import load_benchmark_case
from backend.app.benchmark.reporting import write_replay_case_report, write_replay_run_report
from backend.app.benchmark.schemas import (
    BenchmarkCaseResult,
    BenchmarkReplayCaseResult,
    BenchmarkReplayMismatch,
    BenchmarkReplayRunReport,
    BenchmarkReplaySummary,
)


_COMPARE_FIELDS = (
    "status",
    "workflow_status",
    "observed_tool_names",
    "action_count",
    "injected_failure_count",
    "recovery_actions",
)
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


class BenchmarkReplayHarness:
    replay_harness_version = "locallife_bench_replay_harness_v0"

    def __init__(
        self,
        benchmark_harness: Any,
        replay_report_dir: Path | str = "var/benchmark-replays",
    ) -> None:
        self.benchmark_harness = benchmark_harness
        self.replay_report_dir = Path(replay_report_dir)

    def replay_result(self, source_result: BenchmarkCaseResult) -> BenchmarkReplayCaseResult:
        return self._replay_result(
            source_result,
            benchmark_report_path=source_result.report_path,
        )

    def replay_report(self, source_report_path: Path | str) -> BenchmarkReplayCaseResult:
        path = Path(source_report_path)
        source_result = self._load_source_report(path)
        return self._replay_result(source_result, benchmark_report_path=str(path))

    def replay_results(
        self,
        source_results: Sequence[BenchmarkCaseResult],
    ) -> BenchmarkReplayRunReport:
        results = [self.replay_result(source_result) for source_result in source_results]
        return self._run_report(results)

    def replay_reports(
        self,
        source_report_paths: Sequence[Path | str],
    ) -> BenchmarkReplayRunReport:
        results = [self.replay_report(path) for path in source_report_paths]
        report = self._run_report(results)
        write_replay_run_report(report, self.replay_report_dir)
        return report

    def _replay_result(
        self,
        source_result: BenchmarkCaseResult,
        benchmark_report_path: str | None,
    ) -> BenchmarkReplayCaseResult:
        source_summary = stable_replay_summary(source_result)
        case = load_benchmark_case(source_result.case_id)
        try:
            replayed_result = self.benchmark_harness.run_case(case)
        except BenchmarkHarnessError:
            raise
        except Exception as exc:
            result = BenchmarkReplayCaseResult(
                case_id=source_result.case_id,
                status="error",
                source=source_summary,
                replay=BenchmarkReplaySummary(status="error"),
                mismatches=[],
                replay_benchmark_status="error",
                benchmark_report_path=benchmark_report_path,
                failure_reasons=[_safe_failure_reason(exc)],
            )
            report_path = write_replay_case_report(result, self.replay_report_dir)
            return result.model_copy(update={"replay_report_path": report_path})

        replay_summary = stable_replay_summary(replayed_result)
        if replayed_result.status == "error":
            result = BenchmarkReplayCaseResult(
                case_id=source_result.case_id,
                status="error",
                source=source_summary,
                replay=replay_summary,
                mismatches=[],
                replay_benchmark_status=replayed_result.status,
                benchmark_report_path=benchmark_report_path,
                failure_reasons=[_sanitize_text(reason) for reason in replayed_result.failure_reasons],
            )
            report_path = write_replay_case_report(result, self.replay_report_dir)
            return result.model_copy(update={"replay_report_path": report_path})

        mismatches = _compare_summaries(source_summary, replay_summary)
        result = BenchmarkReplayCaseResult(
            case_id=source_result.case_id,
            status="passed" if not mismatches else "failed",
            source=source_summary,
            replay=replay_summary,
            mismatches=mismatches,
            replay_benchmark_status=replayed_result.status,
            benchmark_report_path=benchmark_report_path,
        )
        report_path = write_replay_case_report(result, self.replay_report_dir)
        return result.model_copy(update={"replay_report_path": report_path})

    def _load_source_report(self, source_report_path: Path) -> BenchmarkCaseResult:
        try:
            payload = json.loads(source_report_path.read_text(encoding="utf-8"))
            return BenchmarkCaseResult.model_validate(payload)
        except FileNotFoundError as exc:
            raise BenchmarkHarnessError(f"Benchmark replay source report not found: {source_report_path}") from exc
        except json.JSONDecodeError as exc:
            raise BenchmarkHarnessError(f"Benchmark replay source report is malformed: {source_report_path}") from exc
        except ValidationError as exc:
            raise BenchmarkHarnessError(f"Benchmark replay source report is invalid: {source_report_path}") from exc

    def _run_report(self, results: Sequence[BenchmarkReplayCaseResult]) -> BenchmarkReplayRunReport:
        passed_count = sum(1 for result in results if result.status == "passed")
        failed_count = sum(1 for result in results if result.status == "failed")
        error_count = sum(1 for result in results if result.status == "error")
        if error_count:
            run_status = "error"
        elif failed_count:
            run_status = "failed"
        else:
            run_status = "passed"
        return BenchmarkReplayRunReport(
            run_status=run_status,
            case_results=list(results),
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
        )


def stable_replay_summary(result: BenchmarkCaseResult) -> BenchmarkReplaySummary:
    return BenchmarkReplaySummary(
        status=result.status,
        workflow_status=result.workflow_status,
        observed_tool_names=sorted(
            _string_list(_score_detail(result, "trajectory", "observed_tool_names", []))
        ),
        action_count=result.action_count,
        injected_failure_count=_int_value(
            _score_detail(result, "failure_injection", "injected_failure_count", 0)
        ),
        recovery_actions=_string_list(
            _score_detail(result, "recovery_expectation", "observed_recovery_actions", [])
        ),
    )


def _compare_summaries(
    source: BenchmarkReplaySummary,
    replay: BenchmarkReplaySummary,
) -> list[BenchmarkReplayMismatch]:
    mismatches = []
    for field in _COMPARE_FIELDS:
        source_value = getattr(source, field)
        replay_value = getattr(replay, field)
        if source_value != replay_value:
            mismatches.append(
                BenchmarkReplayMismatch(
                    field=field,
                    source=source_value,
                    replay=replay_value,
                )
            )
    return mismatches


def _score_detail(
    result: BenchmarkCaseResult,
    score_name: str,
    detail_name: str,
    default: Any,
) -> Any:
    for score in result.scores:
        if score.name == score_name:
            return score.details.get(detail_name, default)
    return default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_failure_reason(exc: Exception) -> str:
    return f"{type(exc).__name__}: {_sanitize_text(str(exc))}"


def _sanitize_text(value: str) -> str:
    sanitized = value
    for fragment in _SENSITIVE_TEXT_PARTS:
        sanitized = sanitized.replace(fragment, "[redacted]")
        sanitized = sanitized.replace(fragment.upper(), "[redacted]")
        sanitized = sanitized.replace(fragment.title(), "[redacted]")
    return sanitized
