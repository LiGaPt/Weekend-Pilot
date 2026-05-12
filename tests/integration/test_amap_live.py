import os

import pytest

from backend.app.core.config import get_settings
from backend.app.providers.amap import AMapClient, AMapProvider


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AMAP_LIVE_TESTS") != "1",
    reason="Set RUN_AMAP_LIVE_TESTS=1 to run optional AMAP live smoke tests.",
)


@pytest.fixture()
def amap_provider() -> AMapProvider:
    secret = get_settings().amap_maps_api_key
    if secret is None or not secret.get_secret_value().strip():
        pytest.skip("AMAP_MAPS_API_KEY is not configured.")
    return AMapProvider(AMapClient(secret.get_secret_value()))


def test_live_search_poi_shape(amap_provider: AMapProvider) -> None:
    result = amap_provider.invoke(
        "search_poi",
        {
            "keywords": "museum",
            "city": "310000",
            "page_size": 1,
        },
    )

    assert "results" in result
    assert isinstance(result["results"], list)


def test_live_check_route_shape(amap_provider: AMapProvider) -> None:
    result = amap_provider.invoke(
        "check_route",
        {
            "origin": "121.4737,31.2304",
            "destination": "121.4998,31.2397",
            "mode": "walking",
        },
    )

    assert result["route"]["source"] == "amap"
    assert result["route"]["mode"] == "walking"


def test_live_check_weather_shape(amap_provider: AMapProvider) -> None:
    result = amap_provider.invoke(
        "check_weather",
        {
            "city": "310000",
        },
    )

    assert result["weather"]["source"] == "amap"
    assert "condition" in result["weather"]
