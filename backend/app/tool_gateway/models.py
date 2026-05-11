from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


ToolType = Literal["read", "write"]
GatewayStatus = Literal[
    "succeeded",
    "failed",
    "blocked",
    "rate_limited",
    "cached",
    "idempotent_replay",
]


class ToolRateLimit(BaseModel):
    limit: int = Field(gt=0)
    window_seconds: int = Field(gt=0)


class ToolDefinition(BaseModel):
    name: str
    tool_type: ToolType
    default_provider: str
    cache_ttl_seconds: int | None = Field(default=None, gt=0)
    rate_limit: ToolRateLimit | None = None

    @model_validator(mode="after")
    def validate_cache_policy(self) -> "ToolDefinition":
        if self.tool_type == "write" and self.cache_ttl_seconds is not None:
            raise ValueError("Write tools must not define cache TTL.")
        return self


class ToolGatewayRequest(BaseModel):
    run_id: UUID
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None
    user_confirmed: bool = False
    target_id: str | None = None
    idempotency_key: str | None = None
    langsmith_trace_id: str | None = None


class ToolGatewayResult(BaseModel):
    tool_name: str
    tool_type: ToolType
    provider: str
    status: GatewayStatus
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    cache_hit: bool = False
    latency_ms: int | None = None
    tool_event_id: UUID | None = None
    action_id: UUID | None = None
    idempotency_key: str | None = None
