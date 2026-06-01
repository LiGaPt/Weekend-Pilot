import { describe, expect, it } from "vitest";
import { buildProgressCardItem, projectConversationThread, resolveSelectedPlanIndex } from "./thread";
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
});
