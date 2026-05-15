from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RunTraceContext(BaseModel):
    run_id: UUID
    trace_id: str
    project_name: str
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    failure_profile: str | None = None
    case_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LangSmithPostStatus(BaseModel):
    enabled: bool
    posted: bool = False
    error: str | None = None


class TraceRecordResult(BaseModel):
    run_id: UUID | None = None
    trace_id: str | None = None
    status: str
    local_buffer_written: bool = False
    local_buffer_path: str | None = None
    langsmith_enabled: bool = False
    langsmith_posted: bool = False
    error_json: dict[str, Any] | None = None
    recorder_version: str
