# Internal Observability Detail Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tool-event and action-ledger placeholders on `/observability` with sanitized, useful internal details.

**Architecture:** Extend the existing internal observability API with additive list summaries built from already-persisted `tool_events` and `action_ledger` rows. Render those summaries in the existing internal review page while leaving the public demo flow unchanged and keeping benchmark/recovery placeholders for later tasks.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic, React, Vite, TypeScript, pytest, Vitest.

---

## 1. Spec Reference

Spec file:

```text
docs/specs/037-internal-observability-detail-panels-v0.md
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

- Current branch is `codex/run-trace-benchmark-summary-alignment-v0`.
- Latest completed numbered task is `036`.
- Latest commit is `694ba45 feat: align run trace and benchmark summary contracts`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `036`.
- `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` are present locally and must stay unstaged.
- Task 034 already created:
  - `GET /internal/runs/{run_id}/observability`
  - `/observability`
- Task 035 already redacted public demo observability fields.
- Task 036 already aligned the run/trace/benchmark summary contracts.
- `frontend/src/main.tsx` already dispatches `/observability` to the internal page, so no route work is needed.
- `ToolEventRepository` already has `list_for_run(...)`.
- `ActionLedgerRepository` does not yet have `list_for_run(...)`.
- Existing internal observability tests already cover run overview, timing summary, node history, agent roles, and observability summary.
- Existing frontend observability tests already cover the page skeleton and placeholder panels.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/repositories/action_ledger.py` - add run-scoped list loading.
- `backend/app/observability/schemas.py` - add additive internal tool-event and action-ledger summary models and response fields.
- `backend/app/observability/service.py` - build and sanitize the new summaries.
- `frontend/src/observability/types.ts` - add the new internal summary types.
- `frontend/src/observability/ObservabilityPage.tsx` - render the new internal detail panels.
- `frontend/src/styles.css` - add any list/card styles needed for the new panels.
- `frontend/src/observability/ObservabilityPage.test.tsx` - update fixtures and assertions for the new sections.
- `frontend/src/observability/api.test.ts` - update the internal observability fixture shape.
- `tests/test_observability.py` - add backend unit coverage for the new summary fields.
- `tests/integration/test_observability_gateway.py` - add end-to-end coverage for the new internal data.
- `README.md` - note that the internal observability page now includes tool-event and action-ledger panels.
- `docs/WEB_DEMO_README.md` - update the internal review instructions to mention the new details.

## 5. Implementation Steps

### Task 1: Extend the backend internal observability contract

Files:
- Modify: `backend/app/repositories/action_ledger.py`
- Modify: `backend/app/observability/schemas.py`
- Modify: `backend/app/observability/service.py`

Steps:
- [ ] Add `ActionLedgerRepository.list_for_run(run_id)` with deterministic chronological ordering.
- [ ] Add additive summary models for tool events and action-ledger rows in `backend/app/observability/schemas.py`.
- [ ] Add additive `tool_event_summaries` and `action_ledger_summaries` fields to `InternalObservabilityRunSummary`.
- [ ] In `InternalObservabilityService`, load the run’s tool events and action-ledger rows and map them into sanitized preview objects.
- [ ] Keep the existing internal summary fields unchanged.
- [ ] Make sure previews omit IDs, idempotency keys, and raw sensitive payloads.
- [ ] Keep missing optional data as empty lists rather than breaking the existing response shape.

### Task 2: Render the new panels in the existing internal page

Files:
- Modify: `frontend/src/observability/types.ts`
- Modify: `frontend/src/observability/ObservabilityPage.tsx`
- Modify: `frontend/src/styles.css`

Steps:
- [ ] Add the new internal summary types to the frontend model layer.
- [ ] Replace the tool-event placeholder with a real panel that renders the returned summaries.
- [ ] Replace the action-ledger placeholder with a real panel that renders the returned summaries.
- [ ] Keep the benchmark-artifacts and recovery-path placeholders unchanged.
- [ ] Add empty states for runs that have no tool events or no action-ledger rows.
- [ ] Add only the minimum CSS needed for legible lists/cards.

### Task 3: Lock in the behavior with tests

Files:
- Modify: `tests/test_observability.py`
- Modify: `tests/integration/test_observability_gateway.py`
- Modify: `frontend/src/observability/ObservabilityPage.test.tsx`
- Modify: `frontend/src/observability/api.test.ts`

Steps:
- [ ] Add a unit test that asserts the service returns sanitized tool-event and action-ledger summaries.
- [ ] Add an integration test that seeds one run with tool events and one action-ledger row and asserts the API response contains the new lists.
- [ ] Add frontend tests that render the new panels and still show the existing placeholder panels for benchmark and recovery.
- [ ] Update the API client fixture shape so Vitest continues to compile against the widened response.
- [ ] Verify the tests assert that no raw IDs or idempotency keys leak into the returned payloads.

### Task 4: Update docs and verify the full slice

Files:
- Modify: `README.md`
- Modify: `docs/WEB_DEMO_README.md`

Steps:
- [ ] Update the public docs to state that `/observability` now shows tool-event and action-ledger detail panels.
- [ ] Keep the documentation explicit that benchmark-artifact and recovery-path inspection are future work.
- [ ] Run the focused backend and frontend verification commands below.
- [ ] Confirm `git diff --check` and `git status --short` are clean before commit.
- [ ] Commit with the expected conventional message and push the branch.

## 6. Testing Plan

- Unit tests:
  - `InternalObservabilityService` returns additive tool-event and action-ledger summaries.
  - summary previews are sanitized and omit forbidden fields.
  - empty tool-event or action-ledger lists render safely.
- Integration tests:
  - the internal observability API returns the new summaries for a seeded run.
  - the response remains backward compatible for existing internal fields.
- Frontend tests:
  - the `/observability` page renders the new panels.
  - placeholder panels for benchmark artifacts and recovery path remain visible.
  - the internal API client fixture matches the widened response shape.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add internal observability detail panels
```

Expected commands:

```bash
git status --short
git add README.md docs/WEB_DEMO_README.md backend/app/repositories/action_ledger.py backend/app/observability/schemas.py backend/app/observability/service.py frontend/src/styles.css frontend/src/observability/types.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/ObservabilityPage.test.tsx frontend/src/observability/api.test.ts tests/test_observability.py tests/integration/test_observability_gateway.py
git diff --cached --check
git commit -m "feat: add internal observability detail panels"
git push -u origin codex/037-internal-observability-detail-panels-v0
```

The implementer must confirm `.env`, secrets, `var/`, caches, build output, and unrelated untracked files are not staged.

## 9. Out-of-scope Changes

- Do not add benchmark artifact browsing.
- Do not add recovery-path visualization or replay linkage.
- Do not split the frontend into separate deployables.
- Do not change public demo contracts or customer-facing pages.
- Do not add authentication or RBAC.
- Do not add database tables, Alembic migrations, or package dependencies.
- Do not change workflow routing, confirmation behavior, execution behavior, or benchmark grading.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `frontend/dist/`, `.env`, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The internal observability API includes sanitized tool-event summaries.
- [ ] The internal observability API includes sanitized action-ledger summaries.
- [ ] Existing internal summary fields remain unchanged.
- [ ] The `/observability` page renders the new panels.
- [ ] The benchmark-artifacts and recovery-path panels are still placeholders.
- [ ] The public demo surface remains unchanged.
- [ ] Backend and frontend tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated untracked file was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- Verification commands and results.
- Commit hash.
- Push result.
- Confirmation that the new summaries are sanitized.
- Confirmation that the public demo contract was untouched.
- Confirmation that benchmark-artifacts and recovery-path panels were intentionally left as placeholders.
