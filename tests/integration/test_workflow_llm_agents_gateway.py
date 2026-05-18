from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.session import SessionLocal
from backend.app.llm import LLMCallMetadata, LLMChatCompletion, LLMUsage
from backend.app.models.runtime import ActionLedger, AgentRun
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowRunner,
)


TEST_PREFIX = "weekendpilot:test:workflow-llm-agents"
USER_INPUT = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
)
EXPECTED_ROLES = {
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
}


class FakeWorkflowLLMClient:
    def __init__(self, *payloads: dict[str, Any]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    def chat_json(self, *, messages, temperature=0.2, max_tokens=400):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        payload = self.payloads.pop(0)
        return LLMChatCompletion(
            content_json=payload,
            metadata=LLMCallMetadata(
                provider_kind="openai_compatible",
                model_id="qwen3.6-plus",
                base_url_host="dashscope.aliyuncs.com",
                latency_ms=9,
                usage=LLMUsage(input_count=4, output_count=3, total_count=7),
                status="completed",
            ),
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
def redis_runtime():
    client = get_redis_client()
    client.ping()
    keys = RedisKeyBuilder(prefix=f"{TEST_PREFIX}:{uuid4()}")

    def cleanup() -> None:
        redis_keys = list(client.scan_iter(f"{keys.prefix}:*"))
        if redis_keys:
            client.delete(*redis_keys)

    cleanup()
    try:
        yield JsonRedisCache(client, keys), FixedWindowRateLimiter(client, keys)
    finally:
        cleanup()


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


def _settings(enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        llm_enabled=enabled,
        llm_api_key="local-test-key" if enabled else None,
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1" if enabled else None,
        llm_model_id="qwen3.6-plus" if enabled else None,
    )


def _runner(
    session: Session,
    redis_runtime,
    trace_path: Path,
    *,
    settings: Settings,
    llm_client=None,
) -> WeekendPilotWorkflowRunner:
    cache, rate_limiter = redis_runtime
    return WeekendPilotWorkflowRunner(
        WeekendPilotWorkflowDependencies(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            trace_buffer_path=trace_path,
            settings=settings,
            llm_client=llm_client,
        )
    )


def _action_count(session: Session, run_id) -> int:
    return int(
        session.scalar(select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id))
        or 0
    )


def test_workflow_defaults_to_deterministic_agents_when_llm_disabled(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    result = _runner(
        db_session,
        redis_runtime,
        trace_path,
        settings=_settings(False),
    ).run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-llm-disabled-{uuid4()}",
            display_name="Workflow LLM Disabled Tester",
            case_id="case-workflow-llm-disabled",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    versions = {agent.role: agent.adapter_version for agent in result.agent_results}
    assert versions["discovery"] == "deterministic_discovery_v1"
    assert versions["dining"] == "deterministic_dining_v1"
    assert versions["itinerary_planner"] == "deterministic_itinerary_planner_v1"
    assert _action_count(db_session, result.run_id) == 0


def test_workflow_uses_llm_for_three_agents_and_preserves_confirmation_boundary(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    fake_client = FakeWorkflowLLMClient(
        {
            "summary": "活动候选适合亲子下午安排。",
            "candidate_ids": ["activity_museum_001"],
            "tool_names_used": ["get_poi_detail", "check_opening_hours"],
            "risk_codes": [],
        },
        {
            "summary": "餐厅候选符合清淡和亲子需求。",
            "candidate_ids": ["restaurant_light_001"],
            "tool_names_used": ["get_poi_detail", "check_table_availability"],
            "risk_codes": [],
        },
        {
            "summary": "保留当前最稳妥的草案。",
            "draft_ids": ["draft_1"],
        },
    )

    result = _runner(
        db_session,
        redis_runtime,
        trace_path,
        settings=_settings(True),
        llm_client=fake_client,
    ).run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-llm-enabled-{uuid4()}",
            display_name="Workflow LLM Enabled Tester",
            case_id="case-workflow-llm-enabled",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert _action_count(db_session, result.run_id) == 0
    assert len(fake_client.calls) == 3
    assert {agent.role for agent in result.agent_results} == EXPECTED_ROLES
    versions = {agent.role: agent.adapter_version for agent in result.agent_results}
    assert versions["supervisor"] == "deterministic_supervisor_v1"
    assert versions["discovery"] == "llm_discovery_v0"
    assert versions["dining"] == "llm_dining_v0"
    assert versions["itinerary_planner"] == "llm_itinerary_planner_v0"
    assert versions["validator_recovery"] == "deterministic_validator_recovery_v1"

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    agents = run.metadata_json["agents"]
    serialized_agents = json.dumps(agents, sort_keys=True)
    assert "prompt_tokens" not in serialized_agents
    assert "completion_tokens" not in serialized_agents
    assert "total_tokens" not in serialized_agents
    assert "local-test-key" not in serialized_agents
    assert "tool_event_id" not in serialized_agents
    assert "action_id" not in serialized_agents
    llm_results = [
        entry
        for entry in agents["results"]
        if entry["adapter_version"] in {"llm_discovery_v0", "llm_dining_v0", "llm_itinerary_planner_v0"}
    ]
    assert len(llm_results) == 3
    assert all(entry["output_json"]["llm"]["usage"]["total_count"] == 7 for entry in llm_results)


def test_workflow_llm_metadata_reaches_local_trace_summary(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    fake_client = FakeWorkflowLLMClient(
        {
            "summary": "活动候选适合亲子下午安排。",
            "candidate_ids": ["activity_museum_001"],
            "tool_names_used": ["get_poi_detail"],
            "risk_codes": [],
        },
        {
            "summary": "餐厅候选符合清淡和亲子需求。",
            "candidate_ids": ["restaurant_light_001"],
            "tool_names_used": ["get_poi_detail"],
            "risk_codes": [],
        },
        {
            "summary": "保留当前最稳妥的草案。",
            "draft_ids": ["draft_1"],
        },
    )

    result = _runner(
        db_session,
        redis_runtime,
        trace_path,
        settings=_settings(True),
        llm_client=fake_client,
    ).run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-llm-trace-{uuid4()}",
            display_name="Workflow LLM Trace Tester",
            case_id="case-workflow-llm-trace",
            auto_confirm=True,
        )
    )

    assert result.status == "completed"
    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    serialized_payload = json.dumps(payload, sort_keys=True)
    assert "llm_discovery_v0" in serialized_payload
    assert '"total_count": 7' in serialized_payload
    assert "prompt_tokens" not in serialized_payload
    assert "completion_tokens" not in serialized_payload
    assert "total_tokens" not in serialized_payload
    assert "local-test-key" not in serialized_payload
