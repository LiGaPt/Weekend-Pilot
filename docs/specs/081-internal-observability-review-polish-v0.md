# Spec: 081 Internal Observability Review Polish v0

## 1. Goal

Finish the reviewer-first polish of the internal observability surface at `http://127.0.0.1:5174/`.

The backend already exposes the required evidence: the latest `release_gate_v1` summary, workflow timing, tool-event summaries, benchmark artifact summaries, and recovery-path summaries. The remaining gap is frontend readability and reviewer ergonomics. After this task, a judge should be able to open the internal page, scan release readiness first, copy canonical report paths directly, and then inspect trace, benchmark-artifact, and recovery evidence without switching to raw JSON or backend routes.

This task is a closure task for the current in-progress `081` branch. It is not yet the consolidated submission demo script / Reviewer Guide task. That docs-only consolidation should happen after this UI behavior is stable.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default, with internal observability separated from the customer-safe demo experience. `docs/NEXT_PHASE_ROADMAP.md` says the current phase should prioritize `M1. 评测与观测基础设施` before broader UX expansion.

This task fits that milestone directly:

- it improves consumption of existing benchmark and recovery evidence
- it keeps the customer/internal boundary intact
- it does not add new product capability or backend observability infrastructure
- it prepares the repo for a later submission-facing reviewer guide by making the internal reviewer surface stable enough to cite

Relevant prior tasks already established the underlying capability chain:

- `034` internal observability API and page skeleton
- `037` tool-event and action-ledger panels
- `041` benchmark artifact panels
- `042` recovery-path visualization
- `068` richer Web UI V1 reviewer flow
- `080` customer demo E2E regression coverage

## 3. Requirements

- Keep `GET /internal/runs/{run_id}/observability` unchanged.
- Keep `GET /internal/benchmarks/release-gate-v1/summary` unchanged.
- Do not add new backend response fields, new database rows, or new persisted metadata.
- Complete the current `081` frontend work on branch `codex/internal-observability-review-polish-v0` instead of opening a new feature slice.
- The internal page must visually prioritize the latest release-gate evidence before any run ID is loaded.
- The top benchmark section must prominently show the suite title.
- The top benchmark section must prominently show the run status.
- The top benchmark section must prominently show the overall score.
- The top benchmark section must prominently show passed, failed, and error counts.
- The top benchmark section must prominently show the canonical latest alias path from `summary.report_path`.
- The top benchmark section must provide a one-click copy action for `summary.report_path`.
- The copy action must show brief inline success or failure feedback without reloading the page.
- The trace summary must derive reviewer-facing timing summaries from the existing `workflow_timing_summary` only.
- The trace summary must show total duration clearly.
- The trace summary must show stage count clearly.
- The trace summary must show the slowest stage clearly.
- The trace summary must render an ordered per-stage lane or bar list that preserves backend stage order.
- The tool-events section must stay based only on `tool_event_summaries`.
- The tool-events section must show reviewer-facing rollups such as total count, read/write split, and status/type/provider counts.
- The tool-events section must keep per-event detail in sanitized cards or rows.
- The benchmark-artifacts section must stay based only on `benchmark_artifact_summary`.
- The benchmark-artifacts section must clearly distinguish the current run report path from the canonical latest release-gate alias path.
- The benchmark-artifacts section must provide a one-click copy action for the current run report path when that path exists.
- The benchmark-artifacts section must provide a one-click copy action for the canonical latest release-gate alias path already loaded on the page when that path exists.
- The recovery section must stay based only on `recovery_path_summary`.
- The recovery section must show attempt count clearly.
- The recovery section must show max attempts clearly.
- The recovery section must show the latest attempt status clearly.
- The recovery section must render numbered attempts in sequence.
- The recovery section must show the replay-source path clearly when it exists.
- The recovery section must provide a one-click copy action for the replay-source path when it exists.
- Missing or null paths must stay neutral and must not render dead copy controls.
- The page must remain responsive on the existing desktop and mobile browser baselines.
- The customer surface at `5173` must remain unchanged.
- Public demo API contracts must remain unchanged.
- Benchmark rules, release-gate thresholds, replay behavior, and persistence logic must remain unchanged.
- Update `docs/WEB_DEMO_README.md` so the internal reviewer flow mentions the release-gate hero, copy-path actions, and the intended reviewer scan order.
- Update frontend tests for the refined hierarchy and copy actions without adding new dependencies or backend test-only hooks.

## 4. Non-goals

- Do not add a new top-level Reviewer Guide or submission demo script in this task.
- Do not add new internal endpoints.
- Do not add new database tables, migrations, or persisted metadata.
- Do not add benchmark rerun controls, replay controls, or a file browser.
- Do not expose raw report JSON bodies through the frontend.
- Do not redesign the customer page at `5173`.
- Do not change benchmark grading, suite membership, or release-gate logic.
- Do not widen this task into a generic Vite, Vitest, or Playwright infrastructure refactor.
- Do not commit `.env`, API keys, tokens, secrets, generated `dist/` outputs, or runtime artifacts.

## 5. Interfaces and Contracts

### Inputs

- `GET /internal/benchmarks/release-gate-v1/summary`
- `GET /internal/runs/{run_id}/observability`
- `InternalReleaseGateBenchmarkSummary`
- `InternalObservabilityRunSummary`
- `InternalBenchmarkArtifactSummary`
- `InternalRecoveryPathSummary`
- Existing `report_path` values already exposed by those contracts

### Outputs

- An updated internal review page at `http://127.0.0.1:5174/`
- No backend schema changes
- Updated reviewer documentation in `docs/WEB_DEMO_README.md`
- Updated frontend unit and browser tests

### Schemas

This task does not change backend schemas. It introduces only frontend-local derived view state. A representative derived shape is:

```json
{
  "latest_release_gate_alias": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
  "current_run_report_path": "var/benchmarks/solo_afternoon_v1.json",
  "replay_report_path": "var/benchmarks/family_route_failure_v1.json",
  "slowest_stage": {
    "node_name": "execute_searches",
    "total_duration_ms": 37
  },
  "tool_event_rollup": {
    "total_count": 4,
    "read_count": 3,
    "write_count": 1
  }
}
```

The derived state must be computed entirely from already-loaded frontend data and must not require new API fields.

## 6. Observability

This task does not add new telemetry, new persistence, new LangSmith behavior, or new benchmark generation.

It only changes how existing internal observability data is presented on the frontend. Copy-to-clipboard feedback is ephemeral UI state only and must not be persisted anywhere. Existing internal endpoints remain the source of truth for all displayed values.

## 7. Failure Handling

- If the latest release-gate summary is missing, keep the existing reviewer-readable missing state.
- If the latest release-gate summary request fails, keep the existing reviewer-readable error state.
- If `workflow_timing_summary` is null, keep a neutral timing state.
- If `benchmark_artifact_summary` is null, keep a neutral benchmark-artifact state.
- If `benchmark_artifact_summary` is partial, render the available identity fields and keep the detailed-score section neutral.
- If `recovery_path_summary` is null, keep a neutral recovery state.
- If recovery metadata exists but attempts are empty, render a reviewer-readable partial state.
- If a visible report path is null, omit the related copy control.
- If `navigator.clipboard.writeText` fails or is unavailable, show a non-blocking inline failure message.
- A failure in one panel must not block the rest of the already-loaded page from rendering.

## 8. Acceptance Criteria

- [ ] The current `081` frontend slice is completed without adding backend contract changes.
- [ ] The internal page visually prioritizes the latest release-gate summary before any run ID is loaded.
- [ ] The top benchmark section prominently shows status, overall score, counts, and the canonical latest alias path.
- [ ] The top benchmark section provides a one-click copy action for the canonical latest alias path.
- [ ] The trace summary clearly surfaces total duration, stage count, slowest stage, and an ordered stage-duration view without changing backend timing data.
- [ ] The tool-events section is more reviewer-readable and still uses only existing sanitized tool-event summary data.
- [ ] The benchmark-artifacts section clearly distinguishes the current run report path from the canonical latest alias path.
- [ ] The recovery section is more reviewer-readable and still uses only existing sanitized recovery summary data.
- [ ] Any visible report path copy action degrades gracefully when copying is unavailable or fails.
- [ ] `docs/WEB_DEMO_README.md` documents the refined internal review scan order and copy-path actions.
- [ ] `npm --prefix frontend run build` passes.
- [ ] `npm --prefix frontend run test -- --run src/observability/ObservabilityPage.test.tsx` passes.
- [ ] `npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"` passes.
- [ ] No public API shape, internal API shape, benchmark logic, replay logic, or customer-surface behavior changes in this task.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
npm --prefix frontend run build
npm --prefix frontend run test -- --run src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
feat: polish internal observability review surface
```

## 11. Notes for the Implementer

The working tree already contains in-progress `081` edits on branch `codex/internal-observability-review-polish-v0`. Treat those edits as the starting point for this task, not as unrelated changes.

Current repository facts that matter for execution:

- `docs/specs` and `docs/plans` are continuous and slug-matched through `081` in the working tree.
- The latest committed task is still `080`, with latest commit `b80bce2 test: expand customer demo e2e regression coverage`.
- `npm --prefix frontend run build` currently passes on the in-progress `081` branch.
- `npm --prefix frontend run test -- --run src/observability/ObservabilityPage.test.tsx` currently fails because `getByText("execute_searches")` now matches both the slowest-stage summary and the ordered stage lane.

Finish and verify `081` before opening a new docs-only task such as a fixed demo script / Reviewer Guide consolidation. If the implementation starts needing new backend fields, new internal routes, or a generic file browser, stop and split that into a separate task.
