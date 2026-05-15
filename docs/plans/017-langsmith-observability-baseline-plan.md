# Plan: 017 LangSmith Observability Baseline

## 1. Spec Reference

Spec file:

```text
docs/specs/017-langsmith-observability-baseline.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task16`.
- Current Task 016 commit is `3225d96 feat: add deterministic feedback writer`.
- `backend/app/feedback` exists and completes the deterministic product chain through feedback.
- `ToolGatewayRequest.langsmith_trace_id` already exists.
- `tool_events.langsmith_trace_id` already exists.
- `AgentRunRepository` does not yet expose metadata update helpers.
- No `backend/app/observability` package exists yet.
- No default test should require real LangSmith credentials or network access.

## 3. Files to Add

- `backend/app/observability/__init__.py` - public exports.
- `backend/app/observability/errors.py` - `ObservabilityError`.
- `backend/app/observability/schemas.py` - trace context and result schemas.
- `backend/app/observability/redaction.py` - recursive sanitizer.
- `backend/app/observability/local_buffer.py` - local JSONL trace writer.
- `backend/app/observability/langsmith_recorder.py` - optional LangSmith post adapter.
- `backend/app/observability/context.py` - context builder and summary recorder.
- `tests/test_observability.py` - unit tests.
- `tests/integration/test_observability_gateway.py` - traced full Mock World integration test.
- `docs/specs/017-langsmith-observability-baseline.md` - Task 017 spec.
- `docs/plans/017-langsmith-observability-baseline-plan.md` - Task 017 plan.

## 4. Files to Modify

- `pyproject.toml` - add `langsmith>=0.1.133,<1.0`.
- `.env.example` - add `LANGSMITH_TRACING=false`, `LANGSMITH_ENDPOINT=`, and `LOCAL_TRACE_BUFFER_PATH=var/traces/weekendpilot-traces.jsonl`.
- `backend/app/core/config.py` - add new observability settings while keeping old fields.
- `backend/app/repositories/runs.py` - add `update_metadata_json`.
- `backend/app/planning/execution.py` - accept optional trace context or trace ID and pass it to `ToolGatewayRequest`.
- `backend/app/planning/enrichment.py` - same trace propagation.
- `backend/app/execution/workflow.py` - same trace propagation for write tools.
- `README.md` - document focused observability tests and optional LangSmith setup.

## 5. Implementation Steps

1. Confirm clean baseline.

```bash
git status --short --branch
git log --oneline -5
```

2. Create `task17` from `task16`.

```bash
git switch task16
git switch -c task17
```

3. Add `langsmith>=0.1.133,<1.0` to `pyproject.toml`.

This version floor is chosen because official docs note FastAPI tracing middleware exists from `langsmith==0.1.133`; Task 017 does not need middleware yet, but the dependency should be new enough for future compatibility.

4. Extend settings.

Add:

```python
langsmith_tracing: bool = False
langsmith_endpoint: str | None = None
local_trace_buffer_path: str = "var/traces/weekendpilot-traces.jsonl"
```

Keep existing `langchain_tracing_v2` as a legacy compatibility field.

5. Add `AgentRunRepository.update_metadata_json`.

Behavior:

- Load run by ID.
- Return `None` if missing.
- Replace `metadata_json` with supplied dict.
- Flush and refresh.
- Do not commit.

6. Add observability schemas.

Required schemas:

- `RunTraceContext`
- `LangSmithPostStatus`
- `TraceRecordResult`

`TraceRecordResult` should include:

```text
run_id
trace_id
status
local_buffer_written
local_buffer_path
langsmith_enabled
langsmith_posted
error_json
recorder_version
```

7. Add recursive redaction.

Rules:

- Redact dict keys containing case-insensitive:
  - `api_key`
  - `token`
  - `secret`
  - `password`
  - `authorization`
  - `prompt`
  - `debug_trace`
- Redact values by replacing with `"[REDACTED]"`.
- Preserve non-sensitive structure.

8. Add local buffer writer.

Behavior:

- Create parent directory if missing.
- Append one JSON object per line.
- Use UTF-8.
- Do not include secrets or raw debug traces.
- Return structured success/failure data.

9. Add optional LangSmith recorder.

Behavior:

- Disabled unless `settings.langsmith_tracing is True` and `settings.langsmith_api_key` exists.
- Use `langsmith.trace` or a thin wrapper around it to post a top-level run summary.
- Pass `project_name=settings.langsmith_project`.
- Capture and return errors instead of raising by default.
- Unit tests should use a fake recorder; no live network calls.

10. Add `ObservabilityRecorder`.

Responsibilities:

- Build `RunTraceContext` from `AgentRun`.
- Query related `ToolEvent`, `ActionLedger`, and selected `Plan` rows.
- Build sanitized trace summary.
- Write local JSONL buffer.
- Optionally post LangSmith summary.
- Update `agent_runs.metadata_json["observability"]`.

11. Propagate trace ID into Tool Gateway callers.

Update method signatures in a backward-compatible way:

```python
def execute_initial_calls(..., langsmith_trace_id: str | None = None)
def enrich(..., langsmith_trace_id: str | None = None)
def execute_confirmed_plan(..., langsmith_trace_id: str | None = None)
```

When present, pass it to each `ToolGatewayRequest`.

Existing tests should continue passing without changes.

12. Add unit tests in `tests/test_observability.py`.

Required coverage:

- context builds from `AgentRun`
- local buffer creates parent directory and writes JSONL
- sanitizer redacts sensitive keys recursively
- LangSmith recorder does nothing when disabled
- missing API key does not attempt upload
- recorder updates `agent_runs.metadata_json["observability"]`
- repository metadata update does not self-commit

13. Add integration test in `tests/integration/test_observability_gateway.py`.

Flow:

```text
create run
-> build trace context
-> parse intent
-> build query plan
-> execute read calls with trace ID
-> enrich with trace ID
-> generate itinerary
-> final review
-> persist/select/confirm
-> execute confirmed actions with trace ID
-> feedback writer
-> record run summary
```

Assertions:

- all new Tool Event rows for traced calls have the trace ID
- local trace JSONL exists and contains one sanitized summary
- run metadata contains observability status
- feedback remains user-safe
- no live LangSmith upload occurs in default test

14. Update README with:

````markdown
## LangSmith Observability Baseline

Default tests use a local JSONL trace buffer and do not require LangSmith credentials.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -v
```

Optional LangSmith tracing can be enabled locally with `.env` values only:

```bash
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=weekend-pilot
LANGSMITH_API_KEY=your-local-key
LOCAL_TRACE_BUFFER_PATH=var/traces/weekendpilot-traces.jsonl
```
````

15. Run focused verification.

```bash
python -m pytest tests/test_observability.py -v
python -m pytest tests/integration/test_observability_gateway.py -v
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
git add pyproject.toml .env.example README.md backend/app/core/config.py backend/app/repositories/runs.py backend/app/planning/execution.py backend/app/planning/enrichment.py backend/app/execution/workflow.py backend/app/observability tests/test_observability.py tests/integration/test_observability_gateway.py docs/specs/017-langsmith-observability-baseline.md docs/plans/017-langsmith-observability-baseline-plan.md
git commit -m "feat: add langsmith observability baseline"
git push origin task17
```

## 6. Testing Plan

- Unit tests:
  - trace context creation
  - metadata update
  - redaction
  - local JSONL buffer
  - disabled LangSmith behavior
  - no self-commit behavior
- Integration tests:
  - full Mock World path with trace ID propagation
  - local trace summary written
  - run metadata updated
  - no default LangSmith network upload
- Smoke tests:
  - `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py -v
python -m pytest tests/integration/test_observability_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add langsmith observability baseline
```

Expected push target:

```text
origin/task17
```

## 9. Out-of-scope Changes

- Do not implement LangGraph orchestration.
- Do not add bounded LLM agents.
- Do not add benchmark cases or graders.
- Do not add API, CLI, or Web UI.
- Do not require LangSmith credentials for default tests.
- Do not upload live LangSmith traces unless explicitly enabled through local `.env`.
- Do not log or persist API keys, tokens, prompts, secrets, or raw debug traces.
- Do not modify provider behavior or Tool Gateway status semantics.

## 10. Review Checklist

- [ ] Implementation matches `docs/specs/017-langsmith-observability-baseline.md`.
- [ ] Local product path works without LangSmith credentials.
- [ ] Trace ID propagates into Tool Gateway requests and `tool_events.langsmith_trace_id`.
- [ ] Local JSONL trace buffer writes sanitized summaries.
- [ ] Run metadata records observability status.
- [ ] LangSmith failures cannot fail the product workflow.
- [ ] No secrets, prompts, or debug traces are persisted in trace summaries.
- [ ] Focused tests pass.
- [ ] Full `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Commit message is `feat: add langsmith observability baseline`.
- [ ] Push to `origin/task17` succeeds.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Verification commands and results.
- Whether any live LangSmith behavior was intentionally skipped.
- Commit hash.
- Push result.
- Any deviations from this spec/plan.
- Recommended Task 018 direction: LocalLife-Bench harness or CLI demo.
