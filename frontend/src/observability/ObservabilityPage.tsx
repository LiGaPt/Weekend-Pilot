import { useState } from "react";
import { DemoApiError } from "../api/demo";
import { getObservabilityRun } from "./api";
import type { InternalObservabilityRunSummary } from "./types";

const GENERIC_ERROR_MESSAGE = "Internal observability request failed. Please try again.";

export function ObservabilityPage() {
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState<InternalObservabilityRunSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleLoad() {
    const trimmed = runId.trim();
    if (!trimmed) {
      setValidationMessage("Enter a run ID before loading.");
      setResult(null);
      setErrorMessage(null);
      return;
    }

    setValidationMessage(null);
    setErrorMessage(null);
    setResult(null);
    setIsLoading(true);

    try {
      const next = await getObservabilityRun(trimmed);
      setResult(next);
    } catch (error) {
      if (error instanceof DemoApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(GENERIC_ERROR_MESSAGE);
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell observability-shell">
      <section className="app-header" aria-labelledby="observability-title">
        <div>
          <p className="eyebrow">Internal Review</p>
          <h1 id="observability-title">Internal Observability Review</h1>
        </div>
      </section>

      <div className="observability-grid">
        <section className="panel observability-panel">
          <div className="section-heading">
            <h2>Load Run</h2>
          </div>
          <label className="field-label" htmlFor="observability-run-id">
            Run ID
          </label>
          <input
            id="observability-run-id"
            className="text-input"
            type="text"
            value={runId}
            onChange={(event) => setRunId(event.target.value)}
            disabled={isLoading}
          />
          {validationMessage ? <p className="validation-text">{validationMessage}</p> : null}
          <div className="button-row">
            <button className="primary-button" type="button" onClick={handleLoad} disabled={isLoading}>
              <span>{isLoading ? "Loading..." : "Load Run"}</span>
            </button>
          </div>
          {errorMessage ? (
            <div className="error-banner" role="alert">
              <span>{errorMessage}</span>
            </div>
          ) : null}
        </section>

        {result ? (
          <ObservabilityResult result={result} />
        ) : (
          <section className="empty-workspace observability-empty">
            <h2>Internal Run Summary</h2>
            <p>
              {isLoading
                ? "Loading internal observability data..."
                : "Paste a run ID to inspect the internal workflow summary."}
            </p>
          </section>
        )}
      </div>
    </main>
  );
}

function ObservabilityResult({ result }: { result: InternalObservabilityRunSummary }) {
  const timing = result.workflow_timing_summary;

  return (
    <div className="workspace observability-workspace">
      <section className="panel">
        <div className="section-heading">
          <h2>Run Overview</h2>
        </div>
        <dl className="metadata-list observability-list">
          <MetaItem label="Run ID" value={result.run_id} mono />
          <MetaItem label="Trace ID" value={result.trace_id} mono />
          <MetaItem label="Status" value={result.status} />
          <MetaItem label="Case ID" value={result.case_id} />
          <MetaItem label="Agent Version" value={result.agent_version} />
          <MetaItem label="Prompt Version" value={result.prompt_version} />
          <MetaItem label="Tool Profile" value={result.tool_profile} />
          <MetaItem label="World Profile" value={result.world_profile} />
          <MetaItem label="Failure Profile" value={result.failure_profile} />
          <MetaItem label="Tool Events" value={String(result.tool_event_count)} />
          <MetaItem label="Action Count" value={String(result.action_count)} />
          <MetaItem label="Execution Status" value={result.execution_status} />
          <MetaItem label="Feedback Status" value={result.feedback_status} />
          <MetaItem label="Observability Status" value={result.observability_status} />
          <MetaItem label="Created At" value={result.created_at} />
          <MetaItem label="Updated At" value={result.updated_at} />
        </dl>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Workflow Timing</h2>
        </div>
        {timing ? (
          <>
            <dl className="metadata-list observability-list">
              <MetaItem label="Schema" value={timing.schema_version} />
              <MetaItem label="Total Duration" value={`${timing.total_duration_ms} ms`} />
              <MetaItem label="Stage Count" value={String(timing.stage_count)} />
            </dl>
            <ul className="observability-stage-list">
              {timing.stages.map((stage) => (
                <li key={stage.node_name}>
                  <strong>{stage.node_name}</strong>
                  <span>{stage.total_duration_ms} ms</span>
                  <span>attempts: {stage.attempt_count}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">No workflow timing summary is available for this run yet.</p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Node History</h2>
        </div>
        {result.node_history.length ? (
          <ol className="node-list">
            {result.node_history.map((node, index) => (
              <li key={`${node}-${index}`}>{node}</li>
            ))}
          </ol>
        ) : (
          <p className="muted">No node history is available.</p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Agent Roles</h2>
        </div>
        {result.agent_roles.length ? (
          <ul className="observability-chip-list">
            {result.agent_roles.map((role) => (
              <li key={role}>{role}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No agent roles were recorded.</p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Observability Summary</h2>
        </div>
        <dl className="metadata-list observability-list">
          <MetaItem label="Trace ID" value={result.observability_summary.trace_id} mono />
          <MetaItem label="Status" value={result.observability_summary.status} />
          <MetaItem
            label="Local Buffer Written"
            value={booleanLabel(result.observability_summary.local_buffer_written)}
          />
          <MetaItem
            label="LangSmith Enabled"
            value={booleanLabel(result.observability_summary.langsmith_enabled)}
          />
          <MetaItem
            label="LangSmith Posted"
            value={booleanLabel(result.observability_summary.langsmith_posted)}
          />
          <MetaItem
            label="Local Buffer Error"
            value={stringifyValue(result.observability_summary.local_buffer_error)}
          />
          <MetaItem label="LangSmith Error" value={stringifyValue(result.observability_summary.langsmith_error)} />
        </dl>
      </section>

      <div className="observability-placeholder-grid">
        <PlaceholderPanel title="Tool Events" body="Detailed tool event inspection is not implemented in this task yet." />
        <PlaceholderPanel title="Action Ledger" body="Detailed action ledger inspection is not implemented in this task yet." />
        <PlaceholderPanel
          title="Benchmark Artifacts"
          body="Detailed benchmark artifact inspection is not implemented in this task yet."
        />
        <PlaceholderPanel title="Recovery Path" body="Detailed recovery path inspection is not implemented in this task yet." />
      </div>
    </div>
  );
}

function PlaceholderPanel({ title, body }: { title: string; body: string }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>{title}</h2>
      </div>
      <p className="muted">{body}</p>
    </section>
  );
}

function MetaItem({
  label,
  value,
  mono = false,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{value && value.trim() ? value : "N/A"}</dd>
    </div>
  );
}

function booleanLabel(value: boolean | null) {
  if (value === true) {
    return "true";
  }
  if (value === false) {
    return "false";
  }
  return null;
}

function stringifyValue(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}
