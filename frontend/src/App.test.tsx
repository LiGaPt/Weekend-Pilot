import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { clarifyRun, confirmRun, getRun, replanRun, startRun } from "./api/demo";
import type { DemoRunSummary } from "./types/demo";

vi.mock("./api/demo", () => ({
  startRun: vi.fn(),
  getRun: vi.fn(),
  clarifyRun: vi.fn(),
  confirmRun: vi.fn(),
  declineRun: vi.fn(),
  replanRun: vi.fn(),
}));

const awaitingRun: DemoRunSummary = {
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
      title: "徐汇亲子半日行",
      summary: "先安排室内亲子活动，再去吃一顿清淡晚餐。",
      activity: {
        name: "徐汇亲子科学馆",
        category: "activity",
        address: "上海市徐汇区亲子科普路100号",
        tags: ["child_friendly", "indoor"],
      },
      dining: {
        name: "绿箸家庭轻食",
        category: "dining",
        address: "上海市徐汇区健康街6号",
        tags: ["lighter_options", "family_tables"],
      },
      timeline: [
        {
          sequence: 1,
          title: "体验亲子科学馆",
          start_label: "14:00",
          end_label: "16:00",
          duration_minutes: 120,
        },
      ],
      route: {
        mode: "driving",
        distance_meters: 3200,
        duration_minutes: 18,
        summary: "活动与餐厅之间车程很短，适合带孩子轻松衔接。",
      },
      feasibility: {
        is_feasible: true,
        reasons: ["符合半日出行时长。"],
        warnings: [],
        total_duration_minutes: 270,
        route_duration_minutes: 18,
        queue_wait_minutes: 5,
      },
      proposed_actions: [],
      action_manifest: {
        source: "proposed_actions",
        action_count: 1,
        actions: [
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            action_type: "reserve_restaurant",
            target_id: "green-table",
            payload_preview: { party_size: 3 },
            reason: "确认后可提前锁定晚餐座位。",
          },
        ],
      },
      confirmation: { status: "pending", action_count: 1 },
    },
    {
      plan_id: "plan-2",
      status: "reviewed",
      selected: false,
      title: "滨江轻松备选",
      summary: "先去户外活动，再简单吃一顿轻便晚餐。",
      activity: {
        name: "滨江亲子乐园",
        category: "activity",
        address: "上海市徐汇区滨江步道28号",
        tags: [],
      },
      dining: {
        name: "街角轻食小馆",
        category: "dining",
        address: "上海市徐汇区咖啡街3号",
        tags: [],
      },
      timeline: [],
      route: null,
      feasibility: null,
      proposed_actions: [],
      action_manifest: {
        source: "none",
        action_count: 0,
        actions: [],
      },
      confirmation: { status: "pending", action_count: 0 },
    },
  ],
  action_count: 0,
  execution_status: null,
  feedback_status: null,
  error: null,
  clarification: null,
};

const awaitingClarificationRun: DemoRunSummary = {
  run_id: "run-clarify-1",
  status: "awaiting_clarification",
  read_profile: "mock_world",
  selected_plan_id: null,
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
  clarification: {
    prompt: "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
    missing_fields: ["scenario_or_participants", "time_window"],
  },
};

const clarifiedRun: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-2",
};

const awaitingAmapRun: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-amap",
  read_profile: "amap",
};

const replannedRunV2FromPlan2: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-2",
  plan_version: {
    version_number: 2,
    version_label: "v2",
    source_run_id: "run-1",
    source_selected_plan_id: "plan-2",
  },
};

const completedRun: DemoRunSummary = {
  ...awaitingRun,
  status: "completed",
  action_count: 2,
  execution_status: "succeeded",
  feedback_status: "written",
  plans: [
    {
      ...awaitingRun.plans[0],
      status: "executed",
      action_manifest: {
        source: "confirmed_actions",
        action_count: 1,
        actions: [
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            action_type: "reserve_restaurant",
            target_id: "green-table",
            payload_preview: { party_size: 3 },
            reason: "Lock the dinner table after confirmation.",
          },
        ],
      },
      confirmation: { status: "confirmed", confirmed_by: "web-demo-user", action_count: 1 },
      execution: {
        status: "succeeded",
        started_at: "2026-05-26T14:00:00+08:00",
        finished_at: "2026-05-26T14:02:00+08:00",
        succeeded_count: 2,
        failed_count: 0,
        action_results: [
          {
            action_ref: "draft_1_action_2",
            execution_order: 2,
            tool_name: "send_message",
            target_id: "family-chat",
            status: "succeeded",
          },
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            tool_name: "reserve_restaurant",
            target_id: "green-table",
            status: "succeeded",
          },
        ],
      },
      feedback: {
        status: "written",
        headline: "安排已完成",
        message: "订座和通知都已处理完成。",
        completed_actions: [{ action_type: "reserve_restaurant", status: "succeeded" }],
        failed_actions: [],
        next_steps: ["建议 13:40 左右出发。"],
      },
    },
  ],
};

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

describe("App", () => {
  beforeEach(() => {
    vi.mocked(startRun).mockReset();
    vi.mocked(getRun).mockReset();
    vi.mocked(clarifyRun).mockReset();
    vi.mocked(confirmRun).mockReset();
    vi.mocked(replanRun).mockReset();
  });

  it("renders a single composer with examples and hides advanced options by default", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole("heading", { name: "企业级对话式周末规划" })).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveValue("");
    expect(screen.getByRole("button", { name: "亲子半天" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "朋友轻社交" })).toBeInTheDocument();
    expect(screen.queryByTestId("read-profile-select")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-id")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "亲子半天" }));
    expect(screen.getByRole("textbox")).toHaveValue(
      "今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。孩子要适合亲子活动，爱人最近想吃清淡一点，帮我安排一下。",
    );
  });

  it("appends the user request and a visible system progress item while starting", async () => {
    const user = userEvent.setup();
    const deferred = createDeferred<DemoRunSummary>();
    vi.mocked(startRun).mockReturnValue(deferred.promise);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我安排一个下午的亲子活动。");
    await user.click(screen.getByTestId("start-button"));

    expect(screen.getAllByText("帮我安排一个下午的亲子活动。").length).toBeGreaterThan(0);
    expect(screen.getByTestId("system-progress")).toHaveTextContent("正在生成推荐方案...");

    deferred.resolve(awaitingRun);
    expect(await screen.findByRole("heading", { name: "徐汇亲子半日行" })).toBeInTheDocument();
  });

  it("renders a summary-first plan card and keeps run metadata hidden until disclosure opens", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我安排一个下午的亲子活动。");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("heading", { name: "徐汇亲子半日行" })).toBeInTheDocument();
    expect(screen.getByText("先安排室内亲子活动，再去吃一顿清淡晚餐。")).toBeInTheDocument();
    expect(screen.queryByText("体验亲子科学馆")).not.toBeInTheDocument();
    expect(screen.queryByText("green-table")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-id")).not.toBeInTheDocument();
    expect(screen.queryByTestId("action-count")).not.toBeInTheDocument();

    const runInfoButtons = screen.getAllByTestId("run-info-toggle");
    await user.click(runInfoButtons[runInfoButtons.length - 1]);

    expect(screen.getByTestId("run-id")).toHaveTextContent("run-1");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v1");
    expect(screen.getByTestId("active-read-profile")).toHaveTextContent("Mock World");
  });

  it("keeps plan details collapsed until the reviewer expands them", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我安排一个下午的亲子活动。");
    await user.click(screen.getByTestId("start-button"));
    const planHeading = await screen.findByRole("heading", { name: "徐汇亲子半日行" });
    const planCard = planHeading.closest(".thread-bubble");
    expect(planCard).not.toBeNull();

    expect(screen.queryByText("体验亲子科学馆")).not.toBeInTheDocument();
    await user.click(within(planCard as HTMLElement).getByRole("button", { name: "时间线" }));
    expect(screen.getByText("体验亲子科学馆")).toBeInTheDocument();

    expect(screen.queryByText("green-table")).not.toBeInTheDocument();
    await user.click(within(planCard as HTMLElement).getByRole("button", { name: "确认前动作" }));
    expect(screen.getByText("green-table")).toBeInTheDocument();
  });

  it("renders clarification inside the chat flow and submits the inline reply", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingClarificationRun);
    vi.mocked(clarifyRun).mockResolvedValue(clarifiedRun);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "想周末出去玩一下。");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("clarification-card")).toBeInTheDocument();
    expect(screen.getByText("为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。")).toBeInTheDocument();
    expect(screen.getByTestId("clarification-fields")).toHaveTextContent("出行人 / 场景");
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();

    await user.type(screen.getByTestId("clarification-reply-input"), "今天下午和家人出门，玩 4 个小时。");
    await user.click(screen.getByTestId("clarification-submit-button"));

    expect(clarifyRun).toHaveBeenCalledWith("run-clarify-1", {
      user_input: "今天下午和家人出门，玩 4 个小时。",
      selected_plan_index: 0,
    });
    expect(await screen.findByRole("heading", { name: "徐汇亲子半日行" })).toBeInTheDocument();
  });

  it("uses the selected non-default plan index when replanning inside the chat flow", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(replanRun).mockResolvedValue(replannedRunV2FromPlan2);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我安排一个下午的亲子活动。");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("heading", { name: "徐汇亲子半日行" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "滨江轻松备选" }));
    await user.type(screen.getByTestId("replan-reply-input"), "保留备选方案，但减少步行。");
    await user.click(screen.getByTestId("replan-submit-button"));

    expect(replanRun).toHaveBeenCalledWith("run-1", {
      user_input: "保留备选方案，但减少步行。",
      selected_plan_index: 1,
    });

    const runInfoButtons = screen.getAllByTestId("run-info-toggle");
    await user.click(runInfoButtons[runInfoButtons.length - 1]);
    expect(await screen.findByTestId("plan-version")).toHaveTextContent("v2");
  });

  it("keeps refresh inside the run-info disclosure and updates the latest run without duplicating cards", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(getRun).mockResolvedValue({
      ...awaitingRun,
      plans: [
        {
          ...awaitingRun.plans[0],
          summary: "更新后的方案摘要。",
        },
        awaitingRun.plans[1],
      ],
    });
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我安排一个下午的亲子活动。");
    await user.click(screen.getByTestId("start-button"));
    expect(await screen.findByRole("heading", { name: "徐汇亲子半日行" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "徐汇亲子半日行" })).toHaveLength(1);

    const runInfoButtons = screen.getAllByTestId("run-info-toggle");
    await user.click(runInfoButtons[runInfoButtons.length - 1]);
    await user.click(screen.getByTestId("refresh-button"));

    expect(await screen.findByText("更新后的方案摘要。")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "徐汇亲子半日行" })).toHaveLength(1);
  });

  it("keeps the AMap preview path behind advanced options and blocks confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingAmapRun);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我先预览一个周末下午行程。");
    await user.click(screen.getByTestId("advanced-options-toggle"));
    await user.selectOptions(screen.getByTestId("read-profile-select"), "amap");
    await user.click(screen.getByTestId("start-button"));

    expect(startRun).toHaveBeenCalledWith(
      expect.objectContaining({
        read_profile: "amap",
      }),
    );
    expect(await screen.findByTestId("amap-read-only-notice")).toHaveTextContent("只读预览");
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
  });

  it("renders completed feedback in chat and keeps the execution timeline collapsed until expanded", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(confirmRun).mockResolvedValue(completedRun);
    render(<App />);

    await user.type(screen.getByRole("textbox"), "帮我安排一个下午的亲子活动。");
    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("confirm-button"));

    expect(await screen.findByTestId("assistant-result-card")).toBeInTheDocument();
    expect(screen.getByText("安排已完成")).toBeInTheDocument();
    expect(screen.getByText("订座和通知都已处理完成。")).toBeInTheDocument();
    expect(screen.queryByTestId("execution-timeline")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("execution-timeline-toggle"));
    const timeline = await screen.findByTestId("execution-timeline");
    expect(timeline).toBeInTheDocument();
    expect(within(timeline).getByText("2026-05-26T14:00:00+08:00")).toBeInTheDocument();
    expect(within(timeline).getByText("2026-05-26T14:02:00+08:00")).toBeInTheDocument();
    expect(within(timeline).getByText("green-table")).toBeInTheDocument();
    expect(within(timeline).getByText("family-chat")).toBeInTheDocument();
  });
});
