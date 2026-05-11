from __future__ import annotations

from backend.app.tool_gateway.models import ToolDefinition, ToolRateLimit
from backend.app.tool_gateway.providers import ToolProvider


READ_TOOLS = (
    "search_poi",
    "get_poi_detail",
    "check_route",
    "check_opening_hours",
    "check_weather",
    "check_queue",
    "check_table_availability",
    "check_ticket_availability",
)

WRITE_TOOLS = (
    "join_queue",
    "reserve_restaurant",
    "book_ticket",
    "order_addon",
    "send_message",
)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._providers: dict[str, ToolProvider] = {}

    def register_tool(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool {definition.name!r} is already registered.")
        self._tools[definition.name] = definition

    def register_provider(self, provider: ToolProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Provider {provider.name!r} is already registered.")
        self._providers[provider.name] = provider

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_provider(self, name: str) -> ToolProvider | None:
        return self._providers.get(name)


def build_default_registry(default_provider: str = "mock_world") -> ToolRegistry:
    registry = ToolRegistry()

    for tool_name in READ_TOOLS:
        registry.register_tool(
            ToolDefinition(
                name=tool_name,
                tool_type="read",
                default_provider=default_provider,
                cache_ttl_seconds=_read_cache_ttl(tool_name),
                rate_limit=_read_rate_limit(tool_name),
            )
        )

    for tool_name in WRITE_TOOLS:
        registry.register_tool(
            ToolDefinition(
                name=tool_name,
                tool_type="write",
                default_provider=default_provider,
                rate_limit=_write_rate_limit(tool_name),
            )
        )

    return registry


def _read_cache_ttl(tool_name: str) -> int | None:
    if tool_name in {
        "check_weather",
        "check_queue",
        "check_table_availability",
        "check_ticket_availability",
    }:
        return 60
    return None


def _read_rate_limit(tool_name: str) -> ToolRateLimit | None:
    if tool_name == "search_poi":
        return ToolRateLimit(limit=10, window_seconds=60)
    return None


def _write_rate_limit(tool_name: str) -> ToolRateLimit | None:
    if tool_name == "reserve_restaurant":
        return ToolRateLimit(limit=3, window_seconds=60)
    return None
