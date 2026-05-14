from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.execution import DeterministicExecutionWorkflow, ExecutionWorkflowError
from backend.app.repositories import AgentRunRepository, PlanRepository, UserRepository
from backend.app.tool_gateway import ToolGatewayResult


@pytest.fixture()
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


class FakeGateway:
    def __init__(self, statuses: list[str] | None = None) -> None:
        self.statuses = statuses or ["succeeded"]
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        index = len(self.requests) - 1
        status = self.statuses[min(index, len(self.statuses) - 1)]
        is_success = status in {"succeeded", "idempotent_replay"}
        return ToolGatewayResult(
            tool_name=request.tool_name,
            tool_type="write",
            provider=request.provider or "mock_world",
            status=status,
            response_json={"ok": True} if is_success else None,
            error_json=None if is_success else {"code": status},
            tool_event_id=uuid4(),
            action_id=uuid4() if is_success else None,
            idempotency_key=request.idempotency_key,
        )


def _create_run(session: Session):
    user = UserRepository(session).create(
        external_id=f"execution-workflow-user-{uuid4()}",
        display_name="Execution Workflow Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-execution-workflow",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status="running",
        metadata_json={"source": "execution-workflow-test"},
    )


def _confirmed_action(
    *,
    action_ref: str = "draft_1_action_1",
    execution_order: int = 1,
    tool_name: str = "book_ticket",
    target_id: str = "activity_museum_001",
    idempotency_key: str | None = None,
    user_confirmed: bool = True,
    payload: dict | None = None,
) -> dict:
    return {
        "action_ref": action_ref,
        "execution_order": execution_order,
        "tool_name": tool_name,
        "target_id": target_id,
        "payload": {"quantity": 3} if payload is None else payload,
        "idempotency_key": idempotency_key or f"test-key:{action_ref}",
        "user_confirmed": user_confirmed,
        "reason": "Confirmed by the user.",
    }


def _confirmed_plan_json(
    run_id: UUID,
    *,
    actions: list[dict] | None = None,
    confirmation_status: str = "confirmed",
    provider_profile: str = "mock_world",
) -> dict:
    return {
        "schema_version": "reviewed_plan_v1",
        "persistence_version": "reviewed_plan_persistence_v1",
        "run_id": str(run_id),
        "provider_profile": provider_profile,
        "draft_id": "draft_1",
        "status": "reviewed",
        "safe_to_present": True,
        "review_decision": "approved",
        "draft": {
            "draft_id": "draft_1",
            "proposed_actions": [],
        },
        "reviewed_draft": {
            "draft_id": "draft_1",
            "decision": "approved",
            "safe_to_present": True,
        },
        "final_review": {
            "decision": "approved",
            "safe_to_present": True,
            "gate_version": "test-gate",
        },
        "confirmation": {
            "schema_version": "human_confirmation_v1",
            "confirmation_id": f"confirmation:{run_id}:plan",
            "status": confirmation_status,
            "confirmed_by": "user",
            "source": "test",
            "action_count": len(actions or []),
            "service_version": "human_confirmation_v1",
        },
        "confirmed_actions": [] if actions is None else actions,
    }


def _create_confirmed_plan(
    session: Session,
    *,
    run_id: UUID | None = None,
    status: str = "confirmed",
    selected: bool = True,
    actions: list[dict] | None = None,
    plan_json: dict | None = None,
):
    if run_id is None:
        run_id = _create_run(session).run_id
    default_actions = [
        _confirmed_action(
            action_ref="draft_1_action_2",
            execution_order=2,
            tool_name="reserve_restaurant",
            target_id="restaurant_light_001",
            idempotency_key=f"confirm:{run_id}:draft_1_action_2",
            payload={"restaurant_id": "restaurant_light_001", "party_size": 3},
        ),
        _confirmed_action(
            action_ref="draft_1_action_1",
            execution_order=1,
            tool_name="book_ticket",
            target_id="activity_museum_001",
            idempotency_key=f"confirm:{run_id}:draft_1_action_1",
            payload={"poi_id": "activity_museum_001", "quantity": 3},
        ),
    ]
    return PlanRepository(session).create(
        run_id=run_id,
        status=status,
        selected=selected,
        plan_json=(
            _confirmed_plan_json(run_id, actions=default_actions if actions is None else actions)
            if plan_json is None
            else plan_json
        ),
    )


def test_executes_confirmed_actions_in_order_and_persists_summary(db_session: Session) -> None:
    plan = _create_confirmed_plan(db_session)
    gateway = FakeGateway()

    result = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        plan.run_id,
        plan.plan_id,
    )

    assert result.status == "succeeded"
    assert result.plan_status == "executed"
    assert result.succeeded_count == 2
    assert result.failed_count == 0
    assert [request.tool_name for request in gateway.requests] == ["book_ticket", "reserve_restaurant"]
    assert [request.user_confirmed for request in gateway.requests] == [True, True]
    assert [request.target_id for request in gateway.requests] == ["activity_museum_001", "restaurant_light_001"]
    assert [request.provider for request in gateway.requests] == ["mock_world", "mock_world"]
    assert gateway.requests[0].payload == {"poi_id": "activity_museum_001", "quantity": 3}

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    assert row.status == "executed"
    execution = row.plan_json["execution"]
    assert execution["schema_version"] == "execution_workflow_v1"
    assert execution["workflow_version"] == "deterministic_execution_workflow_v1"
    assert execution["status"] == "succeeded"
    assert execution["plan_status"] == "executed"
    assert execution["succeeded_count"] == 2
    assert execution["failed_count"] == 0
    assert [item["action_ref"] for item in execution["action_results"]] == [
        "draft_1_action_1",
        "draft_1_action_2",
    ]


def test_idempotent_replay_counts_as_success(db_session: Session) -> None:
    plan = _create_confirmed_plan(db_session)
    gateway = FakeGateway(statuses=["idempotent_replay"])

    result = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        plan.run_id,
        plan.plan_id,
    )

    assert result.status == "succeeded"
    assert result.plan_status == "executed"
    assert result.succeeded_count == 2
    assert result.failed_count == 0
    assert {item.status for item in result.action_results} == {"idempotent_replay"}


def test_mixed_failures_continue_and_update_partial_status(db_session: Session) -> None:
    plan = _create_confirmed_plan(db_session)
    gateway = FakeGateway(statuses=["failed", "succeeded"])

    result = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        plan.run_id,
        plan.plan_id,
    )

    assert len(gateway.requests) == 2
    assert result.status == "partially_succeeded"
    assert result.plan_status == "partially_executed"
    assert result.succeeded_count == 1
    assert result.failed_count == 1
    assert [item.status for item in result.action_results] == ["failed", "succeeded"]
    assert PlanRepository(db_session).get_by_id(plan.plan_id).status == "partially_executed"


@pytest.mark.parametrize("status", ["failed", "blocked", "rate_limited"])
def test_all_failed_statuses_update_execution_failed(db_session: Session, status: str) -> None:
    plan = _create_confirmed_plan(db_session)
    gateway = FakeGateway(statuses=[status])

    result = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        plan.run_id,
        plan.plan_id,
    )

    assert result.status == "failed"
    assert result.plan_status == "execution_failed"
    assert result.succeeded_count == 0
    assert result.failed_count == 2
    assert PlanRepository(db_session).get_by_id(plan.plan_id).status == "execution_failed"


def test_no_confirmed_actions_updates_execution_skipped(db_session: Session) -> None:
    plan = _create_confirmed_plan(db_session, actions=[])
    gateway = FakeGateway()

    result = DeterministicExecutionWorkflow(PlanRepository(db_session), gateway).execute_confirmed_plan(
        plan.run_id,
        plan.plan_id,
    )

    assert result.status == "skipped"
    assert result.plan_status == "execution_skipped"
    assert result.action_results == []
    assert gateway.requests == []
    assert PlanRepository(db_session).get_by_id(plan.plan_id).status == "execution_skipped"


def test_rejects_missing_wrong_run_unselected_declined_and_unconfirmed_plans(db_session: Session) -> None:
    repo = PlanRepository(db_session)
    workflow = DeterministicExecutionWorkflow(repo, FakeGateway())
    run = _create_run(db_session)
    other_run = _create_run(db_session)
    confirmed = _create_confirmed_plan(db_session, run_id=run.run_id)
    unselected = _create_confirmed_plan(db_session, selected=False)
    declined = _create_confirmed_plan(
        db_session,
        status="declined",
        plan_json=_confirmed_plan_json(run.run_id, actions=[], confirmation_status="declined"),
    )
    unconfirmed = _create_confirmed_plan(db_session, status="selected")

    with pytest.raises(ExecutionWorkflowError):
        workflow.execute_confirmed_plan(run.run_id, uuid4())
    with pytest.raises(ExecutionWorkflowError):
        workflow.execute_confirmed_plan(other_run.run_id, confirmed.plan_id)
    with pytest.raises(ExecutionWorkflowError):
        workflow.execute_confirmed_plan(unselected.run_id, unselected.plan_id)
    with pytest.raises(ExecutionWorkflowError):
        workflow.execute_confirmed_plan(declined.run_id, declined.plan_id)
    with pytest.raises(ExecutionWorkflowError):
        workflow.execute_confirmed_plan(unconfirmed.run_id, unconfirmed.plan_id)


@pytest.mark.parametrize(
    "plan_json",
    [
        {"schema_version": "reviewed_plan_v1"},
        _confirmed_plan_json(uuid4(), actions=[], provider_profile=""),
        {**_confirmed_plan_json(uuid4(), actions=[]), "confirmed_actions": None},
        {**_confirmed_plan_json(uuid4(), actions=[]), "confirmed_actions": "bad"},
    ],
)
def test_rejects_malformed_plan_json(db_session: Session, plan_json: dict) -> None:
    plan = _create_confirmed_plan(db_session, plan_json=plan_json)

    with pytest.raises(ExecutionWorkflowError):
        DeterministicExecutionWorkflow(PlanRepository(db_session), FakeGateway()).execute_confirmed_plan(
            plan.run_id,
            plan.plan_id,
        )


@pytest.mark.parametrize(
    "action",
    [
        {"not": "an action"},
        _confirmed_action(action_ref=""),
        _confirmed_action(execution_order=0),
        _confirmed_action(tool_name="search_poi"),
        _confirmed_action(target_id=""),
        {**_confirmed_action(), "idempotency_key": ""},
        _confirmed_action(idempotency_key="x" * 256),
        _confirmed_action(user_confirmed=False),
        _confirmed_action(payload="bad-payload"),
    ],
)
def test_rejects_malformed_confirmed_actions(db_session: Session, action: dict) -> None:
    plan = _create_confirmed_plan(db_session, actions=[action])

    with pytest.raises(ExecutionWorkflowError):
        DeterministicExecutionWorkflow(PlanRepository(db_session), FakeGateway()).execute_confirmed_plan(
            plan.run_id,
            plan.plan_id,
        )


@pytest.mark.parametrize(
    "actions",
    [
        [_confirmed_action(action_ref="duplicate"), _confirmed_action(action_ref="duplicate", execution_order=2)],
        [_confirmed_action(execution_order=1), _confirmed_action(action_ref="other", execution_order=1)],
    ],
)
def test_rejects_duplicate_action_refs_and_orders(db_session: Session, actions: list[dict]) -> None:
    plan = _create_confirmed_plan(db_session, actions=actions)

    with pytest.raises(ExecutionWorkflowError):
        DeterministicExecutionWorkflow(PlanRepository(db_session), FakeGateway()).execute_confirmed_plan(
            plan.run_id,
            plan.plan_id,
        )


def test_workflow_and_repository_do_not_self_commit() -> None:
    session = SessionLocal()
    try:
        run = _create_run(session)
        plan = _create_confirmed_plan(session, run_id=run.run_id)
        run_id = run.run_id
        plan_id = plan.plan_id

        DeterministicExecutionWorkflow(PlanRepository(session), FakeGateway()).execute_confirmed_plan(
            run_id,
            plan_id,
        )
        session.rollback()
    finally:
        session.close()

    verification_session = SessionLocal()
    try:
        assert AgentRunRepository(verification_session).get_by_id(run_id) is None
        assert PlanRepository(verification_session).get_by_id(plan_id) is None
    finally:
        verification_session.close()
