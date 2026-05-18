from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LLMFallbackReason = Literal[
    "llm_disabled",
    "llm_config_incomplete",
    "llm_timeout",
    "llm_provider_error",
    "llm_bad_json",
    "llm_schema_mismatch",
    "agent_policy_mismatch",
    "invalid_candidate_ids",
    "invalid_draft_ids",
    "no_deterministic_drafts",
]


class LLMUsage(BaseModel):
    input_count: int | None = None
    output_count: int | None = None
    total_count: int | None = None


class LLMCallMetadata(BaseModel):
    provider_kind: str = "openai_compatible"
    model_id: str | None = None
    base_url_host: str | None = None
    latency_ms: int | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    status: Literal["completed", "failed", "skipped", "fallback"]
    fallback_reason: LLMFallbackReason | None = None
    error_type: str | None = None


class LLMChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMChatCompletion(BaseModel):
    content_json: dict[str, Any]
    metadata: LLMCallMetadata
