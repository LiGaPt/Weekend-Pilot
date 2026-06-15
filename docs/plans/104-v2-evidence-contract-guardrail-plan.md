# Plan: 104 V2 Evidence Contract Guardrail

## 1. Spec Reference

Spec file:

```text
docs/specs/104-v2-evidence-contract-guardrail.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/103-system-integrity-panel-v0`.
- Latest commit is `f92c874 feat: add system integrity review panel`, which matches the latest completed task `103`.
- `docs/specs/` and `docs/plans/` are continuous and slug-matched from `001` through `103`.
- There is no tracked `104` spec or plan yet.
- Current untracked local paths include:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
  These are not part of Task `104` and must not be staged.
- `scripts/show_submission_evidence.py` already includes:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `formal_verification_all_registered`
  - `recovery_review_family_route_failure_v1`
- `scripts/show_submission_evidence.py` does not yet include:
  - `v2_integrity_passk`
- `backend/app/benchmark/review_evidence.py` still enforces only the older V1.5 review-evidence contract from Task `076`.
- Existing schema types already exist for the required V2 contracts:
  - `BenchmarkRunReport`
  - `BenchmarkStabilityPassKReport`
  - `RecoveryReplayReviewResult`

## 3. Files to Add

- `backend/app/benchmark/submission_evidence.py` - shared evidence-contract registry and helper functions for summary/verifier use.

## 4. Files to Modify

- `scripts/show_submission_evidence.py` - replace local hard-coded evidence list with shared contract usage and add V2 Pass@k summary support.
- `backend/app/benchmark/review_evidence.py` - extend the existing V1.5 verifier with V2 gate and V2 Pass@k validation using the shared contract.
- `scripts/verify_review_evidence.py` - keep thin wrapper behavior, update only if import path changes.
- `tests/test_demo_support_scripts.py` - update summary-script fixture and assertions for V2 Pass@k coverage.
- `tests/test_review_evidence.py` - extend fixture repo and add V2 artifact guardrail failure cases.

## 5. Implementation Steps

1. Read the current contract boundaries before editing:
   - `scripts/show_submission_evidence.py`
   - `backend/app/benchmark/review_evidence.py`
   - `tests/test_demo_support_scripts.py`
   - `tests/test_review_evidence.py`
   - confirm the exact V2 artifact identifiers from `backend/app/benchmark/schemas.py`

2. Add `backend/app/benchmark/submission_evidence.py`.
   - Define one canonical registry for all supported evidence artifacts.
   - Store, per artifact:
     - `evidence_id`
     - `command`
     - `relative_path`
     - `artifact_kind`
     - `proves`
     - expected schema/model identifier
     - expected suite/gate/case/metric fields
   - Include these six artifacts:
     - `release_gate_v1`
     - `coverage_gate_v1_5`
     - `v2_integrity_gate`
     - `v2_integrity_passk`
     - `formal_verification_all_registered`
     - `recovery_review_family_route_failure_v1`
   - Keep deterministic ordering in the registry itself so both CLI tools inherit the same order.

3. Refactor `scripts/show_submission_evidence.py` to consume the shared registry.
   - Remove the local `EVIDENCE_ITEMS` duplication.
   - Keep the repo-root CLI shape unchanged.
   - For benchmark reports, print concise structured output like:
     - `run_status`
     - `suite_id`
   - For the V2 gate entry, also include the gate identifier when present.
   - For the V2 Pass@k entry, print concise stability fields:
     - `suite_id`
     - `gate_id`
     - `metric_version`
   - For recovery review, keep the compact `status + case_id` summary.
   - Make missing or invalid required artifacts produce exit code `1`.

4. Extend `backend/app/benchmark/review_evidence.py` without regressing Task `076`.
   - Preserve the existing V1.5 document checks and original four-alias checks.
   - Import the shared evidence-contract entries instead of re-stating V2 path/ID literals in a second place.
   - Add validation for `v2_integrity_gate`:
     - parse with `BenchmarkRunReport`
     - require `run_status == "passed"`
     - require `benchmark_summary.suite_id == "v2_integrity"`
     - require raw `v2_integrity_gate_evaluation.gate_id == "v2_integrity_gate"`
     - require raw `v2_integrity_gate_evaluation.suite_id == "v2_integrity"`
     - require raw `v2_integrity_gate_evaluation.release_blocked == false`
   - Add validation for `v2_integrity_passk`:
     - parse with `BenchmarkStabilityPassKReport`
     - require `suite_id == "v2_integrity"`
     - require `gate_id == "v2_integrity_gate"`
     - require `metric_version == "passk_v0"`
     - require `window_count >= 1`
   - Keep actionable failure formatting with rerun command hints.

5. Update `tests/test_demo_support_scripts.py`.
   - Extend the fake repo fixture in the submission-evidence test to include:
     - `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`
   - Assert the output includes:
     - `v2_integrity_passk`
     - the stability alias path
     - the human-readable proof string
   - Keep the existing assertions for release, coverage, V2 gate, formal verification, and recovery review.

6. Update `tests/test_review_evidence.py`.
   - Extend the fake repo fixture writer so it creates the V2 Pass@k alias by default.
   - Extend the passing-case assertions so `checked_aliases` includes:
     - `v2_integrity_gate`
     - `v2_integrity_passk`
   - Add focused failing tests for:
     - missing V2 Pass@k alias
     - V2 gate wrong suite ID
     - V2 gate missing or wrong gate ID
     - V2 Pass@k wrong suite ID
     - V2 Pass@k wrong gate ID
     - V2 Pass@k wrong metric version
   - Keep at least one regression test proving the old V1.5 missing-doc-content failure still works.

7. Run focused tests first.
   - Fix fixture mismatches before running repo-root smoke commands.
   - Do not update submission docs in this task just to “match” the new summary output.

8. Run repo-root smoke commands on the real workspace.
   - `python scripts/show_submission_evidence.py`
   - `python scripts/verify_review_evidence.py`
   - If the verifier fails on the real repo because a current artifact is actually malformed or missing, stop and report instead of widening scope into artifact refresh work.

9. Perform final git hygiene checks.
   - Confirm only Task `104` files are staged.
   - Explicitly avoid staging:
     - `docs/NEW_WORKFLOW_PROMPT.md`
     - `docs/TASK_INFO.md`
     - `docs/superpowers/`
     - any `var/` files

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_support_scripts.py`
    - submission-evidence summary includes V2 Pass@k alias
    - summary output remains human-readable and deterministic
  - `tests/test_review_evidence.py`
    - aligned fixture passes
    - V2 gate drift fails
    - V2 Pass@k drift fails
    - missing V2 Pass@k alias fails
    - pre-existing V1.5 doc-contract failure still fails

- Smoke tests:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/verify_review_evidence.py`

- No new integration, browser, or API tests are required for this task.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
python scripts/show_submission_evidence.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add v2 evidence guardrails
```

Expected commands:

```bash
git status --short
git switch -c codex/104-v2-evidence-contract-guardrail
git add backend/app/benchmark/submission_evidence.py backend/app/benchmark/review_evidence.py scripts/show_submission_evidence.py scripts/verify_review_evidence.py tests/test_demo_support_scripts.py tests/test_review_evidence.py docs/specs/104-v2-evidence-contract-guardrail.md docs/plans/104-v2-evidence-contract-guardrail-plan.md
git commit -m "feat: add v2 evidence guardrails"
git push -u origin codex/104-v2-evidence-contract-guardrail
```

The implementer must confirm `.env`, secrets, `var/`, and unrelated untracked local docs are not staged.

## 9. Out-of-scope Changes

- Do not change `docs/WEB_DEMO_README.md`, `docs/submission/*`, or broader README wording beyond the minimum required by the spec. Task `105` owns the documentation convergence.
- Do not refresh evidence artifacts under `var/`.
- Do not change benchmark runners, suite definitions, gate thresholds, or stability formulas.
- Do not modify `backend/app/observability/integrity_summary.py`, internal API routes, or frontend code unless a tiny import-level adaptation is strictly required.
- Do not add CI automation, release scripts, or package dependencies.
- Do not stage unrelated workspace files or ignored outputs.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] `show_submission_evidence.py` and the verifier share one contract source instead of duplicating V2 identifiers.
- [ ] The verifier still enforces the Task `076` V1.5 contract while adding V2 coverage.
- [ ] `v2_integrity_passk` is now visible in the submission evidence summary.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Whether the real workspace smoke commands passed without refreshing artifacts
- Any follow-up for Task `105`, especially if summary output now leads the current reviewer/submission wording
- Confirmation that unrelated untracked files were left untouched
