# Plan: 028 LocalLife-Bench Case Expansion v1

## 1. Spec Reference

Spec file:

```text
docs/specs/028-locallife-bench-case-expansion-v1.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `task27`.
- Latest completed commit is `e2e59c1 feat: add bounded recovery routing v0`.
- Task 027 added bounded recovery routing without expanding benchmark fixtures.
- Task 028 spec should be saved at `docs/specs/028-locallife-bench-case-expansion-v1.md` before implementation starts.
- Current default benchmark loader is `backend/app/benchmark/fixtures.py`.
- Current default benchmark suite contains only `family_afternoon_v1`.
- Current case schema is in `backend/app/benchmark/schemas.py`.
- Current benchmark harness runs cases through `WeekendPilotWorkflowRunner` with `auto_confirm=True`.
- Existing benchmark tests assert one default case and must be updated.
- PostgreSQL and Redis are required for benchmark integration tests.
- Working tree currently has unrelated untracked `docs/TASK_WORKFLOW_PROMPTS.md`; do not stage it.

## 3. Files to Add

- `docs/plans/028-locallife-bench-case-expansion-v1-plan.md` - this implementation plan.
- `backend/app/benchmark/cases/family_indoor_light_meal_v1.json` - L2 indoor family activity plus lighter meal case.
- `backend/app/benchmark/cases/family_outdoor_quick_dinner_v1.json` - L2 outdoor activity plus quick dinner case.
- `backend/app/benchmark/cases/family_memory_override_v1.json` - L2 case where current request should override stored preference memory.
- `backend/app/benchmark/cases/family_citywalk_addon_v1.json` - L1/L2 citywalk/add-on oriented family case.

## 4. Files to Modify

- `backend/app/benchmark/fixtures.py` - expand `_DEFAULT_CASE_IDS` to five deterministic case IDs.
- `backend/app/benchmark/cases/family_afternoon_v1.json` - optionally update metadata to `locallife_bench_v1` with `level` and `focus`.
- `tests/test_benchmark_harness.py` - update default fixture tests and add fixture validation coverage for all five cases.
- `tests/integration/test_benchmark_harness_gateway.py` - run the full default suite and verify aggregate results plus sanitized per-case reports.
- `README.md` - update only if benchmark instructions become misleading after expanding the default suite.

## 5. Implementation Steps

1. Confirm preconditions:
   - Run `git status --short --branch`.
   - Confirm `docs/specs/028-locallife-bench-case-expansion-v1.md` exists.
   - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` remains unrelated and unstaged.

2. Review the saved spec:
   - Read `docs/specs/028-locallife-bench-case-expansion-v1.md`.
   - Confirm the exact required case IDs, expected commit message, and non-goals.

3. Update the default case registry in `backend/app/benchmark/fixtures.py`.
   - Replace `_DEFAULT_CASE_IDS = ("family_afternoon_v1",)` with this exact ordered tuple:
     - `family_afternoon_v1`
     - `family_indoor_light_meal_v1`
     - `family_outdoor_quick_dinner_v1`
     - `family_memory_override_v1`
     - `family_citywalk_addon_v1`
   - Keep `load_benchmark_case("missing_case")` rejecting unknown IDs with `BenchmarkHarnessError`.

4. Add `family_indoor_light_meal_v1.json`.
   - Use `tool_profile="mock_world"` and `world_profile="family_afternoon"`.
   - Use a user input asking for an indoor, child-friendly afternoon and lighter dinner.
   - Use empty or reinforcing memory items only.
   - Use the same required tool list as `family_afternoon_v1`.
   - Set `min_tool_event_count=8`, `min_action_count=1`, expected execution `succeeded`, expected feedback `completed`.
   - Set metadata `suite="locallife_bench_v1"`, `level="L2"`, `focus="indoor_activity_and_lighter_meal"`.

5. Add `family_outdoor_quick_dinner_v1.json`.
   - Use a user input asking for outdoor child-friendly activity and quick/simple dinner.
   - Keep profile and expected tools the same as the existing case.
   - Set metadata `suite="locallife_bench_v1"`, `level="L2"`, `focus="outdoor_activity_and_quick_dinner"`.

6. Add `family_memory_override_v1.json`.
   - Include memory items that are plausible but should be overridden by the current request, such as a prior preference for outdoor walking while the request asks for indoor activity.
   - Keep the current request explicit enough for deterministic planning to pass.
   - Set metadata `suite="locallife_bench_v1"`, `level="L2"`, `focus="current_request_overrides_memory"`.

7. Add `family_citywalk_addon_v1.json`.
   - Use a user input asking for a light citywalk-style afternoon with family and an optional drink/snack add-on.
   - Keep expectations stable with `min_action_count=1`; do not require a specific add-on write action unless existing workflow already reliably executes it.
   - Set metadata `suite="locallife_bench_v1"`, `level="L1"`, `focus="citywalk_and_optional_addon"`.

8. Update `family_afternoon_v1.json` metadata only if desired for consistency.
   - If updated, keep all existing behavior and expected values unchanged.
   - Recommended metadata:
     - `suite="locallife_bench_v1"`
     - `level="L1"`
     - `focus="baseline_family_afternoon"`

9. Update unit tests in `tests/test_benchmark_harness.py`.
   - Change the default fixture test to assert exactly five cases and the exact ordered case IDs.
   - Assert every default case is a `BenchmarkCase`.
   - Assert every default case uses `mock_world` / `family_afternoon`.
   - Assert every default case can be loaded individually with `load_benchmark_case(case.case_id)`.
   - Assert every default case includes metadata `suite`, `level`, and `focus`.
   - Assert every default case includes the required read tools from the spec.
   - Keep the unknown-case error test.

10. Update integration tests in `tests/integration/test_benchmark_harness_gateway.py`.
    - Keep the existing single-case smoke behavior if useful, but rename it to clarify it runs one selected case.
    - Add or replace with a suite-level test that calls:
      `harness.run_cases(load_default_benchmark_cases())`.
    - Assert the aggregate result has five case results, `passed_count == 5`, `failed_count == 0`, `error_count == 0`, and `run_status == "passed"`.
    - Assert every case result has a run ID, trace ID, completed workflow status, completed feedback status, expected agent roles, and report path.
    - Assert one JSON report file exists per case.
    - Assert serialized report JSON excludes `action_id`, `tool_event_id`, `api_key`, `token`, `secret`, and `debug_trace`.
    - Assert each persisted `AgentRun` has benchmark metadata with matching `case_id`, workflow metadata, agents metadata, and observability metadata.

11. Review README.
    - If the LocalLife-Bench section still describes the harness accurately, leave it unchanged.
    - If it says or implies only one default case exists, update that sentence only.

12. Run focused unit tests:
    - `python -m pytest tests/test_benchmark_harness.py -v`

13. Start required services if needed:
    - `docker compose up -d postgres redis`
    - `python -m alembic upgrade head`

14. Run benchmark integration tests:
    - `python -m pytest tests/integration/test_benchmark_harness_gateway.py -v`

15. Run broad verification:
    - `python -m pytest -q`
    - `docker compose config`
    - `git diff --check`
    - `git status --short`

16. If any new benchmark case fails:
    - First inspect the generated case result report and workflow failure reason.
    - Prefer adjusting the case input or expected threshold within the existing spec.
    - Do not loosen graders, add a new world profile, or change workflow behavior just to make a fixture pass.

17. Review changed files.
    - Confirm no migrations were added.
    - Confirm no provider, workflow, frontend, or recovery-routing behavior changed.
    - Confirm no generated files under `var/` are staged.
    - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` is not staged.

18. Commit Task 028 only.

## 6. Testing Plan

- Unit tests:
  - default fixture loader returns exactly five ordered cases.
  - each default case loads individually by ID.
  - unknown case ID still raises `BenchmarkHarnessError`.
  - all default cases validate as `BenchmarkCase`.
  - all default cases use `mock_world` / `family_afternoon`.
  - all default cases include required metadata and expected read-tool trajectory.

- Integration tests:
  - `BenchmarkHarness.run_cases(load_default_benchmark_cases())` runs all five default cases.
  - aggregate run report passes when all five cases pass.
  - each case writes a sanitized report.
  - each persisted run records benchmark, workflow, agents, and observability metadata.
  - agent roles remain supervisor, discovery, dining, itinerary_planner, and validator_recovery.

- Smoke tests:
  - full backend test suite still passes.
  - Docker Compose configuration remains valid.
  - whitespace check passes with `git diff --check`.

## 7. Verification Commands

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

## 8. Commit and Push Plan

Expected commit message:

```text
test: expand locallife bench cases
```

Expected commands:

```bash
git status --short
git add docs/specs/028-locallife-bench-case-expansion-v1.md docs/plans/028-locallife-bench-case-expansion-v1-plan.md
git add backend/app/benchmark/fixtures.py backend/app/benchmark/cases/family_afternoon_v1.json
git add backend/app/benchmark/cases/family_indoor_light_meal_v1.json backend/app/benchmark/cases/family_outdoor_quick_dinner_v1.json backend/app/benchmark/cases/family_memory_override_v1.json backend/app/benchmark/cases/family_citywalk_addon_v1.json
git add tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py
git add README.md
git diff --cached --check
git commit -m "test: expand locallife bench cases"
git push
```

Only stage `README.md` if it was actually modified. Before committing, confirm `.env`, API keys, tokens, secrets, `var/`, `.venv`, caches, `node_modules`, `frontend/dist`, Playwright artifacts, and unrelated `docs/TASK_WORKFLOW_PROMPTS.md` are not staged.

## 9. Out-of-scope Changes

- Do not add LLM calls, prompts, model config, or LLM-backed agents.
- Do not add real provider support or change live AMAP behavior.
- Do not add a new Mock World profile.
- Do not add failure injection, replay, chaos harness, benchmark database tables, or migrations.
- Do not implement L3-L5 benchmark cases.
- Do not add recovery scoring or richer grader logic.
- Do not loosen existing benchmark graders to hide failures.
- Do not change Web demo API response fields, frontend UI, or frontend tests.
- Do not change workflow node names, recovery routing, confirmation boundary, Action Ledger behavior, or execution workflow.
- Do not add dependencies.
- Do not commit generated reports, local traces, caches, virtual environments, frontend build output, or secrets.
- Do not stage unrelated local files.

## 10. Review Checklist

- [ ] Task 028 spec exists at `docs/specs/028-locallife-bench-case-expansion-v1.md`.
- [ ] Task 028 plan exists at `docs/plans/028-locallife-bench-case-expansion-v1-plan.md`.
- [ ] The existing `family_afternoon_v1` case remains valid.
- [ ] Exactly four new benchmark case JSON fixtures were added.
- [ ] `load_default_benchmark_cases()` returns exactly five ordered cases.
- [ ] Each default case loads individually with `load_benchmark_case`.
- [ ] Unknown case IDs still raise `BenchmarkHarnessError`.
- [ ] Every default case uses `mock_world` / `family_afternoon`.
- [ ] Every default case includes `metadata.suite`, `metadata.level`, and `metadata.focus`.
- [ ] Unit benchmark tests pass.
- [ ] Integration benchmark suite test passes.
- [ ] One sanitized report is written per default case.
- [ ] Persisted benchmark metadata matches each case ID.
- [ ] Benchmark harness still uses `WeekendPilotWorkflowRunner`.
- [ ] No workflow, provider, frontend, migration, LLM, or recovery-routing behavior was changed.
- [ ] `python -m pytest -q` passed.
- [ ] `docker compose config` passed.
- [ ] `git diff --check` passed.
- [ ] No secrets or generated artifacts were staged.
- [ ] Commit message is `test: expand locallife bench cases`.
- [ ] Push succeeded or a clear reason for not pushing was reported.

## 11. Handoff Notes

Report back with:

- Branch name.
- Commit hash.
- Files changed.
- The five default benchmark case IDs.
- Verification commands and pass/fail results.
- Any skipped command and exact environment reason.
- Confirmation that reports remain sanitized.
- Confirmation that no provider, workflow, frontend, migration, or recovery-routing behavior changed.
- Confirmation that `docs/TASK_WORKFLOW_PROMPTS.md` was not staged.
- Push result.
- Known limitation: Task 028 expands deterministic L1-L2 style benchmark breadth only; failure injection, replay, L3-L5 cases, recovery scoring, and new world profiles remain future tasks.
