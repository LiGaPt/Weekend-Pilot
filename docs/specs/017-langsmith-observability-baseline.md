# Spec: 017 LangSmith Observability Baseline

## 1. Goal

Add a LangSmith-ready observability baseline for WeekendPilot without making LangSmith required for local runs or tests.

After Task 016, WeekendPilot can complete the deterministic Mock World path through feedback writing. Task 017 should add a reusable trace context, local JSONL trace buffer, optional LangSmith run posting, and trace ID propagation into Tool Gateway calls so later LangGraph, LocalLife-Bench, and demo layers can correlate runs, tool calls, actions, execution results, and feedback.

## 2. Project Context

This task implements the observability foundation from `docs/PROJECT_BLUEPRINT.md` section 14.

It supports these requirements:

- Runs, tool calls, latency, recovery/failure metadata, and final results should be traceable.
- LangSmith is the observability layer, but the core product must run when LangSmith is unavailable.
- Tool Gateway already stores durable tool-call metadata in PostgreSQL.
- `tool_events.langsmith_trace_id` already exists and should be populated when a trace context is supplied.

Task 017 depends on:

- Task 005 Tool Gateway pass-through `langsmith_trace_id`.
- Task 015 execution metadata.
- Task 016 feedback metadata.

## 3. Requirements

- Add `backend.app.observability`.
- Add a typed `RunTraceContext` with:
  - `run_id`
  - `trace_id`
  - `project_name`
  - `agent_version`
  - `prompt_version`
  - `tool_profile`
  - `world_profile`
  - `failure_profile`
  - `case_id`
  - `metadata`
- Generate trace IDs as UUID strings.
- Add a local JSONL trace buffer that writes sanitized trace summaries.
- Add an optional LangSmith recorder that posts a top-level run summary only when tracing is enabled and a LangSmith API key is configured.
- LangSmith upload failure must not fail the product workflow.
- Add settings:
  - `langsmith_tracing: bool = False`
  - `langsmith_endpoint: str | None = None`
  - `local_trace_buffer_path: str = "var/traces/weekendpilot-traces.jsonl"`
- Preserve existing `langchain_tracing_v2` for compatibility, but new code should prefer `langsmith_tracing`.
- Add `AgentRunRepository.update_metadata_json`.
- Pass trace ID through existing Tool Gateway callers:
  - `QueryPlanExecutor`
  - `CandidateEnricher`
  - `DeterministicExecutionWorkflow`
- Do not change behavior when no trace context is provided.
- Do not add live LangSmith calls to default tests.
- Do not expose API keys, prompts, raw debug traces, or secrets in local trace payloads.
- Add unit tests for trace context creation, redaction, local JSONL buffering, repository metadata updates, and no-op behavior when LangSmith is disabled.
- Add integration test that runs the full Mock World path and verifies `tool_events.langsmith_trace_id` is populated when trace context is supplied.

## 4. Non-goals

- Do not implement LangGraph.
- Do not add LLM agents.
- Do not add benchmark cases or graders.
- Do not add API endpoints, CLI, or Web UI.
- Do not require a LangSmith account, API key, or network access for tests.
- Do not upload traces in default test runs.
- Do not modify provider behavior.
- Do not add database migrations unless an existing column is missing.
- Do not log secrets, `.env` values, prompts, or raw provider debug payloads.

## 5. Interfaces and Contracts

### Public Modules

```text
backend.app.observability.__init__
backend.app.observability.errors
backend.app.observability.schemas
backend.app.observability.redaction
backend.app.observability.local_buffer
backend.app.observability.langsmith_recorder
backend.app.observability.context
```

### Trace Context

```python
class RunTraceContext(BaseModel):
    run_id: UUID
    trace_id: str
    project_name: str
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    failure_profile: str | None = None
    case_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Recorder

```python
class ObservabilityRecorder:
    recorder_version = "observability_recorder_v1"

    def __init__(
        self,
        runs: AgentRunRepository,
        tool_events: ToolEventRepository,
        action_ledger: ActionLedgerRepository,
        plans: PlanRepository,
        local_buffer: LocalTraceBuffer,
        langsmith: LangSmithRecorder | None = None,
    ) -> None:
        ...

    def build_context(self, run_id: UUID) -> RunTraceContext:
        ...

    def record_run_summary(self, context: RunTraceContext) -> TraceRecordResult:
        ...
```

### Local Trace JSONL Shape

Each line must be one JSON object:

```json
{
  "schema_version": "weekendpilot_trace_v1",
  "recorder_version": "observability_recorder_v1",
  "trace_id": "uuid",
  "run_id": "uuid",
  "project_name": "weekend-pilot",
  "status": "completed",
  "tool_event_count": 8,
  "action_count": 2,
  "plan_status": "executed",
  "feedback_status": "completed",
  "langsmith": {
    "enabled": false,
    "posted": false,
    "error": null
  },
  "metadata": {}
}
```

## 6. Observability

This task is itself observability work.

It must create:

- local JSONL trace summaries
- optional LangSmith top-level run summaries
- `tool_events.langsmith_trace_id` propagation
- `agent_runs.metadata_json["observability"]` update with trace ID, recorder version, local buffer result, and LangSmith post status

LangSmith failure should be represented as `observability_failed` metadata, not as workflow failure.

## 7. Failure Handling

- Missing run raises `ObservabilityError`.
- Missing local trace directory should be created automatically.
- Local trace buffer write failure returns a failed `TraceRecordResult` and updates run metadata; it should not corrupt existing run data.
- LangSmith disabled means no network attempt.
- LangSmith API key missing means no network attempt.
- LangSmith post failure is captured in result metadata and must not raise unless the caller explicitly opts into strict mode.
- Redaction must remove keys containing `api_key`, `token`, `secret`, `password`, `authorization`, `prompt`, or `debug_trace`.

## 8. Acceptance Criteria

- [ ] `backend.app.observability` is importable.
- [ ] `RunTraceContext` is typed and generated from `AgentRun`.
- [ ] Local JSONL trace buffer writes sanitized trace summaries.
- [ ] Optional LangSmith recorder is disabled by default.
- [ ] Missing LangSmith API key does not fail tests or local product runs.
- [ ] Tool Gateway callers pass trace IDs when a trace context is supplied.
- [ ] Existing callers without trace context keep current behavior.
- [ ] `tool_events.langsmith_trace_id` is populated in traced integration flow.
- [ ] `agent_runs.metadata_json["observability"]` is updated.
- [ ] Local trace payloads do not include secrets, prompts, raw debug traces, `action_id`, or `tool_event_id`.
- [ ] No live LangSmith upload happens in default tests.
- [ ] README documents local trace buffer and optional LangSmith env vars.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task17` branch created from `task16`.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 9. Verification Commands

```bash
git switch task16
git switch -c task17
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py -v
python -m pytest tests/integration/test_observability_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add langsmith observability baseline
```

## 11. Notes for the Implementer

Keep this task focused on observability primitives and trace propagation. Do not build LangGraph orchestration, benchmark harnesses, CLI, Web UI, or new agents in Task 017.
