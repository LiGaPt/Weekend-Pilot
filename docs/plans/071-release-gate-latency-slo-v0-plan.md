# Plan: 071 Release Gate Latency SLO v0

## 1. Spec Reference

Spec file:

```text
docs/specs/071-release-gate-latency-slo-v0.md
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

- Current branch is `codex/deterministic-release-gate-isolation-v0`.
- Latest completed numbered task on disk is `070`.
- Latest commit is:

  ```text
  dc076a7 fix: isolate release gate runtime settings
  ```

- That latest commit matches Task `070` because it updates the `070` spec/plan and the release-gate runtime code/tests.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `070`.
- There is no newer numbered spec/plan to continue before opening Task `071`.
- Current unrelated dirty files are:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `docs/artifacts/`
  - `qc`
- Those local changes are not part of Task `071` and must remain unstaged.
- Task `033` already provides:
  - per-case `workflow_timing_summary`
  - suite-level `benchmark_timing_summary`
  - `overall_total_duration_ms.max_ms`
  - stage-level percentile stats
- Task `065` already provides:
  - `release_gate_v1`
  - latest-alias copy-on-pass behavior
  - blocking count and matrix-summary checks
- Task `070` already guarantees release-gate timing is deterministic and isolated from local preview env.
- `backend/app/benchmark/release_gate.py` currently prints `p50`, `p95`, and `p99`, but does not:
  - block on latency thresholds
  - record `max_ms` in the result
  - preserve slow case ranking
  - preserve slow stage ranking
  - preserve focus-stage metrics in the suite report
- The current implementation path should stay narrow:
  - enrich only the release-gate suite report
  - do not redesign generic benchmark report schemas

## 3. Files to Add

- `docs/specs/071-release-gate-latency-slo-v0.md` - task spec.
- `docs/plans/071-release-gate-latency-slo-v0-plan.md` - implementation plan.

## 4. Files to Modify

- `README.md` - document the blocking latency SLO and the new report diagnostics.
- `backend/app/benchmark/release_gate.py` - add SLO enforcement, ranked latency diagnostics, report enrichment, and updated CLI formatting.
- `tests/test_benchmark_release_gate.py` - add focused unit coverage for SLO blocking, ranking, and report enrichment.
- `tests/integration/test_benchmark_release_gate.py` - add real-run assertions for the enriched report payload.

## 5. Implementation Steps

1. Save the approved Task `071` spec and plan files at the target paths before editing code.

2. Create the implementation branch from the current `070` baseline instead of reusing the `070` task name.

   Run:

   ```bash
   git status --short --branch
   git switch -c codex/release-gate-latency-slo-v0
   ```

3. In `backend/app/benchmark/release_gate.py`, add explicit latency SLO constants.

   Use exact values:

   - `EXPECTED_P50_DURATION_MS = 2000`
   - `EXPECTED_P95_DURATION_MS = 5000`
   - `EXPECTED_MAX_DURATION_MS = 8000`

   Add one constant list for the focus stages:

   - `FOCUS_STAGE_NODE_NAMES = ("pre_flight_check_availability", "logical_planner_agent")`

4. Extend the release-gate result data model so the in-memory result can drive both JSON enrichment and CLI output.

   Add:

   - `max_duration_ms: int | None`
   - one structured slow-case collection
   - one structured slow-stage collection
   - one structured focus-stage collection
   - one structured latency-SLO evaluation object or equivalent fields

   Keep the existing fields from Task `065` unchanged.

5. Build one private helper that extracts and validates overall timing from the suite report object.

   The helper must:

   - read `report.benchmark_timing_summary.overall_total_duration_ms`
   - capture `p50_ms`, `p95_ms`, `p99_ms`, `max_ms`
   - return blocking failures when any required blocking field is missing
   - mark the SLO status failed when:
     - `p50_ms > 2000`
     - `p95_ms > 5000`
     - `max_ms > 8000`

6. Build one private helper that constructs the slow-case ranking from `report.case_results`.

   The helper must:

   - require `workflow_timing_summary.total_duration_ms` for every `release_gate_v1` case result
   - create entries with:
     - `rank`
     - `case_id`
     - `workflow_status`
     - `total_duration_ms`
     - `report_path`
   - sort by:
     1. `total_duration_ms` descending
     2. `case_id` ascending
   - emit a blocking failure if any case is missing `workflow_timing_summary.total_duration_ms`

7. Build one private helper that constructs the slow-stage ranking from `report.benchmark_timing_summary.stages`.

   The helper must:

   - read existing stage percentile entries only
   - create ranked entries with:
     - `rank`
     - `node_name`
     - `sample_count`
     - `retry_case_count`
     - `min_ms`
     - `p50_ms`
     - `p95_ms`
     - `p99_ms`
     - `max_ms`
     - `mean_ms`
   - sort by:
     1. `p95_ms` descending
     2. `max_ms` descending
     3. `mean_ms` descending
     4. `node_name` ascending

8. Build one private helper that extracts the two focus stages.

   The helper must:

   - find entries for:
     - `pre_flight_check_availability`
     - `logical_planner_agent`
   - reuse the same field set as the stage ranking
   - emit a blocking failure if either focus stage is missing

9. In `_finalize_release_gate_result(...)`, keep the current Task `065` count/matrix checks first, then add the new latency diagnostics and blocking failures.

   The order should be:

   1. existing suite identity and count checks
   2. existing matrix-summary checks
   3. overall latency SLO checks
   4. slow-case completeness check
   5. focus-stage presence check

   Do not remove any pre-existing blocking rule.

10. Build one additive `release_gate_evaluation` payload from the finalized diagnostics.

    Use exact top-level structure:

    - `schema_version`
    - `gate_id`
    - `suite_id`
    - `release_blocked`
    - `blocking_failures`
    - `latency_slo`
    - `slow_cases`
    - `slow_stages`
    - `focus_stages`

    Use exact schema versions:

    - `weekendpilot_release_gate_evaluation_v1`
    - `weekendpilot_release_gate_latency_slo_v1`

11. Enrich the unique suite report JSON in place before any latest-alias copy.

    Add one helper that:

    - reads `suite-release_gate_v1-run-report.json`
    - inserts or replaces the top-level `release_gate_evaluation`
    - writes back through a temporary file plus replace
    - preserves existing `report_path` values and all existing benchmark payloads
    - raises a release-gate error or returns a blocking failure if the write cannot be completed

12. Keep latest-alias semantics narrow and deterministic.

    Use this rule:

    - always enrich the unique suite report JSON first
    - only refresh `latest-release_gate_v1-run-report.json` when there are zero blocking failures after enrichment
    - on any blocked run, leave the old latest alias untouched

13. Update the human-readable success and failure formatters.

    The success and failure summaries must both include:

    - timing line with `p50`, `p95`, `p99`, and `max`
    - one `Latency SLO` line with exact thresholds and pass/fail status
    - one `Focus stages` section printing both focus stages with `mean`, `p95`, and `max`
    - one `Slow cases` section printing the first 3 ranked entries
    - one `Slow stages` section printing the first 5 ranked entries

    Keep the existing gate/suite/case/score/path lines intact.

14. Update `README.md` only where the release-gate contract actually changed.

    In the `Benchmark Release Gate` section, add:

    - the exact blocking latency thresholds
    - that these thresholds are evaluated on `release_gate_v1` only
    - that the release-gate run report now carries `release_gate_evaluation`
    - that the report preserves slow case ranking, slow stage ranking, and focus-stage metrics
    - that the latest alias still refreshes only on a fully passing gate

    Do not change the formal verification section.

15. Add focused unit tests in `tests/test_benchmark_release_gate.py`.

    Cover:

    - a passing fake report now records `max_duration_ms`
    - `release_gate_evaluation` is written into the suite report and copied into the latest alias
    - `p50` breach blocks the gate
    - `p95` breach blocks the gate
    - `max` breach blocks the gate
    - missing case timing blocks the gate
    - missing `pre_flight_check_availability` blocks the gate
    - missing `logical_planner_agent` blocks the gate
    - slow-case ranking order is deterministic
    - slow-stage ranking order is deterministic
    - failure summary and success summary include `max` and focus-stage lines
    - blocked runs still preserve the prior latest alias contents

16. Add focused integration assertions in `tests/integration/test_benchmark_release_gate.py`.

    On a real `run_benchmark_release_gate(output_root=<temp>, start_services=False)` run, assert:

    - `result.release_blocked is False`
    - `result.max_duration_ms is not None`
    - the unique suite report JSON contains `release_gate_evaluation`
    - the latest alias JSON contains `release_gate_evaluation`
    - `release_gate_evaluation.latency_slo.p50_threshold_ms == 2000`
    - `release_gate_evaluation.latency_slo.p95_threshold_ms == 5000`
    - `release_gate_evaluation.latency_slo.max_threshold_ms == 8000`
    - `release_gate_evaluation.slow_cases` is sorted descending by `total_duration_ms`
    - `release_gate_evaluation.focus_stages.pre_flight_check_availability` exists
    - `release_gate_evaluation.focus_stages.logical_planner_agent` exists

17. Run verification in this order.

    First:

    ```bash
    python -m pytest tests/test_benchmark_release_gate.py -q
    ```

    Then:

    ```bash
    docker compose up -d postgres redis
    python -m alembic upgrade head
    python -m pytest tests/integration/test_benchmark_release_gate.py -q
    ```

    Then:

    ```bash
    python scripts/run_benchmark_release_gate.py
    git diff --check
    git status --short
    ```

18. Stage only task-relevant files.

    Do not stage:

    - `.gitignore`
    - `docs/COMPETITION_SUBMISSION_DESIGN.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/V1_DEVELOPMENT_REPORT.md`
    - `docs/artifacts/`
    - `qc`
    - any `var/` runtime artifacts

## 6. Testing Plan

- Unit tests:
  - passing release gate includes `max_duration_ms`
  - passing release gate enriches the suite report with `release_gate_evaluation`
  - blocked gate on `p50` threshold breach
  - blocked gate on `p95` threshold breach
  - blocked gate on `max` threshold breach
  - blocked gate when case timing is missing
  - blocked gate when `pre_flight_check_availability` is missing
  - blocked gate when `logical_planner_agent` is missing
  - slow-case ranking order is deterministic
  - slow-stage ranking order is deterministic
  - stdout summary includes `max` and focus-stage diagnostics

- Integration tests:
  - real `release_gate_v1` run still passes
  - unique suite report contains `release_gate_evaluation`
  - latest alias contains `release_gate_evaluation`
  - `slow_cases` ranking is sorted descending
  - both focus stages are present in the report payload

- Smoke tests:
  - `python scripts/run_benchmark_release_gate.py`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_release_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_release_gate.py -q
python scripts/run_benchmark_release_gate.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add release gate latency slo
```

Expected commands:

```bash
git status --short
git switch -c codex/release-gate-latency-slo-v0
git add docs/specs/071-release-gate-latency-slo-v0.md
git add docs/plans/071-release-gate-latency-slo-v0-plan.md
git add README.md backend/app/benchmark/release_gate.py
git add tests/test_benchmark_release_gate.py tests/integration/test_benchmark_release_gate.py
git diff --cached --check
git commit -m "feat: add release gate latency slo"
git push -u origin codex/release-gate-latency-slo-v0
```

The implementer must confirm `.env`, secrets, `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, `docs/artifacts/`, `qc`, and runtime `var/` outputs are not staged.

## 9. Out-of-scope Changes

- Do not optimize the workflow to meet the thresholds in this task.
- Do not change `release_gate_v1` membership, matrix-summary rules, or deterministic runtime settings.
- Do not change `all_registered` or `run_formal_verification.py`.
- Do not add frontend, API, database, or Redis changes.
- Do not redesign generic benchmark schemas or harness behavior.
- Do not modify unrelated document drafts or local artifacts.
- Do not commit generated caches, virtual environments, `node_modules`, frontend build outputs, or secrets.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/071-release-gate-latency-slo-v0.md`.
- [ ] The task stayed inside `release_gate_v1` latency governance scope.
- [ ] The gate enforces exactly `p50 <= 2000ms`, `p95 <= 5000ms`, `max <= 8000ms`.
- [ ] Existing Task `065` release-gate count and matrix checks still work unchanged.
- [ ] Existing Task `070` deterministic isolation still works unchanged.
- [ ] The unique suite report contains additive top-level `release_gate_evaluation`.
- [ ] The latest passing alias contains the same `release_gate_evaluation`.
- [ ] `slow_cases` ranking is deterministic and complete for passing runs.
- [ ] `slow_stages` ranking is deterministic.
- [ ] `focus_stages` includes both `pre_flight_check_availability` and `logical_planner_agent`.
- [ ] A blocked run does not overwrite the prior latest alias.
- [ ] The CLI summary now includes `max`, focus stages, and ranked slow diagnostics.
- [ ] Required tests and smoke commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- Changed files.
- The exact threshold values implemented.
- Whether the release-gate run passed or blocked under the new SLO.
- The observed `p50`, `p95`, `p99`, and `max` from the verification run.
- The top 3 slow cases from the verification run.
- The reported metrics for:
  - `pre_flight_check_availability`
  - `logical_planner_agent`
- Verification commands and results.
- Commit hash.
- Push result.
- Any blocker, especially if the repo now legitimately fails its own new SLO instead of passing.
