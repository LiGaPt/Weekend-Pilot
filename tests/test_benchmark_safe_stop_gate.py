from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID
from uuid import uuid4

import pytest

import backend.app.benchmark.safe_stop_gate as safe_stop_gate


PASSING_FAILURE_MODE_COUNTS = {
    "route_unavailable": 1,
    "route_and_dining_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 1,
    "queue_closed_and_budget_constraint": 1,
    "table_unavailable_and_replan_required": 1,
}


def test_run_benchmark_safe_stop_gate_enriches_report_and_refreshes_latest_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("11111111-2222-3333-4444-555555555555")
    run_directory = output_root / f"safe-stop-gate-{fixed_uuid}"
    suite_report_path = run_directory / "suite-recovery_focused-run-report.json"
    latest_alias = output_root / "latest-safe_stop_gate_v1-run-report.json"

    monkeypatch.setattr(
        safe_stop_gate,
        "run_safe_stop_verification",
        lambda **kwargs: _write_verification_result(
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            payload=_build_report_payload(),
        ),
    )

    try:
        result = safe_stop_gate.run_benchmark_safe_stop_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is False
        assert result.case_count == 6
        assert result.zero_action_case_count == 6
        assert result.bounded_case_count == 6
        assert result.terminal_safe_stop_case_count == 6
        assert result.multistep_recovery_case_count == 1
        assert result.failure_mode_counts == PASSING_FAILURE_MODE_COUNTS

        payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        evaluation = payload["safe_stop_gate_evaluation"]
        assert evaluation["schema_version"] == "weekendpilot_safe_stop_gate_evaluation_v1"
        assert evaluation["release_blocked"] is False
        assert evaluation["zero_action_case_count"] == 6
        assert evaluation["multistep_recovery_case_count"] == 1
        assert evaluation["failure_mode_counts"] == PASSING_FAILURE_MODE_COUNTS
        assert latest_alias.exists()
        assert latest_alias.read_bytes() == suite_report_path.read_bytes()
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_safe_stop_gate_blocks_when_multistep_chain_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("66666666-7777-8888-9999-000000000000")
    run_directory = output_root / f"safe-stop-gate-{fixed_uuid}"
    suite_report_path = run_directory / "suite-recovery_focused-run-report.json"
    latest_alias = output_root / "latest-safe_stop_gate_v1-run-report.json"
    latest_alias.write_text('{"status":"keep"}', encoding="utf-8")

    monkeypatch.setattr(
        safe_stop_gate,
        "run_safe_stop_verification",
        lambda **kwargs: _write_verification_result(
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            payload=_build_report_payload(multistep=False),
        ),
    )

    try:
        result = safe_stop_gate.run_benchmark_safe_stop_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert any("replace_candidate" in failure for failure in result.blocking_failures)
        assert latest_alias.read_text(encoding="utf-8") == '{"status":"keep"}'
    finally:
        _cleanup_test_dir(output_root)


def _write_verification_result(
    *,
    run_directory: Path,
    suite_report_path: Path,
    payload: dict[str, object],
):
    run_directory.mkdir(parents=True, exist_ok=True)
    suite_report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return type(
        "SafeStopVerificationResult",
        (),
        {
            "suite_id": "recovery_focused",
            "run_status": "passed",
            "case_count": 6,
            "passed_count": 6,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "run_directory": run_directory,
            "suite_report_path": suite_report_path,
        },
    )()


def _build_report_payload(*, multistep: bool = True) -> dict[str, object]:
    case_results = []
    for failure_mode, _count in PASSING_FAILURE_MODE_COUNTS.items():
        recovery_actions = ["stop_safely"]
        if multistep and failure_mode == "table_unavailable_and_replan_required":
            recovery_actions = ["replace_candidate", "stop_safely"]
        case_results.append(
            {
                "case_id": f"case-{failure_mode}",
                "status": "passed",
                "taxonomy": {
                    "suite": "locallife_bench_v1",
                    "scenario_bucket": "family" if "route" in failure_mode or "table" in failure_mode else "mixed",
                    "level": "L5",
                    "tags": ["failure_injected"],
                    "failure_mode": failure_mode,
                },
                "scores": [],
                "overall_score": 1.0,
                "tool_event_count": 8,
                "action_count": 0,
                "workflow_status": "failed",
                "failure_chain_summary": {
                    "profile_id": f"{failure_mode}_v0",
                    "injected_effects": [f"tool:{failure_mode}:failed"],
                    "recovery_actions": recovery_actions,
                    "attempt_count": len(recovery_actions),
                    "max_attempts": 2,
                    "bounded": True,
                    "terminal_workflow_status": "failed",
                },
            }
        )

    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": case_results,
        "passed_count": 6,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "recovery_focused",
            "suite_title": "Recovery focused benchmark suite",
            "run_status": "passed",
            "case_count": 6,
            "passed_count": 6,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
        },
        "report_path": "ignored-by-test",
    }


def _make_test_dir() -> Path:
    path = Path("var/test-safe-stop-gate") / str(uuid4())
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
