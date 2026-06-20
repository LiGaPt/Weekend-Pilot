from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel

from backend.app.memory_lifecycle import resolve_memory_lifecycle_state


MEMORY_POLICY_VERSION = "memory_query_policy_v1"
TRUSTED_CONFIDENCE_THRESHOLD = Decimal("0.8000")
ADVISORY_CONFIDENCE_THRESHOLD = Decimal("0.5000")
SUPPORTED_MEMORY_DIMENSIONS = {
    "activity_style": "activity_preferences",
    "spouse_lighter_meals": "dining_preferences",
}
MemoryGovernanceTier = Literal["trusted", "advisory", "weak"]
MemoryGovernanceAuditStatus = Literal["trusted", "advisory", "weak", "unsupported", "not_governable"]
MemoryGovernanceAuditReason = Literal[
    "trusted_memory_applied",
    "low_confidence_downgraded_to_advisory",
    "expired_memory_downgraded_to_advisory",
    "weak_signal_not_applied",
    "unsupported_projected_key",
    "unrecognized_supported_value",
    "non_governable_lifecycle",
]


class MemoryGovernanceAudit(BaseModel):
    policy_version: str = MEMORY_POLICY_VERSION
    normalized_value: str | None
    governable: bool
    expired: bool
    tier: MemoryGovernanceTier | None
    audit_status: MemoryGovernanceAuditStatus
    audit_reason: MemoryGovernanceAuditReason


def classify_memory_governance_audit(
    *,
    memory_type: str,
    key: str,
    value_json: dict[str, Any],
    text: str | None,
    confidence: Any,
    status: str,
    expires_at: datetime | str | None,
    lifecycle_state: str | None = None,
) -> MemoryGovernanceAudit:
    resolved_expires_at = expires_at if isinstance(expires_at, datetime) else _parse_datetime(expires_at)
    lifecycle = lifecycle_state or resolve_memory_lifecycle_state(status, resolved_expires_at)
    normalized_value = normalize_supported_preference_value(key=key, value_json=value_json, text=text)
    expired = lifecycle == "expired"

    if memory_type != "preference" or key not in SUPPORTED_MEMORY_DIMENSIONS:
        return MemoryGovernanceAudit(
            normalized_value=None,
            governable=False,
            expired=False,
            tier=None,
            audit_status="unsupported",
            audit_reason="unsupported_projected_key",
        )

    if lifecycle not in {"active", "expired"}:
        return MemoryGovernanceAudit(
            normalized_value=normalized_value,
            governable=False,
            expired=expired,
            tier=None,
            audit_status="not_governable",
            audit_reason="non_governable_lifecycle",
        )

    tier = memory_tier(confidence, expired)
    if normalized_value is None:
        return MemoryGovernanceAudit(
            normalized_value=None,
            governable=True,
            expired=expired,
            tier=tier,
            audit_status="weak",
            audit_reason="unrecognized_supported_value",
        )

    if tier == "trusted":
        return MemoryGovernanceAudit(
            normalized_value=normalized_value,
            governable=True,
            expired=expired,
            tier=tier,
            audit_status="trusted",
            audit_reason="trusted_memory_applied",
        )
    if tier == "advisory":
        return MemoryGovernanceAudit(
            normalized_value=normalized_value,
            governable=True,
            expired=expired,
            tier=tier,
            audit_status="advisory",
            audit_reason="expired_memory_downgraded_to_advisory" if expired else "low_confidence_downgraded_to_advisory",
        )
    return MemoryGovernanceAudit(
        normalized_value=normalized_value,
        governable=True,
        expired=expired,
        tier=tier,
        audit_status="weak",
        audit_reason="weak_signal_not_applied",
    )


def normalize_supported_preference_value(*, key: str, value_json: dict[str, Any], text: str | None) -> str | None:
    value_preference = value_json.get("preference") if isinstance(value_json, dict) else None
    normalized_from_value = _normalize_memory_value(key, value_preference)
    normalized_from_text = _normalize_memory_value(key, text)
    if normalized_from_value and normalized_from_text and normalized_from_value != normalized_from_text:
        raise ValueError("Memory value_json and text normalize to conflicting values.")
    return normalized_from_value or normalized_from_text


def memory_dimension(key: str) -> str | None:
    return SUPPORTED_MEMORY_DIMENSIONS.get(key)


def memory_tier(confidence: Any, expired: bool) -> MemoryGovernanceTier:
    parsed_confidence = parse_confidence(confidence)
    if parsed_confidence is None:
        return "weak"
    if not expired and parsed_confidence >= TRUSTED_CONFIDENCE_THRESHOLD:
        return "trusted"
    if not expired and parsed_confidence >= ADVISORY_CONFIDENCE_THRESHOLD:
        return "advisory"
    if expired and parsed_confidence >= TRUSTED_CONFIDENCE_THRESHOLD:
        return "advisory"
    return "weak"


def parse_confidence(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def memory_is_expired(*, lifecycle_state: str | None, expires_at: datetime | str | None, now: datetime) -> bool:
    if lifecycle_state == "expired":
        return True
    if lifecycle_state == "active":
        return False
    return is_expired(expires_at, now)


def is_expired(value: datetime | str | None, now: datetime) -> bool:
    if isinstance(value, datetime):
        expires_at = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return expires_at <= now
    if not isinstance(value, str) or not value:
        return False
    expires_at = _parse_datetime(value)
    if expires_at is None:
        return True
    return expires_at <= now


def _parse_datetime(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _normalize_memory_value(key: str, value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if key == "activity_style":
        if "citywalk" in normalized or "city walk" in normalized or "鍩庡競婕" in normalized:
            return "citywalk"
        if "indoor" in normalized or "inside" in normalized or "瀹ゅ唴" in normalized:
            return "indoor"
        if "outdoor" in normalized or "outside" in normalized or "鎴峰" in normalized or "瀹ゅ" in normalized:
            return "outdoor"
        return None
    if key == "spouse_lighter_meals":
        if any(fragment in normalized for fragment in ("lighter_options", "lighter", "light food", "light meals", "娓呮贰")):
            return "lighter_options"
        return None
    return None
