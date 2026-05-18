# Spec: 030 LocalLife-Bench Replay Harness v0

## 1. Goal

Add the first deterministic replay harness for LocalLife-Bench so WeekendPilot can rerun a previously produced benchmark case report and verify that stable behavior remains reproducible.

After this task, a sanitized benchmark case report from the existing `BenchmarkHarness` should be usable as a replay source. The replay harness should load the matching benchmark fixture, rerun it through the existing workflow-backed benchmark path, compare stable replay fields, and write a sanitized replay report. This unlocks the blueprint's Replay Harness direction without adding chaos testing, new benchmark difficulty levels, database benchmark tables, or frontend UI.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines the harness as product engineering infrastructure responsible for loading scenarios, initializing Mock World, injecting failures, driving the full workflow, collecting traces/tool events/action ledger data, generating reports, and replaying failed cases.

The current repository already has:

- A workflow-backed LocalLife-Bench harness.
- Five default happy-path benchmark cases from Task 028.
- A non-default route failure benchmark case from Task 029.
- Deterministic failure injection through Tool Gateway for `route_unavailable_v0`.
- Sanitized benchmark case report writing.
- Unit and integration tests for benchmark fixture loading, grading, failure injection, and report sanitization.

Task 030 should add replay capability on top of those existing pieces. It should reuse `BenchmarkHarness`, existing benchmark fixtures, existing graders where practical, and existing report sanitization behavior. It should not redesign benchmark scoring or broaden benchmark coverage.

## 3. Requirements

- Add a replay harness module for LocalLife-Bench v0.
- Replay must use the existing `BenchmarkHarness` to execute benchmark cases through `WeekendPilotWorkflowRunner`.
- Replay input must support a sanitized benchmark case report produced by `write_case_report`.
- Replay input must support an in-memory `BenchmarkCaseResult` for unit tests and future callers.
- Replay must load the matching benchmark fixture using `load_benchmark_case(result.case_id)`.
- Replay must work for default happy-path benchmark cases.
- Replay must work for the non-default `family_route_failure_v1` failure-injection case.
- Replay must compare only stable fields:
  - benchmark result status
  - workflow status
  - tool trajectory by observed tool names from the trajectory score details
  - action count
  - injected failure count from the failure-injection score details
  - recovery action from the recovery expectation score details when present
- Replay must not compare unstable identifiers:
  - `run_id`
  - `trace_id`
  - `report_path`
  - raw database IDs
  - raw action IDs
  - raw tool event IDs
  - latency
  - timestamps
  - generated trace buffer paths
- Replay mismatch must produce a replay result with `status="failed"` and explicit mismatch details; it must not raise unless input loading or schema validation itself is invalid.
- A successful replay must produce `status="passed"` when all stable compared fields match.
- A benchmark execution error during replay must produce `status="error"` with a sanitized failure reason.
- Replay reports must be written as sanitized JSON under a replay-specific report directory, defaulting to a path under `var/`.
- Replay reports must not expose `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, `authorization`, `debug_trace`, traceback text, or raw stack traces.
- Add a replay run report model for multiple case replays with:
  - `run_status`
  - `case_results`
  - `passed_count`
  - `failed_count`
  - `error_count`
- Add a replay case result model with:
  - `case_id`
  - `status`
  - source summary
  - replay summary
  - mismatches
  - replay benchmark result status
  - replay report path
- Export replay harness entry points from `backend.app.benchmark` only if doing so follows current package export patterns.
- Preserve existing `BenchmarkHarness`, `BenchmarkCaseResult`, and `BenchmarkRunReport` public fields.
- Preserve existing benchmark report format; do not break existing report readers or tests.
- Do not require LangSmith credentials, live AMAP APIs, external network calls, frontend services, or new environment variables.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add chaos harness behavior.
- Do not add new L3, L4, or L5 benchmark cases.
- Do not expand the default benchmark suite.
- Do not add write-tool failure injection.
- Do not add new failure profiles.
- Do not change `route_unavailable_v0` behavior.
- Do not add replay scheduling, background jobs, or automations.
- Do not add CLI commands unless required by tests; direct Python APIs are enough for v0.
- Do not add Web demo API endpoints, frontend UI, or Playwright changes.
- Do not add database tables, Alembic migrations, or durable benchmark replay tables.
- Do not add new package dependencies.
- Do not redesign benchmark graders or loosen existing happy-path grading.
- Do not compare raw IDs, timestamps, latency, trace paths, or other unstable fields.
- Do not require generated reports under `var/` to be tracked by git.
- Do not commit generated reports, local traces, caches, virtual environments, `node_modules`, `frontend/dist`, Playwright artifacts, or unrelated untracked files such as `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

Replay must support these input forms:

- A path to a sanitized benchmark case report JSON written by `write_case_report`.
- An in-memory `BenchmarkCaseResult`.

The report must include at minimum:

- `case_id`
- `status`
- `workflow_status`
- `action_count`
- `scores`

Replay must derive stable comparison fields from the source result.

### Outputs

Add replay result schemas similar to:

```json
{
  "schema_version": "weekendpilot_benchmark_replay_case_v1",
  "case_id": "family_afternoon_v1",
  "status": "passed",
  "source": {
    "status": "passed",
    "workflow_status": "completed",
    "observed_tool_names": ["search_poi", "check_weather"],
    "action_count": 2,
    "injected_failure_count": 0,
    "recovery_actions": []
  },
  "replay": {
    "status": "passed",
    "workflow_status": "completed",
    "observed_tool_names": ["search_poi", "check_weather"],
    "action_count": 2,
    "injected_failure_count": 0,
    "recovery_actions": []
  },
  "mismatches": [],
  "benchmark_report_path": "var/benchmarks/family_afternoon_v1.json",
  "replay_report_path": "var/benchmark-replays/family_afternoon_v1-replay.json"
}
```

Add an aggregate replay report similar to:

```json
{
  "schema_version": "weekendpilot_benchmark_replay_run_v1",
  "run_status": "passed",
  "case_results": [],
  "passed_count": 1,
  "failed_count": 0,
  "error_count": 0
}
```

### Schemas

Replay comparison should use a normalized stable summary similar to:

```json
{
  "status": "passed",
  "workflow_status": "completed",
  "observed_tool_names": ["search_poi", "check_weather", "check_route"],
  "action_count": 2,
  "injected_failure_count": 0,
  "recovery_actions": []
}
```

For `family_route_failure_v1`, expected replay summary should include:

```json
{
  "status": "passed",
  "workflow_status": "failed",
  "action_count": 0,
  "injected_failure_count": 1,
  "recovery_actions": ["stop_safely"]
}
```

Exact run IDs, trace IDs, report paths, database IDs, timestamps, and latency must not be part of the comparison contract.

No schema migration is allowed for this task.

## 6. Observability

Task 030 must not add a new telemetry backend.

Replay execution should preserve existing observability behavior because it runs through `BenchmarkHarness` and `WeekendPilotWorkflowRunner`.

Replay reports must include enough sanitized metadata to understand what was replayed:

- `case_id`
- source benchmark result status
- replay benchmark result status
- compared stable fields
- mismatch list
- replay harness version

Replay reports must not include raw action IDs, tool event IDs, API keys, tokens, secrets, authorization headers, raw tracebacks, raw debug traces, prompts, or generated trace file contents.

If replay updates `agent_runs.metadata_json`, the metadata must be sanitized and nested under existing benchmark metadata without breaking current benchmark metadata keys.

## 7. Failure Handling

- If a source report path does not exist, replay must raise or return a typed `BenchmarkHarnessError`.
- If source report JSON is malformed, replay must raise or return a typed `BenchmarkHarnessError`.
- If source report schema is invalid or lacks required stable fields, replay must raise or return a typed `BenchmarkHarnessError`.
- If `case_id` is unknown, replay must preserve existing `load_benchmark_case` error behavior.
- If the replayed benchmark run returns `status="error"`, replay must return a replay case result with `status="error"` and a sanitized reason.
- If stable fields differ, replay must return `status="failed"` with one mismatch entry per differing field.
- If report writing fails, preserve existing benchmark reporting error behavior.
- If PostgreSQL or Redis is unavailable, integration tests may fail explicitly as existing integration tests do; do not add silent fallback storage.
- If LangSmith upload or local trace buffering fails, preserve current workflow behavior; replay must not add new fatal observability dependencies.

## 8. Acceptance Criteria

- [ ] `docs/specs/030-locallife-bench-replay-harness-v0.md` exists and matches this task.
- [ ] A replay harness module exists for LocalLife-Bench v0.
- [ ] Replay can accept an in-memory `BenchmarkCaseResult`.
- [ ] Replay can accept a sanitized benchmark case report JSON path.
- [ ] Replay loads the matching fixture through `load_benchmark_case`.
- [ ] Replay executes cases through existing `BenchmarkHarness`.
- [ ] Replay supports at least one default happy-path case.
- [ ] Replay supports `family_route_failure_v1`.
- [ ] Replay compares benchmark status, workflow status, observed tool names, action count, injected failure count, and recovery actions.
- [ ] Replay does not compare run IDs, trace IDs, report paths, raw database IDs, timestamps, latency, or trace paths.
- [ ] Matching stable fields produce a replay case result with `status="passed"`.
- [ ] A stable-field mismatch produces `status="failed"` and explicit mismatch details.
- [ ] Benchmark execution errors during replay produce `status="error"` with sanitized failure reasons.
- [ ] Aggregate replay reports compute passed, failed, error counts, and run status correctly.
- [ ] Replay reports are written as sanitized JSON.
- [ ] Replay report JSON does not contain `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, `authorization`, `debug_trace`, traceback text, or stack traces.
- [ ] Existing benchmark report format remains backward compatible.
- [ ] Existing default benchmark tests still pass.
- [ ] Existing failure-injection tests still pass.
- [ ] No benchmark database tables or Alembic migrations are added.
- [ ] No frontend, Web demo API, CLI, chaos harness, new failure profile, or new benchmark case is added.
- [ ] Existing backend unit tests pass after updates.
- [ ] Existing benchmark integration tests pass after updates.
- [ ] `docker compose config` passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, `var/`, `.venv`, cache, `node_modules`, `frontend/dist`, Playwright artifact, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_replay.py tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_benchmark_replay_gateway.py tests/integration/test_benchmark_harness_gateway.py -v
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
feat: add locallife bench replay harness v0
```

## 11. Notes for the Implementer

Keep Task 030 focused on deterministic replay of existing benchmark case reports.

The safest implementation path is to add a small replay module that normalizes stable fields from an existing `BenchmarkCaseResult`, reruns the same case through `BenchmarkHarness`, normalizes the replayed result, compares those stable summaries, and writes a sanitized replay report.

Do not add broader replay orchestration, chaos testing, new benchmark cases, migrations, frontend UI, or CLI workflow in this task. Future tasks can build on this v0 replay API to replay failed suites, add richer recovery scoring, or support chaos runs.

The current untracked `docs/TASK_WORKFLOW_PROMPTS.md` appears unrelated to Task 030. Do not stage or commit it unless the user explicitly adds it to this task.
