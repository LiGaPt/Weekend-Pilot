# Plan: 112 Canonical Evidence Artifact Refresh v0

## 1. Spec Reference

Spec file:

```text
docs/specs/112-canonical-evidence-artifact-refresh-v0.md
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

- Current branch is:

```text
codex/session-conversation-turn-trace-snapshots-v0
```

- Latest committed numbered task is `111`.
- Latest commit is:

```text
dc93da2 feat: add conversation turn trace snapshots
```

- `docs/specs/` and `docs/plans/` are continuous and matched through `111`.
- There is no tracked in-progress implementation to continue before starting `112`.
- The current workspace does contain unrelated untracked local files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- The shared canonical submission-evidence contract already exists in:
  - `backend/app/benchmark/submission_evidence.py`
- Reviewer-doc / evidence verification already exists in:
  - `backend/app/benchmark/review_evidence.py`
  - `scripts/show_submission_evidence.py`
  - `scripts/demo_preflight.py`
  - `scripts/verify_review_evidence.py`
- The current drift is documentation truthfulness, not missing product capability:
  - tracked docs still cite stale evidence counts
  - README and reviewer surfaces have moved forward
  - the multi-turn clarify / replan feature set already exists and is not the next missing slice

## 3. Files to Add

- None.

## 4. Files to Modify

- `README.md` - align current delivery-story evidence numbers, commands, and canonical alias narrative with refreshed artifacts.
- `docs/WEB_DEMO_README.md` - align reviewer walkthrough text and cited benchmark / integrity evidence facts with refreshed artifacts.
- `docs/submission/OVERVIEW.md` - replace stale benchmark / integrity / recovery counts with refreshed canonical evidence truth.
- `docs/submission/EVIDENCE_MAP.md` - replace stale alias summaries and quoted counts with refreshed canonical evidence truth.
- `docs/V1_5_REVIEW_EVIDENCE.md` - update reviewer guidance only if the refreshed current evidence package or canonical command wording requires it.
- `docs/COMPETITION_SUBMISSION_DESIGN.md` - update evidence-package wording only if it currently contradicts refreshed repo truth.
- `tests/test_demo_support_scripts.py` - update assertions only where they intentionally lock refreshed README / runbook / evidence-summary wording.
- `tests/test_review_evidence.py` - update assertions only where they intentionally lock refreshed tracked-doc snippets or alias expectations.
- `tests/test_system_integrity_summary.py` - update only if the tracked reviewer-surface truth it enforces is now stale.
- Modify only if a blocking contract drift is proven by verification:
  - `backend/app/benchmark/submission_evidence.py`
  - `backend/app/benchmark/review_evidence.py`
  - `scripts/demo_preflight.py`

## 5. Implementation Steps

1. Confirm the baseline before making any edits.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -1`
   - Verify the branch / latest-commit assumptions above still hold.
   - Do not touch the unrelated untracked local docs.

2. Inspect the current tracked evidence story.
   - Read:
     - `README.md`
     - `docs/WEB_DEMO_README.md`
     - `docs/submission/OVERVIEW.md`
     - `docs/submission/EVIDENCE_MAP.md`
     - `docs/V1_5_REVIEW_EVIDENCE.md`
     - `docs/COMPETITION_SUBMISSION_DESIGN.md`
   - Note every tracked location that quotes:
     - benchmark passed counts
     - gate counts
     - passk metrics
     - recovery status wording
     - canonical alias paths
     - repo-root verification commands

3. Run the focused support-script and reviewer-doc tests before refreshing evidence.
   - Run:
     - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py tests/test_system_integrity_summary.py -q`
   - Record which failures are stale-doc drift versus actual code / contract drift.
   - Do not edit anything yet.

4. Refresh the canonical evidence artifacts from the repo root.
   - Run these commands in this order:
     - `python scripts/run_benchmark_release_gate.py`
     - `python scripts/run_benchmark_coverage_gate.py`
     - `python scripts/run_benchmark_v2_integrity_gate.py`
     - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
     - `python scripts/run_formal_verification.py`
     - `python scripts/run_benchmark_safe_stop_gate.py`
     - `python scripts/run_recovery_replay_review.py`
   - Treat any command failure as blocking.
   - Do not guess counts or statuses.

5. Read the refreshed evidence truth from the canonical aliases.
   - Use:
     - `python scripts/show_submission_evidence.py`
   - Also inspect the refreshed alias files under `var/` as needed to capture:
     - current total case counts
     - current gate counts
     - current recovery review status
     - any supporting `safe_stop_gate_v1` count now quoted by tracked docs
   - Write down the exact refreshed facts that tracked docs must cite.

6. Re-run the repo-root evidence verifiers before editing docs.
   - Run:
     - `python scripts/demo_preflight.py`
     - `python scripts/verify_review_evidence.py`
   - If these already pass but tracked docs are still stale, the task is doc-only.
   - If one fails because of a real contract drift, identify the minimum contract-side fix needed.

7. Update tracked docs to match the refreshed truth.
   - Edit `README.md` first so the top-level repo narrative matches refreshed artifacts.
   - Edit `docs/submission/OVERVIEW.md` and `docs/submission/EVIDENCE_MAP.md` next.
   - Edit `docs/WEB_DEMO_README.md`, `docs/V1_5_REVIEW_EVIDENCE.md`, and `docs/COMPETITION_SUBMISSION_DESIGN.md` only where they still contradict refreshed truth.
   - Keep these constraints:
     - cite canonical aliases under `var/`
     - keep `5173` / `5174` role separation unchanged
     - do not invent new metrics
     - do not broaden the evidence package story beyond what refreshed artifacts prove

8. Update focused tests only where they intentionally lock stale tracked wording.
   - In `tests/test_demo_support_scripts.py`, adjust assertions that depend on refreshed README / reviewer-doc copy.
   - In `tests/test_review_evidence.py`, adjust only the tracked snippet expectations that must follow the refreshed docs.
   - In `tests/test_system_integrity_summary.py`, update only if a stale reviewer-facing truth assumption is now incorrect.
   - Do not weaken tests into generic smoke checks; keep them enforcing the refreshed current truth.

9. Fix contract-side drift only if verification still proves it is necessary.
   - If `show_submission_evidence.py`, `demo_preflight.py`, and `verify_review_evidence.py` still disagree after doc updates:
     - inspect `backend/app/benchmark/submission_evidence.py`
     - inspect `backend/app/benchmark/review_evidence.py`
     - inspect `scripts/demo_preflight.py`
   - Apply only the smallest alignment fix required.
   - Prefer preserving the existing shared submission-evidence contract rather than adding new evidence IDs.

10. Re-run the focused verification suite end to end.
    - Run:
      - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py tests/test_system_integrity_summary.py -q`
      - `python scripts/show_submission_evidence.py`
      - `python scripts/demo_preflight.py`
      - `python scripts/verify_review_evidence.py`
    - Confirm all pass.

11. Sanity-check the diff and staging boundaries.
    - Run:
      - `git diff --check`
      - `git status --short`
    - Confirm:
      - no `var/` files are staged
      - no unrelated untracked files are staged
      - only task-relevant tracked docs / tests / minimal drift fixes remain

12. Commit only the task-relevant tracked files.
    - Create a new branch from current HEAD for this task.
    - Stage only task-relevant files.
    - Use the expected commit message from section 8.
    - Leave ignored runtime evidence under `var/` unstaged.

## 6. Testing Plan

- Unit / focused regression tests:
  - `tests/test_demo_support_scripts.py`
    - README / runbook / evidence-summary contract remains aligned
  - `tests/test_review_evidence.py`
    - reviewer-doc snippets and artifact verifier still match tracked docs plus canonical aliases
  - `tests/test_system_integrity_summary.py`
    - reviewer-facing integrity summary assumptions remain aligned with current evidence story if this test covers quoted evidence paths or counts

- Script-level verification:
  - `python scripts/show_submission_evidence.py`
    - canonical six-artifact summary passes
  - `python scripts/demo_preflight.py`
    - repo-root preflight passes with refreshed evidence
  - `python scripts/verify_review_evidence.py`
    - tracked docs and current latest aliases remain aligned

- Evidence refresh commands:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_benchmark_coverage_gate.py`
  - `python scripts/run_benchmark_v2_integrity_gate.py`
  - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
  - `python scripts/run_formal_verification.py`
  - `python scripts/run_benchmark_safe_stop_gate.py`
  - `python scripts/run_recovery_replay_review.py`

- Smoke checks:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py tests/test_system_integrity_summary.py -q
python scripts/run_benchmark_release_gate.py
python scripts/run_benchmark_coverage_gate.py
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4
python scripts/run_formal_verification.py
python scripts/run_benchmark_safe_stop_gate.py
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
chore: refresh canonical evidence artifacts
```

Expected commands:

```bash
git status --short
git switch -c codex/112-canonical-evidence-artifact-refresh-v0
git add README.md docs/WEB_DEMO_README.md docs/submission/OVERVIEW.md docs/submission/EVIDENCE_MAP.md docs/V1_5_REVIEW_EVIDENCE.md docs/COMPETITION_SUBMISSION_DESIGN.md tests/test_demo_support_scripts.py tests/test_review_evidence.py tests/test_system_integrity_summary.py docs/specs/112-canonical-evidence-artifact-refresh-v0.md docs/plans/112-canonical-evidence-artifact-refresh-v0-plan.md
git diff --cached --check
git commit -m "chore: refresh canonical evidence artifacts"
git push -u origin codex/112-canonical-evidence-artifact-refresh-v0
```

If contract-side drift fixes are required, add only the minimal additional files:
- `backend/app/benchmark/submission_evidence.py`
- `backend/app/benchmark/review_evidence.py`
- `scripts/demo_preflight.py`

The implementer must confirm:
- no `var/` files are staged
- no `.env` or secrets are staged
- unrelated untracked local docs remain unstaged

## 9. Out-of-scope Changes

- Do not add new benchmark suites, benchmark cases, or failure profiles.
- Do not modify workflow logic, API schemas, frontend behavior, or multi-turn conversation behavior.
- Do not redesign the shared submission-evidence contract unless verification proves it is broken.
- Do not broaden the reviewer package beyond the current evidence story.
- Do not modify `docs/TASK_INFO.md`, `docs/NEW_WORKFLOW_PROMPT.md`, or `docs/superpowers/`.
- Do not stage or commit generated `var/` artifacts.
- Do not add new dependencies.
- Do not mix unrelated doc cleanup or style rewrites into this task.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/112-canonical-evidence-artifact-refresh-v0.md`.
- [ ] The task stayed inside evidence refresh / doc convergence scope.
- [ ] The six shared submission-evidence artifacts were refreshed successfully.
- [ ] Tracked docs no longer quote stale evidence numbers or stale alias facts.
- [ ] `show_submission_evidence.py`, `demo_preflight.py`, and `verify_review_evidence.py` all passed after the refresh.
- [ ] Focused support-script / reviewer-doc tests passed.
- [ ] No product behavior or public API changed.
- [ ] No `var/` artifacts were committed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- exact refreshed commands that were run
- the final current evidence counts / statuses cited in tracked docs
- which tracked docs changed and why
- whether any test file needed updates to follow refreshed truth
- whether any contract-side drift fix was required beyond doc updates
- verification commands run and their results
- commit hash
- push result
- confirmation that no `var/` artifacts were committed
