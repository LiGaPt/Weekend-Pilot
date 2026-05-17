# Spec: 029 LocalLife-Bench Failure Injection v0

## 1. Goal

Add the first deterministic failure-injection layer for LocalLife-Bench so benchmark cases can exercise WeekendPilot's failure handling and Task 027 recovery routing without monkeypatch-only tests.

After this task, a benchmark case with a known `failure_profile` should run through the official `WeekendPilotWorkflowRunner`, inject a typed read-tool failure through the Tool Gateway path, produce persisted tool events and sanitized reports, and pass the benchmark when the expected safe-stop recovery behavior occurs. The existing five-case default happy-path suite from Task 028 must remain unchanged and passing.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` says Tool Gateway should support failure injection for benchmark mode, LocalLife-Bench should evaluate full behavior trajectories, and the harness should initialize Mock World, inject tool failures, collect traces/tool events/action ledger data, and generate reports.

The current repository already has:

- A workflow-backed LocalLife-Bench harness.
- `BenchmarkCase.failure_profile`, `WeekendPilotWorkflowRequest.failure_profile`, and persisted `agent_runs.failure_profile`.
- A deterministic Mock World provider behind Tool Gateway.
- Bounded recovery routing v0 that can stop safely and persist recovery metadata.
- Five passing default benchmark cases with `failure_profile=null`.

Task 029 should make the existing `failure_profile` field operational for benchmark-mode read-tool failures. It should not build full replay, chaos testing, L3-L5 benchmarks, or richer recovery intelligence.

## 3. Requirements

- Keep `load_default_benchmark_cases()` returning exactly the five Task 028 happy-path cases in the same deterministic order.
- Keep all default cases passing without any injected failures.
- Add a small deterministic failure-injection profile registry for benchmark mode.
- Support one built-in v0 profile:
  - `route_unavailable_v0`
  - It injects failures for Mock World `check_route` read-tool calls.
  - It must not affect write tools.
- Apply failure injection through the Tool Gateway path so injected failures still create normal `tool_events` rows.
- Injected failure tool events must use `status="failed"`.
- Injected failure `error_json` must be typed and sanitized, with:
  - `error_type="failure_injected"`
  - a user-safe message
  - non-sensitive details including `profile_id`, `rule_id`, `tool_name`, and `injected_error_type`.
- Do not call the underlying provider for a tool invocation that is failed by the failure injector.
- Failure injection must run before read cache reuse so a failure-profile case cannot accidentally pass because an earlier cache entry exists.
- Add or update workflow dependencies so `WeekendPilotWorkflowNodes` can build Tool Gateway with a failure injector derived from `WeekendPilotWorkflowRequest.failure_profile`.
- Keep `WeekendPilotWorkflowRequest` and `WeekendPilotWorkflowResult` field names backward compatible.
- Keep unsupported `tool_profile` / `world_profile` behavior unchanged.
- Add one non-default benchmark fixture:
  - `family_route_failure_v1`
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `failure_profile="route_unavailable_v0"`
  - metadata `suite="locallife_bench_v1"`, `level="L2"`, and `focus="route_failure_safe_stop"`.
- The failure benchmark case must be loadable by `load_benchmark_case("family_route_failure_v1")`.
- The failure benchmark case must not be included in `load_default_benchmark_cases()`.
- Add a loader entry point for non-default failure cases, such as `load_failure_benchmark_cases()`, returning the failure cases in deterministic order.
- Extend benchmark expected-outcome schema only as needed to represent expected failure behavior while preserving existing defaults for happy-path cases.
- Failure-case expected outcome must support:
  - expected workflow status
  - optional expected execution status
  - optional expected feedback status
  - expected workflow error type
  - expected recovery action
  - minimum injected failure count.
- The failure benchmark should pass when:
  - the workflow reaches the expected safe-stop failure status,
  - injected `check_route` failures are recorded,
  - recovery metadata records a stopped recovery attempt,
  - no write action is executed,
  - the report remains sanitized.
- `BenchmarkHarness.run_case(load_benchmark_case("family_route_failure_v1"))` must return `status="passed"` when expected safe-stop behavior occurs.
- `BenchmarkHarness.run_cases(load_failure_benchmark_cases())` must return `run_status="passed"` when all failure-profile cases meet their expected outcomes.
- Benchmark reports must remain sanitized and must not expose `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, or `debug_trace`.
- Persisted benchmark metadata must include the case's `failure_profile` or failure-profile metadata in a sanitized form.
- Unknown failure profiles must produce a typed, sanitized benchmark error result or validation error; they must not silently disable injection.
- Do not require LangSmith credentials, live AMAP APIs, external network calls, frontend services, or new environment variables.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add LLM calls, prompts, model configuration, or LLM-backed agents.
- Do not add real provider support or modify live AMAP behavior.
- Do not add a new Mock World profile.
- Do not modify the existing Mock World fixture unless a test proves a fixture typo blocks this task.
- Do not inject failures into write tools in v0.
- Do not execute write tools before explicit human confirmation.
- Do not add replay harness, chaos harness, benchmark database tables, or migrations.
- Do not implement L3-L5 benchmark cases, dynamic user changes, cross-scenario execution, or full failure recovery scoring.
- Do not redesign benchmark reports beyond the minimum needed to represent expected failure outcomes.
- Do not loosen existing happy-path benchmark graders to hide regressions.
- Do not change the Web demo API response schema, frontend UI, or frontend tests.
- Do not change official workflow node names, confirmation boundary behavior, Action Ledger behavior, or execution workflow semantics.
- Do not add new package dependencies.
- Do not commit generated reports under `var/`, pytest caches, `.venv`, `node_modules`, `frontend/dist`, Playwright artifacts, or unrelated untracked files such as `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

Existing benchmark case input remains:

- `BenchmarkCase.failure_profile: str | None`

Existing workflow request input remains:

- `WeekendPilotWorkflowRequest.failure_profile: str | None`

New or extended benchmark loader behavior:

- `load_benchmark_case("family_route_failure_v1") -> BenchmarkCase`
- `load_failure_benchmark_cases() -> list[BenchmarkCase]`

The default loader remains:

- `load_default_benchmark_cases() -> list[BenchmarkCase]`

Failure injection is configured only from known profile IDs. For v0, the only supported profile is:

```text
route_unavailable_v0
```

### Outputs

For a matched injected tool call, Tool Gateway must write a normal `tool_events` row with:

- `tool_name="check_route"`
- `tool_type="read"`
- `provider="mock_world"`
- `status="failed"`
- `response_json=null`
- sanitized `error_json`
- the workflow trace ID if present.

`BenchmarkHarness.run_case()` for the failure case must return a `BenchmarkCaseResult` with `status="passed"` when the expected failure path is observed.

The workflow result for `family_route_failure_v1` is expected to stop safely before execution:

- `status="failed"`
- `error_json.error_type="recovery_stopped"`
- `action_count=0`
- node history includes `apply_recovery`
- node history does not include `saga_execution_engine`.

### Schemas

The existing `BenchmarkExpectedOutcome` may be extended with backward-compatible defaults similar to:

```json
{
  "required_tool_names": ["search_poi", "check_weather", "check_route"],
  "min_tool_event_count": 8,
  "min_action_count": 0,
  "expected_workflow_status": "failed",
  "expected_execution_status": null,
  "expected_feedback_status": null,
  "expected_error_type": "recovery_stopped",
  "expected_recovery_action": "stop_safely",
  "min_injected_failure_count": 1
}
```

The new failure fixture should follow this shape:

```json
{
  "case_id": "family_route_failure_v1",
  "title": "Family afternoon route failure safe stop",
  "user_input": "This afternoon I want to go out with my wife and 5-year-old child for a few hours. Keep it close by and choose a lighter dinner.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": "route_unavailable_v0",
  "memory_items": [],
  "expected": {
    "required_tool_names": [
      "search_poi",
      "check_weather",
      "get_poi_detail",
      "check_opening_hours",
      "check_queue",
      "check_table_availability",
      "check_ticket_availability",
      "check_route"
    ],
    "min_tool_event_count": 8,
    "min_action_count": 0,
    "expected_workflow_status": "failed",
    "expected_execution_status": null,
    "expected_feedback_status": null,
    "expected_error_type": "recovery_stopped",
    "expected_recovery_action": "stop_safely",
    "min_injected_failure_count": 1
  },
  "metadata": {
    "suite": "locallife_bench_v1",
    "level": "L2",
    "focus": "route_failure_safe_stop"
  }
}
```

Injected tool error JSON should follow this safe shape:

```json
{
  "error_type": "failure_injected",
  "message": "Benchmark failure injected for tool call.",
  "details": {
    "profile_id": "route_unavailable_v0",
    "rule_id": "route_unavailable_v0.check_route",
    "tool_name": "check_route",
    "injected_error_type": "route_infeasible"
  }
}
```

Do not add a schema migration for this task.

## 6. Observability

Task 029 must not add a new telemetry backend.

Existing observability must continue:

- Tool events keep the workflow trace ID.
- Workflow metadata remains under `agent_runs.metadata_json["workflow"]`.
- Bounded-agent metadata remains under `agent_runs.metadata_json["agents"]`.
- Benchmark metadata remains under `agent_runs.metadata_json["benchmark"]`.
- Observability metadata remains under `agent_runs.metadata_json["observability"]` when the workflow reaches summary recording.
- Reports written by `write_case_report` remain sanitized.

Task 029 must add enough sanitized benchmark metadata to identify failure injection behavior:

- `case_id`
- `failure_profile`
- known failure profile metadata or profile ID
- injected failure count in score/report details where useful.

Failure metadata must not include raw action IDs, raw tool event IDs, prompts, secrets, API keys, tokens, raw tracebacks, or debug traces.

## 7. Failure Handling

- If `failure_profile` is `null`, the workflow must behave exactly as it does today.
- If `failure_profile="route_unavailable_v0"`, Mock World `check_route` reads must fail through the injector.
- If a failure profile is unknown, benchmark execution must not silently continue without injection.
- If an injected read failure prevents safe planning, the workflow should stop safely through existing recovery routing and preserve `action_count=0`.
- If injected failure metadata cannot be serialized, benchmark execution should return a typed error result with a sanitized failure reason.
- If PostgreSQL or Redis is unavailable, integration tests may fail explicitly as existing integration tests do; do not add silent fallback storage.
- If a benchmark report cannot be written, preserve existing `BenchmarkHarnessError` behavior.
- If LangSmith upload or local trace buffering fails, preserve existing behavior; failure injection must not make observability failure fatal to completed workflow state.

## 8. Acceptance Criteria

- [ ] `docs/specs/029-locallife-bench-failure-injection-v0.md` exists and matches this task.
- [ ] The existing five default benchmark cases remain unchanged in default ordering.
- [ ] `load_default_benchmark_cases()` still returns exactly five cases.
- [ ] All default cases have no injected failures and still pass.
- [ ] `family_route_failure_v1` is added as a non-default benchmark case.
- [ ] `load_benchmark_case("family_route_failure_v1")` returns a valid `BenchmarkCase`.
- [ ] `load_failure_benchmark_cases()` returns `family_route_failure_v1` in deterministic order.
- [ ] `failure_profile="route_unavailable_v0"` resolves to a known deterministic failure profile.
- [ ] Unknown failure profiles are rejected or reported as typed benchmark errors; they are not ignored.
- [ ] Failure injection applies only to read tools in v0.
- [ ] Failure injection does not call the underlying provider for injected `check_route` calls.
- [ ] Injected `check_route` calls create `tool_events` rows with `status="failed"`.
- [ ] Injected failure `error_json.error_type` is `failure_injected`.
- [ ] Injected failure details include `profile_id`, `rule_id`, `tool_name`, and `injected_error_type`.
- [ ] Injected failure details do not expose secrets, raw action IDs, raw tool event IDs, prompts, tracebacks, or debug traces.
- [ ] `BenchmarkHarness.run_case(load_benchmark_case("family_route_failure_v1"))` returns `status="passed"` when the workflow stops safely as expected.
- [ ] Failure-case benchmark result records `workflow_status="failed"` and `action_count=0`.
- [ ] Failure-case node history includes `apply_recovery`.
- [ ] Failure-case node history does not include `saga_execution_engine`.
- [ ] Persisted workflow recovery metadata records one stopped recovery attempt.
- [ ] Persisted benchmark metadata includes the case ID and sanitized failure profile information.
- [ ] Failure-case report JSON is written and sanitized.
- [ ] Report JSON does not contain `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, or `debug_trace`.
- [ ] No Action Ledger rows are created for the failure case.
- [ ] Existing workflow recovery tests still pass.
- [ ] Existing benchmark integration tests still pass.
- [ ] Existing backend unit tests pass after updates.
- [ ] `docker compose config` passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, `var/`, `.venv`, cache, `node_modules`, `frontend/dist`, Playwright artifact, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_langgraph_workflow.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest -q
docker compose config
git diff --check
git status --short
```

If PostgreSQL or Redis is not running, start required services and apply migrations before integration verification:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 10. Expected Commit

```text
feat: add locallife bench failure injection v0
```

## 11. Notes for the Implementer

Keep this task focused on making `failure_profile` real for benchmark-mode read failures.

The safest implementation path is to add a deterministic injector that Tool Gateway consults before read cache/provider execution, wire it from benchmark case to workflow dependencies, then add one non-default failure benchmark case that expects safe stop and recovery metadata.

Do not make the Validator & Recovery adapter smarter in this task. It is acceptable for the injected route failure case to validate the existing `stop_safely` recovery path. Retry, replay, chaos runs, L3-L5 benchmarks, recovery scoring, and recovery visualization should remain follow-up tasks.

The current untracked `docs/TASK_WORKFLOW_PROMPTS.md` appears unrelated to Task 029. Do not stage or commit it unless the user explicitly adds it to this task.
