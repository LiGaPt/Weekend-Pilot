import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLatestReleaseGateBenchmarkSummary, getObservabilityRun, getSystemIntegritySummary } from "./api";
import { FrontendApiError } from "../shared/http";
import type {
  InternalObservabilityRunSummary,
  InternalReleaseGateBenchmarkSummary,
  SystemIntegritySummary,
} from "./types";

const summary: InternalObservabilityRunSummary = {
  schema_version: "weekendpilot_internal_observability_run_v1",
  run_id: "run-1",
  status: "completed",
  trace_id: "trace-1",
  case_id: "web-demo",
  agent_version: "agent-v1",
  prompt_version: "prompt-v1",
  tool_profile: "mock_world",
  world_profile: "family_afternoon",
  failure_profile: null,
  created_at: "2026-05-19T13:01:33+08:00",
  updated_at: "2026-05-19T13:02:10+08:00",
  tool_event_count: 4,
  action_count: 1,
  execution_status: "succeeded",
  feedback_status: "completed",
  observability_status: "completed",
  agent_roles: ["supervisor", "discovery"],
  node_history: ["initialize", "wait_confirmation"],
  selected_plan_review: {
    plan_id: "plan-1",
    status: "selected",
    title: "Family Afternoon Plan",
    summary: "Indoor activity first, then a lighter dinner nearby.",
    activity: {
      name: "Family Science Center",
      category: "activity",
      address: "100 Science Road",
      tags: ["child_friendly", "indoor"],
    },
    dining: {
      name: "Light Table",
      category: "dining",
      address: "8 Dinner Street",
      tags: ["lighter_options"],
    },
    timeline: [
      {
        sequence: 1,
        title: "Indoor activity",
        start_label: "14:00",
        end_label: "16:00",
        duration_minutes: 120,
      },
    ],
    route: {
      mode: "driving",
      distance_meters: 3200,
      duration_minutes: 18,
      summary: "A short drive keeps the afternoon easy.",
    },
    feasibility: {
      is_feasible: true,
      reasons: ["Fits the requested afternoon window."],
      warnings: [],
      total_duration_minutes: 270,
      route_duration_minutes: 18,
      queue_wait_minutes: 5,
    },
    action_manifest: {
      source: "proposed_actions",
      action_count: 1,
      actions: [
        {
          action_ref: "draft_1_action_1",
          execution_order: 1,
          action_type: "reserve_restaurant",
          target_id: "restaurant_light_001",
          payload_preview: { party_size: 3 },
          reason: "Lock dinner seating after confirmation.",
        },
      ],
    },
  },
  tool_event_summaries: [],
  action_ledger_summaries: [],
  workflow_timing_summary: {
    schema_version: "workflow_timing_summary_v1",
    total_duration_ms: 42,
    stage_count: 1,
    stages: [{ node_name: "initialize", attempt_count: 1, total_duration_ms: 42 }],
  },
  observability_summary: {
    trace_id: "trace-1",
    status: "completed",
    local_buffer_written: true,
    langsmith_enabled: false,
    langsmith_posted: false,
    local_buffer_error: null,
    langsmith_error: null,
  },
  benchmark_artifact_summary: null,
  recovery_path_summary: null,
  run_summary: {
    schema_version: "weekendpilot_internal_run_summary_v1",
    run_id: "run-1",
    trace_id: "trace-1",
    workflow_status: "completed",
    selected_plan_id: "plan-1",
    plan_status: "selected",
    execution_status: "succeeded",
    feedback_status: "completed",
    stage_timing: {
      present: true,
      total_duration_ms: 42,
      stage_count: 1,
      slowest_stage_name: "initialize",
      slowest_stage_duration_ms: 42,
    },
    tool_events: {
      total_count: 4,
      read_count: 4,
      write_count: 0,
      status_counts: { completed: 4 },
      provider_counts: { mock_world: 4 },
      latest_event: {
        tool_name: "search_poi",
        tool_type: "read",
        provider: "mock_world",
        status: "completed",
        latency_ms: 12,
        created_at: "2026-05-19T13:01:40+08:00",
      },
    },
    recovery: {
      entered_recovery: false,
      attempt_count: 0,
      max_attempts: 0,
      terminal_action: null,
      terminal_status: null,
      latest_error_type: null,
      replay_case_id: null,
    },
  },
} as InternalObservabilityRunSummary;

const integritySummary: SystemIntegritySummary = {
  schema_version: "weekendpilot_system_integrity_summary_v1",
  status: "ready",
  benchmark_summary: {
    status: "ready",
    reason: null,
    suite_id: "v2_integrity",
    gate_id: "v2_integrity_gate",
    run_status: "passed",
    release_blocked: false,
    case_count: 20,
    passed_count: 20,
    failed_count: 0,
    error_count: 0,
    overall_score: 1,
    blocking_failures: [],
    integrity_coverage_summary: {},
    memory_mode_counts: {},
    conversation_mode_counts: {},
    failure_mode_counts: {},
    latest_report_path: "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
  },
  stability_summary: {
    status: "ready",
    reason: null,
    suite_id: "v2_integrity",
    gate_id: "v2_integrity_gate",
    metric_version: "passk_v0",
    requested_run_count: 4,
    executed_run_count: 4,
    window_size: 4,
    window_count: 1,
    discarded_tail_run_count: 0,
    success_count: 4,
    failure_count: 0,
    error_count: 0,
    success_at_1: 1,
    pass_at_4: 1,
    pass_pow_4: 1,
    stable_enough: true,
    has_required_window: true,
    latest_report_path: "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
  },
  formal_verification_summary: {
    status: "ready",
    reason: null,
    source_suite_id: "all_registered",
    case_count: 30,
    passed_count: 30,
    failed_count: 0,
    error_count: 0,
    overall_score: 1,
    latest_report_path: "var/formal-benchmarks/latest-all_registered-run-report.json",
  },
  memory_governance_summary: {
    status: "ready",
    reason: null,
    source_suite_id: "all_registered",
    memory_case_count: 2,
    passed_case_count: 2,
    failed_case_count: 0,
    error_case_count: 0,
    all_memory_cases_passed: true,
    case_ids: ["family_memory_override_v1", "family_memory_advisory_fill_v1"],
    failing_case_ids: [],
    latest_report_path: "var/formal-benchmarks/latest-all_registered-run-report.json",
  },
  safe_stop_summary: {
    status: "ready",
    reason: null,
    gate_id: "safe_stop_gate_v1",
    suite_id: "recovery_focused",
    run_status: "passed",
    release_blocked: false,
    case_count: 8,
    passed_count: 8,
    failed_count: 0,
    error_count: 0,
    overall_score: 1,
    latest_report_path: "var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json",
  },
  recovery_replay_summary: {
    status: "ready",
    reason: null,
    case_id: "family_route_failure_v1",
    review_status: "passed",
    check_count: 3,
    passed_check_count: 3,
    failed_check_count: 0,
    latest_review_path: "var/recovery-reviews/latest-family_route_failure_v1-review.json",
    source_report_path: "var/formal-benchmarks/family_route_failure_v1.json",
    replay_report_path: "var/recovery-reviews/family_route_failure_v1-replay.json",
    recovery_actions: ["stop_safely"],
    attempt_count: 1,
    max_attempts: 2,
  },
  timing_summary: {
    status: "ready",
    reason: null,
    benchmark_timing_summary_present: true,
    benchmark_timing_summary: { p50_ms: 390, p95_ms: 424 },
    stability_window_size: 4,
    stability_executed_run_count: 4,
  },
  redaction_summary: {
    internal_only: true,
    sanitized: true,
    relative_evidence_paths_only: true,
    forbidden_key_markers: ["api_key", "token"],
  },
  evidence_paths: [
    {
      evidence_id: "v2_integrity_gate",
      path: "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
      exists: true,
      required_for_summary: true,
      status: "ready",
    },
    {
      evidence_id: "safe_stop_gate_v1",
      path: "var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json",
      exists: true,
      required_for_summary: true,
      status: "ready",
    },
  ],
};

const releaseGateSummary: InternalReleaseGateBenchmarkSummary = {
  schema_version: "weekendpilot_internal_benchmark_summary_v1",
  suite_id: "release_gate_v1",
  suite_title: "Benchmark release gate v1",
  run_status: "passed",
  case_count: 15,
  passed_count: 15,
  failed_count: 0,
  error_count: 0,
  overall_score: 1,
  matrix_summary: {
    level_counts: { L1: 3, L2: 8, L3: 4 },
    tool_profile_counts: { mock_world: 15 },
    failure_mode_counts: { none: 14, route_unavailable: 1 },
    tag_counts: { memory_governance: 2 },
  },
  benchmark_timing_summary_present: true,
  benchmark_timing_summary: {
    schema_version: "benchmark_timing_summary_v1",
    case_count: 15,
    overall_total_duration_ms: {
      sample_count: 15,
      min_ms: 320,
      p50_ms: 390,
      p95_ms: 424,
      p99_ms: 424,
      max_ms: 424,
      mean_ms: 387.8,
    },
    stages: [
      {
        node_name: "pre_flight_check_availability",
        sample_count: 15,
        retry_case_count: 0,
        min_ms: 12,
        p50_ms: 20,
        p95_ms: 36,
        p99_ms: 36,
        max_ms: 36,
        mean_ms: 19.6,
      },
    ],
  },
  report_path: "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
};

describe("internal observability API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(summary), { status: 200 })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the internal observability endpoint with the run ID", async () => {
    const result = await getObservabilityRun("run-1");

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/internal/runs/run-1/observability");
    expect(result.run_summary?.stage_timing.slowest_stage_name).toBe("initialize");
    expect(result.run_summary?.tool_events.total_count).toBe(4);
    expect(result.selected_plan_review?.action_manifest?.actions).toHaveLength(1);
  });

  it("calls the system integrity summary endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(integritySummary), { status: 200 })));

    await getSystemIntegritySummary();

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/internal/system/integrity-summary");
  });

  it("calls the latest release-gate summary endpoint and preserves timing fields", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(releaseGateSummary), { status: 200 })));

    const result = await getLatestReleaseGateBenchmarkSummary();

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/internal/benchmarks/release-gate-v1/summary");
    expect(result.benchmark_timing_summary_present).toBe(true);
    expect(result.benchmark_timing_summary?.overall_total_duration_ms.p95_ms).toBe(424);
    expect(result.benchmark_timing_summary?.stages[0].node_name).toBe("pre_flight_check_availability");
  });

  it("throws FrontendApiError with a reviewer-readable message for connection failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connect ECONNREFUSED 127.0.0.1:8000");
      }),
    );

    await expect(getObservabilityRun("run-1")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 0,
      message: "无法连接内部观测服务，请确认后端正在运行。",
    } satisfies Partial<FrontendApiError>);
  });

  it("throws FrontendApiError with backend detail for not found responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Observability run was not found." }), { status: 404 })),
    );

    await expect(getObservabilityRun("missing")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 404,
      message: "未找到对应的内部观测运行。",
    } satisfies Partial<FrontendApiError>);
  });
});
