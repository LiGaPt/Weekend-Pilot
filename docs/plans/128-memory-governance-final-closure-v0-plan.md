# Plan: 128 Memory governance final closure v0

## 1. Spec Reference

Spec file:

```text
docs/specs/128-memory-governance-final-closure-v0.md
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

- Current working directory is the WeekendPilot repository.
- Latest commit observed during planning is:

  ```text
  13842ce test: consolidate recovery safe-stop evidence
  ```

- Latest committed numbered task is Task `127`.
- `docs/specs` and `docs/plans` are matched through Task `127`, with one known historical numbering gap around Task `122`.
- No Task `128` spec or plan exists yet.
- Existing memory governance implementation already includes:
  - internal memory list/detail/create/update/control/delete routes
  - lifecycle actions `activate`, `disable`, `suppress`, `expire`, `mark_candidate`
  - delete-as-suppress behavior
  - governance control events
  - minimization events
  - additive `governance_audit`
  - `memory_query_policy_v1`
  - memory governance benchmark cases
- Existing unrelated untracked files are present and must not be staged:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Task `128` should be a tests/docs/evidence closure unless verification reveals a stale evidence-summary bug that requires a minimal production fix.

## 3. Files to Add

- `docs/specs/128-memory-governance-final-closure-v0.md` - approved Task 128 spec.
- `docs/plans/128-memory-governance-final-closure-v0-plan.md` - approved Task 128 implementation plan.
- `tests/test_memory_governance_delivery_surface.py` - optional focused closure tests if existing memory tests do not provide a single final regression surface.

## 4. Files to Modify

- `tests/test_memory_governance_audit.py` - tighten audit-preview coverage only if current helper tests miss final closure cases.
- `tests/test_memory_query_policy.py` - tighten explicit override, advisory, expired downgrade, weak/unsupported suppression, or sensitive minimization assertions only if gaps exist.
- `tests/test_memory_user_control.py` - expand lifecycle action and idempotency assertions if current baseline only covers disable/suppress.
- `tests/test_memory_crud_governance.py` - tighten CRUD/update/delete/minimization/governance-event assertions if needed.
- `tests/test_feedback_memory_candidates.py` - confirm sensitive fields do not become active governable memory.
- `tests/test_benchmark_suites.py` - lock memory governance suite membership and integrity memory-mode counts if current tests are incomplete.
- `tests/test_review_evidence.py` - ensure reviewer evidence includes memory governance aliases/status when applicable.
- `tests/test_demo_support_scripts.py` - ensure submission evidence summary reports memory governance status if current script coverage is incomplete.
- `tests/test_system_integrity_summary.py` - update only if memory governance status is stale or missing from system integrity summary tests.
- `backend/app/observability/integrity_summary.py` - update only if tests prove memory governance evidence is stale or hardcoded incorrectly.
- `scripts/show_submission_evidence.py` - update only if it omits existing memory-governance evidence needed for final delivery.
- `docs/MEMORY_GOVERNANCE_RUNBOOK.md` - update from V1 read-only slice wording to current local governance closure wording.
- `docs/submission/EVIDENCE_MAP.md` - add or tighten memory governance evidence references if stale.
- `docs/submission/FUNCTION_COVERAGE_MAP.md` - add or tighten reviewer-facing memory governance proof points if stale.
- `docs/submission/DEMO_SCRIPT.md` - add or tighten memory governance narration if stale.
- `docs/submission/RECORDING_CHECKLIST.md` - add or tighten memory governance checklist items if stale.
- `README.md` - update only if current delivery summary omits memory governance closure or incorrectly frames it as read-only.
- `docs/WEB_DEMO_README.md` - update only if reviewer flow omits memory governance evidence or local-governance boundary.

## 5. Implementation Steps

1. Confirm the starting state.
   - Run:
     ```bash
     git status --short
     git branch --show-current
     git log --oneline -5
     ```
   - Confirm latest commit corresponds to Task `127`.
   - Confirm `docs/specs/128-memory-governance-final-closure-v0.md` and `docs/plans/128-memory-governance-final-closure-v0-plan.md` do not already exist.
   - Note unrelated untracked local docs and keep them unstaged.

2. Save the approved Task 128 spec and plan.
   - Add the spec to:
     - `docs/specs/128-memory-governance-final-closure-v0.md`
   - Add the plan to:
     - `docs/plans/128-memory-governance-final-closure-v0-plan.md`
   - Do not edit historical specs/plans.

3. Audit existing memory tests before adding new tests.
   - Read:
     - `tests/test_memory_governance_audit.py`
     - `tests/test_memory_query_policy.py`
     - `tests/test_memory_user_control.py`
     - `tests/test_memory_crud_governance.py`
     - `tests/test_feedback_memory_candidates.py`
     - `tests/test_benchmark_suites.py`
     - `tests/integration/test_memory_api_gateway.py`
     - `tests/integration/test_memory_crud_api_gateway.py`
     - `tests/integration/test_langgraph_workflow_gateway.py`
   - Map current coverage against Task 128 acceptance criteria.
   - Prefer strengthening existing focused tests over creating a large duplicate test file.

4. Close any CRUD/lifecycle regression gaps.
   - Ensure service/API-level tests prove:
     - create stores canonical minimized `value_json`
     - create stores `text = null`
     - list/detail query returns lifecycle state and `governance_audit`
     - update preserves immutable provenance fields
     - delete suppresses to `ignored`
     - control actions include `activate`, `disable`, `suppress`, `expire`, `mark_candidate`
     - idempotent no-op controls do not append duplicate control events
     - create/applied update append minimization events
   - If existing tests already prove a point, do not duplicate it.

5. Close any read-memory policy regression gaps.
   - Ensure tests prove:
     - explicit user input suppresses conflicting memory
     - advisory memory fills vague requests
     - expired high-confidence memory is downgraded to advisory
     - weak or unsupported memory cannot mutate intent
     - disabled, ignored, and candidate memory stay out of active planning
     - sensitive memory or extra payload fields do not enter active planning
   - Preserve existing `memory_query_policy_v1` output names and policy summary shape.

6. Close benchmark/evidence registration gaps.
   - Ensure `tests/test_benchmark_suites.py` proves the focused `memory_governance` suite includes the current memory cases:
     - `family_memory_override_v1`
     - `family_memory_advisory_fill_v1`
     - `family_memory_expired_advisory_v1`
     - `family_memory_disabled_ignored_v1`
     - `family_memory_candidate_not_auto_active_v1`
     - `family_memory_sensitive_minimization_v1`
   - Ensure memory-mode counts in `v2_integrity` / `all_registered` remain covered by current tests.
   - Do not add new cases or change suite membership unless a current test proves a mismatch.

7. Check system integrity and submission evidence surfaces.
   - Inspect:
     - `backend/app/observability/integrity_summary.py`
     - `scripts/show_submission_evidence.py`
     - `tests/test_system_integrity_summary.py`
     - `tests/test_demo_support_scripts.py`
     - `tests/test_review_evidence.py`
   - If memory governance status is already derived and tested, leave production code unchanged.
   - If memory governance status is stale, missing, or hardcoded incorrectly, update the smallest summary/script path and add a focused regression.

8. Update `docs/MEMORY_GOVERNANCE_RUNBOOK.md`.
   - Replace the old "V1 read-only slice" framing with current closure wording.
   - Preserve historical context where useful, but make the current boundary explicit:
     - local memory governance loop
     - internal CRUD/control/delete lifecycle
     - audit preview
     - durable governance metadata
     - sensitive minimization
     - benchmark evidence
   - State explicitly that the current implementation does not depend on:
     - real user profiles
     - external accounts
     - third-party identity
     - vector databases
     - real personalization services
   - Include the focused verification commands and canonical evidence aliases.

9. Update submission-facing docs narrowly if stale.
   - Check:
     - `docs/submission/EVIDENCE_MAP.md`
     - `docs/submission/FUNCTION_COVERAGE_MAP.md`
     - `docs/submission/DEMO_SCRIPT.md`
     - `docs/submission/RECORDING_CHECKLIST.md`
     - `README.md`
     - `docs/WEB_DEMO_README.md`
   - Add or tighten memory governance evidence wording only where current text is stale or incomplete.
   - Do not rewrite unrelated demo, AMap, recovery, or benchmark sections.

10. Run focused memory unit tests.
    - Run:
      ```bash
      python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/test_feedback_memory_candidates.py tests/test_benchmark_suites.py -q
      ```
    - Fix failures with the smallest changes that preserve existing behavior.

11. Run focused memory integration tests.
    - Run:
      ```bash
      python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
      ```
    - If local database or Redis setup blocks integration tests, report the blocker and still complete non-service-dependent tests.

12. Run reviewer/evidence tests.
    - Run:
      ```bash
      python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
      ```
    - If system integrity or observability code changed, also run:
      ```bash
      python -m pytest tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py tests/test_observability.py -q
      python -m pytest tests/integration/test_observability_gateway.py -q
      ```

13. Inspect canonical evidence summary.
    - Run:
      ```bash
      python scripts/show_submission_evidence.py
      ```
    - Confirm output includes the existing current evidence aliases and memory governance status through the current system integrity / benchmark surfaces.
    - Do not stage generated `var/` changes.

14. Run hygiene checks.
    - Run:
      ```bash
      git diff --check
      git status --short
      ```
    - Confirm only Task 128 docs, focused tests, and narrowly necessary docs/source files are modified.
    - Confirm unrelated untracked files remain unstaged.
    - Confirm no `.env`, secrets, generated artifacts, caches, virtual environments, `node_modules`, frontend build output, or Playwright artifacts are staged.

15. Stage and commit.
    - Stage only files changed for Task `128`.
    - Run:
      ```bash
      git diff --cached --check
      ```
    - Commit with:
      ```bash
      git commit -m "test: close memory governance delivery surface"
      ```

16. Push.
    - Use branch:
      ```text
      codex/128-memory-governance-final-closure-v0
      ```
    - If not already on that branch, create/switch before implementation commit:
      ```bash
      git switch -c codex/128-memory-governance-final-closure-v0
      ```
    - Push:
      ```bash
      git push -u origin codex/128-memory-governance-final-closure-v0
      ```

## 6. Testing Plan

- Unit tests:
  - `tests/test_memory_governance_audit.py` for trusted/advisory/expired/weak/unsupported/non-governable audit states.
  - `tests/test_memory_query_policy.py` for explicit override, advisory fill, expired downgrade, weak suppression, and unsupported suppression.
  - `tests/test_memory_user_control.py` for lifecycle actions, idempotency, and governance event preservation.
  - `tests/test_memory_crud_governance.py` for create/detail/update/delete, canonical minimization, audit preview, and metadata events.
  - `tests/test_feedback_memory_candidates.py` for sensitive minimization and candidate-only memory.
  - `tests/test_benchmark_suites.py` for memory-governance suite membership and integrity taxonomy counts.

- Integration tests:
  - `tests/integration/test_memory_api_gateway.py` for baseline list/control compatibility.
  - `tests/integration/test_memory_crud_api_gateway.py` for CRUD route behavior.
  - `tests/integration/test_langgraph_workflow_gateway.py -k "memory"` for workflow query-shaping behavior.

- Evidence/doc tests:
  - `tests/test_review_evidence.py` for canonical evidence docs.
  - `tests/test_demo_support_scripts.py` for submission evidence script behavior.
  - `tests/test_system_integrity_summary.py` and `tests/test_benchmark_internal_summary.py` only if summary code changes.

- Smoke checks:
  - `python scripts/show_submission_evidence.py`
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
git status --short
git branch --show-current
git log --oneline -5

python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/test_feedback_memory_candidates.py tests/test_benchmark_suites.py -q
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py

git diff --check
git status --short
```

Run if system integrity or observability summary files change:

```bash
python -m pytest tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py tests/test_observability.py -q
python -m pytest tests/integration/test_observability_gateway.py -q
```

Run after staging:

```bash
git diff --cached --check
git status --short
```

## 8. Commit and Push Plan

Expected branch:

```text
codex/128-memory-governance-final-closure-v0
```

Expected commit message:

```text
test: close memory governance delivery surface
```

Expected commands:

```bash
git status --short
git switch -c codex/128-memory-governance-final-closure-v0
git add docs/specs/128-memory-governance-final-closure-v0.md docs/plans/128-memory-governance-final-closure-v0-plan.md
git add tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/test_feedback_memory_candidates.py tests/test_benchmark_suites.py
git add tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py
git add tests/test_review_evidence.py tests/test_demo_support_scripts.py tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py
git add docs/MEMORY_GOVERNANCE_RUNBOOK.md docs/submission/EVIDENCE_MAP.md docs/submission/FUNCTION_COVERAGE_MAP.md docs/submission/DEMO_SCRIPT.md docs/submission/RECORDING_CHECKLIST.md README.md docs/WEB_DEMO_README.md
git add backend/app/observability/integrity_summary.py scripts/show_submission_evidence.py
git diff --cached --check
git commit -m "test: close memory governance delivery surface"
git push -u origin codex/128-memory-governance-final-closure-v0
```

Only stage files that actually changed. Do not stage unrelated untracked files or generated artifacts.

## 9. Out-of-scope Changes

- Do not implement frontend memory-management UI.
- Do not add auth, permissions, external accounts, real user profiles, or third-party identity integration.
- Do not add vector DBs, embeddings, broader personalization, new memory keys, or new memory types.
- Do not redesign retention policy or implement physical hard delete.
- Do not change `memory_query_policy_v1` contract, benchmark grading semantics, or workflow topology.
- Do not change confirmation boundaries, execution safety, Tool Gateway write policy, Action Ledger behavior, or recovery routing.
- Do not add AMap/provider behavior.
- Do not refresh or stage generated `var/` evidence unless explicitly required and tracked.
- Do not stage:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Do not stage `.env`, API keys, tokens, secrets, caches, virtual environments, `node_modules`, frontend build output, or Playwright artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/128-memory-governance-final-closure-v0.md`.
- [ ] Task `128` stayed a memory governance closure and did not become a new feature expansion.
- [ ] Memory CRUD, list/detail, update, delete-as-suppress, disable, activate, expire, suppress, and mark-candidate behavior are covered.
- [ ] Governance control events and minimization events are tested.
- [ ] Explicit user input, advisory memory, expired downgrade, weak suppression, unsupported suppression, and non-governable lifecycle exclusion are tested.
- [ ] Sensitive memory minimization is tested and does not place raw sensitive data into active planning.
- [ ] Memory governance benchmark suite membership and integrity memory-mode coverage are locked.
- [ ] `docs/MEMORY_GOVERNANCE_RUNBOOK.md` describes the current local governance loop and external-account non-dependency.
- [ ] Submission/evidence docs mention memory governance evidence clearly and accurately.
- [ ] `python scripts/show_submission_evidence.py` still reports expected evidence.
- [ ] Required focused unit tests passed.
- [ ] Required integration tests passed or local service blockers are explicitly reported.
- [ ] `git diff --check` and `git diff --cached --check` passed.
- [ ] No generated artifacts, secrets, or unrelated local docs are committed.
- [ ] Commit message matches the plan.
- [ ] Push succeeds.

## 11. Handoff Notes

After finishing, report back:

- changed files
- whether production code changed or the task was tests/docs only
- final memory governance regression surface covered
- final memory benchmark case count and suite membership
- final runbook boundary wording
- verification commands and results
- any commands blocked by local service availability
- commit hash
- push result
- confirmation that unrelated untracked files were not staged
- recommended next task after memory governance closure
