import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clarifyRun, confirmRun, declineRun, getRun, replanRun, startRun } from "./demo";
import { FrontendApiError } from "../shared/http";
import type { DemoRunSummary } from "../types/demo";

const summary: DemoRunSummary = {
  run_id: "run-1",
  status: "awaiting_confirmation",
  read_profile: "mock_world",
  selected_plan_id: "plan-1",
  plan_version: {
    version_number: 1,
    version_label: "v1",
    source_run_id: null,
    source_selected_plan_id: null,
  },
  plans: [
    {
      plan_id: "plan-1",
      status: "reviewed",
      selected: true,
      title: "Family-friendly afternoon",
      summary: "A short family outing with a lighter dinner option.",
      proposed_actions: [],
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
            reason: "Confirm to lock dinner seating.",
          },
        ],
      },
    },
  ],
  action_count: 0,
  execution_status: null,
  feedback_status: null,
  error: null,
  clarification: null,
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
      read_profile: "amap",
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
          read_profile: "amap",
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
          reason: "\u7528\u6237\u9009\u62e9\u6682\u4e0d\u7ee7\u7eed\u3002",
        }),
      }),
    );
  });

  it("posts clarifyRun with the expected body", async () => {
    await clarifyRun("run-clarify-1", {
      user_input: "今天下午一个人出门玩几个小时，别太远。",
      selected_plan_index: 0,
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/demo/runs/run-clarify-1/clarify",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: "今天下午一个人出门玩几个小时，别太远。",
          selected_plan_index: 0,
        }),
      }),
    );
  });

  it("posts replanRun with the expected body", async () => {
    await replanRun("run-1", {
      user_input: "Keep it nearby, but make it a solo outing this time.",
      selected_plan_index: 0,
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/demo/runs/run-1/replan",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: "Keep it nearby, but make it a solo outing this time.",
          selected_plan_index: 0,
        }),
      }),
    );
  });

  it("throws FrontendApiError with localized message for connection failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connect ECONNREFUSED 127.0.0.1:8000");
      }),
    );

    await expect(getRun("run-1")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 0,
      message: "\u65e0\u6cd5\u8fde\u63a5\u6f14\u793a\u670d\u52a1\uff0c\u8bf7\u786e\u8ba4\u540e\u7aef\u6b63\u5728\u8fd0\u884c\u3002",
    } satisfies Partial<FrontendApiError>);
  });

  it("throws FrontendApiError with backend detail for non-2xx responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Run not found." }), { status: 404 })),
    );

    await expect(getRun("missing")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 404,
      message: "\u672a\u627e\u5230\u5bf9\u5e94\u7684\u6f14\u793a\u8fd0\u884c\u3002",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes the AMAP configuration error detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ detail: "AMAP read path is not configured for this environment." }),
            { status: 500 },
          ),
      ),
    );

    await expect(getRun("run-1")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 500,
      message: "\u672c\u5730\u73af\u5883\u672a\u914d\u7f6e AMap \u53ea\u8bfb\u9884\u89c8\u6240\u9700\u7684\u5bc6\u94a5\u3002",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes the AMAP read-only confirm rejection detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ detail: "AMAP read-only demo runs cannot be confirmed." }),
            { status: 409 },
          ),
      ),
    );

    await expect(confirmRun("run-1", "plan-1")).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "AMap \u53ea\u8bfb\u9884\u89c8\u8def\u5f84\u4e0d\u652f\u6301\u786e\u8ba4\u6267\u884c\u3002",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes clarification status conflicts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Source run status does not allow clarification." }), {
            status: 409,
          }),
      ),
    );

    await expect(
      clarifyRun("run-1", { user_input: "补充一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行已不能继续补充信息，请刷新状态后重试。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes missing clarification session errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ detail: "Source run is missing session persistence for clarification." }),
            { status: 409 },
          ),
      ),
    );

    await expect(
      clarifyRun("run-1", { user_input: "补充一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行缺少补充信息会话，请重新开始规划。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes unavailable clarification session errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Source run session is unavailable for clarification." }), {
            status: 409,
          }),
      ),
    );

    await expect(
      clarifyRun("run-1", { user_input: "补充一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行缺少补充信息会话，请重新开始规划。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes unavailable clarification user errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Source run user is unavailable for clarification." }), {
            status: 409,
          }),
      ),
    );

    await expect(
      clarifyRun("run-1", { user_input: "补充一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行缺少关联用户，请重新开始规划。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes replan status conflicts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Source run status does not allow replanning." }), {
            status: 409,
          }),
      ),
    );

    await expect(
      replanRun("run-1", { user_input: "调整一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行还不能继续调整方案，请刷新状态后重试。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes missing replan session errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ detail: "Source run is missing session persistence for replanning." }),
            { status: 409 },
          ),
      ),
    );

    await expect(
      replanRun("run-1", { user_input: "调整一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行缺少继续规划会话，请重新开始规划。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes unavailable replan session errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Source run session is unavailable for replanning." }), {
            status: 409,
          }),
      ),
    );

    await expect(
      replanRun("run-1", { user_input: "调整一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行缺少继续规划会话，请重新开始规划。",
    } satisfies Partial<FrontendApiError>);
  });

  it("localizes unavailable replan user errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Source run user is unavailable for replanning." }), {
            status: 409,
          }),
      ),
    );

    await expect(
      replanRun("run-1", { user_input: "调整一下", selected_plan_index: 0 }),
    ).rejects.toMatchObject({
      name: "DemoApiError",
      status: 409,
      message: "当前运行缺少关联用户，请重新开始规划。",
    } satisfies Partial<FrontendApiError>);
  });
});
