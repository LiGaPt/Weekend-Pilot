# Plan: 018 LocalLife-Bench Harness v0

## 1. Spec Reference

Spec file:

```text
docs/specs/018-locallife-bench-harness.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task17`.
- Current Task 017 commit is `1585239 feat: add langsmith observability baseline`.
- `backend.app.observability` exists and can build trace contexts and write local trace summaries.
- `tests/integration/test_observability_gateway.py` proves the full deterministic Mock World flow can run through feedback.
- `ToolGatewayRequest.langsmith_trace_id` is propagated by planning, enrichment, and execution callers.
- No benchmark package exists yet.
- No benchmark database tables exist and none should be added in Task 018.
- Default tests should not require real LangSmith credentials, real providers, or network access.

## 3. Files to Add

- `backend/app/benchmark/__init__.py` - public exports.
- `backend/app/benchmark/errors.py` - `BenchmarkHarnessError`.
- `backend/app/benchmark/schemas.py` - benchmark case, score, result, and run report schemas.
- `backend/app/benchmark/fixtures.py` - JSON fixture loader.
- `backend/app/benchmark/graders.py` - deterministic graders.
- `backend/app/benchmark/harness.py` - full-flow benchmark runner.
- `backend/app/benchmark/reporting.py` - sanitized JSON report writer.
- `backend/app/benchmark/cases/family_afternoon_v1.json` - first benchmark case fixture.
- `tests/test_benchmark_harness.py` - unit tests.
- `tests/integration/test_benchmark_harness_gateway.py` - full Mock World harness integration test.
- `docs/specs/018-locallife-bench-harness.md` - Task 018 spec.
- `docs/plans/018-locallife-bench-harness-plan.md` - Task 018 plan.

## 4. Files to Modify

- `README.md` - document the focused LocalLife-Bench harness verification command.

No `pyproject.toml` change should be needed because fixture loading and report writing can use the standard library and existing Pydantic/SQLAlchemy dependencies.

## 5. Implementation Steps

1. Confirm clean baseline.

```bash
git status --short --branch
git log --oneline -5
```

2. Create `task18` from `task17`.

```bash
git switch task17
git switch -c task18
```

3. Add `backend/app/benchmark/errors.py`.

Define:

```python
class BenchmarkHarnessError(RuntimeError):
    """Raised when benchmark fixture loading or report writing cannot continue."""
```

4. Add schemas in `backend/app/benchmark/schemas.py`.

Include:

- `BenchmarkMemoryItem`
- `BenchmarkExpectedOutcome`
- `BenchmarkCase`
- `BenchmarkScore`
- `BenchmarkCaseResult`
- `BenchmarkRunReport`

Use the contracts from the spec. Keep result statuses to:

```python
Literal["passed", "failed", "error"]
```

5. Add `backend/app/benchmark/cases/family_afternoon_v1.json`.

Use this shape:

```json
{
  "case_id": "family_afternoon_v1",
  "title": "Family afternoon local-life plan",
  "user_input": "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": null,
  "memory_items": [
    {
      "memory_type": "family",
      "key": "child_age",
      "value_json": { "age": 5 },
      "text": "The child is 5 years old.",
      "confidence": "1.0",
      "status": "active"
    },
    {
      "memory_type": "preference",
      "key": "spouse_lighter_meals",
      "value_json": { "preference": "lighter meals" },
      "text": "The spouse prefers lighter meals.",
      "confidence": "1.0",
      "status": "active"
    }
  ],
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
    "min_action_count": 1,
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed"
  },
  "metadata": {
    "suite": "locallife_bench_v0"
  }
}
```

6. Add fixture loader in `fixtures.py`.

Behavior:

- Use `importlib.resources.files("backend.app.benchmark.cases")`.
- Load UTF-8 JSON.
- Validate through `BenchmarkCase`.
- `load_benchmark_case("family_afternoon_v1")` loads the matching JSON file.
- `load_default_benchmark_cases()` returns `[load_benchmark_case("family_afternoon_v1")]`.
- Raise `BenchmarkHarnessError` for unknown IDs, malformed JSON, or invalid schema.

7. Add deterministic graders in `graders.py`.

Implement pure functions:

- `grade_trajectory(case, tool_events) -> BenchmarkScore`
- `grade_plan_quality(selected_plan) -> BenchmarkScore`
- `grade_execution_safety(execution_result) -> BenchmarkScore`
- `grade_feedback(feedback_result) -> BenchmarkScore`
- `combine_scores(scores) -> tuple[str, float, list[str]]`

Rules:

- Trajectory passes when every required tool appears at least once and total tool events meet `min_tool_event_count`.
- Plan quality passes when selected plan exists, is selected, and its plan JSON has `safe_to_present is True`.
- Execution safety passes when execution status equals the fixture expectation and every action tool is one of `WRITE_TOOLS`.
- Feedback passes when feedback status equals the fixture expectation and feedback text does not contain raw IDs or stack/debug wording.
- Overall status is `passed` only when all scores pass, `failed` when any score fails, and `error` only for exceptions or infrastructure failures.
- Overall score is the arithmetic average of score values rounded to 4 decimals.

8. Add report writer in `reporting.py`.

Behavior:

- Create report directory automatically.
- Write one JSON file named `{case_id}.json`.
- Use `model_dump(mode="json")`.
- Write UTF-8 with sorted keys and indentation.
- Sanitize by reusing Task 017 redaction if available.
- Ensure serialized output does not include:
  - `api_key`
  - `token`
  - `secret`
  - `password`
  - `authorization`
  - `prompt`
  - `debug_trace`
  - `action_id`
  - `tool_event_id`
- Return the report path as a string.

9. Add public exports in `backend/app/benchmark/__init__.py`.

Export:

- `BenchmarkHarness`
- `BenchmarkHarnessError`
- `BenchmarkCase`
- `BenchmarkCaseResult`
- `BenchmarkRunReport`
- `BenchmarkScore`
- `load_benchmark_case`
- `load_default_benchmark_cases`

10. Add `BenchmarkHarness` in `harness.py`.

Constructor inputs:

```python
session: Session
cache: JsonRedisCache
rate_limiter: FixedWindowRateLimiter
report_dir: Path | str = "var/benchmarks"
trace_buffer_path: Path | str | None = None
```

`run_case` flow:

- Create a user with external ID derived from case ID and a UUID suffix.
- Insert fixture memory items through `MemoryItemRepository`.
- Create `AgentRun` with case fields and metadata containing `benchmark_harness_version`.
- Build Mock World gateway with `build_mock_world_registry(case.world_profile)`.
- Build `ObservabilityRecorder` with `LocalTraceBuffer`.
- Build trace context.
- Run parser, planner, initial calls, enrichment, itinerary generation, final review, plan persistence, plan selection, confirmation, execution, feedback, and observability summary.
- Query tool events and selected plan for grading.
- Run graders.
- Build `BenchmarkCaseResult`.
- Write report and set `report_path`.
- Return result.

`run_cases` flow:

- Run each case sequentially.
- Continue after failed grader results.
- Convert unexpected exceptions into `BenchmarkCaseResult(status="error")`.
- Return aggregate counts and average score.

11. Add unit tests in `tests/test_benchmark_harness.py`.

Required tests:

- default fixture loads as `BenchmarkCase`
- unknown case raises `BenchmarkHarnessError`
- trajectory grader passes when required tools are present
- trajectory grader fails when a required tool is missing
- `combine_scores` returns failed status when one score fails
- report writer creates parent directory and JSON file
- report writer output excludes raw IDs and sensitive keys

12. Add integration test in `tests/integration/test_benchmark_harness_gateway.py`.

Reuse the setup style from `tests/integration/test_observability_gateway.py`:

- `SessionLocal`
- Redis runtime with unique prefix
- temporary trace/report paths under `var/test-traces` and `var/test-benchmarks`

Test:

```text
load_default_benchmark_cases()
-> BenchmarkHarness(...).run_case(case)
-> assert result.status == "passed"
-> assert result.run_id is not None
-> assert result.trace_id is not None
-> assert result.tool_event_count >= case.expected.min_tool_event_count
-> assert result.action_count >= case.expected.min_action_count
-> assert result.feedback_status == "completed"
-> assert report JSON exists and matches case_id
-> assert ToolEvent rows for run have the trace ID
-> assert AgentRun metadata has observability trace ID
```

Also assert report JSON does not contain:

```text
action_id
tool_event_id
api_key
token
secret
debug_trace
```

13. Update README.

Add a short section:

````markdown
## LocalLife-Bench Harness

The v0 benchmark harness runs deterministic Mock World cases and writes local JSON reports. It does not require LangSmith credentials or live provider access.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
```
````

14. Run focused verification.

```bash
python -m pytest tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
```

15. Run full verification.

```bash
python -m pytest
docker compose config
git diff --check
git status --short
```

16. Commit and push.

```bash
git add README.md backend/app/benchmark tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py docs/specs/018-locallife-bench-harness.md docs/plans/018-locallife-bench-harness-plan.md
git commit -m "feat: add locallife bench harness"
git push origin task18
```
