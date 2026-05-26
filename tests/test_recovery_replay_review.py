from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

import backend.app.benchmark.recovery_review as recovery_review
from backend.app.benchmark.schemas import (
    BenchmarkCaseResult,
    BenchmarkFailureChainSummary,
    BenchmarkReplayCaseResult,
    BenchmarkReplaySummary,
    BenchmarkScore,
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
            return _source_case_result(run_id=run_id, report_path=str(source_report_path))

    class FakeReplayHarness:
        def __init__(self, benchmark_harness, *, replay_report_dir) -> None:
            captured["replay_report_dir"] = Path(replay_report_dir)
            captured["replay_benchmark_harness"] = benchmark_harness

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            captured["replay_source_report_path"] = report_path
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"ok"}', encoding="utf-8")
            return _replay_case_result(
                benchmark_report_path=report_path,
                replay_report_path=str(replay_report_path),
            )

    class FakeObservabilityService:
        def __init__(self, db_session) -> None:
            captured["observability_session"] = db_session

        def get_run_summary(self, observed_run_id):
            assert observed_run_id == run_id
            return _observability_summary(run_id=run_id, source_report_path=str(source_report_path))

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
        lambda case_id: type("Case", (), {"case_id": case_id})(),
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
        lambda case_id: type("Case", (), {"case_id": case_id})(),
    )

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path) -> None:
            self.report_dir = Path(report_dir)
            self.trace_buffer_path = Path(trace_buffer_path)

        def run_case(self, case):
            assert case.case_id == "family_route_failure_v1"
            source_report_path.parent.mkdir(parents=True, exist_ok=True)
            source_report_path.write_text('{"source":"ok"}', encoding="utf-8")
            return _source_case_result(run_id=run_id, report_path=str(source_report_path))

    class FakeReplayHarness:
        def __init__(self, _benchmark_harness, *, replay_report_dir) -> None:
            self.replay_report_dir = Path(replay_report_dir)

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            replay_report_path = self.replay_report_dir / "family_route_failure_v1-replay.json"
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"failed"}', encoding="utf-8")
            return _replay_case_result(
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
                source_report_path=str(source_report_path.parent / "wrong-source.json"),
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
        lambda case_id: type("Case", (), {"case_id": case_id})(),
    )

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path) -> None:
            self.report_dir = Path(report_dir)
            self.trace_buffer_path = Path(trace_buffer_path)

        def run_case(self, case):
            assert case.case_id == "family_route_failure_v1"
            source_report_path.parent.mkdir(parents=True, exist_ok=True)
            source_report_path.write_text('{"source":"ok"}', encoding="utf-8")
            return _source_case_result(run_id=run_id, report_path=str(source_report_path))

    class FakeReplayHarness:
        def __init__(self, _benchmark_harness, *, replay_report_dir) -> None:
            self.replay_report_dir = Path(replay_report_dir)

        def replay_report(self, report_path: str) -> BenchmarkReplayCaseResult:
            replay_report_path = self.replay_report_dir / "family_route_failure_v1-replay.json"
            replay_report_path.parent.mkdir(parents=True, exist_ok=True)
            replay_report_path.write_text('{"replay":"ok"}', encoding="utf-8")
            return _replay_case_result(
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

    exit_code = recovery_review.main()
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

    exit_code = recovery_review.main()
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

    exit_code = recovery_review.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recovery replay review passed." in captured.out
    assert "Case: family_route_failure_v1" in captured.out
    assert "Run ID: ffffffff-ffff-ffff-ffff-ffffffffffff" in captured.out


def _source_case_result(*, run_id: UUID, report_path: str) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        case_id="family_route_failure_v1",
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
        failure_chain_summary=_failure_chain_summary(),
        report_path=report_path,
    )


def _failure_chain_summary() -> BenchmarkFailureChainSummary:
    return BenchmarkFailureChainSummary(
        profile_id="route_unavailable_v0",
        injected_effects=["check_route:route_infeasible:failed"],
        recovery_actions=["stop_safely"],
        attempt_count=1,
        max_attempts=2,
        bounded=True,
        terminal_workflow_status="failed",
    )


def _replay_case_result(
    *,
    benchmark_report_path: str,
    replay_report_path: str,
    mismatches: list[dict] | None = None,
    status: str = "passed",
) -> BenchmarkReplayCaseResult:
    mismatch_models = mismatches or []
    return BenchmarkReplayCaseResult(
        case_id="family_route_failure_v1",
        status=status,
        source=BenchmarkReplaySummary(
            status="passed",
            workflow_status="failed",
            observed_tool_names=["check_route", "search_poi"],
            action_count=0,
            injected_failure_count=1,
            recovery_actions=["stop_safely"],
            failure_chain_signature=["check_route:route_infeasible:failed"],
        ),
        replay=BenchmarkReplaySummary(
            status="passed" if status == "passed" else "failed",
            workflow_status="failed",
            observed_tool_names=["check_route", "search_poi"],
            action_count=0 if status == "passed" else 1,
            injected_failure_count=1,
            recovery_actions=["stop_safely"],
            failure_chain_signature=["check_route:route_infeasible:failed"],
        ),
        mismatches=mismatch_models,
        replay_benchmark_status="passed" if status == "passed" else "failed",
        benchmark_report_path=benchmark_report_path,
        replay_report_path=replay_report_path,
    )


def _observability_summary(*, run_id: UUID, source_report_path: str) -> InternalObservabilityRunSummary:
    now = datetime.now(timezone.utc)
    return InternalObservabilityRunSummary(
        run_id=run_id,
        status="failed",
        case_id="family_route_failure_v1",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        created_at=now,
        updated_at=now,
        benchmark_artifact_summary=InternalBenchmarkArtifactSummary(
            case_id="family_route_failure_v1",
            benchmark_status="passed",
            workflow_status="failed",
            tool_event_count=3,
            action_count=0,
            report_path=source_report_path,
        ),
        recovery_path_summary=InternalRecoveryPathSummary(
            attempt_count=1,
            max_attempts=2,
            attempts=[
                InternalRecoveryAttemptSummary(
                    attempt_index=1,
                    source_node="execute_searches",
                    recovery_action="stop_safely",
                    error_type="draft_exists",
                    reason="Bounded safe stop",
                    retry_budget_before=2,
                    retry_budget_after=1,
                    status="stopped",
                )
            ],
            replay_source=InternalRecoveryReplaySourceSummary(
                case_id="family_route_failure_v1",
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
