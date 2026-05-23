from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import uuid4

from backend.app.planning import (
    IntentParseSignals,
    LocalLifeIntent,
    ParticipantProfile,
    TimeWindow,
)
from backend.app.workflow.state import WorkflowMemoryRecord


def _intent(
    *,
    activity_preferences: list[str] | None = None,
    dining_preferences: list[str] | None = None,
) -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="Maybe something fun later",
        participants=ParticipantProfile(),
        time_window=TimeWindow(),
        activity_preferences=activity_preferences or [],
        dining_preferences=dining_preferences or [],
        parser_version="test-parser",
    )


def _memory(
    *,
    key: str,
    preference: str,
    confidence: str,
    memory_type: str = "preference",
    text: str | None = None,
    expires_at: str | None = None,
) -> WorkflowMemoryRecord:
    return WorkflowMemoryRecord(
        memory_id=uuid4(),
        memory_type=memory_type,
        key=key,
        value_json={"preference": preference},
        text=text,
        confidence=confidence,
        expires_at=expires_at,
        status="active",
    )


def test_memory_query_policy_applies_trusted_dining_preference() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(),
        IntentParseSignals(),
        [
            _memory(
                key="spouse_lighter_meals",
                preference="lighter meals",
                confidence="1.0",
                text="The spouse prefers lighter meals.",
            )
        ],
    )

    assert effective_intent.dining_preferences == ["lighter_options"]
    assert summary.applied_memory_keys == ["spouse_lighter_meals"]
    assert summary.advisory_memory_keys == []
    assert [outcome.model_dump(mode="json") for outcome in summary.dimension_outcomes] == [
        {
            "dimension": "dining_preferences",
            "winner_source": "memory",
            "winner_memory_key": "spouse_lighter_meals",
            "winner_tier": "trusted",
            "effective_values": ["lighter_options"],
            "suppressed_memory_keys": [],
        }
    ]
    assert [decision.model_dump(mode="json") for decision in summary.memory_decisions] == [
        {
            "memory_key": "spouse_lighter_meals",
            "dimension": "dining_preferences",
            "normalized_value": "lighter_options",
            "confidence": "1.0",
            "tier": "trusted",
            "expired": False,
            "outcome": "applied_trusted",
        }
    ]
    assert summary.effective_dining_preferences == ["lighter_options"]


def test_memory_query_policy_applies_advisory_dining_preference_when_user_is_vague() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(),
        IntentParseSignals(),
        [
            _memory(
                key="spouse_lighter_meals",
                preference="lighter meals",
                confidence="0.7000",
                text="The spouse often prefers lighter meals.",
            )
        ],
    )

    assert effective_intent.dining_preferences == ["lighter_options"]
    assert summary.applied_memory_keys == ["spouse_lighter_meals"]
    assert summary.advisory_memory_keys == ["spouse_lighter_meals"]
    assert summary.downgraded_low_confidence_keys == ["spouse_lighter_meals"]
    assert summary.memory_decisions[0].tier == "advisory"
    assert summary.memory_decisions[0].outcome == "applied_advisory"
    assert summary.dimension_outcomes[0].winner_tier == "advisory"


def test_memory_query_policy_applies_expired_high_confidence_activity_as_advisory() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(),
        IntentParseSignals(),
        [
            _memory(
                key="activity_style",
                preference="indoor activities",
                confidence="1.0",
                text="The family recently preferred indoor plans.",
                expires_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC).isoformat(),
            )
        ],
    )

    assert effective_intent.activity_preferences == ["indoor"]
    assert summary.applied_memory_keys == ["activity_style"]
    assert summary.advisory_memory_keys == ["activity_style"]
    assert summary.downgraded_expired_keys == ["activity_style"]
    assert summary.memory_decisions[0].expired is True
    assert summary.memory_decisions[0].tier == "advisory"
    assert summary.memory_decisions[0].outcome == "applied_advisory"


def test_memory_query_policy_suppresses_weak_memory_without_mutating_intent() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(),
        IntentParseSignals(),
        [
            _memory(
                key="activity_style",
                preference="citywalk",
                confidence="0.4999",
                text="The family once wanted citywalk plans.",
            )
        ],
    )

    assert effective_intent.activity_preferences == []
    assert summary.applied_memory_keys == []
    assert summary.advisory_memory_keys == []
    assert summary.downgraded_low_confidence_keys == ["activity_style"]
    assert summary.memory_decisions[0].tier == "weak"
    assert summary.memory_decisions[0].outcome == "suppressed_weak_signal"
    assert summary.dimension_outcomes == []


def test_memory_query_policy_explicit_user_override_beats_memory_for_both_dimensions() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(activity_preferences=["indoor"], dining_preferences=["lighter_options"]),
        IntentParseSignals(activity_preferences=True, dining_preferences=True),
        [
            _memory(
                key="activity_style",
                preference="citywalk",
                confidence="1.0",
                text="The family usually wants citywalk plans.",
            ),
            _memory(
                key="spouse_lighter_meals",
                preference="lighter meals",
                confidence="1.0",
                text="The spouse prefers lighter meals.",
            ),
        ],
    )

    assert effective_intent.activity_preferences == ["indoor"]
    assert effective_intent.dining_preferences == ["lighter_options"]
    assert summary.user_override_dimensions == ["activity_preferences", "dining_preferences"]
    assert [outcome.model_dump(mode="json") for outcome in summary.dimension_outcomes] == [
        {
            "dimension": "activity_preferences",
            "winner_source": "user_input",
            "winner_memory_key": None,
            "winner_tier": None,
            "effective_values": ["indoor"],
            "suppressed_memory_keys": ["activity_style"],
        },
        {
            "dimension": "dining_preferences",
            "winner_source": "user_input",
            "winner_memory_key": None,
            "winner_tier": None,
            "effective_values": ["lighter_options"],
            "suppressed_memory_keys": ["spouse_lighter_meals"],
        },
    ]
    assert [decision.outcome for decision in summary.memory_decisions] == [
        "suppressed_user_override",
        "suppressed_user_override",
    ]


def test_memory_query_policy_records_unsupported_keys_and_sanitizes_summary() -> None:
    from backend.app.planning import apply_memory_query_policy

    _, summary = apply_memory_query_policy(
        _intent(dining_preferences=["lighter_options"]),
        IntentParseSignals(dining_preferences=True),
        [
            _memory(
                key="preferred_neighborhood",
                preference="Xuhui",
                confidence="1.0",
                text="The user likes Xuhui.",
            )
        ],
    )

    assert summary.unsupported_memory_keys == ["preferred_neighborhood"]
    assert [decision.model_dump(mode="json") for decision in summary.memory_decisions] == [
        {
            "memory_key": "preferred_neighborhood",
            "dimension": "activity_preferences",
            "normalized_value": None,
            "confidence": "1.0",
            "tier": "weak",
            "expired": False,
            "outcome": "unsupported_key",
        }
    ]
    serialized = json.dumps(summary.model_dump(mode="json"), sort_keys=True)
    assert "text" not in serialized
    assert "value_json" not in serialized
    assert "memory_id" not in serialized
    assert "trace_id" not in serialized
