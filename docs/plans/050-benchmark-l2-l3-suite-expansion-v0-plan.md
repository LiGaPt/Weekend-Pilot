# Plan: 050 Benchmark L2/L3 Suite Expansion v0

## 1. Spec Reference

Spec file:

```text
docs/specs/050-benchmark-l2-l3-suite-expansion-v0.md
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

- Current working branch is `codex/mock-world-scenario-pack-expansion-v1`.
- Latest code commit is `36aee8a feat: expand mock world scenario pack`.
- The benchmark inventory already contains `11` registered cases:
  - `6` legacy non-failure baseline cases
  - `4` new scenario-pack cases added by Task `049`
  - `1` recovery/failure case
- Current suite catalog exposes only `default`, `failures`, and `all_registered`.
- Current suite reports expose `matrix_summary` coverage counts but do not expose direct per-dimension pass-rate rollups.
- `docs/specs` and `docs/plans` are continuous and matched on disk through `049`.
- Only `048` docs are tracked in git; local `047` and `049` docs are currently untracked.
- Focused benchmark verification already passes at the current baseline:
  - `python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_mock_world_loader.py -q` -> `57 passed`
  - `python -m pytest tests/integration/test_benchmark_harness_gateway.py -q` -> `6 passed`
- Unrelated local paths must stay unstaged throughout execution:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/specs/047-memory-query-policy-baseline-v0.md`
  - `docs/plans/047-memory-query-policy-baseline-v0-plan.md`
  - `docs/specs/049-mock-world-scenario-pack-expansion-v1.md`
  - `docs/plans/049-mock-world-scenario-pack-expansion-v1-plan.md`
  - `qc`
  - `var/`

## 3. Files to Add

- `backend/app/benchmark/rollups.py` - deterministic helper module that builds suite outcome rollups by scenario bucket, constraint tag, and failure mode from benchmark results.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add additive outcome-rollup models and additive `BenchmarkSummary` fields for `suite_id`, `suite_title`, and `outcome_rollup`.
- `backend/app/benchmark/suites.py` - define canonical `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered` suite catalog entries; keep `failures` as a compatibility alias; update per-case suite membership behavior.
- `backend/app/benchmark/harness.py` - add `run_suite(...)`, normalize suite metadata, attach outcome rollups to suite summaries, and write suite-specific report filenames.
- `tests/test_benchmark_suites.py` - replace three-suite expectations with canonical five-suite expectations, alias checks, exact suite memberships, and updated case-to-suite mappings.
- `tests/test_benchmark_harness.py` - add unit coverage for additive summary schemas, outcome-rollup builders, canonical suite filenames, and canonical suite pass-rate summaries.
- `tests/integration/test_benchmark_harness_gateway.py` - add gateway-backed canonical suite execution coverage for `baseline`, `expanded`, `recovery_focused`, and `all_registered`.
- `tests/test_observability.py` - update expected `registered_suite_ids` arrays to canonical suite memberships.
- `tests/integration/test_observability_gateway.py` - update benchmark artifact membership assertions to canonical suite memberships.
- `README.md` - document canonical suites, the `failures -> recovery_focused` compatibility behavior, and suite report rollups.

## 5. Implementation Steps

1. Create the new rollup helper module.
   Add `backend/app/benchmark/rollups.py` with one deterministic builder that consumes `BenchmarkCaseResult` values and produces additive outcome rollups.
   The helper must:
   - count by `taxonomy.scenario_bucket`
   - count by constraint-tag dimension using current `taxonomy.tags`
   - exclude `baseline`, `failure_injected`, and `route_failure` from the constraint-tag rollup
   - count by `taxonomy.failure_mode or "none"`
   - compute `case_count`, `passed_count`, `failed_count`, `error_count`, and `pass_rate`
   - sort all emitted dictionaries deterministically by key
   - count each tag at most once per case

2. Extend benchmark schemas without breaking current report readers.
   In `backend/app/benchmark/schemas.py`, add:
   - one model for per-bucket outcome stats
   - one model for the additive suite outcome-rollup summary
   - additive `suite_id`, `suite_title`, and `outcome_rollup` fields on `BenchmarkSummary`
   Keep all current existing fields unchanged and keep all new fields optional/additive where needed for backward compatibility.

3. Expand the suite catalog into canonical suite families.
   In `backend/app/benchmark/suites.py`:
   - define canonical suite IDs in this exact order: `baseline`, `expanded`, `recovery_focused`, `default`, `all_registered`
   - keep `load_benchmark_suite("failures")` as a string alias to the canonical `recovery_focused` suite
   - keep `load_default_benchmark_cases()` delegating to `default`
   - change `load_failure_benchmark_cases()` to delegate to `recovery_focused`
   - define exact case lists:
     - `baseline` = first six non-failure legacy cases
     - `expanded` = `couple_afternoon_v1`, `friends_gathering_v1`, `rainy_day_fallback_v1`, `budget_lite_v1`
     - `recovery_focused` = `family_route_failure_v1`
     - `default` = `baseline + expanded`
     - `all_registered` = `default + recovery_focused`
   - update `list_benchmark_suite_ids_for_case(...)` so canonical memberships are:
     - baseline cases -> `baseline`, `default`, `all_registered`
     - expanded cases -> `expanded`, `default`, `all_registered`
     - recovery case -> `recovery_focused`, `all_registered`
   - do not return the alias suite ID `failures` from `list_benchmark_suites()` or from `list_benchmark_suite_ids_for_case(...)`

4. Add first-class suite execution to the harness.
   In `backend/app/benchmark/harness.py`:
   - add `run_suite(suite_id)` as the preferred named-suite execution entry point
   - normalize alias input `failures` to canonical suite ID `recovery_focused`
   - load cases via `load_benchmark_suite(...)`
   - attach canonical `suite_id` and `suite_title` into the emitted `BenchmarkSummary`
   - build `outcome_rollup` from result statuses plus taxonomies
   - keep `run_cases(cases)` working for ad hoc case lists
   - keep `run_cases(cases)` writing `run-report.json`
   - make `run_suite(suite_id)` write `suite-<canonical-suite-id>-run-report.json`
   - preserve current `matrix_summary` behavior and current benchmark result semantics

5. Lock exact expected suite counts into unit tests.
   In `tests/test_benchmark_suites.py`:
   - replace current three-suite ordering expectations with five canonical suites
   - assert exact case orders for `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered`
   - assert that `load_benchmark_suite("failures")` equals `load_benchmark_suite("recovery_focused")`
   - assert exact canonical case-to-suite memberships
   - assert exact matrix summaries for `baseline`, `expanded`, and `recovery_focused`
   - re-assert current exact `default` and `all_registered` matrix counts

6. Add unit coverage for report rollups and filenames.
   In `tests/test_benchmark_harness.py`:
   - add deterministic checks for the new rollup builder using current suite fixtures
   - assert exact scenario-bucket outcome rollups for `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered`
   - assert exact failure-mode outcome rollups, especially `route_unavailable` for `recovery_focused`
   - assert selected exact constraint-tag outcome counts:
     - `baseline.child_friendly == 5`
     - `expanded.budget_limited == 1`
     - `recovery_focused.light_meal == 1`
     - `default.citywalk == 2`
     - `all_registered.light_meal == 6`
   - assert `pass_rate == 1.0` for every emitted rollup bucket in the current green fixture set
   - assert `run_suite("baseline")` writes `suite-baseline-run-report.json`
   - assert `run_suite("expanded")` writes `suite-expanded-run-report.json`
   - assert `run_suite("recovery_focused")` writes `suite-recovery_focused-run-report.json`
   - keep current `run_cases(...)` report-filename behavior unchanged

7. Add gateway-backed integration coverage for the canonical suites.
   In `tests/integration/test_benchmark_harness_gateway.py`:
   - add suite-run tests for `baseline`, `expanded`, and `recovery_focused`
   - keep the current `all_registered` suite integration assertion
   - assert exact case counts `6`, `4`, `1`, and `11`
   - assert `report.benchmark_summary.suite_id` is canonical
   - assert serialized suite report filenames match the canonical suite name
   - assert exact scenario-bucket and failure-mode outcome rollups in the serialized report payloads
   - keep current recovery-case workflow expectations unchanged

8. Update observability expectations, not observability surface area.
   In `tests/test_observability.py` and `tests/integration/test_observability_gateway.py`:
   - update benchmark artifact summary expectations so `registered_suite_ids` use canonical suite membership values
   - for `solo_afternoon_v1`, expect `["baseline", "default", "all_registered"]`
   - for `family_route_failure_v1`, expect `["recovery_focused", "all_registered"]`
   - do not add new observability fields or routes

9. Update the README last.
   In `README.md`:
   - replace the current three-suite description with the canonical five-suite description
   - explain the intent of `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered`
   - document that `load_failure_benchmark_cases()` now points to the canonical recovery suite
   - mention that `load_benchmark_suite("failures")` still works as a compatibility alias
   - document that named suite runs write `suite-<suite_id>-run-report.json`
   - document that suite reports now include additive coverage/pass-rate rollups by scenario family, constraint tag, and failure mode

10. Re-run focused checks and keep staging clean.
    Before staging:
    - confirm `git status --short` still shows the pre-existing unrelated untracked files and nothing new outside task scope
    - confirm only benchmark/README files for Task `050` are staged
    - confirm `docs/specs/047...`, `docs/plans/047...`, `docs/specs/049...`, `docs/plans/049...`, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, and `var/` stay unstaged

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_suites.py` for canonical suite order, alias behavior, exact membership, and exact matrix counts
  - `tests/test_benchmark_harness.py` for rollup builder correctness, suite-specific filenames, and additive summary schema coverage
  - `tests/test_observability.py` for canonical `registered_suite_ids` membership expectations
- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py` for `baseline`, `expanded`, `recovery_focused`, and `all_registered` suite execution and serialized report assertions
  - `tests/integration/test_observability_gateway.py` for canonical suite memberships in benchmark artifact summaries
- Smoke checks:
  - `git diff --check`
  - `git status --short`
- Explicit non-tests:
  - no new frontend feature tests
  - no new replay tests
  - no new workflow-route tests
  - no new migration tests

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_observability_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark suite coverage rollups
```

Expected commands:

```bash
git status --short
git switch -c codex/benchmark-l2-l3-suite-expansion-v0
git add backend/app/benchmark/rollups.py
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/suites.py
git add backend/app/benchmark/harness.py
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/integration/test_benchmark_harness_gateway.py
git add tests/test_observability.py
git add tests/integration/test_observability_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: add benchmark suite coverage rollups"
git push -u origin codex/benchmark-l2-l3-suite-expansion-v0
```

The implementer must confirm that `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/specs/047-memory-query-policy-baseline-v0.md`, `docs/plans/047-memory-query-policy-baseline-v0-plan.md`, `docs/specs/049-mock-world-scenario-pack-expansion-v1.md`, `docs/plans/049-mock-world-scenario-pack-expansion-v1-plan.md`, `qc`, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not add any new benchmark case JSON fixture.
- Do not add any new world profile or failure profile.
- Do not implement genuine multi-turn L3 benchmark orchestration in this task.
- Do not change workflow routing, planner behavior, recovery behavior, or Tool Gateway behavior.
- Do not change replay semantics.
- Do not add new HTTP routes, CLI commands, or frontend controls.
- Do not add new dependencies or migrations.
- Do not edit unrelated docs or local runtime artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/050-benchmark-l2-l3-suite-expansion-v0.md`.
- [ ] The canonical suite catalog now exposes `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered` in the right order.
- [ ] The `failures` alias still loads and normalizes to the canonical `recovery_focused` suite.
- [ ] Case-to-suite memberships match the spec exactly.
- [ ] `baseline`, `expanded`, and `recovery_focused` matrix summaries match the exact counts in the spec.
- [ ] `default` and `all_registered` matrix summaries remain unchanged from Task `049`.
- [ ] Suite reports include additive `suite_id`, `suite_title`, and `outcome_rollup`.
- [ ] `run_suite("baseline")`, `run_suite("expanded")`, and `run_suite("recovery_focused")` write the correct suite-specific filenames.
- [ ] Outcome rollups show direct coverage/pass-rate summaries by scenario family, constraint tag, and failure mode.
- [ ] The recovery-focused suite still passes as a benchmark even though its workflow status remains `failed`.
- [ ] Internal observability benchmark artifact summaries show canonical suite memberships.
- [ ] Required verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, unrelated local doc draft, or runtime artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final canonical case lists for `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered`.
- The exact serialized report filenames produced by `run_suite(...)`.
- The exact scenario-bucket outcome rollups for `baseline`, `expanded`, `recovery_focused`, and `all_registered`.
- The exact `registered_suite_ids` arrays observed for `solo_afternoon_v1` and `family_route_failure_v1`.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that the unrelated untracked `047` and `049` docs and other local files remained unstaged.
- The follow-up recommendation that true multi-turn L3 benchmark case authoring should remain a separate task after this suite/report layer lands cleanly.
