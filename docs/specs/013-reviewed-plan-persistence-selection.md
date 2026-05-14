# Spec: 013 Reviewed Plan Persistence and Selection

## 1. Goal

Add deterministic persistence and selection for itinerary drafts that have passed the Final Review Gate.

After Task 012, WeekendPilot can review itinerary drafts and decide which drafts are safe to present. Task 013 should store those safe reviewed drafts in the existing PostgreSQL `plans` table so later human confirmation, execution workflow, CLI/Web demo, and benchmark harness code can rely on a durable selected plan record.

This task must not execute side-effect write tools. It only persists reviewed planning artifacts and marks one persisted plan as selected for a run.

## 2. Project Context

This task sits between Final Review Gate and Human-in-the-loop confirmation in `docs/PROJECT_BLUEPRINT.md`:

```text
generate_itinerary
-> validate
-> final_review
-> persist_reviewed_plans
-> wait_confirmation
-> execute
```

It supports these blueprint requirements:

- PostgreSQL is the durable source of truth.
- Final Review Gate remains deterministic and separate from persistence.
- Human confirmation remains the boundary before write tools.
- Execution Workflow and Action Ledger remain deterministic follow-up work.
- Later CLI/Web and benchmark harness code can fetch reviewed/selected plans from PostgreSQL.

Task 013 depends on:

- Task 002 `plans` table.
- Task 003 repository patterns.
- Task 011 itinerary draft schemas.
- Task 012 Final Review Gate result schemas.

## 3. Requirements

- Add `PlanRepository` for the existing `plans` table.
- Add a deterministic reviewed plan persistence service.
- Persist only reviewed drafts where `ReviewedDraft.safe_to_present is True`.
- Do not persist blocked drafts.
- Store persisted rows in the existing `plans` table:
  - `run_id`
  - `status="reviewed"` initially
  - `selected=False` initially
  - `plan_json` containing draft, review metadata, source versions, and persistence metadata.
- Provide idempotent persistence for repeated calls with the same `run_id` and `draft_id`.
- Provide a selection operation that marks exactly one plan selected for a run.
- Selecting a plan must:
  - verify the plan exists
  - verify the plan belongs to the requested `run_id`
  - set that plan to `selected=True` and `status="selected"`
  - set all other plans for the same run to `selected=False`
  - reset previously selected plans for the same run back to `status="reviewed"`
- Repositories and services must flush but not commit sessions.
- Add unit tests for repository/service behavior.
- Add integration test that runs the read-only planning path through Final Review Gate, persists reviewed plans, selects one, and confirms no write tools or Action Ledger rows are created.
- README must include focused plan persistence test commands.
- No database migration should be added unless the existing `plans` table is missing.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement user confirmation API or UI.
- Do not execute write tools.
- Do not write Action Ledger rows.
- Do not implement Action Ledger writer.
- Do not implement Execution Workflow.
- Do not implement LangGraph.
- Do not implement Supervisor, Discovery, Dining, Itinerary Planner, or Validator agents.
- Do not call LLMs.
- Do not call Tool Gateway or providers from the persistence service.
- Do not add Redis usage.
- Do not add LangSmith tracing.
- Do not add database migrations unless the existing `plans` model/table is absent.
- Do not change Final Review Gate rules.
- Do not add benchmark cases or graders.
- Do not commit `.env`, generated caches, virtualenvs, Docker volumes, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- `FinalReviewResult` from `backend.app.review`.
- `ItineraryDraftResult` from `backend.app.planning`.
- Existing SQLAlchemy `Session`.
- Existing PostgreSQL `plans` table.

### Outputs

- `plans` rows for safe reviewed drafts.
- Structured persistence result.
- Selected plan row for a run.

### Public Modules

Task 013 may add:

```text
backend.app.repositories.plans
backend.app.plans.__init__
backend.app.plans.errors
backend.app.plans.schemas
backend.app.plans.persistence
```

### PlanRepository Contract

```python
class PlanRepository:
    def __init__(self, session: Session) -> None:
        ...

    def create(
        self,
        run_id: UUID,
        status: str,
        plan_json: dict[str, Any],
        selected: bool = False,
    ) -> Plan:
        ...

    def get_by_id(self, plan_id: UUID) -> Plan | None:
        ...

    def list_for_run(self, run_id: UUID) -> list[Plan]:
        ...

    def find_by_run_and_draft_id(self, run_id: UUID, draft_id: str) -> Plan | None:
        ...

    def update_status(self, plan_id: UUID, status: str) -> Plan | None:
        ...

    def select_for_run(self, run_id: UUID, plan_id: UUID) -> Plan | None:
        ...
```

`find_by_run_and_draft_id` should inspect existing rows for the run and compare `plan_json["draft_id"]` to avoid adding a migration solely for a unique constraint.

### ReviewedPlanPersistenceService Contract

```python
class ReviewedPlanPersistenceService:
    service_version = "reviewed_plan_persistence_v1"

    def __init__(self, plans: PlanRepository) -> None:
        ...

    def persist_reviewed_drafts(
        self,
        review: FinalReviewResult,
        drafts: ItineraryDraftResult,
    ) -> PersistedPlanResult:
        ...

    def select_plan(
        self,
        run_id: UUID,
        plan_id: UUID,
    ) -> PersistedPlan:
        ...
```

### Persistence Schemas

```python
PlanPersistenceStatus = Literal["created", "already_exists"]
SkippedPlanReason = Literal[
    "review_blocked",
    "draft_not_found",
    "not_safe_to_present",
]

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

### `plan_json` Contract

Persisted `plan_json` must use this top-level shape:

```json
{
  "schema_version": "reviewed_plan_v1",
  "persistence_version": "reviewed_plan_persistence_v1",
  "run_id": "uuid",
  "provider_profile": "mock_world",
  "draft_id": "draft_1",
  "status": "reviewed",
  "safe_to_present": true,
  "review_decision": "approved",
  "draft": {},
  "reviewed_draft": {},
  "final_review": {
    "decision": "approved_with_warnings",
    "safe_to_present": true,
    "gate_version": "final_review_gate_v1"
  },
  "source_versions": {
    "generator_version": "deterministic_itinerary_generator_v1",
    "gate_version": "final_review_gate_v1",
    "persistence_version": "reviewed_plan_persistence_v1"
  }
}
```

`draft` must come from `ItineraryDraft.model_dump(mode="json")`.
`reviewed_draft` must come from `ReviewedDraft.model_dump(mode="json")`.

## 6. Observability

Task 013 does not add LangSmith or Redis observability.

It must persist enough metadata in PostgreSQL for later tracing and benchmark review:

- `run_id`
- `draft_id`
- `provider_profile`
- Final Review top-level decision.
- Per-draft review decision.
- `gate_version`
- itinerary `generator_version`
- persistence service version.
- review warnings/errors inside `reviewed_draft`.

No Tool Gateway event should be created by persistence or selection.

## 7. Failure Handling

- If `review.run_id != drafts.run_id`, raise `PlanPersistenceError`.
- If `review.provider_profile != drafts.provider_profile`, raise `PlanPersistenceError`.
- If `review.safe_to_present is False`, persist no plans and return skipped drafts for reviewed drafts.
- If a reviewed draft is safe but the matching draft is missing from `drafts.drafts`, skip it with `reason="draft_not_found"`.
- If a reviewed draft is blocked or not safe to present, skip it with `reason="not_safe_to_present"`.
- If persistence is called repeatedly for the same `run_id` and `draft_id`, return the existing row instead of creating a duplicate.
- If selecting a missing plan, raise `PlanSelectionError`.
- If selecting a plan that belongs to a different run, raise `PlanSelectionError`.
- Repository and service methods must not commit. Caller owns transaction boundaries.

## 8. Acceptance Criteria

- [ ] `PlanRepository` exists and is exported from `backend.app.repositories`.
- [ ] Reviewed plan persistence service exists and is importable.
- [ ] Safe reviewed drafts are persisted into the existing `plans` table.
- [ ] Blocked or unsafe reviewed drafts are not persisted.
- [ ] Repeated persistence for the same `run_id` and `draft_id` does not create duplicate rows.
- [ ] Persisted rows initially have `status="reviewed"` and `selected=False`.
- [ ] Persisted `plan_json` includes draft, reviewed draft, final review metadata, source versions, and persistence version.
- [ ] Selecting a plan marks exactly one plan selected for the run.
- [ ] Selecting a missing or wrong-run plan fails cleanly.
- [ ] Persistence and selection do not call Tool Gateway, providers, Redis, LangSmith, LLMs, or write tools.
- [ ] Integration test confirms Action Ledger remains empty.
- [ ] Integration test confirms Tool Event count does not increase during persistence/selection.
- [ ] README includes focused plan persistence verification commands.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task13` branch created from `task12`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task12
git switch -c task13
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_plan_persistence.py -v
python -m pytest tests/integration/test_plan_persistence_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add reviewed plan persistence and selection
```

## 11. Notes for the Implementer

If Task 012 files are missing, stop and report the branch/base mismatch.

Keep this task focused on durable reviewed plan records and deterministic selection. Do not add user confirmation, write tool execution, Action Ledger writer, LangGraph, agents, benchmark graders, or API endpoints in Task 013.
