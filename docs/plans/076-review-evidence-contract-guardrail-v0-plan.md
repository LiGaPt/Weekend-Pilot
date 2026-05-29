# Plan: 076 V1.5 Review Evidence Contract Guardrail v0

## 1. Spec Reference

Spec file:

```text
docs/specs/076-review-evidence-contract-guardrail-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/review-evidence-package-cleanup-v0`.
- Latest commit is:

  ```text
  ecd23a1 docs: clean up v1.5 review evidence package
  ```

- `docs/specs/` and `docs/plans/` are continuous and fully matched through Task `075`.
- The latest formal task on disk is:
  - `075-review-evidence-package-cleanup-v0`
- The latest commit matches that latest task and there is no newer unfinished formal spec/plan to continue.
- The current worktree is clean.
- Task `075` already aligned the official docs manually:
  - `README.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `.gitignore`
- The four canonical latest alias artifacts already exist locally and currently reflect passing evidence:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json` -> `release_gate_v1`, `15/15 passed`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json` -> `all_registered`, `21/21 passed`, coverage gate passed
  - `var/formal-benchmarks/latest-all_registered-run-report.json` -> `all_registered`, `21/21 passed`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json` -> `family_route_failure_v1`, review passed
- There is currently no script or pytest module that verifies the reviewer-evidence doc contract and latest aliases together.
- Existing benchmark/recovery modules already provide the typed schemas and runner constants this task should reuse:
  - `backend/app/benchmark/schemas.py`
  - `backend/app/benchmark/formal_verification.py`
  - `backend/app/benchmark/release_gate.py`
  - `backend/app/benchmark/coverage_gate.py`
  - `backend/app/benchmark/recovery_review.py`
  - `backend/app/benchmark/internal_summary.py`

## 3. Files to Add

- `backend/app/benchmark/review_evidence.py` - repo-root V1.5 review evidence verifier with typed alias loading, doc contract checks, and CLI-facing result formatting.
- `scripts/verify_review_evidence.py` - thin repo-root wrapper that imports the verifier `main()` and exits with its code.
- `tests/test_review_evidence.py` - focused unit tests for passing and failing doc/alias contract cases using temporary repo fixtures.

## 4. Files to Modify

- `README.md` - add one concise additive note that the pinned V1.5 evidence package can be checked with `python scripts/verify_review_evidence.py`.
- `docs/V1_5_REVIEW_EVIDENCE.md` - add one short verification section for the new checker command while preserving the existing four-command evidence table.

## 5. Implementation Steps

1. Re-read the current manual contract before coding.
   Inspect:
   - `README.md`
   - `docs/V1_5_REVIEW_EVIDENCE.md`
   - `docs/COMPETITION_SUBMISSION_DESIGN.md`
   - `.gitignore`
   - `docs/specs/075-review-evidence-package-cleanup-v0.md`
   - `backend/app/benchmark/internal_summary.py`
   Lock the exact strings and paths that the new verifier must enforce.

2. Define the canonical contract in one new backend module.
   In `backend/app/benchmark/review_evidence.py`, add:
   - repo-root path constants
   - canonical command-to-alias mapping
   - official tracked doc list
   - required `.gitignore` entries
   - forbidden stale artifact string
   - expected suite / case IDs for the four aliases
   Keep this module self-contained; do not scatter the contract across multiple files.

3. Add typed result / error structures and file-loading helpers.
   The module should expose:
   - one error type for verification failures
   - one result object that captures pass/fail status, checked docs, checked aliases, and failure messages
   - helper functions to read UTF-8 text files
   - helper functions to load JSON payloads and validate them with Pydantic
   Follow the style used by `backend/app/benchmark/internal_summary.py` and the existing `run_*` modules.

4. Implement document contract checks.
   Add explicit checks for:
   - `README.md` contains `docs/V1_5_REVIEW_EVIDENCE.md`
   - `docs/V1_5_REVIEW_EVIDENCE.md` contains the exact four commands
   - `docs/V1_5_REVIEW_EVIDENCE.md` contains the exact four latest alias paths
   - `docs/V1_5_REVIEW_EVIDENCE.md` contains the `docs/artifacts/` / `var/` source-of-truth wording
   - `docs/COMPETITION_SUBMISSION_DESIGN.md` points to `docs/V1_5_REVIEW_EVIDENCE.md`
   - `docs/COMPETITION_SUBMISSION_DESIGN.md` contains the same four latest alias paths
   - official docs do not contain `docs/artifacts/benchmark-all-registered-formal-report.json`
   - `.gitignore` contains the required ignore entries
   Do not check historical specs/plans; this verifier is only for the official tracked reviewer/submission surfaces and ignore contract.

5. Implement latest-alias contract checks with structured parsing.
   - Use `BenchmarkRunReport.model_validate(...)` for:
     - `latest-release_gate_v1-run-report.json`
     - `latest-coverage_gate_v1_5-run-report.json`
     - `latest-all_registered-run-report.json`
   - Use `RecoveryReplayReviewResult.model_validate(...)` for:
     - `latest-family_route_failure_v1-review.json`
   - Enforce the suite / case / status rules from the spec.
   - For release-gate and coverage-gate reports, inspect raw JSON as needed for additive top-level keys:
     - `release_gate_evaluation.gate_id == "release_gate_v1"`
     - `coverage_gate_evaluation.gate_id == "coverage_gate_v1_5"`
   Do not assert nested absolute `report_path` values.

6. Make failures actionable and deterministic.
   - Map each alias to the exact rerun command from `docs/V1_5_REVIEW_EVIDENCE.md`.
   - If an alias file is missing or invalid, the failure output must include:
     - alias path
     - reason
     - rerun command
   - Keep success output compact:
     - one header line
     - checked-doc summary
     - checked-alias summary
   - `main()` must return `0` on pass and `1` on any failure.

7. Add the repo-root wrapper script.
   Create `scripts/verify_review_evidence.py` using the same pattern as the existing `scripts/run_*.py` files:
   - compute `REPO_ROOT`
   - add it to `sys.path`
   - import `main` from `backend.app.benchmark.review_evidence`
   - `raise SystemExit(main())`

8. Add focused unit tests in `tests/test_review_evidence.py`.
   Build temporary fake repo fixtures that include only the files the verifier needs.
   Cover at least:
   - passing contract with fake docs and fake alias JSON files
   - failure when `docs/V1_5_REVIEW_EVIDENCE.md` is missing one required command
   - failure when `docs/COMPETITION_SUBMISSION_DESIGN.md` contains the stale `docs/artifacts/...` path
   - failure when `.gitignore` is missing one required ignore rule
   - failure when the release-gate alias has the wrong suite ID or missing `release_gate_evaluation`
   - failure when the recovery review alias has the wrong `case_id` or non-passing `status`
   - `main()` returns non-zero and prints failure text on invalid repo fixtures
   Keep the tests independent of the real workspace `var/` directory.

9. Update the two official docs minimally.
   - In `docs/V1_5_REVIEW_EVIDENCE.md`, add one short “Verification” section after the existing command/ownership guidance:
     - `python scripts/verify_review_evidence.py`
     - one sentence that it checks official docs and the four current latest aliases before submission
   - In `README.md`, update the existing V1.5 reviewer-evidence pointer with one concise follow-up sentence naming the verifier command.
   Do not duplicate the full four-command matrix into README.

10. Run focused verification before staging.
    Required:
    - `python -m pytest tests/test_review_evidence.py -q`
    - `python scripts/verify_review_evidence.py`
    - `git diff --check`
    - `git status --short`
    If the smoke verifier fails on the current real repo, only make the minimum direct fix required to bring the already-intended `075` contract back into alignment. Do not broaden scope.

11. Stage only the intended task files.
    The staged set should be exactly:
    - `backend/app/benchmark/review_evidence.py`
    - `scripts/verify_review_evidence.py`
    - `tests/test_review_evidence.py`
    - `README.md`
    - `docs/V1_5_REVIEW_EVIDENCE.md`
    Do not stage:
    - `var/`
    - `.env`
    - `docs/artifacts/`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/V1_DEVELOPMENT_REPORT.md`
    - unrelated benchmark/frontend/runtime files

12. Commit on a fresh task branch.
    Create a new branch from the current clean `075` state and commit with the message from the spec.

## 6. Testing Plan

- Unit tests:
  - `tests/test_review_evidence.py`
    - passing verifier contract on a fake repo fixture
    - missing required doc string failure
    - stale `docs/artifacts/...` reference failure
    - missing `.gitignore` entry failure
    - wrong suite / case / status failure for alias payloads
    - `main()` exit-code coverage

- Integration tests:
  - No new runtime integration tests are required.
  - Do not rerun full benchmark suites for this task.

- Smoke tests:
  - `python scripts/verify_review_evidence.py` against the real repo root
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_review_evidence.py -q
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add review evidence contract guardrail
```

Expected commands:

```bash
git status --short
git switch -c codex/review-evidence-contract-guardrail-v0
python -m pytest tests/test_review_evidence.py -q
python scripts/verify_review_evidence.py
git diff --check
git add backend/app/benchmark/review_evidence.py
git add scripts/verify_review_evidence.py
git add tests/test_review_evidence.py
git add README.md
git add docs/V1_5_REVIEW_EVIDENCE.md
git diff --cached --check
git commit -m "feat: add review evidence contract guardrail"
git push -u origin codex/review-evidence-contract-guardrail-v0
```

The implementer must confirm:
- the branch base already contains `ecd23a1`
- no `var/` JSON artifact was staged
- no `.env` or secret file was staged

## 9. Out-of-scope Changes

- Do not change benchmark runner behavior in:
  - `backend/app/benchmark/formal_verification.py`
  - `backend/app/benchmark/release_gate.py`
  - `backend/app/benchmark/coverage_gate.py`
  - `backend/app/benchmark/recovery_review.py`
- Do not change suite membership, counts, thresholds, or artifact directory layout.
- Do not rewrite `docs/COMPETITION_SUBMISSION_DESIGN.md` unless the new verifier proves the current tracked doc is already out of contract; even then, only make the minimum direct fix.
- Do not add CI automation, pre-commit hooks, or GitHub workflow files.
- Do not modify `frontend/`, demo APIs, or user-facing workflow behavior.
- Do not commit generated caches, ignored `var/` outputs, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The task stayed focused on review-evidence contract validation.
- [ ] `backend/app/benchmark/review_evidence.py` exists and contains the canonical contract checks.
- [ ] `scripts/verify_review_evidence.py` exists and works from the repo root.
- [ ] `tests/test_review_evidence.py` covers both passing and failing cases.
- [ ] `README.md` includes the concise verifier pointer.
- [ ] `docs/V1_5_REVIEW_EVIDENCE.md` includes the new verification command.
- [ ] `docs/COMPETITION_SUBMISSION_DESIGN.md` was not broadened into a larger rewrite.
- [ ] No benchmark/runtime/frontend behavior changed.
- [ ] No `var/` artifact was committed.
- [ ] Verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back with:

- Changed files
- The final repo-root verification command
- The exact docs and alias paths verified by the new guardrail
- Verification commands and results
- Whether the real repo smoke check passed without additional doc fixes
- Confirmation that no `var/` artifact or local secret was staged
- Commit hash
- Push result
- Known limitations or follow-up tasks:
  - the verifier is a manual maintainer guardrail, not CI enforcement
  - if future tasks add new canonical evidence chains, this contract must be updated in both docs and code together
