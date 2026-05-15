from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.observability.redaction import sanitize_trace_payload
from backend.app.observability.schemas import TraceRecordResult


class LocalTraceBuffer:
    recorder_version = "local_trace_buffer_v1"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, payload: dict[str, Any]) -> TraceRecordResult:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            sanitized = sanitize_trace_payload(payload)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(sanitized, sort_keys=True) + "\n")
        except Exception as exc:
            return TraceRecordResult(
                run_id=payload.get("run_id"),
                trace_id=payload.get("trace_id"),
                status="failed",
                local_buffer_written=False,
                local_buffer_path=str(self.path),
                error_json={
                    "code": "local_trace_buffer_write_failed",
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                },
                recorder_version=self.recorder_version,
            )

        return TraceRecordResult(
            run_id=payload.get("run_id"),
            trace_id=payload.get("trace_id"),
            status="completed",
            local_buffer_written=True,
            local_buffer_path=str(self.path),
            recorder_version=self.recorder_version,
        )
