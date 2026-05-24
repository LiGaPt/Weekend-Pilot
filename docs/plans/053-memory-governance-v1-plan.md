# Plan: 053 Memory Governance v1

## 1. Spec Reference

Spec file:

```text
docs/specs/053-memory-governance-v1.md
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

- Current branch is `codex/chaos-harness-composite-failures-v0`.
- Latest code commit is `6f13ce5 feat: add chaos harness composite failures`.
- Latest completed product task in code history is `052`.
- At authoring time, `docs/specs/` and `docs/plans/` on disk were matched but not continuous because Tasks `047`, `049`, and `050` were still pending doc backfill.
- At authoring time, that backfill work lived on isolated doc-only branch tips outside Task `053`.
- Those branch tips are convergence debt only and must stay out of Task `053`.
- Current memory behavior before this task is:
  - `load_memory(...)` only loads non-expired active memory through `list_active_for_user(...)`
  - `apply_memory_query_policy(...)` persists `memory_query_policy_v0`
  - supported keys are only `activity_style` and `spouse_lighter_meals`
  - low-confidence memory is effectively threshold-filtered
  - no per-dimension winner/suppressed source summary exists
- Current benchmark behavior before this task is:
  - no `memory_governance` suite exists
  - no benchmark score specifically grades memory-governance expectations
  - `family_memory_override_v1` is the only memory-focused benchmark case
- Pre-existing unrelated local paths must remain unstaged:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`

## 3. Files to Add

- `backend/app/benchmark/cases/family_memory_advisory_fill_v1.json` - governance benchmark case where advisory dining memory helps a vague family request.
- `backend/app/benchmark/cases/family_memory_expired_advisory_v1.json` - governance benchmark case where expired high-confidence activity memory is downgraded but still visible and usable.

## 4. Files to Modify

- `backend/app/planning/memory_query_policy.py` - upgrade the v0 helper into the governed v1 policy, summary model, tiering, and decision outcomes.
- `backend/app/planning/__init__.py` - keep planning package exports aligned with the upgraded summary/helper surface if tests import through the package root.
- `backend/app/repositories/memory.py` - add `list_governable_for_user(...)` while preserving `list_active_for_user(...)`.
- `backend/app/workflow/nodes.py` - load governable memory candidates and persist the new v1 memory summary shape.
- `backend/app/benchmark/schemas.py` - add memory-governance expectation models and extend `BenchmarkSuiteId`.
- `backend/app/benchmark/graders.py` - add deterministic `memory_governance` scoring.
- `backend/app/benchmark/harness.py` - attach the new score for opted-in cases using persisted workflow metadata.
- `backend/app/benchmark/fixtures.py` - register the two new memory-governance case IDs in canonical order.
- `backend/app/benchmark/suites.py` - add the additive `memory_governance` suite and update `all_registered`.
- `backend/app/benchmark/cases/family_memory_override_v1.json` - add explicit memory-governance expectations without changing taxonomy.
- `tests/test_memory_query_policy.py` - replace v0-only assertions with governed v1 tiering, outcome, and sanitization coverage.
- `tests/integration/test_repositories.py` - prove the new governable repository method includes expired active memory while the old active-only method still filters it.
- `tests/test_benchmark_suites.py` - add the `memory_governance` suite, update canonical suite order, and update exact counts.
- `tests/test_benchmark_harness.py` - add fixture, suite, and grader coverage for memory-governance expectations and updated registered counts.
- `tests/integration/test_benchmark_harness_gateway.py` - prove the override case plus both new cases pass through the real harness with correct governed metadata.
- `README.md` - document the new memory-governance benchmark suite and the v1 policy summary behavior.

## 5. Implementation Steps

1. Add the repository regression first.
   In `tests/integration/test_repositories.py`, extend the existing memory repository test so it proves:
   - `list_active_for_user(...)` still returns only non-expired active rows
   - `list_governable_for_user(...)` returns active rows regardless of expiry
   - archived rows stay excluded from both methods
   Then implement `list_governable_for_user(...)` in `backend/app/repositories/memory.py` using the same deterministic ordering as `list_active_for_user(...)` but without the `expires_at > now()` filter.

2. Lock the governed v1 policy behavior with failing unit tests before changing workflow code.
   Rewrite `tests/test_memory_query_policy.py` so it covers:
   - trusted non-expired memory applying as `applied_trusted`
   - active `0.7000` memory applying as `applied_advisory` when the user is vague
   - expired `1.0` memory applying as `applied_advisory`
   - malformed or very weak memory producing `tier = "weak"` and `outcome = "suppressed_weak_signal"`
   - explicit activity and dining user signals forcing `suppressed_user_override`
   - unsupported keys producing `unsupported_key`
   - summary sanitization: no raw text, no raw `value_json`, no `memory_id`, no trace ID fields

3. Upgrade `backend/app/planning/memory_query_policy.py` to the exact v1 contract.
   Implement:
   - `policy_version = "memory_query_policy_v1"`
   - exact tier rules:
     - trusted: `>= 0.8000` and not expired
     - advisory: `0.5000-0.7999` and not expired, or `>= 0.8000` and expired
     - weak: malformed, `< 0.5000`, or expired and `< 0.8000`
   - exact outcomes:
     - `applied_trusted`
     - `applied_advisory`
     - `suppressed_user_override`
     - `suppressed_weak_signal`
     - `unsupported_key`
     - `unrecognized_value`
   - exact summary fields:
     - `applied_memory_keys`
     - `advisory_memory_keys`
     - `downgraded_low_confidence_keys`
     - `downgraded_expired_keys`
     - `user_override_dimensions`
     - `unsupported_memory_keys`
     - `effective_activity_preferences`
     - `effective_dining_preferences`
     - `dimension_outcomes`
     - `memory_decisions`
   Keep the projected keys limited to `activity_style` and `spouse_lighter_meals`.

4. Keep workflow wiring small and deterministic.
   In `backend/app/workflow/nodes.py`:
   - switch `load_memory(...)` to `list_governable_for_user(...)`
   - keep the state key `active_memories`
   - keep `generate_queries(...)` calling `apply_memory_query_policy(...)`
   - persist the governed summary under the same metadata path `workflow.memory_policy`
   No graph topology change, no parser change, and no query planner change are needed in this task.

5. Extend benchmark schemas before adding fixtures.
   In `backend/app/benchmark/schemas.py`:
   - add `memory_governance` to `BenchmarkSuiteId`
   - add `BenchmarkMemoryDecisionExpectation`
   - add `BenchmarkMemoryGovernanceExpectation`
   - add optional `memory_governance` to `BenchmarkExpectedOutcome`
   - extend `BenchmarkMemoryItem` with `expires_at: datetime | None = None`
   Keep all existing cases backward compatible by defaulting the new fields.

6. Add the new benchmark fixtures and exact suite membership.
   Update `backend/app/benchmark/cases/family_memory_override_v1.json` with the exact `expected.memory_governance` block from the spec.
   Add:
   - `family_memory_advisory_fill_v1.json`
   - `family_memory_expired_advisory_v1.json`
   Then update `backend/app/benchmark/fixtures.py` so registered case order is exactly:
   1. `family_afternoon_v1`
   2. `family_indoor_light_meal_v1`
   3. `family_outdoor_quick_dinner_v1`
   4. `family_memory_override_v1`
   5. `family_citywalk_addon_v1`
   6. `solo_afternoon_v1`
   7. `couple_afternoon_v1`
   8. `friends_gathering_v1`
   9. `rainy_day_fallback_v1`
   10. `budget_lite_v1`
   11. `family_route_failure_v1`
   12. `family_route_and_dining_unavailable_v1`
   13. `rainy_day_ticket_sold_out_v1`
   14. `family_memory_advisory_fill_v1`
   15. `family_memory_expired_advisory_v1`

7. Add the new suite without disturbing existing ones.
   In `backend/app/benchmark/suites.py`:
   - keep `baseline`, `expanded`, `recovery_focused`, and `default` memberships unchanged
   - add `memory_governance` with exact case order:
     - `family_memory_override_v1`
     - `family_memory_advisory_fill_v1`
     - `family_memory_expired_advisory_v1`
   - keep `all_registered` as every registered case in canonical order
   - update `_ORDERED_SUITE_IDS` to:
     - `baseline`
     - `expanded`
     - `recovery_focused`
     - `memory_governance`
     - `default`
     - `all_registered`

8. Add benchmark grading for memory governance.
   In `backend/app/benchmark/graders.py`, implement `grade_memory_governance(case, run_metadata)` that:
   - is only called when `case.expected.memory_governance` is not `None`
   - reads `run_metadata["workflow"]["memory_policy"]`
   - checks exact policy version
   - checks expected dimension winners
   - checks expected dimension tiers
   - checks expected per-key outcomes
   - returns a normal `BenchmarkScore`
   In `backend/app/benchmark/harness.py`, append that score only for opted-in cases and leave all other benchmark scoring unchanged.

9. Update benchmark tests with exact counts and taxonomy.
   In `tests/test_benchmark_suites.py` and `tests/test_benchmark_harness.py`, update constants and assertions to the exact new state:
   - registered case count: `15`
   - `memory_governance` suite count: `3`
   - `default` suite count: `10`
   - `recovery_focused` suite count: `3`
   - `all_registered` suite count: `15`
   - `memory_governance` matrix summary:
     - `scenario_bucket_counts={"family": 3}`
     - `level_counts={"L2": 1, "L3": 2}`
     - `world_profile_counts={"family_afternoon": 3}`
     - `failure_mode_counts={"none": 3}`
     - `tag_counts={"child_friendly": 3, "indoor_activity": 2, "light_meal": 2, "memory_advisory": 1, "memory_expired": 1, "memory_governance": 2, "memory_override": 1}`
   - updated `all_registered` summary:
     - `scenario_bucket_counts={"couple": 1, "family": 9, "friends": 1, "mixed": 2, "solo": 1, "unknown": 1}`
     - `level_counts={"L1": 3, "L2": 8, "L3": 2, "L5": 2}`
     - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 9, "friends_gathering": 1, "rainy_day_fallback": 2, "solo_afternoon": 1}`
     - `failure_mode_counts={"none": 12, "route_and_dining_unavailable": 1, "route_unavailable": 1, "ticket_sold_out_and_bad_weather": 1}`
     - `tag_counts={"addon_optional": 1, "bad_weather": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 9, "citywalk": 2, "composite_failure": 2, "date_friendly": 1, "dining_unavailable": 1, "failure_injected": 3, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 4, "light_activity": 1, "light_meal": 7, "memory_advisory": 1, "memory_expired": 1, "memory_governance": 2, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 2, "route_failure": 2, "ticket_sold_out": 1}`

10. Prove the real harness behavior in gateway-backed integration tests.
    In `tests/integration/test_benchmark_harness_gateway.py`:
    - keep the existing override test but update it to assert `memory_query_policy_v1` and the new structured fields
    - add one integration test for `family_memory_advisory_fill_v1`
    - add one integration test for `family_memory_expired_advisory_v1`
    - add one suite-level assertion that `load_benchmark_suite("memory_governance")` runs 3 passing cases
    Each integration assertion should inspect `AgentRun.metadata_json["workflow"]["memory_policy"]` and at least one benchmark score named `memory_governance`.

11. Update README last and keep staging tight.
    In `README.md`, update the LocalLife-Bench section to say:
    - repository now keeps six named suites: `baseline`, `expanded`, `recovery_focused`, `memory_governance`, `default`, `all_registered`
    - `default` stays the 10-case non-failure suite
    - `memory_governance` is a focused 3-case suite
    - `all_registered` now contains 15 total registered cases
    - governed memory policy persists v1 metadata with dimension winners and per-memory outcomes
    Before staging, confirm these remain unstaged:
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `qc`
    - `var/`
    - any unrelated local doc drafts

## 6. Testing Plan

- Unit tests:
  - `tests/test_memory_query_policy.py` for trusted/advisory/weak tiers, expiry downgrade, explicit override, unsupported keys, and sanitization.
  - `tests/test_benchmark_suites.py` for the additive `memory_governance` suite plus exact 15-case `all_registered` inventory.
  - `tests/test_benchmark_harness.py` for fixture loadability, taxonomy, suite summaries, and `grade_memory_governance(...)`.
- Integration tests:
  - `tests/integration/test_repositories.py` for `list_governable_for_user(...)`.
  - `tests/integration/test_benchmark_harness_gateway.py` for the override case, advisory-fill case, expired-advisory case, and the `memory_governance` suite.
- Smoke tests:
  - `git diff --check`
  - `git status --short`
- Explicit non-tests:
  - no frontend tests
  - no public API tests
  - no replay tests
  - no recovery-routing tests
  - no query-planner tests unless implementation accidentally expands scope

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_memory_query_policy.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_repositories.py tests/integration/test_benchmark_harness_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add memory governance v1
```

Expected commands:

```bash
git status --short
git switch -c codex/memory-governance-v1
git add backend/app/planning/memory_query_policy.py
git add backend/app/planning/__init__.py
git add backend/app/repositories/memory.py
git add backend/app/workflow/nodes.py
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/graders.py
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/suites.py
git add backend/app/benchmark/cases/family_memory_override_v1.json
git add backend/app/benchmark/cases/family_memory_advisory_fill_v1.json
git add backend/app/benchmark/cases/family_memory_expired_advisory_v1.json
git add tests/test_memory_query_policy.py
git add tests/integration/test_repositories.py
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/integration/test_benchmark_harness_gateway.py
git add README.md
git add docs/specs/053-memory-governance-v1.md
git add docs/plans/053-memory-governance-v1-plan.md
git diff --cached --check
git commit -m "feat: add memory governance v1"
git push -u origin codex/memory-governance-v1
```

- If Task `052` is not merged yet, branch from the current `6f13ce5` tip or its merged equivalent.
- Do not stage `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, or any unrelated local doc drafts.

## 9. Out-of-scope Changes

- Do not add memory write-back, memory editing, or user memory CRUD.
- Do not change public demo API routes, response schemas, or frontend rendering.
- Do not modify query planning semantics beyond the existing effective-intent contract.
- Do not change recovery routing, replay behavior, or benchmark failure injection.
- Do not add new dependencies.
- Do not add or modify Alembic revisions, tables, columns, or indexes.
- Do not merge unrelated task-doc convergence branches as part of this task.
- Do not commit generated caches, secrets, or unrelated local files.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/053-memory-governance-v1.md`.
- [ ] `list_active_for_user(...)` remained unchanged.
- [ ] `list_governable_for_user(...)` was added and is covered by tests.
- [ ] `memory_query_policy_v1` enforces the exact trusted/advisory/weak rules from the spec.
- [ ] Explicit user input still wins over memory in both supported dimensions.
- [ ] Expired memory is no longer invisible to the policy.
- [ ] Low-confidence memory is down-ranked rather than silently flattened into the old behavior.
- [ ] The persisted summary includes `dimension_outcomes` and `memory_decisions`.
- [ ] The persisted summary is sanitized.
- [ ] The `memory_governance` benchmark score only applies to opted-in cases and passes for the three specified cases.
- [ ] `default` and `recovery_focused` suite memberships stayed unchanged.
- [ ] `memory_governance` suite membership is exact.
- [ ] `all_registered` case order and counts are exact.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final `workflow.memory_policy` v1 summary shape from one advisory case and one override case.
- The result of the `memory_governance` benchmark suite run.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no migration changed.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, and any unrelated local doc drafts were not staged.
- Any remaining follow-up limitation, especially that memory CRUD, sensitive-data minimization, and user-editable controls remain future work.
