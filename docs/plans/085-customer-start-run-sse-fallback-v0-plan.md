# Plan: 085 Customer Start-Run SSE Fallback v0

## 1. Spec Reference

Spec file:

```text
docs/specs/085-customer-start-run-sse-fallback-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/customer-start-run-sse-progress-v0`.
- Working tree is clean.
- Current `HEAD` is `d7e390b feat: add customer start-run sse progress`.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `084`.
- The backend already exposes both:
  - `POST /demo/runs/stream`
  - `POST /demo/runs`
- The customer initial start flow currently calls `startRunStream(...)` only.
- The synchronous `startRun(...)` helper still exists and still returns the same `DemoRunSummary` contract.
- Current frontend tests explicitly treat stream failure as a terminal error banner rather than a fallback path.
- Existing App UI behavior already covers the “no live progress yet” state through the transient `system_progress` row, so no App state redesign should be necessary for this task.

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/src/shared/http.ts` - add additive frontend error classification metadata so stream transport failures can be distinguished from explicit stream business errors.
- `frontend/src/api/demo.ts` - keep the stream-first start helper, classify stream failures, and add one-time pre-progress fallback to synchronous `POST /demo/runs`.
- `frontend/src/api/demo.test.ts` - add focused unit coverage for fallback-eligible and fallback-ineligible start-run failures.
- `README.md` - document that the customer start flow is stream-first with automatic pre-progress sync fallback.
- `docs/WEB_DEMO_README.md` - update the runbook and expected-results text to describe the new fallback boundary and unchanged non-goals.

## 5. Implementation Steps

1. Confirm the current helper boundaries before editing:
   - `frontend/src/api/demo.ts` contains both `startRun(...)` and `startRunStream(...)`.
   - `frontend/src/App.tsx` already calls only `startRunStream(...)` for the initial start flow.
   - `frontend/src/App.tsx` already shows `system_progress` until a real live progress card or final summary arrives.
   Do not widen scope into App/UI changes unless the API-layer-only approach proves impossible.

2. In `frontend/src/shared/http.ts`, extend `FrontendApiError` additively with a classification field such as `kind`.
   - Keep `name = "DemoApiError"`.
   - Keep existing `message` and `status` behavior unchanged for current callers.
   - Default the new field so existing non-stream call sites do not need semantic rewrites.

3. In `frontend/src/api/demo.ts`, refactor the current stream-only logic into two layers:
   - one internal function that performs the raw `/demo/runs/stream` request and current SSE parsing behavior
   - one outer exported `startRunStream(...)` wrapper that decides whether to fallback to `startRun(...)`
   The exported function name and signature must stay unchanged.

4. In the raw stream layer inside `frontend/src/api/demo.ts`, classify errors precisely:
   - connection failure from `fetch(...)` => `kind = "connection"`
   - HTTP non-2xx response from `/demo/runs/stream` => `kind = "http"`
   - missing body, invalid JSON frame, malformed `summary`, or premature stream termination => `kind = "stream_protocol"`
   - explicit SSE `error` event => `kind = "stream_event"`
   Preserve current localized message behavior.

5. In the outer `startRunStream(...)` wrapper, track whether any valid streamed `progress` event has been emitted.
   - Forward real `progress` events to `handlers.onProgress`.
   - Set `sawProgress = true` only after a valid `DemoRunStreamProgressEvent` has been parsed.
   - Do not set it for malformed frames.
   - `summary` continues to resolve immediately without fallback.

6. Implement exact fallback eligibility in the outer wrapper:
   - fallback is allowed only when `sawProgress === false`
   - fallback is allowed for:
     - `kind === "connection"`
     - `kind === "stream_protocol"`
     - `kind === "http"` with `status === 404`
     - `kind === "http"` with `status === 405`
     - `kind === "http"` with `status >= 500`
   - fallback is not allowed for:
     - `kind === "stream_event"`
     - `kind === "http"` with `400-499` other than `404` and `405`
     - any error after `sawProgress === true`
   - when fallback is allowed, call existing `startRun(input)` exactly once with the original unchanged request body
   - do not recurse into another stream attempt
   - do not emit synthetic `onProgress` callbacks during sync fallback

7. Keep the rest of the client behavior unchanged:
   - `startRun(...)` remains the plain synchronous helper
   - `getRun`, `clarifyRun`, `replanRun`, `confirmRun`, and `declineRun` remain untouched except for any additive `FrontendApiError` constructor updates required by the new `kind` field
   - current localization map stays the source of truth for user-facing messages

8. Update `frontend/src/api/demo.test.ts` with focused fallback coverage. Add or adjust these exact cases:
   - `falls back to /demo/runs when /demo/runs/stream returns 404 before any progress`
   - `falls back to /demo/runs when the stream response has no body before any progress`
   - `does not fall back when the stream emits an explicit error event`
   - `does not fall back after one valid progress event if the stream later ends without summary`
   - `surfaces the sync failure if the fallback /demo/runs request also fails`
   These tests must assert request order, whether `/demo/runs` was called, and the final resolved/rejected outcome.

9. Rerun existing `frontend/src/App.test.tsx` without rewriting App behavior unless the API-layer fallback forces a contract change.
   - The existing “spinner first, then final summary” coverage should remain valid.
   - The existing “localized error banner when the streamed start fails” case should continue to cover unrecoverable helper failure, not be removed.

10. Update documentation:
    - in `README.md`, revise the Web demo API/customer-flow text so it says the initial start flow is stream-first and auto-falls back to sync start before any live progress has been received
    - in `docs/WEB_DEMO_README.md`, update:
      - overview
      - transport notes
      - remaining non-goals
      - expected results
      so the fallback boundary is explicit and follow-up routes are still called out as synchronous

11. Run the verification commands, review the diff for scope, then commit and push the new stacked task branch.

## 6. Testing Plan

- Unit tests:
  - `frontend/src/api/demo.test.ts`
    - fallback on stream `404`
    - fallback on `2xx` missing body
    - no fallback on explicit SSE `error`
    - no fallback after live progress has started
    - sync fallback failure bubbles correctly
- Existing UI regression tests to rerun unchanged:
  - `frontend/src/App.test.tsx`
- Smoke tests:
  - `npm --prefix frontend run build`
- Document review checks:
  - confirm `README.md` and `docs/WEB_DEMO_README.md` both say:
    - stream-first
    - sync fallback only before any valid live progress
    - no polling/WebSocket/reconnect
    - follow-up routes remain synchronous

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/api/demo.test.ts src/App.test.tsx
npm --prefix frontend run build
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
fix: add customer start-run stream fallback
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/customer-start-run-sse-fallback-v0
git add frontend/src/shared/http.ts frontend/src/api/demo.ts frontend/src/api/demo.test.ts
git add README.md docs/WEB_DEMO_README.md
git commit -m "fix: add customer start-run stream fallback"
git push -u origin codex/customer-start-run-sse-fallback-v0
```

The implementer must confirm `.env`, `frontend/.env`, `frontend/dist/`, Playwright artifacts, `var/`, and any other generated local files are not staged.

## 9. Out-of-scope Changes

- Do not modify backend routes, backend schemas, migrations, or persistence.
- Do not add fallback for clarify, replan, confirm, decline, or readback routes.
- Do not add polling, WebSockets, reconnect/resume, or background workers.
- Do not add a customer-visible fallback banner, badge, or transport-mode switch.
- Do not add synthetic live progress events for the sync fallback path.
- Do not retry sync start after any valid streamed `progress` event has already been shown.
- Do not add backend run-deduplication or session-resume logic in this task.
- Do not rewrite `frontend/src/App.tsx` unless the API-layer-only fallback approach is proven impossible.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] The initial customer start flow still attempts `/demo/runs/stream` first.
- [ ] The client falls back to `/demo/runs` only for eligible pre-progress stream failures.
- [ ] Explicit stream `error` events do not trigger sync fallback.
- [ ] Once live progress has started, later stream failure does not trigger sync fallback.
- [ ] Successful sync fallback returns the normal final summary without a customer-visible error banner.
- [ ] No synthetic live progress is emitted during sync fallback.
- [ ] Clarify, replan, confirm, decline, and readback flows remain unchanged.
- [ ] Required tests and build verification passed.
- [ ] Documentation reflects the new fallback boundary accurately.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Whether `frontend/src/App.tsx` stayed unchanged
- Whether fallback was verified for at least:
  - stream `404` before progress
  - missing body before progress
  - explicit stream `error` with no fallback
  - post-progress failure with no fallback
- Known limitations or follow-up tasks:
  - fallback still applies only to the initial start path
  - no backend dedupe/resume exists for the bounded pre-progress duplicate-run edge case
