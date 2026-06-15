# Spec: 103 System Integrity Panel v0

## 1. Goal

Add a reviewer-facing `System Integrity Summary` panel to the internal observability page at `http://127.0.0.1:5174/` by consuming the existing backend endpoint `GET /internal/system/integrity-summary`.

WeekendPilot already has the backend evidence aggregation from Task `102`, but reviewers still have to inspect the raw API response or stitch evidence paths together manually. After this task, the internal review page should surface the current V2 integrity posture directly in the UI: `v2_integrity` status, `Pass@k`, memory-governance status, recovery replay status, and the latest evidence paths. The result should be a smaller reviewer loop: open `5174`, scan integrity readiness, copy evidence paths if needed, then load a specific `run_id` only when trace-level inspection is required.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

It is the smallest direct continuation of Task `102`:

- Task `102` added `GET /internal/system/integrity-summary`.
- The current branch and latest commit already correspond to Task `102`:
  - branch: `codex/102-system-integrity-summary-api-v0`
  - latest commit: `4eba547 feat: add system integrity summary api`
- `docs/specs/` and `docs/plans/` are continuous and slug-matched from `001` through `102`.
- There is no tracked Task `103` spec or plan yet.
- The internal page at `5174` already shows:
  - `Benchmark Summary`
  - `Load Run`
  - `Trace Summary`
  - `Benchmark Artifacts`
  - `Recovery Visualization`

That means the repository does not need a new backend evidence task first. It needs the smallest frontend convergence task that makes the new integrity summary reviewer-visible.

This task fits these `docs/PROJECT_BLUEPRINT.md` areas:

- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- failure handling and recovery auditability
- memory-governance auditability
- small, reviewable tasks

This task must stay narrower than roadmap item `M2. 前端分离`. It should improve the existing internal page, not redesign the customer/internal frontend split.

## 3. Requirements

- Consume the existing internal-only backend route:

  ```text
  GET /internal/system/integrity-summary
  ```

- Do not add, remove, or rename backend fields on that route in this task.
- Add frontend-local typed models for the system-integrity summary contract in the internal observability client layer.
- Load the system-integrity summary automatically when `http://127.0.0.1:5174/` opens, without requiring a `run_id`.
- Keep the existing `Benchmark Summary` request and `Load Run` request flow independent from the new integrity request.
- A failure in the integrity request must not block:
  - the release-gate hero from loading
  - the run-specific `Load Run` flow
  - any already-loaded panel from rendering

### A. Panel placement and hierarchy

- Add a new panel titled `System Integrity Summary` to the existing internal observability page.
- The panel must be visible before any `run_id` is loaded.
- The panel must live in the same reviewer-first surface as the existing `Benchmark Summary`.
- The page hierarchy must keep reviewer scan order as:
  1. `Benchmark Summary`
  2. `System Integrity Summary`
  3. `Load Run`
  4. run-specific trace / artifact / recovery panels
- The task may reuse the existing `observability-grid` and panel styling patterns rather than creating a new page shell.

### B. Mandatory displayed content

The `System Integrity Summary` panel must display at minimum:

- `v2_integrity` benchmark/gate status
- `Pass@k` stability metrics
- memory-governance status
- recovery replay status
- latest evidence paths

The panel must use the Task `102` response instead of reconstructing these values client-side from raw files or separate routes.

### C. V2 integrity status display

- The panel must render the top-level integrity summary `status`.
- The panel must render the benchmark gate run status from `benchmark_summary.run_status`.
- The panel must render `release_blocked`.
- The panel must render `overall_score` when available.
- The panel must render `case_count`, `passed_count`, `failed_count`, and `error_count` when available.
- The panel must surface `benchmark_summary.reason` when the benchmark section is `missing`, `invalid`, or `partial`.
- The panel may render `blocking_failures` and coverage/count maps as additive reviewer detail only if it stays compact.

### D. Pass@k display

- The panel must render a dedicated `Pass@k` subsection.
- The subsection must show, when available:
  - `success_at_1`
  - `pass_at_4`
  - `pass_pow_4`
  - `executed_run_count`
  - `window_size`
  - `window_count`
- The subsection must show `stability_summary.status`.
- The subsection must show `stability_summary.reason` when the stability section is degraded.
- The UI must not invent fallback values when metrics are missing.
- Missing metrics must render as a neutral reviewer-readable state such as `N/A`.

### E. Memory-governance display

- The panel must render a dedicated memory-governance subsection.
- The subsection must show:
  - `memory_governance_summary.status`
  - `all_memory_cases_passed`
  - `memory_case_count`
  - `passed_case_count`
  - `failed_case_count`
  - `error_case_count`
- If `failing_case_ids` is non-empty, the panel must render those IDs explicitly.
- If the memory-governance section is degraded, the panel must render `memory_governance_summary.reason`.

### F. Recovery replay display

- The panel must render a dedicated recovery replay subsection.
- The subsection must show:
  - `recovery_replay_summary.status`
  - `review_status`
  - `check_count`
  - `passed_check_count`
  - `failed_check_count`
  - `attempt_count`
  - `max_attempts`
- If `recovery_actions` is non-empty, the panel must render them.
- If the recovery section is degraded, the panel must render `recovery_replay_summary.reason`.

### G. Evidence path display

- The panel must render the `evidence_paths` returned by the Task `102` summary.
- Evidence paths must stay repository-relative strings only.
- Each rendered evidence-path row must show:
  - `evidence_id`
  - `path`
  - `exists`
  - `required_for_summary`
  - `status`
- Required evidence should appear before optional evidence.
- Within the same requirement class, rows must render in deterministic order by `evidence_id`.
- A visible path must provide a copy action.
- A missing or empty path must not render a dead copy button.
- Copy feedback must be inline, non-blocking, and reset automatically using the existing clipboard-feedback pattern.

### H. Loading, degraded, and error states

- Before the integrity request resolves, the panel must show a reviewer-readable loading state.
- If the request fails at the HTTP or network level, the panel must show an error banner scoped to the integrity panel only.
- If the backend returns `200` with top-level `status` of:
  - `ready`
  - `degraded`
  - `missing_evidence`
  - `invalid_evidence`

  the page must render the payload normally and reflect the returned status in the UI.
- The frontend must not treat `degraded`, `missing_evidence`, or `invalid_evidence` as transport failures.
- If `evidence_paths` is empty, the panel must show a neutral reviewer-readable empty state.

### I. Existing surface compatibility

- Keep `GET /internal/benchmarks/release-gate-v1/summary` unchanged.
- Keep `GET /internal/runs/{run_id}/observability` unchanged.
- Keep the customer-facing page at `http://127.0.0.1:5173/` unchanged.
- Keep the existing internal trace/artifact/recovery run-loading flow unchanged.
- Do not add a router dependency, new frontend app, or new deployable.
- Do not add new backend routes, database tables, Alembic migrations, or package dependencies.

### J. Documentation

- Update `README.md` so the `5174` internal review surface description includes `System Integrity Summary`.
- Update `docs/WEB_DEMO_README.md` so the reviewer flow mentions:
  - the new system-integrity panel
  - when to scan it
  - that evidence paths can be copied directly from the page
- The documentation update must stay reviewer-focused and must not widen into a general architecture rewrite.

## 4. Non-goals

- Do not modify the backend summary contract from Task `102`.
- Do not add benchmark rerun controls, replay rerun controls, or an artifact file browser.
- Do not surface the full `timing_summary` or `redaction_summary` unless needed for compact reviewer clarity.
- Do not redesign the existing `Benchmark Summary` hero beyond minimal layout adjustments needed to fit the new panel.
- Do not change `5173` customer UI copy, layout, or API usage.
- Do not split customer and internal frontends into separate applications or repositories.
- Do not add authentication, RBAC, admin login, or internal-user management.
- Do not add new dependencies, new routes, new migrations, or new persisted metadata.
- Do not commit `.env`, API keys, tokens, secrets, generated artifacts, or unrelated untracked files.

## 5. Interfaces and Contracts

### Inputs

This task depends on existing frontend and backend contracts:

- `GET /internal/system/integrity-summary`
- `GET /internal/benchmarks/release-gate-v1/summary`
- `GET /internal/runs/{run_id}/observability`
- Task `102` backend response model `SystemIntegritySummary`
- existing frontend clipboard-feedback interaction
- existing internal observability status-badge pattern

### Outputs

Updated internal frontend surface:

```text
http://127.0.0.1:5174/
```

Additive frontend-local API function:

```text
getSystemIntegritySummary()
```

Additive frontend-local types for the Task `102` response model.

### Schemas

Representative consumed payload shape:

```json
{
  "schema_version": "weekendpilot_system_integrity_summary_v1",
  "status": "ready",
  "benchmark_summary": {
    "status": "ready",
    "suite_id": "v2_integrity",
    "gate_id": "v2_integrity_gate",
    "run_status": "passed",
    "release_blocked": false,
    "case_count": 18,
    "passed_count": 18,
    "failed_count": 0,
    "error_count": 0,
    "overall_score": 1.0,
    "latest_report_path": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json"
  },
  "stability_summary": {
    "status": "ready",
    "executed_run_count": 4,
    "window_size": 4,
    "window_count": 1,
    "success_at_1": 1.0,
    "pass_at_4": 1.0,
    "pass_pow_4": 1.0,
    "latest_report_path": "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json"
  },
  "memory_governance_summary": {
    "status": "ready",
    "memory_case_count": 6,
    "passed_case_count": 6,
    "failed_case_count": 0,
    "error_case_count": 0,
    "all_memory_cases_passed": true,
    "failing_case_ids": [],
    "latest_report_path": "var/formal-benchmarks/latest-all_registered-run-report.json"
  },
  "recovery_replay_summary": {
    "status": "ready",
    "review_status": "passed",
    "check_count": 3,
    "passed_check_count": 3,
    "failed_check_count": 0,
    "attempt_count": 1,
    "max_attempts": 2,
    "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
  },
  "evidence_paths": [
    {
      "evidence_id": "v2_integrity_gate",
      "path": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
      "exists": true,
      "required_for_summary": true,
      "status": "ready"
    }
  ]
}
```

Representative frontend-local derived display state:

```json
{
  "headline_status": "ready",
  "benchmark_gate_label": "passed",
  "passk_primary_metric": "Pass@4 = 1.0",
  "memory_state": "all passed",
  "recovery_state": "review passed",
  "path_count": 6
}
```

Notes:

- This task does not change backend schemas.
- Derived display state must be computed only from already-returned backend fields.
- The panel may remain fully additive inside the existing page.

## 6. Observability

This task does not add new telemetry, persistence, LangSmith behavior, benchmark recording, or replay recording.

It only changes how existing internal evidence is consumed and presented on the frontend. The panel must remain bounded to already-sanitized backend output and must not reconstruct data from local files, browser storage, or ad hoc debug endpoints.

Clipboard success or failure is ephemeral UI state only and must not be persisted anywhere.

## 7. Failure Handling

- If the integrity endpoint request fails due to network or backend transport error:
  - show a panel-local error banner
  - keep the rest of the page usable
- If the integrity endpoint returns top-level `status = "degraded"`:
  - render the panel
  - show the degraded status badge
  - surface section-level reasons when present
- If one section is `missing`, `invalid`, or `partial`:
  - render available data from other sections
  - show `N/A` or neutral text for unavailable fields
  - do not hide the whole panel
- If `evidence_paths` contains rows with `exists = false`:
  - show their status and path
  - do not render copy controls for empty paths
- If copying a path fails:
  - show inline non-blocking `Copy failed`
  - keep the panel interactive
- If the panel has no usable evidence-path rows:
  - show a neutral message instead of crashing or leaving an empty container
- This task does not need polling, retry loops, or live refresh.

## 8. Acceptance Criteria

- [ ] `docs/specs/103-system-integrity-panel-v0.md` exists and matches this task.
- [ ] `docs/plans/103-system-integrity-panel-v0-plan.md` exists and matches this task.
- [ ] The internal page at `http://127.0.0.1:5174/` loads `GET /internal/system/integrity-summary` automatically on page load.
- [ ] The page renders a new `System Integrity Summary` panel before any `run_id` is loaded.
- [ ] The panel displays the current `v2_integrity` status from the Task `102` API.
- [ ] The panel displays `Pass@k` metrics from the Task `102` API.
- [ ] The panel displays memory-governance status from the Task `102` API.
- [ ] The panel displays recovery replay status from the Task `102` API.
- [ ] The panel displays the latest evidence paths from the Task `102` API.
- [ ] Visible evidence paths expose copy actions and inline copy feedback.
- [ ] Degraded or partial backend payloads render as reviewer-readable panel states instead of transport errors.
- [ ] A transport failure in the integrity request does not block the existing release-gate hero or `Load Run` flow.
- [ ] Existing `Benchmark Summary`, `Load Run`, `Trace Summary`, `Benchmark Artifacts`, and `Recovery Visualization` flows remain functional.
- [ ] The customer-facing `5173` page remains unchanged.
- [ ] `README.md` mentions the new `System Integrity Summary` panel on `5174`.
- [ ] `docs/WEB_DEMO_README.md` documents the reviewer scan order including `System Integrity Summary`.
- [ ] Focused frontend tests cover:
  - API client route call
  - ready integrity state
  - degraded integrity state
  - integrity request error state
  - evidence-path copy action
- [ ] Internal desktop browser smoke covers the new panel on `5174`.
- [ ] `npm --prefix frontend run build` passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except unrelated pre-existing untracked local files.

## 9. Verification Commands

```bash
npm --prefix frontend run test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
feat: add system integrity review panel
```

## 11. Notes for the Implementer

Keep this task frontend-only and explicitly stacked on Task `102`.

Preferred implementation shape:

1. add frontend-local types for the Task `102` contract
2. add one internal API client function
3. load the integrity summary on page mount independently from the release-gate summary
4. render one compact reviewer-facing panel with subsections for:
   - benchmark integrity
   - `Pass@k`
   - memory governance
   - recovery replay
   - evidence paths
5. reuse the existing copy-path and status-badge interaction patterns
6. update reviewer docs after the UI is stable

The implementer should stop and report back if:

- the Task `102` backend contract no longer matches the committed frontend assumptions
- the new panel would require backend field changes to be reviewer-useful
- the work starts pulling in a broader frontend split, router migration, or artifact-browser scope
