import { describe, expect, it } from "vitest";
import { projectConversationThread, resolveSelectedPlanIndex } from "./thread";
import type { DemoRunSummary } from "../types/demo";

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
            reason: "确认后锁定晚餐座位。",
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

describe("projectConversationThread", () => {
  it("projects summary-first plan cards with closed-by-default detail sections and hidden debug info", () => {
    const items = projectConversationThread({
      entries: [
        { id: "user-1", kind: "user", event: "start", text: "帮我安排下午亲子出行。" },
        { id: "run-1", kind: "run", run: awaitingRun },
      ],
      activeRunId: "run-1",
      selectedPlanId: "plan-1",
    });

    const planCard = items.find((item) => item.kind === "assistant_plan_card");
    expect(planCard).toBeDefined();
    expect(planCard?.sections.map((section) => section.id)).toEqual([
      "timeline",
      "activity_dining",
      "route_feasibility",
      "pre_confirmation_actions",
    ]);
    expect(planCard?.sections.every((section) => section.collapsedByDefault)).toBe(true);
    expect(planCard?.hiddenRunInfo.collapsedByDefault).toBe(true);
    expect(planCard?.hiddenRunInfo.runId).toBe("run-1");
    expect(planCard?.visibleBadges).toEqual(["v1", "等待确认"]);
    expect("actionCount" in (planCard?.hiddenRunInfo ?? {})).toBe(false);
    expect("executionStatus" in (planCard?.hiddenRunInfo ?? {})).toBe(false);
    expect("feedbackStatus" in (planCard?.hiddenRunInfo ?? {})).toBe(false);
  });

  it("projects the locally selected alternative plan and keeps the selected index resolvable", () => {
    const items = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: awaitingRun }],
      activeRunId: "run-1",
      selectedPlanId: "plan-2",
    });

    const planCard = items.find((item) => item.kind === "assistant_plan_card");
    expect(planCard?.planId).toBe("plan-2");
    expect(planCard?.title).toBe("滨江轻松备选");
    expect(planCard?.alternativePlans.map((plan) => [plan.planId, plan.selected])).toEqual([
      ["plan-1", false],
      ["plan-2", true],
    ]);
    expect(resolveSelectedPlanIndex(awaitingRun, "plan-2")).toBe(1);
  });

  it("keeps execution timeline data hidden behind a closed-by-default result disclosure", () => {
    const items = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: completedRun }],
      activeRunId: "run-1",
      selectedPlanId: "plan-1",
    });

    const resultCard = items.find((item) => item.kind === "assistant_result_card");
    expect(resultCard).toBeDefined();
    expect(resultCard?.timelineCollapsedByDefault).toBe(true);
    expect(resultCard?.executionTimeline.map((step) => step.executionOrder)).toEqual([1, 2]);
    expect(resultCard?.headline).toBe("安排已完成");
  });

  it("distinguishes clarification cards from awaiting-confirmation replan cards", () => {
    const clarificationItems = projectConversationThread({
      entries: [{ id: "run-clarify-1", kind: "run", run: awaitingClarificationRun }],
      activeRunId: "run-clarify-1",
      selectedPlanId: null,
    });
    const clarificationCard = clarificationItems.find((item) => item.kind === "assistant_clarification");
    expect(clarificationCard).toBeDefined();
    expect(clarificationCard?.followUpKind).toBe("clarification");
    expect(clarificationItems.some((item) => item.kind === "assistant_plan_card")).toBe(false);

    const awaitingItems = projectConversationThread({
      entries: [{ id: "run-1", kind: "run", run: awaitingRun }],
      activeRunId: "run-1",
      selectedPlanId: "plan-1",
    });
    const planCard = awaitingItems.find((item) => item.kind === "assistant_plan_card");
    expect(planCard?.followUpKind).toBe("replan");
  });
});
