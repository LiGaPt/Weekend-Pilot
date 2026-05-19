# Spec: 036 Run Trace Benchmark Summary Alignment v0

## 1. Goal

Add the first canonical summary contract for workflow-backed run artifacts so that trace records, internal run inspection, and benchmark reports can reuse the same identity/status/timing envelope instead of each rebuilding overlapping fields differently.

After this task, every workflow-backed run that reaches the current observability path should persist a sanitized `run_summary` under `agent_runs.metadata_json["summary"]`. The same contract should be embedded in local trace JSONL payloads and benchmark case reports, while benchmark suite run reports should expose a compact `benchmark_summary` envelope. This task closes the remaining small M1 contract-alignment gap after Task 033 added workflow timing summaries and benchmark percentiles, and after Tasks 034-035 completed the minimum internal/public view separation.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. `docs/NEXT_PHASE_ROADMAP.md` explicitly prioritizes M1 "evaluation and observability infrastructure" before broader UX expansion, and the remaining M1 work includes:

- unifying `run summary`, `trace summary`, and `benchmark summary` output structure
- making performance, stability, and failure signals easier to compare across cases

The repository already has the core building blocks:

- workflow timing summaries from Task 033
- internal observability read surface from Task 034
- public/internal view redaction from Task 035
- workflow-backed benchmark case and suite reports
- local trace JSONL summaries from Task 017

The current gap is structural:

- `backend/app/observability/context.py` writes a trace payload with one shape
- `backend/app/observability/service.py` reconstructs overlapping fields for internal review with another shape
- `backend/app/benchmark/harness.py` and `backend/app/benchmark/schemas.py` serialize case and suite reports with yet another shape

This task should create one shared canonical `run_summary` contract for the overlap while keeping artifact-specific fields intact. It belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

## 3. Requirements

- Add a shared canonical `run_summary` contract for workflow-backed runs.
- Persist the canonical summary under:

  ```text
  agent_runs.metadata_json["summary"]
  ```

- The canonical `run_summary` must be created during `ObservabilityRecorder.record_run_summary(...)` for workflow-backed runs that already produce local trace summaries.
- `run_summary` v0 must include these fields:
  - `schema_version`
  - `run_id`
  - `trace_id`
  - `case_id`
  - `agent_version`
  - `prompt_version`
  - `tool_profile`
  - `world_profile`
  - `failure_profile`
  - `workflow_status`
  - `selected_plan_id`
  - `plan_status`
  - `execution_status`
  - `feedback_status`
  - `tool_event_count`
  - `action_count`
  - `agent_roles`
  - `workflow_timing_summary`
  - `error`
- `run_summary.error` must be sanitized and compact. It must not expose secrets, raw prompts, raw tool payloads, raw action payloads, auth headers, or stack traces.
- `run_summary` v0 must not absorb these artifact-specific fields:
  - `node_history`
  - `workflow_node_history`
  - `observability_status`
  - benchmark scores
  - benchmark pass/fail aggregate counts
  - raw metadata blobs
- Local trace JSONL payloads written by `ObservabilityRecorder` must add a top-level `run_summary` object.
- The existing top-level trace payload fields must remain unchanged in this task.
- `InternalObservabilityService` must prefer `agent_runs.metadata_json["summary"]` for overlapping top-level fields when it is present and valid.
- `InternalObservabilityService` must fall back to the current reconstruction logic for older runs or malformed stored summaries.
- The internal observability API response shape may stay backward compatible in this task; it does not need a new frontend view or route.
- `BenchmarkCaseResult` and serialized case report JSON must add a top-level `run_summary` object.
- Add a compact `benchmark_summary` contract for suite reports.
- `benchmark_summary` must include:
  - `schema_version`
  - `run_status`
  - `case_count`
  - `passed_count`
  - `failed_count`
  - `error_count`
  - `overall_score`
  - `benchmark_timing_summary`
- `BenchmarkRunReport` and serialized suite `run-report.json` must add a top-level `benchmark_summary` object.
- Existing top-level fields on `BenchmarkCaseResult` and `BenchmarkRunReport` must remain unchanged in this task.
- `BenchmarkReplayHarness` must continue to load case reports and ignore the new additive summary fields in stable replay comparison.
- Update `README.md` to document that:
  - local trace summaries now embed canonical `run_summary`
  - benchmark case reports embed `run_summary`
  - benchmark suite reports embed `benchmark_summary`
- Do not add new environment variables, database tables, Alembic migrations, routes, or package dependencies.

## 4. Non-goals

- Do not change the public demo API or customer-facing UI.
- Do not change the internal observability page UI.
- Do not remove or rename existing top-level summary fields yet.
- Do not move `node_history` or `workflow_node_history` into the canonical `run_summary` in this task.
- Do not move `observability_status` into the canonical `run_summary` in this task.
- Do not change workflow routing, retry budgets, timing instrumentation, or benchmark percentile math.
- Do not redesign benchmark scoring, replay rules, or benchmark fixtures.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, or unrelated local planning files.

## 5. Interfaces and Contracts

### Inputs

This task depends on existing workflow-backed persisted data and artifacts:

- `AgentRun`
- `Plan`
- `ToolEvent`
- `ActionLedger`
- `agent_runs.metadata_json["workflow"]["timing"]`
- `agent_runs.metadata_json["agents"]`
- `agent_runs.metadata_json["observability"]`
- `agent_runs.metadata_json["demo"]`
- local trace summary payload generation in `ObservabilityRecorder`
- benchmark case report generation in `BenchmarkHarness.run_case(...)`
- benchmark suite report generation in `BenchmarkHarness.run_cases(...)`

### Outputs

Additive persisted output:

```text
agent_runs.metadata_json["summary"]
```

Additive trace artifact output:

```text
local trace JSONL payload["run_summary"]
```

Additive benchmark artifact outputs:

```text
BenchmarkCaseResult.run_summary
BenchmarkRunReport.benchmark_summary
```

The internal observability API remains backward compatible, but should consume the canonical summary when available.

### Schemas

Canonical `run_summary` shape:

```json
{
  "schema_version": "weekendpilot_run_summary_v1",
  "run_id": "4dfb35e8-f5a4-4cb8-a2b9-e9c8bd4d4d7a",
  "trace_id": "trace-123",
  "case_id": "family_afternoon_v1",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": null,
  "workflow_status": "completed",
  "selected_plan_id": "a4c5b2d1-3fe3-4f0a-9d2f-5c7a1a3b5d44",
  "plan_status": "executed",
  "execution_status": "succeeded",
  "feedback_status": "completed",
  "tool_event_count": 8,
  "action_count": 2,
  "agent_roles": ["supervisor", "discovery", "dining"],
  "workflow_timing_summary": {
    "schema_version": "workflow_timing_summary_v1",
    "total_duration_ms": 913,
    "stage_count": 6,
    "stages": [
      {
        "node_name": "initialize",
        "attempt_count": 1,
        "total_duration_ms": 4
      }
    ]
  },
  "error": null
}
```

Compact `benchmark_summary` shape:

```json
{
  "schema_version": "weekendpilot_benchmark_summary_v1",
  "run_status": "passed",
  "case_count": 5,
  "passed_count": 5,
  "failed_count": 0,
  "error_count": 0,
  "overall_score": 0.94,
  "benchmark_timing_summary": {
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
    "stages": []
  }
}
```

Notes:

- `run_summary.workflow_timing_summary` may be `null` for older runs.
- `run_summary.error` may be `null` when no safe compact error summary is available.
- `run_summary` is canonical for shared overlap only; artifact-specific details stay outside it.

## 6. Observability

This task is observability and evaluation infrastructure work.

It must add:

- canonical `run_summary` persistence under `agent_runs.metadata_json["summary"]`
- canonical `run_summary` embedding in local trace JSONL payloads
- canonical `run_summary` embedding in benchmark case report payloads
- compact `benchmark_summary` embedding in benchmark suite run reports

It must not add a new telemetry backend.

All new summary artifacts must remain sanitized and must not expose:

- secrets
- API keys
- tokens
- auth headers
- raw prompts
- raw tool request/response bodies
- raw action ledger request/response bodies
- raw stack traces
- raw tracebacks
- raw benchmark fixture blobs

## 7. Failure Handling

- If canonical `run_summary` validation fails during trace recording, the workflow and existing trace recording path must continue; `metadata_json["summary"]` may be absent for that run, and consumers must fall back.
- If `agent_runs.metadata_json["summary"]` is missing on an older run, `InternalObservabilityService` must continue to return the current response by using legacy reconstruction.
- If `agent_runs.metadata_json["summary"]` is malformed, `InternalObservabilityService` and `BenchmarkHarness` must ignore it and use fallback reconstruction rather than failing.
- If a benchmark case report omits `run_summary` due to an additive failure, replay loading and report writing must still work.
- If `benchmark_summary` cannot be built, keep the current benchmark report writing path functional and surface the same benchmark error behavior already used for report failures.
- This task does not need to backfill old `var/` artifacts or rewrite old benchmark reports on disk.

## 8. Acceptance Criteria

- [ ] A shared canonical `run_summary` contract exists for workflow-backed runs.
- [ ] `agent_runs.metadata_json["summary"]` is populated for a workflow-backed run that reaches the current observability path.
- [ ] Local trace JSONL payloads include top-level `run_summary`.
- [ ] Existing top-level trace payload fields remain present and unchanged.
- [ ] `BenchmarkCaseResult` and serialized benchmark case report JSON include `run_summary`.
- [ ] `BenchmarkRunReport` and serialized suite `run-report.json` include `benchmark_summary`.
- [ ] Existing top-level `BenchmarkCaseResult` and `BenchmarkRunReport` fields remain present and unchanged.
- [ ] `InternalObservabilityService` returns the same top-level fields for older runs without `metadata_json["summary"]`.
- [ ] `InternalObservabilityService` prefers the canonical stored summary for overlapping top-level fields when it is present and valid.
- [ ] Benchmark replay tests still pass and do not compare the additive summary fields.
- [ ] `README.md` documents the new `run_summary` and `benchmark_summary` artifact envelopes.
- [ ] No frontend, route, migration, or dependency change is added.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated untracked file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing local context files intentionally left unstaged.

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py -q
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_replay_gateway.py -v
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: align run trace and benchmark summary contracts
```

## 11. Notes for the Implementer

Keep this task additive and M1-scoped.

The safest implementation path is:

1. define one shared canonical `run_summary` contract,
2. build and persist it once in the observability recording layer,
3. reuse it in benchmark artifacts and internal observability fallback/preference logic,
4. leave current top-level artifact fields in place for compatibility.

Do not expand the task into full artifact normalization. In v0, `node_history`, `workflow_node_history`, and `observability_status` remain artifact-specific. If the canonical summary cannot be trusted for an older run, fall back to the current behavior instead of forcing migrations or rewrites.
