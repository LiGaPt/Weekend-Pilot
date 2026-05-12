from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

import backend.app.providers.amap.registry as amap_registry_module
from backend.app.providers.amap import AMapClient, AMapProvider
from backend.app.providers.amap.errors import (
    AMapConfigurationError,
    AMapProviderError,
    AMapUnsupportedToolError,
)
from backend.app.providers.amap.registry import build_amap_registry


class FakeAMapClient:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, params))
        return self.responses[path]


def poi_response() -> dict[str, Any]:
    return {
        "status": "1",
        "pois": [
            {
                "id": "B001",
                "name": "Shanghai Museum",
                "type": "Science;Museum",
                "address": "201 Renmin Ave",
                "location": "121.475,31.228",
                "cityname": "Shanghai",
            }
        ],
    }


def route_response() -> dict[str, Any]:
    return {
        "status": "1",
        "route": {
            "paths": [
                {
                    "distance": "1200",
                    "duration": "900",
                }
            ]
        },
    }


def weather_response() -> dict[str, Any]:
    return {
        "status": "1",
        "lives": [
            {
                "city": "Shanghai",
                "weather": "Sunny",
                "temperature": "25",
                "winddirection": "Southeast",
                "windpower": "3",
                "reporttime": "2026-05-12 10:00:00",
            }
        ],
    }


def test_provider_name_is_amap() -> None:
    provider = AMapProvider(FakeAMapClient({}))

    assert provider.name == "amap"


def test_search_poi_passes_expected_params() -> None:
    client = FakeAMapClient({"/v3/place/text": poi_response()})
    provider = AMapProvider(client)

    result = provider.invoke(
        "search_poi",
        {
            "keywords": "family museum",
            "city": "Shanghai",
            "types": "140000",
            "location": "121.4737,31.2304",
            "radius": 5000,
            "page_size": 10,
        },
    )

    assert result["results"][0]["poi_id"] == "B001"
    assert client.calls == [
        (
            "/v3/place/text",
            {
                "keywords": "family museum",
                "city": "Shanghai",
                "types": "140000",
                "location": "121.4737,31.2304",
                "radius": 5000,
                "offset": 10,
            },
        )
    ]


def test_get_poi_detail_passes_id_param() -> None:
    client = FakeAMapClient({"/v3/place/detail": poi_response()})
    provider = AMapProvider(client)

    result = provider.invoke("get_poi_detail", {"poi_id": "B001"})

    assert result["poi"]["poi_id"] == "B001"
    assert client.calls == [("/v3/place/detail", {"id": "B001"})]


def test_check_route_selects_walking_path_by_default() -> None:
    client = FakeAMapClient({"/v3/direction/walking": route_response()})
    provider = AMapProvider(client)

    result = provider.invoke(
        "check_route",
        {
            "origin": "121.4737,31.2304",
            "destination": "121.4998,31.2397",
        },
    )

    assert result["route"]["mode"] == "walking"
    assert client.calls == [
        (
            "/v3/direction/walking",
            {
                "origin": "121.4737,31.2304",
                "destination": "121.4998,31.2397",
            },
        )
    ]


def test_check_route_selects_driving_path_when_requested() -> None:
    client = FakeAMapClient({"/v3/direction/driving": route_response()})
    provider = AMapProvider(client)

    result = provider.invoke(
        "check_route",
        {
            "origin": "121.4737,31.2304",
            "destination": "121.4998,31.2397",
            "mode": "driving",
        },
    )

    assert result["route"]["mode"] == "driving"
    assert client.calls == [
        (
            "/v3/direction/driving",
            {
                "origin": "121.4737,31.2304",
                "destination": "121.4998,31.2397",
            },
        )
    ]


def test_check_weather_defaults_extensions_to_base() -> None:
    client = FakeAMapClient({"/v3/weather/weatherInfo": weather_response()})
    provider = AMapProvider(client)

    result = provider.invoke("check_weather", {"city": "310000"})

    assert result["weather"]["city"] == "Shanghai"
    assert client.calls == [
        (
            "/v3/weather/weatherInfo",
            {
                "city": "310000",
                "extensions": "base",
            },
        )
    ]


@pytest.mark.parametrize(
    ("tool_name", "payload"),
    [
        ("search_poi", {}),
        ("search_poi", {"keywords": ""}),
        ("get_poi_detail", {}),
        ("check_route", {"origin": "121.4737,31.2304"}),
        ("check_route", {"destination": "121.4998,31.2397"}),
        ("check_weather", {}),
    ],
)
def test_missing_required_fields_raise_provider_error(tool_name: str, payload: dict[str, Any]) -> None:
    provider = AMapProvider(FakeAMapClient({}))

    with pytest.raises(AMapProviderError):
        provider.invoke(tool_name, payload)


def test_invalid_route_mode_raises_provider_error() -> None:
    provider = AMapProvider(FakeAMapClient({}))

    with pytest.raises(AMapProviderError, match="Unsupported route mode"):
        provider.invoke(
            "check_route",
            {
                "origin": "121.4737,31.2304",
                "destination": "121.4998,31.2397",
                "mode": "cycling",
            },
        )


def test_unsupported_canonical_tool_raises_unsupported_tool_error() -> None:
    provider = AMapProvider(FakeAMapClient({}))

    with pytest.raises(AMapUnsupportedToolError):
        provider.invoke("check_queue", {"poi_id": "B001"})


def test_build_amap_registry_uses_settings_and_default_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummySettings:
        amap_maps_api_key = SecretStr("fake-amap-test-key")

    monkeypatch.setattr(amap_registry_module, "get_settings", lambda: DummySettings())

    registry = build_amap_registry()

    assert registry.get_tool("search_poi").default_provider == "amap"
    assert registry.get_provider("amap").name == "amap"


def test_build_amap_registry_missing_key_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummySettings:
        amap_maps_api_key = None

    monkeypatch.setattr(amap_registry_module, "get_settings", lambda: DummySettings())

    with pytest.raises(AMapConfigurationError):
        build_amap_registry()


def test_client_missing_key_raises_configuration_error() -> None:
    with pytest.raises(AMapConfigurationError):
        AMapClient("")


def test_client_amap_error_status_raises_without_leaking_api_key() -> None:
    fake_key = "fake-amap-test-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "0",
                "infocode": "10001",
                "info": "INVALID_USER_KEY",
            },
        )

    http_client = httpx.Client(
        base_url="https://restapi.amap.test",
        transport=httpx.MockTransport(handler),
    )
    client = AMapClient(fake_key, http_client=http_client)

    with pytest.raises(AMapProviderError) as exc_info:
        client.get("/v3/place/text", {"keywords": "museum"})

    assert "INVALID_USER_KEY" in str(exc_info.value)
    assert fake_key not in str(exc_info.value)


def test_client_injects_key_internally() -> None:
    fake_key = "fake-amap-test-key"
    observed_query: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_query.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "pois": []})

    http_client = httpx.Client(
        base_url="https://restapi.amap.test",
        transport=httpx.MockTransport(handler),
    )
    client = AMapClient(fake_key, http_client=http_client)

    assert client.get("/v3/place/text", {"keywords": "museum"}) == {"status": "1", "pois": []}
    assert observed_query == {
        "keywords": "museum",
        "key": fake_key,
    }
