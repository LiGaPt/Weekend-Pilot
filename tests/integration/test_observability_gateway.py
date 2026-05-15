from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.confirmation import HumanConfirmationService
from backend.app.db.session import SessionLocal
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger, ToolEvent
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicItineraryGenerator,
    DeterministicQueryPlanner,
    QueryPlanExecutor,
)
from backend.app.plans import ReviewedPlanPersistenceService
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.review import FinalReviewGate
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import ToolGateway


TEST_PREFIX = "weekendpilot:test:observability-gateway"


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


def _create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"observability-gateway-user-{uuid4()}",
        display_name="Observability Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-observability-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "observability-gateway-test", "api_key": "must-redact"},
    )


def _build_gateway(
    session: Session,
    cache: JsonRedisCache,
    rate_limiter: FixedWindowRateLimiter,
) -> ToolGateway:
    return ToolGateway(
        registry=build_mock_world_registry(),
        tool_events=ToolEventRepository(session),
        action_ledger=ActionLedgerRepository(session),
        cache=cache,
        rate_limiter=rate_limiter,
    )


def _count_rows(session: Session, model, run_id):
    return session.scalar(select(func.count()).select_from(model).where(model.run_id == run_id))


def test_full_mock_world_flow_populates_tool_event_trace_ids_and_records_summary(
    db_session: Session,
    redis_runtime,
    trace_path,
) -> None:
    cache, rate_limiter = redis_runtime
    run = _create_run(db_session)
    gateway = _build_gateway(db_session, cache, rate_limiter)
    recorder = ObservabilityRecorder(
        runs=AgentRunRepository(db_session),
        tool_events=ToolEventRepository(db_session),
        action_ledger=ActionLedgerRepository(db_session),
        plans=PlanRepository(db_session),
        local_buffer=LocalTraceBuffer(trace_path),
    )
    trace_context = recorder.build_context(run.run_id)

    intent = DeterministicIntentParser().parse(
        "This afternoon I want to go out with my wife and child for a few hours. "
        "Not too far. My child is 5, and my wife is trying to eat lighter."
    )
    query_plan = DeterministicQueryPlanner().build(intent, provider_profile="mock_world")
    collection = QueryPlanExecutor(gateway).execute_initial_calls(
        query_plan,
        run.run_id,
        langsmith_trace_id=trace_context.trace_id,
    )
    enrichment = CandidateEnricher(gateway).enrich(
        query_plan,
        collection,
        langsmith_trace_id=trace_context.trace_id,
    )
    drafts = DeterministicItineraryGenerator().generate(query_plan, enrichment)
    review = FinalReviewGate().review(
        query_plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=_count_rows(db_session, ActionLedger, run.run_id),
    )
    assert review.safe_to_present is True

    persistence = ReviewedPlanPersistenceService(PlanRepository(db_session))
    persisted = persistence.persist_reviewed_drafts(review, drafts)
    selected = persistence.select_plan(run.run_id, persisted.persisted_plans[0].plan_id)
    HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        run.run_id,
        selected.plan_id,
        confirmed_by="user",
        source="integration-test",
    )

    execution = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        run.run_id,
        selected.plan_id,
        langsmith_trace_id=trace_context.trace_id,
    )
    assert execution.status == "succeeded"
    feedback = DeterministicFeedbackWriter(
        plans=PlanRepository(db_session),
        runs=AgentRunRepository(db_session),
    ).write_execution_feedback(run.run_id, selected.plan_id)
    assert feedback.status == "completed"

    result = recorder.record_run_summary(trace_context)

    trace_ids = set(
        db_session.scalars(select(ToolEvent.langsmith_trace_id).where(ToolEvent.run_id == run.run_id)).all()
    )
    assert trace_ids == {trace_context.trace_id}
    assert result.local_buffer_written is True
    row = AgentRunRepository(db_session).get_by_id(run.run_id)
    assert row is not None
    assert row.metadata_json["observability"]["trace_id"] == trace_context.trace_id
    assert row.metadata_json["observability"]["langsmith"]["enabled"] is False

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["trace_id"] == trace_context.trace_id
    assert payload["tool_event_count"] > 0
    assert payload["action_count"] == len(execution.action_results)
    assert payload["feedback_status"] == "completed"
    serialized = json.dumps(payload, sort_keys=True)
    assert "must-redact" not in serialized
    assert "api_key" in serialized
    assert "action_id" not in serialized
    assert "tool_event_id" not in serialized
