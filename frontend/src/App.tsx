import { AlertCircle, Compass, Loader2, RotateCcw, Send, SlidersHorizontal, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { clarifyRun, confirmRun, declineRun, getRun, replanRun, startRun } from "./api/demo";
import { ConversationThread } from "./chat/ConversationThread";
import {
  choosePlan,
  isClarificationSummary,
  progressLabelForState,
  projectConversationThread,
  readProfileHelper,
  resolveSelectedPlanIndex,
  statusLabel,
  type ConversationHistoryEntry,
  type PendingConversationAction,
} from "./chat/thread";
import type { DemoReadProfile, DemoReplanRunRequest, DemoRunSummary } from "./types/demo";

const EXAMPLE_PROMPTS = [
  {
    label: "亲子半天",
    prompt:
      "今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。孩子要适合亲子活动，爱人最近想吃清淡一点，帮我安排一下。",
  },
  {
    label: "朋友轻社交",
    prompt:
      "This afternoon I want to hang out with friends nearby for a few hours. Start with an outdoor walk and chatting, then find a casual dinner place that's good for sharing. Not too far.",
  },
  {
    label: "只读预览",
    prompt: "帮我先预览一个适合周末下午的附近轻松行程，不要直接执行任何动作。",
  },
];

const GENERIC_ERROR_MESSAGE = "演示请求失败，请稍后重试。";

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
  const [userInput, setUserInput] = useState("");
  const [selectedReadProfile, setSelectedReadProfile] = useState<DemoReadProfile>("mock_world");
  const [run, setRun] = useState<DemoRunSummary | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [clarificationReply, setClarificationReply] = useState("");
  const [replanReply, setReplanReply] = useState("");
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [advancedOptionsOpen, setAdvancedOptionsOpen] = useState(false);
  const [conversationEntries, setConversationEntries] = useState<ConversationHistoryEntry[]>([]);

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
  const replanReplyIsEmpty = replanReply.trim().length === 0;
  const showClarificationComposer = Boolean(isAwaitingClarification && clarificationPayload);
  const canClarify = Boolean(showClarificationComposer && run?.run_id && !clarificationReplyIsEmpty && !isInFlight);
  const canConfirm = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight && !isAmapPreview);
  const canDecline = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight);
  const canReplan = Boolean(isAwaitingConfirmation && selectedPlan && run?.run_id && !replanReplyIsEmpty && !isInFlight);

  const pendingAction: PendingConversationAction | null = isInFlight
    ? {
        id: `pending-${requestState}`,
        kind: "system_progress",
        label: progressLabelForState(requestState),
        status: requestState,
      }
    : null;

  const threadItems = useMemo(
    () =>
      projectConversationThread({
        entries: conversationEntries,
        activeRunId: run?.run_id ?? null,
        selectedPlanId,
        pendingAction,
      }),
    [conversationEntries, pendingAction, run?.run_id, selectedPlanId],
  );

  async function handleStart() {
    if (inputIsEmpty || isInFlight) {
      return;
    }

    appendUserEntry("start", trimmedInput);
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

    appendUserEntry("replan", replanReply.trim());
    const selectedPlanIndex = resolveSelectedPlanIndex(run, selectedPlanId);

    await runAction(
      "replanning",
      () => replanRun(run.run_id, buildReplanRequest(replanReply, selectedPlanIndex)),
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

    appendUserEntry("clarify", clarificationReply.trim());
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
      upsertRunEntry(nextRun);
      setRun(nextRun);
      setSelectedReadProfile(nextRun.read_profile);
      setSelectedPlanId(nextRun.selected_plan_id ?? nextRun.plans[0]?.plan_id ?? null);
      setRequestState(stateFromRun(nextRun));

      if (nextState === "starting") {
        setUserInput("");
      }
    } catch (error) {
      setRequestState("error");
      setErrorMessage(errorMessageForDisplay(error));
    }
  }

  function appendUserEntry(event: Extract<ConversationHistoryEntry, { kind: "user" }>["event"], text: string) {
    setConversationEntries((current) => [
      ...current,
      {
        id: `${event}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        kind: "user",
        event,
        text,
      },
    ]);
  }

  function upsertRunEntry(nextRun: DemoRunSummary) {
    setConversationEntries((current) => {
      const nextEntry: ConversationHistoryEntry = {
        id: `run-${nextRun.run_id}`,
        kind: "run",
        run: nextRun,
      };
      const existingIndex = current.findIndex(
        (entry) => entry.kind === "run" && entry.run.run_id === nextRun.run_id,
      );

      if (existingIndex >= 0) {
        const nextEntries = [...current];
        nextEntries[existingIndex] = nextEntry;
        return nextEntries;
      }

      return [...current, nextEntry];
    });
  }

  function resetComposer() {
    setUserInput("");
    setSelectedReadProfile("mock_world");
    setAdvancedOptionsOpen(false);
    setErrorMessage(null);
  }

  return (
    <main className="app-shell customer-chat-shell">
      <section className="app-header customer-chat-header" aria-labelledby="app-title">
        <div>
          <p className="eyebrow">WeekendPilot Web Demo</p>
          <h1 id="app-title">企业级对话式周末规划</h1>
          <p className="hero-supporting-copy">先给你推荐方案摘要，再按需展开时间线、餐厅、路线和确认动作。</p>
        </div>
        <StatusBadge status={requestState === "idle" ? "ready" : requestState} />
      </section>

      <section className="chat-hero">
        <div className="chat-hero-copy">
          <div className="hero-kicker">
            <Sparkles size={16} aria-hidden="true" />
            <span>Chat-First Customer Surface</span>
          </div>
          <h2>只保留一个主输入框，剩下的进度和方案都在聊天流里完成。</h2>
          <p>
            默认走 Mock World。需要只读实时预览时，再从高级选项切到 AMap。内部运行 ID、动作计数和原始状态字段不会默认铺开。
          </p>
        </div>

        <section className="panel chat-composer-card" aria-labelledby="request-title">
          <div className="section-heading">
            <Compass size={18} aria-hidden="true" />
            <h2 id="request-title">告诉我这次想怎么安排</h2>
          </div>

          <label className="field-label" htmlFor="request-input">
            需求描述
          </label>
          <textarea
            id="request-input"
            value={userInput}
            onChange={(event) => setUserInput(event.target.value)}
            rows={5}
            disabled={isInFlight}
            placeholder="例如：今天下午想带孩子在家附近玩几个小时，再吃一顿清淡晚餐。"
          />

          <div className="field-stack">
            <p className="field-label">示例入口</p>
            <div className="example-chip-row">
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example.label}
                  className="example-chip"
                  type="button"
                  onClick={() => setUserInput(example.prompt)}
                  disabled={isInFlight}
                >
                  {example.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field-stack advanced-options-shell">
            <button
              className="advanced-options-toggle"
              type="button"
              onClick={() => setAdvancedOptionsOpen((current) => !current)}
              data-testid="advanced-options-toggle"
              aria-expanded={advancedOptionsOpen}
            >
              <span className="advanced-options-label">
                <SlidersHorizontal size={16} aria-hidden="true" />
                <span>高级选项</span>
              </span>
              <span>{advancedOptionsOpen ? "收起" : "展开"}</span>
            </button>

            {advancedOptionsOpen ? (
              <div className="advanced-options-panel">
                <label className="field-label" htmlFor="read-profile-select">
                  读取路径
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
                  <option value="amap">AMap 只读预览</option>
                </select>
                <p className="helper-text">{readProfileHelper(selectedReadProfile)}</p>
              </div>
            ) : null}
          </div>

          {inputIsEmpty ? <p className="validation-text">请输入需求，或先点一个示例入口。</p> : null}

          <div className="button-row">
            <button
              className="primary-button"
              type="button"
              onClick={handleStart}
              disabled={inputIsEmpty || isInFlight}
              data-testid="start-button"
            >
              {requestState === "starting" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
              <span>{requestState === "starting" ? "生成中..." : "开始规划"}</span>
            </button>

            <button className="secondary-button" type="button" onClick={resetComposer} disabled={isInFlight}>
              <RotateCcw size={17} />
              <span>清空输入</span>
            </button>
          </div>

          {visibleErrorMessage ? (
            <div className="error-banner" role="alert">
              <AlertCircle size={18} aria-hidden="true" />
              <span>{visibleErrorMessage}</span>
            </div>
          ) : null}
        </section>
      </section>

      <section className="chat-thread-stage" aria-label="对话式规划进度">
        {threadItems.length ? (
          <ConversationThread
            items={threadItems}
            activeRunId={run?.run_id ?? null}
            requestState={requestState}
            clarificationReply={clarificationReply}
            replanReply={replanReply}
            canClarify={canClarify}
            canConfirm={canConfirm}
            canDecline={canDecline}
            canReplan={canReplan}
            canRefresh={canRefresh}
            onSelectPlan={setSelectedPlanId}
            onClarificationReplyChange={setClarificationReply}
            onClarificationSubmit={handleClarify}
            onReplanReplyChange={setReplanReply}
            onReplanSubmit={handleReplan}
            onConfirm={handleConfirm}
            onDecline={handleDecline}
            onRefresh={handleRefresh}
          />
        ) : (
          <section className="chat-thread-empty-state">
            <p className="eyebrow">Conversation Preview</p>
            <h2>首屏不再展示运行摘要或大面板</h2>
            <p>提交需求后，这里会按时间顺序出现你的请求、系统进度、推荐方案摘要、补充问题和最终结果。</p>
          </section>
        )}
      </section>
    </main>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = status === "ready" ? "准备就绪" : statusLabel(status) ?? status;
  return <span className={`status-badge status-${status.replace(/[^a-z0-9_-]/gi, "-")}`}>{label}</span>;
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

function errorMessageForDisplay(error: unknown) {
  if (error instanceof Error && error.name === "DemoApiError" && error.message.trim()) {
    return error.message;
  }
  return GENERIC_ERROR_MESSAGE;
}

function buildDemoExternalUserId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `web-demo-user-${crypto.randomUUID()}`;
  }
  return `web-demo-user-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildReplanRequest(reply: string, selectedPlanIndex: number): DemoReplanRunRequest {
  return {
    user_input: reply.trim(),
    selected_plan_index: selectedPlanIndex,
  };
}
