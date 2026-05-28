# Plan: 074 Benchmark Matrix Coverage Threshold v0

## 1. Spec Reference

Spec file:

```text
docs/specs/074-benchmark-matrix-coverage-threshold-v0.md
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

- Current branch is `codex/benchmark-robustness-cases-v0`.
- Latest numbered task on disk is `073`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `073`.
- Latest commit is:

  ```text
  d2b35ae feat: add benchmark robustness cases
  ```

- That latest commit matches the latest task on disk:
  - `073-benchmark-robustness-cases-v0`
- During planning on 2026-05-28, these focused benchmark-related checks passed:
  - `python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q`
  - `python -m pytest tests/test_benchmark_release_gate.py -q`
- Current workspace still has unrelated dirty files that must remain unstaged throughout this task:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `docs/artifacts/`
  - `qc`
- Current benchmark state already includes:
  - `all_registered = 21` cases
  - `release_gate_v1 = 15` cases
  - `release_gate_v1` blocking checks for:
    - exact suite membership
    - exact `level_counts`
    - exact `tool_profile_counts`
    - exact `failure_mode_counts`
    - latency SLO
- Current repository does **not** yet block on:
  - scenario-bucket diversity across `all_registered`
  - world-profile diversity across `all_registered`
  - failure-mode balance across `all_registered`
  - selected constraint-tag coverage across `all_registered`
- This task should therefore add a separate V1.5 coverage gate instead of modifying the existing V1 release gate semantics.

## 3. Files to Add

- `backend/app/benchmark/coverage_gate.py` - V1.5 coverage-gate orchestration, threshold evaluation helpers, report enrichment, latest-pass alias refresh, CLI `main(...)`.
- `scripts/run_benchmark_coverage_gate.py` - repo-root CLI wrapper for the new coverage gate.
- `tests/test_benchmark_coverage_gate.py` - focused unit tests for the new gate pass/fail paths, alias behavior, and CLI exit codes.
- `tests/integration/test_benchmark_coverage_gate.py` - real integration test that runs the new gate against `all_registered` with PostgreSQL/Redis and a temporary output root.

## 4. Files to Modify

- `README.md` - document `coverage_gate_v1_5`, the exact thresholds, the command, and the separate latest-pass alias.

## 5. Implementation Steps

1. Lock the threshold policy before writing the runner.
   In `tests/test_benchmark_coverage_gate.py`, define the exact threshold constants from the spec:
   - scenario minimums
   - `family` max share
   - world-profile minimums
   - `family_afternoon` max share
   - failure-mode minimums
   - `none` max share
   - required constraint-tag minimums
   This keeps the implementation from drifting into “close enough” policy.

2. Write the first failing unit test for the green path.
   Build a fake `FormalVerificationResult` and a fake `suite-all_registered-run-report.json` payload that includes:
   - `benchmark_summary.matrix_summary`
   - `benchmark_summary.outcome_rollup.constraint_tag_outcomes`
   - the current passing 21-case counts from the spec
   Assert that:
   - `run_benchmark_coverage_gate(...)` returns `release_blocked == False`
   - the unique report is enriched with `coverage_gate_evaluation`
   - `latest-coverage_gate_v1_5-run-report.json` is refreshed
   - the refreshed alias equals the enriched unique report byte-for-byte

3. Add failing unit tests for each blocking rule family.
   Write focused test cases for:
   - scenario minimum miss
   - `family` share breach
   - world-profile minimum miss
   - `family_afternoon` share breach
   - failure-mode minimum miss
   - `none` share breach
   - constraint-tag minimum miss
   - missing `matrix_summary`
   - missing `outcome_rollup`
   - missing `constraint_tag_outcomes`
   - missing required bucket keys
   - blocked run preserves prior latest coverage alias
   Keep each test isolated to one failure reason.

4. Implement the new module skeleton.
   In `backend/app/benchmark/coverage_gate.py`, add:
   - `COVERAGE_GATE_ID = "coverage_gate_v1_5"`
   - `COVERAGE_SUITE_ID = "all_registered"`
   - `LATEST_REPORT_FILENAME = "latest-coverage_gate_v1_5-run-report.json"`
   - a frozen dataclass `BenchmarkCoverageGateResult`
   - a top-level function:
     - `run_benchmark_coverage_gate(output_root: Path | str | None = None, *, start_services: bool = True, timeout_seconds: float = 60.0, poll_interval_seconds: float = 1.0) -> BenchmarkCoverageGateResult`
   - a `main() -> int` CLI adapter

5. Reuse formal verification instead of duplicating suite execution logic.
   Inside `run_benchmark_coverage_gate(...)`:
   - call `run_formal_verification(...)`
   - use its returned:
     - `suite_id`
     - `run_status`
     - `case_count`
     - `passed_count`
     - `failed_count`
     - `error_count`
     - `overall_score`
     - `run_directory`
     - `suite_report_path`
     - `latest_report_path`
   Do not reimplement PostgreSQL/Redis bootstrapping or rerun the harness directly in this task.

6. Load and validate the fresh suite report payload.
   After `run_formal_verification(...)` succeeds:
   - read the returned `suite_report_path`
   - parse it as JSON
   - validate it through `BenchmarkRunReport.model_validate(...)` or an equally strict typed path
   - fail immediately if:
     - the report cannot be read
     - the report is malformed
     - `benchmark_summary` is missing
     - `matrix_summary` is missing
     - `outcome_rollup` is missing
     - `constraint_tag_outcomes` is missing

7. Implement deterministic extraction helpers.
   Add small internal helpers that extract:
   - `scenario_bucket_counts` from `benchmark_summary.matrix_summary`
   - `world_profile_counts` from `benchmark_summary.matrix_summary`
   - `failure_mode_counts` from `benchmark_summary.matrix_summary`
   - `constraint_tag_case_counts` from `benchmark_summary.outcome_rollup.constraint_tag_outcomes[*].case_count`
   Keep them read-only and deterministic. Do not modify report schemas or benchmark runtime code.

8. Implement threshold evaluation helpers.
   Add helpers that:
   - check minimum-count rules for each bucket map
   - compute ratio checks using `round(observed / case_count, 4)`
   - return deterministic failure messages
   Recommended internal split:
   - `_evaluate_minimums(...)`
   - `_evaluate_share_cap(...)`
   - `_required_case_count_failure(...)`
   - `_coerce_case_count_from_outcome_rollup(...)`
   Use the exact thresholds from the spec and avoid deriving them from the current report dynamically.

9. Build the additive evaluation payload.
   Implement `_build_coverage_gate_evaluation(...)` returning:
   - `schema_version`
   - `gate_id`
   - `suite_id`
   - `release_blocked`
   - `blocking_failures`
   - `coverage_thresholds`
   - `observed_coverage`
   - `share_checks`
   Ensure:
   - the threshold block contains the exact configured constants
   - the observed block contains only aggregated counts
   - the three share checks include `observed_ratio`, `max_ratio`, and `status`

10. Enrich the unique suite report in place.
    Add a helper like `_write_coverage_gate_evaluation(suite_report_path, evaluation_payload)` that:
    - reads the current report JSON
    - injects top-level `coverage_gate_evaluation`
    - rewrites the file atomically through a `*.tmp` file
    - preserves UTF-8 and sorted-key deterministic output
    If enrichment fails, the gate must fail.

11. Refresh the latest-pass alias only when coverage passes.
    Add a helper like `_refresh_latest_alias(...)` that copies the enriched unique suite report to:
    - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
    Only call it when `blocking_failures` is empty.
    On blocked runs:
    - keep the unique report
    - keep the prior latest coverage alias untouched

12. Implement human-readable CLI summaries.
    `main()` should:
    - return `0` on pass
    - return `1` on blocked or failed evaluation
    Print at least:
    - gate ID
    - suite ID
    - case count / passed / failed / error
    - overall score
    - `family` share
    - `family_afternoon` share
    - `none` share
    - run directory
    - unique suite report path
    - latest coverage alias path
    On blocked runs, also print each blocking failure as a flat bullet line.

13. Add the repo-root script wrapper.
    Create `scripts/run_benchmark_coverage_gate.py` exactly like the existing runner wrappers:
    - add repo root to `sys.path`
    - import `backend.app.benchmark.coverage_gate.main`
    - `raise SystemExit(main())`

14. Add the unit tests for CLI behavior.
    In `tests/test_benchmark_coverage_gate.py`, add tests that:
    - `main()` returns `0` and prints the success summary when the gate passes
    - `main()` returns `1` and prints blocking failures when the gate is blocked
    - `main()` returns `1` when `run_formal_verification(...)` raises an error
    Keep the pattern aligned with `tests/test_formal_verification.py` and `tests/test_benchmark_release_gate.py`.

15. Add the real integration test.
    In `tests/integration/test_benchmark_coverage_gate.py`:
    - call `run_benchmark_coverage_gate(output_root=<temp>, start_services=False)`
    - assert:
      - `gate_id == "coverage_gate_v1_5"`
      - `suite_id == "all_registered"`
      - `release_blocked is False`
      - `case_count == 21`
      - `failed_count == 0`
      - `error_count == 0`
      - the unique report exists
      - the latest coverage alias exists
      - `coverage_gate_evaluation` exists in both files
      - observed scenario/world/failure/tag counts match the spec exactly
      - `family_scenario_share.observed_ratio == 0.5238`
      - `family_afternoon_world_profile_share.observed_ratio == 0.5238`
      - `non_failure_share.observed_ratio == 0.8571`
      - latest coverage alias bytes equal the enriched unique report bytes
      - forbidden sensitive strings are absent from the serialized JSON

16. Update the README only where release governance is documented.
    Add a new section, e.g. `Benchmark Coverage Gate`, that explains:
    - `release_gate_v1` is still the V1 blocking quality/latency gate
    - `run_formal_verification.py` is still the broader full-inventory engineering run
    - `coverage_gate_v1_5` is the new broader-inventory coverage blocker
    - the exact thresholds
    - the exact command
    - the exact latest coverage alias path
    Do not rewrite unrelated README sections.

17. Keep unrelated local files untouched.
    Do not stage:
    - `.gitignore`
    - `docs/COMPETITION_SUBMISSION_DESIGN.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/V1_DEVELOPMENT_REPORT.md`
    - `docs/artifacts/`
    - `qc`
    - generated `var/` output files outside what is intentionally used for verification

18. Run verification in this order.
    1. `python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_formal_verification.py tests/test_benchmark_coverage_gate.py -q`
    2. `docker compose up -d postgres redis`
    3. `python -m alembic upgrade head`
    4. `python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_coverage_gate.py -k "all_registered or coverage_gate" -v`
    5. `python scripts/run_benchmark_coverage_gate.py`
    6. `git diff --check`
    7. `git status --short`

19. Branch and stage carefully.
    Because the current workspace is still on the `073` task branch and has unrelated dirty files, start from a clean base that already contains `d2b35ae`.
    Preferred flow:
    - use a fresh worktree or a clean branch base
    - create `codex/benchmark-matrix-coverage-threshold-v0`
    - stage only files from this task

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_coverage_gate.py`
    - pass path creates enriched report and latest coverage alias
    - scenario minimum miss blocks
    - `family` share breach blocks
    - world-profile minimum miss blocks
    - `family_afternoon` share breach blocks
    - failure-mode minimum miss blocks
    - `none` share breach blocks
    - constraint-tag minimum miss blocks
    - missing `matrix_summary` blocks
    - missing `constraint_tag_outcomes` blocks
    - blocked run preserves previous latest coverage alias
    - `main()` exit codes and summaries are correct
  - `tests/test_formal_verification.py`
    - regression check remains green because the new gate reuses it
  - `tests/test_benchmark_suites.py`
    - current `all_registered` constants stay aligned with the coverage floor assumptions
  - `tests/test_benchmark_harness.py`
    - current `all_registered` matrix and outcome-rollup counts remain aligned with the coverage floor assumptions

- Integration tests:
  - `tests/integration/test_benchmark_coverage_gate.py`
    - real `all_registered` run through the new gate
    - enriched report and latest alias assertions
    - exact observed counts and share ratios
  - `tests/integration/test_benchmark_harness_gateway.py`
    - regression evidence for current `all_registered` suite composition and counts

- Smoke tests:
  - `python scripts/run_benchmark_coverage_gate.py`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_formal_verification.py tests/test_benchmark_coverage_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_coverage_gate.py -k "all_registered or coverage_gate" -v
python scripts/run_benchmark_coverage_gate.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark matrix coverage threshold
```

Expected commands:

```bash
git status --short
git branch --show-current
git log --oneline -n 1
git switch -c codex/benchmark-matrix-coverage-threshold-v0
git add backend/app/benchmark/coverage_gate.py
git add scripts/run_benchmark_coverage_gate.py
git add tests/test_benchmark_coverage_gate.py
git add tests/integration/test_benchmark_coverage_gate.py
git add README.md
git diff --cached --check
git commit -m "feat: add benchmark matrix coverage threshold"
git push -u origin codex/benchmark-matrix-coverage-threshold-v0
```

The implementer must confirm that:
- the branch base already contains `d2b35ae` or the merge commit that brought it in
- `.env`, secrets, unrelated docs, `qc`, and non-task `var/` outputs are not staged

## 9. Out-of-scope Changes

- Do not change `release_gate_v1` suite membership or thresholds.
- Do not change `all_registered` suite membership or case order.
- Do not add new benchmark cases or suites.
- Do not modify `backend/app/benchmark/matrix.py`, `backend/app/benchmark/rollups.py`, `backend/app/benchmark/harness.py`, or Mock World fixture payloads unless a focused failing test proves it is strictly necessary. The default expectation is that this task is additive and read-only with respect to benchmark generation.
- Do not alter workflow, planner, provider, recovery, or frontend behavior.
- Do not add internal observability API or UI changes.
- Do not add a generic policy engine or external configuration file for thresholds.
- Do not commit generated caches, virtual environments, secrets, or unrelated local artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `coverage_gate_v1_5` is a separate gate from `release_gate_v1`.
- [ ] The gate evaluates `all_registered`, not `release_gate_v1`.
- [ ] The exact scenario, world-profile, failure-mode, and constraint-tag thresholds match the spec.
- [ ] The exact concentration caps match the spec.
- [ ] The unique `suite-all_registered-run-report.json` is enriched with `coverage_gate_evaluation`.
- [ ] A passing run refreshes `latest-coverage_gate_v1_5-run-report.json`.
- [ ] A blocked run does not overwrite the prior latest coverage alias.
- [ ] `run_formal_verification.py` behavior remains unchanged.
- [ ] `run_benchmark_release_gate.py` behavior remains unchanged.
- [ ] Required tests and smoke commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- The final `coverage_gate_v1_5` threshold constants as implemented
- The final observed `all_registered` counts:
  - `scenario_bucket_counts`
  - `world_profile_counts`
  - `failure_mode_counts`
  - `constraint_tag_case_counts`
- The final observed share ratios:
  - `family`
  - `family_afternoon`
  - `none`
- Verification commands and results
- Coverage-gate script output summary
- Unique report path
- Latest coverage alias path
- Commit hash
- Push result
- Known limitations or follow-up tasks:
  - thresholds are intentionally tied to the current 21-case floor
  - `elder` coverage is still out of scope until such cases exist
