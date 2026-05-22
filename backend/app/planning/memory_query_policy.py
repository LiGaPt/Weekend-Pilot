from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from backend.app.planning.schemas import IntentParseSignals, LocalLifeIntent


if TYPE_CHECKING:
    from backend.app.workflow.state import WorkflowMemoryRecord


_MEMORY_POLICY_VERSION = "memory_query_policy_v0"
_CONFIDENCE_THRESHOLD = Decimal("0.8000")


class MemoryQueryPolicySummary(BaseModel):
    policy_version: str = _MEMORY_POLICY_VERSION
    applied_memory_keys: list[str] = Field(default_factory=list)
    ignored_low_confidence_keys: list[str] = Field(default_factory=list)
    user_override_dimensions: list[str] = Field(default_factory=list)
    unsupported_memory_keys: list[str] = Field(default_factory=list)
    effective_activity_preferences: list[str] = Field(default_factory=list)
    effective_dining_preferences: list[str] = Field(default_factory=list)


def apply_memory_query_policy(
    intent: LocalLifeIntent,
    signals: IntentParseSignals,
    active_memories: list[WorkflowMemoryRecord],
) -> tuple[LocalLifeIntent, MemoryQueryPolicySummary]:
    effective_activity_preferences = list(intent.activity_preferences)
    effective_dining_preferences = list(intent.dining_preferences)
    applied_memory_keys: list[str] = []
    ignored_low_confidence_keys: list[str] = []
    user_override_dimensions: list[str] = []
    unsupported_memory_keys: list[str] = []

    for memory in active_memories:
        if memory.memory_type != "preference":
            continue

        key = memory.key
        if key not in {"activity_style", "spouse_lighter_meals"}:
            _append_unique(unsupported_memory_keys, key)
            continue

        if key == "activity_style" and signals.activity_preferences:
            _append_unique(user_override_dimensions, "activity_preferences")
        if key == "spouse_lighter_meals" and signals.dining_preferences:
            _append_unique(user_override_dimensions, "dining_preferences")

        confidence = _parse_confidence(memory.confidence)
        if confidence is None or confidence < _CONFIDENCE_THRESHOLD:
            _append_unique(ignored_low_confidence_keys, key)
            continue

        if key == "activity_style":
            if signals.activity_preferences:
                continue
            normalized = _normalize_activity_style(memory.value_json.get("preference"))
            if normalized is None:
                normalized = _normalize_activity_style(memory.text)
            if normalized is None:
                continue
            if normalized not in effective_activity_preferences:
                effective_activity_preferences.append(normalized)
            _append_unique(applied_memory_keys, key)
            continue

        if signals.dining_preferences:
            continue
        normalized_dining = _normalize_lighter_meals(memory.value_json.get("preference"))
        if normalized_dining is None:
            normalized_dining = _normalize_lighter_meals(memory.text)
        if normalized_dining is None:
            continue
        if normalized_dining not in effective_dining_preferences:
            effective_dining_preferences.append(normalized_dining)
        _append_unique(applied_memory_keys, key)

    effective_intent = intent.model_copy(
        update={
            "activity_preferences": effective_activity_preferences,
            "dining_preferences": effective_dining_preferences,
        }
    )
    summary = MemoryQueryPolicySummary(
        applied_memory_keys=applied_memory_keys,
        ignored_low_confidence_keys=ignored_low_confidence_keys,
        user_override_dimensions=user_override_dimensions,
        unsupported_memory_keys=unsupported_memory_keys,
        effective_activity_preferences=effective_activity_preferences,
        effective_dining_preferences=effective_dining_preferences,
    )
    return effective_intent, summary


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
