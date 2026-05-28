from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID
from uuid import uuid4

import pytest

import backend.app.benchmark.coverage_gate as coverage_gate
from backend.app.benchmark.formal_verification import FormalVerificationResult


PASSING_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 11,
    "friends": 2,
    "mixed": 3,
    "solo": 2,
    "unknown": 2,
}
PASSING_WORLD_PROFILE_COUNTS = {
    "budget_lite": 2,
    "couple_afternoon": 1,
    "family_afternoon": 11,
    "friends_gathering": 2,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2,
}
PASSING_FAILURE_MODE_COUNTS = {
    "none": 18,
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
}
PASSING_CONSTRAINT_TAG_CASE_COUNTS = {
    "budget_limited": 2,
    "casual_dining": 2,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "friends_group": 2,
    "memory_governance": 2,
    "rainy_day": 3,
    "robustness_case": 4,
}
EXPECTED_SCENARIO_MINIMUMS = {
    "couple": 1,
    "family": 5,
    "friends": 2,
    "mixed": 3,
    "solo": 2,
    "unknown": 2,
}
EXPECTED_WORLD_PROFILE_MINIMUMS = {
    "budget_lite": 2,
    "couple_afternoon": 1,
    "family_afternoon": 5,
    "friends_gathering": 2,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2,
}
EXPECTED_FAILURE_MODE_MINIMUMS = {
    "route_unavailable": 1,
    "route_and_dining_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
}
EXPECTED_CONSTRAINT_TAG_MINIMUMS = PASSING_CONSTRAINT_TAG_CASE_COUNTS.copy()
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


def test_run_benchmark_coverage_gate_enriches_unique_report_and_refreshes_latest_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("12345678-1234-5678-1234-567812345678")
    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-all_registered-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"
    latest_coverage_alias = output_root / "latest-coverage_gate_v1_5-run-report.json"

    monkeypatch.setattr(
        coverage_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            output_root=output_root,
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=_build_report_payload(),
            fixed_uuid=fixed_uuid,
        ),
    )

    try:
        result = coverage_gate.run_benchmark_coverage_gate(output_root=output_root, start_services=False)

        assert result.gate_id == "coverage_gate_v1_5"
        assert result.suite_id == "all_registered"
        assert result.release_blocked is False
        assert result.blocking_failures == []
        assert result.run_status == "passed"
        assert result.case_count == 21
        assert result.passed_count == 21
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.run_directory == run_directory
        assert result.suite_report_path == suite_report_path
        assert result.latest_report_path == latest_coverage_alias
        assert result.scenario_bucket_counts == PASSING_SCENARIO_BUCKET_COUNTS
        assert result.world_profile_counts == PASSING_WORLD_PROFILE_COUNTS
        assert result.failure_mode_counts == PASSING_FAILURE_MODE_COUNTS
        assert result.constraint_tag_case_counts == PASSING_CONSTRAINT_TAG_CASE_COUNTS
        assert result.share_checks["family_scenario_share"]["observed_ratio"] == 0.5238
        assert result.share_checks["family_afternoon_world_profile_share"]["observed_ratio"] == 0.5238
        assert result.share_checks["non_failure_share"]["observed_ratio"] == 0.8571
        assert result.share_checks["family_scenario_share"]["status"] == "passed"
        assert result.share_checks["family_afternoon_world_profile_share"]["status"] == "passed"
        assert result.share_checks["non_failure_share"]["status"] == "passed"

        enriched_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        assert "coverage_gate_evaluation" in enriched_payload
        evaluation = enriched_payload["coverage_gate_evaluation"]
        assert evaluation["schema_version"] == "weekendpilot_coverage_gate_evaluation_v1"
        assert evaluation["gate_id"] == "coverage_gate_v1_5"
        assert evaluation["suite_id"] == "all_registered"
        assert evaluation["release_blocked"] is False
        assert evaluation["blocking_failures"] == []
        assert evaluation["coverage_thresholds"]["minimum_case_count"] == 21
        assert evaluation["coverage_thresholds"]["scenario_bucket_minimums"] == EXPECTED_SCENARIO_MINIMUMS
        assert evaluation["coverage_thresholds"]["world_profile_minimums"] == EXPECTED_WORLD_PROFILE_MINIMUMS
        assert evaluation["coverage_thresholds"]["failure_mode_minimums"] == EXPECTED_FAILURE_MODE_MINIMUMS
        assert evaluation["coverage_thresholds"]["constraint_tag_minimums"] == EXPECTED_CONSTRAINT_TAG_MINIMUMS
        assert evaluation["coverage_thresholds"]["scenario_bucket_max_share"] == {"family": 0.6}
        assert evaluation["coverage_thresholds"]["world_profile_max_share"] == {"family_afternoon": 0.6}
        assert evaluation["coverage_thresholds"]["failure_mode_max_share"] == {"none": 0.9}
        assert evaluation["observed_coverage"]["case_count"] == 21
        assert evaluation["observed_coverage"]["scenario_bucket_counts"] == PASSING_SCENARIO_BUCKET_COUNTS
        assert evaluation["observed_coverage"]["world_profile_counts"] == PASSING_WORLD_PROFILE_COUNTS
        assert evaluation["observed_coverage"]["failure_mode_counts"] == PASSING_FAILURE_MODE_COUNTS
        assert evaluation["observed_coverage"]["constraint_tag_case_counts"] == PASSING_CONSTRAINT_TAG_CASE_COUNTS
        assert evaluation["share_checks"] == result.share_checks

        assert latest_coverage_alias.exists()
        assert latest_coverage_alias.read_bytes() == suite_report_path.read_bytes()

        latest_payload = json.loads(latest_coverage_alias.read_text(encoding="utf-8"))
        assert latest_payload["coverage_gate_evaluation"] == evaluation

        serialized = json.dumps(enriched_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_coverage_gate_blocks_when_scenario_minimum_is_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        matrix_overrides={"scenario_bucket_counts": {**PASSING_SCENARIO_BUCKET_COUNTS, "mixed": 2}},
    )

    assert result.release_blocked is True
    assert any("scenario_bucket_counts['mixed']" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_family_share_exceeds_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        case_count=10,
        passed_count=10,
        matrix_overrides={
            "scenario_bucket_counts": {
                "couple": 1,
                "family": 7,
                "friends": 1,
                "mixed": 0,
                "solo": 1,
                "unknown": 0,
            },
            "world_profile_counts": {
                "budget_lite": 2,
                "couple_afternoon": 1,
                "family_afternoon": 5,
                "friends_gathering": 2,
                "rainy_day_fallback": 3,
                "solo_afternoon": 2,
            },
            "failure_mode_counts": PASSING_FAILURE_MODE_COUNTS,
            "tool_profile_counts": {"mock_world": 10},
        },
        constraint_tag_counts=PASSING_CONSTRAINT_TAG_CASE_COUNTS,
    )

    assert result.release_blocked is True
    assert result.share_checks["family_scenario_share"]["status"] == "failed"
    assert result.share_checks["family_scenario_share"]["observed_ratio"] == 0.7
    assert any("family_scenario_share" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_world_profile_minimum_is_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        matrix_overrides={"world_profile_counts": {**PASSING_WORLD_PROFILE_COUNTS, "rainy_day_fallback": 2}},
    )

    assert result.release_blocked is True
    assert any("world_profile_counts['rainy_day_fallback']" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_family_afternoon_share_exceeds_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        case_count=10,
        passed_count=10,
        matrix_overrides={
            "scenario_bucket_counts": {
                "couple": 1,
                "family": 5,
                "friends": 2,
                "mixed": 1,
                "solo": 1,
                "unknown": 0,
            },
            "world_profile_counts": {
                "budget_lite": 1,
                "couple_afternoon": 1,
                "family_afternoon": 7,
                "friends_gathering": 1,
                "rainy_day_fallback": 0,
                "solo_afternoon": 0,
            },
            "failure_mode_counts": PASSING_FAILURE_MODE_COUNTS,
            "tool_profile_counts": {"mock_world": 10},
        },
        constraint_tag_counts=PASSING_CONSTRAINT_TAG_CASE_COUNTS,
    )

    assert result.release_blocked is True
    assert result.share_checks["family_afternoon_world_profile_share"]["status"] == "failed"
    assert result.share_checks["family_afternoon_world_profile_share"]["observed_ratio"] == 0.7
    assert any("family_afternoon_world_profile_share" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_failure_mode_minimum_is_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        matrix_overrides={
            "failure_mode_counts": {
                "none": 19,
                "route_and_dining_unavailable": 1,
                "ticket_sold_out_and_bad_weather": 1,
            }
        },
    )

    assert result.release_blocked is True
    assert any("failure_mode_counts['route_unavailable']" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_non_failure_share_exceeds_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        case_count=21,
        passed_count=21,
        matrix_overrides={
            "scenario_bucket_counts": PASSING_SCENARIO_BUCKET_COUNTS,
            "world_profile_counts": PASSING_WORLD_PROFILE_COUNTS,
            "failure_mode_counts": {
                "none": 20,
                "route_and_dining_unavailable": 1,
                "route_unavailable": 0,
                "ticket_sold_out_and_bad_weather": 0,
            },
            "tool_profile_counts": {"mock_world": 21},
        },
        constraint_tag_counts=PASSING_CONSTRAINT_TAG_CASE_COUNTS,
    )

    assert result.release_blocked is True
    assert result.share_checks["non_failure_share"]["status"] == "failed"
    assert result.share_checks["non_failure_share"]["observed_ratio"] == 0.9524
    assert any("non_failure_share" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_constraint_tag_minimum_is_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        constraint_tag_counts={**PASSING_CONSTRAINT_TAG_CASE_COUNTS, "robustness_case": 3},
    )

    assert result.release_blocked is True
    assert any("constraint_tag_case_counts['robustness_case']" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_matrix_summary_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        include_matrix_summary=False,
    )

    assert result.release_blocked is True
    assert any("matrix_summary" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_outcome_rollup_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        include_outcome_rollup=False,
    )

    assert result.release_blocked is True
    assert any("outcome_rollup" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_constraint_tag_outcomes_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_gate_with_payload(
        monkeypatch,
        include_constraint_tag_outcomes=False,
    )

    assert result.release_blocked is True
    assert any("constraint_tag_outcomes" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_blocks_when_required_bucket_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = PASSING_SCENARIO_BUCKET_COUNTS.copy()
    observed.pop("unknown")
    result = _run_gate_with_payload(
        monkeypatch,
        matrix_overrides={"scenario_bucket_counts": observed},
    )

    assert result.release_blocked is True
    assert any("scenario_bucket_counts['unknown']" in failure for failure in result.blocking_failures)


def test_run_benchmark_coverage_gate_preserves_latest_alias_on_blocked_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("87654321-4321-8765-4321-876543218765")
    latest_coverage_alias = output_root / "latest-coverage_gate_v1_5-run-report.json"
    latest_coverage_alias.write_text('{"status":"keep"}', encoding="utf-8")

    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-all_registered-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"

    monkeypatch.setattr(
        coverage_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            output_root=output_root,
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=_build_report_payload(matrix_overrides={"scenario_bucket_counts": {**PASSING_SCENARIO_BUCKET_COUNTS, "mixed": 2}}),
            fixed_uuid=fixed_uuid,
        ),
    )

    try:
        result = coverage_gate.run_benchmark_coverage_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert latest_coverage_alias.read_text(encoding="utf-8") == '{"status":"keep"}'
        enriched_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        assert enriched_payload["coverage_gate_evaluation"]["release_blocked"] is True
    finally:
        _cleanup_test_dir(output_root)


def test_main_returns_non_zero_when_runner_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        coverage_gate,
        "run_benchmark_coverage_gate",
        lambda **kwargs: (_ for _ in ()).throw(coverage_gate.BenchmarkCoverageGateError("boom")),
    )

    exit_code = coverage_gate.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "boom" in captured.err


def test_main_returns_non_zero_and_prints_blocking_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = _make_test_dir()
    result = coverage_gate.BenchmarkCoverageGateResult(
        gate_id="coverage_gate_v1_5",
        suite_id="all_registered",
        release_blocked=True,
        blocking_failures=["Expected case_count>=21, got 20."],
        run_status="passed",
        case_count=20,
        passed_count=20,
        failed_count=0,
        error_count=0,
        overall_score=1.0,
        run_directory=output_root / "formal-123",
        suite_report_path=output_root / "formal-123" / "suite-all_registered-run-report.json",
        latest_report_path=output_root / "latest-coverage_gate_v1_5-run-report.json",
        scenario_bucket_counts=PASSING_SCENARIO_BUCKET_COUNTS,
        world_profile_counts=PASSING_WORLD_PROFILE_COUNTS,
        failure_mode_counts=PASSING_FAILURE_MODE_COUNTS,
        constraint_tag_case_counts=PASSING_CONSTRAINT_TAG_CASE_COUNTS,
        share_checks=_expected_share_checks(),
    )
    monkeypatch.setattr(coverage_gate, "run_benchmark_coverage_gate", lambda **kwargs: result)

    try:
        exit_code = coverage_gate.main()
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "Benchmark coverage gate failed." in captured.err
        assert "Gate: coverage_gate_v1_5" in captured.err
        assert "Expected case_count>=21, got 20." in captured.err
    finally:
        _cleanup_test_dir(output_root)


def test_main_prints_success_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = _make_test_dir()
    result = coverage_gate.BenchmarkCoverageGateResult(
        gate_id="coverage_gate_v1_5",
        suite_id="all_registered",
        release_blocked=False,
        blocking_failures=[],
        run_status="passed",
        case_count=21,
        passed_count=21,
        failed_count=0,
        error_count=0,
        overall_score=1.0,
        run_directory=output_root / "formal-123",
        suite_report_path=output_root / "formal-123" / "suite-all_registered-run-report.json",
        latest_report_path=output_root / "latest-coverage_gate_v1_5-run-report.json",
        scenario_bucket_counts=PASSING_SCENARIO_BUCKET_COUNTS,
        world_profile_counts=PASSING_WORLD_PROFILE_COUNTS,
        failure_mode_counts=PASSING_FAILURE_MODE_COUNTS,
        constraint_tag_case_counts=PASSING_CONSTRAINT_TAG_CASE_COUNTS,
        share_checks=_expected_share_checks(),
    )
    monkeypatch.setattr(coverage_gate, "run_benchmark_coverage_gate", lambda **kwargs: result)

    try:
        exit_code = coverage_gate.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Benchmark coverage gate passed." in captured.out
        assert "Gate: coverage_gate_v1_5" in captured.out
        assert "Suite: all_registered" in captured.out
        assert "family_scenario_share: 0.5238 <= 0.6 (passed)" in captured.out
        assert "family_afternoon_world_profile_share: 0.5238 <= 0.6 (passed)" in captured.out
        assert "non_failure_share: 0.8571 <= 0.9 (passed)" in captured.out
    finally:
        _cleanup_test_dir(output_root)


def _run_gate_with_payload(
    monkeypatch: pytest.MonkeyPatch,
    *,
    case_count: int = 21,
    passed_count: int = 21,
    matrix_overrides: dict[str, object] | None = None,
    constraint_tag_counts: dict[str, int] | None = None,
    include_matrix_summary: bool = True,
    include_outcome_rollup: bool = True,
    include_constraint_tag_outcomes: bool = True,
) -> coverage_gate.BenchmarkCoverageGateResult:
    output_root = _make_test_dir()
    fixed_uuid = UUID("aaaaaaaa-1234-5678-1234-567812345678")
    run_directory = output_root / f"formal-{fixed_uuid}"
    suite_report_path = run_directory / "suite-all_registered-run-report.json"
    latest_formal_alias = output_root / "latest-all_registered-run-report.json"
    payload = _build_report_payload(
        case_count=case_count,
        passed_count=passed_count,
        matrix_overrides=matrix_overrides,
        constraint_tag_counts=constraint_tag_counts,
        include_matrix_summary=include_matrix_summary,
        include_outcome_rollup=include_outcome_rollup,
        include_constraint_tag_outcomes=include_constraint_tag_outcomes,
    )

    monkeypatch.setattr(
        coverage_gate,
        "run_formal_verification",
        lambda **kwargs: _write_formal_result(
            output_root=output_root,
            run_directory=run_directory,
            suite_report_path=suite_report_path,
            latest_formal_alias=latest_formal_alias,
            payload=payload,
            fixed_uuid=fixed_uuid,
        ),
    )

    try:
        return coverage_gate.run_benchmark_coverage_gate(output_root=output_root, start_services=False)
    finally:
        _cleanup_test_dir(output_root)


def _write_formal_result(
    *,
    output_root: Path,
    run_directory: Path,
    suite_report_path: Path,
    latest_formal_alias: Path,
    payload: dict[str, object],
    fixed_uuid: UUID,
) -> FormalVerificationResult:
    run_directory.mkdir(parents=True, exist_ok=True)
    suite_report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    latest_formal_alias.write_text(json.dumps({"status": "formal-latest"}, indent=2), encoding="utf-8")
    return FormalVerificationResult(
        suite_id="all_registered",
        run_status="passed",
        case_count=int(payload["benchmark_summary"]["case_count"]),
        passed_count=int(payload["benchmark_summary"]["passed_count"]),
        failed_count=int(payload["benchmark_summary"]["failed_count"]),
        error_count=int(payload["benchmark_summary"]["error_count"]),
        overall_score=float(payload["benchmark_summary"]["overall_score"]),
        run_directory=run_directory,
        suite_report_path=suite_report_path,
        latest_report_path=latest_formal_alias,
        trace_buffer_path=run_directory / "formal-traces.jsonl",
        p50_duration_ms=446,
        p95_duration_ms=1564,
    )


def _build_report_payload(
    *,
    case_count: int = 21,
    passed_count: int = 21,
    matrix_overrides: dict[str, object] | None = None,
    constraint_tag_counts: dict[str, int] | None = None,
    include_matrix_summary: bool = True,
    include_outcome_rollup: bool = True,
    include_constraint_tag_outcomes: bool = True,
) -> dict[str, object]:
    matrix_summary = {
        "schema_version": "weekendpilot_benchmark_case_matrix_v1",
        "case_count": case_count,
        "scenario_bucket_counts": PASSING_SCENARIO_BUCKET_COUNTS,
        "level_counts": {"L1": 3, "L2": 12, "L3": 4, "L5": 2},
        "tool_profile_counts": {"mock_world": case_count},
        "world_profile_counts": PASSING_WORLD_PROFILE_COUNTS,
        "failure_mode_counts": PASSING_FAILURE_MODE_COUNTS,
        "tag_counts": {},
    }
    if matrix_overrides:
        matrix_summary.update(matrix_overrides)

    payload: dict[str, object] = {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [],
        "passed_count": passed_count,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "report_path": "ignored-by-test",
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": "all_registered",
            "suite_title": "All registered benchmark suite",
            "run_status": "passed",
            "case_count": case_count,
            "passed_count": passed_count,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
        },
    }

    if include_matrix_summary:
        payload["benchmark_summary"]["matrix_summary"] = matrix_summary

    if include_outcome_rollup:
        outcome_rollup: dict[str, object] = {
            "schema_version": "weekendpilot_benchmark_outcome_rollup_v1",
            "scenario_bucket_outcomes": {},
            "failure_mode_outcomes": {},
        }
        if include_constraint_tag_outcomes:
            outcome_rollup["constraint_tag_outcomes"] = _bucket_stats_map(
                constraint_tag_counts or PASSING_CONSTRAINT_TAG_CASE_COUNTS
            )
        payload["benchmark_summary"]["outcome_rollup"] = outcome_rollup

    return payload


def _bucket_stats_map(counts: dict[str, int]) -> dict[str, dict[str, object]]:
    return {
        key: {
            "case_count": value,
            "passed_count": value,
            "failed_count": 0,
            "error_count": 0,
            "pass_rate": 1.0,
        }
        for key, value in counts.items()
    }


def _expected_share_checks() -> dict[str, dict[str, object]]:
    return {
        "family_scenario_share": {
            "observed_ratio": 0.5238,
            "max_ratio": 0.6,
            "status": "passed",
        },
        "family_afternoon_world_profile_share": {
            "observed_ratio": 0.5238,
            "max_ratio": 0.6,
            "status": "passed",
        },
        "non_failure_share": {
            "observed_ratio": 0.8571,
            "max_ratio": 0.9,
            "status": "passed",
        },
    }


def _make_test_dir() -> Path:
    path = Path("var/test-coverage-gate") / str(uuid4())
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
