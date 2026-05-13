# Plan: 009 Query Plan Execution and Candidate Collection

## 1. Spec Reference

Spec file:

```text
docs/specs/009-query-plan-execution-candidate-collection.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task8`.
- Current Task 008 commit is `643ae96 feat: add deterministic intent and query planning`.
- `backend/app/planning/schemas.py` defines `QueryPlan`, `PlannedToolCall`, and related planning models.
- `backend/app/tool_gateway` exposes `ToolGateway` and `ToolGatewayRequest`.
- `backend/app/tool_gateway/registry.py` exposes canonical `WRITE_TOOLS`.
- `backend/app/providers/mock_world` and its gateway integration tests exist.
- No query-plan execution or candidate collection service exists yet.

## 3. Files to Add

- `backend/app/planning/candidates.py` - candidate and execution result schemas.
- `backend/app/planning/execution.py` - `QueryPlanExecutor`.
- `tests/test_query_plan_execution.py` - unit tests with fake gateway.
- `tests/integration/test_query_plan_execution_gateway.py` - real PostgreSQL/Redis + Mock World gateway integration test.

## 4. Files to Modify

- `backend/app/planning/__init__.py` - export new schemas and executor.
- `README.md` - add focused planning execution test command.
- `docs/specs/009-query-plan-execution-candidate-collection.md` - save Task 009 spec.
- `docs/plans/009-query-plan-execution-candidate-collection-plan.md` - save Task 009 plan.

No dependency or database migration changes are expected.

## 5. Implementation Steps

1. Create branch:

```bash
git switch task8
git switch -c task9
```

2. Confirm baseline:

```bash
git status --short --branch
rg --files backend/app/planning backend/app/tool_gateway backend/app/providers tests docs/specs docs/plans
```

Expected:

- Branch is `task9`.
- Task 008 planning files exist.
- Task 007 Mock World provider files exist.
- `backend/app/planning/execution.py` does not exist yet.

3. Add `QueryExecutionError`.

Modify `backend/app/planning/errors.py`:

```python
class QueryExecutionError(ValueError):
    pass
```

4. Add `backend/app/planning/candidates.py`.

Use Pydantic `BaseModel`.

Required models:

```python
class Candidate(BaseModel):
    candidate_id: str
    name: str
    category: str
    provider: str
    source: str | None = None
    address: str | None = None
    location: dict[str, Any] | str | None = None
    tags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    source_call_index: int
    tool_event_id: UUID | None = None


class InitialToolExecutionResult(BaseModel):
    source_call_index: int
    tool_name: str
    provider: str
    status: str
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    tool_event_id: UUID | None = None


class CandidateCollectionResult(BaseModel):
    run_id: UUID
    provider_profile: str
    activity_candidates: list[Candidate] = Field(default_factory=list)
    dining_candidates: list[Candidate] = Field(default_factory=list)
    other_candidates: list[Candidate] = Field(default_factory=list)
    weather: dict[str, Any] | None = None
    tool_results: list[InitialToolExecutionResult] = Field(default_factory=list)
    failed_tool_results: list[InitialToolExecutionResult] = Field(default_factory=list)
    executor_version: str
```

5. Add `backend/app/planning/execution.py`.

Implement:

```python
class QueryPlanExecutor:
    executor_version = "query_plan_executor_v1"

    def __init__(self, gateway: ToolGateway) -> None:
        self._gateway = gateway

    def execute_initial_calls(
        self,
        plan: QueryPlan,
        run_id: UUID,
        fail_fast: bool = False,
    ) -> CandidateCollectionResult:
        ...
```

6. Implement preflight write-tool rejection.

Before invoking the gateway:

- inspect every `plan.initial_tool_calls`
- if `call.tool_name in WRITE_TOOLS`, raise `QueryExecutionError`
- ensure no gateway call is made in that case

7. Implement gateway invocation loop.

For each `PlannedToolCall`, call:

```python
gateway.invoke(
    ToolGatewayRequest(
        run_id=run_id,
        tool_name=call.tool_name,
        payload=call.payload,
        provider=call.provider,
        user_confirmed=False,
    )
)
```

Do not set `target_id` or `idempotency_key`.

8. Implement result classification.

For every gateway result:

- append `InitialToolExecutionResult` to `tool_results`
- if status is not `succeeded` or `cached`, append to `failed_tool_results`
- if `fail_fast=True`, raise `QueryExecutionError`

Treat statuses `succeeded` and `cached` as usable.

9. Implement candidate normalization.

For `search_poi` responses:

- read `response_json["results"]`
- if missing or not a list, handle as malformed according to `fail_fast`
- for each item:
  - `candidate_id`: prefer `poi_id`, then `id`
  - `name`: prefer `name`, fallback to candidate ID
  - `category`: prefer `category`, fallback to `"unknown"`
  - `provider`: from planned call provider
  - `source`: prefer item `source`
  - `address`: optional
  - `location`: optional
  - `tags`: item tags if list, otherwise `[]`
  - `raw_payload`: full item
  - `source_call_index`: loop index
  - `tool_event_id`: gateway result id

Place candidates:

- `category == "activity"` -> `activity_candidates`
- `category == "dining"` -> `dining_candidates`
- otherwise -> `other_candidates`

10. Implement weather capture.

For `check_weather` responses:

- if `response_json` contains `weather`, set `CandidateCollectionResult.weather`
- if multiple weather calls are present, last successful one wins and add a note only if a `notes` field is added later; for Task 009 no notes field is required

11. Add unit tests in `tests/test_query_plan_execution.py`.

Use a fake gateway object with an `invoke(request)` method.

Cover:

- executor calls gateway once per initial planned call
- search results become activity/dining candidates
- AMAP-shaped candidate with `source="amap"` and no tags normalizes safely
- weather response is captured
- failed gateway result is collected when `fail_fast=False`
- failed gateway result raises when `fail_fast=True`
- initial write tool raises before invoking fake gateway
- executor does not inspect or execute enrichment/route templates

12. Add integration test in `tests/integration/test_query_plan_execution_gateway.py`.

Use:

- `SessionLocal`
- existing `UserRepository`, `AgentRunRepository`, `ToolEventRepository`, `ActionLedgerRepository`
- `build_mock_world_registry()`
- `JsonRedisCache`, `FixedWindowRateLimiter`, and `RedisKeyBuilder`
- `DeterministicIntentParser`
- `DeterministicQueryPlanner`
- `QueryPlanExecutor`

Scenario:

1. Parse the MVP English family request.
2. Build a mock_world query plan.
3. Execute initial calls through Tool Gateway.
4. Assert:
   - activity candidates are non-empty
   - dining candidates are non-empty
   - weather is captured
   - all tool results are succeeded or cached
   - PostgreSQL `tool_events` count equals initial calls
   - no `action_ledger` rows are created

13. Update `backend/app/planning/__init__.py`.

Export:

```python
Candidate
CandidateCollectionResult
InitialToolExecutionResult
QueryExecutionError
QueryPlanExecutor
```

14. Update README.

Add focused command:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_query_plan_execution.py tests/integration/test_query_plan_execution_gateway.py -v
```

Do not claim full itinerary planning exists.

15. Run focused tests:

```bash
python -m pytest tests/test_query_plan_execution.py -v
```

16. Run integration test:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_query_plan_execution_gateway.py -v
```

17. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

18. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - fake gateway invocation count
  - candidate normalization for Mock World and AMAP-shaped responses
  - activity/dining/other candidate classification
  - weather capture
  - failed result collection
  - fail-fast error path
  - write-tool preflight rejection
  - enrichment/route templates are not executed
- Integration tests:
  - intent parser + query planner + query executor + Tool Gateway + Mock World
  - real PostgreSQL `tool_events`
  - real Redis runtime services
  - no Action Ledger rows from read-only execution
- Smoke:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add query plan execution and candidate collection
```

Expected branch:

```text
task9
```

Expected commands:

```bash
git status --short
git add README.md backend/app/planning tests/test_query_plan_execution.py tests/integration/test_query_plan_execution_gateway.py docs/specs/009-query-plan-execution-candidate-collection.md docs/plans/009-query-plan-execution-candidate-collection-plan.md
git status --short
git commit -m "feat: add query plan execution and candidate collection"
git push -u origin task9
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement Memory Retriever.
- Do not implement Candidate Merger.
- Do not implement candidate scoring.
- Do not execute enrichment templates.
- Do not execute route templates.
- Do not implement Availability Checker.
- Do not implement Route & Time Calculator.
- Do not generate itineraries.
- Do not implement LangGraph, agents, prompts, or LLM calls.
- Do not add API endpoints.
- Do not add database migrations.
- Do not commit `.env`, API keys, tokens, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task9`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] Executor only executes initial read calls.
- [ ] Executor rejects write tools before gateway invocation.
- [ ] Executor uses Tool Gateway and does not call providers directly.
- [ ] Candidate normalization works for Mock World and AMAP-shaped results.
- [ ] Weather is captured separately.
- [ ] Failed tool results are handled according to `fail_fast`.
- [ ] Integration test creates tool events and no action ledger rows.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add query plan execution and candidate collection`.
- [ ] Push to `origin/task9` succeeds.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused query execution test result.
- Integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 009 intentionally stops at initial candidate collection.
- Candidate merger, route/time calculation, availability checking, and itinerary generation are follow-up tasks.
- Mock World is the primary integration provider for this task because it is deterministic and supports all MVP tool types.
