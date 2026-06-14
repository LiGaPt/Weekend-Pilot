from __future__ import annotations

from backend.app.agents.schemas import RecoveryDecision, RecoveryEvaluationContext
from backend.app.planning import ClarificationPolicySummary, ItineraryDraftResult, LocalLifeIntent, QueryPlan
from backend.app.review.schemas import FinalReviewResult, ReviewCheck


_SAFETY_BOUNDARY_FAILURES = {
    "run_id_consistency",
    "pre_confirmation_no_actions",
    "actions_require_confirmation",
    "actions_reference_draft_objects",
    "actions_have_no_execution_fields",
    "sensitive_payload_scan",
}


def decide_recovery_action(
    *,
    plan: QueryPlan,
    review: FinalReviewResult,
    drafts: ItineraryDraftResult,
    recovery_context: RecoveryEvaluationContext | None = None,
) -> RecoveryDecision:
    context = recovery_context or RecoveryEvaluationContext()
    primary_error = _primary_error(review)

    if review.safe_to_present:
        return RecoveryDecision(
            verdict="passed",
            recovery_action="none",
            retry_budget=0,
            reason="Final review is safe to present.",
        )

    if primary_error in _SAFETY_BOUNDARY_FAILURES:
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="stop_safely",
            retry_budget=0,
            reason="Blocking review failed at a confirmation or integrity boundary.",
        )

    if _has_route_wide_failure(review, drafts, context):
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="stop_safely",
            retry_budget=0,
            reason="All current routes are unusable, so deterministic recovery cannot improve the result safely.",
        )

    dining_block = _dining_availability_block(review)
    if dining_block == "queue_closed":
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="stop_safely",
            retry_budget=0,
            reason="Queue access is closed, so deterministic recovery should stop before proposing write actions.",
        )
    if dining_block in {"table_unavailable", "table_and_queue_unavailable"} and "replace_candidate" in context.attempted_actions:
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="stop_safely",
            retry_budget=0,
            reason="Dining availability remained blocked after one candidate replacement, so recovery stops safely.",
        )

    if _can_replace_candidate(review, drafts, context):
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="replace_candidate",
            route_to="logical_planner_agent",
            retry_budget=1,
            reason="The first blocked draft has an alternative candidate pair that can be tried safely.",
        )

    if _can_expand_search(review, drafts, context):
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="expand_search_radius",
            route_to="generate_queries",
            retry_budget=1,
            reason="Current candidate breadth is too narrow for a safe draft, so expand deterministic search once.",
        )

    if _user_tradeoff_may_help(review, drafts):
        return RecoveryDecision(
            verdict="failed",
            error_type=primary_error,
            recovery_action="ask_user",
            retry_budget=0,
            reason="Deterministic recovery is exhausted and needs user tradeoff input to continue planning.",
        )

    return RecoveryDecision(
        verdict="failed",
        error_type=primary_error,
        recovery_action="stop_safely",
        retry_budget=0,
        reason="No safe deterministic recovery rule matched the current review failure.",
    )


def build_recovery_clarification(intent: LocalLifeIntent) -> ClarificationPolicySummary:
    if intent.constraints.max_distance_km is not None:
        return ClarificationPolicySummary(
            policy_version="recovery_clarification_v1",
            missing_fields=["distance_flexibility"],
            question_text=(
                "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u544a\u8bc9\u6211\u662f\u5426\u53ef\u4ee5"
                "\u63a5\u53d7\u66f4\u8fdc\u4e00\u70b9\uff0c\u6216\u8005\u4ecd\u7136\u9700\u8981\u63a7\u5236"
                "\u5728\u5f53\u524d\u8ddd\u79bb\u5185\u3002"
            ),
        )

    return ClarificationPolicySummary(
        policy_version="recovery_clarification_v1",
        missing_fields=["preference_tradeoff"],
        question_text=(
            "\u4e3a\u4e86\u7ee7\u7eed\u89c4\u5212\uff0c\u8bf7\u8865\u5145\u66f4\u504f\u597d\u7684\u6d3b"
            "\u52a8\u6216\u7528\u9910\u65b9\u5411\uff0c\u6216\u8bf4\u660e\u54ea\u4e9b\u7ea6\u675f\u53ef"
            "\u4ee5\u653e\u5bbd\u3002"
        ),
    )


def _primary_error(review: FinalReviewResult) -> str:
    first_error = review.errors[0] if review.errors else None
    return first_error.check_name if isinstance(first_error, ReviewCheck) else "plan_invalid"


def _has_route_wide_failure(
    review: FinalReviewResult,
    drafts: ItineraryDraftResult,
    recovery_context: RecoveryEvaluationContext,
) -> bool:
    if _primary_error(review) != "draft_exists":
        return False
    if drafts.drafts:
        return False
    if any(reason.code == "missing_usable_route" for reason in drafts.failed_reasons):
        return True
    return "route_infeasible" in recovery_context.route_failure_codes


def _can_replace_candidate(
    review: FinalReviewResult,
    drafts: ItineraryDraftResult,
    recovery_context: RecoveryEvaluationContext,
) -> bool:
    if len(drafts.drafts) < 2:
        return False
    first_pair = _first_draft_pair(drafts)
    if first_pair is None or not _first_draft_is_blocked(review, drafts):
        return False
    return first_pair not in {
        (pair.activity_candidate_id, pair.dining_candidate_id)
        for pair in recovery_context.excluded_candidate_pairs
    }


def _can_expand_search(
    review: FinalReviewResult,
    drafts: ItineraryDraftResult,
    recovery_context: RecoveryEvaluationContext,
) -> bool:
    if recovery_context.search_expansion_level != 0:
        return False
    return not drafts.drafts or _first_draft_is_blocked(review, drafts)


def _user_tradeoff_may_help(review: FinalReviewResult, drafts: ItineraryDraftResult) -> bool:
    return _primary_error(review) == "draft_exists" or _first_draft_is_blocked(review, drafts)


def _first_draft_is_blocked(review: FinalReviewResult, drafts: ItineraryDraftResult) -> bool:
    if not drafts.drafts:
        return False
    first_draft_id = drafts.drafts[0].draft_id
    for reviewed_draft in review.reviewed_drafts:
        if reviewed_draft.draft_id == first_draft_id:
            return not reviewed_draft.safe_to_present
    return any(check.draft_id == first_draft_id for check in review.errors)


def _first_draft_pair(drafts: ItineraryDraftResult) -> tuple[str, str] | None:
    if not drafts.drafts:
        return None
    first_draft = drafts.drafts[0]
    return first_draft.activity.candidate_id, first_draft.dining.candidate_id


def _dining_availability_block(review: FinalReviewResult) -> str | None:
    for error in review.errors:
        if not isinstance(error, ReviewCheck) or error.check_name != "dining_availability":
            continue
        details = error.details if isinstance(error.details, dict) else {}
        status = details.get("availability_status")
        return status if isinstance(status, str) and status else None
    return None
