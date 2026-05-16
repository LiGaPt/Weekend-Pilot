# Plan: 021 Workflow-Backed LocalLife-Bench Harness

## 1. Spec Reference

Spec file:

```text
docs/specs/021-workflow-backed-benchmark-harness.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task20`.
- Current Task 020 commit is `6af4dbc feat: add bounded agent contracts`.
- `backend.app.workflow` exposes `WeekendPilotWorkflowRunner`, `WeekendPilotWorkflowDependencies`, and `WeekendPilotWorkflowRequest`.
- `WeekendPilotWorkflowResult` includes `agent_results`.
- `backend.app.agents` persists bounded agent metadata under `agent_runs.metadata_json["agents"]`.
- `backend.app.benchmark.harness.BenchmarkHarness` still manually orchestrates the full deterministic chain.
- Task 021 should remove that benchmark-side orchestration and use the workflow runner.

## 3. Files to Modify

- `backend/app/benchmark/harness.py` - replace manual orchestration with workflow runner and persisted artifact grading.
- `backend/app/benchmark/graders.py` - add workflow/agent graders and support dict execution/feedback metadata.
- `backend/app/benchmark/schemas.py` - add workflow and agent report fields.
- `tests/test_benchmark_harness.py` - add grader/report coverage for new fields.
- `tests/integration/test_benchmark_harness_gateway.py` - assert benchmark runs through workflow and agents.
- `README.md` - update LocalLife-Bench wording to mention workflow-backed harness.
- `docs/specs/021-workflow-backed-benchmark-harness.md` - Task 021 spec.
- `docs/plans/021-workflow-backed-benchmark-harness-plan.md` - Task 021 plan.

No new production package is required.

## 4. Implementation Steps

1. Confirm clean baseline.

```bash
git status --short --branch
git log --oneline -5
```

2. Create `task21` from `task20`.

```bash
git switch task20
git switch -c task21
```

3. Update `BenchmarkCaseResult` in `backend/app/benchmark/schemas.py`.

Add:

```python
workflow_status: str | None = None
workflow_node_history: list[str] = Field(default_factory=list)
agent_roles: list[str] = Field(default_factory=list)
```

This is additive and should not break existing reports.

4. Update `backend/app/benchmark/graders.py`.

Add:

```python
REQUIRED_WORKFLOW_NODES = (
    "initialize_run",
    "parse_intent",
    "load_memory",
    "build_query_plan",
    "collect_candidates",
    "enrich_candidates",
    "generate_itinerary",
    "final_review",
    "persist_and_select_plan",
    "wait_confirmation",
    "execute",
    "write_feedback",
    "record_observability",
)

REQUIRED_AGENT_ROLES = (
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
)
```

Implement:

```python
def grade_workflow_path(workflow_result) -> BenchmarkScore:
    ...


def grade_agent_coverage(workflow_result) -> BenchmarkScore:
    ...
```

Rules:

- Workflow path passes when `workflow_result.status == "completed"` and all required node names are present in `workflow_result.node_history`.
- Agent coverage passes when all five required roles are present in `workflow_result.agent_results`.

5. Make execution grader support persisted dict metadata.

Current grader expects object-style `ExecutionWorkflowResult`. Keep that path working.

Add dict support:

- `execution["status"]`
- `execution["action_results"]`
- action result `tool_name`

Pass criteria stay unchanged:

- status equals `case.expected.expected_execution_status`
- action count meets `case.expected.min_action_count`
- all write tools are registered `WRITE_TOOLS`

6. Make feedback grader support persisted dict metadata.

Current grader expects object-style `ExecutionFeedbackResult`. Keep that path working.

Add dict support:

- `feedback["status"]`
- `feedback["headline"]`
- `feedback["message"]`
- `feedback["next_steps"]`

Pass criteria stay unchanged:

- status equals `case.expected.expected_feedback_status`
- feedback text does not expose raw IDs or debug wording

7. Refactor imports in `backend/app/benchmark/harness.py`.

Remove direct orchestration imports:

- `HumanConfirmationService`
- `DeterministicExecutionWorkflow`
- `DeterministicFeedbackWriter`
- `LocalTraceBuffer`
- `ObservabilityRecorder`
- planning service classes
- `ReviewedPlanPersistenceService`
- `build_mock_world_registry`
- `FinalReviewGate`
- `ToolGateway`

Add workflow imports:

```python
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowRunner,
)
```

Keep repository imports needed for:

- users
- memory
- runs
- plans
- tool events
- action ledger

8. Refactor `BenchmarkHarness._run_case`.

Behavior:

- Validate supported profile.
- Create benchmark user.
- Insert fixture memory items for that user.
- Build workflow runner with current session/cache/rate limiter/trace path.
- Run workflow with `auto_confirm=True`.
- If workflow has no `run_id`, produce error result and report.
- Load persisted artifacts:
  - run via `AgentRunRepository.get_by_id`
  - tool events via `ToolEventRepository.list_for_run`
  - selected plan via `PlanRepository.get_selected_for_run`
  - action count via existing `_action_count`
- Extract:
  - `execution = selected_plan.plan_json.get("execution")`
  - `feedback = selected_plan.plan_json.get("feedback")`
  - `workflow_status = workflow_result.status`
  - `workflow_node_history = workflow_result.node_history`
  - `agent_roles = sorted({agent.role for agent in workflow_result.agent_results})`
- Score with:
  - `grade_workflow_path`
  - `grade_agent_coverage`
  - `grade_trajectory`
  - `grade_plan_quality`
  - `grade_execution_safety`
  - `grade_feedback`
- Write report.

9. Preserve benchmark metadata.

Because workflow creates the `AgentRun`, benchmark metadata should be added after workflow returns:

```python
metadata = dict(run.metadata_json or {})
metadata["benchmark"] = {
    "case_id": case.case_id,
    "title": case.title,
    "benchmark_harness_version": self.harness_version,
    "harness_version": self.harness_version,
    "metadata": case.metadata,
    "workflow_backed": True,
}
repositories.runs.update_metadata_json(run.run_id, metadata)
```

Do not overwrite existing `workflow`, `agents`, or `observability` metadata.

10. Handle workflow error and failed statuses.

If `workflow_result.status == "error"`:

- return `BenchmarkCaseResult(status="error")`
- include `workflow_status`
- include node history and agent roles if present
- include failure reason from `workflow_result.error_json`

If `workflow_result.status == "failed"`:

- attempt persisted-artifact grading when `run_id` exists
- benchmark status should be `failed` unless scores unexpectedly all pass

11. Update report writer only if necessary.

`write_case_report` should already sanitize recursively. Add unit assertions for new fields rather than changing implementation unless tests show a gap.

12. Update `tests/test_benchmark_harness.py`.

Add tests:

- `grade_workflow_path` passes for completed workflow-like object with all nodes.
- `grade_workflow_path` fails when a required node is missing.
- `grade_agent_coverage` passes for all five roles.
- `grade_agent_coverage` fails when one role is missing.
- `grade_execution_safety` passes with persisted execution dict.
- `grade_feedback` passes with persisted feedback dict.
- report writer includes `workflow_status`, `workflow_node_history`, and `agent_roles` while still excluding forbidden keys.

13. Update `tests/integration/test_benchmark_harness_gateway.py`.

Keep existing happy-path assertions and add:

```python
assert result.workflow_status == "completed"
assert "initialize_run" in result.workflow_node_history
assert "record_observability" in result.workflow_node_history
assert set(result.agent_roles) == {
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
}
```

Update run metadata assertions:

```python
assert run.metadata_json["benchmark"]["workflow_backed"] is True
assert "workflow" in run.metadata_json
assert "agents" in run.metadata_json
assert "observability" in run.metadata_json
```

Add report payload assertions for the same fields.

14. Add an assertion that benchmark harness no longer creates a parallel orchestration path.

Do this through behavioral assertions, not brittle source-code inspection:

- benchmark run metadata has `workflow.source == "langgraph-workflow"` or equivalent existing workflow marker.
- benchmark report has workflow node history.
- benchmark run metadata has bounded agents.

15. Update README.

Revise LocalLife-Bench section:

````markdown
## LocalLife-Bench Harness

The benchmark harness runs file-based cases through the official LangGraph workflow and bounded deterministic agent adapters, then writes local JSON reports. It does not require LangSmith credentials or live provider access.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
```
````

16. Run focused verification.

```bash
python -m pytest tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
```

17. Run workflow and agent regression verification.

```bash
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_agents.py tests/integration/test_workflow_agents_gateway.py -v
```

18. Run full verification.

```bash
python -m pytest
docker compose config
git diff --check
git status --short
```

19. Commit and push.

```bash
git add README.md backend/app/benchmark tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py docs/specs/021-workflow-backed-benchmark-harness.md docs/plans/021-workflow-backed-benchmark-harness-plan.md
git commit -m "feat: align benchmark harness with workflow"
git push origin task21
```

## 5. Follow-up Task Order

After Task 021:

1. Task 022: CLI demo runner.
2. Task 023: recovery routing v0.
3. Task 024: LocalLife-Bench case expansion.
4. Task 025: first LLM-backed bounded agent behind existing contracts.

Do not pull these follow-up scopes into Task 021.
