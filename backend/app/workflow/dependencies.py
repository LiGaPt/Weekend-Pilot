from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache
from backend.app.tool_gateway import ToolFailureInjector


class WeekendPilotWorkflowDependencies(BaseModel):
    session: Session
    cache: JsonRedisCache
    rate_limiter: FixedWindowRateLimiter
    world_profile: str = "family_afternoon"
    failure_injector: ToolFailureInjector | None = None
    trace_buffer_path: Path | str | None = None
    settings: Settings | None = None
    llm_client: Any | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
