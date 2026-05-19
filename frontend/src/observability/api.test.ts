import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoApiError } from "../api/demo";
import { getObservabilityRun } from "./api";
import type { InternalObservabilityRunSummary } from "./types";

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

  it("throws DemoApiError with a reviewer-readable message for connection failures", async () => {
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
    } satisfies Partial<DemoApiError>);
  });

  it("throws DemoApiError with backend detail for not found responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Observability run was not found." }), { status: 404 })),
    );

    await expect(getObservabilityRun("missing")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 404,
      message: "未找到对应的内部观测运行。",
    } satisfies Partial<DemoApiError>);
  });
});
