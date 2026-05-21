import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock3,
  ClipboardCheck,
  Loader2,
  MapPinned,
  Play,
  RefreshCw,
  RotateCcw,
  Route,
  Send,
  Utensils,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { confirmRun, declineRun, getRun, startRun } from "./api/demo";
import type {
  DemoCandidateSummary,
  DemoPlanPreview,
  DemoRunSummary,
} from "./types/demo";

const DEFAULT_PROMPT =
  "今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。孩子要适合亲子活动，爱人最近想吃清淡一点，帮我安排一下。";
const GENERIC_ERROR_MESSAGE = "演示请求失败，请稍后重试。";

type RequestState =
  | "idle"
  | "starting"
  | "awaiting_confirmation"
  | "refreshing"
  | "confirming"
  | "declining"
  | "completed"
  | "declined"
  | "error";

const TERMINAL_SUCCESS_STATUSES = new Set(["completed", "partially_completed", "failed", "skipped"]);

export default function App() {
  const [userInput, setUserInput] = useState(DEFAULT_PROMPT);
  const [run, setRun] = useState<DemoRunSummary | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedPlan = useMemo(() => choosePlan(run, selectedPlanId), [run, selectedPlanId]);
  const trimmedInput = userInput.trim();
  const inputIsEmpty = trimmedInput.length === 0;
  const isInFlight = ["starting", "refreshing", "confirming", "declining"].includes(requestState);
  const canRefresh = Boolean(run?.run_id) && !isInFlight;
  const canMutate = run?.status === "awaiting_confirmation" && Boolean(selectedPlan) && !isInFlight;
  const canConfirm = canMutate;
  const canDecline = canMutate;

  async function handleStart() {
    if (inputIsEmpty || isInFlight) {
      return;
    }
    await runAction("starting", () =>
      startRun({
        user_input: trimmedInput,
        external_user_id: "web-demo-user",
        display_name: "Web Demo User",
        case_id: "web-demo",
        selected_plan_index: 0,
      }),
    );
  }

  async function handleRefresh() {
    if (!run?.run_id || isInFlight) {
      return;
    }
    await runAction("refreshing", () => getRun(run.run_id));
  }

  async function handleConfirm() {
    if (!run?.run_id || !selectedPlan || !canConfirm) {
      return;
    }
    await runAction("confirming", () => confirmRun(run.run_id, selectedPlan.plan_id));
  }

  async function handleDecline() {
    if (!run?.run_id || !selectedPlan || !canDecline) {
      return;
    }
    await runAction("declining", () => declineRun(run.run_id, selectedPlan.plan_id));
  }

  async function runAction(nextState: RequestState, action: () => Promise<DemoRunSummary>) {
    setRequestState(nextState);
    setErrorMessage(null);
    try {
      const nextRun = await action();
      setRun(nextRun);
      setSelectedPlanId(nextRun.selected_plan_id ?? nextRun.plans[0]?.plan_id ?? null);
      setRequestState(stateFromRun(nextRun));
    } catch (error) {
      setRequestState("error");
      setErrorMessage(errorMessageForDisplay(error));
    }
  }

  return (
    <main className="app-shell">
      <section className="app-header" aria-labelledby="app-title">
        <div>
          <p className="eyebrow">WeekendPilot 中文演示</p>
          <h1 id="app-title">周末亲子半日规划</h1>
        </div>
        <StatusBadge status={requestState} />
      </section>

      <div className="app-grid">
        <aside className="side-rail" aria-label="需求和运行信息">
          <section className="panel composer-panel" aria-labelledby="request-title">
            <div className="section-heading">
              <Send size={18} aria-hidden="true" />
              <h2 id="request-title">需求</h2>
            </div>
            <label className="field-label" htmlFor="request-input">
              需求
            </label>
            <textarea
              id="request-input"
              value={userInput}
              onChange={(event) => setUserInput(event.target.value)}
              rows={8}
              disabled={isInFlight}
            />
            {inputIsEmpty ? <p className="validation-text">请输入需求后再开始规划。</p> : null}
            <div className="button-row">
              <button className="primary-button" type="button" onClick={handleStart} disabled={inputIsEmpty || isInFlight}>
                {requestState === "starting" ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
                <span>{requestState === "starting" ? "规划中" : "开始规划"}</span>
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setUserInput(DEFAULT_PROMPT);
                  setErrorMessage(null);
                }}
                disabled={isInFlight}
              >
                <RotateCcw size={17} />
                <span>重置示例</span>
              </button>
            </div>
            {errorMessage ? (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} aria-hidden="true" />
                <span>{errorMessage}</span>
              </div>
            ) : null}
          </section>

          <RunInspector run={run} onRefresh={handleRefresh} canRefresh={canRefresh} requestState={requestState} />
        </aside>

        <section className="workspace" aria-label="方案确认区">
          {run && selectedPlan ? (
            <>
              <PlanTabs
                plans={run.plans}
                selectedPlanId={selectedPlan.plan_id}
                onSelect={setSelectedPlanId}
                disabled={isInFlight}
              />
              <PlanDetail plan={selectedPlan} />
              <ConfirmationControls
                run={run}
                plan={selectedPlan}
                requestState={requestState}
                canConfirm={canConfirm}
                canDecline={canDecline}
                onConfirm={handleConfirm}
                onDecline={handleDecline}
              />
              <ExecutionResult run={run} plan={selectedPlan} />
            </>
          ) : (
            <section className="empty-workspace">
              <Clock3 size={28} aria-hidden="true" />
              <h2>准备开始演示</h2>
              <p>使用示例需求生成一个基于 Mock World 的本地生活规划。</p>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

function RunInspector({
  run,
  onRefresh,
  canRefresh,
  requestState,
}: {
  run: DemoRunSummary | null;
  onRefresh: () => void;
  canRefresh: boolean;
  requestState: RequestState;
}) {
  return (
    <section className="panel metadata-panel" aria-labelledby="run-title">
      <div className="section-heading">
        <ClipboardCheck size={18} aria-hidden="true" />
        <h2 id="run-title">运行信息</h2>
      </div>
      <dl className="metadata-list">
        <MetaItem label="运行状态" value={run?.status} testId="run-status" />
        <MetaItem label="运行 ID" value={run?.run_id} mono testId="run-id" />
        <MetaItem label="已执行操作" value={numberValue(run?.action_count)} testId="action-count" />
        <MetaItem label="执行状态" value={run?.execution_status} />
        <MetaItem label="反馈状态" value={run?.feedback_status} />
        <MetaItem label="方案版本" value={run?.plan_version.version_label} testId="plan-version" />
      </dl>
      <button
        className="secondary-button full-width"
        type="button"
        onClick={onRefresh}
        disabled={!canRefresh}
        data-testid="refresh-button"
      >
        {requestState === "refreshing" ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
        <span>{requestState === "refreshing" ? "刷新中" : "刷新状态"}</span>
      </button>
    </section>
  );
}

function PlanTabs({
  plans,
  selectedPlanId,
  onSelect,
  disabled,
}: {
  plans: DemoPlanPreview[];
  selectedPlanId: string;
  onSelect: (planId: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="plan-tabs" role="tablist" aria-label="返回方案">
      {plans.map((plan, index) => (
        <button
          key={plan.plan_id}
          role="tab"
          type="button"
          aria-selected={plan.plan_id === selectedPlanId}
          className={plan.plan_id === selectedPlanId ? "tab-button active" : "tab-button"}
          onClick={() => onSelect(plan.plan_id)}
          disabled={disabled}
        >
          <span>{plan.title || `方案 ${index + 1}`}</span>
        </button>
      ))}
    </div>
  );
}

function PlanDetail({ plan }: { plan: DemoPlanPreview }) {
  return (
    <article className="panel plan-panel">
      <header className="plan-header">
        <div>
          <p className="eyebrow">已选方案</p>
          <h2>{plan.title || "未命名方案"}</h2>
          <p>{plan.summary || "暂无摘要"}</p>
        </div>
        <StatusBadge status={plan.status} />
      </header>

      <div className="plan-grid">
        <CandidateSection title="活动" icon={<Activity size={18} />} candidate={plan.activity} />
        <CandidateSection title="用餐" icon={<Utensils size={18} />} candidate={plan.dining} />
      </div>

      <section className="detail-section" aria-labelledby="timeline-title">
        <div className="section-heading">
          <Clock3 size={18} aria-hidden="true" />
          <h3 id="timeline-title">时间安排</h3>
        </div>
        {plan.timeline?.length ? (
          <ol className="timeline-list">
            {plan.timeline.map((item, index) => (
              <li key={`${item.sequence ?? index}-${item.title ?? index}`}>
                <span className="time-range">
                  {item.start_label || "开始时间暂无"} - {item.end_label || "结束时间暂无"}
                </span>
                <span className="timeline-title">{item.title || "未命名站点"}</span>
                <span className="muted">{minutes(item.duration_minutes)}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">暂无</p>
        )}
      </section>

      <section className="detail-section" aria-labelledby="route-title">
        <div className="section-heading">
          <Route size={18} aria-hidden="true" />
          <h3 id="route-title">路线</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="方式" value={routeMode(plan.route?.mode)} />
          <MetaItem label="距离" value={distance(plan.route?.distance_meters)} />
          <MetaItem label="耗时" value={minutes(plan.route?.duration_minutes)} />
          <MetaItem label="说明" value={plan.route?.summary} />
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="feasibility-title">
        <div className="section-heading">
          <CheckCircle2 size={18} aria-hidden="true" />
          <h3 id="feasibility-title">可行性</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="结果" value={feasibilityLabel(plan.feasibility?.is_feasible)} />
          <MetaItem label="总时长" value={minutes(plan.feasibility?.total_duration_minutes)} />
          <MetaItem label="路程耗时" value={minutes(plan.feasibility?.route_duration_minutes)} />
          <MetaItem label="排队等待" value={minutes(plan.feasibility?.queue_wait_minutes)} />
        </dl>
        <TextList title="理由" items={plan.feasibility?.reasons} />
        <TextList title="提醒" items={plan.feasibility?.warnings} />
      </section>

      <section className="detail-section" aria-labelledby="actions-title">
        <div className="section-heading">
          <MapPinned size={18} aria-hidden="true" />
          <h3 id="actions-title">待确认操作</h3>
        </div>
        {plan.proposed_actions?.length ? (
          <ul className="action-list">
            {plan.proposed_actions.map((action, index) => (
              <li key={`${action.action_ref ?? action.action_type ?? index}`}>
                <span className="action-type">{actionLabel(action.action_type) || "操作"}</span>
                <span>{action.target_id || "目标暂无"}</span>
                <span className="muted">{action.reason || "理由暂无"}</span>
                <span className="requirement">
                  {action.requires_confirmation ? "需要确认" : "未标记确认"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">暂无</p>
        )}
      </section>
    </article>
  );
}

function CandidateSection({
  title,
  icon,
  candidate,
}: {
  title: string;
  icon: ReactNode;
  candidate?: DemoCandidateSummary | null;
}) {
  return (
    <section className="candidate-section" aria-label={title}>
      <div className="section-heading">
        {icon}
        <h3>{title}</h3>
      </div>
      <dl className="compact-list">
        <MetaItem label="名称" value={candidate?.name} />
        <MetaItem label="类型" value={categoryLabel(candidate?.category)} />
        <MetaItem label="地址" value={candidate?.address} />
        <MetaItem label="标签" value={candidate?.tags?.length ? candidate.tags.map(tagLabel).join(", ") : undefined} />
      </dl>
    </section>
  );
}

function ConfirmationControls({
  run,
  plan,
  requestState,
  canConfirm,
  canDecline,
  onConfirm,
  onDecline,
}: {
  run: DemoRunSummary;
  plan: DemoPlanPreview;
  requestState: RequestState;
  canConfirm: boolean;
  canDecline: boolean;
  onConfirm: () => void;
  onDecline: () => void;
}) {
  return (
    <section className="panel action-panel" aria-labelledby="confirm-title">
      <div>
        <p className="eyebrow">确认</p>
        <h2 id="confirm-title">{plan.confirmation?.status || confirmationStatus(run.status)}</h2>
        <p>
          {run.status === "awaiting_confirmation"
            ? "确认前不会执行订座、取号、购票或消息发送。"
            : "当前运行已不再等待确认。"}
        </p>
      </div>
      {run.status === "awaiting_confirmation" ? (
        <div className="button-row align-end">
          <button
            className="primary-button"
            type="button"
            onClick={onConfirm}
            disabled={!canConfirm}
            data-testid="confirm-button"
          >
            {requestState === "confirming" ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
            <span>{requestState === "confirming" ? "确认中" : "确认所选方案"}</span>
          </button>
          <button
            className="danger-button"
            type="button"
            onClick={onDecline}
            disabled={!canDecline}
            data-testid="decline-button"
          >
            {requestState === "declining" ? <Loader2 className="spin" size={17} /> : <XCircle size={17} />}
            <span>{requestState === "declining" ? "取消中" : "暂不继续"}</span>
          </button>
        </div>
      ) : null}
    </section>
  );
}

function ExecutionResult({ run, plan }: { run: DemoRunSummary; plan: DemoPlanPreview }) {
  if (run.status === "declined" || plan.confirmation?.status === "declined") {
    return (
      <section className="panel result-panel" aria-labelledby="declined-title">
        <p className="eyebrow">结果</p>
        <h2 id="declined-title">已取消</h2>
        <p>{userFacingText(plan.confirmation?.reason) || "所选方案已取消，没有执行结果。"}</p>
      </section>
    );
  }

  if (!plan.execution && !plan.feedback) {
    return null;
  }

  const feedback = plan.feedback;

  return (
    <section className="panel result-panel" aria-labelledby="result-title">
      <p className="eyebrow">执行与反馈</p>
      <h2 id="result-title">{feedback?.headline || plan.execution?.status || "执行结果"}</h2>
      <dl className="compact-list">
        <MetaItem label="执行状态" value={plan.execution?.status || run.execution_status} />
        <MetaItem label="成功数" value={numberValue(plan.execution?.succeeded_count)} />
        <MetaItem label="失败数" value={numberValue(plan.execution?.failed_count)} />
        <MetaItem label="反馈状态" value={feedback?.status || run.feedback_status} />
      </dl>
      {feedback?.message ? <p>{feedback.message}</p> : null}
      <FeedbackActions title="已完成操作" items={feedback?.completed_actions} />
      <FeedbackActions title="未完成操作" items={feedback?.failed_actions} />
      <TextList title="下一步" items={feedback?.next_steps} />
    </section>
  );
}

function FeedbackActions({ title, items }: { title: string; items?: Record<string, unknown>[] }) {
  if (!items?.length) {
    return (
      <div className="feedback-block">
        <h3>{title}</h3>
        <p className="muted">暂无</p>
      </div>
    );
  }

  return (
    <div className="feedback-block">
      <h3>{title}</h3>
      <ul className="feedback-list">
        {items.map((item, index) => (
          <li key={`${safeText(item.tool_name) || safeText(item.action_type) || title}-${index}`}>
            <span>{actionLabel(safeText(item.tool_name) || safeText(item.action_type)) || "操作"}</span>
            <span>{feedbackStatusLabel(safeText(item.status)) || "状态暂无"}</span>
            <span className="muted">{userFacingText(safeText(item.message)) || safeText(item.target_label) || "详情暂无"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TextList({ title, items }: { title: string; items?: string[] }) {
  return (
    <div className="text-list-block">
      <h4>{title}</h4>
      {items?.length ? (
        <ul>
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">暂无</p>
      )}
    </div>
  );
}

function MetaItem({
  label,
  value,
  mono = false,
  testId,
}: {
  label: string;
  value?: string | number | null;
  mono?: boolean;
  testId?: string;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined} data-testid={testId}>
        {display(value)}
      </dd>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-${status.replace(/[^a-z0-9_-]/gi, "-")}`}>{status}</span>;
}

function choosePlan(run: DemoRunSummary | null, selectedPlanId: string | null): DemoPlanPreview | null {
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

function stateFromRun(run: DemoRunSummary): RequestState {
  if (run.status === "awaiting_confirmation") {
    return "awaiting_confirmation";
  }
  if (run.status === "declined") {
    return "declined";
  }
  if (TERMINAL_SUCCESS_STATUSES.has(run.status)) {
    return "completed";
  }
  return "idle";
}

function confirmationStatus(status: string) {
  if (status === "awaiting_confirmation") {
    return "pending";
  }
  return status;
}

function display(value?: string | number | null) {
  if (value === null || value === undefined || value === "") {
    return "暂无";
  }
  return String(value);
}

function numberValue(value?: number | null) {
  return typeof value === "number" ? String(value) : undefined;
}

function minutes(value?: number | null) {
  return typeof value === "number" ? `${value} 分钟` : "暂无";
}

function distance(value?: number | null) {
  if (typeof value !== "number") {
    return "暂无";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} km`;
  }
  return `${value} m`;
}

function routeMode(value?: string | null) {
  if (value === "walking") {
    return "步行";
  }
  if (value === "driving") {
    return "驾车";
  }
  return value;
}

function categoryLabel(value?: string | null) {
  const labels: Record<string, string> = {
    activity: "活动",
    dining: "用餐",
    addon: "加购",
  };
  return value ? labels[value] ?? value : null;
}

function tagLabel(value: string) {
  const labels: Record<string, string> = {
    child_friendly: "亲子友好",
    indoor: "室内",
    museum: "博物馆",
    educational: "科普",
    outdoor: "户外",
    playground: "游乐场",
    citywalk: "城市漫步",
    light_activity: "轻活动",
    lighter_options: "清淡选项",
    quiet: "安静",
    vegetable_forward: "蔬菜为主",
    family_tables: "家庭桌位",
    balanced_menu: "均衡菜单",
    quick_meal: "快餐",
    simple: "简单",
    drinks: "饮品",
    snacks: "小食",
    family: "家庭",
  };
  return labels[value] ?? value;
}

function feasibilityLabel(value?: boolean | null) {
  if (value === true) {
    return "可行";
  }
  if (value === false) {
    return "不可行";
  }
  return "暂无";
}

function safeText(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function actionLabel(value?: string | null) {
  const labels: Record<string, string> = {
    book_ticket: "订票",
    reserve_restaurant: "订座",
    join_queue: "排队取号",
    order_addon: "加购点单",
    send_message: "发送消息",
  };
  return value ? labels[value] ?? value : null;
}

function feedbackStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    completed: "已完成",
    already_completed: "已完成",
    failed: "失败",
    blocked: "已阻止",
    rate_limited: "限流",
  };
  return value ? labels[value] ?? value : null;
}

function userFacingText(value?: string | null) {
  if (!value) {
    return null;
  }
  const mapped: Record<string, string> = {
    "User chose not to continue.": "用户选择暂不继续。",
  };
  return mapped[value] ?? value;
}

function errorMessageForDisplay(error: unknown) {
  if (error instanceof Error && error.name === "DemoApiError" && error.message.trim()) {
    return error.message;
  }
  return GENERIC_ERROR_MESSAGE;
}
