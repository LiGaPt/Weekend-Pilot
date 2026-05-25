from __future__ import annotations

from backend.app.planning.errors import IntentParseError
from backend.app.planning.intent_parser import DeterministicIntentParser

FAMILY_AFTERNOON_PROFILE = "family_afternoon"
FRIENDS_GATHERING_PROFILE = "friends_gathering"


def resolve_mock_world_demo_profile(user_input: str) -> str:
    try:
        intent = DeterministicIntentParser().parse(user_input)
    except IntentParseError:
        return FAMILY_AFTERNOON_PROFILE

    if intent.scenario_type == "friends":
        return FRIENDS_GATHERING_PROFILE
    return FAMILY_AFTERNOON_PROFILE
