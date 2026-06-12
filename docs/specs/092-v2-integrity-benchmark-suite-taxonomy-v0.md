# Spec: 092 V2 Integrity Benchmark Suite and Taxonomy v0

## 1. Goal

WeekendPilot already has a stable V1.5 benchmark baseline built on `Mock World`, with `release_gate_v1`, `coverage_gate_v1_5`, the full `all_registered` inventory, and recovery replay evidence. What is still missing is a V2-specific benchmark layer that proves system integrity directly instead of treating integrity signals as side effects of older V1 suites.

This task defines two additive benchmark contracts for Phase 1:

- a new `v2_integrity` benchmark suite focused on integrity evidence
- a V2 benchmark taxonomy that classifies every case consistently across memory, recovery, continuation, robustness, and composite integrity stress

After this task is implemented, the repository should be able to expose a dedicated V2 integrity suite without changing the current `release_gate_v1` contract, and every registered benchmark case should resolve to a deterministic V2 taxonomy even if the fixture has not yet been explicitly backfilled with V2-only fields.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven, deterministic where possible, and observable by default. `docs/NEXT_PHASE_ROADMAP.md` now frames the next step as `V2 Integrity Edition`, with priority on benchmark completeness, memory governance, auditability, recovery evidence, and stability rather than deeper real-provider integration.

The repository state already contains the building blocks this task must reuse rather than replace:

- Task `039` added the current typed benchmark taxonomy and `matrix_summary`.
- Task `040` added the suite catalog and canonical suite ordering.
- Task `065` fixed `release_gate_v1` as the blocking V1 suite.
- Task `074` added `coverage_gate_v1_5` on top of `all_registered`.
- The current canonical inventory contains `22` registered Mock World benchmark cases.

This task belongs to the V2 Integrity Edition line, but it is still benchmark-governance work. It must not alter workflow routing, Tool Gateway behavior, Action Ledger semantics, AMap preview boundaries, or the current V1 formal evidence layout.

## 3. Problem / Goal

Current benchmark structure proves breadth and baseline correctness, but it still mixes V2 integrity evidence into older suite shapes:

- `release_gate_v1` is a blocking V1 suite with exact fixed counts and latency checks.
- `coverage_gate_v1_5` proves inventory breadth on `all_registered`, not V2 integrity specifically.
- The existing taxonomy only captures:
  - `scenario_bucket`
  - `level`
  - `tags`
  - `failure_mode`
- There is no canonical way to ask:
  - which cases prove memory governance
  - which cases prove continuation integrity
  - which cases prove robustness
  - which cases are composite integrity stress cases
  - which suite is the dedicated V2 integrity sign-off surface

This task solves that gap by defining one additive suite and one additive taxonomy layer for V2 integrity evidence.

## 4. Current State

The implementation this spec targets starts from the following repository facts:

- `backend/app/benchmark/suites.py` currently defines these canonical suites:
  - `baseline`
  - `expanded`
  - `recovery_focused`
  - `memory_governance`
  - `conversation_continuations`
  - `robustness_focused`
  - `default`
  - `release_gate_v1`
  - `all_registered`
- `release_gate_v1` currently depends on exact case membership, exact `level_counts`, exact `tool_profile_counts`, and exact `failure_mode_counts`.
- `coverage_gate_v1_5` currently depends on `matrix_summary` and `outcome_rollup`, especially:
  - `scenario_bucket_counts`
  - `world_profile_counts`
  - `failure_mode_counts`
  - selected constraint-tag outcomes
- `BenchmarkCaseTaxonomy` currently contains only:
  - `suite`
  - `scenario_bucket`
  - `level`
  - `tags`
  - `failure_mode`
- `build_case_matrix_summary(...)` currently summarizes only the V1 taxonomy fields plus `tool_profile` and `world_profile`.
- Existing fixtures already express the core V2 integrity dimensions through a mix of:
  - `taxonomy.tags`
  - `expected.memory_governance`
  - `expected.conversation`
  - `expected.robustness`
  - `failure_mode`
  - `failure_profile`

Important examples already present in the current 22-case inventory:

- memory governance: `family_memory_override_v1`, `family_memory_advisory_fill_v1`, `family_memory_expired_advisory_v1`
- continuation: `solo_clarification_continuation_v1`, `family_replan_version_continuation_v1`
- robustness: `family_distractor_selection_v1`, `friends_distractor_selection_v1`, `rainy_day_stable_sorting_v1`, `budget_indoor_fallback_v1`
- recovery: `family_route_failure_v1`, `family_route_and_dining_unavailable_v1`, `rainy_day_ticket_sold_out_v1`
- composite integrity stress already expressible from current inventory:
  - `family_route_and_dining_unavailable_v1`
  - `family_replan_version_continuation_v1`

## 5. In Scope

- Define a new additive suite ID: `v2_integrity`
- Define the suite membership rule for `v2_integrity`
- Define a V2 taxonomy contract for benchmark classification
- Define deterministic fallback rules so all existing cases resolve to the V2 taxonomy
- Define how V2 taxonomy appears in suite-level reporting
- Define compatibility rules so current `release_gate_v1`, `coverage_gate_v1_5`, and `all_registered` behavior do not change
- Define acceptance and verification requirements for the later implementation task

## 6. Non-goals

- Do not modify `release_gate_v1`
- Do not put AMap into the formal benchmark path
- Do not add deeper real-provider integration
- Do not introduce `Pass@4` or `Pass^4`
- Do not implement memory lifecycle management
- Do not add a System Integrity UI
- Do not commit `var/`, `.env`, secrets, tokens, keys, or local artifacts
- Do not require new benchmark cases in this task unless the implementer proves the current 22 cases cannot express the composite integrity requirement
- Do not change workflow routing, scoring semantics, replay semantics, or public demo behavior

## 7. Proposed Behavior

### 7.1 New Suite

Add a new canonical benchmark suite:

- `suite_id = "v2_integrity"`

Purpose:

- provide a dedicated V2 integrity evidence surface
- remain additive relative to the current suite catalog
- keep `release_gate_v1` as the unchanged V1 blocking gate

### 7.2 Suite Membership Rule

`v2_integrity` must be constructed from the existing registered case inventory in canonical registered order. Membership must be deterministic and rule-based, not hand-picked per run.

A case belongs to `v2_integrity` if it satisfies at least one of these integrity dimensions:

- memory:
  - `expected.memory_governance` is present, or
  - current taxonomy tags include `memory_governance` or `memory_override`
- recovery:
  - current taxonomy `failure_mode` is non-null, or
  - `expected.expected_recovery_action` is non-null, or
  - `failure_profile` is non-null
- continuation:
  - `continuations` is non-empty, or
  - `expected.conversation` is present, or
  - current taxonomy tags include `conversation_continuation`
- robustness:
  - `expected.robustness` is present, or
  - current taxonomy tags include `robustness_case`
- L4-style combination:
  - the resolved V2 taxonomy `level` is `L4`, or
  - the case resolves to a composite integrity classification as defined in Section 8.4

The suite implementation must preserve canonical registered order and must not reorder `all_registered`.

For the current inventory, the expected direction is to populate `v2_integrity` entirely by reusing existing cases. The implementation may add a new benchmark case only if it can show, with a failing test or explicit inventory analysis, that no current registered case can satisfy the composite integrity requirement.

### 7.3 V2 Taxonomy Resolution

Every registered benchmark case must resolve to a V2 taxonomy object.

Resolution order:

1. If the fixture defines an explicit V2 taxonomy block, use it.
2. Otherwise derive V2 taxonomy deterministically from the existing fixture fields.

This allows the V2 taxonomy to be introduced without forcing a same-change rewrite of all historical fixtures.

### 7.4 Summary Exposure

The existing `matrix_summary` contract should remain unchanged for backward compatibility.

V2 taxonomy reporting must therefore use one additive summary surface:

- either a dedicated `v2_taxonomy_summary`
- or another equivalently named additive summary block

This new summary must not replace or silently redefine the current `matrix_summary` used by the existing release and coverage gates.

## 8. Data / Schema Contract

### 8.1 Benchmark Case V2 Taxonomy

Add one additive V2 taxonomy contract. The recommended name is:

- `BenchmarkCaseV2Taxonomy`

Recommended fixture field:

- `v2_taxonomy`

Recommended fields:

- `scenario_bucket`
- `level`
- `failure_mode`
- `memory_mode`
- `conversation_mode`
- `stability_required`

Recommended value domains:

- `scenario_bucket`
  - `family`
  - `solo`
  - `friends`
  - `couple`
  - `elder`
  - `mixed`
  - `unknown`
- `level`
  - `L1`
  - `L2`
  - `L3`
  - `L4`
  - `L5`
- `failure_mode`
  - `none` or a lower-snake-case failure label
- `memory_mode`
  - `none`
  - `override_guarded`
  - `advisory_fill`
  - `expired_advisory`
- `conversation_mode`
  - `single_turn`
  - `clarification`
  - `replan_versioned`
- `stability_required`
  - `false`
  - `true`

Notes:

- `failure_mode` in V2 taxonomy should normalize `null` to `"none"` for summary stability.
- `stability_required` is a V2 integrity classification field, not a runtime execution switch.
- The existing V1 taxonomy remains authoritative for the old gates until a later task explicitly migrates those gates.

### 8.2 Backward-Compatible Case Contract

The existing `BenchmarkCase.taxonomy` must remain valid and loadable without change.

The additive V2 contract must allow all current case fixtures to continue loading even if they do not yet contain an explicit `v2_taxonomy` block.

### 8.3 Suite and Run Summary Contract

Add one additive summary block for V2 taxonomy rollups. Recommended contents:

- `case_count`
- `scenario_bucket_counts`
- `level_counts`
- `failure_mode_counts`
- `memory_mode_counts`
- `conversation_mode_counts`
- `stability_required_counts`

This summary may appear in:

- `BenchmarkSuiteDescription`
- suite run summaries
- both, if implementation reuse is simpler

It must serialize deterministically.

### 8.4 Composite Integrity Rule

The V2 taxonomy must define a deterministic notion of composite integrity stress. For Phase 1, a case should resolve to V2 `level = "L4"` when at least one of the following is true:

- it combines multiple integrity stressors in one case, such as route plus dining failure
- it requires multi-turn plan evolution with version continuity before confirmation
- it requires stability-sensitive selection under noisy or degraded candidate conditions with explicit integrity expectations

For the current inventory, the implementation should treat at least one existing case as satisfying this rule. The intended candidates are:

- `family_route_and_dining_unavailable_v1`
- `family_replan_version_continuation_v1`

If the implementer cannot justify either candidate under the adopted rule, they must stop and report the gap rather than silently broadening scope.

## 9. Taxonomy Field Semantics

### `scenario_bucket`

High-level scenario family used for V2 coverage comparison. It should remain aligned with the existing scenario taxonomy values to avoid unnecessary drift.

### `level`

V2 integrity complexity level.

- `L1`: simple single-path non-integrity-heavy planning
- `L2`: one bounded integrity concern, such as robustness-only or memory-only evidence
- `L3`: multi-turn or governance-sensitive integrity behavior without composite stress
- `L4`: composite integrity stress across multiple signals or versioned interaction chains
- `L5`: hard failure-recovery and bounded safe-stop integrity behavior

This V2 `level` is allowed to differ from the existing V1 taxonomy `level` when derived through fallback. That difference must stay confined to the V2 taxonomy path and must not mutate the old matrix counts.

### `failure_mode`

Normalized integrity failure classification.

- use `"none"` for non-failure cases
- otherwise use one deterministic lower-snake-case failure label

### `memory_mode`

How memory is expected to participate in the benchmark:

- `none`: no meaningful memory behavior under test
- `override_guarded`: explicit user input must override memory
- `advisory_fill`: memory can fill a vague user request
- `expired_advisory`: stale memory must be downgraded or ignored

### `conversation_mode`

Conversation-shape classification:

- `single_turn`: no follow-up interaction required
- `clarification`: clarification turn required or validated
- `replan_versioned`: follow-up replan with preserved plan lineage or version continuity

### `stability_required`

Whether the case explicitly requires deterministic or stability-sensitive behavior beyond simple pass/fail output, such as:

- stable candidate ordering
- distractor resistance
- bounded continuation integrity
- auditable recovery behavior

## 10. Backward Compatibility

- `v2_integrity` must be additive
- existing suite IDs and suite ordering must remain unchanged except for appending the new suite in a deliberate, deterministic position
- current `release_gate_v1` results must not change
- current `all_registered` membership and ordering must not change
- current `coverage_gate_v1_5` behavior must not change
- the existing `matrix_summary` contract must remain usable by current release and coverage gate tests
- old benchmark fixtures without explicit V2 taxonomy must resolve through deterministic fallback
- old benchmark artifacts already stored under `var/` do not need to be backfilled in this task

Recommended deterministic fallback rules:

- `scenario_bucket`: copy from existing taxonomy
- `failure_mode`: existing taxonomy `failure_mode` or `"none"`
- `memory_mode`:
  - `override_guarded` if tag `memory_override` is present
  - `advisory_fill` if tag `memory_governance` or `memory_advisory` is present and not expired
  - `expired_advisory` if tag `memory_expired` is present
  - otherwise `none`
- `conversation_mode`:
  - `replan_versioned` if tag `plan_versioning` or `replan_turn` is present
  - `clarification` if tag `clarification_turn` is present
  - otherwise `single_turn`
- `stability_required`:
  - `true` if tag `robustness_case`, `conversation_continuation`, `route_failure`, `composite_failure`, or an explicit robustness/recovery expectation is present
  - otherwise `false`
- `level`:
  - derive according to Section 8.4 and Section 9, without changing the existing V1 taxonomy field

## 11. Acceptance Criteria

- [ ] `list_benchmark_suites()` includes `v2_integrity`
- [ ] `v2_integrity` is additive and does not modify `release_gate_v1` membership
- [ ] `v2_integrity` deterministically covers memory, recovery, continuation, robustness, and at least one L4-style composite integrity case
- [ ] The current 22 registered cases remain the primary source of `v2_integrity` membership
- [ ] Every registered case resolves to a V2 taxonomy object
- [ ] Cases without explicit `v2_taxonomy` resolve through deterministic fallback
- [ ] The old `BenchmarkCase.taxonomy` contract remains valid and unchanged for existing gates
- [ ] The existing `matrix_summary` contract remains usable by current release and coverage gates
- [ ] V2 taxonomy appears in an additive suite/run summary surface or equivalent dedicated summary
- [ ] `release_gate_v1` summary counts and gate outcome do not change
- [ ] `all_registered` ordering does not change
- [ ] `coverage_gate_v1_5` thresholds and pass/fail semantics do not change
- [ ] Focused tests cover:
  - suite membership for `v2_integrity`
  - fallback resolution for V2 taxonomy
  - additive V2 summary generation
  - non-regression for `release_gate_v1`
  - non-regression for `all_registered`
  - non-regression for `coverage_gate_v1_5`

## 12. Verification Commands

These commands define the expected verification surface for the later implementation task:

```powershell
git status --short
Get-ChildItem -File backend\app\benchmark\cases | Measure-Object
python scripts/show_submission_evidence.py
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_coverage_gate.py -q
python -m pytest tests/test_benchmark_matrix_v2.py -q
git diff --check
git status --short
```

Notes:

- `tests/test_benchmark_matrix_v2.py` is a recommended new focused test target, not an existing file requirement for this spec-only task.
- If the implementation chooses another focused test file name, it must still cover the acceptance surface listed above.

## 13. Risks and Rollback

Main risks:

- accidentally changing the old `level_counts` or `failure_mode_counts` consumed by `release_gate_v1`
- extending `matrix_summary` in place and breaking exact test assertions
- overfitting `v2_integrity` to hand-picked case IDs instead of a deterministic rule
- forcing immediate fixture rewrites when fallback resolution would be safer
- broadening scope into new provider integration, UI work, or memory lifecycle work

Rollback strategy:

- keep all V2 behavior additive
- keep the old taxonomy and old summary contracts intact
- isolate V2 taxonomy resolution behind a new contract and new summary surface
- if V2 taxonomy rollout causes gate or report regressions, remove `v2_integrity` and the V2 summary surface without touching `release_gate_v1`, `all_registered`, or `coverage_gate_v1_5`

## 14. Notes for the Implementer

Implement this as a compatibility-first benchmark governance change.

Recommended sequence:

1. add the V2 taxonomy contract and fallback resolver
2. add focused tests proving deterministic resolution for the current 22-case inventory
3. add the additive V2 summary surface
4. add `v2_integrity` suite membership using deterministic rule-based selection in canonical order
5. prove non-regression for `release_gate_v1`, `all_registered`, and `coverage_gate_v1_5`

Do not treat this task as permission to rewrite benchmark inventory, add AMap to formal evaluation, or redefine the current V1 baseline.
