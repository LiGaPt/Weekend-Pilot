import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getObservabilityRun, getSystemIntegritySummary } from "./api";
import { FrontendApiError } from "../shared/http";
import type { InternalObservabilityRunSummary, SystemIntegritySummary } from "./types";

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
};

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
    case_count: 18,
    passed_count: 18,
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
  ],
};

describe("internal observability API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(summary), { status: 200 })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the internal observability endpoint with the run ID", async () => {
    await getObservabilityRun("run-1");

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/internal/runs/run-1/observability");
  });

  it("calls the system integrity summary endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(integritySummary), { status: 200 })));

    await getSystemIntegritySummary();

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/internal/system/integrity-summary");
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
