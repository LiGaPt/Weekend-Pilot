from __future__ import annotations

import hashlib
import json
from typing import Any


def build_tool_cache_key(tool_name: str, provider: str, payload: dict[str, Any]) -> str:
    normalized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(normalized_payload.encode("utf-8")).hexdigest()
    return f"tool:{provider}:{tool_name}:{digest}"
