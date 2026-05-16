# Plan: 022 Web Demo API Surface

## 1. Spec Reference

Spec file:

```text
docs/specs/022-web-demo-api-surface.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task21`.
- Current Task 021 commit is `27645a9 feat: align benchmark harness with workflow`.
- `docs/PROJECT_BLUEPRINT.md` may already contain an uncommitted user-requested Web-first update. Do not revert it.
- FastAPI currently exposes only `/health`.
- `WeekendPilotWorkflowRunner` supports the initial planning path and can stop at `awaiting_confirmation` when `auto_confirm=False`.
- The workflow does not yet expose a resume API for continuing an awaiting-confirmation run.
- Existing services can continue the run after Web confirmation:
  - `HumanConfirmationService`
  - `DeterministicExecutionWorkflow`
  - `DeterministicFeedbackWriter`
  - `ObservabilityRecorder`
- The first Web demo should remain fully Mock World.

## 3. Files to Add

- `backend/app/demo/__init__.py` - package exports for demo service and schemas if useful.
- `backend/app/demo/schemas.py` - Web demo request and sanitized response schemas.
- `backend/app/demo/service.py` - start/status/confirm/decline orchestration and summary building.
- `backend/app/api/demo.py` - FastAPI router for `/demo/runs`.
- `tests/test_demo_api.py` - focused API schema, app wiring, CORS, and sanitization tests.
- `tests/integration/test_demo_api_gateway.py` - integration tests with PostgreSQL, Redis, workflow, confirmation, execution, feedback, and action ledger.
- `docs/specs/022-web-demo-api-surface.md` - Task 022 spec.
- `docs/plans/022-web-demo-api-surface-plan.md` - Task 022 plan.

## 4. Files to Modify

- `backend/app/main.py` - include the demo router and CORS middleware.
- `backend/app/core/config.py` - add demo CORS origins setting.
- `README.md` - document focused Web demo API setup and smoke commands.

Do not modify `docs/PROJECT_BLUEPRINT.md` in Task 022.

## 5. Implementation Steps

1. Confirm baseline and branch.

```bash
git status --short --branch
git log --oneline -5
git switch task21
git switch -c task22
```

If `docs/PROJECT_BLUEPRINT.md` is already modified, keep it intact and do not stage it for the Task 022 commit unless the user explicitly requests that separately.

2. Add CORS settings in `backend/app/core/config.py`.

Add:

```python
demo_cors_origins: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
```

Keep the setting simple. Do not add environment parsing beyond what Pydantic settings already supports.

3. Update `backend/app/main.py`.

Add `CORSMiddleware` and include the new demo router:

```python
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.demo import router as demo_router
```

Inside `create_app()`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.demo_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(demo_router)
```

4. Create `backend/app/demo/schemas.py`.

Define request models:

```python
class DemoStartRunRequest(BaseModel):
    user_input: str = Field(min_length=1)
    external_user_id: str | None = None
    display_name: str | None = None
    case_id: str | None = "web-demo"
    selected_plan_index: int = Field(default=0, ge=0)


class DemoConfirmRunRequest(BaseModel):
    plan_id: UUID | None = None
    confirmed_by: str = "web-demo-user"


class DemoDeclineRunRequest(BaseModel):
    plan_id: UUID | None = None
    declined_by: str = "web-demo-user"
    reason: str | None = None
```

Define response models:

- `DemoCandidateSummary`
- `DemoTimelineItem`
- `DemoRouteSummary`
- `DemoFeasibilitySummary`
- `DemoProposedActionSummary`
- `DemoConfirmationSummary`
- `DemoExecutionSummary`
- `DemoFeedbackSummary`
- `DemoPlanPreview`
- `DemoRunSummary`

Keep fields minimal and Web-oriented. Do not expose `tool_event_id`, `action_id`, `event_id`, or `idempotency_key`.

5. Create `backend/app/demo/service.py`.

Add a `DemoWorkflowService` initialized with:

```python
session: Session
cache: JsonRedisCache
rate_limiter: FixedWindowRateLimiter
trace_buffer_path: str | Path | None
```

Give it methods:

```python
start_run(request: DemoStartRunRequest) -> DemoRunSummary
get_run(run_id: UUID) -> DemoRunSummary
confirm_run(run_id: UUID, request: DemoConfirmRunRequest) -> DemoRunSummary
decline_run(run_id: UUID, request: DemoDeclineRunRequest) -> DemoRunSummary
```

6. Implement `start_run`.

Behavior:

- Instantiate `WeekendPilotWorkflowRunner` with `WeekendPilotWorkflowDependencies`.
- Call `WeekendPilotWorkflowRequest` with:
  - `user_input=request.user_input`
  - `external_user_id=request.external_user_id`
  - `display_name=request.display_name`
  - `case_id=request.case_id`
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `auto_confirm=False`
  - `selected_plan_index=request.selected_plan_index`
- If the workflow returns no `run_id`, raise an HTTP-safe service error.
- Persist demo metadata:

```python
metadata["demo"] = {
    "api_version": "web_demo_api_v1",
    "trace_id": result.trace_id,
    "initial_status": result.status,
    "initial_node_history": result.node_history,
    "continuation_history": [],
}
```

- Commit the session.
- Return `build_summary(result.run_id)`.

7. Implement `build_summary`.

Load:

- `AgentRunRepository.get_by_id`
- `PlanRepository.list_for_run`
- `PlanRepository.get_selected_for_run`
- `ToolEventRepository.list_for_run`
- `ActionLedger` count through SQLAlchemy or repository access

Extract `trace_id` from:

1. `run.metadata_json["demo"]["trace_id"]`
2. `run.metadata_json["observability"]["trace_id"]`
3. `None`

Extract `agent_roles` from `run.metadata_json["agents"]["results"]`.

For each plan, parse `plan.plan_json`:

- `draft.title`
- `draft.summary`
- `draft.activity`
- `draft.dining`
- `draft.timeline`
- `draft.route`
- `draft.feasibility`
- `draft.proposed_actions`
- `confirmation`
- `execution`
- `feedback`

Sanitize every nested response to remove forbidden keys.

8. Implement plan selection helper.

Add `_resolve_plan(run_id, requested_plan_id)`:

- If `requested_plan_id` is provided, load it and verify `plan.run_id == run_id`.
- If omitted, use `PlanRepository.get_selected_for_run(run_id)`.
- If no selected plan exists, raise a conflict error.
- If requested plan is not selected and is still safe/reviewed, select it through `PlanRepository.select_for_run`.
- Reject plans from other runs.

9. Implement `confirm_run`.

Behavior:

- Load the run or return `404`.
- Resolve the plan.
- If the run is already in a terminal successful state and selected plan already has execution and feedback metadata, return summary without re-executing.
- Confirm the plan via `HumanConfirmationService.confirm_plan`.
- Build `ToolGateway` with `build_mock_world_registry()`, `ToolEventRepository`, `ActionLedgerRepository`, cache, and rate limiter.
- Execute with `DeterministicExecutionWorkflow.execute_confirmed_plan(..., langsmith_trace_id=trace_id)`.
- Write feedback with `DeterministicFeedbackWriter.write_execution_feedback`.
- Record observability using `ObservabilityRecorder`.

For observability continuation, construct `RunTraceContext` using the stored trace ID and run metadata, then call `record_run_summary`. Do not call `build_context()` here because it creates a new trace ID.

Update demo continuation metadata:

```python
continuation_history += [
    "confirm_plan",
    "execute",
    "write_feedback",
    "record_observability",
]
```

Commit and return summary.

10. Implement `decline_run`.

Behavior:

- Load run.
- Resolve selected/requested plan.
- Reject already confirmed/executed plans with conflict.
- Call `HumanConfirmationService.decline_plan`.
- Update run status to `declined`.
- Append `"decline_plan"` to demo continuation metadata.
- Commit and return summary.

11. Add service-level error mapping.

Use small custom exceptions or direct `HTTPException` mapping in router:

- `404` for missing run or plan.
- `409` for invalid state transitions.
- `500` for sanitized unexpected demo continuation failures.

Roll back the session on mutation failures before raising.

12. Create `backend/app/api/demo.py`.

Dependencies:

```python
db: Session = Depends(get_db)
redis_client = Depends(get_redis_client)
settings: Settings = Depends(get_settings)
```

Build runtime services per request:

```python
keys = RedisKeyBuilder.from_settings()
cache = JsonRedisCache(redis_client, keys)
rate_limiter = FixedWindowRateLimiter(redis_client, keys)
service = DemoWorkflowService(
    session=db,
    cache=cache,
    rate_limiter=rate_limiter,
    trace_buffer_path=settings.local_trace_buffer_path,
)
```

Router endpoints:

```python
@router.post("/demo/runs", response_model=DemoRunSummary)
def start_demo_run(...)

@router.get("/demo/runs/{run_id}", response_model=DemoRunSummary)
def get_demo_run(...)

@router.post("/demo/runs/{run_id}/confirm", response_model=DemoRunSummary)
def confirm_demo_run(...)

@router.post("/demo/runs/{run_id}/decline", response_model=DemoRunSummary)
def decline_demo_run(...)
```

13. Add `tests/test_demo_api.py`.

Cover:

- `create_app()` includes demo routes.
- CORS preflight allows `http://localhost:5173`.
- Start request rejects empty `user_input`.
- Response sanitizer removes `action_id`, `tool_event_id`, `event_id`, `idempotency_key`, `api_key`, `token`, `secret`, `authorization`, `prompt`, and `debug_trace`.
- `DemoRunSummary` can serialize a minimal valid payload.

14. Add `tests/integration/test_demo_api_gateway.py`.

Use existing integration fixture style from workflow tests:

- `SessionLocal`
- unique Redis key prefix
- `get_redis_client().ping()`
- trace path under `var/test-traces`
- `TestClient(create_app())`
- dependency overrides if needed for DB or Redis isolation

Test happy path:

```text
POST /demo/runs
-> status awaiting_confirmation
-> action_count == 0
-> plans not empty
GET /demo/runs/{run_id}
-> same run and selected plan
POST /demo/runs/{run_id}/confirm
-> feedback_status == completed
-> action_count > 0
-> execution summary present
```

Assert in database:

- no actions after start
- actions after confirm
- all post-confirmation write tool events for the run have `langsmith_trace_id == initial_trace_id`

Test idempotency:

- Call confirm twice.
- Assert `ActionLedger` count does not increase on the second call.

Test decline:

- Start a second run.
- Decline it.
- Assert selected plan has declined confirmation metadata.
- Assert action count remains zero.

Test not found/conflict:

- unknown run returns `404`.
- confirming a declined run returns `409`.

15. Update README.

Add a `Web Demo API` section:

```markdown
## Web Demo API

The Web demo API starts the official workflow, pauses before write tools, and continues execution only after explicit confirmation.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
```

Start a run:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.\"}"
```
```

Include status and confirmation examples. Keep commands short.

16. Run focused verification.

```bash
python -m pytest tests/test_demo_api.py -v
python -m pytest tests/integration/test_demo_api_gateway.py -v
```

17. Run regression verification.

```bash
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
```

18. Run full verification.

```bash
python -m pytest
docker compose config
git diff --check
git status --short
```

19. Commit only Task 022 files.

```bash
git add backend/app/demo backend/app/api/demo.py backend/app/main.py backend/app/core/config.py README.md tests/test_demo_api.py tests/integration/test_demo_api_gateway.py docs/specs/022-web-demo-api-surface.md docs/plans/022-web-demo-api-surface-plan.md
git commit -m "feat: add web demo API surface"
git push origin task22
```

If `docs/PROJECT_BLUEPRINT.md` is still modified from the earlier blueprint update, do not include it in this commit unless the user explicitly asks to stage that blueprint change too.

## 6. Testing Plan

- Unit tests:
  - schema validation for demo request models
  - route registration and CORS preflight
  - sanitizer behavior for forbidden internal/sensitive keys
  - summary serialization
- Integration tests:
  - start run pauses at confirmation
  - status endpoint reads persisted state
  - confirm endpoint executes deterministic write tools and writes feedback
  - duplicate confirm is idempotent
  - decline endpoint creates no action ledger rows
  - missing and invalid state errors map to HTTP-safe responses
- Regression tests:
  - existing LangGraph workflow tests
  - existing workflow-backed benchmark harness tests

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py -v
python -m pytest tests/integration/test_demo_api_gateway.py -v
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest
docker compose config
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add web demo API surface
```

Expected commands:

```bash
git status --short
git add backend/app/demo backend/app/api/demo.py backend/app/main.py backend/app/core/config.py README.md tests/test_demo_api.py tests/integration/test_demo_api_gateway.py docs/specs/022-web-demo-api-surface.md docs/plans/022-web-demo-api-surface-plan.md
git commit -m "feat: add web demo API surface"
git push origin task22
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not build frontend UI.
- Do not add CLI.
- Do not refactor LangGraph into the V1 optimized DAG.
- Do not add recovery loops.
- Do not add LLM calls.
- Do not add real map or local-life provider calls.
- Do not add new dependencies unless FastAPI CORS support unexpectedly requires a missing package.
- Do not include unrelated blueprint edits in the Task 022 implementation commit.
- Do not commit generated caches, virtual environments, trace files, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] API starts the official workflow instead of duplicating planning orchestration.
- [ ] Start endpoint pauses before write tools.
- [ ] Confirm endpoint is deterministic and idempotent.
- [ ] Decline endpoint does not execute write tools.
- [ ] Responses are Web-safe and sanitized.
- [ ] Original trace ID is preserved through post-confirmation write tool events.
- [ ] CORS supports the local Vite frontend.
- [ ] Tests cover happy path, idempotency, decline, and error states.
- [ ] Existing workflow and benchmark regressions pass.
- [ ] Required verification commands passed.
- [ ] Git status was clean after commit, except unrelated pre-existing changes intentionally left out.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

The implementer should report back:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Whether `docs/PROJECT_BLUEPRINT.md` remained uncommitted from the earlier blueprint update
- Any known limitation in confirmation continuation or observability reuse
