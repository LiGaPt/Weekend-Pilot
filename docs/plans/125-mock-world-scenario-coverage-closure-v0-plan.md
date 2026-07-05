# Plan: 125 Mock World Scenario Coverage Closure v0

## 1. Spec Reference

Spec file:

```text
docs/specs/125-mock-world-scenario-coverage-closure-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
M3. Mock World 场景与 benchmark 完整性
```

## 2. Current Repository Assumptions

- Current branch is `codex/124-review-evidence-entrypoint-convergence-v0`.
- Latest commit is `f3c59d4 docs: add review evidence entrypoint task docs`.
- Latest implemented and documented task is Task `124`.
- `docs/specs/` and `docs/plans/` match through Task `124`.
- Historical numbering has a shared Task `122` gap and a special `113.5` task; do not backfill or renumber either.
- Existing untracked local files are unrelated and must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Task `116` already added a focused Mock World scenario taxonomy regression.
- Task `117` already introduced `backend/app/benchmark/case_matrix.py`; `fixtures.py` and `suites.py` now derive registered order and suite membership from it.
- Current canonical profile set is:
  - `family_afternoon`
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
  - `elder_afternoon`
- Current canonical benchmark counts are:
  - `registered = 30`
  - `default = 11`
  - `expanded = 5`
  - `recovery_focused = 8`
  - `v2_integrity = 20`
  - `all_registered = 30`

## 3. Files to Add

- `tests/test_mock_world_scenario_coverage_closure.py` - focused closure regression that ties together Mock World profile loadability, benchmark representation, suite/matrix parity, and planning-review readiness.
- `docs/specs/125-mock-world-scenario-coverage-closure-v0.md` - task spec created from the approved content.
- `docs/plans/125-mock-world-scenario-coverage-closure-v0-plan.md` - implementation plan created from the approved content.

## 4. Files to Modify

- `tests/test_mock_world_scenario_taxonomy.py` - modify only if the new closure test would duplicate existing assertions and a small shared constant/helper reduces drift.
- `README.md` - update current-state wording only if it still implies Mock World is family-only.
- `docs/WEB_DEMO_README.md` - update current-state wording only if it still implies Mock World is family-only or omits the current public/benchmark distinction.
- `docs/COMPETITION_DESIGN_DOCUMENT.md` - update only if it presents current capability as family-only rather than historical MVP context.
- `docs/submission/EVIDENCE_MAP.md` or `docs/submission/DEMO_SCRIPT.md` - update only if current reviewer-facing wording contradicts multi-scenario Mock World coverage.

Do not modify production code unless a focused test proves an actual loader, matrix, suite, or demo planning regression.

## 5. Implementation Steps

1. Confirm baseline state before editing.
   - Run `git status --short`.
   - Run `git branch --show-current`.
   - Run `git log --oneline -5`.
   - Confirm Task `124` is the latest tracked task and unrelated untracked docs remain unstaged.

2. Inspect the existing source of truth.
   - Read `backend/app/providers/mock_world/loader.py`.
   - Read `backend/app/benchmark/case_matrix.py`.
   - Read `backend/app/benchmark/fixtures.py`.
   - Read `backend/app/benchmark/suites.py`.
   - Read `backend/app/benchmark/matrix.py`.
   - Read current focused tests:
     - `tests/test_mock_world_scenario_taxonomy.py`
     - `tests/test_benchmark_case_matrix_generation.py`
     - `tests/test_benchmark_suites.py`
     - `tests/test_benchmark_harness.py`

3. Identify the current demo planning entrypoint for reviewable plan readiness.
   - Inspect `backend/app/demo/` modules and existing tests that create demo runs.
   - Prefer an existing in-process service/helper used by current tests.
   - If only API-level coverage exists, use the current test client pattern rather than starting uvicorn.
   - Do not invent a new public API just for this task.

4. Create the focused closure regression file.
   - Add `tests/test_mock_world_scenario_coverage_closure.py`.
   - Define local constants:
     - `SUPPORTED_MOCK_WORLD_PROFILES`
     - `EXPECTED_CORE_SUITE_COUNTS`
   - Add `test_all_supported_mock_world_profiles_load`.
     - For each supported profile, call `load_mock_world(profile)`.
     - Assert the returned profile equals the requested profile.
   - Add `test_all_supported_profiles_have_registered_benchmark_representation`.
     - Load `load_registered_benchmark_cases()`.
     - Build counts by `case.world_profile`.
     - Assert every supported profile has at least one registered case.
     - Assert the expected all-registered distribution remains:
       - `family_afternoon = 16`
       - `friends_gathering = 3`
       - `solo_afternoon = 2`
       - `couple_afternoon = 1`
       - `rainy_day_fallback = 3`
       - `budget_lite = 3`
       - `elder_afternoon = 2`
   - Add `test_case_matrix_suite_and_loaded_suite_counts_stay_aligned`.
     - Build `build_benchmark_case_matrix_manifest()`.
     - Compare manifest counts against `load_benchmark_suite()` counts for `default`, `expanded`, `recovery_focused`, `v2_integrity`, and `all_registered`.
     - Assert `registered_case_count == 30`.
   - Add `test_suite_descriptions_expose_multi_scenario_world_profile_summary`.
     - Use `list_benchmark_suites()`.
     - Assert `all_registered.matrix_summary.world_profile_counts` equals the current seven-profile distribution.
     - Assert `v2_integrity.matrix_summary.world_profile_counts` includes non-family profiles: `friends_gathering`, `solo_afternoon`, `rainy_day_fallback`, `budget_lite`, and `elder_afternoon`.
   - Add `test_public_mock_world_profiles_reach_reviewable_planning_state`.
     - Use the existing demo/backend test helper or API test client found in Step 3.
     - Cover current public scenario profiles, not benchmark-only profiles unless the current public API already accepts arbitrary `mock_world_profile`.
     - Assert each run reaches the existing reviewed/planning-ready status used by current tests.
     - Assert no write action is executed before confirmation.

5. Run the new focused test alone.
   - Run `python -m pytest tests/test_mock_world_scenario_coverage_closure.py -q`.
   - If it fails because the chosen demo test helper is wrong, adjust the test to use the established current helper.
   - If it fails because a real profile/suite/matrix drift exists, fix the nearest source of truth and keep the fix minimal.

6. Run existing benchmark and taxonomy tests.
   - Run:
     - `python -m pytest tests/test_mock_world_scenario_taxonomy.py tests/test_benchmark_case_matrix_generation.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q`
   - Do not update expected counts unless the source-of-truth inspection proves the canonical inventory intentionally changed.

7. Check docs for current-state family-only wording.
   - Run:
     - `rg -n "family-only|only family|只支持亲子|只覆盖亲子|五个默认 Mock World 家庭场景|默认 Mock World 家庭场景" README.md docs`
   - Review every hit.
   - Leave historical MVP statements intact if clearly historical.
   - Update current-state statements that imply today’s Mock World or benchmark only covers family scenarios.
   - Keep wording precise:
     - public demo currently exposes the existing public scenario set
     - benchmark inventory also includes `elder_afternoon`
     - Mock World is the formal benchmark base
     - AMap remains API-only/read-only preview and not formal benchmark dependency

8. Run matrix/export smoke.
   - Run:
     - `python scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json`
   - Confirm output parses and reports:
     - `registered_case_count = 30`
     - `selected_suite_id = "all_registered"`
     - `len(cases) = 30`

9. Run formal benchmark smoke commands.
   - Run:
     - `python scripts/run_benchmark_coverage_gate.py`
     - `python scripts/run_formal_verification.py`
   - If these refresh local `var/` artifacts, do not stage generated artifacts unless they are already tracked and intentionally changed.
   - If either command fails due to environment-only issues, record the exact failure and still run all focused pytest commands.

10. Run hygiene checks.
    - Run:
      - `git diff --check`
      - `git status --short`
    - Confirm only Task 125 spec/plan, the new or updated focused test, and necessary docs are changed.
    - Confirm unrelated untracked files remain unstaged.

11. Stage and commit.
    - Stage only relevant files:
      - `docs/specs/125-mock-world-scenario-coverage-closure-v0.md`
      - `docs/plans/125-mock-world-scenario-coverage-closure-v0-plan.md`
      - `tests/test_mock_world_scenario_coverage_closure.py`
      - any intentionally updated docs
      - any intentionally updated existing focused test
    - Run `git diff --cached --check`.
    - Commit with `test: lock mock world scenario coverage closure`.

12. Push.
    - Push the task branch.
    - If still on the Task 124 branch, create/switch to the task branch before committing:
      - `git switch -c codex/125-mock-world-scenario-coverage-closure-v0`
    - Push with:
      - `git push -u origin codex/125-mock-world-scenario-coverage-closure-v0`

## 6. Testing Plan

- Unit tests:
  - `tests/test_mock_world_scenario_coverage_closure.py::test_all_supported_mock_world_profiles_load`
  - `tests/test_mock_world_scenario_coverage_closure.py::test_all_supported_profiles_have_registered_benchmark_representation`
  - `tests/test_mock_world_scenario_coverage_closure.py::test_case_matrix_suite_and_loaded_suite_counts_stay_aligned`
  - `tests/test_mock_world_scenario_coverage_closure.py::test_suite_descriptions_expose_multi_scenario_world_profile_summary`
  - `tests/test_mock_world_scenario_coverage_closure.py::test_public_mock_world_profiles_reach_reviewable_planning_state`

- Existing regression tests:
  - `tests/test_mock_world_scenario_taxonomy.py`
  - `tests/test_benchmark_case_matrix_generation.py`
  - `tests/test_benchmark_suites.py`
  - `tests/test_benchmark_harness.py`

- Script smoke tests:
  - `scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json`
  - `scripts/run_benchmark_coverage_gate.py`
  - `scripts/run_formal_verification.py`

- Documentation checks:
  - Search for current-state family-only wording.
  - Verify docs distinguish public demo scenario chips from full benchmark profile coverage.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_mock_world_scenario_coverage_closure.py -q
python -m pytest tests/test_mock_world_scenario_taxonomy.py tests/test_benchmark_case_matrix_generation.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
python scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json
python scripts/run_benchmark_coverage_gate.py
python scripts/run_formal_verification.py
rg -n "family-only|only family|只支持亲子|只覆盖亲子|五个默认 Mock World 家庭场景|默认 Mock World 家庭场景" README.md docs
git diff --check
git status --short
```

Commands to run after staging:

```bash
git diff --cached --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
test: lock mock world scenario coverage closure
```

Expected commands:

```bash
git status --short
git switch -c codex/125-mock-world-scenario-coverage-closure-v0
git add docs/specs/125-mock-world-scenario-coverage-closure-v0.md docs/plans/125-mock-world-scenario-coverage-closure-v0-plan.md
git add tests/test_mock_world_scenario_coverage_closure.py
git add tests/test_mock_world_scenario_taxonomy.py README.md docs/WEB_DEMO_README.md docs/COMPETITION_DESIGN_DOCUMENT.md docs/submission/EVIDENCE_MAP.md docs/submission/DEMO_SCRIPT.md
git diff --cached --check
git commit -m "test: lock mock world scenario coverage closure"
git push -u origin codex/125-mock-world-scenario-coverage-closure-v0
```

Only stage existing docs/tests that actually changed. Do not stage unrelated untracked local files or generated `var/` artifacts.

## 9. Out-of-scope Changes

- Do not add new profiles or benchmark cases.
- Do not add a new public scenario chip.
- Do not change suite membership unless current implementation is inconsistent with `case_matrix.py`.
- Do not change benchmark gate thresholds or report schemas.
- Do not change public API contracts.
- Do not change AMap preview behavior.
- Do not change memory governance, recovery routing, execution safety, Action Ledger, or confirmation behavior.
- Do not run formatters that rewrite unrelated files.
- Do not commit generated benchmark artifacts, caches, `.env`, credentials, or secrets.
- Do not stage:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/125-mock-world-scenario-coverage-closure-v0.md`.
- [ ] The task stayed a closure/regression slice and did not become a scenario expansion.
- [ ] All seven canonical Mock World profiles load.
- [ ] Every canonical Mock World profile has registered benchmark representation.
- [ ] Public Mock World profiles can reach reviewable planning state.
- [ ] No write action occurs before confirmation in the planning-readiness regression.
- [ ] Suite counts remain `default=11`, `expanded=5`, `recovery_focused=8`, `v2_integrity=20`, `all_registered=30`.
- [ ] Matrix manifest and loaded suites agree.
- [ ] Docs no longer imply current Mock World support is family-only.
- [ ] Historical MVP family-scenario wording remains accurate where clearly historical.
- [ ] Required pytest and script verification commands passed or blockers were explicitly reported.
- [ ] `git diff --check` passed.
- [ ] `git diff --cached --check` passed before commit.
- [ ] No generated `var/` artifacts were committed.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] Unrelated untracked docs remained untouched.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.

## 11. Handoff Notes

After finishing, report back:

- changed files
- whether any production code changed, or whether the task was tests/docs only
- final confirmed profile distribution for `all_registered`
- final confirmed suite counts
- verification commands and results
- whether `python scripts/run_benchmark_coverage_gate.py` and `python scripts/run_formal_verification.py` passed or had environment blockers
- commit hash
- push result
- confirmation that unrelated untracked local files were not staged
- any recommended next task, likely Task `126 Conversation and plan versioning closure`
