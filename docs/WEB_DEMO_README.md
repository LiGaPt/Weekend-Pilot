# Web Demo Runbook

## Overview

The Web demo is the primary MVP review path for WeekendPilot. It runs the React/Vite frontend against the FastAPI demo API, uses the Mock World provider only, pauses before write tools, and continues execution only after explicit confirmation. The visible demo copy and Mock World family-afternoon content are localized in Chinese for competition review.

The public demo API now also supports `POST /demo/runs/{run_id}/replan` for follow-up replanning. Every public `DemoRunSummary` includes a compact `plan_version` object: the initial run starts at `v1`, and each follow-up replan returns a new `run_id` with the next visible version label. The internal conversation session is reused, but that session state remains internal and is still not exposed in `DemoRunSummary`.

No external local-life provider, map provider, LangSmith upload, API key, token, or secret is required.

## Prerequisites

- Python environment with this package installed.
- Node.js and npm for the frontend.
- Docker Compose for local PostgreSQL and Redis.
- Alembic migrations applied before API or E2E runs.
- Chromium installed through Playwright before browser tests.

Playwright does not start Docker and does not run migrations. Keep these prerequisites explicit so failures are easy to diagnose.

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

Start Vite:

```bash
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`.

The frontend defaults to `http://127.0.0.1:8000` for API calls. To override it locally, create `frontend/.env` with:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not commit local `.env` files.

## Internal Review Surface

The repository now includes a separate internal observability review page for reviewers and developers:

- page: `http://127.0.0.1:5173/observability`
- backend endpoint: `GET /internal/runs/{run_id}/observability`

Paste a `run_id` from the public demo flow into `/observability` to inspect the internal workflow summary, including timing, node history, agent roles, observability status, and benchmark artifact context for benchmark-backed runs. The customer-facing demo at `/` stays customer-safe and no longer renders those internal fields.

The internal review page now also shows sanitized tool-event and action-ledger detail panels, a real benchmark-artifact panel populated from persisted run metadata, and a real recovery-path panel populated from persisted bounded recovery metadata. For benchmark-backed recovery runs, the page also shows the persisted benchmark case report path as replay input context. Replay execution and replay report browsing remain separate tooling.

## Manual Demo Flow

### Happy Path

1. Open `http://127.0.0.1:5173`.
2. Keep the default Chinese family afternoon request or enter an equivalent request.
3. Click `开始规划`.
4. Confirm the run reaches `awaiting_confirmation`.
5. Confirm the visible plan version label is `v1`.
6. Confirm the action count is `0`.
7. Review the selected plan, timeline, route, feasibility, and proposed actions.
8. Click `确认所选方案`.
9. Confirm the run reaches `completed`.
10. Confirm execution and feedback are visible.
11. Confirm the action count is greater than `0`.

### Decline Path

1. Start a fresh run.
2. Wait for `awaiting_confirmation`.
3. Click `暂不继续`.
4. Confirm the run reaches `declined`.
5. Confirm `确认所选方案` is no longer available.
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
- frontend: Vite on `127.0.0.1:5173`

PostgreSQL, Redis, and migrations must already be ready.

## Expected Results

- Planning stops at `awaiting_confirmation` before any write action.
- The initial public run shows `plan_version.version_label = v1`.
- Action count is `0` before confirmation.
- Confirmation executes write actions through the deterministic workflow.
- Completed execution and feedback are visible after confirmation.
- Action count is greater than `0` after confirmation.
- Declining a run leaves no confirm action available.
- Replanning returns a new `run_id`, increments the visible version label, and still reuses the internal conversation session.
- Refresh preserves the current visible run.
- The page does not expose internal or sensitive keys such as `action_id`, `tool_event_id`, `idempotency_key`, `debug_trace`, `api_key`, `token`, `secret`, or `authorization`.

## Troubleshooting

- Backend health check fails: confirm `uvicorn backend.app.main:app --reload` starts and `http://127.0.0.1:8000/health` returns `ok`.
- API requests fail: confirm PostgreSQL and Redis are running and migrations were applied.
- E2E server startup fails: stop any stale process already using ports `8000` or `5173`, then rerun the command.
- Browser launch fails: rerun `npm --prefix frontend run e2e:install`.
- Frontend points at the wrong API: set `VITE_API_BASE_URL` in `frontend/.env`.
- LangSmith is unavailable: no action is required for the Mock World demo path.

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
