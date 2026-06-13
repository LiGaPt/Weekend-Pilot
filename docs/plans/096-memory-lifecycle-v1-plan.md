# Plan: 096 Memory lifecycle v1

## 1. Spec Reference

Spec file:

```text
docs/specs/096-memory-lifecycle-v1.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/memory-decision-log-v0`.
- Latest commit is `348acd1 feat: add memory decision audit log`, which matches Task `095`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `095`.
- The working tree currently has unrelated untracked docs:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Focused memory-path verification already passes before this task:
  - `python -m pytest tests/test_memory_query_policy.py tests/integration/test_repositories.py tests/test_benchmark_harness.py -k "memory or governable" -q`
  - observed result: `15 passed`
- Current memory behavior is partially converged but not fully modeled:
  - repository exposes `list_active_for_user(...)` and `list_governable_for_user(...)`
  - workflow already loads governable memory
  - memory policy already supports expired advisory behavior
  - benchmark audit surfaces already exist
  - explicit lifecycle states `disabled`, `ignored`, and `candidate` are not yet first-class and legacy `archived` still appears in tests

## 3. Files to Add

- `backend/app/memory_lifecycle.py` - shared lifecycle types, legacy alias mapping, and effective lifecycle resolution helper.
- `tests/test_memory_lifecycle.py` - focused unit coverage for lifecycle resolution and legacy alias behavior.

## 4. Files to Modify

- `backend/app/repositories/memory.py` - normalize supported statuses on create and align active/governable queries with lifecycle rules.
- `backend/app/workflow/state.py` - add `lifecycle_state` to `WorkflowMemoryRecord`.
- `backend/app/workflow/nodes.py` - populate `lifecycle_state` while loading memory rows into workflow state.
- `backend/app/planning/memory_query_policy.py` - prefer workflow lifecycle state when deciding expired-vs-active behavior, while keeping existing summary contracts backward compatible.
- `backend/app/benchmark/schemas.py` - validate benchmark fixture memory status against supported statuses plus legacy alias.
- `backend/app/benchmark/cases/family_memory_expired_advisory_v1.json` - switch the expired-memory fixture to explicit status `expired`.
- `tests/integration/test_repositories.py` - extend repository assertions for active, expired, candidate, disabled, ignored, and legacy archived input behavior.
- `tests/test_memory_query_policy.py` - add coverage proving explicit lifecycle-state-aware expired handling remains backward compatible.
- `tests/integration/test_langgraph_workflow_gateway.py` - add one workflow-path assertion that only governable lifecycle states reach the policy and that explicit expired status still behaves as expired advisory memory.
- `tests/test_benchmark_harness.py` - keep fixture-loading coverage aligned with the explicit `expired` status benchmark case.

## 5. Implementation Steps

1. Add the shared lifecycle helper first.
   Create `backend/app/memory_lifecycle.py` with:
   - `MemoryLifecycleState = Literal["active", "expired", "disabled", "ignored", "candidate"]`
   - `PersistedMemoryStatus = Literal["active", "expired", "disabled", "ignored", "candidate", "archived"]`
   - one legacy alias map:
     - `archived -> ignored`
   - one canonical normalization helper for incoming persisted statuses
   - one deterministic resolver:
     - input: `status`, `expires_at`, optional `now`
     - output: effective lifecycle state
   Use UTC-aware logic and treat naive datetimes as UTC.

2. Lock the lifecycle helper rules with failing unit tests before wiring other layers.
   In `tests/test_memory_lifecycle.py`, add exact tests for:
   - `active + no expires_at -> active`
   - `active + future expires_at -> active`
   - `active + past expires_at -> expired`
   - `expired + no expires_at -> expired`
   - `disabled -> disabled`
   - `ignored -> ignored`
   - `candidate -> candidate`
   - `archived -> ignored`
   - unsupported status raises a deterministic error

3. Update repository write/read behavior to use the helper.
   In `backend/app/repositories/memory.py`:
   - normalize incoming `status` inside `create(...)`
   - persist `ignored` when the caller passes legacy `archived`
   - keep `list_active_for_user(...)` returning only effective active rows
   - keep `list_governable_for_user(...)` returning effective active or expired rows only
   - do not introduce non-deterministic ordering
   Implement the query logic so that:
   - explicit stored `expired` rows are included in governable reads
   - active rows with past expiry are also included in governable reads
   - `disabled`, `ignored`, `candidate`, and normalized legacy archived rows are excluded from governable reads

4. Extend repository integration coverage immediately after the repository changes.
   In `tests/integration/test_repositories.py`:
   - keep the existing active-memory assertions
   - add one explicit `expired` row
   - add one `candidate` row
   - add one `disabled` row
   - add one `ignored` row
   - keep one legacy `archived` creation path and assert it is normalized to `ignored`
   Verify:
   - `list_active_for_user(...)` returns only the effective active row
   - `list_governable_for_user(...)` returns exactly the active row plus both expired variants
   - non-governable rows are absent from both list methods where appropriate

5. Add lifecycle state to workflow-loaded records without renaming the state key.
   In `backend/app/workflow/state.py`, add `lifecycle_state` to `WorkflowMemoryRecord`.
   In `backend/app/workflow/nodes.py`, update `_memory_record(...)` to:
   - preserve the persisted `status` string
   - compute `lifecycle_state` from the new helper
   - continue serializing `expires_at` as ISO text
   Do not change `active_memories` key name or graph topology.

6. Keep memory policy backward compatible while preferring explicit lifecycle state.
   In `backend/app/planning/memory_query_policy.py`:
   - when deciding whether a memory is expired, first read `memory.lifecycle_state` if present
   - map `lifecycle_state == "expired"` to the existing expired behavior
   - fall back to current `expires_at` parsing only when `lifecycle_state` is absent
   - do not rename `memory_query_policy_v1`
   - do not change existing `decision_log`, `policy_summary`, `dimension_outcomes`, or score contract names
   In `tests/test_memory_query_policy.py`, add or update assertions proving:
   - a direct `WorkflowMemoryRecord` with `lifecycle_state="expired"` still produces the expired advisory behavior
   - old-style fixtures without lifecycle state still behave the same through fallback parsing

7. Update benchmark fixture parsing, but do not expand benchmark scope.
   In `backend/app/benchmark/schemas.py`, constrain `BenchmarkMemoryItem.status` to the supported persisted statuses plus legacy alias `archived`.
   Update `backend/app/benchmark/cases/family_memory_expired_advisory_v1.json` so the memory item uses:
   - `status = "expired"`
   Keep the rest of the case unchanged.

8. Add one workflow-path integration test that proves repository/workflow consistency.
   In `tests/integration/test_langgraph_workflow_gateway.py`, add one focused test that:
   - creates a user and seeds memory rows with statuses `active`, `expired`, `candidate`, `disabled`, and `ignored`
   - runs the workflow with a vague request using `existing_user_id`
   - inspects persisted `run.metadata_json["workflow"]["memory_policy"]`
   - asserts:
     - expired governable memory is still visible and treated as expired by policy
     - candidate/disabled/ignored memories do not appear in `memory_decisions` or `decision_log`
   Keep this test pre-confirmation if possible so it stays narrow.

9. Refresh benchmark-fixture unit coverage last.
   In `tests/test_benchmark_harness.py`, update or add the smallest assertion needed to confirm:
   - the expired advisory case still loads
   - its memory item status is now `expired`
   - its expected memory-governance contract remains unchanged
   Do not modify suite counts, suite IDs, or release-gate expectations in this task.

10. Run verification in the smallest useful order.
    Run:
    - lifecycle unit tests
    - repository + policy tests
    - DB-backed workflow integration
    - benchmark fixture load test
    Then run `git diff --check` and `git status --short`.

## 6. Testing Plan

- Unit tests:
  - lifecycle resolution helper covers all canonical states plus legacy alias
  - memory policy still applies expired advisory behavior when lifecycle is explicit
  - old fallback behavior still works when lifecycle state is absent
- Integration tests:
  - repository create/list behavior for active, expired, candidate, disabled, ignored, and archived alias
  - workflow only loads governable lifecycle states and still treats expired memory correctly
- Fixture/schema checks:
  - expired advisory benchmark case loads with explicit status `expired`
- Smoke tests:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_memory_lifecycle.py tests/test_memory_query_policy.py tests/integration/test_repositories.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/test_benchmark_harness.py -k "memory or lifecycle or expired" -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add memory lifecycle states
```

Expected commands:

```bash
git status --short
git switch -c codex/memory-lifecycle-v1
git add backend/app/memory_lifecycle.py
git add backend/app/repositories/memory.py
git add backend/app/workflow/state.py
git add backend/app/workflow/nodes.py
git add backend/app/planning/memory_query_policy.py
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/cases/family_memory_expired_advisory_v1.json
git add tests/test_memory_lifecycle.py
git add tests/integration/test_repositories.py
git add tests/test_memory_query_policy.py
git add tests/integration/test_langgraph_workflow_gateway.py
git add tests/test_benchmark_harness.py
git add docs/specs/096-memory-lifecycle-v1.md
git add docs/plans/096-memory-lifecycle-v1-plan.md
git diff --cached --check
git commit -m "feat: add memory lifecycle states"
git push -u origin codex/memory-lifecycle-v1
```

The implementer must confirm `.env`, secrets, `var/`, and the pre-existing unrelated untracked docs are not staged.

## 9. Out-of-scope Changes

- Do not add memory CRUD or user-facing memory controls.
- Do not implement feedback-to-candidate memory creation.
- Do not implement sensitive-memory minimization.
- Do not add new benchmark suites, new case IDs, or gate-threshold changes.
- Do not add or modify Alembic migrations.
- Do not change public API routes or frontend behavior.
- Do not stage unrelated local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/096-memory-lifecycle-v1.md`.
- [ ] Effective lifecycle states are exactly `active`, `expired`, `disabled`, `ignored`, and `candidate`.
- [ ] Legacy `archived` input is still readable and is normalized to `ignored` for new writes.
- [ ] `list_active_for_user(...)` and `list_governable_for_user(...)` now reflect effective lifecycle semantics, not inconsistent ad hoc filtering.
- [ ] `WorkflowMemoryRecord.lifecycle_state` is populated correctly.
- [ ] Existing expired advisory memory-governance behavior still passes unchanged.
- [ ] Candidate, disabled, and ignored memory do not leak into planning.
- [ ] No benchmark suite membership or gate semantics changed.
- [ ] Required unit and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit, excluding pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- the exact files changed
- the final lifecycle resolution rules implemented
- whether legacy `archived` was normalized on write
- verification commands run and their results
- one example of a workflow-loaded expired memory record including `lifecycle_state`
- confirmation that candidate/disabled/ignored rows no longer reach memory policy
- the commit hash and push result
- any remaining follow-up task, especially that candidate-memory generation and sensitive-memory minimization remain future work
