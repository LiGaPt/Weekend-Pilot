from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.providers.mock_world.errors import MockWorldError
from backend.app.providers.mock_world.loader import _validate_world, load_mock_world


class MockWorldProvider:
    name = "mock_world"

    def __init__(self, world: dict[str, Any] | None = None) -> None:
        self._world = world or load_mock_world()
        _validate_world(self._world)
        self._pois_by_id = {poi["poi_id"]: poi for poi in self._world["pois"]}
        self._addons_by_vendor_id = {addon["vendor_id"]: addon for addon in self._world["addons"]}

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "search_poi":
            return self._search_poi(payload)
        if tool_name == "get_poi_detail":
            return self._get_poi_detail(payload)
        if tool_name == "check_route":
            return self._check_route(payload)
        if tool_name == "check_opening_hours":
            return self._check_opening_hours(payload)
        if tool_name == "check_weather":
            return self._check_weather(payload)
        if tool_name == "check_queue":
            return self._check_queue(payload)
        if tool_name == "check_table_availability":
            return self._check_table_availability(payload)
        if tool_name == "check_ticket_availability":
            return self._check_ticket_availability(payload)
        if tool_name == "join_queue":
            return self._join_queue(payload)
        if tool_name == "reserve_restaurant":
            return self._reserve_restaurant(payload)
        if tool_name == "book_ticket":
            return self._book_ticket(payload)
        if tool_name == "order_addon":
            return self._order_addon(payload)
        if tool_name == "send_message":
            return self._send_message(payload)
        raise MockWorldError(f"Unknown Mock World tool {tool_name!r}.")

    def _search_poi(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = _optional_text(payload, "query") or _optional_text(payload, "keywords")
        category = _optional_text(payload, "category")
        tags = _optional_tags(payload.get("tags"))
        limit = _optional_limit(payload.get("limit"))

        results = []
        for poi in self._world["pois"]:
            if category is not None and poi.get("category") != category:
                continue
            poi_tags = set(poi.get("tags", []))
            if tags and not set(tags).issubset(poi_tags):
                continue
            if query is not None and not _matches_query(poi, query):
                continue
            results.append(deepcopy(poi))

        results.sort(key=lambda item: (item.get("sort_order", 999), item["poi_id"]))
        if limit is not None:
            results = results[:limit]
        return {"results": results}

    def _get_poi_detail(self, payload: dict[str, Any]) -> dict[str, Any]:
        poi_id = _required_text(payload, "poi_id")
        poi = deepcopy(self._get_poi(poi_id))
        addon = self._addons_by_vendor_id.get(poi_id)
        if addon is not None:
            poi["vendor_id"] = addon["vendor_id"]
            poi["menu"] = deepcopy(addon.get("menu", []))
        return {"poi": poi}

    def _check_route(self, payload: dict[str, Any]) -> dict[str, Any]:
        origin_id = _required_text(payload, "origin_id")
        destination_id = _required_text(payload, "destination_id")
        mode = _optional_text(payload, "mode") or "walking"
        self._get_poi(origin_id)
        self._get_poi(destination_id)

        for route in self._world["routes"]:
            if (
                route.get("origin_id") == origin_id
                and route.get("destination_id") == destination_id
                and route.get("mode") == mode
            ):
                return {"route": deepcopy(route)}
        raise MockWorldError(
            f"Unknown route from {origin_id!r} to {destination_id!r} for mode {mode!r}."
        )

    def _check_opening_hours(self, payload: dict[str, Any]) -> dict[str, Any]:
        poi_id = _required_text(payload, "poi_id")
        poi = self._get_poi(poi_id)
        opening_hours = poi.get("opening_hours")
        if not isinstance(opening_hours, dict):
            raise MockWorldError(f"POI {poi_id!r} does not have opening hours.")
        return {"opening_hours": {"poi_id": poi_id, **deepcopy(opening_hours)}}

    def _check_weather(self, payload: dict[str, Any]) -> dict[str, Any]:
        weather = deepcopy(self._world["weather"])
        location = _optional_text(payload, "location")
        date = _optional_text(payload, "date")
        if location is not None and weather.get("location") != location:
            raise MockWorldError(f"Unknown weather location {location!r}.")
        if date is not None and weather.get("date") != date:
            raise MockWorldError(f"Unknown weather date {date!r}.")
        return {"weather": weather}

    def _check_queue(self, payload: dict[str, Any]) -> dict[str, Any]:
        queue = self._find_queue(payload)
        return {"queue": deepcopy(queue)}

    def _check_table_availability(self, payload: dict[str, Any]) -> dict[str, Any]:
        restaurant_id = _required_text(payload, "restaurant_id")
        self._get_restaurant(restaurant_id)
        availability = self._world["table_availability"].get(restaurant_id)
        if not isinstance(availability, dict):
            raise MockWorldError(f"Unknown table availability for restaurant {restaurant_id!r}.")

        result = deepcopy(availability)
        party_size = _optional_positive_int(payload.get("party_size"), "party_size")
        requested_time = _optional_text(payload, "time")
        if party_size is not None and party_size > result.get("max_party_size", party_size):
            result["available"] = False
        if requested_time is not None and requested_time not in result.get("time_slots", []):
            result["available"] = False
        return {"table_availability": result}

    def _check_ticket_availability(self, payload: dict[str, Any]) -> dict[str, Any]:
        poi_id = _required_text(payload, "poi_id")
        self._get_poi(poi_id)
        availability = self._world["ticket_availability"].get(poi_id)
        if not isinstance(availability, dict):
            raise MockWorldError(f"Unknown ticket availability for POI {poi_id!r}.")

        result = deepcopy(availability)
        quantity = _optional_positive_int(payload.get("quantity"), "quantity")
        requested_time = _optional_text(payload, "time")
        if quantity is not None and quantity > result.get("remaining", quantity):
            result["available"] = False
        if requested_time is not None and requested_time not in result.get("time_slots", []):
            result["available"] = False
        return {"ticket_availability": result}

    def _join_queue(self, payload: dict[str, Any]) -> dict[str, Any]:
        queue_id = _required_text(payload, "queue_id")
        queue = self._get_queue(queue_id)
        party_size = _optional_positive_int(payload.get("party_size"), "party_size")
        return {
            "confirmation": {
                "confirmation_id": f"mock-confirmation-join_queue-{queue_id}",
                "tool_name": "join_queue",
                "status": "simulated_confirmed",
                "target_id": queue_id,
                "poi_id": queue["poi_id"],
                "party_size": party_size,
                "estimated_wait_minutes": queue["wait_minutes"],
            }
        }

    def _reserve_restaurant(self, payload: dict[str, Any]) -> dict[str, Any]:
        restaurant_id = _required_text(payload, "restaurant_id")
        party_size = _required_positive_int(payload, "party_size")
        time_slot = _required_text(payload, "time_slot")
        self._get_restaurant(restaurant_id)
        self._require_table_slot(restaurant_id, time_slot, party_size)
        return {
            "confirmation": {
                "confirmation_id": f"mock-confirmation-reserve_restaurant-{restaurant_id}-{time_slot}",
                "tool_name": "reserve_restaurant",
                "status": "simulated_confirmed",
                "target_id": restaurant_id,
                "party_size": party_size,
                "time_slot": time_slot,
            }
        }

    def _book_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        poi_id = _required_text(payload, "poi_id")
        quantity = _required_positive_int(payload, "quantity")
        time_slot = _required_text(payload, "time_slot")
        self._require_ticket_slot(poi_id, time_slot, quantity)
        return {
            "confirmation": {
                "confirmation_id": f"mock-confirmation-book_ticket-{poi_id}-{time_slot}",
                "tool_name": "book_ticket",
                "status": "simulated_confirmed",
                "target_id": poi_id,
                "quantity": quantity,
                "time_slot": time_slot,
            }
        }

    def _order_addon(self, payload: dict[str, Any]) -> dict[str, Any]:
        vendor_id = _required_text(payload, "vendor_id")
        addon = self._get_addon(vendor_id)
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise MockWorldError("Mock World payload field 'items' is required.")

        menu_skus = {item["sku"] for item in addon.get("menu", [])}
        requested_skus = []
        for item in items:
            if not isinstance(item, dict):
                raise MockWorldError("Mock World order items must be objects.")
            sku = item.get("sku")
            quantity = item.get("quantity")
            if not isinstance(sku, str) or not sku.strip():
                raise MockWorldError("Mock World order items require non-empty 'sku'.")
            if sku not in menu_skus:
                raise MockWorldError(f"Unknown add-on item {sku!r} for vendor {vendor_id!r}.")
            if not isinstance(quantity, int) or quantity <= 0:
                raise MockWorldError("Mock World order items require positive integer 'quantity'.")
            requested_skus.append(sku)

        sku_part = "-".join(sorted(requested_skus))
        return {
            "confirmation": {
                "confirmation_id": f"mock-confirmation-order_addon-{vendor_id}-{sku_part}",
                "tool_name": "order_addon",
                "status": "simulated_confirmed",
                "target_id": vendor_id,
                "items": deepcopy(items),
            }
        }

    def _send_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        recipient = _required_text(payload, "recipient")
        message = _required_text(payload, "message")
        recipients = self._world.get("message_recipients", [])
        if recipient not in recipients:
            raise MockWorldError(f"Unknown message recipient {recipient!r}.")
        return {
            "confirmation": {
                "confirmation_id": f"mock-confirmation-send_message-{recipient}",
                "tool_name": "send_message",
                "status": "simulated_confirmed",
                "target_id": recipient,
                "message": message,
            }
        }

    def _get_poi(self, poi_id: str) -> dict[str, Any]:
        poi = self._pois_by_id.get(poi_id)
        if poi is None:
            raise MockWorldError(f"Unknown POI {poi_id!r}.")
        return poi

    def _get_restaurant(self, restaurant_id: str) -> dict[str, Any]:
        poi = self._get_poi(restaurant_id)
        if poi.get("category") != "dining":
            raise MockWorldError(f"Unknown restaurant {restaurant_id!r}.")
        return poi

    def _find_queue(self, payload: dict[str, Any]) -> dict[str, Any]:
        queue_id = _optional_text(payload, "queue_id")
        poi_id = _optional_text(payload, "poi_id")
        if queue_id is None and poi_id is None:
            raise MockWorldError("Mock World payload requires 'poi_id' or 'queue_id'.")
        if queue_id is not None:
            return self._get_queue(queue_id)
        assert poi_id is not None
        self._get_poi(poi_id)
        for queue in self._world["queues"].values():
            if queue.get("poi_id") == poi_id:
                return queue
        raise MockWorldError(f"Unknown queue for POI {poi_id!r}.")

    def _get_queue(self, queue_id: str) -> dict[str, Any]:
        queue = self._world["queues"].get(queue_id)
        if not isinstance(queue, dict):
            raise MockWorldError(f"Unknown queue {queue_id!r}.")
        return queue

    def _get_addon(self, vendor_id: str) -> dict[str, Any]:
        addon = self._addons_by_vendor_id.get(vendor_id)
        if addon is None:
            raise MockWorldError(f"Unknown add-on vendor {vendor_id!r}.")
        self._get_poi(vendor_id)
        return addon

    def _require_table_slot(self, restaurant_id: str, time_slot: str, party_size: int) -> None:
        availability = self._world["table_availability"].get(restaurant_id)
        if not isinstance(availability, dict):
            raise MockWorldError(f"Unknown table availability for restaurant {restaurant_id!r}.")
        if not availability.get("available"):
            raise MockWorldError(f"Restaurant {restaurant_id!r} is not available.")
        if party_size > availability.get("max_party_size", party_size):
            raise MockWorldError(f"Party size {party_size!r} exceeds restaurant capacity.")
        if time_slot not in availability.get("time_slots", []):
            raise MockWorldError(f"Unknown table time slot {time_slot!r} for restaurant {restaurant_id!r}.")

    def _require_ticket_slot(self, poi_id: str, time_slot: str, quantity: int) -> None:
        self._get_poi(poi_id)
        availability = self._world["ticket_availability"].get(poi_id)
        if not isinstance(availability, dict):
            raise MockWorldError(f"Unknown ticket availability for POI {poi_id!r}.")
        if not availability.get("available"):
            raise MockWorldError(f"Tickets for POI {poi_id!r} are not available.")
        if quantity > availability.get("remaining", quantity):
            raise MockWorldError(f"Ticket quantity {quantity!r} exceeds remaining availability.")
        if time_slot not in availability.get("time_slots", []):
            raise MockWorldError(f"Unknown ticket time slot {time_slot!r} for POI {poi_id!r}.")


def _matches_query(poi: dict[str, Any], query: str) -> bool:
    query_text = query.casefold()
    searchable = [
        poi.get("poi_id", ""),
        poi.get("name", ""),
        poi.get("description", ""),
        poi.get("address", ""),
        " ".join(poi.get("tags", [])),
    ]
    return any(query_text in str(value).casefold() for value in searchable)


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise MockWorldError(f"Mock World payload field {field_name!r} is required.")
    return value


def _optional_text(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise MockWorldError(f"Mock World payload field {field_name!r} must be text.")
    return value


def _required_positive_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    return _validate_positive_int(value, field_name, required=True)


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    return _validate_positive_int(value, field_name, required=False)


def _validate_positive_int(value: Any, field_name: str, required: bool) -> int:
    if value is None and required:
        raise MockWorldError(f"Mock World payload field {field_name!r} is required.")
    if not isinstance(value, int) or value <= 0:
        raise MockWorldError(f"Mock World payload field {field_name!r} must be a positive integer.")
    return value


def _optional_tags(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
        return value
    raise MockWorldError("Mock World payload field 'tags' must be text or a list of text values.")


def _optional_limit(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        raise MockWorldError("Mock World payload field 'limit' must be a positive integer.")
    return value
