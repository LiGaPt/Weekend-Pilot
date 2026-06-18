export type InternalWorkflowTimingStage = {
  node_name: string;
  attempt_count: number;
  total_duration_ms: number;
};

export type InternalWorkflowTimingSummary = {
  schema_version: string;
  total_duration_ms: number;
  stage_count: number;
  stages: InternalWorkflowTimingStage[];
};

export type InternalToolEventSummary = {
  tool_name: string;
  tool_type: string;
  provider: string;
  status: string;
  cache_hit: boolean;
  latency_ms: number | null;
  created_at: string;
  request_preview: Record<string, unknown> | null;
  response_preview: Record<string, unknown> | null;
  error_preview: Record<string, unknown> | null;
};

export type InternalActionLedgerSummary = {
  action_type: string;
  target_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  request_preview: Record<string, unknown> | null;
  response_preview: Record<string, unknown> | null;
  error_preview: Record<string, unknown> | null;
};

export type InternalRecoveryAttemptSummary = {
  attempt_index: number;
  source_node: string;
  recovery_action: string;
  route_to: string | null;
  error_type: string | null;
  reason: string;
  retry_budget_before: number;
  retry_budget_after: number;
  status: string;
};

export type InternalRecoveryReplaySourceSummary = {
  case_id: string;
  benchmark_report_path: string;
};

export type InternalRecoveryPathSummary = {
  schema_version: string;
  attempt_count: number;
  max_attempts: number;
  attempts: InternalRecoveryAttemptSummary[];
  replay_source: InternalRecoveryReplaySourceSummary | null;
};

export type InternalObservabilitySummary = {
  trace_id: string | null;
  status: string | null;
  local_buffer_written: boolean | null;
  langsmith_enabled: boolean | null;
  langsmith_posted: boolean | null;
  local_buffer_error: Record<string, unknown> | null;
  langsmith_error: unknown;
};

export type InternalSelectedPlanReview = {
  plan_id: string;
  status: string | null;
  title: string | null;
  summary: string | null;
  activity: Record<string, unknown> | null;
  dining: Record<string, unknown> | null;
  timeline: Record<string, unknown>[];
  route: Record<string, unknown> | null;
  feasibility: Record<string, unknown> | null;
  action_manifest: Record<string, unknown> | null;
};

export type InternalBenchmarkTaxonomySummary = {
  suite: string;
  scenario_bucket: string;
  level: string;
  tags: string[];
  failure_mode: string | null;
};

export type InternalBenchmarkScoreSummary = {
  name: string;
  status: string;
  score: number;
  reason: string;
};

export type InternalBenchmarkArtifactSummary = {
  schema_version: string;
  case_id: string;
  title: string | null;
  workflow_backed: boolean | null;
  registered_suite_ids: string[];
  taxonomy: InternalBenchmarkTaxonomySummary | null;
  benchmark_status: string | null;
  overall_score: number | null;
  workflow_status: string | null;
  tool_event_count: number | null;
  action_count: number | null;
  failure_reasons: string[];
  score_summaries: InternalBenchmarkScoreSummary[];
  report_path: string | null;
};

export type InternalReleaseGateBenchmarkSummaryMatrix = {
  level_counts: Record<string, number>;
  tool_profile_counts: Record<string, number>;
  failure_mode_counts: Record<string, number>;
  tag_counts: Record<string, number>;
};

export type InternalBenchmarkTimingPercentileStats = {
  sample_count: number;
  min_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  mean_ms: number;
};

export type InternalBenchmarkStageTimingPercentileEntry = InternalBenchmarkTimingPercentileStats & {
  node_name: string;
  retry_case_count: number;
};

export type InternalBenchmarkTimingSummary = {
  schema_version: string;
  case_count: number;
  overall_total_duration_ms: InternalBenchmarkTimingPercentileStats | null;
  stages: InternalBenchmarkStageTimingPercentileEntry[];
};

export type InternalReleaseGateBenchmarkSummary = {
  schema_version: string;
  suite_id: string;
  suite_title: string;
  run_status: string;
  case_count: number;
  passed_count: number;
  failed_count: number;
  error_count: number;
  overall_score: number;
  matrix_summary: InternalReleaseGateBenchmarkSummaryMatrix;
  benchmark_timing_summary_present: boolean;
  benchmark_timing_summary: InternalBenchmarkTimingSummary | null;
  report_path: string;
};

export type IntegritySectionStatus = "ready" | "missing" | "invalid" | "partial";
export type SystemIntegrityStatus = "ready" | "degraded" | "missing_evidence" | "invalid_evidence";

export type SystemIntegrityEvidencePathSummary = {
  evidence_id: string;
  path: string;
  exists: boolean;
  required_for_summary: boolean;
  status: IntegritySectionStatus;
};

export type SystemIntegrityBenchmarkSummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  suite_id: string | null;
  gate_id: string | null;
  run_status: string | null;
  release_blocked: boolean | null;
  case_count: number | null;
  passed_count: number | null;
  failed_count: number | null;
  error_count: number | null;
  overall_score: number | null;
  blocking_failures: string[];
  integrity_coverage_summary: Record<string, number>;
  memory_mode_counts: Record<string, number>;
  conversation_mode_counts: Record<string, number>;
  failure_mode_counts: Record<string, number>;
  latest_report_path: string | null;
};

export type SystemIntegrityStabilitySummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  suite_id: string | null;
  gate_id: string | null;
  metric_version: string | null;
  requested_run_count: number | null;
  executed_run_count: number | null;
  window_size: number | null;
  window_count: number | null;
  discarded_tail_run_count: number | null;
  success_count: number | null;
  failure_count: number | null;
  error_count: number | null;
  success_at_1: number | null;
  pass_at_4: number | null;
  pass_pow_4: number | null;
  stable_enough: boolean | null;
  has_required_window: boolean | null;
  latest_report_path: string | null;
};

export type SystemIntegrityMemoryGovernanceSummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  source_suite_id: string | null;
  memory_case_count: number;
  passed_case_count: number;
  failed_case_count: number;
  error_case_count: number;
  all_memory_cases_passed: boolean;
  case_ids: string[];
  failing_case_ids: string[];
  latest_report_path: string | null;
};

export type SystemIntegrityFormalVerificationSummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  source_suite_id: string | null;
  case_count: number | null;
  passed_count: number | null;
  failed_count: number | null;
  error_count: number | null;
  overall_score: number | null;
  latest_report_path: string | null;
};

export type SystemIntegritySafeStopSummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  gate_id: string | null;
  suite_id: string | null;
  run_status: string | null;
  release_blocked: boolean | null;
  case_count: number | null;
  passed_count: number | null;
  failed_count: number | null;
  error_count: number | null;
  overall_score: number | null;
  latest_report_path: string | null;
};

export type SystemIntegrityRecoveryReplaySummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  case_id: string | null;
  review_status: string | null;
  check_count: number;
  passed_check_count: number;
  failed_check_count: number;
  latest_review_path: string | null;
  source_report_path: string | null;
  replay_report_path: string | null;
  recovery_actions: string[];
  attempt_count: number | null;
  max_attempts: number | null;
};

export type SystemIntegrityTimingSummary = {
  status: IntegritySectionStatus;
  reason: string | null;
  benchmark_timing_summary_present: boolean;
  benchmark_timing_summary: Record<string, unknown> | null;
  stability_window_size: number | null;
  stability_executed_run_count: number | null;
};

export type SystemIntegrityRedactionSummary = {
  internal_only: boolean;
  sanitized: boolean;
  relative_evidence_paths_only: boolean;
  forbidden_key_markers: string[];
};

export type InternalRunSummaryStageTimingDigest = {
  present: boolean;
  total_duration_ms: number | null;
  stage_count: number | null;
  slowest_stage_name: string | null;
  slowest_stage_duration_ms: number | null;
};

export type InternalRunSummaryLatestToolEvent = {
  tool_name: string;
  tool_type: string;
  provider: string;
  status: string;
  latency_ms: number | null;
  created_at: string;
};

export type InternalRunSummaryToolEventDigest = {
  total_count: number;
  read_count: number;
  write_count: number;
  status_counts: Record<string, number>;
  provider_counts: Record<string, number>;
  latest_event: InternalRunSummaryLatestToolEvent | null;
};

export type InternalRunSummaryRecoveryDigest = {
  entered_recovery: boolean;
  attempt_count: number;
  max_attempts: number;
  terminal_action: string | null;
  terminal_status: string | null;
  latest_error_type: string | null;
  replay_case_id: string | null;
};

export type InternalStructuredRunSummary = {
  schema_version: string;
  run_id: string;
  trace_id: string | null;
  workflow_status: string;
  selected_plan_id: string | null;
  plan_status: string | null;
  execution_status: string | null;
  feedback_status: string | null;
  stage_timing: InternalRunSummaryStageTimingDigest;
  tool_events: InternalRunSummaryToolEventDigest;
  recovery: InternalRunSummaryRecoveryDigest;
};

export type SystemIntegritySummary = {
  schema_version: string;
  status: SystemIntegrityStatus;
  benchmark_summary: SystemIntegrityBenchmarkSummary;
  stability_summary: SystemIntegrityStabilitySummary;
  formal_verification_summary: SystemIntegrityFormalVerificationSummary;
  memory_governance_summary: SystemIntegrityMemoryGovernanceSummary;
  safe_stop_summary: SystemIntegritySafeStopSummary;
  recovery_replay_summary: SystemIntegrityRecoveryReplaySummary;
  timing_summary: SystemIntegrityTimingSummary;
  redaction_summary: SystemIntegrityRedactionSummary;
  evidence_paths: SystemIntegrityEvidencePathSummary[];
};

export type InternalObservabilityRunSummary = {
  schema_version: string;
  run_id: string;
  status: string;
  trace_id: string | null;
  case_id: string | null;
  agent_version: string;
  prompt_version: string;
  tool_profile: string;
  world_profile: string;
  failure_profile: string | null;
  created_at: string;
  updated_at: string;
  tool_event_count: number;
  action_count: number;
  execution_status: string | null;
  feedback_status: string | null;
  observability_status: string | null;
  agent_roles: string[];
  node_history: string[];
  selected_plan_review: InternalSelectedPlanReview | null;
  tool_event_summaries: InternalToolEventSummary[];
  action_ledger_summaries: InternalActionLedgerSummary[];
  workflow_timing_summary: InternalWorkflowTimingSummary | null;
  observability_summary: InternalObservabilitySummary;
  benchmark_artifact_summary: InternalBenchmarkArtifactSummary | null;
  recovery_path_summary: InternalRecoveryPathSummary | null;
  run_summary: InternalStructuredRunSummary | null;
};
