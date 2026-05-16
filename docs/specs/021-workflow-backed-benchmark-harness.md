# Spec: 021 Workflow-Backed LocalLife-Bench Harness

## 1. Goal

Refactor LocalLife-Bench so benchmark cases evaluate the official Task 019/020 product workflow instead of a parallel hand-wired service chain.

After Task 021, `BenchmarkHarness.run_case()` must call `WeekendPilotWorkflowRunner` with `auto_confirm=True`, then grade and report from persisted workflow outputs: `ToolEvent`, `ActionLedger`, selected `Plan`, `AgentRun.metadata_json`, and `WeekendPilotWorkflowResult`.

## 2. Project Context

Task 018 added the first file-based benchmark harness, but it manually orchestrates parser, planner, enrichment, review, confirmation, execution, feedback, and observability.

Task 019 added the official LangGraph workflow.

Task 020 added bounded deterministic agent adapters and agent metadata.

Task 021 should remove the benchmark bypass. Benchmarks must now measure the product route.

## 3. Requirements

- Update `backend.app.benchmark.BenchmarkHarness` to use `WeekendPilotWorkflowRunner`.
- Preserve current public constructor parameters:
  - `session`
  - `cache`
  - `rate_limiter`
  - `report_dir`
  - `trace_buffer_path`
- Before running workflow, create or reuse a benchmark user and insert fixture `memory_items` for that user.
- Call workflow with:
  - `case.user_input`
  - benchmark user external ID
  - `case.case_id`
  - `case.agent_version`
  - `case.prompt_version`
  - `case.tool_profile`
  - `case.world_profile`
  - `case.failure_profile`
  - `auto_confirm=True`
  - `selected_plan_index=0`
- Do not create `AgentRun` directly inside benchmark harness.
- Do not call planning, review, execution, feedback, or observability services directly from benchmark harness.
- Grade from persisted workflow state:
  - trajectory from `ToolEventRepository.list_for_run`
  - plan quality from `PlanRepository.get_selected_for_run`
  - execution safety from selected plan `plan_json["execution"]`
  - feedback from selected plan `plan_json["feedback"]`
  - agent coverage from workflow result or `agent_runs.metadata_json["agents"]`
  - workflow status from `WeekendPilotWorkflowResult.status`
- Add benchmark score dimensions:
  - `workflow_path`
  - `agent_coverage`
- Add optional report fields:
  - `workflow_status`
  - `workflow_node_history`
  - `agent_roles`
- Preserve existing report sanitization. Reports must not include raw `action_id`, `tool_event_id`, secrets, prompts, or debug traces.
- Existing Task 018 benchmark fixture should still pass.
- Existing Task 019/020 workflow and agent tests should still pass.

## 4. Non-goals

- Do not add new benchmark cases.
- Do not add CLI, API endpoint, or Web UI.
- Do not add recovery routing.
- Do not add LLM-backed agents.
- Do not add durable benchmark DB tables or migrations.
- Do not change LangGraph topology unless required to expose already-computed workflow result fields.
- Do not add live provider calls or credential requirements.

## 5. Public Interface Changes

Modify `BenchmarkCaseResult` additively:

```python
class BenchmarkCaseResult(BaseModel):
    ...
    workflow_status: str | None = None
    workflow_node_history: list[str] = Field(default_factory=list)
    agent_roles: list[str] = Field(default_factory=list)
```

Add benchmark graders:

```python
def grade_workflow_path(workflow_result: WeekendPilotWorkflowResult) -> BenchmarkScore:
    ...


def grade_agent_coverage(workflow_result: WeekendPilotWorkflowResult) -> BenchmarkScore:
    ...
```

Update execution and feedback graders to accept persisted metadata dicts from selected `Plan.plan_json`:

```python
def grade_execution_safety(case: BenchmarkCase, execution: Any) -> BenchmarkScore:
    ...


def grade_feedback(case: BenchmarkCase, feedback: Any) -> BenchmarkScore:
    ...
```

They should support both existing object-style inputs and dict-style persisted metadata to minimize regression risk.

## 6. Workflow-Backed Harness Behavior

`BenchmarkHarness.run_case(case)` should:

1. Validate the benchmark profile is supported.
2. Create a benchmark user with a unique external ID derived from `case.case_id`.
3. Insert `case.memory_items` for that benchmark user.
4. Instantiate `WeekendPilotWorkflowRunner` with existing session, cache, rate limiter, and trace path.
5. Run `WeekendPilotWorkflowRequest(auto_confirm=True)`.
6. If workflow returns `error`, write an error benchmark report.
7. If workflow returns `failed`, grade available persisted artifacts and mark benchmark failed.
8. Query persisted facts by `workflow_result.run_id`.
9. Run benchmark graders.
10. Write sanitized JSON report.

The benchmark harness remains responsible for:

- fixture loading
- memory setup
- benchmark scoring
- report writing

The workflow remains responsible for:

- product orchestration
- run creation
- tool calls
- plan persistence
- confirmation
- execution
- feedback
- observability
- agent metadata

## 7. Acceptance Criteria

- [ ] `BenchmarkHarness.run_case()` calls `WeekendPilotWorkflowRunner`.
- [ ] `BenchmarkHarness` no longer directly calls parser, planner, enricher, reviewer, confirmation, execution, feedback, or observability services.
- [ ] Benchmark result passes for `family_afternoon_v1`.
- [ ] Benchmark report includes workflow status, node history, and bounded agent roles.
- [ ] Report confirms all five agent roles are present.
- [ ] `agent_runs.metadata_json["agents"]` exists for benchmark runs.
- [ ] `agent_runs.metadata_json["observability"]` exists for completed benchmark runs.
- [ ] Tool events retain the workflow trace ID.
- [ ] Existing report sanitizer still removes forbidden fields.
- [ ] Existing Task 019 workflow tests pass.
- [ ] Existing Task 020 agent tests pass.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task21` branch created from `task20`.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 8. Verification Commands

```bash
git switch task20
git switch -c task21
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_agents.py tests/integration/test_workflow_agents_gateway.py -v
python -m pytest
docker compose config
git diff --check
git status --short
```

## 9. Expected Commit

```text
feat: align benchmark harness with workflow
```

## 10. Notes for the Implementer

Task 021 is a path-alignment task. Do not expand benchmark coverage or build user-facing surfaces here. The important outcome is that LocalLife-Bench evaluates the same workflow that product entrypoints will call.
