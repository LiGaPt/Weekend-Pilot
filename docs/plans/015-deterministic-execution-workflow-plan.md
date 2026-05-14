# Plan: 015 Deterministic Execution Workflow

## 1. Spec Reference

Spec file:

```text
docs/specs/015-deterministic-execution-workflow.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task14`.
- Current Task 014 commit is `13b598e feat: add human confirmation boundary`.
- `backend/app/confirmation/service.py` defines `HumanConfirmationService`.
- `backend/app/confirmation/schemas.py` defines `ConfirmedActionSpec`.
- `backend/app/repositories/plans.py` defines `PlanRepository`.
- `backend/app/tool_gateway/gateway.py` executes confirmed write tools and writes Action Ledger rows.
- `backend/app/tool_gateway/models.py` defines `ToolGatewayRequest` and `ToolGatewayResult`.
- `backend/app/tool_gateway/registry.py` defines `WRITE_TOOLS`.
- Confirmed plans store actions under `plan_json["confirmed_actions"]`.
- No `backend/app/execution` package exists yet.
- No Execution Workflow exists yet.

## 3. Files to Add

- `backend/app/execution/__init__.py` - exports execution workflow public API.
- `backend/app/execution/errors.py` - `ExecutionWorkflowError`.
- `backend/app/execution/schemas.py` - execution result schemas.
- `backend/app/execution/workflow.py` - deterministic execution workflow service.
- `tests/test_execution_workflow.py` - unit tests for workflow validation and status mapping.
- `tests/integration/test_execution_workflow_gateway.py` - full Mock World confirmed execution integration test.
- `docs/specs/015-deterministic-execution-workflow.md` - Task 015 spec.
- `docs/plans/015-deterministic-execution-workflow-plan.md` - Task 015 plan.

## 4. Files to Modify

- `backend/app/repositories/plans.py` - add `update_status_and_plan_json`.
- `README.md` - add focused execution workflow test command.

No changes are expected in:

- `backend/app/models/runtime.py`
- `alembic/versions`
- Tool Gateway behavior
- Mock World provider behavior
- confirmation service behavior
- Final Review Gate
- planning generators
- FastAPI endpoints

## 5. Implementation Steps

1. Create task branch.

```bash
git switch task14
git switch -c task15
git status --short --branch
```

Expected:

- Branch is `task15`.
- Working tree is clean before implementation.

2. Confirm baseline files.

```bash
rg --files backend/app/confirmation backend/app/plans backend/app/repositories backend/app/tool_gateway backend/app/providers/mock_world tests/integration docs/specs docs/plans
```

Expected:

- Task 014 files exist.
- `backend/app/execution` does not exist yet.
- Tool Gateway and Mock World write tools exist.

3. Extend `backend/app/repositories/plans.py`.

Add:

```python
def update_status_and_plan_json(
    self,
    plan_id: UUID,
    status: str,
    plan_json: dict[str, Any],
) -> Plan | None:
    plan = self.get_by_id(plan_id)
    if plan is None:
        return None

    plan.status = status
    plan.plan_json = plan_json
    self.session.flush()
    self.session.refresh(plan)
    return plan
```

Do not call `commit()`.

4. Add `backend/app/execution/errors.py`.

```python
class ExecutionWorkflowError(ValueError):
    pass
```

5. Add `backend/app/execution/schemas.py`.

Create:

```python
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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

6. Add `backend/app/execution/workflow.py`.

Imports:

```python
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.execution.errors import ExecutionWorkflowError
from backend.app.execution.schemas import ExecutionActionResult, ExecutionWorkflowResult
from backend.app.models.runtime import Plan
from backend.app.repositories import PlanRepository
from backend.app.tool_gateway import ToolGateway, ToolGatewayRequest
from backend.app.tool_gateway.registry import WRITE_TOOLS
```

Create class:

```python
class DeterministicExecutionWorkflow:
    workflow_version = "deterministic_execution_workflow_v1"
    _SUCCESS_STATUSES = {"succeeded", "idempotent_replay"}
    _FAILURE_STATUSES = {"failed", "blocked", "rate_limited"}
    _ALLOWED_PLAN_STATUSES = {
        "confirmed",
        "executed",
        "partially_executed",
        "execution_failed",
        "execution_skipped",
    }

    def __init__(
        self,
        plans: PlanRepository,
        gateway: ToolGateway,
    ) -> None:
        self.plans = plans
        self.gateway = gateway
```

7. Implement `execute_confirmed_plan`.

```python
def execute_confirmed_plan(
    self,
    run_id: UUID,
    plan_id: UUID,
) -> ExecutionWorkflowResult:
    started_at = datetime.now(UTC)
    plan = self._load_executable_plan(run_id, plan_id)
    plan_json = self._plan_json(plan)
    actions = self._confirmed_actions(plan_json)

    if not actions:
        result = ExecutionWorkflowResult(
            run_id=run_id,
            plan_id=plan_id,
            status="skipped",
            plan_status="execution_skipped",
            action_results=[],
            succeeded_count=0,
            failed_count=0,
            workflow_version=self.workflow_version,
        )
        self._persist_execution(plan, plan_json, result, started_at, datetime.now(UTC))
        return result

    action_results = []
    for action in actions:
        gateway_result = self.gateway.invoke(
            ToolGatewayRequest(
                run_id=run_id,
                tool_name=action["tool_name"],
                payload=deepcopy(action.get("payload") or {}),
                provider=plan_json.get("provider_profile"),
                user_confirmed=True,
                target_id=action["target_id"],
                idempotency_key=action["idempotency_key"],
            )
        )
        action_results.append(
            ExecutionActionResult(
                action_ref=action["action_ref"],
                execution_order=action["execution_order"],
                tool_name=action["tool_name"],
                target_id=action["target_id"],
                idempotency_key=action["idempotency_key"],
                status=gateway_result.status,
                action_id=gateway_result.action_id,
                tool_event_id=gateway_result.tool_event_id,
                response_json=gateway_result.response_json,
                error_json=gateway_result.error_json,
            )
        )

    succeeded_count = sum(1 for item in action_results if item.status in self._SUCCESS_STATUSES)
    failed_count = len(action_results) - succeeded_count
    workflow_status, plan_status = self._status_pair(succeeded_count, failed_count)

    result = ExecutionWorkflowResult(
        run_id=run_id,
        plan_id=plan_id,
        status=workflow_status,
        plan_status=plan_status,
        action_results=action_results,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        workflow_version=self.workflow_version,
    )
    self._persist_execution(plan, plan_json, result, started_at, datetime.now(UTC))
    return result
```

8. Implement plan loading.

```python
def _load_executable_plan(self, run_id: UUID, plan_id: UUID) -> Plan:
    plan = self.plans.get_by_id(plan_id)
    if plan is None:
        raise ExecutionWorkflowError("Plan does not exist.")
    if plan.run_id != run_id:
        raise ExecutionWorkflowError("Plan does not belong to the requested run.")
    if not plan.selected:
        raise ExecutionWorkflowError("Plan must be selected before execution.")
    if plan.status == "declined":
        raise ExecutionWorkflowError("Declined plans cannot be executed.")
    if plan.status not in self._ALLOWED_PLAN_STATUSES:
        raise ExecutionWorkflowError("Plan must be confirmed before execution.")
    return plan
```

9. Implement plan JSON validation.

```python
def _plan_json(self, plan: Plan) -> dict[str, Any]:
    plan_json = plan.plan_json
    if not isinstance(plan_json, dict):
        raise ExecutionWorkflowError("Plan JSON is malformed.")
    if plan_json.get("schema_version") != "reviewed_plan_v1":
        raise ExecutionWorkflowError("Plan JSON is not a reviewed plan.")
    confirmation = plan_json.get("confirmation")
    if not isinstance(confirmation, dict):
        raise ExecutionWorkflowError("Plan is missing confirmation metadata.")
    if confirmation.get("status") != "confirmed":
        raise ExecutionWorkflowError("Plan must be confirmed before execution.")
    provider_profile = plan_json.get("provider_profile")
    if not isinstance(provider_profile, str) or not provider_profile:
        raise ExecutionWorkflowError("Plan provider profile is missing.")
    return plan_json
```

10. Implement confirmed action validation and sorting.

```python
def _confirmed_actions(self, plan_json: dict[str, Any]) -> list[dict[str, Any]]:
    actions = plan_json.get("confirmed_actions")
    if actions is None:
        raise ExecutionWorkflowError("Plan is missing confirmed actions.")
    if not isinstance(actions, list):
        raise ExecutionWorkflowError("Confirmed actions must be a list.")

    validated = []
    seen_refs = set()
    seen_orders = set()
    for action in actions:
        if not isinstance(action, dict):
            raise ExecutionWorkflowError("Confirmed action must be an object.")
        self._validate_action(action)
        if action["action_ref"] in seen_refs:
            raise ExecutionWorkflowError("Duplicate confirmed action ref.")
        if action["execution_order"] in seen_orders:
            raise ExecutionWorkflowError("Duplicate execution order.")
        seen_refs.add(action["action_ref"])
        seen_orders.add(action["execution_order"])
        validated.append(action)

    return sorted(validated, key=lambda item: item["execution_order"])
```

Add:

```python
def _validate_action(self, action: dict[str, Any]) -> None:
    if not isinstance(action.get("action_ref"), str) or not action["action_ref"]:
        raise ExecutionWorkflowError("Confirmed action is missing action_ref.")
    if not isinstance(action.get("execution_order"), int) or action["execution_order"] <= 0:
        raise ExecutionWorkflowError("Confirmed action has invalid execution_order.")
    if action.get("tool_name") not in WRITE_TOOLS:
        raise ExecutionWorkflowError("Confirmed action tool must be a write tool.")
    if not isinstance(action.get("target_id"), str) or not action["target_id"]:
        raise ExecutionWorkflowError("Confirmed action is missing target_id.")
    if not isinstance(action.get("idempotency_key"), str) or not action["idempotency_key"]:
        raise ExecutionWorkflowError("Confirmed action is missing idempotency_key.")
    if len(action["idempotency_key"]) > 255:
        raise ExecutionWorkflowError("Confirmed action idempotency_key exceeds 255 characters.")
    if action.get("user_confirmed") is not True:
        raise ExecutionWorkflowError("Confirmed action must set user_confirmed=True.")
    payload = action.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise ExecutionWorkflowError("Confirmed action payload must be an object.")
```

11. Implement status mapping.

```python
def _status_pair(self, succeeded_count: int, failed_count: int) -> tuple[str, str]:
    if succeeded_count > 0 and failed_count == 0:
        return "succeeded", "executed"
    if succeeded_count > 0 and failed_count > 0:
        return "partially_succeeded", "partially_executed"
    return "failed", "execution_failed"
```

12. Implement execution persistence.

```python
def _persist_execution(
    self,
    plan: Plan,
    plan_json: dict[str, Any],
    result: ExecutionWorkflowResult,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    updated_json = deepcopy(plan_json)
    updated_json["execution"] = {
        "schema_version": "execution_workflow_v1",
        "workflow_version": self.workflow_version,
        "status": result.status,
        "plan_status": result.plan_status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "succeeded_count": result.succeeded_count,
        "failed_count": result.failed_count,
        "action_results": [
            action.model_dump(mode="json")
            for action in result.action_results
        ],
    }
    updated = self.plans.update_status_and_plan_json(
        plan.plan_id,
        result.plan_status,
        updated_json,
    )
    if updated is None:
        raise ExecutionWorkflowError("Plan disappeared during execution persistence.")
```

13. Add `backend/app/execution/__init__.py`.

Export:

```python
DeterministicExecutionWorkflow
ExecutionActionResult
ExecutionActionStatus
ExecutionWorkflowError
ExecutionWorkflowResult
ExecutionWorkflowStatus
```

14. Add unit tests in `tests/test_execution_workflow.py`.

Use real PostgreSQL session for plan rows and a fake gateway object.

Create helper fixtures that:

- create user/run
- create selected confirmed plan with two confirmed actions
- create selected confirmed plan with zero actions
- create unselected/declined/unconfirmed/malformed plans

Fake gateway:

```python
class FakeGateway:
    def __init__(self, statuses: list[str] | None = None) -> None:
        self.statuses = statuses or ["succeeded"]
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        index = len(self.requests) - 1
        status = self.statuses[min(index, len(self.statuses) - 1)]
        return ToolGatewayResult(
            tool_name=request.tool_name,
            tool_type="write",
            provider=request.provider or "mock_world",
            status=status,
            response_json={"ok": True} if status in {"succeeded", "idempotent_replay"} else None,
            error_json=None if status in {"succeeded", "idempotent_replay"} else {"code": status},
            tool_event_id=uuid4(),
            action_id=uuid4() if status in {"succeeded", "idempotent_replay"} else None,
            idempotency_key=request.idempotency_key,
        )
```

Cover:

- executes confirmed actions in ascending `execution_order`
- sends `user_confirmed=True`
- sends target IDs and idempotency keys to gateway
- sends provider from `plan_json["provider_profile"]`
- updates plan status to `executed` on all success
- persists `plan_json["execution"]`
- treats `idempotent_replay` as success
- updates plan status to `partially_executed` on mixed success/failure
- updates plan status to `execution_failed` when all actions fail
- updates plan status to `execution_skipped` when confirmed actions list is empty
- continues after failures
- rejects missing plan
- rejects wrong-run plan
- rejects unselected plan
- rejects declined plan
- rejects unconfirmed plan
- rejects malformed confirmed actions
- rejects read tool actions
- rejects action with `user_confirmed=False`
- rejects missing/too-long idempotency key
- repository/workflow does not self-commit; rollback removes execution mutation

15. Add integration test in `tests/integration/test_execution_workflow_gateway.py`.

Use the setup style from `tests/integration/test_human_confirmation_gateway.py`:

- `SessionLocal`
- `UserRepository`
- `AgentRunRepository`
- `ToolEventRepository`
- `ActionLedgerRepository`
- `PlanRepository`
- `ReviewedPlanPersistenceService`
- `HumanConfirmationService`
- `DeterministicExecutionWorkflow`
- `JsonRedisCache`
- `FixedWindowRateLimiter`
- `RedisKeyBuilder`
- `build_mock_world_registry`
- `ToolGateway`
- `DeterministicIntentParser`
- `DeterministicQueryPlanner`
- `QueryPlanExecutor`
- `CandidateEnricher`
- `DeterministicItineraryGenerator`
- `FinalReviewGate`

Scenario:

1. Create a user and `AgentRun`.
2. Parse the MVP family request.
3. Build Mock World query plan.
4. Execute initial read calls.
5. Enrich candidates.
6. Generate itinerary drafts.
7. Run Final Review Gate.
8. Persist reviewed plans.
9. Select first persisted plan.
10. Confirm selected plan.
11. Count existing Tool Event rows and Action Ledger rows.
12. Execute confirmed plan.
13. Assert:
    - result status is `succeeded`
    - plan status is `executed`
    - action result count equals confirmed action count
    - all action results have status `succeeded`
    - every action result has `tool_event_id`
    - every action result has `action_id`
    - Action Ledger count increased by confirmed action count
    - Tool Event count increased by confirmed action count
    - persisted `plan_json["execution"]["status"] == "succeeded"`
14. Execute the same confirmed plan again.
15. Assert:
    - replay result status is `succeeded`
    - every replay action status is `idempotent_replay`
    - Action Ledger count does not increase
    - Tool Event count increases by confirmed action count because replay attempts are observable

16. Update README.

Add section:

```markdown
## Deterministic Execution Workflow

Focused execution workflow tests require PostgreSQL and Redis for the gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_execution_workflow.py tests/integration/test_execution_workflow_gateway.py -v
```
```

Do not claim LangGraph, recovery routing, feedback writing, API, CLI, or Web UI exists.

17. Run focused tests.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_execution_workflow.py -v
python -m pytest tests/integration/test_execution_workflow_gateway.py -v
```

18. Run full verification.

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

19. Inspect tracked files and secrets.

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - confirmed action execution order
  - request fields sent to Tool Gateway
  - all-success status mapping
  - idempotent replay status mapping
  - partial failure status mapping
  - all-failed status mapping
  - no-action skip behavior
  - malformed plan/action validation
  - read-tool rejection
  - unconfirmed/declined/unselected/wrong-run rejection
  - execution summary persistence
  - no self-commit behavior
- Integration tests:
  - parser -> planner -> query executor -> candidate enricher -> itinerary generator -> final review -> plan persistence -> plan selection -> confirmation -> execution
  - real PostgreSQL and Redis for Tool Gateway path
  - Mock World write tools through Tool Gateway
  - Action Ledger rows created by Tool Gateway
  - duplicate execution uses idempotent replay without duplicate Action Ledger rows
- Smoke tests:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_execution_workflow.py -v
python -m pytest tests/integration/test_execution_workflow_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add deterministic execution workflow
```

Expected branch:

```text
task15
```

Expected commands:

```bash
git switch task14
git switch -c task15
git status --short
git add README.md backend/app/repositories/plans.py backend/app/execution tests/test_execution_workflow.py tests/integration/test_execution_workflow_gateway.py docs/specs/015-deterministic-execution-workflow.md docs/plans/015-deterministic-execution-workflow-plan.md
git status --short
git commit -m "feat: add deterministic execution workflow"
git push -u origin task15
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement LangGraph.
- Do not implement agents, prompts, or LLM calls.
- Do not implement recovery routing or compensation.
- Do not implement Feedback Writer.
- Do not add benchmark harness or graders.
- Do not add API endpoints.
- Do not add CLI or Web UI.
- Do not call providers directly.
- Do not bypass Tool Gateway.
- Do not write Action Ledger rows directly.
- Do not modify Tool Gateway behavior.
- Do not modify Mock World behavior unless an existing bug blocks confirmed action execution.
- Do not add database migrations unless the existing `plans` table is absent.
- Do not add LangSmith tracing.
- Do not commit `.env`, API keys, tokens, secrets, generated caches, virtualenvs, logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task15`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] `DeterministicExecutionWorkflow` is deterministic and importable.
- [ ] Execution schemas and errors are importable.
- [ ] Workflow executes only selected confirmed plans.
- [ ] Workflow rejects unsafe states before Tool Gateway invocation.
- [ ] Workflow invokes Tool Gateway, not providers.
- [ ] Workflow passes `user_confirmed=True`.
- [ ] Workflow passes target IDs and idempotency keys.
- [ ] Action Ledger rows are created by Tool Gateway.
- [ ] Duplicate execution does not duplicate Action Ledger rows.
- [ ] Partial and failed executions are represented accurately.
- [ ] Execution summary is persisted in `plans.plan_json`.
- [ ] Integration test covers full Mock World execution path.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add deterministic execution workflow`.
- [ ] Push to `origin/task15` succeeds.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused execution workflow unit test result.
- Focused integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 015 starts from `task14`.
- Existing `plans` table is sufficient; no migration is needed.
- Task 014 confirmation metadata is the only valid source of execution-ready actions.
- Gateway `succeeded` and `idempotent_replay` are treated as successful action outcomes.
- Gateway `failed`, `blocked`, and `rate_limited` are captured as action failures.
- Execution continues after failures and reports partial success instead of performing recovery.
- Recovery, compensation, feedback writing, LangGraph orchestration, and UI/API surfaces are follow-up tasks.
