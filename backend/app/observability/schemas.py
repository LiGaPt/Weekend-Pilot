from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.planning.memory_query_policy import MemoryPolicyAuditSummary
from backend.app.observability.summary import PreviewDiagnostics


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
    memory_policy_summary: MemoryPolicyAuditSummary | None = None
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
    preview_diagnostics: PreviewDiagnostics | None = None
    tool_event_summaries: list[InternalToolEventSummary] = Field(default_factory=list)
    action_ledger_summaries: list[InternalActionLedgerSummary] = Field(default_factory=list)
    workflow_timing_summary: Any | None = None
    observability_summary: InternalObservabilitySummary = Field(default_factory=InternalObservabilitySummary)
    benchmark_artifact_summary: InternalBenchmarkArtifactSummary | None = None
    recovery_path_summary: InternalRecoveryPathSummary | None = None


IntegritySectionStatus = Literal["ready", "missing", "invalid", "partial"]
SystemIntegrityStatus = Literal["ready", "degraded", "missing_evidence", "invalid_evidence"]


class SystemIntegrityEvidencePathSummary(BaseModel):
    evidence_id: str
    path: str
    exists: bool
    required_for_summary: bool
    status: IntegritySectionStatus


class SystemIntegrityBenchmarkSummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    suite_id: str | None = None
    gate_id: str | None = None
    run_status: str | None = None
    release_blocked: bool | None = None
    case_count: int | None = None
    passed_count: int | None = None
    failed_count: int | None = None
    error_count: int | None = None
    overall_score: float | None = None
    blocking_failures: list[str] = Field(default_factory=list)
    integrity_coverage_summary: dict[str, int] = Field(default_factory=dict)
    memory_mode_counts: dict[str, int] = Field(default_factory=dict)
    conversation_mode_counts: dict[str, int] = Field(default_factory=dict)
    failure_mode_counts: dict[str, int] = Field(default_factory=dict)
    latest_report_path: str | None = None


class SystemIntegrityStabilitySummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    suite_id: str | None = None
    gate_id: str | None = None
    metric_version: str | None = None
    requested_run_count: int | None = None
    executed_run_count: int | None = None
    window_size: int | None = None
    window_count: int | None = None
    discarded_tail_run_count: int | None = None
    success_count: int | None = None
    failure_count: int | None = None
    error_count: int | None = None
    success_at_1: float | None = None
    pass_at_4: float | None = None
    pass_pow_4: float | None = None
    stable_enough: bool | None = None
    has_required_window: bool | None = None
    latest_report_path: str | None = None


class SystemIntegrityMemoryGovernanceSummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    source_suite_id: str | None = None
    memory_case_count: int = 0
    passed_case_count: int = 0
    failed_case_count: int = 0
    error_case_count: int = 0
    all_memory_cases_passed: bool = False
    case_ids: list[str] = Field(default_factory=list)
    failing_case_ids: list[str] = Field(default_factory=list)
    latest_report_path: str | None = None


class SystemIntegrityFormalVerificationSummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    source_suite_id: str | None = None
    case_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    overall_score: float | None = None
    latest_report_path: str | None = None


class SystemIntegrityRecoveryReplaySummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    case_id: str | None = None
    review_status: str | None = None
    check_count: int = 0
    passed_check_count: int = 0
    failed_check_count: int = 0
    latest_review_path: str | None = None
    source_report_path: str | None = None
    replay_report_path: str | None = None
    recovery_actions: list[str] = Field(default_factory=list)
    attempt_count: int | None = None
    max_attempts: int | None = None


class SystemIntegritySafeStopSummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    gate_id: str | None = None
    suite_id: str | None = None
    run_status: str | None = None
    release_blocked: bool | None = None
    case_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    overall_score: float | None = None
    latest_report_path: str | None = None


class SystemIntegrityTimingSummary(BaseModel):
    status: IntegritySectionStatus
    reason: str | None = None
    benchmark_timing_summary_present: bool = False
    benchmark_timing_summary: Any | None = None
    stability_window_size: int | None = None
    stability_executed_run_count: int | None = None


class SystemIntegrityRedactionSummary(BaseModel):
    internal_only: bool = True
    sanitized: bool = True
    relative_evidence_paths_only: bool = True
    forbidden_key_markers: list[str] = Field(default_factory=list)


class SystemIntegritySummary(BaseModel):
    schema_version: str = "weekendpilot_system_integrity_summary_v1"
    status: SystemIntegrityStatus
    benchmark_summary: SystemIntegrityBenchmarkSummary
    stability_summary: SystemIntegrityStabilitySummary
    formal_verification_summary: SystemIntegrityFormalVerificationSummary
    memory_governance_summary: SystemIntegrityMemoryGovernanceSummary
    safe_stop_summary: SystemIntegritySafeStopSummary
    recovery_replay_summary: SystemIntegrityRecoveryReplaySummary
    timing_summary: SystemIntegrityTimingSummary
    redaction_summary: SystemIntegrityRedactionSummary
    evidence_paths: list[SystemIntegrityEvidencePathSummary] = Field(default_factory=list)
