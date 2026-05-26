# Plan: 067 Recovery Replay Review Closure v0

## 1. Spec Reference

Spec file:

```text
docs/specs/067-recovery-replay-review-closure-v0.md
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

- Current branch is `codex/memory-governance-release-closure-v1`.
- Latest completed task in the repository is `066`.
- Latest commit is `4e5d863 docs: close memory governance v1 release scope`, which matches Task `066`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `066`.
- Existing relevant capability is already present:
  - Task `029` failure injection for `family_route_failure_v1`
  - Task `030` file-based replay harness
  - Task `042` internal `recovery_path_summary`
  - Task `051` bounded recovery routing v1
  - Task `052` replay-stable `failure_chain_signature`
  - Task `061` formal verification runner
  - Task `065` release-gate runner
- Existing canonical failure case is already registered:
  - `backend/app/benchmark/cases/family_route_failure_v1.json`
- Existing latest formal evidence already exists:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
- Focused verification has already shown the current building blocks are green:
  - unit tests around benchmark replay, observability, failure injection, suites, harness, release gate, and formal verification pass
  - focused integration tests around replay, observability recovery summary, and benchmark harness pass
- There is currently no production runner that writes a canonical `var/recovery-reviews/` artifact bundle. Replay outputs exist only through library calls and test output directories.
- The worktree is already dirty with unrelated local files. These must remain out of scope and unstaged:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/`
  - `qc`

## 3. Files to Add

- `backend/app/benchmark/recovery_review.py` - orchestrates source benchmark run, replay run, internal observability lookup, aggregate checks, artifact writing, latest-alias refresh, and CLI-facing summary formatting.
- `scripts/run_recovery_replay_review.py` - thin wrapper that exposes the new runner as a repo-root command.
- `tests/test_recovery_replay_review.py` - unit coverage for aggregate review status computation, path-linking checks, latest-alias behavior, and main-path formatting.
- `tests/integration/test_recovery_replay_review.py` - end-to-end integration coverage for the canonical `family_route_failure_v1` closure path.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add additive review-result and review-check models for the aggregate closure artifact.
- `backend/app/benchmark/reporting.py` - add a writer for the aggregate recovery-review artifact, reusing the existing sanitizer and forbidden-key handling.
- `backend/app/benchmark/__init__.py` - export the new runner and additive review models if doing so stays consistent with current package exports.
- `README.md` - add a concise `Recovery Replay Review` section with the new command and artifact locations.
- `docs/WEB_DEMO_README.md` - add one short note explaining how the script’s `run_id` and source report path relate to existing internal observability review.

## 5. Implementation Steps

1. Add failing unit tests first in `tests/test_recovery_replay_review.py`.
   Lock the exact closure contract before implementation:
   - a passing source benchmark result plus passing replay result plus matching observability paths yields aggregate `status="passed"`
   - replay mismatches yield aggregate `status="failed"`
   - missing `recovery_path_summary` or mismatched observability report paths yield aggregate `status="failed"`
   - latest alias refreshes only on `status="passed"`
   - a typed runner error yields `status="error"` and a nonzero CLI exit path

2. Add additive review models in `backend/app/benchmark/schemas.py`.
   Add compact typed models for:
   - one review check record with `name`, `passed`, and `detail`
   - one replay-review summary record with `status`, `mismatch_count`, and `failure_chain_signature`
   - one compact recovery-review summary record with `benchmark_report_path`, `attempt_count`, `max_attempts`, `recovery_actions`, and `replay_source`
   - one aggregate `RecoveryReplayReviewResult` model with:
     - `schema_version="weekendpilot_recovery_replay_review_v1"`
     - `status`
     - `case_id`
     - `run_id`
     - `run_directory`
     - `source_report_path`
     - `replay_report_path`
     - `latest_review_path`
     - `checks`
     - `failure_chain_summary`
     - compact replay summary
     - compact recovery review summary

3. Add a review artifact writer in `backend/app/benchmark/reporting.py`.
   Add one helper such as:
   - `write_recovery_review_report(result, report_dir, filename="recovery-review.json") -> str`
   The helper must:
   - reuse the existing report sanitizer path
   - write sorted UTF-8 JSON
   - preserve the existing forbidden-key filtering behavior
   - raise `BenchmarkHarnessError` on write failure

4. Implement `backend/app/benchmark/recovery_review.py`.
   Mirror the style of `release_gate.py` and `formal_verification.py` without refactoring them.
   The module should define:
   - constants for:
     - canonical case ID `family_route_failure_v1`
     - output root `var/recovery-reviews`
     - trace filename
     - latest alias filename `latest-family_route_failure_v1-review.json`
   - a typed runtime error such as `RecoveryReplayReviewError`
   - the runner function `run_recovery_replay_review(...)`
   - `main()` for CLI use
   - success and failure summary formatters

5. Implement the canonical review flow inside `run_recovery_replay_review(...)`.
   The exact sequence should be:
   - bootstrap runtime with `docker compose up -d postgres redis`
   - wait for PostgreSQL and Redis
   - run `python -m alembic upgrade head`
   - create a unique run directory under `var/recovery-reviews/recovery-review-<uuid>/`
   - instantiate `BenchmarkHarness` with:
     - `report_dir=run_directory`
     - `trace_buffer_path=run_directory / "review-traces.jsonl"`
   - run `load_benchmark_case("family_route_failure_v1")`
   - run `source_result = harness.run_case(case)`
   - assert `source_result.run_id` and `source_result.report_path` are present
   - instantiate `BenchmarkReplayHarness` with:
     - `replay_report_dir=run_directory / "replays"`
   - run `replay_result = replay_harness.replay_report(source_result.report_path)`
   - open `InternalObservabilityService(session).get_run_summary(source_result.run_id)`
   - build the compact recovery-review summary from:
     - `benchmark_artifact_summary`
     - `recovery_path_summary`
   - compute the three exact checks:
     - `benchmark_failure_path`
     - `replay_matches_source_report`
     - `observability_links_source_report`
   - derive aggregate `status`:
     - `passed` if all checks pass
     - `failed` if execution completed but one or more checks fail
     - `error` if orchestration could not complete
   - write the aggregate artifact
   - refresh the latest alias only for `passed`

6. Keep the exact closure invariants narrow and explicit.
   In `backend/app/benchmark/recovery_review.py`, do not infer or soften these checks:
   - source benchmark result:
     - `status == "passed"`
     - `workflow_status == "failed"`
     - `action_count == 0`
     - `failure_chain_summary.profile_id == "route_unavailable_v0"`
     - `failure_chain_summary.injected_effects == ["check_route:route_infeasible:failed"]`
     - `failure_chain_summary.recovery_actions == ["stop_safely"]`
   - replay result:
     - `status == "passed"`
     - `mismatches == []`
     - `failure_chain_signature == ["check_route:route_infeasible:failed"]`
   - observability result:
     - `benchmark_artifact_summary.case_id == "family_route_failure_v1"`
     - `benchmark_artifact_summary.report_path == source_result.report_path`
     - `recovery_path_summary.attempt_count == 1`
     - `recovery_path_summary.max_attempts == 2`
     - first attempt `recovery_action == "stop_safely"`
     - `recovery_path_summary.replay_source.case_id == "family_route_failure_v1"`
     - `recovery_path_summary.replay_source.benchmark_report_path == source_result.report_path`

7. Add the thin CLI wrapper in `scripts/run_recovery_replay_review.py`.
   Match the existing script pattern exactly:
   - prepend repo root to `sys.path`
   - import `main` from `backend.app.benchmark.recovery_review`
   - exit with `SystemExit(main())`

8. Add integration coverage in `tests/integration/test_recovery_replay_review.py`.
   Use real PostgreSQL and Redis like the existing benchmark/replay integration tests.
   Cover the single canonical flow:
   - run the new runner against `family_route_failure_v1`
   - assert aggregate `status == "passed"`
   - assert source report exists
   - assert replay report exists
   - assert latest alias exists
   - assert aggregate artifact JSON is sanitized
   - assert `benchmark_failure_path`, `replay_matches_source_report`, and `observability_links_source_report` are all present and true
   - assert `recovery_review.replay_source.benchmark_report_path == source_report_path`

9. Update docs only after the code and tests are stable.
   In `README.md`:
   - add one short `Recovery Replay Review` section near the benchmark/release-verification area
   - show the single command
   - name the canonical case
   - mention the output directory and latest alias
   - note that this is a reviewer-closure flow, not a replay UI
   In `docs/WEB_DEMO_README.md`:
   - add one short paragraph under internal observability review that says the new script emits a `run_id` and source benchmark report path that can be cross-checked with the existing internal observability surface

10. Verify the final behavior end-to-end.
    Run the focused unit tests, the focused integration tests, and the new script itself.
    Confirm:
    - CLI exit code is `0`
    - aggregate status is `passed`
    - latest alias points to the new passed review artifact
    - no `var/` output is staged

## 6. Testing Plan

- Unit tests:
  - `tests/test_recovery_replay_review.py`
  - keep `tests/test_benchmark_replay.py` green
  - keep `tests/test_observability.py` green
  - keep `tests/test_benchmark_harness.py` green
- Integration tests:
  - `tests/integration/test_recovery_replay_review.py`
  - keep `tests/integration/test_benchmark_replay_gateway.py` green for the canonical failure replay path
  - keep `tests/integration/test_observability_gateway.py` green for `recovery_path_summary`
  - keep `tests/integration/test_benchmark_harness_gateway.py` green for `family_route_failure_v1`
- Smoke tests:
  - `python scripts/run_recovery_replay_review.py`
- Explicit non-tests:
  - no frontend tests
  - no new HTTP route tests
  - no suite membership changes
  - no release-gate/formal-verification contract changes

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_recovery_replay_review.py tests/test_benchmark_replay.py tests/test_observability.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_recovery_replay_review.py tests/integration/test_benchmark_replay_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py -k "family_route_failure or recovery_replay_review" -q
python scripts/run_recovery_replay_review.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add recovery replay review closure
```

Expected commands:

```bash
git status --short
git switch -c codex/recovery-replay-review-closure-v0
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/reporting.py
git add backend/app/benchmark/recovery_review.py
git add backend/app/benchmark/__init__.py
git add scripts/run_recovery_replay_review.py
git add tests/test_recovery_replay_review.py
git add tests/integration/test_recovery_replay_review.py
git add README.md
git add docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: add recovery replay review closure"
git push -u origin codex/recovery-replay-review-closure-v0
```

The implementer must confirm the staged set does not include:

- `.gitignore`
- `docs/COMPETITION_SUBMISSION_DESIGN.md`
- `docs/TASK_WORKFLOW_PROMPTS.md`
- `docs/artifacts/`
- `qc`
- any generated `var/` file
- any secret or local `.env` file

## 9. Out-of-scope Changes

- Do not modify benchmark case JSON fixtures.
- Do not modify benchmark suite IDs or suite memberships.
- Do not change replay comparison semantics in `backend/app/benchmark/replay.py`.
- Do not change internal observability route shapes or frontend pages.
- Do not refactor shared bootstrap logic across the existing runners.
- Do not add arbitrary case selection or suite-wide review batching.
- Do not add new dependencies or migrations.
- Do not commit generated benchmark, replay, or review artifacts from `var/`.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/067-recovery-replay-review-closure-v0.md`.
- [ ] The runner is pinned to the canonical `family_route_failure_v1` closure path.
- [ ] The source benchmark report, replay report, and aggregate review artifact are all written.
- [ ] The aggregate artifact contains exactly the three named checks.
- [ ] The aggregate artifact status becomes `passed` only when all three checks pass.
- [ ] The source benchmark and internal observability report paths match exactly.
- [ ] The replay run consumes the written source report from disk, not only the in-memory result.
- [ ] The latest alias refreshes only on success.
- [ ] The artifact output is sanitized.
- [ ] Existing replay, observability, and benchmark harness behavior stayed green.
- [ ] No frontend, API, fixture, suite, dependency, or migration scope leaked into the task.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or generated `var/` artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The aggregate review artifact path.
- The latest alias path.
- The source benchmark report path.
- The replay report path.
- The source run ID.
- The three explicit check results:
  - `benchmark_failure_path`
  - `replay_matches_source_report`
  - `observability_links_source_report`
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no benchmark fixture, suite, API, or frontend behavior changed.
- Confirmation that no `var/` artifact was staged or committed.
- Any narrow follow-up limitations, especially that arbitrary case selection, replay browsing, and broader recovery UI remain separate future work.
