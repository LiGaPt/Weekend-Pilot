# Spec: 011 Deterministic Itinerary Draft Generation

## 1. Goal

Add a deterministic itinerary draft generation service for WeekendPilot.

After Task 010, the system can collect enriched activity and dining candidates, availability evidence, queue/table/ticket information, and route matrix entries. Task 011 should consume that enrichment result and produce 2-3 structured itinerary draft options that later Final Review, human confirmation, execution workflow, and demo surfaces can consume.

This task creates plan drafts only. It must not call LLMs, execute write tools, persist plans to PostgreSQL, implement LangGraph, or run the deterministic execution workflow.

## 2. Project Context

This task follows the blueprint workflow:

```text
parse_intent
-> load_memory
-> build_query_plan
-> discover_candidates
-> enrich_candidates
-> generate_itinerary
-> validate
-> final_review
-> wait_confirmation
-> execute
```

Task 011 covers the first deterministic version of `generate_itinerary`. It intentionally remains a service-layer module rather than an Itinerary Planner Agent. The later bounded multi-agent layer may replace or augment this generator, but it should be able to reuse the same structured output contracts.

Task 011 unlocks:

- a stable structured plan object for Final Review Gate
- a user-facing draft plan shape for CLI/Web demo
- proposed write-action planning without side effects
- LocalLife-Bench trajectory assertions beyond raw tool calls

## 3. Requirements

- Add deterministic itinerary draft generation under `backend.app.planning`.
- Consume:
  - `QueryPlan`
  - `CandidateEnrichmentResult`
- Produce an `ItineraryDraftResult` containing 0-3 `ItineraryDraft` options.
- Default to at most 3 draft options.
- Generate only options that contain:
  - one activity candidate
  - one dining candidate
  - one usable activity-to-dining route when available
- Preserve candidate IDs, route evidence, tool event IDs, and availability evidence references.
- Build deterministic timeline items for:
  - activity block
  - transfer block
  - dining block
  - optional buffer/wrap-up block
- Respect requested time intent when available:
  - use `plan.intent.time_window.start_at` and `end_at` when present
  - otherwise use deterministic afternoon clock labels starting at `13:30`
- Aim for 4-6 hour coverage for MVP family-afternoon requests.
- Produce proposed write actions without executing them:
  - `book_ticket` when ticket availability is available
  - `reserve_restaurant` when table availability is available
  - `join_queue` when queue is open and table reservation is not preferred/available
- Every proposed action must include:
  - `action_type`
  - `target_id`
  - `payload`
  - `requires_confirmation=True`
  - a stable local `action_ref`
- Do not call Tool Gateway.
- Do not call providers directly.
- Do not write Action Ledger.
- Do not write PostgreSQL `plans` rows.
- Keep draft ordering deterministic using feasibility-first rules:
  - successful route before failed/missing route
  - available ticket/table/queue evidence before missing evidence
  - shorter route duration before longer route duration
  - lower queue wait before higher queue wait
  - original candidate order as final tie-breaker
- Return structured failure reasons when no draft can be generated.
- Add unit tests with constructed enrichment results.
- Add an integration test running the existing pipeline through Mock World:
  - intent parser
  - query planner
  - query plan executor
  - candidate enricher
  - itinerary draft generator
- README should include a focused itinerary draft test command.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement LangGraph.
- Do not implement Supervisor, Discovery, Dining, Itinerary Planner, or Validator agents.
- Do not call LLMs.
- Do not implement Final Review Gate.
- Do not implement human confirmation.
- Do not execute write tools.
- Do not write Action Ledger rows.
- Do not implement Execution Workflow.
- Do not persist generated drafts into the `plans` table.
- Do not add `PlanRepository`.
- Do not add database migrations.
- Do not add FastAPI endpoints.
- Do not add benchmark cases or graders.
- Do not implement personalized or learned scoring.

## 5. Interfaces and Contracts

### Inputs

- `QueryPlan`
- `CandidateEnrichmentResult`
- optional `max_drafts: int`, default `3`

### Outputs

- `ItineraryDraftResult`
- no Tool Gateway calls
- no PostgreSQL writes
- no Redis writes
- no Action Ledger rows

### Public Modules

Task 011 may add:

```text
backend.app.planning.itinerary_drafts
backend.app.planning.itinerary_generation
```

### Public API

```python
class DeterministicItineraryGenerator:
    generator_version = "deterministic_itinerary_generator_v1"

    def __init__(self, max_drafts: int = 3) -> None:
        ...

    def generate(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
    ) -> ItineraryDraftResult:
        ...
```

### ItineraryDraftResult Schema

Required fields:

```text
run_id: UUID
provider_profile: str
drafts: list[ItineraryDraft]
failed_reasons: list[ItineraryFailureReason]
generator_version: str
```

### ItineraryDraft Schema

Required fields:

```text
draft_id: str
status: "draft"
title: str
summary: str
activity: ItineraryCandidateRef
dining: ItineraryCandidateRef
route: ItineraryRouteRef | None
timeline: list[TimelineItem]
proposed_actions: list[ProposedAction]
feasibility: FeasibilitySummary
evidence: dict
```

### ItineraryCandidateRef Schema

Required fields:

```text
candidate_id: str
name: str
category: str
provider: str
address: str | None
tags: list[str]
tool_event_ids: list[UUID]
evidence: dict
```

### ItineraryRouteRef Schema

Required fields:

```text
origin_candidate_id: str
destination_candidate_id: str
provider: str
mode: str
distance_meters: int | None
duration_minutes: int | None
tool_event_id: UUID | None
summary: str | None
```

### TimelineItem Schema

Required fields:

```text
sequence: int
item_type: "activity" | "transfer" | "dining" | "buffer"
title: str
candidate_id: str | None
duration_minutes: int
start_label: str
end_label: str
notes: list[str]
```

### ProposedAction Schema

Required fields:

```text
action_ref: str
action_type: "book_ticket" | "reserve_restaurant" | "join_queue"
target_id: str
payload: dict
requires_confirmation: bool
reason: str
```

### FeasibilitySummary Schema

Required fields:

```text
is_feasible: bool
reasons: list[str]
warnings: list[str]
total_duration_minutes: int
route_duration_minutes: int | None
queue_wait_minutes: int | None
```

### ItineraryFailureReason Schema

Required fields:

```text
code: str
message: str
details: dict
```

## 6. Observability

Task 011 does not create new durable observability rows.

The generated drafts must preserve references to existing evidence:

- candidate IDs
- route `tool_event_id`
- enrichment `tool_event_id`
- provider profile
- generator version

No LangSmith tracing is added in this task.

## 7. Failure Handling

- If no enriched activity candidates exist, return no drafts and failed reason `missing_activity_candidate`.
- If no enriched dining candidates exist, return no drafts and failed reason `missing_dining_candidate`.
- If no usable route exists:
  - return no drafts by default
  - include failed reason `missing_usable_route`
- If a candidate has unavailable ticket/table evidence, deprioritize or skip it according to feasibility rules.
- If queue wait is present and greater than 30 minutes, add a warning and deprioritize the dining option.
- If time-window data is missing, use deterministic labels rather than failing.
- Malformed optional evidence should produce warnings, not exceptions.
- The service must not execute any tool or write any durable state.

## 8. Acceptance Criteria

- [ ] `DeterministicItineraryGenerator` exists and is importable.
- [ ] Itinerary draft schemas are typed and importable.
- [ ] Generator consumes `QueryPlan` and `CandidateEnrichmentResult`.
- [ ] Generator produces 1-3 itinerary drafts for the Mock World MVP happy path.
- [ ] Each draft includes activity, dining, route, timeline, feasibility summary, evidence, and proposed actions.
- [ ] Drafts preserve candidate IDs and relevant `tool_event_id` values.
- [ ] Timeline covers the MVP 4-6 hour target unless a warning explains why not.
- [ ] Proposed actions are generated but no write tools are executed.
- [ ] No Tool Gateway/provider calls occur inside the generator.
- [ ] Empty/missing activity, dining, or route inputs return structured failed reasons.
- [ ] Unit tests cover deterministic ordering and failure cases.
- [ ] Integration test runs parser -> planner -> executor -> enricher -> itinerary generator with Mock World.
- [ ] Integration test confirms no Action Ledger rows are created by the full read/draft path.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task11` branch created from `task10`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task10
git switch -c task11
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_itinerary_generation.py -v
python -m pytest tests/integration/test_itinerary_generation_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add deterministic itinerary draft generation
```

## 11. Notes for the Implementer

If Task 010 files are missing, stop and report the branch/base mismatch.

Keep Task 011 focused on deterministic draft generation. Do not add LangGraph, agents, Final Review, persistence, confirmation, or execution in this task.
