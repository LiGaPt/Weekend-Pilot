from __future__ import annotations

from backend.app.demo.world_profile import (
    FAMILY_AFTERNOON_PROFILE,
    FRIENDS_GATHERING_PROFILE,
    resolve_mock_world_demo_profile,
)


FRIENDS_PROMPT = (
    "This afternoon I want to hang out with friends nearby for a few hours. "
    "Start with an outdoor walk and chatting, then find a casual dinner place that's good for sharing. "
    "Not too far."
)
FAMILY_PROMPT = (
    "This afternoon I want to go out with my wife and child for a few hours. "
    "Not too far. My child is 5, and my wife is trying to eat lighter."
)
VAGUE_PROMPT = "Plan something relaxed nearby this afternoon."
OUTDOOR_FRIENDS_PROMPT = (
    "This afternoon a few friends want to stay nearby, walk outside for a while, and then have dinner together."
)


def test_resolve_mock_world_demo_profile_routes_friends_prompt_to_friends_gathering() -> None:
    assert resolve_mock_world_demo_profile(FRIENDS_PROMPT) == FRIENDS_GATHERING_PROFILE


def test_resolve_mock_world_demo_profile_keeps_family_prompt_on_family_afternoon() -> None:
    assert resolve_mock_world_demo_profile(FAMILY_PROMPT) == FAMILY_AFTERNOON_PROFILE


def test_resolve_mock_world_demo_profile_falls_back_to_family_for_vague_prompt() -> None:
    assert resolve_mock_world_demo_profile(VAGUE_PROMPT) == FAMILY_AFTERNOON_PROFILE


def test_resolve_mock_world_demo_profile_routes_outdoor_friends_prompt_without_extra_rules() -> None:
    assert resolve_mock_world_demo_profile(OUTDOOR_FRIENDS_PROMPT) == FRIENDS_GATHERING_PROFILE
