from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agents import AgentResult, DeterministicValidatorRecoveryAgent, RecoveryDecision
from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, AgentRun
from backend.app.review.schemas import FinalReviewResult, ReviewCheck
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowRunner,
)


TEST_PREFIX = "weekendpilot:test:workflow-agents"
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


def _build_runner(
    session: Session,
    redis_runtime,
    trace_path: Path,
) -> WeekendPilotWorkflowRunner:
    cache, rate_limiter = redis_runtime
    return WeekendPilotWorkflowRunner(
        WeekendPilotWorkflowDependencies(
            session=session,
            cache=cache,
            rate_limiter=rate_limiter,
            trace_buffer_path=trace_path,
        )
    )


def _action_count(session: Session, run_id) -> int:
    return int(
        session.scalar(select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id))
        or 0
    )


def _metadata_text(value) -> str:
    return str(value)


def test_workflow_persists_agent_metadata_before_confirmation(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-agents-awaiting-{uuid4()}",
            display_name="Workflow Agents Awaiting Tester",
            case_id="case-workflow-agents-awaiting",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert {agent.role for agent in result.agent_results} == EXPECTED_ROLES
    assert _action_count(db_session, result.run_id) == 0

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    agents = run.metadata_json["agents"]
    assert agents["version"] == "bounded_agents_v1"
    assert {entry["role"] for entry in agents["results"]} == EXPECTED_ROLES
    assert "action_id" not in _metadata_text(agents)
    assert "tool_event_id" not in _metadata_text(agents)
    assert "debug_trace" not in _metadata_text(agents)


def test_workflow_auto_confirm_returns_agent_results_and_keeps_execution_path(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-agents-confirmed-{uuid4()}",
            display_name="Workflow Agents Confirmed Tester",
            case_id="case-workflow-agents-confirmed",
            auto_confirm=True,
        )
    )

    assert result.status == "completed"
    assert result.run_id is not None
    assert result.execution_status == "succeeded"
    assert result.feedback_status == "completed"
    assert {agent.role for agent in result.agent_results} == EXPECTED_ROLES

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    agents = run.metadata_json["agents"]
    assert agents["version"] == "bounded_agents_v1"
    assert {entry["role"] for entry in agents["results"]} == EXPECTED_ROLES
    assert "observability" in run.metadata_json


def test_workflow_recovery_metadata_is_sanitized(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _blocked_review(self, plan, enrichment, drafts, pre_confirmation_action_count=0, context=None):
        del self, plan, enrichment, pre_confirmation_action_count, context
        failed_check = ReviewCheck(
            check_name="route_verified",
            status="failed",
            severity="error",
            message="Route cannot be verified.",
        )
        review = FinalReviewResult(
            run_id=drafts.run_id,
            provider_profile=drafts.provider_profile,
            decision="blocked",
            safe_to_present=False,
            checks=[failed_check],
            errors=[failed_check],
            gate_version="test-gate",
        )
        decision = RecoveryDecision(
            verdict="failed",
            error_type="route_verified",
            recovery_action="stop_safely",
            retry_budget=0,
            reason="Stop safely without leaking debug_trace or secrets.",
        )
        return (
            AgentResult(
                role="validator_recovery",
                status="blocked",
                summary="Blocked by test gate.",
                adapter_version="test-validator",
                output_json={"recovery_decision": decision.model_dump(mode="json")},
            ),
            review,
            decision,
        )

    monkeypatch.setattr(DeterministicValidatorRecoveryAgent, "review", _blocked_review)
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-recovery-metadata-{uuid4()}",
            display_name="Workflow Recovery Metadata Tester",
            case_id="case-workflow-recovery-metadata",
            auto_confirm=False,
        )
    )

    assert result.status == "failed"
    assert result.run_id is not None
    assert {agent.role for agent in result.agent_results} == EXPECTED_ROLES

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert "recovery" in run.metadata_json["workflow"]
    metadata_text = _metadata_text(run.metadata_json["workflow"]["recovery"])
    assert "action_id" not in metadata_text
    assert "tool_event_id" not in metadata_text
    assert "api_key" not in metadata_text
    assert "token" not in metadata_text
    assert "secret" not in metadata_text
