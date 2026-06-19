# Plan: 120 Memory audit and minimization v0

## 1. Spec Reference

Spec file:

```text
docs/specs/120-memory-audit-minimization-v0.md
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

- Current branch is `codex/119-memory-crud-governance-v0`.
- Latest commit is:

  ```text
  b6f085a feat: add memory CRUD and lifecycle controls
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched through Task `119`, including the special matched pair `113.5`.
- Latest numbered task is `119`, and the latest commit already corresponds to it.
- Focused memory regressions currently pass:
  - `tests/test_memory_query_policy.py`
  - `tests/test_memory_user_control.py`
  - `tests/test_memory_crud_governance.py`
  - `tests/integration/test_memory_api_gateway.py`
  - `tests/integration/test_memory_crud_api_gateway.py`
  - `tests/integration/test_langgraph_workflow_gateway.py -k "memory"`
- Current repository gap after Task `119`:
  - internal memory CRUD persists raw `text` for supported preference memory
  - internal memory CRUD persists extra `value_json` keys for supported preference memory
  - internal memory API does not expose how a stored row would currently be interpreted by the read-memory policy
  - expired / low-confidence downgrade logic exists in workflow policy code, but is not shared with the internal CRUD surface
- Existing unrelated local files must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- `backend/app/memory_governance_audit.py` - shared helper for normalized value resolution, governability, tier selection, and audit preview classification.
- `tests/test_memory_governance_audit.py` - focused unit tests for trusted, advisory, expired, weak, unsupported, and non-governable audit classification cases.
- `docs/specs/120-memory-audit-minimization-v0.md` - saved approved spec.
- `docs/plans/120-memory-audit-minimization-v0-plan.md` - saved implementation plan.

## 4. Files to Modify

- `backend/app/memory_control/schemas.py` - add the additive `governance_audit` response model and attach it to internal memory item payloads.
- `backend/app/memory_control/service.py` - canonicalize supported preference storage, drop raw `text`, append minimization events, and serialize the shared audit preview.
- `backend/app/memory_control/__init__.py` - export any new audit response models if needed.
- `backend/app/planning/memory_query_policy.py` - refactor to consume the shared audit helper while preserving existing `memory_query_policy_v1` behavior and output contracts.
- `backend/app/feedback/memory_candidates.py` - optionally reuse the shared normalization helper so candidate-memory minimization stays aligned with the new canonical storage contract.
- `tests/test_memory_query_policy.py` - keep existing read-memory policy behavior assertions valid under the helper refactor.
- `tests/test_memory_crud_governance.py` - update CRUD expectations to the minimized storage contract and minimization-event behavior.
- `tests/integration/test_memory_api_gateway.py` - keep baseline list/control coverage valid when item payloads gain additive `governance_audit`.
- `tests/integration/test_memory_crud_api_gateway.py` - add API assertions for canonical storage and additive audit preview.
- `tests/integration/test_langgraph_workflow_gateway.py` - keep or extend focused memory regressions so helper reuse does not change workflow behavior.
- `docs/specs/120-memory-audit-minimization-v0.md` - save final spec content.
- `docs/plans/120-memory-audit-minimization-v0-plan.md` - save final plan content.

## 5. Implementation Steps

1. Reconfirm the execution baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm the starting point is the committed Task `119` baseline and unrelated local docs remain out of scope.

2. Add the shared governance-audit helper module.
   - Create `backend/app/memory_governance_audit.py`.
   - Move the reusable pieces of supported preference interpretation into this module:
     - supported-key lookup
     - normalized value resolution
     - expired detection
     - confidence parsing
     - tier selection
   - Add one public helper that returns the additive audit preview fields required by the spec:
     - `policy_version`
     - `normalized_value`
     - `governable`
     - `expired`
     - `tier`
     - `audit_status`
     - `audit_reason`
   - Keep the helper independent of user-override logic. It should classify one stored memory row in isolation.

3. Write focused helper unit tests first.
   - In `tests/test_memory_governance_audit.py`, add deterministic unit tests for:
     - trusted active supported memory
     - low-confidence advisory supported memory
     - expired high-confidence advisory memory
     - weak supported memory
     - unsupported key
     - disabled / ignored / candidate lifecycle states returning `not_governable`
   - Assert exact `audit_status`, `audit_reason`, `tier`, `expired`, and `normalized_value`.

4. Refactor query-policy internals to use the helper without changing behavior.
   - In `backend/app/planning/memory_query_policy.py`, replace duplicate normalization / tier / expiry logic with the shared helper.
   - Keep the existing public response contract unchanged:
     - `memory_decisions`
     - `decision_log`
     - `policy_summary`
     - `policy_version = "memory_query_policy_v1"`
   - Preserve the current decision mapping:
     - advisory from low confidence -> `low_confidence_downgraded_to_advisory`
     - advisory from expired high-confidence -> `expired_memory_downgraded_to_advisory`
     - weak -> `suppressed_weak_signal`
     - unsupported key -> `unsupported_key`
     - unrecognized value -> `unrecognized_value`

5. Tighten internal memory CRUD storage to canonical minimized form.
   - In `backend/app/memory_control/service.py`, replace the current “validate only” flow with “validate and canonicalize”.
   - For supported preference memory create/update:
     - derive the canonical normalized value
     - persist `value_json = {"preference": "<normalized_value>"}`
     - persist `text = None`
     - preserve `confidence`, `expires_at`, `status`, `source_run_id`, and `source_langsmith_trace_id`
   - Keep conflict and unsupported-value rejection behavior unchanged.
   - Do not change the supported key set.

6. Add durable minimization events.
   - In `backend/app/memory_control/service.py`, extend the governance metadata handling to maintain:
     - `metadata_json["governance"]["minimization_events"]`
   - Append one event for:
     - create
     - applied update
   - Each event must include:
     - `schema_version = "memory_audit_minimization_v0"`
     - `action`
     - `actor = "user"`
     - `source = "internal_memory_api_v1"`
     - `reason`
     - `normalized_value`
     - `dropped_text`
     - `dropped_value_keys`
     - `acted_at`
   - Do not append events for no-op updates.
   - Rebuild malformed governance metadata from `{}` exactly once before appending.

7. Extend internal memory response schemas with additive audit preview.
   - In `backend/app/memory_control/schemas.py`, add one response model for `governance_audit`.
   - Attach it to:
     - `MemoryControlItemSummary`
     - `MemoryDetailResponse`
     - mutation item payloads through the shared item summary
   - Keep existing response fields from Task `119` intact and additive.

8. Serialize the shared audit preview from the service.
   - In `backend/app/memory_control/service.py`, update `_serialize_item(...)` to call the shared helper and populate `governance_audit`.
   - Ensure list, detail, create, update, control, and delete responses all use the same serialization path.
   - The preview must derive current expired / low-confidence downgrade interpretation live from the stored row rather than persisting a stale snapshot.

9. Align feedback candidate normalization if needed.
   - In `backend/app/feedback/memory_candidates.py`, reuse the shared normalization helper only if it reduces duplication without widening scope.
   - Keep feedback candidate behavior unchanged:
     - `status = "candidate"`
     - `text = null`
     - minimal structured `value_json`
   - Do not add new candidate keys or promotion behavior.

10. Update CRUD unit tests to the new minimized-storage contract.
    - In `tests/test_memory_crud_governance.py`, update or add assertions for:
      - create stores only canonical `value_json`
      - create stores `text is None`
      - create records a minimization event
      - update drops extra `value_json` keys and clears stored `text`
      - update records a minimization event only when applied
      - item payload includes `governance_audit`
      - expired / low-confidence rows show the expected additive audit preview
    - Keep the existing Task `119` lifecycle-control behavior checks.

11. Update API integration tests.
    - In `tests/integration/test_memory_crud_api_gateway.py`, add assertions that:
      - create response returns minimized `value_json`
      - create response returns `text = null`
      - detail response returns `governance_audit`
      - low-confidence or expired rows surface the expected audit preview
      - candidate / ignored / disabled rows surface `audit_status = "not_governable"`
    - In `tests/integration/test_memory_api_gateway.py`, keep older route coverage valid when item payloads gain additive `governance_audit`.

12. Re-run and, only if needed, extend workflow memory regressions.
    - Prefer to keep `tests/integration/test_langgraph_workflow_gateway.py` unchanged if current coverage already proves behavior preservation.
    - If one extra assertion is needed, add only a narrow regression that confirms helper reuse did not change:
      - expired advisory behavior
      - disabled / ignored exclusion
      - created candidate exclusion

13. Save the numbered docs.
    - Save the spec to:
      - `docs/specs/120-memory-audit-minimization-v0.md`
    - Save the plan to:
      - `docs/plans/120-memory-audit-minimization-v0-plan.md`
    - Do not modify unrelated historical numbered docs.

14. Run focused verification before commit.
    - Run:
      ```bash
      python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_crud_governance.py -q
      ```
    - Run API regressions:
      ```bash
      python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py -q
      ```
    - Run workflow memory regressions:
      ```bash
      python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
      ```
    - Final hygiene:
      ```bash
      git diff --check
      git status --short
      ```

15. Commit only task-relevant files on a new branch.
    - Create and switch to:
      ```bash
      git switch -c codex/120-memory-audit-minimization-v0
      ```
    - Stage only the helper, memory-control, query-policy, focused tests, and numbered docs for Task `120`.
    - Commit with:
      ```bash
      git commit -m "feat: tighten memory audit and minimization"
      ```

## 6. Testing Plan

- Unit tests:
  - `tests/test_memory_governance_audit.py`
    - trusted
    - advisory low-confidence
    - advisory expired
    - weak
    - unsupported
    - non-governable lifecycle
  - `tests/test_memory_query_policy.py`
    - existing override / advisory / expired / weak / unsupported behavior remains unchanged
  - `tests/test_memory_crud_governance.py`
    - canonical storage
    - dropped text
    - dropped extra value keys
    - minimization-event append
    - additive `governance_audit`
- Integration tests:
  - `tests/integration/test_memory_api_gateway.py`
    - baseline list/control route compatibility
  - `tests/integration/test_memory_crud_api_gateway.py`
    - create/detail/update minimized storage
    - additive audit preview
    - candidate / ignored / disabled audit preview
  - `tests/integration/test_langgraph_workflow_gateway.py`
    - existing memory behavior still passes after helper reuse
- Smoke checks:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_crud_governance.py -q
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py -q
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: tighten memory audit and minimization
```

Expected commands:

```bash
git status --short
git switch -c codex/120-memory-audit-minimization-v0
git add backend/app/memory_governance_audit.py backend/app/memory_control/schemas.py backend/app/memory_control/service.py backend/app/memory_control/__init__.py backend/app/planning/memory_query_policy.py backend/app/feedback/memory_candidates.py tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_crud_governance.py tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py docs/specs/120-memory-audit-minimization-v0.md docs/plans/120-memory-audit-minimization-v0-plan.md
git diff --cached --check
git commit -m "feat: tighten memory audit and minimization"
git push -u origin codex/120-memory-audit-minimization-v0
```

The implementer must confirm unrelated local docs, `.env`, secrets, generated caches, and artifacts are not staged.

## 9. Out-of-scope Changes

- Do not implement frontend memory-management UI.
- Do not add auth or permission boundaries.
- Do not add new memory keys or memory types.
- Do not redesign retention policies or add hard delete.
- Do not add benchmark cases, expand suite counts, or change release-gate thresholds.
- Do not rename `memory_query_policy_v1` or change its public contract.
- Do not touch unrelated local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Do not stage `var/`, caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/120-memory-audit-minimization-v0.md`.
- [ ] The task stayed backend-only and hardening-focused.
- [ ] Supported memory scope remains limited to `preference`, `activity_style`, and `spouse_lighter_meals`.
- [ ] Internal CRUD create/update now stores canonical minimized `value_json`.
- [ ] Internal CRUD create/update now stores `text = null` for supported preference memory.
- [ ] Durable minimization events are appended only for create and applied update.
- [ ] No-op updates do not append duplicate minimization events.
- [ ] Internal memory item responses include additive `governance_audit`.
- [ ] `governance_audit` reports expired / low-confidence downgrade interpretation correctly.
- [ ] `disabled`, `ignored`, and `candidate` rows report `not_governable` audit status.
- [ ] `memory_query_policy_v1` behavior stayed backward compatible.
- [ ] Feedback-generated candidate memory stayed minimized and non-governable.
- [ ] Focused unit, API, and workflow memory tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back:

- exact files changed
- the final additive `governance_audit` response shape
- the exact minimization-event payload shape
- which fields are now canonicalized or dropped on create/update
- whether `memory_query_policy_v1` behavior changed or remained identical
- verification commands run and their results
- commit hash
- push result
- confirmation that unrelated local docs remained untouched
- any known limitation, especially that user-facing review UI, retention policy work, and broader memory extraction remain future tasks
