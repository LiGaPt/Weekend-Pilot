# Plan: 121 Execution safety and ledger hardening v0

## 1. Spec Reference

Spec file:

```text
docs/specs/121-execution-safety-ledger-hardening-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/121-execution-safety-ledger-hardening-v0`.
- Latest commit is:

```text
5288674 feat: harden execution safety and action ledger
```

- `docs/specs/` and `docs/plans/` are tracked and matched through Task `120`; Task `121` spec/plan drafts exist locally but are not yet committed.
- Existing unrelated untracked local files must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Current repository code already contains Task `121` implementation signals:
  - `backend/app/execution/schemas.py` defines `skipped_due_to_prior_failure`
  - `backend/app/execution/workflow.py` references `rollback_status`, `rollback_reason`, `rollback_candidate_action_refs`, and `replayed_from_ledger`
  - focused tests already assert replay and skipped-tail behavior
- Existing gaps to close for this task are therefore documentation alignment, explicit plan/spec formalization, and final verification that implementation behavior matches the intended contract.

## 3. Files to Add

Use an empty list if no files are added.

- None. The target numbered spec and plan files already exist locally and should be finalized rather than introduced as brand-new paths.

## 4. Files to Modify

- `docs/specs/121-execution-safety-ledger-hardening-v0.md` - finalize the task spec so it matches current repository state and the actual implemented behavior.
- `docs/plans/121-execution-safety-ledger-hardening-v0-plan.md` - finalize the implementation plan so it is decision-complete for a fresh execution session.
- `backend/app/repositories/action_ledger.py` - verify and, if needed, tighten replay-oriented lookup helpers around `idempotency_key`.
- `backend/app/execution/schemas.py` - verify additive result-schema fields and bounded status values.
- `backend/app/execution/workflow.py` - verify terminal replay, ledger-backed resume, stop-on-first-failure, skipped-tail actions, and rollback metadata persistence.
- `backend/app/tool_gateway/gateway.py` - verify gateway-side ledger reuse semantics remain aligned with repository lookup-first behavior.
- `backend/app/demo/service.py` - verify repeated confirm continues to route through safe replay semantics without changing outward confirmation behavior.
- `tests/test_execution_workflow.py` - verify unit coverage fully pins replay, safe-stop, and rollback metadata semantics.
- `tests/test_human_confirmation.py` - verify duplicate confirm stays idempotent with persisted execution metadata.
- `tests/integration/test_execution_workflow_gateway.py` - verify end-to-end replay and ledger-backed reconstruction behavior.
- `tests/integration/test_human_confirmation_gateway.py` - verify duplicate confirm does not create duplicate side effects.
- `tests/integration/test_langgraph_workflow_gateway.py` - verify workflow-level zero pre-confirmation writes and safe duplicate-confirm execution behavior.

## 5. Implementation Steps

1. Reconfirm current task selection before any edits.
   - Check `git status --short`, `git branch --show-current`, and `git log --oneline -3`.
   - Confirm the repository is already on the Task `121` branch and that the latest commit corresponds to Task `121`.
   - Confirm the untracked `121` spec/plan files are the only task-local docs still needing formal closure.

2. Inspect the execution hardening implementation against the intended contract.
   - Read:
     - `backend/app/execution/workflow.py`
     - `backend/app/execution/schemas.py`
     - `backend/app/repositories/action_ledger.py`
     - `backend/app/tool_gateway/gateway.py`
     - `backend/app/demo/service.py`
   - Verify that code paths already implement:
     - terminal execution replay from persisted execution summary
     - ledger-backed hydration by `idempotency_key`
     - stop-on-first-terminal-failure behavior
     - skipped tail-action serialization
     - additive rollback metadata persistence

3. Inspect the focused regression coverage.
   - Read:
     - `tests/test_execution_workflow.py`
     - `tests/test_human_confirmation.py`
     - `tests/integration/test_execution_workflow_gateway.py`
     - `tests/integration/test_human_confirmation_gateway.py`
     - `tests/integration/test_langgraph_workflow_gateway.py`
   - Verify tests already cover:
     - replay without new ToolGateway calls
     - duplicate confirm safety
     - partial ledger resume
     - skipped actions after first failure
     - rollback metadata
     - zero pre-confirmation writes

4. Reconcile code and docs for the replay contract.
   - Make sure the spec and plan describe the same bounded statuses and fields used by code.
   - Keep terminology consistent across docs and tests:
     - `replayed_from_ledger`
     - `skipped_due_to_prior_failure`
     - `rollback_status`
     - `rollback_reason`
     - `rollback_candidate_action_refs`
   - If current code uses different wording than the draft spec, update docs to match code unless a real implementation bug is discovered.

5. Verify Action Ledger replay primitives are explicit and narrow.
   - Ensure `backend/app/repositories/action_ledger.py` exposes direct replay-oriented helpers by `idempotency_key`.
   - Ensure the workflow does not rely primarily on unique-constraint exceptions for replay behavior.
   - If helper naming or return shape is ambiguous, tighten it only enough to make the replay contract unambiguous.

6. Verify execution ordering and stop semantics.
   - Ensure `execute_confirmed_plan(...)` processes actions strictly by ascending `execution_order`.
   - Ensure the first terminal failure stops any further live tool invocation.
   - Ensure later actions are serialized as `skipped_due_to_prior_failure` instead of being omitted.
   - Ensure succeeded/failed counts exclude skipped tail actions.

7. Verify replay and resume paths are separated clearly.
   - Confirm three effective execution modes remain valid:
     - replay existing persisted terminal execution summary
     - rebuild from durable ledger rows when execution summary is missing or incomplete
     - fresh execution when no prior durable evidence exists
   - Ensure the workflow does not invoke later actions if an earlier hydrated ledger row already represents failure.
   - Ensure all-action ledger hydration can persist a missing plan-level execution summary without writing new side effects.

8. Verify duplicate-confirm safety at the service boundary.
   - Ensure `HumanConfirmationService.confirm_plan(...)` remains outwardly idempotent.
   - Ensure repeated `/demo/runs/{run_id}/confirm` reuses deterministic replay rather than creating duplicate writes.
   - Ensure no selected-plan routing or pre-confirmation semantics are widened in this task.

9. Finalize the numbered spec document.
   - Update `docs/specs/121-execution-safety-ledger-hardening-v0.md` so it:
     - matches the actual branch and repository state
     - describes the current higher-priority rationale over opening a new recovery-chaos task
     - keeps scope strictly backend-only and execution-safety-focused
     - preserves additive-only API and schema expectations

10. Finalize the numbered plan document.
    - Update `docs/plans/121-execution-safety-ledger-hardening-v0-plan.md` so it:
      - matches the template structure exactly
      - reflects the current branch and latest commit
      - names only the files genuinely relevant to Task `121`
      - gives a fresh execution session enough detail to verify or finish the implementation without making design decisions

11. Run focused verification.
    - Run:
      - `python -m pytest tests/test_human_confirmation.py tests/test_execution_workflow.py -q`
      - `python -m pytest tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py -q`
      - `python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "confirmation or execution" -q`
    - If any test fails, treat it as a Task `121` convergence blocker and update code or docs accordingly.

12. Run repository hygiene checks.
    - Run:
      - `git diff --check`
      - `git status --short`
    - Confirm only Task `121` backend/tests/docs files are modified or staged.
    - Confirm unrelated local docs and generated artifacts remain unstaged.

13. Prepare commit closure.
    - Stage only Task `121` files.
    - Commit with:
      - `feat: harden execution safety and action ledger`
    - Push the current `codex/121-execution-safety-ledger-hardening-v0` branch after verification passes.

## 6. Testing Plan

- Unit tests:
  - `tests/test_execution_workflow.py`
    - stop after first failure
    - skipped tail actions
    - replay existing execution summary
    - ledger-backed reconstruction
    - resume from partial ledger prefix
    - rollback metadata values
  - `tests/test_human_confirmation.py`
    - repeated confirm remains idempotent with existing execution metadata

- Integration tests:
  - `tests/integration/test_execution_workflow_gateway.py`
    - repository + gateway + execution wiring obeys safe-stop semantics
    - repeated execution does not duplicate writes
    - ledger-backed resume persists combined execution summary correctly
  - `tests/integration/test_human_confirmation_gateway.py`
    - duplicate confirm does not create duplicate ledger rows or duplicate provider-side writes
  - `tests/integration/test_langgraph_workflow_gateway.py`
    - workflow-level confirm/re-entry preserves zero pre-confirmation writes and duplicate-confirm safety

- Smoke tests:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_human_confirmation.py tests/test_execution_workflow.py -q
python -m pytest tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py -q
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "confirmation or execution" -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: harden execution safety and action ledger
```

Expected commands:

```bash
git status --short
git add docs/specs/121-execution-safety-ledger-hardening-v0.md docs/plans/121-execution-safety-ledger-hardening-v0-plan.md backend/app/repositories/action_ledger.py backend/app/execution/schemas.py backend/app/execution/workflow.py backend/app/tool_gateway/gateway.py backend/app/demo/service.py tests/test_execution_workflow.py tests/test_human_confirmation.py tests/integration/test_execution_workflow_gateway.py tests/integration/test_human_confirmation_gateway.py tests/integration/test_langgraph_workflow_gateway.py
git diff --cached --check
git commit -m "feat: harden execution safety and action ledger"
git push -u origin codex/121-execution-safety-ledger-hardening-v0
```

The implementer must confirm `.env`, secrets, generated artifacts, and unrelated local docs are not staged.

## 9. Out-of-scope Changes

- Do not add compensation tools or rollback executors.
- Do not add operator replay UI or admin APIs.
- Do not redesign confirmation payloads or selected-plan routing.
- Do not expand benchmark suites or introduce Task `122` recovery-chaos scope in this task.
- Do not modify unrelated memory, observability, or frontend modules.
- Do not touch unrelated local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Do not stage `var/`, caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/121-execution-safety-ledger-hardening-v0.md`.
- [ ] The task stayed backend-only and execution-safety-focused.
- [ ] Execution stops after the first terminal failure.
- [ ] Later confirmed actions are represented as `skipped_due_to_prior_failure`.
- [ ] Existing terminal execution summaries replay without new ToolGateway calls.
- [ ] Existing ledger rows can reconstruct or resume execution without duplicate writes.
- [ ] Duplicate confirm does not create duplicate side effects.
- [ ] Rollback metadata is explicit and bounded.
- [ ] Confirmation boundary and AMAP read-only restrictions remain unchanged.
- [ ] Focused unit and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back:

- exact files changed
- the final additive execution summary shape
- the final action-result replay / skipped fields
- the exact rollback metadata contract and bounded values
- whether ToolGateway behavior changed or only workflow replay logic changed
- verification commands run and their results
- commit hash
- push result
- confirmation that unrelated local docs remained untouched
- known limitations, especially that real compensating rollback and operator-driven retry remain future work
