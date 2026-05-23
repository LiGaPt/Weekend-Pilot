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
  DemoActionManifestSummary,
  DemoCandidateSummary,
  DemoPlanPreview,
  DemoReadProfile,
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
  const [selectedReadProfile, setSelectedReadProfile] = useState<DemoReadProfile>("mock_world");
  const [run, setRun] = useState<DemoRunSummary | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedPlan = useMemo(() => choosePlan(run, selectedPlanId), [run, selectedPlanId]);
  const trimmedInput = userInput.trim();
  const inputIsEmpty = trimmedInput.length === 0;
  const isInFlight = ["starting", "refreshing", "confirming", "declining"].includes(requestState);
  const canRefresh = Boolean(run?.run_id) && !isInFlight;
  const isAwaitingConfirmation = run?.status === "awaiting_confirmation";
  const isAmapPreview = run?.read_profile === "amap";
  const canConfirm = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight && !isAmapPreview);
  const canDecline = Boolean(isAwaitingConfirmation && selectedPlan && !isInFlight);

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
        read_profile: selectedReadProfile,
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
          <p className="eyebrow">WeekendPilot Demo</p>
          <h1 id="app-title">Weekend planning preview</h1>
        </div>
        <StatusBadge status={requestState} />
      </section>

      <div className="app-grid">
        <aside className="side-rail" aria-label="Request and run summary">
          <section className="panel composer-panel" aria-labelledby="request-title">
            <div className="section-heading">
              <Send size={18} aria-hidden="true" />
              <h2 id="request-title">Request</h2>
            </div>

            <label className="field-label" htmlFor="request-input">
              Planning prompt
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
                Read path
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
                <span>{requestState === "starting" ? "Planning..." : "Start planning"}</span>
              </button>

              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setUserInput(DEFAULT_PROMPT);
                  setSelectedReadProfile("mock_world");
                  setErrorMessage(null);
                }}
                disabled={isInFlight}
              >
                <RotateCcw size={17} />
                <span>Reset example</span>
              </button>
            </div>

            {errorMessage ? (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} aria-hidden="true" />
                <span>{errorMessage}</span>
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

        <section className="workspace" aria-label="Plan preview and confirmation boundary">
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
              <h2>Ready for preview</h2>
              <p>Mock World stays the default. AMap can be enabled explicitly for read-only local preview.</p>
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
        <h2 id="run-title">Run summary</h2>
      </div>

      <dl className="metadata-list">
        <MetaItem label="Run status" value={run?.status} testId="run-status" />
        <MetaItem label="Run ID" value={run?.run_id} mono testId="run-id" />
        <MetaItem label="Read path" value={readProfileLabel(run?.read_profile)} testId="active-read-profile" />
        <MetaItem label="Action count" value={numberValue(run?.action_count)} testId="action-count" />
        <MetaItem label="Execution status" value={run?.execution_status} />
        <MetaItem label="Feedback status" value={run?.feedback_status} />
        <MetaItem label="Plan version" value={run?.plan_version.version_label} testId="plan-version" />
      </dl>

      <button
        className="secondary-button full-width"
        type="button"
        onClick={onRefresh}
        disabled={!canRefresh}
        data-testid="refresh-button"
      >
        {requestState === "refreshing" ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
        <span>{requestState === "refreshing" ? "Refreshing..." : "Refresh run"}</span>
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
    <div className="plan-tabs" role="tablist" aria-label="Returned plans">
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
          <span>{plan.title || `Plan ${index + 1}`}</span>
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
          <p className="eyebrow">Selected plan</p>
          <h2>{plan.title || "Untitled plan"}</h2>
          <p>{plan.summary || "No summary available."}</p>
        </div>
        <StatusBadge status={plan.status} />
      </header>

      <div className="plan-grid">
        <CandidateSection title="Activity" icon={<Activity size={18} />} candidate={plan.activity} />
        <CandidateSection title="Dining" icon={<Utensils size={18} />} candidate={plan.dining} />
      </div>

      <section className="detail-section" aria-labelledby="timeline-title">
        <div className="section-heading">
          <Clock3 size={18} aria-hidden="true" />
          <h3 id="timeline-title">Timeline</h3>
        </div>
        {plan.timeline?.length ? (
          <ol className="timeline-list">
            {plan.timeline.map((item, index) => (
              <li key={`${item.sequence ?? index}-${item.title ?? index}`}>
                <span className="time-range">
                  {item.start_label || "TBD"} - {item.end_label || "TBD"}
                </span>
                <span className="timeline-title">{item.title || "Untitled stop"}</span>
                <span className="muted">{minutes(item.duration_minutes)}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No timeline yet.</p>
        )}
      </section>

      <section className="detail-section" aria-labelledby="route-title">
        <div className="section-heading">
          <Route size={18} aria-hidden="true" />
          <h3 id="route-title">Route</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="Mode" value={routeMode(plan.route?.mode)} />
          <MetaItem label="Distance" value={distance(plan.route?.distance_meters)} />
          <MetaItem label="Duration" value={minutes(plan.route?.duration_minutes)} />
          <MetaItem label="Summary" value={plan.route?.summary} />
        </dl>
      </section>

      <section className="detail-section" aria-labelledby="feasibility-title">
        <div className="section-heading">
          <CheckCircle2 size={18} aria-hidden="true" />
          <h3 id="feasibility-title">Feasibility</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="Result" value={feasibilityLabel(plan.feasibility?.is_feasible)} />
          <MetaItem label="Total duration" value={minutes(plan.feasibility?.total_duration_minutes)} />
          <MetaItem label="Route duration" value={minutes(plan.feasibility?.route_duration_minutes)} />
          <MetaItem label="Queue wait" value={minutes(plan.feasibility?.queue_wait_minutes)} />
        </dl>
        <TextList title="Reasons" items={plan.feasibility?.reasons} />
        <TextList title="Warnings" items={plan.feasibility?.warnings} />
      </section>

      <section className="detail-section" aria-labelledby="actions-title">
        <div className="section-heading">
          <MapPinned size={18} aria-hidden="true" />
          <h3 id="actions-title">Action preview</h3>
        </div>
        <p className="muted">{actionManifestSourceLabel(plan.action_manifest)}</p>
        {plan.action_manifest.actions.length ? (
          <ul className="action-list">
            {plan.action_manifest.actions.map((action, index) => (
              <li key={`${action.action_ref ?? action.action_type ?? index}`}>
                <span className="action-type">{actionLabel(action.action_type) || "Action"}</span>
                <span>{action.target_id || "No target"}</span>
                <span className="muted">{action.reason || "No reason provided."}</span>
                <span className="requirement">{actionExecutionLabel(action.execution_order)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No pending actions.</p>
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
        <MetaItem label="Name" value={candidate?.name} />
        <MetaItem label="Category" value={categoryLabel(candidate?.category)} />
        <MetaItem label="Address" value={candidate?.address} />
        <MetaItem label="Tags" value={candidate?.tags?.length ? candidate.tags.map(tagLabel).join(", ") : undefined} />
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
        <p className="eyebrow">Confirmation boundary</p>
        <h2 id="confirm-title">{plan.confirmation?.status || confirmationStatus(run.status)}</h2>
        <p>
          {showReadOnlyNotice
            ? AMAP_READ_ONLY_NOTE
            : "The workflow pauses here until a reviewer confirms or declines the selected plan."}
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
              <span>{requestState === "confirming" ? "Confirming..." : "Confirm selected plan"}</span>
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
            <span>{requestState === "declining" ? "Declining..." : "Do not continue"}</span>
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
        <p className="eyebrow">Result</p>
        <h2 id="declined-title">Declined</h2>
        <p>{userFacingText(plan.confirmation?.reason) || "The selected plan was declined before execution."}</p>
      </section>
    );
  }

  if (!plan.execution && !plan.feedback) {
    return null;
  }

  const feedback = plan.feedback;

  return (
    <section className="panel result-panel" aria-labelledby="result-title">
      <p className="eyebrow">Execution and feedback</p>
      <h2 id="result-title">{feedback?.headline || plan.execution?.status || "Execution result"}</h2>
      <dl className="compact-list">
        <MetaItem label="Execution status" value={plan.execution?.status || run.execution_status} />
        <MetaItem label="Succeeded" value={numberValue(plan.execution?.succeeded_count)} />
        <MetaItem label="Failed" value={numberValue(plan.execution?.failed_count)} />
        <MetaItem label="Feedback status" value={feedback?.status || run.feedback_status} />
      </dl>
      {feedback?.message ? <p>{feedback.message}</p> : null}
      <FeedbackActions title="Completed actions" items={feedback?.completed_actions} />
      <FeedbackActions title="Failed actions" items={feedback?.failed_actions} />
      <TextList title="Next steps" items={feedback?.next_steps} />
    </section>
  );
}

function FeedbackActions({ title, items }: { title: string; items?: Record<string, unknown>[] }) {
  if (!items?.length) {
    return (
      <div className="feedback-block">
        <h3>{title}</h3>
        <p className="muted">None.</p>
      </div>
    );
  }

  return (
    <div className="feedback-block">
      <h3>{title}</h3>
      <ul className="feedback-list">
        {items.map((item, index) => (
          <li key={`${safeText(item.tool_name) || safeText(item.action_type) || title}-${index}`}>
            <span>{actionLabel(safeText(item.tool_name) || safeText(item.action_type)) || "Action"}</span>
            <span>{feedbackStatusLabel(safeText(item.status)) || "Unknown"}</span>
            <span className="muted">
              {userFacingText(safeText(item.message)) || safeText(item.target_label) || "No details available."}
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
        <p className="muted">None.</p>
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
    return "N/A";
  }
  return String(value);
}

function numberValue(value?: number | null) {
  return typeof value === "number" ? String(value) : undefined;
}

function minutes(value?: number | null) {
  return typeof value === "number" ? `${value} min` : "N/A";
}

function distance(value?: number | null) {
  if (typeof value !== "number") {
    return "N/A";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} km`;
  }
  return `${value} m`;
}

function routeMode(value?: string | null) {
  const labels: Record<string, string> = {
    walking: "Walking",
    driving: "Driving",
  };
  return value ? labels[value] ?? value : null;
}

function categoryLabel(value?: string | null) {
  const labels: Record<string, string> = {
    activity: "Activity",
    dining: "Dining",
    addon: "Addon",
  };
  return value ? labels[value] ?? value : null;
}

function tagLabel(value: string) {
  const labels: Record<string, string> = {
    child_friendly: "Child friendly",
    indoor: "Indoor",
    museum: "Museum",
    educational: "Educational",
    outdoor: "Outdoor",
    playground: "Playground",
    citywalk: "City walk",
    light_activity: "Light activity",
    lighter_options: "Lighter options",
    quiet: "Quiet",
    vegetable_forward: "Vegetable forward",
    family_tables: "Family tables",
    balanced_menu: "Balanced menu",
    quick_meal: "Quick meal",
    simple: "Simple",
    drinks: "Drinks",
    snacks: "Snacks",
    family: "Family",
  };
  return labels[value] ?? value;
}

function feasibilityLabel(value?: boolean | null) {
  if (value === true) {
    return "Feasible";
  }
  if (value === false) {
    return "Not feasible";
  }
  return "N/A";
}

function safeText(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function actionLabel(value?: string | null) {
  const labels: Record<string, string> = {
    book_ticket: "Book ticket",
    reserve_restaurant: "Reserve restaurant",
    join_queue: "Join queue",
    order_addon: "Order addon",
    send_message: "Send message",
  };
  return value ? labels[value] ?? value : null;
}

function actionExecutionLabel(value?: number | null) {
  return typeof value === "number" ? `Step ${value}` : "Execution order pending";
}

function actionManifestSourceLabel(manifest: DemoActionManifestSummary) {
  if (manifest.source === "confirmed_actions") {
    return "This preview reflects the confirmed action manifest that would execute after approval.";
  }
  if (manifest.source === "proposed_actions") {
    return "This preview reflects the proposed actions before any side effect is allowed to run.";
  }
  return "No public action preview is available for this plan.";
}

function feedbackStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    completed: "Completed",
    already_completed: "Already completed",
    failed: "Failed",
    blocked: "Blocked",
    rate_limited: "Rate limited",
    succeeded: "Succeeded",
    written: "Written",
  };
  return value ? labels[value] ?? value : null;
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
