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
import { clarifyRun, confirmRun, declineRun, getRun, replanRun, startRun } from "./api/demo";
import type {
  DemoActionManifestSummary,
  DemoCandidateSummary,
  DemoClarificationSummary,
  DemoPlanPreview,
  DemoReadProfile,
  DemoReplanRunRequest,
  DemoRunSummary,
} from "./types/demo";

const DEFAULT_PROMPT =
  "\u4eca\u5929\u4e0b\u5348\u60f3\u548c\u7231\u4eba\u30015\u5c81\u7684\u5b69\u5b50\u51fa\u95e8\u73a9\u51e0\u4e2a\u5c0f\u65f6\uff0c\u522b\u79bb\u5bb6\u592a\u8fdc\u3002\u5b69\u5b50\u8981\u9002\u5408\u4eb2\u5b50\u6d3b\u52a8\uff0c\u7231\u4eba\u6700\u8fd1\u60f3\u5403\u6e05\u6de1\u4e00\u70b9\uff0c\u5e2e\u6211\u5b89\u6392\u4e00\u4e0b\u3002";
const GENERIC_ERROR_MESSAGE =
  "\u6f14\u793a\u8bf7\u6c42\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002";
const AMAP_READ_ONLY_NOTE =
  "AMap \u53ea\u8bfb\u9884\u89c8\u8def\u5f84\u53ea\u7528\u4e8e\u89c4\u5212\u67e5\u8be2\u4e0e\u7ed3\u679c\u9884\u89c8\uff0c\u4f1a\u5728\u786e\u8ba4\u524d\u505c\u6b62\uff0c\u4e0d\u4f1a\u6267\u884c\u4efb\u4f55\u5199\u64cd\u4f5c\u3002";

type RequestState =
  | "idle"
  | "starting"
  | "awaiting_clarification"
  | "clarifying"
  | "awaiting_confirmation"
  | "replanning"
  | "refreshing"
  | "confirming"
  | "declining"
  | "completed"
  | "declined"
  | "error";

const TERMINAL_SUCCESS_STATUSES = new Set(["completed", "partially_completed", "failed", "skipped"]);

export default function App() {
  const [userInput, setUserInput] = useState(DEFAULT_PROMPT);
  const [selectedReadProfile, setSelectedReadProfile] = useState<DemoReadProfile>("mock_world");
  const [run, setRun] = useState<DemoRunSummary | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [clarificationReply, setClarificationReply] = useState("");
  const [replanReply, setReplanReply] = useState("");
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedPlan = useMemo(() => choosePlan(run, selectedPlanId), [run, selectedPlanId]);
  const trimmedInput = userInput.trim();
  const inputIsEmpty = trimmedInput.length === 0;
  const clarificationPayload = isClarificationSummary(run?.clarification) ? run.clarification : null;
  const clarificationPayloadIsInvalid =
    run?.status === "awaiting_clarification" && !isClarificationSummary(run.clarification);
  const visibleErrorMessage = errorMessage ?? (clarificationPayloadIsInvalid ? GENERIC_ERROR_MESSAGE : null);
  const isInFlight = ["starting", "clarifying", "replanning", "refreshing", "confirming", "declining"].includes(
    requestState,
  );
  const canRefresh = Boolean(run?.run_id) && !isInFlight;
  const isAwaitingClarification = run?.status === "awaiting_clarification";
  const isAwaitingConfirmation = run?.status === "awaiting_confirmation";
  const isAmapPreview = run?.read_profile === "amap";
  const clarificationReplyIsEmpty = clarificationReply.trim().length === 0;
  const showClarificationPanel = Boolean(isAwaitingClarification && clarificationPayload);
  const replanReplyIsEmpty = replanReply.trim().length === 0;
  const canClarify = Boolean(showClarificationPanel && run?.run_id && !clarificationReplyIsEmpty && !isInFlight);
  const canConfirm = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight && !isAmapPreview);
  const canDecline = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight);
  const showReplanPanel = Boolean(run?.status === "awaiting_confirmation" && selectedPlan);
  const canReplan = Boolean(showReplanPanel && run?.run_id && !replanReplyIsEmpty && !isInFlight);

  async function handleStart() {
    if (inputIsEmpty || isInFlight) {
      return;
    }

    setClarificationReply("");
    setReplanReply("");
    await runAction("starting", () =>
      startRun({
        user_input: trimmedInput,
        external_user_id: buildDemoExternalUserId(),
        display_name: "Web Demo User",
        case_id: "web-demo",
        selected_plan_index: 0,
        read_profile: selectedReadProfile,
      }),
    );
  }

  async function handleReplan() {
    if (!run?.run_id || !canReplan) {
      return;
    }

    await runAction(
      "replanning",
      () => replanRun(run.run_id, buildReplanRequest(replanReply)),
      () => {
        setReplanReply("");
      },
    );
  }

  async function handleRefresh() {
    if (!run?.run_id || isInFlight) {
      return;
    }
    await runAction("refreshing", () => getRun(run.run_id));
  }

  async function handleClarify() {
    if (!run?.run_id || !canClarify) {
      return;
    }

    await runAction(
      "clarifying",
      () =>
        clarifyRun(run.run_id, {
          user_input: clarificationReply.trim(),
          selected_plan_index: 0,
        }),
      () => {
        setClarificationReply("");
      },
    );
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

  async function runAction(
    nextState: RequestState,
    action: () => Promise<DemoRunSummary>,
    onSuccess?: (nextRun: DemoRunSummary) => void,
  ) {
    setRequestState(nextState);
    setErrorMessage(null);

    try {
      const nextRun = await action();
      onSuccess?.(nextRun);
      setRun(nextRun);
      setSelectedReadProfile(nextRun.read_profile);
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
          <p className="eyebrow">WeekendPilot 演示版</p>
          <h1 id="app-title">周末出行规划预览</h1>
        </div>
        <StatusBadge status={requestState} />
      </section>

      <div className="app-grid">
        <aside className="side-rail" aria-label="需求输入与运行摘要">
          <section className="panel composer-panel" aria-labelledby="request-title">
            <div className="section-heading">
              <Send size={18} aria-hidden="true" />
              <h2 id="request-title">需求</h2>
            </div>

            <label className="field-label" htmlFor="request-input">
              规划需求
            </label>
            <textarea
              id="request-input"
              value={userInput}
              onChange={(event) => setUserInput(event.target.value)}
              rows={8}
              disabled={isInFlight}
            />

            {inputIsEmpty ? (
              <p className="validation-text">
                \u8bf7\u5148\u8f93\u5165\u8981\u89c4\u5212\u7684\u9700\u6c42\uff0c\u518d\u542f\u52a8 demo\u3002
              </p>
            ) : null}

            <div className="field-stack">
              <label className="field-label" htmlFor="read-profile-select">
                规划路径
              </label>
              <select
                id="read-profile-select"
                className="select-input"
                value={selectedReadProfile}
                disabled={isInFlight}
                onChange={(event) => setSelectedReadProfile(event.target.value as DemoReadProfile)}
                data-testid="read-profile-select"
              >
                <option value="mock_world">Mock World</option>
                <option value="amap">AMap \u53ea\u8bfb\u9884\u89c8</option>
              </select>
              <p className="helper-text">{readProfileHelper(selectedReadProfile)}</p>
            </div>

            <div className="button-row">
              <button
                className="primary-button"
                type="button"
                onClick={handleStart}
                disabled={inputIsEmpty || isInFlight}
                data-testid="start-button"
              >
                {requestState === "starting" ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
                <span>{requestState === "starting" ? "规划中..." : "开始规划"}</span>
              </button>

              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setUserInput(DEFAULT_PROMPT);
                  setSelectedReadProfile("mock_world");
                  setClarificationReply("");
                  setReplanReply("");
                  setErrorMessage(null);
                }}
                disabled={isInFlight}
              >
                <RotateCcw size={17} />
                <span>恢复示例</span>
              </button>
            </div>

            {visibleErrorMessage ? (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} aria-hidden="true" />
                <span>{visibleErrorMessage}</span>
              </div>
            ) : null}
          </section>

          <RunInspector
            run={run}
            onRefresh={handleRefresh}
            canRefresh={canRefresh}
            requestState={requestState}
          />
        </aside>

        <section className="workspace" aria-label="方案预览与确认边界">
          {showClarificationPanel && clarificationPayload ? (
            <ClarificationPanel
              clarification={clarificationPayload}
              reply={clarificationReply}
              requestState={requestState}
              canClarify={canClarify}
              onReplyChange={setClarificationReply}
              onSubmit={handleClarify}
            />
          ) : run && selectedPlan ? (
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
              {showReplanPanel ? (
                <ReplanPanel
                  reply={replanReply}
                  requestState={requestState}
                  canReplan={canReplan}
                  onReplyChange={setReplanReply}
                  onSubmit={handleReplan}
                />
              ) : null}
              <ExecutionResult run={run} plan={selectedPlan} />
            </>
          ) : (
            <section className="empty-workspace">
              <Clock3 size={28} aria-hidden="true" />
              <h2>准备预览</h2>
              <p>默认使用 Mock World，也可以切换到 AMap 只读预览查看只读规划结果。</p>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

function ReplanPanel({
  reply,
  requestState,
  canReplan,
  onReplyChange,
  onSubmit,
}: {
  reply: string;
  requestState: RequestState;
  canReplan: boolean;
  onReplyChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="panel replan-panel" aria-labelledby="replan-title" data-testid="replan-panel">
      <div>
        <p className="eyebrow">继续规划</p>
        <h2 id="replan-title">继续调整方案</h2>
        <p>补充新的限制或偏好后，会基于当前运行创建新的方案版本，并切换到新的 run。</p>
      </div>

      <label className="field-label" htmlFor="replan-reply-input">
        新的需求或限制
      </label>
      <textarea
        id="replan-reply-input"
        className="replan-textarea"
        value={reply}
        onChange={(event) => onReplyChange(event.target.value)}
        rows={4}
        disabled={requestState === "replanning"}
        data-testid="replan-reply-input"
      />

      <div className="button-row align-end">
        <button
          className="primary-button"
          type="button"
          onClick={onSubmit}
          disabled={!canReplan}
          data-testid="replan-submit-button"
        >
          {requestState === "replanning" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
          <span>{requestState === "replanning" ? "重新规划中..." : "重新规划当前方案"}</span>
        </button>
      </div>
    </section>
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
        <h2 id="run-title">运行摘要</h2>
      </div>

      <dl className="metadata-list">
        <MetaItem label="运行状态" value={statusLabel(run?.status)} testId="run-status" />
        <MetaItem label="运行 ID" value={run?.run_id} mono testId="run-id" />
        <MetaItem label="规划路径" value={readProfileLabel(run?.read_profile)} testId="active-read-profile" />
        <MetaItem label="动作数" value={numberValue(run?.action_count)} testId="action-count" />
        <MetaItem label="执行状态" value={statusLabel(run?.execution_status)} />
        <MetaItem label="反馈状态" value={statusLabel(run?.feedback_status)} />
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
        <span>{requestState === "refreshing" ? "刷新中..." : "刷新状态"}</span>
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

function ClarificationPanel({
  clarification,
  reply,
  requestState,
  canClarify,
  onReplyChange,
  onSubmit,
}: {
  clarification: DemoClarificationSummary;
  reply: string;
  requestState: RequestState;
  canClarify: boolean;
  onReplyChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="panel clarification-panel" aria-labelledby="clarification-title" data-testid="clarification-panel">
      <div>
        <p className="eyebrow">继续规划</p>
        <h2 id="clarification-title">需要补充信息</h2>
        <p>{clarification.prompt}</p>
      </div>

      <div className="field-stack">
        <p className="field-label">待补充项</p>
        <ul className="clarification-chip-list" data-testid="clarification-fields">
          {clarification.missing_fields.map((field) => (
            <li key={field} className="clarification-chip">
              {clarificationFieldLabel(field)}
            </li>
          ))}
        </ul>
      </div>

      <label className="field-label" htmlFor="clarification-reply-input">
        补充说明
      </label>
      <textarea
        id="clarification-reply-input"
        className="clarification-textarea"
        value={reply}
        onChange={(event) => onReplyChange(event.target.value)}
        rows={4}
        disabled={requestState === "clarifying"}
        data-testid="clarification-reply-input"
      />
      <p className="helper-text">补充后会继续当前规划流程，仍会在确认前停下。</p>

      <div className="button-row align-end">
        <button
          className="primary-button"
          type="button"
          onClick={onSubmit}
          disabled={!canClarify}
          data-testid="clarification-submit-button"
        >
          {requestState === "clarifying" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
          <span>{requestState === "clarifying" ? "提交中..." : "提交补充信息"}</span>
        </button>
      </div>
    </section>
  );
}

function PlanDetail({ plan }: { plan: DemoPlanPreview }) {
  return (
    <article className="panel plan-panel">
      <header className="plan-header">
        <div>
          <p className="eyebrow">已选方案</p>
          <h2>{plan.title || "未命名方案"}</h2>
          <p>{plan.summary || "暂无摘要。"}</p>
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
          <h3 id="timeline-title">行程时间线</h3>
        </div>
        {plan.timeline?.length ? (
          <ol className="timeline-list">
            {plan.timeline.map((item, index) => (
              <li key={`${item.sequence ?? index}-${item.title ?? index}`}>
                <span className="time-range">
                  {item.start_label || "待定"} - {item.end_label || "待定"}
                </span>
                <span className="timeline-title">{item.title || "未命名站点"}</span>
                <span className="muted">{minutes(item.duration_minutes)}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">暂无时间线。</p>
        )}
      </section>

      <section className="detail-section" aria-labelledby="route-title">
        <div className="section-heading">
          <Route size={18} aria-hidden="true" />
          <h3 id="route-title">路线</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="出行方式" value={routeMode(plan.route?.mode)} />
          <MetaItem label="距离" value={distance(plan.route?.distance_meters)} />
          <MetaItem label="时长" value={minutes(plan.route?.duration_minutes)} />
          <MetaItem label="摘要" value={plan.route?.summary} />
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="feasibility-title">
        <div className="section-heading">
          <CheckCircle2 size={18} aria-hidden="true" />
          <h3 id="feasibility-title">可执行性</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="结果" value={feasibilityLabel(plan.feasibility?.is_feasible)} />
          <MetaItem label="总时长" value={minutes(plan.feasibility?.total_duration_minutes)} />
          <MetaItem label="路线耗时" value={minutes(plan.feasibility?.route_duration_minutes)} />
          <MetaItem label="排队等待" value={minutes(plan.feasibility?.queue_wait_minutes)} />
        </dl>
        <TextList title="依据" items={plan.feasibility?.reasons} />
        <TextList title="提醒" items={plan.feasibility?.warnings} />
      </section>

      <section className="detail-section" aria-labelledby="actions-title">
        <div className="section-heading">
          <MapPinned size={18} aria-hidden="true" />
          <h3 id="actions-title">执行动作预览</h3>
        </div>
        <p className="muted">{actionManifestSourceLabel(plan.action_manifest)}</p>
        {plan.action_manifest.actions.length ? (
          <ul className="action-list">
            {plan.action_manifest.actions.map((action, index) => (
              <li key={`${action.action_ref ?? action.action_type ?? index}`}>
                <span className="action-type">{actionLabel(action.action_type) || "动作"}</span>
                <span>{action.target_id || "暂无目标"}</span>
                <span className="muted">{action.reason || "暂无说明。"}</span>
                <span className="requirement">{actionExecutionLabel(action.execution_order)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">暂无待执行动作。</p>
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
        <MetaItem label="类别" value={categoryLabel(candidate?.category)} />
        <MetaItem label="地址" value={candidate?.address} />
        <MetaItem label="标签" value={candidate?.tags?.length ? candidate.tags.map(tagLabel).join("、") : undefined} />
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
  const showPendingButtons = run.status === "awaiting_confirmation";
  const showReadOnlyNotice = showPendingButtons && run.read_profile === "amap";

  return (
    <section className="panel action-panel" aria-labelledby="confirm-title">
      <div>
        <p className="eyebrow">确认边界</p>
        <h2 id="confirm-title">{statusLabel(plan.confirmation?.status || confirmationStatus(run.status))}</h2>
        <p>
          {showReadOnlyNotice
            ? AMAP_READ_ONLY_NOTE
            : "工作流会在这里暂停，等待确认或放弃当前方案。"}
        </p>
      </div>

      {showPendingButtons ? (
        <div className="button-row align-end">
          {showReadOnlyNotice ? (
            <div className="notice-banner" data-testid="amap-read-only-notice">
              <AlertCircle size={18} aria-hidden="true" />
              <span>{AMAP_READ_ONLY_NOTE}</span>
            </div>
          ) : (
            <button
              className="primary-button"
              type="button"
              onClick={onConfirm}
              disabled={!canConfirm}
              data-testid="confirm-button"
            >
              {requestState === "confirming" ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
              <span>{requestState === "confirming" ? "确认中..." : "确认当前方案"}</span>
            </button>
          )}

          <button
            className="danger-button"
            type="button"
            onClick={onDecline}
            disabled={!canDecline}
            data-testid="decline-button"
          >
            {requestState === "declining" ? <Loader2 className="spin" size={17} /> : <XCircle size={17} />}
            <span>{requestState === "declining" ? "处理中..." : "暂不继续"}</span>
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
        <h2 id="declined-title">已放弃</h2>
        <p>{userFacingText(plan.confirmation?.reason) || "已在执行前放弃当前方案。"}</p>
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
      <h2 id="result-title">{feedback?.headline || statusLabel(plan.execution?.status) || "执行结果"}</h2>
      <dl className="compact-list">
        <MetaItem label="执行状态" value={statusLabel(plan.execution?.status || run.execution_status)} />
        <MetaItem label="成功数" value={numberValue(plan.execution?.succeeded_count)} />
        <MetaItem label="失败数" value={numberValue(plan.execution?.failed_count)} />
        <MetaItem label="反馈状态" value={statusLabel(feedback?.status || run.feedback_status)} />
      </dl>
      {feedback?.message ? <p>{feedback.message}</p> : null}
      <FeedbackActions title="已完成动作" items={feedback?.completed_actions} />
      <FeedbackActions title="失败动作" items={feedback?.failed_actions} />
      <TextList title="后续建议" items={feedback?.next_steps} />
    </section>
  );
}

function FeedbackActions({ title, items }: { title: string; items?: Record<string, unknown>[] }) {
  if (!items?.length) {
    return (
      <div className="feedback-block">
        <h3>{title}</h3>
        <p className="muted">暂无。</p>
      </div>
    );
  }

  return (
    <div className="feedback-block">
      <h3>{title}</h3>
      <ul className="feedback-list">
        {items.map((item, index) => (
          <li key={`${safeText(item.tool_name) || safeText(item.action_type) || title}-${index}`}>
            <span>{actionLabel(safeText(item.tool_name) || safeText(item.action_type)) || "动作"}</span>
            <span>{feedbackStatusLabel(safeText(item.status)) || "未知"}</span>
            <span className="muted">
              {userFacingText(safeText(item.message)) || safeText(item.target_label) || "暂无详情。"}
            </span>
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
        <p className="muted">暂无。</p>
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
  return <span className={`status-badge status-${status.replace(/[^a-z0-9_-]/gi, "-")}`}>{statusLabel(status) ?? status}</span>;
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
  if (run.status === "awaiting_clarification") {
    return "awaiting_clarification";
  }
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
    return `${(value / 1000).toFixed(1)} 公里`;
  }
  return `${value} 米`;
}

function routeMode(value?: string | null) {
  const labels: Record<string, string> = {
    walking: "步行",
    driving: "驾车",
  };
  return value ? labels[value] ?? value : null;
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
  };
  return labels[value] ?? value;
}

function feasibilityLabel(value?: boolean | null) {
  if (value === true) {
    return "可执行";
  }
  if (value === false) {
    return "不可执行";
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
    order_addon: "加购",
    send_message: "发送消息",
  };
  return value ? labels[value] ?? value : null;
}

function actionExecutionLabel(value?: number | null) {
  return typeof value === "number" ? `第 ${value} 步` : "待确定执行顺序";
}

function actionManifestSourceLabel(manifest: DemoActionManifestSummary) {
  if (manifest.source === "confirmed_actions") {
    return "以下为确认后将执行的动作清单。";
  }
  if (manifest.source === "proposed_actions") {
    return "以下为确认前的动作预览，尚未执行任何写操作。";
  }
  return "当前方案没有可公开展示的动作预览。";
}

function feedbackStatusLabel(value?: string | null) {
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

function clarificationFieldLabel(value: string) {
  const labels: Record<string, string> = {
    scenario_or_participants: "出行人/场景",
    time_window: "时间安排",
    distance_flexibility: "距离取舍",
    preference_tradeoff: "偏好取舍",
  };
  return labels[value] ?? value;
}

function userFacingText(value?: string | null) {
  if (!value) {
    return null;
  }

  const mapped: Record<string, string> = {
    "User chose not to continue.": "\u7528\u6237\u9009\u62e9\u6682\u4e0d\u7ee7\u7eed\u3002",
  };
  return mapped[value] ?? value;
}

function statusLabel(value?: string | null) {
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

function errorMessageForDisplay(error: unknown) {
  if (error instanceof Error && error.name === "DemoApiError" && error.message.trim()) {
    return error.message;
  }
  return GENERIC_ERROR_MESSAGE;
}

function readProfileLabel(profile?: DemoReadProfile | null) {
  if (profile === "amap") {
    return "AMap \u53ea\u8bfb\u9884\u89c8";
  }
  if (profile === "mock_world") {
    return "Mock World";
  }
  return null;
}

function readProfileHelper(profile: DemoReadProfile) {
  if (profile === "amap") {
    return "AMap \u8def\u5f84\u4ec5\u7528\u4e8e\u672c\u5730\u53ea\u8bfb\u9884\u89c8\uff0c\u5728\u786e\u8ba4\u524d\u505c\u6b62\uff0c\u4e0d\u4f1a\u6267\u884c\u5199\u64cd\u4f5c\u3002";
  }
  return "Mock World \u662f\u9ed8\u8ba4\u8def\u5f84\uff0c\u4e5f\u662f benchmark \u7684\u7a33\u5b9a\u9ed8\u8ba4\u503c\u3002";
}

function isClarificationSummary(value: DemoRunSummary["clarification"] | undefined): value is DemoClarificationSummary {
  return Boolean(
    value &&
      typeof value.prompt === "string" &&
      Array.isArray(value.missing_fields) &&
      value.missing_fields.every((field) => typeof field === "string"),
  );
}

function buildDemoExternalUserId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `web-demo-user-${crypto.randomUUID()}`;
  }
  return `web-demo-user-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildReplanRequest(reply: string): DemoReplanRunRequest {
  return {
    user_input: reply.trim(),
    selected_plan_index: 0,
  };
}
