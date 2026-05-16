import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoApiError, confirmRun, declineRun, getRun, startRun } from "./demo";
import type { DemoRunSummary } from "../types/demo";

const summary: DemoRunSummary = {
  run_id: "run-1",
  trace_id: "trace-1",
  status: "awaiting_confirmation",
  selected_plan_id: "plan-1",
  plans: [],
  node_history: [],
  tool_event_count: 0,
  action_count: 0,
  execution_status: null,
  feedback_status: null,
  observability_status: null,
  agent_roles: [],
  error: null,
};

describe("demo API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(summary), { status: 200 })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts startRun to /demo/runs with the expected body", async () => {
    await startRun({
      user_input: "Family afternoon",
      external_user_id: "web-demo-user",
      display_name: "Web Demo User",
      case_id: "web-demo",
      selected_plan_index: 0,
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/demo/runs",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: "Family afternoon",
          external_user_id: "web-demo-user",
          display_name: "Web Demo User",
          case_id: "web-demo",
          selected_plan_index: 0,
        }),
      }),
    );
  });

  it("calls getRun with the run ID", async () => {
    await getRun("run-1");

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/demo/runs/run-1");
  });

  it("posts confirmRun with the selected plan ID", async () => {
    await confirmRun("run-1", "plan-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/demo/runs/run-1/confirm",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ plan_id: "plan-1", confirmed_by: "web-demo-user" }),
      }),
    );
  });

  it("posts declineRun with the selected plan ID and reason", async () => {
    await declineRun("run-1", "plan-1");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/demo/runs/run-1/decline",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          plan_id: "plan-1",
          declined_by: "web-demo-user",
          reason: "User chose not to continue.",
        }),
      }),
    );
  });

  it("throws DemoApiError with backend detail for non-2xx responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Run not found." }), { status: 404 })),
    );

    await expect(getRun("missing")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 404,
      message: "Run not found.",
    } satisfies Partial<DemoApiError>);
  });
});
