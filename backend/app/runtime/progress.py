from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis import Redis

from backend.app.runtime.keys import RedisKeyBuilder


@dataclass(frozen=True)
class ProgressEvent:
    event_id: str
    event_type: str
    payload: dict[str, Any]


class RedisProgressStream:
    def __init__(self, client: Redis, keys: RedisKeyBuilder) -> None:
        self._client = client
        self._keys = keys

    def append(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        maxlen: int = 1000,
    ) -> str:
        event_id = self._client.xadd(
            self._keys.progress(run_id),
            {
                "event_type": event_type,
                "payload_json": json.dumps(payload, allow_nan=False),
            },
            maxlen=maxlen,
            approximate=True,
        )
        return str(event_id)

    def read(self, run_id: str, last_id: str = "0-0", count: int = 100) -> list[ProgressEvent]:
        minimum_id = "0-0" if last_id == "0-0" else f"({last_id}"
        raw_events = self._client.xrange(
            self._keys.progress(run_id),
            min=minimum_id,
            max="+",
            count=count,
        )
        return [
            ProgressEvent(
                event_id=str(event_id),
                event_type=str(fields["event_type"]),
                payload=json.loads(fields["payload_json"]),
            )
            for event_id, fields in raw_events
        ]
