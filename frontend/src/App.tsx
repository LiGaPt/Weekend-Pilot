import { AlertCircle, Loader2, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { clarifyRun, confirmRun, declineRun, replanRun, startRunStream } from "./api/demo";
import { ConversationThread } from "./chat/ConversationThread";
import {
  buildProgressCardItem,
  choosePlan,
  isClarificationSummary,
  progressLabelForState,
  projectConversationThread,
  resolveSelectedPlanIndex,
  statusLabel,
  type ConversationHistoryEntry,
} from "./chat/thread";
import { demoScenarioPresets } from "./demoScenarioPresets";
import type {
  DemoMockWorldProfile,
  DemoProgressSummary,
  DemoReadProfile,
  DemoReplanRunRequest,
  DemoRunSummary,
} from "./types/demo";

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

type ComposerMode = "start" | "clarify" | "replan";

const TERMINAL_SUCCESS_STATUSES = new Set(["completed", "partially_completed", "failed", "skipped"]);
const INPUT_ACTION_STATES = new Set<RequestState>(["starting", "clarifying", "replanning"]);

export default function App() {
  const [userInput, setUserInput] = useState("");
  const selectedReadProfile: DemoReadProfile = "mock_world";
  const [selectedMockWorldProfile, setSelectedMockWorldProfile] = useState<DemoMockWorldProfile | null>(null);
  const [run, setRun] = useState<DemoRunSummary | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [conversationEntries, setConversationEntries] = useState<ConversationHistoryEntry[]>([]);
  const [liveStartProgress, setLiveStartProgress] = useState<{
    runId: string;
    progress: DemoProgressSummary;
  } | null>(null);

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
  const isAwaitingClarification = run?.status === "awaiting_clarification";
  const isAwaitingConfirmation = run?.status === "awaiting_confirmation";
  const isAmapPreview = run?.read_profile === "amap";
  const showClarificationComposer = Boolean(isAwaitingClarification && clarificationPayload);
  const composerMode = resolveComposerMode(showClarificationComposer, isAwaitingConfirmation, selectedPlan);
  const canConfirm = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight && !isAmapPreview);
  const canDecline = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight);
  const canSubmit = canSubmitComposer({
    mode: composerMode,
    run,
    selectedPlan,
    inputIsEmpty,
    isInFlight,
    showClarificationComposer,
    isAwaitingConfirmation,
  });

  const liveProgressCard = useMemo(
    () => (liveStartProgress ? buildProgressCardItem(liveStartProgress.runId, liveStartProgress.progress) : null),
    [liveStartProgress],
  );

  const pendingAction =
    liveProgressCard ??
    (isInFlight
      ? {
          id: `pending-${requestState}`,
          kind: "system_progress",
          label: progressLabelForState(requestState),
          status: requestState,
        }
      : null);

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

  async function handleComposerSubmit() {
    if (!canSubmit) {
      return;
    }

    if (composerMode === "clarify") {
      await handleClarify();
      return;
    }

    if (composerMode === "replan") {
      await handleReplan();
      return;
    }

    await handleStart();
  }

  async function handleStart() {
    if (inputIsEmpty || isInFlight) {
      return;
    }

    appendUserEntry("start", trimmedInput);

    setRequestState("starting");
    setErrorMessage(null);
    setLiveStartProgress(null);

    try {
      const nextRun = await startRunStream(
        {
          user_input: trimmedInput,
          external_user_id: buildDemoExternalUserId(),
          display_name: "网页用户",
          case_id: "web-demo",
          selected_plan_index: 0,
          read_profile: selectedReadProfile,
          ...(selectedMockWorldProfile ? { mock_world_profile: selectedMockWorldProfile } : {}),
        },
        {
          onProgress: (event) => {
            setLiveStartProgress({
              runId: event.run_id,
              progress: event.progress,
            });
          },
        },
      );

      applyRun(nextRun, "starting");
    } catch (error) {
      setLiveStartProgress(null);
      setRequestState("error");
      setErrorMessage(errorMessageForDisplay(error));
    }
  }

  async function handleReplan() {
    if (!run?.run_id || !selectedPlan || inputIsEmpty || isInFlight) {
      return;
    }

    appendUserEntry("replan", trimmedInput);
    const selectedPlanIndex = resolveSelectedPlanIndex(run, selectedPlanId);

    await runAction("replanning", () => replanRun(run.run_id, buildReplanRequest(trimmedInput, selectedPlanIndex)));
  }

  async function handleClarify() {
    if (!run?.run_id || !showClarificationComposer || inputIsEmpty || isInFlight) {
      return;
    }

    appendUserEntry("clarify", trimmedInput);
    await runAction("clarifying", () =>
      clarifyRun(run.run_id, {
        user_input: trimmedInput,
        selected_plan_index: 0,
      }),
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
    setLiveStartProgress(null);

    try {
      const nextRun = await action();
      onSuccess?.(nextRun);
      applyRun(nextRun, nextState);
    } catch (error) {
      setLiveStartProgress(null);
      setRequestState("error");
      setErrorMessage(errorMessageForDisplay(error));
    }
  }

  function applyRun(nextRun: DemoRunSummary | null | undefined, sourceState: RequestState) {
    if (!isDemoRunSummary(nextRun)) {
      throw new Error("Invalid demo run summary.");
    }

    setLiveStartProgress(null);
    upsertRunEntry(nextRun);
    setRun(nextRun);
    setSelectedPlanId(nextRun.selected_plan_id ?? nextRun.plans[0]?.plan_id ?? null);
    setRequestState(stateFromRun(nextRun));

    if (INPUT_ACTION_STATES.has(sourceState)) {
      setUserInput("");
      if (sourceState === "starting") {
        setSelectedMockWorldProfile(null);
      }
    }
  }

  function handleScenarioPresetClick(profile: DemoMockWorldProfile, prompt: string) {
    setErrorMessage(null);

    if (selectedMockWorldProfile === profile) {
      setSelectedMockWorldProfile(null);
      return;
    }

    setUserInput(prompt);
    setSelectedMockWorldProfile(profile);
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

  return (
    <main className="app-shell customer-chat-shell">
      <header className="chat-topbar" aria-label="周末规划助手">
        <div className="chat-brand-block">
          <p className="chat-brand">周末规划助手</p>
        </div>
        <StatusBadge status={requestState === "idle" ? "ready" : requestState} />
      </header>

      <section className="chat-thread-stage" aria-label="对话式规划进度">
        {threadItems.length ? (
          <ConversationThread
            items={threadItems}
            activeRunId={run?.run_id ?? null}
            requestState={requestState}
            canConfirm={canConfirm}
            canDecline={canDecline}
            onSelectPlan={setSelectedPlanId}
            onConfirm={handleConfirm}
            onDecline={handleDecline}
          />
        ) : (
          <section className="chat-thread-empty-state" aria-label="空对话">
            <h1>今天想怎么安排？</h1>
          </section>
        )}
      </section>

      <section className="chat-composer-shell" data-testid="chat-composer" aria-label="发送消息">
        <div className="chat-composer">
          {visibleErrorMessage ? (
            <div className="error-banner composer-error" role="alert">
              <AlertCircle size={18} aria-hidden="true" />
              <span>{visibleErrorMessage}</span>
            </div>
          ) : null}

          {composerMode === "start" ? (
            <div className="example-chip-row" data-testid="scenario-selector" aria-label="Mock World 场景入口">
              {demoScenarioPresets.map((preset) => {
                const isSelected = selectedMockWorldProfile === preset.mockWorldProfile;
                return (
                  <button
                    key={preset.mockWorldProfile}
                    type="button"
                    className={`example-chip${isSelected ? " active" : ""}`}
                    data-testid={`scenario-chip-${preset.mockWorldProfile}`}
                    aria-pressed={isSelected}
                    disabled={isInFlight}
                    onClick={() => handleScenarioPresetClick(preset.mockWorldProfile, preset.prompt)}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>
          ) : null}

          <div className="composer-row">
            <label className="sr-only" htmlFor="request-input">
              {labelForComposerMode(composerMode)}
            </label>
            <textarea
              id="request-input"
              data-testid="main-composer-input"
              value={userInput}
              onChange={(event) => setUserInput(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  void handleComposerSubmit();
                }
              }}
              rows={1}
              disabled={isInFlight}
              placeholder={placeholderForComposerMode(composerMode)}
            />
            <button
              className="primary-button composer-submit-button"
              type="button"
              onClick={() => void handleComposerSubmit()}
              disabled={!canSubmit}
              data-testid="start-button"
              aria-label={submitLabelForState(requestState, composerMode)}
            >
              {isInputActionInFlight(requestState) ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              <span>{submitLabelForState(requestState, composerMode)}</span>
            </button>
          </div>

          {run !== null && contextForComposerMode(composerMode) ? (
            <div className="composer-footer">
              <span className="composer-context">{contextForComposerMode(composerMode)}</span>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = status === "ready" ? "准备就绪" : statusLabel(status) ?? status;
  return <span className={`status-badge status-${status.replace(/[^a-z0-9_-]/gi, "-")}`}>{label}</span>;
}

function resolveComposerMode(
  showClarificationComposer: boolean,
  isAwaitingConfirmation: boolean,
  selectedPlan: unknown,
): ComposerMode {
  if (showClarificationComposer) {
    return "clarify";
  }
  if (isAwaitingConfirmation && selectedPlan) {
    return "replan";
  }
  return "start";
}

function canSubmitComposer({
  mode,
  run,
  selectedPlan,
  inputIsEmpty,
  isInFlight,
  showClarificationComposer,
  isAwaitingConfirmation,
}: {
  mode: ComposerMode;
  run: DemoRunSummary | null;
  selectedPlan: unknown;
  inputIsEmpty: boolean;
  isInFlight: boolean;
  showClarificationComposer: boolean;
  isAwaitingConfirmation: boolean;
}) {
  if (inputIsEmpty || isInFlight) {
    return false;
  }
  if (mode === "clarify") {
    return Boolean(run?.run_id && showClarificationComposer);
  }
  if (mode === "replan") {
    return Boolean(run?.run_id && isAwaitingConfirmation && selectedPlan);
  }
  return true;
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

function isInputActionInFlight(state: RequestState) {
  return INPUT_ACTION_STATES.has(state);
}

function labelForComposerMode(mode: ComposerMode) {
  if (mode === "clarify") {
    return "补充信息";
  }
  if (mode === "replan") {
    return "继续调整方案";
  }
  return "需求描述";
}

function placeholderForComposerMode(mode: ComposerMode) {
  if (mode === "clarify") {
    return "补充出发时间、同行人、时长或偏好...";
  }
  if (mode === "replan") {
    return "输入新的限制或偏好，例如：少走路、换成一个人、预算低一点...";
  }
  return "例如：今天下午想带孩子在家附近玩几个小时，再吃一顿清淡晚餐。";
}

function submitLabelForState(state: RequestState, mode: ComposerMode) {
  if (state === "starting") {
    return "生成中...";
  }
  if (state === "clarifying") {
    return "提交中...";
  }
  if (state === "replanning") {
    return "调整中...";
  }
  if (mode === "clarify") {
    return "提交补充";
  }
  if (mode === "replan") {
    return "继续调整";
  }
  return "开始规划";
}

function contextForComposerMode(mode: ComposerMode) {
  if (mode === "clarify") {
    return "补充信息会接到当前对话里。";
  }
  if (mode === "replan") {
    return "输入要求后会生成新的方案版本。";
  }
  return "";
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

function isDemoRunSummary(value: DemoRunSummary | null | undefined): value is DemoRunSummary {
  return Boolean(
    value &&
      typeof value.run_id === "string" &&
      typeof value.status === "string" &&
      typeof value.read_profile === "string" &&
      Array.isArray(value.plans) &&
      value.plan_version &&
      typeof value.plan_version.version_label === "string",
  );
}
