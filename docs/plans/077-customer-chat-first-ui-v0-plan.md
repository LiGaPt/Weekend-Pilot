# Plan: 077 Customer Chat-First UI v0

## 1. Spec Reference

Spec file:

```text
docs/specs/077-customer-chat-first-ui-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/review-evidence-contract-guardrail-v0`.
- `git status --short` is clean in this workspace.
- `docs/specs` and `docs/plans` are continuous and slug-matched from `001` through `076`.
- Latest commit is `2e9a65c feat: add review evidence contract guardrail`, and that exact commit message matches the expected commit recorded in task `076`.
- There is no `077` draft spec, draft plan, or dirty working-tree evidence that this task already exists in progress.
- The current customer surface is still implemented primarily in `frontend/src/App.tsx` with a two-column layout, a default-visible run summary inspector, and plan details rendered panel-first.
- The internal review surface in `frontend/src/observability/ObservabilityPage.tsx` is already separated and must remain behaviorally unchanged.
- Shared customer/internal styling lives in `frontend/src/styles.css`, so customer-page CSS changes can regress the internal page unless tested.
- Older linked worktree branches exist locally for historical tasks, but the numbered docs chain and later completed commits show they are not the current continuation target for this task.
- Implementation should start from a fresh branch off the current `HEAD` or the merged equivalent baseline, not by continuing to commit new UI work onto the `076` branch.

## 3. Files to Add

- `frontend/src/chat/thread.ts` - pure chat-thread item types and projection helpers that turn existing run responses plus local interaction history into summary-first customer chat cards.
- `frontend/src/chat/thread.test.ts` - unit tests for transcript projection, selected-plan switching, disclosure section ordering, and default-hidden metadata decisions.
- `frontend/src/chat/ConversationThread.tsx` - presentational chat-thread renderer for user/system/assistant items, summary-first plan cards, and inline clarification/replan/result blocks.

## 4. Files to Modify

- `frontend/src/App.tsx` - replace the current side-rail customer flow with a single-column chat-first container, advanced-options disclosure, local interaction history, and inline follow-up controls.
- `frontend/src/styles.css` - add chat-first customer styles, hero composer/example styles, disclosure styles, and responsive single-column layout rules while preserving internal-page rendering.
- `frontend/src/App.test.tsx` - update customer-surface tests for the new first screen, hidden metadata, in-chat clarification/replan, selected-plan switching, and result rendering.
- `frontend/e2e/demo.spec.ts` - update browser tests to use the new customer chat surface, the advanced-options AMap path, and the summary-first confirmation flow.
- `docs/WEB_DEMO_README.md` - rewrite the customer reviewer flow to match the chat-first page.
- `docs/RICHER_WEB_UI_V1_CHECKLIST.md` - adjust customer evidence wording from panel-first review to chat-first summary/disclosure review.

## 5. Implementation Steps

1. Add the pure chat-thread helper in `frontend/src/chat/thread.ts`.
   Define one frontend-local model for customer chat items, including at least user message, system progress, assistant clarification, assistant plan card, and assistant result card.
   The helper must consume existing `DemoRunSummary` and selected-plan state only.
   It must not import API clients or require backend schema changes.

2. Write the new helper tests first in `frontend/src/chat/thread.test.ts`.
   Cover:
   - summary-first section ordering
   - selected alternative plan projection
   - omission of default-visible `run_id` and `action_count`
   - execution timeline collapse behavior
   - clarification vs replan assistant card shape
   Keep these tests pure and independent from DOM rendering.

3. Refactor `frontend/src/App.tsx` state management around a chat-first flow.
   Keep the existing API calls and request-state machine, but add local interaction history so start, clarify, replan, confirm, and decline all append to one visible transcript.
   On successful requests, update the latest run and selected plan from the returned `DemoRunSummary`.
   On failed requests, preserve the user draft and show the existing error banner.

4. Remove the default-visible customer run inspector from the main layout.
   Replace the current two-column structure with one centered single-column chat container.
   Keep refresh available, but move it into a closed-by-default run-info disclosure or a compact non-inspector control group.
   Do not render `action_count` as customer-visible metadata.

5. Build the new first-screen hero inside `App.tsx`.
   Keep one primary composer and a small example-entry strip.
   Add one advanced-options disclosure that contains the existing read-path selector.
   Keep `Mock World` as the default.
   Keep AMap preview reachable only through that secondary control.

6. Add the presentational thread renderer in `frontend/src/chat/ConversationThread.tsx`.
   Render:
   - user bubbles
   - system progress items
   - assistant clarification cards with inline reply form
   - assistant plan cards with plan-version badge, compact alternative-plan chips, and default-collapsed detail sections
   - assistant result cards with default-collapsed execution timeline
   Keep confirm, decline, and replan controls attached to the appropriate assistant card, not in a separate inspector panel.

7. Rework selected-plan presentation into a summary-first assistant card.
   Show the recommended title and summary first.
   Keep timeline, activity/dining, route/feasibility, and action-manifest details behind closed-by-default disclosures.
   Keep selected-plan switching in-chat and make sure confirm/replan keep using the selected plan index.

8. Preserve clarification, replan, and completion behavior inside the new layout.
   Clarification replies must remain inline and must keep `v1` when the first real plan appears.
   Replans must keep advancing `v2`, `v3`, and so on.
   Completion cards must keep the existing neutral empty state when execution exists but `action_results` is empty.

9. Update `frontend/src/styles.css`.
   Add styles for:
   - single-column chat layout
   - hero composer and example chips
   - message cards and system-progress rows
   - closed-by-default disclosure sections
   - compact run-info disclosure
   - responsive mobile layout without horizontal overflow
   Verify that internal-page structure still looks correct with the shared stylesheet.

10. Update `frontend/src/App.test.tsx`.
    Replace or adapt assertions that currently depend on default-visible run-summary fields.
    Add coverage for:
    - first-screen minimal entry
    - hidden default metadata
    - clarification inside the chat flow
    - replan inside the chat flow
    - selected non-default plan still affecting replan index
    - summary-first disclosure rendering
    - AMap path via advanced options
    - final result card with execution timeline disclosure

11. Update `frontend/e2e/demo.spec.ts`.
    Keep the existing customer scenarios, but adapt them to the new surface:
    - stable happy path
    - Chinese reviewer prompt path
    - friends-group path
    - clarification path
    - replan path
    - AMap read-only path
    - mobile smoke
    Use the new customer-visible controls instead of relying on a default-visible run inspector.

12. Update the customer docs.
    In `docs/WEB_DEMO_README.md`, rewrite the customer page description and manual flow around the chat-first UI.
    In `docs/RICHER_WEB_UI_V1_CHECKLIST.md`, change customer-side evidence wording so reviewers verify summary-first chat cards and expandable sections rather than a fixed panel stack.

13. Run focused verification, then full customer/internal browser regression.
    Because `styles.css` is shared, do not stop at customer-only checks.
    Confirm the internal observability page still passes its current smoke as part of the frontend suite.

## 6. Testing Plan

- Unit tests: `frontend/src/chat/thread.test.ts` covers transcript projection and default-hidden metadata; `frontend/src/App.test.tsx` covers first-screen, clarification, replan, selected-plan switching, AMap advanced options, and result cards.
- Regression unit tests: `frontend/src/observability/ObservabilityPage.test.tsx` remains in the verification set because shared CSS and app-level layout changes must not break the internal page.
- Frontend API regression: keep `frontend/src/api/demo.test.ts` in the run set even though the public API client should stay unchanged.
- Backend regression: run `tests/test_demo_api.py` and `tests/integration/test_demo_api_gateway.py` to prove the UI refactor did not silently drift the public contract assumptions.
- Browser E2E: run the full `npm --prefix frontend run e2e` suite so customer desktop, customer mobile, and internal observability smoke all stay green.
- Manual spot-check expectation: after a happy-path run, the customer page should show a user message, system progress, an assistant summary-first plan card, and default-hidden run metadata.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/chat/thread.test.ts src/App.test.tsx src/observability/ObservabilityPage.test.tsx src/api/demo.test.ts
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add chat-first customer ui
```

Expected commands:

```bash
git status --short
git switch -c codex/customer-chat-first-ui-v0
git add frontend/src/chat/thread.ts
git add frontend/src/chat/thread.test.ts
git add frontend/src/chat/ConversationThread.tsx
git add frontend/src/App.tsx frontend/src/styles.css frontend/src/App.test.tsx
git add frontend/e2e/demo.spec.ts
git add docs/WEB_DEMO_README.md docs/RICHER_WEB_UI_V1_CHECKLIST.md
git commit -m "feat: add chat-first customer ui"
git push -u origin codex/customer-chat-first-ui-v0
```

The implementer must confirm that `.env`, `frontend/dist/`, Playwright artifacts, `var/`, and unrelated local files are not staged.

## 9. Out-of-scope Changes

- Do not change any backend public API schema or add any new customer API route.
- Do not expose persisted conversation-turn history on the customer API.
- Do not redesign the internal observability page or its API client.
- Do not change benchmark, recovery, AMap, confirmation, or execution backend behavior.
- Do not add dependencies, auth controls, or a new design-system package.
- Do not widen this task into a server-backed transcript persistence task for hard browser reloads.
- Do not commit generated build output, Playwright reports, or unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The customer page is now chat-first and single-column by default.
- [ ] The first screen shows only the main composer plus example entries.
- [ ] The read-path selector is hidden behind advanced options by default.
- [ ] `run_id` and `action_count` are not visible by default on the customer surface.
- [ ] Clarification, replan, confirm, decline, and refresh still work in the customer flow.
- [ ] The recommended plan is summary-first and detail disclosures are collapsed by default.
- [ ] Selecting a non-default plan still affects confirm/replan behavior correctly.
- [ ] AMap preview remains reachable and non-confirmable.
- [ ] Internal observability regression tests still pass.
- [ ] Required tests and commands passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No secret, generated artifact, or unrelated file was committed.

## 11. Handoff Notes

The implementer should report back with:

- Changed files.
- Verification commands and results.
- Whether the internal observability regression remained green after the shared CSS update.
- Whether selected non-default plan replan indexing was re-verified after the UI refactor.
- Commit hash.
- Push result.
- Any residual limitation, especially that full browser reload transcript reconstruction remains out of scope until a later public-history task exists.
