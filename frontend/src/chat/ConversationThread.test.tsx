import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DemoRunSummary } from "../types/demo";
import { ConversationThread } from "./ConversationThread";
import { projectConversationThread } from "./thread";

const runWithEnglishDemoData: DemoRunSummary = {
  run_id: "run-localization",
  status: "awaiting_confirmation",
  read_profile: "mock_world",
  selected_plan_id: "plan-garden",
  progress: {
    schema_version: "public_demo_progress_v1",
    current_stage: "ready_for_confirmation",
    current_label: "推荐方案已准备好",
    stage_history: ["ready_for_confirmation"],
    steps: [
      {
        stage: "ready_for_confirmation",
        label: "推荐方案已准备好",
        status: "current",
        summary: "推荐方案已准备好",
      },
    ],
  },
  plan_version: {
    version_number: 1,
    version_label: "v1",
    source_run_id: null,
    source_selected_plan_id: null,
  },
  plans: [
    {
      plan_id: "plan-garden",
      status: "reviewed",
      selected: true,
      title: "徐汇亲子科学馆 + Garden Supper Room",
      summary: "先去徐汇亲子科学馆做亲子活动，再去Garden Supper Room吃清淡晚餐，中间步行约16分钟。",
      activity: {
        candidate_id: "activity_museum_001",
        name: "徐汇亲子科学馆",
        category: "activity",
        address: "上海市徐汇区亲子科普路100号",
        tags: ["child_friendly", "indoor"],
      },
      dining: {
        candidate_id: "restaurant_garden_001",
        name: "Garden Supper Room",
        category: "dining",
        address: "Family Garden Road 15",
        tags: ["child_friendly", "lighter_options"],
      },
      timeline: [],
      route: {
        mode: "walking",
        distance_meters: 1180,
        duration_minutes: 16,
        summary: "A longer but usable museum-to-garden-dining route for the fallback family dinner.",
      },
      feasibility: {
        is_feasible: true,
        reasons: ["已选择亲子活动", "已选择清淡用餐", "活动到餐厅路线已验证"],
        warnings: [],
        total_duration_minutes: 256,
        route_duration_minutes: 16,
        queue_wait_minutes: 18,
      },
      proposed_actions: [],
      action_manifest: {
        source: "proposed_actions",
        action_count: 2,
        actions: [
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            action_type: "book_ticket",
            target_id: "activity_museum_001",
            payload_preview: { quantity: 3 },
            reason: "票务可用，确认后可提前锁定入场名额。",
          },
          {
            action_ref: "draft_1_action_2",
            execution_order: 2,
            action_type: "reserve_restaurant",
            target_id: "restaurant_garden_001",
            payload_preview: { party_size: 3 },
            reason: "餐厅有可订桌位，确认后可提前锁定晚餐座位。",
          },
        ],
      },
      confirmation: { status: "pending", action_count: 2 },
    },
    {
      plan_id: "plan-reading",
      status: "reviewed",
      selected: false,
      title: "Riverside Reading Hall + 绿碗家庭轻食",
      summary: "更安静的备选路线。",
      activity: {
        candidate_id: "activity_riverside_reading_001",
        name: "Riverside Reading Hall",
        category: "activity",
        address: "Family Riverside Walk 20",
        tags: ["child_friendly", "indoor", "quiet"],
      },
      dining: null,
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
  action_count: 2,
  execution_status: null,
  feedback_status: null,
  error: null,
  clarification: null,
};

describe("ConversationThread", () => {
  it("localizes demo fallback names and hides internal action target ids", async () => {
    const user = userEvent.setup();
    const items = projectConversationThread({
      entries: [{ id: "run-localization", kind: "run", run: runWithEnglishDemoData }],
      activeRunId: "run-localization",
      selectedPlanId: "plan-garden",
    });

    render(
      <ConversationThread
        items={items}
        activeRunId="run-localization"
        requestState="idle"
        canConfirm
        canDecline
        onSelectPlan={vi.fn()}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "徐汇亲子科学馆 + 花园家庭轻食餐室" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "滨江亲子阅读馆 + 绿碗家庭轻食" })).toBeInTheDocument();
    expect(screen.queryByText(/Garden Supper Room|Riverside Reading Hall/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "路线与可执行性" }));
    expect(screen.getByText("博物馆到花园轻食餐厅的步行路线稍长，但仍可用于备选家庭晚餐。")).toBeInTheDocument();
    expect(screen.queryByText(/museum-to-garden-dining|fallback family dinner/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认前动作" }));
    const ticketAction = screen.getByText("订票").closest("li");
    const reservationAction = screen.getByText("订座").closest("li");
    if (!ticketAction || !reservationAction) {
      throw new Error("Expected pre-confirmation action rows to render.");
    }
    expect(within(ticketAction).getByText("徐汇亲子科学馆")).toBeInTheDocument();
    expect(within(reservationAction).getByText("花园家庭轻食餐室")).toBeInTheDocument();
    expect(screen.queryByText(/activity_museum_001|restaurant_garden_001/)).not.toBeInTheDocument();
  });
});
