from __future__ import annotations

from typing import Any


_SENSITIVE_KEY_PARTS = (
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
    "traceback",
    "stack_trace",
    "stack trace",
)
_SAFE_KEY_NAMES = {
    "prompt_version",
}
_DROP_KEYS = {
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_tokens_details",
    "completion_tokens_details",
}
_REDACTED = "[REDACTED]"


def sanitize_trace_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if str(key).casefold() in _DROP_KEYS:
                continue
            if _is_sensitive_key(key):
                sanitized[key] = _REDACTED
            else:
                sanitized[key] = sanitize_trace_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_trace_payload(item) for item in value]
    return value


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).casefold()
    if normalized in _SAFE_KEY_NAMES:
        return False
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
