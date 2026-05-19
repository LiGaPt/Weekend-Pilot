# Spec: 034 Internal Observability API and Review Console Skeleton v0

## 1. Goal

Add the first internal-only observability read surface for WeekendPilot without changing the customer-facing demo flow.

After this task, the repository should expose one dedicated backend API for internal run observability and one minimal frontend review console page that consumes it. The new surface should let a reviewer inspect a run's internal execution summary by `run_id`, including workflow timing, node history, agent roles, tool/action counts, and observability status, while keeping the existing `/demo/runs*` contract and current customer-facing page unchanged.

This task is the first concrete step under `docs/NEXT_PHASE_ROADMAP.md` milestone M2 "frontend separation." It establishes a separate internal contract before any later task removes internal fields from the public demo payload or fully splits client and observability frontends.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as an observable-by-default, benchmark-driven local-life planning and execution system. The current implementation already includes:

- workflow-backed run execution through FastAPI and LangGraph
- local JSONL observability summaries from Task 017
- benchmark timing summaries and run reports from Task 033
- a minimal Web demo API and UI from Tasks 022-025

The current gap is that internal and customer concerns are still mixed:

- `DemoRunSummary` includes `trace_id`, `node_history`, `agent_roles`, and `observability_status`
- the current frontend renders those internal fields directly in the main customer demo page
- there is no dedicated backend API or frontend page for internal run inspection

`docs/NEXT_PHASE_ROADMAP.md` explicitly prioritizes:
1. M1 evaluation and observability infrastructure
2. then M2 frontend separation

Task 033 delivered the first M1 timing/reporting milestone. Task 034 should now start M2 in the smallest possible way by introducing:

- one internal observability API contract
- one minimal review console page skeleton

It must not yet split the frontend into two deployables, and it must not change workflow behavior, Tool Gateway safety, Human Confirmation, Action Ledger semantics, or benchmark grading behavior.

## 3. Requirements

- Add one internal-only FastAPI read endpoint at:

  ```text
  GET /internal/runs/{run_id}/observability
  ```

- The new endpoint must return a structured, sanitized internal observability summary for the specified run.
- The endpoint must return `404` when the run does not exist.
- The endpoint must not require new environment variables, auth providers, or database tables for this task.
- The endpoint response must be additive to the repository and must not change any existing `/demo/runs*` request or response contract.
- Add a dedicated internal response schema distinct from `DemoRunSummary`.
- The internal response must include:
  - `schema_version`
  - `run_id`
  - `status`
  - `trace_id`
  - `case_id`
  - `agent_version`
  - `prompt_version`
  - `tool_profile`
  - `world_profile`
  - `failure_profile`
  - `tool_event_count`
  - `action_count`
  - `execution_status`
  - `feedback_status`
  - `observability_status`
  - `agent_roles`
  - `node_history`
  - `workflow_timing_summary`
- The internal response must include an `observability_summary` object derived from persisted run metadata with:
  - `trace_id`
  - `status`
  - `local_buffer_written`
  - `langsmith_enabled`
  - `langsmith_posted`
  - `local_buffer_error`
  - `langsmith_error`
- The internal response may include run timestamps for internal review:
  - `created_at`
  - `updated_at`
- The endpoint must source data only from existing persisted state and existing metadata:
  - `agent_runs`
  - `plans`
  - `tool_events`
  - `action_ledger`
  - persisted workflow/observability metadata
- The endpoint must not parse local JSONL trace files or benchmark report files for this task.
- The endpoint must keep all returned payloads sanitized and must not expose:
  - `action_id`
  - `tool_event_id`
  - `event_id`
  - `idempotency_key`
  - `api_key`
  - `token`
  - `secret`
  - `authorization`
  - `prompt`
  - `debug_trace`
  - raw provider request/response bodies
  - raw benchmark report bodies
- Add one internal review console page to the frontend, reachable without adding a router dependency.
- The page must be reachable at:

  ```text
  /observability
  ```

- The page must let a reviewer enter a `run_id` and fetch the internal observability summary from the new backend endpoint.
- The page must render these sections:
  - run overview
  - workflow timing summary
  - node history
  - agent roles
  - observability summary
- The page must also render placeholder sections for future internal views:
  - tool events
  - action ledger
  - benchmark artifacts
  - recovery path
- Placeholder sections must clearly state that the detailed data is not implemented yet in this task.
- The page must handle:
  - initial empty state
  - loading state
  - successful response
  - backend `404`
  - generic request failure
  - missing `workflow_timing_summary`
- The current customer-facing page at `/` must remain functionally unchanged in this task.
- The current public demo API and public frontend tests must continue to pass.
- Update `README.md` and `docs/WEB_DEMO_README.md` to document the new internal observability page and endpoint at a high level.
- Do not require Playwright changes or new end-to-end tests for this task.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not remove internal fields from `DemoRunSummary` yet.
- Do not split the customer and observability frontends into separate apps, builds, or deployable packages yet.
- Do not add detailed tool event tables, action ledger tables, benchmark report browsers, or recovery-path visualizations.
- Do not add authentication, RBAC, admin login, or internal-user management.
- Do not add database tables, Alembic migrations, or package dependencies.
- Do not change workflow routing, benchmark harness behavior, replay behavior, or observability recording behavior.
- Do not read trace JSONL files or benchmark report JSON files directly from the API layer.
- Do not stage or commit `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, or `var/`.

## 5. Interfaces and Contracts

### Inputs

This task depends on existing persisted run state and runtime metadata:

- `AgentRun`
- `Plan`
- `ToolEvent`
- `ActionLedger`
- `agent_runs.metadata_json["workflow"]["timing"]`
- `agent_runs.metadata_json["observability"]`
- `agent_runs.metadata_json["agents"]`
- `agent_runs.metadata_json["demo"]`

Frontend input:

- a `run_id` string entered on `/observability`

### Outputs

New backend output:

```text
GET /internal/runs/{run_id}/observability
```

New frontend output:

```text
/observability
```

New public contracts introduced by this task:

- internal backend schema for run observability
- internal frontend API client and view model for run observability

### Schemas

The backend response should follow this shape:

```json
{
  "schema_version": "weekendpilot_internal_observability_run_v1",
  "run_id": "4dfb35e8-f5a4-4cb8-a2b9-e9c8bd4d4d7a",
  "status": "completed",
  "trace_id": "trace-123",
  "case_id": "web-demo",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": null,
  "created_at": "2026-05-19T13:01:33+08:00",
  "updated_at": "2026-05-19T13:02:10+08:00",
  "tool_event_count": 8,
  "action_count": 2,
  "execution_status": "succeeded",
  "feedback_status": "completed",
  "observability_status": "completed",
  "agent_roles": ["supervisor", "discovery", "dining"],
  "node_history": [
    "initialize",
    "generate_queries",
    "execute_searches",
    "wait_confirmation",
    "saga_execution_engine",
    "generate_summary_message"
  ],
  "workflow_timing_summary": {
    "schema_version": "workflow_timing_summary_v1",
    "total_duration_ms": 913,
    "stage_count": 6,
    "stages": [
      {
        "node_name": "initialize",
        "attempt_count": 1,
        "total_duration_ms": 4
      }
    ]
  },
  "observability_summary": {
    "trace_id": "trace-123",
    "status": "completed",
    "local_buffer_written": true,
    "langsmith_enabled": false,
    "langsmith_posted": false,
    "local_buffer_error": null,
    "langsmith_error": null
  }
}
```

Notes:

- `workflow_timing_summary` may be `null` for older runs or runs that did not persist timing data.
- `node_history` and `agent_roles` must follow current persisted ordering.
- `observability_summary` is derived from sanitized persisted metadata and must remain sanitized.

## 6. Observability

This task adds an internal read surface only. It must not add a new telemetry backend or new recording path.

It must reuse existing persisted observability data and expose it through one sanitized internal contract.

The internal API and internal page must not expose:

- secrets
- API keys
- tokens
- authorization headers
- raw prompts
- raw tool request/response payloads
- raw benchmark report bodies
- raw action ledger request/response bodies
- internal IDs for tool events or actions

If a requested run has no persisted timing summary or no persisted observability metadata, the internal API must still return a valid summary with nullable fields rather than failing.

## 7. Failure Handling

- If the run does not exist, the internal API must return `404`.
- If the run exists but lacks persisted `workflow_timing_summary`, the API must return `workflow_timing_summary: null`.
- If the run exists but lacks persisted `observability` metadata, the API must return `observability_summary` with null/false values instead of erroring.
- If the frontend submits an empty `run_id`, the page must not call the backend and should show a validation hint.
- If the backend returns `404`, the page must show a reviewer-readable not-found state.
- If the request fails for other reasons, the page must show a generic failure state and keep the last successful result cleared.
- This task does not need retry logic, polling, or live streaming updates.
- This task does not need to recover missing trace files or benchmark report files.

## 8. Acceptance Criteria

- [ ] `docs/specs/034-internal-observability-api-and-review-console-skeleton-v0.md` exists and matches this task.
- [ ] A new backend endpoint exists at `GET /internal/runs/{run_id}/observability`.
- [ ] The endpoint returns `404` for missing runs.
- [ ] The endpoint returns a dedicated internal observability response schema distinct from `DemoRunSummary`.
- [ ] The endpoint returns run overview fields, node history, agent roles, tool/action counts, observability status, and `workflow_timing_summary`.
- [ ] The endpoint returns `observability_summary` derived from persisted metadata.
- [ ] The endpoint remains sanitized and does not expose forbidden internal/sensitive keys.
- [ ] The endpoint does not parse local trace files or benchmark report files.
- [ ] The existing `/demo/runs*` backend contract remains unchanged.
- [ ] The frontend serves a new page at `/observability`.
- [ ] The page supports empty, loading, success, not-found, generic-error, and missing-timing states.
- [ ] The page renders run overview, workflow timing summary, node history, agent roles, and observability summary.
- [ ] The page renders placeholder sections for tool events, action ledger, benchmark artifacts, and recovery path.
- [ ] The customer-facing page at `/` remains functionally unchanged.
- [ ] Existing demo API tests still pass.
- [ ] Existing frontend App tests still pass.
- [ ] New focused backend and frontend tests for the internal observability surface pass.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` mention the new internal observability surface.
- [ ] No router dependency, migration, database table, or new package dependency is added.
- [ ] No `.env`, API key, token, secret, generated `dist/`, `var/`, or unrelated untracked file is staged.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/test_demo_api.py -q
python -m pytest tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

If PostgreSQL and Redis are not already available for integration tests:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 10. Expected Commit

```text
feat: add internal observability api and review console skeleton
```

## 11. Notes for the Implementer

Keep this task strictly as the smallest bridge from M1 into M2.

The implementation should introduce a stable internal contract first, not a full frontend split. The safest shape is:

1. read existing persisted run state through a dedicated internal service,
2. expose one sanitized internal API endpoint,
3. add one minimal `/observability` page that consumes it,
4. leave the current customer flow unchanged.

Do not use this task to remove internal fields from `DemoRunSummary`; that belongs in the next frontend-splitting task once the internal surface is stable.
