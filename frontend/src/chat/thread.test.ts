import { describe, expect, it } from "vitest";
import {
  actionTargetLabel,
  buildProgressCardItem,
  projectConversationThread,
  resolveSelectedPlanIndex,
  tagLabel,
  userFacingText,
} from "./thread";
import type { DemoRunSummary, DemoProgressStage } from "../types/demo";

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

const awaitingRun: DemoRunSummary = {
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

const awaitingClarificationRun: DemoRunSummary = {
  run_id: "run-clarify-1",
  status: "awaiting_clarification",
  read_profile: "mock_world",
  selected_plan_id: null,
  progress: buildProgress("planning_queries", ["understanding_request", "planning_queries"]),
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

const completedRun: DemoRunSummary = {
  ...awaitingRun,
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
        final_arrangement_message: "搞定了，下午 2 点出发，先去Family Science Center，再到Light Table；订座和后续消息都已安排好",
        completed_actions: [{ action_type: "reserve_restaurant", status: "succeeded" }],
        failed_actions: [],
        next_steps: ["Leave a little before 2pm."],
      },
    },
  ],
};

describe("projectConversationThread", () => {
  it("projects a live pending progress card without inventing a separate thread item kind", () => {
    const pendingProgress = buildProgressCardItem(
      "run-live-1",
      buildProgress("searching_dining", [
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
      ], {
        searching_activities: "已找到 5 个活动",
        searching_dining: "已找到 5 个餐厅",
      }),
    );

    const items = projectConversationThread({
      entries: [{ id: "start-1", kind: "user", event: "start", text: "Plan a family afternoon" }],
      activeRunId: null,
      selectedPlanId: null,
      pendingAction: pendingProgress,
    });

    expect(items).toHaveLength(2);
    expect(items[0].kind).toBe("user_message");
    expect(items[1].kind).toBe("assistant_progress_card");

    const progressItem = items[1];
    if (progressItem.kind !== "assistant_progress_card") {
      throw new Error("Expected the live pending item to project as an assistant progress card.");
    }
    expect(progressItem.completedCollapsedByDefault).toBe(true);
    expect(progressItem.completedSteps).toHaveLength(3);
    expect(progressItem.completedSteps[1]?.summary).toBe("正在规划查询");
  });

  it("projects the progress card before the plan card and keeps completed steps hidden in data", () => {
    const items = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: awaitingRun }],
      activeRunId: "run-1",
      selectedPlanId: "plan-1",
    });

    expect(items[0].kind).toBe("assistant_progress_card");
    const progressItem = items[0];
    if (progressItem.kind !== "assistant_progress_card") {
      throw new Error("Expected the first projected item to be the progress card.");
    }
    expect(progressItem.completedCollapsedByDefault).toBe(true);
    expect(progressItem.completedSteps).toHaveLength(8);

    const planCard = items.find((item) => item.kind === "assistant_plan_card");
    expect(planCard).toBeDefined();
    expect(planCard?.sections.every((section) => section.collapsedByDefault)).toBe(true);
    expect(planCard?.hiddenRunInfo.collapsedByDefault).toBe(true);
    expect(planCard?.visibleBadges).toEqual(["v1", "\u7b49\u5f85\u786e\u8ba4"]);
  });

  it("projects the selected non-default plan and keeps the index resolvable", () => {
    const items = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: awaitingRun }],
      activeRunId: "run-1",
      selectedPlanId: "plan-2",
    });

    const planCard = items.find((item) => item.kind === "assistant_plan_card");
    expect(planCard?.planId).toBe("plan-2");
    expect(planCard?.title).toBe("备选散步方案");
    expect(planCard?.alternativePlans.map((plan) => [plan.planId, plan.selected])).toEqual([
      ["plan-1", false],
      ["plan-2", true],
    ]);
    expect(resolveSelectedPlanIndex(awaitingRun, "plan-2")).toBe(1);
  });

  it("keeps the result card collapsed and preserves execution ordering", () => {
    const items = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: completedRun }],
      activeRunId: "run-1",
      selectedPlanId: "plan-1",
    });

    const progressIndex = items.findIndex((item) => item.kind === "assistant_progress_card");
    const resultIndex = items.findIndex((item) => item.kind === "assistant_result_card");
    expect(progressIndex).toBeGreaterThanOrEqual(0);
    expect(resultIndex).toBeGreaterThan(progressIndex);

    const resultCard = items.find((item) => item.kind === "assistant_result_card");
    expect(resultCard?.timelineCollapsedByDefault).toBe(true);
    expect(resultCard?.executionTimeline.map((step) => step.executionOrder)).toEqual([1, 2]);
    expect(resultCard?.headline).toBe("安排已完成");
    expect(resultCard?.finalArrangementMessage).toBe("搞定了，下午 2 点出发，先去亲子科学中心，再到轻食餐桌；订座和后续消息都已安排好");
    expect(resultCard?.message).toBe("订座和后续消息都已完成。");
  });

  it("falls back to the generic feedback message when no final arrangement message is present", () => {
    const runWithoutFinalMessage: DemoRunSummary = {
      ...completedRun,
      plans: completedRun.plans.map((plan) => ({
        ...plan,
        feedback: plan.feedback
          ? {
              ...plan.feedback,
              final_arrangement_message: null,
            }
          : plan.feedback,
      })),
    };

    const items = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: runWithoutFinalMessage }],
      activeRunId: "run-1",
      selectedPlanId: "plan-1",
    });

    const resultCard = items.find((item) => item.kind === "assistant_result_card");
    expect(resultCard?.finalArrangementMessage).toBeNull();
    expect(resultCard?.message).toBe("订座和后续消息都已完成。");
  });

  it("renders clarification cards after the progress card in the clarification flow", () => {
    const clarificationItems = projectConversationThread({
      entries: [{ id: "run-clarify-1", kind: "run", run: awaitingClarificationRun }],
      activeRunId: "run-clarify-1",
      selectedPlanId: null,
    });

    expect(clarificationItems[0].kind).toBe("assistant_progress_card");
    expect(clarificationItems[1].kind).toBe("assistant_clarification");
    const clarificationCard = clarificationItems[1];
    if (clarificationCard.kind !== "assistant_clarification") {
      throw new Error("Expected the second projected item to be the clarification card.");
    }
    expect(clarificationCard.followUpKind).toBe("clarification");
  });

  it("localizes visible english names, addresses, and route summaries for non-family fixtures", () => {
    expect(userFacingText("Patio Queue House")).toBe("露台排队餐屋");
    expect(userFacingText("Friends Patio Road 11")).toBe("上海市长宁区朋友露台路11号");
    expect(userFacingText("A usable outdoor link, but slower than the canonical lawn-to-yard pairing.")).toBe(
      "这条户外步行路线可用，但比首选草坪到庭院餐吧的组合更慢。",
    );
    expect(userFacingText("Shared Table Game Loft")).toBe("共享桌游阁楼");
    expect(userFacingText("Jing'an District Counter Road 10")).toBe("上海市静安区吧台路10号");
    expect(userFacingText("A straightforward walk from the gallery to a louder dining room farther down the block.")).toBe(
      "从展馆步行到更热闹的备选餐厅路线直接，但整体氛围不如首选单人晚餐。",
    );
    expect(userFacingText("Hotpot Queue Counter")).toBe("火锅排队柜台");
    expect(userFacingText("A valid covered walk, but slower than the canonical market-to-soup transfer.")).toBe(
      "这条有遮挡的步行路线可用，但比首选室内市集到热汤店的衔接更慢。",
    );
    expect(userFacingText("Value Bistro Express")).toBe("高性价比小馆快线");
    expect(userFacingText("A valid route, but it is longer than the canonical park-to-bento walk.")).toBe(
      "这条路线可用，但比首选公园到便当店的步行更长。",
    );
  });

  it("localizes newly exposed multi-scenario tags", () => {
    expect(tagLabel("hangout")).toBe("轻松聚会");
    expect(tagLabel("sports")).toBe("轻运动");
    expect(tagLabel("casual_dining")).toBe("轻松用餐");
    expect(tagLabel("friends_group")).toBe("朋友同行");
    expect(tagLabel("sharing_plates")).toBe("适合分享");
    expect(tagLabel("slow_service")).toBe("出餐较慢");
    expect(tagLabel("couple_friendly")).toBe("适合两人同行");
    expect(tagLabel("date_friendly")).toBe("适合约会");
    expect(tagLabel("casual")).toBe("轻松氛围");
    expect(tagLabel("social")).toBe("适合社交");
    expect(tagLabel("gallery")).toBe("画廊");
    expect(tagLabel("light_meal")).toBe("轻食");
    expect(tagLabel("family_pause")).toBe("适合短暂休息");
    expect(tagLabel("comfort_food")).toBe("暖胃热食");
    expect(tagLabel("market")).toBe("市集");
    expect(tagLabel("nearby")).toBe("就近");
    expect(tagLabel("warm_food")).toBe("热食");
    expect(tagLabel("restaurant")).toBe("餐饮");
    expect(tagLabel("budget_limited")).toBe("预算有限");
    expect(tagLabel("free_activity")).toBe("免费活动");
    expect(tagLabel("premium")).toBe("价格偏高");
    expect(tagLabel("value_set")).toBe("平价套餐");
  });

  it("does not fall back to raw target ids for newly public multi-scenario plans", () => {
    const friendsPlan = {
      ...awaitingRun.plans[0],
      activity: {
        candidate_id: "activity_lawn_301",
        name: "苏河边草坪聚会点",
        category: "activity",
        address: "上海市长宁区临空一路88号附近",
        tags: ["group_friendly", "hangout"],
      },
      dining: {
        candidate_id: "restaurant_yard_301",
        name: "庭院分享餐吧",
        category: "dining",
        address: "上海市长宁区天山西路58号",
        tags: ["casual_dining", "friends_group"],
      },
    };

    expect(actionTargetLabel(friendsPlan, "activity_lawn_301", "book_ticket")).toBe("苏河边草坪聚会点");
    expect(actionTargetLabel(friendsPlan, "restaurant_yard_301", "reserve_restaurant")).toBe("庭院分享餐吧");
    expect(actionTargetLabel(friendsPlan, "queue_restaurant_yard_301", "join_queue")).toBe("庭院分享餐吧排队取号");
    expect(actionTargetLabel(friendsPlan, "activity_arcade_301", "book_ticket")).toBe("苏河边草坪聚会点");
    expect(actionTargetLabel(friendsPlan, "restaurant_patio_301", "reserve_restaurant")).not.toBe("restaurant_patio_301");
  });
});
