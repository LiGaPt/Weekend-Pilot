# Plan: 094 Stability Harness + Pass@k v0

## 1. Spec Reference

Spec file:

```text
docs/specs/094-stability-harness-passk-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is still:
  - `codex/093-v2-integrity-matrix-gate-v0`
- Latest commit is:
  - `3c65154 feat: add v2 integrity benchmark gate`
- `docs/specs` and `docs/plans` are continuous and matched through `093`.
- The current worktree is not fully clean because of unrelated untracked docs:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Those untracked docs are not part of Task `094` and must not be staged accidentally.
- The existing V2 integrity substrate already exists:
  - `backend/app/benchmark/suites.py` includes `v2_integrity`
  - `backend/app/benchmark/schemas.py` includes V2 taxonomy and integrity coverage summary models
  - `backend/app/benchmark/harness.py` writes `v2_taxonomy_summary` and `integrity_coverage_summary`
  - `backend/app/benchmark/v2_integrity_gate.py` runs the formal gate and refreshes `latest-v2_integrity_gate-run-report.json`
- Existing formal evidence scripts already know about `v2_integrity_gate`:
  - `scripts/show_submission_evidence.py`
  - `scripts/demo_preflight.py`
- The stricter evidence-contract verifier does not yet include V2 integrity and should remain untouched in this task.
- Task `094` should be implemented as a fresh additive benchmark runner, not as a docs-only change.

## 3. Files to Add

- `backend/app/benchmark/stability_harness.py` - repeat-run stability runner that aggregates attempt outcomes into `Success@1`, `Pass@4`, and `Pass^4`.
- `scripts/run_benchmark_stability_passk.py` - repo-root CLI wrapper for the new stability harness.
- `tests/test_benchmark_stability_harness.py` - focused unit tests for metric formulas, alias isolation, relative paths, and runner validation.
- `tests/integration/test_benchmark_stability_harness.py` - integration test that runs a real 4-attempt `v2_integrity` stability pass.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add typed stability attempt/window/report schemas.
- `backend/app/benchmark/v2_integrity_gate.py` - add an explicit control to disable canonical latest-alias refresh when invoked from the stability harness.
- `backend/app/benchmark/__init__.py` - export new stability types or runner if the package already re-exports benchmark entrypoints.
- `tests/test_benchmark_v2_integrity_gate.py` - add regression coverage for the new no-alias-refresh path while preserving existing default behavior.

## 5. Implementation Steps

1. Add failing unit tests in `tests/test_benchmark_stability_harness.py` for the new typed report contract.
   - Cover `runs < 4`
   - Cover unsupported `suite_id`
   - Cover `Success@1`, `Pass@4`, and `Pass^4`
   - Cover `discarded_tail_run_count`
   - Cover relative `suite_report_path`
   - Cover deterministic attempt and window ordering

2. Add failing regression tests in `tests/test_benchmark_v2_integrity_gate.py` for alias-refresh control.
   - Default call must still refresh `latest-v2_integrity_gate-run-report.json`
   - Stability-mode call must skip canonical latest alias refresh
   - The gate report itself must still be enriched with `v2_integrity_gate_evaluation`

3. Extend `backend/app/benchmark/schemas.py` with additive stability models.
   - Add one attempt-result model
   - Add one window-result model
   - Add one top-level stability report model
   - Use `schema_version = "weekendpilot_benchmark_stability_passk_v1"`
   - Use JSON field `pass_pow_4` for `Pass^4`

4. Modify `backend/app/benchmark/v2_integrity_gate.py` to support isolated invocation from the stability harness.
   - Add a parameter such as `refresh_latest_alias: bool = True`
   - Keep default behavior unchanged for the existing CLI runner
   - Skip alias refresh only when explicitly disabled
   - Preserve all existing thresholds and report enrichment logic

5. Implement `backend/app/benchmark/stability_harness.py`.
   - Accept `suite_id`, `runs`, `output_root`, and `start_services`
   - Reject anything other than `suite_id="v2_integrity"` in v0
   - Reject `runs < 4`
   - Bootstrap runtime once at the start of the stability run
   - Create one stability run directory under `var/formal-benchmarks/stability`
   - Create deterministic attempt subdirectories named `attempt-001`, `attempt-002`, and so on
   - For each attempt, call the existing `run_benchmark_v2_integrity_gate(...)` path with:
     - `start_services=False`
     - canonical latest-alias refresh disabled
     - per-attempt output root
   - Record attempt outcome as `passed`, `failed`, or `error`
   - Continue remaining attempts even if one attempt fails
   - Build non-overlapping 4-attempt windows in attempt order
   - Compute:
     - `success_at_1 = success_count / executed_run_count`
     - `pass_at_4 = any-success windows / window_count`
     - `pass_pow_4 = all-success windows / window_count`
   - Write the final stability report and refresh only:
     - `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`

6. Add the CLI wrapper in `scripts/run_benchmark_stability_passk.py`.
   - Parse:
     - `--suite`
     - `--runs`
     - optional `--output-root`
     - optional `--no-start-services`
   - Print a concise success summary on pass
   - Print a concise failure summary on error
   - Exit non-zero on invalid input or failed stability run

7. Add or update package exports only if needed.
   - If benchmark entrypoints are already re-exported from `backend/app/benchmark/__init__.py`, export the new stability runner there too.
   - Do not refactor unrelated benchmark modules.

8. Add the real integration test in `tests/integration/test_benchmark_stability_harness.py`.
   - Run exactly 4 attempts against `v2_integrity`
   - Assert the report schema is valid
   - Assert attempt ordering is `1..4`
   - Assert `window_count == 1`
   - Assert the dedicated stability latest alias exists
   - Assert the report references attempt artifacts through relative paths
   - Assert the canonical `latest-v2_integrity_gate-run-report.json` is not touched by the stability harness path

9. Run focused regressions and one live CLI smoke.
   - Keep verification scoped to the stability harness and `v2_integrity_gate`
   - Do not refresh formal submission evidence in this task

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_stability_harness.py`
    - invalid suite rejection
    - `runs < 4` rejection
    - exact metric formulas
    - non-overlapping window grouping
    - tail discard behavior
    - relative path serialization
    - deterministic attempt/window ordering
  - `tests/test_benchmark_v2_integrity_gate.py`
    - default alias refresh unchanged
    - explicit no-refresh mode for stability harness

- Integration tests:
  - `tests/integration/test_benchmark_stability_harness.py`
    - real 4-attempt `v2_integrity` run
    - dedicated stability alias creation
    - canonical alias isolation
    - report schema and path assertions

- Smoke tests:
  - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark stability passk metrics
```

Expected commands:

```bash
git status --short
git add docs/specs/094-stability-harness-passk-v0.md
git add docs/plans/094-stability-harness-passk-v0-plan.md
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/v2_integrity_gate.py
git add backend/app/benchmark/stability_harness.py
git add backend/app/benchmark/__init__.py
git add scripts/run_benchmark_stability_passk.py
git add tests/test_benchmark_v2_integrity_gate.py
git add tests/test_benchmark_stability_harness.py
git add tests/integration/test_benchmark_stability_harness.py
git commit -m "feat: add benchmark stability passk metrics"
git push
```

The implementer must confirm `.env`, secrets, and `var/` artifacts are not staged.

## 9. Out-of-scope Changes

- Do not add `Avg@4`.
- Do not support suites other than `v2_integrity`.
- Do not change `v2_integrity` suite membership or taxonomy rules.
- Do not change `release_gate_v1`.
- Do not change `coverage_gate_v1_5`.
- Do not update `backend/app/benchmark/review_evidence.py`.
- Do not update `scripts/show_submission_evidence.py`.
- Do not update `scripts/demo_preflight.py`.
- Do not refresh or commit any generated benchmark artifacts under `var/`.
- Do not add reviewer UI, internal API, or submission-package changes.
- Do not add new dependencies unless strictly necessary and explicitly justified.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `Success@1`, `Pass@4`, and `Pass^4` use the exact formulas from the spec.
- [ ] The harness rejects unsupported suites and `runs < 4`.
- [ ] The harness uses non-overlapping windows of 4.
- [ ] Tail attempts are excluded from `Pass@4` and `Pass^4`.
- [ ] The stability runner writes only to the dedicated stability artifact root.
- [ ] The canonical `latest-v2_integrity_gate-run-report.json` is unchanged by stability-mode execution.
- [ ] Existing `v2_integrity_gate` default behavior still refreshes its own latest alias.
- [ ] Required tests and smoke checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or `var/` artifact was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- changed files
- exact report schema and field names
- whether `v2_integrity_gate` required any internal refactor beyond alias-refresh control
- verification commands and results
- one sample stability report path
- confirmation that canonical formal latest aliases were not modified by the stability harness
- commit hash
- push result
- known limitations or follow-up tasks:
  - `Avg@4`
  - support for additional suites
  - eventual V2 evidence-contract integration
