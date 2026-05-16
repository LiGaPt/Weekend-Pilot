# Plan: 023 Minimal Web UI Demo

## 1. Spec Reference

Spec file:

```text
docs/specs/023-minimal-web-ui-demo.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task22`.
- Current Task 022 commit is `1adec6b feat: add web demo API surface`.
- Task 022 API exists under `backend/app/api/demo.py`.
- Task 022 response schemas exist under `backend/app/demo/schemas.py`.
- There is no existing frontend app.
- Node and npm are available locally.
- `docs/PROJECT_BLUEPRINT.md` may have unrelated uncommitted changes from the Web-first blueprint update. Do not revert or stage them unless explicitly instructed.
- `var/` may contain local runtime files. Do not commit them.

## 3. Files to Add

- `frontend/package.json` - npm scripts and frontend dependencies.
- `frontend/package-lock.json` - pinned npm dependency graph.
- `frontend/index.html` - Vite HTML entry.
- `frontend/vite.config.ts` - Vite React config and test config.
- `frontend/tsconfig.json` - TypeScript config.
- `frontend/tsconfig.node.json` - TypeScript config for Vite config if needed.
- `frontend/src/main.tsx` - React app mount.
- `frontend/src/App.tsx` - main demo workflow UI.
- `frontend/src/styles.css` - responsive product UI styling.
- `frontend/src/types/demo.ts` - Task 022 API response/request types.
- `frontend/src/api/demo.ts` - API client functions and error handling.
- `frontend/src/test/setup.ts` - Vitest DOM setup.
- `frontend/src/App.test.tsx` - UI state and rendering tests.
- `frontend/src/api/demo.test.ts` - API client tests.
- `frontend/.env.example` - optional API base URL example.
- `docs/specs/023-minimal-web-ui-demo.md` - Task 023 spec.
- `docs/plans/023-minimal-web-ui-demo-plan.md` - Task 023 plan.

## 4. Files to Modify

- `README.md` - add minimal Web UI setup and run commands.

Do not modify backend production code for Task 023 unless a blocking API incompatibility is discovered. If that happens, document the reason in the implementation handoff.

## 5. Implementation Steps

1. Confirm baseline.

```bash
git status --short --branch
git log --oneline -6
```

2. Create Task 023 branch.

```bash
git switch task22
git switch -c task23
```

3. Create the frontend package.

Create `frontend/package.json` with scripts:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest"
  }
}
```

Dependencies should include:

- `@vitejs/plugin-react`
- `vite`
- `typescript`
- `react`
- `react-dom`
- `lucide-react`
- `vitest`
- `jsdom`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `@testing-library/user-event`

Keep dependency scope minimal. Do not add a router, state library, CSS framework, or component library.

4. Add Vite and TypeScript config.

`frontend/vite.config.ts` should:

- use React plugin
- configure Vitest with `jsdom`
- load `frontend/src/test/setup.ts`

5. Add `.env.example`.

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

6. Define API types in `frontend/src/types/demo.ts`.

Include:

- `DemoStartRunRequest`
- `DemoRunSummary`
- `DemoPlanPreview`
- `DemoCandidateSummary`
- `DemoTimelineItem`
- `DemoRouteSummary`
- `DemoFeasibilitySummary`
- `DemoProposedActionSummary`
- `DemoConfirmationSummary`
- `DemoExecutionSummary`
- `DemoFeedbackSummary`

Use string UUIDs. Keep optional fields tolerant of missing backend data.

7. Implement API client in `frontend/src/api/demo.ts`.

Add:

```ts
export class DemoApiError extends Error {
  status: number;
}
```

Add:

```ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
```

Implement:

- `startRun`
- `getRun`
- `confirmRun`
- `declineRun`

Rules:

- Always send `Content-Type: application/json` for POST.
- Parse backend `detail` for errors.
- Throw `DemoApiError` on non-2xx.
- Do not log raw responses to console.

8. Implement `frontend/src/main.tsx`.

Mount `<App />` into `#root`.

9. Implement `frontend/src/App.tsx`.

State:

```ts
type RequestState =
  | "idle"
  | "starting"
  | "awaiting_confirmation"
  | "refreshing"
  | "confirming"
  | "declining"
  | "completed"
  | "declined"
  | "error";
```

Core state:

- `userInput`
- `run`
- `selectedPlanId`
- `requestState`
- `errorMessage`

Derived behavior:

- selected plan defaults to `run.selected_plan_id` or first plan.
- confirm enabled only when run status is `awaiting_confirmation`.
- decline enabled only when run status is `awaiting_confirmation`.
- refresh enabled when `run?.run_id` exists and no mutation is active.

10. Build request composer.

Elements:

- textarea with default family prompt
- Start planning button
- Reset sample button
- inline validation when textarea is empty

Start click:

- calls `startRun`
- sets returned run
- sets selected plan
- clears prior error

11. Build run inspector.

Show:

- status
- run ID
- trace ID
- tool event count
- action count
- execution status
- feedback status
- observability status
- agent roles
- compact node history

Use labels and compact text. Do not show raw JSON.

12. Build plan tabs.

Use buttons with plan title fallback:

```text
Plan 1
Plan 2
Plan 3
```

Clicking a tab changes frontend-selected plan only. Do not call backend to reselect plans in Task 023.

13. Build plan detail workspace.

For selected plan, show:

- title and summary
- activity name, category, address, tags
- dining name, category, address, tags
- timeline list with start/end labels and duration
- route distance/duration/summary
- feasibility total duration, route duration, queue wait, warnings
- proposed actions list with type, target, reason, and confirmation required

Fallbacks should render as `Unavailable` or `Not provided`.

14. Build confirmation controls.

Confirm:

- calls `confirmRun(run.run_id, selectedPlan.plan_id)`
- sets returned run
- sets selected plan to returned selected plan

Decline:

- calls `declineRun(run.run_id, selectedPlan.plan_id)`
- sets returned run

Button labels:

- `Confirm selected plan`
- `Decline`

While confirming/declining, disable both buttons and show a loading label.

15. Build execution and feedback result area.

After confirm, show:

- execution status
- succeeded and failed counts
- completed action summaries
- failed action summaries
- feedback headline
- feedback message
- next steps

After decline, show:

- declined status
- decline reason if returned
- no execution result

16. Add styling in `frontend/src/styles.css`.

Style as a restrained app surface:

- no marketing hero
- no nested cards
- desktop layout: composer/status side rail plus plan workspace
- mobile layout: single column
- stable button sizes
- readable timeline
- clear disabled states
- clear error banner

Avoid decorative gradients, purple-blue theme dominance, bokeh/orb decorations, and dashboard-card mosaics.

17. Add API client tests in `frontend/src/api/demo.test.ts`.

Mock `global.fetch`.

Test:

- `startRun` posts to `/demo/runs` with expected body.
- `getRun` calls `/demo/runs/{run_id}`.
- `confirmRun` posts selected plan ID.
- `declineRun` posts selected plan ID and reason.
- non-2xx response throws `DemoApiError` with backend detail.

18. Add UI tests in `frontend/src/App.test.tsx`.

Use Testing Library.

Test:

- app renders default prompt and start button.
- empty input disables start or shows validation.
- successful start renders awaiting-confirmation status and plan title.
- plan tabs switch selected visible plan.
- confirm button calls confirm API and renders completed feedback.
- decline button calls decline API and hides confirm action.
- API error renders visible error message.

Mock the API module rather than starting backend.

19. Update README.

Add a `Minimal Web UI Demo` section after `Web Demo API`:

```markdown
## Minimal Web UI Demo

Run the backend first:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
```

Run the frontend:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`.
```

Mention optional `VITE_API_BASE_URL` override through `frontend/.env`.

20. Install dependencies.

```bash
npm --prefix frontend install
```

Confirm `frontend/package-lock.json` is created.

21. Run frontend tests and build.

```bash
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

22. Run backend regression for the API contract.

```bash
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
```

23. Manual smoke with browser.

Run:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
```

Check:

- start default prompt
- see awaiting confirmation and plan details
- confirm selected plan
- see completed execution and feedback
- start another run and decline
- resize to mobile width and verify no overlap

24. Final checks.

```bash
git diff --check
git status --short
```

25. Commit only Task 023 files.

```bash
git add frontend README.md docs/specs/023-minimal-web-ui-demo.md docs/plans/023-minimal-web-ui-demo-plan.md
git commit -m "feat: add minimal web ui demo"
git push origin task23
```

Do not stage `docs/PROJECT_BLUEPRINT.md` or `var/` unless separately instructed.

## 6. Testing Plan

- Frontend unit tests:
  - API client success and error behavior
  - app initial render and validation
  - successful planning render
  - plan tab switching
  - confirm flow
  - decline flow
  - error display
- Frontend build:
  - `npm --prefix frontend run build`
- Backend contract regression:
  - `python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v`
- Manual browser smoke:
  - run full backend plus frontend locally
  - verify start, refresh, confirm, decline
  - verify desktop/mobile layout

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend install
npm --prefix frontend run test -- --run
npm --prefix frontend run build
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
docker compose up -d postgres redis
python -m alembic upgrade head
git diff --check
git status --short
```

Manual run commands:

```bash
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
```

Open:

```text
http://127.0.0.1:5173
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add minimal web ui demo
```

Expected commands:

```bash
git status --short
git add frontend README.md docs/specs/023-minimal-web-ui-demo.md docs/plans/023-minimal-web-ui-demo-plan.md
git commit -m "feat: add minimal web ui demo"
git push origin task23
```

The implementer must confirm `.env`, API keys, tokens, secrets, `node_modules`, `frontend/dist`, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not modify backend API contracts unless a blocking bug prevents the UI from using Task 022.
- Do not add Web E2E or Playwright.
- Do not add benchmark report screens.
- Do not add recovery visualization.
- Do not add auth or deployment config.
- Do not add frontend global state libraries or a component framework.
- Do not commit generated runtime traces or local server PID files.
- Do not commit unrelated blueprint changes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The app is a working demo surface, not a landing page.
- [ ] The UI calls Task 022 endpoints correctly.
- [ ] Confirmation boundary is visible: action count remains zero before confirm.
- [ ] Confirm and decline controls are state-safe.
- [ ] Execution and feedback render after confirm.
- [ ] Declined run cannot be confirmed.
- [ ] Forbidden internal/sensitive keys are not rendered.
- [ ] Desktop and mobile layouts are usable without overlap.
- [ ] Frontend tests and build pass.
- [ ] Backend Task 022 regression tests pass.
- [ ] README has enough commands to run the UI locally.
- [ ] Git status is clean after commit, except unrelated pre-existing files intentionally left out.
- [ ] No secrets or generated dependency/build folders were committed.

## 11. Handoff Notes

The implementer should report back:

- Changed files
- npm install/build/test results
- backend regression results
- manual browser smoke result
- commit hash
- push result
- any frontend limitation deferred to Task 024
