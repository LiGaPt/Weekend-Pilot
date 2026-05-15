# Plan: 019 LangGraph Workflow Skeleton

## 1. Spec Reference

Spec file:

```text
docs/specs/019-langgraph-workflow-skeleton.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task18`.
- Current Task 018 commit is `737d24f feat: add locallife bench harness`.
- `backend.app.benchmark` exists and can run the full deterministic Mock World path.
- `backend.app.observability` exists and can build trace contexts and write local trace summaries.
- The project does not yet depend on `langgraph`.
- There is no `backend.app.workflow` package yet.
- The official product route is currently duplicated in tests and the benchmark harness; Task 019 should add the shared workflow layer without refactoring those callers yet.

## 3. Files to Add

- `backend/app/workflow/__init__.py` - public exports.
- `backend/app/workflow/errors.py` - `WorkflowError`.
- `backend/app/workflow/schemas.py` - request, state, status, and result schemas.
- `backend/app/workflow/dependencies.py` - typed runtime dependency container.
- `backend/app/workflow/graph.py` - LangGraph topology and conditional routing.
- `backend/app/workflow/nodes.py` - node handlers that call existing deterministic services.
- `backend/app/workflow/runner.py` - high-level workflow runner and result conversion.
- `tests/test_langgraph_workflow.py` - unit tests for graph and result behavior.
- `tests/integration/test_langgraph_workflow_gateway.py` - full Mock World workflow integration tests.
- `docs/specs/019-langgraph-workflow-skeleton.md` - Task 019 spec.
- `docs/plans/019-langgraph-workflow-skeleton-plan.md` - Task 019 plan.

## 4. Files to Modify

- `pyproject.toml` - add `langgraph>=1.0,<2.0`.
- `README.md` - document focused LangGraph workflow verification commands.

Do not modify Task 018 benchmark code in this task except if a test exposes a narrow compatibility defect that blocks the workflow package.

## 5. Implementation Steps

1. Confirm clean baseline.

```bash
git status --short --branch
git log --oneline -5
```

2. Create `task19` from `task18`.

```bash
git switch task18
git switch -c task19
```

3. Add LangGraph dependency to `pyproject.toml`.

Add:

```toml
"langgraph>=1.0,<2.0",
```

Run:

```bash
python -m pip install -e ".[dev]"
```

4. Add `backend/app/workflow/errors.py`.

Define:

```python
class WorkflowError(RuntimeError):
    """Raised when the WeekendPilot workflow cannot continue."""
```

5. Add schemas in `backend/app/workflow/schemas.py`.

Include:

- `WorkflowStatus`
- `WeekendPilotWorkflowRequest`
- `WeekendPilotWorkflowResult`
- `WeekendPilotWorkflowState`

Use Pydantic models for public request/result. Use a typed state representation that works cleanly with LangGraph. The state must include node history and structured intermediate values, but only expose the public result through `WeekendPilotWorkflowResult`.

6. Add `backend/app/workflow/dependencies.py`.

Define:

```python
class WeekendPilotWorkflowDependencies(BaseModel):
    session: Session
    cache: JsonRedisCache
    rate_limiter: FixedWindowRateLimiter
    trace_buffer_path: Path | str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

Do not create DB sessions inside the workflow package. Callers own the session lifecycle.

7. Add graph topology in `backend/app/workflow/graph.py`.

Create:

```python
def build_weekend_pilot_graph(nodes: WeekendPilotWorkflowNodes):
    ...
```

The graph route must be:

```text
START
-> initialize_run
-> parse_intent
-> load_memory
-> build_query_plan
-> collect_candidates
-> enrich_candidates
-> generate_itinerary
-> final_review
-> persist_and_select_plan
-> wait_confirmation
```

Conditional edge after `wait_confirmation`:

```text
awaiting_confirmation -> END
confirmed -> execute
```

Then:

```text
execute -> write_feedback -> record_observability -> END
```

8. Add node handlers in `backend/app/workflow/nodes.py`.

Create `WeekendPilotWorkflowNodes` with dependencies injected in the constructor.

Node responsibilities:

- `initialize_run`: create or load user by external ID, create `AgentRun`, create gateway, build observability recorder, build trace context.
- `parse_intent`: call `DeterministicIntentParser`.
- `load_memory`: call `MemoryItemRepository.list_active_for_user` and store active memories in state.
- `build_query_plan`: call `DeterministicQueryPlanner`.
- `collect_candidates`: call `QueryPlanExecutor.execute_initial_calls` with trace ID.
- `enrich_candidates`: call `CandidateEnricher.enrich` with trace ID.
- `generate_itinerary`: call `DeterministicItineraryGenerator`.
- `final_review`: call `FinalReviewGate`.
- `persist_and_select_plan`: call `ReviewedPlanPersistenceService`, select `selected_plan_index`, fail when no safe plans exist.
- `wait_confirmation`: if `auto_confirm` is false, set workflow status `awaiting_confirmation`; otherwise call `HumanConfirmationService.confirm_plan`.
- `execute`: call `DeterministicExecutionWorkflow.execute_confirmed_plan` with trace ID.
- `write_feedback`: call `DeterministicFeedbackWriter`.
- `record_observability`: call `ObservabilityRecorder.record_run_summary`.

Every node should append its name to `node_history`.

9. Add runner in `backend/app/workflow/runner.py`.

`WeekendPilotWorkflowRunner.run()` should:

- validate supported profile combination before graph invocation
- build nodes and compiled graph
- invoke the graph with initial state from request
- convert final state to `WeekendPilotWorkflowResult`
- catch unexpected exceptions and return status `error` with `error_json`

Unsupported profile result:

```python
WeekendPilotWorkflowResult(
    run_id=None,
    trace_id=None,
    status="error",
    error_json={
        "error_type": "unsupported_profile",
        "message": "...",
    },
)
```

10. Add exports in `backend/app/workflow/__init__.py`.

Export:

- `WeekendPilotWorkflowDependencies`
- `WeekendPilotWorkflowRequest`
- `WeekendPilotWorkflowResult`
- `WeekendPilotWorkflowRunner`
- `WorkflowError`

11. Add unit tests in `tests/test_langgraph_workflow.py`.

Required coverage:

- graph compiles
- graph exposes the expected node names
- conditional route returns `awaiting_confirmation` when state status is `awaiting_confirmation`
- conditional route returns `execute` when auto-confirmed state is ready
- unsupported profile result is typed and does not raise
- public package exports import cleanly

12. Add integration tests in `tests/integration/test_langgraph_workflow_gateway.py`.

Reuse the integration setup style from:

```text
tests/integration/test_benchmark_harness_gateway.py
tests/integration/test_observability_gateway.py
```

Fixtures:

- `SessionLocal`
- Redis runtime with unique key prefix
- test trace path under `var/test-traces`

Test `auto_confirm=False`:

```text
runner.run(request with auto_confirm=False)
-> status == "awaiting_confirmation"
-> run_id and trace_id exist
-> selected_plan_id exists
-> tool_event_count > 0
-> action_count == 0
-> no ActionLedger rows for run
-> node_history includes wait_confirmation
-> node_history does not include execute
```

Test `auto_confirm=True`:

```text
runner.run(request with auto_confirm=True)
-> status == "completed"
-> execution_status == "succeeded"
-> feedback_status == "completed"
-> observability_status is set
-> action_count > 0
-> ToolEvent rows for run all carry trace ID
-> AgentRun metadata contains observability trace ID
```

13. Update README.

Add:

````markdown
## LangGraph Workflow Skeleton

The workflow package provides the shared product route for the deterministic Mock World flow. It pauses before write-tool execution unless `auto_confirm=True` is supplied by a test or demo caller.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
```
````

14. Run focused verification.

```bash
python -m pytest tests/test_langgraph_workflow.py -v
python -m pytest tests/integration/test_langgraph_workflow_gateway.py -v
```

15. Run regression verification for the existing benchmark path.

```bash
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
```

16. Run full verification.

```bash
python -m pytest
docker compose config
git diff --check
git status --short
```

17. Commit and push.

```bash
git add pyproject.toml README.md backend/app/workflow tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py docs/specs/019-langgraph-workflow-skeleton.md docs/plans/019-langgraph-workflow-skeleton-plan.md
git commit -m "feat: add langgraph workflow skeleton"
git push origin task19
```

## 6. Follow-up Task Order

After Task 019:

1. Task 020: bounded agent contracts and deterministic adapters.
2. Task 021: benchmark harness calls the official workflow.
3. Task 022: CLI demo runner.
4. Task 023: recovery routing v0.
5. Task 024: LocalLife-Bench case expansion.

Do not pull those follow-up scopes into Task 019.
