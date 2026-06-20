from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from backend.app.memory_governance_audit import (
    MEMORY_POLICY_VERSION,
    classify_memory_governance_audit,
    memory_dimension,
    parse_confidence,
)
from backend.app.planning.schemas import IntentParseSignals, LocalLifeIntent


if TYPE_CHECKING:
    from backend.app.workflow.state import WorkflowMemoryRecord


_ACTIVITY_DIMENSION = "activity_preferences"
_DINING_DIMENSION = "dining_preferences"
MemoryGovernanceDimension = Literal["activity_preferences", "dining_preferences"]
MemoryGovernanceTier = Literal["trusted", "advisory", "weak"]
MemoryGovernanceWinnerSource = Literal["user_input", "memory", "none"]
MemoryGovernanceOutcome = Literal[
    "applied_trusted",
    "applied_advisory",
    "suppressed_user_override",
    "suppressed_weak_signal",
    "unsupported_key",
    "unrecognized_value",
]
MemoryDecisionStatus = Literal["used", "ignored", "downgraded", "overridden"]
MemoryDecisionInfluenceLevel = Literal["primary", "advisory", "none"]


class MemoryGovernanceDimensionOutcome(BaseModel):
    dimension: MemoryGovernanceDimension
    winner_source: MemoryGovernanceWinnerSource
    winner_memory_key: str | None = None
    winner_tier: Literal["trusted", "advisory"] | None = None
    effective_values: list[str] = Field(default_factory=list)
    suppressed_memory_keys: list[str] = Field(default_factory=list)


class MemoryGovernanceDecision(BaseModel):
    memory_key: str
    dimension: MemoryGovernanceDimension
    normalized_value: str | None = None
    confidence: str | None = None
    tier: MemoryGovernanceTier
    expired: bool = False
    outcome: MemoryGovernanceOutcome


class MemoryDecisionLogEntry(BaseModel):
    memory_id: str
    key: str
    status: MemoryDecisionStatus
    decision: MemoryGovernanceOutcome
    reason: str
    influence_level: MemoryDecisionInfluenceLevel
    dimension: MemoryGovernanceDimension
    normalized_value: str | None = None
    tier: MemoryGovernanceTier
    expired: bool = False


class MemoryPolicyAuditSummary(BaseModel):
    policy_version: str = MEMORY_POLICY_VERSION
    considered_count: int = 0
    used_count: int = 0
    ignored_count: int = 0
    downgraded_count: int = 0
    overridden_count: int = 0
    primary_influence_count: int = 0
    advisory_influence_count: int = 0
    no_influence_count: int = 0


class MemoryQueryPolicySummary(BaseModel):
    policy_version: str = MEMORY_POLICY_VERSION
    applied_memory_keys: list[str] = Field(default_factory=list)
    advisory_memory_keys: list[str] = Field(default_factory=list)
    downgraded_low_confidence_keys: list[str] = Field(default_factory=list)
    downgraded_expired_keys: list[str] = Field(default_factory=list)
    user_override_dimensions: list[str] = Field(default_factory=list)
    unsupported_memory_keys: list[str] = Field(default_factory=list)
    effective_activity_preferences: list[str] = Field(default_factory=list)
    effective_dining_preferences: list[str] = Field(default_factory=list)
    dimension_outcomes: list[MemoryGovernanceDimensionOutcome] = Field(default_factory=list)
    memory_decisions: list[MemoryGovernanceDecision] = Field(default_factory=list)
    decision_log: list[MemoryDecisionLogEntry] = Field(default_factory=list)
    policy_summary: MemoryPolicyAuditSummary = Field(default_factory=MemoryPolicyAuditSummary)


def apply_memory_query_policy(
    intent: LocalLifeIntent,
    signals: IntentParseSignals,
    active_memories: list[WorkflowMemoryRecord],
) -> tuple[LocalLifeIntent, MemoryQueryPolicySummary]:
    effective_activity_preferences = list(intent.activity_preferences)
    effective_dining_preferences = list(intent.dining_preferences)
    applied_memory_keys: list[str] = []
    advisory_memory_keys: list[str] = []
    downgraded_low_confidence_keys: list[str] = []
    downgraded_expired_keys: list[str] = []
    user_override_dimensions: list[str] = []
    unsupported_memory_keys: list[str] = []
    dimension_outcomes: list[MemoryGovernanceDimensionOutcome] = []
    memory_decisions: list[MemoryGovernanceDecision] = []
    decision_log: list[MemoryDecisionLogEntry] = []

    for memory in active_memories:
        if memory.memory_type != "preference":
            continue

        key = memory.key
        dimension = memory_dimension(key)
        if dimension is None:
            _append_unique(unsupported_memory_keys, key)
            memory_decisions.append(
                decision := MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=_ACTIVITY_DIMENSION,
                    normalized_value=None,
                    confidence=_string_or_none(memory.confidence),
                    tier="weak",
                    expired=False,
                    outcome="unsupported_key",
                )
            )
            decision_log.append(_build_decision_log_entry(memory=memory, decision=decision))
            continue

        audit = classify_memory_governance_audit(
            memory_type=memory.memory_type,
            key=memory.key,
            value_json=memory.value_json,
            text=memory.text,
            confidence=memory.confidence,
            status=memory.status,
            expires_at=memory.expires_at,
            lifecycle_state=getattr(memory, "lifecycle_state", None),
        )
        normalized_value = audit.normalized_value
        confidence = parse_confidence(memory.confidence)
        expired = audit.expired
        tier: MemoryGovernanceTier = audit.tier or "weak"
        confidence_text = _string_or_none(memory.confidence)

        if confidence is None or (not expired and tier != "trusted"):
            _append_unique(downgraded_low_confidence_keys, key)
        if expired:
            _append_unique(downgraded_expired_keys, key)

        if normalized_value is None:
            memory_decisions.append(
                decision := MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=dimension,
                    normalized_value=None,
                    confidence=confidence_text,
                    tier=tier,
                    expired=expired,
                    outcome="unrecognized_value",
                )
            )
            decision_log.append(_build_decision_log_entry(memory=memory, decision=decision))
            continue

        if _is_user_override_dimension(dimension, signals):
            _append_unique(user_override_dimensions, dimension)
            effective_values = (
                effective_activity_preferences
                if dimension == _ACTIVITY_DIMENSION
                else effective_dining_preferences
            )
            dimension_outcomes.append(
                MemoryGovernanceDimensionOutcome(
                    dimension=dimension,
                    winner_source="user_input",
                    winner_memory_key=None,
                    winner_tier=None,
                    effective_values=list(effective_values),
                    suppressed_memory_keys=[key],
                )
            )
            memory_decisions.append(
                decision := MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=dimension,
                    normalized_value=normalized_value,
                    confidence=confidence_text,
                    tier=tier,
                    expired=expired,
                    outcome="suppressed_user_override",
                )
            )
            decision_log.append(_build_decision_log_entry(memory=memory, decision=decision))
            continue

        if tier == "weak":
            memory_decisions.append(
                decision := MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=dimension,
                    normalized_value=normalized_value,
                    confidence=confidence_text,
                    tier=tier,
                    expired=expired,
                    outcome="suppressed_weak_signal",
                )
            )
            decision_log.append(_build_decision_log_entry(memory=memory, decision=decision))
            continue

        effective_values = effective_activity_preferences
        if dimension == _DINING_DIMENSION:
            effective_values = effective_dining_preferences

        if normalized_value not in effective_values:
            effective_values.append(normalized_value)

        _append_unique(applied_memory_keys, key)
        if tier == "advisory":
            _append_unique(advisory_memory_keys, key)
        memory_decisions.append(
            decision := MemoryGovernanceDecision(
                memory_key=key,
                dimension=dimension,
                normalized_value=normalized_value,
                confidence=confidence_text,
                tier=tier,
                expired=expired,
                outcome="applied_trusted" if tier == "trusted" else "applied_advisory",
            )
        )
        decision_log.append(_build_decision_log_entry(memory=memory, decision=decision))
        dimension_outcomes.append(
            MemoryGovernanceDimensionOutcome(
                dimension=dimension,
                winner_source="memory",
                winner_memory_key=key,
                winner_tier=tier,
                effective_values=list(effective_values),
                suppressed_memory_keys=[],
            )
        )

    effective_intent = intent.model_copy(
        update={
            "activity_preferences": effective_activity_preferences,
            "dining_preferences": effective_dining_preferences,
        }
    )
    summary = MemoryQueryPolicySummary(
        applied_memory_keys=applied_memory_keys,
        advisory_memory_keys=advisory_memory_keys,
        downgraded_low_confidence_keys=downgraded_low_confidence_keys,
        downgraded_expired_keys=downgraded_expired_keys,
        user_override_dimensions=user_override_dimensions,
        unsupported_memory_keys=unsupported_memory_keys,
        effective_activity_preferences=effective_activity_preferences,
        effective_dining_preferences=effective_dining_preferences,
        dimension_outcomes=sorted(
            dimension_outcomes,
            key=lambda item: 0 if item.dimension == _ACTIVITY_DIMENSION else 1,
        ),
        memory_decisions=memory_decisions,
        decision_log=decision_log,
        policy_summary=_build_policy_summary(decision_log),
    )
    return effective_intent, summary


def _build_decision_log_entry(
    *,
    memory: "WorkflowMemoryRecord",
    decision: MemoryGovernanceDecision,
) -> MemoryDecisionLogEntry:
    status, reason, influence_level = _normalize_decision(decision)
    return MemoryDecisionLogEntry(
        memory_id=str(memory.memory_id),
        key=decision.memory_key,
        status=status,
        decision=decision.outcome,
        reason=reason,
        influence_level=influence_level,
        dimension=decision.dimension,
        normalized_value=decision.normalized_value,
        tier=decision.tier,
        expired=decision.expired,
    )


def _normalize_decision(
    decision: MemoryGovernanceDecision,
) -> tuple[MemoryDecisionStatus, str, MemoryDecisionInfluenceLevel]:
    if decision.outcome == "applied_trusted":
        return ("used", "trusted_memory_applied", "primary")
    if decision.outcome == "applied_advisory":
        reason = "expired_memory_downgraded_to_advisory" if decision.expired else "low_confidence_downgraded_to_advisory"
        return ("downgraded", reason, "advisory")
    if decision.outcome == "suppressed_user_override":
        return ("overridden", "explicit_user_input_present", "none")
    if decision.outcome == "suppressed_weak_signal":
        return ("ignored", "weak_signal_not_applied", "none")
    if decision.outcome == "unsupported_key":
        return ("ignored", "unsupported_projected_key", "none")
    return ("ignored", "unrecognized_supported_value", "none")


def _build_policy_summary(decision_log: list[MemoryDecisionLogEntry]) -> MemoryPolicyAuditSummary:
    summary = MemoryPolicyAuditSummary(considered_count=len(decision_log))
    for entry in decision_log:
        if entry.status == "used":
            summary.used_count += 1
        elif entry.status == "ignored":
            summary.ignored_count += 1
        elif entry.status == "downgraded":
            summary.downgraded_count += 1
        elif entry.status == "overridden":
            summary.overridden_count += 1

        if entry.influence_level == "primary":
            summary.primary_influence_count += 1
        elif entry.influence_level == "advisory":
            summary.advisory_influence_count += 1
        elif entry.influence_level == "none":
            summary.no_influence_count += 1
    return summary


def _is_user_override_dimension(dimension: MemoryGovernanceDimension, signals: IntentParseSignals) -> bool:
    if dimension == _ACTIVITY_DIMENSION:
        return signals.activity_preferences
    return signals.dining_preferences


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
