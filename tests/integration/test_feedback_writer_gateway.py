from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.confirmation import HumanConfirmationService
from backend.app.db.session import SessionLocal
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger, Plan, ToolEvent
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


TEST_PREFIX = "weekendpilot:test:feedback-writer"


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


def _create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"feedback-writer-gateway-user-{uuid4()}",
        display_name="Feedback Writer Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-feedback-writer-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "feedback-writer-gateway-test"},
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


def test_feedback_writer_persists_user_safe_feedback_after_mock_world_execution(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    run = _create_run(db_session)
    gateway = _build_gateway(db_session, cache, rate_limiter)
    intent = DeterministicIntentParser().parse(
        "This afternoon I want to go out with my wife and child for a few hours. "
        "Not too far. My child is 5, and my wife is trying to eat lighter."
    )
    query_plan = DeterministicQueryPlanner().build(intent, provider_profile="mock_world")
    collection = QueryPlanExecutor(gateway).execute_initial_calls(query_plan, run.run_id)
    enrichment = CandidateEnricher(gateway).enrich(query_plan, collection)
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
    assert persisted.persisted_plans
    selected = persistence.select_plan(run.run_id, persisted.persisted_plans[0].plan_id)

    confirmation = HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        run.run_id,
        selected.plan_id,
        confirmed_by="user",
        source="integration-test",
    )
    assert confirmation.status == "confirmed"
    assert confirmation.confirmed_actions

    execution = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        run.run_id,
        selected.plan_id,
    )
    assert execution.status == "succeeded"
    action_ledger_count_before_feedback = _count_rows(db_session, ActionLedger, run.run_id)
    tool_event_count_before_feedback = _count_rows(db_session, ToolEvent, run.run_id)

    feedback = DeterministicFeedbackWriter(
        plans=PlanRepository(db_session),
        runs=AgentRunRepository(db_session),
    ).write_execution_feedback(run.run_id, selected.plan_id)

    assert feedback.status == "completed"
    assert feedback.run_status == "completed"
    assert f"{len(execution.action_results)}项操作已完成" in feedback.message
    assert "0项需要处理" in feedback.message
    assert AgentRunRepository(db_session).get_by_id(run.run_id).status == "completed"
    assert _count_rows(db_session, ActionLedger, run.run_id) == action_ledger_count_before_feedback
    assert _count_rows(db_session, ToolEvent, run.run_id) == tool_event_count_before_feedback
    assert (
        db_session.scalar(
            select(func.count()).select_from(Plan).where(Plan.run_id == run.run_id, Plan.selected.is_(True))
        )
        == 1
    )

    row = PlanRepository(db_session).get_by_id(selected.plan_id)
    assert row is not None
    stored = row.plan_json["feedback"]
    assert stored["schema_version"] == "execution_feedback_v1"
    assert stored["writer_version"] == "deterministic_feedback_writer_v1"
    assert stored["status"] == "completed"
    assert stored["run_status"] == "completed"
    assert stored["message"] == feedback.message

    serialized_feedback = str(stored)
    assert "tool_event_id" not in serialized_feedback
    assert "action_id" not in serialized_feedback
