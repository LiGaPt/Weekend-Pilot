# V2 Integrity docs + submission package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository's public docs and submission package speak with one V2 Integrity Edition voice.

**Architecture:** This is a docs-only convergence task. Treat `README.md` and the submission docs as the source of user-facing narrative, then align the competition design doc and demo script to the same canonical evidence set and AMap boundary. No code paths, benchmark behavior, or artifact generation should change.

**Tech Stack:** Markdown, repo-root evidence scripts, existing benchmark/review JSON artifacts.

---

## 1. Spec Reference

Spec file:

`docs/specs/105-v2-integrity-docs-submission.md`

Project blueprint:

`docs/PROJECT_BLUEPRINT.md`

Roadmap reference:

`docs/NEXT_PHASE_ROADMAP.md`

## 2. Current Repository Assumptions

- Current branch is `codex/104-v2-evidence-contract-guardrail`.
- Latest commit is `5f883a5 feat: add v2 evidence guardrails`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `104`.
- There is no tracked `105` spec or plan yet.
- The current implementation already includes:
  - `python scripts/show_submission_evidence.py` support for `v2_integrity_passk`
  - `python scripts/verify_review_evidence.py` support for the V2 evidence contract
  - the internal `System Integrity Summary` reviewer surface
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None.

## 4. Files to Modify

- `README.md` - align the current version posture, V2 focus, evidence set, and AMap boundary.
- `docs/COMPETITION_DESIGN_DOCUMENT.md` - restate the current V2 submission posture and keep future roadmap items clearly separated.
- `docs/submission/OVERVIEW.md` - align the submission overview with the V2 Integrity Edition narrative and canonical evidence set.
- `docs/submission/EVIDENCE_MAP.md` - update the canonical evidence table and spoken evidence claims.
- `docs/submission/FUNCTION_COVERAGE_MAP.md` - map each capability to the reviewer surface and the current evidence set.
- `docs/submission/DEMO_SCRIPT.md` - update the spoken demo flow, reviewer ordering, and AMap / integrity-panel framing.

## 5. Implementation Steps

- [ ] **Step 1: Audit current wording and mark conflicts**

Read the current text in:
- `README.md`
- `docs/COMPETITION_DESIGN_DOCUMENT.md`
- `docs/submission/OVERVIEW.md`
- `docs/submission/EVIDENCE_MAP.md`
- `docs/submission/FUNCTION_COVERAGE_MAP.md`
- `docs/submission/DEMO_SCRIPT.md`

Identify the exact lines that still describe the repo as `V1.5 baseline / V2 Integrity candidate`, omit `v2_integrity_passk`, or understate the `System Integrity Summary` reviewer surface.

- [ ] **Step 2: Normalize the top-level narrative**

Update `README.md` and `docs/COMPETITION_DESIGN_DOCUMENT.md` so they:
- describe the current posture as V2 Integrity Edition or V2 Integrity candidate
- explain that AMap is API-only read-only preview
- make benchmark completeness, memory governance, observability, and recovery the V2 priorities
- keep future work clearly separated from current submission posture

- [ ] **Step 3: Normalize the submission package**

Update `docs/submission/OVERVIEW.md`, `docs/submission/EVIDENCE_MAP.md`, and `docs/submission/FUNCTION_COVERAGE_MAP.md` so they:
- use the same canonical evidence list
- include `v2_integrity_gate` and `v2_integrity_passk`
- keep the current reviewer and demo story aligned with the backend and reviewer surfaces
- avoid any wording that implies AMap is a benchmark dependency or customer UI path

- [ ] **Step 4: Rewrite the demo script wording**

Update `docs/submission/DEMO_SCRIPT.md` so it:
- calls out `System Integrity Summary` in the reviewer sequence
- explains that the internal evidence flow is `Benchmark Summary` -> `System Integrity Summary` -> `Load Run` -> `Trace Summary` -> `Benchmark Artifacts` -> `Recovery Visualization`
- keeps AMap framed as optional API-only read preview
- keeps the spoken evidence summary aligned with the current canonical aliases

- [ ] **Step 5: Run consistency checks and fix drift**

Run the repository-root evidence scripts and text searches. Fix any wording drift until:
- the docs agree with the current evidence script output
- the docs agree with the existing reviewer surface names
- no doc still treats AMap as a mainline benchmark dependency

- [ ] **Step 6: Final hygiene pass**

Run diff and status checks, then stop with only the task-relevant doc edits in the tree.

## 6. Testing Plan

- Documentation consistency checks:
  - grep for `V2 Integrity Edition`, `v2_integrity_passk`, `System Integrity Summary`, and `API-only read-only preview`
  - confirm the same alias set appears across the submission docs
- Script smoke checks:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/verify_review_evidence.py`
- Regression checks:
  - `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
- Out-of-scope for testing:
  - no browser automation
  - no backend route changes
  - no benchmark reruns
  - no artifact refresh

## 7. Verification Commands

- `python scripts/show_submission_evidence.py`
- `python scripts/verify_review_evidence.py`
- `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
- `rg -n "V2 Integrity Edition|v2_integrity_passk|System Integrity Summary|API-only read-only preview|Mock World" README.md docs/COMPETITION_DESIGN_DOCUMENT.md docs/submission docs/WEB_DEMO_README.md`
- `git diff --check`
- `git status --short`

## 8. Commit and Push Plan

Expected commit message:

`docs: document v2 integrity submission flow`

Expected commands:

- `git status --short`
- `git switch -c codex/105-v2-integrity-docs-submission`
- `git add README.md docs/COMPETITION_DESIGN_DOCUMENT.md docs/submission/OVERVIEW.md docs/submission/EVIDENCE_MAP.md docs/submission/FUNCTION_COVERAGE_MAP.md docs/submission/DEMO_SCRIPT.md`
- `git diff --cached --check`
- `git commit -m "docs: document v2 integrity submission flow"`
- `git push -u origin codex/105-v2-integrity-docs-submission`

The implementer must confirm `.env`, secrets, `var/`, and unrelated untracked workspace files are not staged.

## 9. Out-of-scope Changes

- Do not change backend or frontend code.
- Do not change `scripts/show_submission_evidence.py` or `scripts/verify_review_evidence.py`.
- Do not change benchmark semantics, artifact content, or evidence generation.
- Do not add new docs-only helper tooling or dependencies.
- Do not expand the task into a broader README redesign or a general project rebrand.
- Do not stage unrelated workspace files.

## 10. Review Checklist

- [ ] The README and design doc both describe the current V2 Integrity Edition posture.
- [ ] The submission docs all agree on the same canonical evidence aliases.
- [ ] `v2_integrity_passk` appears wherever the current V2 evidence set is listed.
- [ ] `System Integrity Summary` appears in the reviewer flow where appropriate.
- [ ] AMap is always described as API-only read-only preview, not as a customer UI or benchmark dependency.
- [ ] The docs do not contradict the current evidence scripts or reviewer surfaces.
- [ ] The verification commands passed.
- [ ] Git diff was clean of accidental whitespace or formatting issues.
- [ ] No `.env`, API key, token, secret, or generated artifact was committed.

## 11. Handoff Notes

Report back with:
- which docs changed
- which canonical aliases are now described in the submission package
- whether any historical V1.5 wording remained and where
- the verification commands run and their results
- the commit hash
- the push result
- any wording gap that still needs follow-up
