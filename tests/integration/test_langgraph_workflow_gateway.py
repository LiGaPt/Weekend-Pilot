from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.runtime import ActionLedger, AgentRun, ToolEvent
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
    assert "execute" not in result.node_history


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
    assert "record_observability" in result.node_history

    trace_ids = set(
        db_session.scalars(select(ToolEvent.langsmith_trace_id).where(ToolEvent.run_id == result.run_id)).all()
    )
    assert trace_ids == {result.trace_id}

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.metadata_json["observability"]["trace_id"] == result.trace_id
