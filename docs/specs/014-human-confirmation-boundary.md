# Spec: 014 Human Confirmation Boundary

## 1. Goal

Add a deterministic human confirmation boundary for selected persisted plans.

After Task 013, WeekendPilot can persist reviewed plans and mark one plan as selected for a run. Task 014 should allow the selected plan to be confirmed or declined in a durable, deterministic way before any write tool can execute.

This task must produce an execution-ready confirmed action package with deterministic idempotency keys, but it must not invoke Tool Gateway, providers, write tools, or Action Ledger. Execution remains a follow-up task.

## 2. Project Context

This task sits between reviewed plan selection and deterministic execution in `docs/PROJECT_BLUEPRINT.md`:

```text
final_review
-> persist_reviewed_plans
-> select_plan
-> wait_confirmation
-> execute
```

It supports these blueprint requirements:

- Human confirmation is required before side effects.
- PostgreSQL is the durable source of truth.
- Write tools remain blocked unless confirmation has happened.
- Execution Workflow remains deterministic and separate from agents.
- Action Ledger remains owned by confirmed write execution, not by planning or confirmation.

Task 014 depends on:

- Task 005 Tool Gateway write tool confirmation and idempotency behavior.
- Task 011 proposed action schemas.
- Task 012 Final Review Gate.
- Task 013 persisted/selected plans.

## 3. Requirements

- Add a deterministic confirmation service.
- Confirm only a selected plan for the requested `run_id`.
- Decline only a selected plan for the requested `run_id`.
- Store confirmation/decline metadata in the existing `plans.plan_json`.
- Update `plans.status`:
  - `confirmed` when confirmed
  - `declined` when declined
- Leave `plans.selected=True` for the selected confirmed/declined plan.
- Generate confirmed action specs from `plan_json["draft"]["proposed_actions"]`.
- Generate deterministic idempotency keys only after confirmation.
- Do not mutate original `draft.proposed_actions`.
- Confirming an already confirmed plan should be idempotent and return the existing confirmation data.
- Declining an already declined plan should be idempotent and return the existing decline data.
- Reject confirmation if:
  - plan does not exist
  - plan belongs to another run
  - plan is not selected
  - plan status is not `selected` or `confirmed`
  - plan is not safe to present
  - plan JSON is missing required reviewed-plan fields
  - proposed action structure is malformed
  - a proposed action does not require confirmation
  - a proposed action already contains execution fields such as `idempotency_key`, `confirmation_id`, or `action_id`
- Reject decline if:
  - plan does not exist
  - plan belongs to another run
  - plan is not selected
  - plan status is not `selected` or `declined`
- Repository and service methods must flush but not commit.
- Add unit tests for confirmation and decline behavior.
- Add integration test covering full read-only planning path through persistence, selection, and confirmation.
- README must include focused human confirmation test commands.
- Do not add database migrations unless the existing `plans` table is missing.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement Execution Workflow.
- Do not invoke Tool Gateway.
- Do not call providers.
- Do not execute write tools.
- Do not write Action Ledger rows.
- Do not implement Action Ledger writer.
- Do not add API endpoints.
- Do not add CLI or Web UI.
- Do not add LangGraph.
- Do not add agents, prompts, or LLM calls.
- Do not add Redis behavior.
- Do not add LangSmith tracing.
- Do not modify Final Review Gate rules.
- Do not modify Tool Gateway write execution behavior.
- Do not add benchmark cases or graders.
- Do not commit `.env`, generated caches, virtualenvs, Docker volumes, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- `run_id: UUID`
- `plan_id: UUID`
- `confirmed_by: str`
- `source: str = "unknown"`
- optional `confirmed_at: datetime | None`
- selected `plans` row from PostgreSQL

### Outputs

- Updated `plans` row.
- `ConfirmationResult`.
- `ConfirmedActionSpec` list for later Execution Workflow.

### Public Modules

Task 014 may add:

```text
backend.app.confirmation.__init__
backend.app.confirmation.errors
backend.app.confirmation.schemas
backend.app.confirmation.service
```

### PlanRepository Additions

Task 014 should extend `PlanRepository` with:

```python
def update_plan_json(
    self,
    plan_id: UUID,
    plan_json: dict[str, Any],
) -> Plan | None:
    ...

def get_selected_for_run(self, run_id: UUID) -> Plan | None:
    ...
```

### Confirmation Service Contract

```python
class HumanConfirmationService:
    service_version = "human_confirmation_v1"

    def __init__(self, plans: PlanRepository) -> None:
        ...

    def confirm_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
        confirmed_by: str,
        source: str = "unknown",
        confirmed_at: datetime | None = None,
    ) -> ConfirmationResult:
        ...

    def decline_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
        declined_by: str,
        source: str = "unknown",
        declined_at: datetime | None = None,
        reason: str | None = None,
    ) -> ConfirmationResult:
        ...
```

### Schemas

```python
ConfirmationDecision = Literal["confirmed", "declined"]
ConfirmationStatus = Literal["confirmed", "declined"]
ConfirmedActionType = Literal[
    "join_queue",
    "reserve_restaurant",
    "book_ticket",
    "order_addon",
    "send_message",
]
```

```python
class ConfirmedActionSpec(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: ConfirmedActionType
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    user_confirmed: bool = True
    reason: str
```

```python
class ConfirmationResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: ConfirmationStatus
    confirmation_id: str
    selected: bool
    confirmed_actions: list[ConfirmedActionSpec] = Field(default_factory=list)
    service_version: str
```

### `plan_json` Confirmation Contract

When confirmed, append or replace:

```json
{
  "confirmation": {
    "schema_version": "human_confirmation_v1",
    "confirmation_id": "confirmation-...",
    "status": "confirmed",
    "confirmed_by": "user",
    "source": "cli",
    "confirmed_at": "2026-05-14T00:00:00+00:00",
    "action_count": 2,
    "service_version": "human_confirmation_v1"
  },
  "confirmed_actions": [
    {
      "action_ref": "draft_1_action_1",
      "execution_order": 1,
      "tool_name": "book_ticket",
      "target_id": "activity_museum_001",
      "payload": {},
      "idempotency_key": "confirm:<run_id>:<plan_id>:draft_1_action_1",
      "user_confirmed": true,
      "reason": "Ticket availability is available."
    }
  ]
}
```

When declined, append or replace:

```json
{
  "confirmation": {
    "schema_version": "human_confirmation_v1",
    "confirmation_id": "confirmation-...",
    "status": "declined",
    "declined_by": "user",
    "source": "cli",
    "declined_at": "2026-05-14T00:00:00+00:00",
    "reason": "user_declined",
    "action_count": 0,
    "service_version": "human_confirmation_v1"
  },
  "confirmed_actions": []
}
```

### Idempotency Key Contract

Confirmed action idempotency keys must be deterministic and stable for the same run, plan, and action:

```text
confirm:<run_id>:<plan_id>:<action_ref>
```

The service must validate that generated keys are non-empty and no longer than 255 characters, matching the existing `action_ledger.idempotency_key` column.

## 6. Observability

Task 014 does not add LangSmith or Redis observability.

It must persist enough metadata in PostgreSQL for later execution and benchmark review:

- `confirmation_id`
- `status`
- `confirmed_by` or `declined_by`
- `source`
- timestamp
- action count
- confirmation service version
- deterministic confirmed actions and idempotency keys

No Tool Event should be created by confirmation or decline.

No Action Ledger row should be created by confirmation or decline.

## 7. Failure Handling

- Missing plan raises `PlanConfirmationError`.
- Wrong-run plan raises `PlanConfirmationError`.
- Unselected plan raises `PlanConfirmationError`.
- Unsafe or malformed `plan_json` raises `PlanConfirmationError`.
- Proposed actions with missing `action_ref`, `action_type`, `target_id`, or `reason` raise `PlanConfirmationError`.
- Proposed actions with `requires_confirmation is not True` raise `PlanConfirmationError`.
- Proposed actions containing `idempotency_key`, `confirmation_id`, or `action_id` anywhere in the action payload raise `PlanConfirmationError`.
- Confirming a confirmed plan returns the existing confirmation result.
- Declining a declined plan returns the existing decline result.
- Confirming a declined plan raises `PlanConfirmationError`.
- Declining a confirmed plan raises `PlanConfirmationError`.
- Repository and service methods must not commit. Caller owns transaction boundaries.

## 8. Acceptance Criteria

- [ ] `HumanConfirmationService` exists and is importable.
- [ ] Confirmation schemas are typed and importable.
- [ ] Confirmation errors are typed and importable.
- [ ] `PlanRepository` supports `update_plan_json`.
- [ ] `PlanRepository` supports `get_selected_for_run`.
- [ ] Selected reviewed plan can be confirmed.
- [ ] Selected reviewed plan can be declined.
- [ ] Confirmed plan status becomes `confirmed`.
- [ ] Declined plan status becomes `declined`.
- [ ] Confirmation metadata is persisted in `plans.plan_json`.
- [ ] Confirmed action specs include deterministic idempotency keys.
- [ ] Confirmed action specs set `user_confirmed=True`.
- [ ] Confirmation does not mutate original `draft.proposed_actions`.
- [ ] Reconfirming an already confirmed plan is idempotent.
- [ ] Re-declining an already declined plan is idempotent.
- [ ] Missing, wrong-run, unselected, unsafe, and malformed plans fail cleanly.
- [ ] Confirmation and decline do not call Tool Gateway, providers, Redis, LangSmith, LLMs, or write tools.
- [ ] Integration test confirms Action Ledger remains empty.
- [ ] Integration test confirms Tool Event count does not increase during confirmation/decline.
- [ ] README includes focused human confirmation verification commands.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task14` branch created from `task13`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task13
git switch -c task14
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_human_confirmation.py -v
python -m pytest tests/integration/test_human_confirmation_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add human confirmation boundary
```

## 11. Notes for the Implementer

If Task 013 files are missing, stop and report the branch/base mismatch.

Keep this task focused on the confirmation boundary. The confirmed action package is an input for a later Execution Workflow task, not execution itself. Do not invoke Tool Gateway or create Action Ledger rows in Task 014.
