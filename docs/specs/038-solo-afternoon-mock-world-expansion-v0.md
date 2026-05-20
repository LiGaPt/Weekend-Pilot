# Spec: 038 Solo Afternoon Mock World Expansion v0

## 1. Goal

Add the first non-family deterministic Mock World profile and exercise it through the existing workflow-backed benchmark stack without changing the public demo flow.

After this task, WeekendPilot should still default to the current `family_afternoon` demo path, but the internal workflow and benchmark infrastructure should also support one additional `mock_world` profile named `solo_afternoon`. A new default benchmark case `solo_afternoon_v1` should run end-to-end through the existing LangGraph workflow, produce a passing benchmark report, and prove that the repository is no longer locked to family-only deterministic evaluation.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a benchmark-driven local-life planning and execution system that should grow beyond a single family-afternoon path. `docs/NEXT_PHASE_ROADMAP.md` marks the current next milestone as M3 "multi-scenario and benchmark expansion" after the M1/M2 observability and frontend-separation work.

The repository already completed the current M1/M2 chain through Tasks `033`-`037`:

- stage timing and benchmark percentiles
- internal observability API
- public/internal view separation
- summary alignment
- internal observability detail panels

The remaining gap is not observability. The gap is scenario coverage. Current code still hardcodes `world_profile="family_afternoon"` across the workflow request contract, workflow runner, workflow node gateway construction, and benchmark harness support checks. Current default benchmark cases are also all family-only.

Task `038` is the smallest useful M3 step. It extends:

- the deterministic Mock World fixture layer
- the workflow profile-selection path
- the benchmark default suite

It must not change:

- Tool Gateway safety rules
- Human Confirmation boundaries
- Action Ledger behavior
- public demo routes or UI
- observability schemas introduced in earlier tasks

## 3. Requirements

- Add a new deterministic Mock World profile named `solo_afternoon`.
- Store the new profile as `backend/app/providers/mock_world/fixtures/solo_afternoon.json`.
- The new fixture must use the same top-level schema shape already validated by `load_mock_world(...)`.
- `load_mock_world("solo_afternoon")` must succeed.
- `load_mock_world()` with no explicit profile must still load `family_afternoon`.
- `build_mock_world_registry(profile=...)` must accept `solo_afternoon` without changing the existing family default.
- `WeekendPilotWorkflowRequest.world_profile` must accept both `family_afternoon` and `solo_afternoon`.
- The workflow runner must continue to reject unsupported profile combinations with a typed `unsupported_profile` error result instead of raising.
- The workflow runner must stop hardcoding the family profile when constructing workflow nodes and ToolGateway state.
- The workflow node layer must build the Mock World gateway using the requested `world_profile`.
- The benchmark harness must stop hardcoding `family_afternoon` as the only supported world profile.
- The benchmark harness must allow any supported Mock World profile from the shared loader registry and keep current typed error behavior for everything else.
- Add a new benchmark fixture `backend/app/benchmark/cases/solo_afternoon_v1.json`.
- `solo_afternoon_v1` must use `tool_profile="mock_world"` and `world_profile="solo_afternoon"`.
- `solo_afternoon_v1` must be added to `load_default_benchmark_cases()` in deterministic order after the existing five default family cases.
- `BenchmarkHarness.run_case(load_benchmark_case("solo_afternoon_v1"))` must return `status="passed"`.
- The new benchmark case must produce `workflow_status="completed"`, a non-null `run_summary`, and sanitized report output consistent with existing benchmark report rules.
- Update unit and integration tests to cover the new profile and the six-case default suite.
- Public demo defaults must remain pinned to the existing family path in this task.

## 4. Non-goals

- Do not add more than one new scenario profile in this task.
- Do not add `friends`, `elder`, `rainy_day`, `budget`, or failure-expansion profiles yet.
- Do not add new benchmark graders, replay logic, or chaos harness logic.
- Do not add public API parameters or frontend controls for selecting `world_profile`.
- Do not refactor deterministic query planning or bounded-agent logic unless required to let `solo_afternoon` run.
- Do not change existing observability contracts or frontend observability pages.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- `load_mock_world(profile: str = "family_afternoon")`
- `build_mock_world_registry(profile: str = "family_afternoon")`
- `WeekendPilotWorkflowRequest.world_profile`
- `BenchmarkCase.world_profile`
- `load_default_benchmark_cases()`

### Outputs

- Existing `WeekendPilotWorkflowResult` shape, with `world_profile="solo_afternoon"` persisted through run metadata and downstream reports when the new case is executed.
- Existing `BenchmarkCaseResult` and `BenchmarkRunReport` shapes, with no new top-level fields required for this task.

### Schemas

The workflow request contract must accept the new supported profile value while preserving the current default:

```json
{
  "tool_profile": "mock_world",
  "world_profile": "solo_afternoon",
  "case_id": "solo_afternoon_v1",
  "auto_confirm": true
}
```

The benchmark fixture contract for the new case must follow the current schema:

```json
{
  "case_id": "solo_afternoon_v1",
  "tool_profile": "mock_world",
  "world_profile": "solo_afternoon",
  "failure_profile": null,
  "metadata": {
    "suite": "locallife_bench_v1",
    "level": "L1",
    "focus": "baseline_solo_afternoon"
  }
}
```

The new Mock World fixture must continue to expose the same required top-level keys already validated by `backend.app.providers.mock_world.loader._validate_world(...)`.

## 6. Observability

This task should not add new observability fields.

It must preserve and correctly populate existing observability/reporting fields for the new profile:

- `agent_runs.world_profile`
- local trace summary metadata
- stored `run_summary`
- benchmark case report `run_summary`
- benchmark suite report membership and timing summaries

When `solo_afternoon_v1` runs, the persisted metadata and benchmark artifacts must clearly show `world_profile="solo_afternoon"` so later M3 comparisons can group runs by scenario profile.

## 7. Failure Handling

- If `solo_afternoon.json` is missing, malformed, or fails the current fixture validation rules, the existing `MockWorldError` path should surface unchanged.
- If `solo_afternoon_v1.json` is missing or fails `BenchmarkCase` validation, the existing `BenchmarkHarnessError` path should surface unchanged.
- If a caller passes `tool_profile != "mock_world"` or `world_profile` not in the supported Mock World profile set, the workflow runner must keep returning a typed `unsupported_profile` result.
- If the benchmark harness receives an unsupported profile combination, it must keep serializing an error `BenchmarkCaseResult` instead of raising.
- If the new fixture does not yield a usable activity+dining route under the current deterministic planner/generator rules, tests should fail and the fixture data should be corrected. Do not add workaround product logic in this task.

## 8. Acceptance Criteria

- [ ] `load_mock_world("solo_afternoon")` returns a valid fixture, and `load_mock_world()` still returns the current `family_afternoon` fixture by default.
- [ ] `WeekendPilotWorkflowRequest` accepts `world_profile="solo_afternoon"`.
- [ ] The workflow runner constructs Mock World execution state from the requested `world_profile` instead of always using the family default.
- [ ] `BenchmarkHarness.run_case(load_benchmark_case("solo_afternoon_v1"))` returns `status="passed"` with `workflow_status="completed"`.
- [ ] `load_default_benchmark_cases()` returns the existing five family default cases plus `solo_afternoon_v1` in deterministic order.
- [ ] The default benchmark suite still produces sanitized per-case and suite reports after the new case is added.
- [ ] Unsupported profile combinations still return typed error results rather than uncaught exceptions.
- [ ] Public demo start/read/confirm behavior remains pinned to the existing family demo path.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_benchmark_harness.py tests/test_langgraph_workflow.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
git status --short
```

## 10. Expected Commit

```text
feat: add solo afternoon mock world benchmark profile
```

## 11. Notes for the Implementer

Keep the task additive and profile-focused.

Use the existing generic non-family planner path rather than redesigning the planner in this task. The new fixture should therefore keep activity POI ids prefixed with `activity_` and dining POI ids prefixed with `restaurant_`, so the current Mock World search queries still match without new planner logic.

Give the primary activity available ticket evidence and the primary dining candidate available table evidence so the current deterministic itinerary generator ranks a feasible pair first.

Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, or `var/` as part of this task unless the user explicitly asks for that.
