from typing import Any, Protocol


class ToolProvider(Protocol):
    name: str

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
