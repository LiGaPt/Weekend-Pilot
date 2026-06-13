from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal


MemoryLifecycleState = Literal["active", "expired", "disabled", "ignored", "candidate"]
PersistedMemoryStatus = Literal["active", "expired", "disabled", "ignored", "candidate", "archived"]

_LEGACY_STATUS_ALIASES: dict[str, MemoryLifecycleState] = {
    "archived": "ignored",
}
_SUPPORTED_PERSISTED_STATUSES = {"active", "expired", "disabled", "ignored", "candidate"}


def normalize_memory_status(status: str) -> MemoryLifecycleState:
    if status in _SUPPORTED_PERSISTED_STATUSES:
        return status  # type: ignore[return-value]
    if status in _LEGACY_STATUS_ALIASES:
        return _LEGACY_STATUS_ALIASES[status]
    raise ValueError(f"Unsupported memory status: {status!r}")


def resolve_memory_lifecycle_state(
    status: str,
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> MemoryLifecycleState:
    normalized_status = normalize_memory_status(status)
    if normalized_status != "active":
        return normalized_status

    resolved_now = now or datetime.now(UTC)
    resolved_expires_at = _as_utc(expires_at)
    if resolved_expires_at is not None and resolved_expires_at <= resolved_now:
        return "expired"
    return "active"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
