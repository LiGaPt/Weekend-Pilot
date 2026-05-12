import pytest

from backend.app.providers.amap.errors import AMapProviderError
from backend.app.providers.amap.mapper import (
    map_poi_detail,
    map_poi_search,
    map_route,
    map_weather,
)


def test_poi_search_maps_two_pois() -> None:
    response = {
        "status": "1",
        "pois": [
            {
                "id": "B001",
                "name": "Shanghai Museum",
                "type": "Science;Museum",
                "address": "201 Renmin Ave",
                "location": "121.475,31.228",
                "cityname": "Shanghai",
            },
            {
                "id": "B002",
                "name": "Family Park",
                "type": "Park",
                "address": [],
                "location": "121.480,31.230",
                "cityname": "Shanghai",
            },
        ],
    }

    assert map_poi_search(response) == {
        "results": [
            {
                "poi_id": "B001",
                "name": "Shanghai Museum",
                "category": "Science;Museum",
                "address": "201 Renmin Ave",
                "location": "121.475,31.228",
                "city": "Shanghai",
                "source": "amap",
            },
            {
                "poi_id": "B002",
                "name": "Family Park",
                "category": "Park",
                "address": "",
                "location": "121.480,31.230",
                "city": "Shanghai",
                "source": "amap",
            },
        ]
    }


def test_poi_search_maps_empty_successful_response() -> None:
    assert map_poi_search({"status": "1", "pois": []}) == {"results": []}


def test_poi_search_with_malformed_poi_raises_provider_error() -> None:
    with pytest.raises(AMapProviderError):
        map_poi_search({"status": "1", "pois": ["not-a-poi"]})


def test_poi_detail_maps_first_returned_poi() -> None:
    response = {
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

    assert map_poi_detail(response) == {
        "poi": {
            "poi_id": "B001",
            "name": "Shanghai Museum",
            "category": "Science;Museum",
            "address": "201 Renmin Ave",
            "location": "121.475,31.228",
            "city": "Shanghai",
            "source": "amap",
        }
    }


@pytest.mark.parametrize("mode", ["walking", "driving"])
def test_route_maps_distance_and_duration(mode: str) -> None:
    response = {
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

    assert map_route(response, "121.4737,31.2304", "121.4998,31.2397", mode) == {
        "route": {
            "origin": "121.4737,31.2304",
            "destination": "121.4998,31.2397",
            "mode": mode,
            "distance_meters": 1200,
            "duration_seconds": 900,
            "source": "amap",
        }
    }


def test_weather_maps_live_weather_fields() -> None:
    response = {
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

    assert map_weather(response) == {
        "weather": {
            "city": "Shanghai",
            "condition": "Sunny",
            "temperature_celsius": "25",
            "wind_direction": "Southeast",
            "wind_power": "3",
            "report_time": "2026-05-12 10:00:00",
            "source": "amap",
        }
    }


@pytest.mark.parametrize(
    ("mapper", "response", "args"),
    [
        (map_poi_detail, {"status": "1", "pois": []}, ()),
        (map_route, {"status": "1", "route": {"paths": []}}, ("a", "b", "walking")),
        (map_weather, {"status": "1", "lives": []}, ()),
    ],
)
def test_malformed_successful_responses_raise_provider_error(mapper, response, args) -> None:
    with pytest.raises(AMapProviderError):
        mapper(response, *args)
