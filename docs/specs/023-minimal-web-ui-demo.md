# Spec: 023 Minimal Web UI Demo

## 1. Goal

Add the first usable Web frontend for WeekendPilot.

After this task, a reviewer or user can open a local React/Vite app, enter the family afternoon request, generate a Mock World plan through the Task 022 demo API, review the selected plan, explicitly confirm or decline it, and see execution feedback. This replaces CLI-first demo expectations with the Web-first MVP path.

## 2. Project Context

Task 022 added the FastAPI demo API surface:

- `POST /demo/runs`
- `GET /demo/runs/{run_id}`
- `POST /demo/runs/{run_id}/confirm`
- `POST /demo/runs/{run_id}/decline`

Task 023 should build the minimal Web UI that consumes those endpoints. It should remain focused on the runnable demo surface and should not add Web E2E coverage or the richer V1 workflow visualization.

This task supports the blueprint areas:

- Minimal Web UI as the first demo surface
- Human confirmation before write tools
- Action Ledger visibility through safe counts and execution status
- LangSmith/local observability visibility through trace IDs and status
- Mock World-only demo path

## 3. Requirements

- Add a new `frontend/` app using React, Vite, TypeScript, and npm.
- The frontend must default to API base URL `http://127.0.0.1:8000`.
- The frontend must support `VITE_API_BASE_URL` override.
- The first screen must be the working demo app, not a marketing landing page.
- The app must include a prefilled editable request textarea using the family afternoon prompt.
- The app must call `POST /demo/runs` to start planning.
- The app must call `GET /demo/runs/{run_id}` to refresh run status.
- The app must call `POST /demo/runs/{run_id}/confirm` to confirm the selected plan.
- The app must call `POST /demo/runs/{run_id}/decline` to decline the selected plan.
- The app must display run status, run ID, trace ID, agent roles, node history summary, tool event count, and action count.
- The app must display at least:
  - selected plan title and summary
  - activity
  - dining
  - timeline
  - route
  - feasibility
  - proposed actions
  - confirmation status
  - execution status
  - feedback summary
- The app must support switching between returned plans through tabs or a segmented control.
- The app must disable mutation buttons while a request is in flight.
- The app must prevent confirm after a declined run.
- The app must prevent decline after a confirmed/completed run.
- The app must show API errors in user-readable form and keep a status refresh action available when a run exists.
- The app must not display raw JSON dumps as the primary UI.
- The app must not display internal or sensitive keys:
  - `action_id`
  - `tool_event_id`
  - `event_id`
  - `idempotency_key`
  - raw prompts
  - debug traces
  - API keys
  - tokens
  - secrets
  - authorization values
- The UI must be responsive for desktop and mobile widths.
- The UI must avoid text overlap and button label overflow.
- Add focused frontend unit tests for API client behavior and main UI flows.
- Update README with minimal Web UI setup and run commands.

## 4. Non-goals

- Do not add new backend API endpoints.
- Do not modify Task 022 API contracts unless a blocking defect is found and documented.
- Do not add Web E2E tests; Task 024 owns Web E2E and the full demo README.
- Do not add authentication, accounts, or persistent frontend sessions.
- Do not add deployment configuration.
- Do not add real provider or map integration.
- Do not add recovery routing.
- Do not implement V1 DAG/state optimization.
- Do not add benchmark report UI.
- Do not rewrite completed task specs or plans.
- Do not change `docs/PROJECT_BLUEPRINT.md` as part of this task.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

The frontend starts from this editable default prompt:

```text
This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.
```

The start request must send:

```json
{
  "user_input": "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.",
  "external_user_id": "web-demo-user",
  "display_name": "Web Demo User",
  "case_id": "web-demo",
  "selected_plan_index": 0
}
```

Confirm request:

```json
{
  "plan_id": "<selected-plan-id>",
  "confirmed_by": "web-demo-user"
}
```

Decline request:

```json
{
  "plan_id": "<selected-plan-id>",
  "declined_by": "web-demo-user",
  "reason": "User chose not to continue."
}
```

### Outputs

The frontend consumes `DemoRunSummary` from Task 022. UUID values should be treated as strings in TypeScript.

Minimum TypeScript contract:

```ts
export type DemoRunSummary = {
  run_id: string;
  trace_id: string | null;
  status: string;
  selected_plan_id: string | null;
  plans: DemoPlanPreview[];
  node_history: string[];
  tool_event_count: number;
  action_count: number;
  execution_status: string | null;
  feedback_status: string | null;
  observability_status: string | null;
  agent_roles: string[];
  error: Record<string, unknown> | null;
};
```

API client functions:

```ts
startRun(input: DemoStartRunRequest): Promise<DemoRunSummary>
getRun(runId: string): Promise<DemoRunSummary>
confirmRun(runId: string, planId?: string | null): Promise<DemoRunSummary>
declineRun(runId: string, planId?: string | null): Promise<DemoRunSummary>
```

### UI States

The app should model these states clearly:

- idle
- starting
- awaiting confirmation
- refreshing
- confirming
- declining
- completed
- declined
- error

## 6. Observability

The frontend should not add telemetry yet.

It must display Web-safe observability fields returned by the backend:

- `trace_id`
- `observability_status`
- `node_history`
- `agent_roles`
- `tool_event_count`
- `action_count`

The UI must label these as demo/run metadata, not as raw debug output.

## 7. Failure Handling

- Empty request input should disable the start button or show inline validation.
- Network failure should show a clear API connection error.
- Non-2xx API responses should display the backend `detail` field when available.
- If a run exists after an error, the UI should keep a refresh button available.
- If confirm or decline fails, the current plan display should remain visible.
- Repeated button clicks during in-flight requests must be ignored through disabled controls.
- Invalid or missing optional plan fields should render as unavailable values, not crash the app.

## 8. Acceptance Criteria

- [ ] `frontend/` contains a React/Vite/TypeScript app.
- [ ] `npm --prefix frontend install` creates a lockfile and installs dependencies.
- [ ] `npm --prefix frontend run dev` starts the UI on Vite's default local server.
- [ ] `npm --prefix frontend run build` passes.
- [ ] `npm --prefix frontend run test -- --run` passes.
- [ ] The app can start a demo run against Task 022 API.
- [ ] The app shows `awaiting_confirmation` after planning.
- [ ] The app shows at least one plan with activity, dining, timeline, route, feasibility, and proposed actions.
- [ ] The app can refresh run status.
- [ ] The app can confirm the selected plan.
- [ ] After confirm, the app shows completed execution and feedback details.
- [ ] The app can decline a fresh selected plan.
- [ ] After decline, confirm is no longer available.
- [ ] The UI does not expose forbidden internal or sensitive keys.
- [ ] Desktop and mobile layouts do not overlap text or overflow button labels.
- [ ] Existing Task 022 backend tests still pass.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit, except unrelated pre-existing changes intentionally left out.

## 9. Verification Commands

```bash
git switch task22
git switch -c task23
npm --prefix frontend install
npm --prefix frontend run test -- --run
npm --prefix frontend run build
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
git diff --check
git status --short
```

Manual browser smoke:

```text
Open http://127.0.0.1:5173
Start a run with the default prompt.
Confirm the selected plan and verify completed feedback.
Start a second run and decline it.
Check desktop and mobile widths for layout overlap.
```

## 10. Expected Commit

```text
feat: add minimal web ui demo
```

## 11. Notes for the Implementer

This is a demo app, but it should still feel like a real product surface. Use a restrained operational UI rather than a marketing page.

Visual thesis:

```text
A calm operations console for turning one family-afternoon request into a confirmed local-life plan.
```

Content plan:

- Request composer
- Run status and trace summary
- Plan review workspace
- Confirmation controls
- Execution and feedback result

Interaction thesis:

- Clear loading states for planning, confirming, declining, and refreshing.
- Plan tabs should make alternatives easy to scan without changing page layout.
- Confirmation controls should visibly disappear or become disabled once a run is terminal.

Keep implementation scoped. If a field from the backend is missing, render a fallback label rather than expanding backend scope.
