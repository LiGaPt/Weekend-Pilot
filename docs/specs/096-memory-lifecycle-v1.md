# Spec: 096 Memory lifecycle v1

## 1. Goal

Add one explicit memory lifecycle contract for the backend so that memory rows, workflow-loaded memory records, and memory-governance evaluation all agree on which memories are governable, which are merely retained, and which must never influence planning.

Today the repository effectively distinguishes only “active and not expired” versus “everything else,” while the workflow and memory policy still rely on a mix of `status`, `expires_at`, and historical test conventions such as `archived`. That is not enough for the next memory tasks. After this task, WeekendPilot must support the lifecycle states `active`, `expired`, `disabled`, `ignored`, and `candidate`, must preserve current read-memory governance behavior for expired-but-governable memory, and must make repository loading plus workflow behavior consistent without changing public API or UI surfaces.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines long-term memory governance as part of the V1/V2 path and sets the relevant rules this task must preserve:

- current user input overrides long-term memory
- low-confidence memory should not strongly influence plans
- expired memory should be ignored or downgraded
- memory should be governable and auditable, not merely stored

In `docs/NEXT_PHASE_ROADMAP.md`, the default near-term focus is still benchmark and observability infrastructure, but the repository already advanced that line substantially through Tasks `092` to `095`, including V2 integrity taxonomy, the integrity gate, Pass^4 stability metrics, and memory decision audit logging. Focused memory-path tests currently pass, and there is no spec/plan continuity gap through Task `095`.

That makes `096` the next smallest useful task in milestone `M5`: it closes the remaining lifecycle-model gap underneath memory governance and unblocks the next follow-up tasks around candidate memory and sensitive-memory minimization. This task must stay backend-only and must not turn into full memory management.

## 3. Requirements

### A. Introduce one canonical lifecycle contract

- Add one shared backend lifecycle helper module for memory statuses.
- The canonical effective lifecycle states for this task must be exactly:
  - `active`
  - `expired`
  - `disabled`
  - `ignored`
  - `candidate`
- The canonical persisted statuses accepted by new code must be:
  - `active`
  - `expired`
  - `disabled`
  - `ignored`
  - `candidate`
- For backward compatibility, persisted status `archived` must remain readable as a legacy alias and must map to effective lifecycle state `ignored`.
- New writes through repository code must not persist `archived`; they must normalize it to `ignored`.

### B. Define exact lifecycle resolution rules

- Effective lifecycle resolution must use both persisted `status` and `expires_at`.
- The exact rules must be:

  1. persisted `disabled` -> effective lifecycle `disabled`
  2. persisted `ignored` -> effective lifecycle `ignored`
  3. persisted `candidate` -> effective lifecycle `candidate`
  4. persisted `expired` -> effective lifecycle `expired`
  5. persisted legacy `archived` -> effective lifecycle `ignored`
  6. persisted `active` with `expires_at` in the past or equal to now -> effective lifecycle `expired`
  7. persisted `active` with `expires_at` null or in the future -> effective lifecycle `active`

- The lifecycle helper must be deterministic and timezone-safe.
- Naive datetimes must be treated as UTC, matching current memory policy expiry handling.

### C. Keep repository behavior aligned with lifecycle semantics

- Keep `MemoryItemRepository.create(...)` public signature unchanged in this task.
- `create(...)` must validate or normalize incoming memory status via the shared lifecycle helper before persisting.
- `list_active_for_user(user_id)` must return only effective lifecycle `active` rows.
- `list_governable_for_user(user_id)` must return only effective lifecycle `active` and `expired` rows.
- `list_governable_for_user(...)` must continue deterministic ordering by `created_at`, then `memory_id`.
- `list_governable_for_user(...)` must exclude rows whose effective lifecycle is:
  - `disabled`
  - `ignored`
  - `candidate`
- Explicit persisted `expired` rows must be included in `list_governable_for_user(...)`.
- Active rows whose `expires_at` is already in the past must also remain included in `list_governable_for_user(...)`, because the existing `memory_query_policy_v1` still needs to see them as expired governable memory.
- Do not add new repository list methods in this task unless they are strictly required to keep the above behavior coherent.

### D. Keep workflow loading consistent with repository semantics

- Keep workflow state key `active_memories` unchanged in this task.
- Add one additive field to `WorkflowMemoryRecord`:
  - `lifecycle_state`
- `lifecycle_state` must hold the effective lifecycle state produced by the shared helper.
- `WeekendPilotWorkflowNodes.load_memory(...)` must continue to read from `list_governable_for_user(...)`.
- `load_memory(...)` must populate `WorkflowMemoryRecord.lifecycle_state` for every loaded memory row.
- Workflow-loaded memory must therefore contain only `active` or `expired` lifecycle states in normal operation.

### E. Keep memory-governance behavior backward compatible

- `apply_memory_query_policy(...)` must keep its public name and module path unchanged.
- Existing `memory_query_policy_v1` outcome names, decision-log shape, and policy-summary shape must remain backward compatible.
- Expired governable memory must continue to participate in the policy as expired memory and must still be able to produce `applied_advisory` when existing v1 rules allow it.
- The policy must prefer `WorkflowMemoryRecord.lifecycle_state` when deciding whether a memory is expired.
- If `lifecycle_state` is absent, the policy may fall back to the current `expires_at` parsing behavior for backward compatibility with direct unit-test fixtures.
- Non-governable lifecycle states must never influence effective intent.
- In normal workflow execution, non-governable lifecycle states must not reach the policy because repository loading already filters them out.

### F. Keep benchmark and fixture contracts coherent

- `BenchmarkMemoryItem.status` must validate against the supported persisted statuses plus legacy alias `archived`.
- Existing benchmark suite IDs, suite membership, score names, and release-gate semantics must remain unchanged.
- Update the existing expired-memory benchmark fixture so it uses explicit lifecycle status support:
  - `backend/app/benchmark/cases/family_memory_expired_advisory_v1.json`
  - the memory item status must become `expired`
- The expired-advisory benchmark case must continue to pass without changing its expected `memory_governance` outcome.
- Do not add new benchmark cases or new benchmark suites in this task.

## 4. Non-goals

- Do not implement memory CRUD, user-editable memory controls, or memory deletion flows.
- Do not implement sensitive-memory minimization or feedback-to-candidate generation in this task.
- Do not add public API routes, frontend UI, or reviewer UI for lifecycle state inspection.
- Do not change benchmark suite membership, release-gate thresholds, or score semantics.
- Do not add or modify Alembic revisions, columns, indexes, or tables.
- Do not redesign `memory_query_policy_v1` beyond what is needed to consume the explicit lifecycle contract.
- Do not commit `.env`, API keys, tokens, secrets, or generated benchmark artifacts under `var/`.

## 5. Interfaces and Contracts

### Inputs

- persisted `memory_items.status`
- persisted `memory_items.expires_at`
- `MemoryItemRepository.create(...)`
- `MemoryItemRepository.list_active_for_user(...)`
- `MemoryItemRepository.list_governable_for_user(...)`
- `WorkflowMemoryRecord`
- `BenchmarkMemoryItem.status`

### Outputs

- canonical effective lifecycle state for memory rows
- workflow-loaded `WorkflowMemoryRecord.lifecycle_state`
- repository lists that consistently include or exclude memories by effective lifecycle
- unchanged memory-governance summaries that still treat expired governable memory correctly

### Schemas

Lifecycle contract example:

```json
{
  "persisted_statuses": ["active", "expired", "disabled", "ignored", "candidate"],
  "legacy_aliases": {
    "archived": "ignored"
  },
  "effective_lifecycle_examples": [
    {
      "persisted_status": "active",
      "expires_at": null,
      "effective_lifecycle": "active",
      "governable": true
    },
    {
      "persisted_status": "active",
      "expires_at": "2026-05-01T12:00:00+00:00",
      "effective_lifecycle": "expired",
      "governable": true
    },
    {
      "persisted_status": "expired",
      "expires_at": null,
      "effective_lifecycle": "expired",
      "governable": true
    },
    {
      "persisted_status": "candidate",
      "expires_at": null,
      "effective_lifecycle": "candidate",
      "governable": false
    },
    {
      "persisted_status": "archived",
      "expires_at": null,
      "effective_lifecycle": "ignored",
      "governable": false
    }
  ]
}
```

Workflow memory record excerpt after this task:

```json
{
  "memory_id": "6f58ce5f-53d0-4c5d-96d8-e1af22f2d112",
  "memory_type": "preference",
  "key": "activity_style",
  "confidence": "1.0",
  "expires_at": "2026-05-01T12:00:00+00:00",
  "status": "active",
  "lifecycle_state": "expired"
}
```

## 6. Observability

This task does not add a new observability surface.

It must preserve current internal auditability by keeping the existing `workflow.memory_policy`, `decision_log`, and `policy_summary` contracts compatible. The main change is that expired-vs-active status must be resolved consistently before or during workflow loading, not inferred inconsistently from multiple layers.

If an additive lifecycle field is logged internally through existing workflow metadata or tests, it must remain sanitized and must not expose secrets or unrelated raw payloads.

## 7. Failure Handling

- If a new write path passes unsupported memory status text, repository code must fail fast with a clear validation error instead of persisting ambiguous status.
- If existing rows contain legacy status `archived`, reads must continue to work by mapping it to effective lifecycle `ignored`.
- If a memory row has persisted status `active` but its `expires_at` is already in the past, the effective lifecycle must be `expired`.
- If a memory row has persisted status `expired` and no `expires_at`, it must still be treated as expired.
- If benchmark fixture status is unsupported, fixture loading must fail deterministically.
- If a non-governable lifecycle state somehow reaches memory policy code directly, it must not mutate effective intent.

## 8. Acceptance Criteria

- [ ] A shared lifecycle helper exists and defines canonical lifecycle states `active`, `expired`, `disabled`, `ignored`, and `candidate`.
- [ ] Legacy persisted status `archived` is still readable and resolves to effective lifecycle `ignored`.
- [ ] New repository writes no longer persist `archived`; they normalize it to `ignored`.
- [ ] `list_active_for_user(...)` returns only effective lifecycle `active` rows.
- [ ] `list_governable_for_user(...)` returns only effective lifecycle `active` and `expired` rows.
- [ ] `list_governable_for_user(...)` excludes `disabled`, `ignored`, and `candidate` rows.
- [ ] `WorkflowMemoryRecord` includes `lifecycle_state`.
- [ ] `load_memory(...)` populates `lifecycle_state` consistently from repository rows.
- [ ] Existing expired-memory governance behavior remains valid for both:
  - persisted `expired` rows
  - persisted `active` rows whose `expires_at` is already past
- [ ] Existing `memory_query_policy_v1` decision names and policy-summary fields remain backward compatible.
- [ ] The expired-advisory benchmark fixture uses explicit status `expired` and still passes.
- [ ] No benchmark suite membership, release-gate semantics, public API, or UI surface changes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except for unrelated local files that already existed before this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_memory_lifecycle.py tests/test_memory_query_policy.py tests/integration/test_repositories.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/test_benchmark_harness.py -k "memory or lifecycle or expired" -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add memory lifecycle states
```

## 11. Notes for the Implementer

Keep this task narrow and infrastructure-focused.

The key design constraint is that `expired` is still governable in V1 memory policy, while `candidate`, `disabled`, and `ignored` are not. That means repository filtering must not collapse `expired` into “non-active and therefore invisible,” and it must not let `candidate` leak into planning.

Do not widen this task into candidate generation, memory CRUD, retention policy redesign, or benchmark-suite expansion. If implementation pressure suggests a migration or a public API change, stop and report that scope expansion instead.
