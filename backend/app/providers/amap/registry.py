from backend.app.core.config import get_settings
from backend.app.providers.amap.client import AMapClient
from backend.app.providers.amap.errors import AMapConfigurationError
from backend.app.providers.amap.provider import AMapProvider
from backend.app.tool_gateway.registry import ToolRegistry, build_default_registry


def build_amap_registry() -> ToolRegistry:
    settings = get_settings()
    secret = settings.amap_maps_api_key
    if secret is None or not secret.get_secret_value().strip():
        raise AMapConfigurationError("AMAP API key is not configured.")

    registry = build_default_registry(default_provider="amap")
    registry.register_provider(AMapProvider(AMapClient(secret.get_secret_value())))
    return registry
