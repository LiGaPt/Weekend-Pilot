from __future__ import annotations

import json

import httpx

from backend.app.core.config import Settings
from backend.app.llm import (
    LLMChatMessage,
    LLMProviderError,
    LLMResponseError,
    OpenAICompatibleChatClient,
)


def test_settings_supports_generic_llm_fields_without_openai_key() -> None:
    settings = Settings(
        _env_file=None,
        llm_enabled=True,
        llm_api_key="local-test-key",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        llm_model_id="qwen3.6-plus",
        llm_timeout=7.5,
        openai_api_key=None,
    )

    assert settings.llm_enabled is True
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "local-test-key"
    assert settings.llm_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.llm_model_id == "qwen3.6-plus"
    assert settings.llm_timeout == 7.5
    assert settings.openai_api_key is None


def test_chat_client_posts_openai_compatible_request_and_normalizes_usage() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "活动证据充足。",
                                    "candidate_ids": ["activity_museum_001"],
                                    "tool_names_used": ["get_poi_detail"],
                                }
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            },
        )

    client = OpenAICompatibleChatClient(
        api_key="local-test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen3.6-plus",
        timeout=5.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.chat_json(
        messages=[
            LLMChatMessage(role="system", content="Return JSON."),
            LLMChatMessage(role="user", content="Summarize candidates."),
        ],
        temperature=0.1,
        max_tokens=200,
    )

    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured["authorization"] == "Bearer local-test-key"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "qwen3.6-plus"
    assert payload["response_format"] == {"type": "json_object"}
    assert result.content_json["summary"] == "活动证据充足。"
    assert result.metadata.provider_kind == "openai_compatible"
    assert result.metadata.model_id == "qwen3.6-plus"
    assert result.metadata.base_url_host == "dashscope.aliyuncs.com"
    assert result.metadata.usage.input_count == 11
    assert result.metadata.usage.output_count == 7
    assert result.metadata.usage.total_count == 18
    serialized = result.model_dump_json()
    assert "prompt_tokens" not in serialized
    assert "completion_tokens" not in serialized
    assert "total_tokens" not in serialized
    assert "local-test-key" not in serialized


def test_chat_client_maps_timeout_to_safe_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("request timed out", request=request)

    client = OpenAICompatibleChatClient(
        api_key="local-test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen3.6-plus",
        timeout=5.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.chat_json(messages=[LLMChatMessage(role="user", content="{}")])
    except LLMProviderError as exc:
        assert exc.fallback_reason == "llm_timeout"
        assert "local-test-key" not in str(exc)
    else:
        raise AssertionError("Expected LLMProviderError for timeout.")


def test_chat_client_maps_http_failure_to_safe_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    client = OpenAICompatibleChatClient(
        api_key="local-test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen3.6-plus",
        timeout=5.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.chat_json(messages=[LLMChatMessage(role="user", content="{}")])
    except LLMProviderError as exc:
        assert exc.fallback_reason == "llm_provider_error"
        assert "rate limited" not in str(exc)
    else:
        raise AssertionError("Expected LLMProviderError for HTTP failure.")


def test_chat_client_maps_malformed_assistant_json_to_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )

    client = OpenAICompatibleChatClient(
        api_key="local-test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen3.6-plus",
        timeout=5.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.chat_json(messages=[LLMChatMessage(role="user", content="{}")])
    except LLMResponseError as exc:
        assert exc.fallback_reason == "llm_bad_json"
        assert "not json" not in str(exc)
    else:
        raise AssertionError("Expected LLMResponseError for malformed assistant JSON.")
