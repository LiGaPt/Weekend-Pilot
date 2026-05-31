# Plan: 081 Internal Observability Review Polish v0

## 1. Spec Reference

Spec file:

```text
docs/specs/081-internal-observability-review-polish-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/internal-observability-review-polish-v0`.
- `git status --short --branch` currently shows:
  - modified `frontend/src/observability/ObservabilityPage.tsx`
  - modified `frontend/src/observability/ObservabilityPage.test.tsx`
  - untracked `docs/specs/081-internal-observability-review-polish-v0.md`
  - untracked `docs/plans/081-internal-observability-review-polish-v0-plan.md`
- `docs/specs` and `docs/plans` are continuous and slug-matched through `081` in the working tree.
- The latest committed task is still `080`, with latest commit `b80bce2 test: expand customer demo e2e regression coverage`.
- The current `081` prototype already compiles and `npm --prefix frontend run build` passes.
- The focused Vitest command currently fails because the test expects a unique `execute_searches` text match, but the current UI intentionally shows that stage name in more than one place.
- `frontend/e2e/internal-observability.spec.ts`, `frontend/src/styles.css`, and `docs/WEB_DEMO_README.md` still need to be aligned with the new reviewer hierarchy.
- No backend API change is required for this task.

## 3. Files to Add

- `docs/specs/081-internal-observability-review-polish-v0.md` - save the approved spec content for the in-progress `081` task.
- `docs/plans/081-internal-observability-review-polish-v0-plan.md` - save the approved implementation plan for the in-progress `081` task.

## 4. Files to Modify

- `frontend/src/observability/ObservabilityPage.tsx` - finish the reviewer-first layout, copy-path interactions, derived timing summaries, and panel wiring.
- `frontend/src/observability/ObservabilityPage.test.tsx` - fix the ambiguous assertion and cover the final reviewer-facing behavior.
- `frontend/e2e/internal-observability.spec.ts` - assert the refined internal reviewer flow on `5174`.
- `frontend/src/styles.css` - add or adjust observability-specific layout and responsive styles.
- `docs/WEB_DEMO_README.md` - document the final internal reviewer scan order and copy-path actions.

## 5. Implementation Steps

1. Save the approved `081` spec and plan documents to `docs/specs/081-internal-observability-review-polish-v0.md` and `docs/plans/081-internal-observability-review-polish-v0-plan.md`.
2. Review the existing `081` diff in `frontend/src/observability/ObservabilityPage.tsx` and `frontend/src/observability/ObservabilityPage.test.tsx`. Continue that work in place; do not discard it.
3. In `frontend/src/observability/ObservabilityPage.tsx`, keep the current request flow unchanged. `getLatestReleaseGateBenchmarkSummary()` and `getObservabilityRun()` must remain the only data sources for this page.
4. Finalize the page-level copy-feedback state and `PathField` usage. Ensure the benchmark hero uses `summary.report_path`, the benchmark-artifacts panel shows both the current run report path and the latest release-gate alias path, and the recovery panel shows the replay report path when available.
5. Keep copy buttons visible only when the corresponding path is non-empty. Show brief inline success or failure feedback and clear it automatically after a short delay.
6. Finalize the workflow timing section. Keep `getSlowestStage(...)` client-side only, preserve backend stage order in the lane list, and compute lane widths relative to the current run’s slowest stage only.
7. Finalize the tool-events section. Keep it based only on `tool_event_summaries`, compute rollups client-side, and keep per-event request/response/error previews sanitized.
8. Finalize the recovery section. Keep it based only on `recovery_path_summary`, sort attempts by `attempt_index`, show the latest-attempt summary card, and keep replay-source details separate from attempt details.
9. Update `frontend/src/styles.css` with observability-specific styles for:
   - benchmark hero
   - metric-card grid
   - copy-path fields
   - stage lanes
   - tool-event rollup cards
   - preview cards
   - recovery attempt cards
   - narrow-screen stacking
10. Keep customer-surface selectors and behavior unchanged while editing shared CSS.
11. Update `frontend/src/observability/ObservabilityPage.test.tsx`. Replace the ambiguous `getByText("execute_searches")` assertion with a scoped or plural assertion that matches the final intended DOM. Keep or extend assertions for:
   - latest release-gate hero
   - latest alias copy button
   - current run report path vs latest alias path
   - replay report copy button
   - copy success and failure feedback
   - latest recovery attempt summary
12. Update `frontend/e2e/internal-observability.spec.ts` so the desktop smoke asserts:
   - `Benchmark Summary` is visible before any run is loaded
   - the latest alias path is visible
   - the latest alias copy control is visible
   - loading a run by `run_id` still works
   - `Trace Summary` still renders
   - `Recovery Visualization` still renders
13. Update `docs/WEB_DEMO_README.md` in the internal-review section so the documented scan order is:
   - benchmark hero first
   - copy canonical latest alias path when needed
   - load a run
   - inspect trace summary
   - inspect benchmark artifacts and recovery details
14. Run the verification commands from this plan.
15. Review the final diff and ensure only the task-relevant files plus the saved `081` spec/plan docs are staged.
16. Commit and push the existing branch.

## 6. Testing Plan

- Build smoke: `npm --prefix frontend run build`
- Focused unit test: `npm --prefix frontend run test -- --run src/observability/ObservabilityPage.test.tsx`
- Focused browser E2E: `npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"`
- Docs review: verify the internal-review section in `docs/WEB_DEMO_README.md` matches the final UI scan order
- Backend tests: no backend test updates are expected because API contracts are intentionally unchanged

## 7. Verification Commands

```bash
npm --prefix frontend run build
npm --prefix frontend run test -- --run src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "internal observability surface"
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: polish internal observability review surface
```

Expected commands:

```bash
git status --short --branch
git add docs/specs/081-internal-observability-review-polish-v0.md docs/plans/081-internal-observability-review-polish-v0-plan.md
git add frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/ObservabilityPage.test.tsx
git add frontend/e2e/internal-observability.spec.ts frontend/src/styles.css docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: polish internal observability review surface"
git push -u origin codex/internal-observability-review-polish-v0
```

The implementer must confirm `.env`, `frontend/dist/`, Playwright artifacts, `var/`, and unrelated local files are not staged.

## 9. Out-of-scope Changes

- Do not add a new top-level Reviewer Guide document.
- Do not add a new submission demo script.
- Do not change `backend/app/api/observability.py`.
- Do not change backend observability schemas or summary builders.
- Do not change the customer surface at `5173`.
- Do not change benchmark release-gate logic, replay logic, or benchmark artifact generation.
- Do not add a generic file browser, report downloader, or replay launcher.
- Do not add new dependencies.
- Do not widen this task into generic frontend test-infrastructure repair.

## 10. Review Checklist

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the `081` scope.
- [ ] The benchmark hero is the first reviewer-facing panel on `5174`.
- [ ] The page exposes copy actions only for visible report paths.
- [ ] Workflow timing is easier to scan and includes a clear slowest-stage summary.
- [ ] Tool events are easier to scan without exposing new raw payloads or IDs.
- [ ] Benchmark artifacts clearly distinguish the current run report path from the canonical latest alias path.
- [ ] Recovery visualization is easier to scan and still uses only existing recovery summary data.
- [ ] `docs/WEB_DEMO_README.md` reflects the final internal review scan order.
- [ ] Required frontend verification commands passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Report back with:

- changed files
- verification commands and results
- commit hash
- push result
- confirmation that the old ambiguous `execute_searches` unit-test failure is resolved
- any remaining clipboard or responsive-layout caveats
- the recommended follow-up task after `081`, which should be the docs-only consolidation of the fixed demo path and the four canonical evidence artifacts
