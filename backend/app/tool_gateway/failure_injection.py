from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from backend.app.tool_gateway.models import ToolDefinition, ToolGatewayRequest
from backend.app.tool_gateway.registry import READ_TOOLS


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
    effect_kind: Literal["hard_failure", "response_override"] = "hard_failure"
    effect_type: str
    gateway_status: Literal["failed", "succeeded"] = "failed"
    message: str | None = None
    response_json_template: dict[str, Any] | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rule(self) -> "ToolFailureInjectionRule":
        if self.tool_name not in READ_TOOLS:
            raise ValueError(f"Benchmark failure injection only supports read tools: {self.tool_name}")
        if self.effect_kind == "hard_failure":
            if self.gateway_status != "failed":
                raise ValueError("Hard-failure benchmark rules must use gateway_status='failed'.")
            if self.response_json_template is not None:
                raise ValueError("Hard-failure benchmark rules must not define response_json_template.")
            if self.message is None:
                self.message = "Benchmark failure injected for tool call."
            return self
        if self.gateway_status != "succeeded":
            raise ValueError("Response-override benchmark rules must use gateway_status='succeeded'.")
        if self.response_json_template is None:
            raise ValueError("Response-override benchmark rules require response_json_template.")
        if self.message is None:
            self.message = "Benchmark response override injected for tool call."
        return self


class StaticToolFailureInjector(BaseModel):
    profile_id: str
    rules: list[ToolFailureInjectionRule]

    def maybe_inject(
        self,
        request: ToolGatewayRequest,
        definition: ToolDefinition,
        provider_name: str,
    ) -> ToolFailureInjectionDecision | None:
        del provider_name
        if definition.tool_type != "read":
            return None

        for rule in self.rules:
            if rule.tool_name == definition.name:
                return self._decision_for_rule(rule, request)
        return None

    def _decision_for_rule(
        self,
        rule: ToolFailureInjectionRule,
        request: ToolGatewayRequest,
    ) -> ToolFailureInjectionDecision:
        response_json = None
        error_type = "failure_injected"
        if rule.effect_kind == "response_override":
            response_json = _render_response_json(rule.response_json_template, request.payload)
            error_type = "failure_injected_response"
        return ToolFailureInjectionDecision(
            status=rule.gateway_status,
            response_json=response_json,
            error_json={
                "error_type": error_type,
                "message": rule.message,
                "details": {
                    "profile_id": self.profile_id,
                    "rule_id": rule.rule_id,
                    "tool_name": rule.tool_name,
                    "effect_kind": rule.effect_kind,
                    "effect_type": rule.effect_type,
                    **rule.details,
                },
            },
        )


_PLACEHOLDER_KEYS = {
    "{poi_id}": "poi_id",
    "{restaurant_id}": "restaurant_id",
    "{location}": "location",
}


def _render_response_json(template: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
    if template is None:
        raise ValueError("Benchmark response override rule is missing response_json_template.")
    rendered = _resolve_placeholder_value(deepcopy(template), payload)
    if not isinstance(rendered, dict):
        raise ValueError("Benchmark response override template must resolve to a JSON object.")
    return rendered


def _resolve_placeholder_value(value: Any, payload: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_placeholder_value(child, payload) for key, child in value.items()}
    if isinstance(value, list):
        return [_resolve_placeholder_value(item, payload) for item in value]
    if isinstance(value, str):
        if value in _PLACEHOLDER_KEYS:
            payload_key = _PLACEHOLDER_KEYS[value]
            resolved = payload.get(payload_key)
            if resolved in {None, ""}:
                raise ValueError(
                    f"Benchmark response override placeholder {value} resolved to an empty value."
                )
            return resolved
        if value.startswith("{") and value.endswith("}"):
            raise ValueError(f"Unsupported benchmark response override placeholder: {value}")
    return value
