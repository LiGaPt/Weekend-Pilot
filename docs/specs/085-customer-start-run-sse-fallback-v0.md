# Spec: 085 Customer Start-Run SSE Fallback v0

## 1. Goal

Add an automatic frontend fallback from the initial customer start-run stream to the existing synchronous `POST /demo/runs` path when the stream transport is unavailable before any valid live progress has been received.

After this task, the customer page must remain stream-first for the initial start flow so reviewers still get live public-safe progress whenever `/demo/runs/stream` works. However, if the stream route is unavailable, the response body is unreadable, the SSE payload is malformed, or the stream terminates before any valid live progress or final summary is received, the frontend must retry the same start request through the already-existing synchronous `POST /demo/runs` route and continue the demo normally. This task is a stability closure only. It must not expand into polling, WebSockets, reconnect/resume, or broader async orchestration.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as customer-safe, observable by default, and explicitly keeps the Web UI on top of stable FastAPI workflow APIs. The blueprint also preserves a strict confirmation boundary before any write tools execute. That makes pre-confirmation fallback on the initial planning start path acceptable as long as the public contract stays unchanged.

`docs/NEXT_PHASE_ROADMAP.md` says the default next-phase priority is still `M1. 评测与观测基础设施`, followed by `M2. 前端分离`. This task is not a new roadmap-expansion slice. It is a convergence task immediately after Tasks `082`, `083`, and `084`:

- Task `082` added `POST /demo/runs/stream`.
- Task `083` added ordered live search milestones inside the stream.
- Task `084` switched the customer initial start flow to consume that stream.

That means the current customer start path now depends on `/demo/runs/stream` even though the older synchronous `POST /demo/runs` route still exists and is contract-compatible. This task belongs closest to `M2` because it only changes customer frontend transport behavior, but it should preempt fresh M1 work because it closes a newly introduced demo-stability gap on the primary public entry path.

## 3. Requirements

- Use new task ID `085`.
- Keep both backend routes unchanged:
  - `POST /demo/runs/stream`
  - `POST /demo/runs`
- The customer initial start flow must still attempt `POST /demo/runs/stream` first.
- The existing `startRunStream(...)` frontend helper signature must remain unchanged:
  - it still accepts `DemoStartRunRequest`
  - it still accepts optional `onProgress`
  - it still resolves to one `DemoRunSummary`
- The frontend must automatically retry the same start request through synchronous `POST /demo/runs` only when the stream attempt fails before any valid `progress` event or final `summary` event has been received.
- Fallback-eligible stream failures must be limited to transport/capability failures such as:
  - connection failure before or during the initial stream request
  - HTTP `404`
  - HTTP `405`
  - HTTP `5xx`
  - HTTP `2xx` with no readable body
  - malformed or invalid SSE payload before any valid `progress` or `summary`
  - stream termination before any valid `summary`, when no valid `progress` has been emitted yet
- Fallback must not happen when:
  - at least one valid `progress` event has already been delivered
  - a valid `summary` event has already been delivered
  - a valid stream `error` event has been delivered
  - the stream request fails with a non-fallback `4xx` request/business error
  - the synchronous fallback request itself fails
- The synchronous fallback request must reuse the exact same `DemoStartRunRequest` body fields:
  - `user_input`
  - `external_user_id`
  - `display_name`
  - `case_id`
  - `selected_plan_index`
  - `read_profile`
- If sync fallback succeeds, the frontend must return the `DemoRunSummary` from `/demo/runs` through the existing path without showing a customer-visible error banner.
- On sync fallback, the frontend must not fabricate live `progress` events or a fake persistent progress card.
- The existing temporary `system_progress` row may remain visible while the sync fallback request is in flight.
- Clarify, replan, confirm, decline, and readback flows must remain unchanged and synchronous.
- The customer-visible public summary contract must remain unchanged:
  - `DemoRunSummary`
  - `DemoProgressSummary`
  - `DemoRunStreamProgressEvent`
  - `DemoRunStreamSummaryEvent`
  - `DemoRunStreamErrorEvent`
- Do not change backend routes, backend schemas, database tables, migrations, benchmark contracts, or npm dependencies.
- Update `README.md` and `docs/WEB_DEMO_README.md` so they state:
  - the initial customer start flow is still stream-first
  - the frontend now automatically falls back to sync `POST /demo/runs` when stream transport fails before any valid live progress is received
  - follow-up routes remain synchronous
  - polling, WebSockets, reconnect/resume, and streamed follow-up routes remain out of scope

## 4. Non-goals

- Do not add fallback behavior for:
  - `POST /demo/runs/{run_id}/clarify`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
  - `GET /demo/runs/{run_id}`
- Do not add polling fallback, WebSockets, reconnect/resume, background jobs, or client-side replay cursors.
- Do not change the existing live progress stage enum, labels, or card behavior.
- Do not add a customer-visible “fallback mode” badge, banner, or debug notice.
- Do not add backend run-deduplication, session lookup, or resume-by-run-id logic in this task.
- Do not retry sync start after any valid live `progress` event has already been shown.
- Do not commit `.env`, API keys, tokens, secrets, build artifacts, Playwright artifacts, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- Existing `DemoStartRunRequest` sent first to `POST /demo/runs/stream`
- Existing optional stream progress callback:

```ts
export type DemoStartRunStreamHandlers = {
  onProgress?: (event: DemoRunStreamProgressEvent) => void;
};
```

### Outputs

The existing helper stays the customer-start entrypoint:

```ts
export async function startRunStream(
  input: DemoStartRunRequest,
  handlers: DemoStartRunStreamHandlers = {},
): Promise<DemoRunSummary>
```

Behavioral contract after this task:

- first try `/demo/runs/stream`
- if fallback is eligible before any valid `progress` or `summary`, retry once through `/demo/runs`
- resolve with the final `DemoRunSummary` from whichever path succeeds first
- emit `onProgress` only for real streamed `progress` events
- do not emit synthetic progress when sync fallback is used

### Schemas

Frontend error classification may be extended additively so fallback logic can distinguish transport failures from explicit stream business errors:

```ts
export type FrontendApiErrorKind =
  | "connection"
  | "http"
  | "stream_protocol"
  | "stream_event";

export class FrontendApiError extends Error {
  status: number;
  kind: FrontendApiErrorKind;
}
```

No backend request or response schema changes are introduced.

## 6. Observability

This task adds no new backend observability layer, no database persistence, and no public payload fields.

It may add frontend-internal error classification only for fallback control flow. That classification must remain implementation-internal and must not become customer-visible. The customer page still must not expose raw workflow node names, tool names, trace IDs, session IDs, prompts, provider payload bodies, or secret-like values.

Documentation must describe this as a transport-stability fallback on the public customer start path, not as a new internal tracing surface.

## 7. Failure Handling

- If the initial stream request fails with a connection error before any valid `progress` or `summary`, retry once through synchronous `POST /demo/runs`.
- If the initial stream request returns HTTP `404`, `405`, or `5xx` before any valid `progress` or `summary`, retry once through synchronous `POST /demo/runs`.
- If the stream request returns `2xx` but has no readable body, retry once through synchronous `POST /demo/runs`.
- If the SSE payload is malformed before any valid `progress` or `summary`, retry once through synchronous `POST /demo/runs`.
- If the stream closes before any valid `summary` and before any valid `progress`, retry once through synchronous `POST /demo/runs`.
- If a valid stream `error` event arrives, do not fallback; surface the localized customer-facing error exactly as today.
- If a valid `progress` event has already been emitted and the stream later fails, do not fallback; surface the current localized failure behavior and clear any stuck live-progress state through the existing UI path.
- If the synchronous fallback request fails, surface the synchronous failure and stop. Do not recurse or attempt a second fallback.
- This task intentionally accepts one bounded edge risk: if the backend accepted the stream start request but the client never received its first valid event, the sync fallback may create a second pre-confirmation run. That risk is acceptable in this task because initial demo runs do not execute write tools before confirmation, and preserving demo availability is higher priority than adding resume/deduplication infrastructure here.

## 8. Acceptance Criteria

- [ ] `docs/specs/085-customer-start-run-sse-fallback-v0.md` exists and matches this task.
- [ ] `docs/plans/085-customer-start-run-sse-fallback-v0-plan.md` exists and matches this task.
- [ ] `docs/specs` and `docs/plans` remain continuous and slug-matched through `085`.
- [ ] The customer initial start flow still attempts `POST /demo/runs/stream` first.
- [ ] When the stream attempt fails before any valid `progress` or `summary` because of an eligible transport/capability failure, the frontend retries the same request once through synchronous `POST /demo/runs`.
- [ ] Successful sync fallback returns the normal `DemoRunSummary` without showing a customer-visible error banner.
- [ ] Successful sync fallback does not fabricate live `progress` events or a fake persistent progress card.
- [ ] A valid stream `error` event still surfaces the localized error and does not trigger sync fallback.
- [ ] Once at least one valid streamed `progress` event has been emitted, later stream failure does not trigger sync fallback.
- [ ] Clarify, replan, confirm, decline, and readback flows remain unchanged and synchronous.
- [ ] No backend route, backend schema, migration, database table, benchmark contract, or npm dependency is added or changed.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the stream-first start path and the new pre-progress sync fallback boundary accurately.
- [ ] Focused frontend verification commands below pass.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
npm --prefix frontend run test -- --run src/api/demo.test.ts src/App.test.tsx
npm --prefix frontend run build
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
fix: add customer start-run stream fallback
```

## 11. Notes for the Implementer

Keep this task as an API-layer recovery slice, not a UI redesign and not a backend refactor.

The existing customer page already has acceptable behavior for “no progress yet”: it shows one transient `system_progress` row until either live progress arrives or a final summary settles. Use that existing behavior. Do not invent synthetic streamed progress for the sync fallback path.

The implementer should stop and report back if this task starts requiring any of the following:

- backend run-deduplication or resume logic
- fallback after live progress has already started
- fallback for clarify / replan / confirm / decline
- polling or WebSocket transport
- public schema changes
- an App-level state rewrite rather than a narrow API-client recovery change
