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

export type InternalObservabilitySummary = {
  trace_id: string | null;
  status: string | null;
  local_buffer_written: boolean | null;
  langsmith_enabled: boolean | null;
  langsmith_posted: boolean | null;
  local_buffer_error: Record<string, unknown> | null;
  langsmith_error: unknown;
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
  workflow_timing_summary: InternalWorkflowTimingSummary | null;
  observability_summary: InternalObservabilitySummary;
};
