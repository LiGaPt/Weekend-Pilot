# Spec: 022 Web Demo API Surface

## 1. Goal

Add the backend API surface needed by the first Web demo.

After this task, a Web client can start a Mock World planning run, read the persisted preview state, explicitly confirm or decline the selected plan, and see execution feedback. The API must use the official workflow path added in Tasks 019-021 and must preserve the human confirmation boundary before any write tool executes.

## 2. Project Context

The updated project blueprint makes the MVP demo Web-first. Task 022 is the backend API step before the minimal React/Vite UI task.

This task connects the current FastAPI app to:

- LangGraph workflow runner
- PostgreSQL source of truth
- Redis runtime services
- Tool Gateway through the official workflow and deterministic execution path
- Human confirmation boundary
- Action Ledger
- LangSmith/local observability metadata

Task 022 should not optimize the V1 DAG yet. The optimized state and DAG work remains a later task after the first Web demo path is usable.

## 3. Requirements

- Add a FastAPI demo router for Web demo workflow calls.
- Add `POST /demo/runs` to start a workflow run with `auto_confirm=False`.
- Add `GET /demo/runs/{run_id}` to return a Web-safe summary from persisted database state.
- Add `POST /demo/runs/{run_id}/confirm` to confirm the selected or requested plan, execute confirmed write actions, write feedback, record observability, and return the updated summary.
- Add `POST /demo/runs/{run_id}/decline` to decline the selected or requested plan without executing write tools.
- Default all demo runs to:
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `agent_version="agent-v1"`
  - `prompt_version="prompt-v1"`
- Use `WeekendPilotWorkflowRunner` for the initial planning path.
- Preserve the confirmation boundary. `POST /demo/runs` must not create any `ActionLedger` rows.
- Implement confirmation continuation with existing deterministic services because the current workflow runner does not yet support resuming an awaiting-confirmation run.
- Reuse the original planning trace ID during confirmation execution so write-tool `ToolEvent.langsmith_trace_id` values remain tied to the same demo run.
- Persist demo metadata under `agent_runs.metadata_json["demo"]`.
- Return only sanitized response payloads suitable for a Web UI.
- Add local CORS support for the Vite demo origins:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
- Add tests for start, status, confirm, decline, idempotent confirmation behavior, and response sanitization.
- Update README with focused Web demo API smoke commands.

## 4. Non-goals

- Do not add the React/Vite frontend.
- Do not add CLI demo tooling.
- Do not add recovery routing.
- Do not implement the V1 optimized DAG/state refactor.
- Do not add LLM-backed agents.
- Do not add real provider calls or new credentials.
- Do not add database migrations unless an existing schema cannot support the API.
- Do not expand LocalLife-Bench cases.
- Do not rewrite completed task specs or plans.
- Do not change `docs/PROJECT_BLUEPRINT.md` as part of this task.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

`POST /demo/runs`

```json
{
  "user_input": "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.",
  "external_user_id": "web-demo-user",
  "display_name": "Web Demo User",
  "case_id": "web-demo",
  "selected_plan_index": 0
}
```

`POST /demo/runs/{run_id}/confirm`

```json
{
  "plan_id": null,
  "confirmed_by": "web-demo-user"
}
```

`POST /demo/runs/{run_id}/decline`

```json
{
  "plan_id": null,
  "declined_by": "web-demo-user",
  "reason": "User chose not to continue."
}
```

If `plan_id` is omitted on confirm or decline, the API must use the currently selected plan for the run.

### Outputs

All endpoints should return a shared `DemoRunSummary` response.

Important response fields:

- `run_id`
- `trace_id`
- `status`
- `selected_plan_id`
- `plans`
- `node_history`
- `tool_event_count`
- `action_count`
- `execution_status`
- `feedback_status`
- `observability_status`
- `agent_roles`
- `error`

Plan preview fields should include:

- `plan_id`
- `status`
- `selected`
- `title`
- `summary`
- `activity`
- `dining`
- `timeline`
- `route`
- `feasibility`
- `proposed_actions`
- `confirmation`
- `execution`
- `feedback`

### Schemas

The implementer should add Pydantic schemas equivalent to:

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

Response schemas should be additive and Web-safe. They must not expose:

- `action_id`
- `tool_event_id`
- `event_id`
- `idempotency_key`
- raw prompts
- debug traces
- API keys, tokens, secrets, or authorization values

## 6. Observability

- Store the initial workflow trace ID in `agent_runs.metadata_json["demo"]["trace_id"]`.
- Store the API version in `agent_runs.metadata_json["demo"]["api_version"]`.
- Store initial workflow node history in demo metadata.
- During confirmation continuation, append continuation steps to `agent_runs.metadata_json["demo"]["continuation_history"]`.
- Use the stored trace ID as `langsmith_trace_id` when executing write tools after confirmation.
- Record observability after confirmation execution if feasible.
- Observability failure must not hide successful execution or fail the whole demo response.

## 7. Failure Handling

- Invalid request bodies should return FastAPI validation errors.
- Unknown `run_id` should return `404`.
- Unknown or non-run-owned `plan_id` should return `404` or `409`.
- Confirming a run without a selected plan should return `409`.
- Confirming a declined plan should return `409`.
- Declining a confirmed or executed plan should return `409`.
- Repeating confirmation for an already executed or completed run should be idempotent and should not create duplicate `ActionLedger` rows.
- Unsupported profiles should remain unavailable through demo endpoints because the demo API only targets Mock World.
- Unexpected errors should return sanitized errors and must not expose internals, prompts, or secrets.

## 8. Acceptance Criteria

- [ ] `POST /demo/runs` starts the official workflow with `auto_confirm=False`.
- [ ] `POST /demo/runs` returns `status="awaiting_confirmation"` for the happy path.
- [ ] `POST /demo/runs` returns at least one plan preview for the family afternoon Mock World input.
- [ ] `POST /demo/runs` creates no `ActionLedger` rows.
- [ ] `GET /demo/runs/{run_id}` rebuilds the same summary from persisted state.
- [ ] `POST /demo/runs/{run_id}/confirm` confirms the selected plan and executes write tools.
- [ ] Confirmation writes execution and feedback metadata to the selected plan.
- [ ] Confirmation writes Action Ledger rows only after confirmation.
- [ ] Write-tool `ToolEvent.langsmith_trace_id` values reuse the original planning trace ID.
- [ ] Repeating confirmation does not create duplicate Action Ledger rows.
- [ ] `POST /demo/runs/{run_id}/decline` declines without write-tool execution.
- [ ] Demo responses exclude raw internal IDs and sensitive fields.
- [ ] CORS allows the local Vite demo origins.
- [ ] Existing workflow and benchmark tests still pass.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit, except for unrelated pre-existing changes explicitly left out of the commit.

## 9. Verification Commands

```bash
git switch task21
git switch -c task22
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

## 10. Expected Commit

```text
feat: add web demo API surface
```

## 11. Notes for the Implementer

The current workflow can pause at confirmation but cannot resume the same graph invocation. Keep Task 022 pragmatic: use the workflow runner for initial planning, then add a small deterministic continuation service for Web confirmation.

Do not duplicate the whole workflow. The continuation should only cover the post-confirmation path:

```text
load selected plan
-> confirm plan
-> execute deterministic write actions
-> write feedback
-> record observability
-> return summary
```

If existing code already exposes a trace ID in run metadata by the time this task is implemented, reuse it. Otherwise, persist `WeekendPilotWorkflowResult.trace_id` under demo metadata immediately after `POST /demo/runs`.
