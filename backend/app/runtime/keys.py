from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.core.config import get_settings


def _normalize_namespace_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "default"


@dataclass(frozen=True)
class RedisKeyBuilder:
    prefix: str

    def __post_init__(self) -> None:
        normalized_prefix = self.prefix.strip(":")
        if not normalized_prefix:
            raise ValueError("Redis key prefix must not be empty")
        object.__setattr__(self, "prefix", normalized_prefix)

    @classmethod
    def from_settings(cls) -> RedisKeyBuilder:
        settings = get_settings()
        app_name = _normalize_namespace_part(settings.app_name)
        app_env = _normalize_namespace_part(settings.app_env)
        return cls(prefix=f"{app_name}:{app_env}")

    def cache(self, name: str) -> str:
        return self._join("cache", name)

    def lock(self, name: str) -> str:
        return self._join("lock", name)

    def rate_limit(self, name: str) -> str:
        return self._join("rate-limit", name)

    def progress(self, run_id: str) -> str:
        return self._join("progress", run_id)

    def _join(self, category: str, name: str) -> str:
        if not name:
            raise ValueError("Redis key name must not be empty")
        return f"{self.prefix}:{category}:{name}"
