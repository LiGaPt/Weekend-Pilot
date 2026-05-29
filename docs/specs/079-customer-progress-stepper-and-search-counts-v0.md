# Spec: 079 Customer Progress Stepper and Search Counts v0

## 1. Goal

Add the first customer-facing progress stepper/timeline to the chat-first Web demo by consuming the public progress contract instead of relying only on local request-state strings.

After this task, every successful public demo response must expose enough public-safe progress detail for the customer frontend to render one persistent enterprise-style progress card: the current step is highlighted, completed steps are collapsed by default, and search milestones can truthfully say `已找到 5 个活动` and `已找到 5 个餐厅` when that evidence exists. The final customer surface should still emphasize the recommended plan first and keep supporting evidence behind detail disclosures instead of turning progress into a raw log stream.

This task does **not** add live mid-request streaming. The customer page still updates only when it receives a `DemoRunSummary` response from the existing synchronous start, refresh, clarify, replan, confirm, or decline routes.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as observable by default, with Redis reserved for runtime progress streams and PostgreSQL plus persisted tool events remaining the durable source of truth. The blueprint also requires the Web demo to remain customer-safe and to avoid leaking internal traces, prompts, or raw debug data.

`docs/NEXT_PHASE_ROADMAP.md` says the current phase should prefer hardening evaluation and observability before larger UX expansion. Task `078` already delivered the public-safe stage contract for that purpose. The next narrow gap is now on the customer side:

- Task `077` moved the customer demo into one chronological chat surface.
- Task `078` added `DemoRunSummary.progress` as the first public-safe backend contract.
- The frontend still does not consume `run.progress`; it still renders only a local in-flight text row from `progressLabelForState(...)`.

This task therefore belongs primarily to `M2. 前端分离`, while directly closing the consumer loop for the `M1` public progress contract from Task `078`. It improves the customer surface without widening the internal observability surface and without introducing a new transport mechanism.

## 3. Requirements

- Keep Task `078` additive progress fields intact:
  - `schema_version`
  - `current_stage`
  - `current_label`
  - `stage_history`
- Extend `DemoProgressSummary` with one additive ordered `steps` array.
- Each `progress.steps[]` item must include exactly these fields:
  - `stage`
  - `label`
  - `status`
  - `summary`
- `progress.steps[].status` must use exactly these values:
  - `completed`
  - `current`
- `progress.steps` must be ordered by the existing public stage order and must include only the reached public-safe stages up to the current stage.
- The last item in `progress.steps` must always be the current stage and must use `status = "current"`.
- Earlier items in `progress.steps` must use `status = "completed"`.
- Build `progress.steps` from existing persisted evidence only:
  - `AgentRun.status`
  - `AgentRun.metadata_json["demo"]["initial_node_history"]`
  - `AgentRun.metadata_json["demo"]["continuation_history"]`
  - ordered `ToolEvent` rows for the run
  - existing plan rows already loaded by `DemoWorkflowService.build_summary(...)`
  - existing execution / feedback state already visible through the selected plan summary
- Do not add a new progress table, a new Alembic migration, a new route, or a Redis-only public dependency.
- Search-step summaries must use existing `search_poi` tool events and must remain public-safe:
  - detect category from `request_json.payload.category`
  - fall back to `request_json.payload.canonical_category`
  - count results from `response_json.results` when it is a list
  - fall back to `response_json.candidate_count` when it is an integer
- When search counts are available, the exact summary copy must be:
  - `已找到 <N> 个活动`
  - `已找到 <N> 个餐厅`
- When search counts are unavailable or malformed, the search-step summary must fall back safely to generic copy instead of failing the response.
- `building_itinerary` may summarize the number of public plans when available, using customer-safe copy such as `已生成 2 个候选方案`.
- Declined runs must keep `current_stage = ready_for_confirmation` for compatibility with Task `078`, but the step `summary` may use decline-aware customer-safe copy.
- Confirmed or completed runs must keep `current_stage = executing_confirmed_actions`, and the step `summary` may reflect action execution counts when available.
- The frontend TypeScript contract must include the additive `progress.steps` field.
- The customer page must render one persistent progress card for every run that has non-empty progress steps.
- The customer progress card must not be rendered as a growing log stream.
- The customer progress card must:
  - highlight the current step
  - hide completed steps behind a closed-by-default disclosure
  - show completed step labels plus summaries after expansion
  - keep customer-safe copy only
- While a request is still in flight and no updated `DemoRunSummary` has arrived yet, the existing local spinner row may remain as temporary feedback.
- Once a run summary arrives, the persistent progress card must be rendered from backend `run.progress`, not from local request-state heuristics alone.
- On `awaiting_clarification` runs, the progress card must appear before the clarification card and must show the last reached planning stage.
- On `awaiting_confirmation` runs, the progress card must appear before the recommended plan card and must end on `ready_for_confirmation`.
- On confirmed, completed, partially completed, skipped, failed, or declined runs, the progress card must remain available as the compact public process history above the later result content.
- Keep the existing Task `077` summary-first plan card behavior:
  - the recommended plan remains the primary visible content
  - timeline, activity/dining, route/feasibility, and pre-confirmation action details remain collapsed by default
- Do not expose raw workflow node names, raw tool names, event IDs, trace IDs, session IDs, provider payloads, prompts, or debug data on the customer surface.
- Update `README.md` and `docs/WEB_DEMO_README.md` to document the additive `progress.steps` contract and the new customer progress card behavior.
- State explicitly in docs that live mid-request transport is still out of scope and remains a later task.

## 4. Non-goals

- Do not make `POST /demo/runs` asynchronous.
- Do not add polling, SSE, WebSockets, or background workers.
- Do not change internal observability routes, schemas, or pages.
- Do not redesign the plan-selection model, benchmark suite surfaces, or internal reviewer controls.
- Do not expose raw candidate lists, raw tool-event bodies, raw workflow nodes, or internal trace data on the customer page.
- Do not change benchmark grading, replay contracts, workflow routing, or Tool Gateway behavior.
- Do not add new database schema, new package dependencies, or new public API routes.
- Do not commit `.env`, secrets, generated runtime artifacts, Playwright artifacts, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

This task depends on existing persisted demo and workflow evidence only:

- `AgentRun.status`
- `AgentRun.metadata_json["demo"]["initial_node_history"]`
- `AgentRun.metadata_json["demo"]["continuation_history"]`
- ordered `ToolEventRepository.list_for_run(run_id)` results
- plan rows already loaded by `DemoWorkflowService.build_summary(...)`
- existing execution / feedback state from selected plan summary

No new user request field, no new frontend request field, and no new environment variable is required.

### Outputs

Additive public API output:

- `DemoRunSummary.progress.steps`

Additive frontend internal output:

- one new thread item kind for a persistent customer progress card derived from `run.progress`

No new route is added.

### Schemas

`DemoRunSummary.progress` should follow this shape after this task:

```json
{
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
        "status": "completed",
        "summary": "已完成营业与可用性检查"
      },
      {
        "stage": "building_itinerary",
        "label": "正在组合行程",
        "status": "completed",
        "summary": "已生成 2 个候选方案"
      },
      {
        "stage": "checking_route_time",
        "label": "正在计算路线与时间",
        "status": "completed",
        "summary": "已完成路线与时间测算"
      },
      {
        "stage": "reviewing_plan",
        "label": "正在复核方案",
        "status": "completed",
        "summary": "已完成推荐方案复核"
      },
      {
        "stage": "ready_for_confirmation",
        "label": "推荐方案已准备好",
        "status": "current",
        "summary": "推荐方案已准备好"
      }
    ]
  }
}
```

Frontend internal thread projection should introduce one additive card-like item that carries:

- `runId`
- `currentStage`
- `currentLabel`
- `currentSummary`
- `completedSteps`
- `collapsedByDefault = true` for the completed-step section

Notes:

- `steps` is a public-safe summary for customer rendering, not a raw workflow trace.
- `stage_history` remains for backward compatibility and lightweight readback.
- `steps` must not include raw tool names, raw event IDs, or raw payload fragments.

## 6. Observability

This task consumes existing persisted workflow evidence and produces one richer public-safe derived summary. It does not add a new telemetry backend.

It may read:

- persisted demo metadata
- persisted run status
- persisted tool-event rows
- existing plan row count
- existing execution and feedback summaries

It must not expose through `progress.steps` or the customer card:

- raw `node_history`
- raw workflow node names
- raw tool names
- event IDs
- trace IDs
- session IDs
- provider-specific payload bodies
- prompts
- secrets
- raw debug fields

This task must also keep the progress snapshot reconstructable from durable data only. It must not require Redis-only ephemeral progress keys for customer readback.

## 7. Failure Handling

- If `initial_node_history` is missing or malformed, build the safest possible `steps` list from existing fallback stage logic instead of failing the demo response.
- If `continuation_history` is missing or malformed, do not assume execution; keep the existing non-execution fallback behavior.
- If search tool events are missing, malformed, or lack usable count data, use generic search summaries instead of count summaries.
- If a search tool event has an unknown or unsupported category, ignore that event for public search-count summaries.
- If plan count is unavailable, `building_itinerary` must use a generic summary instead of failing the response.
- If `progress.steps` is missing or malformed at runtime on the frontend, the customer page must fail soft:
  - do not crash the page
  - keep the existing local pending row behavior while in flight
  - omit the persistent progress card or fall back to the coarsest customer-safe summary available
- Declined runs must not be misreported as `executing_confirmed_actions`.
- AMap preview runs must continue to stop before confirmation and must not be misreported as executed.
- Existing clarification, replan, confirm, decline, and refresh flows must keep working even if the richer progress summary falls back.

## 8. Acceptance Criteria

- [ ] `docs/specs/079-customer-progress-stepper-and-search-counts-v0.md` exists and matches this task.
- [ ] `docs/plans/079-customer-progress-stepper-and-search-counts-v0-plan.md` exists and matches this task.
- [ ] The repository remains continuous and slug-matched through `078`, and this task uses new task ID `079`.
- [ ] `DemoRunSummary.progress` still includes `schema_version`, `current_stage`, `current_label`, and `stage_history`.
- [ ] `DemoRunSummary.progress` now also includes a non-empty additive `steps` array on all successful public demo route responses.
- [ ] Every `progress.steps[]` item includes `stage`, `label`, `status`, and `summary`.
- [ ] `progress.steps[].status` uses only `completed` or `current`.
- [ ] A normal Mock World family run that reaches `awaiting_confirmation` returns progress summaries that include:
  - `已找到 5 个活动`
  - `已找到 5 个餐厅`
- [ ] A normal `awaiting_confirmation` run ends with `ready_for_confirmation` as the current step.
- [ ] A clarification run still returns the existing `clarification` object and also returns a progress card payload ending at the last reached planning stage.
- [ ] A confirmed or completed run ends with `executing_confirmed_actions` as the current step.
- [ ] A declined run keeps `current_stage = ready_for_confirmation` and does not advance into execution.
- [ ] The customer page renders one persistent progress card from backend `run.progress` once a run summary is available.
- [ ] The current step is visually highlighted on the customer page.
- [ ] Completed steps are hidden behind a closed-by-default disclosure.
- [ ] The customer page no longer treats the persistent progress view as a log-like message stream.
- [ ] The recommended plan remains the primary visible content, while timeline, activity/dining, route/feasibility, and action evidence stay behind detail disclosures.
- [ ] No raw workflow node names, raw tool names, event IDs, trace IDs, session IDs, prompts, or provider payloads are exposed on the customer surface.
- [ ] Existing public request bodies and route shapes remain unchanged.
- [ ] No polling route, SSE stream, WebSocket, background worker, or new database schema is added.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the additive `progress.steps` contract and the explicit non-goal that live mid-request transport remains a later task.
- [ ] Focused backend tests, frontend tests, and frontend build verification commands below pass, or any environment blocker is reported clearly.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated local file is committed.

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: add customer progress stepper and search counts
```

## 11. Notes for the Implementer

Keep this task as the smallest contract-plus-consumer slice that turns Task `078` into a real customer-facing progress experience.

The key constraints are:

- no live transport
- no raw log stream UI
- no internal observability leakage
- no widened workflow or routing scope

If implementation starts to require async start, polling, SSE, WebSockets, or a broader redesign of plan selection, stop and split that work into a later follow-up task instead of widening `079`.
