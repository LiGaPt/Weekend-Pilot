# Plan: 099 Generic Recovery Replay v0

## 1. Spec Reference

Spec file:

```text
docs/specs/099-generic-recovery-replay-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/098-memory-governance-suite-v2`.
- Latest completed task is `098`, and latest commit `d418fcf feat: expand memory governance benchmark suite` matches that task.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `098`.
- There is no tracked `099` spec, plan, or implementation branch yet.
- The existing recovery replay tooling is implemented and green, but fixed to `family_route_failure_v1`:
  - `backend/app/benchmark/recovery_review.py`
  - `scripts/run_recovery_replay_review.py`
  - `tests/test_recovery_replay_review.py`
  - `tests/integration/test_recovery_replay_review.py`
- Existing canonical reviewer evidence depends on:
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
  - `RecoveryReplayReviewResult`
  - `python scripts/run_recovery_replay_review.py`
- Existing recovery-capable benchmark inventory is already present in the `recovery_focused` suite:
  - `family_route_failure_v1`
  - `family_route_and_dining_unavailable_v1`
  - `rainy_day_ticket_sold_out_v1`
- Existing evidence-verification and README/demo-support tests assume the family alias remains canonical.
- The worktree currently has unrelated untracked docs files. They are out of scope and must remain unstaged:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None required if the implementation keeps the generic runner, run-level schema, and CLI parsing inside existing files.

## 4. Files to Modify

- `backend/app/benchmark/recovery_review.py` - refactor the family-only runner into reusable per-case execution plus generic selection, aggregate run reporting, and CLI-mode summaries.
- `backend/app/benchmark/schemas.py` - add additive run-level recovery replay review models while keeping `RecoveryReplayReviewResult` compatible.
- `backend/app/benchmark/__init__.py` - export any new run-level schema or generic runner that should be part of the benchmark package surface.
- `scripts/run_recovery_replay_review.py` - keep the thin wrapper but support the updated CLI entrypoint.
- `tests/test_recovery_replay_review.py` - update unit tests for generic case mode, suite mode, selector validation, alias refresh rules, and compatibility wrapper behavior.
- `tests/integration/test_recovery_replay_review.py` - expand integration coverage beyond the family case to include one non-family recovery case and one suite run.
- `README.md` - document additive `--case-id` and `--suite-id` usage while preserving the canonical default family reviewer flow.
- `docs/WEB_DEMO_README.md` - clarify that generic selectors are additive tooling and that the family no-arg path remains the canonical reviewer closure path.

## 5. Implementation Steps

1. Read the current single-case runner and lock the compatibility constraints before editing.
   Confirm from the current code and tests:
   - no-arg script means `family_route_failure_v1`
   - alias path is `latest-family_route_failure_v1-review.json`
   - `RecoveryReplayReviewResult` is the schema parsed by review-evidence checks
   - suite inventory comes from `backend/app/benchmark/suites.py`

2. Write failing unit tests first in `tests/test_recovery_replay_review.py`.
   Add focused tests for:
   - explicit `case_id` runs a non-family recovery case and writes `latest-<case_id>-review.json`
   - `suite_id="recovery_focused"` runs all suite cases and returns an aggregate run report
   - `suite_id="failures"` resolves to the same suite
   - both selectors together raise an error
   - a non-recovery case is rejected before replay execution
   - existing `run_recovery_replay_review()` wrapper still returns the single family case result and keeps the old alias path

3. Add additive run-level schema models in `backend/app/benchmark/schemas.py`.
   Keep `RecoveryReplayReviewResult` unchanged except for strictly additive optional fields if absolutely needed.
   Add new models for:
   - selection mode metadata
   - per-case run summary item if needed
   - aggregate run report with:
     - `schema_version`
     - `status`
     - `selection_mode`
     - `case_id` or `suite_id`
     - `requested_case_ids`
     - `run_directory`
     - `report_path`
     - `passed_count`
     - `failed_count`
     - `error_count`
     - `case_results`

4. Refactor `backend/app/benchmark/recovery_review.py` into two layers.
   Keep backward compatibility by preserving:
   - `run_recovery_replay_review(...) -> RecoveryReplayReviewResult`
   Add generic execution through a new function such as:
   - `run_generic_recovery_replay_review(...) -> RecoveryReplayReviewRunReport`
   Internal structure should be:
   - selector validation helper
   - recovery-capable case validation helper
   - per-case runner helper that does what the current family-only runner does
   - aggregate run writer and summary formatter
   This refactor must avoid changing replay semantics or benchmark harness behavior.

5. Replace family-only validation constants with selected-case-driven validation.
   Keep these family-only constants only where they are still truly canonical:
   - default case ID
   - default alias path
   For per-case review checks:
   - derive expected workflow status and expected recovery action from the loaded case
   - derive expected failure profile from `case.failure_profile`
   - compare replay failure signatures to the source benchmark’s injected effects instead of to one fixed route signature
   - use the last recovery attempt in observability summary as the action-status check target

6. Implement deterministic output layout.
   For single-case mode:
   - keep the existing shape in `recovery-review-<uuid>/`
   - write source report at the run root
   - write replay report under `replays/`
   - write `review-traces.jsonl`
   - write `recovery-review.json`
   For suite mode:
   - create `recovery-review-<uuid>/recovery-review-run.json`
   - create `cases/<case_id>/` per case
   - run each case with its own `report_dir=cases/<case_id>`
   - keep each case’s source report, replay report, trace buffer, and `recovery-review.json` isolated inside its case directory

7. Implement latest-alias refresh rules conservatively.
   - Single-case pass:
     - refresh `latest-<case_id>-review.json`
   - Single-case fail/error:
     - do not refresh alias
   - Suite pass/fail/error:
     - refresh only the per-case aliases for the case results that individually passed
     - never overwrite a failed or errored case alias
   - Preserve the exact behavior and path for the family default alias

8. Update CLI parsing in the benchmark module and keep the script wrapper thin.
   Add `argparse` handling in the benchmark module `main()`:
   - no args -> current family default flow
   - `--case-id <case_id>`
   - `--suite-id <suite_id>`
   - reject both together
   The script file should remain a minimal import-and-exit wrapper.

9. Expand integration coverage in `tests/integration/test_recovery_replay_review.py`.
   Add or update tests for:
   - explicit single-case run on `family_route_and_dining_unavailable_v1`
   - suite run on `recovery_focused`
   Assertions should cover:
   - aggregate run status and counts
   - written run report path
   - per-case review artifact paths
   - refreshed latest aliases
   - persisted report sanitization
   - family default compatibility still works

10. Update docs after code and tests are stable.
    In `README.md`:
    - keep the family alias as the canonical reviewer evidence example
    - add a short additive note showing:
      - `python scripts/run_recovery_replay_review.py --case-id family_route_and_dining_unavailable_v1`
      - `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`
    In `docs/WEB_DEMO_README.md`:
    - keep the family flow as the reviewer-facing closure path
    - add one short note that generic selectors exist for engineering verification and comparison, not as a new UI workflow

11. Run focused verification and inspect git state carefully.
    - run unit tests
    - run integration tests
    - run three CLI smoke commands
    - run `git diff --check`
    - confirm no `var/` output or unrelated local docs are staged

## 6. Testing Plan

- Unit tests:
  - `tests/test_recovery_replay_review.py`
  - cover selector parsing and validation
  - cover generic single-case alias refresh
  - cover suite aggregate counts and status
  - cover compatibility wrapper behavior
- Integration tests:
  - `tests/integration/test_recovery_replay_review.py`
  - cover explicit non-family recovery case
  - cover `recovery_focused` suite run
  - keep default family path green
- Compatibility tests:
  - `tests/test_review_evidence.py`
  - `tests/test_demo_support_scripts.py`
  - verify family alias and reviewer-facing evidence assumptions remain intact
- Smoke tests:
  - `python scripts/run_recovery_replay_review.py`
  - `python scripts/run_recovery_replay_review.py --case-id family_route_and_dining_unavailable_v1`
  - `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_recovery_replay_review.py tests/integration/test_recovery_replay_review.py -q
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/run_recovery_replay_review.py
python scripts/run_recovery_replay_review.py --case-id family_route_and_dining_unavailable_v1
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: generalize recovery replay review
```

Expected commands:

```bash
git status --short
git switch -c codex/099-generic-recovery-replay-v0
git add backend/app/benchmark/recovery_review.py
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/__init__.py
git add scripts/run_recovery_replay_review.py
git add tests/test_recovery_replay_review.py
git add tests/integration/test_recovery_replay_review.py
git add README.md
git add docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: generalize recovery replay review"
git push -u origin codex/099-generic-recovery-replay-v0
```

The implementer must confirm the staged set does not include:

- `var/`
- `docs/NEW_WORKFLOW_PROMPT.md`
- `docs/TASK_INFO.md`
- `docs/superpowers/`
- any `.env` file
- any secrets or local-only artifacts

## 9. Out-of-scope Changes

- Do not modify `backend/app/benchmark/replay.py`.
- Do not modify benchmark case JSON contents.
- Do not modify benchmark suite membership or create new suites.
- Do not add frontend pages, internal API routes, or dashboard panels.
- Do not widen support to arbitrary non-recovery suites.
- Do not refresh formal release evidence or submission docs beyond the minimal README / WEB_DEMO_README notes required here.
- Do not add dependencies or migrations.
- Do not commit generated recovery-review outputs.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/099-generic-recovery-replay-v0.md`.
- [ ] The default no-arg recovery replay flow is unchanged for `family_route_failure_v1`.
- [ ] `latest-family_route_failure_v1-review.json` still exists and validates as `RecoveryReplayReviewResult`.
- [ ] Explicit `--case-id` works for another registered recovery case.
- [ ] Explicit `--suite-id recovery_focused` works and writes an aggregate run report.
- [ ] `--suite-id failures` resolves correctly.
- [ ] Non-recovery cases are rejected explicitly.
- [ ] The run-level schema is additive and does not replace the per-case schema.
- [ ] Per-case validation is driven by the selected case’s expected recovery metadata.
- [ ] Alias refresh happens only for passing case results.
- [ ] README and WEB_DEMO_README reflect additive generic usage without changing the canonical reviewer path.
- [ ] Required tests and smoke commands passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or generated `var/` artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The default family compatibility result.
- The explicit non-family case used for verification.
- The suite ID used for verification.
- The aggregate run report path for the suite run.
- The per-case latest alias paths refreshed during verification.
- The verification commands run and their results.
- The commit hash and push result.
- Confirmation that `latest-family_route_failure_v1-review.json` compatibility was preserved.
- Confirmation that no benchmark fixtures, replay semantics, frontend behavior, or generated `var/` outputs were committed.
