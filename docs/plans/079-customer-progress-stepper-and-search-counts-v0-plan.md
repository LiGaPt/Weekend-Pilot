# Plan: 079 Customer Progress Stepper and Search Counts v0

## 1. Spec Reference

Spec file:

```text
docs/specs/079-customer-progress-stepper-and-search-counts-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/public-demo-progress-contract-v0`.
- `git status --short --branch` is clean in this workspace.
- `docs/specs` and `docs/plans` are continuous and slug-matched from `001` through `078`.
- Latest commit is `59c6744 feat: add public demo progress contract`, and it matches the latest task docs in `078`.
- There is no draft `079` spec, draft `079` plan, or dirty working-tree evidence that a different unfinished task should be resumed first.
- Focused checks already passed during planning:
  - `python -m pytest tests/test_demo_progress.py tests/test_demo_api.py -q`
  - `npm --prefix frontend run test -- --run src/App.test.tsx src/chat/thread.test.ts src/api/demo.test.ts`
  - `npm --prefix frontend run build`
- `backend/app/demo/progress.py` already reconstructs public stage history from durable run evidence, but it exposes only:
  - `schema_version`
  - `current_stage`
  - `current_label`
  - `stage_history`
- `frontend/src/types/demo.ts` still omits `progress`.
- The customer chat surface still uses local `progressLabelForState(...)` strings and a transient `system_progress` row rather than consuming backend `run.progress`.
- The current Task `077` plan/result cards already satisfy the summary-first, details-collapsed customer pattern and should be preserved.
- Existing persisted `ToolEvent` rows already provide enough evidence for count summaries:
  - request category from `request_json.payload.category` or `canonical_category`
  - result count from `response_json.results` length or `response_json.candidate_count`
- The canonical `family_afternoon` Mock World path now has enough category results to support the required `5` activity and `5` dining progress summaries.

## 3. Files to Add

- `frontend/src/chat/ProgressStepperCard.tsx` - dedicated customer progress card component that renders the highlighted current step and closed-by-default completed-step disclosure.
- `frontend/src/chat/ProgressStepperCard.test.tsx` - focused render tests for collapse behavior, current-step emphasis, and search-count copy.

## 4. Files to Modify

- `backend/app/demo/schemas.py` - add progress step summary models and extend `DemoProgressSummary` with additive `steps`.
- `backend/app/demo/progress.py` - derive ordered customer-safe step summaries, search counts, and fallback summaries from existing run evidence.
- `backend/app/demo/service.py` - pass plan count and action count context into progress summary construction without changing route shapes.
- `tests/test_demo_progress.py` - cover step construction, count derivation, decline/confirm nuances, and fallback behavior.
- `tests/test_demo_api.py` - extend API serialization coverage for additive `progress.steps`.
- `tests/integration/test_demo_api_gateway.py` - assert progress steps and family happy-path `5/5` search-count summaries across start/get/clarify/replan/confirm/decline/AMAP flows.
- `frontend/src/types/demo.ts` - add `DemoProgressStepSummary` and `progress.steps` to the public frontend type contract.
- `frontend/src/chat/thread.ts` - introduce a progress-card thread item, keep pending spinner fallback, and project progress cards ahead of clarification/plan/result cards.
- `frontend/src/chat/ConversationThread.tsx` - render the new progress card item in the conversation stream.
- `frontend/src/styles.css` - add customer-safe stepper/timeline styles for current-step emphasis and completed-step disclosure.
- `frontend/src/App.test.tsx` - update fixtures and assert persistent progress-card behavior in the main chat flow.
- `frontend/src/chat/thread.test.ts` - assert progress-card ordering and thread projection behavior.
- `frontend/src/api/demo.test.ts` - update summary fixtures so progress payloads match the new frontend contract shape.
- `frontend/e2e/demo.spec.ts` - extend the existing customer smoke test to assert stepper placement and disclosure behavior.
- `README.md` - document the richer public progress contract and customer progress-card behavior.
- `docs/WEB_DEMO_README.md` - document `progress.steps`, search-count summaries, and the explicit non-goal that live transport is still deferred.

## 5. Implementation Steps

1. Extend backend tests first.
   Update `tests/test_demo_progress.py` so it fails until `progress.steps` exists and includes:
   - ordered `completed/current` step summaries
   - `已找到 N 个活动` and `已找到 N 个餐厅` when count data is available
   - a plan-count summary for `building_itinerary` when plans exist
   - a decline-safe `ready_for_confirmation` current stage
   - a confirm/completed `executing_confirmed_actions` current stage
   - generic summary fallback when search counts cannot be derived

2. Extend `tests/test_demo_api.py` and `tests/integration/test_demo_api_gateway.py` before backend implementation.
   Add assertions that:
   - every successful public demo response carries additive `progress.steps`
   - the family Mock World happy path specifically includes `已找到 5 个活动` and `已找到 5 个餐厅`
   - `GET /demo/runs/{run_id}` preserves the same step summaries
   - clarification, replan, confirm, decline, and AMap preview flows keep the correct current step and safe fallback summaries

3. Extend backend progress schemas in `backend/app/demo/schemas.py`.
   Add:
   - `DemoProgressStepStatus = Literal["completed", "current"]`
   - `DemoProgressStepSummary`
   - `steps: list[DemoProgressStepSummary]` on `DemoProgressSummary`
   Keep:
   - `schema_version = "public_demo_progress_v1"`
   - `current_stage`
   - `current_label`
   unchanged for compatibility.

4. Implement step-summary building in `backend/app/demo/progress.py`.
   Use the existing stage order from Task `078`.
   Build one helper pipeline that:
   - reuses the current stage-history logic
   - derives latest usable search counts per category from ordered tool events
   - falls back from `response_json.results` length to `response_json.candidate_count`
   - generates stable Chinese summaries for each reached stage
   - marks all earlier reached stages as `completed`
   - marks the final stage as `current`
   - preserves public safety by never serializing raw node names, tool names, IDs, or payload fragments

5. Keep summary generation read-time only.
   Do not add new persistence for progress snapshots.
   Do not change workflow nodes, Tool Gateway writes, or Redis progress streams.
   Do not introduce a new progress API route.

6. Wire summary context in `backend/app/demo/service.py`.
   Update `DemoWorkflowService.build_summary(...)` so `build_demo_progress_summary(...)` receives the context it needs for richer summaries:
   - the loaded `tool_events`
   - plan count from `plan_rows`
   - customer-visible action count from the existing run/action state
   - the existing execution and feedback statuses
   Keep all public route behavior unchanged.

7. Update frontend type coverage in `frontend/src/types/demo.ts` and all existing test fixtures.
   Add the progress-step types and make sure all mocked `DemoRunSummary` values in:
   - `frontend/src/App.test.tsx`
   - `frontend/src/chat/thread.test.ts`
   - `frontend/src/api/demo.test.ts`
   include realistic `progress` payloads with `steps`.

8. Add `frontend/src/chat/ProgressStepperCard.tsx`.
   Render one customer-safe card with:
   - header title `当前进度`
   - current-step label and summary always visible
   - current-step visual emphasis
   - completed-step disclosure closed by default
   - completed-step rows that show stage label plus summary
   Use existing visual language from the customer surface; do not introduce reviewer/debug chrome or log-like styling.

9. Add `frontend/src/chat/ProgressStepperCard.test.tsx`.
   Assert:
   - current step is visible
   - completed steps are hidden before expansion
   - expanding reveals the completed step summaries
   - search-count summaries render exactly as provided by the backend contract

10. Update thread projection in `frontend/src/chat/thread.ts`.
    Add one new thread item kind for the progress card.
    Project it for every run that has non-empty `progress.steps`.
    Item ordering must be:
    - progress card first for the run
    - then clarification card or plan card
    - then result card when applicable
    Keep the transient `system_progress` row only for local in-flight states before the updated run summary arrives.

11. Update conversation rendering in `frontend/src/chat/ConversationThread.tsx`.
    Render the new progress card item without changing the existing clarification, plan, or result card behavior.
    Keep the existing summary-first recommendation and detail disclosure structure intact.

12. Update customer styles in `frontend/src/styles.css`.
    Add styles for:
    - progress-card container
    - current-step highlight
    - completed-step disclosure
    - compact step rows
    Keep the output compact and enterprise-like rather than chat-log-like.

13. Update frontend app flow assertions in `frontend/src/App.test.tsx` and `frontend/src/chat/thread.test.ts`.
    Add expectations that:
    - the local spinner row still appears immediately after clicking start
    - once the run summary arrives, the persistent progress card appears above the recommended plan
    - completed steps are collapsed by default
    - clarification runs show the progress card above the clarification card
    - completed or declined runs keep the progress card above the later result content

14. Update `frontend/e2e/demo.spec.ts`.
    Extend the existing customer smoke test so it verifies:
    - the progress card appears before `推荐方案摘要`
    - completed steps are initially hidden
    - expanding the disclosure shows the search-count summaries
    Keep the test on the existing customer flow rather than adding a new e2e scenario.

15. Update docs last.
    In `README.md`, add one short paragraph in the Web demo section that the public progress contract now includes additive step summaries suitable for customer rendering.
    In `docs/WEB_DEMO_README.md`, update the customer-flow expectations so reviewers know to look for:
    - one persistent progress card
    - collapsed completed steps
    - search-count summaries
    - no live streaming in this task

## 6. Testing Plan

- Backend unit tests: `tests/test_demo_progress.py` for step summary construction, count derivation, decline behavior, execution behavior, and fallback summaries.
- Backend unit tests: `tests/test_demo_api.py` for additive `progress.steps` serialization and validation.
- Backend integration tests: `tests/integration/test_demo_api_gateway.py` for start/get/clarify/replan/confirm/decline/AMAP progress-step behavior, including the family `5/5` search-count path.
- Frontend unit tests: `frontend/src/chat/ProgressStepperCard.test.tsx` for collapse/highlight rendering.
- Frontend unit tests: `frontend/src/chat/thread.test.ts` and `frontend/src/App.test.tsx` for thread ordering and persistent customer progress-card behavior.
- Frontend fixture/type tests: `frontend/src/api/demo.test.ts` for updated response-shape coverage.
- Frontend smoke test: `frontend/e2e/demo.spec.ts` for visible progress-card placement and disclosure behavior.
- Build verification: `npm --prefix frontend run build`.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_progress.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run test -- --run src/chat/ProgressStepperCard.test.tsx src/chat/thread.test.ts src/App.test.tsx src/api/demo.test.ts
npm --prefix frontend run build
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add customer progress stepper and search counts
```

Expected commands:

```bash
git status --short
git switch -c codex/customer-progress-stepper-and-search-counts-v0
git add backend/app/demo/schemas.py backend/app/demo/progress.py backend/app/demo/service.py
git add tests/test_demo_progress.py tests/test_demo_api.py tests/integration/test_demo_api_gateway.py
git add frontend/src/types/demo.ts frontend/src/chat/thread.ts frontend/src/chat/ConversationThread.tsx
git add frontend/src/chat/ProgressStepperCard.tsx frontend/src/chat/ProgressStepperCard.test.tsx
git add frontend/src/App.test.tsx frontend/src/chat/thread.test.ts frontend/src/api/demo.test.ts
git add frontend/src/styles.css frontend/e2e/demo.spec.ts
git add README.md docs/WEB_DEMO_README.md
git add docs/specs/079-customer-progress-stepper-and-search-counts-v0.md docs/plans/079-customer-progress-stepper-and-search-counts-v0-plan.md
git commit -m "feat: add customer progress stepper and search counts"
git push -u origin codex/customer-progress-stepper-and-search-counts-v0
```

The implementer must confirm `.env`, `frontend/dist/`, Playwright artifacts, `var/`, and unrelated local files are not staged.

If Task `078` has not merged upstream yet, create the new branch from the current `59c6744` HEAD. If Task `078` has already merged, create the branch from the merged equivalent of that commit.

## 9. Out-of-scope Changes

- Do not make `POST /demo/runs` asynchronous.
- Do not add polling, SSE, WebSockets, or background jobs.
- Do not change internal observability routes, schemas, or pages.
- Do not redesign the alternative-plan selection model or broader customer information architecture beyond the new progress card.
- Do not change benchmark grading, replay outputs, workflow routing, or Tool Gateway behavior.
- Do not add new database schema, Redis-only public dependencies, or new package dependencies.
- Do not commit generated artifacts, Playwright recordings, caches, secrets, or unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the contract-plus-consumer scope.
- [ ] `DemoRunSummary.progress.steps` is additive and public-safe.
- [ ] The family Mock World happy path exposes `已找到 5 个活动` and `已找到 5 个餐厅`.
- [ ] The customer page renders one persistent progress card from backend data rather than a log-like stream.
- [ ] The current step is highlighted.
- [ ] Completed steps are collapsed by default.
- [ ] The recommended plan remains summary-first and supporting evidence remains behind disclosures.
- [ ] Clarification, replan, confirm, decline, and AMap preview flows still behave correctly.
- [ ] No raw node names, raw tool names, IDs, trace metadata, or provider payload bodies leaked onto the customer surface.
- [ ] Required backend tests, frontend tests, build, and e2e smoke checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated local file was committed.

## 11. Handoff Notes

The implementer should report back with:

- Changed files.
- One example public progress payload for:
  - a normal `awaiting_confirmation` run
  - an `awaiting_clarification` run
  - a confirmed or completed run
- Verification commands and results.
- Confirmation that no async transport, polling route, SSE stream, or WebSocket was added.
- Commit hash.
- Push result.
- Any follow-up note that real mid-request live progress remains a later task on top of this richer contract and UI.
