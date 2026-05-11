import pytest

from backend.app.tool_gateway.models import ToolDefinition, ToolRateLimit
from backend.app.tool_gateway.registry import READ_TOOLS, WRITE_TOOLS, ToolRegistry, build_default_registry


def test_default_registry_contains_all_canonical_tools() -> None:
    registry = build_default_registry(default_provider="fake")

    for tool_name in READ_TOOLS + WRITE_TOOLS:
        definition = registry.get_tool(tool_name)
        assert definition is not None
        assert definition.name == tool_name
        assert definition.default_provider == "fake"


def test_default_registry_classifies_read_and_write_tools() -> None:
    registry = build_default_registry()

    for tool_name in READ_TOOLS:
        assert registry.get_tool(tool_name).tool_type == "read"

    for tool_name in WRITE_TOOLS:
        assert registry.get_tool(tool_name).tool_type == "write"


def test_default_registry_includes_cacheable_and_rate_limited_tools() -> None:
    registry = build_default_registry()

    assert registry.get_tool("check_weather").cache_ttl_seconds == 60
    assert registry.get_tool("search_poi").rate_limit == ToolRateLimit(limit=10, window_seconds=60)
    assert registry.get_tool("reserve_restaurant").rate_limit == ToolRateLimit(limit=3, window_seconds=60)


def test_duplicate_tool_registration_is_rejected() -> None:
    registry = ToolRegistry()
    definition = ToolDefinition(name="search_poi", tool_type="read", default_provider="fake")

    registry.register_tool(definition)

    with pytest.raises(ValueError, match="already registered"):
        registry.register_tool(definition)


def test_unknown_tool_returns_none() -> None:
    registry = build_default_registry()

    assert registry.get_tool("unknown_tool") is None
