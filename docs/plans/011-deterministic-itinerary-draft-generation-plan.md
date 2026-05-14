# Plan: 011 Deterministic Itinerary Draft Generation

## 1. Spec Reference

Spec file:

```text
docs/specs/011-deterministic-itinerary-draft-generation.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task10`.
- Current Task 010 commit is `eee2c6d feat: add candidate enrichment and route matrix`.
- `backend/app/planning/enriched_candidates.py` defines enrichment result schemas.
- `backend/app/planning/enrichment.py` defines `CandidateEnricher`.
- `backend/app/planning/query_planner.py` supports Mock World and AMAP route templates.
- `backend/app/planning/execution.py` defines `QueryPlanExecutor`.
- No itinerary draft generator exists yet.
- No `PlanRepository` exists and this task must not add one.

## 3. Files to Add

- `backend/app/planning/itinerary_drafts.py` - Pydantic schemas for draft itinerary output.
- `backend/app/planning/itinerary_generation.py` - deterministic itinerary generator.
- `tests/test_itinerary_generation.py` - unit tests with constructed enrichment results.
- `tests/integration/test_itinerary_generation_gateway.py` - Mock World full read/draft pipeline integration test.
- `docs/specs/011-deterministic-itinerary-draft-generation.md` - Task 011 spec.
- `docs/plans/011-deterministic-itinerary-draft-generation-plan.md` - Task 011 plan.

## 4. Files to Modify

- `backend/app/planning/__init__.py` - export itinerary draft schemas and generator.
- `backend/app/planning/errors.py` - add `ItineraryGenerationError` only if the implementation needs an explicit exception type for programmer errors.
- `README.md` - add focused itinerary generation test command.

No dependency, Docker Compose, Alembic, database model, repository, Tool Gateway, provider, Redis, or API endpoint changes are expected.

## 5. Implementation Steps

1. Create branch:

```bash
git switch task10
git switch -c task11
```

2. Confirm baseline:

```bash
git status --short --branch
rg --files backend/app/planning backend/app/tool_gateway backend/app/providers tests docs/specs docs/plans
```

Expected:

- Branch is `task11`.
- Task 010 files exist.
- `backend/app/planning/itinerary_generation.py` does not exist yet.
- Working tree is clean before implementation.

3. Add `backend/app/planning/itinerary_drafts.py`.

Create these Pydantic models:

```python
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


DraftStatus = Literal["draft"]
TimelineItemType = Literal["activity", "transfer", "dining", "buffer"]
ProposedActionType = Literal["book_ticket", "reserve_restaurant", "join_queue"]


class ItineraryCandidateRef(BaseModel):
    candidate_id: str
    name: str
    category: str
    provider: str
    address: str | None = None
    tags: list[str] = Field(default_factory=list)
    tool_event_ids: list[UUID] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ItineraryRouteRef(BaseModel):
    origin_candidate_id: str
    destination_candidate_id: str
    provider: str
    mode: str
    distance_meters: int | None = None
    duration_minutes: int | None = None
    tool_event_id: UUID | None = None
    summary: str | None = None


class TimelineItem(BaseModel):
    sequence: int
    item_type: TimelineItemType
    title: str
    candidate_id: str | None = None
    duration_minutes: int
    start_label: str
    end_label: str
    notes: list[str] = Field(default_factory=list)


class ProposedAction(BaseModel):
    action_ref: str
    action_type: ProposedActionType
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
    reason: str


class FeasibilitySummary(BaseModel):
    is_feasible: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_duration_minutes: int
    route_duration_minutes: int | None = None
    queue_wait_minutes: int | None = None


class ItineraryDraft(BaseModel):
    draft_id: str
    status: DraftStatus = "draft"
    title: str
    summary: str
    activity: ItineraryCandidateRef
    dining: ItineraryCandidateRef
    route: ItineraryRouteRef | None = None
    timeline: list[TimelineItem] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    feasibility: FeasibilitySummary
    evidence: dict[str, Any] = Field(default_factory=dict)


class ItineraryFailureReason(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ItineraryDraftResult(BaseModel):
    run_id: UUID
    provider_profile: str
    drafts: list[ItineraryDraft] = Field(default_factory=list)
    failed_reasons: list[ItineraryFailureReason] = Field(default_factory=list)
    generator_version: str
```

4. Add `backend/app/planning/itinerary_generation.py`.

Implement:

```python
class DeterministicItineraryGenerator:
    generator_version = "deterministic_itinerary_generator_v1"

    def __init__(self, max_drafts: int = 3) -> None:
        self._max_drafts = max(0, max_drafts)

    def generate(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
    ) -> ItineraryDraftResult:
        ...
```

5. Implement input prechecks.

Rules:

- If no enriched activity candidates: return `ItineraryDraftResult` with failed reason `missing_activity_candidate`.
- If no enriched dining candidates: return failed reason `missing_dining_candidate`.
- If no usable route exists between selected activity/dining pairs: return failed reason `missing_usable_route`.
- Do not raise for ordinary planning gaps.

6. Implement usable route detection.

A route is usable when:

```text
entry.status in {"succeeded", "cached"}
and entry.origin_candidate_id matches an activity candidate
and entry.destination_candidate_id matches a dining candidate
```

Prefer routes with `duration_minutes` present, but do not reject routes solely because distance/duration is missing.

7. Implement candidate feasibility helpers.

For each `EnrichedCandidate`:

- Activity is available when:
  - `ticket_availability` is missing, or
  - `ticket_availability.available is True`
- Dining is available when:
  - `table_availability.available is True`, or
  - `queue.status == "open"`
- Dining with queue wait over 30 minutes remains usable but gets a warning and is deprioritized.

8. Implement deterministic pair ordering.

Build activity/dining pairs from route matrix entries and sort by:

1. route status usable first
2. activity ticket available before unavailable/missing-failed evidence
3. dining table available before queue-only
4. queue wait ascending, missing wait after known short wait
5. route duration ascending, missing duration after known duration
6. route distance ascending, missing distance after known distance
7. activity original order from `enrichment.enriched_activity_candidates`
8. dining original order from `enrichment.enriched_dining_candidates`

Do not add learned/personalized scoring. This is deterministic feasibility ordering only.

9. Implement draft construction.

For each selected pair up to `max_drafts`:

- `draft_id`: `draft_1`, `draft_2`, ...
- `title`: combine activity and dining names, for example `"Xuhui Family Science Museum + Green Bowl Family Bistro"`
- `summary`: one short deterministic sentence with activity, dining, and route duration
- `activity`: build `ItineraryCandidateRef`
- `dining`: build `ItineraryCandidateRef`
- `route`: build `ItineraryRouteRef`
- `timeline`: build timeline items
- `proposed_actions`: build proposed actions
- `feasibility`: build summary and warnings
- `evidence`: include parser/planner/enricher versions and source candidate IDs

10. Implement `ItineraryCandidateRef`.

Preserve:

- candidate ID
- name
- category
- provider
- address
- tags
- tool event IDs from the candidate's enrichment tool results
- evidence dictionary with available details:
  - `poi_detail`
  - `opening_hours`
  - `queue`
  - `table_availability`
  - `ticket_availability`

11. Implement timeline generation.

Use deterministic durations:

- activity block: 150 minutes
- transfer block: route duration if present, else 20 minutes
- dining block: 90 minutes
- buffer/wrap-up block: enough minutes to reach at least 240 total minutes, capped so total does not exceed 360 minutes

Start labels:

- If `plan.intent.time_window.start_at` exists, use `%H:%M` from that datetime.
- Otherwise use `13:30`.
- Calculate each following `start_label` and `end_label` by adding durations.
- If calculated total exceeds `plan.intent.time_window.end_at`, add warning `timeline_exceeds_requested_window`.

The MVP happy path should produce a total duration between 240 and 360 minutes.

12. Implement proposed actions.

For each draft:

- Add `book_ticket` when activity `ticket_availability.available is True`.
  - `target_id`: activity candidate ID
  - payload includes `poi_id`, `quantity`
  - quantity = adults + number of children, minimum 1
- Add `reserve_restaurant` when dining `table_availability.available is True`.
  - `target_id`: dining candidate ID
  - payload includes `restaurant_id`, `party_size`
  - if time slots exist, choose the first slot deterministically
- Add `join_queue` only when no table reservation action was added and dining queue status is `"open"`.
  - `target_id`: queue ID if present, else dining candidate ID
  - payload includes `queue_id` when available and `party_size`

Every action:

- `requires_confirmation=True`
- `action_ref`: stable local ref like `draft_1_action_1`
- must not include or claim a durable Action Ledger `idempotency_key`

13. Implement feasibility summary.

Set:

- `is_feasible=True` for generated drafts
- `reasons` include:
  - `activity_selected`
  - `dining_selected`
  - `route_verified`
- `warnings` include:
  - `long_queue_wait` when queue wait > 30
  - `missing_ticket_availability` if ticket evidence missing
  - `missing_table_or_queue_availability` if dining availability evidence missing
  - `timeline_exceeds_requested_window` when applicable
- `total_duration_minutes`
- `route_duration_minutes`
- `queue_wait_minutes`

14. Ensure no tool/provider/DB calls.

`DeterministicItineraryGenerator` must not import or instantiate:

- `ToolGateway`
- providers
- SQLAlchemy repositories
- Redis clients

It should be pure over Pydantic inputs.

15. Add unit tests in `tests/test_itinerary_generation.py`.

Cover:

- generator returns failed reason when activity candidates are missing
- generator returns failed reason when dining candidates are missing
- generator returns failed reason when route is missing
- generator creates one draft from one activity, one dining, and one route
- draft includes candidate refs, route ref, timeline, feasibility, and actions
- timeline total is between 240 and 360 minutes for MVP-like input
- ticket availability creates `book_ticket` action
- table availability creates `reserve_restaurant` action
- queue-only dining creates `join_queue` action
- table reservation is preferred over queue action when both exist
- route duration and queue wait affect deterministic ordering
- route and enrichment `tool_event_id` values are preserved
- generator does not mutate the input enrichment result

16. Add integration test in `tests/integration/test_itinerary_generation_gateway.py`.

Use the setup from Task 010 integration test:

- `SessionLocal`
- repositories for users/runs/tool events/action ledger
- Redis runtime fixtures
- `build_mock_world_registry`
- `ToolGateway`
- `DeterministicIntentParser`
- `DeterministicQueryPlanner`
- `QueryPlanExecutor`
- `CandidateEnricher`
- `DeterministicItineraryGenerator`

Scenario:

1. Create an `AgentRun`.
2. Parse the MVP family request.
3. Build Mock World query plan.
4. Execute initial calls.
5. Enrich candidates.
6. Generate itinerary drafts.
7. Assert:
   - at least one draft exists
   - first draft has activity, dining, route, timeline, proposed actions, and feasibility
   - all proposed actions require confirmation
   - no Tool Gateway write result is created by generator
   - Action Ledger row count for the run remains `0`
   - Tool Event count does not increase after calling generator

17. Update `backend/app/planning/__init__.py`.

Export:

```python
DeterministicItineraryGenerator
FeasibilitySummary
ItineraryCandidateRef
ItineraryDraft
ItineraryDraftResult
ItineraryFailureReason
ItineraryRouteRef
ProposedAction
TimelineItem
```

18. Optionally update `backend/app/planning/errors.py`.

Only add this if tests or implementation need explicit programmer-error signaling:

```python
class ItineraryGenerationError(ValueError):
    pass
```

Do not use this for ordinary missing candidates/routes; ordinary planning gaps should be returned as failed reasons.

19. Update README.

Add:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_itinerary_generation.py tests/integration/test_itinerary_generation_gateway.py -v
```

Do not claim LangGraph, Final Review, confirmation, or execution exists.

20. Run focused unit tests:

```bash
python -m pytest tests/test_itinerary_generation.py -v
```

21. Run focused integration test:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_itinerary_generation_gateway.py -v
```

22. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

23. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - missing activity/dining/route failure reasons
  - draft generation happy path
  - timeline duration and labels
  - proposed action generation
  - deterministic ordering
  - evidence and tool event preservation
  - pure generator behavior with no gateway/provider/DB imports
- Integration tests:
  - parser -> query planner -> query executor -> candidate enricher -> itinerary generator
  - real PostgreSQL and Redis for upstream gateway path
  - no Action Ledger rows
  - Tool Event count unchanged during draft generation
- Smoke:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_itinerary_generation.py -v
python -m pytest tests/integration/test_itinerary_generation_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add deterministic itinerary draft generation
```

Expected branch:

```text
task11
```

Expected commands:

```bash
git switch task10
git switch -c task11
git status --short
git add README.md backend/app/planning tests/test_itinerary_generation.py tests/integration/test_itinerary_generation_gateway.py docs/specs/011-deterministic-itinerary-draft-generation.md docs/plans/011-deterministic-itinerary-draft-generation-plan.md
git status --short
git commit -m "feat: add deterministic itinerary draft generation"
git push -u origin task11
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement LangGraph.
- Do not implement agents, prompts, or LLM calls.
- Do not implement Final Review Gate.
- Do not implement human confirmation.
- Do not execute write tools.
- Do not create Action Ledger rows.
- Do not persist into `plans`.
- Do not add `PlanRepository`.
- Do not add API endpoints.
- Do not add migrations.
- Do not add dependencies.
- Do not add benchmark harness or graders.
- Do not commit `.env`, API keys, tokens, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task11`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] Generator consumes Task 010 enrichment result.
- [ ] Generator is pure and does not call Tool Gateway/providers/DB/Redis.
- [ ] Generated drafts include activity, dining, route, timeline, feasibility, evidence, and proposed actions.
- [ ] Proposed actions require confirmation and are not executed.
- [ ] Happy-path Mock World integration generates at least one draft.
- [ ] Action Ledger remains empty.
- [ ] Tool Event count does not increase during draft generation.
- [ ] Failure cases return structured failed reasons.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add deterministic itinerary draft generation`.
- [ ] Push to `origin/task11` succeeds.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused itinerary unit test result.
- Focused integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 011 starts from `task10`.
- Mock World remains the required deterministic integration provider.
- Draft generation is deterministic MVP logic, not the bounded Itinerary Planner Agent.
- Plan persistence, Final Review, user confirmation, execution, LangGraph, and agents are follow-up tasks.
