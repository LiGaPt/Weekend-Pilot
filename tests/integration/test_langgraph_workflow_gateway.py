from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agents import (
    AgentResult,
    DeterministicItineraryPlannerAgent,
    DeterministicValidatorRecoveryAgent,
    RecoveryDecision,
)
from backend.app.db.session import SessionLocal
from backend.app.memory_control import MemoryCreateRequest, MemoryUserControlService
from backend.app.models.runtime import ActionLedger, AgentRun, MemoryItem, ToolEvent, User
from backend.app.planning import (
    DeterministicIntentParser,
    DeterministicQueryPlanner,
    FeasibilitySummary,
    ItineraryCandidateRef,
    ItineraryDraft,
    ItineraryDraftResult,
    ItineraryRouteRef,
)
from backend.app.repositories import ConversationSessionRepository, MemoryItemRepository, PlanRepository, UserRepository
from backend.app.review.schemas import FinalReviewResult, ReviewCheck
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client
from backend.app.tool_gateway import build_default_registry
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


class _FakeAmapPreviewProvider:
    name = "amap"

    def invoke(self, tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        if tool_name == "search_poi":
            if payload.get("canonical_category") == "activity":
                return {
                    "results": [
                        {
                            "id": "amap-activity-1",
                            "name": "Riverside Family Park",
                            "category": "Park",
                            "address": "1 Riverside Road",
                            "location": "121.480,31.230",
                            "source": "amap",
                        }
                    ]
                }
            return {
                "results": [
                    {
                        "id": "amap-dining-1",
                        "name": "Light Kitchen",
                        "category": "Restaurant",
                        "address": "8 Dining Road",
                        "location": "121.486,31.232",
                        "source": "amap",
                    }
                ]
            }
        if tool_name == "get_poi_detail":
            poi_id = str(payload.get("poi_id") or "")
            return {
                "poi": {
                    "poi_id": poi_id,
                    "description": f"Preview detail for {poi_id}.",
                }
            }
        if tool_name == "check_weather":
            return {"weather": {"city": "Shanghai", "condition": "Sunny"}}
        if tool_name == "check_route":
            return {
                "route": {
                    "mode": "walking",
                    "distance_meters": 1200,
                    "duration_minutes": 15,
                    "summary": "Walkable route between the preview POIs.",
                }
            }
        raise AssertionError(f"Unexpected tool {tool_name!r} for fake AMAP preview provider.")


def _build_fake_amap_registry():
    registry = build_default_registry(default_provider="amap")
    registry.register_provider(_FakeAmapPreviewProvider())
    return registry


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


def _draft(draft_id: str, *, activity_id: str, dining_id: str) -> ItineraryDraft:
    return ItineraryDraft(
        draft_id=draft_id,
        title=f"{activity_id} + {dining_id}",
        summary="test draft",
        activity=ItineraryCandidateRef(
            candidate_id=activity_id,
            name=activity_id,
            category="activity",
            provider="mock_world",
        ),
        dining=ItineraryCandidateRef(
            candidate_id=dining_id,
            name=dining_id,
            category="dining",
            provider="mock_world",
        ),
        route=ItineraryRouteRef(
            origin_candidate_id=activity_id,
            destination_candidate_id=dining_id,
            provider="mock_world",
            mode="walking",
            distance_meters=1000,
            duration_minutes=15,
        ),
        feasibility=FeasibilitySummary(
            is_feasible=True,
            reasons=["usable"],
            total_duration_minutes=300,
            route_duration_minutes=15,
        ),
    )


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


def test_execution_workflow_reentry_with_existing_terminal_plan_does_not_duplicate_ledger_rows(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-confirmed-reentry-{uuid4()}",
            display_name="Workflow Confirmed Reentry Tester",
            case_id="case-langgraph-confirmed-reentry",
            auto_confirm=True,
        )
    )

    assert result.status == "completed"
    assert result.run_id is not None
    assert result.selected_plan_id is not None

    action_count_before = _action_count(db_session, result.run_id)
    plan = PlanRepository(db_session).get_selected_for_run(result.run_id)
    assert plan is not None

    from backend.app.execution import DeterministicExecutionWorkflow
    from backend.app.tool_gateway import ToolGateway
    from backend.app.tool_gateway import build_default_registry
    from backend.app.repositories import ToolEventRepository, ActionLedgerRepository

    cache, rate_limiter = redis_runtime
    workflow = DeterministicExecutionWorkflow(
        PlanRepository(db_session),
        ToolGateway(
            registry=build_default_registry(default_provider="mock_world"),
            tool_events=ToolEventRepository(db_session),
            action_ledger=ActionLedgerRepository(db_session),
            cache=cache,
            rate_limiter=rate_limiter,
        ),
    )

    replay = workflow.execute_confirmed_plan(result.run_id, plan.plan_id)

    assert replay.status in {"succeeded", "partially_succeeded", "failed", "skipped"}
    assert _action_count(db_session, result.run_id) == action_count_before


def test_workflow_auto_confirm_persists_candidate_memory_without_loading_it_as_governable(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-feedback-candidate-{uuid4()}",
            display_name="Workflow Feedback Candidate Tester",
            case_id="case-langgraph-feedback-candidate",
            auto_confirm=True,
        )
    )

    assert result.status == "completed"
    assert result.run_id is not None
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.user_id is not None

    memory_rows = db_session.scalars(
        select(MemoryItem)
        .where(MemoryItem.user_id == run.user_id)
        .order_by(MemoryItem.key)
    ).all()
    assert [memory.key for memory in memory_rows] == ["activity_style", "spouse_lighter_meals"]
    assert all(memory.status == "candidate" for memory in memory_rows)
    assert all(memory.text is None for memory in memory_rows)
    assert MemoryItemRepository(db_session).list_governable_for_user(run.user_id) == []


def test_workflow_recovery_stop_safely_records_metadata_without_actions(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _blocked_review(
        self,
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
        recovery_context=None,
        context=None,
    ):
        del self, plan, enrichment, pre_confirmation_action_count, recovery_context, context
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
    assert recovery["max_attempts"] == 2
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

    def _retry_then_pass(
        self,
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
        recovery_context=None,
        context=None,
    ):
        call_count["count"] += 1
        if call_count["count"] > 1:
            return original_review(
                self,
                plan,
                enrichment,
                drafts,
                pre_confirmation_action_count=pre_confirmation_action_count,
                recovery_context=recovery_context,
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


def test_workflow_recovery_replace_candidate_filters_first_pair_and_pauses_without_actions(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_review = DeterministicValidatorRecoveryAgent.review
    validator_call_count = {"count": 0}
    excluded_pair: dict[str, str] = {}

    def _replace_then_pass(
        self,
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
        recovery_context=None,
        context=None,
    ):
        validator_call_count["count"] += 1
        if validator_call_count["count"] == 1:
            assert len(drafts.drafts) >= 2
            excluded_pair.update(
                {
                    "activity_candidate_id": drafts.drafts[0].activity.candidate_id,
                    "dining_candidate_id": drafts.drafts[0].dining.candidate_id,
                }
            )
            failed_check = ReviewCheck(
                check_name="route_verified",
                status="failed",
                severity="error",
                message="First draft route is blocked.",
                draft_id="draft_1",
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
                recovery_action="replace_candidate",
                route_to="logical_planner_agent",
                retry_budget=1,
                reason="Try the next candidate pair.",
            )
            return (
                AgentResult(
                    role="validator_recovery",
                    status="blocked",
                    summary="Replace candidate pair.",
                    adapter_version="test-validator",
                    output_json={"recovery_decision": decision.model_dump(mode="json")},
                ),
                    review,
                    decision,
                )

        remaining_pairs = [
            (draft.activity.candidate_id, draft.dining.candidate_id)
            for draft in drafts.drafts
        ]
        assert remaining_pairs
        assert (
            excluded_pair["activity_candidate_id"],
            excluded_pair["dining_candidate_id"],
        ) not in remaining_pairs
        return original_review(
            self,
            plan,
            enrichment,
            drafts,
            pre_confirmation_action_count=pre_confirmation_action_count,
            recovery_context=recovery_context,
            context=context,
        )

    monkeypatch.setattr(DeterministicValidatorRecoveryAgent, "review", _replace_then_pass)
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-recovery-replace-{uuid4()}",
            display_name="Workflow Recovery Replace Tester",
            case_id="case-langgraph-recovery-replace",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert result.node_history.count("logical_planner_agent") >= 2
    assert result.node_history.count("apply_recovery") == 1

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    recovery = run.metadata_json["workflow"]["recovery"]
    assert recovery["attempts"][0]["recovery_action"] == "replace_candidate"
    assert recovery["attempts"][0]["route_to"] == "logical_planner_agent"
    assert recovery["excluded_candidate_pairs"] == [excluded_pair]
    assert recovery["search_expansion_level"] == 0
    _assert_timing_artifacts(result, run, trace_path)


def test_workflow_recovery_expand_search_radius_reruns_query_generation_with_bounded_limit(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_review = DeterministicValidatorRecoveryAgent.review
    original_build = DeterministicQueryPlanner.build
    observed_search_limits: list[int | None] = []
    validator_call_count = {"count": 0}

    def _tracking_build(self, intent, provider_profile="mock_world", *, search_limit_override=None):
        observed_search_limits.append(search_limit_override)
        return original_build(
            self,
            intent,
            provider_profile=provider_profile,
            search_limit_override=search_limit_override,
        )

    def _expand_then_pass(
        self,
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
        recovery_context=None,
        context=None,
    ):
        validator_call_count["count"] += 1
        if validator_call_count["count"] == 1:
            failed_check = ReviewCheck(
                check_name="draft_exists",
                status="failed",
                severity="error",
                message="No draft is available.",
            )
            review = FinalReviewResult(
                run_id=uuid4(),
                provider_profile="mock_world",
                decision="blocked",
                safe_to_present=False,
                checks=[failed_check],
                errors=[failed_check],
                gate_version="test-gate",
            )
            decision = RecoveryDecision(
                verdict="failed",
                error_type="draft_exists",
                recovery_action="expand_search_radius",
                route_to="generate_queries",
                retry_budget=1,
                reason="Expand search breadth once.",
            )
            return (
                AgentResult(
                    role="validator_recovery",
                    status="blocked",
                    summary="Expand search breadth.",
                    adapter_version="test-validator",
                    output_json={"recovery_decision": decision.model_dump(mode="json")},
                ),
                review,
                decision,
            )

        return original_review(
            self,
            plan,
            enrichment,
            drafts,
            pre_confirmation_action_count=pre_confirmation_action_count,
            recovery_context=recovery_context,
            context=context,
        )

    monkeypatch.setattr(DeterministicQueryPlanner, "build", _tracking_build)
    monkeypatch.setattr(DeterministicValidatorRecoveryAgent, "review", _expand_then_pass)
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-recovery-expand-{uuid4()}",
            display_name="Workflow Recovery Expand Tester",
            case_id="case-langgraph-recovery-expand",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert result.node_history.count("generate_queries") >= 2
    assert result.node_history.count("apply_recovery") == 1
    assert observed_search_limits[0] is None
    assert 8 in observed_search_limits[1:]

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    recovery = run.metadata_json["workflow"]["recovery"]
    assert recovery["attempts"][0]["recovery_action"] == "expand_search_radius"
    assert recovery["attempts"][0]["route_to"] == "generate_queries"
    assert recovery["search_expansion_level"] == 1
    _assert_timing_artifacts(result, run, trace_path)


def test_workflow_recovery_ask_user_reuses_clarification_contract_without_actions(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _ask_user(
        self,
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
        recovery_context=None,
        context=None,
    ):
        del self, plan, enrichment, drafts, pre_confirmation_action_count, recovery_context, context
        failed_check = ReviewCheck(
            check_name="draft_exists",
            status="failed",
            severity="error",
            message="Need user tradeoff input.",
        )
        review = FinalReviewResult(
            run_id=uuid4(),
            provider_profile="mock_world",
            decision="blocked",
            safe_to_present=False,
            checks=[failed_check],
            errors=[failed_check],
            gate_version="test-gate",
        )
        decision = RecoveryDecision(
            verdict="failed",
            error_type="draft_exists",
            recovery_action="ask_user",
            retry_budget=0,
            reason="Need user tradeoff input.",
        )
        return (
            AgentResult(
                role="validator_recovery",
                status="blocked",
                summary="Need user tradeoff input.",
                adapter_version="test-validator",
                output_json={"recovery_decision": decision.model_dump(mode="json")},
            ),
            review,
            decision,
        )

    monkeypatch.setattr(DeterministicValidatorRecoveryAgent, "review", _ask_user)
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-recovery-clarify-{uuid4()}",
            display_name="Workflow Recovery Clarify Tester",
            case_id="case-langgraph-recovery-clarify",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_clarification"
    assert result.run_id is not None
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert "apply_recovery" in result.node_history
    assert "wait_confirmation" not in result.node_history

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    workflow = run.metadata_json["workflow"]
    recovery = workflow["recovery"]
    assert recovery["attempts"][0]["recovery_action"] == "ask_user"
    assert recovery["attempts"][0]["status"] == "awaiting_user"
    assert workflow["clarification"] == {
        "policy_version": "recovery_clarification_v1",
        "missing_fields": ["distance_flexibility"],
        "question_text": (
            "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
            "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
            "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
        ),
    }
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


def test_workflow_loads_only_governable_memory_lifecycle_states(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)
    user = UserRepository(db_session).create(
        external_id=None,
        display_name="Workflow Memory Lifecycle Tester",
    )
    memory_repo = MemoryItemRepository(db_session)
    memory_repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="activity_style",
        value_json={"preference": "indoor activities"},
        text="Explicit expired memory.",
        confidence=Decimal("1.0"),
        source_run_id=None,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="expired",
    )
    memory_repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="spouse_lighter_meals",
        value_json={"preference": "lighter meals"},
        text="Candidate memory should stay out of policy.",
        confidence=Decimal("1.0"),
        source_run_id=None,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="candidate",
    )
    memory_repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="activity_style_disabled",
        value_json={"preference": "outdoor activities"},
        text="Disabled memory should stay out of policy.",
        confidence=Decimal("1.0"),
        source_run_id=None,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="disabled",
    )
    memory_repo.create(
        user_id=user.user_id,
        memory_type="preference",
        key="activity_style_ignored",
        value_json={"preference": "citywalk"},
        text="Ignored memory should stay out of policy.",
        confidence=Decimal("1.0"),
        source_run_id=None,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="ignored",
    )

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input="This afternoon please arrange a nearby outing for my partner and our 5-year-old for a few hours, then dinner afterward.",
            case_id="case-langgraph-memory-lifecycle",
            auto_confirm=False,
            existing_user_id=user.user_id,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["advisory_memory_keys"] == ["activity_style"]
    assert memory_policy["downgraded_expired_keys"] == ["activity_style"]
    assert [decision["memory_key"] for decision in memory_policy["memory_decisions"]] == ["activity_style"]
    assert [entry["key"] for entry in memory_policy["decision_log"]] == ["activity_style"]


def test_workflow_memory_control_disable_keeps_controlled_row_out_of_query_shaping(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)
    user = UserRepository(db_session).create(
        external_id=None,
        display_name="Workflow Memory Control Tester",
    )
    memory = MemoryItemRepository(db_session).create(
        user_id=user.user_id,
        memory_type="preference",
        key="activity_style",
        value_json={"preference": "indoor"},
        text="test",
        confidence=Decimal("1.0"),
        source_run_id=None,
        source_langsmith_trace_id=None,
        expires_at=None,
        status="active",
    )
    control_result = MemoryUserControlService(db_session).apply_action(
        user.user_id,
        memory.memory_id,
        "disable",
        "user_requested_control",
    )
    db_session.commit()

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            case_id="case-langgraph-memory-control",
            auto_confirm=False,
            existing_user_id=user.user_id,
        )
    )

    assert result.run_id is not None
    assert result.status == "awaiting_confirmation"
    assert control_result.item.status == "disabled"
    assert MemoryItemRepository(db_session).list_governable_for_user(user.user_id) == []
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["memory_decisions"] == []
    assert memory_policy["decision_log"] == []


def test_workflow_created_active_memory_shapes_later_query_planning(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)
    user = UserRepository(db_session).create(
        external_id=None,
        display_name="Workflow Active Memory Creator",
    )
    create_result = MemoryUserControlService(db_session).create_item(
        user.user_id,
        MemoryCreateRequest(
            memory_type="preference",
            key="spouse_lighter_meals",
            value_json={"preference": "lighter_options"},
            text="lighter options",
            confidence=Decimal("0.9000"),
            status="active",
            expires_at=None,
            source_run_id=None,
            source_langsmith_trace_id="trace-created-active",
            reason="manual_memory_seed",
        ),
    )
    db_session.commit()

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input="This afternoon please arrange a nearby outing for my partner and our 5-year-old for a few hours, then dinner afterward.",
            case_id="case-langgraph-created-active-memory",
            auto_confirm=False,
            existing_user_id=user.user_id,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert create_result.item.status == "active"
    assert result.run_id is not None
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["applied_memory_keys"] == ["spouse_lighter_meals"]
    assert [decision["memory_key"] for decision in memory_policy["memory_decisions"]] == ["spouse_lighter_meals"]
    assert [entry["key"] for entry in memory_policy["decision_log"]] == ["spouse_lighter_meals"]


def test_workflow_created_candidate_memory_stays_out_of_query_shaping(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
) -> None:
    runner = _build_runner(db_session, redis_runtime, trace_path)
    user = UserRepository(db_session).create(
        external_id=None,
        display_name="Workflow Candidate Memory Creator",
    )
    create_result = MemoryUserControlService(db_session).create_item(
        user.user_id,
        MemoryCreateRequest(
            memory_type="preference",
            key="activity_style",
            value_json={"preference": "indoor"},
            text="indoor",
            confidence=Decimal("0.9000"),
            status="candidate",
            expires_at=None,
            source_run_id=None,
            source_langsmith_trace_id="trace-created-candidate",
            reason="manual_memory_seed",
        ),
    )
    db_session.commit()

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input="This afternoon please arrange a nearby outing for my partner and our 5-year-old for a few hours, then dinner afterward.",
            case_id="case-langgraph-created-candidate-memory",
            auto_confirm=False,
            existing_user_id=user.user_id,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert create_result.item.status == "candidate"
    assert MemoryItemRepository(db_session).list_governable_for_user(user.user_id) == []
    assert result.run_id is not None
    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    memory_policy = run.metadata_json["workflow"]["memory_policy"]
    assert memory_policy["memory_decisions"] == []
    assert memory_policy["decision_log"] == []


def test_workflow_amap_preview_reaches_confirmation_without_write_actions(
    db_session: Session,
    redis_runtime,
    trace_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.workflow.nodes.build_amap_registry", _build_fake_amap_registry)
    runner = _build_runner(db_session, redis_runtime, trace_path)

    result = runner.run(
        WeekendPilotWorkflowRequest(
            user_input=USER_INPUT,
            external_user_id=f"workflow-amap-preview-{uuid4()}",
            display_name="Workflow AMAP Preview Tester",
            case_id="case-langgraph-amap-preview",
            tool_profile="amap",
            world_profile="amap_shanghai_live",
            auto_confirm=False,
        )
    )

    assert result.status == "awaiting_confirmation"
    assert result.run_id is not None
    assert result.selected_plan_id is not None
    assert result.action_count == 0
    assert _action_count(db_session, result.run_id) == 0
    assert "wait_confirmation" in result.node_history
    assert "saga_execution_engine" not in result.node_history

    run = db_session.get(AgentRun, result.run_id)
    assert run is not None
    assert run.tool_profile == "amap"
    assert run.world_profile == "amap_shanghai_live"
    assert PlanRepository(db_session).get_selected_for_run(result.run_id) is not None

    providers = set(
        db_session.scalars(select(ToolEvent.provider).where(ToolEvent.run_id == result.run_id)).all()
    )
    write_event_count = int(
        db_session.scalar(
            select(func.count()).select_from(ToolEvent).where(
                ToolEvent.run_id == result.run_id,
                ToolEvent.tool_type == "write",
            )
        )
        or 0
    )
    assert providers == {"amap"}
    assert write_event_count == 0
    assert run.metadata_json["summary"]["preview_diagnostics"] == {
        "schema_version": "weekendpilot_preview_diagnostics_v1",
        "read_profile": "amap",
        "mode": "read_only_preview",
        "confirmation_allowed": False,
        "confirmation_block_reason": "AMAP read-only demo runs cannot be confirmed.",
        "benchmark_eligible": False,
        "benchmark_block_reason": "Canonical benchmark suites support Mock World only.",
        "observed_provider_names": ["amap"],
        "provider_event_count": result.tool_event_count,
        "write_tool_event_count": 0,
        "provider_error_types": [],
        "cross_provider_fallback_detected": False,
    }
