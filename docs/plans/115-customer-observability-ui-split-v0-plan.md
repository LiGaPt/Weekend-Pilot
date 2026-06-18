# Plan: 115 Customer and Observability UI Split v0

## 1. Spec Reference

Spec file:

```text
docs/specs/115-customer-observability-ui-split-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is:

```text
codex/114-internal-observability-run-summary-v0
```

- Latest completed task baseline is:

```text
114-internal-observability-run-summary-v0
```

- Latest commit is:

```text
68ea7c3 feat: add run summary observability
```

- `docs/specs/` and `docs/plans/` are matched through `114`, with one intentional inserted task:
  - `113.5-playwright-internal-observability-e2e-teardown-exit-v0`
- The technical frontend surface split is already complete:
  - customer surface on `5173`
  - internal surface on `5174`
- The remaining gap is semantic/UI-content split:
  - customer surface still renders detailed plan-review panels
  - internal observability surface still lacks selected-plan detail review
- The public demo API already contains enough selected-plan data for the current customer UI and should remain unchanged in this task.
- The internal observability backend already loads:
  - run metadata
  - selected plan
  - tool events
  - action ledger summaries
  - workflow timing summary
  - benchmark artifact summary
  - recovery path summary
- The worktree currently contains unrelated untracked local docs that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/observability/schemas.py` - add additive Pydantic models for `selected_plan_review` and add the new top-level field to `InternalObservabilityRunSummary`.
- `backend/app/observability/service.py` - derive a sanitized selected-plan review payload from the persisted selected plan JSON.
- `frontend/src/observability/types.ts` - mirror the additive `selected_plan_review` contract in TypeScript.
- `frontend/src/observability/ObservabilityPage.tsx` - render the new `Selected Plan Review` section on the internal page.
- `frontend/src/chat/thread.ts` - remove customer-facing section definitions that drive detailed review panels not wanted on `5173`.
- `frontend/src/chat/ConversationThread.tsx` - stop rendering customer-facing detailed plan/timeline/action-review sections and execution timeline toggles.
- `frontend/src/App.test.tsx` - update customer-flow expectations so detailed review panels are absent while confirmation/result flow remains intact.
- `frontend/src/chat/ConversationThread.test.tsx` - update conversation-thread coverage for the reduced customer-visible detail surface.
- `frontend/src/observability/api.test.ts` - update mocked internal route payloads for the additive field.
- `frontend/src/observability/ObservabilityPage.test.tsx` - add rendering coverage for `Selected Plan Review` and null fallback behavior.
- `frontend/e2e/demo.spec.ts` - remove assertions that depend on customer-visible timeline/detail toggles and replace them with assertions for their absence.
- `frontend/e2e/internal-observability.spec.ts` - extend mocked internal payload and assertions to cover `Selected Plan Review`.
- `tests/test_observability.py` - add backend unit coverage for populated and null `selected_plan_review`.
- `tests/integration/test_observability_gateway.py` - assert the route returns the additive field and sanitized values.
- `docs/WEB_DEMO_README.md` - update reviewer instructions so `5173` is described as result/confirmation-oriented and `5174` as the source of timeline/detail/trace/ledger review.
- `README.md` - update the high-level product surface description to reflect the narrower customer UI and the internal detail-review responsibility.

## 5. Implementation Steps

1. Confirm the baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Verify the repo is currently on top of task `114`.
   - Do not touch the unrelated untracked docs.

2. Inspect the current customer detail rendering and internal observability contract.
   - Read:
     - `frontend/src/App.tsx`
     - `frontend/src/chat/thread.ts`
     - `frontend/src/chat/ConversationThread.tsx`
     - `frontend/src/observability/types.ts`
     - `frontend/src/observability/ObservabilityPage.tsx`
     - `backend/app/observability/schemas.py`
     - `backend/app/observability/service.py`
   - Confirm:
     - customer surface still renders timeline/route/action-review sections
     - internal route has run-level observability but no selected-plan review payload
     - selected plan JSON is already available in the observability service

3. Extend backend schemas first.
   - In `backend/app/observability/schemas.py`, add additive models for:
     - `InternalSelectedPlanReview`
     - any minimal supporting typed payloads needed for selected plan review
   - Reuse existing sanitized shape concepts where possible instead of inventing large new parallel schemas.
   - Add `selected_plan_review: InternalSelectedPlanReview | None = None` to `InternalObservabilityRunSummary`.
   - Keep all existing internal route fields backward compatible.

4. Write failing backend unit tests before implementing logic.
   - In `tests/test_observability.py`, add tests that require:
     - a run with a selected plan returns a populated `selected_plan_review`
     - a run with no selected plan returns `selected_plan_review is None`
     - malformed or missing selected plan JSON degrades to `None`
     - the selected-plan review payload is sanitized and does not leak forbidden raw payload/sensitive keys
   - Keep these tests focused on the additive field and null-degradation behavior.

5. Implement backend selected-plan review extraction.
   - In `backend/app/observability/service.py`, add a private helper that:
     - accepts the selected `Plan | None`
     - validates that `plan.plan_json` is a dict
     - extracts the existing user-facing plan fields from the selected plan draft
     - sanitizes the extracted structure through the existing payload-sanitization path before returning it
   - Build only the fields listed in the spec:
     - `plan_id`
     - `status`
     - `title`
     - `summary`
     - `activity`
     - `dining`
     - `timeline`
     - `route`
     - `feasibility`
     - `action_manifest`
   - Return `None` when no valid selected plan exists.

6. Wire the additive field into the internal route response.
   - Update `InternalObservabilityService.get_run_summary(...)` to populate `selected_plan_review`.
   - Do not change route URL, route status handling, or existing detailed sections.

7. Extend backend integration tests.
   - In `tests/integration/test_observability_gateway.py`:
     - update the happy-path route assertion to include `selected_plan_review`
     - assert populated timeline/route/feasibility/action manifest data is present when the selected plan exists
     - assert `selected_plan_review` is `null` for runs without a selected plan
     - assert the route still returns `404` for missing runs
   - Keep existing `run_summary`, tool-event, action-ledger, benchmark-artifact, and recovery assertions intact.

8. Reduce the customer-visible plan detail surface.
   - In `frontend/src/chat/thread.ts`, remove the customer-facing section definitions for:
     - timeline
     - activity/dining detail
     - route/feasibility detail
     - pre-confirmation action detail
   - Keep the customer flow structure that drives:
     - conversation chronology
     - plan summary card
     - plan selection
     - confirm/decline
     - clarification and replan inputs
     - final result summary
   - In `frontend/src/chat/ConversationThread.tsx`, stop rendering the removed detail sections and stop rendering the execution timeline toggle/detail block in the customer result card.

9. Verify customer behavior is still intact after UI reduction.
   - Ensure the customer surface still exposes:
     - plan choice
     - confirm button
     - decline button
     - replan composer
     - final arrangement message after completion
   - Ensure customer-visible text does not regress into internal/debug content.

10. Extend the internal observability frontend types and API tests.
    - In `frontend/src/observability/types.ts`, add the `selected_plan_review` type and its supporting shapes.
    - In `frontend/src/observability/api.test.ts`, update the mocked route payload to include the additive field and ensure parsing still works.

11. Render `Selected Plan Review` on the internal page.
    - In `frontend/src/observability/ObservabilityPage.tsx`, add a reviewer-facing section named `Selected Plan Review`.
    - Place it in the run workspace near the front of the page, after `Run Summary` and before or alongside the existing deeper observability sections.
    - Render:
      - plan identity and summary
      - activity and dining summaries
      - itinerary timeline list
      - route and feasibility summary
      - pre-confirmation action manifest summary
    - If `selected_plan_review` is `null`, render a neutral reviewer message such as “No selected plan detail is available for this run.”

12. Extend internal-page component tests.
    - In `frontend/src/observability/ObservabilityPage.test.tsx`, add assertions that:
      - `Selected Plan Review` renders when the payload is present
      - timeline entries render from the internal payload
      - route/feasibility/action-manifest details render
      - null payload renders a neutral empty state
    - Keep existing assertions for `Run Summary`, `Trace Summary`, `Tool Events`, `Action Ledger`, `Benchmark Artifacts`, and `Recovery Visualization`.

13. Update customer component tests.
    - In `frontend/src/App.test.tsx` and `frontend/src/chat/ConversationThread.test.tsx`, remove assertions that depend on customer-visible timeline/detail sections.
    - Replace them with assertions that:
      - confirm/decline controls still render
      - the customer sees the result summary and final arrangement message
      - the removed detail toggles are absent

14. Update Playwright coverage.
    - In `frontend/e2e/demo.spec.ts`:
      - stop expanding timeline/detail toggles on `5173`
      - assert those toggles or detail sections are absent
      - keep the main happy-path confirm and final-result smoke path
    - In `frontend/e2e/internal-observability.spec.ts`:
      - extend the mocked internal route payload with `selected_plan_review`
      - assert `Selected Plan Review` is visible
      - assert at least one timeline item and one route/action detail are visible on `5174`

15. Update docs.
    - In `docs/WEB_DEMO_README.md`, update the reviewer scan order so:
      - `5173` is described as customer-safe confirmation/result flow
      - `5174` is described as the source of timeline/detail/trace/ledger review
    - In `README.md`, align the high-level description of the two web surfaces with the new content boundary.
    - Do not widen this into a full doc rewrite.

16. Run focused verification.
   - Backend:
     ```bash
     python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -q
     ```
   - Frontend:
     ```bash
     npm --prefix frontend test -- --run src/App.test.tsx src/chat/ConversationThread.test.tsx src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
     ```
   - E2E:
     ```bash
     cd frontend && npx playwright test e2e/demo.spec.ts e2e/internal-observability.spec.ts --project=desktop-chromium
     ```
   - Hygiene:
     ```bash
     git diff --check
     git status --short
     ```

17. Commit only task-relevant files.
   - Stage only the customer UI, internal observability, tests, docs, and task docs touched by this task.
   - Commit with:
     ```bash
     git commit -m "feat: split customer and observability plan detail surfaces"
     ```

## 6. Testing Plan

- Backend unit tests:
  - `tests/test_observability.py`
  - populated `selected_plan_review`
  - null `selected_plan_review`
  - malformed selected plan degradation
  - selected-plan sanitization coverage

- Backend integration tests:
  - `tests/integration/test_observability_gateway.py`
  - additive route field present
  - selected plan detail populated on selected-plan runs
  - null field on no-selected-plan runs
  - missing run still returns `404`

- Customer frontend tests:
  - `frontend/src/App.test.tsx`
  - `frontend/src/chat/ConversationThread.test.tsx`
  - customer flow still shows summary/confirmation/result
  - removed detail toggles are absent

- Internal frontend tests:
  - `frontend/src/observability/api.test.ts`
  - `frontend/src/observability/ObservabilityPage.test.tsx`
  - `Selected Plan Review` renders populated and null states correctly

- E2E smoke:
  - `frontend/e2e/demo.spec.ts`
  - customer happy path still works without customer-visible detail panels
  - `frontend/e2e/internal-observability.spec.ts`
  - internal page shows selected plan detail review

- Documentation check:
  - `docs/WEB_DEMO_README.md` and `README.md` describe the updated surface responsibilities accurately

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -q
npm --prefix frontend test -- --run src/App.test.tsx src/chat/ConversationThread.test.tsx src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
cd frontend && npx playwright test e2e/demo.spec.ts e2e/internal-observability.spec.ts --project=desktop-chromium
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: split customer and observability plan detail surfaces
```

Expected commands:

```bash
git status --short
git switch -c codex/115-customer-observability-ui-split-v0
git add backend/app/observability/schemas.py backend/app/observability/service.py frontend/src/observability/types.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/chat/thread.ts frontend/src/chat/ConversationThread.tsx frontend/src/App.test.tsx frontend/src/chat/ConversationThread.test.tsx frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.test.tsx frontend/e2e/demo.spec.ts frontend/e2e/internal-observability.spec.ts tests/test_observability.py tests/integration/test_observability_gateway.py docs/WEB_DEMO_README.md README.md docs/specs/115-customer-observability-ui-split-v0.md docs/plans/115-customer-observability-ui-split-v0-plan.md
git diff --cached --check
git commit -m "feat: split customer and observability plan detail surfaces"
git push -u origin codex/115-customer-observability-ui-split-v0
```

The implementer must confirm:
- unrelated untracked docs remain unstaged
- no `var/` artifacts or build output are staged
- no secrets are staged

## 9. Out-of-scope Changes

- Do not redo the dedicated customer/internal frontend entry split.
- Do not remove fields from the public demo backend contract.
- Do not redesign benchmark summary, system integrity summary, or recovery visualization.
- Do not change benchmark fixtures, workflow routing, recovery policies, or action ledger persistence.
- Do not add dependencies.
- Do not add a new route or database schema.
- Do not touch `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, or `docs/superpowers/`.
- Do not stage `frontend/dist/`, `var/`, caches, screenshots, videos, or local runtime artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/115-customer-observability-ui-split-v0.md`.
- [ ] The task stayed within M2 semantic UI/content split scope.
- [ ] The customer page still supports start, clarify, replan, confirm, decline, and final result display.
- [ ] The customer page no longer renders detailed timeline/route/action-review panels.
- [ ] The internal route gained additive `selected_plan_review` only.
- [ ] `selected_plan_review` is null-safe and sanitized.
- [ ] The internal page clearly renders `Selected Plan Review`.
- [ ] Existing internal observability sections still work.
- [ ] Focused backend, frontend, and E2E checks passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- exact files changed
- which customer-visible sections were removed from `5173`
- the final `selected_plan_review` schema fields added to the internal route
- verification commands run and results
- whether any customer tests had to be rewritten because they encoded the old review-heavy UI
- commit hash
- push result
- confirmation that unrelated untracked local docs stayed untouched
- any recommended follow-up task, especially if the team later wants to narrow the public demo API contract itself
