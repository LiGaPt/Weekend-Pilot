# Plan: 080 Customer Demo E2E Regression v0

## 1. Spec Reference

Spec file:

```text
docs/specs/080-customer-demo-e2e-regression-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/customer-progress-stepper-and-search-counts-v0`.
- `git status --short` is empty at planning time.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `079`.
- Latest task is `079`, and latest commit is `e78138d feat: add customer progress stepper and search counts`.
- `frontend/e2e/demo.spec.ts` already mixes:
  - live customer flows for happy path, Chinese reviewer prompt, friends-group, clarification, and mobile overflow
  - mocked contract checks for selected-plan replan index, AMap preview, and parts of redaction / replan behavior
- `frontend/playwright.config.ts` already provides the only two customer browser projects needed here:
  - `desktop-chromium`
  - `mobile-chromium`
- Playwright already starts backend, customer frontend, and internal frontend web servers, but PostgreSQL, Redis, and Alembic migrations still have to be prepared before running the suite.
- `frontend/src/chat/ProgressStepperCard.tsx` and `frontend/src/chat/ConversationThread.tsx` already expose stable customer-safe selectors such as `progress-stepper-card`, `progress-completed-toggle`, `clarification-card`, `replan-panel`, `confirm-button`, `execution-timeline-toggle`, and the closed-by-default run-info disclosure.
- No new backend, schema, or Playwright infrastructure is required for this task.

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/e2e/demo.spec.ts` - strengthen customer live regression coverage, keep targeted mocks only where deterministic contract checks are still needed, and tighten helper assertions around progress, replan, redaction, and mobile overflow.
- `docs/WEB_DEMO_README.md` - document the strengthened customer regression matrix, focused commands, and the split between live checks and targeted mocked contract checks.

## 5. Implementation Steps

1. Review `frontend/e2e/demo.spec.ts` and classify every existing customer test as either:
   - live customer regression
   - targeted mocked contract check

2. Keep the current file as the single customer E2E entrypoint.
   Do not create a new Playwright suite file, helper module, or new project.

3. Refine the shared helper layer inside `frontend/e2e/demo.spec.ts` so the live tests can assert the current UI shape without brittle itinerary-content coupling.
   The helper layer should include:
   - a helper that waits for the customer flow to resolve into clarification, confirmation, or result
   - a helper that opens and reads the latest `运行信息` disclosure
   - a helper that asserts the progress stepper is present and its completed-step list is closed by default
   - a helper that scans visible body text for forbidden internal or secret-like keys

4. Strengthen the live desktop happy-path confirm test.
   Make it assert all of the following in one real customer flow:
   - user message and transient system-progress row appear first
   - persistent progress stepper appears once the run summary is available
   - completed steps are hidden until `progress-completed-toggle` is opened
   - `run_id` is not visible by default
   - summary-first plan card is visible
   - confirmation succeeds
   - result card appears later in the same conversation stream
   - execution timeline stays collapsed until the reviewer opens it
   - forbidden internal or secret-like visible text is still absent

5. Strengthen the live desktop clarification test.
   Keep the vague start prompt, but add explicit assertions for:
   - clarification card appears under the progress card
   - inline reply submission works in-page
   - the continuation produces a different `run_id`
   - the first real plan still shows `plan_version.version_label = v1`
   - the page returns to a confirmable plan state without losing the progress stepper

6. Add or convert one live desktop replan regression.
   Use a clear follow-up prompt on a real confirmable run and assert:
   - the inline replan panel is used, not a mocked API success path
   - the returned run has a different `run_id`
   - the visible version advances from `v1` to `v2`
   - the new plan card is still preceded by the progress stepper
   - the run remains at the confirmation boundary
   Keep the existing mocked selected-second-plan regression in place for deterministic `selected_plan_index = 1` contract coverage.

7. Preserve the AMap preview test as a targeted mocked contract check.
   Do not widen it into a live provider dependency. It should continue to validate:
   - advanced-options selector path
   - read-only notice
   - blocked confirmation
   - customer-safe visible read-path state

8. Strengthen the mobile smoke without changing project configuration.
   Keep it on the real customer flow and assert:
   - the page reaches either clarification or confirmation state
   - the corresponding customer controls are visible
   - the progress stepper or clarification card is visible
   - document-level horizontal overflow is absent

9. Update `docs/WEB_DEMO_README.md`.
   Add one short regression section that states:
   - live desktop checks now cover happy path, clarification, live replan, confirm execution, redaction, and progress-stepper behavior
   - mobile smoke remains real and checks viewport stability
   - selected-second-plan and AMap preview remain targeted mocked checks
   - focused local commands and full pre-commit commands

10. Run the verification commands in this plan.
    If any test fails, fix the test or the minimal customer-surface selector issue only.
    Do not change backend contracts or add new test-only backend paths.

11. Before committing, review the diff and confirm only task-relevant files are staged, plus the saved task spec and plan docs for `080`.

## 6. Testing Plan

- Browser E2E live checks:
  - desktop happy path with confirm execution
  - desktop clarification continuation
  - desktop live replan continuation
  - desktop customer redaction boundary
  - mobile overflow smoke
- Browser E2E targeted mocked checks:
  - selected second-plan replan index payload
  - AMap read-only preview confirm block
- Frontend build check:
  - `npm --prefix frontend run build`
- Documentation review:
  - confirm `docs/WEB_DEMO_README.md` matches the final live/mocked regression split and command list

No new backend unit or integration tests are planned for this task.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium
npm --prefix frontend run e2e -- --project=mobile-chromium
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
test: expand customer demo e2e regression coverage
```

Expected commands:

```bash
git status --short
git switch -c codex/customer-demo-e2e-regression-v0
git add frontend/e2e/demo.spec.ts docs/WEB_DEMO_README.md
git add docs/specs/080-customer-demo-e2e-regression-v0.md docs/plans/080-customer-demo-e2e-regression-v0-plan.md
git commit -m "test: expand customer demo e2e regression coverage"
git push -u origin codex/customer-demo-e2e-regression-v0
```

The implementer must confirm `.env`, secrets, `frontend/dist/`, Playwright artifacts, `var/`, and unrelated local files are not staged.

## 9. Out-of-scope Changes

- Do not change backend API schemas, workflow routing, or database schema.
- Do not add async start, polling, SSE, WebSockets, or background job infrastructure.
- Do not redesign the customer UI beyond the minimum needed to keep existing selectors stable.
- Do not modify internal observability routes, pages, or their Playwright coverage.
- Do not add new Playwright projects, browsers, or dependency packages.
- Do not convert deterministic mocked AMap or selected-plan-index checks into flaky live-provider tests.
- Do not edit top-level `README.md`, benchmark docs, or unrelated reviewer docs.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] Core customer regressions now use the real local stack for happy path, clarification, live replan, confirm execution, redaction, and mobile overflow.
- [ ] Only the selected-plan-index and AMap preview checks still rely on targeted mocks.
- [ ] `docs/WEB_DEMO_README.md` accurately documents the final regression matrix and command set.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Whether the live happy path or live replan required any clarification fallback during execution
- Whether any minimal customer-surface selector adjustment was needed to keep the E2E assertions stable
- Any remaining flakiness or follow-up task candidates, especially if live replan still looks too nondeterministic for long-term regression use
