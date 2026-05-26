from __future__ import annotations

import hashlib
from dataclasses import dataclass

from redis import Redis

from backend.app.runtime.keys import RedisKeyBuilder


_SCOPE_HASH_LENGTH = 16
_SCOPE_LABEL_FALLBACK = "scope"
_ALLOWED_SCOPE_LABEL_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "-_"
)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    reset_after_seconds: int


class FixedWindowRateLimiter:
    def __init__(self, client: Redis, keys: RedisKeyBuilder) -> None:
        self._client = client
        self._keys = keys

    def allow(self, name: str, limit: int, window_seconds: int) -> RateLimitDecision:
        key = self._keys.rate_limit(name)
        count = int(self._client.incr(key))
        if count == 1:
            self._client.expire(key, window_seconds)

        ttl = int(self._client.ttl(key))
        reset_after_seconds = max(ttl, 0)
        remaining = max(limit - count, 0)

        return RateLimitDecision(
            allowed=count <= limit,
            remaining=remaining,
            reset_after_seconds=reset_after_seconds,
        )


class ScopedRateLimiter(FixedWindowRateLimiter):
    def __init__(self, base: FixedWindowRateLimiter, namespace: str) -> None:
        self._base = base
        self._namespace = _opaque_namespace(namespace)

    def allow(self, name: str, limit: int, window_seconds: int) -> RateLimitDecision:
        return self._base.allow(
            f"{self._namespace}:{name}",
            limit=limit,
            window_seconds=window_seconds,
        )


def _opaque_namespace(namespace: str) -> str:
    normalized = namespace.strip()
    if not normalized:
        raise ValueError("Rate-limit namespace must not be empty.")

    raw_label = normalized.split(":", 1)[0] if ":" in normalized else _SCOPE_LABEL_FALLBACK
    safe_label = "".join(character for character in raw_label if character in _ALLOWED_SCOPE_LABEL_CHARS)
    if not safe_label:
        safe_label = _SCOPE_LABEL_FALLBACK

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:_SCOPE_HASH_LENGTH]
    return f"{safe_label}:{digest}"
