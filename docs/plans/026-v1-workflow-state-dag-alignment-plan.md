# Plan: 026 V1 Workflow State and DAG Optimization

## 1. Spec Reference

Spec file:

```text
docs/specs/026-v1-workflow-state-dag-alignment.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Suggested plan path:

```text
docs/plans/026-v1-workflow-state-dag-alignment-plan.md
```

## 2. Current Repository Assumptions

- Current branch is `task25`.
- Working tree is currently clean.
- The Task 026 spec content has been drafted, but `docs/specs/026-v1-workflow-state-dag-alignment.md` is not yet present in the workspace. Save the approved spec before implementation.
- Current workflow code lives in `backend/app/workflow/` and uses broad MVP node names.
- `WeekendPilotWorkflowState` currently lives in `backend/app/workflow/schemas.py` and uses many `Any` fields.
- Current benchmark path is workflow-backed and grades `REQUIRED_WORKFLOW_NODES` from `backend/app/benchmark/graders.py`.
- Current Web demo API depends on the workflow runner for initial planning, then continues confirmation/execution/feedback through `backend/app/demo/service.py`.
- No new provider, LLM, migration, benchmark case, or frontend redesign is required.

## 3. Files to Add

- `backend/app/workflow/state.py` - typed workflow state, V1 node constants, and workflow-only adapter models such as memory records, candidate blackboard, and route/time summary.
- `docs/plans/026-v1-workflow-state-dag-alignment-plan.md` - this implementation plan.
- `docs/specs/026-v1-workflow-state-dag-alignment.md` - only if the approved spec has not already been saved.

## 4. Files to Modify

- `backend/app/workflow/schemas.py` - keep request/result models stable and re-export or import typed workflow state.
- `backend/app/workflow/graph.py` - replace MVP graph node list and edges with V1-aligned graph path.
- `backend/app/workflow/nodes.py` - split existing broad node methods into V1-aligned node methods while reusing existing services.
- `backend/app/workflow/runner.py` - initialize new typed state fields and preserve result conversion.
- `backend/app/workflow/__init__.py` - export new workflow state models only if needed by tests or consumers.
- `backend/app/demo/service.py` - align continuation node history names without changing API response shape.
- `backend/app/benchmark/graders.py` - update required workflow node constants.
- `tests/test_langgraph_workflow.py` - update graph, route, and node-history unit tests.
- `tests/integration/test_langgraph_workflow_gateway.py` - update integration assertions for V1 node names.
- `tests/test_benchmark_harness.py` - update benchmark workflow path expectations.
- `tests/integration/test_benchmark_harness_gateway.py` - update report/node-history assertions.
- `tests/test_demo_api.py` and `tests/integration/test_demo_api_gateway.py` - update node-history fixtures/assertions if affected.

## 5. Implementation Steps

1. Create a dedicated branch from `task25`, recommended: `task26`.

2. Save the approved Task 026 spec at `docs/specs/026-v1-workflow-state-dag-alignment.md` if it is still missing.

3. Save this plan at `docs/plans/026-v1-workflow-state-dag-alignment-plan.md`.

4. Add `backend/app/workflow/state.py`.
   - Define `V1_WORKFLOW_NODE_NAMES` in this exact order:
     `initialize`, `parse_intent`, `load_memory`, `generate_queries`, `execute_searches`, `populate_candidate_blackboard`, `pre_flight_check_availability`, `logical_planner_agent`, `route_and_time_engine`, `semantic_validator`, `final_review`, `present_to_user`, `wait_confirmation`, `saga_execution_engine`, `generate_summary_message`.
   - Add workflow-only Pydantic models:
     `WorkflowMemoryRecord`, `CandidateBlackboardEntry`, `CandidateBlackboard`, and `RouteTimeSummary`.
   - Move or define `WeekendPilotWorkflowState` here with typed fields for existing schemas: `LocalLifeIntent`, `QueryPlan`, `CandidateCollectionResult`, `CandidateEnrichmentResult`, `ItineraryDraftResult`, `FinalReviewResult`, `RecoveryDecision`, `PersistedPlan`, `ConfirmationResult`, `ExecutionWorkflowResult`, `ExecutionFeedbackResult`, `TraceRecordResult`, and `AgentResult`.

5. Update `backend/app/workflow/schemas.py`.
   - Keep `WeekendPilotWorkflowRequest`, `WeekendPilotWorkflowResult`, and `WorkflowStatus` compatible.
   - Import/re-export `WeekendPilotWorkflowState` from `workflow.state` so existing imports can be migrated gradually.
   - Avoid changing public request/result field names.

6. Update `backend/app/workflow/graph.py`.
   - Set `REQUIRED_NODE_NAMES = V1_WORKFLOW_NODE_NAMES`.
   - Register V1 node names and methods.
   - Route linearly through V1 planning nodes.
   - Keep `wait_confirmation` as the only conditional boundary.
   - Route `awaiting_confirmation`, `failed`, and `error` to `END`.
   - Route confirmed/auto-confirmed runs to `saga_execution_engine -> generate_summary_message -> END`.

7. Refactor `backend/app/workflow/nodes.py` around V1 node methods.
   - `initialize`: current `initialize_run`; set workflow version to `v1_workflow_state_dag_alignment`.
   - `parse_intent`: current parser behavior.
   - `load_memory`: return `WorkflowMemoryRecord` objects instead of raw dicts where practical.
   - `generate_queries`: current query planner plus supervisor assignment.
   - `execute_searches`: current initial read-tool execution.
   - `populate_candidate_blackboard`: create typed blackboard from `CandidateCollectionResult`; no tool calls.
   - `pre_flight_check_availability`: call current `CandidateEnricher`, persist discovery/dining agent summaries, and update blackboard screened IDs.
   - `logical_planner_agent`: call current deterministic itinerary planner adapter.
   - `route_and_time_engine`: validate and summarize route/timeline/feasibility data from itinerary drafts; do not call tools.
   - `semantic_validator`: call current validator/recovery adapter and store `FinalReviewResult` plus trace-only `RecoveryDecision`.
   - `final_review`: enforce safe/blocked final review status but do not route recovery.
   - `present_to_user`: current reviewed-plan persistence and selection; pass through if state is already failed.
   - `wait_confirmation`: preserve existing confirmation behavior and zero-write pause.
   - `saga_execution_engine`: current deterministic execution workflow.
   - `generate_summary_message`: current feedback writer plus observability recording; preserve completed execution status even if observability fails.

8. Update helper methods in `nodes.py`.
   - Replace `_memory_json` with typed memory conversion.
   - Add blackboard and route/time summary builders.
   - Keep `_updates` as the single node-history append point.
   - Keep all persisted metadata sanitized.
   - Do not consume or execute `RecoveryDecision.route_to`.

9. Update `backend/app/workflow/runner.py`.
   - Initialize new state fields with typed empty defaults.
   - Preserve unsupported-profile typed error result.
   - Preserve `WeekendPilotWorkflowResult` conversion and field names.
   - Ensure `agent_results` still parses from dicts if LangGraph serializes state.

10. Update `backend/app/demo/service.py`.
   - Preserve response schemas and continuation behavior.
   - Change continuation history labels from old execution/feedback names to V1-aligned names where appropriate: `saga_execution_engine`, `generate_summary_message`.
   - Keep confirmation and decline behavior unchanged.

11. Update benchmark grader constants.
   - Replace old `REQUIRED_WORKFLOW_NODES` with V1 node list.
   - Keep grader semantics unchanged: completed workflow plus all required nodes.

12. Update unit tests first.
   - Rewrite `_StubNodes` in `tests/test_langgraph_workflow.py` for V1 methods.
   - Assert graph exposes every V1 node.
   - Assert awaiting confirmation stops before `saga_execution_engine`.
   - Assert confirmed route continues to `saga_execution_engine`.

13. Update integration tests.
   - In workflow integration tests, assert `generate_summary_message` exists for auto-confirmed runs.
   - Assert `saga_execution_engine` is absent for `auto_confirm=False`.
   - Keep trace ID, action count, feedback, and observability assertions.

14. Update benchmark tests.
   - Replace local test constants with V1 required node names.
   - Update missing-node failure assertions to expect a V1 node.
   - Keep one default benchmark case only.

15. Update demo API tests only where node-history fixture values changed.
   - Do not change API field names.
   - Do not change confirmation, decline, idempotency, or sanitizer assertions.

16. Run focused backend tests and fix only Task 026 regressions.

17. Run full backend test suite and frontend regression checks.

18. Review `git diff --check` and `git status --short`.

19. Commit only Task 026 files.

## 6. Testing Plan

- Unit tests:
  - Graph compiles with all V1 node names.
  - `route_after_confirmation` preserves confirmation boundary behavior.
  - Unsupported profiles still return typed `error`.
  - Benchmark workflow-path grader uses V1 nodes.
  - Typed state adapter models serialize cleanly where tested.

- Integration tests:
  - `auto_confirm=False` returns `awaiting_confirmation`, creates no Action Ledger rows, and does not include `saga_execution_engine`.
  - `auto_confirm=True` reaches `completed`, includes `saga_execution_engine` and `generate_summary_message`, writes actions only after confirmation, writes feedback, and records observability.
  - Benchmark harness still runs `family_afternoon_v1` through the workflow runner and writes sanitized reports.
  - Demo API still supports start, get, confirm, decline, idempotent confirm, and response sanitization.

- Frontend regression:
  - Run unit tests, build, and E2E because the Web demo displays workflow node history.

## 7. Verification Commands

```bash
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
python -m pytest tests/integration/test_workflow_agents_gateway.py -v
python -m pytest -q
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run e2e
docker compose config
git diff --check
git status --short
```

If Playwright cannot launch Chromium locally, record the exact error and complete all backend and non-browser frontend checks.

## 8. Commit and Push Plan

Expected commit message:

```text
refactor: align workflow state with v1 dag
```

Expected commands:

```bash
git status --short
git checkout -b task26
git add docs/specs/026-v1-workflow-state-dag-alignment.md docs/plans/026-v1-workflow-state-dag-alignment-plan.md backend/app/workflow backend/app/demo/service.py backend/app/benchmark/graders.py tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py tests/test_demo_api.py tests/integration/test_demo_api_gateway.py tests/integration/test_workflow_agents_gateway.py
git diff --cached --check
git commit -m "refactor: align workflow state with v1 dag"
git push -u origin task26
```

Before committing, confirm `.env`, `var/`, Playwright artifacts, `node_modules`, `frontend/dist`, API keys, tokens, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement recovery routing, retries, route loops, or retry-budget consumption.
- Do not expand LocalLife-Bench cases.
- Do not add real providers or modify live AMAP behavior.
- Do not add LLM calls, prompts, or model configuration.
- Do not change the confirmation boundary.
- Do not redesign the frontend.
- Do not change Web demo API response field names.
- Do not add database migrations.
- Do not introduce new package dependencies.
- Do not rewrite deterministic planning, enrichment, execution, feedback, or benchmark logic beyond adapter changes needed for V1 node boundaries.

## 10. Review Checklist

- [ ] Task 026 spec and plan are saved in the expected docs paths.
- [ ] Workflow state uses typed project schemas for main domain objects.
- [ ] Graph exposes V1 node names in the required order.
- [ ] `wait_confirmation` is still the only conditional execution boundary.
- [ ] `auto_confirm=False` creates zero Action Ledger rows.
- [ ] `auto_confirm=True` completes through deterministic execution and feedback.
- [ ] Recovery decisions are trace-only and do not route the graph.
- [ ] Web demo API response shape is unchanged.
- [ ] Benchmark harness still uses `WeekendPilotWorkflowRunner`.
- [ ] No benchmark cases were added or removed.
- [ ] No provider, LLM, migration, or frontend redesign was added.
- [ ] Required backend and frontend verification commands passed or documented an environment-specific blocker.
- [ ] `git diff --check` passed.
- [ ] No secrets or generated artifacts were staged.
- [ ] Commit message is `refactor: align workflow state with v1 dag`.
- [ ] Push succeeded.

## 11. Handoff Notes

Report back with:

- Branch name.
- Commit hash.
- Files changed.
- Verification commands run and pass/fail results.
- Any skipped command and exact environment reason.
- Confirmation that the Web demo API and benchmark harness stayed compatible.
- Known limitation: Task 026 only aligns state and DAG boundaries; recovery routing v0 remains a follow-up task.
