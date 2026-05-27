from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

import pytest

import backend.app.benchmark.release_gate as release_gate
from backend.app.core.config import Settings


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


def test_run_benchmark_release_gate_creates_unique_run_dir_and_latest_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("12345678-1234-5678-1234-567812345678")
    session = _FakeSession()
    redis_client = _FakeRedis()
    bootstrap_calls: list[bool] = []
    captured: dict[str, object] = {}

    def bootstrap(*, start_services: bool = True, timeout_seconds: float = 60.0, poll_interval_seconds: float = 1.0) -> None:
        bootstrap_calls.append(start_services)
        captured["timeout_seconds"] = timeout_seconds
        captured["poll_interval_seconds"] = poll_interval_seconds

    class FakeHarness:
        def __init__(
            self,
            db_session,
            cache,
            rate_limiter,
            *,
            report_dir,
            trace_buffer_path,
            workflow_settings=None,
            workflow_llm_client=None,
        ) -> None:
            captured["db_session"] = db_session
            captured["cache"] = cache
            captured["rate_limiter"] = rate_limiter
            captured["report_dir"] = Path(report_dir)
            captured["trace_buffer_path"] = Path(trace_buffer_path)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = Path(captured["report_dir"]) / "suite-release_gate_v1-run-report.json"
            payload = {
                "suite_id": "release_gate_v1",
                "report_path": str(report_path),
                "nested": {
                    "report_path": str(report_path),
                },
            }
            report_bytes = json.dumps(payload, indent=2).encode("utf-8")
            report_path.write_bytes(report_bytes)
            captured["report_bytes"] = report_bytes
            return _build_fake_report(report_path)

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", bootstrap)
    monkeypatch.setattr(release_gate, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(release_gate, "SessionLocal", lambda: session)
    monkeypatch.setattr(release_gate, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        expected_run_dir = output_root / f"release-gate-v1-{fixed_uuid}"
        latest_alias = output_root / "latest-release_gate_v1-run-report.json"

        assert bootstrap_calls == [False]
        assert captured["db_session"] is session
        assert captured["report_dir"] == expected_run_dir
        assert captured["trace_buffer_path"] == expected_run_dir / "release-gate-traces.jsonl"
        assert session.closed is True
        assert redis_client.closed is True

        assert result.gate_id == "release_gate_v1"
        assert result.suite_id == "release_gate_v1"
        assert result.release_blocked is False
        assert result.blocking_failures == []
        assert result.run_status == "passed"
        assert result.case_count == 15
        assert result.passed_count == 15
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.overall_score == 1.0
        assert result.run_directory == expected_run_dir
        assert result.suite_report_path == expected_run_dir / "suite-release_gate_v1-run-report.json"
        assert result.latest_report_path == latest_alias
        assert result.trace_buffer_path == expected_run_dir / "release-gate-traces.jsonl"
        assert result.p50_duration_ms == 446
        assert result.p95_duration_ms == 1564
        assert result.p99_duration_ms == 2011
        assert result.max_duration_ms == 2011
        assert result.latency_slo["status"] == "passed"
        assert len(result.slow_cases) == 15
        assert result.slow_cases[0]["total_duration_ms"] >= result.slow_cases[-1]["total_duration_ms"]
        assert result.focus_stages["pre_flight_check_availability"]["node_name"] == "pre_flight_check_availability"
        assert result.focus_stages["logical_planner_agent"]["node_name"] == "logical_planner_agent"

        assert latest_alias.read_bytes() != captured["report_bytes"]
        copied_payload = json.loads(latest_alias.read_text(encoding="utf-8"))
        assert copied_payload["nested"]["report_path"] == str(result.suite_report_path)
        assert copied_payload["release_gate_evaluation"]["latency_slo"]["observed_max_ms"] == 2011
        assert copied_payload["release_gate_evaluation"]["focus_stages"]["logical_planner_agent"]["node_name"] == (
            "logical_planner_agent"
        )
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_injects_deterministic_workflow_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    fixed_uuid = UUID("99999999-1234-5678-1234-567899999999")
    source_settings = Settings(
        _env_file=None,
        app_name="WeekendPilot",
        app_env="preview",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/weekend_pilot",
        redis_url="redis://localhost:6379/0",
        local_trace_buffer_path="var/traces/gate-preview.jsonl",
        langsmith_tracing=True,
        langchain_tracing_v2=True,
        langsmith_api_key="langsmith-preview-key",
        langsmith_endpoint="https://langsmith.example.test",
        llm_enabled=True,
        llm_api_key="llm-preview-key",
        llm_base_url="https://llm.example.test/v1",
        llm_model_id="preview-model",
    )
    captured: dict[str, object] = {}

    class FakeHarness:
        def __init__(
            self,
            db_session,
            cache,
            rate_limiter,
            *,
            report_dir,
            trace_buffer_path,
            workflow_settings=None,
            workflow_llm_client=None,
        ) -> None:
            captured["db_session"] = db_session
            captured["cache"] = cache
            captured["rate_limiter"] = rate_limiter
            captured["report_dir"] = Path(report_dir)
            captured["trace_buffer_path"] = Path(trace_buffer_path)
            captured["workflow_settings"] = workflow_settings
            captured["workflow_llm_client"] = workflow_llm_client

        def run_suite(self, suite_id: str):
            report_path = Path(captured["report_dir"]) / "suite-release_gate_v1-run-report.json"
            report_path.write_text(
                json.dumps({"suite_id": suite_id, "report_path": str(report_path)}),
                encoding="utf-8",
            )
            return _build_fake_report(report_path)

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)
    monkeypatch.setattr(release_gate, "get_settings", lambda: source_settings, raising=False)
    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        injected = captured["workflow_settings"]
        assert isinstance(injected, Settings)
        assert injected is not source_settings
        assert injected.app_name == source_settings.app_name
        assert injected.app_env == source_settings.app_env
        assert injected.database_url == source_settings.database_url
        assert injected.redis_url == source_settings.redis_url
        assert injected.local_trace_buffer_path == source_settings.local_trace_buffer_path
        assert injected.llm_enabled is False
        assert injected.llm_api_key is None
        assert injected.llm_base_url is None
        assert injected.llm_model_id is None
        assert injected.langsmith_tracing is False
        assert injected.langchain_tracing_v2 is False
        assert injected.langsmith_api_key is None
        assert injected.langsmith_endpoint is None
        assert captured["workflow_llm_client"] is None
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_preserves_latest_alias_when_release_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    latest_alias = output_root / "latest-release_gate_v1-run-report.json"
    latest_alias.write_text('{"status":"keep"}', encoding="utf-8")
    fixed_uuid = UUID("87654321-4321-8765-4321-876543218765")

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(
            self,
            _db_session,
            _cache,
            _rate_limiter,
            *,
            report_dir,
            trace_buffer_path,
            workflow_settings=None,
            workflow_llm_client=None,
        ) -> None:
            self.report_dir = Path(report_dir)
            self.trace_buffer_path = Path(trace_buffer_path)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "suite_id": suite_id,
                        "report_path": str(report_path),
                    }
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(
                run_status="failed",
                failed_count=1,
                error_count=0,
                overall_score=0.94,
                report_path=str(report_path),
                benchmark_summary=SimpleNamespace(
                    suite_id="release_gate_v1",
                    case_count=15,
                    passed_count=14,
                    failed_count=1,
                    error_count=0,
                    overall_score=0.94,
                    matrix_summary=SimpleNamespace(
                        level_counts={"L1": 3, "L2": 8, "L3": 4},
                        tool_profile_counts={"mock_world": 15},
                        failure_mode_counts={"none": 14, "route_unavailable": 1},
                    ),
                ),
                benchmark_timing_summary=SimpleNamespace(
                    overall_total_duration_ms=SimpleNamespace(
                        p50_ms=446,
                        p95_ms=1564,
                        p99_ms=2011,
                    )
                ),
            )

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert result.blocking_failures
        assert latest_alias.read_text(encoding="utf-8") == '{"status":"keep"}'
        assert (
            output_root / f"release-gate-v1-{fixed_uuid}" / "suite-release_gate_v1-run-report.json"
        ).exists()
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_blocks_when_p95_exceeds_slo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    latest_alias = output_root / "latest-release_gate_v1-run-report.json"
    latest_alias.write_text('{"status":"keep"}', encoding="utf-8")

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: UUID("aaaaaaaa-1234-5678-1234-567812345678"))
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path, **_kwargs) -> None:
            self.report_dir = Path(report_dir)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            return _build_fake_report(report_path, p95_ms=5001)

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert any("p95_ms<=5000" in failure for failure in result.blocking_failures)
        assert result.latency_slo["status"] == "failed"
        assert latest_alias.read_text(encoding="utf-8") == '{"status":"keep"}'
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_blocks_when_max_exceeds_slo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: UUID("bbbbbbbb-1234-5678-1234-567812345678"))
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path, **_kwargs) -> None:
            self.report_dir = Path(report_dir)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            return _build_fake_report(report_path, max_ms=8001)

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert any("max_ms<=8000" in failure for failure in result.blocking_failures)
        assert result.max_duration_ms == 8001
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_blocks_when_case_timing_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: UUID("cccccccc-1234-5678-1234-567812345678"))
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path, **_kwargs) -> None:
            self.report_dir = Path(report_dir)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            case_results = _default_case_results(self.report_dir)
            case_results[4] = _make_case_result(self.report_dir, "case-05", None)
            return _build_fake_report(report_path, case_results=case_results)

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert any("Missing workflow_timing_summary.total_duration_ms" in failure for failure in result.blocking_failures)
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_blocks_when_focus_stage_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: UUID("dddddddd-1234-5678-1234-567812345678"))
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path, **_kwargs) -> None:
            self.report_dir = Path(report_dir)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            stages = [stage for stage in _default_stage_entries() if stage.node_name != "logical_planner_agent"]
            return _build_fake_report(report_path, stages=stages)

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is True
        assert any("Missing focus stage" in failure for failure in result.blocking_failures)
    finally:
        _cleanup_test_dir(output_root)


def test_main_returns_non_zero_when_bootstrap_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        release_gate,
        "run_benchmark_release_gate",
        lambda **_: (_ for _ in ()).throw(release_gate.BenchmarkReleaseGateError("bootstrap failed")),
    )

    exit_code = release_gate.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "bootstrap failed" in captured.err


def test_main_returns_non_zero_when_release_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = _make_test_dir()
    result = release_gate.BenchmarkReleaseGateResult(
        gate_id="release_gate_v1",
        suite_id="release_gate_v1",
        release_blocked=True,
        blocking_failures=["Expected failed_count=0, got 1."],
        run_status="failed",
        case_count=15,
        passed_count=14,
        failed_count=1,
        error_count=0,
        overall_score=0.94,
        run_directory=output_root / "release-gate-v1-123",
        suite_report_path=output_root / "release-gate-v1-123" / "suite-release_gate_v1-run-report.json",
        latest_report_path=output_root / "latest-release_gate_v1-run-report.json",
        trace_buffer_path=output_root / "release-gate-v1-123" / "release-gate-traces.jsonl",
        p50_duration_ms=446,
        p95_duration_ms=1564,
        p99_duration_ms=2011,
        max_duration_ms=2011,
        latency_slo=_make_latency_slo(),
        slow_cases=[{"rank": 1, "case_id": "case-01", "total_duration_ms": 2011, "workflow_status": "completed"}],
        slow_stages=[_make_stage_dict(_default_stage_entries()[0], rank=1)],
        focus_stages={
            "pre_flight_check_availability": _make_stage_dict(_default_stage_entries()[0]),
            "logical_planner_agent": _make_stage_dict(_default_stage_entries()[1]),
        },
    )
    monkeypatch.setattr(release_gate, "run_benchmark_release_gate", lambda **_: result)

    try:
        exit_code = release_gate.main()
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "Benchmark release gate failed." in captured.err
        assert "release_gate_v1" in captured.err
        assert "Expected failed_count=0, got 1." in captured.err
    finally:
        _cleanup_test_dir(output_root)


def test_main_prints_success_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = _make_test_dir()
    result = release_gate.BenchmarkReleaseGateResult(
        gate_id="release_gate_v1",
        suite_id="release_gate_v1",
        release_blocked=False,
        blocking_failures=[],
        run_status="passed",
        case_count=15,
        passed_count=15,
        failed_count=0,
        error_count=0,
        overall_score=1.0,
        run_directory=output_root / "release-gate-v1-123",
        suite_report_path=output_root / "release-gate-v1-123" / "suite-release_gate_v1-run-report.json",
        latest_report_path=output_root / "latest-release_gate_v1-run-report.json",
        trace_buffer_path=output_root / "release-gate-v1-123" / "release-gate-traces.jsonl",
        p50_duration_ms=446,
        p95_duration_ms=1564,
        p99_duration_ms=2011,
        max_duration_ms=2011,
        latency_slo=_make_latency_slo(),
        slow_cases=[{"rank": 1, "case_id": "case-01", "total_duration_ms": 2011, "workflow_status": "completed"}],
        slow_stages=[_make_stage_dict(_default_stage_entries()[0], rank=1)],
        focus_stages={
            "pre_flight_check_availability": _make_stage_dict(_default_stage_entries()[0]),
            "logical_planner_agent": _make_stage_dict(_default_stage_entries()[1]),
        },
    )
    monkeypatch.setattr(release_gate, "run_benchmark_release_gate", lambda **_: result)

    try:
        exit_code = release_gate.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Benchmark release gate passed." in captured.out
        assert "Gate: release_gate_v1" in captured.out
        assert "Suite: release_gate_v1" in captured.out
        assert "Timing: p50=446ms, p95=1564ms, p99=2011ms, max=2011ms" in captured.out
        assert "Latency SLO: p50<=2000ms, p95<=5000ms, max<=8000ms (passed)" in captured.out
        assert "Focus stages:" in captured.out
        assert "Slow cases:" in captured.out
        assert "Slow stages:" in captured.out
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_sorts_slow_cases_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: UUID("eeeeeeee-1234-5678-1234-567812345678"))
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path, **_kwargs) -> None:
            self.report_dir = Path(report_dir)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            case_results = _default_case_results(self.report_dir)
            case_results[0] = _make_case_result(self.report_dir, "case-b", 2011)
            case_results[1] = _make_case_result(self.report_dir, "case-a", 2011)
            return _build_fake_report(report_path, case_results=case_results)

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is False
        assert [entry["case_id"] for entry in result.slow_cases[:2]] == ["case-a", "case-b"]
        assert [entry["rank"] for entry in result.slow_cases[:2]] == [1, 2]
    finally:
        _cleanup_test_dir(output_root)


def test_run_benchmark_release_gate_sorts_slow_stages_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()

    monkeypatch.setattr(release_gate, "_bootstrap_runtime", lambda **_: None)
    monkeypatch.setattr(release_gate, "uuid4", lambda: UUID("ffffffff-1234-5678-1234-567812345678"))
    monkeypatch.setattr(release_gate, "SessionLocal", _FakeSession)
    monkeypatch.setattr(release_gate, "get_redis_client", _FakeRedis)
    monkeypatch.setattr(release_gate, "RedisKeyBuilder", _FakeRedisKeyBuilder)

    class FakeHarness:
        def __init__(self, _db_session, _cache, _rate_limiter, *, report_dir, trace_buffer_path, **_kwargs) -> None:
            self.report_dir = Path(report_dir)

        def run_suite(self, suite_id: str):
            assert suite_id == "release_gate_v1"
            report_path = self.report_dir / "suite-release_gate_v1-run-report.json"
            stages = [
                SimpleNamespace(
                    node_name="z-stage",
                    sample_count=15,
                    retry_case_count=0,
                    min_ms=1,
                    p50_ms=11,
                    p95_ms=2200,
                    p99_ms=2400,
                    max_ms=2500,
                    mean_ms=320.0,
                ),
                SimpleNamespace(
                    node_name="a-stage",
                    sample_count=15,
                    retry_case_count=0,
                    min_ms=1,
                    p50_ms=12,
                    p95_ms=2200,
                    p99_ms=2300,
                    max_ms=2500,
                    mean_ms=340.0,
                ),
                *_default_stage_entries(),
            ]
            return _build_fake_report(report_path, stages=stages)

    monkeypatch.setattr(release_gate, "BenchmarkHarness", FakeHarness)

    try:
        result = release_gate.run_benchmark_release_gate(output_root=output_root, start_services=False)

        assert result.release_blocked is False
        assert [entry["node_name"] for entry in result.slow_stages[:2]] == ["a-stage", "z-stage"]
        assert [entry["rank"] for entry in result.slow_stages[:2]] == [1, 2]
    finally:
        _cleanup_test_dir(output_root)


def _build_fake_report(
    report_path: Path,
    *,
    run_status: str = "passed",
    passed_count: int = 15,
    failed_count: int = 0,
    error_count: int = 0,
    overall_score: float = 1.0,
    p50_ms: int = 446,
    p95_ms: int = 1564,
    p99_ms: int = 2011,
    max_ms: int = 2011,
    case_results: list[SimpleNamespace] | None = None,
    stages: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "suite_id": "release_gate_v1",
        "report_path": str(report_path),
    }
    if report_path.exists():
        payload.update(json.loads(report_path.read_text(encoding="utf-8")))
        payload["suite_id"] = "release_gate_v1"
        payload["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    report_dir = report_path.parent
    case_results = case_results or _default_case_results(report_dir)
    stages = stages or _default_stage_entries()
    return SimpleNamespace(
        run_status=run_status,
        failed_count=failed_count,
        error_count=error_count,
        overall_score=overall_score,
        report_path=str(report_path),
        case_results=case_results,
        benchmark_summary=SimpleNamespace(
            suite_id="release_gate_v1",
            case_count=15,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            overall_score=overall_score,
            matrix_summary=SimpleNamespace(
                level_counts={"L1": 3, "L2": 8, "L3": 4},
                tool_profile_counts={"mock_world": 15},
                failure_mode_counts={"none": 14, "route_unavailable": 1},
            ),
        ),
        benchmark_timing_summary=SimpleNamespace(
            overall_total_duration_ms=SimpleNamespace(
                p50_ms=p50_ms,
                p95_ms=p95_ms,
                p99_ms=p99_ms,
                max_ms=max_ms,
            ),
            stages=stages,
        ),
    )


def _default_case_results(report_dir: Path) -> list[SimpleNamespace]:
    durations = [
        2011,
        1800,
        1700,
        1600,
        1500,
        1400,
        1300,
        1200,
        1100,
        1000,
        900,
        800,
        700,
        600,
        500,
    ]
    return [
        _make_case_result(report_dir, f"case-{index:02d}", duration)
        for index, duration in enumerate(durations, start=1)
    ]


def _make_case_result(report_dir: Path, case_id: str, total_duration_ms: int | None) -> SimpleNamespace:
    payload: dict[str, object] = {
        "case_id": case_id,
        "workflow_status": "completed",
        "report_path": str(report_dir / f"{case_id}-report.json"),
    }
    if total_duration_ms is not None:
        payload["workflow_timing_summary"] = SimpleNamespace(total_duration_ms=total_duration_ms)
    return SimpleNamespace(**payload)


def _default_stage_entries() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            node_name="pre_flight_check_availability",
            sample_count=15,
            retry_case_count=0,
            min_ms=138,
            p50_ms=162,
            p95_ms=1224,
            p99_ms=1224,
            max_ms=1224,
            mean_ms=232.41,
        ),
        SimpleNamespace(
            node_name="logical_planner_agent",
            sample_count=15,
            retry_case_count=0,
            min_ms=2,
            p50_ms=31,
            p95_ms=36,
            p99_ms=36,
            max_ms=36,
            mean_ms=26.24,
        ),
        SimpleNamespace(
            node_name="execute_searches",
            sample_count=15,
            retry_case_count=0,
            min_ms=8,
            p50_ms=10,
            p95_ms=20,
            p99_ms=20,
            max_ms=20,
            mean_ms=10.76,
        ),
    ]


def _make_latency_slo() -> dict[str, object]:
    return {
        "schema_version": "weekendpilot_release_gate_latency_slo_v1",
        "p50_threshold_ms": 2000,
        "p95_threshold_ms": 5000,
        "max_threshold_ms": 8000,
        "observed_p50_ms": 446,
        "observed_p95_ms": 1564,
        "observed_p99_ms": 2011,
        "observed_max_ms": 2011,
        "status": "passed",
    }


def _make_stage_dict(stage: SimpleNamespace, *, rank: int | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_name": stage.node_name,
        "sample_count": stage.sample_count,
        "retry_case_count": stage.retry_case_count,
        "min_ms": stage.min_ms,
        "p50_ms": stage.p50_ms,
        "p95_ms": stage.p95_ms,
        "p99_ms": stage.p99_ms,
        "max_ms": stage.max_ms,
        "mean_ms": stage.mean_ms,
    }
    if rank is not None:
        payload["rank"] = rank
    return payload


def _make_test_dir() -> Path:
    path = Path("var/test-release-gate") / str(uuid4())
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
