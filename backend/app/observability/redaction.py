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
)
_REDACTED = "[REDACTED]"


def sanitize_trace_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
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
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
