from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import BenchmarkCaseResult
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
)


def write_case_report(result: BenchmarkCaseResult, report_dir: Path | str) -> str:
    directory = Path(report_dir)
    report_path = directory / f"{result.case_id}.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        payload = result.model_copy(update={"report_path": str(report_path)})
        sanitized = _drop_forbidden_keys(sanitize_trace_payload(payload.model_dump(mode="json")))
        report_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        raise BenchmarkHarnessError(f"Could not write benchmark report: {report_path}") from exc
    return str(report_path)


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
    return any(part in normalized for part in _FORBIDDEN_KEY_PARTS)
