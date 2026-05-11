from __future__ import annotations

from dataclasses import dataclass

from redis import Redis

from backend.app.runtime.keys import RedisKeyBuilder


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
