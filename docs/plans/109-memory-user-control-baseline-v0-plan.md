# Plan: 109 Memory User Control Baseline v0

## 1. Spec Reference

Spec file:

```text
docs/specs/109-memory-user-control-baseline-v0.md
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

- Current branch is `codex/108-stage-timing-percentile-reporting-v0`.
- Latest completed numbered task is `108`.
- Latest commit is:

  ```text
  98ba7e0 feat: harden stage timing percentile reporting
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched through `108`.
- There is no tracked `109` spec or plan yet.
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Existing memory-governance prerequisites are already in place:
  - lifecycle states `active`, `expired`, `disabled`, `ignored`, `candidate`
  - feedback-generated `candidate` memory
  - benchmark cases proving `disabled` / `ignored` / `candidate` do not affect query shaping
- Current repository gap:
  - no service for listing a user’s memory rows
  - no service or API for user-driven disable / suppress actions
  - `memory_items` does not currently store dedicated audit metadata
- Existing query-shaping exclusion path already relies on repository filtering:
  - `list_governable_for_user(...)` returns only `active` / `expired`
  - workflow `load_memory(...)` reads only from `list_governable_for_user(...)`

## 3. Files to Add

- `alembic/versions/0003_add_memory_item_metadata_json.py` - add `metadata_json` to `memory_items` with server default/backfill behavior.
- `backend/app/memory_control/__init__.py` - export memory user-control service and schemas.
- `backend/app/memory_control/schemas.py` - define request/response models, action enums, item summary models, and governance event models.
- `backend/app/memory_control/service.py` - implement list + control logic, idempotency rules, and governance metadata append behavior.
- `backend/app/api/memory.py` - add internal memory list/control routes.
- `tests/test_memory_user_control.py` - unit tests for the service and audit metadata behavior.
- `tests/integration/test_memory_api_gateway.py` - integration tests for list/control API behavior.

## 4. Files to Modify

- `backend/app/models/runtime.py` - add `metadata_json` to `MemoryItem`.
- `backend/app/repositories/memory.py` - support `metadata_json`, add `list_for_user(...)`, and add focused status/metadata update support.
- `backend/app/main.py` - register the new memory router.
- `tests/test_db_metadata.py` - update metadata expectations for `memory_items.metadata_json`.
- `tests/integration/test_repositories.py` - add repository integration coverage for list ordering, metadata persistence, and state transitions.
- `tests/integration/test_langgraph_workflow_gateway.py` - add workflow regression coverage proving controlled rows do not re-enter query shaping.
- `docs/specs/109-memory-user-control-baseline-v0.md` - save the approved spec.
- `docs/plans/109-memory-user-control-baseline-v0-plan.md` - save this implementation plan.

## 5. Implementation Steps

1. Reconfirm baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm work starts from the committed `108` baseline and unrelated untracked files remain untouched.

2. Add schema support for auditable memory metadata.
   - In `backend/app/models/runtime.py`, add `metadata_json` to `MemoryItem`:
     - type `JSONB`
     - non-null
     - default `dict`
   - Add Alembic migration `0003_add_memory_item_metadata_json.py`:
     - add column
     - backfill existing rows to `{}` before making it non-null if required by the chosen SQL
   - Update `tests/test_db_metadata.py` so `memory_items` now requires `metadata_json`.

3. Keep repository create/update paths backward compatible.
   - In `backend/app/repositories/memory.py`:
     - add optional `metadata_json: dict[str, Any] | None = None` to `create(...)`
     - add optional `metadata_json: dict[str, Any] | None = None` to `update(...)`
     - coerce missing values to `{}` so existing call sites do not break
   - Do not force changes across unrelated callers.

4. Add repository helpers needed by the control service.
   - In `backend/app/repositories/memory.py`:
     - add `list_for_user(user_id)` ordered by `created_at`, then `memory_id`
     - add one focused update helper for user-control state changes, for example:
       - `update_status_and_metadata(memory_id, *, status, metadata_json)`
     - keep existing `get_by_id(...)` and `get_by_user_memory_key(...)`
   - Preserve current `list_governable_for_user(...)` semantics unchanged.

5. Define memory-control schemas and deterministic contracts.
   - In `backend/app/memory_control/schemas.py`, define:
     - `MemoryUserControlAction = Literal["disable", "suppress"]`
     - `MemoryControlEvent`
     - `MemoryControlItemSummary`
     - `MemoryControlListResponse`
     - `MemoryControlRequest`
     - `MemoryControlMutationResponse`
   - `MemoryControlItemSummary` must include:
     - `memory_id`
     - `memory_type`
     - `key`
     - `value_json`
     - `text`
     - `confidence`
     - `status`
     - `lifecycle_state`
     - `expires_at`
     - `last_used_at`
     - `source_run_id`
     - `created_at`
     - `updated_at`
     - `metadata_json`

6. Implement the user-control service.
   - In `backend/app/memory_control/service.py`, add:
     - `MemoryUserControlServiceError(status_code, message)`
     - `MemoryUserControlService`
   - Service methods must include:
     - `list_items(user_id)`
     - `apply_action(user_id, memory_id, action, reason)`
   - Action rules:
     - `disable -> disabled`
     - `suppress -> ignored`
   - Service behavior:
     - load row
     - verify row belongs to user, else raise `404`
     - derive target status
     - resolve current lifecycle state for response
     - detect idempotent same-target requests
     - for newly applied action:
       - rebuild malformed/missing governance metadata as empty
       - append one control event into `metadata_json["governance"]["control_events"]`
       - persist new `status` and `metadata_json`
   - Fixed event fields:
     - `schema_version = "memory_user_control_v0"`
     - `actor = "user"`
     - `source = "internal_memory_api_v0"`

7. Add the internal API routes.
   - In `backend/app/api/memory.py`, add:
     - `GET /internal/users/{user_id}/memory`
     - `POST /internal/users/{user_id}/memory/{memory_id}/control`
   - Follow the existing API error-handling style:
     - rollback on service error
     - return `HTTPException` with service status/message
   - Commit the DB transaction on successful control mutations.
   - Register the router in `backend/app/main.py`.

8. Add focused unit tests for memory control logic.
   - In `tests/test_memory_user_control.py`, cover:
     - list serialization includes all lifecycle states
     - disable changes `status` to `disabled`
     - suppress changes `status` to `ignored`
     - repeated disable on already-disabled row returns `applied = false`
     - repeated suppress on already-ignored row returns `applied = false`
     - a newly applied action appends exactly one governance event
     - malformed existing `metadata_json` is rebuilt safely
     - control events preserve `value_json` and `text`

9. Extend repository integration coverage.
   - In `tests/integration/test_repositories.py`:
     - seed rows across `active`, `expired`, `candidate`, `disabled`, `ignored`
     - assert `list_for_user(...)` returns all rows in deterministic order
     - assert `metadata_json` defaults to `{}` on create
     - assert user-control update helper persists:
       - new `status`
       - appended `metadata_json.governance.control_events`
       - updated `updated_at`
     - keep current governable filtering assertions unchanged.

10. Add API integration tests.
    - In `tests/integration/test_memory_api_gateway.py`, use FastAPI `TestClient` or the repo’s existing integration pattern to verify:
      - list route returns all rows
      - disable route updates row and returns `applied = true`
      - suppress route updates row and returns `applied = true`
      - repeated route call returns `applied = false`
      - wrong user or missing row returns `404`
      - invalid action payload fails validation
      - response payload includes `lifecycle_state` and `metadata_json`

11. Add workflow regression coverage.
    - In `tests/integration/test_langgraph_workflow_gateway.py`:
      - seed one governable `active` memory row for a user
      - apply user control to set it to `disabled`
      - run workflow for the same user
      - assert:
        - the row is absent from `active_memories`
        - the row key is absent from `memory_policy.memory_decisions`
        - the row key is absent from `memory_policy.decision_log`
      - repeat or mirror with `suppress -> ignored` if one test can cover both cleanly; otherwise keep one focused disabled regression plus one smaller repository/API assertion for suppress

12. Save the numbered task docs.
    - Save the spec to:
      - `docs/specs/109-memory-user-control-baseline-v0.md`
    - Save the plan to:
      - `docs/plans/109-memory-user-control-baseline-v0-plan.md`
    - Do not touch unrelated historical specs/plans.

13. Run focused verification.
   - Run:
     ```bash
     python -m pytest tests/test_memory_user_control.py tests/test_db_metadata.py tests/integration/test_repositories.py -k "memory" -q
     ```
   - Start infra and migrate:
     ```bash
     docker compose up -d postgres redis
     python -m alembic upgrade head
     ```
   - Run API/workflow regressions:
     ```bash
     python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
     ```
   - Final hygiene:
     ```bash
     git diff --check
     git status --short
     ```

14. Commit only task-relevant files.
   - Create a new branch from current HEAD:
     ```bash
     git switch -c codex/109-memory-user-control-baseline-v0
     ```
   - Stage only the schema, backend, tests, and numbered docs for Task `109`.
   - Commit with:
     ```bash
     git commit -m "feat: add memory user control baseline"
     ```

## 6. Testing Plan

- Unit tests:
  - `tests/test_memory_user_control.py`
    - list response shape
    - disable behavior
    - suppress behavior
    - idempotent no-op behavior
    - governance event append behavior
    - malformed metadata rebuild behavior
- Integration tests:
  - `tests/integration/test_repositories.py`
    - `metadata_json` persistence
    - `list_for_user(...)` ordering
    - status + metadata transition persistence
  - `tests/integration/test_memory_api_gateway.py`
    - list route
    - disable route
    - suppress route
    - `404` and validation failures
  - `tests/integration/test_langgraph_workflow_gateway.py`
    - controlled rows no longer enter query shaping
- Schema/metadata tests:
  - `tests/test_db_metadata.py`
    - `memory_items.metadata_json` is part of the schema contract
- Smoke checks:
  - Alembic upgrade succeeds
  - focused memory workflow tests pass
  - `git diff --check` passes

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_memory_user_control.py tests/test_db_metadata.py tests/integration/test_repositories.py -k "memory" -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add memory user control baseline
```

Expected commands:

```bash
git status --short
git switch -c codex/109-memory-user-control-baseline-v0
git add alembic/versions/0003_add_memory_item_metadata_json.py backend/app/models/runtime.py backend/app/repositories/memory.py backend/app/memory_control/__init__.py backend/app/memory_control/schemas.py backend/app/memory_control/service.py backend/app/api/memory.py backend/app/main.py tests/test_db_metadata.py tests/test_memory_user_control.py tests/integration/test_repositories.py tests/integration/test_memory_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py docs/specs/109-memory-user-control-baseline-v0.md docs/plans/109-memory-user-control-baseline-v0-plan.md
git diff --cached --check
git commit -m "feat: add memory user control baseline"
git push -u origin codex/109-memory-user-control-baseline-v0
```

The implementer must confirm unrelated untracked files, generated artifacts, `.env`, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement frontend memory-management UI.
- Do not add physical hard delete.
- Do not add restore / re-enable actions.
- Do not add memory-content editing or new memory keys.
- Do not redesign `memory_query_policy_v1`.
- Do not change benchmark suites, release-gate thresholds, or system-integrity contracts.
- Do not add auth/permission infrastructure.
- Do not stage `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, `docs/superpowers/`, `var/`, caches, virtual environments, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/109-memory-user-control-baseline-v0.md`.
- [ ] The implementation stayed within backend-only baseline scope.
- [ ] `memory_items` now has `metadata_json`.
- [ ] User-control operations are limited to `disable` and `suppress`.
- [ ] Applied actions append durable governance events.
- [ ] Repeated same-target actions are idempotent and do not append duplicate events.
- [ ] The list route returns all user memory rows, not only governable rows.
- [ ] The control route returns the updated row summary and `applied` flag.
- [ ] Cross-user / missing-row control requests return `404`.
- [ ] Disabled or suppressed rows no longer participate in later workflow memory shaping.
- [ ] No physical delete, frontend UI, restore flow, or permission system was introduced.
- [ ] Focused schema, repository, API, and workflow tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- exact files changed
- whether `metadata_json` was added with a migration and whether upgrade succeeded
- the exact stored governance event shape after one disable and one suppress action
- verification commands run and their results
- whether workflow regression proved controlled rows no longer reach `memory_policy`
- commit hash
- push result
- confirmation that unrelated untracked files stayed untouched
- any known limitation, especially that hard delete and restore remain future work
