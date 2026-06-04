import type {
  DemoActionManifestItemSummary,
  DemoActionManifestSummary,
  DemoCandidateSummary,
  DemoClarificationSummary,
  DemoExecutionActionResultSummary,
  DemoPlanPreview,
  DemoProgressSummary,
  DemoProgressStepSummary,
  DemoReadProfile,
  DemoRunSummary,
} from "../types/demo";

export type ConversationHistoryEntry =
  | {
      id: string;
      kind: "user";
      event: "start" | "clarify" | "replan" | "confirm" | "decline";
      text: string;
    }
  | {
      id: string;
      kind: "run";
      run: DemoRunSummary;
    };

export type PendingConversationAction = {
  id: string;
  kind: "system_progress";
  label: string;
  status: string;
};

export type ConversationThreadItem =
  | {
      id: string;
      kind: "user_message";
      event: ConversationHistoryEntry extends infer Entry
        ? Entry extends { kind: "user"; event: infer Event }
          ? Event
          : never
        : never;
      text: string;
    }
  | PendingConversationAction
  | AssistantProgressCardItem
  | AssistantClarificationItem
  | AssistantPlanCardItem
  | AssistantResultCardItem;

export type AssistantProgressCardItem = {
  id: string;
  kind: "assistant_progress_card";
  runId: string;
  currentStage: string;
  currentLabel: string;
  currentSummary: string;
  completedSteps: Array<{
    stage: string;
    label: string;
    summary: string;
  }>;
  completedCollapsedByDefault: true;
};

export type AssistantClarificationItem = {
  id: string;
  kind: "assistant_clarification";
  runId: string;
  versionLabel: string;
  prompt: string;
  missingFields: Array<{ id: string; label: string }>;
  followUpKind: "clarification";
  hiddenRunInfo: HiddenRunInfo;
};

export type AssistantPlanCardItem = {
  id: string;
  kind: "assistant_plan_card";
  runId: string;
  planId: string;
  title: string;
  summary: string;
  versionLabel: string;
  visibleBadges: string[];
  alternativePlans: Array<{ planId: string; title: string; selected: boolean }>;
  sections: PlanSectionSummary[];
  readOnlyPreview: boolean;
  canConfirm: boolean;
  canDecline: boolean;
  canReplan: boolean;
  canRefresh: boolean;
  followUpKind: "replan" | "confirmation";
  plan: DemoPlanPreview;
  hiddenRunInfo: HiddenRunInfo;
};

export type AssistantResultCardItem = {
  id: string;
  kind: "assistant_result_card";
  runId: string;
  planId: string;
  headline: string;
  message: string | null;
  finalArrangementMessage: string | null;
  outcomeLabel: string;
  executionTimeline: ExecutionTimelineStep[];
  timelineCollapsedByDefault: true;
  executionWindow: {
    startedAt: string | null;
    finishedAt: string | null;
  };
  hasVisibleTimeline: boolean;
  completedActions: Record<string, unknown>[];
  failedActions: Record<string, unknown>[];
  nextSteps: string[];
};

export type HiddenRunInfo = {
  collapsedByDefault: true;
  runId: string;
  versionLabel: string;
  readProfileLabel: string;
};

export type PlanSectionSummary = {
  id: "timeline" | "activity_dining" | "route_feasibility" | "pre_confirmation_actions";
  title: string;
  collapsedByDefault: true;
  hasContent: boolean;
};

export type ExecutionTimelineStep = {
  actionRef: string | null;
  executionOrder: number;
  label: string;
  targetId: string | null;
  statusLabel: string;
};

type ProjectConversationThreadOptions = {
  entries: ConversationHistoryEntry[];
  activeRunId?: string | null;
  selectedPlanId?: string | null;
  pendingAction?: PendingConversationAction | AssistantProgressCardItem | null;
};

const RESULT_RUN_STATUSES = new Set(["completed", "partially_completed", "failed", "skipped", "declined"]);

const EXACT_USER_TEXT_LABELS: Record<string, string> = {
  "Family Afternoon Plan": "亲子下午方案",
  "Backup Walk Plan": "备选散步方案",
  "Indoor activity": "室内亲子活动",
  "Indoor activity first, then a lighter dinner nearby.": "先安排室内亲子活动，再去附近吃清淡晚餐。",
  "A lighter backup plan with less structure.": "节奏更轻的备选方案。",
  "A short drive keeps the afternoon easy.": "短途驾车，下午节奏更轻松。",
  "Fits the requested afternoon window.": "符合下午出行时间。",
  "Plan completed": "安排已完成",
  "Reservation and follow-up message both completed.": "订座和后续消息都已完成。",
  "Leave a little before 2pm.": "建议 14:00 前稍早出发。",
  "A longer but usable museum-to-garden-dining route for the fallback family dinner.":
    "博物馆到花园轻食餐厅的步行路线稍长，但仍可用于备选家庭晚餐。",
  "A valid walking link, but it is longer than the canonical museum-to-light-dining path.":
    "这条步行路线可用，但比首选的科学馆到轻食餐厅路线稍长。",
  "A child-friendly craft stop that would normally fit the family plan, but today's ticket inventory is sold out.":
    "适合亲子手作体验，但今天票务已售罄。",
  "A usable but quieter child-friendly stop that feels slower and less playful than the canonical family outing route.":
    "安静的亲子阅读空间，适合作为节奏更慢的备选活动。",
  "A lighter family-friendly dining room that looks suitable, but tables are unavailable and the queue is closed.":
    "清淡、亲子友好的备选餐厅，但当前桌位不可订且排队关闭。",
  "A usable lighter family meal, but it is slower and less polished than the canonical light dining choice.":
    "可作为清淡家庭晚餐备选，但服务节奏比首选轻食餐厅更慢。",
  "Dining room is closed for a private event.": "餐厅因包场活动暂停接待。",
  "Usable family tables remain, but service is slower than the canonical option.":
    "仍有家庭桌位可用，但服务节奏比首选餐厅更慢。",
  "Lock dinner seating after confirmation.": "确认后可提前锁定晚餐座位。",
  "User chose not to continue.": "用户选择暂不继续。",
  "A usable outdoor link, but slower than the canonical lawn-to-yard pairing.": "这条户外步行路线可用，但比首选草坪到庭院餐吧的组合更慢。",
  "A valid route to the quieter dinner fallback farther down the block.": "这条路线可通往街区更安静的晚餐备选，但不是首选聚会晚餐动线。",
  "A straightforward walk from the gallery to a louder dining room farther down the block.": "从展馆步行到更热闹的备选餐厅路线直接，但整体氛围不如首选单人晚餐。",
  "A usable walking link, but it is slightly longer than the canonical gallery-to-dinner route.": "这条步行路线可用，但比首选展馆到晚餐的路线稍长。",
  "A valid covered walk, but slower than the canonical market-to-soup transfer.": "这条有遮挡的步行路线可用，但比首选室内市集到热汤店的衔接更慢。",
  "A usable route to the quieter cafe fallback nearby.": "这条路线可通往附近更安静的咖啡馆备选。",
  "A valid route, but it is longer than the canonical park-to-bento walk.": "这条路线可用，但比首选公园到便当店的步行更长。",
  "A usable route to the pricier dinner fallback farther down the block.": "这条路线可通往街区更远、价格更高的晚餐备选。",
};

const INLINE_USER_TEXT_REPLACEMENTS: Array<[string, string]> = [
  ["Garden Supper Room", "花园家庭轻食餐室"],
  ["Riverside Reading Hall", "滨江亲子阅读馆"],
  ["Story Atelier House", "亲子手作小屋"],
  ["Picnic Greens Table", "野餐绿蔬餐桌"],
  ["Family Science Center", "亲子科学中心"],
  ["Light Table", "轻食餐桌"],
  ["Riverside Walk", "滨江散步路线"],
  ["Simple Kitchen", "简餐厨房"],
  ["100 Science Road", "上海市徐汇区科学路100号"],
  ["8 Dinner Street", "上海市徐汇区晚餐街8号"],
  ["28 Riverside Road", "上海市徐汇区滨江路28号"],
  ["5 Cafe Street", "上海市徐汇区咖啡街5号"],
  ["Family Garden Road 15", "上海市徐汇区花园路15号"],
  ["Family Garden Road 9", "上海市徐汇区花园路9号"],
  ["Family Riverside Walk 20", "上海市徐汇区滨江阅读步道20号"],
  ["Family Studio Road 12", "上海市徐汇区亲子手作路12号"],
  ["Lighter dishes are available, but it remains a weaker fit than the canonical light family meal.", "也提供清淡菜品，但整体匹配度弱于首选轻食餐厅。"],
  ["Team Arcade Lawn", "团队街机草坪场"],
  ["Friends Park Lane 9", "上海市长宁区朋友公园里9号"],
  ["Promenade Bench Loop", "沿河长椅散步环线"],
  ["Friends Riverside Walk 14", "上海市长宁区朋友滨河步道14号"],
  ["Patio Queue House", "露台排队餐屋"],
  ["Friends Patio Road 11", "上海市长宁区朋友露台路11号"],
  ["Quiet Bistro Corner", "安静小酒馆角落"],
  ["Friends Corner Street 16", "上海市长宁区朋友街角路16号"],
  ["Service is paused for a private patio buyout.", "露台区域被包场，当前暂停接待。"],
  ["Usable seating remains, but the room is less group-oriented.", "仍有座位可用，但整体氛围不如首选朋友聚餐路线。"],
  ["Solo Sketch Studio", "单人速写工作室"],
  ["Jing'an District Studio Lane 18", "上海市静安区工作室里18号"],
  ["Shared Table Game Loft", "共享桌游阁楼"],
  ["Jing'an District Loft Street 22", "上海市静安区阁楼街22号"],
  ["Counter Salad Bar", "吧台沙拉小馆"],
  ["Jing'an District Counter Road 10", "上海市静安区吧台路10号"],
  ["Shared Plates Kitchen", "共享餐盘厨房"],
  ["Jing'an District Social Street 14", "上海市静安区社交街14号"],
  ["Light sides are available, but it is still more utilitarian than the canonical light dining stop.", "也有清淡配菜，但整体更偏功能型，不如首选轻食餐厅舒适。"],
  ["A calm sketch workshop that looks appealing for a solo afternoon, but today's drop-in tickets are sold out.", "安静的速写工作室原本适合单人下午，但今天现场票已售罄。"],
  ["A usable but group-leaning board-game loft that feels louder and less focused than the canonical solo gallery stop.", "可作为备选的桌游阁楼更偏多人社交，比首选单人展馆更热闹。"],
  ["The menu fits the lighter-dinner request, but today's counter service is unavailable and the queue is paused.", "菜单符合清淡晚餐需求，但今天吧台服务暂停，排队也已停止。"],
  ["A usable lighter menu, but the room is more group-oriented and noisier than the canonical solo dinner choice.", "菜单可用，但环境更偏多人聚会，比首选单人晚餐更嘈杂。"],
  ["Indoor Arcade Hall", "室内街机厅"],
  ["Rainy Arcade Road 6", "上海市黄浦区雨天街机路6号"],
  ["Covered Garden Hall", "有顶花园厅"],
  ["Rainy Hall Street 18", "上海市黄浦区雨天花园街18号"],
  ["Hotpot Queue Counter", "火锅排队柜台"],
  ["Rainy Soup Lane 10", "上海市黄浦区雨天热汤里10号"],
  ["Warm Cafe Corner", "暖食咖啡角"],
  ["Rainy Cafe Street 14", "上海市黄浦区雨天咖啡街14号"],
  ["The hotpot line is closed because the kitchen is at capacity.", "火锅档口因后厨满负荷，当前已停止排队。"],
  ["Tables remain, but the menu is lighter and less focused than the canonical soup fallback.", "仍有座位，但菜单更轻，整体不如首选热汤备选聚焦。"],
  ["Budget Workshop Pop-up", "预算友好快闪工坊"],
  ["Budget Lane 5", "上海市普陀区预算里5号"],
  ["Design Mall Walkthrough", "设计商场漫步"],
  ["Budget Avenue 12", "上海市普陀区预算大道12号"],
  ["Budget Cafe Counter", "平价咖啡吧台"],
  ["Budget Avenue 16", "上海市普陀区预算大道16号"],
  ["Value Bistro Express", "高性价比小馆快线"],
  ["Budget Avenue 20", "上海市普陀区预算大道20号"],
  ["Counter is short-staffed and not seating walk-ins.", "吧台人手不足，当前不接待现场入座。"],
  ["Seats are available, but the spend is higher than the canonical budget route.", "虽然仍有座位，但整体花费高于首选预算路线。"],
];

const TARGET_ID_LABELS: Record<string, string> = {
  activity_museum_001: "徐汇亲子科学馆",
  activity_playground_001: "滨江亲子乐园",
  activity_walk_001: "武康路亲子城市漫步",
  activity_story_atelier_001: "亲子手作小屋",
  activity_riverside_reading_001: "滨江亲子阅读馆",
  restaurant_light_001: "绿碗家庭轻食",
  restaurant_family_001: "晴天家庭厨房",
  restaurant_noodle_001: "简单面馆",
  restaurant_picnic_001: "野餐绿蔬餐桌",
  restaurant_garden_001: "花园家庭轻食餐室",
  addon_drinks_001: "小水分补给站",
  activity_gallery_001: "静安轻展馆",
  activity_studio_001: "单人速写工作室",
  activity_boardgame_001: "共享桌游阁楼",
  restaurant_counter_001: "吧台沙拉小馆",
  restaurant_sharedplates_001: "共享餐盘厨房",
  activity_citywalk_201: "法式街区漫步",
  activity_gallery_201: "街角小画廊",
  activity_conservatory_201: "温室花房",
  activity_courtyard_201: "庭院慢逛空间",
  restaurant_light_201: "小馆轻食",
  restaurant_bistro_201: "约会小酒馆",
  restaurant_patio_201: "露台晚餐小馆",
  restaurant_sharing_201: "共享餐盘小馆",
  activity_lawn_301: "苏河边草坪聚会点",
  activity_sports_301: "街区运动公园",
  activity_arcade_301: "团队街机草坪场",
  activity_promenade_301: "沿河长椅散步环线",
  restaurant_yard_301: "庭院分享餐吧",
  restaurant_noodle_301: "朋友局面馆",
  restaurant_patio_301: "露台排队餐屋",
  restaurant_bistro_301: "安静小酒馆角落",
  activity_market_401: "室内市集馆",
  activity_booklounge_401: "雨天书房休息室",
  activity_arcade_401: "室内街机厅",
  activity_gardenhall_401: "有顶花园厅",
  restaurant_soup_401: "热汤简餐屋",
  restaurant_rice_401: "街角饭碗店",
  restaurant_hotpot_401: "火锅排队柜台",
  restaurant_cafe_401: "暖食咖啡角",
  activity_park_501: "河边免费公园步道",
  activity_gallery_501: "社区免费展廊",
  activity_workshop_501: "预算友好快闪工坊",
  activity_designmall_501: "设计商场漫步",
  restaurant_bento_501: "平价便当小馆",
  restaurant_noodle_501: "街坊面馆",
  restaurant_cafe_501: "平价咖啡吧台",
  restaurant_bistro_501: "高性价比小馆快线",
};

export function projectConversationThread({
  entries,
  activeRunId,
  selectedPlanId,
  pendingAction,
}: ProjectConversationThreadOptions): ConversationThreadItem[] {
  const items: ConversationThreadItem[] = [];

  for (const entry of entries) {
    if (entry.kind === "user") {
      items.push({
        id: entry.id,
        kind: "user_message",
        event: entry.event,
        text: entry.text,
      });
      continue;
    }

    const localSelectedPlanId = entry.run.run_id === activeRunId ? selectedPlanId : null;
    items.push(...projectRunItems(entry.run, localSelectedPlanId));
  }

  if (pendingAction) {
    items.push(pendingAction);
  }

  return items;
}

export function projectRunItems(run: DemoRunSummary, selectedPlanId?: string | null): ConversationThreadItem[] {
  const items: ConversationThreadItem[] = [];
  const clarification = isClarificationSummary(run.clarification) ? run.clarification : null;
  const resolvedPlan = choosePlan(run, selectedPlanId ?? null);
  const progressItem = buildProgressItem(run);

  if (progressItem) {
    items.push(progressItem);
  }

  if (run.status === "awaiting_clarification" && clarification) {
    items.push(buildClarificationItem(run, clarification));
    return items;
  }

  if (resolvedPlan) {
    items.push(buildPlanCardItem(run, resolvedPlan, selectedPlanId ?? null));
  }

  if (resolvedPlan && shouldRenderResultCard(run, resolvedPlan)) {
    items.push(buildResultCardItem(run, resolvedPlan));
  }

  return items;
}

function buildProgressItem(run: DemoRunSummary): AssistantProgressCardItem | null {
  return buildProgressCardItem(run.run_id, run.progress);
}

export function buildProgressCardItem(
  runId: string,
  progress: DemoProgressSummary | null | undefined,
): AssistantProgressCardItem | null {
  const steps = normalizeProgressSteps(progress?.steps);
  if (!steps.length || !progress) {
    return null;
  }

  const currentStep = steps[steps.length - 1];
  const currentSummary = safeText(currentStep.summary) || safeText(progress.current_label) || currentStep.label;

  return {
    id: `${runId}-progress`,
    kind: "assistant_progress_card",
    runId,
    currentStage: currentStep.stage,
    currentLabel: currentStep.label,
    currentSummary,
    completedSteps: steps.slice(0, -1).map((step) => ({
      stage: step.stage,
      label: step.label,
      summary: step.summary,
    })),
    completedCollapsedByDefault: true,
  };
}

function normalizeProgressSteps(value: unknown): DemoProgressStepSummary[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((step): step is DemoProgressStepSummary => {
    if (!step || typeof step !== "object") {
      return false;
    }

    const candidate = step as Partial<DemoProgressStepSummary>;
    return (
      typeof candidate.stage === "string" &&
      typeof candidate.label === "string" &&
      typeof candidate.summary === "string" &&
      (candidate.status === "completed" || candidate.status === "current")
    );
  });
}

function buildClarificationItem(run: DemoRunSummary, clarification: DemoClarificationSummary): AssistantClarificationItem {
  return {
    id: `${run.run_id}-clarification`,
    kind: "assistant_clarification",
    runId: run.run_id,
    versionLabel: run.plan_version.version_label,
    prompt: clarification.prompt,
    missingFields: clarification.missing_fields.map((field) => ({
      id: field,
      label: clarificationFieldLabel(field),
    })),
    followUpKind: "clarification",
    hiddenRunInfo: buildHiddenRunInfo(run),
  };
}

function buildPlanCardItem(
  run: DemoRunSummary,
  plan: DemoPlanPreview,
  selectedPlanId?: string | null,
): AssistantPlanCardItem {
  const planOptions = run.plans.map((candidate, index) => ({
    planId: candidate.plan_id,
    title: userFacingText(candidate.title) || `方案 ${index + 1}`,
    selected: candidate.plan_id === plan.plan_id,
  }));
  const isReadOnlyPreview = run.read_profile === "amap";
  const canConfirm = run.status === "awaiting_confirmation" && !isReadOnlyPreview;
  const canDecline = run.status === "awaiting_confirmation";
  const canReplan = run.status === "awaiting_confirmation";

  return {
    id: `${run.run_id}-${plan.plan_id}-plan`,
    kind: "assistant_plan_card",
    runId: run.run_id,
    planId: plan.plan_id,
    title: userFacingText(plan.title) || "推荐方案",
    summary: userFacingText(plan.summary) || "已生成一份可继续确认的推荐方案。",
    versionLabel: run.plan_version.version_label,
    visibleBadges: [run.plan_version.version_label, statusLabel(run.status) || run.status],
    alternativePlans: planOptions,
    sections: [
      {
        id: "timeline",
        title: "时间线",
        collapsedByDefault: true,
        hasContent: Boolean(plan.timeline?.length),
      },
      {
        id: "activity_dining",
        title: "活动与餐厅",
        collapsedByDefault: true,
        hasContent: Boolean(plan.activity || plan.dining),
      },
      {
        id: "route_feasibility",
        title: "路线与可执行性",
        collapsedByDefault: true,
        hasContent: Boolean(plan.route || plan.feasibility),
      },
      {
        id: "pre_confirmation_actions",
        title: "确认前动作",
        collapsedByDefault: true,
        hasContent: Boolean(plan.action_manifest.actions.length),
      },
    ],
    readOnlyPreview: isReadOnlyPreview,
    canConfirm,
    canDecline,
    canReplan,
    canRefresh: true,
    followUpKind: run.status === "awaiting_confirmation" ? "replan" : "confirmation",
    plan,
    hiddenRunInfo: buildHiddenRunInfo(run),
  };
}

function buildResultCardItem(run: DemoRunSummary, plan: DemoPlanPreview): AssistantResultCardItem {
  const executionTimeline = normalizeExecutionActions(plan.execution?.action_results, plan);
  const feedback = plan.feedback;
  const isDeclined = run.status === "declined" || plan.confirmation?.status === "declined";
  const outcomeLabel = isDeclined ? "已放弃" : statusLabel(plan.execution?.status || run.execution_status) || "执行结果";

  return {
    id: `${run.run_id}-${plan.plan_id}-result`,
    kind: "assistant_result_card",
    runId: run.run_id,
    planId: plan.plan_id,
    headline:
      userFacingText(feedback?.headline) ||
      (isDeclined ? "已放弃当前方案" : statusLabel(plan.execution?.status || run.status) || "执行结果"),
    message:
      userFacingText(plan.confirmation?.reason) ||
      userFacingText(feedback?.message) ||
      (isDeclined ? "已在执行前放弃当前方案。" : null),
    finalArrangementMessage: userFacingText(feedback?.final_arrangement_message) || null,
    outcomeLabel,
    executionTimeline,
    timelineCollapsedByDefault: true,
    executionWindow: {
      startedAt: plan.execution?.started_at ?? null,
      finishedAt: plan.execution?.finished_at ?? null,
    },
    hasVisibleTimeline: Boolean(plan.execution?.started_at || plan.execution?.finished_at || executionTimeline.length),
    completedActions: feedback?.completed_actions ?? [],
    failedActions: feedback?.failed_actions ?? [],
    nextSteps: feedback?.next_steps ?? [],
  };
}

function buildHiddenRunInfo(run: DemoRunSummary): HiddenRunInfo {
  return {
    collapsedByDefault: true,
    runId: run.run_id,
    versionLabel: run.plan_version.version_label,
    readProfileLabel: readProfileLabel(run.read_profile) || run.read_profile,
  };
}

function shouldRenderResultCard(run: DemoRunSummary, plan: DemoPlanPreview) {
  if (run.status === "declined" || plan.confirmation?.status === "declined") {
    return true;
  }

  return Boolean(plan.execution || plan.feedback || RESULT_RUN_STATUSES.has(run.status));
}

export function choosePlan(run: DemoRunSummary | null, selectedPlanId: string | null): DemoPlanPreview | null {
  if (!run?.plans.length) {
    return null;
  }

  return (
    run.plans.find((plan) => plan.plan_id === selectedPlanId) ??
    run.plans.find((plan) => plan.plan_id === run.selected_plan_id) ??
    run.plans.find((plan) => plan.selected) ??
    run.plans[0]
  );
}

export function resolveSelectedPlanIndex(run: DemoRunSummary | null, selectedPlanId: string | null): number {
  if (!run?.plans.length) {
    return 0;
  }

  const directMatchIndex = run.plans.findIndex((plan) => plan.plan_id === selectedPlanId);
  if (directMatchIndex >= 0) {
    return directMatchIndex;
  }

  const resolvedPlan = choosePlan(run, selectedPlanId);
  if (!resolvedPlan) {
    return 0;
  }

  const resolvedPlanIndex = run.plans.findIndex((plan) => plan.plan_id === resolvedPlan.plan_id);
  return resolvedPlanIndex >= 0 ? resolvedPlanIndex : 0;
}

export function progressLabelForState(value: string) {
  const labels: Record<string, string> = {
    starting: "正在生成推荐方案...",
    clarifying: "正在结合补充信息继续规划...",
    replanning: "正在根据新要求调整方案...",
    refreshing: "正在刷新当前进度...",
    confirming: "正在确认并执行当前方案...",
    declining: "正在结束当前方案...",
  };
  return labels[value] ?? "正在处理你的请求...";
}

export function display(value?: string | number | null) {
  if (value === null || value === undefined || value === "") {
    return "暂无";
  }
  return String(value);
}

export function displayUserText(value?: string | number | null) {
  if (value === null || value === undefined || value === "") {
    return "暂无";
  }
  if (typeof value === "number") {
    return String(value);
  }
  return userFacingText(value) || "暂无";
}

export function numberValue(value?: number | null) {
  return typeof value === "number" ? String(value) : undefined;
}

export function minutes(value?: number | null) {
  return typeof value === "number" ? `${value} 分钟` : "暂无";
}

export function distance(value?: number | null) {
  if (typeof value !== "number") {
    return "暂无";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} 公里`;
  }
  return `${value} 米`;
}

export function routeMode(value?: string | null) {
  const labels: Record<string, string> = {
    walking: "步行",
    driving: "驾车",
  };
  return value ? labels[value] ?? value : null;
}

export function categoryLabel(value?: string | null) {
  const labels: Record<string, string> = {
    activity: "活动",
    dining: "用餐",
    addon: "加购",
  };
  return value ? labels[value] ?? value : null;
}

export function tagLabel(value: string) {
  const labels: Record<string, string> = {
    child_friendly: "亲子友好",
    indoor: "室内",
    museum: "博物馆",
    educational: "益智科普",
    outdoor: "户外",
    playground: "游乐场",
    citywalk: "城市漫步",
    light_activity: "轻量活动",
    creative: "手作创意",
    reading: "阅读空间",
    lighter_options: "清淡选项",
    quiet: "安静",
    vegetable_forward: "多蔬轻食",
    family_tables: "家庭座位",
    balanced_menu: "均衡菜单",
    quick_meal: "快速用餐",
    simple: "简单餐食",
    drinks: "饮品",
    snacks: "小食",
    family: "家庭友好",
    group_friendly: "适合朋友聚会",
    hangout: "轻松聚会",
    sports: "轻运动",
    casual_dining: "轻松用餐",
    friends_group: "朋友同行",
    sharing_plates: "适合分享",
    slow_service: "出餐较慢",
    couple_friendly: "适合两人同行",
    date_friendly: "适合约会",
    casual: "轻松氛围",
    social: "适合社交",
    gallery: "画廊",
    light_meal: "轻食",
    family_pause: "适合短暂休息",
    comfort_food: "暖胃热食",
    market: "市集",
    nearby: "就近",
    warm_food: "热食",
    restaurant: "餐饮",
    budget_limited: "预算有限",
    free_activity: "免费活动",
    premium: "价格偏高",
    value_set: "平价套餐",
  };
  return labels[value] ?? value;
}

export function feasibilityLabel(value?: boolean | null) {
  if (value === true) {
    return "可执行";
  }
  if (value === false) {
    return "不可执行";
  }
  return "暂无";
}

export function safeText(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

export function normalizeExecutionActions(
  actions?: DemoExecutionActionResultSummary[],
  plan?: DemoPlanPreview,
): ExecutionTimelineStep[] {
  if (!Array.isArray(actions)) {
    return [];
  }

  return actions
    .map((action) => {
      const executionOrder = action.execution_order;
      if (typeof executionOrder !== "number" || executionOrder <= 0) {
        return null;
      }

      return {
        actionRef: safeText(action.action_ref),
        executionOrder,
        label: actionLabel(safeText(action.tool_name) || safeText(action.action_type)) || "动作",
        targetId: plan
          ? actionTargetLabel(plan, safeText(action.target_id), safeText(action.tool_name) || safeText(action.action_type))
          : userFacingText(safeText(action.target_id)),
        statusLabel: executionActionStatusLabel(safeText(action.status)),
      };
    })
    .filter((action): action is NonNullable<typeof action> => action !== null)
    .sort((left, right) => left.executionOrder - right.executionOrder);
}

export function actionLabel(value?: string | null) {
  const labels: Record<string, string> = {
    book_ticket: "订票",
    reserve_restaurant: "订座",
    join_queue: "排队取号",
    order_addon: "加购",
    send_message: "发送消息",
  };
  return value ? labels[value] ?? value : null;
}

export function actionExecutionLabel(value?: number | null) {
  return typeof value === "number" ? `第 ${value} 步` : "待确认执行顺序";
}

export function actionManifestSourceLabel(manifest: DemoActionManifestSummary) {
  if (manifest.source === "confirmed_actions") {
    return "以下为确认后将执行的动作清单。";
  }
  if (manifest.source === "proposed_actions") {
    return "以下为确认前的动作预览，尚未执行任何写操作。";
  }
  return "当前方案没有可公开展示的动作预览。";
}

export function feedbackStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    completed: "已完成",
    already_completed: "已完成",
    failed: "失败",
    blocked: "已阻止",
    rate_limited: "限流",
    succeeded: "成功",
    written: "已生成",
  };
  return value ? labels[value] ?? value : null;
}

export function executionActionStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    succeeded: "成功",
    failed: "失败",
    blocked: "已阻止",
    rate_limited: "限流",
    idempotent_replay: "幂等重放",
  };
  return value ? labels[value] ?? value : "未知";
}

export function clarificationFieldLabel(value: string) {
  const labels: Record<string, string> = {
    scenario_or_participants: "出行人 / 场景",
    time_window: "时间安排",
    distance_flexibility: "距离取舍",
    preference_tradeoff: "偏好取舍",
  };
  return labels[value] ?? value;
}

export function userFacingText(value?: string | null) {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const exact = EXACT_USER_TEXT_LABELS[trimmed];
  if (exact) {
    return exact;
  }

  return INLINE_USER_TEXT_REPLACEMENTS.reduce(
    (text, [source, replacement]) => text.split(source).join(replacement),
    trimmed,
  );
}

export function statusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    idle: "待开始",
    starting: "规划中",
    clarifying: "提交补充中",
    replanning: "重新规划中",
    awaiting_confirmation: "等待确认",
    awaiting_clarification: "等待补充信息",
    refreshing: "刷新中",
    confirming: "确认中",
    declining: "处理中",
    completed: "已完成",
    partially_completed: "部分完成",
    failed: "失败",
    skipped: "已跳过",
    declined: "已放弃",
    error: "请求失败",
    reviewed: "已审核",
    selected: "已选中",
    draft: "草案",
    executed: "已执行",
    pending: "待确认",
    confirmed: "已确认",
    written: "已生成",
    succeeded: "成功",
  };
  return value ? labels[value] ?? value : null;
}

export function readProfileLabel(profile?: DemoReadProfile | null) {
  if (profile === "amap") {
    return "地图只读预览";
  }
  if (profile === "mock_world") {
    return "本地演示数据";
  }
  return null;
}

export function readProfileHelper(profile: DemoReadProfile) {
  if (profile === "amap") {
    return "地图只读预览会在确认前停止，不会执行写操作。";
  }
  return "使用本地演示数据生成稳定示例。";
}

export function isClarificationSummary(
  value: DemoRunSummary["clarification"] | undefined,
): value is DemoClarificationSummary {
  return Boolean(
    value &&
      typeof value.prompt === "string" &&
      Array.isArray(value.missing_fields) &&
      value.missing_fields.every((field) => typeof field === "string"),
  );
}

export function candidateSummaryLines(candidate?: DemoCandidateSummary | null) {
  if (!candidate) {
    return [];
  }

  return [
    candidateName(candidate),
    categoryLabel(candidate.category) || null,
    userFacingText(candidate.address),
    candidate.tags?.length ? candidate.tags.map(tagLabel).join("、") : null,
  ].filter((line): line is string => Boolean(line));
}

export function actionTargetLabel(
  plan: DemoPlanPreview,
  targetId?: string | null,
  actionType?: string | null,
) {
  const normalizedTargetId = safeText(targetId);
  if (!normalizedTargetId) {
    return "目标待确认";
  }

  const matchedCandidate = [plan.activity, plan.dining].find(
    (candidate) => candidate?.candidate_id === normalizedTargetId,
  );
  const matchedName = candidateName(matchedCandidate);
  if (matchedName) {
    return actionType === "join_queue" ? `${matchedName}排队取号` : matchedName;
  }

  if (actionType === "book_ticket") {
    return candidateName(plan.activity) || TARGET_ID_LABELS[normalizedTargetId] || "活动目标待确认";
  }
  if (actionType === "reserve_restaurant" || actionType === "join_queue") {
    const diningName = candidateName(plan.dining) || TARGET_ID_LABELS[normalizedTargetId];
    if (diningName) {
      return actionType === "join_queue" ? `${diningName}排队取号` : diningName;
    }
    return "餐厅目标待确认";
  }

  return TARGET_ID_LABELS[normalizedTargetId] || "目标待确认";
}

function candidateName(candidate?: DemoCandidateSummary | null) {
  if (!candidate) {
    return null;
  }
  return userFacingText(candidate.name);
}
