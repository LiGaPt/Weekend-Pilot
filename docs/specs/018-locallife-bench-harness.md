# Spec: 018 LocalLife-Bench Harness v0

## 1. Goal

Add a deterministic, file-based LocalLife-Bench harness v0 for WeekendPilot.

The harness should run one or more benchmark scenarios through the full Mock World workflow, record local observability output, grade the trajectory, and write JSON benchmark reports without requiring LangSmith, live providers, CLI, UI, or new database tables.

## 2. Project Context

This task implements the first LocalLife-Bench foundation from `docs/PROJECT_BLUEPRINT.md` after Task 017 observability.

Task 017 made the deterministic product path traceable through:

- `RunTraceContext`
- local JSONL trace summaries
- trace ID propagation into Tool Gateway calls
- `agent_runs.metadata_json["observability"]`

Task 018 should reuse those capabilities and package the deterministic full-flow path as a repeatable benchmark harness.

The first version should stay intentionally small: file-based cases, deterministic graders, JSON reports, and one happy-path Mock World scenario. Database-backed benchmark tables, replay, failure matrices, CLI, and Web demo belong in later tasks.

## 3. Requirements

- Add `backend.app.benchmark`.
- Add typed schemas for:
  - benchmark case definitions
  - expected outcomes
  - grader scores
  - per-case result
  - run report
- Add JSON fixture loading using the Python standard library plus existing project dependencies.
- Include at least one benchmark fixture case:
  - `family_afternoon_v1`
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
- Harness must initialize:
  - benchmark test user
  - active memory items from the case fixture
  - `AgentRun` with case metadata
  - `RunTraceContext` through the Task 017 observability recorder
- Harness must run the full deterministic pipeline:
  - `DeterministicIntentParser`
  - `DeterministicQueryPlanner`
  - `QueryPlanExecutor`
  - `CandidateEnricher`
  - `DeterministicItineraryGenerator`
  - `FinalReviewGate`
  - `ReviewedPlanPersistenceService`
  - `HumanConfirmationService`
  - `DeterministicExecutionWorkflow`
  - `DeterministicFeedbackWriter`
  - `ObservabilityRecorder.record_run_summary`
- Add deterministic graders:
  - trajectory: required tool names were called and minimum tool-event count was met
  - plan quality: a reviewed, selected, safe-to-present plan exists
  - execution safety: execution succeeded and write tools are from the registered write-tool set
  - feedback: feedback is completed and user-safe
- Write one JSON report per case under a caller-provided report directory, defaulting to `var/benchmarks`.
- Report payload must include:
  - `schema_version`
  - `case_id`
  - `status`
  - `run_id`
  - `trace_id`
  - `scores`
  - `overall_score`
  - `tool_event_count`
  - `action_count`
  - `plan_status`
  - `feedback_status`
  - `observability_status`
  - `failure_reasons`
  - `report_path`
- Reports must not include secrets, raw prompts, raw debug traces, `action_id`, or `tool_event_id`.
- Default tests must not make live LangSmith or real provider calls.
- Keep all benchmark output local and untracked.

## 4. Non-goals

- Do not implement LangGraph.
- Do not add LLM agents.
- Do not add database migrations.
- Do not add benchmark tables.
- Do not add CLI commands, API endpoints, or Web UI.
- Do not add complex failure injection or replay.
- Do not add live provider calls.
- Do not require LangSmith credentials or network access.
- Do not add new external dependencies unless unavoidable.
- Do not track `.env`, API keys, tokens, secrets, generated reports, or trace artifacts.

## 5. Interfaces and Contracts

### Public Modules

```text
backend.app.benchmark.__init__
backend.app.benchmark.errors
backend.app.benchmark.schemas
backend.app.benchmark.fixtures
backend.app.benchmark.graders
backend.app.benchmark.harness
backend.app.benchmark.reporting
```

### Fixture Path

```text
backend/app/benchmark/cases/family_afternoon_v1.json
```

### Benchmark Case

```python
class BenchmarkMemoryItem(BaseModel):
    memory_type: str
    key: str
    value_json: dict[str, Any]
    text: str | None = None
    confidence: Decimal = Decimal("1.0")
    status: str = "active"


class BenchmarkExpectedOutcome(BaseModel):
    required_tool_names: list[str]
    min_tool_event_count: int
    min_action_count: int
    expected_execution_status: str = "succeeded"
    expected_feedback_status: str = "completed"


class BenchmarkCase(BaseModel):
    case_id: str
    title: str
    user_input: str
    agent_version: str = "agent-v1"
    prompt_version: str = "prompt-v1"
    tool_profile: str = "mock_world"
    world_profile: str = "family_afternoon"
    failure_profile: str | None = None
    memory_items: list[BenchmarkMemoryItem] = Field(default_factory=list)
    expected: BenchmarkExpectedOutcome
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Result and Report

```python
BenchmarkCaseStatus = Literal["passed", "failed", "error"]


class BenchmarkScore(BaseModel):
    name: str
    score: float
    passed: bool
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCaseResult(BaseModel):
    schema_version: str = "weekendpilot_benchmark_case_result_v1"
    case_id: str
    status: BenchmarkCaseStatus
    run_id: UUID | None = None
    trace_id: str | None = None
    scores: list[BenchmarkScore]
    overall_score: float
    tool_event_count: int
    action_count: int
    plan_status: str | None = None
    feedback_status: str | None = None
    observability_status: str | None = None
    failure_reasons: list[str] = Field(default_factory=list)
    report_path: str | None = None


class BenchmarkRunReport(BaseModel):
    schema_version: str = "weekendpilot_benchmark_run_v1"
    run_status: Literal["passed", "failed", "error"]
    case_results: list[BenchmarkCaseResult]
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
```

### Harness

```python
class BenchmarkHarness:
    harness_version = "locallife_bench_harness_v0"

    def __init__(
        self,
        session: Session,
        cache: JsonRedisCache,
        rate_limiter: FixedWindowRateLimiter,
        report_dir: Path | str = "var/benchmarks",
        trace_buffer_path: Path | str | None = None,
    ) -> None:
        ...

    def run_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        ...

    def run_cases(self, cases: Sequence[BenchmarkCase]) -> BenchmarkRunReport:
        ...
```

### Fixture Loader

```python
def load_benchmark_case(case_id: str) -> BenchmarkCase:
    ...


def load_default_benchmark_cases() -> list[BenchmarkCase]:
    ...
```

## 6. Report Shape

Each case report must be a single JSON object:

```json
{
  "schema_version": "weekendpilot_benchmark_case_result_v1",
  "case_id": "family_afternoon_v1",
  "status": "passed",
  "run_id": "uuid",
  "trace_id": "uuid",
  "scores": [
    {
      "name": "trajectory",
      "score": 1.0,
      "passed": true,
      "reason": "Required tools were called.",
      "details": {}
    }
  ],
  "overall_score": 1.0,
  "tool_event_count": 8,
  "action_count": 2,
  "plan_status": "executed",
  "feedback_status": "completed",
  "observability_status": "recorded",
  "failure_reasons": [],
  "report_path": "var/benchmarks/family_afternoon_v1.json"
}
```

## 7. Failure Handling

- Invalid fixture JSON raises `BenchmarkHarnessError`.
- Unknown benchmark case ID raises `BenchmarkHarnessError`.
- Missing or unsupported `world_profile` fails the case with status `error`.
- Pipeline exceptions should be captured into `BenchmarkCaseResult.failure_reasons` and result status `error`.
- Grader failures should produce result status `failed`, not raise.
- Report directory should be created automatically.
- Report write failure should raise `BenchmarkHarnessError`.
- LangSmith disabled or missing API key must not fail benchmark execution.

## 8. Acceptance Criteria

- [ ] `backend.app.benchmark` is importable.
- [ ] `family_afternoon_v1` fixture loads as a typed `BenchmarkCase`.
- [ ] Harness initializes user memory items for the benchmark user.
- [ ] Harness creates an `AgentRun` with the benchmark `case_id`.
- [ ] Harness runs the full deterministic Mock World path through feedback.
- [ ] Harness records an observability summary.
- [ ] Harness writes a sanitized JSON report for each case.
- [ ] Trajectory grader verifies required tool calls.
- [ ] Plan quality grader verifies selected safe reviewed plan.
- [ ] Execution safety grader verifies successful safe write execution.
- [ ] Feedback grader verifies completed user-safe feedback.
- [ ] Default tests do not require LangSmith credentials or network access.
- [ ] No generated benchmark report or trace artifact is tracked by git.
- [ ] README documents focused benchmark verification.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task18` branch created from `task17`.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 9. Verification Commands

```bash
git switch task17
git switch -c task18
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest
docker compose config
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add locallife bench harness
```

## 11. Notes for the Implementer

Keep Task 018 focused on a deterministic benchmark harness. Reuse the full-flow structure from `tests/integration/test_observability_gateway.py`; do not build CLI, Web demo, replay, failure injection, or database benchmark persistence in this task.
