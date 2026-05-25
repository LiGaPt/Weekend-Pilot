# Plan: 065 Benchmark Release Gate v0

## 1. Spec Reference

Spec file:

```text
docs/specs/065-benchmark-release-gate-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/friends-group-demo-path-v1`.
- Latest numbered task on disk is `064`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `064`.
- Latest commit is `1695861 feat: add friends group demo path`, and it matches the latest task `064-friends-group-demo-path-v1`.
- Current working tree is not clean because unrelated local files are present:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/`
  - `qc`
- Those unrelated local changes must remain unstaged throughout this task.
- The benchmark suite catalog already contains:
  - `baseline`
  - `expanded`
  - `recovery_focused`
  - `memory_governance`
  - `conversation_continuations`
  - `default`
  - `all_registered`
- The current `all_registered` suite is green in focused validation:
  - `python -m pytest tests/test_benchmark_suites.py tests/test_formal_verification.py tests/test_benchmark_harness.py -q` passed during planning.
  - `python -m pytest tests/integration/test_formal_verification.py tests/integration/test_benchmark_harness_gateway.py -k "formal_verification or all_registered" -q` passed during planning.
- The current workspace also has a latest full-suite artifact at:
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  and it currently shows `17/17` passing, which means the next task is governance and release standardization, not urgent benchmark repair.
- `backend/app/benchmark/formal_verification.py` already defines the repository pattern for a benchmark orchestration runner; this task should mirror that pattern for the release gate without changing its public `all_registered` contract.

## 3. Files to Add

- `backend/app/benchmark/release_gate.py` - release-gate orchestration, blocking-rule evaluation, latest-alias refresh, CLI `main(...)`.
- `scripts/run_benchmark_release_gate.py` - repo-root entrypoint for the V1 blocking gate.
- `tests/test_benchmark_release_gate.py` - unit tests for runner success/failure behavior, latest alias handling, and CLI exit codes.
- `tests/integration/test_benchmark_release_gate.py` - integration test that runs the real `release_gate_v1` suite through the release-gate entrypoint with PostgreSQL/Redis and a temporary output root.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add `release_gate_v1` to `BenchmarkSuiteId`.
- `backend/app/benchmark/suites.py` - define the canonical `release_gate_v1` suite and insert it into suite ordering.
- `tests/test_benchmark_suites.py` - add exact `release_gate_v1` suite-order, membership, and matrix-summary assertions; update representative suite memberships.
- `tests/test_benchmark_harness.py` - add exact `release_gate_v1` matrix-summary coverage at the harness/unit level.
- `tests/test_observability.py` - update expected `registered_suite_ids` values where benchmark-backed cases now include `release_gate_v1`.
- `tests/integration/test_benchmark_harness_gateway.py` - add `release_gate_v1` suite execution assertions and serialized suite-report checks.
- `tests/integration/test_observability_gateway.py` - update expected `registered_suite_ids` values to include `release_gate_v1`.
- `README.md` - add a benchmark release gate section describing the blocking suite, the broader formal-verification scope, the failure rules, and the release checklist.

## 5. Implementation Steps

1. Confirm the exact `release_gate_v1` membership from existing registered cases.
   Use the current 17 registered cases and lock the V1 release gate to the 15 `L1-L3` cases listed in the spec.
   Do not infer membership dynamically by level at runtime; define the suite explicitly in canonical order.

2. Extend the suite schema literal.
   In `backend/app/benchmark/schemas.py`, add `release_gate_v1` to `BenchmarkSuiteId`.
   Do not introduce any new benchmark case schema fields in this task.

3. Add the suite definition and ordering.
   In `backend/app/benchmark/suites.py`:
   - add `_RELEASE_GATE_V1_CASE_IDS`
   - insert `release_gate_v1` into `_ORDERED_SUITE_IDS` after `default` and before `all_registered`
   - add the suite definition with a title and description that clearly mark it as the blocking V1 release gate
   - leave `default` and `all_registered` memberships unchanged

4. Update case-to-suite membership expectations.
   Ensure `list_benchmark_suite_ids_for_case(...)` now includes `release_gate_v1` for:
   - default cases
   - `family_route_failure_v1`
   - the two additive memory-governance cases
   - the two continuation cases
   Ensure the two `L5` composite failure cases still do not include `release_gate_v1`.

5. Add exact suite-catalog unit assertions.
   In `tests/test_benchmark_suites.py`:
   - extend the expected suite-order list with `release_gate_v1`
   - assert the exact 15 case IDs in `release_gate_v1`
   - assert representative `list_benchmark_suite_ids_for_case(...)` outputs including and excluding `release_gate_v1`
   - assert exact `release_gate_v1` matrix-summary counts from the spec

6. Add harness-level matrix-summary coverage.
   In `tests/test_benchmark_harness.py`, add a focused test:
   - `build_case_matrix_summary(load_benchmark_suite("release_gate_v1"))`
   - assert the exact scenario, level, tool-profile, world-profile, failure-mode, and tag counts from the spec

7. Implement the release-gate orchestration module.
   Create `backend/app/benchmark/release_gate.py` with:
   - a dataclass result object for the release-gate run
   - constants:
     - `RELEASE_GATE_SUITE_ID = "release_gate_v1"`
     - `LATEST_REPORT_FILENAME = "latest-release_gate_v1-run-report.json"`
     - a run-directory prefix such as `release-gate-v1-`
   - a top-level function:
     - `run_benchmark_release_gate(output_root: Path | str | None = None, *, start_services: bool = True, timeout_seconds: float = 60.0, poll_interval_seconds: float = 1.0) -> BenchmarkReleaseGateResult`
   - a `main() -> int` CLI adapter

8. Mirror the existing formal-verification bootstrap pattern without changing it.
   In `backend/app/benchmark/release_gate.py`, implement local helpers for:
   - `docker compose up -d postgres redis`
   - PostgreSQL readiness polling
   - Redis readiness polling
   - `python -m alembic upgrade head`
   Reuse the same behavior pattern as `formal_verification.py`, but do not refactor `formal_verification.py` into a shared generic runner in this task.

9. Keep the release-gate output isolated but colocated with existing formal benchmark artifacts.
   The new runner must:
   - default to `var/formal-benchmarks/`
   - create a unique run directory `release-gate-v1-<uuid>`
   - write a trace buffer file in that directory
   - write the suite report to `suite-release_gate_v1-run-report.json`
   - refresh `latest-release_gate_v1-run-report.json` only on success

10. Add explicit blocking-rule evaluation.
    In `backend/app/benchmark/release_gate.py`, evaluate the returned `BenchmarkRunReport` against the exact hard rules from the spec:
    - suite ID exact match
    - case count `15`
    - `run_status == "passed"`
    - `passed_count == 15`
    - `failed_count == 0`
    - `error_count == 0`
    - `overall_score == 1.0`
    - report path exists
    - level counts exactly `{"L1": 3, "L2": 8, "L3": 4}`
    - tool-profile counts exactly `{"mock_world": 15}`
    - failure-mode counts exactly `{"none": 14, "route_unavailable": 1}`
    Collect every violated rule into a `blocking_failures` list.
    Exit `0` only when `blocking_failures` is empty.

11. Preserve failed artifacts and protect the latest alias.
    If the run directory exists but any blocking rule fails:
    - keep the unique directory
    - do not overwrite `latest-release_gate_v1-run-report.json`
    - print a concise failure summary to stderr

12. Add the repo-root wrapper.
    Create `scripts/run_benchmark_release_gate.py` as a thin wrapper that imports `backend.app.benchmark.release_gate.main` and exits with its return code.

13. Add release-gate unit tests.
    In `tests/test_benchmark_release_gate.py`, cover at least:
    - success path creates the unique directory and latest alias
    - latest alias is a direct byte-for-byte copy of the suite report
    - failing gate criteria do not overwrite an existing latest alias
    - `main()` returns `1` on bootstrap error
    - `main()` returns `1` when the suite report is missing or counts drift
    - `main()` returns `0` and prints the expected summary on success

14. Add release-gate integration coverage.
    In `tests/integration/test_benchmark_release_gate.py`:
    - call `run_benchmark_release_gate(output_root=<temp>, start_services=False)`
    - assert `suite_id == "release_gate_v1"`
    - assert `case_count == 15`
    - assert `passed_count == 15`
    - assert `failed_count == 0`
    - assert `error_count == 0`
    - assert the unique suite report exists
    - assert `latest-release_gate_v1-run-report.json` exists
    - assert the copied latest alias still contains nested `report_path` values pointing to the unique run directory
    - assert the serialized report does not contain forbidden sensitive keys

15. Add harness integration coverage for the new suite.
    In `tests/integration/test_benchmark_harness_gateway.py`, add or extend the suite-level integration assertions so `BenchmarkHarness.run_suite("release_gate_v1")` verifies:
    - exact case count `15`
    - zero failures and zero errors
    - expected `suite-release_gate_v1-run-report.json` filename
    - exact matrix-summary counts
    - exact outcome-rollup shape stays structurally valid for the new suite

16. Update observability expectations only where suite membership surfaces changed.
    In `tests/test_observability.py` and `tests/integration/test_observability_gateway.py`, update the expected `registered_suite_ids` arrays to include `release_gate_v1` for benchmark-backed cases that belong to the new suite.
    Do not change observability service code unless a focused failing test proves it is required.

17. Update the README release standard.
    Add a `Benchmark Release Gate` section to `README.md` that includes:
    - what `release_gate_v1` covers
    - what `all_registered` covers
    - which command is blocking vs broader verification
    - the exact gate threshold
    - the failure rules
    - a flat release checklist

18. Keep unrelated local artifacts untouched.
    Do not modify:
    - `.gitignore`
    - `docs/COMPETITION_SUBMISSION_DESIGN.md`
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/artifacts/`
    - `qc`

19. Run focused verification in this order.
    - unit tests
    - PostgreSQL/Redis startup and Alembic
    - benchmark suite integration tests
    - release-gate integration test
    - release-gate script
    - formal-verification script regression
    - `git diff --check`
    - `git status --short`

20. Commit only task-relevant files.
    Stage only the files listed in this plan.
    Ensure `var/` outputs and unrelated dirty files remain unstaged.

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_suites.py`
    - suite ordering includes `release_gate_v1`
    - exact case membership for `release_gate_v1`
    - representative `list_benchmark_suite_ids_for_case(...)` outputs
  - `tests/test_benchmark_harness.py`
    - exact `release_gate_v1` matrix-summary counts
  - `tests/test_benchmark_release_gate.py`
    - success path
    - failure path
    - latest alias preservation
    - CLI exit code behavior
  - `tests/test_observability.py`
    - updated `registered_suite_ids`

- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py`
    - `run_suite("release_gate_v1")`
    - suite report path and exact summary counts
  - `tests/integration/test_benchmark_release_gate.py`
    - real release-gate runner against PostgreSQL/Redis
  - `tests/integration/test_observability_gateway.py`
    - updated `registered_suite_ids`

- Smoke tests:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_formal_verification.py`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_release_gate.py tests/integration/test_observability_gateway.py -k "release_gate_v1 or benchmark_release_gate or registered_suite_ids" -v
python scripts/run_benchmark_release_gate.py
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark release gate
```

Expected commands:

```bash
git status --short
git switch -c codex/benchmark-release-gate-v0
git add backend/app/benchmark/schemas.py backend/app/benchmark/suites.py
git add backend/app/benchmark/release_gate.py scripts/run_benchmark_release_gate.py
git add tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py tests/test_observability.py
git add tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_release_gate.py tests/integration/test_observability_gateway.py
git add README.md
git commit -m "feat: add benchmark release gate"
git push -u origin codex/benchmark-release-gate-v0
```

The implementer must confirm `.env`, secrets, `var/` outputs, and unrelated local docs/artifacts are not staged.

## 9. Out-of-scope Changes

- Do not change unrelated modules.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md` unless the spec explicitly requires it.
- Do not add new dependencies.
- Do not add new benchmark fixtures, failure profiles, or suite types beyond `release_gate_v1`.
- Do not change `default` or `all_registered` semantics.
- Do not refactor `formal_verification.py` into a shared generic benchmark framework.
- Do not add CI workflows, GitHub Actions, or automated release publishing.
- Do not add latency SLO enforcement.
- Do not commit generated `var/` outputs, Docker/runtime caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `release_gate_v1` is exactly the 15-case `L1-L3` suite from the spec.
- [ ] `all_registered` still remains the 17-case broader suite.
- [ ] The release-gate runner exits `0` only for the exact blocking threshold.
- [ ] A failed run does not overwrite `latest-release_gate_v1-run-report.json`.
- [ ] `README.md` clearly distinguishes the blocking gate from broader formal verification.
- [ ] Required tests and smoke commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Exact `release_gate_v1` case order as implemented
- Verification commands and results
- Release-gate script output summary
- Formal-verification regression result
- Commit hash
- Push result
- Known limitations:
  - `L5` composite chaos cases remain outside the blocking V1 gate
  - timing is recorded but non-blocking in this v0 task
