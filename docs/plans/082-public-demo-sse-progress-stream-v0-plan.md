# Plan: 082 Public Demo SSE Progress Stream v0

## 1. Spec Reference

Spec file:

```text
docs/specs/082-public-demo-sse-progress-stream-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/internal-observability-review-polish-v0`.
- `git status --short --branch` is currently clean.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `081`.
- The latest numbered task is still `081`.
- The latest task commit is `57ef4da feat: polish internal observability review surface`.
- Current `HEAD` is `073edca fix: polish customer chat localization`, which is a post-`081` follow-up fix rather than a new numbered task.
- Relevant current backend public-progress tasks already exist:
  - `078` public progress contract
  - `079` customer progress stepper
- `README.md` and `docs/WEB_DEMO_README.md` still say live mid-request transport is out of scope.
- Focused backend unit tests currently pass:
  - `python -m pytest tests/test_demo_progress.py tests/test_demo_api.py -q`
- Local `langgraph` already exposes `CompiledStateGraph.stream(...)`, and local inspection confirmed `stream_mode="values"` yields whole in-flight state snapshots after each node plus the initial input snapshot.
- No frontend code change is required for this task.

## 3. Files to Add

- `docs/specs/082-public-demo-sse-progress-stream-v0.md` - save the approved spec.
- `docs/plans/082-public-demo-sse-progress-stream-v0-plan.md` - save the approved plan.
- `backend/app/demo/streaming.py` - SSE event payload encoding, duplicate-snapshot suppression, and stream helper utilities.
- `tests/test_demo_streaming.py` - focused unit coverage for SSE frame formatting and streamed progress projection behavior.

## 4. Files to Modify

- `backend/app/api/demo.py` - add the new `POST /demo/runs/stream` route and return `StreamingResponse`.
- `backend/app/demo/service.py` - add the streamed start-run generator path and share final metadata/session persistence with the sync path.
- `backend/app/demo/progress.py` - extract shared progress-summary core and add a live in-flight projection helper.
- `backend/app/demo/schemas.py` - add stream event payload models.
- `backend/app/workflow/runner.py` - add a workflow-state streaming iterator and a public way to build a final `WeekendPilotWorkflowResult` from the terminal streamed state.
- `tests/test_demo_api.py` - assert the new route exists and that stream payload models validate.
- `tests/integration/test_demo_api_gateway.py` - add end-to-end SSE route tests.
- `README.md` - document the additive stream route and route-level scope.
- `docs/WEB_DEMO_README.md` - document event names, `curl -N` usage, and remaining non-goals.

## 5. Implementation Steps

1. Create a new branch from the current clean `HEAD` before editing:
   - `git switch -c codex/public-demo-sse-progress-stream-v0`
   Do not continue the `081` branch.

2. Save the approved spec and plan documents to:
   - `docs/specs/082-public-demo-sse-progress-stream-v0.md`
   - `docs/plans/082-public-demo-sse-progress-stream-v0-plan.md`

3. In `backend/app/demo/schemas.py`, add three new public stream payload models:
   - `DemoRunStreamProgressEvent`
   - `DemoRunStreamSummaryEvent`
   - `DemoRunStreamErrorEvent`
   Requirements:
   - each includes `event_index`
   - `progress` event includes `run_id` and `progress: DemoProgressSummary`
   - `summary` event includes `summary: DemoRunSummary`
   - `error` event includes `run_id: UUID | None` and `message: str`
   Do not alter existing `DemoRunSummary` or `DemoStartRunRequest`.

4. In `backend/app/demo/progress.py`, refactor the current logic into a shared core function that accepts explicit evidence instead of only an `AgentRun`.
   Use this shape:
   - one core builder that accepts:
     - `run_status`
     - `node_history`
     - `continuation_history`
     - `tool_events`
     - `plan_count`
     - `action_count`
     - `execution_status`
     - `feedback_status`
   - keep existing `build_demo_progress_summary(run, tool_events, ...)` as a wrapper around that core
   - add one live-stream helper, for example `build_live_demo_progress_summary(...)`, that:
     - reads current in-flight `node_history`
     - uses current `ToolEvent` rows for the run
     - uses in-memory draft count when persisted plan rows do not yet exist
   Preserve all Task `078` / `079` progress-stage, label, search-count, and summary rules.

5. Add `backend/app/demo/streaming.py`.
   Keep it focused on stream mechanics only:
   - JSON-safe SSE frame encoding helper:
     - `encode_sse_event(event_name: str, payload: BaseModel | dict[str, Any]) -> str`
   - helper to compare/deduplicate serialized `DemoProgressSummary` payloads
   - helper to derive the current public progress snapshot from one streamed workflow state plus current DB evidence
   Design constraints:
   - no raw node names in payloads
   - no raw tool names in payloads
   - no reconnect cursor
   - no retry / heartbeat logic

6. In `backend/app/workflow/runner.py`, add an additive streaming API without changing `run(...)`.
   Add two new public methods:
   - one iterator method that yields in-flight state snapshots from `graph.stream(..., stream_mode="values")`
   - one method that converts a terminal streamed state into `WeekendPilotWorkflowResult` by reusing the existing `_to_result(...)` logic
   Implementation details:
   - skip no logic in the runner about public progress or SSE formatting
   - keep the runner responsible only for workflow execution and state/result conversion
   - do not change existing `run(...)` consumers

7. In `backend/app/demo/service.py`, add a new streamed start method, for example `start_run_stream(request: DemoStartRunRequest) -> Iterator[str]`.
   It must:
   - resolve the same tool/world profiles as `start_run(...)`
   - construct the same workflow request with `auto_confirm=False`
   - iterate the new runner streaming API
   - ignore the initial input snapshot that has no `run_id`
   - after each streamed state:
     - derive `run_id`
     - load current `ToolEvent` rows for that run from the same session
     - derive current public progress snapshot through the new live-progress helper
     - emit a `progress` SSE frame only when that public snapshot changed from the previous emitted one
   - after the terminal streamed state:
     - build the final `WeekendPilotWorkflowResult`
     - load the run row
     - call the same conversation/session bootstrap path used by sync start:
       - `_ensure_conversation_baseline(...)`
       - `_persist_demo_metadata(...)`
       - `build_initial_plan_version_metadata()`
     - `commit()`
     - call `build_summary(run_id)`
     - emit one final `summary` SSE frame
   - on startup/runtime failure before summary:
     - rollback as needed
     - emit one `error` SSE frame with a public-safe message
   Keep all sync-path behavior intact.

8. In `backend/app/api/demo.py`, add:
   - `@router.post("/demo/runs/stream")`
   returning `StreamingResponse`.
   Requirements:
   - reuse the existing service builder
   - use `media_type="text/event-stream"`
   - add no `response_model`
   - do not route this endpoint through `_call(...)`, because the stream generator itself is responsible for emitting `error` events

9. In `tests/test_demo_streaming.py`, add focused unit tests for the new stream helpers.
   Add at least:
   - one test that `encode_sse_event("progress", payload)` produces:
     - `event: progress`
     - one JSON `data:` line
     - trailing blank line separator
   - one test that duplicate public snapshots are suppressed
   - one test that the live progress helper uses in-memory draft count for `building_itinerary` before persisted plan rows exist
   - one test that `execute_searches` can surface both search stages in one public snapshot

10. In `tests/test_demo_api.py`:
    - extend the route inventory test so `/demo/runs/stream` is present
    - add model-validation coverage for the new stream payload models
    Do not change unrelated schema tests.

11. In `tests/integration/test_demo_api_gateway.py`, add a small SSE parsing helper that:
    - reads `event:` / `data:` frames from the TestClient streamed response
    - JSON-decodes the payload
    Then add these focused integration tests:
    - `test_demo_run_stream_happy_path_emits_progress_then_final_summary`
      - call `POST /demo/runs/stream`
      - assert `200`
      - collect frames
      - assert at least one `progress` event
      - assert last event is `summary`
      - assert summary status is `awaiting_confirmation`
      - assert streamed summary equals subsequent `GET /demo/runs/{run_id}`
    - `test_demo_run_stream_clarification_path_ends_with_summary`
      - use the existing vague prompt fixture
      - assert final `summary.status == "awaiting_clarification"`
      - assert final `summary.clarification` is present
      - assert `plan_version.version_label == "v1"`
    - `test_demo_run_stream_amap_configuration_error_emits_error_event`
      - send `read_profile="amap"`
      - monkeypatch the same missing-config path already used by sync tests
      - assert the stream contains one `error` event with the same public-safe message

12. Update `README.md`.
    In the Web demo API section:
    - keep synchronous `POST /demo/runs` docs
    - add the new streamed route as additive
    - document:
      - `progress`
      - `summary`
      - `error`
    - add one `curl -N` example
    - say clearly that only the initial planning start path is streamed in this task

13. Update `docs/WEB_DEMO_README.md`.
    Add:
    - where the streamed route fits relative to the existing customer page
    - event-name semantics
    - a reviewer/developer usage example
    - explicit remaining non-goals:
      - no clarify/replan/confirm/decline SSE
      - no polling
      - no WebSockets
      - no reconnect/resume

14. Run the verification commands from this plan.

15. Review the final diff and confirm only task-relevant files are staged.

16. Commit and push the new `082` branch.

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_progress.py`
    - keep existing persisted-progress coverage green
    - add live-progress projection coverage only if it naturally belongs here
  - `tests/test_demo_streaming.py`
    - SSE frame formatting
    - duplicate snapshot suppression
    - live `building_itinerary` draft-count summary
    - combined search-stage snapshot behavior
  - `tests/test_demo_api.py`
    - route presence
    - stream payload model validation

- Integration tests:
  - `tests/integration/test_demo_api_gateway.py`
    - happy-path SSE stream with final summary parity to `GET /demo/runs/{run_id}`
    - clarification-path SSE stream
    - AMap startup error event behavior

- Smoke checks:
  - optional manual local check after backend start:
    ```bash
    curl -N -X POST http://127.0.0.1:8000/demo/runs/stream \
      -H "Content-Type: application/json" \
      -d "{\"user_input\":\"This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.\",\"external_user_id\":\"web-demo-user\",\"display_name\":\"Web Demo User\",\"case_id\":\"web-demo\"}"
    ```
  - confirm multiple `event: progress` frames appear before the final `event: summary`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_progress.py tests/test_demo_streaming.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k stream -v
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add public demo sse progress stream
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/public-demo-sse-progress-stream-v0
git add docs/specs/082-public-demo-sse-progress-stream-v0.md docs/plans/082-public-demo-sse-progress-stream-v0-plan.md
git add backend/app/api/demo.py backend/app/demo/service.py backend/app/demo/progress.py backend/app/demo/schemas.py backend/app/workflow/runner.py backend/app/demo/streaming.py
git add tests/test_demo_streaming.py tests/test_demo_api.py tests/integration/test_demo_api_gateway.py
git add README.md docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: add public demo sse progress stream"
git push -u origin codex/public-demo-sse-progress-stream-v0
```

The implementer must confirm `.env`, `var/`, Playwright artifacts, `dist/`, and other unrelated local files are not staged.

## 9. Out-of-scope Changes

- Do not touch `frontend/src/api/demo.ts`, `frontend/src/types/demo.ts`, `frontend/src/App.tsx`, or customer UI rendering.
- Do not change synchronous `POST /demo/runs` response shape.
- Do not add SSE for clarify, replan, confirm, decline, or refresh.
- Do not add polling, WebSockets, reconnect tokens, or durable replay semantics.
- Do not add a background job framework or worker queue.
- Do not add database schema, Alembic migrations, or new dependencies.
- Do not change benchmark, replay, or internal observability behavior.
- Do not widen public contracts to expose raw node/tool/debug data.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the `082` spec.
- [ ] The task stayed backend-only plus docs and tests.
- [ ] `/demo/runs/stream` exists and keeps `/demo/runs` unchanged.
- [ ] Streamed `progress` payloads reuse the existing public-safe progress contract.
- [ ] Streamed `progress` payloads do not expose raw workflow internals.
- [ ] Duplicate public snapshots are suppressed.
- [ ] Final streamed `summary` equals subsequent `GET /demo/runs/{run_id}` for the same run.
- [ ] Clarification-path streaming still returns `v1` and the existing clarification contract.
- [ ] Startup AMap config failure emits a public-safe `error` event.
- [ ] Docs describe the new route and its remaining non-goals accurately.
- [ ] Required tests passed.
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
- one sample happy-path event sequence (`progress ... progress ... summary`)
- one note confirming that this task intentionally did **not** add frontend consumption or reconnect/resume semantics
- any follow-up suggestion, which should likely be one of:
  - customer frontend consumption of `/demo/runs/stream`
  - streamed clarify/replan follow-up routes
  - durable disconnect/reconnect semantics
