# Spec: 083 Public Demo SSE Search Count Milestones v0

## 1. Goal

Task `082` added `POST /demo/runs/stream` and proved that public-safe live progress can be transported through SSE. The remaining narrow gap is that the stream does not yet guarantee reviewer-visible search milestones as distinct streamed progress snapshots. Because the workflow currently performs activity and dining search inside one combined `execute_searches` node, later frontend work still cannot rely on the live stream to surface `已找到 X 个活动` and `已找到 X 个餐厅` as separate milestones.

After this task, the existing `progress` SSE event type must emit ordered search milestone snapshots derived from the same persisted `search_poi` tool-event evidence already used by Task `079`. This task must keep the `progress` / `summary` / `error` event contract unchanged, keep synchronous demo routes unchanged, and remain a small backend-only follow-up to Task `082`.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` requires WeekendPilot to stay observable by default, customer-safe on the public demo surface, and explicit that Redis is a runtime layer while PostgreSQL remains the durable source of truth. It also requires small, reviewable tasks and customer-safe progress behavior rather than raw internal traces.

`docs/NEXT_PHASE_ROADMAP.md` says the default priority is still `M1. 评测与观测基础设施` before broader UX expansion. This task fits that milestone because it hardens the public live-progress contract before any customer frontend stream consumption is attempted.

Relevant existing task outputs are already in place:

- Task `004` added the Redis runtime progress-stream primitive, but it is not the public contract for this task.
- Task `078` added the public-safe `DemoProgressSummary` contract.
- Task `079` added exact search-count wording derived from persisted `search_poi` tool events.
- Task `082` added `/demo/runs/stream` with `progress`, `summary`, and `error` events.

So the next smallest gap is not a new stream transport and not a frontend consumer. The next smallest gap is locking the search-count milestone behavior within the existing SSE contract.

## 3. Requirements

- Use new task ID `083`.
- Keep the existing public stream route:
  - `POST /demo/runs/stream`
- Keep the existing public SSE event names exactly:
  - `progress`
  - `summary`
  - `error`
- Do not add a new SSE event name such as `search_count`, `milestone`, or `tool_event`.
- Keep the existing synchronous route unchanged:
  - `POST /demo/runs`
- Keep the existing `DemoRunSummary` and `DemoProgressSummary` schemas unchanged.
- Search-count milestone emission must stay inside the existing `progress` event payload only.
- Search-count values must reuse the existing public count derivation from persisted `search_poi` tool events:
  - prefer `response_json.results` length when it is a list
  - fall back to integer `response_json.candidate_count`
- For a normal Mock World start stream, once activity search evidence is available, the stream must emit a `progress` event whose:
  - `progress.current_stage == "searching_activities"`
  - current-step summary is exactly `已找到 <N> 个活动` when count data is available
- For the same run, once dining search evidence is available, the stream must emit a later `progress` event whose:
  - `progress.current_stage == "searching_dining"`
  - current-step summary is exactly `已找到 <N> 个餐厅` when count data is available
- If both activity and dining search evidence are already persisted by the same streamed workflow state, the service must emit two ordered `progress` events in that same state-processing pass:
  - first the `searching_activities` milestone
  - then the `searching_dining` milestone
- The activity milestone must appear before any first `checking_availability` or later-stage `progress` event for the same run.
- The dining milestone must appear before any first `checking_availability` or later-stage `progress` event for the same run.
- Search milestone payloads must still reuse the existing public-safe labels, steps, and summaries from `DemoProgressSummary`.
- Search milestone emission must not require splitting `execute_searches` into multiple workflow nodes.
- Search milestone emission must not require a new database table, a new dependency, a new Redis public channel, or a new frontend contract.
- Existing duplicate-progress suppression must remain active across all emitted `progress` snapshots.
- The final `summary` event behavior from Task `082` must remain unchanged.
- The final streamed `summary` payload must remain equivalent to a subsequent:
  - `GET /demo/runs/{run_id}`
  response for the same run.
- Update `README.md` and `docs/WEB_DEMO_README.md` so they describe the ordered search milestone behavior inside the existing `progress` event type.

## 4. Non-goals

- Do not add a new SSE event type.
- Do not change the request body for `POST /demo/runs/stream`.
- Do not add frontend `EventSource`, fetch-stream, or React consumer work.
- Do not add streamed variants for `clarify`, `replan`, `confirm`, `decline`, or status refresh.
- Do not split `execute_searches` into separate workflow nodes for activity and dining.
- Do not switch the public stream to Redis-backed replay or polling.
- Do not expose raw tool names, raw node names, trace IDs, session IDs, prompts, or secret-like fields.
- Do not modify benchmark suites, internal observability routes, or unrelated workflow behavior.
- Do not commit `.env`, API keys, tokens, secrets, generated runtime artifacts, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- `POST /demo/runs/stream` with the existing `DemoStartRunRequest` body.
- In-flight workflow state from the existing LangGraph stream.
- Persisted `search_poi` tool events already written for the same run.

### Outputs

- Existing `progress` SSE events only.
- Existing `summary` SSE event only.
- Existing `error` SSE event only.

### Schemas

No new public Pydantic models are introduced. This task only strengthens the emission and ordering contract for existing `progress` event payloads.

Example activity-search milestone event:

```json
{
  "event_index": 3,
  "run_id": "11111111-1111-1111-1111-111111111111",
  "progress": {
    "schema_version": "public_demo_progress_v1",
    "current_stage": "searching_activities",
    "current_label": "正在查询游玩地点",
    "stage_history": [
      "understanding_request",
      "planning_queries",
      "searching_activities"
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
        "status": "current",
        "summary": "已找到 5 个活动"
      }
    ]
  }
}
```

Example dining-search milestone event from the same run:

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

Contract rules that remain unchanged:

- `summary` still carries the full existing `DemoRunSummary`.
- `error` still carries the existing public-safe error payload.
- No new top-level `count`, `milestone`, or `tool_event` field is added.

## 6. Observability

This task must not add a new observability backend, new storage layer, or new public trace feed.

It may reuse only:

- the existing in-flight workflow state
- the existing persisted `ToolEvent` rows
- the existing public progress projection rules from Tasks `078` and `079`

It must not expose through the public stream:

- raw workflow node names
- raw tool names
- trace IDs
- session IDs
- prompt/debug fields
- provider payload bodies
- action IDs or tool-event IDs
- secret-like keys

Documentation must make clear that the search milestones are still public-safe `progress` snapshots, not internal tool-event streaming.

## 7. Failure Handling

- If activity search evidence is present but count data is malformed, emit the activity milestone with the existing generic public-safe search summary instead of failing the stream.
- If dining search evidence is present but count data is malformed, emit the dining milestone with the existing generic public-safe search summary instead of failing the stream.
- If only one category has usable search evidence in a streamed state, emit only the available category milestone and continue normally.
- If no run ID exists yet, do not emit a `progress` event.
- If two candidate milestone snapshots would serialize identically to the previously emitted public snapshot, duplicate suppression must skip the duplicate.
- If the stream later reaches a normal terminal state, emit the existing final `summary` event and close the stream.
- If the streamed request fails unexpectedly, keep the existing Task `082` `error` event behavior unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/083-public-demo-sse-search-count-milestones-v0.md` exists and matches this task.
- [ ] `docs/plans/083-public-demo-sse-search-count-milestones-v0-plan.md` exists and matches this task.
- [ ] `docs/specs` and `docs/plans` remain continuous and slug-matched through `083`.
- [ ] `/demo/runs/stream` still uses only `progress`, `summary`, and `error` event names.
- [ ] No new public SSE event type is added.
- [ ] A normal Mock World start stream emits a `progress` event with `progress.current_stage == "searching_activities"` and current-step summary `已找到 5 个活动`.
- [ ] The same stream later emits a `progress` event with `progress.current_stage == "searching_dining"` and current-step summary `已找到 5 个餐厅`.
- [ ] In the happy path, the first `searching_activities` progress event appears before the first `searching_dining` progress event.
- [ ] In the happy path, both search milestone events appear before the first `checking_availability` or later-stage progress event.
- [ ] Existing duplicate-progress suppression still prevents repeated identical public snapshots.
- [ ] The final streamed `summary` payload still matches a subsequent `GET /demo/runs/{run_id}` payload for the same run.
- [ ] Existing synchronous `POST /demo/runs` behavior remains unchanged.
- [ ] No frontend consumer code is added in this task.
- [ ] No workflow-node split, no new dependency, no new polling route, and no new database schema is added.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` describe the ordered search milestone behavior accurately.
- [ ] Focused verification commands below pass, or any environment blocker is reported clearly.
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
feat: emit sse search count milestones
```

## 11. Notes for the Implementer

Keep this as the smallest backend-only follow-up to Task `082`.

The implementation should synthesize ordered search milestone snapshots from the existing combined `execute_searches` state plus persisted `search_poi` tool events. Do not widen this task into new event names, new stream routes, frontend stream consumption, or workflow DAG changes.

Stop and report back if implementation starts to require any of the following:

- a new SSE event type
- splitting `execute_searches` into separate workflow nodes
- frontend `EventSource` integration
- polling, WebSockets, reconnect semantics, or Redis-backed replay
- widening the public schema beyond the existing `DemoProgressSummary` and `DemoRunSummary`
