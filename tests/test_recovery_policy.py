from __future__ import annotations

from uuid import uuid4

from backend.app.agents.recovery_policy import (
    build_recovery_clarification,
    decide_recovery_action,
)
from backend.app.agents.schemas import RecoveryEvaluationContext, RecoveryExcludedCandidatePair
from backend.app.planning import (
    FeasibilitySummary,
    IntentConstraints,
    ItineraryCandidateRef,
    ItineraryDraft,
    ItineraryDraftResult,
    ItineraryFailureReason,
    ItineraryRouteRef,
    LocalLifeIntent,
    ParticipantProfile,
    QueryPlan,
    TimeWindow,
)
from backend.app.review.schemas import FinalReviewResult, ReviewCheck, ReviewedDraft


def _intent(*, max_distance_km: int | None = 8) -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="family afternoon",
        scenario_type="family",
        participants=ParticipantProfile(adults=2, children_ages=[5]),
        time_window=TimeWindow(duration_hours_min=4, duration_hours_max=6),
        constraints=IntentConstraints(child_friendly=True, max_distance_km=max_distance_km),
        activity_preferences=["child_friendly"],
        dining_preferences=["lighter_options"],
        parser_version="test-parser",
    )


def _plan(*, max_distance_km: int | None = 8) -> QueryPlan:
    return QueryPlan(
        intent=_intent(max_distance_km=max_distance_km),
        provider_profile="mock_world",
        planner_version="test-planner",
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
        summary="draft summary",
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
            distance_meters=1200,
            duration_minutes=18,
        ),
        feasibility=FeasibilitySummary(
            is_feasible=True,
            reasons=["usable"],
            total_duration_minutes=300,
            route_duration_minutes=18,
        ),
    )


def _draft_result(
    drafts: list[ItineraryDraft],
    *,
    failed_reasons: list[ItineraryFailureReason] | None = None,
) -> ItineraryDraftResult:
    return ItineraryDraftResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        drafts=drafts,
        failed_reasons=failed_reasons or [],
        generator_version="test-generator",
    )


def _review(
    *,
    safe_to_present: bool,
    errors: list[ReviewCheck],
    reviewed_drafts: list[ReviewedDraft] | None = None,
) -> FinalReviewResult:
    warnings = [check for check in errors if check.status == "warning"]
    return FinalReviewResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        decision="approved" if safe_to_present else "blocked",
        safe_to_present=safe_to_present,
        reviewed_drafts=reviewed_drafts or [],
        checks=list(errors),
        errors=errors,
        warnings=warnings,
        gate_version="test-gate",
    )


def _failed_check(check_name: str, *, draft_id: str | None = None) -> ReviewCheck:
    return ReviewCheck(
        check_name=check_name,
        status="failed",
        severity="error",
        message=f"{check_name} failed",
        draft_id=draft_id,
    )


def _reviewed_draft(
    draft_id: str,
    *,
    safe_to_present: bool,
    errors: list[ReviewCheck] | None = None,
) -> ReviewedDraft:
    return ReviewedDraft(
        draft_id=draft_id,
        decision="approved" if safe_to_present else "blocked",
        safe_to_present=safe_to_present,
        checks=list(errors or []),
        errors=list(errors or []),
        warnings=[],
    )


def test_recovery_policy_returns_pass_for_safe_review() -> None:
    decision = decide_recovery_action(
        plan=_plan(),
        review=_review(safe_to_present=True, errors=[]),
        drafts=_draft_result([_draft("draft_1", activity_id="activity_1", dining_id="dining_1")]),
        recovery_context=RecoveryEvaluationContext(),
    )

    assert decision.verdict == "passed"
    assert decision.recovery_action == "none"
    assert decision.retry_budget == 0


def test_recovery_policy_stops_for_confirmation_boundary_failure() -> None:
    decision = decide_recovery_action(
        plan=_plan(),
        review=_review(
            safe_to_present=False,
            errors=[_failed_check("pre_confirmation_no_actions")],
        ),
        drafts=_draft_result([_draft("draft_1", activity_id="activity_1", dining_id="dining_1")]),
        recovery_context=RecoveryEvaluationContext(),
    )

    assert decision.verdict == "failed"
    assert decision.error_type == "pre_confirmation_no_actions"
    assert decision.recovery_action == "stop_safely"


def test_recovery_policy_stops_for_route_wide_failure_without_drafts() -> None:
    decision = decide_recovery_action(
        plan=_plan(),
        review=_review(
            safe_to_present=False,
            errors=[_failed_check("draft_exists")],
        ),
        drafts=_draft_result(
            [],
            failed_reasons=[
                ItineraryFailureReason(
                    code="missing_usable_route",
                    message="no usable routes",
                )
            ],
        ),
        recovery_context=RecoveryEvaluationContext(route_failure_codes=["route_infeasible"]),
    )

    assert decision.verdict == "failed"
    assert decision.error_type == "draft_exists"
    assert decision.recovery_action == "stop_safely"


def test_recovery_policy_replaces_first_blocked_pair_when_alternative_exists() -> None:
    drafts = _draft_result(
        [
            _draft("draft_1", activity_id="activity_1", dining_id="dining_1"),
            _draft("draft_2", activity_id="activity_2", dining_id="dining_2"),
        ]
    )
    blocked = _failed_check("route_verified", draft_id="draft_1")

    decision = decide_recovery_action(
        plan=_plan(),
        review=_review(
            safe_to_present=False,
            errors=[blocked],
            reviewed_drafts=[
                _reviewed_draft("draft_1", safe_to_present=False, errors=[blocked]),
                _reviewed_draft("draft_2", safe_to_present=True),
            ],
        ),
        drafts=drafts,
        recovery_context=RecoveryEvaluationContext(),
    )

    assert decision.recovery_action == "replace_candidate"
    assert decision.route_to == "logical_planner_agent"
    assert decision.retry_budget == 1


def test_recovery_policy_expands_search_once_when_candidate_breadth_is_narrow() -> None:
    decision = decide_recovery_action(
        plan=_plan(),
        review=_review(
            safe_to_present=False,
            errors=[_failed_check("draft_exists")],
        ),
        drafts=_draft_result([]),
        recovery_context=RecoveryEvaluationContext(search_expansion_level=0),
    )

    assert decision.recovery_action == "expand_search_radius"
    assert decision.route_to == "generate_queries"
    assert decision.retry_budget == 1


def test_recovery_policy_asks_user_after_expansion_is_already_used() -> None:
    decision = decide_recovery_action(
        plan=_plan(),
        review=_review(
            safe_to_present=False,
            errors=[_failed_check("draft_exists")],
        ),
        drafts=_draft_result([]),
        recovery_context=RecoveryEvaluationContext(
            attempted_actions=["expand_search_radius"],
            search_expansion_level=1,
        ),
    )

    assert decision.recovery_action == "ask_user"
    assert decision.route_to is None
    assert decision.retry_budget == 0


def test_recovery_policy_does_not_repeat_replace_candidate_for_same_pair() -> None:
    drafts = _draft_result(
        [
            _draft("draft_1", activity_id="activity_1", dining_id="dining_1"),
            _draft("draft_2", activity_id="activity_2", dining_id="dining_2"),
        ]
    )
    blocked = _failed_check("route_verified", draft_id="draft_1")

    decision = decide_recovery_action(
        plan=_plan(max_distance_km=None),
        review=_review(
            safe_to_present=False,
            errors=[blocked],
            reviewed_drafts=[
                _reviewed_draft("draft_1", safe_to_present=False, errors=[blocked]),
                _reviewed_draft("draft_2", safe_to_present=True),
            ],
        ),
        drafts=drafts,
        recovery_context=RecoveryEvaluationContext(
            excluded_candidate_pairs=[
                RecoveryExcludedCandidatePair(
                    activity_candidate_id="activity_1",
                    dining_candidate_id="dining_1",
                )
            ],
        ),
    )

    assert decision.recovery_action == "expand_search_radius"
    assert decision.route_to == "generate_queries"


def test_recovery_clarification_uses_distance_tradeoff_prompt_when_distance_is_present() -> None:
    clarification = build_recovery_clarification(_intent(max_distance_km=8))

    assert clarification.policy_version == "recovery_clarification_v1"
    assert clarification.missing_fields == ["distance_flexibility"]
    assert clarification.question_text == (
        "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
        "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
        "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
    )


def test_recovery_clarification_uses_preference_tradeoff_prompt_without_distance_constraint() -> None:
    clarification = build_recovery_clarification(_intent(max_distance_km=None))

    assert clarification.policy_version == "recovery_clarification_v1"
    assert clarification.missing_fields == ["preference_tradeoff"]
    assert clarification.question_text == (
        "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u8865\u5145\u66f4\u504f\u597d\u7684\u6d3b"
        "\u52a8\u6216\u7528\u9910\u65b9\u5411\uff0c\u6216\u8bf4\u660e\u54ea\u4e9b\u7ea6\u675f\u53ef"
        "\u4ee5\u653e\u5bbd\u3002"
    )
