# Spec: 082 Public Demo SSE Progress Stream v0

## 1. Goal

Add the first live public-safe planning stream to the Web demo backend through `POST /demo/runs/stream`.

After this task, the demo backend must be able to accept the same start-run request body as `POST /demo/runs`, emit incremental public-safe progress snapshots while the initial planning workflow is running, and finish the stream by sending one complete `DemoRunSummary`. This closes the current gap left intentionally open by Tasks `078` and `079`: public progress is already truthful and customer-safe, but it is still only available after the request finishes.

This task is an additive transport slice only. It must not replace the existing synchronous `POST /demo/runs` route, and it must not widen into a broader async execution architecture.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as observable by default, customer-safe on the public demo surface, and explicit that Redis/runtime progress exists for short-lived feedback while PostgreSQL remains the durable source of truth. `docs/NEXT_PHASE_ROADMAP.md` says the current default priority is still `M1. 评测与观测基础设施` before larger UX expansion.

This task fits that milestone directly:

- Task `004` already introduced a runtime progress-stream primitive.
- Task `022` established the public Web demo API surface.
- Task `043` established session/conversation persistence for demo flows.
- Task `078` introduced the public-safe additive `progress` contract on `DemoRunSummary`.
- Task `079` introduced the customer progress stepper based on that contract.
- `README.md` and `docs/WEB_DEMO_README.md` still explicitly say live mid-request transport is out of scope.

So the next narrow gap is no longer “what is the progress contract?” but “how does the public demo receive that progress before the initial request ends?” This task keeps the scope minimal by streaming only the initial start flow and reusing the existing public progress contract instead of inventing a second progress schema.

## 3. Requirements

- Use new task ID `082`.
- Add a new public route:
  - `POST /demo/runs/stream`
- The new route must accept the same request body schema as `DemoStartRunRequest`.
- The existing synchronous route:
  - `POST /demo/runs`
  must remain unchanged in request shape, response shape, and behavior.
- The new route must return `text/event-stream`.
- The new route must stream only the initial start-run planning flow.
- This task must not add streamed variants for:
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/clarify`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- The stream must use exactly these SSE event names:
  - `progress`
  - `summary`
  - `error`
- `progress` events must carry a public-safe progress snapshot only.
- `summary` events must carry one complete final `DemoRunSummary`.
- `error` events must carry one public-safe error payload and then close the stream.
- Every streamed event payload must include `event_index`, starting at `1` and increasing by `1` within that stream.
- `progress` event payloads must include:
  - `event_index`
  - `run_id`
  - `progress`
- `progress` must reuse the existing `DemoProgressSummary` contract:
  - `schema_version`
  - `current_stage`
  - `current_label`
  - `stage_history`
  - `steps`
- The stream must reuse the existing public progress stage enum only:
  - `understanding_request`
  - `planning_queries`
  - `searching_activities`
  - `searching_dining`
  - `checking_availability`
  - `building_itinerary`
  - `checking_route_time`
  - `reviewing_plan`
  - `ready_for_confirmation`
  - `executing_confirmed_actions`
- This task must not introduce any new public stream-only stage names.
- For the initial start-run flow, streamed `progress` events must never emit `executing_confirmed_actions`.
- Public progress emitted by the stream must stay aligned with the existing Task `078` / `079` rules:
  - use the same public labels
  - use the same public-safe summaries
  - use the same search-count rules
  - use the same clarification-stage fallback behavior
- Live streamed progress must be derived from the in-flight workflow state plus the same persisted tool-event evidence used by the public summary path.
- `execute_searches` may surface both search stages in one streamed snapshot when both activity and dining searches are already persisted by the time that node completes.
- `progress` events must be deduplicated at the public contract level:
  - if two consecutive in-flight states produce the same serialized `DemoProgressSummary`, only the first may be emitted
- `summary` must be emitted exactly once on successful terminal start-flow completion.
- For normal initial demo runs, `summary.summary.status` must end in one of:
  - `awaiting_confirmation`
  - `awaiting_clarification`
  - `failed`
- The final `summary` payload must be produced through the existing `DemoWorkflowService.build_summary(...)` readback path after the stream route persists the same demo/session metadata that the synchronous start route persists today.
- The final `summary` payload must be equivalent to a subsequent:
  - `GET /demo/runs/{run_id}`
  response for the same run.
- The new stream route must preserve existing start-run semantics for:
  - `read_profile`
  - Mock World defaulting
  - AMap read-only preview behavior
  - clarification behavior
  - plan version initialization (`v1`)
  - public redaction rules
- The stream must not expose:
  - raw workflow node names
  - raw tool names
  - trace IDs
  - session IDs
  - agent roles
  - node history
  - tool-event IDs
  - prompts
  - provider payload bodies
  - secret-like keys
- Existing `DemoRunSummary` and `DemoProgressSummary` JSON shapes must remain backward compatible for non-stream routes.
- Do not add new database tables, migrations, package dependencies, polling routes, WebSockets, or frontend consumer code in this task.
- Update `README.md` and `docs/WEB_DEMO_README.md` to document:
  - the new route
  - the three SSE event names
  - a sample `curl -N` start command
  - the fact that this is initial start-flow streaming only
  - the fact that reconnect/resume, polling, and other streamed routes remain later work

## 4. Non-goals

- Do not replace or deprecate synchronous `POST /demo/runs`.
- Do not add stream routes for clarify, replan, confirm, decline, or status refresh.
- Do not add frontend `EventSource`, fetch-stream, or React consumer changes.
- Do not add polling, WebSockets, background workers, durable job queues, or reconnect cursors.
- Do not guarantee replay/resume or continued execution after client disconnect in this v0 task.
- Do not change benchmark suites, replay harnesses, internal observability routes, or release-gate rules.
- Do not add a new public summary schema separate from `DemoRunSummary`.
- Do not expose raw workflow internals on the public route.
- Do not commit `.env`, API keys, tokens, secrets, generated runtime artifacts, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

`POST /demo/runs/stream` must accept the existing `DemoStartRunRequest` body unchanged:

```json
{
  "user_input": "This afternoon I want to go out with my wife and child for a few hours. Not too far.",
  "external_user_id": "web-demo-user",
  "display_name": "Web Demo User",
  "case_id": "web-demo",
  "selected_plan_index": 0,
  "read_profile": "mock_world"
}
```

### Outputs

SSE response only.

Event names:

- `progress`
- `summary`
- `error`

### Schemas

`progress` event payload:

```json
{
  "event_index": 3,
  "run_id": "11111111-1111-1111-1111-111111111111",
  "progress": {
    "schema_version": "public_demo_progress_v1",
    "current_stage": "checking_availability",
    "current_label": "正在检查营业与可用性",
    "stage_history": [
      "understanding_request",
      "planning_queries",
      "searching_activities",
      "searching_dining",
      "checking_availability"
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
        "status": "completed",
        "summary": "已找到 5 个餐厅"
      },
      {
        "stage": "checking_availability",
        "label": "正在检查营业与可用性",
        "status": "current",
        "summary": "已完成营业与可用性检查"
      }
    ]
  }
}
```

SSE frame format for that payload:

```text
event: progress
data: {"event_index":3,"run_id":"11111111-1111-1111-1111-111111111111","progress":{"schema_version":"public_demo_progress_v1","current_stage":"checking_availability","current_label":"正在检查营业与可用性","stage_history":["understanding_request","planning_queries","searching_activities","searching_dining","checking_availability"],"steps":[{"stage":"understanding_request","label":"正在理解需求","status":"completed","summary":"已理解出行目标与核心约束"},{"stage":"planning_queries","label":"正在规划查询","status":"completed","summary":"已整理活动与餐饮查询方向"},{"stage":"searching_activities","label":"正在查询游玩地点","status":"completed","summary":"已找到 5 个活动"},{"stage":"searching_dining","label":"正在查询餐厅","status":"completed","summary":"已找到 5 个餐厅"},{"stage":"checking_availability","label":"正在检查营业与可用性","status":"current","summary":"已完成营业与可用性检查"}]}}
```

`summary` event payload:

```json
{
  "event_index": 8,
  "summary": {
    "run_id": "11111111-1111-1111-1111-111111111111",
    "status": "awaiting_confirmation",
    "read_profile": "mock_world",
    "selected_plan_id": "22222222-2222-2222-2222-222222222222",
    "progress": {
      "schema_version": "public_demo_progress_v1",
      "current_stage": "ready_for_confirmation",
      "current_label": "推荐方案已准备好",
      "stage_history": [
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
        "checking_availability",
        "building_itinerary",
        "checking_route_time",
        "reviewing_plan",
        "ready_for_confirmation"
      ],
      "steps": []
    },
    "plan_version": {
      "version_number": 1,
      "version_label": "v1",
      "source_run_id": null,
      "source_selected_plan_id": null
    },
    "plans": [],
    "action_count": 0,
    "execution_status": null,
    "feedback_status": null,
    "error": null,
    "clarification": null
  }
}
```

`error` event payload:

```json
{
  "event_index": 1,
  "run_id": null,
  "message": "AMAP read path is not configured for this environment."
}
```

Notes:

- `summary.summary` must be the existing `DemoRunSummary` shape.
- `progress.progress` must be the existing `DemoProgressSummary` shape.
- No `id:` line, no replay cursor, and no reconnect token are added in this task.

## 6. Observability

This task does not add a new observability backend, new benchmark artifact, or new persistence layer.

It may reuse:

- in-flight workflow state
- existing persisted `ToolEvent` rows
- existing persisted `AgentRun`, `Plan`, and conversation/session data
- existing public progress projection logic

It must not add or expose through the new public stream:

- raw node history
- raw workflow node names
- raw tool names
- trace IDs
- session IDs
- prompt/debug fields
- provider-specific payload bodies
- action/tool event IDs
- secrets or secret-like keys

Documentation must state clearly that this is a public-safe stream on top of the existing demo path, not an internal trace feed.

## 7. Failure Handling

- Invalid request bodies must keep FastAPI’s existing validation behavior.
- If a valid stream request fails before any run is created, emit one `error` event with:
  - `run_id = null`
  - a public-safe message
  - then close the stream
- If a run reaches a normal terminal start-flow state (`awaiting_confirmation`, `awaiting_clarification`, or `failed`), emit one final `summary` event and close the stream.
- If an unexpected exception happens after a run ID exists but before final summary emission, emit one `error` event with the public-safe message and include `run_id` when available.
- If tool-event evidence is missing or malformed during streaming, the progress snapshot must fall back to generic public-safe summaries instead of failing the stream.
- If in-memory draft count is unavailable during `building_itinerary`, use the existing generic itinerary summary instead of failing.
- Consecutive duplicate progress snapshots must not produce duplicate `progress` events.
- Client disconnect handling is intentionally limited in this v0 task:
  - no reconnect cursor
  - no stream resume
  - no guarantee that an interrupted streamed request continues independently

## 8. Acceptance Criteria

- [ ] `docs/specs/082-public-demo-sse-progress-stream-v0.md` exists and matches this task.
- [ ] `docs/plans/082-public-demo-sse-progress-stream-v0-plan.md` exists and matches this task.
- [ ] `docs/specs` and `docs/plans` remain continuous and slug-matched through `082`.
- [ ] `POST /demo/runs/stream` exists.
- [ ] `POST /demo/runs/stream` accepts the same request body as `DemoStartRunRequest`.
- [ ] A normal Mock World start stream emits one or more `progress` events and ends with exactly one `summary` event.
- [ ] The first emitted public progress stage for a normal run is `understanding_request`.
- [ ] A normal Mock World start stream eventually emits `ready_for_confirmation` before the final `summary`.
- [ ] Consecutive duplicate `DemoProgressSummary` payloads are not emitted as separate `progress` events.
- [ ] Streamed `progress` payloads use only the existing public-safe stage enum and labels.
- [ ] Streamed `progress` payloads do not expose raw node names, raw tool names, trace IDs, session IDs, prompts, provider payloads, or secret-like fields.
- [ ] A clarification-required stream ends with one `summary` event where:
  - `summary.status == "awaiting_clarification"`
  - `summary.clarification` is present
  - `summary.plan_version.version_label == "v1"`
- [ ] A normal confirmation-ready stream ends with one `summary` event where:
  - `summary.status == "awaiting_confirmation"`
  - `summary.selected_plan_id` is non-null
  - `summary.progress.current_stage == "ready_for_confirmation"`
- [ ] The final streamed `summary` payload matches a subsequent `GET /demo/runs/{run_id}` payload for the same run.
- [ ] A valid streamed AMap start request with missing local configuration emits one `error` event with the same public-safe message used by the sync route.
- [ ] Existing synchronous `POST /demo/runs` behavior remains unchanged.
- [ ] No frontend consumer code is added in this task.
- [ ] No new polling route, WebSocket route, background worker, reconnect cursor, or database schema is added.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the new stream route, event names, sample usage, and remaining non-goals.
- [ ] Focused unit and integration verification commands below pass, or any environment blocker is reported clearly.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_progress.py tests/test_demo_streaming.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k stream -v
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
feat: add public demo sse progress stream
```

## 11. Notes for the Implementer

Keep this as the smallest additive live-transport slice.

Use the already-available local LangGraph stream capability to expose in-flight workflow state, but keep the public output strictly limited to the existing public-safe progress contract and the existing final `DemoRunSummary` contract.

The implementation should stop and split into a later task if it starts to require any of the following:

- streamed clarify / replan / confirm / decline endpoints
- frontend EventSource integration
- reconnect or replay semantics
- polling or WebSockets
- a background job system
- widening the public schema beyond `DemoProgressSummary` and `DemoRunSummary`
