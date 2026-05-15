from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.app.agents.policies import default_agent_policy, validate_agent_tool_usage
from backend.app.agents.schemas import (
    AgentInvocationContext,
    AgentResult,
    RecoveryDecision,
    SupervisorAssignment,
    SupervisorAssignmentPlan,
)
from backend.app.planning import (
    CandidateCollectionResult,
    CandidateEnrichmentResult,
    DeterministicItineraryGenerator,
    ItineraryDraftResult,
    QueryPlan,
)
from backend.app.review import FinalReviewGate
from backend.app.review.schemas import FinalReviewResult


AGENT_METADATA_VERSION = "bounded_agents_v1"
_SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
    "tool_event_id",
    "action_id",
)


def sanitize_agent_metadata(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return sanitize_agent_metadata(value.model_dump(mode="json"))
    if isinstance(value, dict):
        sanitized = {}
        for key, child in value.items():
            if isinstance(key, str) and _is_sensitive_key(key):
                continue
            sanitized[key] = sanitize_agent_metadata(child)
        return sanitized
    if isinstance(value, list):
        return [sanitize_agent_metadata(item) for item in value]
    return value


def sanitized_agent_payload(results: list[AgentResult]) -> dict[str, Any]:
    return {
        "version": AGENT_METADATA_VERSION,
        "results": [
            sanitize_agent_metadata(result.model_dump(mode="json"))
            for result in results
        ],
    }


class DeterministicSupervisorAgent:
    adapter_version = "deterministic_supervisor_v1"
    role = "supervisor"

    def assign(
        self,
        plan: QueryPlan,
        context: AgentInvocationContext | None = None,
    ) -> tuple[AgentResult, SupervisorAssignmentPlan]:
        del context
        assignments = [
            SupervisorAssignment(
                assignment_id="assignment_discovery_v1",
                target_role="discovery",
                objective="Summarize activity candidate evidence from deterministic collection and enrichment outputs.",
                required_inputs=["query_plan", "candidate_collection", "enrichment_result"],
                allowed_tool_names=default_agent_policy("discovery").allowed_read_tools,
            ),
            SupervisorAssignment(
                assignment_id="assignment_dining_v1",
                target_role="dining",
                objective="Summarize dining candidate evidence from deterministic collection and enrichment outputs.",
                required_inputs=["query_plan", "candidate_collection", "enrichment_result"],
                allowed_tool_names=default_agent_policy("dining").allowed_read_tools,
            ),
            SupervisorAssignment(
                assignment_id="assignment_itinerary_planner_v1",
                target_role="itinerary_planner",
                objective="Generate deterministic itinerary drafts from enriched candidates.",
                required_inputs=["query_plan", "enrichment_result"],
                allowed_tool_names=[],
            ),
            SupervisorAssignment(
                assignment_id="assignment_validator_recovery_v1",
                target_role="validator_recovery",
                objective="Review deterministic itinerary drafts and emit a bounded recovery decision.",
                required_inputs=["query_plan", "enrichment_result", "itinerary_drafts"],
                allowed_tool_names=[],
            ),
        ]
        assignment_plan = SupervisorAssignmentPlan(
            assignments=assignments,
            summary="Created deterministic bounded-agent assignments.",
        )
        result = _agent_result(
            role="supervisor",
            adapter_version=self.adapter_version,
            summary=assignment_plan.summary,
            output_json={
                "assignment_count": len(assignments),
                "target_roles": [assignment.target_role for assignment in assignments],
            },
        )
        return result, assignment_plan


class DeterministicDiscoveryAgent:
    adapter_version = "deterministic_discovery_v1"
    role = "discovery"

    def summarize(
        self,
        plan: QueryPlan,
        collection: CandidateCollectionResult,
        enrichment: CandidateEnrichmentResult,
        context: AgentInvocationContext | None = None,
    ) -> AgentResult:
        del plan, context
        names = [item.candidate.name for item in enrichment.enriched_activity_candidates]
        tool_names = _unique_tools(
            result.tool_name
            for result in [
                *collection.tool_results,
                *enrichment.tool_results,
                *[
                    tool_result
                    for candidate in enrichment.enriched_activity_candidates
                    for tool_result in candidate.tool_results
                ],
            ]
            if result.tool_name in default_agent_policy("discovery").allowed_read_tools
        )
        route_count = len(enrichment.route_matrix)
        if route_count and "check_route" not in tool_names:
            tool_names.append("check_route")
        validate_agent_tool_usage("discovery", tool_names)
        return _agent_result(
            role="discovery",
            adapter_version=self.adapter_version,
            summary=f"Found {len(names)} activity candidates: {_name_summary(names)}.",
            tool_names_used=tool_names,
            output_json={
                "activity_count": len(names),
                "activity_names": names,
                "evidence_status": _status_counts(
                    tool_result.status
                    for candidate in enrichment.enriched_activity_candidates
                    for tool_result in candidate.tool_results
                ),
                "route_evidence_count": route_count,
            },
        )


class DeterministicDiningAgent:
    adapter_version = "deterministic_dining_v1"
    role = "dining"

    def summarize(
        self,
        plan: QueryPlan,
        collection: CandidateCollectionResult,
        enrichment: CandidateEnrichmentResult,
        context: AgentInvocationContext | None = None,
    ) -> AgentResult:
        del plan, context
        names = [item.candidate.name for item in enrichment.enriched_dining_candidates]
        dining_tool_results = [
            tool_result
            for candidate in enrichment.enriched_dining_candidates
            for tool_result in candidate.tool_results
        ]
        tool_names = _unique_tools(
            result.tool_name
            for result in [*collection.tool_results, *enrichment.tool_results, *dining_tool_results]
            if result.tool_name in default_agent_policy("dining").allowed_read_tools
        )
        route_count = len(enrichment.route_matrix)
        if route_count and "check_route" not in tool_names:
            tool_names.append("check_route")
        validate_agent_tool_usage("dining", tool_names)
        return _agent_result(
            role="dining",
            adapter_version=self.adapter_version,
            summary=f"Found {len(names)} dining candidates: {_name_summary(names)}.",
            tool_names_used=tool_names,
            output_json={
                "dining_count": len(names),
                "dining_names": names,
                "queue_evidence_count": sum(
                    1 for item in enrichment.enriched_dining_candidates if item.queue is not None
                ),
                "table_evidence_count": sum(
                    1 for item in enrichment.enriched_dining_candidates if item.table_availability is not None
                ),
                "evidence_status": _status_counts(tool_result.status for tool_result in dining_tool_results),
                "route_evidence_count": route_count,
            },
        )


class DeterministicItineraryPlannerAgent:
    adapter_version = "deterministic_itinerary_planner_v1"
    role = "itinerary_planner"

    def __init__(self, generator: DeterministicItineraryGenerator | None = None) -> None:
        self._generator = generator or DeterministicItineraryGenerator()

    def generate(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        context: AgentInvocationContext | None = None,
    ) -> tuple[AgentResult, ItineraryDraftResult]:
        del context
        drafts = self._generator.generate(plan, enrichment)
        status = "completed" if drafts.drafts else "blocked"
        result = _agent_result(
            role="itinerary_planner",
            status=status,
            adapter_version=self.adapter_version,
            summary=f"Generated {len(drafts.drafts)} deterministic itinerary drafts.",
            output_json={
                "draft_count": len(drafts.drafts),
                "failed_reason_codes": [reason.code for reason in drafts.failed_reasons],
                "generator_version": drafts.generator_version,
            },
        )
        return result, drafts


class DeterministicValidatorRecoveryAgent:
    adapter_version = "deterministic_validator_recovery_v1"
    role = "validator_recovery"

    def __init__(self, gate: FinalReviewGate | None = None) -> None:
        self._gate = gate or FinalReviewGate()

    def review(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        drafts: ItineraryDraftResult,
        pre_confirmation_action_count: int = 0,
        context: AgentInvocationContext | None = None,
    ) -> tuple[AgentResult, FinalReviewResult, RecoveryDecision]:
        del context
        review = self._gate.review(
            plan,
            enrichment,
            drafts,
            pre_confirmation_action_count=pre_confirmation_action_count,
        )
        decision = self._decision(review)
        result = _agent_result(
            role="validator_recovery",
            status="completed" if review.safe_to_present else "blocked",
            adapter_version=self.adapter_version,
            summary=f"Final review decision is {review.decision}.",
            output_json={
                "review_decision": review.decision,
                "safe_to_present": review.safe_to_present,
                "error_count": len(review.errors),
                "warning_count": len(review.warnings),
                "recovery_decision": decision.model_dump(mode="json"),
            },
        )
        return result, review, decision

    def _decision(self, review: FinalReviewResult) -> RecoveryDecision:
        if review.safe_to_present:
            return RecoveryDecision(
                verdict="passed",
                recovery_action="none",
                retry_budget=0,
                reason="Final review is safe to present.",
            )
        error_type = review.errors[0].check_name if review.errors else "plan_invalid"
        return RecoveryDecision(
            verdict="failed",
            error_type=error_type,
            recovery_action="stop_safely",
            retry_budget=0,
            reason="Final review blocked presentation; Task 020 does not execute recovery routes.",
        )


def _agent_result(
    *,
    role: str,
    adapter_version: str,
    summary: str,
    status: str = "completed",
    tool_names_used: list[str] | None = None,
    output_json: dict[str, Any] | None = None,
    error_json: dict[str, Any] | None = None,
) -> AgentResult:
    return AgentResult(
        role=role,
        status=status,
        summary=summary,
        adapter_version=adapter_version,
        tool_names_used=tool_names_used or [],
        output_json=sanitize_agent_metadata(output_json or {}),
        error_json=sanitize_agent_metadata(error_json) if error_json is not None else None,
    )


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _name_summary(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


def _unique_tools(tool_names: Any) -> list[str]:
    seen = set()
    ordered = []
    for tool_name in tool_names:
        if not isinstance(tool_name, str) or tool_name in seen:
            continue
        seen.add(tool_name)
        ordered.append(tool_name)
    return ordered


def _status_counts(statuses: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses:
        if not isinstance(status, str):
            continue
        counts[status] = counts.get(status, 0) + 1
    return counts
