from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


def test_memory_lifecycle_resolves_active_without_expiry() -> None:
    from backend.app.memory_lifecycle import resolve_memory_lifecycle_state

    assert resolve_memory_lifecycle_state("active", None) == "active"


def test_memory_lifecycle_resolves_active_with_future_expiry() -> None:
    from backend.app.memory_lifecycle import resolve_memory_lifecycle_state

    assert (
        resolve_memory_lifecycle_state(
            "active",
            datetime.now(UTC) + timedelta(days=1),
        )
        == "active"
    )


def test_memory_lifecycle_resolves_active_with_past_expiry_as_expired() -> None:
    from backend.app.memory_lifecycle import resolve_memory_lifecycle_state

    assert (
        resolve_memory_lifecycle_state(
            "active",
            datetime.now(UTC) - timedelta(days=1),
        )
        == "expired"
    )


def test_memory_lifecycle_resolves_explicit_expired_without_timestamp() -> None:
    from backend.app.memory_lifecycle import resolve_memory_lifecycle_state

    assert resolve_memory_lifecycle_state("expired", None) == "expired"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("disabled", "disabled"),
        ("ignored", "ignored"),
        ("candidate", "candidate"),
        ("archived", "ignored"),
    ],
)
def test_memory_lifecycle_resolves_non_governable_and_legacy_states(
    status: str,
    expected: str,
) -> None:
    from backend.app.memory_lifecycle import resolve_memory_lifecycle_state

    assert resolve_memory_lifecycle_state(status, None) == expected


def test_memory_lifecycle_treats_naive_datetime_as_utc() -> None:
    from backend.app.memory_lifecycle import resolve_memory_lifecycle_state

    assert (
        resolve_memory_lifecycle_state(
            "active",
            datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
        )
        == "expired"
    )


def test_memory_lifecycle_rejects_unknown_status() -> None:
    from backend.app.memory_lifecycle import normalize_memory_status

    with pytest.raises(ValueError, match="Unsupported memory status"):
        normalize_memory_status("paused")
