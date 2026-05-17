# Spec: 028 LocalLife-Bench Case Expansion v1

## 1. Goal

Expand WeekendPilot's default LocalLife-Bench suite from one happy-path case to a small, stable v1 suite of five workflow-backed benchmark cases.

After this task, `load_default_benchmark_cases()` should return the existing `family_afternoon_v1` case plus four additional deterministic cases that run through the official `WeekendPilotWorkflowRunner` using the existing `mock_world` / `family_afternoon` profile. This gives the project broader benchmark coverage for family local-life planning without adding new providers, new world profiles, failure injection, replay, or richer grader logic.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` says LocalLife-Bench should evaluate the full behavior trajectory of the local-life agent system and should grow after the core workflow is stable. The current repository has:

- A workflow-backed benchmark harness from Tasks 018 and 021.
- Bounded deterministic agent coverage from Task 020.
- V1 workflow state and DAG alignment from Task 026.
- Bounded recovery routing v0 from Task 027.
- One default benchmark fixture: `family_afternoon_v1`.

Task 028 is the next blueprint step after recovery routing: expand LocalLife-Bench cases. It should keep the expansion deliberately small and deterministic. The task should improve benchmark breadth while preserving the current Mock World demo path, PostgreSQL/Redis integration behavior, Action Ledger safety, observability metadata, sanitized benchmark reports, and current workflow-backed harness design.

## 3. Requirements

- Keep the existing `family_afternoon_v1` benchmark case valid and included in the default suite.
- Expand the default benchmark suite to exactly five cases total.
- Add exactly four new benchmark case JSON fixtures under `backend/app/benchmark/cases/`.
- Keep all five default cases on:
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `agent_version="agent-v1"`
  - `prompt_version="prompt-v1"`
- Do not add a new Mock World profile or modify the existing Mock World world fixture unless a test proves a fixture typo blocks all five cases.
- Update benchmark fixture loading so each default case can be loaded by `load_benchmark_case(case_id)`.
- Keep `load_benchmark_case("missing_case")` raising `BenchmarkHarnessError`.
- Use these default case IDs:
  - `family_afternoon_v1`
  - `family_indoor_light_meal_v1`
  - `family_outdoor_quick_dinner_v1`
  - `family_memory_override_v1`
  - `family_citywalk_addon_v1`
- Each new case must be a valid `BenchmarkCase` and include:
  - `case_id`
  - `title`
  - `user_input`
  - `tool_profile`
  - `world_profile`
  - `failure_profile`
  - `memory_items`
  - `expected`
  - `metadata`
- Each new case must include metadata fields:
  - `suite="locallife_bench_v1"`
  - `level` with value `L1` or `L2`
  - `focus` as a short stable string describing what the case is meant to exercise.
- Keep the existing case's behavior compatible; updating its metadata from `locallife_bench_v0` to include v1 suite metadata is allowed only if tests are updated consistently.
- Each new case should use the same required read-tool trajectory as the existing case unless implementation proves a narrower expectation is needed:
  - `search_poi`
  - `check_weather`
  - `get_poi_detail`
  - `check_opening_hours`
  - `check_queue`
  - `check_table_availability`
  - `check_ticket_availability`
  - `check_route`
- Each new case should set `min_tool_event_count` to a stable threshold no higher than the existing full workflow reliably emits.
- Each new case should set `min_action_count` to `1` unless implementation proves all default cases reliably execute more confirmed write actions.
- The benchmark harness must still run all default cases through `WeekendPilotWorkflowRunner` with `auto_confirm=True`.
- `BenchmarkHarness.run_cases(load_default_benchmark_cases())` must produce one report per case and an aggregate report with `run_status="passed"` when all cases pass.
- Benchmark reports must remain sanitized and must not expose `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, or `debug_trace`.
- Agent-run metadata must continue to include benchmark metadata, workflow metadata, agent metadata, and observability metadata for passing integration cases.
- Do not require LangSmith credentials, live AMAP APIs, external network calls, or frontend services to run the benchmark suite.
- Update README benchmark documentation only if current instructions become misleading after the default suite expands.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add LLM calls, prompts, model configuration, or LLM-backed agents.
- Do not add real provider support or modify live AMAP behavior.
- Do not add a new Mock World profile.
- Do not add failure injection, replay harness, chaos harness, benchmark database tables, or benchmark migrations.
- Do not implement L3-L5 benchmark interaction, cross-scenario execution, dynamic user changes, or failure recovery scoring in this task.
- Do not redesign benchmark graders beyond the minimum needed to keep existing reports and the expanded default suite stable.
- Do not change Web demo API response schemas, frontend UI, or frontend tests unless a backend benchmark change unexpectedly breaks an existing contract.
- Do not change the official workflow node names, recovery routing behavior, Action Ledger behavior, confirmation boundary, or execution workflow.
- Do not loosen report sanitization.
- Do not add new package dependencies.
- Do not commit generated reports under `var/`, pytest caches, `.venv`, `node_modules`, `frontend/dist`, Playwright artifacts, or unrelated untracked files such as `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

The benchmark fixture loader remains the public entry point for case loading:

- `load_benchmark_case(case_id: str) -> BenchmarkCase`
- `load_default_benchmark_cases() -> list[BenchmarkCase]`

The benchmark harness entry points remain:

- `BenchmarkHarness.run_case(case: BenchmarkCase) -> BenchmarkCaseResult`
- `BenchmarkHarness.run_cases(cases: Sequence[BenchmarkCase]) -> BenchmarkRunReport`

Each JSON case remains validated by the existing `BenchmarkCase` Pydantic model.

### Outputs

`load_default_benchmark_cases()` must return five `BenchmarkCase` objects in deterministic order:

1. `family_afternoon_v1`
2. `family_indoor_light_meal_v1`
3. `family_outdoor_quick_dinner_v1`
4. `family_memory_override_v1`
5. `family_citywalk_addon_v1`

`BenchmarkHarness.run_cases(load_default_benchmark_cases())` must return a `BenchmarkRunReport` with:

- `case_results` length of five.
- `passed_count` equal to five when the existing workflow behaves correctly.
- `failed_count` equal to zero.
- `error_count` equal to zero.
- `run_status="passed"`.
- `overall_score` computed from the case results as before.

Each case report must still be written as sanitized JSON under the configured report directory.

### Schemas

Do not require a schema migration. The existing benchmark case schema remains valid.

Each new fixture should follow this shape:

```json
{
  "case_id": "family_indoor_light_meal_v1",
  "title": "Family indoor afternoon with lighter meal",
  "user_input": "This afternoon I want an indoor, child-friendly plan for my partner and our 5-year-old. Keep it close by and choose a lighter dinner.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": null,
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
    "min_action_count": 1,
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed"
  },
  "metadata": {
    "suite": "locallife_bench_v1",
    "level": "L2",
    "focus": "indoor_activity_and_lighter_meal"
  }
}
```

The exact `user_input`, `title`, `memory_items`, and metadata focus values may vary by case, but they must remain deterministic, realistic, and compatible with the existing `family_afternoon` Mock World fixture.

## 6. Observability

Task 028 must not add a new telemetry backend.

Existing observability must continue:

- Workflow runs still create trace IDs.
- Tool events still carry workflow trace IDs.
- Benchmark harness metadata remains stored under `agent_runs.metadata_json["benchmark"]`.
- Workflow metadata remains stored under `agent_runs.metadata_json["workflow"]`.
- Bounded-agent metadata remains stored under `agent_runs.metadata_json["agents"]`.
- Observability metadata remains stored under `agent_runs.metadata_json["observability"]`.
- Reports written by `write_case_report` remain sanitized.

Benchmark metadata should identify each case by its own `case_id`, title, harness version, and fixture metadata.

## 7. Failure Handling

- If a requested case ID is not in the default case registry, `load_benchmark_case` must raise `BenchmarkHarnessError`.
- If a case JSON file is missing, malformed, or schema-invalid, loading must raise `BenchmarkHarnessError` with the existing typed error behavior.
- If one expanded default case fails during `run_cases`, the aggregate `BenchmarkRunReport` must report the failed/error case without hiding other case results.
- If PostgreSQL or Redis is unavailable, integration tests may fail explicitly as existing benchmark integration tests do; do not add silent fallback storage.
- If a benchmark report cannot be written, preserve existing `BenchmarkHarnessError` behavior.
- If a case produces a workflow `error`, the harness should continue to serialize a case result with the workflow failure reason, as it does now.
- Observability upload or local trace buffering behavior must not change as part of this task.

## 8. Acceptance Criteria

- [ ] `docs/specs/028-locallife-bench-case-expansion-v1.md` exists and matches this task.
- [ ] The existing `family_afternoon_v1` case remains loadable and valid.
- [ ] Exactly four new benchmark case JSON fixtures are added.
- [ ] `load_default_benchmark_cases()` returns exactly five cases in deterministic order.
- [ ] All five default case IDs can be loaded individually with `load_benchmark_case(case_id)`.
- [ ] `load_benchmark_case("missing_case")` still raises `BenchmarkHarnessError`.
- [ ] Every default case validates as `BenchmarkCase`.
- [ ] Every default case uses `tool_profile="mock_world"` and `world_profile="family_afternoon"`.
- [ ] Every new case includes `metadata.suite`, `metadata.level`, and `metadata.focus`.
- [ ] Unit tests assert the expanded default case count and IDs.
- [ ] Unit tests assert every default fixture includes expected required tools and stable expected execution/feedback status.
- [ ] Integration tests run all default cases through `BenchmarkHarness.run_cases`.
- [ ] Integration tests assert the aggregate benchmark run passes for all five cases.
- [ ] Integration tests assert one sanitized report file is produced per case.
- [ ] Integration tests assert report JSON does not contain `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, or `debug_trace`.
- [ ] Integration tests assert benchmark metadata is stored for each persisted workflow run.
- [ ] The benchmark harness still uses `WeekendPilotWorkflowRunner`.
- [ ] The workflow confirmation boundary and Action Ledger safety remain unchanged.
- [ ] No benchmark grader is loosened just to make cases pass.
- [ ] No new world profile, failure profile, provider support, LLM call, migration, or frontend redesign is added.
- [ ] Existing backend unit tests pass after updates.
- [ ] Existing benchmark integration tests pass after updates.
- [ ] `docker compose config` passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, `var/`, `.venv`, cache, `node_modules`, `frontend/dist`, Playwright artifact, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
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
test: expand locallife bench cases
```

## 11. Notes for the Implementer

Keep this task focused on benchmark breadth, not benchmark sophistication.

The safest implementation path is to add four JSON fixtures that reuse the existing `family_afternoon` Mock World and existing workflow expectations, then update the fixture registry and tests. Do not add a new world profile or failure profile unless the user explicitly approves a later task for that.

The current default fixture loader hard-codes `_DEFAULT_CASE_IDS = ("family_afternoon_v1",)`. Expanding this tuple and testing deterministic ordering is part of the task.

The current untracked `docs/TASK_WORKFLOW_PROMPTS.md` appears unrelated to Task 028. Do not stage or commit it unless the user explicitly adds it to this task.
