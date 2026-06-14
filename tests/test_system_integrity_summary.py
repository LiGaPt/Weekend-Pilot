from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.observability.integrity_summary import (
    EVIDENCE_PATHS,
    load_system_integrity_summary,
)


def test_load_system_integrity_summary_returns_ready_summary(
    summary_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_json(
        summary_root / "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
        _build_v2_gate_report(),
    )
    _write_json(
        summary_root / "var/formal-benchmarks/latest-all_registered-run-report.json",
        _build_all_registered_report(),
    )
    _write_json(
        summary_root / "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
        _build_stability_report(),
    )
    _write_json(
        summary_root / "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        _build_recovery_review(),
    )
    _patch_evidence_paths(monkeypatch, summary_root)

    summary = load_system_integrity_summary()

    assert summary.status == "ready"
    assert summary.benchmark_summary.status == "ready"
    assert summary.benchmark_summary.release_blocked is False
    assert summary.stability_summary.status == "ready"
    assert summary.stability_summary.pass_pow_4 == 1.0
    assert summary.memory_governance_summary.status == "ready"
    assert summary.memory_governance_summary.memory_case_count == 2
    assert summary.memory_governance_summary.all_memory_cases_passed is True
    assert summary.recovery_replay_summary.status == "ready"
    assert summary.recovery_replay_summary.passed_check_count == 3
    assert summary.timing_summary.status == "ready"
    assert summary.redaction_summary.internal_only is True
    assert "api_key" in summary.redaction_summary.forbidden_key_markers
    assert all(not Path(item.path).is_absolute() for item in summary.evidence_paths)


def test_load_system_integrity_summary_degrades_when_v2_gate_is_missing(
    summary_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_json(
        summary_root / "var/formal-benchmarks/latest-all_registered-run-report.json",
        _build_all_registered_report(),
    )
    _write_json(
        summary_root / "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
        _build_stability_report(),
    )
    _write_json(
        summary_root / "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        _build_recovery_review(),
    )
    _patch_evidence_paths(monkeypatch, summary_root)

    summary = load_system_integrity_summary()

    assert summary.status == "missing_evidence"
    assert summary.benchmark_summary.status == "missing"
    assert summary.stability_summary.status == "ready"
    v2_gate_path = next(item for item in summary.evidence_paths if item.evidence_id == "v2_integrity_gate")
    assert v2_gate_path.exists is False
    assert v2_gate_path.required_for_summary is True


def test_load_system_integrity_summary_marks_invalid_stability_report(
    summary_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_json(
        summary_root / "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
        _build_v2_gate_report(),
    )
    _write_json(
        summary_root / "var/formal-benchmarks/latest-all_registered-run-report.json",
        _build_all_registered_report(),
    )
    _write_json(
        summary_root / "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        _build_recovery_review(),
    )
    bad_path = summary_root / "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text('{"schema_version":"broken"}', encoding="utf-8")
    _patch_evidence_paths(monkeypatch, summary_root)

    summary = load_system_integrity_summary()

    assert summary.status == "invalid_evidence"
    assert summary.stability_summary.status == "invalid"


def test_load_system_integrity_summary_collects_failing_memory_case_ids(
    summary_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _build_all_registered_report()
    report["case_results"][1]["status"] = "failed"
    _write_json(
        summary_root / "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
        _build_v2_gate_report(),
    )
    _write_json(
        summary_root / "var/formal-benchmarks/latest-all_registered-run-report.json",
        report,
    )
    _write_json(
        summary_root / "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
        _build_stability_report(),
    )
    _write_json(
        summary_root / "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        _build_recovery_review(),
    )
    _patch_evidence_paths(monkeypatch, summary_root)

    summary = load_system_integrity_summary()

    assert summary.memory_governance_summary.memory_case_count == 2
    assert summary.memory_governance_summary.passed_case_count == 1
    assert summary.memory_governance_summary.failed_case_count == 1
    assert summary.memory_governance_summary.all_memory_cases_passed is False
    assert summary.memory_governance_summary.failing_case_ids == ["family_memory_advisory_fill_v1"]


def _patch_evidence_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(
        "backend.app.observability.integrity_summary.EVIDENCE_PATHS",
        {
            key: root / relative_path
            for key, relative_path in EVIDENCE_PATHS.items()
        },
    )


@pytest.fixture()
def summary_root() -> Path:
    root = Path("var/test-system-integrity-summary") / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if root.exists():
            root.rmdir()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_v2_gate_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [],
        "passed_count": 18,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "v2_integrity",
            "suite_title": "V2 integrity",
            "run_status": "passed",
            "case_count": 18,
            "passed_count": 18,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "benchmark_timing_summary": {
                "schema_version": "benchmark_timing_summary_v1",
                "case_count": 18,
                "overall_total_duration_ms": {
                    "sample_count": 18,
                    "min_ms": 320,
                    "p50_ms": 390,
                    "p95_ms": 424,
                    "p99_ms": 424,
                    "max_ms": 424,
                    "mean_ms": 388.4,
                },
                "stages": [],
            },
        },
        "v2_integrity_gate_evaluation": {
            "schema_version": "weekendpilot_v2_integrity_gate_evaluation_v1",
            "gate_id": "v2_integrity_gate",
            "suite_id": "v2_integrity",
            "release_blocked": False,
            "blocking_failures": [],
            "coverage_thresholds": {},
            "observed_coverage": {
                "integrity_coverage_summary": {
                    "case_count": 18,
                    "memory_case_count": 6,
                    "recovery_case_count": 6,
                    "continuation_case_count": 2,
                    "robustness_case_count": 4,
                    "l4_case_count": 2,
                },
                "memory_mode_counts": {"none": 12, "override_guarded": 1},
                "conversation_mode_counts": {"single_turn": 15, "replan_versioned": 2, "clarification": 1},
                "failure_mode_counts": {"none": 12, "route_unavailable": 1},
            },
        },
    }


def _build_stability_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_stability_passk_v1",
        "metric_version": "passk_v0",
        "suite_id": "v2_integrity",
        "gate_id": "v2_integrity_gate",
        "requested_run_count": 4,
        "executed_run_count": 4,
        "window_size": 4,
        "window_count": 1,
        "discarded_tail_run_count": 0,
        "success_count": 4,
        "failure_count": 0,
        "error_count": 0,
        "success_at_1": 1.0,
        "pass_at_4": 1.0,
        "pass_pow_4": 1.0,
        "attempts": [],
        "windows": [],
    }


def _build_all_registered_report() -> dict:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [
            {
                "schema_version": "weekendpilot_benchmark_case_result_v1",
                "case_id": "family_memory_override_v1",
                "status": "passed",
                "overall_score": 1.0,
                "tool_event_count": 5,
                "action_count": 0,
                "scores": [
                    {
                        "name": "memory_governance",
                        "score": 1.0,
                        "passed": True,
                        "reason": "ok",
                        "details": {},
                    }
                ],
            },
            {
                "schema_version": "weekendpilot_benchmark_case_result_v1",
                "case_id": "family_memory_advisory_fill_v1",
                "status": "passed",
                "overall_score": 1.0,
                "tool_event_count": 5,
                "action_count": 0,
                "scores": [
                    {
                        "name": "memory_governance",
                        "score": 1.0,
                        "passed": True,
                        "reason": "ok",
                        "details": {},
                    }
                ],
            },
            {
                "schema_version": "weekendpilot_benchmark_case_result_v1",
                "case_id": "solo_afternoon_v1",
                "status": "passed",
                "overall_score": 1.0,
                "tool_event_count": 5,
                "action_count": 1,
                "scores": [
                    {
                        "name": "workflow_path",
                        "score": 1.0,
                        "passed": True,
                        "reason": "ok",
                        "details": {},
                    }
                ],
            },
        ],
        "passed_count": 3,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "all_registered",
            "suite_title": "All registered",
            "run_status": "passed",
            "case_count": 3,
            "passed_count": 3,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
        },
    }


def _build_recovery_review() -> dict:
    return {
        "schema_version": "weekendpilot_recovery_replay_review_v1",
        "status": "passed",
        "case_id": "family_route_failure_v1",
        "run_id": None,
        "run_directory": "var/recovery-reviews/recovery-review-123",
        "source_report_path": "var/formal-benchmarks/family-route.json",
        "replay_report_path": "var/recovery-reviews/replay-family-route.json",
        "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        "checks": [
            {"name": "a", "passed": True, "detail": "ok"},
            {"name": "b", "passed": True, "detail": "ok"},
            {"name": "c", "passed": True, "detail": "ok"},
        ],
        "failure_chain_summary": None,
        "replay_summary": {
            "status": "passed",
            "mismatch_count": 0,
            "failure_chain_signature": ["route_unavailable"],
        },
        "recovery_review": {
            "benchmark_report_path": "var/formal-benchmarks/family-route.json",
            "attempt_count": 1,
            "max_attempts": 2,
            "recovery_actions": ["stop_safely"],
            "replay_source": {
                "case_id": "family_route_failure_v1",
                "benchmark_report_path": "var/formal-benchmarks/family-route.json",
            },
        },
    }
