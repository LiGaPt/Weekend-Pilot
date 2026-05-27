from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.benchmark.release_gate import run_benchmark_release_gate
from backend.app.llm import LLMCallMetadata, LLMChatCompletion, LLMUsage
from backend.app.models.runtime import AgentRun


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


def test_benchmark_release_gate_runs_release_gate_v1_and_refreshes_latest_alias() -> None:
    output_root = _make_test_dir()

    try:
        result = run_benchmark_release_gate(output_root=output_root, start_services=False)

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
        assert result.run_directory.exists()
        assert result.suite_report_path.exists()
        assert result.latest_report_path.exists()
        assert result.trace_buffer_path.exists()
        assert result.p50_duration_ms is not None
        assert result.p95_duration_ms is not None
        assert result.p99_duration_ms is not None
        assert result.max_duration_ms is not None
        assert result.latency_slo["status"] == "passed"
        assert len(result.slow_cases) == 15
        assert result.slow_stages
        assert "pre_flight_check_availability" in result.focus_stages
        assert "logical_planner_agent" in result.focus_stages

        case_report_paths = [path for path in result.run_directory.glob("*.json") if path.is_file()]
        assert len(case_report_paths) >= 16

        suite_bytes = result.suite_report_path.read_bytes()
        latest_bytes = result.latest_report_path.read_bytes()
        assert latest_bytes == suite_bytes

        suite_payload = json.loads(result.suite_report_path.read_text(encoding="utf-8"))
        latest_payload = json.loads(result.latest_report_path.read_text(encoding="utf-8"))
        assert suite_payload["benchmark_summary"]["suite_id"] == "release_gate_v1"
        assert suite_payload["benchmark_summary"]["case_count"] == 15
        assert suite_payload["benchmark_summary"]["passed_count"] == 15
        assert suite_payload["benchmark_summary"]["failed_count"] == 0
        assert suite_payload["benchmark_summary"]["error_count"] == 0
        assert suite_payload["benchmark_summary"]["matrix_summary"]["level_counts"] == {"L1": 3, "L2": 8, "L3": 4}
        assert suite_payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == {"mock_world": 15}
        assert suite_payload["benchmark_summary"]["matrix_summary"]["failure_mode_counts"] == {
            "none": 14,
            "route_unavailable": 1,
        }
        assert suite_payload["report_path"] == str(result.suite_report_path)
        assert latest_payload["report_path"] == str(result.suite_report_path)
        assert latest_payload["benchmark_summary"]["suite_id"] == "release_gate_v1"
        assert latest_payload["benchmark_summary"]["case_count"] == 15
        assert suite_payload["release_gate_evaluation"]["latency_slo"]["p50_threshold_ms"] == 2000
        assert suite_payload["release_gate_evaluation"]["latency_slo"]["p95_threshold_ms"] == 5000
        assert suite_payload["release_gate_evaluation"]["latency_slo"]["max_threshold_ms"] == 8000
        assert suite_payload["release_gate_evaluation"]["latency_slo"]["observed_max_ms"] == result.max_duration_ms
        assert latest_payload["release_gate_evaluation"] == suite_payload["release_gate_evaluation"]
        assert len(suite_payload["release_gate_evaluation"]["slow_cases"]) == 15
        assert suite_payload["release_gate_evaluation"]["focus_stages"]["pre_flight_check_availability"]["node_name"] == (
            "pre_flight_check_availability"
        )
        assert suite_payload["release_gate_evaluation"]["focus_stages"]["logical_planner_agent"]["node_name"] == (
            "logical_planner_agent"
        )
        slow_cases = suite_payload["release_gate_evaluation"]["slow_cases"]
        assert slow_cases == sorted(
            slow_cases,
            key=lambda entry: (-entry["total_duration_ms"], entry["case_id"]),
        )
        assert all(
            str(result.run_directory) in case_result["report_path"]
            for case_result in latest_payload["case_results"]
            if case_result.get("report_path")
        )

        serialized_suite = json.dumps(suite_payload, sort_keys=True)
        for forbidden in FORBIDDEN_REPORT_TEXT:
            assert forbidden not in serialized_suite
    finally:
        _cleanup_test_dir(output_root)


def test_benchmark_release_gate_ignores_fake_llm_preview_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = _make_test_dir()
    created_clients: list[object] = []
    chat_calls: list[dict[str, object]] = []
    session = SessionLocal()

    class FakeOpenAICompatibleChatClient:
        def __init__(self, *args, **kwargs) -> None:
            created_clients.append(self)

        def chat_json(self, *, messages, temperature=0.2, max_tokens=400):
            chat_calls.append(
                {
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            payload = json.loads(messages[-1].content)
            if "candidates" in payload:
                candidate_ids = [candidate["candidate_id"] for candidate in payload["candidates"]]
                return LLMChatCompletion(
                    content_json={
                        "summary": "preview candidate summary",
                        "candidate_ids": candidate_ids[:1],
                        "tool_names_used": [],
                        "risk_codes": [],
                    },
                    metadata=LLMCallMetadata(
                        provider_kind="openai_compatible",
                        model_id="preview-model",
                        base_url_host="llm.example.test",
                        latency_ms=5,
                        usage=LLMUsage(input_count=4, output_count=3, total_count=7),
                        status="completed",
                    ),
                )
            draft_ids = [draft["draft_id"] for draft in payload["drafts"]]
            return LLMChatCompletion(
                content_json={
                    "summary": "preview itinerary summary",
                    "draft_ids": draft_ids[:1],
                },
                metadata=LLMCallMetadata(
                    provider_kind="openai_compatible",
                    model_id="preview-model",
                    base_url_host="llm.example.test",
                    latency_ms=5,
                    usage=LLMUsage(input_count=4, output_count=3, total_count=7),
                    status="completed",
                ),
            )

    before_run_ids = set(session.scalars(select(AgentRun.run_id)).all())
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_API_KEY", "preview-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "preview-model")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "langsmith-preview-key")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://langsmith.example.test")
    monkeypatch.setattr("backend.app.agents.factory.OpenAICompatibleChatClient", FakeOpenAICompatibleChatClient)
    get_settings.cache_clear()

    try:
        result = run_benchmark_release_gate(output_root=output_root, start_services=False)
        after_run_ids = set(session.scalars(select(AgentRun.run_id)).all())
        new_run_ids = sorted(after_run_ids - before_run_ids)
        new_runs = session.scalars(
            select(AgentRun).where(AgentRun.run_id.in_(new_run_ids))
        ).all()

        assert result.release_blocked is False
        assert created_clients == []
        assert chat_calls == []
        assert len(new_runs) >= 15

        forbidden_versions = {
            "llm_discovery_v0",
            "llm_dining_v0",
            "llm_itinerary_planner_v0",
        }
        observed_versions = set()
        for run in new_runs:
            metadata = run.metadata_json if isinstance(run.metadata_json, dict) else {}
            agents = metadata.get("agents")
            if not isinstance(agents, dict):
                continue
            results = agents.get("results")
            if not isinstance(results, list):
                continue
            for entry in results:
                if isinstance(entry, dict) and isinstance(entry.get("adapter_version"), str):
                    observed_versions.add(entry["adapter_version"])

        assert forbidden_versions.isdisjoint(observed_versions)
        assert "deterministic_discovery_v1" in observed_versions
        assert "deterministic_dining_v1" in observed_versions
        assert "deterministic_itinerary_planner_v1" in observed_versions
    finally:
        session.rollback()
        session.close()
        get_settings.cache_clear()
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
