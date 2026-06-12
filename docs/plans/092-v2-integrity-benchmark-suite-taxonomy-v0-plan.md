# 092 V2 Integrity Benchmark Suite and Taxonomy v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive `v2_integrity` benchmark suite and an additive V2 taxonomy resolution path without changing `release_gate_v1`, `coverage_gate_v1_5`, existing suite order, or canonical benchmark artifacts.

**Architecture:** The implementation should keep the current V1 taxonomy and `matrix_summary` contracts intact, then layer V2-specific classification beside them. `v2_integrity` should be added in `suites.py` using deterministic rule-based membership over the current 22 registered cases, while V2 taxonomy should be resolved through schema-plus-derivation helpers and exposed through a separate V2 summary path rather than by mutating the existing gate-facing summary.

**Tech Stack:** Python, Pydantic, pytest, existing benchmark harness/reporting stack.

---

## 1. Spec Reference

Spec file:

```text
docs/specs/092-v2-integrity-benchmark-suite-taxonomy-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current workspace already contains the spec file:
  - `docs/specs/092-v2-integrity-benchmark-suite-taxonomy-v0.md`
- Current benchmark suite catalog in `backend/app/benchmark/suites.py` includes:
  - `baseline`
  - `expanded`
  - `recovery_focused`
  - `memory_governance`
  - `conversation_continuations`
  - `robustness_focused`
  - `default`
  - `release_gate_v1`
  - `all_registered`
- Current benchmark schema in `backend/app/benchmark/schemas.py` has only the V1 taxonomy path:
  - `BenchmarkCaseTaxonomy`
  - `BenchmarkCase.taxonomy`
  - `BenchmarkCaseMatrixSummary`
- Current `build_case_matrix_summary(...)` in `backend/app/benchmark/matrix.py` consumes only V1 taxonomy plus `tool_profile` and `world_profile`.
- `BenchmarkHarness` already:
  - copies `case.taxonomy` into `BenchmarkCaseResult`
  - builds `benchmark_summary.matrix_summary` from input cases
  - writes suite reports via `run_suite(...)`
- Existing tests assert exact suite order and exact matrix counts for:
  - `release_gate_v1`
  - `all_registered`
  - `coverage_gate_v1_5`
- Current registered canonical inventory is `22` cases.
- Current submission evidence is green:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `all_registered`
  - recovery review
- Current dirty state includes untracked files that must remain untouched:
  - `docs/specs/092-v2-integrity-benchmark-suite-taxonomy-v0.md`
  - `docs/superpowers/`

## 3. Files to Add

- `tests/test_benchmark_v2_taxonomy.py` - focused unit coverage for deterministic V2 taxonomy derivation and V2 summary behavior.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add V2 taxonomy schema types, additive summary contract, and new suite ID literal.
- `backend/app/benchmark/suites.py` - add `v2_integrity` suite ID, membership rule, title/description, deterministic suite placement, and V2 summary wiring.
- `backend/app/benchmark/matrix.py` - add additive V2 taxonomy summary builder without changing the existing `matrix_summary` function contract.
- `backend/app/benchmark/fixtures.py` - optionally add loader-level V2 taxonomy derivation hook if that is the narrowest place to centralize fallback resolution.
- `backend/app/benchmark/harness.py` - attach additive V2 summary data to suite/run outputs if needed by the chosen summary surface.
- `tests/test_benchmark_suites.py` - extend suite catalog and suite membership assertions for `v2_integrity` plus non-regression checks for existing suites.
- `tests/test_benchmark_coverage_gate.py` - add explicit regression assertions that the existing coverage-gate path remains unchanged after V2 additions.
- `tests/test_benchmark_harness.py` - add unit coverage for additive V2 summary presence and non-regression of the old summary/report paths.
- `tests/integration/test_benchmark_harness_gateway.py` - add one gateway-backed regression test for `v2_integrity` execution/reporting if the suite is exposed through `run_suite(...)`.
- `README.md` - document `v2_integrity` and the additive V2 taxonomy/summarization surface at a high level if implementation touches public benchmark docs.

## 5. Files That Must Not Change

- `backend/app/benchmark/coverage_gate.py`
- `backend/app/benchmark/release_gate.py`
- `backend/app/benchmark/cases/*.json` as the default implementation path
- `var/` benchmark artifacts
- any release gate threshold constants
- any formal verification or latest canonical artifact files

If an implementer believes one of these files must change, they should stop and report why before proceeding.

## 6. Implementation Strategy Choice

This plan chooses the lower-risk path for Phase 1:

- do **not** batch-edit the 22 benchmark case JSON fixtures first
- do **not** replace the existing V1 taxonomy
- do **not** extend the existing `matrix_summary` payload in place
- instead:
  - add an additive V2 taxonomy schema
  - derive V2 taxonomy deterministically in Python from existing case fields when explicit V2 fields are absent
  - expose V2 rollups via a dedicated additive summary surface

Reasoning:

- existing tests and gates assert exact `matrix_summary` counts
- `release_gate_v1` depends on exact V1 `level_counts` and `failure_mode_counts`
- fixture rewrites create unnecessary churn and increase the risk of canonical-evidence drift
- the spec explicitly allows deterministic fallback and does not require immediate case-JSON backfill

## 7. Implementation Steps

### Task 1: Lock the V2 Taxonomy Contract

**Files:**
- Modify: `backend/app/benchmark/schemas.py`
- Test: `tests/test_benchmark_v2_taxonomy.py`

- [ ] **Step 1: Write the failing schema tests**

Add tests that define the intended additive contracts:
- `BenchmarkSuiteId` accepts `v2_integrity`
- `BenchmarkCaseV2Taxonomy` exists with:
  - `scenario_bucket`
  - `level`
  - `failure_mode`
  - `memory_mode`
  - `conversation_mode`
  - `stability_required`
- `BenchmarkSuiteDescription` or an adjacent additive summary contract can carry a V2 summary without removing `matrix_summary`

Recommended test targets:
- valid values for each new enum-like field
- invalid `failure_mode` format is rejected
- V2 taxonomy summary model serializes deterministically

- [ ] **Step 2: Run the focused schema tests to verify they fail**

Run:

```bash
python -m pytest tests/test_benchmark_v2_taxonomy.py -q
```

Expected:
- FAIL because V2 taxonomy models do not exist yet

- [ ] **Step 3: Add the minimal schema definitions**

In `backend/app/benchmark/schemas.py`:
- extend `BenchmarkSuiteId` to include `v2_integrity`
- add `BenchmarkCaseV2Taxonomy`
- add additive V2 summary model(s), for example:
  - `BenchmarkCaseV2MatrixSummary`
  - or another clearly named additive summary type
- add the additive V2 summary field to the narrowest existing output contract that will expose it, likely:
  - `BenchmarkSuiteDescription`
  - and optionally `BenchmarkSummary`

Keep existing V1 models unchanged in meaning.

- [ ] **Step 4: Re-run the focused schema tests**

Run:

```bash
python -m pytest tests/test_benchmark_v2_taxonomy.py -q
```

Expected:
- PASS for the new schema contract tests

### Task 2: Add Deterministic V2 Taxonomy Derivation

**Files:**
- Modify: `backend/app/benchmark/fixtures.py`
- Modify: `backend/app/benchmark/schemas.py`
- Test: `tests/test_benchmark_v2_taxonomy.py`

- [ ] **Step 1: Write failing derivation tests for the 22-case inventory**

Add tests that lock fallback behavior for representative cases:
- memory:
  - `family_memory_override_v1 -> memory_mode="override_guarded"`
  - `family_memory_advisory_fill_v1 -> memory_mode="advisory_fill"`
  - `family_memory_expired_advisory_v1 -> memory_mode="expired_advisory"`
- continuation:
  - `solo_clarification_continuation_v1 -> conversation_mode="clarification"`
  - `family_replan_version_continuation_v1 -> conversation_mode="replan_versioned"`
- recovery:
  - `family_route_failure_v1 -> failure_mode="route_unavailable"`
  - `family_route_and_dining_unavailable_v1 -> failure_mode="route_and_dining_unavailable"`
- robustness/stability:
  - `family_distractor_selection_v1 -> stability_required=True`
  - `rainy_day_stable_sorting_v1 -> stability_required=True`
- L4-style composite:
  - at least one existing case resolves to `level="L4"`

Also add a global test:
- every case returned by `load_registered_benchmark_cases()` resolves to a non-null V2 taxonomy object

- [ ] **Step 2: Run the derivation tests to verify they fail**

Run:

```bash
python -m pytest tests/test_benchmark_v2_taxonomy.py -q
```

Expected:
- FAIL because no derivation path exists yet

- [ ] **Step 3: Implement a centralized fallback resolver**

Choose one implementation location and keep it single-sourced:
- preferred: `backend/app/benchmark/fixtures.py`
- acceptable: a helper in `backend/app/benchmark/schemas.py`

Add a deterministic resolver that:
- copies `scenario_bucket` from existing V1 taxonomy
- normalizes V2 `failure_mode` to `"none"` when V1 is null
- derives `memory_mode`
- derives `conversation_mode`
- derives `stability_required`
- derives V2 `level` without changing V1 `taxonomy.level`

Do not change case JSON payloads as part of this step.

- [ ] **Step 4: Re-run the V2 derivation tests**

Run:

```bash
python -m pytest tests/test_benchmark_v2_taxonomy.py -q
```

Expected:
- PASS for the explicit fallback cases

### Task 3: Add Additive V2 Summary Builders

**Files:**
- Modify: `backend/app/benchmark/matrix.py`
- Modify: `backend/app/benchmark/harness.py`
- Test: `tests/test_benchmark_v2_taxonomy.py`
- Test: `tests/test_benchmark_harness.py`

- [ ] **Step 1: Write failing summary tests**

Add tests that assert:
- the old `build_case_matrix_summary(...)` output remains unchanged
- a new V2 summary builder exists and counts:
  - `scenario_bucket_counts`
  - `level_counts`
  - `failure_mode_counts`
  - `memory_mode_counts`
  - `conversation_mode_counts`
  - `stability_required_counts`
- the V2 summary can be attached to suite descriptions or benchmark summaries without removing the existing `matrix_summary`

- [ ] **Step 2: Run the summary-focused tests to verify they fail**

Run:

```bash
python -m pytest tests/test_benchmark_v2_taxonomy.py tests/test_benchmark_harness.py -q
```

Expected:
- FAIL because the additive V2 summary builder/field does not exist yet

- [ ] **Step 3: Implement the additive V2 summary builder**

In `backend/app/benchmark/matrix.py`:
- keep `build_case_matrix_summary(...)` exactly as the V1 path
- add a separate helper, for example:
  - `build_case_v2_matrix_summary(...)`

In `backend/app/benchmark/harness.py`:
- attach V2 summary only through an additive field/path
- do not overwrite `benchmark_summary.matrix_summary`

- [ ] **Step 4: Re-run the summary-focused tests**

Run:

```bash
python -m pytest tests/test_benchmark_v2_taxonomy.py tests/test_benchmark_harness.py -q
```

Expected:
- PASS with no changes to old matrix assertions

### Task 4: Add the `v2_integrity` Suite

**Files:**
- Modify: `backend/app/benchmark/suites.py`
- Test: `tests/test_benchmark_suites.py`

- [ ] **Step 1: Write the failing suite-catalog tests**

Add tests that lock:
- `list_benchmark_suites()` now includes `v2_integrity`
- old suite order is preserved
- `release_gate_v1` membership is unchanged
- `all_registered` membership and order are unchanged
- `v2_integrity` membership is deterministic and uses only existing cases
- `v2_integrity` covers:
  - memory
  - recovery
  - continuation
  - robustness
  - at least one L4-style composite case

Also add case-to-suite membership tests for representative cases.

- [ ] **Step 2: Run the suite tests to verify they fail**

Run:

```bash
python -m pytest tests/test_benchmark_suites.py -q
```

Expected:
- FAIL because `v2_integrity` is not in the suite catalog yet

- [ ] **Step 3: Implement `v2_integrity` in `suites.py`**

Add:
- `suite_id = "v2_integrity"`
- title
- description
- membership rule based on deterministic filtering over the registered 22-case order

Preferred membership implementation:
- derive from the canonical registered order
- include a case if it satisfies at least one integrity dimension from the spec
- keep the resulting order equal to canonical registered order

Do not:
- reorder `_ORDERED_SUITE_IDS` except to append/add `v2_integrity` in a deliberate deterministic position
- touch `release_gate_v1` case IDs
- touch `all_registered` case IDs

- [ ] **Step 4: Re-run the suite tests**

Run:

```bash
python -m pytest tests/test_benchmark_suites.py -q
```

Expected:
- PASS for `v2_integrity` membership and legacy non-regression assertions

### Task 5: Add Harness-Level Non-Regression Coverage

**Files:**
- Modify: `tests/test_benchmark_harness.py`
- Modify: `tests/integration/test_benchmark_harness_gateway.py`

- [ ] **Step 1: Write failing unit and integration tests for suite execution**

Add unit assertions that:
- `run_suite("v2_integrity")` emits a suite report with:
  - unchanged old `matrix_summary`
  - additive V2 summary present if the implementation exposes it at suite/run level
- old `run_suite("release_gate_v1")` assertions still pass unchanged

Add one integration test that:
- runs `BenchmarkHarness.run_suite("v2_integrity")`
- asserts the report succeeds
- asserts no old suite summary contract regressed

- [ ] **Step 2: Run the harness unit and integration tests to verify the new expectations fail**

Run:

```bash
python -m pytest tests/test_benchmark_harness.py -q
```

Expected:
- FAIL because `v2_integrity` execution path is not covered yet

- [ ] **Step 3: Make the minimal harness/reporting adjustments**

Only if required by failing tests:
- wire additive V2 summary into the suite/run report path
- keep all old report fields unchanged

Avoid changing benchmark execution semantics.

- [ ] **Step 4: Re-run the harness unit test**

Run:

```bash
python -m pytest tests/test_benchmark_harness.py -q
```

Expected:
- PASS

### Task 6: Prove `coverage_gate_v1_5` and Canonical Evidence Are Unchanged

**Files:**
- Modify: `tests/test_benchmark_coverage_gate.py`

- [ ] **Step 1: Add explicit non-regression assertions**

Add or tighten tests so they prove:
- `coverage_gate_v1_5` still reads the old `matrix_summary`
- no V2 summary field is required by the gate
- passing counts for `all_registered` stay exactly:
  - `case_count == 22`
  - existing scenario/world/failure counts unchanged

- [ ] **Step 2: Run the coverage and harness regression tests**

Run:

```bash
python -m pytest tests/test_benchmark_coverage_gate.py tests/test_benchmark_harness.py -q
```

Expected:
- PASS with no threshold or artifact-layout regressions

### Task 7: Update Benchmark Documentation Minimally

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a small benchmark documentation update**

Document only:
- `v2_integrity` exists as an additive suite
- V2 taxonomy is additive and fallback-derived in Phase 1
- old release/coverage gates remain unchanged

Do not document refreshed artifacts or claim canonical evidence has changed.

- [ ] **Step 2: Review the README diff for scope**

Check that the doc update:
- stays within benchmark catalog/taxonomy explanation
- does not imply AMap or real-provider benchmark inclusion

## 8. Testing Plan

- Unit tests:
  - `tests/test_benchmark_v2_taxonomy.py`
    - V2 taxonomy schema validation
    - deterministic fallback derivation
    - additive V2 summary counts
  - `tests/test_benchmark_suites.py`
    - `v2_integrity` membership
    - old suite order unchanged
    - old suite membership unchanged
  - `tests/test_benchmark_harness.py`
    - `run_suite("v2_integrity")`
    - additive V2 summary exposure
    - old suite report paths unchanged
  - `tests/test_benchmark_coverage_gate.py`
    - V2 additions do not affect the existing gate

- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py`
    - `BenchmarkHarness.run_suite("v2_integrity")` succeeds
    - old benchmark report assertions remain valid

- Smoke tests:
  - `python scripts/show_submission_evidence.py`
  - `git diff --check`
  - `git status --short`

## 9. Verification Commands

Commands the implementer must run before claiming completion:

```bash
python -m pytest tests/test_benchmark_suites.py -q
python -m pytest tests/test_benchmark_v2_taxonomy.py -q
python -m pytest tests/test_benchmark_coverage_gate.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -k "v2_integrity or all_registered or release_gate_v1" -v
python scripts/show_submission_evidence.py
git diff --check
git status --short
```

## 10. Commit and Push Plan

User instruction for this task is documentation-only planning. Do not commit, do not stage, and do not push while executing this plan-writing task.

For the later implementation task, the implementer should prepare a focused commit only after all verification commands pass. Expected commit message:

```text
feat: add v2 integrity benchmark suite and taxonomy
```

## 11. Out-of-scope Changes

- Do not add new benchmark cases unless a failing test proves the current 22 cases cannot express the composite integrity requirement.
- Do not modify `release_gate_v1`.
- Do not change `coverage_gate_v1_5` thresholds or behavior.
- Do not change `all_registered` case order.
- Do not refresh canonical benchmark artifacts.
- Do not add AMap or any real provider to formal benchmark execution.
- Do not implement memory lifecycle, System Integrity UI, Pass@4, or Pass^4.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md`.
- Do not add new dependencies.
- Do not commit generated caches, virtual environments, secrets, or local artifacts.

## 12. Rollback Strategy

- Keep V2 work additive:
  - new schema types
  - new suite ID
  - new V2 summary path
- If regressions appear in existing gates, revert in this order:
  1. remove V2 summary attachment from suite/run output
  2. remove `v2_integrity` from the suite catalog
  3. disable V2 taxonomy derivation hook
- Do not revert or rewrite:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `all_registered`
  - canonical evidence under `var/`

## 13. Review Checklist

- [ ] The implementation matches `docs/specs/092-v2-integrity-benchmark-suite-taxonomy-v0.md`.
- [ ] `v2_integrity` is additive and deterministic.
- [ ] `release_gate_v1` membership and counts are unchanged.
- [ ] `all_registered` membership and order are unchanged.
- [ ] `coverage_gate_v1_5` still passes without using a new required summary field.
- [ ] Every registered case resolves to a V2 taxonomy object.
- [ ] V2 taxonomy fallback rules match the spec.
- [ ] At least one existing case is classified as an L4-style composite integrity case.
- [ ] No new benchmark case was added unless the implementer documented a proven necessity.
- [ ] No benchmark JSON fixture rewrite was performed unless explicitly justified.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] No `.env`, token, key, secret, or `var/` artifact was staged or committed.

## 14. Handoff Notes

After implementation, report back with:

- changed files
- final `v2_integrity` case list in canonical order
- final V2 taxonomy fallback table
- whether any case JSON files were modified or intentionally left unchanged
- the additive V2 summary field name and where it is exposed
- verification commands run and their results
- confirmation that `release_gate_v1`, `all_registered`, and `coverage_gate_v1_5` remained unchanged in behavior
- any blocker around the L4-style composite classification rule
