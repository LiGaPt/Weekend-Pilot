from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agents import AgentResult, DeterministicValidatorRecoveryAgent, RecoveryDecision
from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, AgentRun, ToolEvent, User
from backend.app.planning import DeterministicIntentParser
from backend.app.repositories import ConversationSessionRepository, UserRepository
from backend.app.review.schemas import FinalReviewResult, ReviewCheck
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowRunner,
)


TEST_PREFIX = "weekendpilot:test:langgraph-workflow"
USER_INPUT = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
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
    return session.scalar(select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id))


def _assert_timing_artifacts(result, run: AgentRun, trace_path: Path) -> None:
    assert result.workflow_timing_summary is not None
    assert result.workflow_timing_summary.schema_version == "workflow_timing_summary_v1"
    assert result.workflow_timing_summary.total_duration_ms >= 1
    assert result.workflow_timing_summary.stage_count == len(result.workflow_timing_summary.stages)
    assert result.workflow_timing_summary.stages
    assert result.workflow_timing_summary.stages[0].node_name == "initialize"

    persisted_timing = run.metadata_json["workflow"]["timing"]
    persisted_summary = run.metadata_json["summary"]
    assert persisted_timing["schema_version"] == "workflow_timing_summary_v1"
    assert persisted_timing["stage_count"] == len(persisted_timing["stages"])
    assert persisted_timing["total_duration_ms"] >= result.workflow_timing_summary.total_duration_ms
    assert persisted_summary["schema_version"] == "weekendpilot_run_summary_v1"
    assert persisted_summary["trace_id"] == result.trace_id
    assert persisted_summary["workflow_status"] == result.status

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
    assert payload["run_summary"]["trace_id"] == result.trace_id
    assert payload["run_summary"]["workflow_status"] == result.status
    assert payload["workflow_timing_summary"] == persisted_timing
    assert payload["workflow_timing_summary"]["stages"][0]["node_name"] == "initialize"


def test_workflow_stops_at_confirmation_boundary_without_write_actions(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-awaiting-{uuid4()}",
            display_name="Workflow Awaiting Tester",
            case_id="case-langgraph-awaiting",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert result.trace_id is not None
    assert result.selected_plan_id is not None
    assert result.tool_event_count > 0
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert "wait_confirmation" in result.node_history
    assert "saga_execution_engine" not in result.node_history


def test_workflow_auto_confirm_executes_feedback_and_observability(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-confirmed-{uuid4()}",
            display_name="Workflow Confirmed Tester",
            case_id="case-langgraph-confirmed",
            auto_confirm=True,
        )
    )

    assert result.status == "completed"
    assert result.run_id is not None
    assert result.trace_id is not None
    assert result.selected_plan_id is not None
    assert result.execution_status == "succeeded"
    assert result.feedback_status == "completed"
    assert result.observability_status is not None
    assert result.action_count > 0
    assert "saga_execution_engine" in result.node_history
    assert "generate_summary_message" in result.node_history

    trace_ids = set(
        db_session.scalars(select(ToolEvent.langsmith_trace_id).where(ToolEvent.run_id == result.run_id)).all()
    )
    assert trace_ids == {result.trace_id}

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.metadata_json["observability"]["trace_id"] == result.trace_id
    _assert_timing_artifacts(result, run, trace_path)


def test_workflow_recovery_stop_safely_records_metadata_without_actions(
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
            reason="Route cannot be recovered safely.",
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
            external_user_id=f"workflow-recovery-stop-{uuid4()}",
            display_name="Workflow Recovery Stop Tester",
            case_id="case-langgraph-recovery-stop",
            auto_confirm=False,
        )
    )

    assert result.status == "failed"
    assert result.run_id is not None
    assert result.error_json is not None
    assert result.error_json["error_type"] == "recovery_stopped"
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert "apply_recovery" in result.node_history
    assert "saga_execution_engine" not in result.node_history

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    recovery = run.metadata_json["workflow"]["recovery"]
    assert recovery["attempt_count"] == 1
    assert recovery["max_attempts"] == 1
    assert recovery["attempts"][0]["status"] == "stopped"
    _assert_timing_artifacts(result, run, trace_path)


def test_workflow_recovery_retry_loops_once_and_pauses_without_actions(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_review = DeterministicValidatorRecoveryAgent.review
    call_count = {"count": 0}

    def _retry_then_pass(self, plan, enrichment, drafts, pre_confirmation_action_count=0, context=None):
        call_count["count"] += 1
        if call_count["count"] > 1:
            return original_review(
                self,
                plan,
                enrichment,
                drafts,
                pre_confirmation_action_count=pre_confirmation_action_count,
                context=context,
            )

        failed_check = ReviewCheck(
            check_name="route_infeasible",
            status="failed",
            severity="error",
            message="Route needs a retry.",
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
            error_type="route_infeasible",
            recovery_action="retry",
            route_to="execute_searches",
            retry_budget=1,
            reason="Retry deterministic reads once.",
        )
        return (
            AgentResult(
                role="validator_recovery",
                status="blocked",
                summary="Retry requested by test gate.",
                adapter_version="test-validator",
                output_json={"recovery_decision": decision.model_dump(mode="json")},
            ),
            review,
            decision,
        )

    monkeypatch.setattr(DeterministicValidatorRecoveryAgent, "review", _retry_then_pass)
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-recovery-retry-{uuid4()}",
            display_name="Workflow Recovery Retry Tester",
            case_id="case-langgraph-recovery-retry",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert result.node_history.count("execute_searches") >= 2
    assert result.node_history.count("apply_recovery") == 1
    assert "saga_execution_engine" not in result.node_history

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    recovery = run.metadata_json["workflow"]["recovery"]
    assert recovery["attempt_count"] == 1
    assert recovery["attempts"][0]["status"] == "routed"
    assert recovery["attempts"][0]["route_to"] == "execute_searches"
    _assert_timing_artifacts(result, run, trace_path)


def test_workflow_reuses_existing_user_and_session_with_intent_override(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)
    user = UserRepository(db_session).create(
        external_id=None,
        display_name="Workflow Existing User Tester",
    )
    conversation_session = ConversationSessionRepository(db_session).create(
        user_id=user.user_id,
        channel="web_demo",
        status="active",
        metadata_json={"source": "test"},
    )
    original_user_count = db_session.scalar(select(func.count()).select_from(User))
    intent_override = DeterministicIntentParser().parse(USER_INPUT)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input="Keep it nearby and family friendly.",
            case_id="case-langgraph-existing-user-session",
            auto_confirm=False,
            existing_user_id=user.user_id,
            session_id=conversation_session.session_id,
            intent_override=intent_override,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.user_id == user.user_id
    assert run.session_id == conversation_session.session_id
    assert db_session.scalar(select(func.count()).select_from(User)) == original_user_count
