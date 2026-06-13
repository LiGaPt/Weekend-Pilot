from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

import backend.app.benchmark.stability_harness as stability_harness
from backend.app.benchmark.v2_integrity_gate import BenchmarkV2IntegrityGateResult


PASSING_GATE_RESULT = {
    "gate_id": "v2_integrity_gate",
    "suite_id": "v2_integrity",
    "case_count": 12,
    "error_count": 0,
    "overall_score": 1.0,
    "integrity_coverage_summary": {
        "case_count": 12,
        "memory_case_count": 3,
        "recovery_case_count": 3,
        "continuation_case_count": 2,
        "robustness_case_count": 4,
        "l4_case_count": 1,
    },
    "memory_mode_counts": {
        "advisory_fill": 1,
        "expired_advisory": 1,
        "none": 9,
        "override_guarded": 1,
    },
    "conversation_mode_counts": {
        "clarification": 1,
        "replan_versioned": 1,
        "single_turn": 10,
    },
    "failure_mode_counts": {
        "none": 9,
        "route_and_dining_unavailable": 1,
        "route_unavailable": 1,
        "ticket_sold_out_and_bad_weather": 1,
    },
}


def test_run_benchmark_stability_passk_rejects_unsupported_suite() -> None:
    with pytest.raises(stability_harness.BenchmarkStabilityHarnessError, match="Unsupported suite_id"):
        stability_harness.run_benchmark_stability_passk("release_gate_v1", 4, start_services=False)


def test_run_benchmark_stability_passk_rejects_runs_below_window_size() -> None:
    with pytest.raises(stability_harness.BenchmarkStabilityHarnessError, match="requires at least 4 runs"):
        stability_harness.run_benchmark_stability_passk("v2_integrity", 3, start_services=False)


def test_parse_args_accepts_supported_cli_shape() -> None:
    suite_id, runs, output_root, start_services = stability_harness._parse_args(
        ["--suite", "v2_integrity", "--runs", "4", "--output-root", "var/tmp", "--no-start-services"]
    )

    assert suite_id == "v2_integrity"
    assert runs == 4
    assert output_root == Path("var/tmp")
    assert start_services is False


def test_run_benchmark_stability_passk_aggregates_metrics_and_preserves_relative_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    expected_latest = output_root / "latest-v2_integrity-passk-v0-report.json"
    gate_calls: list[dict[str, object]] = []
    result_specs = [
        {"release_blocked": False, "run_status": "passed", "blocking_failures": []},
        {"release_blocked": True, "run_status": "failed", "blocking_failures": ["blocked"]},
        {"release_blocked": False, "run_status": "passed", "blocking_failures": []},
        {"release_blocked": True, "run_status": "failed", "blocking_failures": ["blocked"]},
        {"release_blocked": True, "run_status": "failed", "blocking_failures": ["blocked"]},
    ]

    monkeypatch.setattr(stability_harness, "_bootstrap_runtime", lambda **kwargs: None)

    def fake_gate_runner(**kwargs):
        gate_calls.append(kwargs)
        spec = result_specs[len(gate_calls) - 1]
        return _gate_result(
            Path(kwargs["output_root"]),
            len(gate_calls),
            release_blocked=spec["release_blocked"],
            run_status=spec["run_status"],
            blocking_failures=spec["blocking_failures"],
        )

    monkeypatch.setattr(stability_harness, "run_benchmark_v2_integrity_gate", fake_gate_runner)

    try:
        report = stability_harness.run_benchmark_stability_passk(
            "v2_integrity",
            5,
            output_root=output_root,
            start_services=False,
        )

        assert report.suite_id == "v2_integrity"
        assert report.gate_id == "v2_integrity_gate"
        assert report.requested_run_count == 5
        assert report.executed_run_count == 5
        assert report.window_size == 4
        assert report.window_count == 1
        assert report.discarded_tail_run_count == 1
        assert report.success_count == 2
        assert report.failure_count == 3
        assert report.error_count == 0
        assert report.success_at_1 == 0.4
        assert report.pass_at_4 == 1.0
        assert report.pass_pow_4 == 0.0
        assert [attempt.attempt_index for attempt in report.attempts] == [1, 2, 3, 4, 5]
        assert report.attempts[0].suite_report_path == "attempt-001/suite-v2_integrity-run-report.json"
        assert report.attempts[-1].suite_report_path == "attempt-005/suite-v2_integrity-run-report.json"
        assert len(report.windows) == 1
        assert report.windows[0].attempt_indexes == [1, 2, 3, 4]
        assert report.windows[0].any_success is True
        assert report.windows[0].all_success is False
        assert report.windows[0].success_count == 2
        assert report.latest_report_path == str(expected_latest)
        assert expected_latest.exists()

        payload = json.loads(expected_latest.read_text(encoding="utf-8"))
        assert payload["pass_pow_4"] == 0.0
        assert payload["discarded_tail_run_count"] == 1
        assert payload["attempts"][0]["suite_report_path"] == "attempt-001/suite-v2_integrity-run-report.json"
        assert all(call["refresh_latest_alias"] is False for call in gate_calls)
        assert all(call["start_services"] is False for call in gate_calls)
    finally:
        _cleanup_test_dir(output_root)


def test_main_returns_non_zero_for_invalid_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = stability_harness.main(["--suite", "v2_integrity", "--runs", "3"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "requires at least 4 runs" in captured.err


def _gate_result(
    attempt_dir: Path,
    attempt_index: int,
    *,
    release_blocked: bool,
    run_status: str,
    blocking_failures: list[str] | None = None,
) -> BenchmarkV2IntegrityGateResult:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    suite_report_path = attempt_dir / "suite-v2_integrity-run-report.json"
    suite_report_path.write_text(json.dumps({"attempt_index": attempt_index}), encoding="utf-8")
    latest_report_path = attempt_dir.parent / "latest-v2_integrity_gate-run-report.json"
    latest_report_path.write_text('{"status":"do-not-touch"}', encoding="utf-8")
    return BenchmarkV2IntegrityGateResult(
        **PASSING_GATE_RESULT,
        release_blocked=release_blocked,
        blocking_failures=list(blocking_failures or []),
        run_status=run_status,
        passed_count=0 if release_blocked else 12,
        failed_count=12 if release_blocked else 0,
        run_directory=attempt_dir,
        suite_report_path=suite_report_path,
        latest_report_path=latest_report_path,
        trace_buffer_path=attempt_dir / "traces.jsonl",
    )


def _make_test_dir() -> Path:
    path = Path("var/test-benchmark-stability-harness") / str(uuid4())
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
