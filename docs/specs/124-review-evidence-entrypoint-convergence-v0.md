# Spec: 124 Review evidence entrypoint convergence v0

## 1. Goal

Close the documentation gap for Task `124 Review evidence entrypoint convergence v0`.

The implementation commit `28efaf8 chore: converge review evidence entrypoint` already converged the reviewer evidence entrypoint, verifier, and focused tests. However, the matching task spec and task plan are still present as untracked local files. This task continuation must save the Task 124 spec and plan into git so the repository preserves the required one-task-one-spec-one-plan audit trail before starting the next final Mock World V2 verification task.

After this task is complete, the latest implemented task will have matching tracked spec and plan documents, the reviewer evidence entrypoint convergence will remain verified, and the repository will be ready for the next new task: final Mock World / V2 delivery verification.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

It directly supports the roadmap principle that every task must have a spec, plan, implementation, verification, and commit. The current repository has already completed substantial M1 convergence work around benchmark evidence, observability surfaces, V2 integrity evidence, recovery review, and reviewer-facing documentation. Task 124 specifically closes the remaining reviewer evidence entrypoint drift by aligning:

- `docs/V1_5_REVIEW_EVIDENCE.md`
- `backend.app.benchmark.review_evidence`
- `tests/test_review_evidence.py`
- top-level submission wording where stale

This continuation does not add runtime capability. It preserves repository-truth discipline required by `docs/PROJECT_BLUEPRINT.md`:

- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- submission and reviewer documentation discipline
- small, reviewable tasks with explicit verification

## 3. Requirements

- `docs/specs/124-review-evidence-entrypoint-convergence-v0.md` must be tracked in git.
- `docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md` must be tracked in git.
- The spec document must describe Task 124 as reviewer evidence entrypoint convergence, not as final release verification.
- The plan document must describe how Task 124 converges the reviewer entrypoint doc, verifier rules, and tests.
- The Task 124 docs must remain consistent with the already committed Task 124 implementation in commit `28efaf8 chore: converge review evidence entrypoint`.
- The Task 124 docs must preserve the six canonical evidence entries:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `v2_integrity_passk`
  - `formal_verification_all_registered`
  - `recovery_review_family_route_failure_v1`
- Focused verification for review evidence and support scripts must still pass.
- Repo-root evidence summary and preflight commands must still pass.
- No generated `var/` evidence artifact may be staged or committed.
- No unrelated untracked local docs may be staged or committed.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not start Task 125 in this task.
- Do not refresh the full Mock World / V2 final delivery evidence package.
- Do not rerun benchmark generators unless verification proves a required canonical alias is missing or malformed.
- Do not modify benchmark semantics, thresholds, suite membership, public APIs, frontend behavior, or observability API behavior.
- Do not commit generated `var/` artifacts, caches, virtual environments, screenshots, or local scratch files.
- Do not backfill or renumber missing historical Task `122`.
- Do not touch unrelated untracked files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 5. Interfaces and Contracts

### Inputs

- Current git state:
  - latest commit: `28efaf8 chore: converge review evidence entrypoint`
  - current branch: `codex/review-evidence-entrypoint-convergence-v0`
  - untracked Task 124 docs under `docs/specs/` and `docs/plans/`
- Task 124 implementation surfaces:
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `backend/app/benchmark/review_evidence.py`
  - `tests/test_review_evidence.py`
- Shared canonical evidence contract:
  - `backend.app.benchmark.submission_evidence.SUBMISSION_EVIDENCE_CONTRACTS`

### Outputs

- Tracked spec:
  - `docs/specs/124-review-evidence-entrypoint-convergence-v0.md`
- Tracked plan:
  - `docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md`
- A commit that adds only the missing Task 124 docs unless inspection shows a small correction is required inside those docs.

### Schemas

The Task 124 documentation must reference this canonical six-artifact evidence manifest:

```json
{
  "release_gate_v1": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
  "coverage_gate_v1_5": "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
  "v2_integrity_gate": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
  "v2_integrity_passk": "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
  "formal_verification_all_registered": "var/formal-benchmarks/latest-all_registered-run-report.json",
  "recovery_review_family_route_failure_v1": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
}
```

No schema, API response, benchmark report shape, or artifact format may change in this task.

## 6. Observability

This task does not add runtime observability.

Its observability responsibility is repository auditability:

- the implemented Task 124 must have a tracked spec
- the implemented Task 124 must have a tracked plan
- the tracked docs must match the current reviewer evidence entrypoint contract
- focused verification commands must prove the evidence-entrypoint contract remains valid

## 7. Failure Handling

- If the Task 124 spec or plan content conflicts with the current implementation, update only the docs to reflect the implementation and current contract.
- If focused verification fails because the committed implementation is broken, stop and report the failing command instead of broadening this documentation-closure task into a product fix.
- If a canonical alias is missing or malformed, rerun only the corresponding existing generator command and then re-run verification.
- If unrelated untracked files are present, leave them untouched and do not stage them.
- If git status shows tracked modifications beyond the Task 124 docs before editing, inspect them and avoid overwriting user work.
- If fixing the issue requires benchmark semantic changes, new evidence IDs, or API changes, stop and split that into a new task.

## 8. Acceptance Criteria

- [ ] `docs/specs/124-review-evidence-entrypoint-convergence-v0.md` is tracked by git.
- [ ] `docs/plans/124-review-evidence-entrypoint-convergence-v0-plan.md` is tracked by git.
- [ ] The Task 124 spec follows `docs/templates/TASK_SPEC_TEMPLATE.md`.
- [ ] The Task 124 plan follows `docs/templates/TASK_PLAN_TEMPLATE.md`.
- [ ] The Task 124 docs describe reviewer evidence entrypoint convergence and do not claim to perform final Mock World V2 verification.
- [ ] The Task 124 docs reference the six canonical evidence entries.
- [ ] `python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q` passes.
- [ ] `python scripts/show_submission_evidence.py` passes.
- [ ] `python scripts/demo_preflight.py` passes.
- [ ] `python scripts/verify_review_evidence.py` passes.
- [ ] `git diff --check` passes.
- [ ] No generated `var/` artifact is staged or committed.
- [ ] No unrelated untracked local docs are staged or committed.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except for unrelated pre-existing untracked files.

## 9. Verification Commands

```bash
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
docs: add review evidence entrypoint task docs
```

## 11. Notes for the Implementer

Do not start the final Mock World V2 verification task until this documentation closure is committed.

Task 125 remains the likely next new task after this closure. Its expected scope should be final V2 delivery verification, full verification command execution, evidence refresh as needed, and delivery documentation refresh. This Task 124 continuation exists only because the current workspace still has untracked Task 124 spec and plan files while the Task 124 implementation commit already exists.
