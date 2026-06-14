# Spec: 098 Memory Governance Benchmark Suite v2

## 1. Goal

Expand the current memory-governance benchmark slice from three cases to a fuller six-case suite that can verify both read-memory policy behavior and the benchmark-visible candidate-memory minimization path.

Today WeekendPilot already has:
- governed read-memory behavior
- decision-log and policy-summary audit surfaces
- explicit lifecycle states including `disabled`, `ignored`, and `candidate`
- deterministic post-execution candidate-memory generation with sensitive-information minimization

However, the current benchmark suite still only proves three behaviors:
- explicit override
- advisory fill
- expired downgrade

That is no longer enough for the current repository state. After this task, the benchmark layer must be able to prove six behaviors end-to-end:

- explicit override
- advisory fill
- expired downgrade
- disabled ignored
- candidate not auto-active
- sensitive minimization

This task must also upgrade grading so it checks memory decision correctness at a finer level than the current winner-only summary.

## 2. Project Context

This task belongs primarily to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

The roadmap currently prioritizes benchmark completeness, comparability, and auditable evaluation over adding larger new product surfaces. That priority matches the current repository state:

- Task `095` added `decision_log` and `policy_summary` audit surfaces.
- Task `096` added explicit lifecycle states `active`, `expired`, `disabled`, `ignored`, and `candidate`.
- Task `097` added feedback-to-candidate generation with sensitive-memory minimization.

Those three tasks created new product behavior that the benchmark suite does not yet fully validate. This task closes that evaluation gap without widening user-facing scope.

This task also supports the blueprint areas in `docs/PROJECT_BLUEPRINT.md`:

- observability by default
- harness engineering as product infrastructure
- memory rules around override, downgrade, and minimization
- benchmark-driven development
- small, reviewable task boundaries

## 3. Requirements

- Keep the current runtime memory-governance behavior backward compatible unless a change is strictly required to expose additive benchmark metadata.
- Keep public API routes, frontend behavior, workflow topology, and database schema unchanged.
- Keep `default` suite membership unchanged at 11 cases.
- Keep `release_gate_v1` membership unchanged at 15 cases.
- Expand `memory_governance` from 3 cases to exactly 6 cases.
- Expand `v2_integrity` and `all_registered` to include the three new memory cases.
- Upgrade benchmark expectation/grading so the suite can verify:
  - observed decision outcomes
  - normalized decision-log status/reason/influence fields
  - exact policy-summary counts
  - absence of non-governable keys from decision surfaces
  - feedback candidate summary for the sensitive-minimization case

### A. Add three new benchmark cases

Add these case files:

1. `backend/app/benchmark/cases/family_memory_disabled_ignored_v1.json`
2. `backend/app/benchmark/cases/family_memory_candidate_not_auto_active_v1.json`
3. `backend/app/benchmark/cases/family_memory_sensitive_minimization_v1.json`

#### `family_memory_disabled_ignored_v1`

- Purpose: prove `disabled` and `ignored` memory rows do not reach governable read-memory policy.
- `tool_profile = "mock_world"`
- `world_profile = "family_afternoon"`
- `failure_profile = null`
- Memory items must include:
  - one `spouse_lighter_meals` row with `status = "disabled"`
  - one `activity_style` row with `status = "ignored"`
- The user input must be intentionally vague enough that governable memory would matter if it were loaded.
- Expected memory result:
  - no dimension winner from memory
  - both keys absent from `memory_decisions`
  - both keys absent from `decision_log`
  - `policy_summary.considered_count == 0`
- Taxonomy must use:
  - `scenario_bucket = "family"`
  - `level = "L3"`
  - `tags` including `child_friendly`, `memory_disabled`, `memory_ignored`, `memory_governance`

#### `family_memory_candidate_not_auto_active_v1`

- Purpose: prove `candidate` memory remains non-governable during the current planning run.
- `tool_profile = "mock_world"`
- `world_profile = "family_afternoon"`
- `failure_profile = null`
- Memory items must include:
  - one `activity_style` row with `status = "candidate"`
- The user input must be intentionally vague enough that active memory would have influenced planning if loaded.
- Expected memory result:
  - no dimension winner from memory
  - `activity_style` absent from `memory_decisions`
  - `activity_style` absent from `decision_log`
  - `policy_summary.considered_count == 0`
- Taxonomy must use:
  - `scenario_bucket = "family"`
  - `level = "L3"`
  - `tags` including `child_friendly`, `memory_candidate`, `memory_governance`

#### `family_memory_sensitive_minimization_v1`

- Purpose: prove the benchmark-visible post-feedback candidate-memory summary stays minimal and safe.
- `tool_profile = "mock_world"`
- `world_profile = "family_afternoon"`
- `failure_profile = null`
- The prompt must deterministically produce a reviewed plan whose selected tags create both:
  - `activity_style`
  - `spouse_lighter_meals`
- This case must not rely on pre-seeded governable memory.
- Expected feedback memory candidate result:
  - `generation_status = "completed"`
  - `created_keys = ["activity_style", "spouse_lighter_meals"]`
  - `updated_keys = []`
  - `skipped_keys = []`
- The benchmark-visible summary must remain safe:
  - no raw addresses
  - no phone numbers
  - no tokens/secrets
  - no raw free-form feedback text
- Taxonomy must use:
  - `scenario_bucket = "family"`
  - `level = "L3"`
  - `tags` including `child_friendly`, `light_meal`, `memory_candidate`, `memory_governance`, `sensitive_minimization`

### B. Expand the memory-governance suite definition

`memory_governance` suite case order must become exactly:

```text
family_memory_override_v1
family_memory_advisory_fill_v1
family_memory_expired_advisory_v1
family_memory_disabled_ignored_v1
family_memory_candidate_not_auto_active_v1
family_memory_sensitive_minimization_v1
```

### C. Expand `v2_integrity` and `all_registered`

`v2_integrity` must include the three new memory cases and remain deterministic in canonical order.

`all_registered` must include the three new memory cases and remain deterministic in canonical repository order.

After this task:

- `memory_governance.case_count == 6`
- `v2_integrity.case_count == 15`
- `all_registered.case_count == 25`
- `integrity_coverage_summary.memory_case_count == 6`

### D. Upgrade benchmark expectation schema additively

Keep `BenchmarkMemoryGovernanceExpectation` backward compatible, but extend it additively so a case may specify:

- expected per-memory decision-log checks
- expected absent memory keys
- exact expected policy-summary counts
- expected feedback memory-candidate summary

Additive expectation surfaces must be optional so all existing cases still load unchanged.

### E. Upgrade `grade_memory_governance(...)`

`grade_memory_governance(...)` must continue to validate:

- policy version
- dimension sources
- dimension tiers
- high-level memory outcomes

It must additionally support:

- per-key decision-log validation:
  - `status`
  - `reason`
  - `influence_level`
- exact absent-key validation against both:
  - `memory_decisions`
  - `decision_log`
- exact policy-summary count validation
- feedback memory-candidate summary validation for the sensitive-minimization case

The score must still be named `memory_governance`.

### F. Surface feedback memory-candidate summary in benchmark case results

Add one additive benchmark case-result surface for the safe feedback candidate summary so benchmark reports can show the sensitive-minimization result without reading raw plan payloads.

This field must be safe for serialization and must only contain:

- `schema_version`
- `generation_status`
- `created_keys`
- `updated_keys`
- `skipped_keys`

It must not contain raw feedback text, addresses, phones, token-like fields, IDs, or provider payload fragments.

### G. Keep V2 taxonomy coherent

Update V2 taxonomy logic and tests so the new memory cases are classified distinctly instead of collapsing into the current three memory modes.

The additive memory-mode variants for this task must include:

- `disabled_ignored`
- `candidate_not_auto_active`
- `sensitive_minimization`

Existing memory modes must remain valid:

- `none`
- `override_guarded`
- `advisory_fill`
- `expired_advisory`

### H. Update benchmark tests and pinned counts

Update test fixtures and expected counts anywhere they currently pin:

- registered case order
- suite membership
- suite case counts
- tag counts
- V2 taxonomy counts
- integrity coverage counts
- all-registered totals
- memory-governance totals

## 4. Non-goals

- Do not change memory-query policy rules, lifecycle filtering rules, or feedback-writer extraction logic except for additive benchmark metadata access.
- Do not add new lifecycle states.
- Do not add memory CRUD, promotion, deletion, or user controls.
- Do not expand `default` or `release_gate_v1`.
- Do not add frontend/UI or public API changes.
- Do not add database migrations, new tables, or new columns.
- Do not commit generated artifacts under `var/`.
- Do not track `.env`, API keys, tokens, or secrets in git.

## 5. Interfaces and Contracts

### Inputs

- existing benchmark fixture JSON cases
- existing `workflow.memory_policy` metadata
- existing `decision_log`
- existing `policy_summary`
- existing selected-plan feedback summary from Task `097`

### Outputs

- three new benchmark case fixtures
- expanded suite memberships for `memory_governance`, `v2_integrity`, and `all_registered`
- additive benchmark expectation fields for richer memory-governance assertions
- additive benchmark case-result field for safe feedback candidate summary
- updated benchmark reports and test expectations

### Schemas

Additive expectation shape example:

```json
{
  "memory_governance": {
    "expected_policy_version": "memory_query_policy_v1",
    "expected_dimension_sources": {},
    "expected_dimension_tiers": {},
    "expected_memory_outcomes": [],
    "expected_decision_log": [],
    "expected_absent_memory_keys": ["activity_style"],
    "expected_policy_summary": {
      "considered_count": 0,
      "used_count": 0,
      "ignored_count": 0,
      "downgraded_count": 0,
      "overridden_count": 0,
      "primary_influence_count": 0,
      "advisory_influence_count": 0,
      "no_influence_count": 0
    }
  }
}
```

Sensitive-minimization benchmark summary example:

```json
{
  "feedback_memory_candidate_summary": {
    "schema_version": "feedback_memory_candidates_v0",
    "generation_status": "completed",
    "created_keys": ["activity_style", "spouse_lighter_meals"],
    "updated_keys": [],
    "skipped_keys": []
  }
}
```

## 6. Observability

This task is benchmark- and audit-surface work.

It must preserve current observability and extend it additively by:

- grading against `decision_log`
- grading against `policy_summary`
- exposing safe `feedback_memory_candidate_summary` in benchmark case results

This task must not expose:

- raw memory text
- raw `value_json`
- addresses or phones
- token/secret-like values
- prompt/debug payloads
- internal IDs beyond already-approved benchmark report surfaces

## 7. Failure Handling

- If an existing case omits new optional expectation fields, loading and grading must still work with current semantics.
- If the sensitive-minimization case lacks a safe feedback summary, its memory-governance score must fail deterministically with a clear reason.
- If expected absent keys appear in `memory_decisions` or `decision_log`, the score must fail deterministically.
- If policy-summary counts do not match the expected exact counts, the score must fail deterministically.
- If suite membership or canonical case ordering is inconsistent, suite-loading tests must fail deterministically.
- If benchmark metadata does not include safe candidate-summary fields for non-sensitive cases, reports may leave that additive field null without failing unrelated cases.

## 8. Acceptance Criteria

- [ ] `docs/specs/098-memory-governance-suite-v2.md` exists and matches this task.
- [ ] `docs/plans/098-memory-governance-suite-v2-plan.md` exists and matches this task.
- [ ] `memory_governance` expands from 3 to exactly 6 cases in the specified order.
- [ ] `v2_integrity` expands from 12 to exactly 15 cases.
- [ ] `all_registered` expands from 22 to exactly 25 cases.
- [ ] `default` remains 11 cases.
- [ ] `release_gate_v1` remains 15 cases.
- [ ] New cases exist for:
  - `disabled ignored`
  - `candidate not auto-active`
  - `sensitive minimization`
- [ ] `grade_memory_governance(...)` can validate additive decision-log expectations.
- [ ] `grade_memory_governance(...)` can validate additive absent-key expectations.
- [ ] `grade_memory_governance(...)` can validate additive policy-summary expectations.
- [ ] `grade_memory_governance(...)` can validate the safe feedback candidate summary for the sensitive-minimization case.
- [ ] Existing three memory-governance cases still pass without behavior regressions.
- [ ] The disabled/ignored case proves non-governable keys do not appear in decision surfaces.
- [ ] The candidate case proves `candidate` memory does not become governable in the current planning run.
- [ ] The sensitive-minimization case proves the benchmark-visible candidate summary is present and safe.
- [ ] V2 taxonomy and integrity coverage tests reflect the expanded six-case memory suite.
- [ ] No memory runtime behavior is widened beyond additive benchmark/reporting work.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except for unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_v2_taxonomy.py tests/test_benchmark_v2_integrity_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_v2_integrity_gate.py -k "memory or sensitive" -q
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: expand memory governance benchmark suite
```

## 11. Notes for the Implementer

Keep this task benchmark-led.

Do not turn it into a runtime memory redesign. The code already has the relevant product slices from `095`, `096`, and `097`. This task exists to make the benchmark suite catch regressions across those slices.

The most important scoping choice is to leave `release_gate_v1` stable and grow only the focused memory suite plus the broader non-blocking integrity/registration surfaces. If the new sensitive-minimization case needs extra runtime metadata, keep it additive and safe rather than reopening feedback persistence semantics.
