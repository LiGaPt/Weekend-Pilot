# Public Demo Contract Redaction and View Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove internal observability/debug fields from the public demo contract and customer UI while leaving the internal observability surface untouched.

**Architecture:** The public demo API will continue to serve the same routes, but `DemoRunSummary` will be narrowed to customer-safe fields only. The customer-facing React page will render only public information, and internal trace/node/agent inspection will remain exclusively on `/observability` through the dedicated internal endpoint from Task 034.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic, React, Vite, TypeScript, pytest, Vitest.

---

## 1. Spec Reference

Spec file:

```text
docs/specs/035-public-demo-contract-redaction-and-view-separation-v0.md
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

- Current branch is `codex/internal-observability-api-and-review-console-skeleton-v0`.
- Latest completed numbered task is `034`.
- Latest commit is `a4ade7f feat: add internal observability api and review console skeleton`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `034`.
- `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` are present as local context and must stay unstaged.
- Task 034 already provides:
  - `GET /internal/runs/{run_id}/observability`
  - `/observability`
  - the internal observability schemas and tests
- The public demo surface still exposes internal observability/debug fields and needs to be narrowed.
- The current public page at `/` still renders those fields and will need to be updated in the same task.
- The internal observability page and endpoint should not be rewritten.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/demo/schemas.py` - remove internal observability/debug fields from `DemoRunSummary`.
- `backend/app/demo/service.py` - stop populating removed public fields in `build_summary`; delete now-unused helper methods if they become dead code.
- `frontend/src/types/demo.ts` - narrow the public TypeScript type.
- `frontend/src/App.tsx` - remove internal observability/debug sections from the customer page.
- `frontend/src/App.test.tsx` - update fixtures and assertions for the narrowed public surface.
- `frontend/src/api/demo.test.ts` - update the public demo API fixture type shape.
- `tests/test_demo_api.py` - update schema serialization assertions for the narrowed response.
- `tests/integration/test_demo_api_gateway.py` - assert the public route omits internal fields and still supports the full demo flow.
- `README.md` - note that internal inspection moved to `/observability`.
- `docs/WEB_DEMO_README.md` - update the internal review guidance and customer-facing flow notes.

## 5. Implementation Steps

1. Confirm the baseline.
   - Run:
     ```bash
     git status --short --branch
     git log --oneline -5
     ```
   - Confirm the current branch is still the Task 034 branch and that only the known local context files are untracked.

2. Narrow the public backend schema in `backend/app/demo/schemas.py`.
   - Remove these fields from `DemoRunSummary`:
     - `trace_id`
     - `tool_event_count`
     - `node_history`
     - `observability_status`
     - `agent_roles`
   - Keep these fields:
     - `run_id`
     - `status`
     - `selected_plan_id`
     - `plans`
     - `action_count`
     - `execution_status`
     - `feedback_status`
     - `error`
   - Do not change `DemoPlanPreview`.

3. Update `backend/app/demo/service.py` to build the narrowed summary.
   - Stop populating the removed fields in `build_summary`.
   - Keep `action_count` as the customer-visible coarse progress indicator.
   - Leave the internal `trace_id` retrieval logic used by confirmation and observability recording untouched.
   - Remove helper methods that become unused only if they are no longer referenced in the file.

4. Update the frontend public demo type and page.
   - In `frontend/src/types/demo.ts`, remove the deleted public fields from `DemoRunSummary`.
   - In `frontend/src/App.tsx`, remove the customer-page UI that renders:
     - trace ID
     - tool-event count
     - observability status
     - agent roles
     - node history
   - Keep the plan details, confirmation controls, execution result, refresh, and `action_count` display.
   - Do not touch `/observability` in this task.

5. Update frontend test fixtures.
   - In `frontend/src/App.test.tsx`, remove the deleted fields from the demo run fixtures.
   - In `frontend/src/api/demo.test.ts`, update the mock `DemoRunSummary` fixture to the narrowed shape.
   - Keep the existing demo-flow assertions that still apply to the public UI.

6. Update backend public API tests.
   - In `tests/test_demo_api.py`, assert the narrowed `DemoRunSummary` shape and remove any expectations for the deleted fields.
   - In `tests/integration/test_demo_api_gateway.py`, add explicit assertions that the public `/demo/runs*` payload no longer contains the removed internal fields.
   - Preserve the public start/confirm/decline behavior checks and the database side-effect assertions.

7. Keep the internal observability surface as regression coverage.
   - Leave `tests/test_observability.py` and `tests/integration/test_observability_gateway.py` intact unless a small adjustment is needed for shared fixtures.
   - The internal route should still assert the presence of trace ID, node history, agent roles, tool count, and observability summary.

8. Update docs.
   - In `README.md`, add a short note that the public demo page is customer-safe and internal trace inspection lives at `/observability`.
   - In `docs/WEB_DEMO_README.md`, update the internal review section so reviewers are directed to `/observability` for trace/node/agent inspection instead of the public page.

9. Run focused verification.
   - Backend unit tests:
     ```bash
     python -m pytest tests/test_demo_api.py tests/test_observability.py -q
     ```
   - Backend integration tests:
     ```bash
     docker compose up -d postgres redis
     python -m alembic upgrade head
     python -m pytest tests/integration/test_demo_api_gateway.py tests/integration/test_observability_gateway.py -v
     ```
   - Frontend tests:
     ```bash
     npm --prefix frontend run test -- --run
     npm --prefix frontend run build
     ```
   - Final hygiene:
     ```bash
     git diff --check
     git status --short
     ```

10. Commit and push only intended files.
    - Expected commit message:
      ```text
      feat: redact public demo observability fields
      ```
    - Expected commands:
      ```bash
      git status --short
      git add README.md docs/WEB_DEMO_README.md backend/app/demo/schemas.py backend/app/demo/service.py frontend/src/types/demo.ts frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/api/demo.test.ts tests/test_demo_api.py tests/integration/test_demo_api_gateway.py
      git diff --cached --check
      git commit -m "feat: redact public demo observability fields"
      git push -u origin <task-035-branch>
      ```
    - Before commit, confirm these stay unstaged:
      - `docs/NEXT_PHASE_ROADMAP.md`
      - `docs/TASK_WORKFLOW_PROMPTS.md`
      - `var/`
      - `.env`
      - caches
      - virtual environments
      - `node_modules`
      - `frontend/dist`

## 6. Testing Plan

- Unit tests:
  - public `DemoRunSummary` serialization no longer includes internal observability fields
  - customer-page render fixtures compile against the narrowed type
  - demo API client fixtures still match the public shape
- Integration tests:
  - public `/demo/runs*` responses omit internal observability/debug fields
  - public start/confirm/decline flow still works
  - internal `/internal/runs/{run_id}/observability` still returns the full internal summary
- Smoke tests:
  - `npm --prefix frontend run build`
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/test_observability.py -q
python -m pytest tests/integration/test_demo_api_gateway.py tests/integration/test_observability_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: redact public demo observability fields
```

Expected commands:

```bash
git status --short
git add README.md docs/WEB_DEMO_README.md backend/app/demo/schemas.py backend/app/demo/service.py frontend/src/types/demo.ts frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/api/demo.test.ts tests/test_demo_api.py tests/integration/test_demo_api_gateway.py
git diff --cached --check
git commit -m "feat: redact public demo observability fields"
git push -u origin <task-035-branch>
```

The implementer must confirm `.env`, secrets, `var/`, and unrelated untracked files are not staged.

## 9. Out-of-scope Changes

- Do not change the internal observability API or review console.
- Do not add authentication, RBAC, or admin-only access control.
- Do not split the frontend into separate apps, builds, or deploy targets.
- Do not add `react-router` or any other new dependency.
- Do not change benchmark cases, graders, replay behavior, or workflow routing.
- Do not change confirmation, execution, or Action Ledger behavior.
- Do not add database tables, migrations, or environment variables.
- Do not add new public demo routes as a compatibility layer for the removed fields.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, caches, `.venv`, `frontend/dist`, or other local artifacts.

## 10. Review Checklist

- [ ] Public `/demo/runs*` responses no longer include internal observability/debug fields.
- [ ] The customer-facing `/` page no longer renders internal trace/node/agent metadata.
- [ ] The customer-facing `/` page still renders the plan, confirmation, execution, and feedback flow.
- [ ] The internal `/observability` page and endpoint still expose the full internal inspection data.
- [ ] Frontend unit tests passed against the narrowed public type.
- [ ] Backend unit and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/`, or unrelated untracked file was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- Verification commands and results.
- Commit hash.
- Push result.
- Confirmation that the internal observability route stayed unchanged.
- Confirmation that public demo responses no longer expose the removed internal fields.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any known limitation, especially if a later task should remove more customer-facing counters or further split the frontend into separate deployables.
