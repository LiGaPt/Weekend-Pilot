# Plan: 075 V1.5 Review Evidence Package Cleanup v0

## 1. Spec Reference

Spec file:

```text
docs/specs/075-review-evidence-package-cleanup-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/benchmark-matrix-coverage-threshold-v0`.
- Latest commit is:

  ```text
  fac1a35 feat: add benchmark matrix coverage threshold
  ```

- `docs/specs/` and `docs/plans/` are continuous and fully matched through Task `074`.
- The latest commit matches the latest formal task on disk:
  - `074-benchmark-matrix-coverage-threshold-v0`
- There is no newer unfinished formal spec/plan/branch to continue.
- Current canonical generated evidence already exists locally at:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Current latest evidence state is already aligned with Task `074`:
  - `release_gate_v1`: `15/15 passed`
  - `all_registered` formal verification: `21/21 passed`
  - `coverage_gate_v1_5`: pass on the same `21`-case inventory
- Current worktree has local dirty files that are not formal task outputs:
  - modified `.gitignore`
  - untracked `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - untracked `docs/TASK_WORKFLOW_PROMPTS.md`
  - untracked `docs/V1_DEVELOPMENT_REPORT.md`
  - untracked `docs/artifacts/`
  - untracked `qc`
- `docs/artifacts/benchmark-all-registered-formal-report.json` is a stale copied snapshot:
  - `all_registered`
  - `17/17 passed`
  - last-modified before Task `073` / `074`
- The repository already documents that formal benchmark artifacts stay under `var/`, not under `docs/artifacts/`.

## 3. Files to Add

- `docs/V1_5_REVIEW_EVIDENCE.md` - canonical V1.5 reviewer-evidence entrypoint with exact commands, latest-alias paths, and ownership rules.

## 4. Files to Modify

- `.gitignore` - ignore local scratch docs/artifacts and `qc` while preserving `.env` and `var/` ignore behavior.
- `README.md` - add one concise pointer to `docs/V1_5_REVIEW_EVIDENCE.md`.
- `docs/COMPETITION_SUBMISSION_DESIGN.md` - convert the existing untracked draft into the official tracked submission-facing doc and replace stale `docs/artifacts/` evidence references.

## 5. Implementation Steps

1. Read the current canonical evidence contract from the repo, not from local scratch docs.
   Use:
   - `README.md`
   - `docs/specs/061-formal-verification-script.md`
   - `docs/specs/065-benchmark-release-gate-v0.md`
   - `docs/specs/067-recovery-replay-review-closure-v0.md`
   - `docs/specs/071-release-gate-latency-slo-v0.md`
   - `docs/specs/074-benchmark-matrix-coverage-threshold-v0.md`
   Also inspect the four current latest alias files under `var/` to confirm the exact paths and current V1.5 evidence state.

2. Add `docs/V1_5_REVIEW_EVIDENCE.md` as the single canonical reviewer doc.
   Keep it concise and practical. It should include:
   - what the doc is for
   - the exact four repo-root commands
   - the exact four latest-alias paths
   - a short “when to rerun vs when to cite latest alias” note
   - one ownership table or section classifying:
     - official tracked docs
     - local scratch docs
     - generated runtime evidence
     - secrets / local env files
   The doc must explicitly say `docs/artifacts/` is not source-of-truth evidence.

3. Update `docs/COMPETITION_SUBMISSION_DESIGN.md` in place instead of creating a duplicate submission doc.
   Keep it short and submission-facing.
   Required edits:
   - remove the stale `docs/artifacts/benchmark-all-registered-formal-report.json` reference
   - replace it with a concise reference to `docs/V1_5_REVIEW_EVIDENCE.md`
   - align its evidence wording with the canonical latest aliases under `var/`
   - remove or update any stale `17/17`-era wording
   Do not expand it into a long internal report.

4. Add one concise README pointer.
   Place it near the benchmark/review governance sections, not at the top of the file.
   The purpose is discoverability:
   - reviewers and future task sessions should know where the pinned V1.5 evidence package lives
   - do not duplicate the entire evidence matrix inside README

5. Tighten `.gitignore` with specific local-scratch entries.
   Add exact ignores for:
   - `docs/artifacts/`
   - `docs/TASK_WORKFLOW_PROMPTS.md`
   - `docs/V1_DEVELOPMENT_REPORT.md`
   - `qc`
   Preserve existing `.env` and `var/` rules.
   Do not add broad ignores that could hide official docs under `docs/`.

6. Do not edit the contents of the local scratch docs you are deciding to ignore.
   In this task:
   - do not revise `docs/V1_DEVELOPMENT_REPORT.md`
   - do not revise `docs/TASK_WORKFLOW_PROMPTS.md`
   - do not rewrite files under `docs/artifacts/`
   - do not move `qc`
   Only establish ownership and ignore behavior for them.

7. Keep all runtime and benchmark code untouched.
   Do not modify anything under:
   - `backend/`
   - `scripts/`
   - `tests/`
   - `frontend/`
   The task should remain docs/hygiene-only.

8. Verify the new doc references and ignore rules before staging.
   Confirm:
   - the four commands appear in the official tracked docs
   - the four canonical latest-alias paths appear in the official tracked docs
   - `docs/artifacts/benchmark-all-registered-formal-report.json` no longer appears in official tracked docs
   - ignored scratch paths are matched by `.gitignore`
   - official docs remain trackable

9. Stage only the intended task files.
   The staged set should be exactly:
   - `.gitignore`
   - `README.md`
   - `docs/COMPETITION_SUBMISSION_DESIGN.md`
   - `docs/V1_5_REVIEW_EVIDENCE.md`
   Do not stage:
   - `docs/V1_DEVELOPMENT_REPORT.md`
   - `docs/TASK_WORKFLOW_PROMPTS.md`
   - `docs/artifacts/`
   - `qc`
   - any `var/` output

10. Commit with the docs-only commit message from the spec.
    Push on a fresh task branch based on the current `074` branch state.

## 6. Testing Plan

- Unit tests:
  - No new unit tests are expected because this task does not change runtime code.
  - Run focused existing regression tests that protect the canonical alias contracts:
    - `tests/test_benchmark_release_gate.py`
    - `tests/test_benchmark_coverage_gate.py`
    - `tests/test_formal_verification.py`
    - `tests/test_recovery_replay_review.py`

- Integration tests:
  - No new integration tests are required.
  - Do not rerun full benchmark suites solely for this docs/ignore cleanup task.

- Smoke tests:
  - `rg` checks for the exact commands and canonical latest-alias paths in the tracked docs
  - `git check-ignore -v` for ignored scratch paths
  - `git ls-files --error-unmatch` for official tracked docs
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_release_gate.py tests/test_benchmark_coverage_gate.py tests/test_formal_verification.py tests/test_recovery_replay_review.py -q
rg -n "python scripts/run_benchmark_release_gate.py|python scripts/run_benchmark_coverage_gate.py|python scripts/run_formal_verification.py|python scripts/run_recovery_replay_review.py" README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
rg -n "latest-release_gate_v1-run-report.json|latest-all_registered-run-report.json|latest-coverage_gate_v1_5-run-report.json|latest-family_route_failure_v1-review.json" README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
rg -n "docs/artifacts/benchmark-all-registered-formal-report.json" README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
# Expected: no matches
git check-ignore -v docs/artifacts/benchmark-all-registered-formal-report.json docs/TASK_WORKFLOW_PROMPTS.md docs/V1_DEVELOPMENT_REPORT.md qc .env var/formal-benchmarks/latest-all_registered-run-report.json
git ls-files --error-unmatch .gitignore README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
docs: clean up v1.5 review evidence package
```

Expected commands:

```bash
git status --short
git branch --show-current
git log --oneline -n 1
git switch -c codex/review-evidence-package-cleanup-v0
git add .gitignore
git add README.md
git add docs/COMPETITION_SUBMISSION_DESIGN.md
git add docs/V1_5_REVIEW_EVIDENCE.md
git diff --cached --check
git commit -m "docs: clean up v1.5 review evidence package"
git push -u origin codex/review-evidence-package-cleanup-v0
```

The implementer must confirm that:
- the branch base already contains `fac1a35`
- no ignored scratch file was force-added
- no `var/` JSON or `.env` file was staged

## 9. Out-of-scope Changes

- Do not change any benchmark/runtime/frontend code.
- Do not refresh `var/formal-benchmarks/` or `var/recovery-reviews/` outputs in this task.
- Do not track `docs/artifacts/benchmark-all-registered-formal-report.json`.
- Do not revise the contents of `docs/V1_DEVELOPMENT_REPORT.md`.
- Do not revise the contents of `docs/TASK_WORKFLOW_PROMPTS.md`.
- Do not create new generic publishing automation, CI checks, or scripts.
- Do not alter roadmap, blueprint, spec numbering, or benchmark governance logic.
- Do not commit generated caches, runtime directories, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The task stayed docs/hygiene-only.
- [ ] `docs/V1_5_REVIEW_EVIDENCE.md` exists and is the canonical reviewer-evidence doc.
- [ ] The exact four commands are present in the official tracked docs.
- [ ] The exact four canonical latest-alias paths are present in the official tracked docs.
- [ ] `docs/COMPETITION_SUBMISSION_DESIGN.md` no longer cites `docs/artifacts/benchmark-all-registered-formal-report.json`.
- [ ] `README.md` points to the new reviewer-evidence doc.
- [ ] `.gitignore` ignores `docs/artifacts/`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, and `qc`.
- [ ] `.env` and `var/` remain ignored.
- [ ] No file under `backend/`, `scripts/`, `tests/`, or `frontend/` changed.
- [ ] No `var/` artifact was committed.
- [ ] Focused regression tests and smoke checks passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back with:

- Changed files
- The final tracked reviewer-entrypoint doc path
- The final ignored local-scratch paths
- The exact four commands and four latest-alias paths confirmed in the docs
- Verification commands and results
- Confirmation that `docs/artifacts/benchmark-all-registered-formal-report.json` is no longer referenced by official tracked docs
- Confirmation that `docs/V1_DEVELOPMENT_REPORT.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/`, `qc`, `.env`, and `var/` were not staged
- Commit hash
- Push result
- Known limitations or follow-up tasks:
  - future benchmark expansions may require updating the reviewer-evidence doc again
  - if the team later wants published static evidence under `docs/`, that should be a separate task with an explicit artifact-publication contract
