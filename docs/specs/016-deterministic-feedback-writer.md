# Spec: 016 Deterministic Feedback Writer

## 1. Goal

Add a deterministic Feedback Writer that turns execution results into a user-safe final response.

After Task 015, WeekendPilot can execute confirmed actions through Tool Gateway and persist execution metadata in `plans.plan_json["execution"]`. Task 016 should consume that selected executed plan, summarize which actions completed or failed, update the run status, and persist a final feedback payload in `plans.plan_json["feedback"]`.

This task must be deterministic service code, not a free-form agent or LLM call.

## 2. Project Context

This task implements the final `write_feedback` node from `docs/PROJECT_BLUEPRINT.md`:

```text
wait_confirmation
-> execute
-> write_feedback
```

It supports these blueprint requirements:

- Final response accurately reflects which actions succeeded or failed.
- Partial failures are visible.
- Internal traces, prompts, secrets, tool event IDs, action IDs, and debug data are not exposed to the user.
- Feedback Writer is deterministic and not an autonomous Agent.

Task 016 depends on:

- Task 011 itinerary draft shape.
- Task 013 reviewed plan persistence.
- Task 014 confirmation metadata.
- Task 015 execution summary metadata.

## 3. Requirements

- Add a deterministic feedback writer service.
- Read only selected plans for the requested `run_id`.
- Require `plans.plan_json["schema_version"] == "reviewed_plan_v1"`.
- Require `plans.plan_json["execution"]["schema_version"] == "execution_workflow_v1"`.
- Accept execution statuses:
  - `succeeded`
  - `partially_succeeded`
  - `failed`
  - `skipped`
- Map execution statuses to feedback/run statuses:
  - `succeeded` -> `completed`
  - `partially_succeeded` -> `partially_completed`
  - `failed` -> `failed`
  - `skipped` -> `skipped`
- Generate a structured `ExecutionFeedbackResult`.
- Generate a deterministic user-facing `message`.
- Include completed and failed action summaries.
- Treat `succeeded` and `idempotent_replay` action statuses as completed actions.
- Treat `failed`, `blocked`, and `rate_limited` action statuses as failed actions.
- Derive action target labels from `plan_json["draft"]["activity"]["name"]` or `plan_json["draft"]["dining"]["name"]` when `target_id` matches their `candidate_id`; otherwise use `target_id`.
- Persist feedback metadata in `plans.plan_json["feedback"]`.
- Update `agent_runs.status` through `AgentRunRepository.update_status`.
- Repository and service methods must flush but not commit.
- Re-running the feedback writer should overwrite `plan_json["feedback"]` with the latest deterministic summary and must not create new rows.
- Add unit tests for status mapping, message content, persistence, validation, and no self-commit behavior.
- Add an integration test that runs Mock World planning -> review -> persistence -> selection -> confirmation -> execution -> feedback.
- Add README focused feedback writer test commands.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement LangGraph.
- Do not implement Supervisor, Discovery, Dining, Itinerary Planner, or Validator agents.
- Do not call LLMs.
- Do not execute tools.
- Do not call providers.
- Do not modify Tool Gateway.
- Do not modify Execution Workflow.
- Do not write Action Ledger or Tool Event rows.
- Do not implement recovery routing or compensation.
- Do not implement user feedback learning, memory updates, benchmark graders, API endpoints, CLI, or Web UI.
- Do not add database migrations unless an existing column is missing.
- Do not add LangSmith tracing.

## 5. Interfaces and Contracts

### Inputs

- `run_id: UUID`
- `plan_id: UUID`
- selected executed `plans` row
- `PlanRepository`
- `AgentRunRepository`

### Outputs

- `ExecutionFeedbackResult`
- Updated `plans.plan_json["feedback"]`
- Updated `agent_runs.status`

### Public Modules

Task 016 may add:

```text
backend.app.feedback.__init__
backend.app.feedback.errors
backend.app.feedback.schemas
backend.app.feedback.writer
```

### Feedback Writer Contract

```python
class DeterministicFeedbackWriter:
    writer_version = "deterministic_feedback_writer_v1"

    def __init__(
        self,
        plans: PlanRepository,
        runs: AgentRunRepository,
    ) -> None:
        ...

    def write_execution_feedback(
        self,
        run_id: UUID,
        plan_id: UUID,
    ) -> ExecutionFeedbackResult:
        ...
```

### Schemas

```python
FeedbackStatus = Literal[
    "completed",
    "partially_completed",
    "failed",
    "skipped",
]

FeedbackActionStatus = Literal[
    "completed",
    "already_completed",
    "failed",
    "blocked",
    "rate_limited",
]
```

```python
class FeedbackActionSummary(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: str
    target_id: str
    target_label: str
    status: FeedbackActionStatus
    message: str
    error_code: str | None = None
```

```python
class ExecutionFeedbackResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: FeedbackStatus
    run_status: str
    headline: str
    message: str
    completed_actions: list[FeedbackActionSummary] = Field(default_factory=list)
    failed_actions: list[FeedbackActionSummary] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    writer_version: str
```

### `plan_json["feedback"]` Contract

```json
{
  "schema_version": "execution_feedback_v1",
  "writer_version": "deterministic_feedback_writer_v1",
  "status": "completed",
  "run_status": "completed",
  "headline": "Plan completed.",
  "message": "Plan completed. 2 actions completed and 0 actions need attention.",
  "completed_actions": [],
  "failed_actions": [],
  "next_steps": [],
  "generated_at": "2026-05-15T00:00:00+00:00"
}
```

The feedback payload must not include `tool_event_id`, `action_id`, LangSmith trace IDs, prompts, secrets, or raw debug traces.

## 6. Observability

Task 016 uses existing durable state only:

- Execution details remain in `plans.plan_json["execution"]`.
- User-safe feedback is written to `plans.plan_json["feedback"]`.
- Run completion status is written to `agent_runs.status`.

Task 016 must not add LangSmith tracing or benchmark artifacts.

## 7. Failure Handling

- Missing plan raises `FeedbackWriterError`.
- Wrong-run plan raises `FeedbackWriterError`.
- Unselected plan raises `FeedbackWriterError`.
- Missing run raises `FeedbackWriterError`.
- Missing or malformed `plan_json` raises `FeedbackWriterError`.
- Missing or malformed execution metadata raises `FeedbackWriterError`.
- Unsupported execution or action status raises `FeedbackWriterError`.
- Failed execution actions are summarized as failed feedback actions, not raised.
- Repository and service methods must not commit. Caller owns transaction boundaries.

## 8. Acceptance Criteria

- [ ] `DeterministicFeedbackWriter` exists and is importable.
- [ ] Feedback schemas and errors are importable.
- [ ] Writer accepts only selected plans for the requested run.
- [ ] Writer rejects missing, wrong-run, unselected, and missing-execution plans.
- [ ] Writer maps execution statuses to deterministic feedback/run statuses.
- [ ] Writer produces user-safe `headline`, `message`, completed actions, failed actions, and next steps.
- [ ] Writer does not expose internal IDs, traces, prompts, or secrets in feedback.
- [ ] Writer persists `plans.plan_json["feedback"]`.
- [ ] Writer updates `agent_runs.status`.
- [ ] Writer does not execute tools or call providers.
- [ ] Writer and repositories do not commit.
- [ ] Integration test covers full Mock World path through feedback.
- [ ] README includes focused feedback writer verification commands.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task16` branch created from `task15`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task15
git switch -c task16
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_feedback_writer.py -v
python -m pytest tests/integration/test_feedback_writer_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add deterministic feedback writer
```

## 11. Notes for the Implementer

If Task 015 execution files are missing, stop and report a branch/base mismatch.

Keep Task 016 focused on deterministic execution feedback. Do not add LangGraph, LangSmith, recovery routing, memory learning, benchmark graders, API endpoints, CLI, or Web UI.
