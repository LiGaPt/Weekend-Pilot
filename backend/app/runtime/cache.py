from __future__ import annotations

import json
from typing import Any, TypeAlias

from redis import Redis

from backend.app.runtime.keys import RedisKeyBuilder


JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None


class JsonRedisCache:
    def __init__(self, client: Redis, keys: RedisKeyBuilder) -> None:
        self._client = client
        self._keys = keys

    def set_json(self, key: str, value: JsonValue, ttl_seconds: int) -> None:
        payload = json.dumps(value, allow_nan=False)
        self._client.set(self._keys.cache(key), payload, ex=ttl_seconds)

    def get_json(self, key: str) -> JsonValue:
        payload = self._client.get(self._keys.cache(key))
        if payload is None:
            return None
        return json.loads(payload)

    def delete(self, key: str) -> int:
        return int(self._client.delete(self._keys.cache(key)))
