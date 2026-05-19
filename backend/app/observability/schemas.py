from __future__ import annotations

from datetime import datetime
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


class InternalObservabilitySummary(BaseModel):
    trace_id: str | None = None
    status: str | None = None
    local_buffer_written: bool | None = None
    langsmith_enabled: bool | None = None
    langsmith_posted: bool | None = None
    local_buffer_error: dict[str, Any] | None = None
    langsmith_error: Any | None = None


class InternalObservabilityRunSummary(BaseModel):
    schema_version: str = "weekendpilot_internal_observability_run_v1"
    run_id: UUID
    status: str
    trace_id: str | None = None
    case_id: str | None = None
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    failure_profile: str | None = None
    created_at: datetime
    updated_at: datetime
    tool_event_count: int = 0
    action_count: int = 0
    execution_status: str | None = None
    feedback_status: str | None = None
    observability_status: str | None = None
    agent_roles: list[str] = Field(default_factory=list)
    node_history: list[str] = Field(default_factory=list)
    workflow_timing_summary: Any | None = None
    observability_summary: InternalObservabilitySummary = Field(default_factory=InternalObservabilitySummary)
