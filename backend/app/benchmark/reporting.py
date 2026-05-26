from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import (
    BenchmarkCaseResult,
    BenchmarkReplayCaseResult,
    BenchmarkReplayRunReport,
    BenchmarkRunReport,
    RecoveryReplayReviewResult,
)
from backend.app.observability import sanitize_trace_payload


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
_SAFE_KEY_NAMES = {
    "prompt_version",
}


def write_case_report(result: BenchmarkCaseResult, report_dir: Path | str) -> str:
    directory = Path(report_dir)
    report_path = directory / f"{result.case_id}.json"
    payload = result.model_copy(update={"report_path": str(report_path)})
    _write_json_report(payload.model_dump(mode="json"), report_path)
    return str(report_path)


def write_replay_case_report(result: BenchmarkReplayCaseResult, report_dir: Path | str) -> str:
    directory = Path(report_dir)
    report_path = directory / f"{result.case_id}-replay.json"
    payload = result.model_copy(update={"replay_report_path": str(report_path)})
    _write_json_report(payload.model_dump(mode="json"), report_path)
    return str(report_path)


def write_replay_run_report(
    result: BenchmarkReplayRunReport,
    report_dir: Path | str,
    filename: str = "replay-run.json",
) -> str:
    report_path = Path(report_dir) / filename
    _write_json_report(result.model_dump(mode="json"), report_path)
    return str(report_path)


def write_run_report(
    result: BenchmarkRunReport,
    report_dir: Path | str,
    filename: str = "run-report.json",
) -> str:
    report_path = Path(report_dir) / filename
    payload = result.model_copy(update={"report_path": str(report_path)})
    _write_json_report(payload.model_dump(mode="json"), report_path)
    return str(report_path)


def write_recovery_review_report(
    result: RecoveryReplayReviewResult,
    report_dir: Path | str,
    filename: str = "recovery-review.json",
) -> str:
    report_path = Path(report_dir) / filename
    _write_json_report(result.model_dump(mode="json"), report_path)
    return str(report_path)


def _write_json_report(payload: dict[str, Any], report_path: Path) -> None:
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = _drop_forbidden_keys(sanitize_trace_payload(payload))
        report_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        raise BenchmarkHarnessError(f"Could not write benchmark report: {report_path}") from exc


def _drop_forbidden_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_forbidden_keys(item)
            for key, item in value.items()
            if not _is_forbidden_key(key)
        }
    if isinstance(value, list):
        return [_drop_forbidden_keys(item) for item in value]
    return value


def _is_forbidden_key(key: Any) -> bool:
    normalized = str(key).casefold()
    if normalized in _SAFE_KEY_NAMES:
        return False
    return any(part in normalized for part in _FORBIDDEN_KEY_PARTS)
