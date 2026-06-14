from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import backend.app.benchmark.recovery_review as recovery_review
from backend.app.benchmark.schemas import (
    BenchmarkCaseResult,
    BenchmarkFailureChainSummary,
    BenchmarkReplayCaseResult,
    BenchmarkReplaySummary,
    BenchmarkScore,
    RecoveryReplayReviewRunReport,
)
from backend.app.observability.schemas import (
    InternalBenchmarkArtifactSummary,
    InternalObservabilityRunSummary,
    InternalRecoveryAttemptSummary,
    InternalRecoveryPathSummary,
    InternalRecoveryReplaySourceSummary,
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


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeRedisKeyBuilder:
    @classmethod
    def from_settings(cls) -> object:
        return object()


def test_run_generic_recovery_replay_review_runs_selected_case_and_refreshes_case_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("11111111-2222-3333-4444-555555555555")
    run_id = UUID("12121212-3434-5656-7878-909090909090")
    selected_case = _recovery_case(
        case_id="family_route_and_dining_unavailable_v1",
        failure_profile="route_and_dining_unavailable_v0",
        expected_recovery_action="stop_safely",
        min_injected_failure_count=3,
    )
    source_report_path = output_root / f"recovery-review-{fixed_uuid}" / f"{selected_case.case_id}.json"
    replay_report_path = (
        output_root
        / f"recovery-review-{fixed_uuid}"
        / "replays"
        / f"{selected_case.case_id}-replay.json"
    )

    monkeypatch.setattr(recovery_review, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(recovery_review, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(recovery_review, "SessionLocal", _FakeSession)
    monkeypatch.setattr(recovery_review, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(recovery_review, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(recovery_review, "load_benchmark_case", lambda case_id: selected_case)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path) -> None:
            self.report_dir = Path(report_dir)
            self.trace_buffer_path = Path(trace_buffer_path)

        def run_case(self, case):
            assert case.case_id == selected_case.case_id
            source_report_path.parent.mkdir(parents=True, exist_ok=True)
            source_report_path.write_text('{"source":"ok"}', encoding="utf-8")
            return _source_case_result(
                case_id=case.case_id,
                run_id=run_id,
                report_path=str(source_report_path),
                profile_id=selected_case.failure_profile,
                injected_effects=[
                    "check_route:route_infeasible:failed",
                    "check_table_availability:no_tables:failed",
                    "check_queue:queue_closed:failed",
                ],
            )

    class FakeReplayHarness:
        def __init__(self, _benchmark_harness, *, replay_report_dir) -> None:
            self.replay_report_dir = Path(replay_report_dir)

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            assert report_path == str(source_report_path)
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"ok"}', encoding="utf-8")
            return _replay_case_result(
                case_id=selected_case.case_id,
                benchmark_report_path=report_path,
                replay_report_path=str(replay_report_path),
                failure_chain_signature=[
                    "check_route:route_infeasible:failed",
                    "check_table_availability:no_tables:failed",
                    "check_queue:queue_closed:failed",
                ],
            )

    class FakeObservabilityService:
        def __init__(self, _db_session) -> None:
            pass

        def get_run_summary(self, observed_run_id):
            assert observed_run_id == run_id
            return _observability_summary(
                run_id=run_id,
                case_id=selected_case.case_id,
                source_report_path=str(source_report_path),
                max_attempts=2,
                attempt_count=1,
                recovery_action="stop_safely",
                attempt_status="stopped",
            )

    monkeypatch.setattr(recovery_review, "BenchmarkHarness", FakeHarness)
    monkeypatch.setattr(recovery_review, "BenchmarkReplayHarness", FakeReplayHarness)
    monkeypatch.setattr(recovery_review, "InternalObservabilityService", FakeObservabilityService)

    try:
        report = recovery_review.run_generic_recovery_replay_review(
            case_id=selected_case.case_id,
            output_root=output_root,
            start_services=False,
        )

        assert isinstance(report, RecoveryReplayReviewRunReport)
        assert report.status == "passed"
        assert report.selection_mode == "case"
        assert report.case_id == selected_case.case_id
        assert report.requested_case_ids == [selected_case.case_id]
        assert report.passed_count == 1
        assert report.failed_count == 0
        assert report.error_count == 0
        assert len(report.case_results) == 1
        assert report.case_results[0].case_id == selected_case.case_id
        assert Path(report.case_results[0].latest_review_path) == (
            output_root / f"latest-{selected_case.case_id}-review.json"
        )
    finally:
        _cleanup_test_dir(output_root)


def test_run_generic_recovery_replay_review_runs_recovery_suite_and_returns_run_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("66666666-7777-8888-9999-000000000000")
    suite_cases = [
        _recovery_case("family_route_failure_v1", "route_unavailable_v0", "stop_safely", 1),
        _recovery_case("family_route_and_dining_unavailable_v1", "route_and_dining_unavailable_v0", "stop_safely", 3),
        _recovery_case("rainy_day_ticket_sold_out_v1", "ticket_sold_out_and_bad_weather_v0", "stop_safely", 2),
        _recovery_case(
            "family_ticket_sold_out_and_route_unavailable_v1",
            "ticket_sold_out_and_route_unavailable_v0",
            "stop_safely",
            2,
        ),
        _recovery_case("budget_queue_closed_constraint_v1", "queue_closed_and_budget_constraint_v0", "stop_safely", 1),
        _recovery_case(
            "family_table_unavailable_replan_required_v1",
            "table_unavailable_and_replan_required_v0",
            "stop_safely",
            1,
        ),
    ]

    monkeypatch.setattr(recovery_review, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(recovery_review, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(recovery_review, "SessionLocal", _FakeSession)
    monkeypatch.setattr(recovery_review, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(recovery_review, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(recovery_review, "load_benchmark_suite", lambda suite_id: suite_cases)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path) -> None:
            self.report_dir = Path(report_dir)

        def run_case(self, case):
            report_path = self.report_dir / f"{case.case_id}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text('{"source":"ok"}', encoding="utf-8")
            if case.case_id == "family_route_failure_v1":
                injected_effects = ["check_route:route_infeasible:failed"]
            elif case.case_id == "budget_queue_closed_constraint_v1":
                injected_effects = ["check_queue:queue_closed:succeeded"]
            elif case.case_id == "family_table_unavailable_replan_required_v1":
                injected_effects = ["check_table_availability:table_unavailable:succeeded"]
            elif case.case_id == "family_ticket_sold_out_and_route_unavailable_v1":
                injected_effects = [
                    "check_ticket_availability:ticket_sold_out:succeeded",
                    "check_route:route_infeasible:failed",
                ]
            elif case.case_id == "rainy_day_ticket_sold_out_v1":
                injected_effects = [
                    "check_weather:bad_weather:succeeded",
                    "check_ticket_availability:ticket_sold_out:succeeded",
                ]
            else:
                injected_effects = [
                    "check_queue:dining_unavailable:succeeded",
                    "check_table_availability:dining_unavailable:succeeded",
                    "check_route:route_infeasible:failed",
                ]
            return _source_case_result(
                case_id=case.case_id,
                run_id=UUID("aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"),
                report_path=str(report_path),
                profile_id=case.failure_profile,
                injected_effects=injected_effects,
            )

    class FakeReplayHarness:
        def __init__(self, _benchmark_harness, *, replay_report_dir) -> None:
            self.replay_report_dir = Path(replay_report_dir)

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            case_id = Path(report_path).stem
            replay_report_path = self.replay_report_dir / f"{case_id}-replay.json"
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"ok"}', encoding="utf-8")
            if case_id == "family_route_failure_v1":
                failure_chain_signature = ["check_route:route_infeasible:failed"]
            elif case_id == "budget_queue_closed_constraint_v1":
                failure_chain_signature = ["check_queue:queue_closed:succeeded"]
            elif case_id == "family_table_unavailable_replan_required_v1":
                failure_chain_signature = ["check_table_availability:table_unavailable:succeeded"]
            elif case_id == "family_ticket_sold_out_and_route_unavailable_v1":
                failure_chain_signature = [
                    "check_ticket_availability:ticket_sold_out:succeeded",
                    "check_route:route_infeasible:failed",
                ]
            elif case_id == "rainy_day_ticket_sold_out_v1":
                failure_chain_signature = [
                    "check_weather:bad_weather:succeeded",
                    "check_ticket_availability:ticket_sold_out:succeeded",
                ]
            else:
                failure_chain_signature = [
                    "check_queue:dining_unavailable:succeeded",
                    "check_table_availability:dining_unavailable:succeeded",
                    "check_route:route_infeasible:failed",
                ]
            return _replay_case_result(
                case_id=case_id,
                benchmark_report_path=report_path,
                replay_report_path=str(replay_report_path),
                failure_chain_signature=failure_chain_signature,
            )

    class FakeObservabilityService:
        def __init__(self, _db_session) -> None:
            pass

        def get_run_summary(self, observed_run_id):
            return _observability_summary(
                run_id=observed_run_id,
                case_id=suite_cases[0].case_id if str(observed_run_id).startswith("aaaaaaaa") else suite_cases[1].case_id,
                source_report_path="placeholder",
                max_attempts=2,
                attempt_count=1,
                recovery_action="stop_safely",
                attempt_status="stopped",
            )

    monkeypatch.setattr(recovery_review, "BenchmarkHarness", FakeHarness)
    monkeypatch.setattr(recovery_review, "BenchmarkReplayHarness", FakeReplayHarness)
    monkeypatch.setattr(recovery_review, "InternalObservabilityService", FakeObservabilityService)

    try:
        report = recovery_review.run_generic_recovery_replay_review(
            suite_id="failures",
            output_root=output_root,
            start_services=False,
        )

        assert isinstance(report, RecoveryReplayReviewRunReport)
        assert report.selection_mode == "suite"
        assert report.suite_id == "recovery_focused"
        assert report.requested_case_ids == [item.case_id for item in suite_cases]
        assert len(report.case_results) == 6
    finally:
        _cleanup_test_dir(output_root)


def test_run_generic_recovery_replay_review_rejects_non_recovery_case_before_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_case = _non_recovery_case("family_afternoon_v1")
    replay_called = {"value": False}

    monkeypatch.setattr(recovery_review, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(recovery_review, "SessionLocal", _FakeSession)
    monkeypatch.setattr(recovery_review, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(recovery_review, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(recovery_review, "load_benchmark_case", lambda case_id: selected_case)

    class FakeReplayHarness:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def replay_report(self, _report_path: str) -> BenchmarkReplayCaseResult:
            replay_called["value"] = True
            raise AssertionError("replay should not be reached")

    monkeypatch.setattr(recovery_review, "BenchmarkReplayHarness", FakeReplayHarness)

    with pytest.raises(recovery_review.RecoveryReplayReviewError):
        recovery_review.run_generic_recovery_replay_review(
            case_id=selected_case.case_id,
            start_services=False,
        )

    assert replay_called["value"] is False


def test_main_rejects_case_and_suite_together(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = recovery_review.main(["--case-id", "family_route_failure_v1", "--suite-id", "recovery_focused"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "cannot be used together" in captured.err


def test_run_recovery_replay_review_creates_bundle_and_latest_alias_on_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("12345678-1234-5678-1234-567812345678")
    run_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    session = _FakeSession()
    redis_client = _FakeRedis()
    bootstrap_calls: list[bool] = []
    captured: dict[str, object] = {}
    source_report_path = output_root / f"recovery-review-{fixed_uuid}" / "family_route_failure_v1.json"
    replay_report_path = (
        output_root / f"recovery-review-{fixed_uuid}" / "replays" / "family_route_failure_v1-replay.json"
    )

    def bootstrap(*, start_services: bool = True, timeout_seconds: float = 60.0, poll_interval_seconds: float = 1.0) -> None:
        bootstrap_calls.append(start_services)
        captured["timeout_seconds"] = timeout_seconds
        captured["poll_interval_seconds"] = poll_interval_seconds

    class FakeHarness:
        def __init__(self, db_session, cache, rate_limiter, *, report_dir, trace_buffer_path) -> None:
            captured["db_session"] = db_session
            captured["cache"] = cache
            captured["rate_limiter"] = rate_limiter
            captured["report_dir"] = Path(report_dir)
            captured["trace_buffer_path"] = Path(trace_buffer_path)

        def run_case(self, case):
            assert case.case_id == "family_route_failure_v1"
            source_report_path.parent.mkdir(parents=True, exist_ok=True)
            source_report_path.write_text('{"source":"ok"}', encoding="utf-8")
            return _source_case_result(
                case_id="family_route_failure_v1",
                run_id=run_id,
                report_path=str(source_report_path),
                profile_id="route_unavailable_v0",
                injected_effects=["check_route:route_infeasible:failed"],
            )

    class FakeReplayHarness:
        def __init__(self, benchmark_harness, *, replay_report_dir) -> None:
            captured["replay_report_dir"] = Path(replay_report_dir)
            captured["replay_benchmark_harness"] = benchmark_harness

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            captured["replay_source_report_path"] = report_path
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"ok"}', encoding="utf-8")
            return _replay_case_result(
                case_id="family_route_failure_v1",
                benchmark_report_path=report_path,
                replay_report_path=str(replay_report_path),
            )

    class FakeObservabilityService:
        def __init__(self, db_session) -> None:
            captured["observability_session"] = db_session

        def get_run_summary(self, observed_run_id):
            assert observed_run_id == run_id
            return _observability_summary(
                run_id=run_id,
                case_id="family_route_failure_v1",
                source_report_path=str(source_report_path),
                max_attempts=2,
                attempt_count=1,
                recovery_action="stop_safely",
                attempt_status="stopped",
            )

    monkeypatch.setattr(recovery_review, "_bootstrap_runtime", bootstrap)
    monkeypatch.setattr(recovery_review, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(recovery_review, "SessionLocal", lambda: session)
    monkeypatch.setattr(recovery_review, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(recovery_review, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(recovery_review, "BenchmarkHarness", FakeHarness)
    monkeypatch.setattr(recovery_review, "BenchmarkReplayHarness", FakeReplayHarness)
    monkeypatch.setattr(recovery_review, "InternalObservabilityService", FakeObservabilityService)
    monkeypatch.setattr(
        recovery_review,
        "load_benchmark_case",
        lambda case_id: _recovery_case(
            case_id,
            "route_unavailable_v0",
            "stop_safely",
            1,
        ),
    )

    try:
        result = recovery_review.run_recovery_replay_review(output_root=output_root, start_services=False)

        expected_run_dir = output_root / f"recovery-review-{fixed_uuid}"
        expected_latest_alias = output_root / "latest-family_route_failure_v1-review.json"
        expected_review_artifact = expected_run_dir / "recovery-review.json"

        assert bootstrap_calls == [False]
        assert captured["db_session"] is session
        assert captured["observability_session"] is session
        assert captured["report_dir"] == expected_run_dir
        assert captured["trace_buffer_path"] == expected_run_dir / "review-traces.jsonl"
        assert captured["replay_report_dir"] == expected_run_dir / "replays"
        assert captured["replay_source_report_path"] == str(source_report_path)
        assert session.closed is True
        assert redis_client.closed is True

        assert result.schema_version == "weekendpilot_recovery_replay_review_v1"
        assert result.status == "passed"
        assert result.case_id == "family_route_failure_v1"
        assert result.run_id == run_id
        assert Path(result.run_directory) == expected_run_dir
        assert Path(result.source_report_path) == source_report_path
        assert Path(result.replay_report_path) == replay_report_path
        assert Path(result.latest_review_path) == expected_latest_alias
        assert result.failure_chain_summary is not None
        assert result.failure_chain_summary.profile_id == "route_unavailable_v0"
        assert [check.name for check in result.checks] == [
            "benchmark_failure_path",
            "replay_matches_source_report",
            "observability_links_source_report",
        ]
        assert all(check.passed for check in result.checks)

        assert expected_review_artifact.exists()
        assert expected_latest_alias.exists()
        assert expected_latest_alias.read_bytes() == expected_review_artifact.read_bytes()

        payload = json.loads(expected_review_artifact.read_text(encoding="utf-8"))
        assert payload["status"] == "passed"
        assert payload["source_report_path"] == str(source_report_path)
        assert payload["replay_report_path"] == str(replay_report_path)
        assert payload["latest_review_path"] == str(expected_latest_alias)
        assert payload["replay_summary"]["status"] == "passed"
        assert payload["replay_summary"]["mismatch_count"] == 0
        assert payload["recovery_review"]["benchmark_report_path"] == str(source_report_path)
        assert payload["recovery_review"]["replay_source"] == {
            "case_id": "family_route_failure_v1",
            "benchmark_report_path": str(source_report_path),
        }
    finally:
        _cleanup_test_dir(output_root)


def test_run_recovery_replay_review_marks_failed_and_preserves_latest_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    latest_alias = output_root / "latest-family_route_failure_v1-review.json"
    latest_alias.write_text('{"status":"keep"}', encoding="utf-8")
    fixed_uuid = UUID("87654321-4321-8765-4321-876543218765")
    run_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    source_report_path = output_root / f"recovery-review-{fixed_uuid}" / "family_route_failure_v1.json"

    monkeypatch.setattr(recovery_review, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(recovery_review, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(recovery_review, "SessionLocal", _FakeSession)
    monkeypatch.setattr(recovery_review, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(recovery_review, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(
        recovery_review,
        "load_benchmark_case",
        lambda case_id: _recovery_case(
            case_id,
            "route_unavailable_v0",
            "stop_safely",
            1,
        ),
    )

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path) -> None:
            self.report_dir = Path(report_dir)
            self.trace_buffer_path = Path(trace_buffer_path)

        def run_case(self, case):
            assert case.case_id == "family_route_failure_v1"
            source_report_path.parent.mkdir(parents=True, exist_ok=True)
            source_report_path.write_text('{"source":"ok"}', encoding="utf-8")
            return _source_case_result(
                case_id="family_route_failure_v1",
                run_id=run_id,
                report_path=str(source_report_path),
                profile_id="route_unavailable_v0",
                injected_effects=["check_route:route_infeasible:failed"],
            )

    class FakeReplayHarness:
        def __init__(self, _benchmark_harness, *, replay_report_dir) -> None:
            self.replay_report_dir = Path(replay_report_dir)

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            replay_report_path = self.replay_report_dir / "family_route_failure_v1-replay.json"
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"failed"}', encoding="utf-8")
            return _replay_case_result(
                case_id="family_route_failure_v1",
                benchmark_report_path=report_path,
                replay_report_path=str(replay_report_path),
                mismatches=[{"field": "action_count", "source": 0, "replay": 1}],
                status="failed",
            )

    class FakeObservabilityService:
        def __init__(self, _db_session) -> None:
            pass

        def get_run_summary(self, observed_run_id):
            assert observed_run_id == run_id
            return _observability_summary(
                run_id=run_id,
                case_id="family_route_failure_v1",
                source_report_path=str(source_report_path.parent / "wrong-source.json"),
                max_attempts=2,
                attempt_count=1,
                recovery_action="stop_safely",
                attempt_status="stopped",
            )

    monkeypatch.setattr(recovery_review, "BenchmarkHarness", FakeHarness)
    monkeypatch.setattr(recovery_review, "BenchmarkReplayHarness", FakeReplayHarness)
    monkeypatch.setattr(recovery_review, "InternalObservabilityService", FakeObservabilityService)

    try:
        result = recovery_review.run_recovery_replay_review(output_root=output_root, start_services=False)

        expected_run_dir = output_root / f"recovery-review-{fixed_uuid}"
        expected_review_artifact = expected_run_dir / "recovery-review.json"

        assert result.status == "failed"
        assert Path(result.run_directory) == expected_run_dir
        assert [check.name for check in result.checks] == [
            "benchmark_failure_path",
            "replay_matches_source_report",
            "observability_links_source_report",
        ]
        assert [check.passed for check in result.checks] == [True, False, False]
        assert latest_alias.read_text(encoding="utf-8") == '{"status":"keep"}'

        payload = json.loads(expected_review_artifact.read_text(encoding="utf-8"))
        assert payload["status"] == "failed"
        assert payload["checks"][1]["name"] == "replay_matches_source_report"
        assert payload["checks"][1]["passed"] is False
        assert payload["checks"][2]["name"] == "observability_links_source_report"
        assert payload["checks"][2]["passed"] is False
    finally:
        _cleanup_test_dir(output_root)


def test_run_recovery_replay_review_returns_error_artifact_for_observability_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    run_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    source_report_path = output_root / f"recovery-review-{fixed_uuid}" / "family_route_failure_v1.json"

    monkeypatch.setattr(recovery_review, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(recovery_review, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(recovery_review, "SessionLocal", _FakeSession)
    monkeypatch.setattr(recovery_review, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(recovery_review, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(
        recovery_review,
        "load_benchmark_case",
        lambda case_id: _recovery_case(
            case_id,
            "route_unavailable_v0",
            "stop_safely",
            1,
        ),
    )

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path) -> None:
            self.report_dir = Path(report_dir)
            self.trace_buffer_path = Path(trace_buffer_path)

        def run_case(self, case):
            assert case.case_id == "family_route_failure_v1"
            source_report_path.parent.mkdir(parents=True, exist_ok=True)
            source_report_path.write_text('{"source":"ok"}', encoding="utf-8")
            return _source_case_result(
                case_id="family_route_failure_v1",
                run_id=run_id,
                report_path=str(source_report_path),
                profile_id="route_unavailable_v0",
                injected_effects=["check_route:route_infeasible:failed"],
            )

    class FakeReplayHarness:
        def __init__(self, _benchmark_harness, *, replay_report_dir) -> None:
            self.replay_report_dir = Path(replay_report_dir)

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            replay_report_path = self.replay_report_dir / "family_route_failure_v1-replay.json"
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"ok"}', encoding="utf-8")
            return _replay_case_result(
                case_id="family_route_failure_v1",
                benchmark_report_path=report_path,
                replay_report_path=str(replay_report_path),
            )

    class FakeObservabilityService:
        def __init__(self, _db_session) -> None:
            pass

        def get_run_summary(self, _observed_run_id):
            raise RuntimeError("observability unavailable")

    monkeypatch.setattr(recovery_review, "BenchmarkHarness", FakeHarness)
    monkeypatch.setattr(recovery_review, "BenchmarkReplayHarness", FakeReplayHarness)
    monkeypatch.setattr(recovery_review, "InternalObservabilityService", FakeObservabilityService)

    try:
        result = recovery_review.run_recovery_replay_review(output_root=output_root, start_services=False)

        artifact_path = Path(result.run_directory) / "recovery-review.json"
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))

        assert result.status == "error"
        assert payload["status"] == "error"
        assert payload["checks"][0]["name"] == "benchmark_failure_path"
        assert payload["checks"][1]["name"] == "replay_matches_source_report"
        assert payload["checks"][2]["name"] == "observability_links_source_report"
        assert payload["checks"][2]["passed"] is False
    finally:
        _cleanup_test_dir(output_root)


def test_main_returns_non_zero_when_runner_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        recovery_review,
        "run_recovery_replay_review",
        lambda **_: (_ for _ in ()).throw(recovery_review.RecoveryReplayReviewError("bootstrap failed")),
    )

    exit_code = recovery_review.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "bootstrap failed" in captured.err


def test_main_returns_non_zero_for_failed_review(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = recovery_review.RecoveryReplayReviewResult(
        status="failed",
        case_id="family_route_failure_v1",
        run_id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        run_directory="var/test-recovery-review/recovery-review-123",
        source_report_path="var/test-recovery-review/recovery-review-123/family_route_failure_v1.json",
        replay_report_path="var/test-recovery-review/recovery-review-123/replays/family_route_failure_v1-replay.json",
        latest_review_path="var/test-recovery-review/latest-family_route_failure_v1-review.json",
        checks=[
            {"name": "benchmark_failure_path", "passed": True, "detail": "ok"},
            {"name": "replay_matches_source_report", "passed": False, "detail": "mismatches found"},
            {"name": "observability_links_source_report", "passed": True, "detail": "ok"},
        ],
        failure_chain_summary=_failure_chain_summary(),
        replay_summary={
            "status": "failed",
            "mismatch_count": 1,
            "failure_chain_signature": ["check_route:route_infeasible:failed"],
        },
        recovery_review={
            "benchmark_report_path": "var/test-recovery-review/recovery-review-123/family_route_failure_v1.json",
            "attempt_count": 1,
            "max_attempts": 2,
            "recovery_actions": ["stop_safely"],
            "replay_source": {
                "case_id": "family_route_failure_v1",
                "benchmark_report_path": "var/test-recovery-review/recovery-review-123/family_route_failure_v1.json",
            },
        },
    )
    monkeypatch.setattr(recovery_review, "run_recovery_replay_review", lambda **_: result)

    exit_code = recovery_review.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Recovery replay review failed." in captured.err
    assert "mismatches found" in captured.err


def test_main_prints_success_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = recovery_review.RecoveryReplayReviewResult(
        status="passed",
        case_id="family_route_failure_v1",
        run_id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        run_directory="var/test-recovery-review/recovery-review-123",
        source_report_path="var/test-recovery-review/recovery-review-123/family_route_failure_v1.json",
        replay_report_path="var/test-recovery-review/recovery-review-123/replays/family_route_failure_v1-replay.json",
        latest_review_path="var/test-recovery-review/latest-family_route_failure_v1-review.json",
        checks=[
            {"name": "benchmark_failure_path", "passed": True, "detail": "ok"},
            {"name": "replay_matches_source_report", "passed": True, "detail": "ok"},
            {"name": "observability_links_source_report", "passed": True, "detail": "ok"},
        ],
        failure_chain_summary=_failure_chain_summary(),
        replay_summary={
            "status": "passed",
            "mismatch_count": 0,
            "failure_chain_signature": ["check_route:route_infeasible:failed"],
        },
        recovery_review={
            "benchmark_report_path": "var/test-recovery-review/recovery-review-123/family_route_failure_v1.json",
            "attempt_count": 1,
            "max_attempts": 2,
            "recovery_actions": ["stop_safely"],
            "replay_source": {
                "case_id": "family_route_failure_v1",
                "benchmark_report_path": "var/test-recovery-review/recovery-review-123/family_route_failure_v1.json",
            },
        },
    )
    monkeypatch.setattr(recovery_review, "run_recovery_replay_review", lambda **_: result)

    exit_code = recovery_review.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recovery replay review passed." in captured.out
    assert "Case: family_route_failure_v1" in captured.out
    assert "Run ID: ffffffff-ffff-ffff-ffff-ffffffffffff" in captured.out


def _recovery_case(case_id: str, failure_profile: str, expected_recovery_action: str, min_injected_failure_count: int):
    return SimpleNamespace(
        case_id=case_id,
        failure_profile=failure_profile,
        expected=SimpleNamespace(
            expected_workflow_status="failed",
            expected_recovery_action=expected_recovery_action,
            min_action_count=0,
            min_injected_failure_count=min_injected_failure_count,
        ),
    )


def _non_recovery_case(case_id: str):
    return SimpleNamespace(
        case_id=case_id,
        failure_profile=None,
        expected=SimpleNamespace(
            expected_workflow_status="completed",
            expected_recovery_action=None,
            min_action_count=1,
            min_injected_failure_count=0,
        ),
    )


def _source_case_result(
    *,
    case_id: str,
    run_id: UUID,
    report_path: str,
    profile_id: str,
    injected_effects: list[str],
) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        case_id=case_id,
        status="passed",
        run_id=run_id,
        scores=[
            BenchmarkScore(
                name="trajectory",
                score=1.0,
                passed=True,
                reason="ok",
                details={"observed_tool_names": ["check_route", "search_poi"]},
            ),
            BenchmarkScore(
                name="failure_injection",
                score=1.0,
                passed=True,
                reason="ok",
                details={"injected_failure_count": 1},
            ),
            BenchmarkScore(
                name="recovery_expectation",
                score=1.0,
                passed=True,
                reason="ok",
                details={"observed_recovery_actions": ["stop_safely"]},
            ),
        ],
        overall_score=1.0,
        tool_event_count=3,
        action_count=0,
        workflow_status="failed",
        failure_chain_summary=_failure_chain_summary(
            profile_id=profile_id,
            injected_effects=injected_effects,
        ),
        report_path=report_path,
    )


def _failure_chain_summary(
    *,
    profile_id: str = "route_unavailable_v0",
    injected_effects: list[str] | None = None,
) -> BenchmarkFailureChainSummary:
    return BenchmarkFailureChainSummary(
        profile_id=profile_id,
        injected_effects=injected_effects or ["check_route:route_infeasible:failed"],
        recovery_actions=["stop_safely"],
        attempt_count=1,
        max_attempts=2,
        bounded=True,
        terminal_workflow_status="failed",
    )


def _replay_case_result(
    *,
    case_id: str,
    benchmark_report_path: str,
    replay_report_path: str,
    failure_chain_signature: list[str] | None = None,
    mismatches: list[dict] | None = None,
    status: str = "passed",
) -> BenchmarkReplayCaseResult:
    mismatch_models = mismatches or []
    signature = failure_chain_signature or ["check_route:route_infeasible:failed"]
    return BenchmarkReplayCaseResult(
        case_id=case_id,
        status=status,
        source=BenchmarkReplaySummary(
            status="passed",
            workflow_status="failed",
            observed_tool_names=["check_route", "search_poi"],
            action_count=0,
            injected_failure_count=1,
            recovery_actions=["stop_safely"],
            failure_chain_signature=signature,
        ),
        replay=BenchmarkReplaySummary(
            status="passed" if status == "passed" else "failed",
            workflow_status="failed",
            observed_tool_names=["check_route", "search_poi"],
            action_count=0 if status == "passed" else 1,
            injected_failure_count=1,
            recovery_actions=["stop_safely"],
            failure_chain_signature=signature,
        ),
        mismatches=mismatch_models,
        replay_benchmark_status="passed" if status == "passed" else "failed",
        benchmark_report_path=benchmark_report_path,
        replay_report_path=replay_report_path,
    )


def _observability_summary(
    *,
    run_id: UUID,
    case_id: str,
    source_report_path: str,
    max_attempts: int,
    attempt_count: int,
    recovery_action: str,
    attempt_status: str,
) -> InternalObservabilityRunSummary:
    now = datetime.now(timezone.utc)
    return InternalObservabilityRunSummary(
        run_id=run_id,
        status="failed",
        case_id=case_id,
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        created_at=now,
        updated_at=now,
        benchmark_artifact_summary=InternalBenchmarkArtifactSummary(
            case_id=case_id,
            benchmark_status="passed",
            workflow_status="failed",
            tool_event_count=3,
            action_count=0,
            report_path=source_report_path,
        ),
        recovery_path_summary=InternalRecoveryPathSummary(
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            attempts=[
                InternalRecoveryAttemptSummary(
                    attempt_index=1,
                    source_node="execute_searches",
                    recovery_action=recovery_action,
                    error_type="draft_exists",
                    reason="Bounded safe stop",
                    retry_budget_before=2,
                    retry_budget_after=1,
                    status=attempt_status,
                )
            ],
            replay_source=InternalRecoveryReplaySourceSummary(
                case_id=case_id,
                benchmark_report_path=source_report_path,
            ),
        ),
    )


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
