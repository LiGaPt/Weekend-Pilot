from __future__ import annotations

from collections.abc import Sequence

from backend.app.planning import DeterministicIntentParser, LocalLifeIntent


def build_follow_up_intent(
    user_turn_texts: Sequence[str],
    parser: DeterministicIntentParser | None = None,
) -> LocalLifeIntent:
    parser = parser or DeterministicIntentParser()
    normalized_turns = [text.strip() for text in user_turn_texts if isinstance(text, str) and text.strip()]
    if not normalized_turns:
        raise ValueError("At least one non-empty user turn is required.")

    parsed_turns = [parser.parse_with_signals(text) for text in normalized_turns]
    merged_intent = parsed_turns[0].intent.model_copy(deep=True)

    for parsed_turn in parsed_turns[1:]:
        next_intent = parsed_turn.intent
        signals = parsed_turn.signals

        if signals.scenario_or_participants:
            merged_intent.scenario_type = next_intent.scenario_type
            merged_intent.participants = next_intent.participants.model_copy(deep=True)
            merged_intent.constraints.child_friendly = next_intent.constraints.child_friendly
            merged_intent.activity_preferences = list(next_intent.activity_preferences)

        if signals.time_window:
            merged_intent.time_window = next_intent.time_window.model_copy(deep=True)

        if signals.max_distance_km:
            merged_intent.constraints.max_distance_km = next_intent.constraints.max_distance_km

        if signals.dining_preferences:
            merged_intent.dining_preferences = list(next_intent.dining_preferences)

    merged_intent.raw_text = "\n".join(parsed_turn.intent.raw_text for parsed_turn in parsed_turns)
    merged_intent.origin_text = None
    merged_intent.parser_version = parser.parser_version
    return merged_intent
