import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { clarifyRun, confirmRun, replanRun, startRun, startRunStream } from "./api/demo";
import { FrontendApiError } from "./shared/http";
import type { DemoRunSummary, DemoProgressStage } from "./types/demo";

vi.mock("./api/demo", () => ({
  startRun: vi.fn(),
  startRunStream: vi.fn(),
  getRun: vi.fn(),
  clarifyRun: vi.fn(),
  confirmRun: vi.fn(),
  declineRun: vi.fn(),
  replanRun: vi.fn(),
}));

const progressLabels: Record<DemoProgressStage, string> = {
  understanding_request: "\u6b63\u5728\u7406\u89e3\u9700\u6c42",
  planning_queries: "\u6b63\u5728\u89c4\u5212\u67e5\u8be2",
  searching_activities: "\u6b63\u5728\u67e5\u8be2\u6e38\u73a9\u5730\u70b9",
  searching_dining: "\u6b63\u5728\u67e5\u8be2\u9910\u5385",
  checking_availability: "\u6b63\u5728\u68c0\u67e5\u8425\u4e1a\u4e0e\u53ef\u7528\u6027",
  building_itinerary: "\u6b63\u5728\u7ec4\u5408\u884c\u7a0b",
  checking_route_time: "\u6b63\u5728\u8ba1\u7b97\u8def\u7ebf\u4e0e\u65f6\u95f4",
  reviewing_plan: "\u6b63\u5728\u590d\u6838\u65b9\u6848",
  ready_for_confirmation: "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
  executing_confirmed_actions: "\u5df2\u786e\u8ba4\uff0c\u6b63\u5728\u6267\u884c\u52a8\u4f5c",
};

function buildProgress(
  currentStage: DemoProgressStage,
  stageHistory: DemoProgressStage[],
  summaryOverrides: Partial<Record<DemoProgressStage, string>> = {},
) {
  return {
    schema_version: "public_demo_progress_v1" as const,
    current_stage: currentStage,
    current_label: progressLabels[currentStage],
    stage_history: stageHistory,
    steps: stageHistory.map((stage, index) => {
      const status: "current" | "completed" = index === stageHistory.length - 1 ? "current" : "completed";
      return {
        stage,
        label: progressLabels[stage],
        status,
        summary: summaryOverrides[stage] ?? progressLabels[stage],
      };
    }),
  };
}

function baseAwaitingRun(): DemoRunSummary {
  return {
    run_id: "run-1",
    status: "awaiting_confirmation",
    read_profile: "mock_world",
    selected_plan_id: "plan-1",
    progress: buildProgress(
      "ready_for_confirmation",
      [
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
        "checking_availability",
        "building_itinerary",
        "checking_route_time",
        "reviewing_plan",
        "ready_for_confirmation",
      ],
      {
        searching_activities: "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8",
        searching_dining: "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385",
        building_itinerary: "\u5df2\u751f\u6210 2 \u4e2a\u5019\u9009\u65b9\u6848",
        ready_for_confirmation: "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
      },
    ),
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
        title: "Family Afternoon Plan",
        summary: "Indoor activity first, then a lighter dinner nearby.",
        activity: {
          name: "Family Science Center",
          category: "activity",
          address: "100 Science Road",
          tags: ["child_friendly", "indoor"],
        },
        dining: {
          name: "Light Table",
          category: "dining",
          address: "8 Dinner Street",
          tags: ["lighter_options", "family_tables"],
        },
        timeline: [
          {
            sequence: 1,
            title: "Indoor activity",
            start_label: "14:00",
            end_label: "16:00",
            duration_minutes: 120,
          },
        ],
        route: {
          mode: "driving",
          distance_meters: 3200,
          duration_minutes: 18,
          summary: "A short drive keeps the afternoon easy.",
        },
        feasibility: {
          is_feasible: true,
          reasons: ["Fits the requested afternoon window."],
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
              reason: "Lock dinner seating after confirmation.",
            },
          ],
        },
        confirmation: { status: "pending", action_count: 1 },
      },
      {
        plan_id: "plan-2",
        status: "reviewed",
        selected: false,
        title: "Backup Walk Plan",
        summary: "A lighter backup plan with less structure.",
        activity: {
          name: "Riverside Walk",
          category: "activity",
          address: "28 Riverside Road",
          tags: [],
        },
        dining: {
          name: "Simple Kitchen",
          category: "dining",
          address: "5 Cafe Street",
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
}

const awaitingRun = baseAwaitingRun();

const awaitingClarificationRun: DemoRunSummary = {
  run_id: "run-clarify-1",
  status: "awaiting_clarification",
  read_profile: "mock_world",
  selected_plan_id: null,
  progress: buildProgress("planning_queries", ["understanding_request", "planning_queries"], {
    understanding_request: "\u5df2\u7406\u89e3\u51fa\u884c\u76ee\u6807\u4e0e\u6838\u5fc3\u7ea6\u675f",
    planning_queries: "\u5df2\u6574\u7406\u6d3b\u52a8\u4e0e\u9910\u996e\u67e5\u8be2\u65b9\u5411",
  }),
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
    prompt: "Please tell me who is going and roughly how long you want to stay out.",
    missing_fields: ["scenario_or_participants", "time_window"],
  },
};

const clarifiedRun: DemoRunSummary = {
  ...baseAwaitingRun(),
  run_id: "run-2",
};

const awaitingAmapRun: DemoRunSummary = {
  ...baseAwaitingRun(),
  run_id: "run-amap",
  read_profile: "amap",
};

const replannedRunV2FromPlan2: DemoRunSummary = {
  ...baseAwaitingRun(),
  run_id: "run-2",
  selected_plan_id: "plan-2",
  plan_version: {
    version_number: 2,
    version_label: "v2",
    source_run_id: "run-1",
    source_selected_plan_id: "plan-2",
  },
  plans: [
    {
      ...baseAwaitingRun().plans[0],
      plan_id: "plan-1",
      selected: false,
    },
    {
      ...baseAwaitingRun().plans[1],
      plan_id: "plan-2",
      selected: true,
    },
  ],
};

const completedRun: DemoRunSummary = {
  ...baseAwaitingRun(),
  status: "completed",
  action_count: 2,
  execution_status: "succeeded",
  feedback_status: "written",
  progress: buildProgress(
    "executing_confirmed_actions",
    [
      "understanding_request",
      "planning_queries",
      "searching_activities",
      "searching_dining",
      "checking_availability",
      "building_itinerary",
      "checking_route_time",
      "reviewing_plan",
      "ready_for_confirmation",
      "executing_confirmed_actions",
    ],
    {
      searching_activities: "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8",
      searching_dining: "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385",
      executing_confirmed_actions: "\u5df2\u5f00\u59cb\u6267\u884c 2 \u4e2a\u786e\u8ba4\u52a8\u4f5c",
    },
  ),
  plans: [
    {
      ...baseAwaitingRun().plans[0],
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
            reason: "Lock dinner seating after confirmation.",
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
        headline: "Plan completed",
        message: "Reservation and follow-up message both completed.",
        completed_actions: [{ action_type: "reserve_restaurant", status: "succeeded" }],
        failed_actions: [],
        next_steps: ["Leave a little before 2pm."],
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

function expectThreadOrder(first: HTMLElement | null, second: HTMLElement | null) {
  expect(first).not.toBeNull();
  expect(second).not.toBeNull();
  expect(first!.compareDocumentPosition(second! as Node) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
}

describe("App", () => {
  beforeEach(() => {
    vi.mocked(startRun).mockReset();
    vi.mocked(startRunStream).mockReset();
    vi.mocked(clarifyRun).mockReset();
    vi.mocked(confirmRun).mockReset();
    vi.mocked(replanRun).mockReset();
    vi.mocked(startRunStream).mockResolvedValue(awaitingRun);
  });

  it("renders one bottom composer without project-design copy", () => {
    render(<App />);

    expect(screen.getByTestId("main-composer-input")).toHaveValue("");
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.getByTestId("chat-composer")).toBeInTheDocument();
    expect(screen.getByTestId("scenario-selector")).toBeInTheDocument();
    expect(screen.getAllByTestId(/^scenario-chip-/).map((chip) => chip.textContent)).toEqual([
      "亲子",
      "朋友",
      "单人",
      "情侣",
      "雨天",
      "预算",
    ]);
    expect(screen.queryByTestId("read-profile-select")).not.toBeInTheDocument();
    expect(screen.queryByTestId("advanced-options-toggle")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-info-toggle")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-id")).not.toBeInTheDocument();
    expect(screen.queryByText("WeekendPilot")).not.toBeInTheDocument();
    expect(screen.queryByText("Mock World")).not.toBeInTheDocument();
    expect(screen.queryByText("AMap")).not.toBeInTheDocument();
    expect(screen.queryByText("企业级对话式周末规划")).not.toBeInTheDocument();
    expect(screen.queryByText("Chat-First Customer Surface")).not.toBeInTheDocument();
    expect(screen.queryByText("只保留一个主输入框，剩下的进度和方案都在聊天流里完成。")).not.toBeInTheDocument();
    expect(screen.queryByText("首屏不再展示运行摘要或大面板")).not.toBeInTheDocument();
    expect(screen.queryByText("示例入口")).not.toBeInTheDocument();
  });

  it("fills the composer and sends mock_world_profile when a scenario chip is selected", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByTestId("scenario-chip-friends_gathering"));

    expect(screen.getByTestId("main-composer-input")).toHaveValue(
      "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
    );
    expect(screen.getByTestId("scenario-chip-friends_gathering")).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByTestId("start-button"));

    expect(startRunStream).toHaveBeenCalledWith(
      expect.objectContaining({
        user_input: "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
        read_profile: "mock_world",
        mock_world_profile: "friends_gathering",
      }),
      expect.any(Object),
    );
  });

  it("clears the explicit scenario selection when the active chip is clicked again", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByTestId("scenario-chip-friends_gathering"));
    expect(screen.getByTestId("main-composer-input")).toHaveValue(
      "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
    );

    await user.click(screen.getByTestId("scenario-chip-friends_gathering"));

    expect(screen.getByTestId("main-composer-input")).toHaveValue(
      "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
    );
    expect(screen.getByTestId("scenario-chip-friends_gathering")).toHaveAttribute("aria-pressed", "false");
  });

  it("hides the scenario selector when the run enters clarification mode", async () => {
    const user = userEvent.setup();
    vi.mocked(startRunStream).mockResolvedValue(awaitingClarificationRun);
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Need a plan");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("clarification-card")).toBeInTheDocument();
    expect(screen.queryByTestId("scenario-selector")).not.toBeInTheDocument();
  });

  it("hides the scenario selector when the run enters replan mode", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("replan-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("scenario-selector")).not.toBeInTheDocument();
  });

  it("shows a transient local spinner first, then renders the persistent progress card above the plan", async () => {
    const user = userEvent.setup();
    const deferred = createDeferred<DemoRunSummary>();
    let onProgress: ((event: { event_index: number; run_id: string; progress: ReturnType<typeof buildProgress> }) => void)
      | undefined;
    vi.mocked(startRunStream).mockImplementation(async (_input, handlers = {}) => {
      onProgress = handlers.onProgress;
      return deferred.promise;
    });
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    expect(screen.getByTestId("system-progress")).toBeInTheDocument();

    await act(async () => {
      onProgress?.({
        event_index: 1,
        run_id: "run-stream-1",
        progress: buildProgress("searching_activities", [
          "understanding_request",
          "planning_queries",
          "searching_activities",
        ], {
          searching_activities: "已找到 5 个活动",
        }),
      });
    });

    expect(await screen.findByTestId("progress-stepper-card")).toBeInTheDocument();
    expect(screen.queryByTestId("system-progress")).not.toBeInTheDocument();
    expect(screen.getByText("已找到 5 个活动")).toBeInTheDocument();

    await act(async () => {
      deferred.resolve(awaitingRun);
    });

    const progressCard = await screen.findByTestId("progress-stepper-card");
    const planHeading = await screen.findByRole("heading", { name: "亲子下午方案" });
    expectThreadOrder(progressCard.closest("article"), planHeading.closest("article"));
    expect(screen.getByTestId("progress-completed-toggle")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8")).not.toBeInTheDocument();
  });

  it("uses the streamed start helper and shows a live progress card before the final summary", async () => {
    const user = userEvent.setup();
    vi.mocked(startRunStream).mockImplementation(async (_input, handlers = {}) => {
      handlers.onProgress?.({
        event_index: 1,
        run_id: "run-stream-1",
        progress: buildProgress("searching_activities", [
          "understanding_request",
          "planning_queries",
          "searching_activities",
        ], {
          searching_activities: "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8",
        }),
      });
      return awaitingRun;
    });
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    expect(startRunStream).toHaveBeenCalledTimes(1);
    expect(startRun).not.toHaveBeenCalled();
    expect(await screen.findByTestId("progress-stepper-card")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "亲子下午方案" })).toBeInTheDocument();
    expect(screen.getAllByTestId("progress-stepper-card")).toHaveLength(1);
  });

  it("keeps the recommended plan summary-first without exposing run metadata", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("heading", { name: "亲子下午方案" })).toBeInTheDocument();
    expect(screen.getByText("先安排室内亲子活动，再去附近吃清淡晚餐。")).toBeInTheDocument();
    expect(screen.queryByText("室内亲子活动")).not.toBeInTheDocument();
    expect(screen.queryByText("green-table")).not.toBeInTheDocument();
    expect(screen.queryByText("\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-id")).not.toBeInTheDocument();
    expect(screen.queryByTestId("run-info-toggle")).not.toBeInTheDocument();
    expect(screen.queryByText("Mock World")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("progress-completed-toggle"));
    expect(screen.getByText("\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8")).toBeInTheDocument();
    expect(screen.getByText("\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385")).toBeInTheDocument();
  });

  it("keeps plan details collapsed until expanded", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    const planHeading = await screen.findByRole("heading", { name: "亲子下午方案" });
    const planCard = planHeading.closest(".thread-bubble");
    expect(planCard).not.toBeNull();
    const disclosureButtons = (planCard as HTMLElement).querySelectorAll<HTMLButtonElement>(".detail-disclosure-toggle");
    expect(disclosureButtons.length).toBeGreaterThanOrEqual(4);

    expect(screen.queryByText("室内亲子活动")).not.toBeInTheDocument();
    await user.click(disclosureButtons[0]);
    expect(screen.getByText("室内亲子活动")).toBeInTheDocument();

    expect(screen.queryByText("green-table")).not.toBeInTheDocument();
    await user.click(disclosureButtons[3]);
    expect(screen.getByText("轻食餐桌")).toBeInTheDocument();
  });

  it("renders the clarification flow with a progress card above the clarification card", async () => {
    const user = userEvent.setup();
    vi.mocked(startRunStream).mockResolvedValue(awaitingClarificationRun);
    vi.mocked(clarifyRun).mockResolvedValue(clarifiedRun);
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Need a plan");
    await user.click(screen.getByTestId("start-button"));

    const progressCard = await screen.findByTestId("progress-stepper-card");
    const clarificationCard = await screen.findByTestId("clarification-card");
    expectThreadOrder(progressCard.closest("article"), clarificationCard.closest("article"));
    expect(within(screen.getByTestId("clarification-fields")).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.queryByTestId("scenario-selector")).not.toBeInTheDocument();

    await user.type(screen.getByTestId("main-composer-input"), "We are leaving around 2pm for four hours.");
    await user.click(screen.getByTestId("start-button"));

    expect(clarifyRun).toHaveBeenCalledWith("run-clarify-1", {
      user_input: "We are leaving around 2pm for four hours.",
      selected_plan_index: 0,
    });
    expect(await screen.findByRole("heading", { name: "亲子下午方案" })).toBeInTheDocument();
  });

  it("uses the locally selected plan index when replanning", async () => {
    const user = userEvent.setup();
    vi.mocked(replanRun).mockResolvedValue(replannedRunV2FromPlan2);
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("heading", { name: "亲子下午方案" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "备选散步方案" }));
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    await user.type(screen.getByTestId("main-composer-input"), "Keep the backup plan, but reduce walking.");
    await user.click(screen.getByTestId("start-button"));

    expect(replanRun).toHaveBeenCalledWith("run-1", {
      user_input: "Keep the backup plan, but reduce walking.",
      selected_plan_index: 1,
    });

    expect(await screen.findByText("v2")).toBeInTheDocument();
    expect(screen.queryByTestId("run-info-toggle")).not.toBeInTheDocument();
  });

  it("blocks confirmation when the server returns a map read-only preview", async () => {
    const user = userEvent.setup();
    vi.mocked(startRunStream).mockResolvedValue(awaitingAmapRun);
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Preview a lighter afternoon plan");
    await user.click(screen.getByTestId("start-button"));

    expect(vi.mocked(startRunStream).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        read_profile: "mock_world",
      }),
    );
    expect(await screen.findByTestId("amap-read-only-notice")).toBeInTheDocument();
    expect(screen.getByTestId("amap-read-only-notice")).toHaveTextContent("地图只读预览");
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
    expect(screen.queryByText("AMap")).not.toBeInTheDocument();
  });

  it("keeps the progress card above the result card after confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(confirmRun).mockResolvedValue(completedRun);
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("confirm-button"));

    const progressCard = await screen.findByTestId("progress-stepper-card");
    const resultCard = await screen.findByTestId("assistant-result-card");
    expectThreadOrder(progressCard.closest("article"), resultCard.closest("article"));
    expect(screen.getByText("安排已完成")).toBeInTheDocument();
    expect(screen.queryByTestId("execution-timeline")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("execution-timeline-toggle"));
    const timeline = await screen.findByTestId("execution-timeline");
    expect(within(timeline).getByText("2026-05-26T14:00:00+08:00")).toBeInTheDocument();
    expect(within(timeline).getByText("轻食餐桌")).toBeInTheDocument();
  });

  it("shows a localized error banner when the streamed start fails", async () => {
    const user = userEvent.setup();
    vi.mocked(startRunStream).mockRejectedValue(
      new FrontendApiError("本地环境未配置地图只读预览所需的密钥。", 500),
    );
    render(<App />);

    await user.type(screen.getByTestId("main-composer-input"), "Plan a family afternoon");
    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("alert")).toHaveTextContent("本地环境未配置地图只读预览所需的密钥。");
    expect(screen.queryByTestId("progress-stepper-card")).not.toBeInTheDocument();
  });
});
