from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.benchmark import load_benchmark_case
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


def _create_run(
    session: Session,
    *,
    metadata_json: dict | None = None,
    tool_profile: str = "mock_world",
    world_profile: str = "family_afternoon",
):
    user = UserRepository(session).create(
        external_id=f"observability-user-{uuid4()}",
        display_name="Observability Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-observability",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile=tool_profile,
        world_profile=world_profile,
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
    assert summary["preview_diagnostics"] is None
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


def test_record_run_summary_adds_amap_preview_diagnostics(
    db_session: Session,
    trace_path,
) -> None:
    run = _create_run(
        db_session,
        metadata_json={"source": "observability-test"},
        tool_profile="amap",
        world_profile="amap_shanghai_live",
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="amap",
        request_json={"query": "museum"},
        response_json={"candidate_count": 2},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=12,
        langsmith_trace_id="trace-amap",
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="check_route",
        tool_type="read",
        provider="amap",
        request_json={"origin": "a", "destination": "b"},
        response_json=None,
        error_json={"error_type": "rate_limited", "api_key": "hide-me"},
        status="failed",
        cache_hit=False,
        latency_ms=25,
        langsmith_trace_id="trace-amap",
    )

    context = _recorder(db_session, trace_path).build_context(run.run_id)
    _recorder(db_session, trace_path).record_run_summary(context)

    row = AgentRunRepository(db_session).get_by_id(run.run_id)
    assert row is not None
    summary = row.metadata_json["summary"]
    assert summary["preview_diagnostics"] == {
        "schema_version": "weekendpilot_preview_diagnostics_v1",
        "read_profile": "amap",
        "mode": "read_only_preview",
        "confirmation_allowed": False,
        "confirmation_block_reason": "AMAP read-only demo runs cannot be confirmed.",
        "benchmark_eligible": False,
        "benchmark_block_reason": "Canonical benchmark suites support Mock World only.",
        "observed_provider_names": ["amap"],
        "provider_event_count": 2,
        "write_tool_event_count": 0,
        "provider_error_types": ["rate_limited"],
        "cross_provider_fallback_detected": False,
    }


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
        request_json={
            "plan_id": str(selected.plan_id),
            "idempotency_key": "internal-confirmation-key",
        },
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
    assert summary.tool_event_summaries[0].request_preview == {
        "query": "museum",
        "event_sequence": 1,
    }
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
    assert summary.benchmark_artifact_summary is None


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
    assert summary.benchmark_artifact_summary is None
    assert summary.recovery_path_summary is None


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
                "preview_diagnostics": {
                    "schema_version": "weekendpilot_preview_diagnostics_v1",
                    "read_profile": "amap",
                    "mode": "read_only_preview",
                    "confirmation_allowed": False,
                    "confirmation_block_reason": "AMAP read-only demo runs cannot be confirmed.",
                    "benchmark_eligible": False,
                    "benchmark_block_reason": "Canonical benchmark suites support Mock World only.",
                    "observed_provider_names": ["amap"],
                    "provider_event_count": 9,
                    "write_tool_event_count": 0,
                    "provider_error_types": [],
                    "cross_provider_fallback_detected": False,
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
    assert summary.preview_diagnostics is not None
    assert summary.preview_diagnostics.provider_event_count == 9


def test_internal_observability_service_recomputes_missing_preview_diagnostics_for_amap_runs(
    db_session: Session,
) -> None:
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
                "tool_profile": "amap",
                "world_profile": "amap_shanghai_live",
                "failure_profile": None,
                "workflow_status": "awaiting_confirmation",
                "selected_plan_id": None,
                "plan_status": None,
                "execution_status": None,
                "feedback_status": None,
                "tool_event_count": 2,
                "action_count": 0,
                "agent_roles": ["summary-supervisor"],
                "workflow_timing_summary": None,
                "preview_diagnostics": None,
                "error": None,
            }
        },
        tool_profile="amap",
        world_profile="amap_shanghai_live",
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="amap",
        request_json={"query": "museum"},
        response_json={"candidate_count": 1},
        error_json=None,
        status="completed",
        cache_hit=False,
        latency_ms=10,
        langsmith_trace_id="trace-observability",
    )
    ToolEventRepository(db_session).create(
        run_id=run.run_id,
        tool_name="check_route",
        tool_type="read",
        provider="amap",
        request_json={"origin": "a", "destination": "b"},
        response_json=None,
        error_json={"code": "route_infeasible", "api_key": "hide-me"},
        status="failed",
        cache_hit=False,
        latency_ms=11,
        langsmith_trace_id="trace-observability",
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.preview_diagnostics is not None
    assert summary.preview_diagnostics.provider_event_count == 2
    assert summary.preview_diagnostics.provider_error_types == ["route_infeasible"]
    assert summary.preview_diagnostics.cross_provider_fallback_detected is False


def test_internal_observability_service_raises_for_missing_run(db_session: Session) -> None:
    with pytest.raises(InternalObservabilityRunNotFoundError):
        InternalObservabilityService(db_session).get_run_summary(uuid4())


def test_internal_observability_service_returns_benchmark_artifact_summary_when_present(
    db_session: Session,
) -> None:
    case = load_benchmark_case("solo_afternoon_v1")
    run = _create_run(
        db_session,
        metadata_json={
            "benchmark": {
                "case_id": case.case_id,
                "title": case.title,
                "workflow_backed": True,
                "taxonomy": case.taxonomy.model_dump(mode="json"),
                "artifact_summary": {
                    "schema_version": "weekendpilot_benchmark_artifact_summary_v1",
                    "benchmark_status": "passed",
                    "overall_score": 0.9583,
                    "workflow_status": "completed",
                    "tool_event_count": 8,
                    "action_count": 1,
                    "failure_reasons": [],
                    "memory_policy_summary": {
                        "policy_version": "memory_query_policy_v1",
                        "considered_count": 1,
                        "used_count": 0,
                        "ignored_count": 0,
                        "downgraded_count": 1,
                        "overridden_count": 0,
                        "primary_influence_count": 0,
                        "advisory_influence_count": 1,
                        "no_influence_count": 0,
                    },
                    "score_summaries": [
                        {
                            "name": "workflow_path",
                            "status": "passed",
                            "score": 1.0,
                            "reason": "Workflow reached the expected path.",
                        }
                    ],
                    "report_path": "var/benchmarks/solo_afternoon_v1.json",
                },
            }
        },
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.benchmark_artifact_summary is not None
    assert summary.benchmark_artifact_summary.case_id == "solo_afternoon_v1"
    assert summary.benchmark_artifact_summary.registered_suite_ids == [
        "baseline",
        "default",
        "release_gate_v1",
        "all_registered",
    ]
    assert summary.benchmark_artifact_summary.taxonomy is not None
    assert summary.benchmark_artifact_summary.taxonomy.scenario_bucket == "solo"
    assert summary.benchmark_artifact_summary.benchmark_status == "passed"
    assert summary.benchmark_artifact_summary.overall_score == 0.9583
    assert summary.benchmark_artifact_summary.memory_policy_summary is not None
    assert summary.benchmark_artifact_summary.memory_policy_summary.downgraded_count == 1
    assert summary.benchmark_artifact_summary.score_summaries[0].status == "passed"
    assert summary.benchmark_artifact_summary.report_path == "var/benchmarks/solo_afternoon_v1.json"


def test_internal_observability_service_falls_back_to_workflow_memory_policy_summary_when_artifact_summary_missing(
    db_session: Session,
) -> None:
    case = load_benchmark_case("family_route_failure_v1")
    run = _create_run(
        db_session,
        metadata_json={
            "benchmark": {
                "case_id": case.case_id,
                "title": case.title,
                "workflow_backed": True,
                "taxonomy": case.taxonomy.model_dump(mode="json"),
            }
        }
        | {
            "workflow": {
                "memory_policy": {
                    "policy_summary": {
                        "policy_version": "memory_query_policy_v1",
                        "considered_count": 1,
                        "used_count": 0,
                        "ignored_count": 1,
                        "downgraded_count": 0,
                        "overridden_count": 0,
                        "primary_influence_count": 0,
                        "advisory_influence_count": 0,
                        "no_influence_count": 1,
                    }
                }
            }
        },
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.benchmark_artifact_summary is not None
    assert summary.benchmark_artifact_summary.case_id == "family_route_failure_v1"
    assert summary.benchmark_artifact_summary.registered_suite_ids == [
        "recovery_focused",
        "release_gate_v1",
        "v2_integrity",
        "all_registered",
    ]
    assert summary.benchmark_artifact_summary.taxonomy is not None
    assert summary.benchmark_artifact_summary.taxonomy.failure_mode == "route_unavailable"
    assert summary.benchmark_artifact_summary.benchmark_status is None
    assert summary.benchmark_artifact_summary.overall_score is None
    assert summary.benchmark_artifact_summary.memory_policy_summary is not None
    assert summary.benchmark_artifact_summary.memory_policy_summary.ignored_count == 1
    assert summary.benchmark_artifact_summary.score_summaries == []
    assert summary.benchmark_artifact_summary.report_path is None


def test_internal_observability_service_returns_recovery_path_summary_when_present(
    db_session: Session,
) -> None:
    case = load_benchmark_case("family_route_failure_v1")
    run = _create_run(
        db_session,
        metadata_json={
            "workflow": {
                "recovery": {
                    "attempt_count": 1,
                    "max_attempts": 1,
                    "attempts": [
                        {
                            "attempt_index": 1,
                            "source_node": "semantic_validator",
                            "recovery_action": "stop_safely",
                            "route_to": None,
                            "error_type": "route_infeasible",
                            "reason": "Recovery stopped after route failure.",
                            "retry_budget_before": 0,
                            "retry_budget_after": 0,
                            "status": "stopped",
                        }
                    ],
                }
            },
            "benchmark": {
                "case_id": case.case_id,
                "title": case.title,
                "workflow_backed": True,
                "taxonomy": case.taxonomy.model_dump(mode="json"),
                "artifact_summary": {
                    "schema_version": "weekendpilot_benchmark_artifact_summary_v1",
                    "benchmark_status": "passed",
                    "overall_score": 1.0,
                    "workflow_status": "failed",
                    "tool_event_count": 3,
                    "action_count": 0,
                    "failure_reasons": [],
                    "score_summaries": [],
                    "report_path": "var/benchmarks/family_route_failure_v1.json",
                },
            },
        },
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.recovery_path_summary is not None
    assert summary.recovery_path_summary.attempt_count == 1
    assert summary.recovery_path_summary.max_attempts == 1
    assert len(summary.recovery_path_summary.attempts) == 1
    assert summary.recovery_path_summary.attempts[0].recovery_action == "stop_safely"
    assert summary.recovery_path_summary.attempts[0].status == "stopped"
    assert summary.recovery_path_summary.replay_source is not None
    assert summary.recovery_path_summary.replay_source.case_id == "family_route_failure_v1"
    assert (
        summary.recovery_path_summary.replay_source.benchmark_report_path
        == "var/benchmarks/family_route_failure_v1.json"
    )


def test_internal_observability_service_skips_malformed_recovery_attempts(
    db_session: Session,
) -> None:
    run = _create_run(
        db_session,
        metadata_json={
            "workflow": {
                "recovery": {
                    "attempt_count": 2,
                    "max_attempts": 2,
                    "attempts": [
                        {
                            "attempt_index": "bad",
                            "recovery_action": "stop_safely",
                        },
                        {
                            "attempt_index": 1,
                            "source_node": "semantic_validator",
                            "recovery_action": "retry",
                            "route_to": "execute_searches",
                            "error_type": "empty_result",
                            "reason": "Retry the search path.",
                            "retry_budget_before": 1,
                            "retry_budget_after": 0,
                            "status": "routed",
                        },
                    ],
                }
            }
        },
    )

    summary = InternalObservabilityService(db_session).get_run_summary(run.run_id)

    assert summary.recovery_path_summary is not None
    assert summary.recovery_path_summary.attempt_count == 1
    assert summary.recovery_path_summary.max_attempts == 2
    assert len(summary.recovery_path_summary.attempts) == 1
    assert summary.recovery_path_summary.attempts[0].route_to == "execute_searches"
    assert summary.recovery_path_summary.replay_source is None
