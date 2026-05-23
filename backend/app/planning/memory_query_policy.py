from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from backend.app.planning.schemas import IntentParseSignals, LocalLifeIntent


if TYPE_CHECKING:
    from backend.app.workflow.state import WorkflowMemoryRecord


_MEMORY_POLICY_VERSION = "memory_query_policy_v1"
_TRUSTED_CONFIDENCE_THRESHOLD = Decimal("0.8000")
_ADVISORY_CONFIDENCE_THRESHOLD = Decimal("0.5000")
_ACTIVITY_DIMENSION = "activity_preferences"
_DINING_DIMENSION = "dining_preferences"
_SUPPORTED_MEMORY_DIMENSIONS = {
    "activity_style": _ACTIVITY_DIMENSION,
    "spouse_lighter_meals": _DINING_DIMENSION,
}
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


class MemoryQueryPolicySummary(BaseModel):
    policy_version: str = _MEMORY_POLICY_VERSION
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


def apply_memory_query_policy(
    intent: LocalLifeIntent,
    signals: IntentParseSignals,
    active_memories: list[WorkflowMemoryRecord],
) -> tuple[LocalLifeIntent, MemoryQueryPolicySummary]:
    now = datetime.now(UTC)
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

    for memory in active_memories:
        if memory.memory_type != "preference":
            continue

        key = memory.key
        dimension = _memory_dimension(key)
        if dimension is None:
            _append_unique(unsupported_memory_keys, key)
            memory_decisions.append(
                MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=_ACTIVITY_DIMENSION,
                    normalized_value=None,
                    confidence=_string_or_none(memory.confidence),
                    tier="weak",
                    expired=False,
                    outcome="unsupported_key",
                )
            )
            continue

        normalized_value = _normalize_memory_value(memory)
        confidence = _parse_confidence(memory.confidence)
        expired = _is_expired(memory.expires_at, now)
        tier = _memory_tier(confidence, expired)
        confidence_text = _string_or_none(memory.confidence)

        if confidence is None or confidence < _TRUSTED_CONFIDENCE_THRESHOLD:
            _append_unique(downgraded_low_confidence_keys, key)
        if expired:
            _append_unique(downgraded_expired_keys, key)

        if normalized_value is None:
            memory_decisions.append(
                MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=dimension,
                    normalized_value=None,
                    confidence=confidence_text,
                    tier=tier,
                    expired=expired,
                    outcome="unrecognized_value",
                )
            )
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
                MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=dimension,
                    normalized_value=normalized_value,
                    confidence=confidence_text,
                    tier=tier,
                    expired=expired,
                    outcome="suppressed_user_override",
                )
            )
            continue

        if tier == "weak":
            memory_decisions.append(
                MemoryGovernanceDecision(
                    memory_key=key,
                    dimension=dimension,
                    normalized_value=normalized_value,
                    confidence=confidence_text,
                    tier=tier,
                    expired=expired,
                    outcome="suppressed_weak_signal",
                )
            )
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
            MemoryGovernanceDecision(
                memory_key=key,
                dimension=dimension,
                normalized_value=normalized_value,
                confidence=confidence_text,
                tier=tier,
                expired=expired,
                outcome="applied_trusted" if tier == "trusted" else "applied_advisory",
            )
        )
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
    )
    return effective_intent, summary


def _memory_dimension(key: str) -> MemoryGovernanceDimension | None:
    return _SUPPORTED_MEMORY_DIMENSIONS.get(key)


def _normalize_memory_value(memory: "WorkflowMemoryRecord") -> str | None:
    if memory.key == "activity_style":
        normalized = _normalize_activity_style(memory.value_json.get("preference"))
        if normalized is None:
            normalized = _normalize_activity_style(memory.text)
        return normalized
    if memory.key == "spouse_lighter_meals":
        normalized = _normalize_lighter_meals(memory.value_json.get("preference"))
        if normalized is None:
            normalized = _normalize_lighter_meals(memory.text)
        return normalized
    return None


def _is_user_override_dimension(dimension: MemoryGovernanceDimension, signals: IntentParseSignals) -> bool:
    if dimension == _ACTIVITY_DIMENSION:
        return signals.activity_preferences
    return signals.dining_preferences


def _memory_tier(confidence: Decimal | None, expired: bool) -> MemoryGovernanceTier:
    if confidence is None:
        return "weak"
    if not expired and confidence >= _TRUSTED_CONFIDENCE_THRESHOLD:
        return "trusted"
    if not expired and confidence >= _ADVISORY_CONFIDENCE_THRESHOLD:
        return "advisory"
    if expired and confidence >= _TRUSTED_CONFIDENCE_THRESHOLD:
        return "advisory"
    return "weak"


def _is_expired(value: Any, now: datetime) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


def _normalize_activity_style(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    for style, fragments in (
        ("citywalk", ("citywalk", "city walk", "城市漫步")),
        ("indoor", ("indoor", "inside", "室内")),
        ("outdoor", ("outdoor", "outside", "户外", "室外")),
    ):
        if any(fragment in normalized for fragment in fragments):
            return style
    return None


def _normalize_lighter_meals(value: Any) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    if any(fragment in normalized for fragment in ("lighter", "light food", "light meals", "清淡")):
        return "lighter_options"
    return None


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _parse_confidence(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
