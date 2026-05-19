# Spec: 033 Workflow Stage Timing and Benchmark Percentiles v0

## 1. Goal

Add the first stage-level timing baseline for the official LangGraph workflow and expose it through benchmark and observability artifacts without changing product behavior.

After this task, every workflow-backed run that reaches a normal terminal state (`awaiting_confirmation`, `completed`, or the current bounded safe-stop `failed` path) should produce a structured `workflow_timing_summary` with total workflow duration and per-stage aggregated durations. The same summary should appear in workflow results, persisted run metadata, local trace summaries, benchmark case reports, and benchmark suite run reports. Benchmark suite reports should also include deterministic `P50`, `P95`, and `P99` timing summaries for total workflow duration and for each executed workflow stage.

This task unlocks the first concrete milestone in `docs/NEXT_PHASE_ROADMAP.md` M1: turning "the workflow runs" into "workflow stages can be measured and compared across cases." It should remain internal infrastructure only. It must not add new frontend pages, new APIs, new database tables, or new benchmark cases.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a benchmark-driven local-life planning and execution system with observable-by-default workflow behavior. `docs/NEXT_PHASE_ROADMAP.md` says the current phase should prioritize M1 "evaluation and observability infrastructure" before frontend separation or broader scenario expansion.

The repository already has the necessary foundations:

- LangGraph workflow routing through `backend.app.workflow`.
- local trace summary recording from Task 017.
- workflow-backed LocalLife-Bench from Task 021.
- expanded benchmark cases, failure injection, and replay from Tasks 028-030.
- optional LLM-backed bounded agents from Task 031.
- a documentation-only Task 032 that does not change runtime behavior.

The current gap is narrow but important:

- workflow results expose `node_history`, but not stage durations;
- local trace summaries include counts and metadata, but not workflow timing summaries;
- benchmark case reports include scores and statuses, but not stage timing summaries;
- benchmark suite runs return aggregate pass/fail counts, but do not write a run report or compute percentile timing summaries.

Task 033 should close that gap for M1 while preserving deterministic routing, Tool Gateway safety, Human Confirmation, Action Ledger behavior, replay compatibility, and current benchmark case semantics.

## 3. Requirements

- Add additive stage timing instrumentation for the official workflow nodes listed in `V1_WORKFLOW_NODE_NAMES`.
- Measure workflow stage duration in integer milliseconds using a monotonic timer.
- Timing instrumentation must not change node routing, workflow status, or node side effects.
- Add a structured `workflow_timing_summary` contract with:
  - `schema_version`
  - `total_duration_ms`
  - `stage_count`
  - ordered per-stage entries
- Each per-stage timing entry must include:
  - `node_name`
  - `attempt_count`
  - `total_duration_ms`
- Repeated execution of the same node during recovery must aggregate into one per-stage entry for that `node_name`, while preserving `attempt_count`.
- `workflow_timing_summary.stages` must follow the stable `V1_WORKFLOW_NODE_NAMES` order and omit stages that were never executed.
- `workflow_timing_summary` must be exposed on `WeekendPilotWorkflowResult`.
- `workflow_timing_summary` must be persisted under:
  - `agent_runs.metadata_json["workflow"]["timing"]`
- The persisted timing summary must be additive to existing workflow metadata and must not remove or overwrite:
  - `workflow_version`
  - `source`
  - `auto_confirm`
  - `selected_plan_index`
  - `recovery`
- Timing summary persistence must work for workflow runs that end in:
  - `awaiting_confirmation`
  - `completed`
  - the current safe-stop `failed` path after bounded recovery
- Add `workflow_timing_summary` to `BenchmarkCaseResult`.
- Extend `BenchmarkRunReport` with:
  - `benchmark_timing_summary`
  - `report_path`
- `BenchmarkHarness.run_cases(...)` must write a suite run report JSON, defaulting to:
  - `var/benchmarks/run-report.json`
  - or the configured benchmark report directory equivalent
- Add a structured `benchmark_timing_summary` contract with:
  - `schema_version`
  - `case_count`
  - overall total-duration stats
  - ordered per-stage percentile stats
- Overall total-duration stats must be computed from `workflow_timing_summary.total_duration_ms` across cases.
- Per-stage stats must be computed from each case's per-stage `total_duration_ms`, using only cases that executed that stage.
- Each per-stage percentile entry must include:
  - `node_name`
  - `sample_count`
  - `retry_case_count`
  - `min_ms`
  - `p50_ms`
  - `p95_ms`
  - `p99_ms`
  - `max_ms`
  - `mean_ms`
- Percentiles must use a fixed nearest-rank method:
  - sort ascending
  - rank = `ceil(percentile * sample_count)`
  - clamp rank into `[1, sample_count]`
  - return the value at `rank - 1`
- `mean_ms` must be rounded to 2 decimal places.
- Add the same `workflow_timing_summary` to local trace summary payloads emitted by `ObservabilityRecorder`.
- Do not persist or expose wall-clock timestamps in benchmark reports or local trace summaries for this task.
- Keep benchmark case report and replay input compatibility backward compatible through additive schema changes only.
- `BenchmarkReplayHarness` stable-field comparison must remain unchanged and must ignore the new timing fields.
- Update benchmark-related documentation in `README.md` to mention the suite run report and percentile timing summary output.
- Do not require LangSmith credentials, live AMAP APIs, new environment variables, or any frontend service to use the new timing reports.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add new benchmark cases, new failure profiles, or new replay comparison fields.
- Do not change workflow routing, node names, retry budgets, confirmation behavior, or Action Ledger semantics.
- Do not add a new frontend page, internal observability API, benchmark API endpoint, or Playwright coverage.
- Do not add database tables, Alembic migrations, or package dependencies.
- Do not redesign benchmark graders beyond additive timing summary support.
- Do not persist raw per-invocation timestamps, raw trace event bodies, raw provider responses, raw prompts, or debug traces.
- Do not attempt to recover timing data for uncaught workflow exceptions that abort `graph.invoke` before a node returns updates.
- Do not stage or commit generated `var/` reports or unrelated untracked files such as `docs/TASK_WORKFLOW_PROMPTS.md` or local planning notes.

## 5. Interfaces and Contracts

### Inputs

This task builds on existing workflow and benchmark inputs:

- `WeekendPilotWorkflowRequest`
- `WeekendPilotWorkflowResult`
- `WeekendPilotWorkflowState`
- `BenchmarkHarness.run_case(case)`
- `BenchmarkHarness.run_cases(cases)`
- existing benchmark case fixtures under `backend/app/benchmark/cases/`

The timing summary is derived only from official workflow node execution and benchmark case results. No new user input or environment variable is required.

### Outputs

Additive workflow output:

- `WeekendPilotWorkflowResult.workflow_timing_summary`

Additive persisted output:

- `agent_runs.metadata_json["workflow"]["timing"]`

Additive benchmark output:

- `BenchmarkCaseResult.workflow_timing_summary`
- `BenchmarkRunReport.benchmark_timing_summary`
- `BenchmarkRunReport.report_path`

Additive observability output:

- local trace payload top-level `workflow_timing_summary`

### Schemas

`workflow_timing_summary` should follow this shape:

```json
{
  "schema_version": "workflow_timing_summary_v1",
  "total_duration_ms": 1284,
  "stage_count": 15,
  "stages": [
    {
      "node_name": "initialize",
      "attempt_count": 1,
      "total_duration_ms": 7
    },
    {
      "node_name": "execute_searches",
      "attempt_count": 2,
      "total_duration_ms": 118
    }
  ]
}
```

`benchmark_timing_summary` should follow this shape:

```json
{
  "schema_version": "benchmark_timing_summary_v1",
  "case_count": 5,
  "overall_total_duration_ms": {
    "sample_count": 5,
    "min_ms": 820,
    "p50_ms": 910,
    "p95_ms": 1140,
    "p99_ms": 1140,
    "max_ms": 1140,
    "mean_ms": 954.2
  },
  "stages": [
    {
      "node_name": "execute_searches",
      "sample_count": 5,
      "retry_case_count": 0,
      "min_ms": 120,
      "p50_ms": 135,
      "p95_ms": 160,
      "p99_ms": 160,
      "max_ms": 160,
      "mean_ms": 139.6
    }
  ]
}
```

Notes:

- `case_count` is the suite size passed to `run_cases`.
- `sample_count` for a stage is the number of case results that contain that stage.
- `retry_case_count` is the number of case results where that stage has `attempt_count > 1`.
- Stage order must match `V1_WORKFLOW_NODE_NAMES`.

## 6. Observability

This task is evaluation/observability infrastructure work.

It must add:

- per-run persisted workflow timing summary in `agent_runs.metadata_json["workflow"]["timing"]`
- top-level `workflow_timing_summary` in local trace JSONL summaries
- benchmark case reports with `workflow_timing_summary`
- benchmark suite run reports with `benchmark_timing_summary`

It must not add a new telemetry backend.

All new timing artifacts must remain sanitized and must not expose:

- secrets
- API keys
- tokens
- authorization headers
- prompts
- debug traces
- raw tracebacks
- raw action IDs
- raw tool event IDs
- raw wall-clock timestamps

If timing metadata is unavailable for a specific run, existing workflow behavior must still be preserved and the artifact should omit the timing summary rather than breaking the product flow.

## 7. Failure Handling

- If timing aggregation fails inside the additive timing wrapper, the wrapper must not change workflow routing or workflow status.
- If timing summary persistence to `agent_runs.metadata_json` fails, existing workflow behavior must continue; the timing summary may be absent from persisted metadata for that run.
- If a benchmark case result lacks `workflow_timing_summary`, `BenchmarkHarness.run_case` should still serialize the case result and preserve existing status/scoring behavior.
- If one or more case results lack timing summaries, the suite `benchmark_timing_summary` should aggregate only available samples.
- If the suite run report cannot be written, preserve existing benchmark reporting error behavior by surfacing a typed benchmark error rather than silently swallowing the failure.
- If PostgreSQL or Redis is unavailable, integration verification may fail explicitly as current workflow and benchmark integration tests already do.
- Replay must remain able to load updated benchmark case reports even when the new timing field is present.
- This task does not need to recover timing information for uncaught workflow exceptions that abort the graph before node updates are returned.

## 8. Acceptance Criteria

- [ ] `docs/specs/033-workflow-stage-timing-and-benchmark-percentiles-v0.md` exists and matches this task.
- [ ] The workflow records additive stage timing data for the official `V1_WORKFLOW_NODE_NAMES`.
- [ ] `WeekendPilotWorkflowResult` exposes `workflow_timing_summary`.
- [ ] `workflow_timing_summary` contains `schema_version`, `total_duration_ms`, `stage_count`, and ordered per-stage entries.
- [ ] Repeated node execution during recovery aggregates into one stage entry with `attempt_count > 1`.
- [ ] `agent_runs.metadata_json["workflow"]["timing"]` is populated for a completed workflow run.
- [ ] `agent_runs.metadata_json["workflow"]["timing"]` is populated for an awaiting-confirmation workflow run.
- [ ] `agent_runs.metadata_json["workflow"]["timing"]` is populated for the existing safe-stop failed workflow run.
- [ ] Local trace JSONL summaries include top-level `workflow_timing_summary`.
- [ ] `BenchmarkCaseResult` includes `workflow_timing_summary`.
- [ ] `BenchmarkHarness.run_cases(...)` writes a suite run report JSON and returns `report_path`.
- [ ] `BenchmarkRunReport` includes `benchmark_timing_summary`.
- [ ] `benchmark_timing_summary` includes overall total-duration stats and per-stage `P50`, `P95`, and `P99`.
- [ ] Percentiles use the fixed nearest-rank method described in this spec.
- [ ] Benchmark stage stats preserve `V1_WORKFLOW_NODE_NAMES` ordering.
- [ ] Benchmark case reports and suite run reports remain sanitized.
- [ ] Benchmark reports do not include raw wall-clock timestamps.
- [ ] `BenchmarkReplayHarness` still loads updated case reports and keeps stable-field comparison unchanged.
- [ ] Existing benchmark happy-path tests still pass.
- [ ] Existing benchmark replay tests still pass.
- [ ] Existing workflow confirmation-boundary behavior still passes.
- [ ] No frontend, Web API, migration, or dependency change is added.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated untracked file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused unit and integration verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_langgraph_workflow.py tests/test_observability.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py -v
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_replay_gateway.py -v
python -m pytest -q
docker compose config
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add workflow stage timing and benchmark percentile reports
```

## 11. Notes for the Implementer

Keep this task strictly inside M1 timing infrastructure.

The safest implementation path is:

1. instrument timing once in the workflow graph wrapper,
2. expose one additive `workflow_timing_summary` contract everywhere,
3. build suite percentile reporting from those case-level summaries,
4. leave replay, UI, APIs, and benchmark case coverage unchanged.

Do not spread timing logic across every workflow node manually if one graph-level wrapper can keep behavior consistent. Do not add wall-clock timestamps to benchmark artifacts. Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, or `var/`.
