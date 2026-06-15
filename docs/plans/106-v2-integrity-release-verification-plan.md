# Plan: 106 V2 Integrity final release verification

## 1. Spec Reference

Spec file:

```text
docs/specs/106-v2-integrity-release-verification.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/105-v2-integrity-docs-submission`.
- Latest commit is `e5e1f5a docs: document v2 integrity submission flow`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `105`.
- There is no tracked `106` spec or `106` plan yet.
- The current canonical V2 evidence contract already exists in `backend/app/benchmark/submission_evidence.py`.
- `scripts/show_submission_evidence.py` and `python scripts/verify_review_evidence.py` already understand the six-artifact V2 evidence set.
- `scripts/demo_preflight.py` still uses its own evidence alias tuple and currently omits `v2_integrity_passk`.
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None.

## 4. Files to Modify

- `scripts/demo_preflight.py` - converge the preflight evidence check onto the full six-artifact canonical contract.
- `tests/test_demo_support_scripts.py` - update the preflight support-script expectations so they include `v2_integrity_passk`.
- `README.md` - update final published evidence values only if refreshed evidence changes quoted reviewer-facing numbers or wording.
- `docs/WEB_DEMO_README.md` - update preflight wording or final evidence wording only if refresh results require it.
- `docs/submission/OVERVIEW.md` - update final evidence wording only if refresh results require it.
- `docs/submission/RECORDING_CHECKLIST.md` - update the checklist wording if the preflight artifact list or published values change.

## 5. Implementation Steps

1. Confirm the baseline before making task changes.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm the task starts from the committed `105` baseline and that unrelated untracked files remain untouched.

2. Create the task branch.
   - Run:
     - `git switch -c codex/106-v2-integrity-release-verification`
   - Branch from the current `105` head unless the user explicitly wants another base.

3. Converge `demo_preflight.py` onto the canonical evidence contract before final verification.
   - Replace the local hard-coded alias tuple with logic derived from `backend.app.benchmark.submission_evidence.SUBMISSION_EVIDENCE_CONTRACTS`.
   - Keep the preflight output concise and reviewer-friendly.
   - Ensure the evidence check now covers:
     - `release_gate_v1`
     - `coverage_gate_v1_5`
     - `v2_integrity_gate`
     - `v2_integrity_passk`
     - `formal_verification_all_registered`
     - `recovery_review_family_route_failure_v1`
   - Do not make `demo_preflight.py` parse all artifact schemas; existence/path-level release readiness is sufficient here.

4. Update the focused preflight support-script test.
   - In `tests/test_demo_support_scripts.py`, update the mocked `Evidence Aliases` pass detail so it includes `latest-v2_integrity-passk-v0-report.json`.
   - Keep the test scoped to preflight output expectations; do not widen it into full evidence verification.

5. Run the focused support-script regression before the expensive refresh.
   - Run:
     - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
   - Fix only preflight/evidence-contract drift if this command fails.

6. Refresh all canonical release evidence in the real repo.
   - Run, in this order:
     - `python scripts/run_benchmark_release_gate.py`
     - `python scripts/run_benchmark_coverage_gate.py`
     - `python scripts/run_benchmark_v2_integrity_gate.py`
     - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
     - `python scripts/run_formal_verification.py`
     - `python scripts/run_recovery_replay_review.py`
   - If any command fails, stop immediately and report the failure instead of broadening scope.

7. Re-run the release verification surfaces against the refreshed evidence.
   - Run:
     - `python scripts/show_submission_evidence.py`
     - `python scripts/demo_preflight.py`
     - `python scripts/verify_review_evidence.py`
   - Confirm all three commands pass and that preflight now covers the same six canonical artifacts as the evidence summary and verifier.

8. Audit whether reviewer-facing docs need result refresh.
   - Inspect:
     - `README.md`
     - `docs/WEB_DEMO_README.md`
     - `docs/submission/OVERVIEW.md`
     - `docs/submission/RECORDING_CHECKLIST.md`
   - Update only if the refreshed outputs changed published values, alias wording, or preflight checklist wording.
   - If the rerun outputs match the current published claims, leave the docs unchanged.

9. Re-run focused verification after any doc edits.
   - Run:
     - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
     - `python scripts/show_submission_evidence.py`
     - `python scripts/demo_preflight.py`
     - `python scripts/verify_review_evidence.py`

10. Perform final git hygiene and prepare the commit.
   - Run:
     - `git diff --check`
     - `git status --short`
   - Confirm no `var/` artifacts, secrets, or unrelated files are staged.

11. Commit and push the task.
   - Stage only the task files that actually changed.
   - Commit with:
     - `git commit -m "chore: refresh v2 integrity release evidence"`
   - Push with:
     - `git push -u origin codex/106-v2-integrity-release-verification`

## 6. Testing Plan

- Unit / support-script tests:
  - `tests/test_demo_support_scripts.py`
    - preflight output includes the V2 Pass@k alias
    - evidence-summary expectations remain valid
  - `tests/test_review_evidence.py`
    - non-regression for the six-artifact review-evidence contract
- Integration / smoke checks:
  - all six repo-root evidence refresh commands
  - `python scripts/show_submission_evidence.py`
  - `python scripts/demo_preflight.py`
  - `python scripts/verify_review_evidence.py`
- Document review checks:
  - only if docs changed, confirm published claims match refreshed outputs

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
python scripts/run_benchmark_release_gate.py
python scripts/run_benchmark_coverage_gate.py
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4
python scripts/run_formal_verification.py
python scripts/run_recovery_replay_review.py
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
chore: refresh v2 integrity release evidence
```

Expected commands:

```bash
git status --short
git switch -c codex/106-v2-integrity-release-verification
git add scripts/demo_preflight.py tests/test_demo_support_scripts.py README.md docs/WEB_DEMO_README.md docs/submission/OVERVIEW.md docs/submission/RECORDING_CHECKLIST.md
git diff --cached --check
git commit -m "chore: refresh v2 integrity release evidence"
git push -u origin codex/106-v2-integrity-release-verification
```

The implementer must:
- omit any unchanged optional doc files from `git add`
- confirm `var/`, `.env`, secrets, and unrelated untracked files are not staged

## 9. Out-of-scope Changes

- Do not change benchmark runner logic beyond what is needed to execute the existing runners.
- Do not change benchmark thresholds, suite membership, stability formulas, or recovery-review grading logic.
- Do not modify `scripts/show_submission_evidence.py` or `backend.app.benchmark.review_evidence` unless a blocking drift is discovered during execution.
- Do not add CI jobs, release automation, or new dependencies.
- Do not redesign README or submission docs when no evidence claim changed.
- Do not stage refreshed `var/` artifacts.
- Do not debug unrelated product regressions inside this task.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `demo_preflight.py` now covers the same six canonical evidence artifacts as the shared V2 evidence contract.
- [ ] Focused support-script tests passed.
- [ ] All repo-root release verification commands passed.
- [ ] Reviewer-facing docs changed only if refreshed evidence required it.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or `var/` artifact was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- exact files changed
- whether `demo_preflight.py` now reads from the shared evidence contract or another minimal six-artifact source
- release verification command results
- whether refreshed evidence changed any published numbers
- commit hash
- push result
- any blocking runner failure that prevented release closure
