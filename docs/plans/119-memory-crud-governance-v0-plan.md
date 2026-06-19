# Plan: 119 Memory CRUD governance v0

## 1. Spec Reference

Spec file:

```text
docs/specs/119-memory-crud-governance-v0.md
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

- Current branch is `codex/118-recovery-replay-visualization-v0`.
- Latest commit is:

  ```text
  f2e154f feat: connect recovery replay to visualization
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched through Task `118`, with one matched special pair at `113.5`.
- There is no tracked numbered spec or plan above `118`.
- Unrelated local files already present and must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Existing memory baseline already exists in code:
  - lifecycle states from Task `096`
  - feedback candidate-memory path from Task `097`
  - list + disable/suppress internal control API from Task `109`
- Current repository gap for Task `119`:
  - no detail read route
  - no internal create route
  - no internal update route
  - no internal delete route
  - no full lifecycle action set beyond `disable` and `suppress`
  - no generalized governance event contract for all CRUD mutations
- Current supported governable planning memory remains narrow:
  - `memory_type = "preference"`
  - `activity_style`
  - `spouse_lighter_meals`

## 3. Files to Add

- `tests/test_memory_crud_governance.py` - focused unit tests for create, update, detail read, lifecycle mutation, delete alias, validation, and audit events.
- `tests/integration/test_memory_crud_api_gateway.py` - focused API integration tests for the new internal CRUD routes and error handling.
- `docs/specs/119-memory-crud-governance-v0.md` - saved approved spec.
- `docs/plans/119-memory-crud-governance-v0-plan.md` - saved implementation plan.

## 4. Files to Modify

- `backend/app/memory_control/schemas.py` - expand the internal memory API schemas for detail read, create, update, expanded lifecycle actions, and a stable v1 mutation envelope.
- `backend/app/memory_control/service.py` - implement detail, create, update, expanded lifecycle control, delete-as-suppress, value validation, and generalized governance event append logic.
- `backend/app/memory_control/__init__.py` - export any new request/response models and action types.
- `backend/app/api/memory.py` - add detail, create, update, and delete routes; keep existing list/control routes; wire all routes to the expanded service.
- `backend/app/repositories/memory.py` - add any small repository helpers needed for user-scoped detail lookup and persistence without changing current governable-loading semantics.
- `tests/test_memory_user_control.py` - keep Task `109` baseline assertions valid after the lifecycle-action contract expands.
- `tests/integration/test_memory_api_gateway.py` - keep existing list/control route coverage valid after the response schema and action set expand.
- `tests/integration/test_langgraph_workflow_gateway.py` - add one or two workflow regressions proving created governable memory participates later and non-governable memory remains excluded.
- `docs/specs/119-memory-crud-governance-v0.md` - save the final spec content.
- `docs/plans/119-memory-crud-governance-v0-plan.md` - save the final plan content.

## 5. Implementation Steps

1. Reconfirm the baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm the task starts from the committed `118` baseline and that unrelated untracked local files remain out of scope.

2. Expand the internal memory schema contract.
   - In `backend/app/memory_control/schemas.py`, replace the narrow control-only contract with one full internal governance contract.
   - Keep the existing item summary shape as the base reusable model.
   - Add:
     - one detail response model
     - one create request model
     - one update request model
     - one expanded lifecycle action type with exactly:
       - `activate`
       - `disable`
       - `suppress`
       - `expire`
       - `mark_candidate`
     - one stable mutation response model that can represent:
       - `create`
       - `update`
       - `activate`
       - `disable`
       - `suppress`
       - `expire`
       - `mark_candidate`
   - Keep the list response route stable in spirit, but allow the internal schema version to move to a v1 label if needed so long as all routes use the same new contract consistently.

3. Define the exact validation rules inside the service layer.
   - In `backend/app/memory_control/service.py`, add small local helpers that validate:
     - `memory_type == "preference"`
     - `key in {"activity_style", "spouse_lighter_meals"}`
     - canonical normalized values:
       - `activity_style -> citywalk | indoor | outdoor`
       - `spouse_lighter_meals -> lighter_options`
   - Validation rules must be exact:
     - prefer `value_json["preference"]` when present
     - fall back to `text` when needed
     - if both are present and normalize differently, raise a validation error
     - if neither normalizes to a supported canonical value, raise a validation error
   - Do not change `memory_query_policy.py` behavior as part of this task.

4. Generalize the governance event payload while reusing the existing metadata path.
   - Keep the storage location:
     - `metadata_json["governance"]["control_events"]`
   - Add one generalized event builder in `service.py`.
   - New events must write:
     - `schema_version = "memory_crud_governance_v0"`
     - `actor = "user"`
     - `source = "internal_memory_api_v1"`
     - `action`
     - `from_status`
     - `to_status`
     - `reason`
     - `acted_at`
     - `changed_fields`
   - Keep Task `109` event payloads readable without migration.
   - Rebuild malformed or missing governance metadata from `{}` before appending new events.

5. Implement user-scoped detail lookup.
   - In `backend/app/repositories/memory.py`, add one small helper if needed, for example:
     - `get_for_user(user_id, memory_id)`
   - Use it consistently so cross-user access behaves exactly like missing-row access.
   - Do not change `list_governable_for_user(...)`.

6. Implement create in the service.
   - Add `create_item(user_id, request)` in `service.py`.
   - Behavior must be:
     - reject unsupported `memory_type` or `key`
     - validate normalized value
     - reject duplicate `(user_id, memory_type, key)` with `409`
     - normalize status through `normalize_memory_status(...)`
     - create the row via repository
     - append one `create` governance event with:
       - `from_status = null`
       - `to_status = persisted status`
       - full create `changed_fields`
     - persist and return the created item summary
   - Preserve caller-provided:
     - `confidence`
     - `expires_at`
     - `source_run_id`
     - `source_langsmith_trace_id`

7. Implement detail read in the service.
   - Add `get_item(user_id, memory_id)` in `service.py`.
   - Load the row by user scope and return the same item summary used by list and mutation responses.
   - Keep `lifecycle_state` derived through `resolve_memory_lifecycle_state(...)`.

8. Implement update in the service.
   - Add `update_item(user_id, memory_id, request)` in `service.py`.
   - Update exactly:
     - `value_json`
     - `text`
     - `confidence`
     - `expires_at`
   - Reject attempts to change:
     - `memory_type`
     - `key`
     - `source_run_id`
     - `source_langsmith_trace_id`
   - Preserve current `status`.
   - Append one `update` governance event with:
     - `from_status = current status`
     - `to_status = current status`
     - `changed_fields` set to the exact fields that changed
   - If the request does not change any mutable field, return success with `applied = false` and do not append a duplicate event.

9. Expand lifecycle control in the service.
   - Replace the current narrow `_ACTION_TARGET_STATUS` mapping with the full five-action mapping.
   - Keep idempotent no-op behavior for same-target requests.
   - Preserve existing `disable` and `suppress` semantics exactly.
   - Append one governance event for newly applied lifecycle changes with:
     - `changed_fields = ["status"]`
   - Do not modify other durable fields during lifecycle transitions.

10. Implement delete-as-suppress in the service.
    - Add `delete_item(user_id, memory_id, reason)` or equivalent.
    - Internally delegate to the same lifecycle mutation path as `suppress`.
    - Return the same mutation envelope as the control route.
    - Never physically delete the row.

11. Update repository helpers only as needed.
    - Keep `create(...)`, `update(...)`, and `update_status_and_metadata(...)` backward compatible.
    - Add only small additive helpers needed for user-scoped lookup or update ergonomics.
    - Do not widen repository behavior into bulk operations or new list semantics.

12. Add the API routes.
    - In `backend/app/api/memory.py`, keep the existing list and control routes.
    - Add:
      - `GET /internal/users/{user_id}/memory/{memory_id}`
      - `POST /internal/users/{user_id}/memory`
      - `PATCH /internal/users/{user_id}/memory/{memory_id}`
      - `DELETE /internal/users/{user_id}/memory/{memory_id}`
    - Route error handling must match the existing style:
      - rollback on service error
      - map service exceptions to `HTTPException`
      - commit on successful mutations only
    - Keep the router registered through `backend/app/main.py`.

13. Add focused unit tests for the new contract.
    - In `tests/test_memory_crud_governance.py`, cover:
      - create active row success
      - create candidate row success
      - create duplicate key returns conflict
      - create invalid normalized value rejection
      - detail read returns source/confidence/expiry/lifecycle
      - update changes only mutable fields
      - update no-op returns `applied = false`
      - update immutable-field rejection
      - lifecycle actions map to the exact target statuses
      - delete maps to ignored
      - malformed metadata is rebuilt
      - governance event payloads include expected `changed_fields`
    - Keep assertions flat and deterministic.

14. Update the existing Task `109` unit tests.
    - In `tests/test_memory_user_control.py`, replace the old “strict action contract is exactly disable/suppress” assertion with the new Task `119` expanded lifecycle action contract.
    - Preserve the original behavior checks for:
      - disable
      - suppress
      - idempotent no-op
      - governance event append

15. Add focused API integration tests for the new routes.
    - In `tests/integration/test_memory_crud_api_gateway.py`, cover:
      - create success
      - detail success
      - update success
      - delete success
      - duplicate create `409`
      - invalid payload `422`
      - cross-user or missing-row `404`
    - Keep these tests separate from the older Task `109` route file so the new CRUD surface stays reviewable.

16. Update the existing API integration baseline.
    - In `tests/integration/test_memory_api_gateway.py`, keep the existing list/control route coverage valid under the expanded response models and action set.
    - Do not delete the old baseline tests; make them pass under the new contract.

17. Add workflow regressions.
    - In `tests/integration/test_langgraph_workflow_gateway.py`, add:
      - one regression that creates an `active` memory row through the service, runs a workflow for the same user, and asserts the key appears in `memory_policy.memory_decisions`
      - one regression that creates or mutates a row to `candidate` or `ignored`, runs a workflow for the same user, and asserts the key remains absent from `active_memories`, `memory_decisions`, and `decision_log`
    - Do not redesign the workflow to satisfy these tests; the task should only prove the existing repository filtering still works after CRUD additions.

18. Save the numbered docs.
    - Save the spec to:
      - `docs/specs/119-memory-crud-governance-v0.md`
    - Save the plan to:
      - `docs/plans/119-memory-crud-governance-v0-plan.md`
    - Do not modify unrelated historical numbered docs.

19. Run focused verification before commit.
   - Run:
     ```bash
     python -m pytest tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py -k "memory" -q
     ```
   - Start infra and migrate:
     ```bash
     docker compose up -d postgres redis
     python -m alembic upgrade head
     ```
   - Run workflow regressions:
     ```bash
     python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
     ```
   - Final hygiene:
     ```bash
     git diff --check
     git status --short
     ```

20. Commit only task-relevant files.
   - Create a new branch:
     ```bash
     git switch -c codex/119-memory-crud-governance-v0
     ```
   - Stage only the backend, tests, and numbered docs for Task `119`.
   - Commit with:
     ```bash
     git commit -m "feat: add memory CRUD and lifecycle controls"
     ```

## 6. Testing Plan

- Unit tests:
  - `tests/test_memory_user_control.py`
  - `tests/test_memory_crud_governance.py`
  - behaviors:
    - expanded lifecycle action contract
    - create validation
    - update validation
    - detail serialization
    - audit event append
    - idempotent no-op behavior
- Integration tests:
  - `tests/integration/test_memory_api_gateway.py`
  - `tests/integration/test_memory_crud_api_gateway.py`
  - behaviors:
    - list/detail/create/update/control/delete routes
    - duplicate create `409`
    - missing-row and cross-user `404`
    - invalid payload `422`
- Workflow regressions:
  - `tests/integration/test_langgraph_workflow_gateway.py`
  - behaviors:
    - created governable memory influences later runs
    - `candidate`, `disabled`, and `ignored` memory remain excluded
- Smoke checks:
  - `docker compose up -d postgres redis`
  - `python -m alembic upgrade head`
  - `git diff --check`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py -k "memory" -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add memory CRUD and lifecycle controls
```

Expected commands:

```bash
git status --short
git switch -c codex/119-memory-crud-governance-v0
git add backend/app/memory_control/schemas.py backend/app/memory_control/service.py backend/app/memory_control/__init__.py backend/app/api/memory.py backend/app/repositories/memory.py tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py docs/specs/119-memory-crud-governance-v0.md docs/plans/119-memory-crud-governance-v0-plan.md
git diff --cached --check
git commit -m "feat: add memory CRUD and lifecycle controls"
git push -u origin codex/119-memory-crud-governance-v0
```

The implementer must confirm unrelated local files, generated artifacts, `.env`, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement frontend memory-management UI.
- Do not implement auth or permissions.
- Do not implement physical delete.
- Do not add bulk CRUD or import/export.
- Do not add new memory types or new governable keys.
- Do not redesign `memory_query_policy_v1`.
- Do not change benchmark suites, release-gate logic, or workflow topology.
- Do not touch unrelated local files such as:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Do not stage caches, `var/` artifacts, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/119-memory-crud-governance-v0.md`.
- [ ] The task stayed backend-only and internal.
- [ ] Supported memory scope remains limited to `preference`, `activity_style`, and `spouse_lighter_meals`.
- [ ] The API supports list, detail, create, update, control, and delete routes.
- [ ] Create preserves provenance, confidence, and expiry fields.
- [ ] Update does not allow immutable identity or provenance changes.
- [ ] Lifecycle control supports exactly `activate`, `disable`, `suppress`, `expire`, and `mark_candidate`.
- [ ] Delete is logical suppression to `ignored`, not physical deletion.
- [ ] Every mutation appends one durable governance event with `changed_fields`.
- [ ] Idempotent no-op mutations do not append duplicate events.
- [ ] Governable rows still load into later workflow runs when `active` or `expired`.
- [ ] Non-governable rows still stay out of later query shaping when `disabled`, `ignored`, or `candidate`.
- [ ] No frontend UI, auth, hard delete, new memory keys, or benchmark redesign was introduced.
- [ ] Focused unit, API, and workflow tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back:

- exact files changed
- the final route list exposed by `backend/app/api/memory.py`
- the exact lifecycle action set implemented
- the exact governance event payload shape for:
  - create
  - update
  - lifecycle control
  - delete
- verification commands run and their results
- whether workflow regression proved governable rows load and non-governable rows stay excluded
- commit hash
- push result
- confirmation that unrelated local files remained untouched
- any remaining limitation, especially that hard delete, bulk operations, auth, and frontend memory UI remain future work
