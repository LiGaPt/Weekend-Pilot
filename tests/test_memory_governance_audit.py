from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.app.memory_governance_audit import classify_memory_governance_audit


def test_memory_governance_audit_classifies_trusted_supported_memory() -> None:
    audit = classify_memory_governance_audit(
        memory_type="preference",
        key="spouse_lighter_meals",
        value_json={"preference": "lighter_options"},
        text=None,
        confidence=Decimal("0.9000"),
        status="active",
        expires_at=None,
        lifecycle_state="active",
    )

    assert audit.model_dump(mode="json") == {
        "policy_version": "memory_query_policy_v1",
        "normalized_value": "lighter_options",
        "governable": True,
        "expired": False,
        "tier": "trusted",
        "audit_status": "trusted",
        "audit_reason": "trusted_memory_applied",
    }


def test_memory_governance_audit_classifies_low_confidence_memory_as_advisory() -> None:
    audit = classify_memory_governance_audit(
        memory_type="preference",
        key="activity_style",
        value_json={"preference": "indoor"},
        text=None,
        confidence=Decimal("0.7000"),
        status="active",
        expires_at=None,
        lifecycle_state="active",
    )

    assert audit.tier == "advisory"
    assert audit.audit_status == "advisory"
    assert audit.audit_reason == "low_confidence_downgraded_to_advisory"


def test_memory_governance_audit_classifies_expired_high_confidence_memory_as_advisory() -> None:
    audit = classify_memory_governance_audit(
        memory_type="preference",
        key="activity_style",
        value_json={"preference": "indoor"},
        text=None,
        confidence=Decimal("0.9000"),
        status="active",
        expires_at=datetime.now(UTC) - timedelta(days=1),
        lifecycle_state="expired",
    )

    assert audit.governable is True
    assert audit.expired is True
    assert audit.tier == "advisory"
    assert audit.audit_status == "advisory"
    assert audit.audit_reason == "expired_memory_downgraded_to_advisory"


def test_memory_governance_audit_classifies_weak_memory() -> None:
    audit = classify_memory_governance_audit(
        memory_type="preference",
        key="activity_style",
        value_json={"preference": "citywalk"},
        text=None,
        confidence=Decimal("0.4999"),
        status="active",
        expires_at=None,
        lifecycle_state="active",
    )

    assert audit.tier == "weak"
    assert audit.audit_status == "weak"
    assert audit.audit_reason == "weak_signal_not_applied"


def test_memory_governance_audit_marks_unsupported_key() -> None:
    audit = classify_memory_governance_audit(
        memory_type="preference",
        key="preferred_neighborhood",
        value_json={"preference": "xuhui"},
        text=None,
        confidence=Decimal("1.0"),
        status="active",
        expires_at=None,
        lifecycle_state="active",
    )

    assert audit.governable is False
    assert audit.tier is None
    assert audit.audit_status == "unsupported"
    assert audit.audit_reason == "unsupported_projected_key"


def test_memory_governance_audit_marks_non_governable_lifecycle() -> None:
    audit = classify_memory_governance_audit(
        memory_type="preference",
        key="activity_style",
        value_json={"preference": "indoor"},
        text=None,
        confidence=Decimal("1.0"),
        status="candidate",
        expires_at=None,
        lifecycle_state="candidate",
    )

    assert audit.governable is False
    assert audit.tier is None
    assert audit.audit_status == "not_governable"
    assert audit.audit_reason == "non_governable_lifecycle"
