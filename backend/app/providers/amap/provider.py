from __future__ import annotations

from typing import Any

from backend.app.providers.amap.client import AMapClient
from backend.app.providers.amap.errors import AMapProviderError, AMapUnsupportedToolError
from backend.app.providers.amap.mapper import map_poi_detail, map_poi_search, map_route, map_weather


class AMapProvider:
    name = "amap"

    def __init__(self, client: AMapClient) -> None:
        self._client = client

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "search_poi":
            return self._search_poi(payload)
        if tool_name == "get_poi_detail":
            return self._get_poi_detail(payload)
        if tool_name == "check_route":
            return self._check_route(payload)
        if tool_name == "check_weather":
            return self._check_weather(payload)
        raise AMapUnsupportedToolError(f"AMAP provider does not support tool {tool_name!r}.")

    def _search_poi(self, payload: dict[str, Any]) -> dict[str, Any]:
        keywords = _required_text(payload, "keywords")
        params: dict[str, Any] = {"keywords": keywords}
        _add_optional(params, payload, "city")
        _add_optional(params, payload, "types")
        _add_optional(params, payload, "location")
        _add_optional(params, payload, "radius")
        if _has_value(payload.get("page_size")):
            params["offset"] = payload["page_size"]

        response = self._client.get("/v3/place/text", params)
        return map_poi_search(response)

    def _get_poi_detail(self, payload: dict[str, Any]) -> dict[str, Any]:
        poi_id = _required_text(payload, "poi_id")
        response = self._client.get("/v3/place/detail", {"id": poi_id})
        return map_poi_detail(response)

    def _check_route(self, payload: dict[str, Any]) -> dict[str, Any]:
        origin = _required_text(payload, "origin")
        destination = _required_text(payload, "destination")
        mode = str(payload.get("mode") or "walking")
        if mode not in {"walking", "driving"}:
            raise AMapProviderError("Unsupported route mode. Expected walking or driving.")

        path = f"/v3/direction/{mode}"
        response = self._client.get(path, {"origin": origin, "destination": destination})
        return map_route(response, origin, destination, mode)

    def _check_weather(self, payload: dict[str, Any]) -> dict[str, Any]:
        city = _required_text(payload, "city")
        extensions = str(payload.get("extensions") or "base")
        response = self._client.get(
            "/v3/weather/weatherInfo",
            {
                "city": city,
                "extensions": extensions,
            },
        )
        return map_weather(response)


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise AMapProviderError(f"AMAP payload field {field_name!r} is required.")
    return value


def _add_optional(params: dict[str, Any], payload: dict[str, Any], field_name: str) -> None:
    value = payload.get(field_name)
    if _has_value(value):
        params[field_name] = value


def _has_value(value: Any) -> bool:
    return value is not None and value != ""
