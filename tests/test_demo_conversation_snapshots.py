from uuid import uuid4

from backend.app.demo.conversation_snapshots import build_conversation_turn_state_snapshot
from backend.app.demo.schemas import (
    DemoClarificationSummary,
    DemoPlanVersionSummary,
    DemoProgressSummary,
    DemoProgressStepSummary,
    DemoRunSummary,
)


def _summary(*, status: str = "awaiting_confirmation", selected_plan_id=None, clarification=None) -> DemoRunSummary:
    progress = DemoProgressSummary(
        current_stage="ready_for_confirmation" if status != "awaiting_clarification" else "planning_queries",
        current_label="Ready" if status != "awaiting_clarification" else "Planning",
        stage_history=["understanding_request", "ready_for_confirmation"]
        if status != "awaiting_clarification"
        else ["understanding_request", "planning_queries"],
        steps=[
            DemoProgressStepSummary(
                stage="understanding_request",
                label="理解需求",
                status="completed",
                summary="done",
            ),
            DemoProgressStepSummary(
                stage="ready_for_confirmation" if status != "awaiting_clarification" else "planning_queries",
                label="准备确认" if status != "awaiting_clarification" else "规划查询",
                status="current",
                summary="current",
            ),
        ],
    )
    return DemoRunSummary(
        run_id=uuid4(),
        status=status,
        read_profile="mock_world",
        selected_plan_id=selected_plan_id,
        progress=progress,
        plan_version=DemoPlanVersionSummary(version_number=2, version_label="v2", source_run_id=None),
        plans=[],
        action_count=0,
        execution_status=None,
        feedback_status=None,
        error=None,
        clarification=clarification,
    )


def test_build_conversation_turn_state_snapshot_for_confirmation_ready_run() -> None:
    selected_plan_id = uuid4()
    summary = _summary(selected_plan_id=selected_plan_id)

    snapshot = build_conversation_turn_state_snapshot(summary)

    assert snapshot == {
        "schema_version": "conversation_turn_state_snapshot_v0",
        "run_status": "awaiting_confirmation",
        "selected_plan_id": str(selected_plan_id),
        "plan_count": 0,
        "plan_version_label": "v2",
        "action_count": 0,
        "execution_status": None,
        "feedback_status": None,
        "clarification_missing_fields": [],
        "progress": summary.progress.model_dump(mode="json"),
    }


def test_build_conversation_turn_state_snapshot_for_clarification_run() -> None:
    summary = _summary(
        status="awaiting_clarification",
        clarification=DemoClarificationSummary(
            prompt="请补充信息",
            missing_fields=["scenario_or_participants", "time_window"],
        ),
    )

    snapshot = build_conversation_turn_state_snapshot(summary)

    assert snapshot["run_status"] == "awaiting_clarification"
    assert snapshot["selected_plan_id"] is None
    assert snapshot["clarification_missing_fields"] == ["scenario_or_participants", "time_window"]
    assert snapshot["progress"] == summary.progress.model_dump(mode="json")


def test_build_conversation_turn_state_snapshot_excludes_internal_fields() -> None:
    summary = _summary()

    snapshot = build_conversation_turn_state_snapshot(summary)

    assert "session_id" not in snapshot
    assert "trace_id" not in snapshot
    assert "node_history" not in snapshot
    assert "prompt" not in snapshot
