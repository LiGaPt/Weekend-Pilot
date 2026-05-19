import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { confirmRun, declineRun, startRun } from "./api/demo";
import type { DemoRunSummary } from "./types/demo";

vi.mock("./api/demo", () => ({
  startRun: vi.fn(),
  getRun: vi.fn(),
  confirmRun: vi.fn(),
  declineRun: vi.fn(),
}));

const awaitingRun: DemoRunSummary = {
  run_id: "run-1",
  status: "awaiting_confirmation",
  selected_plan_id: "plan-1",
  plans: [
    {
      plan_id: "plan-1",
      status: "reviewed",
      selected: true,
      title: "徐汇亲子轻松下午",
      summary: "先做亲子科学体验，再步行去吃清淡晚餐。",
      activity: {
        name: "徐汇亲子科学馆",
        category: "亲子活动",
        address: "上海市徐汇区亲子科普路100号",
        tags: ["亲子友好", "室内"],
      },
      dining: {
        name: "绿碗家庭轻食",
        category: "清淡餐厅",
        address: "上海市徐汇区健康弄66号",
        tags: ["清淡菜", "亲子友好"],
      },
      timeline: [
        {
          sequence: 1,
          title: "参观科学馆",
          start_label: "14:00",
          end_label: "16:00",
          duration_minutes: 120,
        },
      ],
      route: {
        mode: "driving",
        distance_meters: 3200,
        duration_minutes: 18,
        summary: "两站之间步行很短，适合推童车。",
      },
      feasibility: {
        is_feasible: true,
        reasons: ["符合下午出行时间窗。"],
        warnings: [],
        total_duration_minutes: 270,
        route_duration_minutes: 18,
        queue_wait_minutes: 5,
      },
      proposed_actions: [
        {
          action_type: "reserve_restaurant",
          target_id: "green-table",
          requires_confirmation: true,
          reason: "提前锁定晚餐座位。",
        },
      ],
      confirmation: { status: "pending", action_count: 1 },
    },
    {
      plan_id: "plan-2",
      status: "reviewed",
      selected: false,
      title: "公园和咖啡备选",
      summary: "户外活动搭配咖啡简餐。",
      activity: { name: "滨江亲子乐园", category: "户外活动", address: "滨江步道", tags: [] },
      dining: { name: "软勺咖啡", category: "咖啡简餐", address: "咖啡街", tags: [] },
      timeline: [],
      route: null,
      feasibility: null,
      proposed_actions: [],
      confirmation: { status: "pending", action_count: 0 },
    },
  ],
  action_count: 0,
  execution_status: null,
  feedback_status: null,
  error: null,
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
      confirmation: { status: "confirmed", confirmed_by: "web-demo-user", action_count: 1 },
      execution: {
        status: "succeeded",
        succeeded_count: 2,
        failed_count: 0,
      },
      feedback: {
        status: "written",
        headline: "安排已完成",
        message: "订座和消息通知已完成。",
        completed_actions: [{ action_type: "reserve_restaurant", status: "succeeded" }],
        failed_actions: [],
        next_steps: ["13:40 出发。"],
      },
    },
  ],
};

const declinedRun: DemoRunSummary = {
  ...awaitingRun,
  status: "declined",
  plans: [
    {
      ...awaitingRun.plans[0],
      status: "declined",
      confirmation: {
        status: "declined",
        declined_by: "web-demo-user",
        reason: "用户选择暂不继续。",
      },
    },
  ],
};

describe("App", () => {
  beforeEach(() => {
    vi.mocked(startRun).mockReset();
    vi.mocked(confirmRun).mockReset();
    vi.mocked(declineRun).mockReset();
  });

  it("renders the default prompt and start button", () => {
    render(<App />);

    expect(screen.getByRole("textbox", { name: /^需求$/ })).toHaveValue(
      "今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。孩子要适合亲子活动，爱人最近想吃清淡一点，帮我安排一下。",
    );
    expect(screen.getByRole("button", { name: /开始规划/ })).toBeEnabled();
  });

  it("disables start when the request is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.clear(screen.getByRole("textbox", { name: /^需求$/ }));

    expect(screen.getByRole("button", { name: /开始规划/ })).toBeDisabled();
    expect(screen.getByText(/请输入需求/)).toBeInTheDocument();
  });

  it("renders awaiting-confirmation status and plan details after successful start", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /开始规划/ }));

    expect(await screen.findByRole("heading", { name: "徐汇亲子轻松下午" })).toBeInTheDocument();
    expect(screen.getAllByText("awaiting_confirmation").length).toBeGreaterThan(0);
    expect(screen.getByText("徐汇亲子科学馆")).toBeInTheDocument();
    expect(screen.getByText("绿碗家庭轻食")).toBeInTheDocument();
    expect(screen.getByText("两站之间步行很短，适合推童车。")).toBeInTheDocument();
  });

  it("does not render internal observability labels on the public page", async () => {
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    expect(screen.queryByText("Trace ID")).not.toBeInTheDocument();
  });

  it("switches plan tabs without calling the backend", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /开始规划/ }));
    await user.click(await screen.findByRole("tab", { name: /公园和咖啡备选/ }));

    expect(screen.getByText("滨江亲子乐园")).toBeInTheDocument();
    expect(screen.queryByText("徐汇亲子科学馆")).not.toBeInTheDocument();
  });

  it("confirms a selected plan and renders completed feedback", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(confirmRun).mockResolvedValue(completedRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /开始规划/ }));
    await user.click(await screen.findByRole("button", { name: /确认所选方案/ }));

    expect(confirmRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(await screen.findByText("安排已完成")).toBeInTheDocument();
    expect(screen.getByText("订座和消息通知已完成。")).toBeInTheDocument();
  });

  it("declines a selected plan and hides confirm action", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(declineRun).mockResolvedValue(declinedRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /开始规划/ }));
    await user.click(await screen.findByRole("button", { name: /^暂不继续$/ }));

    expect(declineRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(await screen.findByText("用户选择暂不继续。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /确认所选方案/ })).not.toBeInTheDocument();
  });

  it("renders API errors in user-readable form", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockRejectedValue(new Error("API connection failed."));
    render(<App />);

    await user.click(screen.getByRole("button", { name: /开始规划/ }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("演示请求失败，请稍后重试。")).toBeInTheDocument();
  });
});
