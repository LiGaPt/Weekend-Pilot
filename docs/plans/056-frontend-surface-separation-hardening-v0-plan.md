# Plan: 056 Frontend Surface Separation Hardening v0

## 1. Spec Reference

Spec file:

```text
docs/specs/056-frontend-surface-separation-hardening-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/benchmark-multi-turn-continuations-v0`.
- Latest completed numbered task is `055`.
- The latest meaningful task commit is `75f9ea9 feat: add benchmark multi-turn continuations`.
- HEAD `49f0a7a` is only a merge-sync commit and does not change the task baseline.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `055`.
- The current task-055 branch is synced to `origin/codex/benchmark-multi-turn-continuations-v0` but is not merged to `origin/main`.
- Preferred execution baseline for task `056` is a fresh branch from updated `origin/main` after `055` lands.
- The current frontend still uses one Vite app with one runtime entry switch:
  - `frontend/src/main.tsx` checks `window.location.pathname === "/observability"`
- The current frontend still produces one build entry:
  - `frontend/dist/index.html`
- The current internal review surface is route-separated but not deploy-separated:
  - customer URL: `http://127.0.0.1:5173/`
  - internal URL today: `http://127.0.0.1:5173/observability`
- Backend default CORS origins currently allow only `5173`.
- Current public and internal frontend unit tests already pass.
- Current single-surface frontend production build already passes.
- Current worktree has unrelated untracked local paths:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`
- Those paths must remain unstaged during task `056`.

## 3. Files to Add

- `frontend/internal/index.html` - internal-surface HTML entry for the observability app root.
- `frontend/src/internal-main.tsx` - internal-surface React entry that mounts `ObservabilityPage`.
- `frontend/src/shared/http.ts` - shared `API_BASE_URL` and `FrontendApiError`.
- `frontend/vite.internal.config.ts` - internal-surface Vite config for port `5174` and `dist/internal`.
- `frontend/vitest.config.ts` - dedicated Vitest config after `vite.config.ts` becomes customer-only.
- `frontend/e2e/internal-observability.spec.ts` - Playwright smoke coverage for the internal surface on `5174`.

## 4. Files to Modify

- `frontend/package.json` - add customer/internal dev-build-preview scripts and point tests to `vitest.config.ts`.
- `frontend/vite.config.ts` - convert from mixed Vite/Vitest config into customer-only Vite config with `dist/customer`.
- `frontend/tsconfig.node.json` - include `vite.config.ts`, `vite.internal.config.ts`, and `vitest.config.ts`.
- `frontend/playwright.config.ts` - start both customer and internal frontend dev servers during E2E.
- `frontend/src/main.tsx` - remove pathname switching and make it mount only `App`.
- `frontend/src/api/demo.ts` - import `API_BASE_URL` and `FrontendApiError` from the shared helper.
- `frontend/src/api/demo.test.ts` - update the focused API-client tests to the shared error class.
- `frontend/src/observability/api.ts` - import `API_BASE_URL` and `FrontendApiError` from the shared helper.
- `frontend/src/observability/api.test.ts` - update the internal API-client tests to the shared error class.
- `frontend/src/observability/ObservabilityPage.tsx` - use the shared error class instead of importing from customer API code.
- `frontend/src/observability/ObservabilityPage.test.tsx` - update the internal page tests to the shared error class if needed.
- `backend/app/core/config.py` - add `5174` localhost defaults to `demo_cors_origins`.
- `tests/test_health.py` - add a focused preflight/CORS regression test for `5174`.
- `README.md` - document separate customer and internal frontend URLs plus scripts.
- `docs/WEB_DEMO_README.md` - replace `5173/observability` guidance with a dedicated internal-surface URL and startup steps.

## 5. Implementation Steps

1. Confirm the execution baseline before editing.
   - Run:
     ```bash
     git status --short --branch
     git log --oneline -5
     ```
   - Confirm that `055` is the latest completed task.
   - Do not start implementation on the current task-055 branch unless the user explicitly wants stacked work. Preferred baseline:
     ```bash
     git fetch origin
     git switch main
     git pull --ff-only
     git switch -c codex/frontend-surface-separation-hardening-v0
     ```

2. Extract the shared frontend transport boundary first.
   - Create `frontend/src/shared/http.ts`.
   - Export:
     - `API_BASE_URL`
     - `FrontendApiError`
   - Keep `FrontendApiError` compatible with the current behavior:
     - `status: number`
     - stable `name`
   - Do not move localization into the shared helper. Keep localized response-message logic inside each surface-specific API client.
   - Update:
     - `frontend/src/api/demo.ts`
     - `frontend/src/observability/api.ts`
     - `frontend/src/observability/ObservabilityPage.tsx`
   - After this step, internal frontend code must no longer import from `frontend/src/api/demo.ts`.

3. Harden the customer entry by removing the runtime path switch.
   - Modify `frontend/src/main.tsx` so it mounts only:
     - `<App />`
   - Remove:
     - `window.location.pathname === "/observability"`
     - any `ObservabilityPage` import
   - Keep `frontend/src/App.tsx` unchanged unless the build split exposes a small import-path issue.
   - Do not add a client router.

4. Add the dedicated internal frontend entry.
   - Create `frontend/internal/index.html`.
   - Point it at:
     - `../src/internal-main.tsx`
   - Create `frontend/src/internal-main.tsx`.
   - Mount only:
     - `<ObservabilityPage />`
   - Keep `frontend/src/observability/ObservabilityPage.tsx` in place. This task should not widen into moving all internal source files.

5. Split Vite and Vitest config cleanly.
   - Convert `frontend/vite.config.ts` into the customer-surface Vite config.
   - Set customer defaults:
     - port `5173`
     - output dir `dist/customer`
   - Add `frontend/vite.internal.config.ts`.
   - Set internal defaults:
     - root `internal`
     - port `5174`
     - output dir `../dist/internal`
   - Add `frontend/vitest.config.ts` and move the current test setup there:
     - `environment = "jsdom"`
     - `setupFiles = "./src/test/setup.ts"`
   - Update `frontend/tsconfig.node.json` so all config files remain included and typechecked.

6. Update frontend package scripts to expose both surfaces explicitly.
   - In `frontend/package.json`, make customer the default for backwards compatibility:
     - `dev` -> customer
     - `preview` -> customer
   - Add explicit scripts:
     - `dev:customer`
     - `dev:internal`
     - `build:customer`
     - `build:internal`
     - `preview:internal`
   - Make `build` run both surface builds.
   - Point `test` to `vitest.config.ts`.

7. Add the minimal backend change for local dual-surface development.
   - Update `backend/app/core/config.py` so `demo_cors_origins` includes:
     - `http://localhost:5174`
     - `http://127.0.0.1:5174`
   - Add a focused regression in `tests/test_health.py`:
     - send an `OPTIONS` preflight request
     - set `Origin: http://127.0.0.1:5174`
     - assert `access-control-allow-origin == http://127.0.0.1:5174`
   - Do not change any backend routes or response models.

8. Update Playwright to exercise the hard split.
   - In `frontend/playwright.config.ts`, keep the backend server block.
   - Keep the customer frontend server block on `5173`.
   - Add a second frontend server block for `5174` using the internal Vite config.
   - Keep `baseURL` pointed at the customer surface on `5173` so existing public demo tests continue unchanged.
   - Add `frontend/e2e/internal-observability.spec.ts`.
   - The new internal smoke test should:
     - open `http://127.0.0.1:5174/`
     - assert the heading `Internal Observability Review`
     - assert the `Run ID` field and load button are visible
     - assert customer-specific controls such as the planning composer or start button are absent

9. Update docs only where the entry boundary changed.
   - In `README.md`:
     - customer surface URL remains `5173`
     - internal surface URL becomes `5174`
     - show both dev commands
     - show both build outputs
   - In `docs/WEB_DEMO_README.md`:
     - replace `http://127.0.0.1:5173/observability`
     - add the internal dev command
     - update troubleshooting for a second frontend port
   - Do not rewrite unrelated product behavior sections.

10. Run focused verification and confirm the split is real.
    - Run backend unit tests:
      ```bash
      python -m pytest tests/test_health.py -q
      ```
    - Run focused frontend unit tests:
      ```bash
      npm --prefix frontend run test -- --run src/App.test.tsx src/api/demo.test.ts src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
      ```
    - Run dual-surface build:
      ```bash
      npm --prefix frontend run build
      ```
    - Confirm both outputs exist:
      ```bash
      Test-Path frontend/dist/customer/index.html
      Test-Path frontend/dist/internal/index.html
      ```
    - Run E2E:
      ```bash
      docker compose up -d postgres redis
      python -m alembic upgrade head
      npm --prefix frontend run e2e
      ```
    - Prove the old runtime switch is gone:
      ```bash
      if (rg -n "window\\.location\\.pathname" frontend/src) { throw "pathname switch still present" }
      ```
    - Finish with hygiene:
      ```bash
      git diff --check
      git status --short
      ```

11. Stage and commit only task-relevant files.
    - Stage:
      ```bash
      git add README.md docs/WEB_DEMO_README.md backend/app/core/config.py tests/test_health.py frontend/package.json frontend/vite.config.ts frontend/vite.internal.config.ts frontend/vitest.config.ts frontend/tsconfig.node.json frontend/playwright.config.ts frontend/internal/index.html frontend/src/main.tsx frontend/src/internal-main.tsx frontend/src/shared/http.ts frontend/src/api/demo.ts frontend/src/api/demo.test.ts frontend/src/observability/api.ts frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/ObservabilityPage.test.tsx frontend/e2e/internal-observability.spec.ts
      ```
    - Before commit, confirm these remain unstaged:
      - `docs/NEXT_PHASE_ROADMAP.md`
      - `docs/TASK_WORKFLOW_PROMPTS.md`
      - `qc`
      - `var/`
      - `.env`
      - `frontend/dist/`
      - `node_modules/`

## 6. Testing Plan

- Unit tests:
  - `tests/test_health.py` for `5174` CORS preflight
  - `frontend/src/api/demo.test.ts` for shared error/helper regression
  - `frontend/src/observability/api.test.ts` for shared error/helper regression
  - `frontend/src/observability/ObservabilityPage.test.tsx` for internal-surface regression after helper extraction
  - `frontend/src/App.test.tsx` for unchanged customer-surface behavior
- Build checks:
  - customer build output exists at `frontend/dist/customer/index.html`
  - internal build output exists at `frontend/dist/internal/index.html`
- E2E checks:
  - existing public demo Playwright flow still passes on `5173`
  - new internal smoke passes on `5174`
- Structural checks:
  - no `window.location.pathname` switch remains in `frontend/src`
  - internal frontend code no longer imports from `frontend/src/api/demo.ts`

## 7. Verification Commands

Commands the implementer must run before committing:

```powershell
python -m pytest tests/test_health.py -q
npm --prefix frontend run test -- --run src/App.test.tsx src/api/demo.test.ts src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run build
Test-Path frontend/dist/customer/index.html
Test-Path frontend/dist/internal/index.html
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run e2e
if (rg -n "window\\.location\\.pathname" frontend/src) { throw "pathname switch still present" }
if (rg -n "\\.\\./api/demo" frontend/src/observability frontend/src/internal-main.tsx) { throw "internal surface still depends on customer api module" }
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: harden frontend surface separation
```

Expected commands:

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c codex/frontend-surface-separation-hardening-v0
git status --short
git add README.md docs/WEB_DEMO_README.md backend/app/core/config.py tests/test_health.py frontend/package.json frontend/vite.config.ts frontend/vite.internal.config.ts frontend/vitest.config.ts frontend/tsconfig.node.json frontend/playwright.config.ts frontend/internal/index.html frontend/src/main.tsx frontend/src/internal-main.tsx frontend/src/shared/http.ts frontend/src/api/demo.ts frontend/src/api/demo.test.ts frontend/src/observability/api.ts frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/ObservabilityPage.test.tsx frontend/e2e/internal-observability.spec.ts
git diff --cached --check
git commit -m "feat: harden frontend surface separation"
git push -u origin codex/frontend-surface-separation-hardening-v0
```

The implementer must confirm that `.env`, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, `frontend/dist/`, and other unrelated local artifacts are not staged.

## 9. Out-of-scope Changes

- Do not add authentication, RBAC, or admin-only access control.
- Do not add or change backend API routes.
- Do not change public demo or internal observability JSON schemas.
- Do not split the frontend into multiple npm packages or workspaces.
- Do not move all customer and internal code into new top-level source trees.
- Do not add proxy, Docker, reverse-proxy, or deployment-hosting config.
- Do not redesign UI content or visual language.
- Do not keep `/observability` as a supported customer-surface route.
- Do not touch benchmark fixtures, benchmark grading, replay behavior, workflow routing, or confirmation logic.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, `frontend/dist/`, or other local artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/056-frontend-surface-separation-hardening-v0.md`.
- [ ] `frontend/src/main.tsx` is customer-only and no longer switches on pathname.
- [ ] `frontend/internal/index.html` and `frontend/src/internal-main.tsx` create a real internal surface root.
- [ ] Customer and internal surfaces have separate Vite configs and separate dist outputs.
- [ ] `frontend/src/shared/http.ts` is the only shared frontend transport helper introduced.
- [ ] Internal frontend code no longer imports from `frontend/src/api/demo.ts`.
- [ ] Backend default CORS allows both `5173` and `5174`.
- [ ] Focused backend unit tests passed.
- [ ] Existing public frontend unit tests passed.
- [ ] Existing internal frontend unit tests passed.
- [ ] Existing public Playwright demo flow passed.
- [ ] New internal Playwright smoke passed.
- [ ] `frontend/dist/customer/index.html` and `frontend/dist/internal/index.html` both exist after build.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- the exact files changed
- the exact customer URL and internal URL verified locally
- the exact build outputs verified under `frontend/dist/customer` and `frontend/dist/internal`
- the verification commands run and their results
- the commit hash
- the push result
- confirmation that the public and internal API schemas were unchanged
- confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, and `var/` remained unstaged
- any known limitation, especially:
  - this v0 hardens entry/build separation only
  - it does not add auth, deploy infrastructure, or a multi-package frontend workspace
