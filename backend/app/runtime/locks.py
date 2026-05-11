from __future__ import annotations

from uuid import uuid4

from redis import Redis

from backend.app.runtime.keys import RedisKeyBuilder


class RedisLockManager:
    _RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    def __init__(self, client: Redis, keys: RedisKeyBuilder) -> None:
        self._client = client
        self._keys = keys

    def acquire(self, name: str, ttl_seconds: int) -> str | None:
        token = uuid4().hex
        acquired = self._client.set(
            self._keys.lock(name),
            token,
            nx=True,
            ex=ttl_seconds,
        )
        return token if acquired else None

    def release(self, name: str, token: str) -> bool:
        deleted = self._client.eval(self._RELEASE_SCRIPT, 1, self._keys.lock(name), token)
        return int(deleted) == 1
