import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { clarifyRun, confirmRun, declineRun, replanRun, startRun } from "./api/demo";
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
      title: "徐汇亲子科学半日行",
      summary: "先安排亲子活动，再去吃一顿清淡晚餐。",
      activity: {
        name: "徐汇亲子科学馆",
        category: "activity",
        address: "上海市徐汇区亲子科普路100号",
        tags: ["child_friendly", "indoor"],
      },
      dining: {
        name: "绿碗家庭轻食",
        category: "dining",
        address: "上海市徐汇区健康弄66号",
        tags: ["lighter_options", "family_tables"],
      },
      timeline: [
        {
          sequence: 1,
          title: "体验徐汇亲子科学馆",
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
        reasons: ["符合下午半日出行时长。"],
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
      title: "滨江轻松备选方案",
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
        address: "上海市徐汇区咖啡街8号",
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

const awaitingClarificationRunRoundTwo: DemoRunSummary = {
  ...awaitingClarificationRun,
  run_id: "run-clarify-2",
  clarification: {
    prompt: "为了继续规划，请补充大概什么时间出发、准备玩多久。",
    missing_fields: ["time_window"],
  },
};

const awaitingAmapRun: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-amap",
  read_profile: "amap",
};

const clarifiedRun: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-2",
  clarification: null,
};

const replannedRunV2: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-2",
  plan_version: {
    version_number: 2,
    version_label: "v2",
    source_run_id: "run-1",
    source_selected_plan_id: "plan-1",
  },
  clarification: null,
};

const replannedRunV2FromPlan2: DemoRunSummary = {
  ...replannedRunV2,
  plan_version: {
    version_number: 2,
    version_label: "v2",
    source_run_id: "run-1",
    source_selected_plan_id: "plan-2",
  },
};

const replannedRunV3: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-3",
  plan_version: {
    version_number: 3,
    version_label: "v3",
    source_run_id: "run-2",
    source_selected_plan_id: "plan-1",
  },
  clarification: null,
};

const replannedAwaitingClarificationRun: DemoRunSummary = {
  ...awaitingClarificationRunRoundTwo,
  plan_version: {
    version_number: 2,
    version_label: "v2",
    source_run_id: "run-1",
    source_selected_plan_id: "plan-1",
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
        reason: "User chose not to continue.",
      },
    },
  ],
};

describe("App", () => {
  beforeEach(() => {
    vi.mocked(startRun).mockReset();
    vi.mocked(clarifyRun).mockReset();
    vi.mocked(confirmRun).mockReset();
    vi.mocked(declineRun).mockReset();
    vi.mocked(replanRun).mockReset();
  });

  it("renders the default prompt, default read profile, and start button", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "周末出行规划预览" })).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveValue(
      "\u4eca\u5929\u4e0b\u5348\u60f3\u548c\u7231\u4eba\u30015\u5c81\u7684\u5b69\u5b50\u51fa\u95e8\u73a9\u51e0\u4e2a\u5c0f\u65f6\uff0c\u522b\u79bb\u5bb6\u592a\u8fdc\u3002\u5b69\u5b50\u8981\u9002\u5408\u4eb2\u5b50\u6d3b\u52a8\uff0c\u7231\u4eba\u6700\u8fd1\u60f3\u5403\u6e05\u6de1\u4e00\u70b9\uff0c\u5e2e\u6211\u5b89\u6392\u4e00\u4e0b\u3002",
    );
    expect(screen.getByTestId("start-button")).toBeEnabled();
    expect(screen.getByTestId("read-profile-select")).toHaveValue("mock_world");
  });

  it("disables start when the request is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.clear(screen.getByRole("textbox"));

    expect(screen.getByTestId("start-button")).toBeDisabled();
    expect(
      screen.getByText((_, element) => element?.classList.contains("validation-text") ?? false),
    ).toBeInTheDocument();
  });

  it("renders awaiting-confirmation status and plan details after successful start", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("heading", { name: "徐汇亲子科学半日行" })).toBeInTheDocument();
    expect(screen.getAllByText("等待确认").length).toBeGreaterThan(0);
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v1");
    expect(screen.getByText("徐汇亲子科学馆")).toBeInTheDocument();
    expect(screen.getByText("绿碗家庭轻食")).toBeInTheDocument();
    expect(screen.getByText("活动与餐厅之间车程很短，适合带孩子轻松衔接。")).toBeInTheDocument();
    expect(screen.getByText("green-table")).toBeInTheDocument();
    expect(screen.getByTestId("active-read-profile")).toHaveTextContent("Mock World");
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

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByRole("tab", { name: /滨江轻松备选方案/ }));

    expect(screen.getByText("滨江亲子乐园")).toBeInTheDocument();
    expect(screen.queryByText("徐汇亲子科学馆")).not.toBeInTheDocument();
  });

  it("confirms a selected plan and renders completed feedback", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(confirmRun).mockResolvedValue(completedRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("confirm-button"));

    expect(confirmRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(await screen.findByText("安排已完成")).toBeInTheDocument();
    expect(screen.getByText("订座和通知都已处理完成。")).toBeInTheDocument();
    expect(screen.getByTestId("execution-timeline")).toBeInTheDocument();
    expect(screen.getByText("2026-05-26T14:00:00+08:00")).toBeInTheDocument();
    expect(screen.getByText("2026-05-26T14:02:00+08:00")).toBeInTheDocument();
    const timelineEntries = within(screen.getByTestId("execution-timeline")).getAllByRole("listitem");
    expect(timelineEntries[0]).toHaveTextContent("第 1 步");
    expect(timelineEntries[0]).toHaveTextContent("订座");
    expect(timelineEntries[0]).toHaveTextContent("green-table");
    expect(timelineEntries[0]).toHaveTextContent("成功");
    expect(timelineEntries[1]).toHaveTextContent("第 2 步");
    expect(timelineEntries[1]).toHaveTextContent("发送消息");
    expect(timelineEntries[1]).toHaveTextContent("family-chat");
  });

  it("declines a selected plan and hides confirm action", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(declineRun).mockResolvedValue(declinedRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("decline-button"));

    expect(declineRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
  });

  it("renders API errors in user-readable form", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockRejectedValue(new Error("API connection failed."));
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/./)).toBeInTheDocument();
  });

  it("renders a clarification panel when the run is awaiting clarification", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingClarificationRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("clarification-panel")).toBeInTheDocument();
    expect(screen.getByTestId("run-status")).toHaveTextContent("等待补充信息");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v1");
    expect(screen.getByTestId("action-count")).toHaveTextContent("0");
    expect(
      screen.getByText("为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("clarification-fields")).toHaveTextContent("出行人/场景");
    expect(screen.getByTestId("clarification-fields")).toHaveTextContent("时间安排");
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
  });

  it("disables clarification submit when the reply is empty", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingClarificationRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    const replyInput = await screen.findByTestId("clarification-reply-input");
    const submitButton = screen.getByTestId("clarification-submit-button");

    expect(submitButton).toBeDisabled();

    await user.type(replyInput, "   ");

    expect(submitButton).toBeDisabled();
  });

  it("submits a clarification reply and returns to plan review while keeping v1", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingClarificationRun);
    vi.mocked(clarifyRun).mockResolvedValue(clarifiedRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.type(
      await screen.findByTestId("clarification-reply-input"),
      "今天下午一个人出门玩几个小时，别太远。",
    );
    await user.click(screen.getByTestId("clarification-submit-button"));

    expect(clarifyRun).toHaveBeenCalledWith("run-clarify-1", {
      user_input: "今天下午一个人出门玩几个小时，别太远。",
      selected_plan_index: 0,
    });
    expect(await screen.findByRole("heading", { name: /徐汇亲子科学半日行/ })).toBeInTheDocument();
    expect(screen.getByTestId("run-status")).toHaveTextContent("等待确认");
    expect(screen.getByTestId("run-id")).toHaveTextContent("run-2");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v1");
  });

  it("keeps the clarification panel visible when clarification is still required", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingClarificationRun);
    vi.mocked(clarifyRun).mockResolvedValue(awaitingClarificationRunRoundTwo);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.type(await screen.findByTestId("clarification-reply-input"), "和朋友一起去。");
    await user.click(screen.getByTestId("clarification-submit-button"));

    expect(await screen.findByTestId("clarification-panel")).toBeInTheDocument();
    expect(screen.getByTestId("run-id")).toHaveTextContent("run-clarify-2");
    expect(screen.getByTestId("clarification-fields")).toHaveTextContent("时间安排");
    expect(screen.getByText("为了继续规划，请补充大概什么时间出发、准备玩多久。")).toBeInTheDocument();
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
  });

  it("renders a replan panel when the run is awaiting confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("replan-panel")).toBeInTheDocument();
    expect(screen.getByTestId("replan-submit-button")).toBeDisabled();
    expect(screen.getByText("继续调整方案")).toBeInTheDocument();
  });

  it("disables replan submit when the reply is empty", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    const replyInput = await screen.findByTestId("replan-reply-input");
    const submitButton = screen.getByTestId("replan-submit-button");

    expect(submitButton).toBeDisabled();

    await user.type(replyInput, "   ");

    expect(submitButton).toBeDisabled();
  });

  it("submits a replan request and advances the visible version", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(replanRun).mockResolvedValue(replannedRunV2);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.type(
      await screen.findByTestId("replan-reply-input"),
      "Keep it nearby, but make it a solo outing this time.",
    );
    await user.click(screen.getByTestId("replan-submit-button"));

    expect(replanRun).toHaveBeenCalledWith("run-1", {
      user_input: "Keep it nearby, but make it a solo outing this time.",
      selected_plan_index: 0,
    });
    expect(await screen.findByTestId("run-id")).toHaveTextContent("run-2");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v2");
    expect(screen.getByTestId("confirm-button")).toBeInTheDocument();
  });

  it("submits the selected second plan index when replanning", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(replanRun).mockResolvedValue(replannedRunV2FromPlan2);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    const tabs = await screen.findAllByRole("tab");
    await user.click(tabs[1]);

    expect(tabs[0]).toHaveAttribute("aria-selected", "false");
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("green-table")).not.toBeInTheDocument();

    await user.type(await screen.findByTestId("replan-reply-input"), "Keep the backup plan, but reduce walking.");
    await user.click(screen.getByTestId("replan-submit-button"));

    expect(replanRun).toHaveBeenCalledWith("run-1", {
      user_input: "Keep the backup plan, but reduce walking.",
      selected_plan_index: 1,
    });
    expect(await screen.findByTestId("run-id")).toHaveTextContent("run-2");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v2");
  });

  it("supports repeated replans and shows v3 on the next run", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(replanRun).mockResolvedValueOnce(replannedRunV2).mockResolvedValueOnce(replannedRunV3);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    const replanInput = await screen.findByTestId("replan-reply-input");

    await user.type(replanInput, "Keep it nearby, but make it a solo outing this time.");
    await user.click(screen.getByTestId("replan-submit-button"));
    expect(await screen.findByTestId("plan-version")).toHaveTextContent("v2");

    const nextInput = screen.getByTestId("replan-reply-input");
    await user.type(nextInput, "Reduce walking even more.");
    await user.click(screen.getByTestId("replan-submit-button"));

    expect(replanRun).toHaveBeenNthCalledWith(2, "run-2", {
      user_input: "Reduce walking even more.",
      selected_plan_index: 0,
    });
    expect(await screen.findByTestId("run-id")).toHaveTextContent("run-3");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v3");
  });

  it("switches back to the clarification panel when replan needs more user input", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(replanRun).mockResolvedValue(replannedAwaitingClarificationRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.type(await screen.findByTestId("replan-reply-input"), "改成和朋友一起，但时间还没定。");
    await user.click(screen.getByTestId("replan-submit-button"));

    expect(await screen.findByTestId("clarification-panel")).toBeInTheDocument();
    expect(screen.getByTestId("run-id")).toHaveTextContent("run-clarify-2");
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v2");
    expect(screen.queryByTestId("replan-panel")).not.toBeInTheDocument();
  });

  it("sends the selected read profile when starting a run", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingAmapRun);
    render(<App />);

    await user.selectOptions(screen.getByTestId("read-profile-select"), "amap");
    await user.click(screen.getByTestId("start-button"));

    expect(startRun).toHaveBeenCalledWith(
      expect.objectContaining({
        read_profile: "amap",
      }),
    );
  });

  it("shows AMAP as the active read profile and blocks confirmation for the read-only preview path", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingAmapRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("active-read-profile")).toHaveTextContent(
      "AMap \u53ea\u8bfb\u9884\u89c8",
    );
    expect(screen.getByTestId("amap-read-only-notice")).toHaveTextContent(
      "\u53ea\u8bfb\u9884\u89c8",
    );
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
    expect(screen.getByTestId("decline-button")).toBeEnabled();
    expect(screen.getByTestId("refresh-button")).toBeEnabled();
  });

  it("shows a neutral execution timeline state when execution exists without visible actions", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(confirmRun).mockResolvedValue({
      ...completedRun,
      plans: [
        {
          ...completedRun.plans[0],
          execution: {
            ...completedRun.plans[0].execution!,
            action_results: [],
          },
        },
      ],
    });
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("confirm-button"));

    expect(await screen.findByTestId("execution-timeline")).toBeInTheDocument();
    expect(screen.getByText("已生成执行结果，但当前没有可展示的执行动作。")).toBeInTheDocument();
  });
});
