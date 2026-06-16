from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.formal_verification import run_formal_verification


FORBIDDEN_REPORT_TEXT = (
    "action_id",
    "tool_event_id",
    "api_key",
    "token",
    "secret",
    "authorization",
    "debug_trace",
    "traceback",
)


def test_formal_verification_runs_all_registered_suite_and_refreshes_latest_alias() -> None:
    output_root = _make_test_dir()

    try:
        result = run_formal_verification(output_root=output_root, start_services=False)

        assert result.suite_id == "all_registered"
        assert result.run_status == "passed"
        assert result.case_count == 28
        assert result.passed_count == 28
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.run_directory.exists()
        assert result.suite_report_path.exists()
        assert result.latest_report_path.exists()
        assert result.trace_buffer_path.exists()

        case_report_paths = [path for path in result.run_directory.glob("*.json") if path.is_file()]
        assert len(case_report_paths) >= 29

        suite_bytes = result.suite_report_path.read_bytes()
        latest_bytes = result.latest_report_path.read_bytes()
        assert latest_bytes == suite_bytes

        suite_payload = json.loads(result.suite_report_path.read_text(encoding="utf-8"))
        latest_payload = json.loads(result.latest_report_path.read_text(encoding="utf-8"))
        assert suite_payload["benchmark_summary"]["suite_id"] == "all_registered"
        assert suite_payload["benchmark_summary"]["case_count"] == 28
        assert suite_payload["benchmark_summary"]["passed_count"] == 28
        assert suite_payload["benchmark_summary"]["failed_count"] == 0
        assert suite_payload["benchmark_summary"]["error_count"] == 0
        assert suite_payload["report_path"] == str(result.suite_report_path)
        assert latest_payload["report_path"] == str(result.suite_report_path)
        assert latest_payload["benchmark_summary"]["suite_id"] == "all_registered"
        assert latest_payload["benchmark_summary"]["case_count"] == 28

        serialized_suite = json.dumps(suite_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized_suite
    finally:
        _cleanup_test_dir(output_root)


def _make_test_dir() -> Path:
    path = Path("var/test-formal") / str(uuid4())
    path.mkdir(parents=True, exist_ok=False)
    return path


def _cleanup_test_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            else:
                child.rmdir()
        path.rmdir()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    grandparent = parent.parent
    if grandparent.exists() and not any(grandparent.iterdir()):
        grandparent.rmdir()
