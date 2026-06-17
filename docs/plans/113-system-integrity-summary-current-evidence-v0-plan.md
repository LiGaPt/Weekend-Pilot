# Plan: 113 System Integrity Summary Current Evidence v0

## 1. Spec Reference

Spec file:

```text
docs/specs/113-system-integrity-summary-current-evidence-v0.md
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
codex/112-canonical-evidence-artifact-refresh-v0
```

- Latest completed numbered task is `112`.
- Latest commit is:

```text
ac41148 chore: refresh canonical evidence artifacts
```

- `docs/specs/` and `docs/plans/` are continuous and matched through `112`.
- There is no tracked `113` spec, plan, or implementation branch yet.
- Untracked local materials exist and must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Existing internal integrity support already exists in:
  - `backend/app/observability/integrity_summary.py`
  - `backend/app/observability/schemas.py`
  - `backend/app/api/observability.py`
  - `frontend/src/observability/ObservabilityPage.tsx`
- The main gap is convergence, not missing infrastructure:
  - code and tests still use stale integrity fixture counts
  - the API does not expose formal-verification breadth and safe-stop gate summaries as first-class sections
  - reviewer docs still contain at least one stale `18/18` / `28/28` checklist reference

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/observability/schemas.py` - add additive schema models and top-level fields for `formal_verification_summary` and `safe_stop_summary`.
- `backend/app/observability/integrity_summary.py` - load and validate `all_registered` as a full formal-verification section, load `safe_stop_gate_v1`, extend required evidence IDs, extend top-level status derivation, and include the new evidence-path entry.
- `frontend/src/observability/types.ts` - mirror the additive API fields in TS types.
- `frontend/src/observability/ObservabilityPage.tsx` - render new `Formal Verification` and `Safe Stop Gate` sections in the `System Integrity Summary` panel.
- `tests/test_system_integrity_summary.py` - cover ready / missing / invalid behavior for the new sections and update fixture counts to current evidence truth.
- `tests/integration/test_observability_gateway.py` - update endpoint-shape expectations for the extended summary payload.
- `frontend/src/observability/api.test.ts` - update mocked integrity payload to the new schema and current counts.
- `frontend/src/observability/ObservabilityPage.test.tsx` - update the page fixture and assertions for new sections and current counts.
- `frontend/e2e/internal-observability.spec.ts` - update Playwright fixture payload and visible assertions for the new summary sections.
- `docs/submission/RECORDING_CHECKLIST.md` - align reviewer checklist counts and wording with the current `30/20/8` summary story.
- Modify only if verification proves it is required:
  - `tests/test_demo_support_scripts.py`
  - `tests/test_review_evidence.py`

## 5. Implementation Steps

1. Confirm the task start point.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -1`
   - Verify the branch / commit assumptions above.
   - Do not touch the unrelated untracked docs.

2. Inspect the current integrity-summary contract and its consumers.
   - Read:
     - `backend/app/observability/schemas.py`
     - `backend/app/observability/integrity_summary.py`
     - `frontend/src/observability/types.ts`
     - `frontend/src/observability/ObservabilityPage.tsx`
     - `tests/test_system_integrity_summary.py`
     - `tests/integration/test_observability_gateway.py`
     - `frontend/src/observability/api.test.ts`
     - `frontend/src/observability/ObservabilityPage.test.tsx`
     - `frontend/e2e/internal-observability.spec.ts`
     - `docs/submission/RECORDING_CHECKLIST.md`

3. Verify the current evidence truth before changing fixtures.
   - Run:
     - `python scripts/show_submission_evidence.py`
   - Record the current values for:
     - `v2_integrity_gate`
     - `all_registered`
     - `safe_stop_gate_v1`
     - `v2_integrity_passk`
     - canonical replay review
   - Use these live alias values as the only source of truth for all mock payload updates.

4. Extend backend schemas first.
   - In `backend/app/observability/schemas.py`:
     - add `SystemIntegrityFormalVerificationSummary`
     - add `SystemIntegritySafeStopSummary`
     - add both fields to `SystemIntegritySummary`
   - Keep the schema additive. Do not rename existing models or fields.

5. Add failing backend tests before touching the loader.
   - In `tests/test_system_integrity_summary.py`, add or update tests to require:
     - `formal_verification_summary` is populated from `latest-all_registered-run-report.json`
     - `safe_stop_summary` is populated from `latest-safe_stop_gate_v1-run-report.json`
     - missing `safe_stop_gate_v1` sets section status to `missing` and degrades top-level status
     - invalid `safe_stop_gate_v1` sets section status to `invalid`
     - evidence paths include `safe_stop_gate_v1`
     - current mock counts reflect current alias truth, not stale `18` / `28`
   - Keep tests focused on structure and evidence interpretation.

6. Implement the backend loader changes.
   - In `backend/app/observability/integrity_summary.py`:
     - add `safe_stop_gate_v1` to `EVIDENCE_PATHS`
     - add `safe_stop_gate_v1` to `REQUIRED_EVIDENCE_IDS`
     - implement `_load_formal_verification_summary()`
       - validate `BenchmarkRunReport`
       - use full `benchmark_summary` values from `all_registered`
     - keep `_load_memory_governance_summary()` but do not repurpose it
     - implement `_load_safe_stop_summary()`
       - validate the benchmark run report from `latest-safe_stop_gate_v1-run-report.json`
       - read gate metadata and summary counts
     - include both new summaries in `load_system_integrity_summary()`
     - update `_build_evidence_paths()` and `_derive_top_level_status()` accordingly
   - Preserve existing relative-path and redaction behavior.

7. Update backend integration expectations.
   - In `tests/integration/test_observability_gateway.py`, update the mocked integrity payload shape and assertions to include:
     - `formal_verification_summary`
     - `safe_stop_summary`
     - current evidence counts
   - Do not widen the test beyond the endpoint contract.

8. Extend frontend types and page rendering.
   - In `frontend/src/observability/types.ts`, add TS types for the new sections and include them in `SystemIntegritySummary`.
   - In `frontend/src/observability/ObservabilityPage.tsx`:
     - render a dedicated `Formal Verification` section
     - render a dedicated `Safe Stop Gate` section
     - keep `Pass@k`, `Memory Governance`, and `Recovery Replay` intact
     - show `Reason` in degraded or missing states just like existing sections
   - Keep the UI additive and consistent with the current panel style.

9. Update frontend tests and e2e fixtures.
   - In `frontend/src/observability/api.test.ts`:
     - update the mocked payload shape and current counts
   - In `frontend/src/observability/ObservabilityPage.test.tsx`:
     - assert the new section headings are visible
     - assert current evidence paths and counts are rendered from the updated mock
   - In `frontend/e2e/internal-observability.spec.ts`:
     - update the fixture payload to include `formal_verification_summary` and `safe_stop_summary`
     - assert the internal page shows these sections

10. Update the reviewer checklist text.
    - In `docs/submission/RECORDING_CHECKLIST.md`:
      - replace stale `18/18` and `28/28` quotes with the current alias truth
      - keep the wording tied to what the `5174` reviewer actually sees
    - Touch other docs only if `verify_review_evidence` proves they still contradict current tracked truth.

11. Run focused verification and only then patch any doc-locking tests.
    - Run:
      - `python -m pytest tests/test_system_integrity_summary.py tests/integration/test_observability_gateway.py tests/test_review_evidence.py -q`
      - `npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx`
      - `npm --prefix frontend exec playwright test e2e/internal-observability.spec.ts --project=desktop-chromium`
      - `python scripts/show_submission_evidence.py`
      - `python scripts/verify_review_evidence.py`
    - If `tests/test_review_evidence.py` or `tests/test_demo_support_scripts.py` fail only because they intentionally lock stale reviewer text, update just those assertions.

12. Final diff and commit preparation.
    - Run:
      - `git diff --check`
      - `git status --short`
    - Confirm only task-relevant files changed and no generated `var/` artifacts are staged.

## 6. Testing Plan

- Unit tests:
  - `tests/test_system_integrity_summary.py`
    - ready summary includes `formal_verification_summary` and `safe_stop_summary`
    - missing / invalid safe-stop alias degrades status correctly
    - evidence paths include `safe_stop_gate_v1`
  - `frontend/src/observability/api.test.ts`
    - API client accepts the extended integrity payload
  - `frontend/src/observability/ObservabilityPage.test.tsx`
    - page renders new sections and current-evidence values

- Integration tests:
  - `tests/integration/test_observability_gateway.py`
    - backend endpoint returns the additive contract
  - `frontend/e2e/internal-observability.spec.ts`
    - `5174` reviewer page shows the new sections from mocked endpoint responses

- Smoke / contract checks:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/verify_review_evidence.py`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_system_integrity_summary.py tests/integration/test_observability_gateway.py tests/test_review_evidence.py -q
npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend exec playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
python scripts/show_submission_evidence.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
fix: align system integrity summary with current evidence
```

Expected commands:

```bash
git status --short
git switch -c codex/113-system-integrity-summary-current-evidence-v0
git add backend/app/observability/schemas.py backend/app/observability/integrity_summary.py frontend/src/observability/types.ts frontend/src/observability/ObservabilityPage.tsx tests/test_system_integrity_summary.py tests/integration/test_observability_gateway.py frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.test.tsx frontend/e2e/internal-observability.spec.ts docs/submission/RECORDING_CHECKLIST.md docs/specs/113-system-integrity-summary-current-evidence-v0.md docs/plans/113-system-integrity-summary-current-evidence-v0-plan.md
git diff --cached --check
git commit -m "fix: align system integrity summary with current evidence"
git push -u origin codex/113-system-integrity-summary-current-evidence-v0
```

If focused verification proves a tracked reviewer-text assertion also needs updating, stage only the minimal additional test file:
- `tests/test_review_evidence.py`
- `tests/test_demo_support_scripts.py`

The implementer must confirm:
- no `var/` artifacts are staged
- unrelated untracked local docs remain unstaged
- no secrets are staged

## 9. Out-of-scope Changes

- Do not change workflow logic, benchmark grading logic, or canonical evidence generation commands.
- Do not add new benchmark suites, cases, or recovery policies.
- Do not modify public demo routes, customer frontend behavior, or plan/action-manifest flows.
- Do not redesign the internal observability page beyond additive integrity-summary sections.
- Do not update unrelated docs for style or wording cleanup.
- Do not modify `docs/TASK_INFO.md`, `docs/NEW_WORKFLOW_PROMPT.md`, or `docs/superpowers/`.
- Do not stage or commit generated evidence files under `var/`.
- Do not add new dependencies.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/113-system-integrity-summary-current-evidence-v0.md`.
- [ ] The task stayed within reviewer-surface convergence scope.
- [ ] The backend API contract was extended additively, not broken.
- [ ] `formal_verification_summary` reflects full `all_registered` evidence rather than memory-only subset counts.
- [ ] `safe_stop_summary` reflects `safe_stop_gate_v1` and participates in required evidence status.
- [ ] The `5174` page renders `Formal Verification` and `Safe Stop Gate`.
- [ ] Existing `Pass@k`, `Memory Governance`, and `Recovery Replay` sections still work.
- [ ] Current mock / test counts align with the actual latest alias truth.
- [ ] `docs/submission/RECORDING_CHECKLIST.md` no longer contradicts the reviewer surface.
- [ ] Focused backend, frontend, and e2e checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- the exact current counts read from `show_submission_evidence.py`
- which schema fields were added
- which backend and frontend files changed
- verification commands run and results
- whether any doc-locking tests needed updates
- commit hash
- push result
- confirmation that no `var/` artifacts were committed
