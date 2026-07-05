# Spec: 125 Mock World Scenario Coverage Closure v0

## 1. Goal

Complete the final closure pass for Mock World multi-scenario coverage. WeekendPilot should be able to prove that the current system is not dependent on a single family-afternoon happy path, but can load, plan, review, execute, and evaluate across the canonical local Mock World scenario inventory.

This task is a convergence and regression-lock task, not a new scenario expansion. After completion, the repository should have a focused verification surface showing that supported Mock World profiles, benchmark cases, suite membership, taxonomy summaries, and case matrix rows remain aligned. Documentation should no longer imply that the system only supports a parent-child/family scenario, while still preserving the current public-demo boundary.

## 2. Project Context

This task maps to `docs/NEXT_PHASE_ROADMAP.md` milestone `M3. Mock World 场景与 benchmark 完整性`.

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a benchmark-driven local-life planning and execution system. The MVP started with a family scenario, but the V1/V2 direction requires broader LocalLife-Bench coverage across personas, constraints, failure modes, recovery paths, and evaluation surfaces.

Current repository context:

- Task `116` locked the Mock World scenario taxonomy baseline.
- Task `117` introduced `backend/app/benchmark/case_matrix.py` as the derived source for registered benchmark order and suite membership.
- Task `123` stabilized the customer Mock World V2 demo flow.
- Task `124` converged the reviewer evidence entrypoint and unblocked final Mock World V2 verification.
- Current benchmark inventory is expected to remain at `30` registered Mock World cases, with `v2_integrity = 20`, `recovery_focused = 8`, `default = 11`, `expanded = 5`, and `all_registered = 30`.

This task should strengthen the evidence that Mock World is the stable formal benchmark base and that scenario breadth is intentional, measurable, and protected from drift.

## 3. Requirements

- The task must verify that the canonical Mock World profile set still loads:
  - `family_afternoon`
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
  - `elder_afternoon`

- The task must confirm every supported Mock World profile is represented by at least one registered benchmark case in `all_registered`.

- The task must confirm all public Mock World demo profiles can enter a reviewable planning state through the existing demo/backend planning path.
  - Public scenario chips should remain the current public set.
  - `elder_afternoon` should remain benchmark-covered unless existing product code already exposes it publicly.

- The task must confirm benchmark case inventory and suite membership remain aligned with the case matrix:
  - `load_registered_benchmark_cases()` returns `30` cases.
  - `build_benchmark_case_matrix_manifest()` reports `30` registered cases.
  - `load_benchmark_suite("default")` returns `11` cases.
  - `load_benchmark_suite("expanded")` returns `5` cases.
  - `load_benchmark_suite("recovery_focused")` returns `8` cases.
  - `load_benchmark_suite("v2_integrity")` returns `20` cases.
  - `load_benchmark_suite("all_registered")` returns `30` cases.

- The task must confirm suite descriptions, matrix summaries, and V2 taxonomy summaries agree for representative suites:
  - `default`
  - `expanded`
  - `release_gate_v1`
  - `v2_integrity`
  - `all_registered`

- The task must add or tighten a focused regression surface that fails if:
  - a supported profile disappears from loader coverage
  - a supported profile is no longer represented by registered benchmark cases
  - case matrix rows drift from benchmark fixture values
  - suite counts drift without intentional test updates
  - public docs regress to family-only wording

- The task must update documentation that still implies Mock World only supports the family scenario.
  - Keep the historically accurate statement that the MVP started with a family scenario.
  - Update current-state wording to say Mock World now covers multiple local simulated scenarios.
  - Preserve the distinction between public demo scenario chips and benchmark-only coverage.

- The task must not add new dependencies, migrations, report schema changes, public API fields, or new generated artifacts.

## 4. Non-goals

- Do not add a new Mock World profile.
- Do not add a new benchmark case ID.
- Do not add a seventh public scenario chip unless an existing test proves the code already expects it.
- Do not change `release_gate_v1`, `coverage_gate_v1_5`, `v2_integrity_gate`, `safe_stop_gate_v1`, or `all_registered` semantics.
- Do not rewrite `BenchmarkCaseTaxonomy`, `BenchmarkCaseV2Taxonomy`, benchmark report schemas, or artifact schemas.
- Do not change AMap preview behavior.
- Do not change memory governance, recovery policy, Action Ledger behavior, or the human confirmation boundary.
- Do not refresh or commit `var/` benchmark artifacts unless a verification command explicitly requires regeneration and the project already tracks that exact artifact type.
- Do not commit `.env`, API keys, tokens, secrets, caches, virtual environments, or local-only files.

## 5. Interfaces and Contracts

### Inputs

- `load_mock_world(profile)`
- `load_registered_benchmark_cases()`
- `load_benchmark_suite(suite_id)`
- `list_benchmark_suites()`
- `build_benchmark_case_matrix_manifest(suite_id=None)`
- `list_benchmark_case_matrix_rows()`
- `scripts/generate_benchmark_case_matrix.py`
- Existing demo planning API/service entrypoints used by current tests
- Existing public documentation in `README.md`, `docs/WEB_DEMO_README.md`, and submission docs

### Outputs

- A focused regression test proving Mock World scenario coverage closure.
- Updated docs only where current wording still understates multi-scenario Mock World coverage.
- No behavior change unless inspection finds a real drift between loader, matrix, suite, taxonomy, or planning readiness.

### Schemas

This task introduces no new runtime schema. The expected closure baseline is:

```json
{
  "supported_world_profiles": [
    "family_afternoon",
    "friends_gathering",
    "solo_afternoon",
    "couple_afternoon",
    "rainy_day_fallback",
    "budget_lite",
    "elder_afternoon"
  ],
  "registered_case_count": 30,
  "suite_counts": {
    "default": 11,
    "expanded": 5,
    "recovery_focused": 8,
    "v2_integrity": 20,
    "all_registered": 30
  },
  "formal_tool_profile": "mock_world"
}
```

If the implementation adds a test helper constant, keep it local to the test module unless an existing production constant already exists.

## 6. Observability

This task does not add a new runtime observability surface or report schema.

It must preserve and verify the existing evidence surfaces:

- benchmark matrix manifest
- suite descriptions from `list_benchmark_suites()`
- `matrix_summary`
- `v2_taxonomy_summary`
- coverage gate / formal verification outputs

If documentation is updated, it should direct reviewers to existing evidence commands rather than adding a new evidence format.

## 7. Failure Handling

- If a supported Mock World profile no longer loads, fix the minimal loader or fixture issue that caused the regression.
- If a profile loads but has no registered benchmark representation, inspect whether the drift is in `case_matrix.py` or the expected profile set; fix the nearest source of truth.
- If suite membership differs from `case_matrix.py`, treat `case_matrix.py` as the intended source of truth after Task 117 and fix stale consumers unless `case_matrix.py` is demonstrably wrong.
- If documentation already correctly reflects multi-scenario coverage, do not rewrite it only to create a diff.
- If proving planning-review readiness requires broad workflow or frontend rewrites, stop and report because that exceeds this closure slice.
- If verification commands fail because of missing local dependencies, report the exact blocker and still run all commands that do not require that dependency.

## 8. Acceptance Criteria

- [ ] `docs/specs/125-mock-world-scenario-coverage-closure-v0.md` exists and matches this task.
- [ ] `docs/plans/125-mock-world-scenario-coverage-closure-v0-plan.md` exists and matches this task.
- [ ] A focused regression test verifies all canonical Mock World profiles load.
- [ ] A focused regression test verifies every canonical Mock World profile is represented by at least one `all_registered` benchmark case.
- [ ] A focused regression test verifies public Mock World demo profiles can enter a reviewable planning state using the current demo/backend path.
- [ ] A focused regression test verifies case matrix counts, suite counts, and loaded suite counts remain aligned.
- [ ] Existing benchmark suite and matrix tests remain green.
- [ ] `README.md` and relevant docs no longer imply that the current system only supports family/parent-child scenarios.
- [ ] Historical MVP wording is preserved where it is explicitly historical.
- [ ] No new profile, benchmark case, public scenario chip, dependency, migration, public API field, or report schema is introduced.
- [ ] No `.env`, API key, token, secret, cache, virtual environment, or unrelated local file is staged.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except for pre-existing unrelated untracked files.

## 9. Verification Commands

```bash
python -m pytest tests/test_mock_world_scenario_taxonomy.py tests/test_benchmark_case_matrix_generation.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
python -m pytest tests/test_mock_world_scenario_coverage_closure.py -q
python scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json
python scripts/run_benchmark_coverage_gate.py
python scripts/run_formal_verification.py
rg -n "family-only|only family|只支持亲子|只覆盖亲子|五个默认 Mock World 家庭场景|默认 Mock World 家庭场景" README.md docs
git diff --check
git status --short
```

If the final `rg` command returns historical references only, the implementer must document why those references are acceptable. If it returns current-state family-only wording, update the docs and rerun the command.

## 10. Expected Commit

```text
test: lock mock world scenario coverage closure
```

## 11. Notes for the Implementer

This is a closure task. Prefer tests and minimal doc wording fixes over production changes.

Start by confirming current behavior, because Task 116 and Task 117 already implemented much of the taxonomy and matrix foundation. The likely remaining gap is a single focused closure test that combines loader coverage, benchmark representation, planning readiness, and doc drift checks.

Do not stage existing untracked local files such as `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, or `docs/superpowers/` unless the user explicitly asks for them in a separate task.
