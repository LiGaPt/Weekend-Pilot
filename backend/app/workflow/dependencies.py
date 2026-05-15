from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache


class WeekendPilotWorkflowDependencies(BaseModel):
    session: Session
    cache: JsonRedisCache
    rate_limiter: FixedWindowRateLimiter
    trace_buffer_path: Path | str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
