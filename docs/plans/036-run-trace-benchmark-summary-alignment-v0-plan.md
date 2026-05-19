# Plan: 036 Run Trace Benchmark Summary Alignment v0

## 1. Spec Reference

Spec file:

```text
docs/specs/036-run-trace-benchmark-summary-alignment-v0.md
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

- Current branch is:

  ```text
  codex/public-demo-contract-redaction-and-view-separation-v0
  ```

- Latest completed numbered task is `035`.
- Latest commit is:

  ```text
  85c6368 feat: redact public demo observability fields
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `035`.
- The latest commit corresponds to the latest numbered task `035`.
- `docs/NEXT_PHASE_ROADMAP.md` still prioritizes M1 before larger UX or scenario-expansion work; the remaining actionable M1 gap is summary-structure alignment.
- Current pre-existing local context files remain untracked:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- These files are not part of Task 036 and must remain unstaged.
- Focused baseline tests already pass in the current workspace:
  - `python -m pytest tests/test_observability.py tests/test_benchmark_harness.py -q`
  - `python -m pytest tests/test_demo_api.py -q`
- A fresh task branch should be created from the current `HEAD` before implementation.

## 3. Files to Add

- `backend/app/observability/summary.py` - canonical `RunSummary` and `RunErrorSummary` models plus load/build helpers for shared workflow-backed run summaries.

## 4. Files to Modify

- `README.md` - document the new `run_summary` and `benchmark_summary` artifact envelopes.
- `backend/app/observability/context.py` - build `run_summary`, embed it in trace payloads, and persist `metadata_json["summary"]`.
- `backend/app/observability/service.py` - prefer canonical stored summary for overlapping top-level fields, with fallback to current reconstruction.
- `backend/app/benchmark/schemas.py` - add `run_summary` to `BenchmarkCaseResult` and `BenchmarkSummary` / `benchmark_summary` to `BenchmarkRunReport`.
- `backend/app/benchmark/harness.py` - attach canonical summaries to benchmark case and suite results.
- `tests/test_observability.py` - unit coverage for summary build, persistence, redaction, and fallback behavior.
- `tests/integration/test_langgraph_workflow_gateway.py` - assert workflow trace payloads and persisted run metadata include canonical summary.
- `tests/integration/test_observability_gateway.py` - assert internal observability still returns the current top-level shape while using canonical summary-backed values.
- `tests/test_benchmark_harness.py` - assert benchmark case and suite report writers serialize canonical summary envelopes.
- `tests/integration/test_benchmark_harness_gateway.py` - assert workflow-backed benchmark runs persist and emit canonical summary envelopes.
- `tests/test_benchmark_replay.py` - regression that additive `run_summary` does not affect replay stability.

## 5. Implementation Steps

1. Create a fresh task branch before editing.
   - Use a new branch name such as:

     ```text
     codex/run-trace-benchmark-summary-alignment-v0
     ```

   - Confirm the existing local context files remain unstaged:
     - `docs/NEXT_PHASE_ROADMAP.md`
     - `docs/TASK_WORKFLOW_PROMPTS.md`
     - `var/`

2. Add the shared canonical summary helper in `backend/app/observability/summary.py`.
   - Define `RunErrorSummary` with:
     - `error_type`
     - `message`
     - `source`
     - `details`
   - Define `RunSummary` with exactly these fields:
     - `schema_version = "weekendpilot_run_summary_v1"`
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
   - Add `load_run_summary(metadata: dict[str, Any]) -> RunSummary | None`.
   - Add `build_run_summary(...) -> RunSummary` using:
     - `AgentRun` for identity/profile fields and `workflow_status`
     - selected `Plan` and `plan_json` for `selected_plan_id`, `plan_status`, `execution_status`, `feedback_status`
     - explicit `tool_event_count` and `action_count` call-site values
     - `metadata["agents"]["results"]` for ordered `agent_roles`
     - `metadata["workflow"]["timing"]` for `workflow_timing_summary`
     - `trace_id_override` first, then `metadata["demo"]["trace_id"]`, then `metadata["observability"]["trace_id"]`
     - sanitized `demo.initial_error` first, then sanitized `observability.error`, otherwise `None`
   - Do not include `node_history`, `workflow_node_history`, or `observability_status` in `RunSummary` v0.

3. Update `backend/app/observability/context.py` to build and persist canonical summary.
   - In `record_run_summary(...)`, fetch once:
     - current run row
     - selected plan
     - `tool_event_count`
     - `action_count`
     - current metadata
   - Build canonical `run_summary` with the new helper before writing the local trace payload.
   - Add top-level `run_summary` to `_summary_payload(...)`.
   - Keep existing top-level trace payload keys unchanged:
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
     - `workflow_timing_summary`
     - `langsmith`
     - `metadata`
   - Persist `metadata["summary"] = sanitize_trace_payload(run_summary.model_dump(mode="json"))` in the same metadata update that already writes `metadata["observability"]`.
   - Do not change `TraceRecordResult`.

4. Update `backend/app/observability/service.py` to prefer canonical summary when present.
   - Parse `summary = load_run_summary(metadata)` once near the top of `get_run_summary(...)`.
   - For overlapping top-level response fields, prefer the canonical summary when available:
     - `trace_id`
     - `tool_event_count`
     - `action_count`
     - `execution_status`
     - `feedback_status`
     - `agent_roles`
     - `workflow_timing_summary`
   - Continue sourcing these fields outside the canonical summary from the existing logic:
     - `status`
     - `case_id`
     - `agent_version`
     - `prompt_version`
     - `tool_profile`
     - `world_profile`
     - `failure_profile`
     - `created_at`
     - `updated_at`
     - `observability_status`
     - `node_history`
     - `observability_summary`
   - If `metadata["summary"]` is missing or invalid, keep the current legacy helper behavior unchanged.

5. Extend benchmark schemas in `backend/app/benchmark/schemas.py`.
   - Import `RunSummary` from `backend.app.observability.summary`.
   - Add to `BenchmarkCaseResult`:

     ```text
     run_summary: RunSummary | None = None
     ```

   - Add `BenchmarkSummary` model with:
     - `schema_version = "weekendpilot_benchmark_summary_v1"`
     - `run_status`
     - `case_count`
     - `passed_count`
     - `failed_count`
     - `error_count`
     - `overall_score`
     - `benchmark_timing_summary`
   - Add to `BenchmarkRunReport`:

     ```text
     benchmark_summary: BenchmarkSummary | None = None
     ```

   - Keep all existing top-level fields unchanged.

6. Populate canonical summary fields in `backend/app/benchmark/harness.py`.
   - In `_run_case(...)`, after `_record_benchmark_metadata(...)`, reload the updated run row and metadata.
   - Attempt `load_run_summary(run_metadata)`.
   - If the stored summary is absent or invalid, build a fallback summary with the shared helper using:
     - current run row
     - selected plan
     - current metadata
     - `workflow_result.trace_id`
     - current tool/action counts
   - Attach `run_summary` to all `BenchmarkCaseResult` construction paths where a run exists:
     - successful workflow-backed case
     - persisted-run-missing fallback
     - workflow error result with `run_id`
   - For unsupported-profile or no-run paths, keep `run_summary=None`.
   - In `run_cases(...)`, build `benchmark_summary` from:
     - final `run_status`
     - `len(results)`
     - `passed_count`
     - `failed_count`
     - `error_count`
     - existing rounded `overall_score`
     - existing `benchmark_timing_summary`
   - Leave existing top-level benchmark fields untouched.

7. Update `README.md`.
   - In the observability section, note that local trace JSONL summaries now embed a canonical `run_summary`.
   - In the benchmark harness section, note that:
     - each case report embeds `run_summary`
     - suite `run-report.json` embeds `benchmark_summary`
   - Keep the update short and implementation-focused.

8. Add unit tests in `tests/test_observability.py`.
   - Add coverage that `record_run_summary(...)`:
     - writes `payload["run_summary"]`
     - persists `agent_runs.metadata_json["summary"]`
     - preserves `workflow_timing_summary`
     - redacts sensitive fields inside `run_summary.error.details`
   - Add coverage that `load_run_summary(...)` returns `None` for malformed stored summaries.
   - Add coverage that `InternalObservabilityService` prefers the stored canonical summary when both the new summary and the legacy fields exist.
   - Keep existing fallback coverage for missing optional metadata.

9. Add integration workflow/observability coverage.
   - In `tests/integration/test_langgraph_workflow_gateway.py`, assert:
     - `run.metadata_json["summary"]["schema_version"] == "weekendpilot_run_summary_v1"`
     - local trace payload includes `run_summary`
     - `payload["run_summary"]["workflow_status"]` matches the run status
   - In `tests/integration/test_observability_gateway.py`, assert:
     - the internal endpoint still returns the current top-level fields
     - those fields match canonical summary-backed values when `metadata["summary"]` exists
     - sensitive keys stay absent from serialized output

10. Add benchmark unit and integration coverage.
    - In `tests/test_benchmark_harness.py`, assert:
      - case report JSON includes `run_summary`
      - suite report JSON includes `benchmark_summary`
      - top-level legacy benchmark fields remain present
    - In `tests/integration/test_benchmark_harness_gateway.py`, assert:
      - workflow-backed benchmark runs persist `metadata_json["summary"]`
      - serialized case report JSON includes `run_summary`
      - serialized suite report JSON includes `benchmark_summary`
      - timing summary and existing benchmark fields still exist

11. Add replay compatibility regression in `tests/test_benchmark_replay.py`.
    - Add one test proving an additive `run_summary` difference between source and replay does not create a mismatch.
    - Do not change `backend/app/benchmark/replay.py` stable compare fields unless a failing test proves a real compatibility bug.

12. Run verification and stage only intended files.
    - Run focused backend unit tests.
    - Run focused integration tests with PostgreSQL and Redis.
    - Run public demo API regressions as smoke coverage because demo confirmation still uses the observability recorder.
    - Confirm `git diff --check` and `git status --short` before commit.
    - Keep unrelated local files unstaged.

## 6. Testing Plan

- Unit tests:
  - canonical `RunSummary` building and validation
  - canonical summary persistence into `agent_runs.metadata_json["summary"]`
  - trace payload serialization of `run_summary`
  - internal observability fallback/preference behavior
  - benchmark case and suite report serialization of `run_summary` / `benchmark_summary`
  - replay ignoring additive `run_summary`
- Integration tests:
  - workflow-backed run persists canonical summary and emits it in local trace payload
  - internal observability endpoint still returns stable top-level fields backed by canonical summary
  - benchmark harness case and suite reports include canonical summary envelopes
- Smoke tests:
  - demo API tests still pass unchanged
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py -q
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_replay_gateway.py -v
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: align run trace and benchmark summary contracts
```

Expected commands:

```bash
git switch -c codex/run-trace-benchmark-summary-alignment-v0
git status --short
git add README.md backend/app/observability/summary.py backend/app/observability/context.py backend/app/observability/service.py backend/app/benchmark/schemas.py backend/app/benchmark/harness.py tests/test_observability.py tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_observability_gateway.py tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py tests/test_benchmark_replay.py docs/specs/036-run-trace-benchmark-summary-alignment-v0.md docs/plans/036-run-trace-benchmark-summary-alignment-v0-plan.md
git diff --cached --check
git commit -m "feat: align run trace and benchmark summary contracts"
git push -u origin codex/run-trace-benchmark-summary-alignment-v0
```

The implementer must confirm these remain unstaged:

- `docs/NEXT_PHASE_ROADMAP.md`
- `docs/TASK_WORKFLOW_PROMPTS.md`
- `var/`
- `.env`
- caches
- virtual environments
- `frontend/dist`
- `node_modules`

## 9. Out-of-scope Changes

- Do not change the public demo contract or customer-facing frontend.
- Do not add or remove API routes.
- Do not remove legacy top-level fields from trace or benchmark artifacts.
- Do not normalize `node_history`, `workflow_node_history`, or `observability_status` into the canonical `run_summary` in this task.
- Do not change workflow routing, benchmark scoring, replay compare fields, or percentile math.
- Do not add database tables, migrations, or dependencies.
- Do not rewrite old `var/` artifacts or backfill historic reports.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, caches, `.venv`, or other local artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/036-run-trace-benchmark-summary-alignment-v0.md`.
- [ ] Workflow-backed runs persist `agent_runs.metadata_json["summary"]`.
- [ ] Local trace JSONL payloads include canonical `run_summary`.
- [ ] Benchmark case reports include canonical `run_summary`.
- [ ] Benchmark suite reports include compact `benchmark_summary`.
- [ ] Existing top-level trace and benchmark fields remain present.
- [ ] Internal observability still returns the current top-level shape and falls back correctly for older runs.
- [ ] Replay stability is unaffected by additive summary fields.
- [ ] `README.md` documents the new artifact envelopes.
- [ ] Focused unit, integration, and smoke tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except intentionally unstaged local context files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/`, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- changed files
- verification commands and results
- commit hash
- push result
- confirmation that legacy top-level trace and benchmark fields were preserved
- confirmation that older runs without `metadata_json["summary"]` still work through fallback logic
- confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged
- any known limitation, especially that `node_history`, `workflow_node_history`, and `observability_status` remain artifact-specific outside the canonical `run_summary` in v0
