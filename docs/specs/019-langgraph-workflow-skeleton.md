# Spec: 019 LangGraph Workflow Skeleton

## 1. Goal

Add a LangGraph-based workflow skeleton that becomes the single product orchestration path for WeekendPilot's deterministic Mock World flow.

The workflow should reuse the deterministic services built in Tasks 008-018 and provide one official route for future CLI, API, benchmark, and bounded-agent layers. It must support stopping at the human confirmation boundary by default, and it may auto-confirm only when explicitly requested by test or demo-like callers.

## 2. Project Context

The project blueprint says the normal route should be controlled by a LangGraph state machine, not by free-form LLM routing.

Earlier tasks intentionally built deterministic service nodes first:

- intent parsing and query planning
- query execution and candidate collection
- candidate enrichment and route matrix
- itinerary draft generation
- final review
- reviewed plan persistence and selection
- human confirmation boundary
- deterministic execution workflow
- feedback writer
- observability recorder
- LocalLife-Bench harness

Task 019 should now add the missing orchestration layer. It should not introduce bounded LLM agents yet; those should be a later task after the graph contract is stable.

## 3. Requirements

- Add `langgraph>=1.0,<2.0` to `pyproject.toml`.
- Add `backend.app.workflow`.
- Build a LangGraph `StateGraph` route:

```text
initialize_run
-> parse_intent
-> load_memory
-> build_query_plan
-> collect_candidates
-> enrich_candidates
-> generate_itinerary
-> final_review
-> persist_and_select_plan
-> wait_confirmation
-> execute
-> write_feedback
-> record_observability
```

- `wait_confirmation` must conditionally route:
  - `auto_confirm=False`: stop with status `awaiting_confirmation`
  - `auto_confirm=True`: call `HumanConfirmationService`, then continue to execution
- Preserve the confirmation boundary: no write tools or Action Ledger rows before confirmation.
- Support only:
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
- Reuse existing deterministic services. Do not duplicate planning, review, execution, feedback, or observability logic.
- Propagate `langsmith_trace_id` through read and write tool calls.
- Record local observability summary when the workflow reaches completion.
- Return a typed workflow result containing:
  - `run_id`
  - `trace_id`
  - `status`
  - `selected_plan_id`
  - `node_history`
  - `tool_event_count`
  - `action_count`
  - `execution_status`
  - `feedback_status`
  - `observability_status`
  - `error_json`
- Keep LangSmith optional and disabled by default.
- Add focused unit and integration tests.
- Existing Task 018 benchmark harness tests must keep passing unchanged.

## 4. Non-goals

- Do not add bounded multi-agent architecture yet.
- Do not add Supervisor, Discovery, Dining, Itinerary Planner, or Validator agents.
- Do not add LLM calls, prompts, model configuration, or agent provider packages.
- Do not add CLI, API endpoints, or Web UI.
- Do not refactor the benchmark harness to call this workflow yet.
- Do not add durable LangGraph checkpointing or LangGraph Platform server support.
- Do not add recovery routing, retry budgets, fallback loops, or failure injection.
- Do not add database migrations unless a blocking schema defect is found.
- Do not require LangSmith credentials or network access for default tests.

## 5. Interfaces and Contracts

### Public Modules

```text
backend.app.workflow.__init__
backend.app.workflow.errors
backend.app.workflow.schemas
backend.app.workflow.dependencies
backend.app.workflow.graph
backend.app.workflow.nodes
backend.app.workflow.runner
```

### Request

```python
class WeekendPilotWorkflowRequest(BaseModel):
    user_input: str
    external_user_id: str | None = None
    display_name: str | None = None
    case_id: str | None = None
    agent_version: str = "agent-v1"
    prompt_version: str = "prompt-v1"
    tool_profile: Literal["mock_world"] = "mock_world"
    world_profile: Literal["family_afternoon"] = "family_afternoon"
    failure_profile: str | None = None
    auto_confirm: bool = False
    selected_plan_index: int = 0
```

### Result

```python
WorkflowStatus = Literal[
    "awaiting_confirmation",
    "completed",
    "failed",
    "error",
]


class WeekendPilotWorkflowResult(BaseModel):
    run_id: UUID | None
    trace_id: str | None
    status: WorkflowStatus
    selected_plan_id: UUID | None = None
    node_history: list[str] = Field(default_factory=list)
    tool_event_count: int = 0
    action_count: int = 0
    execution_status: str | None = None
    feedback_status: str | None = None
    observability_status: str | None = None
    error_json: dict[str, Any] | None = None
```

### State

The workflow state should be typed and internal to `backend.app.workflow`.

It should hold only structured values needed between nodes, including:

- request fields
- `run_id`
- `user_id`
- `trace_id`
- active memories
- parsed intent
- query plan
- candidate collection
- enrichment result
- itinerary drafts
- final review result
- persisted plans
- selected plan ID
- execution result
- feedback result
- observability result
- node history
- error JSON

### Dependencies

```python
class WeekendPilotWorkflowDependencies(BaseModel):
    session: Session
    cache: JsonRedisCache
    rate_limiter: FixedWindowRateLimiter
    trace_buffer_path: Path | str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

### Runner

```python
class WeekendPilotWorkflowRunner:
    def __init__(self, dependencies: WeekendPilotWorkflowDependencies) -> None:
        ...

    def run(self, request: WeekendPilotWorkflowRequest) -> WeekendPilotWorkflowResult:
        ...
```

## 6. Workflow Behavior

### `auto_confirm=False`

The workflow should:

- initialize run and trace context
- execute all read-only planning and review nodes
- persist reviewed plans
- select the requested plan index
- stop at `wait_confirmation`
- return status `awaiting_confirmation`
- not create Action Ledger rows
- not call write tools
- not write execution feedback

### `auto_confirm=True`

The workflow should:

- run the same planning path
- confirm the selected plan with source `langgraph-workflow`
- execute confirmed actions
- write feedback
- record observability
- return status `completed` when execution and feedback succeed

### Error Handling

- Unsupported profiles should return status `error` with structured `error_json`.
- Node exceptions should be captured into status `error`.
- Final review blocked or no persisted plans should return status `failed`.
- Observability failure must not crash the workflow; capture it in `observability_status` and metadata.
- LangSmith disabled or missing API key must not fail the workflow.

## 7. Acceptance Criteria

- [ ] `backend.app.workflow` is importable.
- [ ] `langgraph>=1.0,<2.0` is installed as a project dependency.
- [ ] Workflow graph compiles.
- [ ] Graph route includes all required nodes in order.
- [ ] `auto_confirm=False` returns `awaiting_confirmation`.
- [ ] `auto_confirm=False` creates no Action Ledger rows.
- [ ] `auto_confirm=True` completes through execution, feedback, and observability.
- [ ] Tool events created by workflow have the trace ID.
- [ ] Existing deterministic services are reused rather than duplicated.
- [ ] Existing Task 018 benchmark harness tests pass unchanged.
- [ ] Default tests require no live LangSmith credentials or provider network calls.
- [ ] README documents focused workflow verification.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task19` branch created from `task18`.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 8. Verification Commands

```bash
git switch task18
git switch -c task19
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_langgraph_workflow.py -v
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest
docker compose config
git diff --check
git status --short
```

## 9. Expected Commit

```text
feat: add langgraph workflow skeleton
```

## 10. Notes for the Implementer

Task 019 is the orchestration correction point. Keep it focused on the LangGraph product route and confirmation boundary. Bounded agents, benchmark refactoring, CLI, API, Web UI, and recovery loops should come later.
