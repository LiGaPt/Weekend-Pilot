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
  DemoFeedbackSummary,
  DemoPlanPreview,
  DemoProposedActionSummary,
  DemoRunSummary,
} from "./types/demo";

const DEFAULT_PROMPT =
  "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.";

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
      setErrorMessage(error instanceof Error ? error.message : "The demo request failed.");
    }
  }

  return (
    <main className="app-shell">
      <section className="app-header" aria-labelledby="app-title">
        <div>
          <p className="eyebrow">WeekendPilot Web Demo</p>
          <h1 id="app-title">Family afternoon planner</h1>
        </div>
        <StatusBadge status={requestState} />
      </section>

      <div className="app-grid">
        <aside className="side-rail" aria-label="Request and run metadata">
          <section className="panel composer-panel" aria-labelledby="request-title">
            <div className="section-heading">
              <Send size={18} aria-hidden="true" />
              <h2 id="request-title">Request</h2>
            </div>
            <label className="field-label" htmlFor="request-input">
              Request
            </label>
            <textarea
              id="request-input"
              value={userInput}
              onChange={(event) => setUserInput(event.target.value)}
              rows={8}
              disabled={isInFlight}
            />
            {inputIsEmpty ? <p className="validation-text">Enter a request to start planning.</p> : null}
            <div className="button-row">
              <button className="primary-button" type="button" onClick={handleStart} disabled={inputIsEmpty || isInFlight}>
                {requestState === "starting" ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
                <span>{requestState === "starting" ? "Planning" : "Start planning"}</span>
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
                <span>Reset sample</span>
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

        <section className="workspace" aria-label="Plan review workspace">
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
              <h2>Ready for a demo run</h2>
              <p>Start with the sample request to generate plans from the Mock World workflow.</p>
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
        <h2 id="run-title">Run metadata</h2>
      </div>
      <dl className="metadata-list">
        <MetaItem label="Run status" value={run?.status} testId="run-status" />
        <MetaItem label="Run ID" value={run?.run_id} mono testId="run-id" />
        <MetaItem label="Trace ID" value={run?.trace_id} mono />
        <MetaItem label="Tool events" value={numberValue(run?.tool_event_count)} />
        <MetaItem label="Actions" value={numberValue(run?.action_count)} testId="action-count" />
        <MetaItem label="Execution" value={run?.execution_status} />
        <MetaItem label="Feedback" value={run?.feedback_status} />
        <MetaItem label="Observability" value={run?.observability_status} />
      </dl>
      <div className="metadata-block">
        <h3>Agent roles</h3>
        <p>{run?.agent_roles?.length ? run.agent_roles.join(", ") : "Unavailable"}</p>
      </div>
      <div className="metadata-block">
        <h3>Node history</h3>
        <ol className="node-list">
          {run?.node_history?.length ? (
            run.node_history.map((node, index) => <li key={`${node}-${index}`}>{node}</li>)
          ) : (
            <li>Unavailable</li>
          )}
        </ol>
      </div>
      <button
        className="secondary-button full-width"
        type="button"
        onClick={onRefresh}
        disabled={!canRefresh}
        data-testid="refresh-button"
      >
        {requestState === "refreshing" ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
        <span>{requestState === "refreshing" ? "Refreshing" : "Refresh status"}</span>
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
          <p>{plan.summary || "Not provided"}</p>
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
                  {item.start_label || "Start unavailable"} - {item.end_label || "End unavailable"}
                </span>
                <span className="timeline-title">{item.title || "Untitled stop"}</span>
                <span className="muted">{minutes(item.duration_minutes)}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">Unavailable</p>
        )}
      </section>

      <section className="detail-section" aria-labelledby="route-title">
        <div className="section-heading">
          <Route size={18} aria-hidden="true" />
          <h3 id="route-title">Route</h3>
        </div>
        <dl className="compact-list">
          <MetaItem label="Mode" value={plan.route?.mode} />
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
          <h3 id="actions-title">Proposed actions</h3>
        </div>
        {plan.proposed_actions?.length ? (
          <ul className="action-list">
            {plan.proposed_actions.map((action, index) => (
              <li key={`${action.action_ref ?? action.action_type ?? index}`}>
                <span className="action-type">{action.action_type || "Action"}</span>
                <span>{action.target_id || "Target unavailable"}</span>
                <span className="muted">{action.reason || "Reason unavailable"}</span>
                <span className="requirement">
                  {action.requires_confirmation ? "Requires confirmation" : "No confirmation flag"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Unavailable</p>
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
        <MetaItem label="Category" value={candidate?.category} />
        <MetaItem label="Address" value={candidate?.address} />
        <MetaItem label="Tags" value={candidate?.tags?.length ? candidate.tags.join(", ") : undefined} />
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
        <p className="eyebrow">Confirmation</p>
        <h2 id="confirm-title">{plan.confirmation?.status || confirmationStatus(run.status)}</h2>
        <p>
          {run.status === "awaiting_confirmation"
            ? "Review the selected plan before allowing write actions."
            : "This run is no longer awaiting a mutation decision."}
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
            <span>{requestState === "confirming" ? "Confirming" : "Confirm selected plan"}</span>
          </button>
          <button
            className="danger-button"
            type="button"
            onClick={onDecline}
            disabled={!canDecline}
            data-testid="decline-button"
          >
            {requestState === "declining" ? <Loader2 className="spin" size={17} /> : <XCircle size={17} />}
            <span>{requestState === "declining" ? "Declining" : "Decline"}</span>
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
        <p>{plan.confirmation?.reason || "The selected plan was declined. No execution result is available."}</p>
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
        <p className="muted">Unavailable</p>
      </div>
    );
  }

  return (
    <div className="feedback-block">
      <h3>{title}</h3>
      <ul className="feedback-list">
        {items.map((item, index) => (
          <li key={`${safeText(item.tool_name) || safeText(item.action_type) || title}-${index}`}>
            <span>{safeText(item.tool_name) || safeText(item.action_type) || "Action"}</span>
            <span>{safeText(item.status) || "Status unavailable"}</span>
            <span className="muted">{safeText(item.message) || safeText(item.target_label) || "Detail unavailable"}</span>
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
        <p className="muted">Unavailable</p>
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
    return "Unavailable";
  }
  return String(value);
}

function numberValue(value?: number | null) {
  return typeof value === "number" ? String(value) : undefined;
}

function minutes(value?: number | null) {
  return typeof value === "number" ? `${value} min` : "Unavailable";
}

function distance(value?: number | null) {
  if (typeof value !== "number") {
    return "Unavailable";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} km`;
  }
  return `${value} m`;
}

function feasibilityLabel(value?: boolean | null) {
  if (value === true) {
    return "Feasible";
  }
  if (value === false) {
    return "Not feasible";
  }
  return "Unavailable";
}

function safeText(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}
