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
  report_path: string;
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
  tool_event_summaries: InternalToolEventSummary[];
  action_ledger_summaries: InternalActionLedgerSummary[];
  workflow_timing_summary: InternalWorkflowTimingSummary | null;
  observability_summary: InternalObservabilitySummary;
  benchmark_artifact_summary: InternalBenchmarkArtifactSummary | null;
  recovery_path_summary: InternalRecoveryPathSummary | null;
};
