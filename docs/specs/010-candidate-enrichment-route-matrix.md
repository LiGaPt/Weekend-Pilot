# Spec: 010 Candidate Enrichment and Route Matrix

## 1. Goal

Add a deterministic candidate enrichment and route matrix service for WeekendPilot.

After Task 009, WeekendPilot can execute initial query-plan read calls and collect normalized activity and dining candidates. Task 010 should consume `QueryPlan` plus `CandidateCollectionResult`, execute planned enrichment and route read tools through Tool Gateway, and return structured enrichment evidence for later candidate merging, feasibility review, and itinerary generation.

This task must stay read-only and deterministic. It must not generate itineraries, rank plans, call LLMs, implement LangGraph, or execute write tools.

## 2. Project Context

This task follows the blueprint workflow:

```text
parse_intent
-> load_memory
-> build_query_plan
-> discover_candidates
-> enrich_candidates
-> generate_itinerary
```

Task 010 covers the deterministic `enrich_candidates` service layer and lays groundwork for:

- Availability Checker
- Route & Time Calculator
- Candidate Merger
- Itinerary Planner Agent
- Validator & Recovery Agent
- Final Review Gate

It must continue the existing architecture principle that all tool calls go through Tool Gateway, and that write tools are blocked before explicit user confirmation.

## 3. Requirements

- Add a candidate enrichment service under `backend.app.planning`.
- Consume:
  - `QueryPlan`
  - `CandidateCollectionResult`
  - existing `ToolGateway`
- Execute only read tools from:
  - `QueryPlan.candidate_enrichment_templates`
  - `QueryPlan.route_templates`
- Never execute `QueryPlan.initial_tool_calls`; those remain owned by Task 009.
- Never execute write tools.
- Reject any write tool found in enrichment or route templates before invoking Tool Gateway.
- Invoke providers only through `ToolGateway`.
- Preserve `tool_event_id`, provider, tool name, status, response JSON, and error JSON for every gateway result.
- Enrich bounded candidate sets, preserving provider order:
  - default max 3 activity candidates
  - default max 3 dining candidates
  - default max 0 other candidates unless explicitly configured
- Deduplicate selected candidates by `candidate_id` while preserving first occurrence.
- For activity candidates, support:
  - `get_poi_detail`
  - `check_opening_hours`
  - `check_ticket_availability`
- For dining candidates, support:
  - `get_poi_detail`
  - `check_opening_hours`
  - `check_queue`
  - `check_table_availability`
- For other candidates, support only:
  - `get_poi_detail`
  - `check_opening_hours`
- Build route matrix entries for selected activity-to-dining pairs using `check_route`.
- Normalize route distance and duration where possible:
  - `distance_meters`
  - `duration_minutes`
- Support Mock World route payloads using candidate IDs:
  - `origin_id`
  - `destination_id`
- Support AMAP route payloads when both candidates expose text locations:
  - `origin`
  - `destination`
- Record missing template inputs as failed local tool results without calling Tool Gateway.
- Continue on failed gateway/local results when `fail_fast=False`.
- Raise `CandidateEnrichmentError` on the first failed gateway/local result when `fail_fast=True`.
- Add unit tests using fake gateway objects.
- Add integration tests using real PostgreSQL and Redis with Mock World through Tool Gateway.
- README should include focused commands for candidate enrichment and route matrix tests.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement Candidate Merger scoring or ranking.
- Do not generate final itineraries.
- Do not create proposed action lists.
- Do not implement LangGraph.
- Do not implement agents or LLM calls.
- Do not implement Memory Retriever.
- Do not implement Execution Workflow.
- Do not write Action Ledger rows.
- Do not call providers directly.
- Do not add FastAPI endpoints.
- Do not add PostgreSQL migrations.
- Do not add new dependencies.
- Do not use real AMAP live tests as required verification.

## 5. Interfaces and Contracts

### Inputs

- `QueryPlan`
- `CandidateCollectionResult`
- `ToolGateway`
- `fail_fast: bool`
- optional candidate limits

### Outputs

- `CandidateEnrichmentResult`
- Tool Gateway `tool_events` created by existing gateway behavior
- no `action_ledger` rows

### Public Modules

Task 010 may add:

```text
backend.app.planning.enriched_candidates
backend.app.planning.enrichment
```

### Public API

```python
class CandidateEnricher:
    def __init__(
        self,
        gateway: ToolGateway,
        max_activity_candidates: int = 3,
        max_dining_candidates: int = 3,
        max_other_candidates: int = 0,
    ) -> None:
        ...

    def enrich(
        self,
        plan: QueryPlan,
        collection: CandidateCollectionResult,
        fail_fast: bool = False,
    ) -> CandidateEnrichmentResult:
        ...
```

### Enrichment Tool Result Schema

Required fields:

```text
stage: "candidate_enrichment" | "route_matrix"
candidate_id: str | None
origin_candidate_id: str | None
destination_candidate_id: str | None
tool_name: str
provider: str
status: str
response_json: dict | None
error_json: dict | None
tool_event_id: UUID | None
```

### Enriched Candidate Schema

Required fields:

```text
candidate: Candidate
poi_detail: dict | None
opening_hours: dict | None
queue: dict | None
table_availability: dict | None
ticket_availability: dict | None
tool_results: list[EnrichmentToolResult]
failed_tool_results: list[EnrichmentToolResult]
```

### Route Matrix Entry Schema

Required fields:

```text
origin_candidate_id: str
destination_candidate_id: str
provider: str
mode: str
status: str
route_json: dict | None
distance_meters: int | None
duration_minutes: int | None
tool_event_id: UUID | None
error_json: dict | None
```

### Candidate Enrichment Result Schema

Required fields:

```text
run_id: UUID
provider_profile: str
enriched_activity_candidates: list[EnrichedCandidate]
enriched_dining_candidates: list[EnrichedCandidate]
enriched_other_candidates: list[EnrichedCandidate]
route_matrix: list[RouteMatrixEntry]
tool_results: list[EnrichmentToolResult]
failed_tool_results: list[EnrichmentToolResult]
enricher_version: str
```

### Payload Resolution Rules

For candidate enrichment:

- `poi_id`: candidate raw `poi_id`, else `candidate_id`
- `restaurant_id`: candidate raw `restaurant_id`, else `candidate_id`
- `party_size`: adults plus children from `plan.intent.participants`, minimum 1
- `quantity`: adults plus children from `plan.intent.participants`, minimum 1
- `time`: optional and may be omitted in Task 010
- candidate template tools should be skipped if their template is absent from `QueryPlan.candidate_enrichment_templates`

For route matrix:

- Mock World:
  - `origin_id`: activity `candidate_id`
  - `destination_id`: dining `candidate_id`
  - `mode`: template value or `"walking"`
- AMAP:
  - `origin`: activity `location` when it is a non-empty string
  - `destination`: dining `location` when it is a non-empty string
  - `mode`: template value or `"walking"`
- If required route inputs are missing, record a failed local result with error code `missing_template_input`.

## 6. Observability

Task 010 must not write observability records directly.

All durable tool-call observability must come from Tool Gateway:

- PostgreSQL `tool_events`
- Redis cache behavior
- gateway status/error payloads

The returned enrichment result must preserve `tool_event_id` for each gateway-backed result so future benchmark, route review, and final review services can connect feasibility evidence back to tool events.

No LangSmith runtime tracing is added in this task.

## 7. Failure Handling

- If enrichment or route templates contain a write tool, raise `CandidateEnrichmentError` before invoking any gateway call.
- If required local template inputs are missing:
  - record a failed local result with `tool_event_id=None`
  - continue when `fail_fast=False`
  - raise `CandidateEnrichmentError` when `fail_fast=True`
- If gateway returns `failed`, `blocked`, or `rate_limited`:
  - record the failed result
  - continue when `fail_fast=False`
  - raise `CandidateEnrichmentError` when `fail_fast=True`
- If a successful provider response is malformed:
  - record a failed local result
  - continue when `fail_fast=False`
  - raise when `fail_fast=True`
- Empty candidate lists are valid and should return empty enrichment lists and route matrix.
- Failed route checks must not remove enriched candidates.
- The service must never call write tools or create Action Ledger rows.

## 8. Acceptance Criteria

- [ ] `CandidateEnricher` exists and is importable.
- [ ] `CandidateEnrichmentResult`, `EnrichedCandidate`, `RouteMatrixEntry`, and `EnrichmentToolResult` are typed and importable.
- [ ] Enricher consumes `QueryPlan` and `CandidateCollectionResult`.
- [ ] Enricher does not execute `initial_tool_calls`.
- [ ] Enricher invokes tools only through `ToolGateway`.
- [ ] Enricher rejects write tools in enrichment or route templates before gateway invocation.
- [ ] Activity candidates receive detail/opening-hours/ticket checks when templates exist.
- [ ] Dining candidates receive detail/opening-hours/queue/table checks when templates exist.
- [ ] Route matrix is built for selected activity-to-dining pairs.
- [ ] Mock World route payloads use `origin_id` and `destination_id`.
- [ ] AMAP route payloads use text `origin` and `destination` when available.
- [ ] Failed gateway/local results are collected when `fail_fast=False`.
- [ ] Failed gateway/local results raise `CandidateEnrichmentError` when `fail_fast=True`.
- [ ] Integration test uses real PostgreSQL and Redis with Mock World through Tool Gateway.
- [ ] Integration test confirms no Action Ledger rows are created.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task10` branch created from `task9`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task9
git switch -c task10
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_candidate_enrichment.py -v
python -m pytest tests/integration/test_candidate_enrichment_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add candidate enrichment and route matrix
```

## 11. Notes for the Implementer

If Task 009 files are missing, stop and report the branch/base mismatch.

Keep Task 010 narrow. This task creates feasibility evidence, not final itinerary decisions. Candidate ranking, itinerary generation, LangGraph, agents, final review, and execution belong to later tasks.
