import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getLatestReleaseGateBenchmarkSummary,
  getObservabilityRun,
} from "./api";
import { FrontendApiError } from "../shared/http";
import { ObservabilityPage } from "./ObservabilityPage";
import type {
  InternalObservabilityRunSummary,
  InternalReleaseGateBenchmarkSummary,
} from "./types";

vi.mock("./api", () => ({
  getObservabilityRun: vi.fn(),
  getLatestReleaseGateBenchmarkSummary: vi.fn(),
}));

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

const benchmarkArtifactSummary = summary.benchmark_artifact_summary!;
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
    tag_counts: {
      memory_advisory: 1,
      memory_expired: 1,
      memory_governance: 2,
      memory_override: 1,
    },
  },
  report_path: "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
};

describe("ObservabilityPage", () => {
  beforeEach(() => {
    vi.mocked(getObservabilityRun).mockReset();
    vi.mocked(getLatestReleaseGateBenchmarkSummary).mockReset();
    vi.mocked(getLatestReleaseGateBenchmarkSummary).mockResolvedValue(releaseGateSummary);
  });

  it("renders the initial empty state and benchmark summary panel", async () => {
    render(<ObservabilityPage />);

    expect(screen.getByRole("heading", { name: "Internal Observability Review" })).toBeInTheDocument();
    expect(screen.getByText("Paste a run ID to inspect the internal workflow summary.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Benchmark Summary" })).toBeInTheDocument();
    expect(screen.getByText("Benchmark release gate v1")).toBeInTheDocument();
    expect(screen.getByText("var/formal-benchmarks/latest-release_gate_v1-run-report.json")).toBeInTheDocument();
  });

  it("validates empty run IDs before loading", async () => {
    const user = userEvent.setup();
    render(<ObservabilityPage />);

    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(getObservabilityRun).not.toHaveBeenCalled();
    expect(screen.getByText("Enter a run ID before loading.")).toBeInTheDocument();
  });

  it("loads and renders the internal observability summary", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockResolvedValue(summary);
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(await screen.findByRole("heading", { name: "Trace Summary" })).toBeInTheDocument();
    expect(await screen.findAllByText("trace-1")).toHaveLength(2);
    expect(screen.getByText("execute_searches")).toBeInTheDocument();
    expect(screen.getByText("supervisor")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tool Events" })).toBeInTheDocument();
    expect(screen.getByText("search_poi")).toBeInTheDocument();
    expect(screen.getByText("green-table")).toBeInTheDocument();
    expect(screen.getByText(/\"query\":\"museum\"/)).toBeInTheDocument();
    expect(screen.getByText(/\"plan_id\":\"\[REDACTED\]\"/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Benchmark Artifacts" })).toBeInTheDocument();
    expect(screen.getByText("solo_afternoon_v1")).toBeInTheDocument();
    expect(screen.getByText("Solo afternoon local-life plan")).toBeInTheDocument();
    expect(screen.getByText("var/benchmarks/solo_afternoon_v1.json")).toBeInTheDocument();
    expect(screen.getByText("locallife_bench_v1")).toBeInTheDocument();
    expect(screen.getByText("light_activity")).toBeInTheDocument();
    expect(screen.getByText("Workflow reached the expected path.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recovery Visualization" })).toBeInTheDocument();
    expect(screen.getByText("stop_safely")).toBeInTheDocument();
    expect(screen.getByText("Recovery stopped after route failure.")).toBeInTheDocument();
    expect(screen.getByText("family_route_failure_v1")).toBeInTheDocument();
    expect(screen.getByText("var/benchmarks/family_route_failure_v1.json")).toBeInTheDocument();
  });

  it("shows a reviewer-readable missing state when the latest benchmark report is unavailable", async () => {
    vi.mocked(getLatestReleaseGateBenchmarkSummary).mockRejectedValue(
      new FrontendApiError(
        "Latest release_gate_v1 benchmark summary was not found. Run python scripts/run_benchmark_release_gate.py first.",
        404,
      ),
    );
    render(<ObservabilityPage />);

    expect(
      await screen.findByText(
        "Latest release_gate_v1 benchmark summary was not found. Run python scripts/run_benchmark_release_gate.py first.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a neutral state when workflow timing is missing", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockResolvedValue({
      ...summary,
      workflow_timing_summary: null,
    });
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(await screen.findByText("No workflow timing summary is available for this run yet.")).toBeInTheDocument();
  });

  it("shows a neutral state when benchmark metadata is missing", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockResolvedValue({
      ...summary,
      benchmark_artifact_summary: null,
    });
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(await screen.findByText("This run does not have benchmark artifact metadata.")).toBeInTheDocument();
  });

  it("shows a partial benchmark state when only benchmark identity is available", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockResolvedValue({
      ...summary,
      benchmark_artifact_summary: {
        ...benchmarkArtifactSummary,
        benchmark_status: null,
        overall_score: null,
        workflow_status: null,
        tool_event_count: null,
        action_count: null,
        failure_reasons: [],
        score_summaries: [],
        report_path: null,
      },
    });
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(await screen.findByText("Solo afternoon local-life plan")).toBeInTheDocument();
    expect(screen.getByText("Detailed benchmark scoring is not available for this run yet.")).toBeInTheDocument();
  });

  it("shows a neutral state when recovery metadata is missing", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockResolvedValue({
      ...summary,
      recovery_path_summary: null,
    });
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(await screen.findByText("This run did not enter bounded recovery.")).toBeInTheDocument();
  });

  it("shows a partial recovery state when no valid recovery attempts are available", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockResolvedValue({
      ...summary,
      recovery_path_summary: {
        ...summary.recovery_path_summary!,
        attempt_count: 0,
        attempts: [],
        replay_source: null,
      },
    });
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    expect(
      await screen.findByText("Recovery metadata exists for this run, but no valid recovery attempts are available."),
    ).toBeInTheDocument();
  });

  it("renders not found errors from the backend", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockRejectedValue(new FrontendApiError("未找到对应的内部观测运行。", 404));
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "missing");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("未找到对应的内部观测运行。")).toBeInTheDocument();
  });

  it("renders a generic error for unexpected failures", async () => {
    const user = userEvent.setup();
    vi.mocked(getObservabilityRun).mockRejectedValue(new Error("boom"));
    render(<ObservabilityPage />);

    await user.type(screen.getByRole("textbox", { name: "Run ID" }), "run-1");
    await user.click(screen.getByRole("button", { name: "Load Run" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Internal observability request failed. Please try again.")).toBeInTheDocument();
  });
});
