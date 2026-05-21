from __future__ import annotations

from backend.app.demo.replan import build_follow_up_intent


BASE_FAMILY_REQUEST = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
)


def test_follow_up_intent_uses_latest_explicit_scenario_and_participant_bundle() -> None:
    intent = build_follow_up_intent(
        [
            BASE_FAMILY_REQUEST,
            "Keep it nearby, but make it a solo outing this time.",
        ]
    )

    assert intent.scenario_type == "solo"
    assert intent.participants.adults == 1
    assert intent.participants.children_ages == []
    assert intent.constraints.child_friendly is False
    assert intent.activity_preferences == []
    assert intent.constraints.max_distance_km == 8
    assert intent.dining_preferences == ["lighter_options"]
    assert intent.raw_text == (
        BASE_FAMILY_REQUEST + "\n" + "Keep it nearby, but make it a solo outing this time."
    )


def test_follow_up_intent_preserves_supported_fields_when_follow_up_is_vague() -> None:
    intent = build_follow_up_intent(
        [
            BASE_FAMILY_REQUEST,
            "Maybe make it fun.",
        ]
    )

    assert intent.scenario_type == "family"
    assert intent.participants.adults == 2
    assert intent.participants.children_ages == [5]
    assert intent.time_window.label == "this_afternoon"
    assert intent.time_window.duration_hours_min == 4
    assert intent.time_window.duration_hours_max == 6
    assert intent.constraints.max_distance_km == 8
    assert intent.dining_preferences == ["lighter_options"]


def test_follow_up_intent_uses_latest_explicit_dining_preference_signal() -> None:
    intent = build_follow_up_intent(
        [
            "Plan a nearby solo afternoon.",
            "Let's eat lighter.",
        ]
    )

    assert intent.scenario_type == "solo"
    assert intent.participants.adults == 1
    assert intent.constraints.max_distance_km == 8
    assert intent.dining_preferences == ["lighter_options"]
