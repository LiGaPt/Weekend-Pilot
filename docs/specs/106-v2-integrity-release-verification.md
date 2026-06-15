# Spec: 106 V2 Integrity final release verification

## 1. Goal

Complete the final release-closure pass for the current `V2 Integrity Edition` submission package.

This task must do two things together: refresh the canonical release evidence by rerunning the approved verification scripts, and make the repo-root preflight check reflect the same six-artifact evidence contract already established by Tasks `104` and `105`. After this task is complete, maintainers should be able to run the release verification commands from the repo root, confirm the canonical evidence is fresh, run `python scripts/demo_preflight.py`, and trust that the submission package is stable without adding new functionality.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

It is a convergence and release-closure task after Tasks `101-105`:
- `101` restored coverage-gate verification consistency.
- `102` added the internal system-integrity summary API.
- `103` surfaced the reviewer-facing `System Integrity Summary`.
- `104` established the shared six-artifact V2 evidence contract.
- `105` aligned the README and submission package docs to that V2 evidence story.

This task fits these `docs/PROJECT_BLUEPRINT.md` architecture areas:
- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- failure handling and recovery auditability
- small, reviewable tasks

It must not introduce new product behavior. It only refreshes evidence, closes the remaining preflight/evidence drift, and verifies the release package end to end.

## 3. Requirements

- Refresh the canonical release artifacts by rerunning all current release-verification entrypoints:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_benchmark_coverage_gate.py`
  - `python scripts/run_benchmark_v2_integrity_gate.py`
  - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
  - `python scripts/run_formal_verification.py`
  - `python scripts/run_recovery_replay_review.py`
- `python scripts/show_submission_evidence.py` must report the refreshed six-artifact canonical evidence set successfully.
- `python scripts/demo_preflight.py` must validate the same six canonical evidence artifacts, including `v2_integrity_passk`.
- The preflight evidence check must not keep an outdated five-alias list that can drift from the shared submission evidence contract.
- The preferred implementation is for `demo_preflight.py` to consume the shared evidence contract from `backend.app.benchmark.submission_evidence` rather than duplicating a separate alias registry.
- `python scripts/verify_review_evidence.py` must still pass after the evidence refresh.
- Focused regression tests for preflight and review-evidence support scripts must pass after any preflight contract update.
- Reviewer-facing docs may be updated only when refreshed evidence changes published numeric claims, alias wording, or final verification wording.
- If refreshed evidence keeps the current published numbers and wording accurate, do not make unnecessary docs edits.
- No benchmark semantics, thresholds, suite membership, API contracts, or frontend behavior may change in this task.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add new benchmark suites, new gates, new UI panels, or new observability APIs.
- Do not change release-gate, coverage-gate, V2 gate, Pass@k, formal-verification, or recovery-review grading semantics.
- Do not redesign submission docs beyond final evidence-result refresh and preflight wording convergence.
- Do not commit generated `var/` evidence artifacts.
- Do not broaden this task into debugging product regressions if a real gate fails.

## 5. Interfaces and Contracts

### Inputs

- Repo-root release verification commands:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_benchmark_coverage_gate.py`
  - `python scripts/run_benchmark_v2_integrity_gate.py`
  - `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4`
  - `python scripts/run_formal_verification.py`
  - `python scripts/run_recovery_replay_review.py`
- Shared evidence contract:
  - `backend.app.benchmark.submission_evidence.SUBMISSION_EVIDENCE_CONTRACTS`
- Repo-root verification/support commands:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/demo_preflight.py`
  - `python scripts/verify_review_evidence.py`

### Outputs

- Refreshed local canonical evidence artifacts under `var/` for the six supported evidence entries.
- A passing repo-root evidence summary.
- A passing repo-root preflight report that includes all six canonical artifacts.
- Optional doc updates only if final evidence claims changed.

### Schemas

The canonical evidence set for this task is:

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

The preflight evidence section must succeed only when all six canonical paths exist and are readable enough for release verification.

## 6. Observability

This task does not add new runtime telemetry.

It relies on existing benchmark and recovery artifacts, and on deterministic CLI outputs from:
- `show_submission_evidence.py`
- `demo_preflight.py`
- `verify_review_evidence.py`

If docs are updated, those updates must reflect the refreshed evidence outputs and not invent new metrics.

## 7. Failure Handling

- If any benchmark or recovery runner fails, stop the task and report the failing command, exit status, and affected artifact path. Do not patch product behavior in this task.
- If `show_submission_evidence.py` fails after refresh, treat that as a blocking release-verification failure.
- If `demo_preflight.py` still omits `v2_integrity_passk` or otherwise diverges from the shared evidence contract, fix only that release-verification drift.
- If refreshed evidence changes published reviewer-facing numbers, update only the docs that quote those exact numbers.
- If refreshed evidence does not change published reviewer-facing numbers, avoid churn in docs.
- If `verify_review_evidence.py` fails because docs drifted from refreshed evidence, update the docs or wording to match repo truth.
- Do not auto-stage or commit generated `var/` files even when they were refreshed successfully.

## 8. Acceptance Criteria

- [ ] All six repo-root release verification runners complete successfully.
- [ ] `python scripts/show_submission_evidence.py` reports the six canonical evidence entries successfully after refresh.
- [ ] `python scripts/demo_preflight.py` validates the same six canonical evidence artifacts, including `v2_integrity_passk`.
- [ ] `demo_preflight.py` no longer maintains an outdated five-alias evidence check.
- [ ] Focused support-script tests pass after the preflight convergence change.
- [ ] `python scripts/verify_review_evidence.py` passes after the refresh.
- [ ] Reviewer-facing docs are updated only if refreshed evidence changed published claims or checklist wording.
- [ ] No benchmark semantics, suite membership, thresholds, API contracts, or frontend behavior changed in this task.
- [ ] No generated `var/` artifact is staged or committed.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python scripts/run_benchmark_release_gate.py
python scripts/run_benchmark_coverage_gate.py
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4
python scripts/run_formal_verification.py
python scripts/run_recovery_replay_review.py
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
python scripts/verify_review_evidence.py
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
chore: refresh v2 integrity release evidence
```

## 11. Notes for the Implementer

Sequence this as a release-closure task, not a feature task.

Preferred order:
1. branch from the current `105` baseline
2. fix the preflight/evidence-contract drift first or immediately after the first failing preflight run
3. refresh all canonical evidence
4. re-run preflight, evidence summary, and verifier
5. update docs only if evidence claims changed
6. stage only task files, never `var/`

Stop and report back if any benchmark or recovery runner fails because that indicates a real product regression outside the scope of this release-verification task.
