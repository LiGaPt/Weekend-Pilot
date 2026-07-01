# Plan: 123 Customer demo flow stabilization v0

## 1. Spec Reference

Spec file:

```text
docs/specs/123-customer-demo-flow-stabilization-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/121-execution-safety-ledger-hardening-v0`.
- Latest documented task is `121`, and the latest visible commit tied to task closure is:

```text
7752183 feat: harden execution safety and action ledger
```

- `docs/specs/` and `docs/plans/` are continuous and matched through `121`.
- The candidate `122` recovery-chaos expansion is already materially present in code and tests:
  - `friends_route_and_dining_unavailable_v1`
  - `elder_ticket_sold_out_and_route_unavailable_v1`
  - `recovery_focused = 8`
  - related safe-stop/recovery tests
- The customer and internal frontend surfaces are already split:
  - `frontend/src/App.tsx` is the public customer surface
  - `frontend/src/observability/ObservabilityPage.tsx` is the internal review surface
- Existing unrelated untracked local files must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- The customer surface already contains the right major building blocks:
  - one primary composer
  - scenario chips for Mock World presets
  - clarification/replan flow
  - progress stepper card
  - bounded result card
  - AMap read-only preview notice
- The likely remaining work is behavior tightening, visibility cleanup, and regression coverage alignment rather than greenfield feature work.

## 3. Files to Add

- `docs/specs/123-customer-demo-flow-stabilization-v0.md` - the numbered spec for this task.
- `docs/plans/123-customer-demo-flow-stabilization-v0-plan.md` - the numbered implementation plan for this task.

Use an empty list if the execution session decides these files already exist locally before work starts; in that case, finalize rather than recreate them.

## 4. Files to Modify

- `frontend/src/App.tsx` - tighten composer-mode transitions, scenario-selector visibility, progress-state handling, and bounded public error/result behavior.
- `frontend/src/chat/ConversationThread.tsx` - keep customer plan/result cards summary-first and ensure reviewer-style controls stay hidden.
- `frontend/src/chat/thread.ts` - tighten thread projection rules for progress/plan/result ordering and customer-facing text shaping.
- `frontend/src/types/demo.ts` - only if additive typing alignment is needed for bounded public statuses already returned by the backend.
- `frontend/src/App.test.tsx` - update and extend customer-surface unit tests for stabilized flow behavior.
- `frontend/src/chat/ConversationThread.test.tsx` - update and extend conversation-card visibility and copy constraints.
- `tests/integration/test_demo_api_gateway.py` - keep public-contract and flow-state assertions aligned with the stabilized customer UI.
- `frontend/e2e/demo.spec.ts` or the repository’s current customer demo browser-test file - add or tighten end-to-end coverage for happy path, clarification, replan, confirm, and one fallback/error path.
- `docs/WEB_DEMO_README.md` - align public demo instructions and visible-state expectations with the stabilized customer flow.
- `README.md` - keep the top-level public demo description aligned with the stabilized Mock World V2 customer experience.

## 5. Implementation Steps

1. Reconfirm task selection before touching code.
   - Run `git status --short`, `git branch --show-current`, and `git log --oneline -5`.
   - Confirm `121` is the latest tracked task.
   - Confirm `122` is already materially implemented in code/tests and therefore should not be recreated.
   - Confirm this task should be a new `123` convergence slice.

2. Inspect the current public customer flow end to end.
   - Read:
     - `frontend/src/App.tsx`
     - `frontend/src/chat/ConversationThread.tsx`
     - `frontend/src/chat/thread.ts`
     - `frontend/src/types/demo.ts`
     - `frontend/src/App.test.tsx`
     - `frontend/src/chat/ConversationThread.test.tsx`
     - `tests/integration/test_demo_api_gateway.py`
   - Identify where visible states are already correct and where behavior is still broader or noisier than the intended stable public flow.

3. Lock the public flow rules in the thread projection layer.
   - In `frontend/src/chat/thread.ts`, make the customer-thread projection deterministic for:
     - one active progress representation
     - progress card ordering above active clarification/plan/result
     - bounded customer result-card generation
     - summary-first plan-card generation
   - Do not expose reviewer-only fields through projection helpers.

4. Tighten composer and request-state behavior in `frontend/src/App.tsx`.
   - Preserve only the intended customer composer modes:
     - `start`
     - `clarify`
     - `replan`
   - Ensure scenario chips render only in start mode.
   - Ensure start/clarify/replan button labels and placeholders stay user-facing Chinese.
   - Ensure streamed start uses:
     - transient local spinner before first progress event
     - then exactly one persistent progress card
   - Ensure fallback request errors reset transient progress state cleanly and show only one bounded localized error banner.

5. Tighten public plan-card and result-card visibility in `frontend/src/chat/ConversationThread.tsx`.
   - Keep the active plan card summary-first.
   - Keep reviewer detail disclosures off the customer plan card.
   - Preserve bounded confirm/decline/replan affordances only for the active run.
   - Keep AMap preview in one read-only notice state with confirm hidden.
   - Keep result cards in one bounded shape:
     - headline
     - outcome label
     - optional final arrangement message
     - completed actions
     - failed actions
     - next steps
   - Prevent execution/debug/timeline internals from surfacing in the customer result card.

6. Align typing only if needed.
   - Update `frontend/src/types/demo.ts` only if the current public contract already returns statuses or fields not fully encoded in the frontend.
   - Keep this additive and do not redesign the public API contract.

7. Update unit tests for stabilized public behavior.
   - In `frontend/src/App.test.tsx`, assert:
     - one primary composer
     - scenario chips only in start mode
     - clarification mode hides scenario chips
     - replan mode hides scenario chips
     - transient spinner transitions into one persistent progress card
     - progress card stays above plan/result cards
     - read-only preview hides confirm
     - error state does not leave duplicate progress UI behind
   - In `frontend/src/chat/ConversationThread.test.tsx`, assert:
     - active run info remains bounded
     - reviewer detail controls remain hidden
     - raw IDs/tool names/debug text do not leak into the customer surface
     - final arrangement copy behavior stays bounded
     - visible fallback names remain localized/customer-facing

8. Update integration assertions for the customer-facing public contract.
   - In `tests/integration/test_demo_api_gateway.py`, keep asserting that:
     - public responses remain redacted
     - progress history and public statuses align with the customer flow
     - clarification and replan flows remain in the same public contract family
     - confirm and decline remain compatible with the stabilized customer UI
   - Add or tighten assertions only where the current tests under-specify visible customer-flow invariants.

9. Update focused browser regression.
   - Edit the current customer demo Playwright test file.
   - Cover one stable path each for:
     - happy path start -> confirm -> result
     - clarification path -> reply -> plan
     - replan path from awaiting confirmation
     - decline path or one bounded failure/error path
   - Prefer existing selectors and real local stack behavior over mocking new success paths.
   - Do not expand this into broad reviewer-surface coverage.

10. Align docs with the stabilized customer flow.
    - In `docs/WEB_DEMO_README.md`, describe the public `5173` experience as:
      - one bottom composer
      - optional clarification
      - optional replan
      - bounded confirm/decline
      - bounded result/fallback
    - In `README.md`, keep the public demo summary aligned with the stabilized Mock World V2 customer path and clearly separate it from the internal observability page.

11. Save the numbered task docs.
    - Save the finalized spec to:
      - `docs/specs/123-customer-demo-flow-stabilization-v0.md`
    - Save the finalized plan to:
      - `docs/plans/123-customer-demo-flow-stabilization-v0-plan.md`

12. Run focused verification.
    - Run the frontend unit tests first.
    - Run the demo API integration test second.
    - Run the focused customer browser regression third.
    - If failures appear, fix the smallest customer-flow issue that restores the intended bounded public behavior.

13. Run repository hygiene checks.
    - Run `git diff --check` and `git status --short`.
    - Confirm only task-relevant frontend/tests/docs files are modified or staged.
    - Confirm unrelated local docs remain untouched.

14. Prepare commit and push.
    - Stage only Task `123` files.
    - Commit with:
      - `feat: stabilize customer demo flow`
    - Push the task branch after verification passes.

## 6. Testing Plan

- Unit tests:
  - `frontend/src/App.test.tsx`
    - one primary composer
    - start/clarify/replan mode transitions
    - scenario-chip visibility rules
    - transient spinner to persistent progress-card transition
    - progress-card ordering above plan/result
    - read-only preview confirm blocking
    - bounded error handling
  - `frontend/src/chat/ConversationThread.test.tsx`
    - summary-first plan card
    - reviewer/detail controls hidden on customer surface
    - bounded result-card rendering
    - final arrangement message copy behavior
    - customer-facing localization and no raw internal leakage

- Integration tests:
  - `tests/integration/test_demo_api_gateway.py`
    - public redaction contract
    - happy path public summary compatibility
    - clarification and replan continuity
    - confirm/decline compatibility with customer flow
    - progress schema and public statuses used by the frontend

- Smoke / browser tests:
  - current customer demo Playwright file
    - happy path start -> confirm -> result
    - clarification flow
    - replan flow
    - one fallback/error path
    - optional decline flow if already present in existing suite

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend test -- --run src/App.test.tsx src/chat/ConversationThread.test.tsx
python -m pytest tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend run test:e2e -- --grep "customer demo|happy path|clarification|replan|confirm"
git diff --check
git status --short
```

If the repository uses a different e2e script name, substitute the existing customer demo browser-test command while keeping the scenario coverage equivalent.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: stabilize customer demo flow
```

Expected commands:

```bash
git status --short
git switch -c codex/123-customer-demo-flow-stabilization-v0
git add docs/specs/123-customer-demo-flow-stabilization-v0.md docs/plans/123-customer-demo-flow-stabilization-v0-plan.md frontend/src/App.tsx frontend/src/chat/ConversationThread.tsx frontend/src/chat/thread.ts frontend/src/types/demo.ts frontend/src/App.test.tsx frontend/src/chat/ConversationThread.test.tsx tests/integration/test_demo_api_gateway.py docs/WEB_DEMO_README.md README.md frontend/e2e/demo.spec.ts
git diff --cached --check
git commit -m "feat: stabilize customer demo flow"
git push -u origin codex/123-customer-demo-flow-stabilization-v0
```

If `frontend/src/types/demo.ts` or `frontend/e2e/demo.spec.ts` do not need changes after inspection, omit them from staging. The implementer must confirm `.env`, secrets, generated artifacts, and unrelated local docs are not staged.

## 9. Out-of-scope Changes

- Do not add new benchmark cases, new suites, or change benchmark thresholds.
- Do not add new recovery-routing behavior or recovery visualization work.
- Do not modify the internal observability surface beyond doc wording that distinguishes it from the customer surface.
- Do not redesign the public backend API contract.
- Do not add new provider behavior, real-map execution behavior, or new write tools.
- Do not turn this into a major visual redesign or information-architecture rewrite.
- Do not touch unrelated local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Do not stage `var/`, caches, virtual environments, screenshots, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/123-customer-demo-flow-stabilization-v0.md`.
- [ ] The task stayed focused on customer-flow stabilization rather than feature expansion.
- [ ] The public page still uses one bottom composer as the primary input.
- [ ] Scenario chips appear only in start mode.
- [ ] The progress card appears at most once and stays above the active clarification/plan/result card.
- [ ] Reviewer/debug controls remain hidden on the customer surface.
- [ ] The active plan card stays summary-first.
- [ ] The result card stays bounded and customer-facing.
- [ ] The AMap read-only preview path still blocks confirmation.
- [ ] Focused frontend unit tests passed.
- [ ] Focused API integration tests passed.
- [ ] Focused customer browser regression passed.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` match the stabilized public flow.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back:

- exact files changed
- whether `frontend/src/types/demo.ts` needed any additive typing changes
- the final bounded customer-visible flow states
- the final browser scenarios covered
- verification commands run and their results
- commit hash
- push result
- confirmation that Task `122` was intentionally not recreated because its recovery-chaos slice already exists in code/tests
- confirmation that unrelated untracked local docs remained untouched
- any residual follow-up, especially if there is still a docs-only cleanup needed to reconcile `122` numbering/history with the already-present implementation
