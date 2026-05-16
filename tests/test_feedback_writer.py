from __future__ import annotations

import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.feedback import DeterministicFeedbackWriter, FeedbackWriterError
from backend.app.models.runtime import Plan
from backend.app.repositories import AgentRunRepository, PlanRepository, UserRepository


@pytest.fixture()
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _create_run(session: Session, *, status: str = "running"):
    user = UserRepository(session).create(
        external_id=f"feedback-writer-user-{uuid4()}",
        display_name="Feedback Writer Tester",
    )
    return AgentRunRepository(session).create(
        user_id=user.user_id,
        case_id="case-feedback-writer",
        agent_version="agent-v1",
        prompt_version="prompt-v1",
        tool_profile="mock_world",
        world_profile="family_afternoon",
        failure_profile=None,
        status=status,
        metadata_json={"source": "feedback-writer-test"},
    )


def _action_result(
    *,
    action_ref: str = "draft_1_action_1",
    execution_order: int = 1,
    tool_name: str = "book_ticket",
    target_id: str = "activity_museum_001",
    status: str = "succeeded",
    error_json: dict | None = None,
) -> dict:
    is_success = status in {"succeeded", "idempotent_replay"}
    return {
        "action_ref": action_ref,
        "execution_order": execution_order,
        "tool_name": tool_name,
        "target_id": target_id,
        "idempotency_key": f"confirm:{uuid4()}:{action_ref}",
        "status": status,
        "action_id": str(uuid4()) if is_success else None,
        "tool_event_id": str(uuid4()),
        "response_json": {"debug_trace": "hidden-from-user"} if is_success else None,
        "error_json": error_json if error_json is not None else (None if is_success else {"code": status}),
    }


def _reviewed_plan_json(
    run_id: UUID,
    *,
    execution_status: str = "succeeded",
    action_results: list[dict] | None = None,
    execution_schema_version: str = "execution_workflow_v1",
) -> dict:
    actions = [_action_result()] if action_results is None else action_results
    return {
        "schema_version": "reviewed_plan_v1",
        "persistence_version": "reviewed_plan_persistence_v1",
        "run_id": str(run_id),
        "provider_profile": "mock_world",
        "draft_id": "draft_1",
        "status": "reviewed",
        "safe_to_present": True,
        "review_decision": "approved",
        "draft": {
            "draft_id": "draft_1",
            "status": "draft",
            "title": "徐汇亲子轻松下午",
            "summary": "一条已审核的亲子半日方案。",
            "activity": {
                "candidate_id": "activity_museum_001",
                "name": "徐汇亲子科学馆",
            },
            "dining": {
                "candidate_id": "restaurant_light_001",
                "name": "绿碗家庭轻食",
            },
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
        "execution": {
            "schema_version": execution_schema_version,
            "workflow_version": "deterministic_execution_workflow_v1",
            "status": execution_status,
            "plan_status": "executed",
            "started_at": "2026-05-15T00:00:00+00:00",
            "finished_at": "2026-05-15T00:01:00+00:00",
            "succeeded_count": sum(1 for item in actions if item.get("status") in {"succeeded", "idempotent_replay"}),
            "failed_count": sum(1 for item in actions if item.get("status") in {"failed", "blocked", "rate_limited"}),
            "action_results": actions,
        },
    }


def _create_executed_plan(
    session: Session,
    *,
    run_id: UUID | None = None,
    selected: bool = True,
    plan_json: dict | None = None,
    execution_status: str = "succeeded",
    action_results: list[dict] | None = None,
):
    if run_id is None:
        run_id = _create_run(session).run_id
    return PlanRepository(session).create(
        run_id=run_id,
        status="executed",
        selected=selected,
        plan_json=(
            _reviewed_plan_json(
                run_id,
                execution_status=execution_status,
                action_results=action_results,
            )
            if plan_json is None
            else plan_json
        ),
    )


def _write_feedback(session: Session, run_id: UUID, plan_id: UUID):
    return DeterministicFeedbackWriter(
        plans=PlanRepository(session),
        runs=AgentRunRepository(session),
    ).write_execution_feedback(run_id, plan_id)


def _stable_feedback(feedback: dict) -> dict:
    stable = deepcopy(feedback)
    stable.pop("generated_at", None)
    return stable


def test_successful_execution_creates_completed_feedback_and_run_status(db_session: Session) -> None:
    run = _create_run(db_session)
    plan = _create_executed_plan(db_session, run_id=run.run_id)

    result = _write_feedback(db_session, run.run_id, plan.plan_id)

    assert result.status == "completed"
    assert result.run_status == "completed"
    assert result.headline == "安排已完成"
    assert "1项操作已完成" in result.message
    assert "0项需要处理" in result.message
    assert len(result.completed_actions) == 1
    assert result.completed_actions[0].target_label == "徐汇亲子科学馆"
    assert result.completed_actions[0].status == "completed"
    assert result.completed_actions[0].message == "已为徐汇亲子科学馆完成订票。"
    assert result.failed_actions == []
    assert AgentRunRepository(db_session).get_by_id(run.run_id).status == "completed"

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    feedback = row.plan_json["feedback"]
    assert feedback["schema_version"] == "execution_feedback_v1"
    assert feedback["writer_version"] == "deterministic_feedback_writer_v1"
    assert feedback["status"] == "completed"
    assert feedback["run_status"] == "completed"
    assert feedback["completed_actions"][0]["target_label"] == "徐汇亲子科学馆"


def test_partial_execution_groups_completed_replayed_and_failed_actions(db_session: Session) -> None:
    run = _create_run(db_session)
    actions = [
        _action_result(
            action_ref="draft_1_action_1",
            execution_order=1,
            target_id="activity_museum_001",
            status="succeeded",
        ),
        _action_result(
            action_ref="draft_1_action_2",
            execution_order=2,
            tool_name="reserve_restaurant",
            target_id="restaurant_light_001",
            status="idempotent_replay",
        ),
        _action_result(
            action_ref="draft_1_action_3",
            execution_order=3,
            tool_name="join_queue",
            target_id="queue_123",
            status="failed",
            error_json={"code": "provider_unavailable"},
        ),
    ]
    plan = _create_executed_plan(
        db_session,
        run_id=run.run_id,
        execution_status="partially_succeeded",
        action_results=actions,
    )

    result = _write_feedback(db_session, run.run_id, plan.plan_id)

    assert result.status == "partially_completed"
    assert result.run_status == "partially_completed"
    assert result.headline == "部分安排已完成"
    assert "2项操作已完成" in result.message
    assert "1项需要处理" in result.message
    assert [item.status for item in result.completed_actions] == ["completed", "already_completed"]
    assert [item.target_label for item in result.completed_actions] == ["徐汇亲子科学馆", "绿碗家庭轻食"]
    assert len(result.failed_actions) == 1
    assert result.failed_actions[0].status == "failed"
    assert result.failed_actions[0].target_label == "queue_123"
    assert result.failed_actions[0].error_code == "provider_unavailable"
    assert result.next_steps
    assert AgentRunRepository(db_session).get_by_id(run.run_id).status == "partially_completed"


def test_failed_execution_creates_failed_feedback(db_session: Session) -> None:
    run = _create_run(db_session)
    plan = _create_executed_plan(
        db_session,
        run_id=run.run_id,
        execution_status="failed",
        action_results=[
            _action_result(status="blocked", error_json={"code": "confirmation_expired"}),
            _action_result(
                action_ref="draft_1_action_2",
                execution_order=2,
                tool_name="reserve_restaurant",
                target_id="restaurant_light_001",
                status="rate_limited",
                error_json={"code": "rate_limit"},
            ),
        ],
    )

    result = _write_feedback(db_session, run.run_id, plan.plan_id)

    assert result.status == "failed"
    assert result.run_status == "failed"
    assert result.completed_actions == []
    assert [item.status for item in result.failed_actions] == ["blocked", "rate_limited"]
    assert "0项操作已完成" in result.message
    assert "2项需要处理" in result.message
    assert AgentRunRepository(db_session).get_by_id(run.run_id).status == "failed"


def test_skipped_execution_creates_skipped_feedback_without_action_summaries(db_session: Session) -> None:
    run = _create_run(db_session)
    plan = _create_executed_plan(
        db_session,
        run_id=run.run_id,
        execution_status="skipped",
        action_results=[],
    )

    result = _write_feedback(db_session, run.run_id, plan.plan_id)

    assert result.status == "skipped"
    assert result.run_status == "skipped"
    assert result.completed_actions == []
    assert result.failed_actions == []
    assert result.next_steps
    assert "0项操作已完成" in result.message
    assert AgentRunRepository(db_session).get_by_id(run.run_id).status == "skipped"


def test_missing_wrong_run_missing_run_unselected_and_malformed_plans_raise(db_session: Session) -> None:
    run = _create_run(db_session)
    other_run = _create_run(db_session)
    plan = _create_executed_plan(db_session, run_id=run.run_id)
    unselected = _create_executed_plan(db_session, selected=False)
    malformed = _create_executed_plan(db_session, run_id=run.run_id, plan_json={"schema_version": "not-reviewed"})
    missing_execution = _create_executed_plan(
        db_session,
        run_id=run.run_id,
        plan_json={**_reviewed_plan_json(run.run_id), "execution": None},
    )

    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, run.run_id, uuid4())
    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, other_run.run_id, plan.plan_id)
    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, uuid4(), plan.plan_id)
    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, unselected.run_id, unselected.plan_id)
    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, malformed.run_id, malformed.plan_id)
    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, missing_execution.run_id, missing_execution.plan_id)


@pytest.mark.parametrize(
    ("plan_json_update", "action_update"),
    [
        ({"execution": {"schema_version": "unexpected"}}, None),
        ({"execution": {"schema_version": "execution_workflow_v1", "status": "unexpected", "action_results": []}}, None),
        (None, {"status": "cached"}),
        (None, {"execution_order": 0}),
        (None, {"tool_name": ""}),
        (None, {"target_id": ""}),
    ],
)
def test_unsupported_execution_or_action_metadata_raises(
    db_session: Session,
    plan_json_update: dict | None,
    action_update: dict | None,
) -> None:
    run = _create_run(db_session)
    plan_json = _reviewed_plan_json(run.run_id)
    if plan_json_update is not None:
        plan_json.update(plan_json_update)
    if action_update is not None:
        action = {**plan_json["execution"]["action_results"][0], **action_update}
        plan_json["execution"]["action_results"] = [action]
    plan = _create_executed_plan(db_session, run_id=run.run_id, plan_json=plan_json)

    with pytest.raises(FeedbackWriterError):
        _write_feedback(db_session, run.run_id, plan.plan_id)


def test_feedback_payload_does_not_expose_internal_execution_ids_or_debug_data(db_session: Session) -> None:
    run = _create_run(db_session)
    action = _action_result()
    plan = _create_executed_plan(db_session, run_id=run.run_id, action_results=[action])

    _write_feedback(db_session, run.run_id, plan.plan_id)

    row = PlanRepository(db_session).get_by_id(plan.plan_id)
    assert row is not None
    serialized = json.dumps(row.plan_json["feedback"], sort_keys=True)
    assert "tool_event_id" not in serialized
    assert "action_id" not in serialized
    assert action["tool_event_id"] not in serialized
    assert action["action_id"] not in serialized
    assert action["idempotency_key"] not in serialized
    assert "debug_trace" not in serialized


def test_rerun_overwrites_existing_feedback_without_creating_rows(db_session: Session) -> None:
    run = _create_run(db_session)
    plan_json = _reviewed_plan_json(run.run_id)
    plan_json["feedback"] = {
        "schema_version": "old_feedback",
        "status": "stale",
        "message": "stale feedback",
    }
    plan = _create_executed_plan(db_session, run_id=run.run_id, plan_json=plan_json)
    rows_before = db_session.scalar(select(func.count()).select_from(Plan).where(Plan.run_id == run.run_id))

    _write_feedback(db_session, run.run_id, plan.plan_id)
    first = _stable_feedback(PlanRepository(db_session).get_by_id(plan.plan_id).plan_json["feedback"])
    _write_feedback(db_session, run.run_id, plan.plan_id)
    second = _stable_feedback(PlanRepository(db_session).get_by_id(plan.plan_id).plan_json["feedback"])

    assert first == second
    assert first["schema_version"] == "execution_feedback_v1"
    assert first["message"] != "stale feedback"
    assert db_session.scalar(select(func.count()).select_from(Plan).where(Plan.run_id == run.run_id)) == rows_before


def test_writer_and_repositories_do_not_self_commit() -> None:
    session = SessionLocal()
    try:
        run = _create_run(session)
        plan = _create_executed_plan(session, run_id=run.run_id)
        run_id = run.run_id
        plan_id = plan.plan_id

        _write_feedback(session, run_id, plan_id)
        session.rollback()
    finally:
        session.close()

    verification_session = SessionLocal()
    try:
        assert AgentRunRepository(verification_session).get_by_id(run_id) is None
        assert PlanRepository(verification_session).get_by_id(plan_id) is None
    finally:
        verification_session.close()
