# Spec: 109 Memory User Control Baseline v0

## 1. Goal

Add the smallest auditable user-control loop for long-term memory so that WeekendPilot memory is no longer only a read-only query-shaping policy. After this task, the backend must support listing a user’s persisted memory items and applying user-controlled state changes that prevent specific memories from influencing future planning.

The goal is not to build a full memory-management product. The goal is to add one narrow backend baseline that is testable end-to-end: a caller can inspect memory rows, disable or suppress a memory row, and verify that the changed row no longer participates in workflow memory loading or query shaping. Every control action must leave durable audit metadata on the memory row or in repository state.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines long-term memory governance as part of the V1/V2 path and states the relevant product rules this task must preserve:

- current user input overrides long-term memory
- low-confidence memory should not strongly influence plans
- expired memory should be ignored or downgraded
- memory should be governable, auditable, and bounded

`docs/NEXT_PHASE_ROADMAP.md` keeps the default near-term emphasis on benchmark and observability infrastructure, but the current repository has already completed that baseline chain through Task `108`, including stage timing reporting, internal observability, benchmark completeness, and integrity gate hardening.

The roadmap’s remaining open memory-governance closure explicitly includes memory CRUD / user control / stronger minimization. The latest memory chain already established the required prerequisites:

- Task `096` added explicit lifecycle states `active`, `expired`, `disabled`, `ignored`, and `candidate`.
- Task `097` added bounded feedback-to-candidate memory generation.
- Task `098` expanded benchmark coverage for disabled / ignored / candidate / sensitive-minimization scenarios.

That makes this task the next smallest useful M5 follow-up. It should add backend-only user control over existing memory rows without expanding into frontend UI, permission systems, or full physical deletion semantics.

## 3. Requirements

### A. Add durable audit metadata to memory rows

- Add `metadata_json` to `memory_items` as a non-null JSON object field with default `{}`.
- Add one Alembic migration that backfills existing rows to `{}`.
- Keep all existing columns and unique constraints unchanged.
- Existing repository create/update paths must remain backward compatible; if they accept `metadata_json`, it must be optional and default to an empty object.

### B. Add one backend-only memory user-control service

- Add one dedicated service that supports:
  - listing all memory rows for one user
  - applying one control action to one memory row for that user
- The service must work with the existing `memory_items` table and repository layer.
- The service must not create new memory rows in this task.
- The service must not modify `value_json`, `text`, `confidence`, `expires_at`, or key identity when applying control actions.

### C. Support exactly two control actions in v0

- Supported control actions in this task must be exactly:
  - `disable`
  - `suppress`
- `disable` must set the row’s persisted `status` to `disabled`.
- `suppress` must set the row’s persisted `status` to `ignored`.
- `suppress` is the delete-equivalent baseline for this task because it preserves auditability on the existing schema.
- This task must not perform physical row deletion.
- This task must not add a restore / re-enable action.

### D. Record a durable governance audit trail for every applied control action

- Applied control actions must append one event into `memory_items.metadata_json["governance"]["control_events"]`.
- Each stored control event must include:
  - `schema_version`
  - `action`
  - `from_status`
  - `to_status`
  - `actor`
  - `source`
  - `reason`
  - `acted_at`
- The exact fixed values in this task must be:
  - `schema_version = "memory_user_control_v0"`
  - `actor = "user"`
  - `source = "internal_memory_api_v0"`
- `reason` may be nullable or empty, but the field must exist in the stored event payload.
- The memory row’s `updated_at` timestamp must change when an action is applied.
- If an existing row has missing or malformed `metadata_json`, the service must rebuild the governance subtree from an empty object instead of failing the request.

### E. Make control actions idempotent

- If a control request targets a row that is already at the same persisted status:
  - the request must succeed
  - the response must mark the operation as not newly applied
  - the service must not append a duplicate control event
- Example:
  - `disable` on an already `disabled` row is a successful no-op
  - `suppress` on an already `ignored` row is a successful no-op

### F. Add a deterministic list surface for all user memory rows

- Add repository support for `list_for_user(user_id)` that returns all memory rows for that user.
- The list order must be deterministic:
  - `created_at`
  - then `memory_id`
- The user-control list surface must include all statuses, including:
  - `active`
  - `expired`
  - `disabled`
  - `ignored`
  - `candidate`
- The list surface must include effective `lifecycle_state` resolved from persisted `status` plus `expires_at`.

### G. Add one internal API surface for the baseline

- Add `GET /internal/users/{user_id}/memory`.
- Add `POST /internal/users/{user_id}/memory/{memory_id}/control`.
- The list route must return a stable response envelope with:
  - `schema_version`
  - `user_id`
  - `items`
- The control route must accept:
  - `action`
  - `reason`
- The control route must return:
  - `schema_version`
  - `operation`
  - `applied`
  - `item`
- The route must return `404` if the memory row does not exist for the specified user.
- The route must stay backend-only; no frontend UI work is part of this task.

### H. Keep query shaping behavior correct after control actions

- Existing workflow loading must continue to use `list_governable_for_user(...)`.
- Because `list_governable_for_user(...)` already excludes `disabled` and `ignored`, a row changed by:
  - `disable`
  - `suppress`
  must not appear in a later workflow run’s `active_memories`.
- A disabled or suppressed row must therefore not appear in:
  - `workflow.memory_policy.memory_decisions`
  - `workflow.memory_policy.decision_log`
  in later runs, unless some separate future task reactivates it.
- This task must not change the current `memory_query_policy_v1` decision naming or scoring semantics.

### I. Add focused repository, API, and workflow regression tests

- Add unit tests for:
  - list serialization
  - disable
  - suppress
  - idempotent no-op behavior
  - governance event append behavior
- Add repository integration tests for:
  - new `metadata_json`
  - `list_for_user(...)`
  - status transitions plus stored audit metadata
- Add API integration tests for:
  - list route success
  - disable success
  - suppress success
  - idempotent no-op
  - cross-user / missing-row `404`
  - invalid action request validation
- Add workflow regression coverage proving a previously governable row no longer shapes memory policy after disable/suppress.

## 4. Non-goals

- Do not implement frontend memory-management UI.
- Do not implement physical hard deletion of memory rows.
- Do not implement restore, re-enable, merge, edit-value, or retention-policy controls.
- Do not add a complex permission or authentication system.
- Do not widen supported memory keys beyond the current project scope.
- Do not redesign `memory_query_policy_v1`.
- Do not change benchmark suite membership, scoring thresholds, or release-gate logic.
- Do not add vector storage, embeddings, or external memory backends.
- Do not commit `.env`, API keys, tokens, secrets, or generated artifacts.

## 5. Interfaces and Contracts

### Inputs

- Existing `memory_items` rows for one user.
- Existing lifecycle resolution helper:
  - `resolve_memory_lifecycle_state(...)`
- Existing repository filtering behavior:
  - `list_governable_for_user(...)`
- Internal control request payload:
  - `action`
  - `reason`

### Outputs

- New list response for all memory rows for a user.
- New control response for one memory row.
- Durable `metadata_json.governance.control_events` history on changed rows.
- Persisted `status` change to `disabled` or `ignored`.
- No change to current public demo routes or frontend rendering.

### Schemas

Example list response:

```json
{
  "schema_version": "memory_user_control_list_v0",
  "user_id": "3d2eb347-589a-4fd5-8ec9-c0f87cb96c5a",
  "items": [
    {
      "memory_id": "0c7ec1c2-2058-4a51-bf8d-efab64d7c1b0",
      "memory_type": "preference",
      "key": "activity_style",
      "value_json": {
        "preference": "indoor"
      },
      "text": null,
      "confidence": "0.9000",
      "status": "active",
      "lifecycle_state": "active",
      "expires_at": null,
      "last_used_at": null,
      "source_run_id": "8af71dc2-2f5d-4e72-b2eb-3626045fd959",
      "created_at": "2026-06-16T10:00:00+00:00",
      "updated_at": "2026-06-16T10:00:00+00:00",
      "metadata_json": {}
    }
  ]
}
```

Example control request:

```json
{
  "action": "disable",
  "reason": "user_no_longer_wants_this_preference"
}
```

Example applied control response:

```json
{
  "schema_version": "memory_user_control_item_v0",
  "operation": "disable",
  "applied": true,
  "item": {
    "memory_id": "0c7ec1c2-2058-4a51-bf8d-efab64d7c1b0",
    "memory_type": "preference",
    "key": "activity_style",
    "status": "disabled",
    "lifecycle_state": "disabled",
    "metadata_json": {
      "governance": {
        "control_events": [
          {
            "schema_version": "memory_user_control_v0",
            "action": "disable",
            "from_status": "active",
            "to_status": "disabled",
            "actor": "user",
            "source": "internal_memory_api_v0",
            "reason": "user_no_longer_wants_this_preference",
            "acted_at": "2026-06-16T10:15:00+00:00"
          }
        ]
      }
    }
  }
}
```

Example idempotent no-op response:

```json
{
  "schema_version": "memory_user_control_item_v0",
  "operation": "disable",
  "applied": false,
  "item": {
    "memory_id": "0c7ec1c2-2058-4a51-bf8d-efab64d7c1b0",
    "status": "disabled",
    "lifecycle_state": "disabled"
  }
}
```

## 6. Observability

This task does not add a new benchmark or LangSmith surface.

Its auditability must be implemented through durable repository state:

- `memory_items.status`
- `memory_items.updated_at`
- `memory_items.metadata_json.governance.control_events`

The task must not rely on transient logs alone to prove that a control action happened.

The new internal API may return stored `metadata_json`, but it must not introduce prompt, token, secret, or provider-payload leakage through newly invented fields.

## 7. Failure Handling

- If a memory row does not exist, the control route must return `404`.
- If a memory row exists but belongs to another user, the control route must behave as `404`.
- If the request action is not one of `disable` or `suppress`, request validation must fail deterministically.
- If a row’s existing `metadata_json` is missing or malformed, the service must rebuild the governance subtree from `{}` and still apply the action.
- If the database migration has not been applied, the task should fail loudly in integration verification rather than silently degrading.
- If the row is already in the requested target status, the service must return success with `applied = false`.
- If the repository update disappears between read and write, the service must fail clearly instead of pretending the control action succeeded.

## 8. Acceptance Criteria

- [ ] `memory_items` has a non-null `metadata_json` JSON field with default `{}`.
- [ ] Existing repository create/update paths remain backward compatible after the schema change.
- [ ] A backend-only user-control service exists for list + control operations.
- [ ] Supported control actions are exactly `disable` and `suppress`.
- [ ] `disable` persists `status = "disabled"`.
- [ ] `suppress` persists `status = "ignored"`.
- [ ] Applied control actions append one durable governance event into `metadata_json.governance.control_events`.
- [ ] Repeating the same action on an already-matching row succeeds as an idempotent no-op and does not append a duplicate event.
- [ ] `GET /internal/users/{user_id}/memory` returns all user memory rows in deterministic order.
- [ ] The list response includes effective `lifecycle_state` for each row.
- [ ] `POST /internal/users/{user_id}/memory/{memory_id}/control` returns the updated row summary and whether the action was newly applied.
- [ ] Cross-user or missing-row control requests return `404`.
- [ ] A row changed to `disabled` or `ignored` no longer appears in later workflow `active_memories`.
- [ ] A row changed to `disabled` or `ignored` no longer appears in later workflow `memory_decisions` or `decision_log`.
- [ ] No frontend UI, permission system, physical hard delete, restore flow, or new memory key is added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_memory_user_control.py tests/test_db_metadata.py tests/integration/test_repositories.py -k "memory" -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add memory user control baseline
```

## 11. Notes for the Implementer

The most important scoping decision in this task is to treat user-visible delete as logical suppression, not physical deletion. That keeps the task aligned with the existing lifecycle model (`ignored`) and preserves auditability without forcing a larger tombstone or audit-table design.

Do not widen this task into full CRUD, frontend surfaces, restore semantics, or memory-content editing. If implementation pressure suggests true hard delete, new permission boundaries, or a broader governance redesign, stop and report that scope expansion instead.
