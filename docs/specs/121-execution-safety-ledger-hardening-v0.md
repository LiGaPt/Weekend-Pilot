# Spec: 121 Execution safety and ledger hardening v0

## 1. Goal

Harden the deterministic execution layer so that WeekendPilot side-effect execution is safe to replay, safe to stop, and auditable when a confirmed plan is executed more than once or partially completes.

After Task `120`, the repository already has a stable human confirmation boundary, deterministic confirmed action generation, and durable `action_ledger` rows with unique `idempotency_key`. However, the current execution flow still has three safety gaps. First, execution continues through later confirmed write actions even after an earlier write action fails, which weakens the intended safe-stop boundary. Second, duplicate confirmation or repeated execution re-entry depends mostly on provider-level idempotency and unique-key behavior instead of one explicit repository-backed replay contract. Third, if some ledger rows exist but the plan-level `execution` summary was not fully persisted, the execution workflow does not have a defined recovery path for resuming safely from durable ledger facts.

After this task, execution must stop on the first terminal write failure, duplicate confirmation and repeated execution must replay deterministically from existing durable execution evidence, and partial-success semantics must be explicit and auditable. Rollback semantics must also be explicit: this task does not introduce compensating write tools, so failed executions must record that rollback was not attempted rather than implying that compensation occurred.

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in these areas:

- deterministic execution workflow
- Action Ledger
- human-in-the-loop confirmation boundary
- PostgreSQL as durable source of truth
- failure handling and recovery
- benchmark-driven execution safety
- small, reviewable tasks

This task maps to `docs/NEXT_PHASE_ROADMAP.md` milestone `M5. 恢复与治理`. Although the roadmap’s default near-term emphasis is `M1. 评测与观测基础设施`, this task is a higher-priority convergence slice because it closes an execution-safety gap in the confirmed write path. The current repository state also shows that Task `121` has already been partially carried into branch and code, so the correct next move is to finish and formalize it before opening a new recovery-chaos expansion task.

Relevant existing task chain:

- Task `014` established the human confirmation boundary.
- Task `015` established deterministic execution workflow.
- Task `091` reinforced pre-confirmation action-list semantics.
- Task `099` and `118` expanded replay and recovery visibility.
- Task `120` closed memory-governance hardening, leaving execution safety as the next highest-risk deterministic gap.

## 3. Requirements

### A. Keep scope focused on execution and ledger hardening

- This task must stay backend-only.
- It must not introduce new UI flows, new write tools, or new benchmark suites.
- It must not redesign plan generation, confirmation routing, or memory governance.
- It must not change the current confirmed action payload contract produced by `HumanConfirmationService` except for additive execution metadata.

### B. Add durable Action Ledger replay primitives

- `backend/app/repositories/action_ledger.py` must expose one explicit read/replay helper for durable idempotency by `idempotency_key`.
- The repository contract must support:
  - loading an existing ledger row by `idempotency_key`
  - reusing an existing terminal row without attempting a second insert
  - listing all ledger rows for one run in deterministic order
- The repository must remain the source of truth for execution replay decisions.
- This task must not rely on catching a database unique-constraint failure as the primary replay mechanism.

### C. Stop execution after the first terminal write failure

- `DeterministicExecutionWorkflow.execute_confirmed_plan(...)` must process confirmed actions in ascending `execution_order`.
- Once one action returns a terminal failure status:
  - `failed`
  - `blocked`
  - `rate_limited`
- the workflow must not invoke any later confirmed write action.
- Remaining later actions must be represented explicitly in the execution summary as skipped because of a prior failure.
- This task must not silently omit unexecuted tail actions from the persisted execution summary.

### D. Make repeated execution idempotent at the workflow layer

If a selected plan already has a persisted terminal `execution` summary and a terminal execution plan status:

- `executed`
- `partially_executed`
- `execution_failed`
- `execution_skipped`

then `execute_confirmed_plan(...)` must return a deterministic replay of the existing execution result and must not invoke Tool Gateway again.

This replay must preserve:

- workflow status
- plan status
- action result ordering
- succeeded / failed counts
- existing action IDs, tool event IDs, response payloads, and error payloads when present

### E. Support ledger-backed recovery when execution summary is missing or incomplete

If a confirmed selected plan does not yet have a persisted terminal `execution` summary, but one or more confirmed actions already have durable `action_ledger` rows:

- the execution workflow must treat those ledger rows as authoritative for the matching confirmed actions
- it must hydrate action results from ledger for those action refs instead of reinvoking the provider
- it must continue only from the first missing action, in order
- if a hydrated ledger row is a terminal failure, the workflow must stop and mark later actions as skipped due to prior failure
- if all confirmed actions are already represented by ledger rows, the workflow must persist the missing plan-level execution summary without issuing new write calls

### F. Make rollback semantics explicit and auditable

This task does not add compensating write tools. Therefore:

- when all executed actions succeed, workflow-level rollback status must be `not_needed`
- when the first executed action fails and no prior action succeeded, workflow-level rollback status must be `not_applicable`
- when one or more earlier actions succeeded but a later action fails, workflow-level rollback status must be `not_attempted`
- the persisted execution summary must include:
  - `rollback_status`
  - `rollback_reason`
  - `rollback_candidate_action_refs`
- `rollback_reason` must use bounded values:
  - `all_actions_succeeded`
  - `no_successful_actions_before_failure`
  - `compensation_tools_not_available`
- `rollback_candidate_action_refs` must list only the succeeded or idempotent-replay action refs that completed before the first failure

### G. Extend execution result schemas additively

`backend/app/execution/schemas.py` must extend the existing schema additively.

Per-action results must include:

- `replayed_from_ledger: bool`
- `skipped_due_to_prior_failure: bool`

Workflow results must include:

- `rollback_status`
- `rollback_reason`
- `rollback_candidate_action_refs`

Allowed action result statuses must include one new bounded status:

- `skipped_due_to_prior_failure`

This new status is only valid for actions that were not invoked because an earlier confirmed write action failed.

### H. Preserve confirmation idempotency and duplicate-confirm safety

- `HumanConfirmationService.confirm_plan(...)` must remain idempotent for already confirmed plans.
- Repeating `/demo/runs/{run_id}/confirm` for a plan that already executed, partially executed, execution-failed, or execution-skipped must not create duplicate ledger rows or duplicate provider-side writes.
- The confirm path may still call the execution workflow, but the execution workflow must resolve the call as deterministic replay when prior execution evidence already exists.

### I. Keep existing confirmation boundary and write-tool restrictions intact

- No write tool may run before confirmation.
- Confirmed action validation must still require write-tool membership and `user_confirmed = true`.
- This task must not weaken AMAP read-only preview restrictions.
- This task must not change selected-plan resolution rules in the demo service.

### J. Add focused unit and integration regressions

Add or update tests covering:

- Action Ledger repository replay / reuse behavior
- execution stops after first failure and marks later actions as skipped
- repeated execution of an already executed plan does not invoke Tool Gateway again
- confirmed plan with existing partial ledger rows resumes safely from ledger facts
- repeated confirm on an already executed or partially executed plan does not duplicate writes
- workflow-level confirm and auto-confirm paths still respect zero pre-confirmation writes

## 4. Non-goals

- Do not add real rollback or compensation tools.
- Do not add operator-triggered retry UI or manual replay UI.
- Do not redesign `confirmed_actions`.
- Do not add new benchmark cases or change suite membership.
- Do not change frontend APIs unless additive response compatibility requires no client update.
- Do not alter memory-governance behavior, conversation continuity, or observability surface design.
- Do not commit `.env`, API keys, tokens, secrets, generated artifacts, or caches.

## 5. Interfaces and Contracts

### Inputs

- Existing confirmed selected plans with:
  - `plan.status = "confirmed"` or an existing terminal execution status
  - `plan_json["confirmed_actions"]`
  - `plan_json["confirmation"]`
- Existing `action_ledger` rows keyed by `idempotency_key`
- Existing `ToolGateway.invoke(...)` execution path
- Existing `/demo/runs/{run_id}/confirm` path and workflow auto-confirm path

### Outputs

- Deterministic execution replay when terminal execution already exists
- Ledger-backed recovery when durable action rows exist without a full execution summary
- Safe-stop execution summaries that explicitly mark tail actions as skipped
- Additive rollback metadata in persisted execution summaries
- No duplicate side-effect writes for repeated confirm or repeated execution re-entry

### Schemas

Example additive execution summary:

```json
{
  "schema_version": "execution_workflow_v1",
  "workflow_version": "deterministic_execution_workflow_v1",
  "status": "partially_succeeded",
  "plan_status": "partially_executed",
  "started_at": "2026-06-30T10:00:00+00:00",
  "finished_at": "2026-06-30T10:00:02+00:00",
  "succeeded_count": 1,
  "failed_count": 1,
  "rollback_status": "not_attempted",
  "rollback_reason": "compensation_tools_not_available",
  "rollback_candidate_action_refs": [
    "draft_1_action_1"
  ],
  "action_results": [
    {
      "action_ref": "draft_1_action_1",
      "execution_order": 1,
      "tool_name": "reserve_restaurant",
      "target_id": "dining_draft_1",
      "idempotency_key": "confirm:run:plan:draft_1_action_1",
      "status": "succeeded",
      "replayed_from_ledger": false,
      "skipped_due_to_prior_failure": false
    },
    {
      "action_ref": "draft_1_action_2",
      "execution_order": 2,
      "tool_name": "send_message",
      "target_id": "family_group",
      "idempotency_key": "confirm:run:plan:draft_1_action_2",
      "status": "failed",
      "replayed_from_ledger": false,
      "skipped_due_to_prior_failure": false,
      "error_json": {
        "error_type": "provider_unavailable"
      }
    },
    {
      "action_ref": "draft_1_action_3",
      "execution_order": 3,
      "tool_name": "order_addon",
      "target_id": "dessert_combo",
      "idempotency_key": "confirm:run:plan:draft_1_action_3",
      "status": "skipped_due_to_prior_failure",
      "replayed_from_ledger": false,
      "skipped_due_to_prior_failure": true
    }
  ]
}
```

Example workflow replay of an already executed plan:

```json
{
  "status": "succeeded",
  "plan_status": "executed",
  "rollback_status": "not_needed",
  "rollback_reason": "all_actions_succeeded",
  "rollback_candidate_action_refs": [],
  "action_results": [
    {
      "action_ref": "draft_1_action_1",
      "status": "succeeded",
      "replayed_from_ledger": true,
      "skipped_due_to_prior_failure": false
    }
  ]
}
```

## 6. Observability

This task must keep observability additive and bounded.

Required durable evidence:

- existing `action_ledger` rows remain the durable per-action source of truth
- persisted `plan_json["execution"]` must now include:
  - `rollback_status`
  - `rollback_reason`
  - `rollback_candidate_action_refs`
  - per-action `replayed_from_ledger`
  - per-action `skipped_due_to_prior_failure`

This task must not add a new top-level artifact format. Existing observability and internal summary code may consume the additive execution fields but must remain backward compatible if those fields are absent on old rows.

## 7. Failure Handling

- Missing plan, wrong run, unselected plan, declined plan, malformed confirmed actions, or malformed plan JSON must still raise deterministic execution errors.
- If Tool Gateway returns an unsupported status, execution must fail loudly rather than guessing behavior.
- If an existing persisted execution summary is malformed, the execution workflow must raise a deterministic error rather than replaying unsafe data.
- If ledger rows exist with duplicate or conflicting statuses for the same confirmed action contract, the execution workflow must fail deterministically.
- If a ledger row exists for a later action but an earlier action is missing and there is no persisted execution summary, the execution workflow must not reorder execution; it must only trust the confirmed action order.
- If a terminal failure is encountered from either a live gateway call or a hydrated ledger row, no later action may be invoked.
- If rollback is not supported, the workflow must record that fact explicitly instead of implying successful compensation.

## 8. Acceptance Criteria

- [ ] `ActionLedgerRepository` exposes explicit replay-oriented lookup behavior by `idempotency_key`.
- [ ] `DeterministicExecutionWorkflow` stops after the first terminal failure and does not invoke later confirmed write actions.
- [ ] Later uninvoked confirmed actions are represented as `skipped_due_to_prior_failure`.
- [ ] Re-executing a plan with an already persisted terminal execution summary does not invoke ToolGateway again.
- [ ] Re-executing a confirmed plan with existing ledger rows but missing execution summary reuses ledger facts instead of duplicating writes.
- [ ] Repeated confirm on an already executed, partially executed, execution-failed, or execution-skipped plan does not create duplicate ledger rows or duplicate provider calls.
- [ ] Execution summaries include additive rollback metadata with bounded values.
- [ ] Rollback semantics are explicit: `not_needed`, `not_applicable`, or `not_attempted`.
- [ ] Confirmation boundary rules, write-tool restrictions, and AMAP read-only preview restrictions remain unchanged.
- [ ] Focused unit and integration tests cover duplicate confirmation, partial success replay, failure safe-stop, and ledger-backed recovery.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_human_confirmation.py tests/test_execution_workflow.py -q
python -m pytest tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py -q
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -k "confirmation or execution" -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: harden execution safety and action ledger
```

## 11. Notes for the Implementer

Keep this task narrow and deterministic.

The central safety decision for this task is:

- replay from durable evidence before invoking new writes
- stop on first terminal write failure
- represent skipped tail actions explicitly
- record rollback as `not_attempted` when compensation tools do not exist

Do not widen this task into generalized compensation workflows, operator replay consoles, or benchmark expansion. If implementation pressure suggests changing the confirmation contract, adding new write tools, or redesigning execution storage beyond additive fields, stop and report the scope expansion.
