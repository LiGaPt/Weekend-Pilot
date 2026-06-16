from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID
from uuid import uuid4

import pytest

import backend.app.benchmark.v2_integrity_gate as v2_integrity_gate
from backend.app.benchmark.formal_verification import FormalVerificationResult


PASSING_TOOL_PROFILE_COUNTS = {"mock_world": 20}
PASSING_FAILURE_MODE_COUNTS = {
    "none": 12,
    "queue_closed_and_budget_constraint": 1,
    "route_and_dining_unavailable": 2,
    "route_unavailable": 1,
    "table_unavailable_and_replan_required": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 2,
}
PASSING_MEMORY_MODE_COUNTS = {
    "advisory_fill": 1,
    "candidate_not_auto_active": 1,
    "disabled_ignored": 1,
    "expired_advisory": 1,
    "none": 14,
    "override_guarded": 1,
    "sensitive_minimization": 1,
}
PASSING_CONVERSATION_MODE_COUNTS = {
    "clarification": 1,
    "replan_versioned": 2,
    "single_turn": 17,
}
PASSING_INTEGRITY_COVERAGE = {
    "case_count": 20,
    "memory_case_count": 6,
    "recovery_case_count": 8,
    "continuation_case_count": 3,
    "robustness_case_count": 4,
    "l4_case_count": 1,
}
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


def test_run_benchmark_v2_integrity_gate_enriches_unique_report_and_refreshes_latest_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("12345678-1234-5678-1234-567812345678")
    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-v2_integrity-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"
    latest_gate_alias = output_root / "latest-v2_integrity_gate-run-report.json"

    monkeypatch.setattr(
        v2_integrity_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=_build_report_payload(),
        ),
    )

    try:
        result = v2_integrity_gate.run_benchmark_v2_integrity_gate(
            output_root=output_root,
            start_services=False,
        )

        assert result.gate_id == "v2_integrity_gate"
        assert result.suite_id == "v2_integrity"
        assert result.release_blocked is False
        assert result.blocking_failures == []
        assert result.run_status == "passed"
        assert result.case_count == 20
        assert result.passed_count == 20
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.run_directory == run_directory
        assert result.suite_report_path == suite_report_path
        assert result.latest_report_path == latest_gate_alias
        assert result.integrity_coverage_summary == PASSING_INTEGRITY_COVERAGE
        assert result.memory_mode_counts == PASSING_MEMORY_MODE_COUNTS
        assert result.conversation_mode_counts == PASSING_CONVERSATION_MODE_COUNTS
        assert result.failure_mode_counts == PASSING_FAILURE_MODE_COUNTS

        enriched_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        evaluation = enriched_payload["v2_integrity_gate_evaluation"]
        assert evaluation["schema_version"] == "weekendpilot_v2_integrity_gate_evaluation_v1"
        assert evaluation["gate_id"] == "v2_integrity_gate"
        assert evaluation["suite_id"] == "v2_integrity"
        assert evaluation["release_blocked"] is False
        assert evaluation["blocking_failures"] == []
        assert evaluation["coverage_thresholds"]["minimum_case_count"] == 20
        assert evaluation["coverage_thresholds"]["minimum_memory_case_count"] == 6
        assert evaluation["coverage_thresholds"]["minimum_recovery_case_count"] == 8
        assert evaluation["coverage_thresholds"]["minimum_continuation_case_count"] == 2
        assert evaluation["coverage_thresholds"]["minimum_robustness_case_count"] == 4
        assert evaluation["coverage_thresholds"]["minimum_l4_case_count"] == 1
        assert evaluation["observed_coverage"]["integrity_coverage_summary"] == PASSING_INTEGRITY_COVERAGE
        assert evaluation["observed_coverage"]["memory_mode_counts"] == PASSING_MEMORY_MODE_COUNTS
        assert evaluation["observed_coverage"]["conversation_mode_counts"] == PASSING_CONVERSATION_MODE_COUNTS
        assert evaluation["observed_coverage"]["failure_mode_counts"] == PASSING_FAILURE_MODE_COUNTS

        assert latest_gate_alias.exists()
        assert latest_gate_alias.read_bytes() == suite_report_path.read_bytes()
        serialized = json.dumps(enriched_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_v2_integrity_gate_blocks_when_integrity_minimum_is_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        integrity_overrides={"memory_case_count": 2},
    )

    assert result.release_blocked is True
    assert any("memory_case_count" in failure for failure in result.blocking_failures)


def test_run_benchmark_v2_integrity_gate_preserves_latest_alias_on_blocked_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("aaaaaaaa-1234-5678-1234-567812345678")
    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-v2_integrity-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"
    latest_gate_alias = output_root / "latest-v2_integrity_gate-run-report.json"
    latest_gate_alias.write_text('{"status":"keep"}', encoding="utf-8")

    monkeypatch.setattr(
        v2_integrity_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=_build_report_payload(integrity_overrides={"l4_case_count": 0}),
        ),
    )

    try:
        result = v2_integrity_gate.run_benchmark_v2_integrity_gate(
            output_root=output_root,
            start_services=False,
        )

        assert result.release_blocked is True
        assert latest_gate_alias.read_text(encoding="utf-8") == '{"status":"keep"}'
        enriched_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        assert enriched_payload["v2_integrity_gate_evaluation"]["release_blocked"] is True
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_v2_integrity_gate_can_skip_latest_alias_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("cccccccc-1234-5678-1234-567812345678")
    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-v2_integrity-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"
    latest_gate_alias = output_root / "latest-v2_integrity_gate-run-report.json"
    latest_gate_alias.write_text('{"status":"keep"}', encoding="utf-8")

    monkeypatch.setattr(
        v2_integrity_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=_build_report_payload(),
        ),
    )

    try:
        result = v2_integrity_gate.run_benchmark_v2_integrity_gate(
            output_root=output_root,
            start_services=False,
            refresh_latest_alias=False,
        )

        assert result.release_blocked is False
        assert latest_gate_alias.read_text(encoding="utf-8") == '{"status":"keep"}'
        enriched_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        assert enriched_payload["v2_integrity_gate_evaluation"]["release_blocked"] is False
    finally:
        _cleanup_test_dir(output_root)


def test_main_returns_non_zero_when_runner_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        v2_integrity_gate,
        "run_benchmark_v2_integrity_gate",
        lambda **kwargs: (_ for _ in ()).throw(v2_integrity_gate.BenchmarkV2IntegrityGateError("boom")),
    )

    exit_code = v2_integrity_gate.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "boom" in captured.err


def test_main_prints_success_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = _make_test_dir()
    result = v2_integrity_gate.BenchmarkV2IntegrityGateResult(
        gate_id="v2_integrity_gate",
        suite_id="v2_integrity",
        release_blocked=False,
        blocking_failures=[],
        run_status="passed",
        case_count=20,
        passed_count=20,
        failed_count=0,
        error_count=0,
        overall_score=1.0,
        run_directory=output_root / "formal-123",
        suite_report_path=output_root / "formal-123" / "suite-v2_integrity-run-report.json",
        latest_report_path=output_root / "latest-v2_integrity_gate-run-report.json",
        integrity_coverage_summary=PASSING_INTEGRITY_COVERAGE,
        memory_mode_counts=PASSING_MEMORY_MODE_COUNTS,
        conversation_mode_counts=PASSING_CONVERSATION_MODE_COUNTS,
        failure_mode_counts=PASSING_FAILURE_MODE_COUNTS,
    )
    monkeypatch.setattr(v2_integrity_gate, "run_benchmark_v2_integrity_gate", lambda **kwargs: result)

    try:
        exit_code = v2_integrity_gate.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Benchmark v2 integrity gate passed." in captured.out
        assert "Gate: v2_integrity_gate" in captured.out
        assert "Suite: v2_integrity" in captured.out
        assert "memory_case_count: 6" in captured.out
        assert "l4_case_count: 1" in captured.out
    finally:
        _cleanup_test_dir(output_root)


def _run_gate_with_payload(
    monkeypatch: pytest.MonkeyPatch,
    *,
    integrity_overrides: dict[str, int] | None = None,
    v2_overrides: dict[str, object] | None = None,
    suite_id: str = "v2_integrity",
    run_status: str = "passed",
    failed_count: int = 0,
    error_count: int = 0,
) -> v2_integrity_gate.BenchmarkV2IntegrityGateResult:
    output_root = _make_test_dir()
    fixed_uuid = UUID("bbbbbbbb-1234-5678-1234-567812345678")
    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-v2_integrity-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"
    payload = _build_report_payload(
        integrity_overrides=integrity_overrides,
        v2_overrides=v2_overrides,
        suite_id=suite_id,
        run_status=run_status,
        failed_count=failed_count,
        error_count=error_count,
    )

    monkeypatch.setattr(
        v2_integrity_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=payload,
        ),
    )

    try:
        return v2_integrity_gate.run_benchmark_v2_integrity_gate(
            output_root=output_root,
            start_services=False,
        )
    finally:
        _cleanup_test_dir(output_root)


def _write_formal_result(
    *,
    run_directory: Path,
    suite_report_path: Path,
    latest_formal_alias: Path,
    payload: dict[str, object],
) -> FormalVerificationResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    suite_report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    latest_formal_alias.write_text(json.dumps({"status": "formal-latest"}, indent=2), encoding="utf-8")
    summary = payload["benchmark_summary"]
    return FormalVerificationResult(
        suite_id=str(summary["suite_id"]),
        run_status=str(payload["run_status"]),
        case_count=int(summary["case_count"]),
        passed_count=int(summary["passed_count"]),
        failed_count=int(summary["failed_count"]),
        error_count=int(summary["error_count"]),
        overall_score=float(summary["overall_score"]),
        run_directory=run_directory,
        suite_report_path=suite_report_path,
        latest_report_path=latest_formal_alias,
        trace_buffer_path=run_directory / "formal-traces.jsonl",
        p50_duration_ms=446,
        p95_duration_ms=1564,
    )


def _build_report_payload(
    *,
    integrity_overrides: dict[str, int] | None = None,
    v2_overrides: dict[str, object] | None = None,
    suite_id: str = "v2_integrity",
    run_status: str = "passed",
    failed_count: int = 0,
    error_count: int = 0,
) -> dict[str, object]:
    integrity_summary = {
        "schema_version": "weekendpilot_benchmark_integrity_coverage_v1",
        **PASSING_INTEGRITY_COVERAGE,
    }
    if integrity_overrides:
        integrity_summary.update(integrity_overrides)
    v2_summary = {
        "schema_version": "weekendpilot_benchmark_case_v2_matrix_v1",
        "case_count": 20,
        "scenario_bucket_counts": {"elder": 1, "family": 12, "friends": 2, "mixed": 3, "solo": 1, "unknown": 1},
        "level_counts": {"L2": 5, "L3": 6, "L4": 1, "L5": 8},
        "failure_mode_counts": PASSING_FAILURE_MODE_COUNTS,
        "memory_mode_counts": PASSING_MEMORY_MODE_COUNTS,
        "conversation_mode_counts": PASSING_CONVERSATION_MODE_COUNTS,
        "stability_required_counts": {"false": 8, "true": 12},
    }
    if v2_overrides:
        v2_summary.update(v2_overrides)

    passed_count = 20 - failed_count - error_count
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": run_status,
        "case_results": [],
        "passed_count": passed_count,
        "failed_count": failed_count,
        "error_count": error_count,
        "overall_score": 1.0,
        "report_path": "ignored-by-test",
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": suite_id,
            "suite_title": "V2 integrity benchmark suite",
            "run_status": run_status,
            "case_count": 20,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "error_count": error_count,
            "overall_score": 1.0,
            "matrix_summary": {
                "schema_version": "weekendpilot_benchmark_case_matrix_v1",
                "case_count": 20,
                "scenario_bucket_counts": {"elder": 1, "family": 12, "friends": 2, "mixed": 3, "solo": 1, "unknown": 1},
                "level_counts": {"L2": 6, "L3": 7, "L5": 7},
                "tool_profile_counts": PASSING_TOOL_PROFILE_COUNTS,
                "world_profile_counts": {
                    "budget_lite": 2,
                    "elder_afternoon": 1,
                    "family_afternoon": 12,
                    "friends_gathering": 2,
                    "rainy_day_fallback": 2,
                    "solo_afternoon": 1,
                },
                "failure_mode_counts": PASSING_FAILURE_MODE_COUNTS,
                "tag_counts": {"robustness_case": 4},
            },
            "v2_taxonomy_summary": v2_summary,
            "integrity_coverage_summary": integrity_summary,
        },
    }


def _make_test_dir() -> Path:
    path = Path("var/test-v2-integrity-gate") / str(uuid4())
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
