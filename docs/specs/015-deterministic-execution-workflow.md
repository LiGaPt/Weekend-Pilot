# Spec: 015 Deterministic Execution Workflow

## 1. Goal

Add a deterministic Execution Workflow that executes confirmed plan actions through Tool Gateway.

After Task 014, WeekendPilot can confirm a selected plan and generate execution-ready `confirmed_actions` with deterministic idempotency keys. Task 015 should consume those confirmed actions, invoke the corresponding write tools through Tool Gateway with `user_confirmed=True`, and persist execution summary metadata back to the existing `plans` row.

The workflow must be deterministic service code, not a free-form agent. It must use Tool Gateway for all write tool execution so Tool Events and Action Ledger rows are produced by the existing gateway path.

## 2. Project Context

This task implements the execution node from `docs/PROJECT_BLUEPRINT.md`:

```text
final_review
-> persist_reviewed_plans
-> select_plan
-> wait_confirmation
-> execute
-> write_feedback
```

It supports these blueprint requirements:

- Human confirmation before side effects.
- Execution Workflow is deterministic, not an Agent.
- All tools go through Tool Gateway.
- Action Ledger records every side-effect action.
- Write tools use idempotency keys.
- Duplicate execution attempts do not duplicate side effects.
- Partial success is visible and stored.

Task 015 depends on:

- Task 005 Tool Gateway write execution and Action Ledger integration.
- Task 007 Mock World write tools.
- Task 013 selected persisted plans.
- Task 014 confirmed action package.

## 3. Requirements

- Add a deterministic execution workflow service.
- Execute only selected confirmed plans for the requested `run_id`.
- Read actions from `plans.plan_json["confirmed_actions"]`.
- Reject execution unless:
  - plan exists
  - plan belongs to the requested `run_id`
  - plan is selected
  - plan has `plan_json["confirmation"]["status"] == "confirmed"`
  - plan has `confirmed_actions` as a list
- Execute confirmed actions in ascending `execution_order`.
- For each action, invoke Tool Gateway with:
  - `run_id`
  - `tool_name=action.tool_name`
  - `payload=action.payload`
  - `provider=plan_json["provider_profile"]`
  - `user_confirmed=True`
  - `target_id=action.target_id`
  - `idempotency_key=action.idempotency_key`
- Treat Tool Gateway statuses as:
  - success: `succeeded`, `idempotent_replay`
  - failure: `failed`, `blocked`, `rate_limited`
- Continue through all confirmed actions even if one action fails.
- Return a structured execution result with per-action results.
- Persist execution metadata in `plans.plan_json["execution"]`.
- Update `plans.status`:
  - `executed` if all actions succeed or replay
  - `partially_executed` if at least one action succeeds/replays and at least one fails
  - `execution_failed` if all actions fail
  - `execution_skipped` if the confirmed plan has no actions
- Re-running an already executed confirmed plan should invoke Tool Gateway again with the same idempotency keys and rely on gateway idempotent replay. It must not create duplicate Action Ledger rows.
- Do not call providers directly.
- Do not write Action Ledger rows directly.
- Do not implement recovery routing.
- Repository and service methods must flush but not commit.
- Add unit tests for execution workflow validation, status mapping, idempotent replay behavior, and plan JSON updates.
- Add integration test running Mock World planning -> review -> persistence -> selection -> confirmation -> execution.
- README must include focused execution workflow test commands.
- Do not add database migrations unless the existing `plans` table is missing.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement LangGraph.
- Do not implement Supervisor, Discovery, Dining, Itinerary Planner, or Validator agents.
- Do not call LLMs.
- Do not implement recovery routing or compensation.
- Do not implement Feedback Writer.
- Do not add benchmark cases or graders.
- Do not add API endpoints.
- Do not add CLI or Web UI.
- Do not call providers directly.
- Do not bypass Tool Gateway.
- Do not write Action Ledger rows directly.
- Do not change Tool Gateway behavior.
- Do not change Mock World provider behavior unless an existing bug blocks execution.
- Do not add Redis behavior beyond whatever Tool Gateway already uses.
- Do not add LangSmith tracing.
- Do not commit `.env`, generated caches, virtualenvs, Docker volumes, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- `run_id: UUID`
- `plan_id: UUID`
- selected and confirmed `plans` row
- `ToolGateway`

### Outputs

- `ExecutionWorkflowResult`
- Tool Events created by Tool Gateway.
- Action Ledger rows created by Tool Gateway for write tools.
- Updated `plans.status`.
- Updated `plans.plan_json["execution"]`.

### Public Modules

Task 015 may add:

```text
backend.app.execution.__init__
backend.app.execution.errors
backend.app.execution.schemas
backend.app.execution.workflow
```

### PlanRepository Addition

Task 015 should extend `PlanRepository` with:

```python
def update_status_and_plan_json(
    self,
    plan_id: UUID,
    status: str,
    plan_json: dict[str, Any],
) -> Plan | None:
    ...
```

This helper should flush and refresh, but not commit.

### Execution Workflow Contract

```python
class DeterministicExecutionWorkflow:
    workflow_version = "deterministic_execution_workflow_v1"

    def __init__(
        self,
        plans: PlanRepository,
        gateway: ToolGateway,
    ) -> None:
        ...

    def execute_confirmed_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
    ) -> ExecutionWorkflowResult:
        ...
```

### Schemas

```python
ExecutionWorkflowStatus = Literal[
    "succeeded",
    "partially_succeeded",
    "failed",
    "skipped",
]

ExecutionActionStatus = Literal[
    "succeeded",
    "failed",
    "blocked",
    "rate_limited",
    "idempotent_replay",
]
```

```python
class ExecutionActionResult(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: str
    target_id: str
    idempotency_key: str
    status: ExecutionActionStatus
    action_id: UUID | None = None
    tool_event_id: UUID | None = None
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
```

```python
class ExecutionWorkflowResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: ExecutionWorkflowStatus
    plan_status: str
    action_results: list[ExecutionActionResult] = Field(default_factory=list)
    succeeded_count: int
    failed_count: int
    workflow_version: str
```

### `plan_json["execution"]` Contract

Execution metadata must use this shape:

```json
{
  "schema_version": "execution_workflow_v1",
  "workflow_version": "deterministic_execution_workflow_v1",
  "status": "succeeded",
  "plan_status": "executed",
  "started_at": "2026-05-14T00:00:00+00:00",
  "finished_at": "2026-05-14T00:00:01+00:00",
  "succeeded_count": 2,
  "failed_count": 0,
  "action_results": [
    {
      "action_ref": "draft_1_action_1",
      "execution_order": 1,
      "tool_name": "book_ticket",
      "target_id": "activity_museum_001",
      "idempotency_key": "confirm:<run_id>:<plan_id>:draft_1_action_1",
      "status": "succeeded",
      "action_id": "uuid",
      "tool_event_id": "uuid",
      "response_json": {},
      "error_json": null
    }
  ]
}
```

## 6. Observability

Task 015 uses existing observability paths:

- Tool Gateway writes `tool_events`.
- Tool Gateway writes `action_ledger` for confirmed write tools.
- Execution Workflow writes a summary into `plans.plan_json["execution"]`.

Task 015 must not add LangSmith runtime tracing yet.

The execution summary must include:

- workflow version
- status
- started/finished timestamps
- action refs
- tool names
- target IDs
- idempotency keys
- Tool Event IDs
- Action Ledger IDs
- response/error JSON
- success/failure counts

## 7. Failure Handling

- Missing plan raises `ExecutionWorkflowError`.
- Wrong-run plan raises `ExecutionWorkflowError`.
- Unselected plan raises `ExecutionWorkflowError`.
- Unconfirmed plan raises `ExecutionWorkflowError`.
- Declined plan raises `ExecutionWorkflowError`.
- Malformed `plan_json` raises `ExecutionWorkflowError`.
- Missing or malformed `confirmed_actions` raises `ExecutionWorkflowError`.
- Confirmed action missing `tool_name`, `target_id`, `idempotency_key`, or `execution_order` raises `ExecutionWorkflowError`.
- Confirmed action with `user_confirmed is not True` raises `ExecutionWorkflowError`.
- Confirmed action with a non-write tool raises `ExecutionWorkflowError`.
- Tool Gateway `failed`, `blocked`, or `rate_limited` results are captured as action failures, not raised as workflow exceptions.
- The workflow continues after action failures and returns a partial or failed result.
- Duplicate execution relies on Tool Gateway idempotency and should produce `idempotent_replay` action results without duplicate Action Ledger rows.
- Repository and service methods must not commit. Caller owns transaction boundaries.

## 8. Acceptance Criteria

- [ ] `DeterministicExecutionWorkflow` exists and is importable.
- [ ] Execution schemas are typed and importable.
- [ ] Execution errors are typed and importable.
- [ ] Workflow executes only confirmed selected plans.
- [ ] Workflow rejects missing, wrong-run, unselected, declined, unconfirmed, and malformed plans.
- [ ] Workflow executes actions in ascending `execution_order`.
- [ ] Workflow invokes Tool Gateway with `user_confirmed=True`.
- [ ] Workflow passes deterministic `idempotency_key` and `target_id` to Tool Gateway.
- [ ] Workflow does not call providers directly.
- [ ] Workflow does not write Action Ledger rows directly.
- [ ] Successful execution creates Action Ledger rows through Tool Gateway.
- [ ] Re-running execution does not create duplicate Action Ledger rows.
- [ ] Re-running execution returns idempotent replay action results.
- [ ] Failed/blocked/rate-limited action results are captured in the workflow result.
- [ ] Partial success updates plan status to `partially_executed`.
- [ ] All-failed execution updates plan status to `execution_failed`.
- [ ] No-action execution updates plan status to `execution_skipped`.
- [ ] Execution metadata is persisted in `plans.plan_json["execution"]`.
- [ ] Integration test runs Mock World planning -> review -> persistence -> selection -> confirmation -> execution.
- [ ] Integration test confirms Action Ledger rows are created for confirmed actions.
- [ ] Integration test confirms Tool Event rows are created for execution actions.
- [ ] README includes focused execution workflow verification commands.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task15` branch created from `task14`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task14
git switch -c task15
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_execution_workflow.py -v
python -m pytest tests/integration/test_execution_workflow_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add deterministic execution workflow
```

## 11. Notes for the Implementer

If Task 014 confirmation files are missing, stop and report the branch/base mismatch.

Keep Task 015 focused on deterministic execution. Do not add LangGraph, agents, recovery routing, feedback writing, API endpoints, CLI, Web UI, or benchmark graders in this task.
