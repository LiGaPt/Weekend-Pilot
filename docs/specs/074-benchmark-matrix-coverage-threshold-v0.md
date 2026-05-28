# Spec: 074 Benchmark Matrix Coverage Threshold v0

## 1. Goal

WeekendPilot now has enough benchmark structure to measure coverage, but it still does not have a blocking rule that says whether the broader benchmark inventory is actually diverse enough.

Task `039` added typed taxonomy and suite-level `matrix_summary`. Task `040` added the suite catalog. Task `065` and Task `071` turned `release_gate_v1` into a blocking V1 release gate with latency SLOs. Task `073` expanded the registered inventory to 21 cases and added the focused robustness pack. What is still missing is the governance layer that prevents future case growth from remaining concentrated in `family` and `family_afternoon` while still looking superficially larger.

This task adds a separate blocking V1.5 coverage gate on top of the broader `all_registered` suite. After this task, the repository must be able to fail V1.5 coverage when scenario coverage, world-profile coverage, failure-mode coverage, or selected constraint-tag coverage drifts below the current floor or becomes too concentrated in the historical family-heavy path. This task must not change the existing V1 release gate contract.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. `docs/NEXT_PHASE_ROADMAP.md` says the current default priority is `M1. 评测与观测基础设施`: make evaluation comparable and enforceable before expanding more product surface.

The repository is already far enough along that the next gap is not raw instrumentation:

- Task `039` added typed benchmark taxonomy and `matrix_summary`.
- Task `040` added the canonical suite catalog.
- Task `065` added the blocking `release_gate_v1` runner.
- Task `071` added blocking latency SLO enforcement and structured release-gate diagnostics.
- Task `073` expanded `all_registered` to 21 cases and added the `robustness_focused` suite.

The current gap is governance across the broader benchmark inventory. `release_gate_v1` still blocks only on the fixed 15-case V1 suite and currently checks exact `level_counts`, `tool_profile_counts`, `failure_mode_counts`, and latency. `run_formal_verification.py` proves that `all_registered` passes, but it does not block on coverage diversity. That means future tasks could keep adding cases to the registered inventory while still staying heavily concentrated in `family` / `family_afternoon`.

This task belongs to `M1. 评测与观测基础设施`, but it directly protects the M3 benchmark-expansion work already landed in Tasks `038`, `049`, `050`, `055`, and `073`. It turns the current 21-case breadth into a maintained coverage floor without changing workflow behavior, Tool Gateway behavior, Mock World fixture data, or frontend contracts.

## 3. Requirements

- Add a new coverage gate module:
  - `backend/app/benchmark/coverage_gate.py`

- Add a new repo-root entrypoint:
  - `scripts/run_benchmark_coverage_gate.py`

- The canonical gate ID for this task must be:
  - `coverage_gate_v1_5`

- The standard command must be:
  - `python scripts/run_benchmark_coverage_gate.py`

- `run_benchmark_coverage_gate(...)` must run against a fresh `all_registered` benchmark result.
- The simplest allowed implementation path is:
  - call `run_formal_verification(...)`
  - reuse the returned unique run directory and `suite-all_registered-run-report.json`
  - evaluate coverage against that fresh suite report
- The gate must not silently use an old latest alias as its primary source of truth.

- This task must not change the public contract of:
  - `python scripts/run_formal_verification.py`
  - `backend.app.benchmark.formal_verification.run_formal_verification(...)`
  - `FORMAL_SUITE_ID = "all_registered"`

- The coverage gate must block unless all of the following base conditions are true:
  - `suite_id == "all_registered"`
  - `run_status == "passed"`
  - `failed_count == 0`
  - `error_count == 0`
  - `case_count >= 21`
  - `benchmark_summary.matrix_summary` exists
  - `benchmark_summary.outcome_rollup` exists
  - `benchmark_summary.outcome_rollup.constraint_tag_outcomes` exists
  - `benchmark_summary.matrix_summary.tool_profile_counts == {"mock_world": case_count}`

- The gate must evaluate scenario coverage from:
  - `benchmark_summary.matrix_summary.scenario_bucket_counts`
- The exact scenario minimums must be:
  - `couple >= 1`
  - `family >= 5`
  - `friends >= 2`
  - `mixed >= 3`
  - `solo >= 2`
  - `unknown >= 2`
- The gate must also enforce:
  - `family / case_count <= 0.60`

- The gate must evaluate world-profile coverage from:
  - `benchmark_summary.matrix_summary.world_profile_counts`
- The exact world-profile minimums must be:
  - `budget_lite >= 2`
  - `couple_afternoon >= 1`
  - `family_afternoon >= 5`
  - `friends_gathering >= 2`
  - `rainy_day_fallback >= 3`
  - `solo_afternoon >= 2`
- The gate must also enforce:
  - `family_afternoon / case_count <= 0.60`

- The gate must evaluate failure-mode coverage from:
  - `benchmark_summary.matrix_summary.failure_mode_counts`
- The exact failure-mode minimums must be:
  - `route_unavailable >= 1`
  - `route_and_dining_unavailable >= 1`
  - `ticket_sold_out_and_bad_weather >= 1`
- The gate must also enforce:
  - `none / case_count <= 0.90`

- The gate must evaluate constraint-tag coverage from:
  - `benchmark_summary.outcome_rollup.constraint_tag_outcomes[*].case_count`
- The exact required constraint-tag minimums must be:
  - `budget_limited >= 2`
  - `casual_dining >= 2`
  - `conversation_continuation >= 2`
  - `date_friendly >= 1`
  - `friends_group >= 2`
  - `memory_governance >= 2`
  - `rainy_day >= 3`
  - `robustness_case >= 4`

- Constraint-tag coverage in this task must continue to inherit the existing rollup exclusions from `backend/app/benchmark/rollups.py`:
  - `baseline`
  - `failure_injected`
  - `route_failure`
- This task must not redefine those exclusions.

- The unique `suite-all_registered-run-report.json` must be enriched with one additive top-level block:
  - `coverage_gate_evaluation`

- `coverage_gate_evaluation.schema_version` must be:
  - `weekendpilot_coverage_gate_evaluation_v1`

- `coverage_gate_evaluation` must include at least:
  - `gate_id`
  - `suite_id`
  - `release_blocked`
  - `blocking_failures`
  - `coverage_thresholds`
  - `observed_coverage`
  - `share_checks`

- `coverage_thresholds` must include the exact minimum and maximum-share rules listed in this spec.
- `observed_coverage` must include:
  - `case_count`
  - `scenario_bucket_counts`
  - `world_profile_counts`
  - `failure_mode_counts`
  - `constraint_tag_case_counts`
- `share_checks` must include:
  - `family_scenario_share`
  - `family_afternoon_world_profile_share`
  - `non_failure_share`
- Each share check must include:
  - `observed_ratio`
  - `max_ratio`
  - `status`
- `observed_ratio` values must be rounded deterministically to 4 decimal places.

- The coverage gate must create a separate latest-pass alias:
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`

- On a fully passing coverage gate:
  - the enriched unique suite report must exist
  - the latest coverage alias must be refreshed successfully
  - the latest coverage alias must be a direct copy of the enriched unique suite report

- On any blocked run:
  - the unique run directory must be preserved for debugging
  - `latest-coverage_gate_v1_5-run-report.json` must not be overwritten
  - the existing `latest-all_registered-run-report.json` behavior from `run_formal_verification.py` must remain unchanged

- The CLI result object for the new gate must expose:
  - `gate_id`
  - `suite_id`
  - `release_blocked`
  - `blocking_failures`
  - `case_count`
  - `passed_count`
  - `failed_count`
  - `error_count`
  - `overall_score`
  - `run_directory`
  - `suite_report_path`
  - `latest_report_path`
  - `scenario_bucket_counts`
  - `world_profile_counts`
  - `failure_mode_counts`
  - `constraint_tag_case_counts`
  - `share_checks`

- The CLI summary must print at least:
  - gate ID
  - suite ID
  - case count
  - overall score
  - the three share checks
  - latest coverage alias path
  - unique run directory
  - suite report path

- Add focused unit tests for:
  - green path
  - scenario minimum miss
  - family scenario share breach
  - world-profile minimum miss
  - family-afternoon world-profile share breach
  - failure-mode minimum miss
  - non-failure share breach
  - constraint-tag minimum miss
  - missing `matrix_summary`
  - missing `outcome_rollup.constraint_tag_outcomes`
  - latest coverage alias is not overwritten on blocked run
  - CLI exit code behavior

- Add focused integration tests for:
  - real `all_registered` run through the new coverage gate
  - additive `coverage_gate_evaluation` in the unique suite report
  - additive `coverage_gate_evaluation` in the latest coverage alias
  - exact observed coverage counts for the current 21-case inventory
  - expected passing share checks for the current inventory

- Update `README.md` to document:
  - the purpose of `coverage_gate_v1_5`
  - the difference between:
    - `release_gate_v1`
    - `all_registered` formal verification
    - `coverage_gate_v1_5`
  - the exact coverage-gate command
  - the exact blocking thresholds
  - the latest coverage alias path

- Do not add new benchmark cases, new suites, new taxonomy fields, new database tables, new Redis data structures, new APIs, new frontend panels, new provider integrations, or new dependencies.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not change `release_gate_v1` suite membership, latency SLOs, artifact layout, or deterministic runtime isolation.
- Do not change `all_registered` suite membership or case ordering.
- Do not add new benchmark case-generation tooling or a generic threshold-policy DSL.
- Do not add `elder` coverage requirements in this task because there is no current registered `elder` inventory.
- Do not modify Mock World fixture payloads, workflow routing, planner logic, candidate logic, or recovery behavior.
- Do not add internal observability API changes or frontend views for the new gate in this task.
- Do not modify unrelated local files such as `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, `docs/artifacts/`, or `qc`.

## 5. Interfaces and Contracts

### Inputs

- `python scripts/run_benchmark_coverage_gate.py`
- `backend.app.benchmark.formal_verification.run_formal_verification(...)`
- `BenchmarkRunReport`
- `BenchmarkSummary.matrix_summary`
- `BenchmarkSummary.outcome_rollup.constraint_tag_outcomes`
- the unique suite report `suite-all_registered-run-report.json`

### Outputs

- New blocking gate ID:
  - `coverage_gate_v1_5`
- New command:
  - `python scripts/run_benchmark_coverage_gate.py`
- Additive report block:
  - `coverage_gate_evaluation`
- New latest-pass alias:
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`

### Schemas

Example additive report shape:

```json
{
  "coverage_gate_evaluation": {
    "schema_version": "weekendpilot_coverage_gate_evaluation_v1",
    "gate_id": "coverage_gate_v1_5",
    "suite_id": "all_registered",
    "release_blocked": false,
    "blocking_failures": [],
    "coverage_thresholds": {
      "minimum_case_count": 21,
      "scenario_bucket_minimums": {
        "couple": 1,
        "family": 5,
        "friends": 2,
        "mixed": 3,
        "solo": 2,
        "unknown": 2
      },
      "scenario_bucket_max_share": {
        "family": 0.6
      },
      "world_profile_minimums": {
        "budget_lite": 2,
        "couple_afternoon": 1,
        "family_afternoon": 5,
        "friends_gathering": 2,
        "rainy_day_fallback": 3,
        "solo_afternoon": 2
      },
      "world_profile_max_share": {
        "family_afternoon": 0.6
      },
      "failure_mode_minimums": {
        "route_unavailable": 1,
        "route_and_dining_unavailable": 1,
        "ticket_sold_out_and_bad_weather": 1
      },
      "failure_mode_max_share": {
        "none": 0.9
      },
      "constraint_tag_minimums": {
        "budget_limited": 2,
        "casual_dining": 2,
        "conversation_continuation": 2,
        "date_friendly": 1,
        "friends_group": 2,
        "memory_governance": 2,
        "rainy_day": 3,
        "robustness_case": 4
      }
    },
    "observed_coverage": {
      "case_count": 21,
      "scenario_bucket_counts": {
        "couple": 1,
        "family": 11,
        "friends": 2,
        "mixed": 3,
        "solo": 2,
        "unknown": 2
      },
      "world_profile_counts": {
        "budget_lite": 2,
        "couple_afternoon": 1,
        "family_afternoon": 11,
        "friends_gathering": 2,
        "rainy_day_fallback": 3,
        "solo_afternoon": 2
      },
      "failure_mode_counts": {
        "none": 18,
        "route_and_dining_unavailable": 1,
        "route_unavailable": 1,
        "ticket_sold_out_and_bad_weather": 1
      },
      "constraint_tag_case_counts": {
        "budget_limited": 2,
        "casual_dining": 2,
        "conversation_continuation": 2,
        "date_friendly": 1,
        "friends_group": 2,
        "memory_governance": 2,
        "rainy_day": 3,
        "robustness_case": 4
      }
    },
    "share_checks": {
      "family_scenario_share": {
        "observed_ratio": 0.5238,
        "max_ratio": 0.6,
        "status": "passed"
      },
      "family_afternoon_world_profile_share": {
        "observed_ratio": 0.5238,
        "max_ratio": 0.6,
        "status": "passed"
      },
      "non_failure_share": {
        "observed_ratio": 0.8571,
        "max_ratio": 0.9,
        "status": "passed"
      }
    }
  }
}
```

Notes:

- `coverage_gate_v1_5` evaluates the broader `all_registered` inventory.
- `release_gate_v1` remains the existing V1 blocking suite.
- This task adds a separate coverage contract; it does not widen `release_gate_v1`.

## 6. Observability

This task must reuse the existing benchmark artifact pipeline.

It must add:

- additive `coverage_gate_evaluation` in the unique `suite-all_registered-run-report.json`
- a separate latest-pass alias at:
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`

It must not add:

- new API routes
- new frontend surfaces
- new database tables
- new Redis events
- new benchmark top-level schema fields outside the additive report block

The new report block must remain sanitized. It must not expose:

- secrets
- API keys
- tokens
- authorization headers
- prompts
- raw tool payloads
- raw action payloads
- tracebacks
- debug traces

## 7. Failure Handling

- If `run_formal_verification(...)` fails, the coverage gate must fail immediately and return a non-zero exit code.
- If the resulting suite is not `all_registered`, the coverage gate must fail.
- If `matrix_summary` is missing, the coverage gate must fail.
- If `outcome_rollup` is missing, the coverage gate must fail.
- If `constraint_tag_outcomes` is missing, the coverage gate must fail.
- If any required scenario bucket, world profile, failure mode, or constraint tag is missing from the observed report, the coverage gate must fail.
- If any required minimum count is not met, the coverage gate must fail.
- If `family / case_count > 0.60`, the coverage gate must fail.
- If `family_afternoon / case_count > 0.60`, the coverage gate must fail.
- If `none / case_count > 0.90`, the coverage gate must fail.
- If report enrichment fails, the coverage gate must fail.
- If refreshing `latest-coverage_gate_v1_5-run-report.json` fails, the coverage gate must fail.
- On a blocked run, the prior `latest-coverage_gate_v1_5-run-report.json` must remain untouched.
- This task must not change the current success/failure semantics of `run_formal_verification.py` or `run_benchmark_release_gate.py`.

## 8. Acceptance Criteria

- [ ] `docs/specs/074-benchmark-matrix-coverage-threshold-v0.md` exists and matches this task.
- [ ] `docs/plans/074-benchmark-matrix-coverage-threshold-v0-plan.md` exists and matches this task.
- [ ] `docs/specs/` and `docs/plans/` remain continuous and matched through `074`.
- [ ] `python scripts/run_benchmark_coverage_gate.py` exists and returns exit code `0` only when the current `all_registered` inventory passes the coverage thresholds in this spec.
- [ ] The gate evaluates fresh `all_registered` evidence rather than silently reading a stale alias as its primary input.
- [ ] The gate blocks when any required scenario minimum is missed.
- [ ] The gate blocks when `family / case_count > 0.60`.
- [ ] The gate blocks when any required world-profile minimum is missed.
- [ ] The gate blocks when `family_afternoon / case_count > 0.60`.
- [ ] The gate blocks when any required failure-mode minimum is missed.
- [ ] The gate blocks when `none / case_count > 0.90`.
- [ ] The gate blocks when any required constraint-tag minimum is missed.
- [ ] The unique `suite-all_registered-run-report.json` contains additive top-level `coverage_gate_evaluation`.
- [ ] A passing run refreshes `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`.
- [ ] A blocked run does not overwrite `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`.
- [ ] The current 21-case `all_registered` inventory passes the new coverage gate unchanged.
- [ ] `run_formal_verification.py` public behavior remains unchanged.
- [ ] `run_benchmark_release_gate.py` public behavior remains unchanged.
- [ ] `README.md` documents the new V1.5 coverage gate, exact thresholds, and latest alias path.
- [ ] Focused unit and integration verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except for pre-existing unrelated local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_formal_verification.py tests/test_benchmark_coverage_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_coverage_gate.py -k "all_registered or coverage_gate" -v
python scripts/run_benchmark_coverage_gate.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add benchmark matrix coverage threshold
```

## 11. Notes for the Implementer

Keep this task governance-only.

Important boundaries:

1. `release_gate_v1` remains the existing V1 blocking gate.
2. `coverage_gate_v1_5` is a separate broader-inventory gate on `all_registered`.
3. The coverage thresholds in this spec are intentionally the current minimum floor plus concentration caps, not a generic policy language.
4. Do not “fix” blocked coverage by weakening the threshold design during implementation.
5. Do not expand scope into new cases, new suites, new providers, or frontend/API exposure.
6. Stop and report back if making this task pass would require changing benchmark fixture payloads, suite membership, or the semantics of `all_registered`.
