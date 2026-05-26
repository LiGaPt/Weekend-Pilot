import { expect, test } from "@playwright/test";

const benchmarkSummary = {
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
    tag_counts: {
      memory_advisory: 1,
      memory_expired: 1,
      memory_governance: 2,
      memory_override: 1,
    },
  },
  report_path: "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
};

const observabilityRun = {
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
  tool_event_summaries: [
    {
      tool_name: "search_poi",
      tool_type: "read",
      provider: "mock_world",
      status: "completed",
      cache_hit: false,
      latency_ms: 12,
      created_at: "2026-05-19T13:01:40+08:00",
      request_preview: { query: "museum" },
      response_preview: { candidate_count: 2 },
      error_preview: null,
    },
  ],
  action_ledger_summaries: [
    {
      action_type: "reserve_restaurant",
      target_id: "green-table",
      status: "succeeded",
      created_at: "2026-05-19T13:02:00+08:00",
      updated_at: "2026-05-19T13:02:10+08:00",
      request_preview: { plan_id: "[REDACTED]" },
      response_preview: { result: "ok" },
      error_preview: null,
    },
  ],
  workflow_timing_summary: {
    schema_version: "workflow_timing_summary_v1",
    total_duration_ms: 42,
    stage_count: 2,
    stages: [
      { node_name: "initialize", attempt_count: 1, total_duration_ms: 5 },
      { node_name: "execute_searches", attempt_count: 2, total_duration_ms: 37 },
    ],
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
  benchmark_artifact_summary: {
    schema_version: "weekendpilot_internal_benchmark_artifact_v1",
    case_id: "solo_afternoon_v1",
    title: "Solo afternoon local-life plan",
    workflow_backed: true,
    registered_suite_ids: ["default", "all_registered"],
    taxonomy: {
      suite: "locallife_bench_v1",
      scenario_bucket: "solo",
      level: "L1",
      tags: ["baseline", "light_activity", "light_meal"],
      failure_mode: null,
    },
    benchmark_status: "passed",
    overall_score: 0.9583,
    workflow_status: "completed",
    tool_event_count: 8,
    action_count: 1,
    failure_reasons: [],
    score_summaries: [
      {
        name: "workflow_path",
        status: "passed",
        score: 1,
        reason: "Workflow reached the expected path.",
      },
    ],
    report_path: "var/benchmarks/solo_afternoon_v1.json",
  },
  recovery_path_summary: {
    schema_version: "weekendpilot_internal_recovery_path_v1",
    attempt_count: 1,
    max_attempts: 1,
    attempts: [
      {
        attempt_index: 1,
        source_node: "semantic_validator",
        recovery_action: "stop_safely",
        route_to: null,
        error_type: "route_infeasible",
        reason: "Recovery stopped after route failure.",
        retry_budget_before: 0,
        retry_budget_after: 0,
        status: "stopped",
      },
    ],
    replay_source: {
      case_id: "family_route_failure_v1",
      benchmark_report_path: "var/benchmarks/family_route_failure_v1.json",
    },
  },
};

test.describe("internal observability surface", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Internal surface smoke runs once on desktop.");
  });

  test("loads on the dedicated internal frontend origin", async ({ page }) => {
    await page.route("**/internal/benchmarks/release-gate-v1/summary", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(benchmarkSummary),
      });
    });

    await page.route("**/internal/runs/run-1/observability", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(observabilityRun),
      });
    });

    await page.goto("http://127.0.0.1:5174/");

    await expect(page.getByRole("heading", { name: "Internal Observability Review" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Benchmark Summary" })).toBeVisible();
    await expect(page.getByText("Benchmark release gate v1")).toBeVisible();
    await expect(page.getByText("var/formal-benchmarks/latest-release_gate_v1-run-report.json")).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Run ID" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Load Run" })).toBeVisible();
    await expect(page.getByTestId("start-button")).toHaveCount(0);
    await expect(page.getByTestId("read-profile-select")).toHaveCount(0);

    await page.getByRole("textbox", { name: "Run ID" }).fill("run-1");
    await page.getByRole("button", { name: "Load Run" }).click();

    await expect(page.getByRole("heading", { name: "Trace Summary" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recovery Visualization" })).toBeVisible();
    await expect(page.getByText("Recovery stopped after route failure.")).toBeVisible();
  });
});
