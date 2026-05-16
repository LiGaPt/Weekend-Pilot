# Spec: 026 V1 Workflow State and DAG Optimization

## 1. Goal

Align the LangGraph workflow state and node boundaries with the V1 Optimized Workflow Target in `docs/PROJECT_BLUEPRINT.md` while preserving the existing MVP behavior.

After this task, the workflow should still support the same Mock World Web demo, confirmation boundary, workflow-backed benchmark harness, deterministic bounded-agent adapters, execution workflow, feedback writer, and observability path. The main improvement is structural: workflow state should become more typed and explicit, and the graph should expose clearer V1 node responsibilities without introducing recovery routing or changing product behavior.

## 2. Project Context

Tasks 019-025 established the current MVP route:

- LangGraph workflow skeleton
- bounded deterministic agent adapters
- workflow-backed LocalLife-Bench harness
- Web demo API
- minimal React/Vite Web UI
- Web E2E coverage and Chinese localized demo content

The current workflow is functional but still shaped like the Task 019 skeleton. `WeekendPilotWorkflowState` stores many fields as `Any`, and the graph has broad MVP nodes such as `build_query_plan`, `collect_candidates`, `enrich_candidates`, `generate_itinerary`, `final_review`, `execute`, and `write_feedback`.

`docs/PROJECT_BLUEPRINT.md` says V1 should evolve toward this DAG:

```text
initialize
-> parse_intent
-> load_memory
-> generate_queries
-> execute_searches
-> populate_candidate_blackboard
-> pre_flight_check_availability
-> logical_planner_agent
-> route_and_time_engine
-> semantic_validator
-> final_review
-> present_to_user
-> wait_confirmation
-> saga_execution_engine
-> generate_summary_message
```

Task 026 is the structural alignment task before recovery routing v0 and expanded benchmark cases. It should make the official product workflow easier to reason about, test, observe, and extend without changing the visible demo contract.

## 3. Requirements

- Replace broad `Any` fields in workflow state with existing project schemas wherever practical.
- Keep `WeekendPilotWorkflowRequest` and `WeekendPilotWorkflowResult` backward compatible for current callers.
- Preserve `tool_profile="mock_world"` and `world_profile="family_afternoon"` as the only supported workflow profile.
- Introduce V1-aligned workflow node names or node boundaries for:
  - `initialize`
  - `parse_intent`
  - `load_memory`
  - `generate_queries`
  - `execute_searches`
  - `populate_candidate_blackboard`
  - `pre_flight_check_availability`
  - `logical_planner_agent`
  - `route_and_time_engine`
  - `semantic_validator`
  - `final_review`
  - `present_to_user`
  - `wait_confirmation`
  - `saga_execution_engine`
  - `generate_summary_message`
- Preserve the existing behavior of the current deterministic service chain:
  - deterministic intent parsing
  - deterministic query planning
  - Tool Gateway read calls
  - candidate enrichment
  - deterministic itinerary generation
  - validator/recovery adapter review
  - final review gate
  - reviewed plan persistence and selection
  - human confirmation boundary
  - deterministic execution workflow
  - deterministic feedback writing
  - observability summary recording
- Keep all tool calls routed through Tool Gateway.
- Keep all write-tool execution blocked before explicit confirmation.
- Keep deterministic bounded-agent adapters as deterministic adapters; do not add LLM calls.
- Persist workflow metadata under `agent_runs.metadata_json["workflow"]`.
- Continue persisting sanitized bounded-agent metadata under `agent_runs.metadata_json["agents"]`.
- Update workflow path tests and benchmark graders so they assert the V1-aligned node history.
- Keep Web demo API responses Web-safe and unchanged in shape.
- Keep LocalLife-Bench using the official workflow runner.

## 4. Non-goals

- Do not implement recovery routing, retries, route loops, or retry-budget consumption.
- Do not expand benchmark cases.
- Do not add a real provider or modify live AMAP behavior.
- Do not add LLM calls, prompt templates, model configuration, or LLM-backed agent behavior.
- Do not change the confirmation boundary.
- Do not redesign the frontend.
- Do not break Web demo API contracts.
- Do not break the workflow-backed benchmark harness.
- Do not add database tables or migrations unless an existing test proves the workflow cannot be aligned without one.
- Do not commit `.env`, API keys, tokens, secrets, `var/`, Playwright artifacts, `node_modules`, or `frontend/dist`.

## 5. Interfaces and Contracts

### Inputs

The workflow entrypoint remains:

- `WeekendPilotWorkflowRunner.run(request: WeekendPilotWorkflowRequest)`

`WeekendPilotWorkflowRequest` must remain compatible with the current fields:

- `user_input`
- `external_user_id`
- `display_name`
- `case_id`
- `agent_version`
- `prompt_version`
- `tool_profile`
- `world_profile`
- `failure_profile`
- `auto_confirm`
- `selected_plan_index`

The Web demo API must continue to use the same request and response shapes from Task 022-025.

### Outputs

`WeekendPilotWorkflowResult` must remain compatible with current consumers:

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
- `agent_results`
- `error_json`

`node_history` should now reflect V1-aligned workflow node names. The benchmark harness and tests should treat those names as the official workflow path after Task 026.

### Workflow State

The workflow state should continue to be a LangGraph-compatible state type, but it should use typed domain objects where existing schemas already exist.

Expected state categories:

- request context:
  - user input
  - user/run identifiers
  - profile metadata
  - confirmation mode
- typed planning data:
  - parsed intent as `LocalLifeIntent`
  - active memory records as a typed workflow memory summary or clearly documented serializable structure
  - query plan as `QueryPlan`
  - candidate collection as `CandidateCollectionResult`
  - candidate blackboard as a typed workflow model or a documented Pydantic model introduced by this task
  - enrichment result as `CandidateEnrichmentResult`
  - itinerary drafts as `ItineraryDraftResult`
  - final review result as `FinalReviewResult`
  - recovery decision as `RecoveryDecision`
- persistence and execution data:
  - persisted reviewed plans
  - selected plan ID
  - confirmation result
  - execution result
  - feedback result
  - observability result

If the implementation introduces new workflow-only schemas, they should live under `backend.app.workflow` and remain adapter models, not durable database models.

### Node Boundary Mapping

Task 026 may reuse existing deterministic service implementations internally, but graph-facing node names and responsibilities should align with V1:

- `generate_queries` wraps current deterministic query planning and supervisor assignment.
- `execute_searches` wraps current initial read-tool execution.
- `populate_candidate_blackboard` creates a typed candidate/evidence working set from collected candidates.
- `pre_flight_check_availability` wraps current enrichment checks that remove or mark unavailable candidates before planning.
- `logical_planner_agent` wraps itinerary planner adapter output at the semantic sequence/rationale level.
- `route_and_time_engine` owns deterministic route/time feasibility data used by final itinerary output.
- `semantic_validator` wraps validator/recovery adapter output without executing recovery routing.
- `final_review` remains the final rule and consistency gate.
- `present_to_user` persists reviewed plans and selects the initial plan for presentation.
- `wait_confirmation` preserves the existing human confirmation pause.
- `saga_execution_engine` wraps deterministic confirmed action execution.
- `generate_summary_message` wraps deterministic feedback writing and observability recording, unless the implementation keeps observability as a distinct final node and documents why.

## 6. Observability

Task 026 should not add a new telemetry backend.

Existing observability behavior must continue:

- Tool events carry the workflow trace ID.
- Action Ledger rows are written only after confirmation.
- `agent_runs.metadata_json["workflow"]` records workflow source, version, `auto_confirm`, and selected plan index.
- `agent_runs.metadata_json["agents"]` records sanitized bounded-agent results.
- Local trace buffer and optional LangSmith recorder behavior continue to work.

Task 026 should update workflow metadata to identify the new workflow version, for example `v1_workflow_state_dag_alignment`.

Benchmark reports should continue to include workflow status, node history, agent roles, tool event count, action count, feedback status, and observability status.

## 7. Failure Handling

- Unsupported workflow profiles should still return a typed `WeekendPilotWorkflowResult` with `status="error"` and `error_type="unsupported_profile"`.
- Missing required typed state should fail cleanly with a workflow error, not an unhelpful `KeyError` or `AttributeError`.
- Final review failure should still stop safely before presentation or execution.
- `auto_confirm=False` must always stop before write-tool execution.
- `auto_confirm=True` may continue through deterministic confirmation, execution, feedback, and observability.
- Observability failure must not erase a completed execution result.
- Recovery decisions may be produced and stored for traceability, but they must not route the graph or trigger retries in Task 026.
- If V1-aligned node splitting exposes a mismatch in existing deterministic service outputs, fix the adapter boundary rather than changing public Web demo or benchmark contracts.

## 8. Acceptance Criteria

- [ ] `WeekendPilotWorkflowState` no longer relies on broad `Any` for the main existing domain objects when project schemas exist.
- [ ] The workflow graph exposes V1-aligned node names or documented V1-aligned node boundaries.
- [ ] `REQUIRED_NODE_NAMES` is updated to represent the Task 026 official workflow path.
- [ ] `WeekendPilotWorkflowRequest` remains backward compatible.
- [ ] `WeekendPilotWorkflowResult` remains backward compatible.
- [ ] `auto_confirm=False` still returns `awaiting_confirmation`.
- [ ] `auto_confirm=False` still creates zero Action Ledger rows.
- [ ] `auto_confirm=True` still completes through execution, feedback, and observability.
- [ ] Web demo API happy path still starts, reads, confirms, declines, and refreshes runs with the same response shape.
- [ ] Benchmark harness still calls `WeekendPilotWorkflowRunner` and not a parallel orchestration path.
- [ ] Benchmark report still includes workflow status, node history, and all five bounded-agent roles.
- [ ] Tool events created by the workflow retain the workflow trace ID.
- [ ] Recovery decisions remain trace-only and do not execute recovery routing.
- [ ] No benchmark cases are added or removed.
- [ ] No real provider or LLM call is added.
- [ ] Frontend behavior and API field names remain compatible with Task 025.
- [ ] Existing backend unit tests pass after updates.
- [ ] Existing backend integration tests for workflow, agents, benchmark, and demo API pass.
- [ ] Existing frontend unit tests, build, and E2E checks pass.
- [ ] No `.env`, API key, token, secret, `var/`, Playwright artifact, `node_modules`, or `frontend/dist` file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored or intentionally untracked local runtime files.

## 9. Verification Commands

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

## 10. Expected Commit

```text
refactor: align workflow state with v1 dag
```

## 11. Notes for the Implementer

Keep this task structural and compatibility-focused. The purpose is to make the workflow easier to extend safely, not to add new product behavior.

Prefer adapting existing deterministic services behind clearer workflow nodes over rewriting planning, enrichment, review, execution, or feedback logic. Keep the Web demo and benchmark harness as regression anchors: if either breaks, the task is drifting beyond alignment.

Do not interpret `RecoveryDecision` as a graph-routing instruction in this task. Recovery routing v0 should be a later task after typed state and V1 node boundaries are stable.
