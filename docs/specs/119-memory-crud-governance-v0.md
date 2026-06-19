# Spec: 119 Memory CRUD governance v0

## 1. Goal

Extend the existing backend-only memory user-control baseline into one full internal memory governance surface so that WeekendPilot long-term memory is no longer limited to read-path query shaping plus disable/suppress controls.

After this task, the backend must support internal memory create, list, detail read, update, logical delete, and explicit lifecycle mutation while preserving the current memory-governance contract: provenance, confidence, expiry, lifecycle state, and durable governance audit metadata must remain visible and stable. This task must stay small and reviewable: it does not build a user-facing memory-management product, but it does make long-term memory operationally governable.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` places long-term memory governance on the V1/V2 path and defines the rules this task must preserve:

- current user input overrides long-term memory
- low-confidence memory should not strongly influence plans
- expired memory should be ignored or downgraded
- memory should be governable, auditable, and bounded
- PostgreSQL remains the durable source of truth for memory rows

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M5. 恢复与记忆治理`. Although the roadmap says the default near-term focus is `M1`, the current repository has already advanced the benchmark and observability baseline through Task `118`, and there is no higher-priority open breakage in the numbered spec/plan chain.

This task builds directly on the completed memory chain:

- Task `096` introduced explicit lifecycle states
- Task `097` introduced bounded candidate-memory generation
- Task `109` introduced backend list plus disable/suppress user control
- current workflow and benchmark tests already prove that `disabled`, `ignored`, and `candidate` rows stay out of governable query shaping

That makes `119` the next smallest useful follow-up: complete the internal CRUD and lifecycle governance loop without widening into frontend memory UI, full retention redesign, or a broader memory schema expansion.

## 3. Requirements

### A. Keep the governed memory surface intentionally narrow

- This task must stay backend-only and internal.
- Supported memory type in this task must be exactly:
  - `memory_type = "preference"`
- Supported memory keys in this task must be exactly:
  - `activity_style`
  - `spouse_lighter_meals`
- Supported normalized values in this task must be exactly:
  - for `activity_style`: `citywalk`, `indoor`, `outdoor`
  - for `spouse_lighter_meals`: `lighter_options`
- Create and update validation must use the same normalization contract already implied by `memory_query_policy_v1`.
- This task must not expand supported planning memory keys beyond the current project surface.

### B. Preserve and expose existing memory governance fields

Every read and mutation response in this task must include the current durable memory facts:

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
- `source_langsmith_trace_id`
- `created_at`
- `updated_at`
- `metadata_json`

This task must preserve provenance, confidence, and expiry information rather than hiding or rewriting them during governance operations.

### C. Keep deterministic read surfaces and add detail read

- Keep `GET /internal/users/{user_id}/memory` as the list surface.
- Keep deterministic list ordering:
  - `created_at`
  - then `memory_id`
- Add `GET /internal/users/{user_id}/memory/{memory_id}`.
- The list and detail routes must both return all persisted lifecycle states, including:
  - `active`
  - `expired`
  - `disabled`
  - `ignored`
  - `candidate`
- `lifecycle_state` must continue to be resolved from persisted `status` plus `expires_at` through the shared lifecycle helper.

### D. Add internal create support

- Add `POST /internal/users/{user_id}/memory`.
- Create must accept:
  - `memory_type`
  - `key`
  - `value_json`
  - `text`
  - `confidence`
  - `status`
  - `expires_at`
  - `source_run_id`
  - `source_langsmith_trace_id`
  - `reason`
- Create must reject duplicate `(user_id, memory_type, key)` with deterministic `409`.
- Create must reject unsupported memory types, keys, or unrecognized normalized values with deterministic request validation failure.
- Create must normalize lifecycle status through the shared lifecycle helper before persistence.
- If both `value_json["preference"]` and `text` are present and normalize to different supported values, create must fail instead of persisting ambiguous memory.
- Create must preserve the submitted source, confidence, and expiry values when valid.

### E. Add internal update support

- Add `PATCH /internal/users/{user_id}/memory/{memory_id}`.
- Updateable fields in this task must be exactly:
  - `value_json`
  - `text`
  - `confidence`
  - `expires_at`
  - `reason`
- Update must not allow changing:
  - `memory_type`
  - `key`
  - `source_run_id`
  - `source_langsmith_trace_id`
- Update must validate the updated memory content against the same supported key/value contract as create.
- Update must not silently change lifecycle status; lifecycle state changes must go through the lifecycle control route or delete route.
- Update must preserve existing provenance fields.

### F. Expand lifecycle control from baseline into full internal state governance

- Keep `POST /internal/users/{user_id}/memory/{memory_id}/control`.
- Supported lifecycle control actions in this task must be exactly:
  - `activate`
  - `disable`
  - `suppress`
  - `expire`
  - `mark_candidate`
- These actions must map to persisted statuses exactly:
  - `activate -> active`
  - `disable -> disabled`
  - `suppress -> ignored`
  - `expire -> expired`
  - `mark_candidate -> candidate`
- Existing Task `109` semantics for `disable` and `suppress` must remain valid.
- Control actions must be idempotent:
  - if the target row is already at the target persisted status, the request succeeds
  - `applied = false`
  - no duplicate governance event is appended
- Control actions must not modify:
  - `value_json`
  - `text`
  - `confidence`
  - `expires_at`
  - `source_run_id`
  - `source_langsmith_trace_id`

### G. Add delete as logical suppression, not physical removal

- Add `DELETE /internal/users/{user_id}/memory/{memory_id}`.
- Delete in this task must be implemented as the same logical outcome as `suppress`:
  - persisted `status = "ignored"`
- Delete must return the same stable mutation envelope used by other governance operations.
- Delete must be idempotent when the row is already `ignored`.
- This task must not physically remove memory rows from PostgreSQL.

### H. Keep governance audit metadata durable and additive

- All create, update, control, and delete operations must append one event into:
  - `metadata_json["governance"]["control_events"]`
- The stored governance event payload in this task must include:
  - `schema_version`
  - `action`
  - `from_status`
  - `to_status`
  - `actor`
  - `source`
  - `reason`
  - `acted_at`
  - `changed_fields`
- The exact fixed values in new events must be:
  - `schema_version = "memory_crud_governance_v0"`
  - `actor = "user"`
  - `source = "internal_memory_api_v1"`
- `changed_fields` must be:
  - `["memory_type", "key", "value_json", "text", "confidence", "status", "expires_at", "source_run_id", "source_langsmith_trace_id"]` for create
  - the exact subset of changed mutable fields for update
  - `["status"]` for lifecycle control and delete
- Existing older Task `109` events with schema version `memory_user_control_v0` must remain readable.
- If existing `metadata_json` is missing or malformed, the service must rebuild the governance subtree from `{}` and continue.

### I. Keep workflow memory-governance behavior correct

- `list_governable_for_user(...)` must remain unchanged in semantics:
  - only effective lifecycle `active` and `expired` rows are governable
- This task must not change `memory_query_policy_v1` decision names, summary shape, or benchmark grading semantics.
- A row created or moved into:
  - `active`
  - `expired`
  must remain eligible for later workflow loading under current repository rules.
- A row created or moved into:
  - `disabled`
  - `ignored`
  - `candidate`
  must remain excluded from later workflow `active_memories`, `memory_decisions`, and `decision_log`.

### J. Add focused service, API, and workflow regressions

- Add or update unit tests for:
  - create success
  - create duplicate `409`
  - create invalid key/value rejection
  - detail read
  - update success
  - update immutable-field rejection
  - lifecycle action mappings
  - delete-as-suppress behavior
  - idempotent no-op behavior
  - governance event append behavior
- Add or update API integration tests for:
  - list route success
  - detail route success
  - create success
  - update success
  - control success
  - delete success
  - duplicate create `409`
  - cross-user or missing-row `404`
  - invalid payload validation
- Add workflow regression coverage proving:
  - a newly created `active` or `expired` row can shape later runs under existing rules
  - `disabled`, `ignored`, and `candidate` rows remain excluded from later query shaping

## 4. Non-goals

- Do not implement frontend memory-management UI.
- Do not implement authentication or a permission system.
- Do not implement physical hard deletion.
- Do not implement bulk CRUD, import/export, or batch lifecycle operations.
- Do not implement restore history browsing or separate tombstone tables.
- Do not add new memory types or new governable keys.
- Do not redesign `memory_query_policy_v1`, benchmark suites, release-gate thresholds, or workflow topology.
- Do not change feedback candidate-generation semantics from Task `097`.
- Do not commit `.env`, API keys, tokens, secrets, or generated artifacts.

## 5. Interfaces and Contracts

### Inputs

- Existing `memory_items` rows.
- Existing shared lifecycle helper:
  - `normalize_memory_status(...)`
  - `resolve_memory_lifecycle_state(...)`
- Existing repository filtering behavior:
  - `list_for_user(...)`
  - `list_governable_for_user(...)`
- Internal create request payload.
- Internal update request payload.
- Internal lifecycle-control request payload.
- Internal delete request path.

### Outputs

- Deterministic list and detail read surfaces for one user’s memory rows.
- Internal create/update/control/delete mutation responses.
- Durable governance audit metadata under `metadata_json.governance.control_events`.
- Persisted lifecycle transitions that stay compatible with the current workflow and benchmark memory-governance path.

### Schemas

Example create request:

```json
{
  "memory_type": "preference",
  "key": "activity_style",
  "value_json": {
    "preference": "indoor"
  },
  "text": "indoor",
  "confidence": "0.9000",
  "status": "active",
  "expires_at": "2026-07-01T12:00:00+00:00",
  "source_run_id": "7b3ffb1f-1c93-4a34-b032-e90ee4056c34",
  "source_langsmith_trace_id": "trace-memory-manual-1",
  "reason": "manual_memory_seed"
}
```

Example detail or mutation item payload:

```json
{
  "memory_id": "0c7ec1c2-2058-4a51-bf8d-efab64d7c1b0",
  "memory_type": "preference",
  "key": "activity_style",
  "value_json": {
    "preference": "indoor"
  },
  "text": "indoor",
  "confidence": "0.9000",
  "status": "active",
  "lifecycle_state": "active",
  "expires_at": "2026-07-01T12:00:00+00:00",
  "last_used_at": null,
  "source_run_id": "7b3ffb1f-1c93-4a34-b032-e90ee4056c34",
  "source_langsmith_trace_id": "trace-memory-manual-1",
  "created_at": "2026-06-19T08:00:00+00:00",
  "updated_at": "2026-06-19T08:00:00+00:00",
  "metadata_json": {
    "governance": {
      "control_events": [
        {
          "schema_version": "memory_crud_governance_v0",
          "action": "create",
          "from_status": null,
          "to_status": "active",
          "actor": "user",
          "source": "internal_memory_api_v1",
          "reason": "manual_memory_seed",
          "acted_at": "2026-06-19T08:00:00+00:00",
          "changed_fields": [
            "memory_type",
            "key",
            "value_json",
            "text",
            "confidence",
            "status",
            "expires_at",
            "source_run_id",
            "source_langsmith_trace_id"
          ]
        }
      ]
    }
  }
}
```

Example lifecycle control request:

```json
{
  "action": "mark_candidate",
  "reason": "downgrade_for_manual_review"
}
```

Example delete behavior:

```json
{
  "schema_version": "memory_control_item_v1",
  "operation": "suppress",
  "applied": true,
  "item": {
    "memory_id": "0c7ec1c2-2058-4a51-bf8d-efab64d7c1b0",
    "status": "ignored",
    "lifecycle_state": "ignored"
  }
}
```

## 6. Observability

This task does not add a new benchmark suite or LangSmith route.

Its required observability must remain durable and local to the PostgreSQL memory record:

- `memory_items.status`
- `memory_items.updated_at`
- `memory_items.metadata_json.governance.control_events`

The internal API may return governance metadata, but it must not introduce new prompt, token, secret, or provider-payload leakage. Existing workflow and benchmark metadata surfaces must remain backward compatible.

## 7. Failure Handling

- If a memory row does not exist, detail/update/control/delete must return `404`.
- If a memory row exists for another user, the route must behave as `404`.
- If create would violate `(user_id, memory_type, key)`, the API must return `409`.
- If the request uses unsupported `memory_type`, `key`, `status`, or lifecycle action, validation must fail deterministically.
- If the submitted content does not normalize to a supported value for the selected key, validation must fail deterministically.
- If `value_json["preference"]` and `text` normalize to conflicting values, create or update must fail rather than persist ambiguous memory.
- If existing `metadata_json` is malformed, governance metadata must be rebuilt safely from an empty object.
- If the row is already in the requested target status, lifecycle control and delete must succeed with `applied = false`.
- If repository persistence fails between read and write, the service must fail clearly instead of pretending the mutation succeeded.

## 8. Acceptance Criteria

- [ ] The internal memory API supports list, detail, create, update, control, and delete routes.
- [ ] The governed memory surface remains limited to `memory_type = "preference"` and keys `activity_style` / `spouse_lighter_meals`.
- [ ] Read responses expose provenance, confidence, expiry, lifecycle state, and governance metadata.
- [ ] Create preserves valid `source_run_id`, `source_langsmith_trace_id`, `confidence`, and `expires_at`.
- [ ] Create rejects duplicate `(user_id, memory_type, key)` with `409`.
- [ ] Update can modify only `value_json`, `text`, `confidence`, and `expires_at`.
- [ ] Update cannot change `memory_type`, `key`, `source_run_id`, or `source_langsmith_trace_id`.
- [ ] Lifecycle control supports exactly `activate`, `disable`, `suppress`, `expire`, and `mark_candidate`.
- [ ] Delete is implemented as logical suppression to `ignored`, not physical deletion.
- [ ] Control and delete operations are idempotent and do not append duplicate events on no-op requests.
- [ ] Every create, update, control, and delete operation appends one durable governance event.
- [ ] Existing older governance events from Task `109` remain readable.
- [ ] Rows in effective lifecycle `active` and `expired` remain governable for later workflow runs.
- [ ] Rows in effective lifecycle `disabled`, `ignored`, and `candidate` remain excluded from later query shaping.
- [ ] No frontend UI, auth system, bulk CRUD, hard delete, new memory keys, or benchmark-suite redesign is introduced.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_memory_user_control.py tests/integration/test_memory_api_gateway.py -k "memory" -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add memory CRUD and lifecycle controls
```

## 11. Notes for the Implementer

Keep this task deliberately smaller than a full memory product.

The key boundary is that `119` completes internal governance, not end-user productization. The safest design is:

- keep the supported memory domain narrow
- treat delete as logical suppression
- preserve existing workflow memory-governance behavior
- reuse the current durable governance metadata path instead of inventing a second audit system

If implementation pressure suggests hard delete, bulk operations, auth, new memory keys, or benchmark redesign, stop and report that scope expansion instead of folding it into this task.
