# Spec: 024 Web E2E Tests and Demo README

## 1. Goal

Add end-to-end verification and demo documentation for the Web-first MVP path.

After this task, the project should have automated browser coverage proving that the Task 023 frontend can drive the Task 022 backend workflow through planning, confirmation, execution, feedback, decline, and refresh. The repository should also include a dedicated Web demo runbook that a reviewer can follow without reading the implementation plans.

## 2. Project Context

Task 022 added the Web demo FastAPI surface.
Task 023 added the minimal React/Vite Web UI.

Task 024 should make that demo repeatable and reviewable. It corresponds to the blueprint roadmap item "Add Web end-to-end tests and demo README."

This task supports:

- Web-first MVP demo
- human confirmation boundary
- Action Ledger safety visibility
- browser-level verification
- demo reviewer handoff
- local Mock World-only execution

## 3. Requirements

- Add Playwright E2E test support for the frontend.
- Add npm scripts:
  - `e2e`
  - `e2e:headed`
  - `e2e:install`
- Add a Playwright config that starts both local servers:
  - backend: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
  - frontend: Vite on `127.0.0.1:5173`
- Treat PostgreSQL, Redis, and Alembic migrations as explicit prerequisites. Playwright must not silently start Docker or run migrations.
- Add E2E coverage for the happy path:
  - start a demo run
  - see `awaiting_confirmation`
  - verify action count is `0` before confirmation
  - confirm the selected plan
  - see completed execution and feedback
  - verify action count is greater than `0`
- Add E2E coverage for the decline path:
  - start a fresh run
  - decline selected plan
  - see declined state
  - verify confirm action is unavailable
- Add E2E coverage for refresh:
  - start a run
  - refresh status
  - verify the same run remains visible
- Add E2E mobile smoke coverage:
  - run the main flow or a loaded run at a mobile viewport
  - assert the document does not have horizontal overflow
- Add response hygiene coverage:
  - visible page text must not include forbidden internal or sensitive keys:
    - `action_id`
    - `tool_event_id`
    - `event_id`
    - `idempotency_key`
    - `debug_trace`
    - `api_key`
    - `token`
    - `secret`
    - `authorization`
- Prefer accessible role and text selectors.
- Add stable `data-testid` attributes only where role/text selectors are brittle, such as status, action count, and trace/run identifiers.
- Add `docs/WEB_DEMO_README.md` with:
  - prerequisites
  - backend setup
  - frontend setup
  - test commands
  - manual demo flow
  - expected results
  - troubleshooting
  - no-secrets guidance
- Update root `README.md` to link to `docs/WEB_DEMO_README.md`.
- Keep product behavior unchanged except for testability and accessibility improvements.

## 4. Non-goals

- Do not add new backend features or API endpoints.
- Do not change Task 022 API contracts.
- Do not add recovery routing.
- Do not expand LocalLife-Bench cases.
- Do not add benchmark report UI.
- Do not add auth, deployment config, or real provider support.
- Do not make Playwright start Docker.
- Do not make Playwright run Alembic migrations.
- Do not commit Playwright reports, traces, screenshots, videos, `node_modules`, `frontend/dist`, `.env`, API keys, tokens, secrets, or `var/`.
- Do not change `docs/PROJECT_BLUEPRINT.md` as part of this task.

## 5. Interfaces and Contracts

### Inputs

Playwright tests drive the browser at:

```text
http://127.0.0.1:5173
```

The frontend calls the backend at:

```text
http://127.0.0.1:8000
```

The default demo prompt remains:

```text
This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.
```

### Outputs

Playwright should assert visible UI outcomes, not database internals:

- run status
- action count
- plan content
- confirmation controls
- execution and feedback result
- declined state
- absence of forbidden internal keys
- mobile viewport without horizontal overflow

### Scripts

Add scripts to `frontend/package.json`:

```json
{
  "e2e": "playwright test",
  "e2e:headed": "playwright test --headed",
  "e2e:install": "playwright install chromium"
}
```

### Playwright Projects

Use Chromium only for this task:

- desktop Chromium
- mobile Chromium using a mobile viewport/device profile

Cross-browser coverage is not required yet.

## 6. Observability

Task 024 should not add telemetry.

The E2E tests should verify that the Web UI displays existing observability fields safely:

- trace ID is visible when available
- node history or run metadata area is visible
- tool event count is visible
- action count changes only after confirmation

Playwright artifacts should be generated only on failure and should not be committed.

## 7. Failure Handling

- If backend or frontend server startup fails, Playwright should fail clearly.
- If PostgreSQL or Redis is unavailable, tests may fail but the README must document the prerequisite.
- If migrations are missing, tests may fail but the README must instruct running Alembic first.
- If API calls fail, the UI should show the existing error message and tests should surface it in failure output.
- Tests should avoid brittle UUID matching except where checking that the same run remains visible after refresh.

## 8. Acceptance Criteria

- [ ] `@playwright/test` is added to frontend dev dependencies.
- [ ] `frontend/playwright.config.ts` starts backend and frontend servers.
- [ ] `npm --prefix frontend run e2e:install` installs Chromium.
- [ ] `npm --prefix frontend run e2e` passes with PostgreSQL, Redis, and migrations ready.
- [ ] E2E happy path verifies action count is `0` before confirm and greater than `0` after confirm.
- [ ] E2E happy path verifies completed execution or feedback is visible after confirm.
- [ ] E2E decline path verifies confirm is unavailable after decline.
- [ ] E2E refresh path verifies the same run remains visible.
- [ ] E2E mobile smoke verifies no document-level horizontal overflow.
- [ ] E2E hygiene check verifies forbidden internal/sensitive keys are not visible.
- [ ] Existing frontend unit tests still pass.
- [ ] Existing frontend build still passes.
- [ ] Existing Task 022 demo API tests still pass.
- [ ] `docs/WEB_DEMO_README.md` documents full local demo setup and troubleshooting.
- [ ] Root `README.md` links to `docs/WEB_DEMO_README.md`.
- [ ] No generated Playwright reports/traces/screenshots/videos are committed.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit, except unrelated pre-existing changes intentionally left out.

## 9. Verification Commands

```bash
git switch task23
git switch -c task24
npm --prefix frontend install
npm --prefix frontend run e2e:install
npm --prefix frontend run test -- --run
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run e2e
git diff --check
git status --short
```

Manual demo check:

```bash
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
```

Open:

```text
http://127.0.0.1:5173
```

Run:

```text
start -> confirm -> verify feedback
start -> decline -> verify no confirm action
mobile viewport -> verify no overlap or horizontal overflow
```

## 10. Expected Commit

```text
test: add web demo e2e coverage
```

## 11. Notes for the Implementer

Keep this task focused on confidence and handoff quality. Do not improve the product UI unless the change is needed for robust browser tests or accessibility.

Recommended selector policy:

- Use accessible roles and labels first.
- Add `data-testid` only for dynamic fields that are hard to target reliably.
- Prefer stable test IDs:
  - `run-status`
  - `run-id`
  - `action-count`
  - `confirm-button`
  - `decline-button`
  - `refresh-button`

If a Playwright test discovers a real Task 023 bug, fix the smallest frontend issue needed to make the existing demo contract work. Do not expand the backend or workflow scope.
