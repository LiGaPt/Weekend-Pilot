# Spec: 112 Canonical Evidence Artifact Refresh v0

## 1. Goal

Refresh the current canonical evidence package so reviewer-facing docs, submission docs, support scripts, and repo-root verification commands all describe the same real repository state.

The current repository already has the core evidence infrastructure in place: a shared submission-evidence contract, repo-root evidence summary and verifier scripts, internal integrity surfaces, and the benchmark / recovery scripts that generate canonical latest aliases under `var/`. The problem is convergence drift. Some tracked docs still cite older counts and older narrative snapshots even though the latest committed task chain has expanded the benchmark inventory and recovery coverage beyond those earlier numbers. After this task, the canonical evidence artifacts must be freshly regenerated, every tracked doc that quotes those artifacts must match the refreshed repo truth, and the repo-root evidence commands must pass against that refreshed state without adding new product behavior.

## 2. Project Context

This task belongs to milestone `M1. 评测与观测基础设施` in `docs/NEXT_PHASE_ROADMAP.md`.

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. The roadmap explicitly prioritizes evaluation and observability infrastructure before further feature expansion. The repository has already completed the core M1 and reviewer-surface groundwork through tasks such as:

- benchmark gates and summary reporting
- system integrity summary API and panel
- evidence-contract guardrails
- release verification support scripts

The latest committed task, `111`, is a multi-turn persistence-quality slice and is already closed by the current branch and latest commit. There is no unfinished tracked spec / plan gap to continue first. The more urgent issue is that reviewer-facing evidence docs and submission docs have drifted from the latest benchmark and recovery outputs. That drift makes the repository harder to trust during review even though the underlying product behavior and verification tooling already exist.

This task touches these blueprint areas directly:

- LocalLife-Bench evidence and release verification
- LangSmith / local observability review posture
- Minimal Web demo reviewer packaging
- Submission and reviewer documentation discipline

## 3. Requirements

- Re-run the current canonical evidence generation commands for the tracked reviewer / submission package.
- The refresh scope must include the six shared submission-evidence contract artifacts defined in `backend.app.benchmark.submission_evidence.SUBMISSION_EVIDENCE_CONTRACTS`:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `v2_integrity_passk`
  - `formal_verification_all_registered`
  - `recovery_review_family_route_failure_v1`
- In addition to the six shared submission-evidence artifacts, the implementation must refresh any supporting evidence artifact that is currently quoted by tracked docs as part of the current delivery story, including `safe_stop_gate_v1` when the tracked docs cite its counts or status.
- The task must treat refreshed artifact contents under `var/` as canonical runtime evidence, but must not stage or commit generated `var/` files.

- After refresh, the following tracked docs must be reviewed against the refreshed artifacts and updated when their quoted facts are stale:
  - `README.md`
  - `docs/WEB_DEMO_README.md`
  - `docs/submission/OVERVIEW.md`
  - `docs/submission/EVIDENCE_MAP.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
- Any tracked doc that quotes benchmark case counts, gate counts, pass / fail totals, stability metrics, recovery status, or canonical alias paths must match the refreshed artifact truth exactly after this task.
- Tracked docs must no longer cite stale counts such as earlier `28/28` or `18/18` numbers if refreshed artifacts now prove a different current baseline.
- Tracked docs must continue to cite canonical latest aliases under `var/`, not copied JSON under `docs/`.
- Tracked docs must keep the current public story:
  - `5173` is the customer-facing surface
  - `5174` is the reviewer / internal review surface
  - benchmark breadth is demonstrated through canonical evidence rather than live reruns during a demo
  - AMap remains an API-only read-only preview outside the main customer benchmark path

- The repo-root verification surfaces must remain aligned after the refresh:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/demo_preflight.py`
  - `python scripts/verify_review_evidence.py`
- `show_submission_evidence.py` must succeed against the refreshed six-artifact contract.
- `demo_preflight.py` must continue to validate the same canonical submission-evidence contract that the repo already treats as authoritative.
- `verify_review_evidence.py` must pass after docs are aligned to the refreshed artifact truth.

- Focused regression tests that guard the support scripts and tracked reviewer docs must pass after the refresh.
- If any existing focused test encodes stale reviewer-facing numbers or stale required snippets, update that test so it enforces the refreshed repo truth instead of the obsolete wording.

- This task must stay narrow:
  - do not add a new benchmark suite
  - do not add a new evidence ID to the shared contract unless it is strictly required to keep the current tracked docs truthful
  - do not change product APIs, workflow behavior, frontend behavior, or benchmark grading logic
  - do not change the system integrity summary schema unless a failing focused test proves the current tracked reviewer surfaces cannot remain truthful otherwise

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add new benchmark cases, failure profiles, replay flows, or memory-governance behavior.
- Do not change multi-turn clarification, replan, confirmation, execution, or feedback logic.
- Do not redesign `show_submission_evidence.py`, `verify_review_evidence.py`, or `demo_preflight.py` beyond drift fixes required to keep them aligned with current repository truth.
- Do not widen the shared submission-evidence contract casually.
- Do not modify `docs/TASK_INFO.md`, `docs/NEW_WORKFLOW_PROMPT.md`, or `docs/superpowers/`; they are currently untracked local materials, not canonical repo deliverables.
- Do not commit generated `var/` evidence artifacts, caches, virtual environments, or other ignored runtime files.

## 5. Interfaces and Contracts

### Inputs

- The current shared evidence contract in:
  - `backend.app.benchmark.submission_evidence.SUBMISSION_EVIDENCE_CONTRACTS`
- Repo-root evidence verification commands:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/demo_preflight.py`
  - `python scripts/verify_review_evidence.py`
- Existing benchmark / recovery generation commands:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_benchmark_coverage_gate.py`
  - `python scripts/run_benchmark_v2_integrity_gate.py`
  - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
  - `python scripts/run_formal_verification.py`
  - `python scripts/run_benchmark_safe_stop_gate.py`
  - `python scripts/run_recovery_replay_review.py`

### Outputs

- Refreshed local canonical evidence artifacts under `var/` for the current delivery baseline.
- Updated tracked docs whose cited counts, paths, or wording drifted from refreshed repo truth.
- Updated focused tests only where they intentionally enforce reviewer-facing text or current evidence claims.
- No public API shape changes.
- No new runtime schema or route changes.

### Schemas

The shared submission-evidence contract after this task must still be driven by entries shaped like:

```json
{
  "evidence_id": "v2_integrity_gate",
  "command": "python scripts/run_benchmark_v2_integrity_gate.py",
  "relative_path": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
  "artifact_kind": "benchmark_run",
  "proves": "V2 integrity benchmark gate"
}
```

A reviewer-facing tracked doc quote after this task must align with the refreshed alias truth, for example:

```json
{
  "alias": "var/formal-benchmarks/latest-all_registered-run-report.json",
  "quoted_status": "passed",
  "quoted_case_count": 30,
  "source_of_truth": "refreshed canonical latest alias under var/"
}
```

## 6. Observability

This task does not add a new observability backend or API surface.

Its observability responsibility is evidence freshness and evidence truthfulness:

- refreshed benchmark and recovery artifacts under `var/`
- reviewer-facing docs that accurately describe those artifacts
- repo-root verification commands that confirm the refreshed evidence package is internally consistent

If the refreshed artifacts change published counts, those updated numbers are the new observable truth for tracked docs. No new trace fields, Redis keys, database tables, or system integrity API fields should be introduced merely to complete this task.

## 7. Failure Handling

- If any canonical evidence generation command fails, treat that as a blocking task failure and do not update docs with guessed numbers.
- If a refreshed artifact exists but fails schema validation through `show_submission_evidence.py` or `verify_review_evidence.py`, treat that as blocking evidence drift and fix only the minimum script / doc alignment issue needed for truthfulness.
- If refreshed artifacts do not change a tracked doc’s quoted facts, avoid churn in that doc.
- If refreshed artifacts do change a tracked doc’s quoted facts, update only the affected tracked wording and any focused tests that intentionally lock that wording.
- If `demo_preflight.py`, `show_submission_evidence.py`, and `verify_review_evidence.py` disagree about which canonical aliases matter, resolve that drift in favor of the existing shared submission-evidence contract unless a focused test proves the contract itself is now incomplete.
- If `safe_stop_gate_v1` or another supporting artifact is quoted by tracked docs but not part of the shared six-artifact contract, keep that distinction explicit:
  - the six shared artifacts remain the canonical submission-evidence contract
  - supporting artifacts may still be documented truthfully as additional reviewer-facing evidence
- If any tracked doc cannot be reconciled with current committed code and refreshed artifacts without a larger product change, stop and report that conflict instead of inventing a new narrative.

## 8. Acceptance Criteria

- [ ] `docs/specs/112-canonical-evidence-artifact-refresh-v0.md` exists and matches this task.
- [ ] `docs/plans/112-canonical-evidence-artifact-refresh-v0-plan.md` exists and matches this task.
- [ ] The six shared submission-evidence artifacts have been regenerated successfully in the local workspace.
- [ ] Any supporting evidence artifact quoted by tracked docs has been refreshed or its tracked wording has been corrected to match current repo truth.
- [ ] `python scripts/show_submission_evidence.py` passes against the refreshed evidence package.
- [ ] `python scripts/demo_preflight.py` passes against the refreshed evidence package.
- [ ] `python scripts/verify_review_evidence.py` passes after tracked docs are aligned.
- [ ] `README.md`, `docs/WEB_DEMO_README.md`, `docs/submission/OVERVIEW.md`, `docs/submission/EVIDENCE_MAP.md`, `docs/V1_5_REVIEW_EVIDENCE.md`, and `docs/COMPETITION_SUBMISSION_DESIGN.md` no longer quote stale evidence counts or stale canonical alias facts.
- [ ] Focused support-script / reviewer-doc regression tests pass after the refresh.
- [ ] No product behavior, API contract, workflow routing, benchmark grading logic, or frontend behavior changed.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] No generated `var/` evidence artifact is staged for commit.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except for pre-existing unrelated local untracked files.

## 9. Verification Commands

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

## 10. Expected Commit

```text
chore: refresh canonical evidence artifacts
```

## 11. Notes for the Implementer

Use the refreshed artifact outputs as the only source of truth for counts and status language. Do not patch docs first and hope the scripts will later agree.

Keep the edit set narrow. The likely valid outcome is tracked doc wording updates plus any focused test adjustments needed to enforce the refreshed truth. Only touch the evidence scripts or shared evidence-contract code if one of the repo-root verification commands proves there is still an actual contract drift.

The current branch and latest commit already close Task `111`. Treat this task as the next numbered slice on top of current HEAD, not as a backfill into an older pre-`111` base.
