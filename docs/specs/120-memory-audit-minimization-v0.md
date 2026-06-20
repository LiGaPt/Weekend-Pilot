# Spec: 120 Memory audit and minimization v0

## 1. Goal

Tighten the new internal memory governance surface so that WeekendPilot long-term memory is easier to audit and stores less sensitive information by default.

After Task `119`, the repository can create, read, update, suppress, and lifecycle-control supported preference memory rows, but two gaps remain. First, the internal memory API does not show how a stored row would currently be treated by the read-memory governance policy, so operators still have to infer whether a row is trusted, advisory, weak, expired-downgraded, or non-governable. Second, the CRUD surface still persists raw `text` and extra `value_json` keys for supported preference memory, even when the same row can be represented safely as one normalized enum value. After this task, supported preference memory must be stored in canonical minimized form, and the internal API must expose a deterministic governance-audit preview that uses the same expired / low-confidence downgrade logic as the workflow policy.

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in these areas:

- long-term memory governance
- PostgreSQL as the durable source of truth
- observability by default
- small, reviewable tasks
- sensitive details should be structured and minimized rather than stored as raw text when possible
- expired memory should be ignored or downgraded
- low-confidence memory should not strongly influence plans

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M5. 恢复与记忆治理`.

The repository is already past the prerequisite chain for this work:

- Task `095` added the compact read-memory decision log and policy summary
- Task `096` added explicit lifecycle states and governable filtering
- Task `097` added bounded sensitive-memory minimization for feedback-generated `candidate` memory
- Task `109` added durable row-level governance events for disable / suppress control
- Task `119` added internal CRUD and lifecycle controls for supported preference memory

That makes this task the next smallest useful follow-up. It does not reopen CRUD scope. It hardens the newly added internal memory surface so that supported governable memory is stored minimally and exposed with a clear audit interpretation.

## 3. Requirements

### A. Keep the governed scope intentionally narrow

- This task must stay backend-only and internal.
- It must continue to support only:
  - `memory_type = "preference"`
  - `key in {"activity_style", "spouse_lighter_meals"}`
- It must not add new governable keys, new memory types, or new public routes.
- It must not change benchmark suite membership, release-gate semantics, or workflow topology.

### B. Add one shared governance-audit classification helper

- Add one shared backend helper for supported preference-memory audit classification.
- The helper must accept the durable fields already available on a memory row:
  - `memory_type`
  - `key`
  - `value_json`
  - `text`
  - `confidence`
  - `status`
  - `expires_at`
  - effective `lifecycle_state` when present
- The helper must produce a deterministic audit preview with these fields:
  - `policy_version`
  - `normalized_value`
  - `governable`
  - `expired`
  - `tier`
  - `audit_status`
  - `audit_reason`
- `policy_version` must be `memory_query_policy_v1`.
- `tier` must be:
  - `trusted`
  - `advisory`
  - `weak`
  - or `null` when the row is not governable or not a supported projected key.
- `audit_status` must use only:
  - `trusted`
  - `advisory`
  - `weak`
  - `unsupported`
  - `not_governable`
- `audit_reason` must use only:
  - `trusted_memory_applied`
  - `low_confidence_downgraded_to_advisory`
  - `expired_memory_downgraded_to_advisory`
  - `weak_signal_not_applied`
  - `unsupported_projected_key`
  - `unrecognized_supported_value`
  - `non_governable_lifecycle`
- The helper must use the same confidence thresholds as the current query policy:
  - trusted when non-expired and `confidence >= 0.8000`
  - advisory when non-expired and `0.5000 <= confidence < 0.8000`
  - advisory when expired and `confidence >= 0.8000`
  - weak otherwise
- The helper must treat `disabled`, `ignored`, and `candidate` lifecycle states as `governable = false` with:
  - `audit_status = "not_governable"`
  - `audit_reason = "non_governable_lifecycle"`

### C. Reuse the shared helper inside query shaping without changing policy behavior

- `backend/app/planning/memory_query_policy.py` must use the shared helper for:
  - normalized value resolution
  - expired detection
  - low-confidence downgrade detection
  - tier selection
- `apply_memory_query_policy(...)` must keep:
  - public function name
  - module path
  - `policy_version = "memory_query_policy_v1"`
  - existing `memory_decisions` outcome names
  - existing `decision_log` status / reason semantics
  - existing `policy_summary` field names and meanings
- This task must not change the observable behavior of the existing benchmark-backed cases for:
  - explicit override
  - advisory fill
  - expired advisory downgrade
  - disabled / ignored exclusion
  - candidate non-governable exclusion

### D. Minimize durable storage for supported preference memory

For supported preference memory created or updated through the internal memory CRUD surface:

- Persist `value_json` in canonical minimized form:
  - exactly `{"preference": "<normalized_value>"}`
- Persist `text = null`.
- Do not persist extra keys from the incoming `value_json`.
- Do not persist raw free-form input text once the normalized supported value has been derived.
- Keep these existing validation rules:
  - unsupported keys are rejected
  - unsupported values are rejected
  - conflicting `value_json["preference"]` and `text` normalization is rejected
- Keep these durable fields unchanged when valid:
  - `confidence`
  - `expires_at`
  - `source_run_id`
  - `source_langsmith_trace_id`
  - `status`

### E. Record durable minimization events on create and applied update

- Create and applied update operations must append one event into:
  - `metadata_json["governance"]["minimization_events"]`
- The minimization event payload must include:
  - `schema_version`
  - `action`
  - `actor`
  - `source`
  - `reason`
  - `normalized_value`
  - `dropped_text`
  - `dropped_value_keys`
  - `acted_at`
- The exact fixed values in this task must be:
  - `schema_version = "memory_audit_minimization_v0"`
  - `actor = "user"`
  - `source = "internal_memory_api_v1"`
- `action` must be:
  - `create`
  - `update`
- `dropped_text` must be `true` when the incoming request supplied non-empty `text` that is not persisted.
- `dropped_value_keys` must list extra incoming `value_json` keys that were not stored.
- No-op updates must not append a new minimization event.
- Existing `metadata_json` that is missing or malformed must be rebuilt safely from `{}`.

### F. Expose additive governance audit preview on internal memory read surfaces

- `GET /internal/users/{user_id}/memory`
- `GET /internal/users/{user_id}/memory/{memory_id}`
- create / update / control / delete mutation responses

must all include one additive field on each returned item:

- `governance_audit`

`governance_audit` must use the shared audit helper and must therefore expose current expired / low-confidence downgrade interpretation for the stored row.

This field must be additive and must not remove any existing item fields introduced by Task `119`.

### G. Keep feedback candidate minimization aligned

- The feedback-generated `candidate` memory path from Task `097` must stay behaviorally unchanged.
- It may reuse the same normalization helper for supported values.
- It must continue to persist:
  - structured `value_json`
  - `text = null`
  - `status = "candidate"`
- This task must not promote feedback-generated `candidate` memory into governable `active` memory.

### H. Add focused unit, API, and workflow regressions

- Add unit tests for the shared governance-audit helper covering:
  - trusted supported memory
  - advisory low-confidence memory
  - expired high-confidence advisory memory
  - weak memory
  - unsupported key
  - non-governable lifecycle
- Add or update CRUD service tests proving:
  - create stores canonical `value_json`
  - create stores `text = null`
  - create appends minimization event
  - update drops extra `value_json` keys
  - update appends minimization event only when applied
  - governance audit preview reports expired / low-confidence downgrade state correctly
- Add or update API tests proving:
  - list and detail routes return `governance_audit`
  - create and update responses show canonical minimized storage
  - non-governable lifecycle rows still return a readable audit preview
- Re-run workflow memory regressions to prove the read-memory policy behavior stays backward compatible after the shared-helper refactor.

## 4. Non-goals

- Do not implement frontend memory-management UI.
- Do not add authentication, permissions, or user-facing memory review flows.
- Do not add new memory types or new projected keys.
- Do not add hard delete, retention-policy redesign, bulk operations, or import/export.
- Do not change `memory_query_policy_v1` outcome names, benchmark thresholds, or suite membership.
- Do not add a new benchmark suite or expand existing suite counts.
- Do not persist raw addresses, phones, tokens, secrets, or other free-form payload fragments as replacement audit fields.
- Do not commit `.env`, API keys, tokens, secrets, or generated artifacts.

## 5. Interfaces and Contracts

### Inputs

- Existing internal memory CRUD routes from Task `119`
- Existing durable `memory_items` fields:
  - `memory_type`
  - `key`
  - `value_json`
  - `text`
  - `confidence`
  - `status`
  - `expires_at`
  - `source_run_id`
  - `source_langsmith_trace_id`
  - `metadata_json`
- Existing workflow read-memory policy path:
  - `apply_memory_query_policy(...)`
- Existing feedback-generated candidate-memory path:
  - `extract_feedback_memory_candidates(...)`

### Outputs

- Canonical minimized storage for supported preference memory created or updated through the internal CRUD surface
- Durable minimization events at `metadata_json.governance.minimization_events`
- Additive `governance_audit` field on internal memory item responses
- Shared audit classification logic reused by both internal CRUD surfaces and query-shaping logic

### Schemas

Example additive item fragment:

```json
{
  "memory_id": "0c7ec1c2-2058-4a51-bf8d-efab64d7c1b0",
  "memory_type": "preference",
  "key": "activity_style",
  "value_json": {
    "preference": "indoor"
  },
  "text": null,
  "confidence": "0.7000",
  "status": "active",
  "lifecycle_state": "active",
  "governance_audit": {
    "policy_version": "memory_query_policy_v1",
    "normalized_value": "indoor",
    "governable": true,
    "expired": false,
    "tier": "advisory",
    "audit_status": "advisory",
    "audit_reason": "low_confidence_downgraded_to_advisory"
  }
}
```

Example non-governable lifecycle preview:

```json
{
  "governance_audit": {
    "policy_version": "memory_query_policy_v1",
    "normalized_value": "indoor",
    "governable": false,
    "expired": false,
    "tier": null,
    "audit_status": "not_governable",
    "audit_reason": "non_governable_lifecycle"
  }
}
```

Example minimization event:

```json
{
  "schema_version": "memory_audit_minimization_v0",
  "action": "update",
  "actor": "user",
  "source": "internal_memory_api_v1",
  "reason": "normalize_manual_memory",
  "normalized_value": "outdoor",
  "dropped_text": true,
  "dropped_value_keys": [
    "address",
    "note"
  ],
  "acted_at": "2026-06-19T10:00:00+00:00"
}
```

## 6. Observability

This task must add auditability in two bounded ways:

- durable minimization events on the memory row:
  - `metadata_json.governance.minimization_events`
- additive internal API audit preview:
  - `item.governance_audit`

It must keep the current run-level compact policy audit summary unchanged at:

- `agent_runs.metadata_json["workflow"]["memory_policy"]`

The new audit surfaces must remain sanitized:

- no raw free-form text copied into `governance_audit`
- no addresses, phone numbers, tokens, secrets, prompts, or debug payloads copied into minimization events
- no raw incoming extra `value_json` payload fragments copied into stored audit fields beyond dropped key names

## 7. Failure Handling

- Unsupported memory type or key must continue to fail deterministically.
- Unsupported normalized values must continue to fail deterministically.
- Conflicting `value_json["preference"]` and `text` normalization must continue to fail deterministically.
- If `metadata_json` is malformed, the service must rebuild the governance subtree from `{}` and proceed safely.
- If the shared helper sees a non-governable lifecycle state, it must return a readable audit preview instead of throwing.
- If the shared helper sees an unsupported key, it must return `audit_status = "unsupported"` instead of mutating workflow intent.
- If the query-policy refactor diverges from existing benchmark-backed behavior, focused workflow and benchmark-facing tests must fail.
- If an update request is a no-op, the service must return success with `applied = false` and must not append a new minimization event.

## 8. Acceptance Criteria

- [ ] A shared governance-audit helper exists and is used by both internal memory CRUD surfaces and `apply_memory_query_policy(...)`.
- [ ] Supported preference memory created or updated through the internal CRUD surface is stored with canonical minimized `value_json`.
- [ ] Supported preference memory created or updated through the internal CRUD surface persists `text = null`.
- [ ] Incoming extra `value_json` keys are not persisted for supported preference memory.
- [ ] Create and applied update append durable minimization events under `metadata_json.governance.minimization_events`.
- [ ] No-op updates do not append duplicate minimization events.
- [ ] Internal memory list, detail, and mutation responses include additive `governance_audit`.
- [ ] `governance_audit` exposes current expired / low-confidence downgrade interpretation for governable rows.
- [ ] `governance_audit` exposes readable `not_governable` status for `disabled`, `ignored`, and `candidate` rows.
- [ ] Existing `memory_query_policy_v1` outcome names, `decision_log` reasons, and `policy_summary` semantics remain backward compatible.
- [ ] Feedback-generated `candidate` memory remains minimized and non-governable.
- [ ] No frontend UI, new route, new memory key, retention redesign, or benchmark-suite expansion is introduced.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_crud_governance.py -q
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py -q
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: tighten memory audit and minimization
```

## 11. Notes for the Implementer

Keep this task narrow and hardening-focused.

The most important design boundary is that Task `120` should not invent a second memory product surface. It should tighten the existing one. The safest implementation is:

- one shared helper for governance classification
- one canonical minimized storage shape for supported preference memory
- one additive durable minimization event stream
- one additive internal audit preview

Do not widen this task into user-facing review UI, benchmark-suite expansion, retention policy work, or broader memory extraction. If the implementation pressure suggests changing supported memory keys or redesigning the read-memory policy contract, stop and report that scope expansion instead.
