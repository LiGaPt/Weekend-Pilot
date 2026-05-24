# Web Demo Runbook

## Overview

The Web demo is the primary MVP review path for WeekendPilot. It runs the React/Vite frontend against the FastAPI demo API, defaults to the Mock World provider, pauses before write tools, and continues execution only after explicit confirmation. The visible demo copy and Mock World family-afternoon content are localized in Chinese for competition review.

The public page now exposes two explicit read paths:

- `Mock World`: the default deterministic demo and the unchanged benchmark baseline
- `AMap 只读预览`: an explicit local preview path that uses live read tools only, returns reviewed plans, and stops before confirmation

The public demo API now also supports `POST /demo/runs/{run_id}/clarify` for clarification replies and `POST /demo/runs/{run_id}/replan` for follow-up replanning. A vague start request, or a bounded recovery path that needs an explicit user tradeoff, can stop in `awaiting_clarification` with `plans = []`, `selected_plan_id = null`, and a compact `clarification` summary that contains the public follow-up prompt plus the missing supported fields.
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

No external local-life provider, map provider, LangSmith upload, API key, token, or secret is required for the default Mock World path.

## Prerequisites

- Python environment with this package installed.
- Node.js and npm for the frontend.
- Docker Compose for local PostgreSQL and Redis.
- Alembic migrations applied before API or E2E runs.
- Chromium installed through Playwright before browser tests.

Playwright does not start Docker and does not run migrations. Keep these prerequisites explicit so failures are easy to diagnose.

If you want to exercise the `AMap 只读预览` selector locally, set `AMAP_MAPS_API_KEY` in local `.env`. That key is not required for Mock World runs, benchmark runs, or the default test suite.

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

## Manual Demo Flow

### Happy Path

1. Open `http://127.0.0.1:5173`.
2. Keep the default Chinese family afternoon request or enter an equivalent request.
3. Click `开始规划`.
4. Confirm the run reaches `awaiting_confirmation`.
5. Confirm the visible plan version label is `v1`.
6. Confirm the action count is `0`.
7. Review the selected plan, timeline, route, feasibility, and the visible `action_manifest` preview.
8. Confirm the selected plan shows `action_manifest.source = proposed_actions`.
9. Click `确认当前方案`.
10. Confirm the run reaches `completed`.
11. Confirm execution and feedback are visible.
12. Confirm the action count is greater than `0`.
13. Confirm the selected plan now shows `action_manifest.source = confirmed_actions`.

### AMap Read-only Preview Path

1. Open `http://127.0.0.1:5173`.
2. Change the read-path selector from `Mock World` to `AMap 只读预览`.
3. Start the run.
4. Confirm the run reaches `awaiting_confirmation`.
5. Confirm the run inspector shows the active read path as `AMap 只读预览`.
6. Confirm the page shows the read-only preview notice and does not render a confirm action.
7. Confirm refresh is still available.
8. Confirm decline is still available.
9. If you call `POST /demo/runs/<run_id>/confirm`, confirm the API returns HTTP `409` with `AMAP read-only demo runs cannot be confirmed.`.
10. Confirm the run still has `action_count = 0` and no write-side effects.

### Clarification Path

1. Start a fresh run with a vague request such as `想周末出去玩一下。`
2. Confirm the run reaches `awaiting_clarification`.
3. Confirm the visible response shows `plans = []`, `selected_plan_id = null`, and a non-null `clarification` summary.
4. Confirm the visible plan version label still shows `v1`.
5. Confirm the page renders the `需要补充信息` panel with:
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
6. Confirm the action count remains `0`.

### Follow-up Replan Path

1. Start a fresh run and wait for `awaiting_confirmation`.
2. Copy the visible `run_id`.
3. Send a follow-up request:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/replan \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"Keep it nearby, but make it a solo outing this time.\",\"selected_plan_index\":0}"
```

4. Confirm the response returns a different `run_id`.
5. Confirm the new run also reaches `awaiting_confirmation`.
6. Confirm the original run still shows `plan_version.version_label = v1` and the follow-up run shows `v2`.
7. Repeat the replan call from the `v2` run if needed and confirm the next run shows `v3`.
8. Confirm the original run is still readable through `GET /demo/runs/<old_run_id>` with its original selected plan unchanged.
9. Confirm the public response still does not expose `session_id` or conversation history.

### Refresh Path

1. Start a run.
2. Copy or inspect the visible run ID.
3. Click `刷新状态`.
4. Confirm the same run ID remains visible.
5. Confirm the run still shows the expected status.

### Mobile Smoke

Use a mobile viewport around 390px wide. Start a run and confirm the main controls and selected plan remain visible without document-level horizontal scrolling.

## Automated Checks

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

The E2E config starts:

- backend: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- customer frontend: Vite on `127.0.0.1:5173`
- internal frontend: Vite on `127.0.0.1:5174`

PostgreSQL, Redis, and migrations must already be ready.

## Expected Results

- Planning stops at `awaiting_confirmation` before any write action.
- `Mock World` remains the default read path for the public demo and for benchmark-aligned checks.
- The explicit `AMap 只读预览` path also stops at `awaiting_confirmation`, keeps `action_count = 0`, and never exposes a working confirm action in the UI.
- Vague start requests can stop at `awaiting_clarification` before any plan is generated.
- Bounded recovery can also stop at `awaiting_clarification` when deterministic recovery is exhausted and user tradeoff input is required.
- The initial public run shows `plan_version.version_label = v1`.
- Clarification-only turns keep the visible version label at `v1` until the first real plan is produced.
- Action count is `0` before confirmation.
- Pre-confirmation selected plans expose `action_manifest.source = proposed_actions` when preview actions exist.
- Confirmation executes write actions through the deterministic workflow.
- Completed execution and feedback are visible after confirmation.
- Action count is greater than `0` after confirmation.
- Confirmed or executed plans expose `action_manifest.source = confirmed_actions` when persisted confirmed actions exist.
- Declining a run leaves no confirm action available.
- Replanning returns a new `run_id`, increments the visible version label, and still reuses the internal conversation session.
- Refresh preserves the current visible run.
- The page does not expose internal or sensitive keys such as `action_id`, `tool_event_id`, `idempotency_key`, `debug_trace`, `api_key`, `token`, `secret`, or `authorization`.

## Troubleshooting

- Backend health check fails: confirm `uvicorn backend.app.main:app --reload` starts and `http://127.0.0.1:8000/health` returns `ok`.
- API requests fail: confirm PostgreSQL and Redis are running and migrations were applied.
- E2E server startup fails: stop any stale process already using ports `8000`, `5173`, or `5174`, then rerun the command.
- Browser launch fails: rerun `npm --prefix frontend run e2e:install`.
- Frontend points at the wrong API: set `VITE_API_BASE_URL` in `frontend/.env`.
- LangSmith is unavailable: no action is required for the Mock World demo path.
- AMap preview start fails with a configuration error: set `AMAP_MAPS_API_KEY` in local `.env`, or switch the selector back to `Mock World`.

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
