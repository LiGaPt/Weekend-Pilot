# Plan: 034 Internal Observability API and Review Console Skeleton v0

## 1. Spec Reference

Spec file:

```text
docs/specs/034-internal-observability-api-and-review-console-skeleton-v0.md
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

- Current branch is:

  ```text
  codex/workflow-stage-timing-and-benchmark-percentiles-v0
  ```

- Latest completed numbered task is `033`.
- Latest commit is:

  ```text
  f6c103f feat: add workflow stage timing and benchmark percentile reports
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `033`.
- Latest commit corresponds to latest numbered task `033`.
- `docs/NEXT_PHASE_ROADMAP.md` still describes the repository as complete through `032`, so Task 034 should explicitly treat Task 033 as the already-finished implementation of roadmap item 1.
- Current untracked local files include:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- These files are not part of Task 034 and must not be staged.
- The existing public demo flow is stable:
  - `python -m pytest tests/test_demo_api.py -q` passes
  - `npm --prefix frontend run test -- --run` passes
  - `npm --prefix frontend run build` passes
- The current public demo contract still includes internal fields:
  - `trace_id`
  - `node_history`
  - `agent_roles`
  - `observability_status`
- There is no existing dedicated internal observability API route.
- There is no existing dedicated internal observability frontend page.
- The current frontend has no router dependency and should keep that constraint in this task.

## 3. Files to Add

- `backend/app/api/observability.py` - internal observability API router.
- `backend/app/observability/service.py` - read-only run observability summary builder.
- `frontend/src/observability/ObservabilityPage.tsx` - internal review console page skeleton.
- `frontend/src/observability/api.ts` - frontend client for the internal observability endpoint.
- `frontend/src/observability/types.ts` - frontend types for the internal observability response.
- `frontend/src/observability/api.test.ts` - frontend API client tests.
- `frontend/src/observability/ObservabilityPage.test.tsx` - frontend page tests.

## 4. Files to Modify

- `README.md` - mention the new internal observability page and endpoint.
- `docs/WEB_DEMO_README.md` - add a short internal review note for `/observability`.
- `backend/app/main.py` - register the new observability router.
- `backend/app/observability/schemas.py` - add backend response models for internal observability summaries.
- `backend/app/demo/service.py` - reuse existing sanitization helpers if needed, but keep public demo behavior unchanged.
- `tests/test_observability.py` - add unit coverage for internal observability summary construction and sanitization.
- `tests/test_demo_api.py` - assert route registration and preserve public demo schema stability.
- `tests/integration/test_observability_gateway.py` - add integration coverage for the new endpoint against persisted data.
- `tests/integration/test_demo_api_gateway.py` - preserve existing public demo route behavior after router expansion.
- `frontend/src/main.tsx` - render `/observability` without adding a router dependency.
- `frontend/src/styles.css` - add minimal styles for the internal page skeleton.

## 5. Implementation Steps

1. Confirm the task baseline before editing.
   - Run:
     ```bash
     git status --short --branch
     git log --oneline -5
     Test-Path docs/specs/034-internal-observability-api-and-review-console-skeleton-v0.md
     Test-Path docs/plans/034-internal-observability-api-and-review-console-skeleton-v0-plan.md
     ```
   - Confirm the repository is currently at Task 033 and that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` remain unstaged.

2. Add backend schema models for the new internal response in `backend/app/observability/schemas.py`.
   - Keep existing recorder-related schemas intact.
   - Add:
     - `InternalObservabilitySummary`
       - `trace_id: str | None`
       - `status: str | None`
       - `local_buffer_written: bool | None`
       - `langsmith_enabled: bool | None`
       - `langsmith_posted: bool | None`
       - `local_buffer_error: dict[str, Any] | None`
       - `langsmith_error: Any | None`
     - `InternalObservabilityRunSummary`
       - `schema_version = "weekendpilot_internal_observability_run_v1"`
       - `run_id: UUID`
       - `status: str`
       - `trace_id: str | None`
       - `case_id: str | None`
       - `agent_version: str`
       - `prompt_version: str`
       - `tool_profile: str`
       - `world_profile: str`
       - `failure_profile: str | None`
       - `created_at: datetime`
       - `updated_at: datetime`
       - `tool_event_count: int`
       - `action_count: int`
       - `execution_status: str | None`
       - `feedback_status: str | None`
       - `observability_status: str | None`
       - `agent_roles: list[str]`
       - `node_history: list[str]`
       - `workflow_timing_summary: WorkflowTimingSummary | None`
       - `observability_summary: InternalObservabilitySummary`

3. Add a dedicated read-only service in `backend/app/observability/service.py`.
   - Create `InternalObservabilityService`.
   - Constructor dependencies:
     - `session: Session`
   - Add `get_run_summary(run_id: UUID) -> InternalObservabilityRunSummary`.
   - Read data from:
     - `AgentRun`
     - selected `Plan`
     - `ToolEvent`
     - `ActionLedger`
     - `run.metadata_json`
   - Build helper methods:
     - `_metadata(run) -> dict[str, Any]`
     - `_trace_id(metadata) -> str | None`
     - `_node_history(metadata) -> list[str]`
     - `_agent_roles(metadata) -> list[str]`
     - `_workflow_timing_summary(metadata) -> WorkflowTimingSummary | None`
     - `_observability_summary(metadata) -> InternalObservabilitySummary`
     - `_execution_status(selected_plan_json) -> str | None`
     - `_feedback_status(selected_plan_json) -> str | None`
   - Reuse sanitized metadata only. Do not open local files.
   - If the run is missing, raise a service-local not-found error that the route maps to `404`.

4. Keep sanitization explicit in the internal service.
   - Reuse `sanitize_trace_payload` for nested observability error payloads if needed.
   - Reuse `sanitize_demo_payload` only if that avoids duplication cleanly; otherwise keep internal sanitization local to observability.
   - Never expose:
     - tool event raw payloads
     - action ledger raw payloads
     - IDs such as `action_id`, `tool_event_id`, `event_id`, `idempotency_key`
     - secret-bearing keys
   - Only expose counts and summary-level fields in Task 034.

5. Add the internal API router in `backend/app/api/observability.py`.
   - Route:
     ```python
     @router.get("/internal/runs/{run_id}/observability", response_model=InternalObservabilityRunSummary)
     ```
   - Inject DB session with `get_db`.
   - Call `InternalObservabilityService`.
   - Map not-found to `HTTPException(status_code=404, detail="Observability run was not found.")`.
   - Map unexpected exceptions to `500` with a generic detail string.
   - Keep this route independent from the public demo router.

6. Register the new router in `backend/app/main.py`.
   - Import the router.
   - `app.include_router(...)` after health/demo router setup.
   - Do not change CORS configuration in this task.

7. Add focused backend unit tests in `tests/test_observability.py`.
   - Add a helper to create a run with:
     - `workflow.timing`
     - `observability`
     - `agents.results`
     - `demo.initial_node_history`
     - optional selected plan feedback/execution data
   - Add tests for:
     - successful summary construction with timing and observability fields
     - `workflow_timing_summary` being `None` when absent
     - sanitized nested observability error content
     - agent role extraction ordering
     - node history combination behavior matching existing persisted metadata
   - Keep existing recorder tests intact.

8. Add backend route smoke checks in `tests/test_demo_api.py`.
   - Preserve current demo route assertions.
   - Add assertion that `create_app()` now includes:
     - `/internal/runs/{run_id}/observability`
   - Do not change existing `DemoRunSummary` serialization assertions.

9. Add backend integration coverage in `tests/integration/test_observability_gateway.py`.
   - Create or reuse a run with persisted metadata and selected plan state.
   - Call the new endpoint through `TestClient`.
   - Assert:
     - `200` for a known run
     - `404` for a missing run
     - response includes overview fields
     - response includes `workflow_timing_summary` when available
     - response includes `observability_summary`
     - forbidden keys are absent from the serialized response
   - Keep current recorder integration tests unchanged.

10. Preserve public demo route behavior in `tests/integration/test_demo_api_gateway.py`.
    - Do not rewrite existing demo tests.
    - Add one regression assertion that public `/demo/runs/{run_id}` still returns the existing shape after the new router is added.
    - The test should confirm public demo status/confirm behavior still works.

11. Add frontend types in `frontend/src/observability/types.ts`.
    - Define:
      - `InternalObservabilitySummary`
      - `InternalObservabilityRunSummary`
    - Match the backend JSON response exactly.
    - Keep these types separate from `frontend/src/types/demo.ts`.

12. Add frontend API client in `frontend/src/observability/api.ts`.
    - Reuse the same base URL pattern as the demo client.
    - Add:
      - `getObservabilityRun(runId: string): Promise<InternalObservabilityRunSummary>`
    - Reuse the existing API error pattern:
      - local connection error
      - backend `404`
      - generic non-2xx
    - Use internal-message text appropriate for reviewers.

13. Add frontend API tests in `frontend/src/observability/api.test.ts`.
    - Assert request URL:
      - `http://127.0.0.1:8000/internal/runs/<run_id>/observability`
    - Assert:
      - successful JSON parsing
      - connection failure produces the expected `DemoApiError`-style error
      - `404` produces a reviewer-readable not-found message
    - Keep tests isolated from the existing demo API tests.

14. Add the review console page skeleton in `frontend/src/observability/ObservabilityPage.tsx`.
    - Page behavior:
      - one text input for `run_id`
      - one load button
      - validation hint for empty input
      - loading state while request is in flight
      - success rendering using the internal response
      - not-found / generic error banner
    - Render sections:
      - run overview
      - workflow timing summary
      - node history
      - agent roles
      - observability summary
      - placeholders:
        - tool events
        - action ledger
        - benchmark artifacts
        - recovery path
    - If timing is missing:
      - show a neutral “暂无 workflow timing summary” message instead of erroring
    - Do not add polling, live refresh, filters, or artifact downloads.

15. Add frontend page tests in `frontend/src/observability/ObservabilityPage.test.tsx`.
    - Mock the new API client.
    - Cover:
      - initial empty state
      - validation on empty input
      - loading state
      - successful render with timing summary
      - successful render with `workflow_timing_summary = null`
      - not-found error
      - generic request error
    - Keep the existing `App.test.tsx` untouched except if shared test helpers are needed.

16. Wire `/observability` in `frontend/src/main.tsx` without a router dependency.
    - Implement a minimal pathname switch:
      - `window.location.pathname === "/observability"` -> render `ObservabilityPage`
      - otherwise -> render existing `App`
    - Do not add `react-router` or any new dependency.
    - Do not change `/` behavior.

17. Add minimal styling in `frontend/src/styles.css`.
    - Reuse current tokens/classes where possible.
    - Add only the layout and section styles needed for the observability skeleton.
    - Keep the customer page styling stable.

18. Update docs only where behavior changed.
    - In `README.md`, add a short note that internal run review is available at `/observability` and uses `/internal/runs/{run_id}/observability`.
    - In `docs/WEB_DEMO_README.md`, add a short “Internal Review Surface” subsection:
      - internal page URL
      - reviewers can paste a `run_id`
      - this page is for internal observability only
    - Do not expand into a full runbook for future detailed observability features.

19. Run focused verification.
    - Backend unit tests:
      ```bash
      python -m pytest tests/test_observability.py tests/test_demo_api.py -q
      ```
    - Backend integration tests:
      ```bash
      docker compose up -d postgres redis
      python -m alembic upgrade head
      python -m pytest tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py -v
      ```
    - Frontend unit tests:
      ```bash
      npm --prefix frontend run test -- --run
      ```
    - Frontend build:
      ```bash
      npm --prefix frontend run build
      ```
    - Final hygiene:
      ```bash
      git diff --check
      git status --short
      ```

20. Stage and commit only intended files.
    - Stage:
      ```bash
      git add README.md docs/WEB_DEMO_README.md backend/app/main.py backend/app/api/observability.py backend/app/observability/schemas.py backend/app/observability/service.py frontend/src/main.tsx frontend/src/styles.css frontend/src/observability tests/test_observability.py tests/test_demo_api.py tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py docs/specs/034-internal-observability-api-and-review-console-skeleton-v0.md docs/plans/034-internal-observability-api-and-review-console-skeleton-v0-plan.md
      ```
    - Before commit, confirm these stay unstaged:
      - `docs/NEXT_PHASE_ROADMAP.md`
      - `docs/TASK_WORKFLOW_PROMPTS.md`
      - `var/`
      - `.env`
      - `frontend/dist`
      - caches
      - virtual environments
      - `node_modules`

## 6. Testing Plan

- Unit tests:
  - internal observability summary model construction from persisted metadata
  - sanitization of nested observability error fields
  - backend route registration for the new internal endpoint
  - frontend internal API client request path and error handling
  - observability page empty, loading, success, missing-timing, and error states
- Integration tests:
  - `/internal/runs/{run_id}/observability` returns a sanitized summary for a real persisted run
  - missing run returns `404`
  - public `/demo/runs*` flow still behaves the same after router expansion
- Smoke tests:
  - `npm --prefix frontend run build`
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add internal observability api and review console skeleton
```

Expected commands:

```bash
git status --short
git add README.md docs/WEB_DEMO_README.md backend/app/main.py backend/app/api/observability.py backend/app/observability/schemas.py backend/app/observability/service.py frontend/src/main.tsx frontend/src/styles.css frontend/src/observability tests/test_observability.py tests/test_demo_api.py tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py docs/specs/034-internal-observability-api-and-review-console-skeleton-v0.md docs/plans/034-internal-observability-api-and-review-console-skeleton-v0-plan.md
git diff --cached --check
git commit -m "feat: add internal observability api and review console skeleton"
git push -u origin <task-034-branch>
```

The implementer must confirm `.env`, secrets, `frontend/dist`, `var/`, and unrelated untracked files are not staged.

## 9. Out-of-scope Changes

- Do not remove internal fields from `DemoRunSummary`.
- Do not split customer and observability frontends into separate apps or deploy targets.
- Do not add `react-router` or any other new dependency.
- Do not add authentication, admin accounts, or access control.
- Do not expose detailed tool-event rows, action-ledger rows, benchmark report bodies, or recovery visualizations.
- Do not parse trace JSONL files or benchmark report files from the API layer.
- Do not change workflow logic, benchmark grading, replay behavior, confirmation behavior, or Action Ledger semantics.
- Do not add database tables, migrations, or environment variables.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, caches, `.venv`, `frontend/dist`, or other local artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/034-internal-observability-api-and-review-console-skeleton-v0.md`.
- [ ] A new internal backend endpoint exists at `GET /internal/runs/{run_id}/observability`.
- [ ] The endpoint returns a sanitized internal summary and `404` for missing runs.
- [ ] The endpoint does not change public `/demo/runs*` contracts.
- [ ] The endpoint does not read local trace or benchmark artifact files.
- [ ] The frontend serves a new `/observability` page without a router dependency.
- [ ] The page renders run overview, workflow timing, node history, agent roles, and observability summary.
- [ ] The page includes placeholder sections for future detailed internal views.
- [ ] The customer page at `/` remains functionally unchanged.
- [ ] Backend unit and integration tests passed.
- [ ] Frontend unit tests and build passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `frontend/dist`, `var/`, or unrelated untracked file was committed.

## 11. Handoff Notes

After implementation, report back with:

- changed files
- verification commands and results
- commit hash
- push result
- confirmation that public demo API behavior remained unchanged
- confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged
- any known limitation, especially:
  - tool events, action ledger, benchmark artifacts, and recovery path are still placeholders in the internal page
  - public demo payload still contains internal fields pending the next frontend-splitting task
