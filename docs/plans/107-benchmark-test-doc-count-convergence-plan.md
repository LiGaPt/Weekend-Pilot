# Plan: 107 Benchmark test/doc count convergence

## 1. Spec Reference

Spec file:

```text
docs/specs/107-benchmark-test-doc-count-convergence.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/106-v2-integrity-release-verification`.
- Latest task docs are continuous and matched through `106`.
- Latest commit is `f01114d chore: refresh v2 integrity release evidence`, which corresponds to Task `106`.
- There is no tracked `107` spec or `107` plan yet.
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Current suite truth is defined in `backend/app/benchmark/suites.py`:
  - `release_gate_v1 = 15`
  - `v2_integrity = 18`
  - `all_registered = 28`
- Current harness-level truth is already reflected in tests such as `tests/test_benchmark_harness.py`, which expects the V2 integrity coverage summary:
  - `case_count = 18`
  - `memory_case_count = 6`
  - `recovery_case_count = 6`
  - `continuation_case_count = 3`
  - `robustness_case_count = 4`
  - `l4_case_count = 1`
- Current focused backend verification command:
  - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
  currently reports `23 passed`.

## 3. Files to Add

- None.

## 4. Files to Modify

- `tests/integration/test_formal_verification.py` - replace stale `17` count assertions and related file-count assumptions with current `all_registered = 28` truth.
- `tests/integration/test_benchmark_v2_integrity_gate.py` - replace stale `15` gate assertions and outdated integrity coverage summary with current `v2_integrity = 18` truth.
- `tests/test_benchmark_v2_taxonomy.py` - replace stale registered inventory count assertions and update any hard-coded old V2 member-pool expectations that are meant to represent current repo truth.
- `tests/test_formal_verification.py` - update stubbed current-state formal-verification counts from `17` to `28` where the test is asserting canonical current behavior.
- `tests/test_benchmark_v2_integrity_gate.py` - update any stubbed current-state V2 gate count and integrity coverage expectations that still reflect the obsolete `15`-case suite.
- `tests/test_demo_support_scripts.py` - update README expectation from `15 passed` to the current actual focused test result.
- `README.md` - update the focused backend verification result wording to the current actual result; keep the benchmark inventory wording accurate and unchanged where already correct.

## 5. Implementation Steps

1. Reconfirm baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm the task starts from the committed `106` baseline and that unrelated untracked files remain untouched.

2. Reconfirm suite truth from code before touching tests.
   - Inspect `backend/app/benchmark/suites.py`.
   - Confirm:
     - `release_gate_v1` still contains 15 cases
     - `v2_integrity` contains 18 cases
     - `all_registered` contains 28 cases
   - Use existing harness tests such as `tests/test_benchmark_harness.py` as supporting truth for the current integrity coverage summary.

3. Update the failing integration test for formal verification.
   - In `tests/integration/test_formal_verification.py`:
     - change `case_count == 17` to `28`
     - change `passed_count == 17` to `28`
     - change JSON payload assertions from `17` to `28`
     - update the minimum generated case-report count if it assumes the old suite size

4. Update the failing integration test for the V2 integrity gate.
   - In `tests/integration/test_benchmark_v2_integrity_gate.py`:
     - change result count assertions from `15` to `18`
     - replace the stale `EXPECTED_INTEGRITY_COVERAGE` payload with:
       - `case_count = 18`
       - `memory_case_count = 6`
       - `recovery_case_count = 6`
       - `continuation_case_count = 3`
       - `robustness_case_count = 4`
       - `l4_case_count = 1`
     - keep gate identity, release-blocking behavior, and forbidden-text assertions unchanged

5. Update the stale taxonomy inventory test.
   - In `tests/test_benchmark_v2_taxonomy.py`:
     - change the full registered inventory assertion from `25` to `28`
     - inspect the hard-coded V2 member-pool fixture list and summary expectations
     - if the list is meant to mirror the current `v2_integrity` suite, expand it to the current 18-case suite and update summary counts accordingly
     - do not change taxonomy derivation behavior itself

6. Update unit tests that stub current formal-verification or V2 gate counts.
   - In `tests/test_formal_verification.py`:
     - change stubbed `case_count` / `passed_count` values that represent the current canonical `all_registered` suite from `17` to `28`
     - keep unique-run-dir and alias-copy semantics unchanged
   - In `tests/test_benchmark_v2_integrity_gate.py`:
     - update any current-state stubbed suite counts or integrity coverage expectations from the obsolete `15`-case truth to the current `18`-case truth
     - keep alias behavior, output formatting, and failure-path tests unchanged

7. Update README-focused support-script expectations.
   - In `README.md`:
     - keep current benchmark inventory lines that already state `28/28` and `18/18`
     - change the focused backend verification result from `` `15 passed` `` to `` `23 passed` ``
   - In `tests/test_demo_support_scripts.py`:
     - update the README assertion to expect `` `23 passed` ``
     - keep the existing assertions for `` `15/15` ``, `` `28/28` ``, `` `3/3` ``, and `` `24 passed` `` unchanged unless the README itself needs further truth-aligned edits

8. Do not broaden documentation edits.
   - Inspect active docs only if needed to verify whether any current-state doc besides `README.md` still claims `17` or `25` as present-day truth.
   - Do not rewrite archived task specs/plans under `docs/specs/` or `docs/plans/` to modernize historical numbers.

9. Run focused regression commands after edits.
   - Run:
     - `python -m pytest tests/integration/test_formal_verification.py tests/integration/test_benchmark_v2_integrity_gate.py -q`
     - `python -m pytest tests/test_benchmark_v2_taxonomy.py tests/test_formal_verification.py tests/test_benchmark_v2_integrity_gate.py -q`
     - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`

10. Perform final hygiene checks.
   - Run:
     - `git diff --check`
     - `git status --short`
   - Confirm only task-relevant files changed and unrelated untracked files remain untouched.

11. Commit the task.
   - Stage only the files actually changed for this task.
   - Commit with:
     - `git commit -m "test: align benchmark inventory expectations"`

## 6. Testing Plan

- Unit tests:
  - `tests/test_formal_verification.py`
    - canonical formal-verification count expectations align to current `all_registered`
  - `tests/test_benchmark_v2_integrity_gate.py`
    - canonical V2 gate count and integrity coverage expectations align to current `v2_integrity`
  - `tests/test_benchmark_v2_taxonomy.py`
    - registered inventory count aligns to current repo truth
  - `tests/test_demo_support_scripts.py`
    - README benchmark/test wording assertions match current text
- Integration tests:
  - `tests/integration/test_formal_verification.py`
    - full formal-verification runner reflects current `all_registered = 28`
  - `tests/integration/test_benchmark_v2_integrity_gate.py`
    - full V2 integrity gate runner reflects current `v2_integrity = 18`
- Smoke tests:
  - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
- Document review checks:
  - verify `README.md` focused test result matches the actual command output
  - verify README benchmark inventory wording still matches `15 / 18 / 28`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/integration/test_formal_verification.py tests/integration/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/test_benchmark_v2_taxonomy.py tests/test_formal_verification.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
test: align benchmark inventory expectations
```

Expected commands:

```bash
git status --short
git switch -c codex/107-benchmark-test-doc-count-convergence
git add tests/integration/test_formal_verification.py tests/integration/test_benchmark_v2_integrity_gate.py tests/test_benchmark_v2_taxonomy.py tests/test_formal_verification.py tests/test_benchmark_v2_integrity_gate.py tests/test_demo_support_scripts.py README.md
git diff --cached --check
git commit -m "test: align benchmark inventory expectations"
git push -u origin codex/107-benchmark-test-doc-count-convergence
```

The implementer must confirm unrelated untracked files, generated `var/` artifacts, `.env`, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not change `backend/app/benchmark/suites.py` suite membership.
- Do not change benchmark scoring, integrity coverage algorithms, pass-k formulas, formal-verification behavior, or recovery-review logic.
- Do not change `release_gate_v1` counts or wording except where current README already correctly states `15/15`.
- Do not rewrite archived specs/plans under `docs/specs/` or `docs/plans/` to modernize historical numbers.
- Do not add new docs, new tests unrelated to benchmark-count convergence, or new dependencies.
- Do not touch frontend code.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] All stale current-state benchmark count assertions were updated to current repo truth.
- [ ] The V2 integrity coverage summary expectations now match the current 18-case suite.
- [ ] `README.md` now reports the current focused backend result instead of `15 passed`.
- [ ] Required focused tests passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- exact files changed
- confirmed suite truth used for the fix (`release_gate_v1 = 15`, `v2_integrity = 18`, `all_registered = 28`)
- verification commands run and their results
- final focused backend test count reflected in README
- commit hash
- push result
- any unrelated residual failures discovered during verification
