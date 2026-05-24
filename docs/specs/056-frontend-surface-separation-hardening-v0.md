# Spec: 056 Frontend Surface Separation Hardening v0

## 1. Goal

Harden the boundary between the customer-safe demo surface and the internal observability review surface without redesigning the backend or changing any API contracts.

The repository already completed route-level and contract-level separation: the public demo API is redacted, and the internal observability API plus review page exist. The remaining gap is deployment and entry isolation. Today both surfaces still live inside one Vite app, one runtime entry file switches on `window.location.pathname`, and one production build emits a single `dist/index.html`. After this task, the customer demo and the internal observability review must run and build as two separate frontend surfaces with separate entrypoints, separate URLs, and separate build outputs.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a minimal Web UI product with observable-by-default internal behavior. `docs/NEXT_PHASE_ROADMAP.md` defines milestone `M2. 前端分离` as the point where customer-visible content and internal observability content stop being mixed together.

Tasks `034` and `035` established the first half of that milestone by creating a dedicated internal API and removing internal fields from the public customer contract. Tasks `037`, `041`, and `042` made the internal review surface useful by filling in tool-event, action-ledger, benchmark-artifact, and recovery-path panels. However, the repository still has one frontend app entry that switches between the two surfaces at runtime.

This task is the smallest useful convergence slice for M2. It does not change:

- the bounded workflow
- public confirmation behavior
- benchmark grading behavior
- public demo request/response shapes
- internal observability request/response shapes

It only hardens the frontend entry and build boundary.

## 3. Requirements

- Keep the current public demo API routes unchanged:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/clarify`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- Keep the current internal observability API route unchanged:
  - `GET /internal/runs/{run_id}/observability`
- Keep `frontend/index.html` as the customer surface entry in this v0 task.
- Add a dedicated internal surface HTML entry at:
  - `frontend/internal/index.html`
- `frontend/src/main.tsx` must become a customer-only entry and must no longer:
  - branch on `window.location.pathname`
  - import `ObservabilityPage`
  - render the internal review surface
- Add a dedicated internal entry module at:
  - `frontend/src/internal-main.tsx`
- Keep `frontend/src/App.tsx` and `frontend/src/observability/ObservabilityPage.tsx` in place. This task must not widen into a broad source-tree move.
- Add one neutral shared frontend helper at:
  - `frontend/src/shared/http.ts`
- `frontend/src/shared/http.ts` must export exactly:
  - `API_BASE_URL`
  - `FrontendApiError`
- Both customer and internal frontend API clients must use `frontend/src/shared/http.ts`.
- The internal observability frontend code must no longer import from:
  - `frontend/src/api/demo.ts`
- Keep customer-specific API behavior in:
  - `frontend/src/api/demo.ts`
- Keep internal observability API behavior in:
  - `frontend/src/observability/api.ts`
- `frontend/vite.config.ts` must become the customer-surface Vite config.
- Add a dedicated internal-surface Vite config at:
  - `frontend/vite.internal.config.ts`
- Add a dedicated Vitest config at:
  - `frontend/vitest.config.ts`
- Update `frontend/tsconfig.node.json` so Vite and Vitest config files remain typechecked.
- `frontend/package.json` must expose these exact surface scripts:
  - `dev`
  - `dev:customer`
  - `dev:internal`
  - `build`
  - `build:customer`
  - `build:internal`
  - `preview`
  - `preview:internal`
- `dev` and `dev:customer` must start the customer surface at `http://127.0.0.1:5173/`.
- `dev:internal` must start the internal surface at `http://127.0.0.1:5174/`.
- `build:customer` must emit:
  - `frontend/dist/customer/index.html`
- `build:internal` must emit:
  - `frontend/dist/internal/index.html`
- `build` must build both surfaces.
- The current customer docs must stop instructing reviewers to use:
  - `http://127.0.0.1:5173/observability`
- The internal review docs must instead instruct reviewers to use:
  - `http://127.0.0.1:5174/`
- `frontend/playwright.config.ts` must start both frontend dev servers during E2E:
  - customer on `5173`
  - internal on `5174`
- Add one internal-surface Playwright smoke spec that verifies:
  - the internal page loads on `5174`
  - the page shows the internal review heading
  - the page shows the `Run ID` input and load control
  - the page does not render the customer planning composer
- Extend backend default CORS origins so local development allows both:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
  - `http://localhost:5174`
  - `http://127.0.0.1:5174`
- Add one focused backend unit test that proves a `5174` origin receives the expected CORS allow-origin header.
- This task must not change any public or internal JSON response shape.
- This task must not add new environment variables.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add authentication, RBAC, or admin-only access control.
- Do not add or change backend API routes.
- Do not add a second npm package, npm workspace, or duplicate dependency manifest.
- Do not move all customer code into a new directory tree.
- Do not move all internal code into a new directory tree.
- Do not redesign customer or internal UI content.
- Do not change benchmark fixtures, benchmark scoring, replay behavior, workflow routing, or confirmation behavior.
- Do not add Docker, proxy, CDN, or deployment-infrastructure configuration.
- Do not preserve `/observability` as a compatibility route on the customer app.
- Do not stage or commit `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, `frontend/dist/`, or other local runtime artifacts.

## 5. Interfaces and Contracts

### Inputs

- Customer frontend entry:
  - `frontend/index.html`
  - `frontend/src/main.tsx`
- Internal frontend entry:
  - `frontend/internal/index.html`
  - `frontend/src/internal-main.tsx`
- Existing API contracts:
  - public demo routes
  - internal observability route
- Existing frontend environment input:
  - `VITE_API_BASE_URL`
- Existing backend setting:
  - `demo_cors_origins`

### Outputs

- Customer surface:
  - dev URL: `http://127.0.0.1:5173/`
  - build output: `frontend/dist/customer/index.html`
- Internal surface:
  - dev URL: `http://127.0.0.1:5174/`
  - build output: `frontend/dist/internal/index.html`

### Schemas

```json
{
  "customer_surface": {
    "dev_url": "http://127.0.0.1:5173/",
    "entry_html": "frontend/index.html",
    "entry_module": "frontend/src/main.tsx",
    "build_output": "frontend/dist/customer/index.html"
  },
  "internal_surface": {
    "dev_url": "http://127.0.0.1:5174/",
    "entry_html": "frontend/internal/index.html",
    "entry_module": "frontend/src/internal-main.tsx",
    "build_output": "frontend/dist/internal/index.html"
  },
  "scripts": {
    "dev": "customer default",
    "dev:customer": "customer default",
    "dev:internal": "internal default",
    "build": "build both surfaces",
    "build:customer": "build customer only",
    "build:internal": "build internal only",
    "preview": "preview customer only",
    "preview:internal": "preview internal only"
  }
}
```

## 6. Observability

This task does not add a new observability backend, new run metadata, or new API payloads.

It only changes how the existing internal observability frontend is entered and built. Existing internal observability data must remain available through the current internal API and current review page content. Existing public demo redaction must remain unchanged.

## 7. Failure Handling

- If the customer surface still renders the internal review UI through a pathname switch, treat that as a task failure.
- If the internal surface cannot call the backend because `5174` is not allowed by default CORS, fix the default CORS list in this task.
- If one surface builds successfully and the other does not, `build` must fail non-zero.
- If the backend is unavailable, both surfaces must continue to show their existing user-readable connection failure messages.
- If the internal surface is unavailable, the customer surface must still work independently.
- This task does not require the customer app to keep a working `/observability` URL. A customer-surface request to that path may fail or fall back; it must not be the supported internal review entry after this task.

## 8. Acceptance Criteria

- [ ] `docs/specs/056-frontend-surface-separation-hardening-v0.md` exists and matches this task.
- [ ] The latest completed task baseline remains `055`, and this task is additive on top of it.
- [ ] `frontend/src/main.tsx` is customer-only and no longer branches on `window.location.pathname`.
- [ ] `frontend/src/main.tsx` no longer imports or renders `ObservabilityPage`.
- [ ] `frontend/internal/index.html` exists and is the internal surface HTML entry.
- [ ] `frontend/src/internal-main.tsx` exists and mounts the internal review page.
- [ ] `frontend/src/shared/http.ts` exists and is used by both frontend API clients.
- [ ] Internal frontend code no longer imports from `frontend/src/api/demo.ts`.
- [ ] `frontend/package.json` exposes separate customer/internal dev and build scripts.
- [ ] `frontend/vite.config.ts` builds the customer surface into `frontend/dist/customer`.
- [ ] `frontend/vite.internal.config.ts` builds the internal surface into `frontend/dist/internal`.
- [ ] `frontend/vitest.config.ts` exists and frontend tests still run through it.
- [ ] `npm --prefix frontend run build` emits both `frontend/dist/customer/index.html` and `frontend/dist/internal/index.html`.
- [ ] The supported customer dev URL is `http://127.0.0.1:5173/`.
- [ ] The supported internal dev URL is `http://127.0.0.1:5174/`.
- [ ] Docs no longer direct internal reviewers to `http://127.0.0.1:5173/observability`.
- [ ] Docs direct internal reviewers to `http://127.0.0.1:5174/`.
- [ ] Backend default CORS origins include both `5173` and `5174`.
- [ ] A focused backend unit test proves `5174` preflight access works.
- [ ] Existing public demo frontend unit tests still pass.
- [ ] Existing internal observability frontend unit tests still pass.
- [ ] The existing public Playwright demo flow still passes.
- [ ] A new internal Playwright smoke flow passes on `5174`.
- [ ] Public demo API schemas remain unchanged.
- [ ] Internal observability API schemas remain unchanged.
- [ ] No `.env`, API key, token, secret, generated `dist/`, `qc`, `var/`, or unrelated untracked file is staged.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

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
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: harden frontend surface separation
```

## 11. Notes for the Implementer

Keep this task narrow and structural.

Use the smallest possible implementation shape:

1. keep the current customer and internal page components in place,
2. remove the runtime pathname switch,
3. add a second HTML entry plus a second Vite config,
4. split build outputs and docs,
5. add only the minimal backend CORS default for the second dev port.

Do not widen this into auth, API schema changes, hosting changes, or a full frontend package split.

The current repository baseline also has one sequencing constraint: task `055` is implemented on the current branch but not merged to `origin/main`. Execute this task on a fresh branch from updated main after `055` lands, unless the user explicitly wants to stack branches.
