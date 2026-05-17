# Plan: 027 Recovery Routing v0

## 1. Spec Reference

Spec file:

```text
docs/specs/027-recovery-routing-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `task26`.
- Latest completed commit is `8559be7 refactor: align workflow state with v1 dag`.
- Task 026 introduced the V1 workflow state and DAG alignment.
- The Task 027 spec is expected at `docs/specs/027-recovery-routing-v0.md`.
- Current workflow code lives in `backend/app/workflow/`.
- `semantic_validator` already stores `RecoveryDecision`, but graph routing does not consume it.
- The happy path must keep the Task 026 V1 required node list valid for benchmark grading.
- Working tree currently has unrelated untracked `docs/TASK_WORKFLOW_PROMPTS.md`; do not stage it.
- PostgreSQL and Redis are required for workflow integration tests.

## 3. Files to Add

- `docs/plans/027-recovery-routing-v0-plan.md` - this implementation plan.
- `backend/app/workflow/recovery.py` - workflow-only recovery routing models and deterministic route mapping helpers.

## 4. Files to Modify

- `backend/app/workflow/state.py` - add recovery attempt models and state fields.
- `backend/app/workflow/__init__.py` - export recovery models if tests or consumers need them.
- `backend/app/workflow/graph.py` - add recovery conditional routing after `semantic_validator`.
- `backend/app/workflow/nodes.py` - add `apply_recovery`, persist recovery metadata, and update workflow version.
- `backend/app/workflow/runner.py` - initialize recovery defaults in workflow state.
- `backend/app/agents/deterministic.py` - update blocked recovery reason text and keep decisions compatible with Task 027.
- `tests/test_langgraph_workflow.py` - add graph and route unit tests for recovery paths.
- `tests/test_agents.py` - add blocked validator/recovery decision tests.
- `tests/integration/test_langgraph_workflow_gateway.py` - add recovery stop and successful retry-loop integration coverage.
- `tests/integration/test_workflow_agents_gateway.py` - assert recovery metadata is sanitized and compatible with agent metadata.
- `tests/test_demo_api.py` and `tests/integration/test_demo_api_gateway.py` - update only if recovery metadata affects existing API summary assertions.

## 5. Implementation Steps

1. Confirm preconditions:
   - Run `git status --short --branch`.
   - Confirm `docs/specs/027-recovery-routing-v0.md` exists.
   - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` remains unrelated and unstaged.

2. Create a dedicated branch if needed:
   - Recommended branch: `task27`.

3. Add `backend/app/workflow/recovery.py`.
   - Define `RecoveryRouteTarget` literal values:
     `final_review`, `generate_queries`, `execute_searches`, `logical_planner_agent`, `failed`, `error`.
   - Define workflow-only `RecoveryAttempt` Pydantic model with:
     `attempt_index`, `source_node`, `recovery_action`, `route_to`, `error_type`, `reason`, `retry_budget_before`, `retry_budget_after`, `status`.
   - Define constants mapping:
     `retry -> execute_searches`,
     `expand_search_radius -> generate_queries`,
     `replace_candidate -> logical_planner_agent`.
   - Add a pure helper such as `resolve_recovery_route(decision, attempt_count, max_attempts)` returning route target plus attempt metadata.
   - Enforce:
     missing decision -> `missing_recovery_decision`,
     unsupported route -> `unsupported_recovery_route`,
     `retry_budget <= 0` -> `recovery_budget_exhausted`,
     attempts exhausted -> `recovery_attempt_limit_exceeded`,
     `ask_user` -> `recovery_requires_user_input`,
     `stop_safely` -> `recovery_stopped`.

4. Update `backend/app/workflow/state.py`.
   - Import `RecoveryAttempt`.
   - Add state fields:
     `recovery_attempts: list[RecoveryAttempt]`,
     `max_recovery_attempts: int`,
     `active_recovery_route: str | None`.
   - Keep existing `RecoveryDecision` state field.
   - Do not change `WorkflowStatus` unless tests prove it is required.

5. Update `backend/app/workflow/runner.py`.
   - Initialize:
     `recovery_attempts=[]`,
     `max_recovery_attempts=1`,
     `active_recovery_route=None`.
   - Keep `WeekendPilotWorkflowResult` unchanged.

6. Update `backend/app/workflow/graph.py`.
   - Add node `apply_recovery`.
   - Replace direct edge `semantic_validator -> final_review` with conditional route:
     passed or `recovery_action="none"` -> `final_review`,
     failed recovery decision -> `apply_recovery`.
   - Add conditional route from `apply_recovery` to:
     `generate_queries`,
     `execute_searches`,
     `logical_planner_agent`,
     `END` for failed/error stop cases.
   - Do not add `apply_recovery` to `V1_WORKFLOW_NODE_NAMES`; benchmark should still require the Task 026 happy-path nodes as a subset.

7. Update `backend/app/workflow/nodes.py`.
   - Set `workflow_version = "recovery_routing_v0"`.
   - Add `apply_recovery(state)`.
   - In `apply_recovery`, call `resolve_recovery_route`.
   - Append one `RecoveryAttempt` to state on every failed decision.
   - Set `active_recovery_route` for routed attempts.
   - For stop cases, update run status to `failed` and set structured `error_json`.
   - Persist recovery metadata under `agent_runs.metadata_json["workflow"]["recovery"]`.
   - Preserve existing workflow metadata keys such as `source`, `auto_confirm`, and `selected_plan_index`.
   - Do not call Tool Gateway or write tools inside `apply_recovery`.

8. Add helper methods in `nodes.py`.
   - `_persist_recovery_metadata(run_id, attempts, max_attempts)`.
   - `_recovery_error_json(error_type, decision, attempt)`.
   - Reuse `_jsonable` and keep metadata sanitized.
   - Ensure metadata omits raw `action_id`, `tool_event_id`, prompts, secrets, tokens, and tracebacks.

9. Update `backend/app/agents/deterministic.py`.
   - Keep safe reviews returning `verdict="passed"`, `recovery_action="none"`, `retry_budget=0`.
   - Keep blocked reviews returning `stop_safely` by default.
   - Update blocked reason text so it no longer says Task 020 does not execute recovery routes.
   - Do not add LLM behavior.

10. Add unit tests in `tests/test_langgraph_workflow.py`.
    - Update `_StubNodes` to include `apply_recovery`.
    - Test passed recovery decisions route to `final_review` without `apply_recovery`.
    - Test `retry` with budget 1 routes back to `execute_searches`.
    - Test `expand_search_radius` routes back to `generate_queries`.
    - Test `replace_candidate` routes back to `logical_planner_agent`.
    - Test `ask_user`, `stop_safely`, budget exhausted, unsupported route, and attempt limit stop at `apply_recovery`.
    - Assert no recovery route can jump to `saga_execution_engine`.

11. Add unit tests in `tests/test_agents.py`.
    - Add a blocked review fixture with no safe draft.
    - Assert `DeterministicValidatorRecoveryAgent` returns `verdict="failed"`, `recovery_action="stop_safely"`, `retry_budget=0`.
    - Assert safe review behavior remains unchanged.

12. Add integration test for recovery stop.
    - In `tests/integration/test_langgraph_workflow_gateway.py`, monkeypatch `DeterministicValidatorRecoveryAgent.review` to return blocked `FinalReviewResult` and `RecoveryDecision(stop_safely)`.
    - Run workflow with `auto_confirm=False`.
    - Assert result status is `failed`.
    - Assert `error_json["error_type"] == "recovery_stopped"`.
    - Assert `action_count == 0`.
    - Assert `saga_execution_engine` is not in node history.
    - Assert run metadata has `workflow.recovery.attempt_count == 1`.

13. Add integration test for one successful retry loop.
    - Monkeypatch validator review so first call returns `RecoveryDecision(recovery_action="retry", route_to="execute_searches", retry_budget=1)` and second call delegates to the original review.
    - Run workflow with `auto_confirm=False`.
    - Assert final status is `awaiting_confirmation`.
    - Assert `execute_searches` appears at least twice.
    - Assert `apply_recovery` appears once.
    - Assert `action_count == 0`.
    - Assert recovery metadata records one routed attempt.

14. Update workflow agent metadata integration test.
    - Assert `agents` metadata still contains all five roles.
    - Assert workflow recovery metadata does not contain `action_id`, `tool_event_id`, `debug_trace`, `api_key`, `token`, or `secret`.

15. Check benchmark tests.
    - Keep `REQUIRED_WORKFLOW_NODES = V1_WORKFLOW_NODE_NAMES`.
    - Add or update assertions only if the extra `apply_recovery` node affects report serialization.
    - Do not add or remove benchmark cases.

16. Check demo API tests.
    - Preserve response field names.
    - If a failed recovery run is exposed through demo summary tests, assert sanitized `error` shape only.
    - Do not redesign frontend behavior.

17. Run focused unit tests:
    - `python -m pytest tests/test_agents.py tests/test_langgraph_workflow.py -v`

18. Run focused workflow integrations:
    - `python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_workflow_agents_gateway.py -v`

19. Run demo and benchmark regression tests:
    - `python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v`
    - `python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v`

20. Run broad verification:
    - `python -m pytest -q`
    - `npm --prefix frontend run test -- --run`
    - `npm --prefix frontend run build`
    - `docker compose config`
    - `git diff --check`
    - `git status --short`

21. Review changed files.
    - Confirm no migrations were added.
    - Confirm no benchmark fixtures were added or removed.
    - Confirm no frontend redesign happened.
    - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` is not staged.

22. Commit Task 027 only.

## 6. Testing Plan

- Unit tests:
  - recovery route resolver maps every supported action deterministically.
  - missing decision, unsupported route, exhausted budget, and attempt limit return stop outcomes.
  - graph routes passed decisions to `final_review`.
  - graph routes failed retry decisions through `apply_recovery`.
  - blocked validator decisions default to `stop_safely`.

- Integration tests:
  - recovery stop returns `failed`, writes no Action Ledger rows, and persists sanitized recovery metadata.
  - one retry loop can return to `execute_searches`, recover to `awaiting_confirmation`, and still create zero pre-confirmation actions.
  - happy-path `auto_confirm=False` still pauses at confirmation.
  - happy-path `auto_confirm=True` still executes after confirmation and records feedback/observability.
  - agent metadata and workflow recovery metadata remain sanitized.

- Regression tests:
  - demo API response shape remains unchanged.
  - benchmark harness still grades the V1 required workflow path.
  - frontend tests and build still pass.

## 7. Verification Commands

```bash
python -m pytest tests/test_agents.py tests/test_langgraph_workflow.py -v
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_workflow_agents_gateway.py -v
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest -q
npm --prefix frontend run test -- --run
npm --prefix frontend run build
docker compose config
git diff --check
git status --short
```

If frontend dependencies are not installed, record the exact npm error and complete all backend checks.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add bounded recovery routing v0
```

Expected commands:

```bash
git status --short
git checkout -b task27
git add docs/specs/027-recovery-routing-v0.md docs/plans/027-recovery-routing-v0-plan.md
git add backend/app/workflow/recovery.py backend/app/workflow/state.py backend/app/workflow/__init__.py backend/app/workflow/graph.py backend/app/workflow/nodes.py backend/app/workflow/runner.py backend/app/agents/deterministic.py
git add tests/test_langgraph_workflow.py tests/test_agents.py tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_workflow_agents_gateway.py tests/test_demo_api.py tests/integration/test_demo_api_gateway.py tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py
git diff --cached --check
git commit -m "feat: add bounded recovery routing v0"
git push -u origin task27
```

Before committing, confirm `.env`, `var/`, Playwright artifacts, `node_modules`, `frontend/dist`, API keys, tokens, secrets, and unrelated `docs/TASK_WORKFLOW_PROMPTS.md` are not staged.

## 9. Out-of-scope Changes

- Do not add LLM calls, prompts, model config, or LLM-backed agents.
- Do not add real provider support or change live AMAP behavior.
- Do not expand benchmark cases or edit benchmark fixtures.
- Do not add failure injection, replay, or chaos harness features.
- Do not redesign frontend UI or add recovery visualization.
- Do not change Web demo API response field names.
- Do not add database migrations unless the existing metadata JSON field is proven insufficient.
- Do not add dependencies.
- Do not execute write tools before explicit confirmation.
- Do not route recovery directly to `wait_confirmation`, `saga_execution_engine`, or `generate_summary_message`.
- Do not rewrite deterministic planning, enrichment, execution, feedback, or benchmark logic beyond recovery routing needs.
- Do not stage unrelated local files.

## 10. Review Checklist

- [ ] Task 027 spec and plan are saved in expected paths.
- [ ] `RecoveryDecision` is consumed after `semantic_validator`.
- [ ] Happy-path V1 required node grading still passes.
- [ ] `retry`, `expand_search_radius`, and `replace_candidate` route only to deterministic read/planning nodes.
- [ ] `ask_user`, `stop_safely`, exhausted budget, unsupported route, and attempt limit stop safely.
- [ ] Recovery attempts are capped by explicit budget and max attempt count.
- [ ] Recovery metadata is persisted under `agent_runs.metadata_json["workflow"]["recovery"]`.
- [ ] Recovery metadata is sanitized.
- [ ] `auto_confirm=False` creates zero Action Ledger rows, including after recovery.
- [ ] `auto_confirm=True` writes Action Ledger rows only after confirmation.
- [ ] Demo API response shape is unchanged.
- [ ] Benchmark harness still uses `WeekendPilotWorkflowRunner`.
- [ ] No benchmark cases, provider support, LLM calls, migrations, or frontend redesign were added.
- [ ] Required backend and frontend verification commands passed or blockers are documented.
- [ ] `git diff --check` passed.
- [ ] No secrets or generated artifacts were staged.
- [ ] Commit message is `feat: add bounded recovery routing v0`.
- [ ] Push succeeded.

## 11. Handoff Notes

Report back with:

- Branch name.
- Commit hash.
- Files changed.
- Verification commands and pass/fail results.
- Any skipped command and exact environment reason.
- Confirmation that recovery metadata is persisted and sanitized.
- Confirmation that no pre-confirmation write actions are created during recovery.
- Confirmation that Web demo API and benchmark harness remained compatible.
- Known limitation: Task 027 adds bounded routing mechanics; richer recovery intelligence, failure injection, replay, and expanded benchmark cases remain follow-up tasks.
