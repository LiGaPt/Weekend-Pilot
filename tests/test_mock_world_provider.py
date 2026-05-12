from __future__ import annotations

from typing import Any

import pytest

from backend.app.providers.mock_world import MockWorldProvider, build_mock_world_registry
from backend.app.providers.mock_world.errors import MockWorldError


def test_provider_name_is_mock_world() -> None:
    provider = MockWorldProvider()

    assert provider.name == "mock_world"


def test_search_poi_returns_deterministic_activity_results() -> None:
    provider = MockWorldProvider()

    result = provider.invoke("search_poi", {"category": "activity"})

    assert [poi["poi_id"] for poi in result["results"]] == [
        "activity_museum_001",
        "activity_playground_001",
        "activity_walk_001",
    ]
    assert all(poi["category"] == "activity" for poi in result["results"])


def test_search_poi_filters_dining_category() -> None:
    provider = MockWorldProvider()

    result = provider.invoke("search_poi", {"category": "dining", "limit": 2})

    assert [poi["poi_id"] for poi in result["results"]] == [
        "restaurant_light_001",
        "restaurant_family_001",
    ]
    assert all(poi["category"] == "dining" for poi in result["results"])


def test_search_poi_filters_query_and_tags() -> None:
    provider = MockWorldProvider()

    result = provider.invoke("search_poi", {"query": "museum", "tags": ["child_friendly"]})

    assert [poi["poi_id"] for poi in result["results"]] == ["activity_museum_001"]


def test_get_poi_detail_returns_known_poi() -> None:
    provider = MockWorldProvider()

    result = provider.invoke("get_poi_detail", {"poi_id": "restaurant_light_001"})

    assert result["poi"]["poi_id"] == "restaurant_light_001"
    assert result["poi"]["category"] == "dining"
    assert "lighter_options" in result["poi"]["tags"]


def test_check_route_returns_deterministic_distance_and_duration() -> None:
    provider = MockWorldProvider()

    result = provider.invoke(
        "check_route",
        {
            "origin_id": "activity_museum_001",
            "destination_id": "restaurant_light_001",
        },
    )

    assert result["route"]["origin_id"] == "activity_museum_001"
    assert result["route"]["destination_id"] == "restaurant_light_001"
    assert result["route"]["mode"] == "walking"
    assert result["route"]["distance_meters"] == 850
    assert result["route"]["duration_minutes"] == 12


def test_check_opening_hours_returns_open_closed_structure() -> None:
    provider = MockWorldProvider()

    result = provider.invoke("check_opening_hours", {"poi_id": "activity_museum_001"})

    assert result["opening_hours"] == {
        "poi_id": "activity_museum_001",
        "is_open": True,
        "windows": [{"start": "13:00", "end": "17:30"}],
        "last_entry": "16:45",
    }


def test_check_weather_returns_deterministic_weather() -> None:
    provider = MockWorldProvider()

    result = provider.invoke("check_weather", {"location": "Xuhui", "date": "2026-05-16"})

    assert result["weather"] == {
        "location": "Xuhui",
        "date": "2026-05-16",
        "condition": "cloudy",
        "temperature_c": 23,
        "precipitation_chance": 0.15,
        "advisory": "Comfortable for family outdoor walking.",
    }


def test_queue_table_and_ticket_availability_return_expected_structures() -> None:
    provider = MockWorldProvider()

    queue = provider.invoke("check_queue", {"poi_id": "restaurant_light_001"})
    table = provider.invoke(
        "check_table_availability",
        {"restaurant_id": "restaurant_light_001", "party_size": 3, "time": "18:00"},
    )
    ticket = provider.invoke(
        "check_ticket_availability",
        {"poi_id": "activity_museum_001", "quantity": 3, "time": "14:00"},
    )

    assert queue["queue"]["queue_id"] == "queue_restaurant_light_001"
    assert queue["queue"]["wait_minutes"] == 10
    assert table["table_availability"]["available"] is True
    assert table["table_availability"]["time_slots"] == ["17:30", "18:00", "18:30"]
    assert ticket["ticket_availability"]["available"] is True
    assert ticket["ticket_availability"]["remaining"] == 42


@pytest.mark.parametrize(
    ("tool_name", "payload", "confirmation_id"),
    [
        (
            "join_queue",
            {"queue_id": "queue_restaurant_light_001", "party_size": 3},
            "mock-confirmation-join_queue-queue_restaurant_light_001",
        ),
        (
            "reserve_restaurant",
            {
                "restaurant_id": "restaurant_light_001",
                "party_size": 3,
                "time_slot": "18:00",
            },
            "mock-confirmation-reserve_restaurant-restaurant_light_001-18:00",
        ),
        (
            "book_ticket",
            {
                "poi_id": "activity_museum_001",
                "quantity": 3,
                "time_slot": "14:00",
            },
            "mock-confirmation-book_ticket-activity_museum_001-14:00",
        ),
        (
            "order_addon",
            {"vendor_id": "addon_drinks_001", "items": [{"sku": "water", "quantity": 3}]},
            "mock-confirmation-order_addon-addon_drinks_001-water",
        ),
        (
            "send_message",
            {"recipient": "wife", "message": "Plan confirmed."},
            "mock-confirmation-send_message-wife",
        ),
    ],
)
def test_write_tools_return_deterministic_confirmation(
    tool_name: str,
    payload: dict[str, Any],
    confirmation_id: str,
) -> None:
    provider = MockWorldProvider()

    result = provider.invoke(tool_name, payload)

    assert result["confirmation"]["confirmation_id"] == confirmation_id
    assert result["confirmation"]["tool_name"] == tool_name
    assert result["confirmation"]["status"] == "simulated_confirmed"


@pytest.mark.parametrize(
    ("tool_name", "payload"),
    [
        ("get_poi_detail", {}),
        ("check_route", {"origin_id": "activity_museum_001"}),
        ("check_opening_hours", {}),
        ("check_queue", {}),
        ("check_table_availability", {}),
        ("check_ticket_availability", {}),
        ("join_queue", {}),
        ("reserve_restaurant", {"restaurant_id": "restaurant_light_001", "party_size": 3}),
        ("book_ticket", {"poi_id": "activity_museum_001", "quantity": 3}),
        ("order_addon", {"vendor_id": "addon_drinks_001"}),
        ("send_message", {"recipient": "wife"}),
    ],
)
def test_missing_required_fields_raise_mock_world_error(tool_name: str, payload: dict[str, Any]) -> None:
    provider = MockWorldProvider()

    with pytest.raises(MockWorldError):
        provider.invoke(tool_name, payload)


@pytest.mark.parametrize(
    ("tool_name", "payload"),
    [
        ("get_poi_detail", {"poi_id": "missing"}),
        (
            "check_route",
            {"origin_id": "activity_museum_001", "destination_id": "missing"},
        ),
        ("check_queue", {"queue_id": "missing"}),
        ("check_table_availability", {"restaurant_id": "activity_museum_001"}),
        ("check_ticket_availability", {"poi_id": "restaurant_light_001"}),
        ("join_queue", {"queue_id": "missing"}),
        (
            "reserve_restaurant",
            {"restaurant_id": "missing", "party_size": 3, "time_slot": "18:00"},
        ),
        (
            "book_ticket",
            {"poi_id": "missing", "quantity": 3, "time_slot": "14:00"},
        ),
        ("order_addon", {"vendor_id": "missing", "items": [{"sku": "water", "quantity": 1}]}),
        ("send_message", {"recipient": "unknown", "message": "Hello"}),
    ],
)
def test_unknown_entities_raise_mock_world_error(tool_name: str, payload: dict[str, Any]) -> None:
    provider = MockWorldProvider()

    with pytest.raises(MockWorldError):
        provider.invoke(tool_name, payload)


def test_unknown_tool_raises_mock_world_error() -> None:
    provider = MockWorldProvider()

    with pytest.raises(MockWorldError, match="Unknown Mock World tool"):
        provider.invoke("unknown_tool", {})


def test_build_mock_world_registry_registers_mock_world_as_default_provider() -> None:
    registry = build_mock_world_registry()

    assert registry.get_tool("search_poi").default_provider == "mock_world"
    assert registry.get_provider("mock_world").name == "mock_world"
