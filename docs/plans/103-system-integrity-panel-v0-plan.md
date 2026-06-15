# Plan: 103 System Integrity Panel v0

## 1. Spec Reference

Spec file:

```text
docs/specs/103-system-integrity-panel-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/102-system-integrity-summary-api-v0`.
- Latest commit is `4eba547 feat: add system integrity summary api`.
- `docs/specs/` and `docs/plans/` are continuous and slug-matched from `001` through `102`.
- Task `102` already added the backend route `GET /internal/system/integrity-summary`.
- Task `102` already added backend summary types in `backend/app/observability/schemas.py`.
- The internal page at `5174` already fetches:
  - `GET /internal/benchmarks/release-gate-v1/summary`
  - `GET /internal/runs/{run_id}/observability`
- The internal page does not yet fetch or render the system-integrity summary.
- `frontend/e2e/internal-observability.spec.ts` currently stubs the existing release-gate and run-observability routes only.
- `README.md` currently describes the `5174` page as showing `Benchmark Summary`, `Trace Summary`, `Benchmark Artifacts`, and `Recovery Visualization`, so it will need a reviewer-facing update for the new integrity panel.
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/src/observability/types.ts` - add frontend-local system-integrity summary types that mirror the Task `102` backend contract.
- `frontend/src/observability/api.ts` - add `getSystemIntegritySummary()` and localized request/error handling for the new route.
- `frontend/src/observability/api.test.ts` - verify the new API client hits `/internal/system/integrity-summary` and preserves existing error mapping behavior.
- `frontend/src/observability/ObservabilityPage.tsx` - load the new summary on page mount, render the `System Integrity Summary` panel, and wire evidence-path copy controls.
- `frontend/src/observability/ObservabilityPage.test.tsx` - add ready/degraded/error/evidence-copy assertions for the new panel while preserving existing run-summary checks.
- `frontend/e2e/internal-observability.spec.ts` - stub the integrity endpoint and assert the new panel appears on `5174`.
- `frontend/src/styles.css` - add or extend panel layout styles for the new system-integrity hero and evidence-path rows.
- `README.md` - update the `5174` summary so it includes `System Integrity Summary`.
- `docs/WEB_DEMO_README.md` - update the internal reviewer flow and scan order to include the integrity panel and evidence-path copy actions.

## 5. Implementation Steps

1. Create and switch to a new task branch from the current `102` HEAD:

   ```bash
   git switch -c codex/103-system-integrity-panel-v0
   ```

2. Read the committed Task `102` contract in:
   - `docs/specs/102-system-integrity-summary-api-v0.md`
   - `backend/app/observability/schemas.py`

3. Read the current internal observability frontend implementation in:
   - `frontend/src/observability/types.ts`
   - `frontend/src/observability/api.ts`
   - `frontend/src/observability/ObservabilityPage.tsx`
   - `frontend/src/observability/ObservabilityPage.test.tsx`
   - `frontend/e2e/internal-observability.spec.ts`

4. Extend `frontend/src/observability/types.ts` with additive system-integrity types:
   - top-level `SystemIntegritySummary`
   - section models for benchmark, stability, memory governance, recovery replay, redaction, timing, and evidence paths
   - literal status unions for section status and top-level summary status
   - keep all fields optional/null-friendly where the backend can degrade

5. Update `frontend/src/observability/api.ts`:
   - add `getSystemIntegritySummary(): Promise<SystemIntegritySummary>`
   - keep the same `request<T>()` helper pattern
   - add localized error mapping only if the endpoint introduces a stable reviewer-facing message worth preserving
   - otherwise let generic internal-request fallback messaging handle non-200 errors

6. Update `frontend/src/observability/api.test.ts`:
   - add a new mocked payload for the integrity summary
   - assert `getSystemIntegritySummary()` calls `http://127.0.0.1:8000/internal/system/integrity-summary`
   - keep the existing `getObservabilityRun()` tests unchanged

7. In `frontend/src/observability/ObservabilityPage.tsx`, add new page-level state:
   - `systemIntegritySummary`
   - `systemIntegrityErrorMessage`
   - `isSystemIntegrityLoading`

8. Add a dedicated page-load effect for reviewer summaries that fetches:
   - latest release-gate summary
   - latest system-integrity summary
   as independent requests so one failure does not mask the other

9. Keep `Load Run` logic unchanged and independent from the new integrity request.

10. Add a new `SystemIntegritySummaryPanel` component inside `ObservabilityPage.tsx`.
11. Place the new panel in the top `observability-grid` so it renders before any `run_id` is loaded and before run-specific panels.
12. In `SystemIntegritySummaryPanel`, render a compact headline section with:
   - title `System Integrity Summary`
   - top-level summary status badge
   - `v2_integrity` run status badge
   - `release_blocked`
   - `overall_score`
   - benchmark case/pass/fail/error counts when available

13. Add a dedicated `Pass@k` subsection that renders:
   - `success_at_1`
   - `pass_at_4`
   - `pass_pow_4`
   - `executed_run_count`
   - `window_size`
   - `window_count`
   - section `status` and `reason`

14. Add a dedicated memory-governance subsection that renders:
   - section `status`
   - `all_memory_cases_passed`
   - case/pass/fail/error counts
   - `failing_case_ids` when present
   - `reason` when degraded

15. Add a dedicated recovery replay subsection that renders:
   - section `status`
   - `review_status`
   - check counts
   - `attempt_count`
   - `max_attempts`
   - `recovery_actions` when present
   - `reason` when degraded

16. Add an evidence-path subsection that:
   - sorts `evidence_paths` with required paths first, then by `evidence_id`
   - renders each path row with:
     - `evidence_id`
     - `status`
     - `exists`
     - `required_for_summary`
     - `path`
   - reuses the existing copy-path interaction and feedback pattern when a path exists

17. Reuse existing helper components where possible:
   - `MetricCard`
   - `PathField`
   - `StatusBadge`
   - `CountMapPanel` only if it keeps the panel compact
   - existing `copyFeedback` state and timeout reset

18. Do not add new shared abstractions unless the existing page becomes unreadable. Prefer one local frontend-only addition over a broad component refactor.

19. Update `frontend/src/styles.css` to support:
   - the new integrity panel block
   - subsection grouping inside the panel
   - responsive evidence-path rows
   - any top-grid adjustments needed so the page still works on desktop and mobile

20. Update `frontend/src/observability/ObservabilityPage.test.tsx` with:
   - a ready-state integrity mock
   - assertions that the new panel appears before run load
   - assertions for `Pass@k`, memory, recovery, and evidence-path rendering
   - one degraded-state test where one section is missing or invalid but the panel still renders
   - one transport-error test where the integrity panel shows only a panel-local error while benchmark summary still loads
   - one copy-path success test for an integrity evidence path

21. Update `frontend/e2e/internal-observability.spec.ts`:
   - stub `/internal/system/integrity-summary`
   - assert `System Integrity Summary` is visible on `5174`
   - assert at least one evidence path is visible before `Load Run`
   - keep the rest of the run-loading smoke intact

22. Update `README.md`:
   - add `System Integrity Summary` to the internal `5174` surface description
   - keep the update narrow and reviewer-facing

23. Update `docs/WEB_DEMO_README.md`:
   - add the new panel to the `Internal Review Surface` section
   - update the reviewer scan order to:
     1. `Benchmark Summary`
     2. `System Integrity Summary`
     3. `Load Run`
     4. `Trace Summary`
     5. `Benchmark Artifacts`
     6. `Recovery Visualization`
   - mention that evidence paths can be copied directly from the page

24. Run focused frontend tests first:

   ```bash
   npm --prefix frontend run test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
   ```

25. Run the frontend build:

   ```bash
   npm --prefix frontend run build
   ```

26. Run the internal desktop browser smoke:

   ```bash
   npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"
   ```

27. Run whitespace and working-tree checks:

   ```bash
   git diff --check
   git status --short --branch
   ```

28. Stage only the task files and the `103` spec/plan docs once they are saved later.
29. Commit with the expected message.
30. Push the `103` branch.

## 6. Testing Plan

- Unit tests:
  - `frontend/src/observability/api.test.ts`
  - verify `getSystemIntegritySummary()` hits the correct endpoint
  - preserve existing connection/not-found error behavior for the internal client layer

- Component tests:
  - `frontend/src/observability/ObservabilityPage.test.tsx`
  - ready state renders `System Integrity Summary`
  - degraded state renders section-level reasons without collapsing the panel
  - transport error state stays scoped to the integrity panel
  - evidence-path copy action shows inline success feedback
  - existing run-load and trace/recovery assertions remain intact

- Browser smoke:
  - `frontend/e2e/internal-observability.spec.ts`
  - page shows `Benchmark Summary` and `System Integrity Summary` on `5174`
  - run-load flow still works after stubbing the new endpoint

- Documentation review:
  - `README.md` and `docs/WEB_DEMO_README.md` both mention the new panel
  - reviewer scan order in `docs/WEB_DEMO_README.md` matches the implemented hierarchy

- Out-of-scope for testing:
  - no backend route tests
  - no benchmark reruns
  - no replay reruns
  - no customer-surface browser regression in this task unless the internal page changes unexpectedly leak into shared layout

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add system integrity review panel
```

Expected commands:

```bash
git switch -c codex/103-system-integrity-panel-v0
git status --short --branch
git add frontend/src/observability/types.ts
git add frontend/src/observability/api.ts
git add frontend/src/observability/api.test.ts
git add frontend/src/observability/ObservabilityPage.tsx
git add frontend/src/observability/ObservabilityPage.test.tsx
git add frontend/e2e/internal-observability.spec.ts
git add frontend/src/styles.css
git add README.md
git add docs/WEB_DEMO_README.md
git add docs/specs/103-system-integrity-panel-v0.md
git add docs/plans/103-system-integrity-panel-v0-plan.md
git diff --cached --check
git commit -m "feat: add system integrity review panel"
git push -u origin codex/103-system-integrity-panel-v0
```

The implementer must confirm the staged set does not include:

- `docs/NEW_WORKFLOW_PROMPT.md`
- `docs/TASK_INFO.md`
- `docs/superpowers/`
- `var/`
- any `.env` file
- any local-only artifacts or secrets

## 9. Out-of-scope Changes

- Do not modify `backend/app/api/observability.py` or the Task `102` backend response schema unless a contract bug is discovered first.
- Do not add benchmark rerun buttons, replay rerun buttons, or path-browsing UI.
- Do not redesign the existing release-gate hero beyond what is needed to fit the new panel.
- Do not change the customer page at `5173`.
- Do not add new dependencies, routers, migrations, or persisted metadata.
- Do not widen this task into the larger frontend-separation milestone.
- Do not touch unrelated untracked local docs or helper directories.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/103-system-integrity-panel-v0.md`.
- [ ] The internal page loads `GET /internal/system/integrity-summary` automatically on `5174`.
- [ ] The page renders a `System Integrity Summary` panel before any `run_id` is loaded.
- [ ] The panel shows `v2_integrity` status, `Pass@k`, memory governance, recovery replay, and evidence paths.
- [ ] Degraded payloads render as reviewer-readable UI states instead of request failures.
- [ ] Evidence-path copy actions work only when a path exists.
- [ ] Existing `Benchmark Summary` and `Load Run` behavior remain intact.
- [ ] The customer page remains unchanged.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` mention the new panel and reviewer scan order.
- [ ] Focused frontend tests passed.
- [ ] Frontend build passed.
- [ ] Internal desktop browser smoke passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for unrelated pre-existing untracked local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- the exact files modified
- confirmation that the task stayed frontend-only
- the final visible reviewer scan order on `5174`
- whether the panel renders all five mandatory content groups:
  - `v2_integrity` status
  - `Pass@k`
  - memory governance
  - recovery replay
  - evidence paths
- the verification commands run and their results
- the commit hash
- the push result
- any follow-up task suggested after `103` if reviewer feedback shows a remaining gap
