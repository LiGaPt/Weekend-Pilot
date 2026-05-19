# Plan: 033 Workflow Stage Timing and Benchmark Percentiles v0

## 1. Spec Reference

Spec file:

```text
docs/specs/033-workflow-stage-timing-and-benchmark-percentiles-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `task32`.
- Latest completed numbered task is `032`.
- Latest commit is:

  ```text
  6b27fa6 docs: add competition design document
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `032`.
- There is no newer numbered spec/plan to continue before opening Task 033.
- Current untracked local files include:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- These untracked files are not part of Task 033 and must not be staged.
- The workflow already exposes `node_history`, but not stage durations.
- `ObservabilityRecorder` writes local JSONL summaries, but does not include a workflow timing summary.
- `BenchmarkHarness.run_case(...)` writes one sanitized case report per case.
- `BenchmarkHarness.run_cases(...)` returns aggregate counts, but does not write a suite run report and does not compute percentile timing summaries.
- `BenchmarkReplayHarness` reads benchmark case reports by validating `BenchmarkCaseResult`; additive fields are safe, but stable-field comparison must not change.
- In this planning session:
  - `git diff --check` passed.
  - `tests/test_benchmark_harness.py` passed.
  - `tests/test_benchmark_replay.py` passed.
  - `tests/test_observability.py` could not be verified because the local Docker/PostgreSQL environment was unavailable in-session.

## 3. Files to Add

- `backend/app/workflow/timing.py` - workflow timing record models and `workflow_timing_summary` aggregation helpers.
- `backend/app/benchmark/timing.py` - benchmark suite timing percentile aggregation helpers.

## 4. Files to Modify

- `README.md` - document the new benchmark suite `run-report.json` output and stage percentile report.
- `backend/app/workflow/graph.py` - wrap workflow nodes with additive timing measurement.
- `backend/app/workflow/state.py` - add timing fields to workflow state.
- `backend/app/workflow/schemas.py` - add `workflow_timing_summary` to `WeekendPilotWorkflowResult`.
- `backend/app/workflow/runner.py` - initialize timing state and return the summary in workflow results.
- `backend/app/workflow/nodes.py` - add additive persistence for `agent_runs.metadata_json["workflow"]["timing"]`.
- `backend/app/observability/context.py` - include top-level `workflow_timing_summary` in local trace summary payloads.
- `backend/app/benchmark/schemas.py` - add timing summary fields to case and run reports.
- `backend/app/benchmark/harness.py` - attach case timing summaries, aggregate suite timing summaries, and write suite run reports.
- `backend/app/benchmark/reporting.py` - add benchmark suite run report writing.
- `backend/app/benchmark/replay.py` - keep compatibility explicit in tests and any narrow schema handling if required.
- `tests/test_langgraph_workflow.py` - add graph-level timing wrapper coverage.
- `tests/integration/test_langgraph_workflow_gateway.py` - assert persisted timing summary for awaiting-confirmation, completed, and safe-stop failed runs.
- `tests/test_observability.py` - assert local trace summary includes sanitized workflow timing summary.
- `tests/integration/test_observability_gateway.py` - assert JSONL trace summaries include workflow timing summary in integration flow.
- `tests/test_benchmark_harness.py` - add timing summary and percentile aggregation coverage.
- `tests/integration/test_benchmark_harness_gateway.py` - assert benchmark suite run report writing and timing summary content.
- `tests/test_benchmark_replay.py` - assert replay still works with additive timing fields in case reports.

## 5. Implementation Steps

1. Create the Task 033 branch from the current completed baseline.
   - Confirm the current branch and latest commit:
     ```bash
     git status --short --branch
     git log --oneline -5
     ```
   - Create/switch branch:
     ```bash
     git switch task32
     git switch -c task33
     ```
   - Confirm `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` stay unstaged throughout the task.

2. Add workflow timing models and aggregation helpers in `backend/app/workflow/timing.py`.
   - Define one internal raw record model:
     - `WorkflowNodeTimingRecord`
       - `node_name: str`
       - `attempt_index: int`
       - `duration_ms: int`
   - Define one additive persisted/public stage entry model:
     - `WorkflowStageTimingEntry`
       - `node_name: str`
       - `attempt_count: int`
       - `total_duration_ms: int`
   - Define one additive persisted/public summary model:
     - `WorkflowTimingSummary`
       - `schema_version = "workflow_timing_summary_v1"`
       - `total_duration_ms: int`
       - `stage_count: int`
       - `stages: list[WorkflowStageTimingEntry]`
   - Add helpers:
     - `append_workflow_timing_record(records, node_name, duration_ms) -> list[WorkflowNodeTimingRecord]`
     - `summarize_workflow_timing(records, node_order) -> WorkflowTimingSummary`
   - Rules:
     - `duration_ms` must be `max(1, round(elapsed_seconds * 1000))`
     - repeated node names aggregate by `node_name`
     - stage output order must follow `V1_WORKFLOW_NODE_NAMES`
     - `total_duration_ms` is the sum of all raw invocation durations

3. Extend workflow state and workflow result contracts.
   - In `backend/app/workflow/state.py`, add:
     - `workflow_stage_timings: list[WorkflowNodeTimingRecord]`
     - `workflow_timing_summary: WorkflowTimingSummary | None`
   - In `backend/app/workflow/runner.py` initial state, initialize:
     - `workflow_stage_timings=[]`
     - `workflow_timing_summary=None`
   - In `backend/app/workflow/schemas.py`, add:
     - `workflow_timing_summary: WorkflowTimingSummary | None = None`
   - In `backend/app/workflow/runner.py::_to_result`, carry the final `workflow_timing_summary` through unchanged.

4. Instrument workflow node execution once at the graph layer.
   - In `backend/app/workflow/graph.py`, replace direct `graph.add_node(name, handler)` calls with a small wrapper factory.
   - Wrapper behavior:
     - capture `start = time.perf_counter()`
     - call the original node handler
     - capture `end = time.perf_counter()`
     - compute `duration_ms`
     - read existing timing records from `state.get("workflow_stage_timings", [])`
     - append one raw timing record for the executed node
     - recompute `workflow_timing_summary`
     - merge these fields into the node updates:
       - `workflow_stage_timings`
       - `workflow_timing_summary`
   - Keep existing `node_history` logic untouched; the timing wrapper must not replace or reorder current node updates.
   - Do not change routing helpers or conditional edge logic.

5. Persist the latest workflow timing summary into run metadata from one additive hook in `backend/app/workflow/nodes.py`.
   - Add a new method:
     - `persist_workflow_timing_summary(run_id: UUID, summary: WorkflowTimingSummary) -> None`
   - Behavior:
     - load `AgentRun`
     - deep-copy existing `metadata_json`
     - ensure `metadata["workflow"]` stays a dict
     - set `metadata["workflow"]["timing"] = summary.model_dump(mode="json")`
     - preserve existing keys:
       - `workflow_version`
       - `source`
       - `auto_confirm`
       - `selected_plan_index`
       - `recovery`
     - flush, do not commit
   - In the graph timing wrapper, after computing the summary, resolve `run_id` from:
     - the node updates first
     - then the incoming state
   - If `run_id` exists and `nodes.persist_workflow_timing_summary` is callable, call it best-effort.
   - If this persistence step raises, swallow the timing-persistence exception and return the original workflow updates plus the in-memory timing fields. Do not alter workflow routing or status.

6. Expose the same timing summary through observability.
   - In `backend/app/observability/context.py::_summary_payload`:
     - read `run.metadata_json["workflow"]["timing"]` if present and dict-like
     - copy it to top-level payload key:
       - `workflow_timing_summary`
   - Keep the existing top-level summary fields:
     - `schema_version`
     - `recorder_version`
     - `trace_id`
     - `run_id`
     - `project_name`
     - `status`
     - `tool_event_count`
     - `action_count`
     - `plan_status`
     - `feedback_status`
     - `langsmith`
     - `metadata`
   - Do not add wall-clock timestamps to the local trace summary.

7. Add benchmark timing aggregation in `backend/app/benchmark/timing.py`.
   - Define a small stats model or dict builder for percentile output:
     - `sample_count`
     - `min_ms`
     - `p50_ms`
     - `p95_ms`
     - `p99_ms`
     - `max_ms`
     - `mean_ms`
   - Define a fixed nearest-rank percentile helper:
     - sort ascending
     - `rank = ceil(p * n)`
     - clamp into `[1, n]`
     - return `values[rank - 1]`
   - Define a benchmark suite summary builder:
     - input: `list[BenchmarkCaseResult]`
     - output:
       - `schema_version = "benchmark_timing_summary_v1"`
       - `case_count`
       - `overall_total_duration_ms`
       - ordered per-stage stats
   - Stage aggregation rules:
     - use `case_result.workflow_timing_summary.stages`
     - aggregate `total_duration_ms` across cases for each `node_name`
     - `sample_count` = number of cases that contain the stage
     - `retry_case_count` = number of cases whose stage `attempt_count > 1`
     - output order follows `V1_WORKFLOW_NODE_NAMES`

8. Extend benchmark schemas and report writing.
   - In `backend/app/benchmark/schemas.py`:
     - add `workflow_timing_summary: WorkflowTimingSummary | None = None` to `BenchmarkCaseResult`
     - add `benchmark_timing_summary: dict | BaseModel | None = None` to `BenchmarkRunReport`
     - add `report_path: str | None = None` to `BenchmarkRunReport`
   - In `backend/app/benchmark/reporting.py`:
     - add `write_run_report(result: BenchmarkRunReport, report_dir: Path | str, filename: str = "run-report.json") -> str`
     - reuse existing sanitization path used by case and replay reports
   - Keep report writing UTF-8 JSON and recursive key dropping behavior unchanged.

9. Wire timing summaries into the benchmark harness.
   - In `backend/app/benchmark/harness.py::run_case`:
     - copy `workflow_result.workflow_timing_summary` into `BenchmarkCaseResult.workflow_timing_summary`
     - preserve all existing scoring/status logic
   - In `backend/app/benchmark/harness.py::run_cases`:
     - collect `case_results` as before
     - compute `benchmark_timing_summary = summarize_benchmark_timing(case_results)`
     - build `BenchmarkRunReport` with the new timing summary
     - write the suite report via `write_run_report(...)`
     - return the report with `report_path`
   - Do not change:
     - happy-path case grading
     - failure-injection grading
     - replay stable-field comparison
     - run status calculation semantics

10. Keep replay compatibility explicit.
    - In `backend/app/benchmark/replay.py`, do not add timing fields to `_COMPARE_FIELDS`.
    - Only make a code change here if needed for validation/typing of additive fields.
    - Otherwise leave runtime logic alone and cover compatibility in tests.

11. Update README only where the instructions are materially different.
    - In the LocalLife-Bench section, mention:
      - case reports still write under `var/benchmarks/`
      - suite runs now also write `var/benchmarks/run-report.json`
      - the suite report includes overall and per-stage `P50/P95/P99` timing summaries
    - Keep commands focused and consistent with the current README structure.

12. Add focused unit tests.
    - `tests/test_langgraph_workflow.py`
      - assert graph execution with stub nodes produces `workflow_timing_summary`
      - assert repeated node execution aggregates `attempt_count`
    - `tests/test_observability.py`
      - assert `record_run_summary(...)` includes sanitized `workflow_timing_summary` when run metadata already contains it
    - `tests/test_benchmark_harness.py`
      - assert case report JSON includes `workflow_timing_summary`
      - assert suite timing summary percentile math for a small fixed sample
      - assert suite run report writes `run-report.json`
      - assert report JSON remains sanitized
    - `tests/test_benchmark_replay.py`
      - assert replay still passes when source case reports include additive `workflow_timing_summary`

13. Add focused integration tests.
    - `tests/integration/test_langgraph_workflow_gateway.py`
      - awaiting-confirmation run: `result.workflow_timing_summary` exists and persisted metadata contains `workflow.timing`
      - completed run: same assertion plus existing observability assertions
      - safe-stop failure run: same assertion plus existing recovery assertions
    - `tests/integration/test_observability_gateway.py`
      - assert local JSONL trace output includes top-level `workflow_timing_summary`
    - `tests/integration/test_benchmark_harness_gateway.py`
      - `run_case(...)` result includes `workflow_timing_summary`
      - `run_cases(...)` returns `benchmark_timing_summary`
      - `report_path` exists and points to the suite run report
      - suite run report JSON contains overall stats and at least one per-stage stats entry
      - suite run report JSON remains sanitized

14. Run verification in this order.
    - Bring up services:
      ```bash
      docker compose up -d postgres redis
      python -m alembic upgrade head
      ```
    - Focused unit tests:
      ```bash
      python -m pytest tests/test_langgraph_workflow.py tests/test_observability.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py -v
      ```
    - Focused integration tests:
      ```bash
      python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_replay_gateway.py -v
      ```
    - Optional broader regression:
      ```bash
      python -m pytest -q
      docker compose config
      git diff --check
      git status --short
      ```

15. Commit and push only intended files.
    - Expected commit message:
      ```text
      feat: add workflow stage timing and benchmark percentile reports
      ```
    - Expected commands:
      ```bash
      git status --short
      git add README.md backend/app/workflow backend/app/observability/context.py backend/app/benchmark tests/test_langgraph_workflow.py tests/test_observability.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py docs/specs/033-workflow-stage-timing-and-benchmark-percentiles-v0.md docs/plans/033-workflow-stage-timing-and-benchmark-percentiles-v0-plan.md
      git diff --cached --check
      git commit -m "feat: add workflow stage timing and benchmark percentile reports"
      git push -u origin task33
      ```
    - Before commit, confirm these stay unstaged:
      - `docs/NEXT_PHASE_ROADMAP.md`
      - `docs/TASK_WORKFLOW_PROMPTS.md`
      - `var/`
      - `.env`
      - caches
      - virtual environments
      - `node_modules`
      - `frontend/dist`

## 6. Testing Plan

- Unit tests:
  - workflow timing wrapper creates aggregated per-stage summary
  - repeated node execution increments `attempt_count`
  - observability summary includes sanitized timing summary
  - benchmark suite timing summary computes nearest-rank `P50/P95/P99`
  - case and suite report writers serialize timing summaries and stay sanitized
  - replay still ignores timing summaries for stable comparison
- Integration tests:
  - workflow runs in `awaiting_confirmation`, `completed`, and safe-stop `failed` states all persist `workflow.timing`
  - benchmark harness case and suite runs expose timing summaries and write suite run report
  - local trace JSONL includes `workflow_timing_summary`
- Smoke tests:
  - `python -m pytest -q`
  - `docker compose config`
  - `git diff --check`

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add workflow stage timing and benchmark percentile reports
```

Expected commands:

```bash
git status --short
git add README.md backend/app/workflow backend/app/observability/context.py backend/app/benchmark tests/test_langgraph_workflow.py tests/test_observability.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py docs/specs/033-workflow-stage-timing-and-benchmark-percentiles-v0.md docs/plans/033-workflow-stage-timing-and-benchmark-percentiles-v0-plan.md
git diff --cached --check
git commit -m "feat: add workflow stage timing and benchmark percentile reports"
git push -u origin task33
```

The implementer must confirm `.env`, secrets, `var/`, and unrelated untracked files are not staged.

## 9. Out-of-scope Changes

- Do not change frontend UI, demo API payloads, or Playwright tests.
- Do not add internal observability API endpoints or dashboard pages.
- Do not add benchmark cases, failure profiles, or replay comparison fields.
- Do not change workflow node names, routing, retry budgets, confirmation behavior, or Action Ledger semantics.
- Do not add database tables, Alembic migrations, or new dependencies.
- Do not persist raw timestamps, raw trace bodies, secrets, prompts, or debug traces in timing artifacts.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, caches, virtual environments, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/033-workflow-stage-timing-and-benchmark-percentiles-v0.md`.
- [ ] The implementation stayed within M1 timing/reporting scope.
- [ ] Workflow timing summary is additive and does not change routing or confirmation behavior.
- [ ] `WeekendPilotWorkflowResult` exposes `workflow_timing_summary`.
- [ ] `agent_runs.metadata_json["workflow"]["timing"]` is populated for the covered terminal states.
- [ ] Local trace summaries include top-level `workflow_timing_summary`.
- [ ] Benchmark case reports include `workflow_timing_summary`.
- [ ] Benchmark suite run report includes `benchmark_timing_summary` and `report_path`.
- [ ] Percentile math uses the fixed nearest-rank algorithm from the spec.
- [ ] Replay compatibility was preserved.
- [ ] Focused tests and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/`, or unrelated untracked file was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- Verification commands and results.
- Whether Docker/PostgreSQL/Redis setup was required for verification and whether any environment blocker remained.
- Commit hash.
- Push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any known limitation, especially if timing summaries are still absent for uncaught graph-abort exceptions.
