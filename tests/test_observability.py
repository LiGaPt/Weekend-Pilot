from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.observability import (
    LangSmithRecorder,
    LocalTraceBuffer,
    ObservabilityError,
    ObservabilityRecorder,
    sanitize_trace_payload,
)
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)


@pytest.fixture()
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def trace_path():
    directory = Path("var/test-traces") / str(uuid4())
    path = directory / "weekendpilot-traces.jsonl"
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()
        if directory.exists():
            directory.rmdir()


def _create_run(session: Session, *, metadata_json: dict | None = None):
    user = UserRepository(session).create(
        external_id=f"observability-user-{uuid4()}",
        display_name="Observability Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-observability",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="completed",
        metadata_json=metadata_json or {"source": "observability-test"},
    )


def _recorder(session: Session, buffer_path, langsmith=None) -> ObservabilityRecorder:
    return ObservabilityRecorder(
        runs=AgentRunRepository(session),
        tool_events=ToolEventRepository(session),
        action_ledger=ActionLedgerRepository(session),
        plans=PlanRepository(session),
        local_buffer=LocalTraceBuffer(buffer_path),
        langsmith=langsmith,
    )


def test_context_builds_from_agent_run(db_session: Session, trace_path) -> None:
    run = _create_run(db_session, metadata_json={"safe": "value"})

    context = _recorder(db_session, trace_path).build_context(run.run_id)

    assert context.run_id == run.run_id
    assert context.case_id == "case-observability"
    assert context.project_name == "weekend-pilot"
    assert context.trace_id
    assert context.agent_version == "agent-v1"
    assert context.metadata == {"safe": "value"}


def test_context_missing_run_raises(db_session: Session, trace_path) -> None:
    with pytest.raises(ObservabilityError):
        _recorder(db_session, trace_path).build_context(uuid4())


def test_sanitizer_redacts_sensitive_keys_recursively() -> None:
    payload = {
        "api_key": "abc",
        "nested": {
            "Authorization": "Bearer token",
            "keep": "visible",
            "items": [{"prompt_version": "hide-me"}, {"normal": "ok"}],
        },
        "debug_trace": {"raw": "hidden"},
    }

    sanitized = sanitize_trace_payload(payload)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["Authorization"] == "[REDACTED]"
    assert sanitized["nested"]["items"][0]["prompt_version"] == "[REDACTED]"
    assert sanitized["nested"]["items"][1]["normal"] == "ok"
    assert sanitized["debug_trace"] == "[REDACTED]"


def test_local_buffer_creates_parent_directory_and_writes_jsonl(trace_path) -> None:
    result = LocalTraceBuffer(trace_path).write({"trace_id": "trace-1", "token": "secret"})

    assert result.local_buffer_written is True
    assert result.local_buffer_path == str(trace_path)
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"trace_id": "trace-1", "token": "[REDACTED]"}]


def test_langsmith_recorder_is_noop_when_disabled_or_missing_key() -> None:
    disabled = LangSmithRecorder(enabled=False, api_key=None, project_name="weekend-pilot")
    missing_key = LangSmithRecorder(enabled=True, api_key=None, project_name="weekend-pilot")

    assert disabled.post_summary({"trace_id": "trace-1"}).enabled is False
    missing_result = missing_key.post_summary({"trace_id": "trace-1"})
    assert missing_result.enabled is True
    assert missing_result.posted is False
    assert missing_result.error is None


def test_record_run_summary_writes_buffer_and_updates_run_metadata(db_session: Session, trace_path) -> None:
    run = _create_run(db_session, metadata_json={"nested": {"secret_token": "hidden", "safe": "value"}})
    context = _recorder(db_session, trace_path).build_context(run.run_id)

    result = _recorder(db_session, trace_path).record_run_summary(context)

    assert result.status == "completed"
    assert result.local_buffer_written is True
    row = AgentRunRepository(db_session).get_by_id(run.run_id)
    assert row is not None
    observability = row.metadata_json["observability"]
    assert observability["trace_id"] == context.trace_id
    assert observability["local_buffer"]["written"] is True
    assert observability["langsmith"]["posted"] is False

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["schema_version"] == "weekendpilot_trace_v1"
    assert payload["metadata"]["nested"]["secret_token"] == "[REDACTED]"
    assert "action_id" not in json.dumps(payload)
    assert "tool_event_id" not in json.dumps(payload)


def test_record_run_summary_uses_latest_sanitized_agent_metadata(
    db_session: Session,
    trace_path,
) -> None:
    run = _create_run(db_session, metadata_json={"workflow": {"source": "test"}})
    recorder = _recorder(db_session, trace_path)
    context = recorder.build_context(run.run_id)
    AgentRunRepository(db_session).update_metadata_json(
        run.run_id,
        {
            "workflow": {"source": "test"},
            "agents": {
                "version": "bounded_agents_v1",
                "results": [
                    {
                        "role": "discovery",
                        "status": "completed",
                        "summary": "LLM discovery summary.",
                        "adapter_version": "llm_discovery_v0",
                        "tool_names_used": ["get_poi_detail"],
                        "output_json": {
                            "llm": {
                                "provider_kind": "openai_compatible",
                                "model_id": "qwen3.6-plus",
                                "base_url_host": "dashscope.aliyuncs.com",
                                "latency_ms": 12,
                                "usage": {
                                    "input_count": 3,
                                    "output_count": 2,
                                    "total_count": 5,
                                },
                                "status": "completed",
                                "prompt_tokens": 3,
                            }
                        },
                    }
                ],
            },
        },
    )

    recorder.record_run_summary(context)

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    llm = payload["metadata"]["agents"]["results"][0]["output_json"]["llm"]
    assert llm["model_id"] == "qwen3.6-plus"
    assert llm["usage"] == {
        "input_count": 3,
        "output_count": 2,
        "total_count": 5,
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert "prompt_tokens" not in serialized
    assert "completion_tokens" not in serialized
    assert "total_tokens" not in serialized
    assert "api_key" not in serialized
    assert "authorization" not in serialized


def test_agent_run_metadata_update_does_not_self_commit() -> None:
    session = SessionLocal()
    try:
        run = _create_run(session)
        run_id = run.run_id
        AgentRunRepository(session).update_metadata_json(run_id, {"observability": {"trace_id": "trace-1"}})
        session.rollback()
    finally:
        session.close()

    verification_session = SessionLocal()
    try:
        assert AgentRunRepository(verification_session).get_by_id(run_id) is None
    finally:
        verification_session.close()
