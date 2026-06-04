from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.benchmark import load_benchmark_case
from backend.app.confirmation import HumanConfirmationService
from backend.app.db.session import SessionLocal
from backend.app.execution import DeterministicExecutionWorkflow
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


TEST_PREFIX = "weekendpilot:test:execution-workflow"


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
        external_id=f"execution-workflow-gateway-user-{uuid4()}",
        display_name="Execution Workflow Gateway Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-execution-workflow-gateway",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "execution-workflow-gateway-test"},
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


def test_execution_workflow_runs_confirmed_mock_world_actions_and_replays(
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

    confirmed_row = PlanRepository(db_session).get_by_id(selected.plan_id)
    assert confirmed_row is not None
    confirmed_action_count = len(confirmed_row.plan_json["confirmed_actions"])
    action_ledger_count_before = _count_rows(db_session, ActionLedger, run.run_id)
    tool_event_count_before = _count_rows(db_session, ToolEvent, run.run_id)

    workflow = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway)
    result = workflow.execute_confirmed_plan(run.run_id, selected.plan_id)

    assert result.status == "succeeded"
    assert result.plan_status == "executed"
    assert len(result.action_results) == confirmed_action_count
    assert {item.status for item in result.action_results} == {"succeeded"}
    assert all(item.tool_event_id is not None for item in result.action_results)
    assert all(item.action_id is not None for item in result.action_results)
    assert _count_rows(db_session, ActionLedger, run.run_id) == action_ledger_count_before + confirmed_action_count
    assert _count_rows(db_session, ToolEvent, run.run_id) == tool_event_count_before + confirmed_action_count
    assert (
        db_session.scalar(
            select(func.count()).select_from(Plan).where(Plan.run_id == run.run_id, Plan.selected.is_(True))
        )
        == 1
    )

    executed_row = PlanRepository(db_session).get_by_id(selected.plan_id)
    assert executed_row is not None
    assert executed_row.status == "executed"
    assert executed_row.plan_json["execution"]["status"] == "succeeded"

    action_ledger_count_after_first = _count_rows(db_session, ActionLedger, run.run_id)
    tool_event_count_after_first = _count_rows(db_session, ToolEvent, run.run_id)
    replay = workflow.execute_confirmed_plan(run.run_id, selected.plan_id)

    assert replay.status == "succeeded"
    assert {item.status for item in replay.action_results} == {"idempotent_replay"}
    assert _count_rows(db_session, ActionLedger, run.run_id) == action_ledger_count_after_first
    assert _count_rows(db_session, ToolEvent, run.run_id) == tool_event_count_after_first + confirmed_action_count


def test_execution_workflow_executes_order_addon_and_replays_idempotently(
    db_session: Session,
    redis_runtime,
) -> None:
    cache, rate_limiter = redis_runtime
    case = load_benchmark_case("family_citywalk_addon_v1")
    run = _create_run(db_session)
    gateway = _build_gateway(db_session, cache, rate_limiter)
    intent = DeterministicIntentParser().parse(case.user_input)
    query_plan = DeterministicQueryPlanner().build(intent, provider_profile="mock_world")
    collection = QueryPlanExecutor(gateway).execute_initial_calls(query_plan, run.run_id)
    enrichment = CandidateEnricher(gateway, max_other_candidates=1).enrich(query_plan, collection)
    drafts = DeterministicItineraryGenerator().generate(query_plan, enrichment)
    review = FinalReviewGate().review(
        query_plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=_count_rows(db_session, ActionLedger, run.run_id),
    )
    persistence = ReviewedPlanPersistenceService(PlanRepository(db_session))
    persisted = persistence.persist_reviewed_drafts(review, drafts)
    selected = persistence.select_plan(run.run_id, persisted.persisted_plans[0].plan_id)

    confirmation = HumanConfirmationService(PlanRepository(db_session)).confirm_plan(
        run.run_id,
        selected.plan_id,
        confirmed_by="user",
        source="integration-test",
    )
    assert confirmation.confirmed_actions[-1].tool_name == "order_addon"

    workflow = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway)
    result = workflow.execute_confirmed_plan(run.run_id, selected.plan_id)

    addon_results = [item for item in result.action_results if item.tool_name == "order_addon"]
    assert len(addon_results) == 1
    assert addon_results[0].status == "succeeded"
    assert addon_results[0].target_id == "addon_drinks_001"
    assert db_session.scalar(
        select(func.count()).select_from(ActionLedger).where(
            ActionLedger.run_id == run.run_id,
            ActionLedger.action_type == "order_addon",
        )
    ) == 1

    replay = workflow.execute_confirmed_plan(run.run_id, selected.plan_id)
    replay_addon_results = [item for item in replay.action_results if item.tool_name == "order_addon"]
    assert len(replay_addon_results) == 1
    assert replay_addon_results[0].status == "idempotent_replay"
