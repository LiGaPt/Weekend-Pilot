from __future__ import annotations

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
) -> WorkflowMemoryRecord:
    return WorkflowMemoryRecord(
        memory_id=uuid4(),
        memory_type=memory_type,
        key=key,
        value_json={"preference": preference},
        text=text,
        confidence=confidence,
        status="active",
    )


def test_memory_query_policy_applies_high_confidence_dining_preference() -> None:
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
    assert summary.effective_dining_preferences == ["lighter_options"]


def test_memory_query_policy_applies_high_confidence_activity_style() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(),
        IntentParseSignals(),
        [
            _memory(
                key="activity_style",
                preference="indoor activities",
                confidence="0.8000",
                text="The family usually prefers indoor plans.",
            )
        ],
    )

    assert effective_intent.activity_preferences == ["indoor"]
    assert summary.applied_memory_keys == ["activity_style"]
    assert summary.effective_activity_preferences == ["indoor"]


def test_memory_query_policy_ignores_low_confidence_memory() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(),
        IntentParseSignals(),
        [
            _memory(
                key="activity_style",
                preference="outdoor citywalk",
                confidence="0.7999",
                text="The family often likes citywalk plans.",
            )
        ],
    )

    assert effective_intent.activity_preferences == []
    assert summary.applied_memory_keys == []
    assert summary.ignored_low_confidence_keys == ["activity_style"]


def test_memory_query_policy_explicit_user_override_beats_memory() -> None:
    from backend.app.planning import apply_memory_query_policy

    effective_intent, summary = apply_memory_query_policy(
        _intent(activity_preferences=["indoor"]),
        IntentParseSignals(activity_preferences=True),
        [
            _memory(
                key="activity_style",
                preference="citywalk",
                confidence="1.0",
                text="The family usually wants citywalk plans.",
            )
        ],
    )

    assert effective_intent.activity_preferences == ["indoor"]
    assert summary.applied_memory_keys == []
    assert summary.user_override_dimensions == ["activity_preferences"]


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
    serialized = json.dumps(summary.model_dump(mode="json"), sort_keys=True)
    assert "text" not in serialized
    assert "value_json" not in serialized
    assert "memory_id" not in serialized
    assert "trace_id" not in serialized
