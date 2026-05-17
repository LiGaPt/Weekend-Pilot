from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from backend.app.tool_gateway.models import ToolDefinition, ToolGatewayRequest


class ToolFailureInjectionDecision(BaseModel):
    status: str = "failed"
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any]


@runtime_checkable
class ToolFailureInjector(Protocol):
    def maybe_inject(
        self,
        request: ToolGatewayRequest,
        definition: ToolDefinition,
        provider_name: str,
    ) -> ToolFailureInjectionDecision | None:
        ...


class ToolFailureInjectionRule(BaseModel):
    rule_id: str
    tool_name: str
    injected_error_type: str
    message: str = "Benchmark failure injected for tool call."
    details: dict[str, Any] = Field(default_factory=dict)


class StaticToolFailureInjector(BaseModel):
    profile_id: str
    rules: list[ToolFailureInjectionRule]

    def maybe_inject(
        self,
        request: ToolGatewayRequest,
        definition: ToolDefinition,
        provider_name: str,
    ) -> ToolFailureInjectionDecision | None:
        del request, provider_name
        if definition.tool_type != "read":
            return None

        for rule in self.rules:
            if rule.tool_name == definition.name:
                return ToolFailureInjectionDecision(
                    response_json=None,
                    error_json={
                        "error_type": "failure_injected",
                        "message": rule.message,
                        "details": {
                            "profile_id": self.profile_id,
                            "rule_id": rule.rule_id,
                            "tool_name": rule.tool_name,
                            "injected_error_type": rule.injected_error_type,
                            **rule.details,
                        },
                    },
                )
        return None
