# Plan: 010 Candidate Enrichment and Route Matrix

## 1. Spec Reference

Spec file:

```text
docs/specs/010-candidate-enrichment-route-matrix.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task9`.
- Current Task 009 commit is `1ac3a0d feat: add query plan execution and candidate collection`.
- `backend/app/planning/candidates.py` defines `Candidate`, `CandidateCollectionResult`, and `InitialToolExecutionResult`.
- `backend/app/planning/execution.py` defines `QueryPlanExecutor`.
- `backend/app/planning/query_planner.py` defines candidate enrichment templates and route templates.
- `backend/app/tool_gateway` exposes `ToolGateway`, `ToolGatewayRequest`, and `ToolGatewayResult`.
- `backend/app/tool_gateway/registry.py` exposes `WRITE_TOOLS`.
- Mock World supports required read tools through Tool Gateway.
- No candidate enrichment or route matrix service exists yet.

## 3. Files to Add

- `backend/app/planning/enriched_candidates.py` - Pydantic schemas for enriched candidates, route matrix entries, and enrichment results.
- `backend/app/planning/enrichment.py` - deterministic `CandidateEnricher` service.
- `tests/test_candidate_enrichment.py` - unit tests with fake gateway.
- `tests/integration/test_candidate_enrichment_gateway.py` - PostgreSQL/Redis + Mock World gateway integration test.
- `docs/specs/010-candidate-enrichment-route-matrix.md` - Task 010 spec.
- `docs/plans/010-candidate-enrichment-route-matrix-plan.md` - Task 010 plan.

## 4. Files to Modify

- `backend/app/planning/__init__.py` - export Task 010 schemas and service.
- `backend/app/planning/errors.py` - add `CandidateEnrichmentError`.
- `backend/app/planning/query_planner.py` - adjust AMAP route template to use `origin` and `destination` if needed for the existing `AMapProvider`.
- `README.md` - add focused candidate enrichment test command.

No dependency, Docker Compose, Alembic, or database schema changes are expected.

## 5. Implementation Steps

1. Create branch:

```bash
git switch task9
git switch -c task10
```

2. Confirm baseline:

```bash
git status --short --branch
rg --files backend/app/planning backend/app/tool_gateway backend/app/providers tests docs/specs docs/plans
```

Expected:

- Branch is `task10`.
- Task 009 files exist.
- `backend/app/planning/enrichment.py` does not exist yet.
- Working tree is clean before implementation.

3. Add error type.

Modify `backend/app/planning/errors.py`:

```python
class CandidateEnrichmentError(ValueError):
    pass
```

4. Add `backend/app/planning/enriched_candidates.py`.

Create Pydantic models:

```python
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.planning.candidates import Candidate


EnrichmentStage = Literal["candidate_enrichment", "route_matrix"]


class EnrichmentToolResult(BaseModel):
    stage: EnrichmentStage
    candidate_id: str | None = None
    origin_candidate_id: str | None = None
    destination_candidate_id: str | None = None
    tool_name: str
    provider: str
    status: str
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    tool_event_id: UUID | None = None


class EnrichedCandidate(BaseModel):
    candidate: Candidate
    poi_detail: dict[str, Any] | None = None
    opening_hours: dict[str, Any] | None = None
    queue: dict[str, Any] | None = None
    table_availability: dict[str, Any] | None = None
    ticket_availability: dict[str, Any] | None = None
    tool_results: list[EnrichmentToolResult] = Field(default_factory=list)
    failed_tool_results: list[EnrichmentToolResult] = Field(default_factory=list)


class RouteMatrixEntry(BaseModel):
    origin_candidate_id: str
    destination_candidate_id: str
    provider: str
    mode: str = "walking"
    status: str
    route_json: dict[str, Any] | None = None
    distance_meters: int | None = None
    duration_minutes: int | None = None
    tool_event_id: UUID | None = None
    error_json: dict[str, Any] | None = None


class CandidateEnrichmentResult(BaseModel):
    run_id: UUID
    provider_profile: str
    enriched_activity_candidates: list[EnrichedCandidate] = Field(default_factory=list)
    enriched_dining_candidates: list[EnrichedCandidate] = Field(default_factory=list)
    enriched_other_candidates: list[EnrichedCandidate] = Field(default_factory=list)
    route_matrix: list[RouteMatrixEntry] = Field(default_factory=list)
    tool_results: list[EnrichmentToolResult] = Field(default_factory=list)
    failed_tool_results: list[EnrichmentToolResult] = Field(default_factory=list)
    enricher_version: str
```

5. Update AMAP route template if needed.

Modify `DeterministicQueryPlanner._build_route_templates()` so AMAP uses the existing AMAP provider contract:

```python
if provider_profile == "amap":
    return [
        ToolCallTemplate(
            tool_name="check_route",
            provider=provider_profile,
            required_inputs=["origin", "destination"],
            payload_template={
                "origin": "{origin}",
                "destination": "{destination}",
                "mode": "walking",
            },
        )
    ]
```

Keep Mock World unchanged:

```python
ToolCallTemplate(
    tool_name="check_route",
    provider=provider_profile,
    required_inputs=["origin_id", "destination_id"],
    payload_template={
        "origin_id": "{origin_id}",
        "destination_id": "{destination_id}",
        "mode": "walking",
    },
)
```

6. Add `backend/app/planning/enrichment.py`.

Implement:

```python
class CandidateEnricher:
    enricher_version = "candidate_enricher_v1"
    _USABLE_STATUSES = {"succeeded", "cached"}

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

Implementation responsibilities:

- preflight reject write tools in `candidate_enrichment_templates` and `route_templates`
- select and dedupe bounded candidates by category
- enrich candidates by applicable tool name
- build activity-to-dining route matrix
- record all gateway-backed results
- record local failures for missing inputs or malformed responses
- respect `fail_fast`

7. Implement candidate selection.

Rules:

- Preserve original provider order.
- Deduplicate by `candidate_id`.
- Use constructor limits:
  - activities: default 3
  - dining: default 3
  - other: default 0
- Do not mutate original `CandidateCollectionResult`.

8. Implement template lookup.

Create dictionaries from plan templates:

```python
enrichment_templates_by_tool = {
    template.tool_name: template
    for template in plan.candidate_enrichment_templates
}
route_template = first template in plan.route_templates where tool_name == "check_route"
```

Only execute a candidate tool if its template exists.

9. Implement write-tool preflight.

Before any gateway call:

- inspect all enrichment and route templates
- if any `template.tool_name in WRITE_TOOLS`, raise `CandidateEnrichmentError`
- verify fake gateway invocation count stays zero in unit test

10. Implement candidate enrichment applicability.

For each selected activity candidate, run available templates in this order:

```text
get_poi_detail
check_opening_hours
check_ticket_availability
```

For each selected dining candidate, run available templates in this order:

```text
get_poi_detail
check_opening_hours
check_queue
check_table_availability
```

For each selected other candidate, run available templates in this order:

```text
get_poi_detail
check_opening_hours
```

11. Implement candidate payload resolution.

For candidate tools:

- `poi_id`: candidate raw `poi_id`, else `candidate.candidate_id`
- `restaurant_id`: candidate raw `restaurant_id`, else `candidate.candidate_id`
- `party_size`: adults + children count from `plan.intent.participants`, minimum 1
- `quantity`: adults + children count from `plan.intent.participants`, minimum 1
- omit optional time fields in Task 010 unless already present in template as a literal

Resolve simple template placeholders:

```text
"{poi_id}"
"{restaurant_id}"
"{party_size}"
"{quantity}"
```

If a required input cannot be resolved, record local failure:

```json
{
  "code": "missing_template_input",
  "message": "Required template input could not be resolved.",
  "missing_input": "..."
}
```

12. Implement gateway invocation for candidate enrichment.

Call only:

```python
ToolGatewayRequest(
    run_id=collection.run_id,
    tool_name=template.tool_name,
    provider=template.provider,
    payload=resolved_payload,
    user_confirmed=False,
)
```

Do not set `target_id` or `idempotency_key`.

13. Implement response attachment.

Attach successful payloads to the enriched candidate:

- `get_poi_detail`: `response_json["poi"]` -> `poi_detail`
- `check_opening_hours`: `response_json["opening_hours"]` -> `opening_hours`
- `check_queue`: `response_json["queue"]` -> `queue`
- `check_table_availability`: `response_json["table_availability"]` -> `table_availability`
- `check_ticket_availability`: `response_json["ticket_availability"]` -> `ticket_availability`

If expected keys are missing from a successful response, record a local malformed response failure.

14. Implement route matrix.

For every selected activity and selected dining pair:

- if no `check_route` template exists, return empty route matrix
- build one gateway request per pair
- append one `RouteMatrixEntry` per attempted pair
- failed gateway/local results should still create route entries with failed status and error JSON

15. Implement route payload resolution.

For Mock World-style templates:

```text
origin_id -> activity.candidate_id
destination_id -> dining.candidate_id
mode -> template literal or "walking"
```

For AMAP-style templates:

```text
origin -> activity.location if it is a non-empty string
destination -> dining.location if it is a non-empty string
mode -> template literal or "walking"
```

If AMAP candidate locations are missing or non-string, record `missing_template_input`.

16. Normalize route response.

For successful route responses:

- expected shape: `response_json["route"]`
- `distance_meters`: integer if present
- `duration_minutes`:
  - use route `duration_minutes` if present
  - else if route `duration_seconds` is present, convert with ceiling division
  - else `None`
- preserve full route object in `route_json`

17. Add unit tests in `tests/test_candidate_enrichment.py`.

Use a fake gateway with an `invoke(request)` method.

Cover:

- write tool in enrichment template raises before gateway invocation
- enricher does not execute `initial_tool_calls`
- activity candidate gets detail, opening hours, and ticket availability
- dining candidate gets detail, opening hours, queue, and table availability
- other candidate is skipped by default when `max_other_candidates=0`
- route matrix executes activity-to-dining pairs
- Mock World route payload uses `origin_id` and `destination_id`
- AMAP route payload uses `origin` and `destination` from string locations
- missing AMAP location records local failure when `fail_fast=False`
- failed gateway result is collected when `fail_fast=False`
- failed gateway result raises `CandidateEnrichmentError` when `fail_fast=True`
- duplicate candidates are deduped by `candidate_id`
- candidate limits are respected

18. Add integration test in `tests/integration/test_candidate_enrichment_gateway.py`.

Use the existing integration setup pattern from `tests/integration/test_query_plan_execution_gateway.py`:

- `SessionLocal`
- `UserRepository`
- `AgentRunRepository`
- `ToolEventRepository`
- `ActionLedgerRepository`
- `JsonRedisCache`
- `FixedWindowRateLimiter`
- `RedisKeyBuilder`
- `build_mock_world_registry()`
- `ToolGateway`
- `DeterministicIntentParser`
- `DeterministicQueryPlanner`
- `QueryPlanExecutor`
- `CandidateEnricher`

Scenario:

1. Create user and run.
2. Parse the MVP family afternoon request.
3. Build a Mock World query plan.
4. Execute initial calls with `QueryPlanExecutor`.
5. Enrich candidates with `CandidateEnricher`.
6. Assert:
   - enriched activity candidates are non-empty
   - enriched dining candidates are non-empty
   - at least one activity has `poi_detail` and `opening_hours`
   - at least one dining candidate has `queue` or `table_availability`
   - route matrix is non-empty
   - at least one route matrix entry has status `succeeded` or `cached`
   - failed route entries, if any, are represented instead of raising
   - PostgreSQL `tool_events` count is at least the number of initial gateway calls plus enrichment gateway calls
   - PostgreSQL `action_ledger` count for the run is 0

19. Update `backend/app/planning/__init__.py`.

Export:

```python
CandidateEnricher
CandidateEnrichmentError
CandidateEnrichmentResult
EnrichedCandidate
EnrichmentToolResult
RouteMatrixEntry
```

20. Update README.

Add focused command:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_candidate_enrichment.py tests/integration/test_candidate_enrichment_gateway.py -v
```

Do not claim itinerary generation exists.

21. Run focused unit tests:

```bash
python -m pytest tests/test_candidate_enrichment.py -v
```

22. Run focused integration tests:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_candidate_enrichment_gateway.py -v
```

23. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

24. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - fake gateway invocation order and payloads
  - category-specific enrichment tool applicability
  - route matrix pair generation
  - Mock World and AMAP payload resolution
  - local missing-input failures
  - gateway failure collection
  - fail-fast behavior
  - write-tool preflight rejection
  - candidate dedupe and limits
- Integration tests:
  - intent parser + query planner + query executor + candidate enricher + Tool Gateway + Mock World
  - real PostgreSQL `tool_events`
  - real Redis cache/rate-limit runtime services
  - no Action Ledger rows from read-only enrichment
- Smoke:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_candidate_enrichment.py -v
python -m pytest tests/integration/test_candidate_enrichment_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add candidate enrichment and route matrix
```

Expected branch:

```text
task10
```

Expected commands:

```bash
git switch task9
git switch -c task10
git status --short
git add README.md backend/app/planning tests/test_candidate_enrichment.py tests/integration/test_candidate_enrichment_gateway.py docs/specs/010-candidate-enrichment-route-matrix.md docs/plans/010-candidate-enrichment-route-matrix-plan.md
git status --short
git commit -m "feat: add candidate enrichment and route matrix"
git push -u origin task10
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement Candidate Merger scoring or ranking.
- Do not generate itineraries.
- Do not create proposed action lists.
- Do not implement LangGraph.
- Do not implement agents, prompts, or LLM calls.
- Do not implement Final Review Gate.
- Do not implement Execution Workflow.
- Do not execute write tools.
- Do not create Action Ledger rows.
- Do not add API endpoints.
- Do not add migrations.
- Do not add dependencies.
- Do not commit `.env`, API keys, tokens, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task10`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] Enricher consumes Task 009 candidate collection result.
- [ ] Enricher does not execute initial tool calls.
- [ ] Enricher rejects write tools before gateway invocation.
- [ ] Enricher uses Tool Gateway and does not call providers directly.
- [ ] Activity/dining enrichment tool applicability is correct.
- [ ] Route matrix uses activity-to-dining pairs only.
- [ ] Mock World route payloads are correct.
- [ ] AMAP route payload contract matches `AMapProvider`.
- [ ] Failed tool/local results are handled according to `fail_fast`.
- [ ] Integration test creates tool events and no action ledger rows.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add candidate enrichment and route matrix`.
- [ ] Push to `origin/task10` succeeds.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused candidate enrichment unit test result.
- Focused integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 010 starts from `task9`.
- Mock World is the required deterministic integration provider.
- AMAP route support is limited to payload-shape correctness and unit tests; no live AMAP test is required.
- Candidate scoring, merging, itinerary generation, and final review are follow-up tasks.
