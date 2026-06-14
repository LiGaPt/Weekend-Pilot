# Plan: 098 Memory Governance Benchmark Suite v2

## 1. Spec Reference

Spec file:

```text
docs/specs/098-memory-governance-suite-v2.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/097-sensitive-memory-feedback-candidate-v0`.
- Latest commit is `9d039d8 feat: add sensitive memory minimization`, which matches Task `097`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `097`.
- There is no higher-priority spec/plan/branch mismatch that should preempt this task.
- Current benchmark inventory contains 22 registered cases.
- Current suite counts are:
  - `memory_governance = 3`
  - `v2_integrity = 12`
  - `all_registered = 22`
  - `default = 11`
  - `release_gate_v1 = 15`
- Current memory-governance grading checks:
  - policy version
  - dimension sources
  - dimension tiers
  - memory outcomes
- Current grading does not fully check:
  - decision-log status/reason/influence
  - absent non-governable keys
  - exact policy-summary counts
  - benchmark-visible sensitive-minimization summary
- The repository already has:
  - `decision_log` and `policy_summary`
  - lifecycle states `disabled`, `ignored`, `candidate`
  - feedback `memory_candidate_summary`
- There are unrelated untracked local docs in the working tree:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- `backend/app/benchmark/cases/family_memory_disabled_ignored_v1.json` - benchmark case proving disabled/ignored memory never reaches governable read-memory policy.
- `backend/app/benchmark/cases/family_memory_candidate_not_auto_active_v1.json` - benchmark case proving `candidate` memory stays non-governable during the current run.
- `backend/app/benchmark/cases/family_memory_sensitive_minimization_v1.json` - benchmark case proving benchmark-visible feedback candidate summary is minimal and safe.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add additive expectation models/fields for richer memory-governance assertions and safe feedback candidate summary exposure.
- `backend/app/benchmark/graders.py` - extend `grade_memory_governance(...)` to validate decision-log details, absent keys, policy-summary counts, and optional feedback candidate summary.
- `backend/app/benchmark/harness.py` - extract safe feedback candidate summary from the selected plan into benchmark case results and pass richer surfaces into grading.
- `backend/app/benchmark/suites.py` - add the three new cases to `memory_governance`, `v2_integrity`, and `all_registered` in exact canonical order.
- `tests/test_benchmark_suites.py` - update registered case order, suite memberships, suite counts, matrix summaries, and V2 integrity expected counts.
- `tests/test_benchmark_harness.py` - add richer grader tests, new fixture-load checks, and new expected benchmark case-result/report fields.
- `tests/test_benchmark_v2_taxonomy.py` - update/add expected taxonomy memory-mode coverage for the new cases.
- `tests/test_benchmark_v2_integrity_gate.py` - update/add expected integrity coverage counts and suite assumptions.
- `tests/integration/test_benchmark_harness_gateway.py` - add end-to-end checks for the three new memory cases and the richer grading surfaces.
- `tests/integration/test_benchmark_v2_integrity_gate.py` - update expected V2 integrity case counts if pinned there.
- Any benchmark summary/count test that hardcodes `memory_governance`, `v2_integrity`, or `all_registered` totals.

## 5. Implementation Steps

1. Re-read the current memory benchmark chain before editing:
   - `backend/app/benchmark/schemas.py`
   - `backend/app/benchmark/graders.py`
   - `backend/app/benchmark/harness.py`
   - `backend/app/benchmark/suites.py`
   - the three existing memory-governance case JSON files
   - benchmark tests that pin suite counts and case order

2. Add additive expectation models in `backend/app/benchmark/schemas.py`.
   Introduce optional shapes for:
   - per-memory decision-log expectations
   - exact policy-summary expectations
   - expected absent memory keys
   - expected feedback memory-candidate summary

3. Keep all new expectation fields optional.
   Existing benchmark fixtures must continue to validate unchanged.

4. Add one additive benchmark case-result field in `backend/app/benchmark/schemas.py` for the safe feedback candidate summary.
   Keep it limited to:
   - `schema_version`
   - `generation_status`
   - `created_keys`
   - `updated_keys`
   - `skipped_keys`

5. Extend `grade_memory_governance(...)` in `backend/app/benchmark/graders.py`.
   Preserve all current checks first:
   - policy version
   - dimension source
   - dimension tier
   - high-level memory outcome

6. Add decision-log validation logic in `grade_memory_governance(...)`.
   For each expected per-key decision entry, compare:
   - key
   - decision outcome
   - normalized `status`
   - normalized `reason`
   - normalized `influence_level`

7. Add absent-key validation in `grade_memory_governance(...)`.
   For each expected absent key, assert it does not appear in either:
   - `memory_decisions`
   - `decision_log`

8. Add exact policy-summary validation in `grade_memory_governance(...)`.
   Compare all expected count fields exactly when the expectation is present.

9. Extend grading inputs so the sensitive-minimization case can inspect the safe feedback candidate summary.
   Use additive benchmark harness plumbing rather than raw plan-json scraping inside tests only.

10. In `backend/app/benchmark/harness.py`, extract the safe feedback candidate summary from the selected plan feedback payload.
    Normalize it into the new additive case-result field.
    Do not copy raw feedback prose, IDs, or provider payloads.

11. Keep the extracted summary nullable for cases that do not exercise this path.

12. Pass the extracted feedback candidate summary into `grade_memory_governance(...)` so the sensitive-minimization case can validate it.

13. Add the three new benchmark JSON cases.

14. Write `family_memory_disabled_ignored_v1.json`.
    Requirements:
    - vague family request
    - one `disabled` memory row for `spouse_lighter_meals`
    - one `ignored` memory row for `activity_style`
    - normal success path expectations
    - memory-governance expectation asserting:
      - no dimension winner from memory
      - absent keys for both memory rows
      - exact zero-count `policy_summary`

15. Write `family_memory_candidate_not_auto_active_v1.json`.
    Requirements:
    - vague family request
    - one `candidate` memory row for `activity_style`
    - normal success path expectations
    - memory-governance expectation asserting:
      - no memory winner
      - absent key for `activity_style`
      - exact zero-count `policy_summary`

16. Write `family_memory_sensitive_minimization_v1.json`.
    Requirements:
    - family request that deterministically yields an indoor/light reviewed plan
    - no governable starting memory
    - normal success path expectations
    - memory-governance expectation asserting:
      - feedback candidate summary exists
      - `generation_status == completed`
      - `created_keys == ["activity_style", "spouse_lighter_meals"]`
      - `updated_keys == []`
      - `skipped_keys == []`

17. Update `backend/app/benchmark/suites.py`.
    Set exact case order for:
    - `memory_governance`
    - `v2_integrity`
    - `all_registered`

18. Keep `default` and `release_gate_v1` unchanged.
    Do not quietly enlarge them.

19. Update V2 taxonomy logic if needed so the three new cases map to distinct memory modes:
    - `disabled_ignored`
    - `candidate_not_auto_active`
    - `sensitive_minimization`

20. Keep existing memory-mode classifications intact for:
    - `override_guarded`
    - `advisory_fill`
    - `expired_advisory`
    - `none`

21. Update `tests/test_benchmark_suites.py`.
    Change:
    - `REGISTERED_CASE_IDS`
    - `MEMORY_GOVERNANCE_CASE_IDS`
    - `V2_INTEGRITY_CASE_IDS`
    - suite counts
    - case-order assertions
    - matrix/tag-count expectations
    - integrity coverage expectations

22. Update `tests/test_benchmark_harness.py`.
    Add or revise:
    - fixture-loading checks for the three new cases
    - unit tests for richer memory-governance expectations
    - one passing grader test for absent keys
    - one passing grader test for exact policy-summary counts
    - one passing grader test for sensitive-minimization feedback summary
    - one failing-path assertion per new surface where useful

23. Update `tests/test_benchmark_v2_taxonomy.py`.
    Assert the new cases resolve to the intended additive memory modes.

24. Update `tests/test_benchmark_v2_integrity_gate.py`.
    Assert:
    - `case_count == 15`
    - `memory_case_count == 6`
    - any other pinned counts that change because of the three new cases

25. Update `tests/integration/test_benchmark_harness_gateway.py`.
    Add end-to-end checks for:
    - `family_memory_disabled_ignored_v1`
    - `family_memory_candidate_not_auto_active_v1`
    - `family_memory_sensitive_minimization_v1`

26. In the disabled/ignored integration case, assert:
    - score `memory_governance` passes
    - `memory_decisions == []`
    - `decision_log == []`
    - `policy_summary.considered_count == 0`

27. In the candidate integration case, assert:
    - score `memory_governance` passes
    - `activity_style` does not appear in decision surfaces
    - `policy_summary.considered_count == 0`

28. In the sensitive-minimization integration case, assert:
    - score `memory_governance` passes
    - case result exposes `feedback_memory_candidate_summary`
    - summary has only the safe schema fields
    - summary matches the expected created/updated/skipped keys

29. Update any integration or summary tests that pin all-registered counts, memory counts, or suite matrix totals.

30. Run focused unit tests first.
    Start with:
    - `tests/test_benchmark_suites.py`
    - `tests/test_benchmark_harness.py`
    - `tests/test_benchmark_v2_taxonomy.py`
    - `tests/test_benchmark_v2_integrity_gate.py`

31. If unit tests pass, start `postgres` and `redis`, run Alembic, then run focused integration tests:
    - `tests/integration/test_benchmark_harness_gateway.py`
    - `tests/integration/test_benchmark_v2_integrity_gate.py`

32. Run `python scripts/run_formal_verification.py` after the focused tests pass.
    Use this as the repository-level confidence check for the expanded `all_registered` suite.

33. Finish with:
    - `git diff --check`
    - `git status --short`

34. Stage only task-relevant files.
    Do not stage unrelated local docs or generated files.

35. Commit with the expected message.

## 6. Testing Plan

- Unit tests:
  - suite membership/order updates for `memory_governance`, `v2_integrity`, and `all_registered`
  - richer `BenchmarkMemoryGovernanceExpectation` parsing remains backward compatible
  - grader validates decision-log status/reason/influence correctly
  - grader validates exact policy-summary counts correctly
  - grader validates absent non-governable keys correctly
  - grader validates safe feedback candidate summary correctly
  - V2 taxonomy classifies the three new memory cases into the intended additive memory modes
- Integration tests:
  - disabled/ignored case produces zero considered governable memory
  - candidate case proves `candidate` memory is absent from decision surfaces
  - sensitive-minimization case exposes safe feedback candidate summary and passes memory-governance grading
  - V2 integrity suite summary reflects six memory cases and fifteen total cases
- Smoke tests:
  - `python scripts/run_formal_verification.py`
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_v2_taxonomy.py tests/test_benchmark_v2_integrity_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_v2_integrity_gate.py -k "memory or sensitive" -q
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: expand memory governance benchmark suite
```

Expected commands:

```bash
git status --short
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/graders.py
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/suites.py
git add backend/app/benchmark/cases/family_memory_disabled_ignored_v1.json
git add backend/app/benchmark/cases/family_memory_candidate_not_auto_active_v1.json
git add backend/app/benchmark/cases/family_memory_sensitive_minimization_v1.json
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/test_benchmark_v2_taxonomy.py
git add tests/test_benchmark_v2_integrity_gate.py
git add tests/integration/test_benchmark_harness_gateway.py
git add tests/integration/test_benchmark_v2_integrity_gate.py
git add docs/specs/098-memory-governance-suite-v2.md
git add docs/plans/098-memory-governance-suite-v2-plan.md
git diff --cached --check
git commit -m "feat: expand memory governance benchmark suite"
git push -u origin codex/098-memory-governance-suite-v2
```

The implementer must confirm `.env`, secrets, `var/`, and the pre-existing unrelated local docs are not staged.

## 9. Out-of-scope Changes

- Do not change memory-query policy logic beyond additive benchmark/report plumbing.
- Do not change lifecycle-state semantics.
- Do not change feedback-writer extraction rules from Task `097`.
- Do not add memory CRUD, promotion, or user controls.
- Do not expand `default` or `release_gate_v1`.
- Do not add frontend/UI or public API changes.
- Do not add migrations, tables, or new persistent schema.
- Do not stage unrelated local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/098-memory-governance-suite-v2.md`.
- [ ] `memory_governance` now has exactly 6 cases in the specified order.
- [ ] `v2_integrity` now has exactly 15 cases.
- [ ] `all_registered` now has exactly 25 cases.
- [ ] `default` remains 11 cases.
- [ ] `release_gate_v1` remains 15 cases.
- [ ] The three new cases load successfully and carry the intended expectations.
- [ ] `grade_memory_governance(...)` now validates decision-log details additively.
- [ ] `grade_memory_governance(...)` now validates absent keys additively.
- [ ] `grade_memory_governance(...)` now validates exact policy-summary counts additively.
- [ ] The sensitive-minimization case exposes only the safe feedback candidate summary fields.
- [ ] Existing three memory-governance cases still pass unchanged.
- [ ] V2 taxonomy and integrity coverage summaries reflect six memory cases.
- [ ] Required unit and integration tests passed.
- [ ] `python scripts/run_formal_verification.py` passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit, excluding unrelated pre-existing local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- exact files changed
- the final six-case `memory_governance` suite order
- the final `v2_integrity` and `all_registered` case counts
- the additive expectation fields introduced
- one example of a passing absent-key case result
- one example of a passing sensitive-minimization benchmark summary
- verification commands run and their results
- commit hash
- push result
- any follow-up recommendation, especially whether a later task should promote some of these six memory cases into a stricter blocking release surface
