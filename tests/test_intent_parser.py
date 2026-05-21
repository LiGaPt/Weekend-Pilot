from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.planning import DeterministicIntentParser, IntentParseError


ENGLISH_MVP_REQUEST = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
)

CHINESE_MVP_REQUEST = "今天下午想带老婆和5岁孩子出去玩几个小时，别太远，吃清淡点。"


def test_parser_extracts_english_mvp_family_request() -> None:
    parser = DeterministicIntentParser()

    intent = parser.parse(
        ENGLISH_MVP_REQUEST,
        reference_now=datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc),
    )

    assert intent.raw_text == ENGLISH_MVP_REQUEST
    assert intent.scenario_type == "family"
    assert intent.participants.adults == 2
    assert intent.participants.children_ages == [5]
    assert intent.time_window.label == "this_afternoon"
    assert intent.time_window.start_at == datetime(2026, 5, 12, 13, 30, tzinfo=timezone.utc)
    assert intent.time_window.end_at == datetime(2026, 5, 12, 18, 30, tzinfo=timezone.utc)
    assert intent.time_window.duration_hours_min == 4
    assert intent.time_window.duration_hours_max == 6
    assert intent.constraints.max_distance_km == 8
    assert intent.constraints.child_friendly is True
    assert "lighter_options" in intent.dining_preferences
    assert "child_friendly" in intent.activity_preferences
    assert intent.origin_text is None
    assert intent.parser_version


def test_parser_extracts_chinese_mvp_family_request() -> None:
    parser = DeterministicIntentParser()

    intent = parser.parse(CHINESE_MVP_REQUEST)

    assert intent.scenario_type == "family"
    assert intent.participants.adults == 2
    assert intent.participants.children_ages == [5]
    assert intent.time_window.label == "this_afternoon"
    assert intent.time_window.start_at is None
    assert intent.time_window.end_at is None
    assert intent.time_window.duration_hours_min == 4
    assert intent.time_window.duration_hours_max == 6
    assert intent.constraints.max_distance_km == 8
    assert intent.constraints.child_friendly is True
    assert "lighter_options" in intent.dining_preferences


def test_parser_rejects_empty_text() -> None:
    parser = DeterministicIntentParser()

    with pytest.raises(IntentParseError, match="empty"):
        parser.parse("   ")


def test_parser_keeps_vague_non_empty_input_with_conservative_defaults() -> None:
    parser = DeterministicIntentParser()

    intent = parser.parse("Maybe something fun later")

    assert intent.scenario_type == "unknown"
    assert intent.participants.adults == 1
    assert intent.participants.children_ages == []
    assert intent.time_window.label is None
    assert intent.time_window.duration_hours_min is None
    assert intent.time_window.duration_hours_max is None
    assert intent.constraints.max_distance_km is None
    assert intent.constraints.child_friendly is False
    assert intent.activity_preferences == []
    assert intent.dining_preferences == []


def test_parser_parse_with_signals_marks_supported_explicit_fields() -> None:
    parser = DeterministicIntentParser()

    parsed = parser.parse_with_signals(ENGLISH_MVP_REQUEST)

    assert parsed.intent.scenario_type == "family"
    assert parsed.signals.scenario_or_participants is True
    assert parsed.signals.time_window is True
    assert parsed.signals.max_distance_km is True
    assert parsed.signals.dining_preferences is True
