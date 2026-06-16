from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.coverage_gate import run_benchmark_coverage_gate


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

EXPECTED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "elder": 2,
    "family": 16,
    "friends": 3,
    "mixed": 4,
    "solo": 2,
    "unknown": 2,
}
EXPECTED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 3,
    "couple_afternoon": 1,
    "elder_afternoon": 2,
    "family_afternoon": 16,
    "friends_gathering": 3,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2,
}
EXPECTED_FAILURE_MODE_COUNTS = {
    "none": 22,
    "queue_closed_and_budget_constraint": 1,
    "route_and_dining_unavailable": 2,
    "route_unavailable": 1,
    "table_unavailable_and_replan_required": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 2,
}
EXPECTED_CONSTRAINT_TAG_COUNTS = {
    "budget_limited": 3,
    "casual_dining": 2,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "elder_friendly": 2,
    "friends_group": 3,
    "memory_governance": 5,
    "rainy_day": 3,
    "robustness_case": 4,
}


def test_benchmark_coverage_gate_runs_all_registered_and_refreshes_latest_alias() -> None:
    output_root = _make_test_dir()

    try:
        result = run_benchmark_coverage_gate(output_root=output_root, start_services=False)

        assert result.gate_id == "coverage_gate_v1_5"
        assert result.suite_id == "all_registered"
        assert result.release_blocked is False
        assert result.blocking_failures == []
        assert result.run_status == "passed"
        assert result.case_count == 30
        assert result.passed_count == 30
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.suite_report_path.exists()
        assert result.latest_report_path.exists()
        assert result.latest_report_path.read_bytes() == result.suite_report_path.read_bytes()
        assert result.scenario_bucket_counts == EXPECTED_SCENARIO_BUCKET_COUNTS
        assert result.world_profile_counts == EXPECTED_WORLD_PROFILE_COUNTS
        assert result.failure_mode_counts == EXPECTED_FAILURE_MODE_COUNTS
        assert result.constraint_tag_case_counts == EXPECTED_CONSTRAINT_TAG_COUNTS
        assert result.share_checks["family_scenario_share"]["observed_ratio"] == 0.5333
        assert result.share_checks["family_afternoon_world_profile_share"]["observed_ratio"] == 0.5333
        assert result.share_checks["non_failure_share"]["observed_ratio"] == 0.7333

        suite_payload = json.loads(result.suite_report_path.read_text(encoding="utf-8"))
        latest_payload = json.loads(result.latest_report_path.read_text(encoding="utf-8"))
        assert suite_payload["benchmark_summary"]["suite_id"] == "all_registered"
        assert suite_payload["benchmark_summary"]["case_count"] == 30
        assert suite_payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == (
            EXPECTED_SCENARIO_BUCKET_COUNTS
        )
        assert suite_payload["benchmark_summary"]["matrix_summary"]["world_profile_counts"] == (
            EXPECTED_WORLD_PROFILE_COUNTS
        )
        assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == (
            EXPECTED_FAILURE_MODE_COUNTS
        )
        assert suite_payload["benchmark_summary"]["outcome_rollup"]["constraint_tag_outcomes"]
        assert suite_payload["coverage_gate_evaluation"]["gate_id"] == "coverage_gate_v1_5"
        assert suite_payload["coverage_gate_evaluation"]["release_blocked"] is False
        assert suite_payload["coverage_gate_evaluation"]["coverage_thresholds"]["minimum_case_count"] == 30
        assert suite_payload["coverage_gate_evaluation"]["observed_coverage"]["case_count"] == 30
        assert suite_payload["coverage_gate_evaluation"]["observed_coverage"]["scenario_bucket_counts"] == (
            EXPECTED_SCENARIO_BUCKET_COUNTS
        )
        assert suite_payload["coverage_gate_evaluation"]["observed_coverage"]["world_profile_counts"] == (
            EXPECTED_WORLD_PROFILE_COUNTS
        )
        assert suite_payload["coverage_gate_evaluation"]["observed_coverage"]["failure_mode_counts"] == (
            EXPECTED_FAILURE_MODE_COUNTS
        )
        assert suite_payload["coverage_gate_evaluation"]["observed_coverage"]["constraint_tag_case_counts"] == (
            EXPECTED_CONSTRAINT_TAG_COUNTS
        )
        assert latest_payload["coverage_gate_evaluation"] == suite_payload["coverage_gate_evaluation"]

        serialized_suite = json.dumps(suite_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized_suite
    finally:
        _cleanup_test_dir(output_root)


def _make_test_dir() -> Path:
    path = Path("var/test-coverage-gate-integration") / str(uuid4())
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
