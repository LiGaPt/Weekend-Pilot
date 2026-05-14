# Plan: 013 Reviewed Plan Persistence and Selection

## 1. Spec Reference

Spec file:

```text
docs/specs/013-reviewed-plan-persistence-selection.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task12`.
- Current Task 012 commit is `a58e699 feat: add final review gate`.
- `backend/app/review/final_review_gate.py` defines `FinalReviewGate`.
- `backend/app/review/schemas.py` defines `FinalReviewResult`, `ReviewedDraft`, and `ReviewCheck`.
- `backend/app/planning/itinerary_drafts.py` defines `ItineraryDraft` and `ItineraryDraftResult`.
- `backend/app/models/runtime.py` already defines `Plan`.
- PostgreSQL migration `0001_create_core_runtime_tables` already creates `plans`.
- Existing repositories flush and refresh records but do not self-commit.
- No `PlanRepository` exists yet.
- No `backend/app/plans` package exists yet.
- No user confirmation or execution workflow exists yet.

## 3. Files to Add

- `backend/app/repositories/plans.py` - repository for existing `plans` table.
- `backend/app/plans/__init__.py` - exports plan persistence public API.
- `backend/app/plans/errors.py` - `PlanPersistenceError` and `PlanSelectionError`.
- `backend/app/plans/schemas.py` - Pydantic result schemas for persisted and skipped plans.
- `backend/app/plans/persistence.py` - deterministic reviewed plan persistence and selection service.
- `tests/test_plan_persistence.py` - unit tests for repository/service behavior.
- `tests/integration/test_plan_persistence_gateway.py` - full read-only planning/review/persistence integration test.
- `docs/specs/013-reviewed-plan-persistence-selection.md` - Task 013 spec.
- `docs/plans/013-reviewed-plan-persistence-selection-plan.md` - Task 013 plan.

## 4. Files to Modify

- `backend/app/repositories/__init__.py` - export `PlanRepository`.
- `README.md` - add focused reviewed plan persistence test command.

No changes are expected in:

- `backend/app/models/runtime.py`
- `alembic/versions`
- Tool Gateway
- providers
- Redis runtime
- Final Review Gate
- planning generators
- FastAPI endpoints

## 5. Implementation Steps

1. Create task branch.

```bash
git switch task12
git switch -c task13
git status --short --branch
```

Expected:

- Branch is `task13`.
- Working tree is clean before implementation.

2. Confirm baseline files.

```bash
rg --files backend/app/review backend/app/planning backend/app/repositories backend/app/models tests/integration docs/specs docs/plans
```

Expected:

- Task 012 review files exist.
- `backend/app/models/runtime.py` contains `Plan`.
- `backend/app/repositories/plans.py` does not exist yet.

3. Add `backend/app/repositories/plans.py`.

Implement using the existing repository style:

```python
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.runtime import Plan


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        run_id: UUID,
        status: str,
        plan_json: dict[str, Any],
        selected: bool = False,
    ) -> Plan:
        plan = Plan(
            run_id=run_id,
            status=status,
            plan_json=plan_json,
            selected=selected,
        )
        self.session.add(plan)
        self.session.flush()
        self.session.refresh(plan)
        return plan

    def get_by_id(self, plan_id: UUID) -> Plan | None:
        return self.session.get(Plan, plan_id)

    def list_for_run(self, run_id: UUID) -> list[Plan]:
        statement = (
            select(Plan)
            .where(Plan.run_id == run_id)
            .order_by(Plan.created_at, Plan.plan_id)
        )
        return list(self.session.scalars(statement).all())

    def find_by_run_and_draft_id(self, run_id: UUID, draft_id: str) -> Plan | None:
        for plan in self.list_for_run(run_id):
            if isinstance(plan.plan_json, dict) and plan.plan_json.get("draft_id") == draft_id:
                return plan
        return None

    def update_status(self, plan_id: UUID, status: str) -> Plan | None:
        plan = self.get_by_id(plan_id)
        if plan is None:
            return None
        plan.status = status
        self.session.flush()
        self.session.refresh(plan)
        return plan

    def select_for_run(self, run_id: UUID, plan_id: UUID) -> Plan | None:
        target = self.get_by_id(plan_id)
        if target is None or target.run_id != run_id:
            return None

        for plan in self.list_for_run(run_id):
            if plan.plan_id == plan_id:
                plan.selected = True
                plan.status = "selected"
            else:
                plan.selected = False
                if plan.status == "selected":
                    plan.status = "reviewed"

        self.session.flush()
        self.session.refresh(target)
        return target
```

Do not call `commit()`.

4. Export `PlanRepository`.

Modify `backend/app/repositories/__init__.py`:

```python
from backend.app.repositories.plans import PlanRepository
```

Add `"PlanRepository"` to `__all__`.

5. Add `backend/app/plans/errors.py`.

```python
class PlanPersistenceError(ValueError):
    pass


class PlanSelectionError(ValueError):
    pass
```

6. Add `backend/app/plans/schemas.py`.

Create:

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


PlanPersistenceStatus = Literal["created", "already_exists"]
SkippedPlanReason = Literal["review_blocked", "draft_not_found", "not_safe_to_present"]


class PersistedPlan(BaseModel):
    plan_id: UUID
    run_id: UUID
    draft_id: str
    status: str
    selected: bool
    safe_to_present: bool
    review_decision: str
    persistence_status: PlanPersistenceStatus | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkippedDraft(BaseModel):
    draft_id: str
    reason: SkippedPlanReason
    review_decision: str | None = None
    message: str


class PersistedPlanResult(BaseModel):
    run_id: UUID
    persisted_plans: list[PersistedPlan] = Field(default_factory=list)
    skipped_drafts: list[SkippedDraft] = Field(default_factory=list)
    service_version: str
```

7. Add `backend/app/plans/persistence.py`.

Implement:

```python
class ReviewedPlanPersistenceService:
    service_version = "reviewed_plan_persistence_v1"

    def __init__(self, plans: PlanRepository) -> None:
        self.plans = plans

    def persist_reviewed_drafts(
        self,
        review: FinalReviewResult,
        drafts: ItineraryDraftResult,
    ) -> PersistedPlanResult:
        ...
```

Rules:

- Validate `review.run_id == drafts.run_id`.
- Validate `review.provider_profile == drafts.provider_profile`.
- Build `draft_by_id = {draft.draft_id: draft for draft in drafts.drafts}`.
- If `review.safe_to_present is False`, skip every `review.reviewed_drafts` item with `reason="review_blocked"`.
- For each `reviewed_draft`:
  - if `reviewed_draft.safe_to_present is False`, skip with `reason="not_safe_to_present"`.
  - if matching draft is missing, skip with `reason="draft_not_found"`.
  - if existing plan exists for same `run_id` and `draft_id`, return it with `persistence_status="already_exists"`.
  - otherwise create a row with `status="reviewed"`, `selected=False`, and `persistence_status="created"`.
- Return `PersistedPlanResult`.

8. Implement plan JSON builder in `persistence.py`.

Add private helper:

```python
def _build_plan_json(
    self,
    review: FinalReviewResult,
    reviewed_draft: ReviewedDraft,
    draft: ItineraryDraft,
    drafts: ItineraryDraftResult,
) -> dict[str, Any]:
    return {
        "schema_version": "reviewed_plan_v1",
        "persistence_version": self.service_version,
        "run_id": str(review.run_id),
        "provider_profile": review.provider_profile,
        "draft_id": draft.draft_id,
        "status": "reviewed",
        "safe_to_present": reviewed_draft.safe_to_present,
        "review_decision": reviewed_draft.decision,
        "draft": draft.model_dump(mode="json"),
        "reviewed_draft": reviewed_draft.model_dump(mode="json"),
        "final_review": {
            "decision": review.decision,
            "safe_to_present": review.safe_to_present,
            "gate_version": review.gate_version,
        },
        "source_versions": {
            "generator_version": drafts.generator_version,
            "gate_version": review.gate_version,
            "persistence_version": self.service_version,
        },
    }
```

9. Implement conversion from ORM row to schema.

Private helper:

```python
def _to_persisted_plan(
    self,
    plan: Plan,
    persistence_status: PlanPersistenceStatus | None = None,
) -> PersistedPlan:
    plan_json = plan.plan_json if isinstance(plan.plan_json, dict) else {}
    return PersistedPlan(
        plan_id=plan.plan_id,
        run_id=plan.run_id,
        draft_id=str(plan_json.get("draft_id", "")),
        status=plan.status,
        selected=plan.selected,
        safe_to_present=bool(plan_json.get("safe_to_present", False)),
        review_decision=str(plan_json.get("review_decision", "")),
        persistence_status=persistence_status,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )
```

10. Implement selection in service.

```python
def select_plan(self, run_id: UUID, plan_id: UUID) -> PersistedPlan:
    selected = self.plans.select_for_run(run_id, plan_id)
    if selected is None:
        raise PlanSelectionError("Plan does not exist for the requested run.")
    return self._to_persisted_plan(selected)
```

11. Add `backend/app/plans/__init__.py`.

Export:

```python
PlanPersistenceError
PlanSelectionError
PersistedPlan
PersistedPlanResult
PlanPersistenceStatus
ReviewedPlanPersistenceService
SkippedDraft
SkippedPlanReason
```

12. Add unit tests in `tests/test_plan_persistence.py`.

Use real PostgreSQL session pattern from `tests/integration/test_repositories.py` or an existing DB fixture style.

Cover:

- `PlanRepository.create`, `get_by_id`, `list_for_run`.
- `PlanRepository.find_by_run_and_draft_id`.
- `PlanRepository.select_for_run` marks exactly one selected.
- Repository methods do not self-commit; rollback removes rows.
- Service persists safe reviewed drafts.
- Service skips unsafe reviewed drafts.
- Service skips when top-level review is blocked.
- Service is idempotent for same `run_id` and `draft_id`.
- Persisted row starts with `status="reviewed"` and `selected=False`.
- Persisted `plan_json` contains:
  - `schema_version`
  - `persistence_version`
  - `run_id`
  - `provider_profile`
  - `draft_id`
  - `draft`
  - `reviewed_draft`
  - `final_review`
  - `source_versions`
- `select_plan` returns selected persisted plan.
- Selecting missing plan raises `PlanSelectionError`.
- Selecting wrong-run plan raises `PlanSelectionError`.
- Mismatched review/draft run metadata raises `PlanPersistenceError`.

13. Add integration test in `tests/integration/test_plan_persistence_gateway.py`.

Use the setup style from `tests/integration/test_final_review_gate_gateway.py`:

- `SessionLocal`
- `UserRepository`
- `AgentRunRepository`
- `ToolEventRepository`
- `ActionLedgerRepository`
- `PlanRepository`
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
- `ReviewedPlanPersistenceService`

Scenario:

1. Create a user and `AgentRun`.
2. Parse the MVP family request.
3. Build Mock World query plan.
4. Execute initial read tool calls.
5. Enrich candidates.
6. Generate itinerary drafts.
7. Run Final Review Gate.
8. Count `ActionLedger` rows before persistence.
9. Count `ToolEvent` rows before persistence.
10. Persist reviewed plans.
11. Assert at least one persisted plan exists.
12. Assert all persisted plans are `selected is False`.
13. Select the first persisted plan.
14. Assert exactly one `plans` row for the run has `selected is True`.
15. Assert selected row has `status == "selected"`.
16. Assert Action Ledger count remains zero.
17. Assert Tool Event count does not increase during persistence/selection.

14. Update README.

Add section:

```markdown
## Reviewed Plan Persistence

Focused reviewed plan persistence tests require PostgreSQL and Redis for the upstream gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_plan_persistence.py tests/integration/test_plan_persistence_gateway.py -v
```
```

Do not claim user confirmation, execution, or Action Ledger writer exists.

15. Run focused tests.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_plan_persistence.py -v
python -m pytest tests/integration/test_plan_persistence_gateway.py -v
```

16. Run full verification.

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

17. Inspect tracked files and secrets.

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - repository create/get/list/find/select behavior
  - no self-commit behavior
  - service persistence of safe reviewed drafts
  - skipped blocked/unsafe drafts
  - idempotent persistence for same run/draft
  - selection success and failure paths
  - persisted `plan_json` contract
- Integration tests:
  - parser -> planner -> query executor -> candidate enricher -> itinerary generator -> final review -> plan persistence -> plan selection
  - real PostgreSQL and Redis for upstream gateway path
  - no Action Ledger rows
  - Tool Event count unchanged during persistence/selection
- Smoke tests:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_plan_persistence.py -v
python -m pytest tests/integration/test_plan_persistence_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add reviewed plan persistence and selection
```

Expected branch:

```text
task13
```

Expected commands:

```bash
git switch task12
git switch -c task13
git status --short
git add README.md backend/app/repositories/__init__.py backend/app/repositories/plans.py backend/app/plans tests/test_plan_persistence.py tests/integration/test_plan_persistence_gateway.py docs/specs/013-reviewed-plan-persistence-selection.md docs/plans/013-reviewed-plan-persistence-selection-plan.md
git status --short
git commit -m "feat: add reviewed plan persistence and selection"
git push -u origin task13
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement user confirmation.
- Do not execute write tools.
- Do not create Action Ledger rows.
- Do not implement Action Ledger writer.
- Do not implement Execution Workflow.
- Do not implement LangGraph.
- Do not implement agents, prompts, or LLM calls.
- Do not call Tool Gateway/providers from persistence or selection.
- Do not add Redis or LangSmith behavior.
- Do not modify Final Review Gate rules.
- Do not add migrations unless the existing `plans` table is absent.
- Do not add API endpoints.
- Do not add benchmark harness or graders.
- Do not commit `.env`, API keys, tokens, secrets, generated caches, virtualenvs, logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task13`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] `PlanRepository` is deterministic and importable.
- [ ] `PlanRepository` is exported from `backend.app.repositories`.
- [ ] Reviewed plan persistence service is deterministic and importable.
- [ ] Safe reviewed drafts are persisted.
- [ ] Unsafe/blocked drafts are skipped.
- [ ] Repeated persistence does not duplicate rows for same `run_id` and `draft_id`.
- [ ] Persisted rows use existing `plans` table without migration.
- [ ] Initial persisted rows are `status="reviewed"` and `selected=False`.
- [ ] Selection marks exactly one plan selected for a run.
- [ ] Wrong-run and missing-plan selection fail cleanly.
- [ ] Persistence and selection do not call Tool Gateway/providers/Redis/LangSmith/LLMs.
- [ ] Integration test proves Tool Event count unchanged during persistence/selection.
- [ ] Integration test proves Action Ledger remains empty.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add reviewed plan persistence and selection`.
- [ ] Push to `origin/task13` succeeds.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused plan persistence unit test result.
- Focused integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 013 starts from `task12`.
- `plans` table from Task 002 is available and migrated.
- No database migration is required for Task 013.
- Duplicate prevention is implemented in repository/service logic by checking existing `plan_json["draft_id"]` for the same run.
- Persistence to PostgreSQL is allowed before user confirmation because it records reviewed planning artifacts, not external side effects.
- Human confirmation, write tool execution, Action Ledger writer, LangGraph, agents, recovery routing, and benchmark graders are follow-up tasks.
