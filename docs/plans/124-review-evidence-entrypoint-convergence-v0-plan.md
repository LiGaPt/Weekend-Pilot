# Plan: 124 Review evidence entrypoint convergence v0

## 1. Spec Reference

Spec file:

```text
docs/specs/124-review-evidence-entrypoint-convergence-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap milestone:

```text
docs/NEXT_PHASE_ROADMAP.md
M1. 评测与观测基础设施
```

## 2. Current Repository Assumptions

- Current branch is `codex/review-evidence-entrypoint-convergence-v0`.
- Latest commit is `28efaf8 chore: converge review evidence entrypoint`.
- Latest implemented task is Task `124`.
- `docs/specs/` and `docs/plans/` are matched through Task `124` in the working tree, but the Task 124 spec and plan are currently untracked.
- Historical numbering has a shared gap at Task `122`, and there is a special `113.5` task; neither should be changed.
- The latest commit corresponds to Task 124 implementation but does not include the Task 124 spec / plan files.
- The next new task after this closure is likely Task `125 Final Mock World V2 verification`, but it should not start until Task 124 docs are tracked.
- Pre-existing unrelated untracked files must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- `docs/specs/124-review-evidence-entrypoint-convergence-v0.md` - tracked spec for the already implemented reviewer evidence entrypoint convergence task.
- `docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md` - tracked implementation plan for the already implemented reviewer evidence entrypoint convergence task.

## 4. Files to Modify

- None expected.

If inspection shows the untracked Task 124 docs conflict with the current committed implementation, modify only those two Task 124 docs to match the implementation and current six-artifact evidence contract.

## 5. Implementation Steps

1. Confirm baseline repository state.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -5`
   - Confirm latest commit is `28efaf8 chore: converge review evidence entrypoint`.
   - Confirm the Task 124 spec and plan are untracked.

2. Inspect the Task 124 docs before staging.
   - Read:
     - `docs/specs/124-review-evidence-entrypoint-convergence-v0.md`
     - `docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md`
   - Confirm both documents describe reviewer evidence entrypoint convergence, not final V2 release verification.
   - Confirm both documents mention the current six-artifact canonical evidence package.

3. Cross-check against committed implementation.
   - Inspect:
     - `docs/V1_5_REVIEW_EVIDENCE.md`
     - `docs/COMPETITION_SUBMISSION_DESIGN.md`
     - `backend/app/benchmark/review_evidence.py`
     - `tests/test_review_evidence.py`
   - Confirm the docs match the implemented Task 124 behavior:
     - reviewer entrypoint doc aligned to six canonical artifacts
     - verifier checks updated entrypoint wording
     - tests use the six-artifact fixture

4. Correct Task 124 docs only if needed.
   - If the untracked spec / plan still describe an older branch, old commit, or old four-alias package, update only those two docs.
   - Do not edit implementation files unless verification proves Task 124 itself is broken.
   - Do not create Task 125 docs in this task.

5. Run focused verification.
   - Run:
     - `python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q`
     - `python scripts/show_submission_evidence.py`
     - `python scripts/demo_preflight.py`
     - `python scripts/verify_review_evidence.py`
   - If a command fails because of missing or malformed canonical evidence alias files, rerun only the specific existing generator required for the missing alias and repeat verification.
   - If a command fails because of product behavior, stop and report; do not broaden the task.

6. Run hygiene checks.
   - Run:
     - `git diff --check`
     - `git status --short`
   - Confirm only the Task 124 spec and plan are intended for staging.
   - Confirm `var/`, `.env`, caches, and unrelated untracked docs are not staged.

7. Stage only the Task 124 docs.
   - Run:
     - `git add docs/specs/124-review-evidence-entrypoint-convergence-v0.md docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md`
   - Run:
     - `git diff --cached --check`
     - `git status --short`
   - Confirm the staged set excludes:
     - `docs/NEW_WORKFLOW_PROMPT.md`
     - `docs/TASK_INFO.md`
     - `docs/superpowers/`
     - `var/`
     - `.env`

8. Commit and push.
   - Commit with:
     - `docs: add review evidence entrypoint task docs`
   - Push the branch:
     - `git push`
   - If the branch needs upstream configuration, use:
     - `git push -u origin codex/review-evidence-entrypoint-convergence-v0`

9. Prepare handoff.
   - Report changed files.
   - Report verification commands and results.
   - Report commit hash and push result.
   - State that Task 125 final Mock World V2 verification is now unblocked.

## 6. Testing Plan

- Document checks:
  - Task 124 spec follows `docs/templates/TASK_SPEC_TEMPLATE.md`.
  - Task 124 plan follows `docs/templates/TASK_PLAN_TEMPLATE.md`.
  - Both docs align with the committed Task 124 implementation.
  - Both docs reference the current six-artifact evidence contract.

- Focused regression tests:
  - `tests/test_review_evidence.py`
  - `tests/test_demo_support_scripts.py`

- Script verification:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/demo_preflight.py`
  - `python scripts/verify_review_evidence.py`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

Commands to run after staging:

```bash
git diff --cached --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
docs: add review evidence entrypoint task docs
```

Expected commands:

```bash
git status --short
git add docs/specs/124-review-evidence-entrypoint-convergence-v0.md docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md
git diff --cached --check
git commit -m "docs: add review evidence entrypoint task docs"
git push
```

If the branch has no upstream:

```bash
git push -u origin codex/review-evidence-entrypoint-convergence-v0
```

The implementer must confirm `.env`, secrets, generated `var/` artifacts, and unrelated untracked docs are not staged.

## 9. Out-of-scope Changes

- Do not create Task 125 spec or plan in this task.
- Do not run full final Mock World V2 delivery verification as part of this task.
- Do not refresh evidence artifacts unless a focused verification command proves a required canonical alias is missing or malformed.
- Do not change benchmark semantics, thresholds, suite membership, artifact schemas, public APIs, frontend behavior, or observability API behavior.
- Do not modify Task numbering or backfill Task `122`.
- Do not commit generated `var/` artifacts, caches, virtual environments, screenshots, or secrets.
- Do not stage or edit unrelated untracked local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] `docs/specs/124-review-evidence-entrypoint-convergence-v0.md` is tracked.
- [ ] `docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md` is tracked.
- [ ] The spec follows `docs/templates/TASK_SPEC_TEMPLATE.md`.
- [ ] The plan follows `docs/templates/TASK_PLAN_TEMPLATE.md`.
- [ ] The docs match the Task 124 implementation committed in `28efaf8`.
- [ ] The docs preserve the six-artifact canonical evidence contract.
- [ ] `python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q` passed.
- [ ] `python scripts/show_submission_evidence.py` passed.
- [ ] `python scripts/demo_preflight.py` passed.
- [ ] `python scripts/verify_review_evidence.py` passed.
- [ ] `git diff --check` passed.
- [ ] `git diff --cached --check` passed before commit.
- [ ] No generated `var/` artifact was committed.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] Unrelated untracked docs remained untouched.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.

## 11. Handoff Notes

After finishing, report back:

- changed files
- verification commands and results
- whether either Task 124 doc required correction before staging
- commit hash
- push result
- confirmation that unrelated untracked files were not touched
- confirmation that Task 125 final Mock World V2 verification is now the next recommended new task
