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
            return SimpleNamespace(
                run_status="passed",
                failed_count=0,
                error_count=0,
                overall_score=1.0,
                report_path=str(report_path),
                benchmark_summary=SimpleNamespace(
                    suite_id="release_gate_v1",
                    case_count=15,
                    passed_count=15,
                    failed_count=0,
                    error_count=0,
                    overall_score=1.0,
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

        assert latest_alias.read_bytes() == captured["report_bytes"]
        copied_payload = json.loads(latest_alias.read_text(encoding="utf-8"))
        assert copied_payload["nested"]["report_path"] == str(result.suite_report_path)
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
            return SimpleNamespace(
                run_status="passed",
                failed_count=0,
                error_count=0,
                overall_score=1.0,
                report_path=str(report_path),
                benchmark_summary=SimpleNamespace(
                    suite_id="release_gate_v1",
                    case_count=15,
                    passed_count=15,
                    failed_count=0,
                    error_count=0,
                    overall_score=1.0,
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
    )
    monkeypatch.setattr(release_gate, "run_benchmark_release_gate", lambda **_: result)

    try:
        exit_code = release_gate.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Benchmark release gate passed." in captured.out
        assert "Gate: release_gate_v1" in captured.out
        assert "Suite: release_gate_v1" in captured.out
        assert "Timing: p50=446ms, p95=1564ms, p99=2011ms" in captured.out
    finally:
        _cleanup_test_dir(output_root)


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
