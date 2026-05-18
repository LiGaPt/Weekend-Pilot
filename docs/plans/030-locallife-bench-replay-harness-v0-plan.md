# Plan: 030 LocalLife-Bench Replay Harness v0

## 1. Spec Reference

Spec file:

```text
docs/specs/030-locallife-bench-replay-harness-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `task29`.
- Latest completed commit is `01f9ab4 feat: add locallife bench failure injection v0`.
- Task 029 added deterministic benchmark failure injection and the non-default `family_route_failure_v1` case.
- Task 030 spec must exist at `docs/specs/030-locallife-bench-replay-harness-v0.md` before implementation starts. If it is missing, stop and save the approved spec first.
- Existing benchmark execution entry point is `BenchmarkHarness.run_case()` / `run_cases()` in `backend/app/benchmark/harness.py`.
- Existing benchmark case reports are written by `write_case_report()` in `backend/app/benchmark/reporting.py`.
- Existing benchmark result schemas live in `backend/app/benchmark/schemas.py`.
- Existing report sanitization drops forbidden keys such as `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, and `debug_trace`.
- Replay v0 should compare stable benchmark result summaries only, not unstable IDs, paths, latency, timestamps, or trace data.
- PostgreSQL and Redis are required for replay integration tests because replay reruns cases through `BenchmarkHarness`.
- Working tree may contain unrelated untracked `docs/TASK_WORKFLOW_PROMPTS.md`; do not stage it unless explicitly requested.

## 3. Files to Add

- `docs/plans/030-locallife-bench-replay-harness-v0-plan.md` - this implementation plan.
- `backend/app/benchmark/replay.py` - replay harness, stable summary extraction, comparison, and aggregate replay orchestration.
- `tests/test_benchmark_replay.py` - focused unit tests for replay summaries, comparisons, source report loading, aggregation, and sanitization.
- `tests/integration/test_benchmark_replay_gateway.py` - integration tests that replay a happy-path case and the route failure case through PostgreSQL, Redis, and the existing benchmark harness.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add replay result, replay run report, replay summary, and replay mismatch Pydantic models.
- `backend/app/benchmark/reporting.py` - add replay report writers that reuse the existing sanitizer and write replay-specific JSON reports.
- `backend/app/benchmark/__init__.py` - export replay harness and replay schemas if consistent with existing package exports.
- `tests/test_benchmark_harness.py` - update only if shared report sanitizer expectations need coverage for replay report helpers.
- `README.md` - update only if LocalLife-Bench instructions become misleading without mentioning replay v0.

## 5. Implementation Steps

1. Confirm preconditions:
   - Run `git status --short --branch`.
   - Confirm `docs/specs/030-locallife-bench-replay-harness-v0.md` exists.
   - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` remains unrelated and unstaged.

2. Create a dedicated branch if needed:
   - Recommended branch: `task30`.

3. Run the current focused baseline:
   - `python -m pytest tests/test_benchmark_harness.py tests/test_failure_injection.py -v`
   - If PostgreSQL and Redis are running, also run:
     `python -m pytest tests/integration/test_benchmark_harness_gateway.py -v`

4. Add replay schemas in `backend/app/benchmark/schemas.py`.
   - Add `BenchmarkReplayStatus = Literal["passed", "failed", "error"]`.
   - Add `BenchmarkReplaySummary` with:
     - `status: str | None`
     - `workflow_status: str | None`
     - `observed_tool_names: list[str]`
     - `action_count: int`
     - `injected_failure_count: int`
     - `recovery_actions: list[str]`
   - Add `BenchmarkReplayMismatch` with:
     - `field: str`
     - `source: Any`
     - `replay: Any`
   - Add `BenchmarkReplayCaseResult` with:
     - `schema_version="weekendpilot_benchmark_replay_case_v1"`
     - `case_id`
     - `status`
     - `source`
     - `replay`
     - `mismatches`
     - `replay_benchmark_status`
     - `benchmark_report_path`
     - `replay_report_path`
     - `failure_reasons`
   - Add `BenchmarkReplayRunReport` with:
     - `schema_version="weekendpilot_benchmark_replay_run_v1"`
     - `run_status`
     - `case_results`
     - `passed_count`
     - `failed_count`
     - `error_count`

5. Add replay report writers in `backend/app/benchmark/reporting.py`.
   - Add `write_replay_case_report(result, report_dir) -> str`.
   - Write to `<report_dir>/<case_id>-replay.json`.
   - Add `write_replay_run_report(result, report_dir, filename="replay-run.json") -> str` if useful for aggregate integration tests.
   - Reuse `sanitize_trace_payload()` and `_drop_forbidden_keys()`.
   - Do not change `write_case_report()` output shape.

6. Add `backend/app/benchmark/replay.py`.
   - Define `BenchmarkReplayHarness`.
   - Constructor should accept:
     - `benchmark_harness: BenchmarkHarness`
     - `replay_report_dir: Path | str = "var/benchmark-replays"`
   - Expose:
     - `replay_result(source_result: BenchmarkCaseResult) -> BenchmarkReplayCaseResult`
     - `replay_report(source_report_path: Path | str) -> BenchmarkReplayCaseResult`
     - `replay_results(source_results: Sequence[BenchmarkCaseResult]) -> BenchmarkReplayRunReport`
     - `replay_reports(source_report_paths: Sequence[Path | str]) -> BenchmarkReplayRunReport`

7. Implement source report loading.
   - Read JSON as UTF-8.
   - Parse with `BenchmarkCaseResult.model_validate(payload)`.
   - Missing file, malformed JSON, or validation failure should raise `BenchmarkHarnessError` with a typed, user-safe message.
   - Do not require `run_id`, `trace_id`, or unstable fields to be present.

8. Implement stable summary extraction.
   - Use the source or replay `BenchmarkCaseResult`.
   - Extract `status`, `workflow_status`, and `action_count` directly.
   - Find score `name=="trajectory"` and read `details["observed_tool_names"]`, defaulting to an empty list.
   - Find score `name=="failure_injection"` and read `details["injected_failure_count"]`, defaulting to `0`.
   - Find score `name=="recovery_expectation"` and read `details["observed_recovery_actions"]`, defaulting to an empty list.
   - Convert all tool names and recovery actions to strings.
   - Do not include `run_id`, `trace_id`, `report_path`, `tool_event_id`, `action_id`, timestamps, latency, or trace paths.

9. Implement replay execution.
   - In `replay_result`, call `load_benchmark_case(source_result.case_id)`.
   - Run the case with `self.benchmark_harness.run_case(case)`.
   - If replayed benchmark result has `status=="error"`, return replay status `error` with sanitized failure reasons and write a replay report.
   - Otherwise normalize both source and replay summaries and compare stable fields.

10. Implement stable comparison.
    - Compare exactly these fields:
      - `status`
      - `workflow_status`
      - `observed_tool_names`
      - `action_count`
      - `injected_failure_count`
      - `recovery_actions`
    - For each mismatch, add `BenchmarkReplayMismatch(field=<field>, source=<source_value>, replay=<replay_value>)`.
    - Return replay status `passed` when mismatch list is empty.
    - Return replay status `failed` when mismatch list is non-empty.
    - Always write a replay case report before returning.

11. Implement aggregate replay.
    - `replay_results` should replay each source result independently.
    - Count passed, failed, and error replay case results.
    - Set run status:
      - `error` if any replay case is `error`
      - `failed` if no errors but any replay case is `failed`
      - `passed` otherwise
    - Write aggregate replay report if `write_replay_run_report` was added.

12. Update benchmark package exports.
    - Export `BenchmarkReplayHarness`.
    - Export replay schemas if following current `backend/app/benchmark/__init__.py` style.
    - Do not remove existing exports.

13. Add unit tests in `tests/test_benchmark_replay.py`.
    - Test stable summary extraction from a `BenchmarkCaseResult` with trajectory, failure injection, and recovery expectation scores.
    - Test `replay_result` returns `passed` when a fake harness returns matching stable fields.
    - Test `replay_result` returns `failed` and records mismatch details when action count or workflow status differs.
    - Test replay ignores unstable source/replay `run_id`, `trace_id`, and `report_path`.
    - Test `replay_report` loads a JSON report written by `write_case_report`.
    - Test malformed or missing source report raises `BenchmarkHarnessError`.
    - Test aggregate replay counts passed, failed, and error case results correctly.
    - Test replay report JSON excludes forbidden text: `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, `authorization`, and `debug_trace`.

14. Add integration tests in `tests/integration/test_benchmark_replay_gateway.py`.
    - Reuse fixture patterns from `tests/integration/test_benchmark_harness_gateway.py`.
    - Start with a happy-path source by running `BenchmarkHarness.run_case(load_default_benchmark_cases()[0])`.
    - Replay that source report path with `BenchmarkReplayHarness.replay_report`.
    - Assert replay result status is `passed`.
    - Assert replay summary workflow status is `completed`.
    - Assert replay report path exists and is sanitized.
    - Run source for `load_benchmark_case("family_route_failure_v1")`.
    - Replay the failure source report path.
    - Assert replay result status is `passed`.
    - Assert source and replay workflow status are `failed`.
    - Assert action count is `0`.
    - Assert injected failure count is at least `1`.
    - Assert recovery actions include `stop_safely`.
    - Assert replay report JSON excludes forbidden text.

15. Review README.
    - If the LocalLife-Bench section remains accurate, leave it unchanged.
    - If it implies the harness can only run fresh cases and not replay reports, add a short replay v0 subsection with the focused verification command.
    - Do not add CLI usage unless a CLI was actually added.

16. Run focused unit tests:
    - `python -m pytest tests/test_benchmark_replay.py tests/test_benchmark_harness.py -v`

17. Start required services if needed:
    - `docker compose up -d postgres redis`
    - `python -m alembic upgrade head`

18. Run focused integration tests:
    - `python -m pytest tests/integration/test_benchmark_replay_gateway.py tests/integration/test_benchmark_harness_gateway.py -v`

19. Run broad verification:
    - `python -m pytest -q`
    - `docker compose config`
    - `git diff --check`
    - `git status --short`

20. If replay comparison is flaky:
    - Inspect which stable field differs.
    - Do not switch comparison to raw IDs or unstable paths.
    - Do not loosen source benchmark graders.
    - Only narrow comparison if the field was not listed in Task 030 spec.

21. Review changed files.
    - Confirm no benchmark fixtures were added or modified.
    - Confirm no migrations were added.
    - Confirm no frontend, API, CLI, chaos harness, new failure profile, or write-tool failure injection was added.
    - Confirm generated `var/` reports and traces are not staged.
    - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` is not staged.

22. Commit Task 030 only.

## 6. Testing Plan

- Unit tests:
  - replay summary extracts stable fields from `BenchmarkCaseResult`.
  - replay comparison passes for matching stable summaries.
  - replay comparison fails with explicit mismatch details for stable-field differences.
  - replay ignores unstable identifiers and paths.
  - replay loads sanitized benchmark report JSON from disk.
  - missing, malformed, or invalid source report fails with `BenchmarkHarnessError`.
  - aggregate replay computes passed, failed, error counts and run status.
  - replay report output is sanitized.

- Integration tests:
  - replay a source report for one default happy-path benchmark case.
  - replay a source report for `family_route_failure_v1`.
  - confirm the replay path reruns through existing `BenchmarkHarness`.
  - confirm failure-case replay preserves safe-stop stable fields: failed workflow, zero actions, injected route failure, and `stop_safely`.
  - confirm replay reports are written and sanitized.

- Smoke tests:
  - full backend test suite passes.
  - Docker Compose configuration remains valid.
  - whitespace check passes with `git diff --check`.

## 7. Verification Commands

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add locallife bench replay harness v0
```

Expected commands:

```bash
git status --short
git checkout -b task30
git add docs/specs/030-locallife-bench-replay-harness-v0.md docs/plans/030-locallife-bench-replay-harness-v0-plan.md
git add backend/app/benchmark/replay.py backend/app/benchmark/schemas.py backend/app/benchmark/reporting.py backend/app/benchmark/__init__.py
git add tests/test_benchmark_replay.py tests/integration/test_benchmark_replay_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: add locallife bench replay harness v0"
git push -u origin task30
```

Only stage `README.md` if it was actually modified. Before committing, confirm `.env`, API keys, tokens, secrets, `var/`, `.venv`, caches, `node_modules`, `frontend/dist`, Playwright artifacts, and unrelated `docs/TASK_WORKFLOW_PROMPTS.md` are not staged.

## 9. Out-of-scope Changes

- Do not add chaos harness behavior.
- Do not add L3, L4, or L5 benchmark cases.
- Do not expand the default benchmark suite.
- Do not add or modify benchmark case fixtures.
- Do not add write-tool failure injection.
- Do not add new failure profiles.
- Do not change `route_unavailable_v0` behavior.
- Do not add scheduling, background jobs, or automations.
- Do not add Web demo API endpoints, frontend UI, or Playwright changes.
- Do not add CLI commands unless explicitly approved later.
- Do not add database tables or Alembic migrations.
- Do not add dependencies.
- Do not redesign benchmark scoring or loosen existing graders.
- Do not compare run IDs, trace IDs, raw database IDs, timestamps, latency, generated report paths, or trace paths.
- Do not change `write_case_report()` output shape.
- Do not commit generated reports, local traces, caches, virtual environments, frontend build output, or secrets.
- Do not stage unrelated local files.

## 10. Review Checklist

- [ ] Task 030 spec exists at `docs/specs/030-locallife-bench-replay-harness-v0.md`.
- [ ] Task 030 plan exists at `docs/plans/030-locallife-bench-replay-harness-v0-plan.md`.
- [ ] Replay harness accepts an in-memory `BenchmarkCaseResult`.
- [ ] Replay harness accepts a benchmark case report JSON path.
- [ ] Replay loads fixtures through `load_benchmark_case`.
- [ ] Replay reruns cases through existing `BenchmarkHarness`.
- [ ] Replay compares only the stable fields listed in the spec.
- [ ] Replay ignores unstable IDs, paths, timestamps, latency, and trace data.
- [ ] Matching stable fields produce replay status `passed`.
- [ ] Mismatching stable fields produce replay status `failed` with mismatch details.
- [ ] Benchmark execution errors during replay produce replay status `error`.
- [ ] Aggregate replay status and counts are correct.
- [ ] Happy-path benchmark replay integration test passes.
- [ ] `family_route_failure_v1` replay integration test passes.
- [ ] Replay reports are written as sanitized JSON.
- [ ] Replay report JSON excludes forbidden strings.
- [ ] Existing benchmark report format remains backward compatible.
- [ ] Existing benchmark and failure-injection tests still pass.
- [ ] No benchmark fixtures, migrations, frontend, API, CLI, chaos, or new failure-profile behavior was added.
- [ ] `python -m pytest -q` passed.
- [ ] `docker compose config` passed.
- [ ] `git diff --check` passed.
- [ ] No secrets or generated artifacts were staged.
- [ ] Commit message is `feat: add locallife bench replay harness v0`.
- [ ] Push succeeded or a clear reason for not pushing was reported.

## 11. Handoff Notes

Report back with:

- Branch name.
- Commit hash.
- Files changed.
- Verification commands and pass/fail results.
- Any skipped command and exact environment reason.
- Confirmation that replay compares only stable benchmark fields.
- Confirmation that replay reports are sanitized.
- Confirmation that happy-path and route-failure replay both pass.
- Confirmation that no benchmark fixtures, migrations, frontend, API, CLI, chaos, or new failure profiles changed.
- Confirmation that `docs/TASK_WORKFLOW_PROMPTS.md` was not staged.
- Push result.
- Known limitation: Task 030 adds only deterministic replay of existing benchmark case reports; chaos testing, replay scheduling, richer recovery scoring, CLI workflow, Web replay UI, and L3-L5 benchmark expansion remain future tasks.
