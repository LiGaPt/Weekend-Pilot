import type {
  DemoActionManifestSummary,
  DemoCandidateSummary,
  DemoClarificationSummary,
  DemoExecutionActionResultSummary,
  DemoPlanPreview,
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
  | AssistantClarificationItem
  | AssistantPlanCardItem
  | AssistantResultCardItem;

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
  pendingAction?: PendingConversationAction | null;
};

const RESULT_RUN_STATUSES = new Set(["completed", "partially_completed", "failed", "skipped", "declined"]);

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
    title: candidate.title?.trim() || `方案 ${index + 1}`,
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
    title: plan.title?.trim() || "推荐方案",
    summary: plan.summary?.trim() || "已生成一份可继续确认的推荐方案。",
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
  const executionTimeline = normalizeExecutionActions(plan.execution?.action_results);
  const feedback = plan.feedback;
  const isDeclined = run.status === "declined" || plan.confirmation?.status === "declined";
  const outcomeLabel = isDeclined ? "已放弃" : statusLabel(plan.execution?.status || run.execution_status) || "执行结果";

  return {
    id: `${run.run_id}-${plan.plan_id}-result`,
    kind: "assistant_result_card",
    runId: run.run_id,
    planId: plan.plan_id,
    headline:
      feedback?.headline?.trim() ||
      (isDeclined ? "已放弃当前方案" : statusLabel(plan.execution?.status || run.status) || "执行结果"),
    message:
      userFacingText(plan.confirmation?.reason) ||
      feedback?.message?.trim() ||
      (isDeclined ? "已在执行前放弃当前方案。" : null),
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

export function normalizeExecutionActions(actions?: DemoExecutionActionResultSummary[]): ExecutionTimelineStep[] {
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
        targetId: safeText(action.target_id),
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

  const mapped: Record<string, string> = {
    "User chose not to continue.": "用户选择暂不继续。",
  };
  return mapped[value] ?? value;
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
    return "AMap 只读预览";
  }
  if (profile === "mock_world") {
    return "Mock World";
  }
  return null;
}

export function readProfileHelper(profile: DemoReadProfile) {
  if (profile === "amap") {
    return "AMap 路径仅用于本地只读预览，在确认前停止，不会执行写操作。";
  }
  return "Mock World 是默认路径，也是 benchmark 的稳定默认值。";
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
    candidate.name?.trim() || null,
    categoryLabel(candidate.category) || null,
    candidate.address?.trim() || null,
    candidate.tags?.length ? candidate.tags.map(tagLabel).join("、") : null,
  ].filter((line): line is string => Boolean(line));
}
