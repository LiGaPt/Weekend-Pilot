# Plan: 127 Recovery and Safe-Stop Evidence Closure v0

## 1. Spec Reference

Spec file:

```text
docs/specs/127-recovery-safe-stop-evidence-closure-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
M5. Recovery and Memory Governance
M1. Evaluation and Observability Infrastructure
```

## 2. Current Repository Assumptions

- Current branch is `codex/126-conversation-plan-versioning-closure-v0`.
- Latest observed commit is `2879348 test: lock conversation and plan versioning closure`.
- Latest completed task is Task `126`.
- `docs/specs/` and `docs/plans/` match through Task `126`.
- The repository has known historical numbering irregularities:
  - special Task `113.5`
  - missing Task `122` in current tracked spec/plan sequence
- These irregularities should not be backfilled or renumbered.
- Existing untracked local files are unrelated and must remain unstaged:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Existing recovery foundations already include:
  - recovery replay review runner
  - generic suite replay review support
  - safe-stop gate runner
  - internal system integrity safe-stop summary
  - internal recovery visualization and replay link summary
  - frontend recovery visualization panel
- This task should add proof and closure, not redesign recovery behavior.

## 3. Files to Add

- `docs/specs/127-recovery-safe-stop-evidence-closure-v0.md` - task spec created from the approved content.
- `docs/plans/127-recovery-safe-stop-evidence-closure-v0-plan.md` - implementation plan created from the approved content.

No new source file is required by default. Add a new focused test file only if existing recovery/safe-stop test modules become too broad:

- Optional: `tests/test_recovery_safe_stop_evidence_closure.py`

Prefer extending existing test modules if the assertions naturally fit there.

## 4. Files to Modify

- `tests/test_recovery_replay_review.py` - add or tighten canonical and suite recovery evidence assertions.
- `tests/test_benchmark_safe_stop_gate.py` - add or tighten 8-case safe-stop evidence assertions.
- `tests/test_system_integrity_summary.py` - add stale/manual safe-stop summary regression coverage.
- `tests/test_benchmark_internal_summary.py` - update only if internal summary evidence fields change.
- `backend/app/benchmark/recovery_review.py` - modify only if review output lacks required failure reason, terminal status, or zero-write proof.
- `backend/app/benchmark/safe_stop_gate.py` - modify only if gate output does not expose sufficient case-level evidence.
- `backend/app/observability/integrity_summary.py` - modify only if safe-stop summary is hardcoded, stale, or does not load latest alias content correctly.
- `backend/app/observability/service.py` - modify only if recovery replay link summary misses latest alias, artifact, source report, or replay report.
- `backend/app/observability/schemas.py` - add fields only if a missing evidence value cannot be represented by the current schema.
- `frontend/src/observability/types.ts` - update only if backend schema changes.
- `frontend/src/observability/api.test.ts` - update only if API fixture shape changes.
- `frontend/src/observability/ObservabilityPage.test.tsx` - update only if recovery visualization rendering changes.
- `frontend/e2e/internal-observability.spec.ts` - update fixtures/assertions only if internal observability output changes.
- `README.md` and `docs/WEB_DEMO_README.md` - update only if verification command text or current evidence status needs correction.

## 5. Implementation Steps

1. Confirm repository state before editing.
   - Run `git status --short`.
   - Run `git branch --show-current`.
   - Run `git log --oneline -5`.
   - Confirm latest committed task is `126`.
   - Confirm unrelated untracked files remain unstaged.

2. Save the approved spec and plan.
   - Create `docs/specs/127-recovery-safe-stop-evidence-closure-v0.md`.
   - Create `docs/plans/127-recovery-safe-stop-evidence-closure-v0-plan.md`.
   - Do not modify historical task docs.

3. Inspect current recovery evidence contracts.
   - Read `backend/app/benchmark/recovery_review.py`.
   - Read `backend/app/benchmark/safe_stop_gate.py`.
   - Read `backend/app/benchmark/failure_chain.py`.
   - Read `backend/app/benchmark/schemas.py`.
   - Identify exactly where failure reason, recovery attempts, terminal workflow status, and action count are serialized.

4. Inspect current observability evidence contracts.
   - Read `backend/app/observability/integrity_summary.py`.
   - Read `backend/app/observability/service.py`.
   - Read `backend/app/observability/schemas.py`.
   - Confirm the internal summary loads:
     - `var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json`
     - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
   - Confirm recovery replay link summary can report:
     - latest alias path
     - review artifact path
     - source benchmark report path
     - replay report path

5. Inspect existing focused tests.
   - Read `tests/test_recovery_replay_review.py`.
   - Read `tests/test_benchmark_safe_stop_gate.py`.
   - Read `tests/test_system_integrity_summary.py`.
   - Read `tests/test_benchmark_internal_summary.py`.
   - Read `frontend/src/observability/ObservabilityPage.test.tsx`.
   - Read `frontend/e2e/internal-observability.spec.ts`.
   - Decide whether to extend existing modules or create `tests/test_recovery_safe_stop_evidence_closure.py`.

6. Write the stale/manual safe-stop summary regression first.
   - In `tests/test_system_integrity_summary.py`, add a test that writes or monkeypatches a temporary `latest-safe_stop_gate_v1-run-report.json` payload.
   - Make the payload contain distinctive values for suite id, case count, passed count, failed count, status, and report path.
   - Assert `_load_safe_stop_summary()` or the public integrity summary returns those distinctive values.
   - Assert changing the payload changes the returned summary.
   - Assert missing or invalid alias degrades section status as expected.
   - This test must fail if the summary is hardcoded to README-era counts.

7. Tighten safe-stop gate evidence assertions.
   - In `tests/test_benchmark_safe_stop_gate.py`, assert the current `safe_stop_gate_v1` evaluation covers exactly the current 8 `recovery_focused` cases.
   - For each case result, assert:
     - benchmark status is successful for the gate
     - workflow terminal status is `failed`
     - action count is `0`
     - terminal recovery action is `stop_safely`
     - failure chain is bounded
     - failure reason or injected failure signature is non-empty
   - Include representative coverage for:
     - `family_route_failure_v1`
     - `rainy_day_ticket_sold_out_v1`
     - `family_route_and_dining_unavailable_v1`
     - `family_ticket_sold_out_and_route_unavailable_v1`
     - `friends_route_and_dining_unavailable_v1`
     - `elder_ticket_sold_out_and_route_unavailable_v1`
     - `budget_queue_closed_constraint_v1`
     - `family_table_unavailable_replan_required_v1`

8. Tighten recovery replay review assertions.
   - In `tests/test_recovery_replay_review.py`, add or extend tests for:
     - default canonical review remains `family_route_failure_v1`
     - `--suite-id recovery_focused` resolves all current recovery-capable cases
     - review result includes source report path and replay report path
     - latest alias path is case-specific
     - failure chain summary includes injected effects and recovery actions
     - observability check links back to the source benchmark report
   - Ensure the tests do not depend on committed `var/` artifacts.

9. Make minimal production changes only if tests expose gaps.
   - If safe-stop summary uses stale constants, update `backend/app/observability/integrity_summary.py` to derive all counts/status from the latest alias payload.
   - If recovery review omits terminal status or zero action evidence from checks, update `backend/app/benchmark/recovery_review.py` check details or summary building.
   - If safe-stop gate omits case-level evidence, update `backend/app/benchmark/safe_stop_gate.py` with additive fields only.
   - If observability replay links are incomplete, update `backend/app/observability/service.py` without changing public customer API contracts.

10. Update frontend observability only if backend schema changes.
    - If new fields are added, update `frontend/src/observability/types.ts`.
    - Update `frontend/src/observability/api.test.ts` fixtures.
    - Update `frontend/src/observability/ObservabilityPage.test.tsx` to assert visible recovery visualization and latest artifact links.
    - Update `frontend/e2e/internal-observability.spec.ts` fixture only when the API shape changes.

11. Refresh local generated recovery evidence for verification.
    - Run `python scripts/run_benchmark_safe_stop_gate.py`.
    - Run `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`.
    - Run `python scripts/run_recovery_replay_review.py`.
    - Confirm local generated aliases update under `var/`.
    - Do not stage generated `var/` artifacts unless they are already tracked and intentionally required.

12. Update docs only if current text is stale.
    - Check `README.md` and `docs/WEB_DEMO_README.md`.
    - If they already correctly state current commands and evidence paths, leave them unchanged.
    - If they cite stale counts or omit the suite-level recovery review command, update narrowly.

13. Run focused backend tests.
    - Run:
      - `python -m pytest tests/test_recovery_replay_review.py tests/test_benchmark_safe_stop_gate.py tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py -q`
    - Fix failures with the smallest change that preserves existing behavior.

14. Run integration tests only if touched paths require them.
    - If recovery review orchestration changed, run:
      - `python -m pytest tests/integration/test_recovery_replay_review.py -q`
    - If observability service or gateway changed, run:
      - `python -m pytest tests/integration/test_observability_gateway.py -q`

15. Run frontend tests only if frontend files changed.
    - Run:
      - `npm --prefix frontend run test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx`
    - If E2E fixture or rendering changed, run:
      - `npm --prefix frontend run e2e -- internal-observability.spec.ts`

16. Run hygiene checks.
    - Run `git diff --check`.
    - Run `git status --short`.
    - Confirm only intended docs/tests/source files changed.
    - Confirm unrelated untracked local docs remain unstaged.
    - Confirm generated `var/` artifacts are not staged unless intentionally tracked.

17. Stage and commit.
    - Stage only:
      - Task 127 spec
      - Task 127 plan
      - focused tests
      - minimal production changes required by tests
      - narrowly updated docs if needed
    - Run `git diff --cached --check`.
    - Commit with:
      - `test: consolidate recovery safe-stop evidence`

18. Push.
    - If still on `codex/126-conversation-plan-versioning-closure-v0`, create/switch to:
      - `codex/127-recovery-safe-stop-evidence-closure-v0`
    - Push with:
      - `git push -u origin codex/127-recovery-safe-stop-evidence-closure-v0`

## 6. Testing Plan

- Backend focused tests:
  - `tests/test_recovery_replay_review.py`
  - `tests/test_benchmark_safe_stop_gate.py`
  - `tests/test_system_integrity_summary.py`
  - `tests/test_benchmark_internal_summary.py`

- Backend integration tests if production orchestration changes:
  - `tests/integration/test_recovery_replay_review.py`
  - `tests/integration/test_observability_gateway.py`

- Evidence-generation scripts:
  - `scripts/run_benchmark_safe_stop_gate.py`
  - `scripts/run_recovery_replay_review.py --suite-id recovery_focused`
  - `scripts/run_recovery_replay_review.py`

- Frontend tests only if frontend observability files change:
  - `frontend/src/observability/api.test.ts`
  - `frontend/src/observability/ObservabilityPage.test.tsx`
  - `frontend/e2e/internal-observability.spec.ts`

## 7. Verification Commands

Run before committing:

```bash
git status --short
git branch --show-current
git log --oneline -5
python -m pytest tests/test_recovery_replay_review.py tests/test_benchmark_safe_stop_gate.py tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py -q
python scripts/run_benchmark_safe_stop_gate.py
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
python scripts/run_recovery_replay_review.py
git diff --check
git status --short
```

Run if backend integration paths change:

```bash
python -m pytest tests/integration/test_recovery_replay_review.py tests/integration/test_observability_gateway.py -q
```

Run if frontend observability files change:

```bash
npm --prefix frontend run test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run e2e -- internal-observability.spec.ts
```

Run after staging:

```bash
git diff --cached --check
git status --short
```

## 8. Commit and Push Plan

Expected branch:

```text
codex/127-recovery-safe-stop-evidence-closure-v0
```

Expected commit message:

```text
test: consolidate recovery safe-stop evidence
```

Expected commands:

```bash
git switch -c codex/127-recovery-safe-stop-evidence-closure-v0
git add docs/specs/127-recovery-safe-stop-evidence-closure-v0.md docs/plans/127-recovery-safe-stop-evidence-closure-v0-plan.md
git add tests/test_recovery_replay_review.py tests/test_benchmark_safe_stop_gate.py tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py
git add backend/app/benchmark/recovery_review.py backend/app/benchmark/safe_stop_gate.py backend/app/observability/integrity_summary.py backend/app/observability/service.py backend/app/observability/schemas.py
git add frontend/src/observability/types.ts frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.test.tsx frontend/e2e/internal-observability.spec.ts
git add README.md docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "test: consolidate recovery safe-stop evidence"
git push -u origin codex/127-recovery-safe-stop-evidence-closure-v0
```

Only stage files that actually changed. Do not stage unrelated untracked files or generated artifacts.

## 9. Out-of-scope Changes

- Do not add new benchmark cases or recovery profiles.
- Do not change suite membership unless a current test proves the existing suite is inconsistent.
- Do not change recovery policy, retry budgets, or routing behavior.
- Do not change confirmation boundaries or Action Ledger write semantics.
- Do not add migrations or dependencies.
- Do not add AMap/provider behavior.
- Do not redesign the internal observability page.
- Do not change customer-facing public demo API contracts.
- Do not commit generated `var/` artifacts, caches, `.env`, credentials, or secrets.
- Do not stage:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/127-recovery-safe-stop-evidence-closure-v0.md`.
- [ ] The task stayed a recovery/safe-stop evidence closure and did not become a recovery feature expansion.
- [ ] Canonical recovery replay review still covers `family_route_failure_v1`.
- [ ] Suite recovery replay review covers all current `recovery_focused` cases.
- [ ] Safe-stop gate still covers 8 recovery-focused cases.
- [ ] Each covered failed path has failure reason or injected failure signature.
- [ ] Each covered failed path has at least one recovery attempt.
- [ ] Each covered failed path terminates with `stop_safely`.
- [ ] Each covered failed path has terminal workflow status `failed`.
- [ ] Each covered failed path has zero write actions.
- [ ] Safe-stop summary is loaded from latest alias payload, not hardcoded values.
- [ ] Internal observability recovery visualization links latest alias, review artifact, source report, and replay report.
- [ ] Required backend focused tests pass.
- [ ] Evidence-generation scripts pass or environment blockers are explicitly reported.
- [ ] Frontend tests pass if frontend files changed.
- [ ] `git diff --check` and `git diff --cached --check` pass.
- [ ] No generated artifacts, secrets, or unrelated local docs are committed.
- [ ] Commit message matches the plan.
- [ ] Push succeeds.

## 11. Handoff Notes

After finishing, report back:

- changed files
- whether production code changed or the task was tests/docs only
- final recovery-focused case count
- final safe-stop gate result
- final canonical recovery replay review result
- final suite recovery replay review result
- whether safe-stop summary stale/manual regression is covered by a focused test
- whether internal observability links latest alias, artifact, source report, and replay report
- verification commands and results
- any commands blocked by local service availability
- commit hash
- push result
- confirmation that unrelated untracked files were not staged
- recommended next task after recovery evidence closure
