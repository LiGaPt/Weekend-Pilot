from backend.app.providers.mock_world.loader import load_mock_world
from backend.app.providers.mock_world.provider import MockWorldProvider
from backend.app.tool_gateway.registry import ToolRegistry, build_default_registry


def build_mock_world_registry(profile: str = "family_afternoon") -> ToolRegistry:
    registry = build_default_registry(default_provider="mock_world")
    registry.register_provider(MockWorldProvider(load_mock_world(profile)))
    return registry
