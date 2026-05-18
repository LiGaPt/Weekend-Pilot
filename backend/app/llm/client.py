from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Sequence
from urllib.parse import urlparse

import httpx

from backend.app.llm.errors import LLMConfigurationError, LLMProviderError, LLMResponseError
from backend.app.llm.schemas import (
    LLMCallMetadata,
    LLMChatCompletion,
    LLMChatMessage,
    LLMUsage,
)


class OpenAICompatibleChatClient:
    provider_kind = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_id: str,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("LLM API key is not configured.", fallback_reason="llm_config_incomplete")
        if not base_url or not base_url.strip():
            raise LLMConfigurationError("LLM base URL is not configured.", fallback_reason="llm_config_incomplete")
        if not model_id or not model_id.strip():
            raise LLMConfigurationError("LLM model ID is not configured.", fallback_reason="llm_config_incomplete")

        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.timeout = timeout
        self._http_client = http_client or httpx.Client(timeout=timeout)

    @property
    def base_url_host(self) -> str | None:
        return _base_url_host(self.base_url)

    def chat_json(
        self,
        *,
        messages: Sequence[LLMChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 400,
    ) -> LLMChatCompletion:
        started = perf_counter()
        try:
            response = self._http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model_id,
                    "messages": [message.model_dump(mode="json") for message in messages],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMProviderError("LLM request timed out.", fallback_reason="llm_timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("LLM provider request failed.", fallback_reason="llm_provider_error") from exc

        latency_ms = max(0, int((perf_counter() - started) * 1000))
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMResponseError("LLM provider response was not valid JSON.", fallback_reason="llm_bad_json") from exc
        if not isinstance(payload, dict):
            raise LLMResponseError("LLM provider response was not an object.", fallback_reason="llm_bad_json")

        content = _assistant_content(payload)
        try:
            content_json = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError("LLM assistant content was not valid JSON.", fallback_reason="llm_bad_json") from exc
        if not isinstance(content_json, dict):
            raise LLMResponseError("LLM assistant JSON was not an object.", fallback_reason="llm_bad_json")

        return LLMChatCompletion(
            content_json=content_json,
            metadata=LLMCallMetadata(
                provider_kind=self.provider_kind,
                model_id=self.model_id,
                base_url_host=self.base_url_host,
                latency_ms=latency_ms,
                usage=_normalize_usage(payload.get("usage")),
                status="completed",
            ),
        )


def _assistant_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMResponseError("LLM provider response did not include choices.", fallback_reason="llm_bad_json")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMResponseError("LLM provider choice was not an object.", fallback_reason="llm_bad_json")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMResponseError("LLM provider choice message was not an object.", fallback_reason="llm_bad_json")
    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise LLMResponseError("LLM provider message content was missing.", fallback_reason="llm_bad_json")
    return content


def _normalize_usage(value: Any) -> LLMUsage:
    if not isinstance(value, dict):
        return LLMUsage()
    return LLMUsage(
        input_count=_int_or_none(value.get("prompt_tokens")),
        output_count=_int_or_none(value.get("completion_tokens")),
        total_count=_int_or_none(value.get("total_tokens")),
    )


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _base_url_host(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    return parsed.hostname
