# Spec: 084 Customer Start-Run SSE Progress v0

## 1. Goal

Add the first customer-frontend consumer for the existing public-safe SSE start route so the customer page can show real-time planning progress while the initial request is still running.

After this task, the initial customer start flow must call `POST /demo/runs/stream`, render the existing progress stepper card from streamed `progress` events, and then hand off cleanly to the final `DemoRunSummary` when the stream emits `summary`. The user should be able to see customer-safe milestones such as `正在理解需求`, `已找到 5 个活动`, and `已找到 5 个餐厅` during the live start flow instead of waiting for the final summary to arrive.

This task is intentionally narrow. It applies only to the initial customer start flow and must not widen into streamed clarify, replan, confirm, decline, polling, WebSockets, or backend contract changes.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as observable by default, customer-safe on the public demo surface, and built around a React/Vite Web UI talking to FastAPI workflow APIs. The blueprint also keeps Redis as a runtime layer and requires customer-safe progress rather than raw internal traces.

`docs/NEXT_PHASE_ROADMAP.md` says the default next-phase priority is still `M1. 评测与观测基础设施`, then `M2. 前端分离`. The relevant M1/M2 slices for this task are already partly complete:

- Task `079` introduced the persistent customer progress stepper derived from `DemoRunSummary.progress`.
- Task `082` introduced `POST /demo/runs/stream` with `progress`, `summary`, and `error` SSE events.
- Task `083` hardened ordered activity/dining search milestones inside the existing `progress` event type.

The remaining gap is now on the customer frontend side. The backend stream contract exists, but the customer page still starts runs through the synchronous `startRun()` path and only renders the persistent progress stepper after the final summary arrives. This task belongs primarily to `M2. 前端分离`, while directly closing the customer-consumer loop for the M1 public progress stream work already shipped in Tasks `082` and `083`.

## 3. Requirements

- Use new task ID `084`.
- Keep the existing backend route contract unchanged:
  - `POST /demo/runs/stream`
  - SSE event names `progress`, `summary`, and `error`
- The customer initial start flow in the frontend must switch from synchronous `POST /demo/runs` to streamed `POST /demo/runs/stream`.
- Clarify, replan, confirm, decline, and refresh/readback flows must stay on the existing synchronous request helpers.
- Because the stream route is `POST`, the frontend must use `fetch` plus `ReadableStream` parsing.
- Do not use browser `EventSource` for this task.
- Add frontend TypeScript types for the existing stream payloads:
  - `DemoRunStreamProgressEvent`
  - `DemoRunStreamSummaryEvent`
  - `DemoRunStreamErrorEvent`
- The frontend stream helper must parse only the existing event names:
  - `progress`
  - `summary`
  - `error`
- Unsupported or empty SSE frames may be ignored safely.
- While the start request is in flight and no valid `progress` event has arrived yet, the existing transient local `system_progress` row may still appear.
- After the first valid `progress` event arrives, the customer page must replace that transient row with one persistent live progress stepper card.
- The live progress stepper must reuse the same customer-safe stage contract already used by the persisted summary path:
  - `schema_version`
  - `current_stage`
  - `current_label`
  - `stage_history`
  - `steps`
- The live progress stepper must reuse the same customer-safe card behavior already introduced by Task `079`:
  - current step highlighted
  - completed steps hidden behind a closed-by-default disclosure
  - no raw log stream rendering
- The live progress card must update in place as later `progress` events arrive.
- The thread must not append one new assistant card per progress event.
- The happy-path live start flow must be able to surface customer-safe milestones such as:
  - `正在理解需求`
  - `已找到 5 个活动`
  - `已找到 5 个餐厅`
- The customer thread must never leave two persistent progress cards visible for the same in-flight start after the final `summary` has settled.
- On `summary`, the frontend must clear the transient live-progress state and render the normal run-derived thread items from the final `DemoRunSummary`.
- Existing post-summary UI behavior must remain intact:
  - clarification cards still appear for `awaiting_clarification`
  - plan summary cards still appear for `awaiting_confirmation`
  - result cards still appear for completed / failed / declined execution outcomes
- Existing selected-plan, clarification, replan, confirmation, and decline behavior must remain unchanged.
- Stream `error` events must surface the same localized user-facing error messages as the current sync API path when the message is already known.
- Network failures, missing response bodies, malformed JSON frames, or stream close without a final `summary` must fail soft:
  - show a customer-facing error banner
  - do not crash the page
  - do not leave a stuck live progress card behind
- Do not change any backend routes, backend Pydantic schemas, database tables, migrations, or benchmark contracts.
- Do not add polling, WebSockets, reconnect cursors, background workers, or new npm dependencies.
- Do not expose raw workflow node names, tool names, trace IDs, session IDs, prompts, or provider payload bodies on the customer page.
- Update `README.md` and `docs/WEB_DEMO_README.md` so they state:
  - the customer page now consumes `/demo/runs/stream` for the initial start flow
  - the implementation uses fetch-stream parsing because the route is `POST`
  - follow-up routes remain synchronous in this task

## 4. Non-goals

- Do not stream `clarify`, `replan`, `confirm`, `decline`, or `GET /demo/runs/{run_id}`.
- Do not add a new backend event type, route, schema, or migration.
- Do not add polling fallback, WebSockets, background async execution, or reconnect/resume support.
- Do not redesign the chat thread, plan summary cards, or internal observability pages.
- Do not reintroduce customer-visible raw run metadata, internal IDs, or internal trace surfaces.
- Do not add a new frontend dependency just to parse SSE.
- Do not commit `.env`, API keys, tokens, secrets, generated frontend artifacts, Playwright artifacts, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- Existing `DemoStartRunRequest` request body sent to `POST /demo/runs/stream`
- Existing SSE event payloads emitted by the backend:
  - `progress`
  - `summary`
  - `error`
- Existing `DemoProgressSummary` and `DemoRunSummary` contracts

### Outputs

Additive frontend-only interfaces:

- one new `startRunStream(...)` API helper
- one frontend-only stream callback contract for `progress` events
- one transient live progress-card projection that reuses the existing assistant progress-card shape

No backend schema or route shape changes are introduced.

### Schemas

Frontend stream event types should match the existing backend payloads exactly:

```ts
export type DemoRunStreamProgressEvent = {
  event_index: number;
  run_id: string;
  progress: DemoProgressSummary;
};

export type DemoRunStreamSummaryEvent = {
  event_index: number;
  summary: DemoRunSummary;
};

export type DemoRunStreamErrorEvent = {
  event_index: number;
  run_id: string | null;
  message: string;
};

export type DemoStartRunStreamHandlers = {
  onProgress?: (event: DemoRunStreamProgressEvent) => void;
};
```

Example `progress` event payload already supported by the backend:

```json
{
  "event_index": 4,
  "run_id": "11111111-1111-1111-1111-111111111111",
  "progress": {
    "schema_version": "public_demo_progress_v1",
    "current_stage": "searching_dining",
    "current_label": "正在查询餐厅",
    "stage_history": [
      "understanding_request",
      "planning_queries",
      "searching_activities",
      "searching_dining"
    ],
    "steps": [
      {
        "stage": "understanding_request",
        "label": "正在理解需求",
        "status": "completed",
        "summary": "已理解出行目标与核心约束"
      },
      {
        "stage": "planning_queries",
        "label": "正在规划查询",
        "status": "completed",
        "summary": "已整理活动与餐饮查询方向"
      },
      {
        "stage": "searching_activities",
        "label": "正在查询游玩地点",
        "status": "completed",
        "summary": "已找到 5 个活动"
      },
      {
        "stage": "searching_dining",
        "label": "正在查询餐厅",
        "status": "current",
        "summary": "已找到 5 个餐厅"
      }
    ]
  }
}
```

The customer page must project that payload into the same visible progress card structure already used after the final summary arrives. No second customer progress-card schema should be invented.

## 6. Observability

This task does not add a new observability backend or a new persistence layer.

It consumes only the already-sanitized public stream payload emitted by the backend. The frontend must not add console logging, debug dumps, or customer-visible diagnostics that expose:

- raw workflow node names
- raw tool names
- trace IDs
- session IDs
- agent roles
- prompt/debug fields
- provider payload bodies
- secret-like keys

Documentation should describe the customer page as a consumer of the existing public-safe SSE stream, not as an internal trace viewer.

## 7. Failure Handling

- If the streamed start request fails before the response is established, show the same localized connection error behavior used by the sync API helper.
- If the HTTP response is non-2xx, reuse the current sync API error-parsing and localization behavior.
- If the stream response is 2xx but has no readable body, fail with a customer-facing error instead of hanging forever.
- If an `error` SSE event arrives, localize known backend messages the same way the sync API helper already does, then stop the live flow.
- If a `progress` event is malformed or missing required fields, ignore that frame and keep waiting unless the stream terminates.
- If JSON parsing fails for a frame, treat the stream as failed and surface a generic customer-facing error.
- If the stream closes without a final `summary` event, surface a generic customer-facing error.
- If the final `summary` arrives without any prior `progress` event, the page must still render the final summary correctly.
- If the start flow errors after one or more live progress updates, clear the transient live progress card so the page does not look stuck in a running state.
- Clarify, replan, confirm, and decline flows must remain unaffected even if the new streamed start path fails.

## 8. Acceptance Criteria

- [ ] `docs/specs/084-customer-start-run-sse-progress-v0.md` exists and matches this task.
- [ ] `docs/plans/084-customer-start-run-sse-progress-v0-plan.md` exists and matches this task.
- [ ] `docs/specs` and `docs/plans` remain continuous and slug-matched through `084`.
- [ ] The customer initial start flow calls `POST /demo/runs/stream` instead of synchronous `POST /demo/runs`.
- [ ] Clarify, replan, confirm, decline, and readback flows still use their existing synchronous API helpers and request shapes.
- [ ] Before the first streamed `progress` event arrives, the existing temporary `system_progress` row may appear.
- [ ] After the first streamed `progress` event arrives, the customer page renders one persistent progress stepper card before the final summary is available.
- [ ] The live progress stepper updates in place rather than appending one new chat card per progress event.
- [ ] On the default Mock World happy path, the live progress card can surface customer-safe milestones including:
  - `正在理解需求`
  - `已找到 5 个活动`
  - `已找到 5 个餐厅`
- [ ] The live progress card uses the same collapsed completed-step disclosure behavior as the existing persisted progress card.
- [ ] When the stream emits its final `summary`, the page renders the existing plan/result surfaces correctly and does not leave duplicate persistent progress cards behind.
- [ ] A clarification-required start still ends on the existing clarification card path after the streamed start flow settles.
- [ ] A confirmation-ready start still ends on the existing plan-summary-first confirmation path after the streamed start flow settles.
- [ ] Known streamed error messages such as the AMap configuration error are localized the same way as sync API errors.
- [ ] Malformed or incomplete stream termination fails soft with a visible customer-facing error banner and without a React crash.
- [ ] No backend route, backend schema, migration, polling path, WebSocket path, or new npm dependency is added.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the customer-page stream consumption accurately.
- [ ] Focused frontend tests, build verification, and browser E2E commands below pass, or any environment blocker is reported clearly.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: add customer start-run sse progress
```

## 11. Notes for the Implementer

This task depends on the backend work from Tasks `082` and `083`. If the execution branch does not already include `/demo/runs/stream` plus ordered search milestones, stop and rebase or stack on top of that work before implementing the frontend consumer.

Keep the scope narrow:

- stream only the initial start flow
- parse the existing backend SSE contract as-is
- reuse the existing progress-card UI contract
- do not widen into broader async architecture

The implementer should stop and report back if the target branch does not already contain the `082/083` backend stream contract or if implementation starts to require streamed follow-up routes, polling, WebSockets, or backend schema changes.
