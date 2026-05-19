from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.observability import (
    InternalObservabilityRunNotFoundError,
    InternalObservabilityService,
    LangSmithRecorder,
    LocalTraceBuffer,
    ObservabilityError,
    ObservabilityRecorder,
    sanitize_trace_payload,
)
from backend.app.observability.summary import load_run_summary
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
            "items": [{"prompt_version": "prompt-v1"}, {"prompt_template": "hide-me"}, {"normal": "ok"}],
        },
        "debug_trace": {"raw": "hidden"},
    }

    sanitized = sanitize_trace_payload(payload)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["Authorization"] == "[REDACTED]"
    assert sanitized["nested"]["items"][0]["prompt_version"] == "prompt-v1"
    assert sanitized["nested"]["items"][1]["prompt_template"] == "[REDACTED]"
    assert sanitized["nested"]["items"][2]["normal"] == "ok"
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
    timing_summary = {
        "schema_version": "workflow_timing_summary_v1",
        "total_duration_ms": 42,
        "stage_count": 1,
        "stages": [
            {
                "node_name": "initialize",
                "attempt_count": 1,
                "total_duration_ms": 42,
            }
        ],
    }
    run = _create_run(
        db_session,
        metadata_json={
            "nested": {"secret_token": "hidden", "safe": "value"},
            "workflow": {"timing": timing_summary},
            "agents": {
                "results": [
                    {"role": "supervisor"},
                    {"role": "discovery"},
                ]
            },
            "demo": {
                "trace_id": "trace-demo-existing",
                "initial_error": {
                    "error_type": "tool_timeout",
                    "message": "Request failed",
                    "details": {
                        "api_key": "hide-me",
                        "authorization": "Bearer secret",
                        "visible": "safe-detail",
                    },
                    "stack_trace": "must-not-leak",
                },
            },
        },
    )
    selected = PlanRepository(db_session).create(
        run_id=run.run_id,
        status="selected",
        selected=True,
        plan_json={
            "execution": {"status": "succeeded"},
            "feedback": {"status": "completed"},
        },
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="mock_world",
        request_json={"query": "museum"},
        response_json={"candidate_count": 3},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=12,
        langsmith_trace_id="trace-demo-existing",
    )
    ActionLedgerRepository(db_session).create(
        run_id=run.run_id,
        action_type="reserve_restaurant",
        target_id="green-table",
        idempotency_key=f"reserve:{run.run_id}",
        status="succeeded",
        request_json={"plan_id": str(selected.plan_id)},
        response_json={"reservation": "ok"},
        error_json=None,
    )
    context = _recorder(db_session, trace_path).build_context(run.run_id)

    result = _recorder(db_session, trace_path).record_run_summary(context)

    assert result.status == "completed"
    assert result.local_buffer_written is True
    row = AgentRunRepository(db_session).get_by_id(run.run_id)
    assert row is not None
    observability = row.metadata_json["observability"]
    summary = row.metadata_json["summary"]
    assert observability["trace_id"] == context.trace_id
    assert observability["local_buffer"]["written"] is True
    assert observability["langsmith"]["posted"] is False
    assert summary["schema_version"] == "weekendpilot_run_summary_v1"
    assert summary["run_id"] == str(run.run_id)
    assert summary["trace_id"] == context.trace_id
    assert summary["prompt_version"] == "prompt-v1"
    assert summary["selected_plan_id"] == str(selected.plan_id)
    assert summary["tool_event_count"] == 1
    assert summary["action_count"] == 1
    assert summary["agent_roles"] == ["supervisor", "discovery"]
    assert summary["workflow_timing_summary"] == timing_summary
    assert summary["error"] == {
        "error_type": "tool_timeout",
        "message": "Request failed",
        "source": "demo.initial_error",
        "details": {
            "api_key": "[REDACTED]",
            "authorization": "[REDACTED]",
            "visible": "safe-detail",
            "stack_trace": "[REDACTED]",
        },
    }

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["schema_version"] == "weekendpilot_trace_v1"
    assert payload["run_summary"] == summary
    assert payload["workflow_timing_summary"] == timing_summary
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


def test_record_run_summary_promotes_workflow_timing_summary_to_top_level(
    db_session: Session,
    trace_path,
) -> None:
    timing_summary = {
        "schema_version": "workflow_timing_summary_v1",
        "total_duration_ms": 42,
        "stage_count": 2,
        "stages": [
            {
                "node_name": "initialize",
                "attempt_count": 1,
                "total_duration_ms": 5,
            },
            {
                "node_name": "execute_searches",
                "attempt_count": 2,
                "total_duration_ms": 37,
            },
        ],
    }
    run = _create_run(
        db_session,
        metadata_json={
            "workflow": {
                "source": "observability-test",
                "timing": timing_summary,
            }
        },
    )
    recorder = _recorder(db_session, trace_path)
    context = recorder.build_context(run.run_id)

    recorder.record_run_summary(context)

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["workflow_timing_summary"] == timing_summary
    assert payload["workflow_timing_summary"]["stages"][1]["attempt_count"] == 2


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


def test_internal_observability_service_builds_sanitized_run_summary(db_session: Session) -> None:
    run = _create_run(
        db_session,
        metadata_json={
            "workflow": {
                "timing": {
                    "schema_version": "workflow_timing_summary_v1",
                    "total_duration_ms": 42,
                    "stage_count": 2,
                    "stages": [
                        {
                            "node_name": "initialize",
                            "attempt_count": 1,
                            "total_duration_ms": 5,
                        },
                        {
                            "node_name": "execute_searches",
                            "attempt_count": 2,
                            "total_duration_ms": 37,
                        },
                    ],
                }
            },
            "observability": {
                "trace_id": "trace-observability",
                "status": "completed",
                "local_buffer": {
                    "written": True,
                    "path": "var/traces/trace.jsonl",
                    "error": {"api_key": "hide-me", "message": "buffer-failed"},
                },
                "langsmith": {
                    "enabled": False,
                    "posted": False,
                    "error": "langsmith-down",
                },
            },
            "agents": {
                "results": [
                    {"role": "supervisor"},
                    {"role": "discovery"},
                    {"role": "dining"},
                ]
            },
            "demo": {
                "trace_id": "trace-demo",
                "initial_node_history": ["initialize", "wait_confirmation"],
                "continuation_history": ["saga_execution_engine", "generate_summary_message"],
            },
        },
    )
    selected = PlanRepository(db_session).create(
        run_id=run.run_id,
        status="selected",
        selected=True,
        plan_json={
            "execution": {"status": "succeeded", "action_id": "should-hide"},
            "feedback": {"status": "completed", "token": "hide-me"},
        },
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="mock_world",
        request_json={"query": "museum"},
        response_json={"candidate_count": 3},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=12,
        langsmith_trace_id="trace-observability",
    )
    ActionLedgerRepository(db_session).create(
        run_id=run.run_id,
        action_type="reserve_restaurant",
        target_id="green-table",
        idempotency_key="reserve:1",
        status="succeeded",
        request_json={"plan_id": str(selected.plan_id)},
        response_json={"reservation": "ok"},
        error_json=None,
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert str(summary.run_id) == str(run.run_id)
    assert summary.status == "completed"
    assert summary.trace_id == "trace-demo"
    assert summary.case_id == "case-observability"
    assert summary.tool_event_count == 1
    assert summary.action_count == 1
    assert summary.execution_status == "succeeded"
    assert summary.feedback_status == "completed"
    assert summary.observability_status == "completed"
    assert summary.agent_roles == ["supervisor", "discovery", "dining"]
    assert summary.node_history == [
        "initialize",
        "wait_confirmation",
        "saga_execution_engine",
        "generate_summary_message",
    ]
    assert len(summary.tool_event_summaries) == 1
    assert summary.tool_event_summaries[0].tool_name == "search_poi"
    assert summary.tool_event_summaries[0].request_preview == {"query": "museum"}
    assert summary.tool_event_summaries[0].response_preview == {"candidate_count": 3}
    assert summary.tool_event_summaries[0].error_preview is None
    assert len(summary.action_ledger_summaries) == 1
    assert summary.action_ledger_summaries[0].action_type == "reserve_restaurant"
    assert summary.action_ledger_summaries[0].target_id == "green-table"
    assert summary.action_ledger_summaries[0].request_preview == {"plan_id": "[REDACTED]"}
    assert summary.action_ledger_summaries[0].response_preview == {"reservation": "ok"}
    assert summary.action_ledger_summaries[0].error_preview is None
    assert summary.workflow_timing_summary is not None
    assert summary.workflow_timing_summary.total_duration_ms == 42
    assert summary.observability_summary.trace_id == "trace-observability"
    assert summary.observability_summary.local_buffer_written is True
    assert summary.observability_summary.local_buffer_error == {"api_key": "[REDACTED]", "message": "buffer-failed"}
    assert summary.observability_summary.langsmith_error == "langsmith-down"


def test_internal_observability_service_handles_missing_optional_metadata(db_session: Session) -> None:
    run = _create_run(db_session, metadata_json={"safe": "value"})

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.trace_id is None
    assert summary.execution_status is None
    assert summary.feedback_status is None
    assert summary.observability_status is None
    assert summary.agent_roles == []
    assert summary.node_history == []
    assert summary.tool_event_summaries == []
    assert summary.action_ledger_summaries == []
    assert summary.workflow_timing_summary is None
    assert summary.observability_summary.trace_id is None
    assert summary.observability_summary.status is None
    assert summary.observability_summary.local_buffer_written is None
    assert summary.observability_summary.langsmith_enabled is None
    assert summary.observability_summary.langsmith_posted is None
    assert summary.observability_summary.local_buffer_error is None
    assert summary.observability_summary.langsmith_error is None


def test_load_run_summary_returns_none_for_malformed_stored_summary() -> None:
    assert load_run_summary({"summary": {"run_id": "not-a-uuid"}}) is None


def test_internal_observability_service_prefers_canonical_summary_when_present(db_session: Session) -> None:
    run = _create_run(
        db_session,
        metadata_json={
            "summary": {
                "schema_version": "weekendpilot_run_summary_v1",
                "run_id": str(uuid4()),
                "trace_id": "trace-from-summary",
                "case_id": "case-observability",
                "agent_version": "agent-v1",
                "prompt_version": "prompt-v1",
                "tool_profile": "mock_world",
                "world_profile": "family_afternoon",
                "failure_profile": None,
                "workflow_status": "completed",
                "selected_plan_id": str(uuid4()),
                "plan_status": "selected",
                "execution_status": "summary-executed",
                "feedback_status": "summary-feedback",
                "tool_event_count": 9,
                "action_count": 4,
                "agent_roles": ["summary-supervisor", "summary-discovery"],
                "workflow_timing_summary": {
                    "schema_version": "workflow_timing_summary_v1",
                    "total_duration_ms": 99,
                    "stage_count": 1,
                    "stages": [
                        {
                            "node_name": "initialize",
                            "attempt_count": 1,
                            "total_duration_ms": 99,
                        }
                    ],
                },
                "error": None,
            },
            "workflow": {
                "timing": {
                    "schema_version": "workflow_timing_summary_v1",
                    "total_duration_ms": 25,
                    "stage_count": 1,
                    "stages": [
                        {
                            "node_name": "execute_searches",
                            "attempt_count": 1,
                            "total_duration_ms": 25,
                        }
                    ],
                }
            },
            "observability": {
                "trace_id": "trace-observability",
                "status": "completed",
                "local_buffer": {"written": True, "error": None},
                "langsmith": {"enabled": False, "posted": False, "error": None},
            },
            "agents": {
                "results": [
                    {"role": "legacy-supervisor"},
                    {"role": "legacy-discovery"},
                ]
            },
            "demo": {"trace_id": "trace-demo"},
        },
    )
    PlanRepository(db_session).create(
        run_id=run.run_id,
        status="selected",
        selected=True,
        plan_json={
            "execution": {"status": "legacy-executed"},
            "feedback": {"status": "legacy-feedback"},
        },
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="mock_world",
        request_json={"query": "museum"},
        response_json={"candidate_count": 1},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=10,
        langsmith_trace_id="trace-observability",
    )
    ActionLedgerRepository(db_session).create(
        run_id=run.run_id,
        action_type="reserve_restaurant",
        target_id="green-table",
        idempotency_key=f"reserve:{run.run_id}",
        status="succeeded",
        request_json={"foo": "bar"},
        response_json={"result": "ok"},
        error_json=None,
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.trace_id == "trace-from-summary"
    assert summary.tool_event_count == 9
    assert summary.action_count == 4
    assert summary.execution_status == "summary-executed"
    assert summary.feedback_status == "summary-feedback"
    assert summary.agent_roles == ["summary-supervisor", "summary-discovery"]
    assert summary.workflow_timing_summary is not None
    assert summary.workflow_timing_summary.total_duration_ms == 99
    assert summary.observability_status == "completed"
    assert summary.observability_summary.trace_id == "trace-observability"


def test_internal_observability_service_raises_for_missing_run(db_session: Session) -> None:
    with pytest.raises(InternalObservabilityRunNotFoundError):
        InternalObservabilityService(db_session).get_run_summary(uuid4())
