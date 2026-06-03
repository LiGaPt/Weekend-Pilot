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

function buildMultiScenarioRun(
  runId: string,
  planId: string,
  planTitle: string,
  summary: string,
  activity: { candidate_id: string; name: string; address: string; tags: string[] },
  dining: { candidate_id: string; name: string; address: string; tags: string[] },
  routeSummary: string,
  targetId: string,
): DemoRunSummary {
  return {
    run_id: runId,
    status: "awaiting_confirmation",
    read_profile: "mock_world",
    selected_plan_id: planId,
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
        plan_id: planId,
        status: "reviewed",
        selected: true,
        title: planTitle,
        summary,
        activity: { ...activity, category: "activity" },
        dining: { ...dining, category: "dining" },
        timeline: [],
        route: {
          mode: "walking",
          distance_meters: 880,
          duration_minutes: 12,
          summary: routeSummary,
        },
        feasibility: {
          is_feasible: true,
          reasons: ["活动到餐厅路线已验证"],
          warnings: [],
          total_duration_minutes: 252,
          route_duration_minutes: 12,
          queue_wait_minutes: 8,
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
              target_id: targetId,
              payload_preview: { party_size: 2 },
              reason: "确认后可提前锁定晚餐座位。",
            },
          ],
        },
        confirmation: { status: "pending", action_count: 1 },
      },
    ],
    action_count: 1,
    execution_status: null,
    feedback_status: null,
    error: null,
    clarification: null,
  };
}

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

  it.each([
    {
      name: "friends",
      run: buildMultiScenarioRun(
        "run-friends",
        "plan-friends",
        "苏河边草坪聚会点 + Patio Queue House",
        "先去苏河边草坪聚会点和朋友散步聊天，再去Patio Queue House吃适合分享的轻松晚餐，中间步行约12分钟。",
        {
          candidate_id: "activity_lawn_301",
          name: "苏河边草坪聚会点",
          address: "上海市长宁区临空一路88号附近",
          tags: ["group_friendly", "hangout"],
        },
        {
          candidate_id: "restaurant_patio_301",
          name: "Patio Queue House",
          address: "Friends Patio Road 11",
          tags: ["casual_dining", "friends_group", "slow_service"],
        },
        "A usable outdoor link, but slower than the canonical lawn-to-yard pairing.",
        "restaurant_patio_301",
      ),
      translatedName: "露台排队餐屋",
      rawText: /Patio Queue House|Friends Patio Road 11/,
      translatedRoute: "这条户外步行路线可用，但比首选草坪到庭院餐吧的组合更慢。",
      translatedTag: "朋友同行",
    },
    {
      name: "solo",
      run: buildMultiScenarioRun(
        "run-solo",
        "plan-solo",
        "静安轻展馆 + Shared Plates Kitchen",
        "先去静安轻展馆一个人轻松逛逛，再去Shared Plates Kitchen吃一顿简餐，中间步行约12分钟。",
        {
          candidate_id: "activity_gallery_001",
          name: "静安轻展馆",
          address: "上海市静安区展览路18号",
          tags: ["museum", "light_activity"],
        },
        {
          candidate_id: "restaurant_sharedplates_001",
          name: "Shared Plates Kitchen",
          address: "Jing'an District Social Street 14",
          tags: ["casual", "social", "light_meal"],
        },
        "A straightforward walk from the gallery to a louder dining room farther down the block.",
        "restaurant_sharedplates_001",
      ),
      translatedName: "共享餐盘厨房",
      rawText: /Shared Plates Kitchen|Jing'an District Social Street 14/,
      translatedRoute: "从展馆步行到更热闹的备选餐厅路线直接，但整体氛围不如首选单人晚餐。",
      translatedTag: "适合社交",
    },
    {
      name: "couple",
      run: buildMultiScenarioRun(
        "run-couple",
        "plan-couple",
        "法式街区漫步 + 约会小酒馆",
        "先去法式街区漫步和伴侣慢慢逛，再去约会小酒馆吃一顿轻松晚餐，中间步行约12分钟。",
        {
          candidate_id: "activity_citywalk_201",
          name: "法式街区漫步",
          address: "上海市徐汇区街区路201号",
          tags: ["citywalk", "couple_friendly"],
        },
        {
          candidate_id: "restaurant_bistro_201",
          name: "约会小酒馆",
          address: "上海市徐汇区晚餐街201号",
          tags: ["date_friendly", "light_meal"],
        },
        "A short drive keeps the afternoon easy.",
        "restaurant_bistro_201",
      ),
      translatedName: "约会小酒馆",
      rawText: /restaurant_bistro_201/,
      translatedRoute: "短途驾车，下午节奏更轻松。",
      translatedTag: "适合约会",
    },
    {
      name: "rainy",
      run: buildMultiScenarioRun(
        "run-rainy",
        "plan-rainy",
        "室内市集馆 + Warm Cafe Corner",
        "先去室内市集馆安排室内避雨活动，再去Warm Cafe Corner吃一顿热一点的简餐，中间步行约12分钟。",
        {
          candidate_id: "activity_market_401",
          name: "室内市集馆",
          address: "上海市黄浦区市集路22号",
          tags: ["indoor", "market"],
        },
        {
          candidate_id: "restaurant_cafe_401",
          name: "Warm Cafe Corner",
          address: "Rainy Cafe Street 14",
          tags: ["warm_food", "nearby", "quiet"],
        },
        "A usable route to the quieter cafe fallback nearby.",
        "restaurant_cafe_401",
      ),
      translatedName: "暖食咖啡角",
      rawText: /Warm Cafe Corner|Rainy Cafe Street 14/,
      translatedRoute: "这条路线可通往附近更安静的咖啡馆备选。",
      translatedTag: "热食",
    },
    {
      name: "budget",
      run: buildMultiScenarioRun(
        "run-budget",
        "plan-budget",
        "河边免费公园步道 + Value Bistro Express",
        "先去河边免费公园步道安排低预算活动，再去Value Bistro Express吃一顿平价简餐，中间步行约12分钟。",
        {
          candidate_id: "activity_park_501",
          name: "河边免费公园步道",
          address: "上海市普陀区光复西路218号附近",
          tags: ["free_activity", "light_activity"],
        },
        {
          candidate_id: "restaurant_bistro_501",
          name: "Value Bistro Express",
          address: "Budget Avenue 20",
          tags: ["budget_limited", "value_set", "premium"],
        },
        "A valid route, but it is longer than the canonical park-to-bento walk.",
        "restaurant_bistro_501",
      ),
      translatedName: "高性价比小馆快线",
      rawText: /Value Bistro Express|Budget Avenue 20/,
      translatedRoute: "这条路线可用，但比首选公园到便当店的步行更长。",
      translatedTag: "预算有限",
    },
  ])("localizes reviewer-visible fallback text for $name scenario", async ({ run, translatedName, rawText, translatedRoute, translatedTag }) => {
    const user = userEvent.setup();
    const items = projectConversationThread({
      entries: [{ id: run.run_id, kind: "run", run }],
      activeRunId: run.run_id,
      selectedPlanId: run.selected_plan_id,
    });

    render(
      <ConversationThread
        items={items}
        activeRunId={run.run_id}
        requestState="idle"
        canConfirm
        canDecline
        onSelectPlan={vi.fn()}
        onConfirm={vi.fn()}
        onDecline={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: new RegExp(translatedName) })).toBeInTheDocument();
    expect(screen.queryByText(rawText)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "路线与可执行性" }));
    expect(screen.getByText(translatedRoute)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "活动与餐厅" }));
    expect(document.body.textContent).toContain(translatedTag);

    await user.click(screen.getByRole("button", { name: "确认前动作" }));
    expect(screen.queryByText(/activity_|restaurant_/)).not.toBeInTheDocument();
  });
});
