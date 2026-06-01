# Plan: 084 Customer Start-Run SSE Progress v0

## 1. Spec Reference

Spec file:

```text
docs/specs/084-customer-start-run-sse-progress-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/public-demo-sse-search-count-milestones-v0`.
- Working tree is clean.
- Current `HEAD` is `06eccfc feat: emit sse search count milestones`.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `083`.
- The backend already provides `POST /demo/runs/stream` and emits only `progress`, `summary`, and `error` events.
- The backend already emits ordered search milestones inside `progress` events for the happy path.
- The customer frontend still starts runs through synchronous `startRun()` and therefore does not consume the existing SSE stream yet.
- The existing customer progress stepper component and thread projection already exist and should be reused instead of redesigned.

## 3. Files to Add

- `frontend/src/api/sse.ts` - browser-side SSE frame parser for `fetch` POST responses.
- `frontend/src/api/sse.test.ts` - focused unit coverage for frame parsing, chunk boundaries, and multi-line `data:` handling.

## 4. Files to Modify

- `frontend/src/types/demo.ts` - add TypeScript types for streamed `progress`, `summary`, and `error` payloads.
- `frontend/src/api/demo.ts` - add `startRunStream(...)`, reuse existing localization/error helpers, and keep the sync helpers intact.
- `frontend/src/App.tsx` - switch the initial start flow to the streamed helper and manage transient live progress state.
- `frontend/src/chat/thread.ts` - extract a reusable progress-card projection helper so live streamed progress and persisted run progress share one display shape.
- `frontend/src/api/demo.test.ts` - add client coverage for streamed start behavior and error localization.
- `frontend/src/App.test.tsx` - update the start-flow tests to mock the streamed helper and assert `spinner -> live card -> final summary`.
- `frontend/src/chat/thread.test.ts` - add focused coverage for projecting a live progress item into the thread.
- `frontend/e2e/demo.spec.ts` - adjust customer-flow assertions so they validate real streamed start behavior without becoming timing-flaky.
- `README.md` - document that the customer start flow now consumes `/demo/runs/stream`.
- `docs/WEB_DEMO_README.md` - update the runbook, expected results, and transport notes for the streamed customer start flow.

## 5. Implementation Steps

1. Create the new stacked task branch from the current clean `HEAD`:

   ```bash
   git switch -c codex/customer-start-run-sse-progress-v0
   ```

2. In `frontend/src/types/demo.ts`, add frontend-only stream payload types that mirror the existing backend contract exactly:

   - `DemoRunStreamProgressEvent`
   - `DemoRunStreamSummaryEvent`
   - `DemoRunStreamErrorEvent`

   Do not change `DemoProgressSummary` or `DemoRunSummary`.

3. Add `frontend/src/api/sse.ts` as a small transport helper with one responsibility: parse SSE frames from a `fetch` response body.

   The helper should:

   - accept a `ReadableStream<Uint8Array>`
   - decode bytes with `TextDecoder`
   - normalize `\r\n` and `\r` to `\n`
   - split frames on blank lines
   - join multiple `data:` lines with `\n`
   - keep the last partial frame buffered across chunks
   - ignore empty frames, comment lines, `id:`, and `retry:` lines
   - return parsed `{ event: string | null, data: string }` frames in order

   Keep it generic enough for this task, but do not overbuild reconnect/resume semantics.

4. In `frontend/src/api/sse.test.ts`, write parser tests before wiring the app:

   - one test with a single chunk containing one `progress` frame
   - one test where a frame is split across multiple chunks
   - one test with CRLF line endings
   - one test where `data:` spans multiple lines and rejoins correctly
   - one test proving ignored fields do not break parsing

5. In `frontend/src/api/demo.ts`, add a new streamed helper with this exact shape:

   ```ts
   export type DemoStartRunStreamHandlers = {
     onProgress?: (event: DemoRunStreamProgressEvent) => void;
   };

   export async function startRunStream(
     input: DemoStartRunRequest,
     handlers: DemoStartRunStreamHandlers = {},
   ): Promise<DemoRunSummary>
   ```

   Implementation rules:

   - POST to `/demo/runs/stream`
   - reuse the existing `API_BASE_URL`
   - keep the existing sync `startRun()` helper unchanged for non-stream callers
   - if the HTTP response is non-2xx, reuse the existing sync error parsing/localization path
   - if `response.body` is missing, throw a `FrontendApiError`
   - consume frames through `frontend/src/api/sse.ts`
   - on `progress`, JSON-parse the payload, minimally validate `run_id` + `progress`, then call `handlers.onProgress`
   - on `summary`, return `payload.summary`
   - on `error`, throw `FrontendApiError` using the same localized message mapping as the sync helpers
   - if the stream ends without a `summary`, throw a generic `FrontendApiError`

6. In `frontend/src/chat/thread.ts`, extract the current run-progress projection into a reusable helper, for example:

   ```ts
   export function buildProgressCardItem(
     runId: string,
     progress: DemoProgressSummary,
   ): AssistantProgressCardItem | null
   ```

   Use this helper both for:

   - existing `DemoRunSummary.progress` projection
   - new live streamed progress projection

   Keep the visible card shape unchanged:
   - same labels
   - same current-summary behavior
   - same completed-step disclosure behavior

7. Still in `frontend/src/chat/thread.ts`, widen `ProjectConversationThreadOptions.pendingAction` so it can accept either:

   - the existing `system_progress` row, or
   - a reusable `AssistantProgressCardItem`

   Do not create a separate live-only progress-card component or a second thread-item kind.

8. In `frontend/src/App.tsx`, keep `runAction(...)` for clarify/replan/confirm/decline and write a dedicated streamed start path for `handleStart()`.

   Exact behavior:

   - before calling the stream helper:
     - append the user message
     - set `requestState` to `starting`
     - clear `errorMessage`
     - clear any prior live start progress state
   - while `requestState === "starting"` and no progress event has arrived yet:
     - keep showing the existing `system_progress` row
   - when `startRunStream(..., { onProgress })` emits a progress event:
     - store `{ runId, progress }` in local state
     - replace the transient `system_progress` row with a projected progress stepper card
   - when the promise resolves with the final summary:
     - clear the transient live-progress state
     - upsert the final run entry into conversation history
     - update `run`, `selectedPlanId`, and `requestState` through the existing summary-driven path
     - clear the composer input
   - when the promise rejects:
     - clear the transient live-progress state
     - set `requestState = "error"`
     - show the localized error banner

   Do not change clarify/replan/confirm/decline behavior.

9. In `frontend/src/App.test.tsx`, replace the initial-start mocks from `startRun` to `startRunStream` and add explicit streamed-start tests.

   Add or update these cases:

   - `shows transient spinner before first progress, then swaps to live progress card before final summary`
   - `renders the final plan after the streamed summary without leaving duplicate persistent progress cards`
   - `shows localized error banner when streamed start emits an error`
   - keep the existing clarification, replan, confirmation, and AMap preview assertions intact, but make them use the new start helper where they begin from the initial start flow

10. In `frontend/src/api/demo.test.ts`, add focused coverage for the new streamed helper:

    - POST target is `/demo/runs/stream`
    - ordered `progress` callbacks are delivered before the resolved `summary`
    - an `error` event localizes known messages such as the AMap configuration error
    - a stream with no body or no terminal `summary` rejects cleanly

11. In `frontend/src/chat/thread.test.ts`, add one focused test for the new reusable progress-card projection path:

    - project a live `AssistantProgressCardItem` as the transient pending item
    - confirm it appears before later run-derived cards
    - confirm completed steps stay collapsed in the projected data

12. In `frontend/e2e/demo.spec.ts`, keep the existing high-level flows, but make the start-flow assertions stream-aware and timing-safe.

    Update the helpers so they assert:

    - immediately after clicking start, the page shows early progress feedback (`system-progress` or, once the first event arrives, the persistent progress card)
    - before the run reaches clarification or confirmation UI, a `progress-stepper-card` becomes visible
    - the final progress card still appears before the clarification card / plan card / result card as appropriate

    Keep the rest of the happy-path, clarification, replan, decline, and mobile assertions unchanged unless they depend directly on the old synchronous-start assumption.

13. Update docs:

    - in `README.md`, state that the customer initial start flow now consumes `/demo/runs/stream`
    - in `docs/WEB_DEMO_README.md`, update:
      - overview text
      - manual demo flow expectations
      - expected results
      - transport notes explaining why the frontend uses `fetch` streaming rather than `EventSource`

14. Run the verification commands, confirm only task-relevant files changed, then commit and push the stacked branch.

## 6. Testing Plan

- Unit tests:
  - `frontend/src/api/sse.test.ts` for chunk/frame parsing
  - `frontend/src/api/demo.test.ts` for streamed start helper behavior
  - `frontend/src/chat/thread.test.ts` for live progress-card projection
  - `frontend/src/App.test.tsx` for streamed start UI state transitions
- Build verification:
  - `npm --prefix frontend run build`
- Browser integration:
  - `npm --prefix frontend run e2e -- --project=desktop-chromium`
  - `npm --prefix frontend run e2e -- --project=mobile-chromium`
- Local stack prerequisites for E2E:
  - `docker compose up -d postgres redis`
  - `python -m alembic upgrade head`
- Documentation review:
  - confirm `README.md` and `docs/WEB_DEMO_README.md` describe the actual start-flow transport and unchanged non-goals

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/api/sse.test.ts src/api/demo.test.ts src/chat/thread.test.ts src/App.test.tsx
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run e2e -- --project=desktop-chromium
npm --prefix frontend run e2e -- --project=mobile-chromium
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add customer start-run sse progress
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/customer-start-run-sse-progress-v0
git add frontend/src/types/demo.ts frontend/src/api/demo.ts frontend/src/api/sse.ts frontend/src/App.tsx frontend/src/chat/thread.ts
git add frontend/src/api/sse.test.ts frontend/src/api/demo.test.ts frontend/src/App.test.tsx frontend/src/chat/thread.test.ts frontend/e2e/demo.spec.ts
git add README.md docs/WEB_DEMO_README.md
git commit -m "feat: add customer start-run sse progress"
git push -u origin codex/customer-start-run-sse-progress-v0
```

The implementer must confirm `.env`, `frontend/.env`, `frontend/dist/`, Playwright artifacts, `var/`, and any other generated local files are not staged.

## 9. Out-of-scope Changes

- Do not stream clarify, replan, confirm, decline, or readback routes.
- Do not modify backend routes, schemas, persistence, or benchmark contracts.
- Do not add polling, WebSockets, reconnect/resume logic, or background workers.
- Do not add a new npm dependency for SSE parsing.
- Do not redesign plan cards, clarification cards, or internal observability pages.
- Do not reintroduce customer-visible raw run metadata or internal trace fields.
- Do not change read-profile product scope as part of this task.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] The customer initial start flow uses `/demo/runs/stream`.
- [ ] Clarify, replan, confirm, and decline still use the existing sync flows.
- [ ] The customer page shows `spinner -> live progress card -> final summary` rather than waiting for the final summary only.
- [ ] The live progress card updates in place and does not append one new card per progress event.
- [ ] No duplicate persistent progress cards remain after the final summary settles.
- [ ] Known streamed errors are localized correctly.
- [ ] Required unit tests, build verification, and E2E checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

The implementer should report back with:

- the exact changed files
- verification commands run and their results
- whether the start flow now uses `fetch` stream parsing successfully on the customer page
- whether the live happy path visibly surfaced `正在理解需求`, `已找到 5 个活动`, and `已找到 5 个餐厅`
- commit hash
- push result
- any remaining limitation, which should still be that only the initial start route is streamed and all follow-up routes remain synchronous
