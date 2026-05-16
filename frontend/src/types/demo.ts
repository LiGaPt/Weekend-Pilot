export type DemoStartRunRequest = {
  user_input: string;
  external_user_id: string;
  display_name: string;
  case_id: string;
  selected_plan_index: number;
};

export type DemoCandidateSummary = {
  candidate_id?: string | null;
  name?: string | null;
  category?: string | null;
  provider?: string | null;
  address?: string | null;
  tags?: string[];
  evidence?: Record<string, unknown>;
};

export type DemoTimelineItem = {
  sequence?: number | null;
  item_type?: string | null;
  title?: string | null;
  candidate_id?: string | null;
  duration_minutes?: number | null;
  start_label?: string | null;
  end_label?: string | null;
  notes?: string[];
};

export type DemoRouteSummary = {
  origin_candidate_id?: string | null;
  destination_candidate_id?: string | null;
  provider?: string | null;
  mode?: string | null;
  distance_meters?: number | null;
  duration_minutes?: number | null;
  summary?: string | null;
};

export type DemoFeasibilitySummary = {
  is_feasible?: boolean | null;
  reasons?: string[];
  warnings?: string[];
  total_duration_minutes?: number | null;
  route_duration_minutes?: number | null;
  queue_wait_minutes?: number | null;
};

export type DemoProposedActionSummary = {
  action_ref?: string | null;
  action_type?: string | null;
  target_id?: string | null;
  payload?: Record<string, unknown>;
  requires_confirmation?: boolean | null;
  reason?: string | null;
};

export type DemoConfirmationSummary = {
  status?: string | null;
  confirmed_by?: string | null;
  declined_by?: string | null;
  source?: string | null;
  confirmed_at?: string | null;
  declined_at?: string | null;
  reason?: string | null;
  action_count?: number | null;
};

export type DemoExecutionSummary = {
  status?: string | null;
  plan_status?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  succeeded_count?: number | null;
  failed_count?: number | null;
  action_results?: Record<string, unknown>[];
};

export type DemoFeedbackSummary = {
  status?: string | null;
  run_status?: string | null;
  headline?: string | null;
  message?: string | null;
  completed_actions?: Record<string, unknown>[];
  failed_actions?: Record<string, unknown>[];
  next_steps?: string[];
  generated_at?: string | null;
};

export type DemoPlanPreview = {
  plan_id: string;
  status: string;
  selected: boolean;
  title?: string | null;
  summary?: string | null;
  activity?: DemoCandidateSummary | null;
  dining?: DemoCandidateSummary | null;
  timeline?: DemoTimelineItem[];
  route?: DemoRouteSummary | null;
  feasibility?: DemoFeasibilitySummary | null;
  proposed_actions?: DemoProposedActionSummary[];
  confirmation?: DemoConfirmationSummary | null;
  execution?: DemoExecutionSummary | null;
  feedback?: DemoFeedbackSummary | null;
};

export type DemoRunSummary = {
  run_id: string;
  trace_id: string | null;
  status: string;
  selected_plan_id: string | null;
  plans: DemoPlanPreview[];
  node_history: string[];
  tool_event_count: number;
  action_count: number;
  execution_status: string | null;
  feedback_status: string | null;
  observability_status: string | null;
  agent_roles: string[];
  error: Record<string, unknown> | null;
};
