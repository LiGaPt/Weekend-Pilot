# Plan: 118 Recovery Replay Visualization v0

## 1. Spec Reference

Spec file:

```text
docs/specs/118-recovery-replay-visualization-v0.md
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

- The latest committed implementation slice already in scope for this work is the recovery replay visualization linkage itself, but the numbered task docs are not yet tracked.
- The last fully tracked numbered spec/plan pair in git is Task `117`.
- The current branch and latest code commit already indicate this task is being closed as `118`, so this plan must align the numbered docs with the implementation rather than invent a new follow-up scope.
- Internal observability already exposes:
  - `benchmark_artifact_summary`
  - `recovery_path_summary`
  - `run_summary`
- Generic recovery replay review artifacts already exist from Task `099` and are written under `var/recovery-reviews/`.
- The current internal UI shows recovery attempts and replay source benchmark report path, but it does not yet formally document or guarantee latest review alias, review artifact path, replay report path, or alias/run mismatch state as a numbered task contract.
- Pre-existing unrelated untracked local docs may exist and must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None if implemented inline in current observability modules.
- Optional helper only if needed for clarity:
  - `backend/app/observability/recovery_replay_links.py` - bounded loader/parser for latest recovery review aliases

## 4. Files to Modify

- `backend/app/observability/schemas.py` - add typed recovery replay link summary contract.
- `backend/app/observability/service.py` - build additive replay-link summary from current run metadata plus latest recovery review alias.
- `frontend/src/observability/types.ts` - mirror the new backend response contract.
- `frontend/src/observability/ObservabilityPage.tsx` - render replay-link status, paths, counts, and mismatch reasons inside the recovery visualization.
- `frontend/src/observability/ObservabilityPage.test.tsx` - add focused UI rendering tests for new replay-link states.
- `frontend/e2e/internal-observability.spec.ts` - update fixture payload and assertions for reviewer-visible replay-link content.
- `tests/test_observability.py` - add unit coverage for matched, missing, invalid, mismatch, and null states.
- `tests/integration/test_observability_gateway.py` - assert API JSON for recovery replay link summary and degraded states.
- `README.md` - mention direct replay-link visibility on the internal observability page.
- `docs/WEB_DEMO_README.md` - update internal-review workflow documentation with the new replay-link block.
- `docs/specs/118-recovery-replay-visualization-v0.md` - save the numbered spec.
- `docs/plans/118-recovery-replay-visualization-v0-plan.md` - save the numbered implementation plan.

## 5. Implementation Steps

1. Reconfirm baseline before staging any numbered docs.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm the code implementation already aligns with the intended Task `118` scope and that unrelated local docs remain unstaged.

2. Add backend schema models for the new additive response field.
   - In `backend/app/observability/schemas.py`, define one Pydantic model for the linkage summary with exactly these fields:
     - `status`
     - `case_id`
     - `source_report_path`
     - `latest_review_path`
     - `review_artifact_path`
     - `replay_report_path`
     - `review_status`
     - `check_count`
     - `passed_check_count`
     - `failed_check_count`
     - `mismatch_reason`
   - Extend `InternalObservabilityRunSummary` with nullable `recovery_replay_link_summary`.
   - Keep existing schema versions unchanged because this is additive.

3. Implement the bounded loader for latest recovery review aliases.
   - In `backend/app/observability/service.py`, resolve current-case latest alias path as:
     - `var/recovery-reviews/latest-<case_id>-review.json`
   - Read only that single alias file when the current run has:
     - `benchmark_artifact_summary.case_id`
     - `benchmark_artifact_summary.report_path`
     - `recovery_path_summary`
   - Do not scan directories or search for fallback candidates.
   - Validate the alias payload with `RecoveryReplayReviewResult`.
   - Compute `review_artifact_path` deterministically as:
     - `<run_directory>/recovery-review.json`
   - Derive counts from `checks`:
     - `check_count = len(checks)`
     - `passed_check_count = number of passed checks`
     - `failed_check_count = number of failed checks`

4. Implement status derivation in the observability service.
   - Return `null` when the run is not eligible for replay linkage.
   - Return `missing` when the alias file does not exist.
   - Return `invalid` when file read, JSON parse, or schema validation fails.
   - Return `mismatch` when either invariant fails:
     - alias `case_id` differs from current benchmark case id
     - alias `source_report_path` differs from current benchmark artifact report path
   - Return `matched` only when both invariants pass.
   - Populate `mismatch_reason` with one short reviewer-readable sentence for `missing`, `invalid`, and `mismatch`.
   - Keep `/internal/runs/{run_id}/observability` returning `200` in all non-fatal linkage states.

5. Add backend unit tests in `tests/test_observability.py`.
   - Cover one eligible matched case with:
     - recovery metadata present
     - benchmark artifact report path present
     - latest alias payload readable and matching
   - Cover one missing-alias case.
   - Cover one invalid-alias case with malformed JSON or invalid schema payload.
   - Cover one mismatch case where alias source report path differs from current run report path.
   - Cover one non-recovery or non-benchmark case returning `null`.
   - Assert that existing `recovery_path_summary` and `run_summary` behavior stays unchanged.

6. Add gateway/API integration coverage in `tests/integration/test_observability_gateway.py`.
   - Seed a recovery-backed run and monkeypatch alias-path resolution or write a temp alias file under a temp root.
   - Assert JSON response includes the additive `recovery_replay_link_summary`.
   - Assert the API still returns `200` for missing and mismatch states.
   - Assert no sensitive keys leak in serialized response.

7. Update frontend response types.
   - In `frontend/src/observability/types.ts`, add the new summary type and include it in `InternalObservabilityRunSummary`.

8. Update `frontend/src/observability/ObservabilityPage.tsx`.
   - Inside the existing `Recovery Visualization` panel, add a new subsection titled `Replay Review Link`.
   - Show a readable no-link state when the summary is `null`.
   - For `matched`, show:
     - link status badge
     - review status badge
     - check counts
     - latest alias path
     - review artifact path
     - replay report path
     - source report path
   - For `missing`, `invalid`, and `mismatch`, show:
     - link status badge
     - mismatch/invalid reason
     - latest alias path when known
     - any artifact-derived paths that are safely available
   - Reuse the existing `PathField` copy-button pattern for each path.
   - Do not remove the existing `Replay Source` section or attempt list.

9. Add frontend tests.
   - In `frontend/src/observability/ObservabilityPage.test.tsx`, cover:
     - matched link block renders all paths and counts
     - missing alias renders a degraded message
     - mismatch renders the reason and still shows the alias path
     - null summary keeps the rest of recovery visualization intact

10. Update Playwright assertions.
    - In `frontend/e2e/internal-observability.spec.ts`, update fixture payload and assertions.
    - Assert the page shows `Recovery Visualization` and `Replay Review Link`.
    - Assert reviewer-visible path text appears for matched sample data.
    - Assert copy-button labels remain present.

11. Update reviewer-facing docs.
    - In `README.md`, mention that internal observability now links recovery visualization to the latest replay review artifact chain when available.
    - In `docs/WEB_DEMO_README.md`, update internal-review instructions so reviewers know they can load a run and copy the linked replay alias, review artifact, and replay report paths from the recovery section.
    - Do not broaden the docs into new replay controls or benchmark behavior changes.

12. Save the numbered task docs.
    - Save the spec to:
      - `docs/specs/118-recovery-replay-visualization-v0.md`
    - Save the plan to:
      - `docs/plans/118-recovery-replay-visualization-v0-plan.md`

13. Run focused verification.
   - Run:
     ```bash
     python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py tests/test_recovery_replay_review.py -q
     ```
   - Run:
     ```bash
     npm --prefix frontend test -- --run src/observability/ObservabilityPage.test.tsx
     ```
   - Run:
     ```bash
     cd frontend && npx playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
     ```
   - Final hygiene:
     ```bash
     git diff --check
     git status --short
     ```

14. Stage only task-relevant files.
   - Stage backend observability, frontend observability, focused tests, and the numbered `118` docs.
   - Explicitly avoid staging:
     - `docs/NEW_WORKFLOW_PROMPT.md`
     - `docs/TASK_INFO.md`
     - `docs/superpowers/`
     - caches, generated artifacts, `.env`, and secrets

15. Commit and push.
   - Commit with:
     ```bash
     git commit -m "feat: connect recovery replay to visualization"
     ```
   - Push with:
     ```bash
     git push -u origin codex/118-recovery-replay-visualization-v0
     ```

## 6. Testing Plan

- Unit tests:
  - `InternalObservabilityService` returns `recovery_replay_link_summary.status = "matched"` for a matching latest alias.
  - `InternalObservabilityService` returns `status = "missing"` when alias file is absent.
  - `InternalObservabilityService` returns `status = "invalid"` when alias payload is unreadable.
  - `InternalObservabilityService` returns `status = "mismatch"` when alias `source_report_path` differs from current run report path.
  - `InternalObservabilityService` returns `null` summary for non-eligible runs.
- Integration tests:
  - `/internal/runs/{run_id}/observability` returns additive replay-link JSON for a recovery benchmark run.
  - The route still returns `200` for missing, invalid, and mismatch alias states.
  - Response serialization still omits sensitive identifiers and secrets.
- Frontend tests:
  - Recovery panel renders the matched replay-link block.
  - Recovery panel renders degraded copy for missing and mismatch states.
- Smoke tests:
  - Load `5174`, inspect one sample run fixture, and confirm replay-link section text and copy buttons are visible.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py tests/test_recovery_replay_review.py -q
npm --prefix frontend test -- --run src/observability/ObservabilityPage.test.tsx
cd frontend && npx playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: connect recovery replay to visualization
```

Expected commands:

```bash
git status --short
git add backend/app/observability/schemas.py
git add backend/app/observability/service.py
git add frontend/src/observability/types.ts
git add frontend/src/observability/ObservabilityPage.tsx
git add frontend/src/observability/ObservabilityPage.test.tsx
git add frontend/e2e/internal-observability.spec.ts
git add tests/test_observability.py
git add tests/integration/test_observability_gateway.py
git add README.md
git add docs/WEB_DEMO_README.md
git add docs/specs/118-recovery-replay-visualization-v0.md
git add docs/plans/118-recovery-replay-visualization-v0-plan.md
git diff --cached --check
git commit -m "feat: connect recovery replay to visualization"
git push -u origin codex/118-recovery-replay-visualization-v0
```

The implementer must confirm `.env` and secrets are not staged, and must confirm unrelated untracked docs remain unstaged.

## 9. Out-of-scope Changes

- Do not change unrelated modules.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md` unless the spec explicitly requires it.
- Do not add new dependencies unless listed in this plan.
- Do not commit generated caches, virtual environments, or secrets.
- Do not modify recovery review runner behavior, benchmark suite membership, or replay execution semantics.
- Do not add new internal routes, file-download routes, or browser-based artifact viewers.
- Do not redesign system integrity summary, benchmark summary, or customer-facing UI.
- Do not widen this task into memory CRUD, user controls, or sensitive-memory minimization work.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/118-recovery-replay-visualization-v0.md`.
- [ ] The implementation stayed within the plan scope.
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] Recovery visualization still shows attempt details while adding replay-link details.
- [ ] Missing or stale latest aliases degrade gracefully instead of breaking the observability route.
- [ ] Matching requires both `case_id` and `source_report_path`, not case id alone.
- [ ] Existing customer-facing routes and UI remain unchanged.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- changed files
- verification commands and results
- which replay-link states were verified:
  - matched
  - missing
  - invalid
  - mismatch
- whether the route stayed additive and backward compatible
- whether reviewer-facing docs were updated
- commit hash
- push result
- confirmation that unrelated untracked docs stayed untouched
- any remaining limitation, especially that this task adds link visibility only and does not add replay rerun controls or report browsing
