# Spec: 009 Query Plan Execution and Candidate Collection

## 1. Goal

Add a deterministic query-plan execution service that consumes the `QueryPlan` produced by Task 008, invokes only its initial read tool calls through Tool Gateway, and collects normalized activity and dining candidates for later enrichment, merging, routing, and itinerary generation.

After this task, WeekendPilot should have a small bridge from "structured query plan" to "candidate search results" while keeping write tools, route evaluation, availability checking, candidate scoring, LangGraph, agents, and itinerary generation out of scope.

## 2. Project Context

Task 005 added Tool Gateway. Task 006 added AMAP read provider. Task 007 added Mock World provider. Task 008 added deterministic intent parsing and query planning.

Task 009 is the next deterministic service-layer step in the blueprint:

```text
parse_intent
-> load_memory
-> build_query_plan
-> discover_candidates
-> enrich_candidates
```

This task covers only the first part of deterministic candidate discovery: execute `QueryPlan.initial_tool_calls` and organize the returned POI candidates. It does not execute enrichment templates, route templates, or any write tools.

## 3. Requirements

- Add query-plan execution and candidate collection under `backend.app.planning`.
- Execute only `QueryPlan.initial_tool_calls`.
- Invoke tools only through existing `ToolGateway`.
- Reject any planned initial write tool before execution.
- Support successful `search_poi` responses from both `mock_world` and `amap` providers.
- Support successful `check_weather` responses from both `mock_world` and `amap` providers.
- Normalize POI-like search results into typed `Candidate` objects.
- Separate candidates into:
  - `activity_candidates`
  - `dining_candidates`
  - `other_candidates`
- Preserve raw provider payloads for later deterministic review.
- Preserve `tool_event_id`, `provider`, `tool_name`, and `source_call_index` for each result where available.
- Collect weather result separately.
- Collect failed tool results without raising when `fail_fast=False`.
- Raise `QueryExecutionError` on the first failed tool result when `fail_fast=True`.
- Do not execute `candidate_enrichment_templates`.
- Do not execute `route_templates`.
- Do not call providers directly.
- Do not call any write tool.
- Add unit tests using fake gateway objects.
- Add integration tests using real PostgreSQL and Redis with Mock World through Tool Gateway.
- README should include a focused test command for the new planning execution service.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement Memory Retriever.
- Do not implement Candidate Merger.
- Do not implement candidate scoring or ranking beyond preserving provider order.
- Do not implement Availability Checker.
- Do not implement Route & Time Calculator.
- Do not execute enrichment templates.
- Do not execute route templates.
- Do not generate itineraries or proposed action lists.
- Do not implement LangGraph.
- Do not implement agents or LLM calls.
- Do not add FastAPI endpoints.
- Do not add PostgreSQL migrations.
- Do not modify provider behavior unless a Task 009 test exposes a clear contract bug that must be reported first.

## 5. Interfaces and Contracts

### Inputs

- `QueryPlan`
- `run_id: UUID`
- `ToolGateway`
- `fail_fast: bool`

### Outputs

- `CandidateCollectionResult`
- Tool Gateway `tool_events` created by existing gateway behavior
- Redis cache usage through existing gateway behavior

### Public Modules

Task 009 may add these modules:

```text
backend.app.planning.execution
backend.app.planning.candidates
```

### Public API

```python
class QueryPlanExecutor:
    def __init__(self, gateway: ToolGateway) -> None:
        ...

    def execute_initial_calls(
        self,
        plan: QueryPlan,
        run_id: UUID,
        fail_fast: bool = False,
    ) -> CandidateCollectionResult:
        ...
```

### Candidate Schema

Required fields:

```text
candidate_id: str
name: str
category: str
provider: str
source: str | None
address: str | None
location: dict[str, Any] | str | None
tags: list[str]
raw_payload: dict[str, Any]
source_call_index: int
tool_event_id: UUID | None
```

### CandidateCollectionResult Schema

Required fields:

```text
run_id: UUID
provider_profile: str
activity_candidates: list[Candidate]
dining_candidates: list[Candidate]
other_candidates: list[Candidate]
weather: dict[str, Any] | None
tool_results: list[InitialToolExecutionResult]
failed_tool_results: list[InitialToolExecutionResult]
executor_version: str
```

### InitialToolExecutionResult Schema

Required fields:

```text
source_call_index: int
tool_name: str
provider: str
status: str
response_json: dict[str, Any] | None
error_json: dict[str, Any] | None
tool_event_id: UUID | None
```

## 6. Observability

This service must not write observability records directly.

All durable tool-call observability must come from Tool Gateway:

- PostgreSQL `tool_events`
- Redis cache behavior
- gateway status/error payloads

The result objects should preserve `tool_event_id` so later workflow, benchmark, and review services can connect candidates back to gateway events.

## 7. Failure Handling

- If `plan.initial_tool_calls` contains a canonical write tool, raise `QueryExecutionError` before invoking any tool.
- If a gateway call returns failed, blocked, or rate-limited:
  - include it in `failed_tool_results`
  - continue when `fail_fast=False`
  - raise `QueryExecutionError` when `fail_fast=True`
- If a `search_poi` response is malformed, record a failed tool result or raise depending on `fail_fast`.
- Empty `search_poi` results are valid and should produce empty candidate lists.
- Unknown candidate category should go to `other_candidates`.
- Missing optional candidate fields should not fail normalization.
- This service must never execute write tools, enrichment templates, or route templates.

## 8. Acceptance Criteria

- [ ] `QueryPlanExecutor` exists and is importable.
- [ ] Candidate/result schemas are typed and importable.
- [ ] Executor only processes `QueryPlan.initial_tool_calls`.
- [ ] Executor invokes tools through `ToolGateway`.
- [ ] Executor rejects planned write tools before any gateway invocation.
- [ ] Mock World `search_poi` results normalize into activity and dining candidates.
- [ ] AMAP-shaped `search_poi` results normalize into candidates.
- [ ] Weather result is captured separately.
- [ ] Failed gateway results are collected when `fail_fast=False`.
- [ ] Failed gateway results raise `QueryExecutionError` when `fail_fast=True`.
- [ ] Integration test uses real PostgreSQL and Redis with Mock World through Tool Gateway.
- [ ] No enrichment templates, route templates, providers, DB repositories, Redis clients, or LLMs are called directly by the executor.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task9` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task8
git switch -c task9
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add query plan execution and candidate collection
```

## 11. Notes for the Implementer

If Task 008 planning schemas or Task 007 Mock World provider files are missing, stop and report the branch/base mismatch.

Keep Task 009 narrow. Do not turn candidate collection into itinerary planning, scoring, or agentic discovery.
