from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.agents import (
    AGENT_METADATA_VERSION,
    AgentPolicyError,
    AgentResult,
    AgentRole,
    DeterministicDiningAgent,
    DeterministicDiscoveryAgent,
    DeterministicItineraryPlannerAgent,
    DeterministicSupervisorAgent,
    DeterministicValidatorRecoveryAgent,
    RecoveryDecision,
    SupervisorAssignmentPlan,
    default_agent_policies,
    sanitize_agent_metadata,
    validate_agent_tool_usage,
)
from backend.app.agents.schemas import RecoveryEvaluationContext
from backend.app.planning import (
    Candidate,
    CandidateCollectionResult,
    CandidateEnrichmentResult,
    DeterministicItineraryGenerator,
    EnrichedCandidate,
    EnrichmentToolResult,
    FeasibilitySummary,
    IntentConstraints,
    ItineraryCandidateRef,
    ItineraryDraft,
    ItineraryDraftResult,
    ItineraryRouteRef,
    LocalLifeIntent,
    ParticipantProfile,
    QueryPlan,
    RouteMatrixEntry,
    TimeWindow,
    ToolCallTemplate,
)
from backend.app.review import FinalReviewGate
from backend.app.review.schemas import FinalReviewResult, ReviewCheck, ReviewedDraft
from backend.app.tool_gateway.registry import WRITE_TOOLS


ALL_ROLES: set[AgentRole] = {
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
}


def _intent() -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="family afternoon",
        scenario_type="family",
        participants=ParticipantProfile(adults=2, children_ages=[5]),
        time_window=TimeWindow(duration_hours_min=4, duration_hours_max=6),
        constraints=IntentConstraints(child_friendly=True, max_distance_km=8),
        activity_preferences=["child_friendly"],
        dining_preferences=["lighter_options"],
        parser_version="test-parser",
    )


def _plan() -> QueryPlan:
    return QueryPlan(
        intent=_intent(),
        provider_profile="mock_world",
        candidate_enrichment_templates=[
            ToolCallTemplate(tool_name="get_poi_detail", provider="mock_world"),
            ToolCallTemplate(tool_name="check_opening_hours", provider="mock_world"),
            ToolCallTemplate(tool_name="check_queue", provider="mock_world"),
            ToolCallTemplate(tool_name="check_table_availability", provider="mock_world"),
            ToolCallTemplate(tool_name="check_ticket_availability", provider="mock_world"),
        ],
        route_templates=[ToolCallTemplate(tool_name="check_route", provider="mock_world")],
        planner_version="test-planner",
    )


def _candidate(
    candidate_id: str,
    *,
    name: str,
    category: str,
    tags: list[str] | None = None,
    tool_event_id: UUID | None = None,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        name=name,
        category=category,
        provider="mock_world",
        address=f"{name} address",
        tags=tags or [],
        raw_payload={"poi_id": candidate_id},
        source_call_index=0,
        tool_event_id=tool_event_id,
    )


def _tool_result(tool_name: str, candidate_id: str) -> EnrichmentToolResult:
    return EnrichmentToolResult(
        stage="candidate_enrichment",
        candidate_id=candidate_id,
        tool_name=tool_name,
        provider="mock_world",
        status="succeeded",
        response_json={},
        tool_event_id=uuid4(),
    )


def _activity() -> EnrichedCandidate:
    candidate_id = "activity_museum_001"
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name="Xuhui Family Science Museum",
            category="activity",
            tags=["child_friendly"],
        ),
        poi_detail={"poi_id": candidate_id},
        opening_hours={"is_open": True},
        ticket_availability={"poi_id": candidate_id, "available": True, "time_slots": ["13:30"]},
        tool_results=[
            _tool_result("get_poi_detail", candidate_id),
            _tool_result("check_opening_hours", candidate_id),
            _tool_result("check_ticket_availability", candidate_id),
        ],
    )


def _dining() -> EnrichedCandidate:
    candidate_id = "restaurant_light_001"
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name="Green Bowl Family Bistro",
            category="dining",
            tags=["lighter_options", "child_friendly"],
        ),
        poi_detail={"poi_id": candidate_id},
        opening_hours={"is_open": True},
        queue={"queue_id": f"queue_{candidate_id}", "status": "open", "wait_minutes": 10},
        table_availability={
            "restaurant_id": candidate_id,
            "available": True,
            "time_slots": ["17:30"],
        },
        tool_results=[
            _tool_result("get_poi_detail", candidate_id),
            _tool_result("check_opening_hours", candidate_id),
            _tool_result("check_queue", candidate_id),
            _tool_result("check_table_availability", candidate_id),
        ],
    )


def _route() -> RouteMatrixEntry:
    return RouteMatrixEntry(
        origin_candidate_id="activity_museum_001",
        destination_candidate_id="restaurant_light_001",
        provider="mock_world",
        mode="walking",
        status="succeeded",
        route_json={"summary": "Short walk"},
        distance_meters=850,
        duration_minutes=12,
        tool_event_id=uuid4(),
    )


def _collection() -> CandidateCollectionResult:
    return CandidateCollectionResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        activity_candidates=[_activity().candidate],
        dining_candidates=[_dining().candidate],
        executor_version="test-executor",
    )


def _enrichment() -> CandidateEnrichmentResult:
    return CandidateEnrichmentResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        enriched_activity_candidates=[_activity()],
        enriched_dining_candidates=[_dining()],
        route_matrix=[_route()],
        tool_results=[*_activity().tool_results, *_dining().tool_results],
        enricher_version="test-enricher",
    )


def _draft(
    draft_id: str,
    *,
    activity_id: str,
    dining_id: str,
) -> ItineraryDraft:
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
            distance_meters=900,
            duration_minutes=12,
        ),
        feasibility=FeasibilitySummary(
            is_feasible=True,
            reasons=["usable"],
            total_duration_minutes=300,
            route_duration_minutes=12,
        ),
    )


class _StaticGate(FinalReviewGate):
    def __init__(self, review: FinalReviewResult) -> None:
        self._review = review

    def review(self, *args, **kwargs):
        del args, kwargs
        return self._review


def test_all_five_roles_exist_and_import_cleanly() -> None:
    assert set(default_agent_policies()) == ALL_ROLES
    assert AGENT_METADATA_VERSION == "bounded_agents_v1"


def test_default_policies_forbid_write_tools_for_every_role() -> None:
    for role, policy in default_agent_policies().items():
        assert policy.role == role
        assert policy.may_execute_write_tools is False
        assert policy.allowed_write_tools == []


@pytest.mark.parametrize("tool_name", WRITE_TOOLS)
def test_validate_agent_tool_usage_rejects_write_tools(tool_name: str) -> None:
    with pytest.raises(AgentPolicyError):
        validate_agent_tool_usage("discovery", [tool_name])


def test_supervisor_returns_assignments_for_specialist_roles() -> None:
    result, plan = DeterministicSupervisorAgent().assign(_plan())

    assert isinstance(result, AgentResult)
    assert result.role == "supervisor"
    assert result.status == "completed"
    assert isinstance(plan, SupervisorAssignmentPlan)
    assert {assignment.target_role for assignment in plan.assignments} == {
        "discovery",
        "dining",
        "itinerary_planner",
        "validator_recovery",
    }
    assert result.tool_names_used == []


def test_discovery_summary_uses_activity_candidates_as_primary_category() -> None:
    result = DeterministicDiscoveryAgent().summarize(_plan(), _collection(), _enrichment())

    assert result.role == "discovery"
    assert result.output_json["activity_count"] == 1
    assert "Xuhui Family Science Museum" in result.summary
    assert "dining_count" not in result.output_json
    assert set(result.tool_names_used) <= {
        "search_poi",
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_ticket_availability",
        "check_route",
    }


def test_dining_summary_uses_dining_candidates_as_primary_category() -> None:
    result = DeterministicDiningAgent().summarize(_plan(), _collection(), _enrichment())

    assert result.role == "dining"
    assert result.output_json["dining_count"] == 1
    assert "Green Bowl Family Bistro" in result.summary
    assert "activity_count" not in result.output_json
    assert set(result.tool_names_used) <= {
        "search_poi",
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_table_availability",
        "check_route",
    }


def test_itinerary_planner_adapter_returns_agent_result_and_drafts() -> None:
    plan = _plan()
    enrichment = _enrichment()

    result, drafts = DeterministicItineraryPlannerAgent().generate(plan, enrichment)

    assert result.role == "itinerary_planner"
    assert result.status == "completed"
    assert isinstance(drafts, ItineraryDraftResult)
    assert drafts.drafts


def test_validator_recovery_returns_passed_decision_for_safe_review() -> None:
    plan = _plan()
    enrichment = _enrichment()
    drafts = DeterministicItineraryGenerator().generate(plan, enrichment)

    result, review, decision = DeterministicValidatorRecoveryAgent().review(
        plan,
        enrichment,
        drafts,
        pre_confirmation_action_count=0,
    )

    assert result.role == "validator_recovery"
    assert review.safe_to_present is True
    assert isinstance(decision, RecoveryDecision)
    assert decision.verdict == "passed"
    assert decision.recovery_action == "none"
    assert decision.retry_budget == 0


def test_validator_recovery_returns_stop_safely_for_boundary_failure() -> None:
    failed_check = ReviewCheck(
        check_name="run_id_consistency",
        status="failed",
        severity="error",
        message="Run metadata is inconsistent.",
    )
    result, review, decision = DeterministicValidatorRecoveryAgent(
        gate=_StaticGate(
            FinalReviewResult(
                run_id=uuid4(),
                provider_profile="mock_world",
                decision="blocked",
                safe_to_present=False,
                checks=[failed_check],
                errors=[failed_check],
                gate_version="test-gate",
            )
        )
    ).review(
        _plan(),
        _enrichment(),
        DeterministicItineraryGenerator().generate(_plan(), _enrichment()),
        pre_confirmation_action_count=0,
    )

    assert result.role == "validator_recovery"
    assert result.status == "blocked"
    assert review.safe_to_present is False
    assert decision.verdict == "failed"
    assert decision.error_type == "run_id_consistency"
    assert decision.recovery_action == "stop_safely"
    assert decision.retry_budget == 0
    assert "does not execute recovery routes" not in decision.reason


def test_validator_recovery_returns_replace_candidate_for_blocked_first_draft_with_alternative() -> None:
    draft_1 = _draft("draft_1", activity_id="activity_1", dining_id="dining_1")
    draft_2 = _draft("draft_2", activity_id="activity_2", dining_id="dining_2")
    failed_check = ReviewCheck(
        check_name="route_verified",
        status="failed",
        severity="error",
        message="First draft route is blocked.",
        draft_id="draft_1",
    )
    review = FinalReviewResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        decision="blocked",
        safe_to_present=False,
        reviewed_drafts=[
            ReviewedDraft(
                draft_id="draft_1",
                decision="blocked",
                safe_to_present=False,
                checks=[failed_check],
                errors=[failed_check],
            ),
            ReviewedDraft(
                draft_id="draft_2",
                decision="approved",
                safe_to_present=True,
            ),
        ],
        checks=[failed_check],
        errors=[failed_check],
        gate_version="test-gate",
    )

    result, _, decision = DeterministicValidatorRecoveryAgent(gate=_StaticGate(review)).review(
        _plan(),
        _enrichment(),
        ItineraryDraftResult(
            run_id=uuid4(),
            provider_profile="mock_world",
            drafts=[draft_1, draft_2],
            generator_version="test-generator",
        ),
        pre_confirmation_action_count=0,
        recovery_context=RecoveryEvaluationContext(),
    )

    assert result.status == "blocked"
    assert decision.recovery_action == "replace_candidate"
    assert decision.route_to == "logical_planner_agent"
    assert decision.retry_budget == 1


def test_validator_recovery_returns_expand_search_radius_when_no_drafts_exist() -> None:
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

    _, _, decision = DeterministicValidatorRecoveryAgent(gate=_StaticGate(review)).review(
        _plan(),
        _enrichment(),
        ItineraryDraftResult(
            run_id=uuid4(),
            provider_profile="mock_world",
            drafts=[],
            generator_version="test-generator",
        ),
        pre_confirmation_action_count=0,
        recovery_context=RecoveryEvaluationContext(search_expansion_level=0),
    )

    assert decision.recovery_action == "expand_search_radius"
    assert decision.route_to == "generate_queries"
    assert decision.retry_budget == 1


def test_validator_recovery_returns_ask_user_after_search_expansion_is_exhausted() -> None:
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

    _, _, decision = DeterministicValidatorRecoveryAgent(gate=_StaticGate(review)).review(
        _plan(),
        _enrichment(),
        ItineraryDraftResult(
            run_id=uuid4(),
            provider_profile="mock_world",
            drafts=[],
            generator_version="test-generator",
        ),
        pre_confirmation_action_count=0,
        recovery_context=RecoveryEvaluationContext(
            attempted_actions=["expand_search_radius"],
            search_expansion_level=1,
        ),
    )

    assert decision.recovery_action == "ask_user"
    assert decision.route_to is None
    assert decision.retry_budget == 0


def test_sanitizer_removes_sensitive_keys_and_raw_ids() -> None:
    sanitized = sanitize_agent_metadata(
        {
            "safe": "value",
            "api_key": "secret",
            "nested": {
                "authorization": "Bearer token",
                "tool_event_id": "event",
                "children": [{"action_id": "action"}, {"keep": "ok"}],
            },
            "debug_trace": {"raw": True},
            "prompt": "do something",
        }
    )

    assert sanitized == {
        "safe": "value",
        "nested": {
            "children": [{}, {"keep": "ok"}],
        },
    }
