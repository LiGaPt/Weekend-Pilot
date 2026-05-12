from __future__ import annotations

from typing import Any

from backend.app.providers.amap.errors import AMapProviderError


def map_poi_search(response: dict[str, Any]) -> dict[str, Any]:
    pois = response.get("pois", [])
    if not isinstance(pois, list):
        raise AMapProviderError("AMAP POI search response is malformed.")
    if any(not isinstance(poi, dict) for poi in pois):
        raise AMapProviderError("AMAP POI search response is malformed.")
    return {"results": [_map_poi(poi) for poi in pois]}


def map_poi_detail(response: dict[str, Any]) -> dict[str, Any]:
    pois = response.get("pois")
    if not isinstance(pois, list) or not pois or not isinstance(pois[0], dict):
        raise AMapProviderError("AMAP POI detail response is malformed.")
    return {"poi": _map_poi(pois[0])}


def map_route(response: dict[str, Any], origin: str, destination: str, mode: str) -> dict[str, Any]:
    route = response.get("route")
    if not isinstance(route, dict):
        raise AMapProviderError("AMAP route response is malformed.")

    paths = route.get("paths")
    if not isinstance(paths, list) or not paths or not isinstance(paths[0], dict):
        raise AMapProviderError("AMAP route response is missing paths.")

    path = paths[0]
    distance = _as_int(path.get("distance"), "distance")
    duration = _as_int(path.get("duration"), "duration")
    return {
        "route": {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "distance_meters": distance,
            "duration_seconds": duration,
            "source": "amap",
        }
    }


def map_weather(response: dict[str, Any]) -> dict[str, Any]:
    lives = response.get("lives")
    if not isinstance(lives, list) or not lives or not isinstance(lives[0], dict):
        raise AMapProviderError("AMAP weather response is malformed.")

    live = lives[0]
    if "city" not in live or "weather" not in live:
        raise AMapProviderError("AMAP weather response is missing required fields.")

    return {
        "weather": {
            "city": _as_text(live.get("city")),
            "condition": _as_text(live.get("weather")),
            "temperature_celsius": _as_text(live.get("temperature")),
            "wind_direction": _as_text(live.get("winddirection")),
            "wind_power": _as_text(live.get("windpower")),
            "report_time": _as_text(live.get("reporttime")),
            "source": "amap",
        }
    }


def _map_poi(poi: dict[str, Any]) -> dict[str, Any]:
    return {
        "poi_id": _as_text(poi.get("id")),
        "name": _as_text(poi.get("name")),
        "category": _as_text(poi.get("type")),
        "address": _as_text(poi.get("address")),
        "location": _as_text(poi.get("location")),
        "city": _as_text(poi.get("cityname") or poi.get("city")),
        "source": "amap",
    }


def _as_text(value: Any) -> str:
    if value is None or isinstance(value, list):
        return ""
    return str(value)


def _as_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AMapProviderError(f"AMAP route response has invalid {field_name}.") from exc
