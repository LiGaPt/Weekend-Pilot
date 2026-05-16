# Plan: 024 Web E2E Tests and Demo README

## 1. Spec Reference

Spec file:

```text
docs/specs/024-web-e2e-tests-demo-readme.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task23`.
- Task 023 has added a React/Vite frontend under `frontend/`.
- Frontend npm scripts currently include `dev`, `build`, `preview`, and `test`.
- Frontend tests currently use Vitest and Testing Library.
- Backend demo API exists under `backend/app/api/demo.py`.
- Demo API tests exist:
  - `tests/test_demo_api.py`
  - `tests/integration/test_demo_api_gateway.py`
- Root README currently has a short Minimal Web UI Demo section but no dedicated demo runbook.
- `docs/PROJECT_BLUEPRINT.md` may have unrelated uncommitted changes. Do not stage it.
- `var/` may contain local runtime files. Do not stage it.

## 3. Files to Add

- `frontend/playwright.config.ts` - Playwright config with backend and frontend web servers.
- `frontend/e2e/demo.spec.ts` - browser E2E tests for start, confirm, decline, refresh, mobile smoke, and response hygiene.
- `docs/WEB_DEMO_README.md` - dedicated Web demo setup and verification runbook.
- `docs/specs/024-web-e2e-tests-demo-readme.md` - Task 024 spec.
- `docs/plans/024-web-e2e-tests-demo-readme-plan.md` - Task 024 plan.

## 4. Files to Modify

- `frontend/package.json` - add Playwright dependency and E2E scripts.
- `frontend/package-lock.json` - update npm lockfile.
- `frontend/src/App.tsx` - add minimal stable selectors or `aria-live` only if needed for E2E reliability/accessibility.
- `README.md` - link to `docs/WEB_DEMO_README.md`.
- `.gitignore` - add Playwright artifact folders only if current ignores do not cover them.

Do not modify backend production code for Task 024 unless a blocking bug is found. If that happens, keep the fix minimal and document it in the handoff.

## 5. Implementation Steps

1. Confirm baseline.

```bash
git status --short --branch
git log --oneline -6
```

2. Create Task 024 branch.

```bash
git switch task23
git switch -c task24
```

3. Add Playwright dependency and scripts.

Modify `frontend/package.json`:

```json
{
  "scripts": {
    "e2e": "playwright test",
    "e2e:headed": "playwright test --headed",
    "e2e:install": "playwright install chromium"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.0"
  }
}
```

Preserve existing scripts and dependencies.

4. Install frontend dependencies.

```bash
npm --prefix frontend install
```

This should update `frontend/package-lock.json`.

5. Add Playwright config.

Create `frontend/playwright.config.ts`.

Required behavior:

- `testDir: "./e2e"`
- `baseURL: "http://127.0.0.1:5173"`
- `trace: "retain-on-failure"`
- `screenshot: "only-on-failure"`
- `video: "retain-on-failure"` or omit video if runtime is too heavy
- desktop Chromium project
- mobile Chromium project
- two `webServer` entries:
  - backend server from repository root
  - frontend server from `frontend`

Use commands:

```ts
{
  command: "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
  cwd: "..",
  url: "http://127.0.0.1:8000/health",
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
}
```

```ts
{
  command: "npm run dev -- --host 127.0.0.1 --port 5173",
  cwd: ".",
  url: "http://127.0.0.1:5173",
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
  env: {
    ...process.env,
    VITE_API_BASE_URL: "http://127.0.0.1:8000",
  },
}
```

6. Check `.gitignore`.

Ensure generated Playwright artifacts are ignored:

```text
frontend/playwright-report/
frontend/test-results/
frontend/blob-report/
```

Add only missing entries. Do not remove existing ignore rules.

7. Add minimal selectors to `frontend/src/App.tsx` if needed.

Prefer existing roles/text. Add only stable attributes needed by Playwright:

```tsx
<span data-testid="run-status">...</span>
<dd data-testid="run-id">...</dd>
<dd data-testid="action-count">...</dd>
<button data-testid="confirm-button">...</button>
<button data-testid="decline-button">...</button>
<button data-testid="refresh-button">...</button>
```

Keep UI behavior unchanged.

8. Create `frontend/e2e/demo.spec.ts`.

Use Playwright test fixtures.

Define constants:

```ts
const forbiddenVisibleText = [
  "action_id",
  "tool_event_id",
  "event_id",
  "idempotency_key",
  "debug_trace",
  "api_key",
  "token",
  "secret",
  "authorization",
];
```

Add helper:

```ts
async function startDemoRun(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /start planning/i }).click();
  await expect(page.getByText("awaiting_confirmation").first()).toBeVisible({ timeout: 60_000 });
}
```

9. Add happy path E2E test.

Test name:

```text
starts a run, preserves confirmation boundary, confirms, and shows feedback
```

Steps:

- `page.goto("/")`
- click `Start planning`
- wait for `awaiting_confirmation`
- assert plan title or selected plan heading is visible
- assert action count is `0`
- click `Confirm selected plan`
- wait for feedback/result section
- assert completed feedback text or status is visible
- assert action count is not `0`
- assert `Confirm selected plan` is no longer visible or disabled

10. Add decline path E2E test.

Test name:

```text
declines a fresh run without exposing confirm action afterward
```

Steps:

- start run
- click `Decline`
- wait for declined state
- assert decline reason/result is visible
- assert `Confirm selected plan` is not visible

11. Add refresh path E2E test.

Test name:

```text
refreshes status without losing the current run
```

Steps:

- start run
- capture run ID from `data-testid="run-id"` or visible run metadata
- click `Refresh status`
- assert same run ID remains visible
- assert awaiting confirmation still visible

12. Add response hygiene test.

Test name:

```text
does not render forbidden internal or sensitive keys
```

Steps:

- start run
- get visible text from `page.locator("body").innerText()`
- assert no forbidden string appears
- confirm selected plan
- repeat visible text assertion

Use case-insensitive matching.

13. Add mobile smoke test.

Use mobile project or explicit viewport:

```ts
await page.setViewportSize({ width: 390, height: 844 });
```

Steps:

- start run
- assert main controls and selected plan are visible
- evaluate:

```ts
const hasHorizontalOverflow = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth
);
expect(hasHorizontalOverflow).toBe(false);
```

14. Add dedicated Web demo runbook.

Create `docs/WEB_DEMO_README.md` with sections:

- Overview
- Prerequisites
- Backend setup
- Frontend setup
- Run the demo
- Expected happy path
- Expected decline path
- Run automated checks
- Troubleshooting
- What not to commit

Include exact commands:

```bash
python -m pip install -e ".[dev]"
npm --prefix frontend install
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
npm --prefix frontend run e2e
```

Mention:

- backend URL: `http://127.0.0.1:8000`
- frontend URL: `http://127.0.0.1:5173`
- optional `frontend/.env` with `VITE_API_BASE_URL`
- no external API keys required
- Mock World only

15. Update root `README.md`.

In the Minimal Web UI section, add a concise link:

```markdown
For the full Web demo runbook, see `docs/WEB_DEMO_README.md`.
```

Do not duplicate the full runbook in root README.

16. Run Playwright browser install.

```bash
npm --prefix frontend run e2e:install
```

17. Run frontend unit tests and build.

```bash
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

18. Prepare backend prerequisites.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

19. Run backend demo API regression.

```bash
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
```

20. Run E2E tests.

```bash
npm --prefix frontend run e2e
```

21. If E2E fails due to selectors only, adjust selectors minimally.

Do not change product behavior for convenience. Prefer accessible selectors before adding more `data-testid`.

22. Manually smoke the demo.

Run:

```bash
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
```

Open:

```text
http://127.0.0.1:5173
```

Check:

- start -> awaiting confirmation
- confirm -> feedback visible
- start new run -> decline -> confirm unavailable
- mobile viewport has no horizontal overflow

23. Clean generated artifacts.

Check for and remove or ignore generated files such as:

- `frontend/playwright-report/`
- `frontend/test-results/`
- `frontend/blob-report/`
- screenshots
- videos
- traces

Do not remove tracked source files.

24. Final checks.

```bash
git diff --check
git status --short
```

25. Commit only Task 024 files.

```bash
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts frontend/e2e/demo.spec.ts frontend/src/App.tsx README.md docs/WEB_DEMO_README.md docs/specs/024-web-e2e-tests-demo-readme.md docs/plans/024-web-e2e-tests-demo-readme-plan.md .gitignore
git commit -m "test: add web demo e2e coverage"
git push origin task24
```

If `.gitignore` or `frontend/src/App.tsx` did not change, omit them from `git add`.

Do not stage `docs/PROJECT_BLUEPRINT.md` or `var/`.

## 6. Testing Plan

- Frontend unit/build:
  - `npm --prefix frontend run test -- --run`
  - `npm --prefix frontend run build`
- Backend API regression:
  - `python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v`
- Browser E2E:
  - `npm --prefix frontend run e2e`
- Manual smoke:
  - backend and frontend servers running locally
  - happy path, decline path, mobile viewport

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
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
test: add web demo e2e coverage
```

Expected commands:

```bash
git status --short
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts frontend/e2e/demo.spec.ts README.md docs/WEB_DEMO_README.md docs/specs/024-web-e2e-tests-demo-readme.md docs/plans/024-web-e2e-tests-demo-readme-plan.md
git commit -m "test: add web demo e2e coverage"
git push origin task24
```

Add `frontend/src/App.tsx` and `.gitignore` only if they changed.

The implementer must confirm `.env`, API keys, tokens, secrets, `node_modules`, `frontend/dist`, Playwright reports, traces, screenshots, videos, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not add new backend endpoints.
- Do not alter API response schemas.
- Do not add recovery routing.
- Do not expand benchmarks.
- Do not add benchmark report UI.
- Do not add auth or deployment config.
- Do not make Playwright manage Docker or migrations.
- Do not commit generated browser artifacts.
- Do not commit unrelated blueprint changes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] E2E tests start backend and frontend servers reliably.
- [ ] E2E tests document Postgres/Redis/migration prerequisites clearly.
- [ ] Happy path verifies confirmation boundary and post-confirmation execution.
- [ ] Decline path verifies no confirm action remains.
- [ ] Refresh path verifies the run remains stable.
- [ ] Mobile smoke checks horizontal overflow.
- [ ] Hygiene test checks forbidden visible text.
- [ ] Root README links to dedicated Web demo runbook.
- [ ] `docs/WEB_DEMO_README.md` is sufficient for a reviewer to run the demo.
- [ ] Unit tests, build, backend regression, and E2E tests pass.
- [ ] Generated artifacts and secrets are not staged.
- [ ] Git status is clean after commit, except unrelated pre-existing files intentionally left out.

## 11. Handoff Notes

The implementer should report back:

- Changed files
- npm install/test/build results
- Playwright browser install result
- E2E test result
- backend regression result
- manual smoke result
- commit hash
- push result
- any flake or environment prerequisite discovered
