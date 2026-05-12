from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from backend.app.providers.mock_world.errors import MockWorldError


SUPPORTED_PROFILES = {"family_afternoon": "family_afternoon.json"}
REQUIRED_TOP_LEVEL_KEYS = {
    "profile",
    "location",
    "pois",
    "routes",
    "weather",
    "queues",
    "table_availability",
    "ticket_availability",
    "addons",
}


def load_mock_world(profile: str = "family_afternoon") -> dict[str, Any]:
    fixture_name = SUPPORTED_PROFILES.get(profile)
    if fixture_name is None:
        raise MockWorldError(f"Unsupported Mock World profile {profile!r}.")

    try:
        fixture = files("backend.app.providers.mock_world").joinpath("fixtures", fixture_name)
        world = json.loads(fixture.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MockWorldError(f"Mock World fixture {fixture_name!r} was not found.") from exc
    except json.JSONDecodeError as exc:
        raise MockWorldError(f"Mock World fixture {fixture_name!r} is not valid JSON.") from exc

    _validate_world(world)
    if world["profile"] != profile:
        raise MockWorldError(
            f"Mock World fixture profile {world['profile']!r} does not match requested profile {profile!r}."
        )
    return world


def _validate_world(world: Any) -> None:
    if not isinstance(world, dict):
        raise MockWorldError("Mock World fixture must be a JSON object.")

    missing_keys = sorted(REQUIRED_TOP_LEVEL_KEYS.difference(world))
    if missing_keys:
        raise MockWorldError(f"Mock World fixture is missing required keys: {missing_keys}.")

    if not isinstance(world["pois"], list):
        raise MockWorldError("Mock World fixture field 'pois' must be a list.")

    for key, expected_type in {
        "location": dict,
        "routes": list,
        "weather": dict,
        "queues": dict,
        "table_availability": dict,
        "ticket_availability": dict,
        "addons": list,
    }.items():
        if not isinstance(world[key], expected_type):
            raise MockWorldError(f"Mock World fixture field {key!r} is malformed.")

    seen_poi_ids: set[str] = set()
    for poi in world["pois"]:
        if not isinstance(poi, dict):
            raise MockWorldError("Mock World fixture POIs must be objects.")
        poi_id = poi.get("poi_id")
        if not isinstance(poi_id, str) or not poi_id.strip():
            raise MockWorldError("Mock World fixture POIs require non-empty 'poi_id' values.")
        if poi_id in seen_poi_ids:
            raise MockWorldError(f"Mock World fixture has duplicate POI id {poi_id!r}.")
        seen_poi_ids.add(poi_id)
