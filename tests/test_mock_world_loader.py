from __future__ import annotations

import pytest

from backend.app.providers.mock_world.errors import MockWorldError
from backend.app.providers.mock_world.loader import _validate_world, load_mock_world


SUPPORTED_PROFILES = (
    "family_afternoon",
    "solo_afternoon",
    "couple_afternoon",
    "friends_gathering",
    "rainy_day_fallback",
    "budget_lite",
    "elder_afternoon",
)
MINIMUM_CATEGORY_COUNTS = {
    "family_afternoon": {"activity": 5, "dining": 5},
    "solo_afternoon": {"activity": 4, "dining": 4},
    "couple_afternoon": {"activity": 4, "dining": 4},
    "friends_gathering": {"activity": 4, "dining": 4},
    "rainy_day_fallback": {"activity": 4, "dining": 4},
    "budget_lite": {"activity": 4, "dining": 4},
    "elder_afternoon": {"activity": 4, "dining": 4},
}


def test_default_fixture_loads_family_afternoon_profile() -> None:
    world = load_mock_world()

    assert world["profile"] == "family_afternoon"
    assert isinstance(world["location"]["city"], str)
    assert world["location"]["city"]
    assert isinstance(world["location"]["area"], str)
    assert world["location"]["area"]


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES[1:])
def test_explicit_fixture_loads_supported_profile(profile: str) -> None:
    world = load_mock_world(profile)

    assert world["profile"] == profile
    assert isinstance(world["location"]["city"], str)
    assert world["location"]["city"]
    assert isinstance(world["location"]["area"], str)
    assert world["location"]["area"]


def test_default_fixture_has_required_top_level_keys() -> None:
    world = load_mock_world()

    assert {
        "profile",
        "location",
        "pois",
        "routes",
        "weather",
        "queues",
        "table_availability",
        "ticket_availability",
        "addons",
    }.issubset(world)


def test_default_fixture_poi_ids_are_unique() -> None:
    world = load_mock_world()

    poi_ids = [poi["poi_id"] for poi in world["pois"]]

    assert len(poi_ids) == len(set(poi_ids))


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_supported_profiles_expose_minimum_activity_and_dining_density(profile: str) -> None:
    world = load_mock_world(profile)
    counts = {
        "activity": sum(1 for poi in world["pois"] if poi["category"] == "activity"),
        "dining": sum(1 for poi in world["pois"] if poi["category"] == "dining"),
    }

    assert counts == MINIMUM_CATEGORY_COUNTS[profile]


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_supported_profiles_keep_unique_poi_ids(profile: str) -> None:
    world = load_mock_world(profile)

    poi_ids = [poi["poi_id"] for poi in world["pois"]]

    assert len(poi_ids) == len(set(poi_ids))


def test_unsupported_profile_raises_mock_world_error() -> None:
    with pytest.raises(MockWorldError, match="Unsupported Mock World profile"):
        load_mock_world("unknown_profile")


def test_malformed_fixture_missing_required_key_raises_mock_world_error() -> None:
    world = load_mock_world()
    del world["pois"]

    with pytest.raises(MockWorldError, match="missing required keys"):
        _validate_world(world)


def test_malformed_fixture_duplicate_poi_id_raises_mock_world_error() -> None:
    world = load_mock_world()
    world["pois"].append(dict(world["pois"][0]))

    with pytest.raises(MockWorldError, match="duplicate POI id"):
        _validate_world(world)
