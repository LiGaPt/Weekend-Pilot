# Spec: 027 Recovery Routing v0

## 1. Goal

Add the first bounded recovery-routing layer for WeekendPilot's official LangGraph workflow.

After this task, structured `RecoveryDecision` objects from the Validator & Recovery adapter should no longer be trace-only. The workflow should be able to consume safe recovery decisions, route back through deterministic read/planning nodes with an explicit retry budget, and stop safely when recovery is not allowed or not useful.

This unlocks the first real failure-recovery path needed by `docs/PROJECT_BLUEPRINT.md` while preserving the existing Mock World Web demo, confirmation boundary, Action Ledger safety, workflow-backed benchmark harness, bounded deterministic agents, and V1 DAG alignment from Task 026.

## 2. Project Context

Task 026 aligned workflow state and node names with the V1 target DAG:

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

Task 026 intentionally kept recovery decisions as trace-only:

- `semantic_validator` stores `FinalReviewResult` and `RecoveryDecision`.
- `final_review` stops failed plans safely.
- No graph route currently consumes `RecoveryDecision.route_to` or `retry_budget`.

`docs/PROJECT_BLUEPRINT.md` says dynamic recovery routing is allowed only through structured Validator & Recovery decisions, retry budgets must be explicit, recovery decisions must be traceable, and confirmation boundaries must remain intact.

Task 027 adds the smallest useful recovery-routing v0 on top of the Task 026 workflow. It should keep the happy path stable and add bounded loopback only for deterministic read/planning stages.

## 3. Requirements

- Keep `WeekendPilotWorkflowRequest` and `WeekendPilotWorkflowResult` response shape backward compatible.
- Keep `tool_profile="mock_world"` and `world_profile="family_afternoon"` as the only supported workflow profile.
- Do not change the successful happy-path V1 node sequence required by the benchmark grader.
- Add workflow state fields for bounded recovery tracking, including attempted decisions, route targets, attempt count, and maximum attempts.
- Consume `RecoveryDecision` after `semantic_validator` and before `final_review`.
- Route passed decisions with `recovery_action="none"` directly to `final_review`.
- Support these v0 recovery actions:
  - `retry`
  - `replace_candidate`
  - `expand_search_radius`
  - `ask_user`
  - `stop_safely`
- Map recovery actions only to deterministic workflow nodes:
  - `retry` may loop back to `execute_searches`.
  - `expand_search_radius` may loop back to `generate_queries`.
  - `replace_candidate` may loop back to `logical_planner_agent`.
  - `ask_user` must stop safely with a structured user-input-required error.
  - `stop_safely` must stop safely with a structured recovery-stopped error.
- Enforce a hard default maximum of one recovery attempt per workflow run unless explicitly configured in workflow state by tests.
- Never execute write tools during recovery.
- Never route from recovery directly to `saga_execution_engine` or any write path.
- Decrement or consume retry budget deterministically so recovery loops cannot be unbounded.
- Persist sanitized recovery metadata under `agent_runs.metadata_json["workflow"]["recovery"]`.
- Preserve existing sanitized bounded-agent metadata under `agent_runs.metadata_json["agents"]`.
- Keep all recovery decisions and attempts serializable and safe for benchmark reports.
- Update unit and integration tests so recovery routing behavior is covered without expanding benchmark fixtures.
- Keep the Web demo API response field names unchanged.
- Keep LocalLife-Bench using `WeekendPilotWorkflowRunner`.

## 4. Non-goals

- Do not add LLM calls, prompts, model configuration, or LLM-backed agents.
- Do not add real provider support or modify live AMAP behavior.
- Do not expand LocalLife-Bench cases.
- Do not implement failure injection, replay harness, chaos harness, or new benchmark difficulty levels.
- Do not redesign the frontend or add recovery visualization UI.
- Do not change Web demo API response schemas or field names.
- Do not add a new public workflow status unless an existing test proves safe recovery cannot be represented otherwise.
- Do not execute write tools before explicit human confirmation.
- Do not route recovery to `wait_confirmation`, `saga_execution_engine`, or `generate_summary_message`.
- Do not add database tables or migrations unless existing PostgreSQL metadata fields are insufficient.
- Do not introduce new package dependencies.
- Do not rewrite deterministic planning, enrichment, execution, feedback, or benchmark logic beyond what is needed for bounded recovery routing.
- Do not commit `.env`, API keys, tokens, secrets, `var/`, Playwright artifacts, `node_modules`, `frontend/dist`, or unrelated untracked files such as `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

The workflow entrypoint remains:

- `WeekendPilotWorkflowRunner.run(request: WeekendPilotWorkflowRequest)`

The recovery router consumes:

- `RecoveryDecision` from `semantic_validator`
- `FinalReviewResult`
- `ItineraryDraftResult`
- `CandidateBlackboard`
- recovery attempt state from `WeekendPilotWorkflowState`

`RecoveryDecision` remains the structured contract from the bounded Validator & Recovery adapter:

- `verdict`
- `error_type`
- `recovery_action`
- `route_to`
- `retry_budget`
- `reason`

Task 027 may tighten validation around `route_to`, but it must not allow arbitrary graph node execution.

### Outputs

`WeekendPilotWorkflowResult` remains compatible with current consumers:

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

Recovery attempts may cause repeated deterministic planning nodes in `node_history`. The happy path should remain the Task 026 V1 path.

If recovery cannot continue, `error_json` must include:

```json
{
  "error_type": "recovery_stopped",
  "message": "Recovery stopped safely.",
  "details": {
    "recovery_action": "stop_safely",
    "retry_budget": 0
  }
}
```

For `ask_user`, use `error_type="recovery_requires_user_input"` and include a concise user-safe reason in `details`.

### Schemas

Task 027 may add workflow-only Pydantic models under `backend.app.workflow`, for example:

```json
{
  "attempt_index": 1,
  "source_node": "semantic_validator",
  "recovery_action": "retry",
  "route_to": "execute_searches",
  "error_type": "route_infeasible",
  "retry_budget_before": 1,
  "retry_budget_after": 0,
  "status": "routed"
}
```

These models are adapter/state models only. They are not durable database models.

## 6. Observability

Task 027 must not add a new telemetry backend.

Existing observability must continue:

- Tool events retain workflow trace IDs.
- Action Ledger rows are written only after confirmation.
- `agent_runs.metadata_json["workflow"]` records workflow source and version.
- `agent_runs.metadata_json["agents"]` records sanitized bounded-agent outputs.
- Local trace buffer and optional LangSmith recorder behavior continue to work.

Task 027 must add sanitized recovery metadata under workflow metadata:

```json
{
  "workflow": {
    "workflow_version": "recovery_routing_v0",
    "recovery": {
      "attempt_count": 1,
      "max_attempts": 1,
      "attempts": []
    }
  }
}
```

Recovery metadata must not include raw tracebacks, prompts, secrets, API keys, raw `tool_event_id`, or raw `action_id`.

## 7. Failure Handling

- If `RecoveryDecision` is missing after `semantic_validator`, fail cleanly with `error_type="missing_recovery_decision"`.
- If `RecoveryDecision.route_to` is unsupported, stop safely with `error_type="unsupported_recovery_route"`.
- If `retry_budget <= 0`, stop safely with `error_type="recovery_budget_exhausted"`.
- If maximum workflow recovery attempts has already been reached, stop safely with `error_type="recovery_attempt_limit_exceeded"`.
- If recovery routes back to a deterministic read/planning node and that node fails again, the workflow must not loop indefinitely.
- If recovery produces a safe final review after one attempt, the workflow may continue to `present_to_user` and then the normal confirmation boundary.
- If `auto_confirm=False`, recovery must still stop before write-tool execution and return `awaiting_confirmation` only after a safe plan has been presented.
- If `auto_confirm=True`, recovery may continue through confirmation and execution only after the final plan passes review.
- Observability failure must not erase completed execution or recovery metadata.
- Unsupported workflow profiles must still return typed `status="error"` with `error_type="unsupported_profile"`.

## 8. Acceptance Criteria

- [ ] The workflow consumes `RecoveryDecision` after `semantic_validator`.
- [ ] Passed decisions with `recovery_action="none"` preserve the existing happy path.
- [ ] `retry` can route back only to deterministic read/planning nodes and cannot execute write tools.
- [ ] `replace_candidate` can route only to deterministic planning nodes and cannot execute write tools.
- [ ] `expand_search_radius` can route only to deterministic query/search nodes and cannot execute write tools.
- [ ] `ask_user` stops safely with `error_type="recovery_requires_user_input"`.
- [ ] `stop_safely` stops safely with structured recovery error metadata.
- [ ] Recovery attempts are capped by explicit retry budget and workflow max attempt count.
- [ ] Recovery attempts are stored in workflow state and persisted under `agent_runs.metadata_json["workflow"]["recovery"]`.
- [ ] Recovery metadata is sanitized and does not expose raw action IDs, tool event IDs, prompts, secrets, API keys, or tracebacks.
- [ ] `auto_confirm=False` still creates zero Action Ledger rows, including after recovery.
- [ ] `auto_confirm=True` still writes Action Ledger rows only after confirmation.
- [ ] The Web demo API happy path keeps the same response shape.
- [ ] The benchmark harness still uses `WeekendPilotWorkflowRunner`.
- [ ] The existing happy-path benchmark grader still passes without requiring recovery nodes.
- [ ] Unit tests cover recovery route mapping, unsupported routes, exhausted budgets, and attempt limits.
- [ ] Integration tests cover at least one safe recovery stop and confirm zero pre-confirmation write actions.
- [ ] No benchmark cases are added or removed.
- [ ] No real provider, LLM call, prompt, migration, or frontend redesign is added.
- [ ] Existing backend unit tests pass after updates.
- [ ] Existing backend integration tests for workflow, agents, demo API, and benchmark path pass.
- [ ] Existing frontend unit tests and build pass.
- [ ] No `.env`, API key, token, secret, `var/`, Playwright artifact, `node_modules`, `frontend/dist`, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

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

If frontend dependencies are not installed, record the exact error and complete all backend checks.

## 10. Expected Commit

```text
feat: add bounded recovery routing v0
```

## 11. Notes for the Implementer

Keep this task focused on bounded routing, not richer recovery intelligence.

Prefer deterministic and testable routing over broad behavior changes. If a recovery action cannot safely improve the state in Task 027, stop safely with structured metadata instead of pretending recovery succeeded.

The confirmation boundary is non-negotiable: recovery may repeat read and planning work, but it must never execute reservations, queues, ticket booking, orders, messages, or Action Ledger writes before explicit confirmation.

The current untracked `docs/TASK_WORKFLOW_PROMPTS.md` appears unrelated to Task 027. Do not stage or commit it unless the user explicitly adds it to this task.
