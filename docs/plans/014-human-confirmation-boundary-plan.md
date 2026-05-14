# Plan: 014 Human Confirmation Boundary

## 1. Spec Reference

Spec file:

```text
docs/specs/014-human-confirmation-boundary.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task13`.
- Current Task 013 commit is `4f4f48a feat: add reviewed plan persistence and selection`.
- `backend/app/repositories/plans.py` defines `PlanRepository`.
- `backend/app/plans/persistence.py` defines `ReviewedPlanPersistenceService`.
- `backend/app/plans/schemas.py` defines persisted plan result schemas.
- `backend/app/models/runtime.py` already defines `Plan`.
- Selected plans use `status="selected"` and `selected=True`.
- Persisted reviewed plans store the draft under `plan_json["draft"]`.
- Proposed actions live under `plan_json["draft"]["proposed_actions"]`.
- Tool Gateway already blocks write tools unless `user_confirmed=True`.
- Tool Gateway already requires `target_id` and `idempotency_key` for confirmed writes.
- No confirmation package exists yet.
- No Execution Workflow exists yet.

## 3. Files to Add

- `backend/app/confirmation/__init__.py` - exports confirmation public API.
- `backend/app/confirmation/errors.py` - typed confirmation errors.
- `backend/app/confirmation/schemas.py` - confirmation result and confirmed action schemas.
- `backend/app/confirmation/service.py` - deterministic confirmation/decline service.
- `tests/test_human_confirmation.py` - unit tests for confirmation behavior.
- `tests/integration/test_human_confirmation_gateway.py` - full read-only planning/review/persist/select/confirm integration test.
- `docs/specs/014-human-confirmation-boundary.md` - Task 014 spec.
- `docs/plans/014-human-confirmation-boundary-plan.md` - Task 014 plan.

## 4. Files to Modify

- `backend/app/repositories/plans.py` - add plan JSON update and selected-plan lookup helpers.
- `README.md` - add focused human confirmation test command.

No changes are expected in:

- `backend/app/models/runtime.py`
- `alembic/versions`
- Tool Gateway
- providers
- Redis runtime
- Final Review Gate
- planning generators
- FastAPI endpoints
- Action Ledger repository

## 5. Implementation Steps

1. Create task branch.

```bash
git switch task13
git switch -c task14
git status --short --branch
```

Expected:

- Branch is `task14`.
- Working tree is clean before implementation.

2. Confirm baseline files.

```bash
rg --files backend/app/plans backend/app/repositories backend/app/tool_gateway backend/app/review backend/app/planning tests/integration docs/specs docs/plans
```

Expected:

- Task 013 files exist.
- `backend/app/confirmation` does not exist yet.
- `backend/app/repositories/plans.py` exists.

3. Extend `backend/app/repositories/plans.py`.

Add imports if needed:

```python
from typing import Any
```

Add methods:

```python
def update_plan_json(
    self,
    plan_id: UUID,
    plan_json: dict[str, Any],
) -> Plan | None:
    plan = self.get_by_id(plan_id)
    if plan is None:
        return None

    plan.plan_json = plan_json
    self.session.flush()
    self.session.refresh(plan)
    return plan


def get_selected_for_run(self, run_id: UUID) -> Plan | None:
    statement = select(Plan).where(
        Plan.run_id == run_id,
        Plan.selected.is_(True),
    )
    return self.session.scalar(statement)
```

Do not call `commit()`.

4. Add `backend/app/confirmation/errors.py`.

```python
class PlanConfirmationError(ValueError):
    pass
```

5. Add `backend/app/confirmation/schemas.py`.

Create:

```python
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConfirmationDecision = Literal["confirmed", "declined"]
ConfirmationStatus = Literal["confirmed", "declined"]
ConfirmedActionType = Literal[
    "join_queue",
    "reserve_restaurant",
    "book_ticket",
    "order_addon",
    "send_message",
]


class ConfirmedActionSpec(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: ConfirmedActionType
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    user_confirmed: bool = True
    reason: str


class ConfirmationResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: ConfirmationStatus
    confirmation_id: str
    selected: bool
    confirmed_actions: list[ConfirmedActionSpec] = Field(default_factory=list)
    service_version: str
```

6. Add `backend/app/confirmation/service.py`.

Implement:

```python
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.confirmation.errors import PlanConfirmationError
from backend.app.confirmation.schemas import ConfirmationResult, ConfirmedActionSpec
from backend.app.models.runtime import Plan
from backend.app.repositories import PlanRepository
```

Create class:

```python
class HumanConfirmationService:
    service_version = "human_confirmation_v1"
    _EXECUTION_FIELD_KEYS = {"idempotency_key", "confirmation_id", "action_id"}
    _WRITE_ACTION_TYPES = {
        "join_queue",
        "reserve_restaurant",
        "book_ticket",
        "order_addon",
        "send_message",
    }

    def __init__(self, plans: PlanRepository) -> None:
        self.plans = plans
```

7. Implement `confirm_plan`.

```python
def confirm_plan(
    self,
    run_id: UUID,
    plan_id: UUID,
    confirmed_by: str,
    source: str = "unknown",
    confirmed_at: datetime | None = None,
) -> ConfirmationResult:
    plan = self._load_plan_for_confirmation(run_id, plan_id)
    if plan.status == "confirmed":
        return self._result_from_plan(plan)
    if plan.status == "declined":
        raise PlanConfirmationError("Declined plans cannot be confirmed.")
    if plan.status != "selected":
        raise PlanConfirmationError("Only selected plans can be confirmed.")

    plan_json = self._reviewed_plan_json(plan)
    actions = self._confirmed_actions(plan, plan_json)
    timestamp = confirmed_at or datetime.now(UTC)
    confirmation_id = self._confirmation_id(run_id, plan_id)
    updated_json = deepcopy(plan_json)
    updated_json["confirmation"] = {
        "schema_version": self.service_version,
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "confirmed_by": confirmed_by,
        "source": source,
        "confirmed_at": timestamp.isoformat(),
        "action_count": len(actions),
        "service_version": self.service_version,
    }
    updated_json["confirmed_actions"] = [
        action.model_dump(mode="json")
        for action in actions
    ]

    plan.status = "confirmed"
    updated = self.plans.update_plan_json(plan.plan_id, updated_json)
    if updated is None:
        raise PlanConfirmationError("Plan disappeared during confirmation.")
    updated.status = "confirmed"
    self.plans.session.flush()
    self.plans.session.refresh(updated)
    return self._result_from_plan(updated)
```

If the implementer prefers avoiding direct status mutation in the service, add a `PlanRepository.update_status_and_json(...)` helper instead. Keep the behavior identical and do not commit.

8. Implement `decline_plan`.

```python
def decline_plan(
    self,
    run_id: UUID,
    plan_id: UUID,
    declined_by: str,
    source: str = "unknown",
    declined_at: datetime | None = None,
    reason: str | None = None,
) -> ConfirmationResult:
    plan = self._load_plan_for_confirmation(run_id, plan_id)
    if plan.status == "declined":
        return self._result_from_plan(plan)
    if plan.status == "confirmed":
        raise PlanConfirmationError("Confirmed plans cannot be declined.")
    if plan.status != "selected":
        raise PlanConfirmationError("Only selected plans can be declined.")

    plan_json = self._reviewed_plan_json(plan)
    timestamp = declined_at or datetime.now(UTC)
    confirmation_id = self._confirmation_id(run_id, plan_id)
    updated_json = deepcopy(plan_json)
    updated_json["confirmation"] = {
        "schema_version": self.service_version,
        "confirmation_id": confirmation_id,
        "status": "declined",
        "declined_by": declined_by,
        "source": source,
        "declined_at": timestamp.isoformat(),
        "reason": reason,
        "action_count": 0,
        "service_version": self.service_version,
    }
    updated_json["confirmed_actions"] = []

    plan.status = "declined"
    updated = self.plans.update_plan_json(plan.plan_id, updated_json)
    if updated is None:
        raise PlanConfirmationError("Plan disappeared during decline.")
    updated.status = "declined"
    self.plans.session.flush()
    self.plans.session.refresh(updated)
    return self._result_from_plan(updated)
```

9. Implement plan loading and validation helpers.

Add:

```python
def _load_plan_for_confirmation(self, run_id: UUID, plan_id: UUID) -> Plan:
    plan = self.plans.get_by_id(plan_id)
    if plan is None:
        raise PlanConfirmationError("Plan does not exist.")
    if plan.run_id != run_id:
        raise PlanConfirmationError("Plan does not belong to the requested run.")
    if not plan.selected:
        raise PlanConfirmationError("Plan must be selected before confirmation.")
    return plan
```

Add:

```python
def _reviewed_plan_json(self, plan: Plan) -> dict[str, Any]:
    plan_json = plan.plan_json
    if not isinstance(plan_json, dict):
        raise PlanConfirmationError("Plan JSON is malformed.")
    if plan_json.get("schema_version") != "reviewed_plan_v1":
        raise PlanConfirmationError("Plan JSON is not a reviewed plan.")
    if plan_json.get("safe_to_present") is not True:
        raise PlanConfirmationError("Plan is not safe to present.")
    draft = plan_json.get("draft")
    if not isinstance(draft, dict):
        raise PlanConfirmationError("Plan JSON is missing draft payload.")
    actions = draft.get("proposed_actions")
    if actions is not None and not isinstance(actions, list):
        raise PlanConfirmationError("Draft proposed actions must be a list.")
    return plan_json
```

10. Implement confirmed action generation.

```python
def _confirmed_actions(
    self,
    plan: Plan,
    plan_json: dict[str, Any],
) -> list[ConfirmedActionSpec]:
    draft = plan_json["draft"]
    proposed_actions = draft.get("proposed_actions") or []
    confirmed_actions = []
    seen_keys = set()

    for index, action in enumerate(proposed_actions, start=1):
        if not isinstance(action, dict):
            raise PlanConfirmationError("Proposed action must be an object.")
        self._validate_proposed_action(action)
        action_ref = action["action_ref"]
        idempotency_key = self._idempotency_key(plan.run_id, plan.plan_id, action_ref)
        if idempotency_key in seen_keys:
            raise PlanConfirmationError("Duplicate confirmed action idempotency key.")
        seen_keys.add(idempotency_key)
        confirmed_actions.append(
            ConfirmedActionSpec(
                action_ref=action_ref,
                execution_order=index,
                tool_name=action["action_type"],
                target_id=action["target_id"],
                payload=deepcopy(action.get("payload") or {}),
                idempotency_key=idempotency_key,
                user_confirmed=True,
                reason=action["reason"],
            )
        )
    return confirmed_actions
```

11. Implement proposed action validation.

```python
def _validate_proposed_action(self, action: dict[str, Any]) -> None:
    for key in ("action_ref", "action_type", "target_id", "reason"):
        if not isinstance(action.get(key), str) or not action[key]:
            raise PlanConfirmationError(f"Proposed action is missing {key}.")
    if action["action_type"] not in self._WRITE_ACTION_TYPES:
        raise PlanConfirmationError("Proposed action type is not a registered write action.")
    if action.get("requires_confirmation") is not True:
        raise PlanConfirmationError("Proposed action must require confirmation.")
    payload = action.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise PlanConfirmationError("Proposed action payload must be an object.")
    forbidden_keys = self._find_forbidden_keys(action)
    if forbidden_keys:
        raise PlanConfirmationError(
            f"Proposed action contains pre-confirmation execution fields: {forbidden_keys}"
        )
```

Add recursive key scan:

```python
def _find_forbidden_keys(self, value: Any) -> list[str]:
    matches = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.casefold() in self._EXECUTION_FIELD_KEYS:
                matches.append(key)
            matches.extend(self._find_forbidden_keys(child))
    elif isinstance(value, list):
        for item in value:
            matches.extend(self._find_forbidden_keys(item))
    return sorted(set(matches))
```

12. Implement deterministic identifiers and result conversion.

```python
def _confirmation_id(self, run_id: UUID, plan_id: UUID) -> str:
    return f"confirmation:{run_id}:{plan_id}"


def _idempotency_key(self, run_id: UUID, plan_id: UUID, action_ref: str) -> str:
    key = f"confirm:{run_id}:{plan_id}:{action_ref}"
    if len(key) > 255:
        raise PlanConfirmationError("Generated idempotency key exceeds 255 characters.")
    return key
```

Add:

```python
def _result_from_plan(self, plan: Plan) -> ConfirmationResult:
    plan_json = self._reviewed_plan_json(plan)
    confirmation = plan_json.get("confirmation")
    if not isinstance(confirmation, dict):
        raise PlanConfirmationError("Plan is missing confirmation metadata.")
    status = confirmation.get("status")
    if status not in {"confirmed", "declined"}:
        raise PlanConfirmationError("Plan confirmation status is invalid.")

    raw_actions = plan_json.get("confirmed_actions") or []
    if not isinstance(raw_actions, list):
        raise PlanConfirmationError("Confirmed actions must be a list.")

    return ConfirmationResult(
        run_id=plan.run_id,
        plan_id=plan.plan_id,
        status=status,
        confirmation_id=str(confirmation.get("confirmation_id")),
        selected=plan.selected,
        confirmed_actions=[
            ConfirmedActionSpec.model_validate(action)
            for action in raw_actions
        ],
        service_version=self.service_version,
    )
```

13. Add `backend/app/confirmation/__init__.py`.

Export:

```python
ConfirmationDecision
ConfirmationResult
ConfirmationStatus
ConfirmedActionSpec
ConfirmedActionType
HumanConfirmationService
PlanConfirmationError
```

14. Add unit tests in `tests/test_human_confirmation.py`.

Use real PostgreSQL session pattern from existing repository tests.

Create helper fixtures that:

- create user/run
- create selected reviewed plan row with Task 013-compatible `plan_json`
- create unselected reviewed plan
- create unsafe reviewed plan

Cover:

- selected reviewed plan can be confirmed
- confirmed plan status becomes `confirmed`
- confirmation metadata is written to `plan_json`
- confirmed actions include deterministic idempotency keys
- confirmed actions set `user_confirmed=True`
- original `draft.proposed_actions` still has no `idempotency_key`, `confirmation_id`, or `action_id`
- reconfirming returns same confirmation id and same idempotency keys
- selected reviewed plan can be declined
- declined plan status becomes `declined`
- re-declining returns same decline result
- confirming declined plan raises `PlanConfirmationError`
- declining confirmed plan raises `PlanConfirmationError`
- missing plan raises
- wrong-run plan raises
- unselected plan raises
- unsafe plan raises
- malformed `plan_json` raises
- proposed action with `requires_confirmation=False` raises
- proposed action containing `idempotency_key`, `confirmation_id`, or `action_id` raises
- proposed action with unsupported write tool raises
- plan with zero proposed actions can be confirmed and returns empty `confirmed_actions`
- service/repository do not self-commit; rollback removes confirmation mutation

15. Add integration test in `tests/integration/test_human_confirmation_gateway.py`.

Use the setup style from `tests/integration/test_plan_persistence_gateway.py`:

- `SessionLocal`
- `UserRepository`
- `AgentRunRepository`
- `ToolEventRepository`
- `ActionLedgerRepository`
- `PlanRepository`
- `ReviewedPlanPersistenceService`
- `HumanConfirmationService`
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
4. Execute initial read tool calls.
5. Enrich candidates.
6. Generate itinerary drafts.
7. Run Final Review Gate.
8. Persist reviewed plans.
9. Select the first persisted plan.
10. Count `ActionLedger` rows before confirmation.
11. Count `ToolEvent` rows before confirmation.
12. Confirm selected plan.
13. Assert result status is `confirmed`.
14. Assert at least one confirmed action exists when the draft proposed actions exist.
15. Assert every confirmed action has:
    - `user_confirmed=True`
    - non-empty `idempotency_key`
    - `tool_name` in write tools
    - `target_id`
16. Assert persisted plan row has `status == "confirmed"`.
17. Assert `plan_json["confirmation"]["status"] == "confirmed"`.
18. Assert Action Ledger count remains zero.
19. Assert Tool Event count does not increase during confirmation.

16. Update README.

Add section:

```markdown
## Human Confirmation Boundary

Focused human confirmation tests require PostgreSQL and Redis for the upstream gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_human_confirmation.py tests/integration/test_human_confirmation_gateway.py -v
```
```

Do not claim execution workflow or Action Ledger writer exists.

17. Run focused tests.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_human_confirmation.py -v
python -m pytest tests/integration/test_human_confirmation_gateway.py -v
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
  - confirm selected reviewed plan
  - decline selected reviewed plan
  - idempotent reconfirm/redecline
  - deterministic confirmation ID and action idempotency keys
  - malformed plan JSON failures
  - unsafe plan failure
  - missing/wrong-run/unselected plan failures
  - forbidden pre-confirmation execution fields failure
  - unsupported action type failure
  - zero-action plan confirmation
  - no self-commit behavior
- Integration tests:
  - parser -> planner -> query executor -> candidate enricher -> itinerary generator -> final review -> plan persistence -> plan selection -> confirmation
  - real PostgreSQL and Redis for upstream gateway path
  - no Action Ledger rows
  - Tool Event count unchanged during confirmation
- Smoke tests:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_human_confirmation.py -v
python -m pytest tests/integration/test_human_confirmation_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add human confirmation boundary
```

Expected branch:

```text
task14
```

Expected commands:

```bash
git switch task13
git switch -c task14
git status --short
git add README.md backend/app/repositories/plans.py backend/app/confirmation tests/test_human_confirmation.py tests/integration/test_human_confirmation_gateway.py docs/specs/014-human-confirmation-boundary.md docs/plans/014-human-confirmation-boundary-plan.md
git status --short
git commit -m "feat: add human confirmation boundary"
git push -u origin task14
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement Execution Workflow.
- Do not invoke Tool Gateway.
- Do not call providers.
- Do not execute write tools.
- Do not create Action Ledger rows.
- Do not implement Action Ledger writer.
- Do not add API endpoints.
- Do not add CLI or Web UI.
- Do not implement LangGraph.
- Do not implement agents, prompts, or LLM calls.
- Do not add Redis behavior.
- Do not add LangSmith tracing.
- Do not modify Final Review Gate rules.
- Do not modify Tool Gateway write execution behavior.
- Do not add database migrations unless the existing `plans` table is absent.
- Do not add benchmark harness or graders.
- Do not commit `.env`, API keys, tokens, secrets, generated caches, virtualenvs, logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task14`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] `HumanConfirmationService` is deterministic and importable.
- [ ] Confirmation schemas and errors are importable.
- [ ] Selected reviewed plans can be confirmed.
- [ ] Selected reviewed plans can be declined.
- [ ] Confirmed plan status is `confirmed`.
- [ ] Declined plan status is `declined`.
- [ ] Confirmation metadata is stored in `plans.plan_json`.
- [ ] Confirmed actions include deterministic idempotency keys.
- [ ] Original proposed actions are not mutated with execution fields.
- [ ] Missing, wrong-run, unselected, unsafe, and malformed plans fail cleanly.
- [ ] Confirmation and decline do not call Tool Gateway/providers/Redis/LangSmith/LLMs.
- [ ] Confirmation and decline do not create Action Ledger rows.
- [ ] Integration test proves Tool Event count unchanged during confirmation.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add human confirmation boundary`.
- [ ] Push to `origin/task14` succeeds.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused human confirmation unit test result.
- Focused integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 014 starts from `task13`.
- Existing `plans` table is sufficient; no migration is needed.
- Confirmation metadata can be stored in `plans.plan_json` for MVP.
- `plans.status` can represent `selected`, `confirmed`, and `declined`.
- Confirmation produces execution-ready action specs but does not execute them.
- Action Ledger rows are created later by Execution Workflow through Tool Gateway.
- API/UI/CLI confirmation surfaces are follow-up tasks.
