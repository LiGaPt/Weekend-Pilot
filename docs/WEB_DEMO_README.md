# Web Demo Runbook

## Overview

The Web demo is the primary MVP review path for WeekendPilot. It runs the React/Vite frontend against the FastAPI demo API, defaults to the Mock World provider, pauses before write tools, and continues execution only after explicit confirmation. The visible demo copy across the current six public Mock World scenario chips is localized in Chinese for competition review.

For hackathon submission and recording, use [docs/submission/OVERVIEW.md](./submission/OVERVIEW.md) as the primary package index, then keep this runbook as the detailed operational reference.

Current version scope: `V1.5 baseline / V2 Integrity candidate`. The next `V2 Integrity Edition` work should focus on benchmark completeness, memory governance, observability, and recovery auditability; AMap remains an API-only read-only preview outside the customer UI main path and outside formal benchmark runs.

## Submission / Recording Quick Start

Before recording, warm up the public happy path once and keep the browser tab order fixed as `5173 -> 5174`.

Run these fixed commands from the repo root before you start recording:

```bash
python scripts/demo_preflight.py
python scripts/show_submission_evidence.py
```

If you also want to show the API-only AMap read preview, run:

```bash
python scripts/demo_amap_preview.py
```

Recording defaults:

- keep the terminal at the repo root
- do not record service startup logs
- open `运行信息` on `5173` when you need to 复制 `run_id`
- after the public flow, switch to `5174`, paste the copied `run_id`, and show `Trace Summary` plus `Benchmark Artifacts`
- benchmark breadth should be demonstrated with the prepared evidence summary and the `Benchmark Summary` hero; 不需要现场等待长时间 benchmark 执行

The customer page at `5173` is now chat-first:

- the first screen shows one primary composer plus six fixed Mock World scenario chips: `亲子`, `朋友`, `单人`, `情侣`, `雨天`, and `预算`
- user requests, system progress, clarification prompts, replans, and final execution feedback appear in one chronological conversation stream
- once a run summary arrives, the transient system-progress row gives way to one persistent progress stepper with the current step highlighted and completed steps hidden behind a disclosure by default
- the assistant shows a recommended plan summary first, then reveals timeline, activity/dining, route/feasibility, and confirmation-action details only when the reviewer expands them
- `run_id`, read path, visible plan version, and refresh now live behind a closed-by-default `运行信息` disclosure instead of a default-visible inspector

The public page now keeps the customer start path on `Mock World` and exposes six fixed scenario chips that map to canonical prompts plus explicit `mock_world_profile` values. Those chips are start-only, they only fill the composer, and they do not auto-submit.
This task does not restore a customer-side AMap selector. Live `AMap` preview remains API-only and read-only for local review.

The public demo API now also supports `POST /demo/runs/{run_id}/clarify` for clarification replies and `POST /demo/runs/{run_id}/replan` for follow-up replanning. A vague start request, or a bounded recovery path that needs an explicit user tradeoff, can stop in `awaiting_clarification` with `plans = []`, `selected_plan_id = null`, and a compact `clarification` summary that contains the public follow-up prompt plus the missing supported fields.
An additive backend stream now also exists at `POST /demo/runs/stream`. It covers only the initial planning start request, reuses the same public-safe progress contract, and is now the transport used by the customer page for the initial start flow. Because this route is a `POST`, the frontend consumes it with `fetch` plus `ReadableStream` SSE parsing rather than browser `EventSource`. If that stream transport fails before any valid live `progress` event is received, the frontend now retries the same start request once through synchronous `POST /demo/runs`. For the default Mock World happy path, that stream now emits ordered search milestones inside the existing `progress` event type: first `searching_activities`, then `searching_dining`, before later stages such as `checking_availability`. Clarify, replan, confirm, decline, and run readback remain synchronous in this task.
Every public `DemoRunSummary` includes a compact `plan_version` object: the initial run starts at `v1`, and each follow-up replan returns a new `run_id` with the next visible version label. Clarification-only turns do not advance that visible version. A source run that ends in `awaiting_clarification` stays at `v1`, and the first clarification continuation that produces real plans also remains at `v1`. The internal conversation session is reused, but that session state remains internal and is still not exposed in `DemoRunSummary`.
Every public `DemoPlanPreview` now includes `action_manifest`, a stable execution-preview summary with this shape:

```json
{
  "source": "proposed_actions | confirmed_actions | none",
  "action_count": 1,
  "actions": [
    {
      "action_ref": "draft_1_action_1",
      "execution_order": 1,
      "action_type": "reserve_restaurant",
      "target_id": "restaurant_light_001",
      "payload_preview": {
        "party_size": 3
      },
      "reason": "Confirm to lock dinner seating."
    }
  ]
}
```

`source = "proposed_actions"` is used for safe pre-confirmation previews, `source = "confirmed_actions"` is used after confirmation when persisted confirmed actions exist, and `source = "none"` is used when no valid public action preview is available.

Every successful public `DemoRunSummary` now also includes an additive `progress` object:

```json
{
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
  ]
}
```

The `progress` payload now also includes additive `steps[]` entries. Each step contains `stage`, `label`, `status`, and `summary`, which is the customer-safe contract for the stepper UI. The default Mock World family path now surfaces public milestones such as `已找到 5 个活动` and `已找到 5 个餐厅` after reviewers expand the completed-step disclosure.

That snapshot is reconstructed from persisted workflow node history, ordered tool events, plan rows, and demo continuation history only.

The new streamed start route uses these event names only:

- `progress`: one public-safe `DemoProgressSummary`
- `summary`: one final `DemoRunSummary`
- `error`: one public-safe startup/runtime failure message

For reviewer expectations on the default Mock World happy path, the first search-count `progress` milestone should say `已找到 5 个活动`, the next should say `已找到 5 个餐厅`, and both should appear before the first availability-check milestone.

Reviewer/developer SSE example:

```bash
curl -N -X POST http://127.0.0.1:8000/demo/runs/stream \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.\",\"external_user_id\":\"web-demo-user\",\"display_name\":\"Web Demo User\",\"case_id\":\"web-demo\",\"selected_plan_index\":0,\"read_profile\":\"mock_world\"}"
```

Remaining non-goals for this transport slice:

- no clarify/replan/confirm/decline SSE routes
- no polling fallback
- no WebSocket transport
- no reconnect or resume cursor
- no streamed follow-up routes

No external local-life provider, map provider, LangSmith upload, API key, token, or secret is required for the default Mock World path.

## Prerequisites

- Python environment with this package installed.
- Node.js and npm for the frontend.
- Docker Compose for local PostgreSQL and Redis.
- Alembic migrations applied before API or E2E runs.
- Chromium installed through Playwright before browser tests.

Playwright does not start Docker and does not run migrations. Keep these prerequisites explicit so failures are easy to diagnose.

If you want to exercise the API-only AMAP read preview locally, set `AMAP_MAPS_API_KEY` in local `.env` and call the demo API with `read_profile="amap"`. That key is not required for Mock World runs, benchmark runs, or the default test suite.

## Backend Setup

Install backend dependencies:

```bash
python -m pip install -e ".[dev]"
```

Start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

Apply migrations:

```bash
python -m alembic upgrade head
```

Start the API:

```bash
uvicorn backend.app.main:app --reload
```

The backend listens at `http://127.0.0.1:8000`.

## Frontend Setup

Install frontend dependencies:

```bash
npm --prefix frontend install
```

Start the customer surface:

```bash
npm --prefix frontend run dev
```

Start the internal review surface in a second terminal:

```bash
npm --prefix frontend run dev:internal
```

Open the customer surface at `http://127.0.0.1:5173/`.
Open the internal review surface at `http://127.0.0.1:5174/`.

The frontend defaults to `http://127.0.0.1:8000` for API calls. To override it locally, create `frontend/.env` with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not commit local `.env` files.

## Internal Review Surface

The repository now includes a separate internal observability review page for reviewers and developers:

- page: `http://127.0.0.1:5174/`
- backend endpoint: `GET /internal/runs/{run_id}/observability`

Paste a `run_id` from the public demo flow into the internal surface to inspect the internal workflow summary, including timing, node history, agent roles, observability status, and benchmark artifact context for benchmark-backed runs. The customer-facing demo at `http://127.0.0.1:5173/` stays customer-safe and no longer renders those internal fields.

The internal review page now also shows sanitized tool-event and action-ledger detail panels, a real benchmark-artifact panel populated from persisted run metadata, and a real recovery-path panel populated from persisted bounded recovery metadata. For benchmark-backed recovery runs, the page also shows the persisted benchmark case report path as replay input context. Replay execution and replay report browsing remain separate tooling.

For the canonical reviewer closure flow, run `python scripts/run_recovery_replay_review.py` from the repo root. It emits the source benchmark `run_id` and the written source benchmark report path for `family_route_failure_v1`, and those two values can be cross-checked directly against this internal observability surface to confirm that `benchmark_artifact_summary.report_path` and `recovery_path_summary.replay_source.benchmark_report_path` both point to the same source report.

Generic recovery replay selectors are now also available for engineering verification: `--case-id <case_id>` runs one recovery-capable case, and `--suite-id recovery_focused` runs the registered recovery suite. Those additive selectors are not a new reviewer UI workflow and do not replace the canonical family default alias used by the current review package.

The internal review surface now also loads `GET /internal/benchmarks/release-gate-v1/summary` on page load and renders a dedicated `Benchmark Summary` panel even before a run ID is entered. That panel is intentionally scoped to the canonical latest alias `var/formal-benchmarks/latest-release_gate_v1-run-report.json`.

Reviewer scan order on `5174` should now be:

1. Start with the release-gate hero in `Benchmark Summary`.
2. Check status, overall score, and pass/fail/error counts first.
3. Copy the canonical latest alias directly from the page when you need to cite the benchmark report path.
4. Load a specific `run_id`.
5. Inspect `Trace Summary`, then `Benchmark Artifacts`, then `Recovery Visualization`.

## Richer Web UI V1 Reviewer Flow

For the V1 richer UI closure, use `docs/RICHER_WEB_UI_V1_CHECKLIST.md` as the canonical acceptance checklist. The shortest reviewer sequence is:

1. On `5173`, verify planning and confirmation with a Mock World run.
2. Confirm the selected plan and verify the customer-facing `执行时间线`.
3. Copy the resulting `run_id`.
4. On `5174`, verify the release-gate hero in `Benchmark Summary` before loading any run.
5. Confirm the page exposes the canonical latest alias `var/formal-benchmarks/latest-release_gate_v1-run-report.json` and a direct copy action for that path.
6. Load the copied `run_id` and verify `Trace Summary`.
7. Review `Benchmark Artifacts`, making sure the current run report path is distinct from the canonical latest release-gate alias path.
8. Run `python scripts/run_recovery_replay_review.py`, then load the emitted recovery `run_id` and verify `Recovery Visualization`, including the replay report copy action.

## Manual Demo Flow

### Happy Path

1. Open `http://127.0.0.1:5173`.
2. Either enter an equivalent request into the main composer or click the `亲子` scenario chip to populate it.
3. Click `开始规划`.
4. Confirm the conversation stream first shows your user message and early progress feedback. Depending on timing, this may appear first as the transient in-chat system progress row or directly as the persistent progress stepper card.
5. Confirm the run reaches `awaiting_confirmation`, any transient row disappears, and one persistent progress stepper appears above the plan card.
6. Expand the completed-step disclosure and verify public-safe evidence such as `已找到 5 个活动` and `已找到 5 个餐厅`.
5. Confirm the run reaches `awaiting_confirmation` and the assistant shows `推荐方案摘要`.
6. Confirm the selected plan first appears as a summary card rather than a fully expanded panel.
7. Confirm `run_id`, `action_count`, raw `execution_status`, and raw `feedback_status` are not visible by default.
8. Expand `时间线`, `活动与餐厅`, `路线与可执行性`, and `确认前动作` only as needed to review details.
9. Open `运行信息` only if you need `run_id`, visible plan version, current read path, or refresh.
10. Confirm the selected plan still shows `action_manifest.source = proposed_actions` after opening `确认前动作`.
11. Click `确认当前方案`.
12. Confirm the run reaches `completed`.
13. Confirm execution and feedback are visible as a later assistant card in the same chat flow.
14. Confirm the result card prominently shows a copyable final arrangement message such as `搞定了，下午 2 点出发...`.
15. Confirm the result card shows a `复制安排消息` action for that final arrangement message.
16. Confirm the page now renders `执行时间线`, but keeps it collapsed by default.
17. Expand the execution timeline and confirm the timeline entries are ordered and show step number, action/tool label, target, and status.
18. Confirm the selected plan now shows `action_manifest.source = confirmed_actions`.

The automated desktop browser suite now keeps two happy-path starts in scope:

- one stable English smoke for regression stability across the existing customer demo flow
- one additive Chinese reviewer-prompt smoke for the localized competition demo path

The Chinese smoke accepts either `awaiting_confirmation` directly or `awaiting_clarification -> clarification reply -> awaiting_confirmation`, but it always starts from a Chinese customer prompt and must end at a confirmable `v1` plan.

### Friends Group Happy Path

1. Open `http://127.0.0.1:5173`.
2. Click the `朋友` scenario chip, or replace the default family sample with:

```text
This afternoon I want to hang out with friends nearby for a few hours. Start with an outdoor walk and chatting, then find a casual dinner place that's good for sharing. Not too far.
```

4. Click `开始规划`.
5. Confirm the run reaches the in-chat confirmation state.
6. Open `运行信息` and confirm the visible plan version label is still `v1`.
7. Expand `活动与餐厅` if needed and confirm the visible plan content reflects the friends-group fixture rather than the family fixture, for example by showing friends-oriented tags such as `适合朋友聚会`.
8. Confirm the page does not show any `AMap 只读预览` notice.
9. Click `确认当前方案`.
10. Confirm the run reaches `completed`.
11. Confirm the final assistant result card is visible in the same chat flow.

This path is intentionally additive. The default customer-page sample remains the family afternoon request, while explicit friends-group Mock World prompts now route to the canonical `friends_gathering` world.

### AMap Read-only Preview Path

The customer page does not expose an AMap selector in this task. To review the existing read-only preview path, use the API directly:

1. Start a run with `read_profile="amap"`:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"Plan a light family afternoon nearby.\",\"external_user_id\":\"web-demo-user\",\"display_name\":\"Web Demo User\",\"case_id\":\"web-demo\",\"selected_plan_index\":0,\"read_profile\":\"amap\"}"
```

2. Confirm the response reaches `awaiting_confirmation`.
3. Confirm the response `read_profile` is `amap`.
4. If you call `POST /demo/runs/<run_id>/confirm`, confirm the API returns HTTP `409` with `AMAP read-only demo runs cannot be confirmed.`.
5. Confirm the run has no write-side effects.

### Clarification Path

1. Start a fresh run with a vague request such as `想周末出去玩一下。`
2. Confirm the run reaches `awaiting_clarification` in the chat flow.
3. Confirm the visible response shows `plans = []`, `selected_plan_id = null`, and a non-null `clarification` summary.
4. Open `运行信息` and confirm the visible plan version label still shows `v1`.
5. Confirm the page renders the in-chat clarification card with:
   - the backend `clarification.prompt`
   - a visible `待补充项` list
   - a dedicated `补充说明` textarea
   - a `提交补充信息` button
6. Enter a reply such as `今天下午一个人出门玩几个小时，别太远。`
7. Click `提交补充信息`.
8. Confirm the page updates to a different `run_id`.
9. Confirm the continuation run reaches `awaiting_confirmation`.
10. Confirm the continuation run still shows `plan_version.version_label = v1`.
11. Confirm the public response still does not expose `session_id` or conversation history.

If you want an API-level fallback check for the same continuation, you can still send:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/clarify \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"今天下午一个人出门玩几个小时，别太远。\",\"selected_plan_index\":0}"
```

### Decline Path

1. Start a fresh run.
2. Wait for `awaiting_confirmation`.
3. Click `暂不继续`.
4. Confirm the run reaches `declined`.
5. Confirm `确认当前方案` is no longer available.
6. Confirm there are still no write-side effects.

### Follow-up Replan Path

1. Start a fresh run and wait for `awaiting_confirmation`.
2. Confirm the latest assistant plan card shows an inline `继续调整方案` textarea and submit button.
3. Open `运行信息` and confirm the visible `plan_version.version_label` is `v1`.
4. Record the visible `run_id`.
5. Enter a follow-up such as `Keep it nearby, but make it a solo outing this time.`
6. Click `基于当前方案继续规划`.
7. Confirm the page updates to a different `run_id`.
8. Confirm the new run also reaches `awaiting_confirmation`.
9. Open `运行信息` and confirm the visible version label advances to `v2`.
10. Enter another follow-up such as `Reduce walking even more.`
11. Click `基于当前方案继续规划` again.
12. Confirm the page stays on `awaiting_confirmation` and now shows `plan_version.version_label = v3`.
13. Confirm the public page still does not expose `session_id` or conversation history.

If you want an API-level fallback check for the same continuation, you can still send:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/replan \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"Keep it nearby, but make it a solo outing this time.\",\"selected_plan_index\":0}"
```

14. Confirm the response returns a different `run_id`.
15. Confirm the new run also reaches `awaiting_confirmation`.
16. Confirm the original run still shows `plan_version.version_label = v1` and the follow-up run shows `v2`.
17. Repeat the replan call from the `v2` run if needed and confirm the next run shows `v3`.
18. Confirm the original run is still readable through `GET /demo/runs/<old_run_id>` with its original selected plan unchanged.

### Refresh Path

1. Start a run.
2. Open `运行信息`.
3. Copy or inspect the visible run ID, then click `刷新当前状态`.
4. Confirm the same run ID remains visible.
5. Confirm the latest assistant card is updated in place rather than duplicated.

### Mobile Smoke

Use a mobile viewport around 390px wide. Start a run and confirm the main controls, latest assistant card, and disclosure buttons remain visible without document-level horizontal scrolling.

### Internal Richer UI Review

1. Open `http://127.0.0.1:5174/`.
2. Confirm `Benchmark Summary` loads before any run ID is entered.
3. Run `python scripts/run_benchmark_release_gate.py` if the benchmark panel reports that the latest release-gate summary is missing.
4. Confirm the benchmark panel shows suite counts, overall score, and matrix counts from the latest release-gate alias.
5. Paste a customer-demo `run_id` and click `Load Run`.
6. Confirm the page shows `Trace Summary`.
7. Confirm `Trace Summary` includes run identity, trace identity, workflow timing, and observability status.
8. Run `python scripts/run_recovery_replay_review.py`.
9. Paste the emitted recovery review `run_id`.
10. Confirm the page shows `Recovery Visualization` with attempt count, max attempts, per-attempt details, and replay source.

## Automated Checks

### Regression Matrix

Customer-surface browser regression is intentionally split into two layers:

- Live desktop checks against the real local stack now cover the primary customer paths:
  - happy path from start through confirm and execution feedback
  - vague-request clarification continuation
  - follow-up replan continuation with visible version advancement
  - customer-safe redaction on the public page
  - progress-stepper visibility plus closed-by-default completed-step disclosure behavior
- Live mobile checks still run against the real local stack and focus on customer-visible controls plus document-level horizontal-overflow safety.
- Targeted mocked desktop checks remain only for deterministic contract assertions that are difficult to force reliably from live data:
  - selected second-plan replan index propagation
  - AMap read-only preview notice and confirm block

Treat the live checks as the primary regression gate for customer behavior. Treat the targeted mocked checks as narrow contract guards rather than replacements for the live browser flow.

Install Playwright Chromium:

```bash
npm --prefix frontend run e2e:install
```

Run frontend unit tests:

```bash
npm --prefix frontend run test -- --run
```

Run the frontend build:

```bash
npm --prefix frontend run build
```

Run backend demo API regression tests:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
```

Run browser E2E tests:

```bash
npm --prefix frontend run e2e
```

Run only the additive Chinese reviewer-prompt desktop smoke during local iteration:

```bash
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "Chinese reviewer prompt"
```

Run only the additive friends-group desktop smoke during local iteration:

```bash
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "friends-group"
```

Run the full desktop browser regression before committing so the existing English stable smoke and the additive Chinese smoke stay green together:

```bash
npm --prefix frontend run e2e -- --project=desktop-chromium
```

Run the full mobile browser regression before committing to confirm the customer viewport still stays stable:

```bash
npm --prefix frontend run e2e -- --project=mobile-chromium
```

The E2E config starts:

- backend: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- customer frontend: Vite on `127.0.0.1:5173`
- internal frontend: Vite on `127.0.0.1:5174`

PostgreSQL, Redis, and migrations must already be ready.

## Expected Results

- Planning stops at `awaiting_confirmation` before any write action.
- Every successful public `DemoRunSummary` includes the additive `progress` snapshot, and refresh/readback preserves the same public-safe stage view after the run completes.
- `POST /demo/runs/stream` emits one or more `progress` events before the final `summary` event for the normal Mock World start path.
- The customer page now consumes `POST /demo/runs/stream` for the initial start flow and uses `fetch` stream parsing because the route is `POST`.
- If the initial stream transport fails before any valid live `progress` event is received, the customer page retries the same start request once through synchronous `POST /demo/runs`.
- On the default Mock World happy path, the stream emits ordered search-count milestones inside `progress`: first `searching_activities` with `已找到 5 个活动`, then `searching_dining` with `已找到 5 个餐厅`, before the first `checking_availability` event.
- Clarify, replan, confirm, decline, and readback remain on their existing synchronous routes in this task.
- `Mock World` remains the default read path for the public demo and for benchmark-aligned checks.
- The API-only `AMap` read preview path also stops at `awaiting_confirmation`, keeps `action_count = 0`, and never exposes a working confirm action.
- Vague start requests can stop at `awaiting_clarification` before any plan is generated.
- Bounded recovery can also stop at `awaiting_clarification` when deterministic recovery is exhausted and user tradeoff input is required.
- The initial public run shows `plan_version.version_label = v1`.
- Clarification-only turns keep the visible version label at `v1` until the first real plan is produced.
- The customer page first shows the composer and the six fixed Mock World scenario chips.
- The customer page shows user turns, system progress, clarifications, replans, and execution results in one chronological chat stream.
- `run_id`, `action_count`, raw `execution_status`, and raw `feedback_status` are not visible by default.
- Pre-confirmation selected plans expose `action_manifest.source = proposed_actions` when preview actions exist.
- Confirmation executes write actions through the deterministic workflow.
- Completed execution and feedback are visible after confirmation.
- Confirmed or executed plans expose `action_manifest.source = confirmed_actions` when persisted confirmed actions exist.
- Declining a run leaves no confirm action available.
- Replanning returns a new `run_id`, increments the visible version label, and still reuses the internal conversation session.
- Refresh preserves the current visible run and updates the latest assistant card in place.
- The page does not expose internal or sensitive keys such as `action_id`, `tool_event_id`, `idempotency_key`, `debug_trace`, `api_key`, `token`, `secret`, or `authorization`.

## Troubleshooting

- Backend health check fails: confirm `uvicorn backend.app.main:app --reload` starts and `http://127.0.0.1:8000/health` returns `ok`.
- API requests fail: confirm PostgreSQL and Redis are running and migrations were applied.
- E2E server startup fails: stop any stale process already using ports `8000`, `5173`, or `5174`, then rerun the command.
- Browser launch fails: rerun `npm --prefix frontend run e2e:install`.
- Frontend points at the wrong API: set `VITE_API_BASE_URL` in `frontend/.env`.
- LangSmith is unavailable: no action is required for the Mock World demo path.
- AMap preview start fails with a configuration error: set `AMAP_MAPS_API_KEY` in local `.env`, or use the default Mock World customer flow instead.

## What Not To Commit

Do not commit:

- `.env` or `frontend/.env`
- API keys, tokens, secrets, or credentials
- `node_modules/`
- `frontend/dist/`
- `frontend/playwright-report/`
- `frontend/test-results/`
- `frontend/blob-report/`
- screenshots, videos, traces, or other generated Playwright artifacts
- `var/` runtime files
