import { useEffect, useState } from "react";
import { getLatestReleaseGateBenchmarkSummary, getObservabilityRun, getSystemIntegritySummary } from "./api";
import { FrontendApiError } from "../shared/http";
import type {
  InternalActionLedgerSummary,
  InternalBenchmarkArtifactSummary,
  InternalBenchmarkTimingSummary,
  InternalObservabilityRunSummary,
  InternalRecoveryPathSummary,
  InternalReleaseGateBenchmarkSummary,
  InternalToolEventSummary,
  InternalWorkflowTimingSummary,
  SystemIntegrityEvidencePathSummary,
  SystemIntegritySummary,
} from "./types";

const GENERIC_ERROR_MESSAGE = "Internal observability request failed. Please try again.";
const BENCHMARK_GENERIC_ERROR_MESSAGE = "Internal benchmark summary request failed. Please try again.";
const INTEGRITY_GENERIC_ERROR_MESSAGE = "Internal system integrity request failed. Please try again.";
const COPY_FEEDBACK_RESET_MS = 1800;

type CopyFeedbackState = {
  key: string;
  status: "success" | "error";
} | null;

export function ObservabilityPage() {
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState<InternalObservabilityRunSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [benchmarkSummary, setBenchmarkSummary] = useState<InternalReleaseGateBenchmarkSummary | null>(null);
  const [benchmarkMissingMessage, setBenchmarkMissingMessage] = useState<string | null>(null);
  const [benchmarkErrorMessage, setBenchmarkErrorMessage] = useState<string | null>(null);
  const [isBenchmarkLoading, setIsBenchmarkLoading] = useState(true);
  const [systemIntegritySummary, setSystemIntegritySummary] = useState<SystemIntegritySummary | null>(null);
  const [systemIntegrityErrorMessage, setSystemIntegrityErrorMessage] = useState<string | null>(null);
  const [isSystemIntegrityLoading, setIsSystemIntegrityLoading] = useState(true);
  const [copyFeedback, setCopyFeedback] = useState<CopyFeedbackState>(null);

  useEffect(() => {
    let active = true;

    async function loadBenchmarkSummary() {
      setIsBenchmarkLoading(true);
      setBenchmarkSummary(null);
      setBenchmarkMissingMessage(null);
      setBenchmarkErrorMessage(null);

      try {
        const next = await getLatestReleaseGateBenchmarkSummary();
        if (!active) {
          return;
        }
        setBenchmarkSummary(next);
      } catch (error) {
        if (!active) {
          return;
        }

        if (error instanceof FrontendApiError && error.status === 404) {
          setBenchmarkMissingMessage(error.message);
        } else if (error instanceof FrontendApiError) {
          setBenchmarkErrorMessage(error.message);
        } else {
          setBenchmarkErrorMessage(BENCHMARK_GENERIC_ERROR_MESSAGE);
        }
      } finally {
        if (active) {
          setIsBenchmarkLoading(false);
        }
      }
    }

    void loadBenchmarkSummary();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadSystemIntegritySummary() {
      setIsSystemIntegrityLoading(true);
      setSystemIntegritySummary(null);
      setSystemIntegrityErrorMessage(null);

      try {
        const next = await getSystemIntegritySummary();
        if (!active) {
          return;
        }
        setSystemIntegritySummary(next);
      } catch (error) {
        if (!active) {
          return;
        }

        if (error instanceof FrontendApiError) {
          setSystemIntegrityErrorMessage(error.message);
        } else {
          setSystemIntegrityErrorMessage(INTEGRITY_GENERIC_ERROR_MESSAGE);
        }
      } finally {
        if (active) {
          setIsSystemIntegrityLoading(false);
        }
      }
    }

    void loadSystemIntegritySummary();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (copyFeedback === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setCopyFeedback((current) => (current?.key === copyFeedback.key ? null : current));
    }, COPY_FEEDBACK_RESET_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [copyFeedback]);

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
      if (error instanceof FrontendApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(GENERIC_ERROR_MESSAGE);
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCopyPath(copyKey: string, path: string) {
    try {
      if (typeof navigator === "undefined" || typeof navigator.clipboard?.writeText !== "function") {
        throw new Error("Clipboard is unavailable.");
      }
      await navigator.clipboard.writeText(path);
      setCopyFeedback({ key: copyKey, status: "success" });
    } catch {
      setCopyFeedback({ key: copyKey, status: "error" });
    }
  }

  function getCopyFeedback(copyKey: string) {
    if (copyFeedback?.key !== copyKey) {
      return null;
    }
    return copyFeedback.status === "success" ? "Copied" : "Copy failed";
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
        <BenchmarkSummaryPanel
          summary={benchmarkSummary}
          missingMessage={benchmarkMissingMessage}
          errorMessage={benchmarkErrorMessage}
          isLoading={isBenchmarkLoading}
          onCopyPath={handleCopyPath}
          copyFeedback={getCopyFeedback("latest-release-gate-alias-hero")}
        />
        <SystemIntegritySummaryPanel
          summary={systemIntegritySummary}
          errorMessage={systemIntegrityErrorMessage}
          isLoading={isSystemIntegrityLoading}
          onCopyPath={handleCopyPath}
          copyFeedbackForKey={getCopyFeedback}
        />

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
          <ObservabilityResult
            result={result}
            latestReleaseGateAliasPath={benchmarkSummary?.report_path ?? null}
            onCopyPath={handleCopyPath}
            copyFeedbackForKey={getCopyFeedback}
          />
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

function BenchmarkSummaryPanel({
  summary,
  missingMessage,
  errorMessage,
  isLoading,
  onCopyPath,
  copyFeedback,
}: {
  summary: InternalReleaseGateBenchmarkSummary | null;
  missingMessage: string | null;
  errorMessage: string | null;
  isLoading: boolean;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedback: string | null;
}) {
  return (
    <section className="panel observability-review-section observability-benchmark-hero-panel">
      <div className="section-heading">
        <h2>Benchmark Summary</h2>
      </div>
      <p className="muted reviewer-note">
        Reviewer-facing snapshot of the latest release_gate_v1 benchmark evidence.
      </p>

      {isLoading ? <p className="muted">Loading latest release_gate_v1 benchmark summary...</p> : null}

      {!isLoading && missingMessage ? <p className="muted">{missingMessage}</p> : null}

      {!isLoading && errorMessage ? (
        <div className="error-banner" role="alert">
          <span>{errorMessage}</span>
        </div>
      ) : null}

      {!isLoading && summary ? (
        <div className="observability-review-stack">
          <section className="observability-benchmark-hero">
            <div className="observability-benchmark-hero-copy">
              <p className="eyebrow">Latest Release Gate</p>
              <div className="observability-benchmark-hero-heading">
                <h3>{summary.suite_title}</h3>
                <StatusBadge status={summary.run_status} />
              </div>
              <p className="muted">
                Canonical reviewer-facing release gate evidence for <span className="mono">{summary.suite_id}</span>.
              </p>
            </div>

            <div className="observability-benchmark-scoreboard">
              <span className="observability-score-label">Overall Score</span>
              <strong>{formatScore(summary.overall_score)}</strong>
            </div>
          </section>

          <div className="observability-metric-grid">
            <MetricCard label="Case Count" value={String(summary.case_count)} />
            <MetricCard label="Passed" value={String(summary.passed_count)} />
            <MetricCard label="Failed" value={String(summary.failed_count)} />
            <MetricCard label="Errors" value={String(summary.error_count)} />
          </div>

          <BenchmarkTimingSummarySection summary={summary.benchmark_timing_summary_present ? summary.benchmark_timing_summary : null} />

          <PathField
            label="Latest Release Gate Alias"
            path={summary.report_path}
            copyLabel="Copy latest alias"
            copyKey="latest-release-gate-alias-hero"
            onCopyPath={onCopyPath}
            copyFeedback={copyFeedback}
          />

          <div className="observability-count-grid">
            <CountMapPanel title="Levels" items={summary.matrix_summary.level_counts} />
            <CountMapPanel title="Tool Profiles" items={summary.matrix_summary.tool_profile_counts} />
            <CountMapPanel title="Failure Modes" items={summary.matrix_summary.failure_mode_counts} />
            <CountMapPanel title="Tags" items={summary.matrix_summary.tag_counts} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function BenchmarkTimingSummarySection({
  summary,
}: {
  summary: InternalBenchmarkTimingSummary | null;
}) {
  const overall = summary?.overall_total_duration_ms ?? null;

  return (
    <section className="panel">
      <div className="section-heading">
        <h3>Timing Percentiles</h3>
      </div>
      {summary === null ? (
        <p className="muted">Suite timing summary is unavailable for this artifact.</p>
      ) : (
        <>
          <div className="observability-metric-grid observability-timing-grid">
            <MetricCard label="p50" value={formatDurationMs(overall?.p50_ms)} />
            <MetricCard label="p95" value={formatDurationMs(overall?.p95_ms)} />
            <MetricCard label="p99" value={formatDurationMs(overall?.p99_ms)} />
            <MetricCard label="Max" value={formatDurationMs(overall?.max_ms)} />
          </div>

          {summary.stages.length ? (
            <table>
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Samples</th>
                  <th>Retry Cases</th>
                  <th>p50</th>
                  <th>p95</th>
                  <th>p99</th>
                  <th>Max</th>
                </tr>
              </thead>
              <tbody>
                {summary.stages.map((stage) => (
                  <tr key={stage.node_name}>
                    <td className="mono">{stage.node_name}</td>
                    <td>{stage.sample_count}</td>
                    <td>{stage.retry_case_count}</td>
                    <td>{formatDurationMs(stage.p50_ms)}</td>
                    <td>{formatDurationMs(stage.p95_ms)}</td>
                    <td>{formatDurationMs(stage.p99_ms)}</td>
                    <td>{formatDurationMs(stage.max_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No per-stage timing rows are available.</p>
          )}
        </>
      )}
    </section>
  );
}

function SystemIntegritySummaryPanel({
  summary,
  errorMessage,
  isLoading,
  onCopyPath,
  copyFeedbackForKey,
}: {
  summary: SystemIntegritySummary | null;
  errorMessage: string | null;
  isLoading: boolean;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedbackForKey: (copyKey: string) => string | null;
}) {
  const evidencePaths = summary
    ? summary.evidence_paths
        .slice()
        .sort(
          (left, right) =>
            Number(right.required_for_summary) - Number(left.required_for_summary) ||
            left.evidence_id.localeCompare(right.evidence_id),
        )
    : [];

  return (
    <section className="panel observability-review-section observability-integrity-panel">
      <div className="section-heading">
        <h2>System Integrity Summary</h2>
      </div>
      <p className="muted reviewer-note">
        Reviewer-facing snapshot of the current V2 integrity posture and canonical evidence paths.
      </p>

      {isLoading ? <p className="muted">Loading system integrity summary...</p> : null}

      {!isLoading && errorMessage ? (
        <div className="error-banner" role="alert">
          <span>{errorMessage}</span>
        </div>
      ) : null}

      {!isLoading && summary ? (
        <div className="observability-review-stack">
          <section className="observability-benchmark-hero observability-integrity-hero">
            <div className="observability-benchmark-hero-copy">
              <p className="eyebrow">Current Integrity</p>
              <div className="observability-benchmark-hero-heading">
                <h3>v2_integrity</h3>
                <StatusBadge status={summary.status} />
                <StatusBadge status={summary.benchmark_summary.run_status} />
              </div>
              <p className="muted">
                Release blocked: {summary.benchmark_summary.release_blocked === null ? "N/A" : String(summary.benchmark_summary.release_blocked)}
              </p>
            </div>
            <div className="observability-benchmark-scoreboard">
              <span className="observability-score-label">Overall Score</span>
              <strong>
                {summary.benchmark_summary.overall_score === null ? "N/A" : formatScore(summary.benchmark_summary.overall_score)}
              </strong>
            </div>
          </section>

          <div className="observability-metric-grid">
            <MetricCard label="Case Count" value={stringOrNA(summary.benchmark_summary.case_count)} />
            <MetricCard label="Passed" value={stringOrNA(summary.benchmark_summary.passed_count)} />
            <MetricCard label="Failed" value={stringOrNA(summary.benchmark_summary.failed_count)} />
            <MetricCard label="Errors" value={stringOrNA(summary.benchmark_summary.error_count)} />
          </div>

          <div className="observability-integrity-section-grid">
            <section className="panel">
              <div className="section-heading">
                <h3>Pass@k</h3>
              </div>
              <dl className="metadata-list observability-list">
                <MetaItem label="Status" value={summary.stability_summary.status} />
                <MetaItem label="Success@1" value={stringifyMetric(summary.stability_summary.success_at_1)} />
                <MetaItem label="Pass@4" value={stringifyMetric(summary.stability_summary.pass_at_4)} />
                <MetaItem label="Pass^4" value={stringifyMetric(summary.stability_summary.pass_pow_4)} />
                <MetaItem label="Executed Runs" value={stringOrNA(summary.stability_summary.executed_run_count)} />
                <MetaItem label="Window Size" value={stringOrNA(summary.stability_summary.window_size)} />
                <MetaItem label="Window Count" value={stringOrNA(summary.stability_summary.window_count)} />
                <MetaItem label="Reason" value={summary.stability_summary.reason} />
              </dl>
            </section>

            <section className="panel">
              <div className="section-heading">
                <h3>Memory Governance</h3>
              </div>
              <dl className="metadata-list observability-list">
                <MetaItem label="Status" value={summary.memory_governance_summary.status} />
                <MetaItem
                  label="All Cases Passed"
                  value={String(summary.memory_governance_summary.all_memory_cases_passed)}
                />
                <MetaItem label="Case Count" value={String(summary.memory_governance_summary.memory_case_count)} />
                <MetaItem label="Passed" value={String(summary.memory_governance_summary.passed_case_count)} />
                <MetaItem label="Failed" value={String(summary.memory_governance_summary.failed_case_count)} />
                <MetaItem label="Errors" value={String(summary.memory_governance_summary.error_case_count)} />
                <MetaItem label="Reason" value={summary.memory_governance_summary.reason} />
              </dl>
              {summary.memory_governance_summary.failing_case_ids.length ? (
                <ul className="observability-chip-list">
                  {summary.memory_governance_summary.failing_case_ids.map((caseId) => (
                    <li key={caseId}>{caseId}</li>
                  ))}
                </ul>
              ) : null}
            </section>

            <section className="panel">
              <div className="section-heading">
                <h3>Recovery Replay</h3>
              </div>
              <dl className="metadata-list observability-list">
                <MetaItem label="Status" value={summary.recovery_replay_summary.status} />
                <MetaItem label="Review Status" value={summary.recovery_replay_summary.review_status} />
                <MetaItem label="Check Count" value={String(summary.recovery_replay_summary.check_count)} />
                <MetaItem label="Passed Checks" value={String(summary.recovery_replay_summary.passed_check_count)} />
                <MetaItem label="Failed Checks" value={String(summary.recovery_replay_summary.failed_check_count)} />
                <MetaItem label="Attempt Count" value={stringOrNA(summary.recovery_replay_summary.attempt_count)} />
                <MetaItem label="Max Attempts" value={stringOrNA(summary.recovery_replay_summary.max_attempts)} />
                <MetaItem label="Reason" value={summary.recovery_replay_summary.reason} />
              </dl>
              {summary.recovery_replay_summary.recovery_actions.length ? (
                <ul className="observability-chip-list">
                  {summary.recovery_replay_summary.recovery_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          </div>

          <section className="panel">
            <div className="section-heading">
              <h3>Evidence Paths</h3>
            </div>
            {evidencePaths.length ? (
              <div className="observability-path-stack">
                {evidencePaths.map((item) => (
                  <EvidencePathField
                    key={item.evidence_id}
                    item={item}
                    onCopyPath={onCopyPath}
                    copyFeedback={copyFeedbackForKey(`integrity-${item.evidence_id}`)}
                  />
                ))}
              </div>
            ) : (
              <p className="muted">No integrity evidence paths are available.</p>
            )}
          </section>
        </div>
      ) : null}
    </section>
  );
}

function EvidencePathField({
  item,
  onCopyPath,
  copyFeedback,
}: {
  item: SystemIntegrityEvidencePathSummary;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedback: string | null;
}) {
  const path = hasTextValue(item.path) ? item.path : null;

  return (
    <section className="observability-path-field">
      <div className="observability-path-field-header">
        <span>{item.evidence_id}</span>
      </div>
      <div className="observability-path-field-body">
        <div className="observability-inline-meta">
          <span>Status: {item.status}</span>
          <span>Exists: {String(item.exists)}</span>
          <span>Required: {String(item.required_for_summary)}</span>
        </div>
        <p className="mono observability-path-value">{path ?? "N/A"}</p>
        {path ? (
          <div className="observability-copy-row">
            <button
              className="secondary-button observability-copy-button"
              type="button"
              onClick={() => void onCopyPath(`integrity-${item.evidence_id}`, path)}
            >
              {`Copy ${item.evidence_id} path`}
            </button>
            {copyFeedback ? (
              <span
                role="status"
                aria-live="polite"
                className={`observability-copy-feedback ${
                  copyFeedback === "Copied" ? "observability-copy-feedback-success" : "observability-copy-feedback-error"
                }`}
              >
                {copyFeedback}
              </span>
            ) : null}
          </div>
        ) : (
          <p className="muted observability-path-empty">Path not available.</p>
        )}
      </div>
    </section>
  );
}

function ObservabilityResult({
  result,
  latestReleaseGateAliasPath,
  onCopyPath,
  copyFeedbackForKey,
}: {
  result: InternalObservabilityRunSummary;
  latestReleaseGateAliasPath: string | null;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedbackForKey: (copyKey: string) => string | null;
}) {
  const timing = result.workflow_timing_summary;
  const slowestStage = getSlowestStage(timing);
  const longestStageDuration = slowestStage?.total_duration_ms ?? 0;

  return (
    <div className="workspace observability-workspace">
      <section className="observability-review-section">
        <div className="section-heading">
          <h2>Trace Summary</h2>
        </div>
        <p className="muted reviewer-note">
          Reviewer-facing summary of run identity, trace identity, workflow timing, and observability status.
        </p>

        <div className="observability-summary-grid">
          <section className="panel">
            <div className="section-heading">
              <h3>Run Identity</h3>
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
              <MetaItem label="Created At" value={result.created_at} />
              <MetaItem label="Updated At" value={result.updated_at} />
            </dl>
          </section>

          <section className="panel">
            <div className="section-heading">
              <h3>Workflow Timing</h3>
            </div>
            {timing ? (
              <>
                <div className="observability-metric-grid observability-timing-grid">
                  <MetricCard label="Total Duration" value={`${timing.total_duration_ms} ms`} />
                  <MetricCard label="Stage Count" value={String(timing.stage_count)} />
                  <MetricCard
                    label="Slowest Stage"
                    value={slowestStage ? slowestStage.node_name : "N/A"}
                    detail={slowestStage ? `${slowestStage.total_duration_ms} ms` : null}
                    mono={slowestStage !== null}
                  />
                </div>

                <ol className="observability-stage-lane-list">
                  {timing.stages.map((stage) => (
                    <li key={stage.node_name} className="observability-stage-lane">
                      <div className="observability-stage-lane-header">
                        <strong className="mono">{stage.node_name}</strong>
                        <span>{stage.total_duration_ms} ms</span>
                      </div>
                      <div className="observability-stage-track" aria-hidden="true">
                        <span
                          className="observability-stage-fill"
                          style={{
                            width: `${getRelativeWidth(stage.total_duration_ms, longestStageDuration)}%`,
                          }}
                        />
                      </div>
                      <span className="muted">attempts: {stage.attempt_count}</span>
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <p className="muted">No workflow timing summary is available for this run yet.</p>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h3>Observability Status</h3>
            </div>
            <dl className="metadata-list observability-list">
              <MetaItem label="Tool Events" value={String(result.tool_event_count)} />
              <MetaItem label="Action Count" value={String(result.action_count)} />
              <MetaItem label="Execution Status" value={result.execution_status} />
              <MetaItem label="Feedback Status" value={result.feedback_status} />
              <MetaItem label="Observability Status" value={result.observability_status} />
              <MetaItem label="Trace ID" value={result.observability_summary.trace_id} mono />
              <MetaItem label="Recorder Status" value={result.observability_summary.status} />
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
        </div>
      </section>

      <div className="observability-secondary-grid">
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
      </div>

      <div className="observability-placeholder-grid">
        <ToolEventsPanel items={result.tool_event_summaries} />
        <ActionLedgerPanel items={result.action_ledger_summaries} />
        <BenchmarkArtifactsPanel
          summary={result.benchmark_artifact_summary}
          latestReleaseGateAliasPath={latestReleaseGateAliasPath}
          onCopyPath={onCopyPath}
          copyFeedbackForKey={copyFeedbackForKey}
        />
        <RecoveryPathPanel
          summary={result.recovery_path_summary}
          onCopyPath={onCopyPath}
          copyFeedback={copyFeedbackForKey("replay-report-path")}
        />
      </div>
    </div>
  );
}

function CountMapPanel({ title, items }: { title: string; items: Record<string, number> }) {
  const entries = Object.entries(items).sort(([left], [right]) => left.localeCompare(right));

  return (
    <section className="panel">
      <div className="section-heading">
        <h3>{title}</h3>
      </div>
      {entries.length ? (
        <ul className="observability-chip-list observability-chip-list-compact">
          {entries.map(([label, count]) => (
            <li key={`${title}-${label}`}>
              <span>{label}</span>
              <strong>{count}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No summary values are available.</p>
      )}
    </section>
  );
}

function BenchmarkArtifactsPanel({
  summary,
  latestReleaseGateAliasPath,
  onCopyPath,
  copyFeedbackForKey,
}: {
  summary: InternalBenchmarkArtifactSummary | null;
  latestReleaseGateAliasPath: string | null;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedbackForKey: (copyKey: string) => string | null;
}) {
  const hasDetailedArtifact =
    summary !== null &&
    (summary.benchmark_status !== null ||
      summary.overall_score !== null ||
      summary.workflow_status !== null ||
      summary.tool_event_count !== null ||
      summary.action_count !== null ||
      summary.report_path !== null ||
      summary.failure_reasons.length > 0 ||
      summary.score_summaries.length > 0);

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Benchmark Artifacts</h2>
      </div>
      {summary === null ? (
        <p className="muted">This run does not have benchmark artifact metadata.</p>
      ) : (
        <>
          <dl className="metadata-list observability-list">
            <MetaItem label="Case ID" value={summary.case_id} mono />
            <MetaItem label="Title" value={summary.title} />
            <MetaItem label="Workflow Backed" value={booleanLabel(summary.workflow_backed)} />
            <MetaItem label="Benchmark Status" value={summary.benchmark_status} />
            <MetaItem
              label="Overall Score"
              value={summary.overall_score === null ? null : String(summary.overall_score)}
            />
            <MetaItem label="Workflow Status" value={summary.workflow_status} />
            <MetaItem
              label="Tool Event Count"
              value={summary.tool_event_count === null ? null : String(summary.tool_event_count)}
            />
            <MetaItem
              label="Action Count"
              value={summary.action_count === null ? null : String(summary.action_count)}
            />
          </dl>

          <div className="observability-path-stack">
            <PathField
              label="Current Run Report"
              path={summary.report_path}
              copyLabel="Copy run report path"
              copyKey="current-run-report"
              onCopyPath={onCopyPath}
              copyFeedback={copyFeedbackForKey("current-run-report")}
            />
            <PathField
              label="Latest Release Gate Alias"
              path={latestReleaseGateAliasPath}
              copyLabel="Copy latest alias path"
              copyKey="latest-release-gate-alias-artifacts"
              onCopyPath={onCopyPath}
              copyFeedback={copyFeedbackForKey("latest-release-gate-alias-artifacts")}
            />
          </div>

          <section className="panel">
            <div className="section-heading">
              <h3>Registered Suites</h3>
            </div>
            {summary.registered_suite_ids.length ? (
              <ul className="observability-chip-list">
                {summary.registered_suite_ids.map((suiteId) => (
                  <li key={suiteId}>{suiteId}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No registered suite IDs matched this benchmark case.</p>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h3>Taxonomy</h3>
            </div>
            {summary.taxonomy ? (
              <>
                <dl className="metadata-list observability-list">
                  <MetaItem label="Suite" value={summary.taxonomy.suite} />
                  <MetaItem label="Scenario Bucket" value={summary.taxonomy.scenario_bucket} />
                  <MetaItem label="Level" value={summary.taxonomy.level} />
                  <MetaItem label="Failure Mode" value={summary.taxonomy.failure_mode} />
                </dl>
                {summary.taxonomy.tags.length ? (
                  <ul className="observability-chip-list">
                    {summary.taxonomy.tags.map((tag) => (
                      <li key={tag}>{tag}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <p className="muted">No benchmark taxonomy is available for this run.</p>
            )}
          </section>

          {hasDetailedArtifact ? (
            <>
              {summary.failure_reasons.length ? (
                <section className="panel">
                  <div className="section-heading">
                    <h3>Failure Reasons</h3>
                  </div>
                  <ul className="node-list">
                    {summary.failure_reasons.map((reason, index) => (
                      <li key={`${reason}-${index}`}>{reason}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {summary.score_summaries.length ? (
                <section className="panel">
                  <div className="section-heading">
                    <h3>Score Summaries</h3>
                  </div>
                  <ul className="observability-detail-list">
                    {summary.score_summaries.map((score, index) => (
                      <li key={`${score.name}-${index}`}>
                        <div className="observability-detail-header">
                          <strong>{score.name}</strong>
                          <span>{score.status}</span>
                        </div>
                        <dl className="metadata-list observability-list">
                          <MetaItem label="Score" value={String(score.score)} />
                          <MetaItem label="Reason" value={score.reason} />
                        </dl>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </>
          ) : (
            <p className="muted">Detailed benchmark scoring is not available for this run yet.</p>
          )}
        </>
      )}
    </section>
  );
}

function RecoveryPathPanel({
  summary,
  onCopyPath,
  copyFeedback,
}: {
  summary: InternalRecoveryPathSummary | null;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedback: string | null;
}) {
  const latestAttempt = getLatestRecoveryAttempt(summary);

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Recovery Visualization</h2>
      </div>
      {summary === null ? (
        <p className="muted">This run did not enter bounded recovery.</p>
      ) : (
        <>
          <div className="observability-metric-grid">
            <MetricCard label="Attempt Count" value={String(summary.attempt_count)} />
            <MetricCard label="Max Attempts" value={String(summary.max_attempts)} />
            <MetricCard
              label="Latest Attempt"
              value={latestAttempt ? latestAttempt.status : "N/A"}
              detail={latestAttempt ? latestAttempt.recovery_action : null}
            />
          </div>

          {summary.attempts.length ? (
            <section className="panel">
              <div className="section-heading">
                <h3>Attempts</h3>
              </div>
              <ol className="observability-detail-list">
                {summary.attempts
                  .slice()
                  .sort((left, right) => left.attempt_index - right.attempt_index)
                  .map((attempt) => (
                  <li key={`${attempt.attempt_index}-${attempt.recovery_action}-${attempt.status}`}>
                    <div className="observability-detail-header">
                      <div>
                        <p className="eyebrow observability-inline-eyebrow">Attempt {attempt.attempt_index}</p>
                        <strong>{attempt.recovery_action}</strong>
                      </div>
                      <StatusBadge status={attempt.status} />
                    </div>
                    <dl className="metadata-list observability-list">
                      <MetaItem label="Source Node" value={attempt.source_node} />
                      <MetaItem label="Route To" value={attempt.route_to} />
                      <MetaItem label="Error Type" value={attempt.error_type} />
                      <MetaItem label="Reason" value={attempt.reason} />
                      <MetaItem label="Retry Budget Before" value={String(attempt.retry_budget_before)} />
                      <MetaItem label="Retry Budget After" value={String(attempt.retry_budget_after)} />
                    </dl>
                  </li>
                ))}
              </ol>
            </section>
          ) : (
            <p className="muted">Recovery metadata exists for this run, but no valid recovery attempts are available.</p>
          )}

          {summary.replay_source ? (
            <section className="panel">
              <div className="section-heading">
                <h3>Replay Source</h3>
              </div>
              <dl className="metadata-list observability-list">
                <MetaItem label="Case ID" value={summary.replay_source.case_id} mono />
              </dl>
              <PathField
                label="Benchmark Report Path"
                path={summary.replay_source.benchmark_report_path}
                copyLabel="Copy replay report path"
                copyKey="replay-report-path"
                onCopyPath={onCopyPath}
                copyFeedback={copyFeedback}
              />
            </section>
          ) : null}
        </>
      )}
    </section>
  );
}

function ToolEventsPanel({ items }: { items: InternalToolEventSummary[] }) {
  const rollup = getToolEventRollup(items);

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Tool Events</h2>
      </div>
      {items.length ? (
        <>
          <div className="observability-metric-grid observability-tool-rollup-grid">
            <MetricCard label="Total Events" value={String(rollup.totalCount)} />
            <MetricCard label="Read Events" value={String(rollup.readCount)} />
            <MetricCard label="Write Events" value={String(rollup.writeCount)} />
            <MetricCard label="Providers" value={String(Object.keys(rollup.providerCounts).length)} />
          </div>

          <div className="observability-rollup-grid">
            <CompactCountList title="By Status" items={rollup.statusCounts} />
            <CompactCountList title="By Type" items={rollup.typeCounts} />
            <CompactCountList title="By Provider" items={rollup.providerCounts} />
          </div>

          <ul className="observability-detail-list">
          {items.map((item, index) => (
            <li key={`${item.tool_name}-${item.created_at}-${index}`}>
              <div className="observability-detail-header">
                <div>
                  <strong>{item.tool_name}</strong>
                  <div className="observability-inline-meta">
                    <span>{item.tool_type}</span>
                    <span>{item.provider}</span>
                    <span>{item.latency_ms === null ? "Latency N/A" : `${item.latency_ms} ms`}</span>
                  </div>
                </div>
                <StatusBadge status={item.status} />
              </div>
              <dl className="metadata-list observability-list">
                <MetaItem label="Cache Hit" value={booleanLabel(item.cache_hit)} />
                <MetaItem label="Created At" value={item.created_at} />
              </dl>
              <div className="observability-preview-grid">
                <PreviewField label="Request Preview" value={stringifyValue(item.request_preview)} />
                <PreviewField label="Response Preview" value={stringifyValue(item.response_preview)} />
                <PreviewField label="Error Preview" value={stringifyValue(item.error_preview)} />
              </div>
            </li>
          ))}
          </ul>
        </>
      ) : (
        <p className="muted">No tool events were recorded for this run.</p>
      )}
    </section>
  );
}

function ActionLedgerPanel({ items }: { items: InternalActionLedgerSummary[] }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Action Ledger</h2>
      </div>
      {items.length ? (
        <ul className="observability-detail-list">
          {items.map((item, index) => (
            <li key={`${item.action_type}-${item.target_id}-${item.created_at}-${index}`}>
              <div className="observability-detail-header">
                <strong>{item.action_type}</strong>
                <span>{item.status}</span>
              </div>
              <dl className="metadata-list observability-list">
                <MetaItem label="Target" value={item.target_id} />
                <MetaItem label="Created At" value={item.created_at} />
                <MetaItem label="Updated At" value={item.updated_at} />
                <MetaItem label="Request Preview" value={stringifyValue(item.request_preview)} />
                <MetaItem label="Response Preview" value={stringifyValue(item.response_preview)} />
                <MetaItem label="Error Preview" value={stringifyValue(item.error_preview)} />
              </dl>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No action ledger entries were recorded for this run.</p>
      )}
    </section>
  );
}

function MetricCard({
  label,
  value,
  detail,
  mono = false,
}: {
  label: string;
  value: string;
  detail?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="observability-metric-card">
      <span>{label}</span>
      <strong className={mono ? "mono" : undefined}>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function PathField({
  label,
  path,
  copyLabel,
  copyKey,
  onCopyPath,
  copyFeedback,
}: {
  label: string;
  path: string | null;
  copyLabel: string;
  copyKey: string;
  onCopyPath: (copyKey: string, path: string) => Promise<void>;
  copyFeedback: string | null;
}) {
  const hasPath = hasTextValue(path);

  return (
    <section className="observability-path-field">
      <div className="observability-path-field-header">
        <span>{label}</span>
      </div>
      <div className="observability-path-field-body">
        <p className="mono observability-path-value">{hasPath ? path : "N/A"}</p>
        {hasPath ? (
          <div className="observability-copy-row">
            <button
              className="secondary-button observability-copy-button"
              type="button"
              onClick={() => void onCopyPath(copyKey, path)}
            >
              {copyLabel}
            </button>
            {copyFeedback ? (
              <span
                role="status"
                aria-live="polite"
                className={`observability-copy-feedback ${
                  copyFeedback === "Copied" ? "observability-copy-feedback-success" : "observability-copy-feedback-error"
                }`}
              >
                {copyFeedback}
              </span>
            ) : null}
          </div>
        ) : (
          <p className="muted observability-path-empty">Path not available.</p>
        )}
      </div>
    </section>
  );
}

function PreviewField({ label, value }: { label: string; value: string | null }) {
  if (!hasTextValue(value)) {
    return null;
  }

  return (
    <section className="observability-preview-card">
      <span>{label}</span>
      <p className="mono">{value}</p>
    </section>
  );
}

function CompactCountList({ title, items }: { title: string; items: Record<string, number> }) {
  const entries = Object.entries(items).sort(([left], [right]) => left.localeCompare(right));

  return (
    <section className="observability-rollup-card">
      <div className="section-heading">
        <h3>{title}</h3>
      </div>
      {entries.length ? (
        <ul className="observability-chip-list observability-chip-list-compact">
          {entries.map(([label, count]) => (
            <li key={`${title}-${label}`}>
              <span>{label}</span>
              <strong>{count}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No summary values are available.</p>
      )}
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

function formatDurationMs(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "N/A";
  }
  return `${value} ms`;
}

function getSlowestStage(timing: InternalWorkflowTimingSummary | null) {
  if (timing === null || timing.stages.length === 0) {
    return null;
  }

  return timing.stages.reduce((slowest, candidate) =>
    candidate.total_duration_ms > slowest.total_duration_ms ? candidate : slowest,
  );
}

function getRelativeWidth(stageDurationMs: number, maxDurationMs: number) {
  if (maxDurationMs <= 0) {
    return 0;
  }

  return Math.max(12, Math.round((stageDurationMs / maxDurationMs) * 100));
}

function getToolEventRollup(items: InternalToolEventSummary[]) {
  const typeCounts: Record<string, number> = {};
  const statusCounts: Record<string, number> = {};
  const providerCounts: Record<string, number> = {};

  let readCount = 0;
  let writeCount = 0;

  for (const item of items) {
    typeCounts[item.tool_type] = (typeCounts[item.tool_type] ?? 0) + 1;
    statusCounts[item.status] = (statusCounts[item.status] ?? 0) + 1;
    providerCounts[item.provider] = (providerCounts[item.provider] ?? 0) + 1;

    if (item.tool_type === "read") {
      readCount += 1;
    } else {
      writeCount += 1;
    }
  }

  return {
    totalCount: items.length,
    readCount,
    writeCount,
    typeCounts,
    statusCounts,
    providerCounts,
  };
}

function getLatestRecoveryAttempt(summary: InternalRecoveryPathSummary | null) {
  if (summary === null || summary.attempts.length === 0) {
    return null;
  }

  return summary.attempts.reduce((latest, candidate) =>
    candidate.attempt_index > latest.attempt_index ? candidate : latest,
  );
}

function formatScore(score: number) {
  if (Number.isInteger(score)) {
    return score.toFixed(0);
  }

  return score.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

function stringifyMetric(value: number | null) {
  return value === null ? null : formatScore(value);
}

function stringOrNA(value: number | null) {
  return value === null ? "N/A" : String(value);
}

function hasTextValue(value: string | null | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function StatusBadge({ status }: { status: string | null }) {
  const label = hasTextValue(status) ? status : "N/A";
  const className = `status-badge ${getStatusClassName(label)}`.trim();

  return <span className={className}>{label}</span>;
}

function getStatusClassName(status: string) {
  return `status-${status.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;
}
