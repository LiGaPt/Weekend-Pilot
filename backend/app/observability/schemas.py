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


class InternalToolEventSummary(BaseModel):
    tool_name: str
    tool_type: str
    provider: str
    status: str
    cache_hit: bool
    latency_ms: int | None = None
    created_at: datetime
    request_preview: dict[str, Any] | None = None
    response_preview: dict[str, Any] | None = None
    error_preview: dict[str, Any] | None = None


class InternalActionLedgerSummary(BaseModel):
    action_type: str
    target_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    request_preview: dict[str, Any] | None = None
    response_preview: dict[str, Any] | None = None
    error_preview: dict[str, Any] | None = None


class InternalRecoveryAttemptSummary(BaseModel):
    attempt_index: int
    source_node: str
    recovery_action: str
    route_to: str | None = None
    error_type: str | None = None
    reason: str
    retry_budget_before: int
    retry_budget_after: int
    status: str


class InternalRecoveryReplaySourceSummary(BaseModel):
    case_id: str
    benchmark_report_path: str


class InternalRecoveryPathSummary(BaseModel):
    schema_version: str = "weekendpilot_internal_recovery_path_v1"
    attempt_count: int
    max_attempts: int
    attempts: list[InternalRecoveryAttemptSummary] = Field(default_factory=list)
    replay_source: InternalRecoveryReplaySourceSummary | None = None


class InternalBenchmarkTaxonomySummary(BaseModel):
    suite: str
    scenario_bucket: str
    level: str
    tags: list[str] = Field(default_factory=list)
    failure_mode: str | None = None


class InternalBenchmarkScoreSummary(BaseModel):
    name: str
    status: str
    score: float
    reason: str


class InternalBenchmarkArtifactSummary(BaseModel):
    schema_version: str = "weekendpilot_internal_benchmark_artifact_v1"
    case_id: str
    title: str | None = None
    workflow_backed: bool | None = None
    registered_suite_ids: list[str] = Field(default_factory=list)
    taxonomy: InternalBenchmarkTaxonomySummary | None = None
    benchmark_status: str | None = None
    overall_score: float | None = None
    workflow_status: str | None = None
    tool_event_count: int | None = None
    action_count: int | None = None
    failure_reasons: list[str] = Field(default_factory=list)
    score_summaries: list[InternalBenchmarkScoreSummary] = Field(default_factory=list)
    report_path: str | None = None


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
    tool_event_summaries: list[InternalToolEventSummary] = Field(default_factory=list)
    action_ledger_summaries: list[InternalActionLedgerSummary] = Field(default_factory=list)
    workflow_timing_summary: Any | None = None
    observability_summary: InternalObservabilitySummary = Field(default_factory=InternalObservabilitySummary)
    benchmark_artifact_summary: InternalBenchmarkArtifactSummary | None = None
    recovery_path_summary: InternalRecoveryPathSummary | None = None
