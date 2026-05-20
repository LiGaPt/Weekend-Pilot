# Plan: 040 Benchmark Suite Catalog v0

## 1. Spec Reference

Spec file:

```text
docs/specs/040-benchmark-suite-catalog-v0.md
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

- Current branch is `codex/benchmark-case-taxonomy-matrix-v0`.
- Latest completed numbered task is `039`.
- Latest commit is `a30ad84 feat: add benchmark case taxonomy and matrix summary`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `039`.
- There is no newer numbered spec/plan to continue before opening Task `040`.
- The current branch is synced with its remote; there is no unfinished numbered task after `039`.
- Pre-existing local context files remain untracked:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- These untracked files are not part of Task `040` and must remain unstaged.
- Current benchmark structure already includes:
  - required taxonomy on every case fixture
  - suite `matrix_summary`
  - canonical `run_summary`
  - benchmark timing summary
- Current suite composition is still hardcoded only through:
  - `_DEFAULT_CASE_IDS`
  - `_FAILURE_CASE_IDS`
  in `backend/app/benchmark/fixtures.py`
- There is no named suite catalog, no suite description contract, and no helper for `all_registered` coverage.
- `BenchmarkHarness.run_cases(cases)` already accepts any ordered case list, so this task should focus on catalog/loading only, not harness redesign.

## 3. Files to Add

- `backend/app/benchmark/suites.py` - canonical named benchmark suite catalog plus load/list helpers.
- `tests/test_benchmark_suites.py` - focused unit coverage for suite IDs, suite membership, and derived matrix summaries.

## 4. Files to Modify

- `backend/app/benchmark/fixtures.py` - expose canonical registered-case ordering and a helper to load all registered cases.
- `backend/app/benchmark/schemas.py` - add the typed suite description contract.
- `backend/app/benchmark/__init__.py` - export the new suite helpers from the package root.
- `tests/integration/test_benchmark_harness_gateway.py` - add gateway-backed `all_registered` suite coverage.
- `README.md` - document the named suite catalog and current suite semantics.

## 5. Implementation Steps

1. Add the suite description contract in `backend/app/benchmark/schemas.py`.
   Define:
   - `BenchmarkSuiteId = Literal["default", "failures", "all_registered"]`
   - `BenchmarkSuiteDescription` with:
     - `suite_id: BenchmarkSuiteId`
     - `title: str`
     - `description: str`
     - `case_ids: list[str]`
     - `case_count: int`
     - `matrix_summary: BenchmarkCaseMatrixSummary`

   Keep the contract repository-facing only. Do not add HTTP or CLI wrappers for it.

2. Refactor fixture loading in `backend/app/benchmark/fixtures.py`.
   Replace the separate default/failure membership constants with one canonical registered-case order:

   - `family_afternoon_v1`
   - `family_indoor_light_meal_v1`
   - `family_outdoor_quick_dinner_v1`
   - `family_memory_override_v1`
   - `family_citywalk_addon_v1`
   - `solo_afternoon_v1`
   - `family_route_failure_v1`

   Then:
   - keep `load_benchmark_case(case_id)` validation against that registered set
   - add `load_registered_benchmark_cases()` that loads all seven cases in that canonical order

   Do not change fixture file schemas or error messages for malformed/missing case files.

3. Create `backend/app/benchmark/suites.py`.
   Add one internal suite catalog with explicit suite definitions and stable ordering.

   Use these exact suite definitions:

   - `default`
     - title: `Default benchmark suite`
     - description: `Current non-failure baseline suite used by repository benchmark examples.`
     - case IDs:
       - `family_afternoon_v1`
       - `family_indoor_light_meal_v1`
       - `family_outdoor_quick_dinner_v1`
       - `family_memory_override_v1`
       - `family_citywalk_addon_v1`
       - `solo_afternoon_v1`

   - `failures`
     - title: `Failure benchmark suite`
     - description: `Current failure-injection benchmark cases kept outside the default suite.`
     - case IDs:
       - `family_route_failure_v1`

   - `all_registered`
     - title: `All registered benchmark cases`
     - description: `Current default plus failure cases in canonical repository order.`
     - case IDs:
       - the six `default` IDs
       - followed by `family_route_failure_v1`

   Implement:
   - `load_benchmark_suite(suite_id: BenchmarkSuiteId) -> list[BenchmarkCase]`
   - `list_benchmark_suites() -> list[BenchmarkSuiteDescription]`
   - `load_default_benchmark_cases()` as a thin wrapper to `load_benchmark_suite("default")`
   - `load_failure_benchmark_cases()` as a thin wrapper to `load_benchmark_suite("failures")`

4. Validate the suite catalog inside `backend/app/benchmark/suites.py`.
   Add one private validation helper that runs when loading or listing suites and checks:
   - suite IDs are known
   - each suite has no duplicate case IDs
   - every case ID referenced by a suite exists in the canonical registered-case order

   On failure, raise `BenchmarkHarnessError` with a clear message such as:
   - `Unknown benchmark suite ID: <suite_id>`
   - `Benchmark suite <suite_id> references unknown case ID: <case_id>`
   - `Benchmark suite <suite_id> contains duplicate case ID: <case_id>`

5. Reuse Task 039 matrix summaries instead of reimplementing them.
   In `list_benchmark_suites()`:
   - load each suite’s cases in the defined order
   - call `build_case_matrix_summary(cases)`
   - return `BenchmarkSuiteDescription` entries in this exact order:
     - `default`
     - `failures`
     - `all_registered`

   Do not duplicate counter logic from `backend/app/benchmark/matrix.py`.

6. Export the new helpers from `backend/app/benchmark/__init__.py`.
   Add exports for:
   - `BenchmarkSuiteDescription`
   - `load_registered_benchmark_cases`
   - `load_benchmark_suite`
   - `list_benchmark_suites`

   Keep existing exports working unchanged.

7. Add focused unit tests in `tests/test_benchmark_suites.py`.
   Add exact assertions for:
   - `load_registered_benchmark_cases()` returns these case IDs in this order:
     - `family_afternoon_v1`
     - `family_indoor_light_meal_v1`
     - `family_outdoor_quick_dinner_v1`
     - `family_memory_override_v1`
     - `family_citywalk_addon_v1`
     - `solo_afternoon_v1`
     - `family_route_failure_v1`
   - `load_benchmark_suite("default")` returns the current six default case IDs in order
   - `load_benchmark_suite("failures")` returns only `family_route_failure_v1`
   - `load_benchmark_suite("all_registered")` returns all seven case IDs in order
   - `list_benchmark_suites()` returns suite descriptions in the order:
     - `default`
     - `failures`
     - `all_registered`
   - `default.matrix_summary` matches:
     - `scenario_bucket_counts={"family": 5, "solo": 1}`
     - `level_counts={"L1": 3, "L2": 3}`
     - `world_profile_counts={"family_afternoon": 5, "solo_afternoon": 1}`
     - `failure_mode_counts={"none": 6}`
   - `all_registered.matrix_summary` matches:
     - `scenario_bucket_counts={"family": 6, "solo": 1}`
     - `level_counts={"L1": 3, "L2": 4}`
     - `world_profile_counts={"family_afternoon": 6, "solo_afternoon": 1}`
     - `failure_mode_counts={"none": 6, "route_unavailable": 1}`
     - `tag_counts` exactly:
       - `addon_optional=1`
       - `baseline=2`
       - `child_friendly=6`
       - `citywalk=1`
       - `failure_injected=1`
       - `indoor_activity=2`
       - `light_activity=1`
       - `light_meal=5`
       - `memory_override=1`
       - `outdoor_activity=1`
       - `quick_dinner=1`
       - `route_failure=1`
   - unknown suite ID raises `BenchmarkHarnessError`
   - legacy wrappers still match the suite catalog:
     - `load_default_benchmark_cases() == load_benchmark_suite("default")`
     - `load_failure_benchmark_cases() == load_benchmark_suite("failures")`

8. Add gateway-backed integration coverage in `tests/integration/test_benchmark_harness_gateway.py`.
   Add one new test that:
   - loads `cases = load_benchmark_suite("all_registered")`
   - runs `BenchmarkHarness.run_cases(cases)`
   - asserts:
     - `len(report.case_results) == 7`
     - `report.run_status == "passed"`
     - `report.passed_count == 7`
     - `report.failed_count == 0`
     - `report.error_count == 0`
     - `report.benchmark_summary.matrix_summary.scenario_bucket_counts == {"family": 6, "solo": 1}`
     - `report.benchmark_summary.matrix_summary.level_counts == {"L1": 3, "L2": 4}`
     - `report.benchmark_summary.matrix_summary.world_profile_counts == {"family_afternoon": 6, "solo_afternoon": 1}`
     - `report.benchmark_summary.matrix_summary.failure_mode_counts == {"none": 6, "route_unavailable": 1}`

   Keep the existing default-suite and failure-suite integration tests unchanged.

9. Update `README.md`.
   In the LocalLife-Bench section, document:
   - current named suites:
     - `default`
     - `failures`
     - `all_registered`
   - `default` remains the explicit baseline suite
   - `all_registered` is the full current fixture inventory
   - suite descriptions derive matrix summaries from the existing taxonomy

   Keep the documentation short. Do not add CLI or API instructions that do not exist.

10. Run focused verification and keep staging clean.
    Run the unit test file for suites first, then the existing benchmark harness unit test, then the gateway-backed integration test.
    Before commit, confirm these remain unstaged:
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `var/`

## 6. Testing Plan

- Unit tests:
  - canonical registered-case order is stable
  - named suite membership is exact and deterministic
  - suite descriptions include derived matrix summaries
  - unknown suite IDs raise typed errors
  - legacy wrappers still match the new suite catalog
- Integration tests:
  - `BenchmarkHarness.run_cases(load_benchmark_suite("all_registered"))` succeeds with the mixed seven-case suite
  - suite benchmark summary keeps exact matrix counts for the full registered inventory
- Smoke checks:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark suite catalog
```

Expected commands:

```bash
git status --short
git add README.md
git add backend/app/benchmark/__init__.py
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/suites.py
git add tests/test_benchmark_suites.py
git add tests/integration/test_benchmark_harness_gateway.py
git add docs/specs/040-benchmark-suite-catalog-v0.md
git add docs/plans/040-benchmark-suite-catalog-v0-plan.md
git diff --cached --check
git commit -m "feat: add benchmark suite catalog"
git push -u origin <task-040-branch>
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not add new benchmark fixtures or new scenario profiles.
- Do not add prompt-driven case generation or fixture synthesis.
- Do not add a taxonomy-filter DSL, suite query language, or automatic suite inference from all discovered cases.
- Do not change benchmark scoring, replay stable-compare fields, workflow routing, or observability/report schemas.
- Do not add CLI commands, API routes, or frontend pages for suite selection.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md`.
- Do not add new dependencies.
- Do not commit generated caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/040-benchmark-suite-catalog-v0.md`.
- [ ] The suite catalog exists with `default`, `failures`, and `all_registered`.
- [ ] The canonical registered-case order is explicit and deterministic.
- [ ] Legacy `load_default_benchmark_cases()` and `load_failure_benchmark_cases()` behavior is preserved.
- [ ] `list_benchmark_suites()` returns derived matrix summaries without duplicating counting logic.
- [ ] The `all_registered` suite produces the exact seven-case composition expected by the spec.
- [ ] Gateway-backed harness execution still passes with the new `all_registered` suite.
- [ ] The implementation stayed inside benchmark-catalog scope only.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/` artifact, or unrelated local file was committed.

## 11. Handoff Notes

Report back with:

- The exact files changed.
- The final ordered suite definitions for `default`, `failures`, and `all_registered`.
- The exact `all_registered` matrix summary counts as serialized by the implementation.
- The verification commands that were run, plus their results.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files were not staged.
- Any follow-up limitation, especially that future roadmap work still needs a separate task for actual case-generation tooling rather than just the suite catalog.
