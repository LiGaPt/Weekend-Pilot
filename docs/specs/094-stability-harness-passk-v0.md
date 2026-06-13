# Spec: 094 Stability Harness + Pass@k v0

## 1. Goal

WeekendPilot now has a dedicated `v2_integrity` benchmark suite and a formal `v2_integrity_gate` sign-off path. What is still missing is a way to measure whether that sign-off surface is stable across repeated executions instead of only proving a single clean run.

This task adds a small, deterministic stability harness for repeated benchmark execution. After this task is complete, the repository must be able to run a supported suite multiple times, aggregate attempt-level success outcomes into `Success@1`, `Pass@4`, and `Pass^4` v0, and write a dedicated stability report that can be compared across runs without disturbing the canonical `latest-*` formal evidence aliases.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven, deterministic where possible, and observable by default. The blueprint’s V2 target explicitly includes stability-style benchmark metrics such as `Success@1`, `Avg@4`, `Pass@4`, and `Pass^4`.

`docs/NEXT_PHASE_ROADMAP.md` says the current default priority remains `M1. 评测与观测基础设施`: turn “the workflow can run” into “the workflow can be measured and compared.” Tasks `092` and `093` already established the V2 integrity benchmark substrate:

- Task `092` introduced the additive `v2_integrity` suite and V2 taxonomy.
- Task `093` introduced the additive `v2_integrity_gate` and integrity-coverage summary.

This task is the smallest direct continuation of that chain. It stays inside M1 benchmark infrastructure. It must not expand into UI work, broader suite matrices, new benchmark cases, or evidence-package governance.

## 3. Requirements

- The repository must provide a new repeat-run stability harness for benchmark execution.
- The v0 harness must accept a target suite ID and a repeat count `N`.
- The v0 harness must support only `suite_id="v2_integrity"`.
- Any unsupported suite ID must fail fast with a clear error message instead of silently falling back.
- The harness must repeat the existing `v2_integrity` sign-off path, not invent a second independent integrity grading path.
- The harness must evaluate attempt success using the existing `v2_integrity_gate` result:
  - an attempt is a success only when `release_blocked == false`
  - and the gate result is otherwise valid
- The harness must require `N >= 4`.
- The harness must bootstrap runtime dependencies once per stability run, then execute repeated attempts without restarting services on every attempt.
- The harness must not refresh or overwrite:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
- The harness must write all artifacts under a dedicated stability output root.
- The recommended default output root is:
  - `var/formal-benchmarks/stability`
- Each stability run must create one dedicated run directory.
- Inside one stability run directory, attempt subdirectories must be deterministic in order and naming:
  - `attempt-001`
  - `attempt-002`
  - `attempt-003`
  - ...
- The top-level stability report must include:
  - requested suite ID
  - requested run count
  - executed run count
  - window size
  - window count
  - discarded tail run count
  - success count
  - failure count
  - error count
  - `Success@1`
  - `Pass@4`
  - `Pass^4`
  - ordered attempt summaries
- Metric definitions for v0 must be fixed as follows:
  - `Success@1 = success_count / executed_run_count`
  - `window_size = 4`
  - `window_count = floor(executed_run_count / 4)`
  - `discarded_tail_run_count = executed_run_count % 4`
  - attempts are grouped into non-overlapping windows of 4 in attempt order
  - `Pass@4 = windows_with_at_least_one_success / window_count`
  - `Pass^4 = windows_with_all_four_successes / window_count`
- If `N` is exactly `4`, the report must still use the same formulas with `window_count = 1`.
- The report must preserve deterministic ordering:
  - attempts in ascending attempt index
  - window results in ascending window index
  - count maps serialized with sorted keys
- The report must include per-attempt references to the produced gate report for debugging.
- The report must not expose secrets, tokens, authorization headers, raw debug traces, or traceback payloads.
- The harness must publish a dedicated latest stability alias that is separate from formal benchmark aliases.
- The recommended alias path is:
  - `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`
- The harness must provide a repo-root CLI entrypoint for local execution.

## 4. Non-goals

- Do not implement `Avg@4`.
- Do not support arbitrary suite families in v0.
- Do not add repeated-run support for `release_gate_v1`, `coverage_gate_v1_5`, or `all_registered`.
- Do not modify benchmark case fixtures.
- Do not add new benchmark cases.
- Do not change `v2_integrity` suite membership.
- Do not change `v2_integrity_gate` thresholds or pass/fail semantics.
- Do not update formal evidence verifier contracts in this task.
- Do not update reviewer-facing README, submission docs, or preflight contracts unless strictly required for the new standalone runner.
- Do not commit `.env`, API keys, tokens, secrets, generated benchmark artifacts, or `var/` contents.

## 5. Interfaces and Contracts

### Inputs

- CLI:
  - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
- Programmatic runner:
  - `run_benchmark_stability_passk(suite_id: str, runs: int, output_root: Path | str | None = None, start_services: bool = True)`

Recommended optional CLI flags:

- `--output-root <path>`
- `--no-start-services`

### Outputs

- Stability run directory under:
  - `var/formal-benchmarks/stability/`
- Stability report file:
  - `stability-v2_integrity-passk-v0-report.json`
- Latest stability alias:
  - `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`

### Schemas

Recommended top-level report schema:

```json
{
  "schema_version": "weekendpilot_benchmark_stability_passk_v1",
  "metric_version": "passk_v0",
  "suite_id": "v2_integrity",
  "gate_id": "v2_integrity_gate",
  "requested_run_count": 4,
  "executed_run_count": 4,
  "window_size": 4,
  "window_count": 1,
  "discarded_tail_run_count": 0,
  "success_count": 4,
  "failure_count": 0,
  "error_count": 0,
  "success_at_1": 1.0,
  "pass_at_4": 1.0,
  "pass_pow_4": 1.0,
  "attempts": [
    {
      "attempt_index": 1,
      "status": "passed",
      "release_blocked": false,
      "run_status": "passed",
      "overall_score": 1.0,
      "suite_report_path": "attempt-001/suite-v2_integrity-run-report.json",
      "blocking_failures": []
    }
  ],
  "windows": [
    {
      "window_index": 1,
      "attempt_indexes": [1, 2, 3, 4],
      "any_success": true,
      "all_success": true,
      "success_count": 4
    }
  ]
}
```

Required contract decisions:

- `status` at the attempt level must be one of:
  - `passed`
  - `failed`
  - `error`
- `release_blocked=true` must map to unsuccessful attempts.
- `suite_report_path` in the stability report must be stored as a path relative to the stability run directory, not as a volatile absolute path.
- The report field name for `Pass^4` must be `pass_pow_4` in JSON.

## 6. Observability

This task adds benchmark-artifact observability only.

The stability harness must record:

- one top-level stability report
- one ordered attempt list
- one ordered window list
- one relative artifact path per attempt
- aggregate success/failure/error counts

This task must not add:

- new PostgreSQL benchmark tables
- new Redis event channels
- new LangSmith metadata contracts
- new internal API routes
- new frontend observability panels

## 7. Failure Handling

Expected failure modes and required behavior:

- Unsupported suite ID:
  - fail fast before any attempts start
  - print a clear error
  - do not create a misleading latest stability alias
- `runs < 4`:
  - fail fast before any attempts start
  - explain that v0 requires at least 4 runs
- Runtime bootstrap failure before attempt 1:
  - fail the whole stability run
  - do not write a success alias
- Individual attempt failure:
  - record the attempt as `failed` or `error`
  - continue remaining attempts
  - include failure details in `blocking_failures`
- Malformed gate report:
  - record the attempt as `error`
  - continue remaining attempts
- Alias write failure for the stability alias:
  - fail the whole stability run after report generation
  - do not silently swallow the write error
- Tail attempts when `N % 4 != 0`:
  - include them in `Success@1`
  - exclude them from `Pass@4` and `Pass^4`
  - report `discarded_tail_run_count`

## 8. Acceptance Criteria

- [ ] The repository provides a CLI runner for stability pass-k execution.
- [ ] `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4` is a valid supported command.
- [ ] v0 rejects unsupported suite IDs with a clear error.
- [ ] v0 rejects `runs < 4` with a clear error.
- [ ] The harness repeats the existing `v2_integrity_gate` path instead of duplicating integrity logic elsewhere.
- [ ] The harness computes `Success@1`, `Pass@4`, and `Pass^4` exactly as defined in this spec.
- [ ] The harness uses non-overlapping windows of 4 in attempt order.
- [ ] Tail attempts beyond full windows are excluded from `Pass@4` and `Pass^4` and counted in `discarded_tail_run_count`.
- [ ] The top-level report uses deterministic field names and deterministic attempt/window ordering.
- [ ] The report stores attempt artifact references as relative paths.
- [ ] The harness writes under a dedicated stability artifact root.
- [ ] The harness refreshes only the dedicated stability latest alias.
- [ ] The harness does not overwrite canonical formal benchmark latest aliases.
- [ ] Focused tests cover:
  - metric calculation
  - tail discard behavior
  - alias isolation
  - per-attempt ordering
  - CLI validation
  - regression for normal `v2_integrity_gate` alias refresh behavior
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git status --short
python -m pytest tests/test_benchmark_v2_integrity_gate.py tests/test_benchmark_stability_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_stability_harness.py -q
python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4
git diff --check
git status --short
```

If the implementation chooses different focused test filenames, the verification surface must still cover the same acceptance criteria.

## 10. Expected Commit

```text
feat: add benchmark stability passk metrics
```

## 11. Notes for the Implementer

Implement this as an additive stability layer on top of Task `093`.

Recommended sequencing:

1. parameterize `v2_integrity_gate` so its alias refresh can be disabled
2. add typed stability report models
3. implement the repeat-run harness and metric aggregation
4. add the CLI wrapper
5. prove alias isolation and metric determinism through focused tests
6. run one real 4-attempt integration pass on `v2_integrity`

Important constraints:

- do not let repeated runs mutate official formal evidence aliases
- do not add `Avg@4` in this task
- do not widen scope to multiple suites or submission-package integration
- if the existing `v2_integrity_gate` code cannot be reused cleanly, stop and report the refactor boundary instead of creating a parallel gate implementation
