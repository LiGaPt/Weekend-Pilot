import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoApiError, confirmRun, declineRun, getRun, startRun } from "./demo";
import type { DemoRunSummary } from "../types/demo";

const summary: DemoRunSummary = {
  run_id: "run-1",
  status: "awaiting_confirmation",
  selected_plan_id: "plan-1",
  plan_version: {
    version_number: 1,
    version_label: "v1",
    source_run_id: null,
    source_selected_plan_id: null,
  },
  plans: [],
  action_count: 0,
  execution_status: null,
  feedback_status: null,
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
          reason: "用户选择暂不继续。",
        }),
      }),
    );
  });

  it("throws DemoApiError with localized message for connection failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connect ECONNREFUSED 127.0.0.1:8000");
      }),
    );

    await expect(getRun("run-1")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 0,
      message: "无法连接演示服务，请确认后端正在运行。",
    } satisfies Partial<DemoApiError>);
  });

  it("throws DemoApiError with backend detail for non-2xx responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Run not found." }), { status: 404 })),
    );

    await expect(getRun("missing")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 404,
      message: "未找到对应的演示运行。",
    } satisfies Partial<DemoApiError>);
  });
});
