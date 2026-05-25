from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.release_gate import run_benchmark_release_gate


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


def test_benchmark_release_gate_runs_release_gate_v1_and_refreshes_latest_alias() -> None:
    output_root = _make_test_dir()

    try:
        result = run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.gate_id == "release_gate_v1"
        assert result.suite_id == "release_gate_v1"
        assert result.release_blocked is False
        assert result.blocking_failures == []
        assert result.run_status == "passed"
        assert result.case_count == 15
        assert result.passed_count == 15
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.run_directory.exists()
        assert result.suite_report_path.exists()
        assert result.latest_report_path.exists()
        assert result.trace_buffer_path.exists()
        assert result.p50_duration_ms is not None
        assert result.p95_duration_ms is not None
        assert result.p99_duration_ms is not None

        case_report_paths = [path for path in result.run_directory.glob("*.json") if path.is_file()]
        assert len(case_report_paths) >= 16

        suite_bytes = result.suite_report_path.read_bytes()
        latest_bytes = result.latest_report_path.read_bytes()
        assert latest_bytes == suite_bytes

        suite_payload = json.loads(result.suite_report_path.read_text(encoding="utf-8"))
        latest_payload = json.loads(result.latest_report_path.read_text(encoding="utf-8"))
        assert suite_payload["benchmark_summary"]["suite_id"] == "release_gate_v1"
        assert suite_payload["benchmark_summary"]["case_count"] == 15
        assert suite_payload["benchmark_summary"]["passed_count"] == 15
        assert suite_payload["benchmark_summary"]["failed_count"] == 0
        assert suite_payload["benchmark_summary"]["error_count"] == 0
        assert suite_payload["benchmark_summary"]["matrix_summary"]["level_counts"] == {"L1": 3, "L2": 8, "L3": 4}
        assert suite_payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == {"mock_world": 15}
        assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == {
            "none": 14,
            "route_unavailable": 1,
        }
        assert suite_payload["report_path"] == str(result.suite_report_path)
        assert latest_payload["report_path"] == str(result.suite_report_path)
        assert latest_payload["benchmark_summary"]["suite_id"] == "release_gate_v1"
        assert latest_payload["benchmark_summary"]["case_count"] == 15
        assert all(
            str(result.run_directory) in case_result["report_path"]
            for case_result in latest_payload["case_results"]
            if case_result.get("report_path")
        )

        serialized_suite = json.dumps(suite_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized_suite
    finally:
        _cleanup_test_dir(output_root)


def _make_test_dir() -> Path:
    path = Path("var/test-release-gate") / str(uuid4())
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
