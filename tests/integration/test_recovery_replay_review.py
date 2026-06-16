from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.recovery_review import (
    run_generic_recovery_replay_review,
    run_recovery_replay_review,
)


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


def test_recovery_replay_review_runs_family_route_failure_closure_and_refreshes_latest_alias() -> None:
    output_root = _make_test_dir()

    try:
        result = run_recovery_replay_review(output_root=output_root, start_services=False)

        run_directory = Path(result.run_directory)
        review_artifact_path = run_directory / "recovery-review.json"
        latest_alias_path = Path(result.latest_review_path)
        source_report_path = Path(result.source_report_path)
        replay_report_path = Path(result.replay_report_path)

        assert result.schema_version == "weekendpilot_recovery_replay_review_v1"
        assert result.status == "passed"
        assert result.case_id == "family_route_failure_v1"
        assert result.run_id is not None
        assert run_directory.exists()
        assert review_artifact_path.exists()
        assert latest_alias_path.exists()
        assert source_report_path.exists()
        assert replay_report_path.exists()
        assert latest_alias_path.read_bytes() == review_artifact_path.read_bytes()

        payload = json.loads(review_artifact_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "weekendpilot_recovery_replay_review_v1"
        assert payload["status"] == "passed"
        assert payload["case_id"] == "family_route_failure_v1"
        assert payload["run_id"] == str(result.run_id)
        assert payload["run_directory"] == str(run_directory)
        assert payload["source_report_path"] == str(source_report_path)
        assert payload["replay_report_path"] == str(replay_report_path)
        assert payload["latest_review_path"] == str(latest_alias_path)
        assert payload["failure_chain_summary"]["profile_id"] == "route_unavailable_v0"
        assert payload["failure_chain_summary"]["injected_effects"] == ["check_route:route_infeasible:failed"]
        assert payload["failure_chain_summary"]["recovery_actions"] == ["stop_safely"]
        assert payload["failure_chain_summary"]["bounded"] is True
        assert payload["replay_summary"]["status"] == "passed"
        assert payload["replay_summary"]["mismatch_count"] == 0
        assert payload["replay_summary"]["failure_chain_signature"] == [
            "check_route:route_infeasible:failed"
        ]
        assert payload["recovery_review"]["benchmark_report_path"] == str(source_report_path)
        assert payload["recovery_review"]["attempt_count"] == 1
        assert payload["recovery_review"]["max_attempts"] == 2
        assert payload["recovery_review"]["recovery_actions"] == ["stop_safely"]
        assert payload["recovery_review"]["replay_source"] == {
            "case_id": "family_route_failure_v1",
            "benchmark_report_path": str(source_report_path),
        }

        checks = {item["name"]: item for item in payload["checks"]}
        assert set(checks) == {
            "benchmark_failure_path",
            "replay_matches_source_report",
            "observability_links_source_report",
        }
        assert all(item["passed"] is True for item in checks.values())

        serialized = json.dumps(payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized
    finally:
        _cleanup_test_dir(output_root)


def test_recovery_replay_review_runs_selected_non_family_case_and_refreshes_case_alias() -> None:
    output_root = _make_test_dir()

    try:
        report = run_generic_recovery_replay_review(
            case_id="family_route_and_dining_unavailable_v1",
            output_root=output_root,
            start_services=False,
        )

        assert report.status == "passed"
        assert report.selection_mode == "case"
        assert report.case_id == "family_route_and_dining_unavailable_v1"
        assert report.requested_case_ids == ["family_route_and_dining_unavailable_v1"]
        assert report.passed_count == 1
        assert report.failed_count == 0
        assert report.error_count == 0
        assert len(report.case_results) == 1

        case_result = report.case_results[0]
        review_artifact_path = Path(case_result.review_artifact_path)
        latest_alias_path = Path(case_result.latest_review_path)
        payload = json.loads(review_artifact_path.read_text(encoding="utf-8"))

        assert latest_alias_path.exists()
        assert latest_alias_path.read_bytes() == review_artifact_path.read_bytes()
        assert payload["case_id"] == "family_route_and_dining_unavailable_v1"
        assert payload["status"] == "passed"
        assert payload["failure_chain_summary"]["profile_id"] == "route_and_dining_unavailable_v0"
        assert payload["failure_chain_summary"]["recovery_actions"] == ["stop_safely"]
        assert len(payload["failure_chain_summary"]["injected_effects"]) >= 3
        assert payload["replay_summary"]["status"] == "passed"
    finally:
        _cleanup_test_dir(output_root)


def test_recovery_replay_review_runs_recovery_suite_and_writes_run_report() -> None:
    output_root = _make_test_dir()

    try:
        report = run_generic_recovery_replay_review(
            suite_id="recovery_focused",
            output_root=output_root,
            start_services=False,
        )

        run_report_path = Path(report.report_path)
        payload = json.loads(run_report_path.read_text(encoding="utf-8"))

        assert report.status == "passed"
        assert report.selection_mode == "suite"
        assert report.suite_id == "recovery_focused"
        assert report.requested_case_ids == [
            "family_route_failure_v1",
            "family_route_and_dining_unavailable_v1",
            "friends_route_and_dining_unavailable_v1",
            "rainy_day_ticket_sold_out_v1",
            "family_ticket_sold_out_and_route_unavailable_v1",
            "elder_ticket_sold_out_and_route_unavailable_v1",
            "budget_queue_closed_constraint_v1",
            "family_table_unavailable_replan_required_v1",
        ]
        assert report.passed_count == 8
        assert report.failed_count == 0
        assert report.error_count == 0
        assert len(report.case_results) == 8
        assert payload["schema_version"] == "weekendpilot_recovery_replay_review_run_v1"
        assert payload["status"] == "passed"
        assert payload["selection_mode"] == "suite"
        assert payload["suite_id"] == "recovery_focused"
        assert len(payload["case_results"]) == 8

        for item in report.case_results:
            review_artifact_path = Path(item.review_artifact_path)
            latest_alias_path = Path(item.latest_review_path)
            assert review_artifact_path.exists()
            assert latest_alias_path.exists()
    finally:
        _cleanup_test_dir(output_root)


def _make_test_dir() -> Path:
    path = Path("var/test-recovery-review") / str(uuid4())
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
