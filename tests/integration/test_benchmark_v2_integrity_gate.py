from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.v2_integrity_gate import run_benchmark_v2_integrity_gate


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

EXPECTED_INTEGRITY_COVERAGE = {
    "case_count": 12,
    "memory_case_count": 3,
    "recovery_case_count": 3,
    "continuation_case_count": 2,
    "robustness_case_count": 4,
    "l4_case_count": 1,
}


def test_benchmark_v2_integrity_gate_runs_suite_and_refreshes_latest_alias() -> None:
    output_root = _make_test_dir()

    try:
        result = run_benchmark_v2_integrity_gate(output_root=output_root, start_services=False)

        assert result.gate_id == "v2_integrity_gate"
        assert result.suite_id == "v2_integrity"
        assert result.release_blocked is False
        assert result.blocking_failures == []
        assert result.run_status == "passed"
        assert result.case_count == 12
        assert result.passed_count == 12
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.suite_report_path.exists()
        assert result.latest_report_path.exists()
        assert result.latest_report_path.read_bytes() == result.suite_report_path.read_bytes()
        assert result.integrity_coverage_summary == EXPECTED_INTEGRITY_COVERAGE

        suite_payload = json.loads(result.suite_report_path.read_text(encoding="utf-8"))
        latest_payload = json.loads(result.latest_report_path.read_text(encoding="utf-8"))
        assert suite_payload["benchmark_summary"]["suite_id"] == "v2_integrity"
        assert suite_payload["benchmark_summary"]["integrity_coverage_summary"] == {
            "schema_version": "weekendpilot_benchmark_integrity_coverage_v1",
            **EXPECTED_INTEGRITY_COVERAGE,
        }
        assert suite_payload["v2_integrity_gate_evaluation"]["gate_id"] == "v2_integrity_gate"
        assert suite_payload["v2_integrity_gate_evaluation"]["release_blocked"] is False
        assert (
            suite_payload["v2_integrity_gate_evaluation"]["observed_coverage"]["integrity_coverage_summary"]
            == EXPECTED_INTEGRITY_COVERAGE
        )
        assert latest_payload["v2_integrity_gate_evaluation"] == suite_payload["v2_integrity_gate_evaluation"]

        serialized_suite = json.dumps(suite_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized_suite
    finally:
        _cleanup_test_dir(output_root)


def _make_test_dir() -> Path:
    path = Path("var/test-v2-integrity-gate-integration") / str(uuid4())
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
