from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from backend.app.agents import RecoveryDecision


RecoveryRouteTarget = Literal[
    "final_review",
    "generate_queries",
    "execute_searches",
    "logical_planner_agent",
    "failed",
    "error",
]
RecoveryAttemptStatus = Literal["routed", "stopped"]

_ACTION_ROUTE_MAP = {
    "retry": "execute_searches",
    "expand_search_radius": "generate_queries",
    "replace_candidate": "logical_planner_agent",
}
_ALLOWED_ACTION_ROUTES = {
    "retry": {"execute_searches"},
    "expand_search_radius": {"generate_queries"},
    "replace_candidate": {"logical_planner_agent"},
}


class RecoveryAttempt(BaseModel):
    attempt_index: int
    source_node: str = "semantic_validator"
    recovery_action: str
    route_to: str | None = None
    error_type: str | None = None
    reason: str
    retry_budget_before: int
    retry_budget_after: int
    status: RecoveryAttemptStatus


class RecoveryRouteResult(BaseModel):
    route_to: RecoveryRouteTarget
    attempt: RecoveryAttempt | None = None
    error_type: str | None = None
    message: str | None = None


def resolve_recovery_route(
    decision: RecoveryDecision | None,
    *,
    attempt_count: int,
    max_attempts: int,
) -> RecoveryRouteResult:
    attempt_index = attempt_count + 1
    max_attempts = max(max_attempts, 0)

    if decision is None:
        return _stop(
            attempt_index=attempt_index,
            recovery_action="missing",
            route_to=None,
            error_type="missing_recovery_decision",
            reason="Recovery decision was missing after semantic validation.",
            retry_budget_before=0,
            retry_budget_after=0,
            message="Recovery stopped safely.",
        )

    if decision.verdict == "passed" or decision.recovery_action == "none":
        return RecoveryRouteResult(route_to="final_review")

    retry_budget_before = max(decision.retry_budget, 0)
    if decision.recovery_action == "ask_user":
        return _stop_from_decision(
            decision,
            attempt_index=attempt_index,
            error_type="recovery_requires_user_input",
            retry_budget_before=retry_budget_before,
            retry_budget_after=retry_budget_before,
            message="Recovery requires user input.",
        )
    if decision.recovery_action == "stop_safely":
        return _stop_from_decision(
            decision,
            attempt_index=attempt_index,
            error_type="recovery_stopped",
            retry_budget_before=retry_budget_before,
            retry_budget_after=retry_budget_before,
            message="Recovery stopped safely.",
        )
    if attempt_count >= max_attempts:
        return _stop_from_decision(
            decision,
            attempt_index=attempt_index,
            error_type="recovery_attempt_limit_exceeded",
            retry_budget_before=retry_budget_before,
            retry_budget_after=retry_budget_before,
            message="Recovery stopped safely.",
        )
    if retry_budget_before <= 0:
        return _stop_from_decision(
            decision,
            attempt_index=attempt_index,
            error_type="recovery_budget_exhausted",
            retry_budget_before=retry_budget_before,
            retry_budget_after=0,
            message="Recovery stopped safely.",
        )

    route_to = decision.route_to or _ACTION_ROUTE_MAP.get(decision.recovery_action)
    if route_to not in _ALLOWED_ACTION_ROUTES.get(decision.recovery_action, set()):
        return _stop_from_decision(
            decision,
            attempt_index=attempt_index,
            error_type="unsupported_recovery_route",
            retry_budget_before=retry_budget_before,
            retry_budget_after=retry_budget_before,
            message="Recovery stopped safely.",
        )

    attempt = RecoveryAttempt(
        attempt_index=attempt_index,
        recovery_action=decision.recovery_action,
        route_to=route_to,
        error_type=decision.error_type,
        reason=decision.reason,
        retry_budget_before=retry_budget_before,
        retry_budget_after=retry_budget_before - 1,
        status="routed",
    )
    return RecoveryRouteResult(route_to=route_to, attempt=attempt)


def _stop_from_decision(
    decision: RecoveryDecision,
    *,
    attempt_index: int,
    error_type: str,
    retry_budget_before: int,
    retry_budget_after: int,
    message: str,
) -> RecoveryRouteResult:
    return _stop(
        attempt_index=attempt_index,
        recovery_action=decision.recovery_action,
        route_to=decision.route_to,
        error_type=error_type,
        reason=decision.reason,
        retry_budget_before=retry_budget_before,
        retry_budget_after=retry_budget_after,
        message=message,
        original_error_type=decision.error_type,
    )


def _stop(
    *,
    attempt_index: int,
    recovery_action: str,
    route_to: str | None,
    error_type: str,
    reason: str,
    retry_budget_before: int,
    retry_budget_after: int,
    message: str,
    original_error_type: str | None = None,
) -> RecoveryRouteResult:
    attempt = RecoveryAttempt(
        attempt_index=attempt_index,
        recovery_action=recovery_action,
        route_to=route_to,
        error_type=original_error_type,
        reason=reason,
        retry_budget_before=retry_budget_before,
        retry_budget_after=retry_budget_after,
        status="stopped",
    )
    return RecoveryRouteResult(
        route_to="failed",
        attempt=attempt,
        error_type=error_type,
        message=message,
    )
