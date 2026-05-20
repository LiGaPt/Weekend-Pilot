# Solo Afternoon Mock World Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first non-family Mock World profile and benchmark case, and thread `world_profile` through the workflow/benchmark stack so `solo_afternoon_v1` runs without changing the public demo flow.

**Architecture:** Keep the public demo pinned to `family_afternoon`, but make the workflow runner instantiate Mock World with the request profile and let the benchmark harness execute any loader-supported Mock World profile. Reuse the existing fixture schema, workflow graph, Tool Gateway, benchmark report contracts, and observability envelopes; only widen profile support additively.

**Tech Stack:** Python, Pydantic, SQLAlchemy, LangGraph, pytest, Docker Compose.

---

## 1. Spec Reference

Spec file:

```text
docs/specs/038-solo-afternoon-mock-world-expansion-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

If the Task 038 spec file is not saved yet at implementation time, stop and save the approved spec before implementing this plan.

## 2. Current Repository Assumptions

- Current branch is `codex/internal-observability-detail-panels-v0`.
- Latest completed task is `037`, and the latest commit `731f104 feat: add internal observability detail panels` matches that task.
- `docs/specs` and `docs/plans` are continuous and matched through `037`.
- Current working tree has untracked local files `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/`; they are not part of Task 038.
- Mock World currently supports only `family_afternoon` in `backend/app/providers/mock_world/loader.py`.
- `WeekendPilotWorkflowRequest`, `WeekendPilotWorkflowRunner`, `WeekendPilotWorkflowNodes`, and `BenchmarkHarness` still hardcode family-only world-profile support.
- The public demo service still intentionally starts only the family profile and should stay that way in this task.
- Focused baseline before implementation passed: `python -m pytest tests/test_intent_parser.py tests/test_query_planner.py tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_benchmark_harness.py -q` -> `80 passed`.

## 3. Files to Add

- `backend/app/providers/mock_world/fixtures/solo_afternoon.json` - second deterministic Mock World profile for a solo afternoon scenario.
- `backend/app/benchmark/cases/solo_afternoon_v1.json` - first non-family default benchmark case using `world_profile="solo_afternoon"`.

## 4. Files to Modify

- `backend/app/providers/mock_world/loader.py` - register `solo_afternoon` as a supported profile while keeping `family_afternoon` as the default.
- `backend/app/workflow/schemas.py` - widen the workflow request contract so `world_profile` accepts `solo_afternoon`.
- `backend/app/workflow/dependencies.py` - carry the requested `world_profile` into workflow node construction.
- `backend/app/workflow/runner.py` - validate supported Mock World profiles via the shared loader registry and pass the request profile into workflow dependencies before creating nodes.
- `backend/app/workflow/nodes.py` - build `ToolGateway` with `build_mock_world_registry(dependencies.world_profile)` instead of the family default.
- `backend/app/benchmark/fixtures.py` - append `solo_afternoon_v1` to `_DEFAULT_CASE_IDS` after the existing five family default cases.
- `backend/app/benchmark/harness.py` - allow any shared-loader-supported Mock World profile instead of only `family_afternoon`.
- `tests/test_mock_world_loader.py` - add unit coverage for `load_mock_world("solo_afternoon")`.
- `tests/test_benchmark_harness.py` - update default fixture ordering/count expectations and add assertions for the new default non-family case.
- `tests/integration/test_benchmark_harness_gateway.py` - update default-suite expectations from five to six cases and ensure the gateway-backed suite still passes.

## 5. Implementation Steps

1. Add `solo_afternoon` to the shared Mock World fixture registry.
   Create `backend/app/providers/mock_world/fixtures/solo_afternoon.json` with the same validated top-level shape as `family_afternoon`. Use deterministic `activity_...` POI ids for activity candidates and `restaurant_...` POI ids for dining candidates so the existing generic non-family Mock World search queries continue to match without planner changes. Ensure the highest-ranked activity has available ticket evidence, the highest-ranked dining option has available table evidence, and there is at least one successful activity-to-dining walking route.

2. Register the new profile in the loader and keep the current default stable.
   Update `backend/app/providers/mock_world/loader.py` so `SUPPORTED_PROFILES` contains both `family_afternoon` and `solo_afternoon`. Do not change the no-argument default for `load_mock_world()` or `build_mock_world_registry()`.

3. Thread requested `world_profile` through workflow construction.
   Update `backend/app/workflow/schemas.py` so `WeekendPilotWorkflowRequest.world_profile` accepts `family_afternoon` and `solo_afternoon`. Add `world_profile` to `WeekendPilotWorkflowDependencies` with default `family_afternoon`. In `backend/app/workflow/runner.py`, replace the family-only support check with a shared supported-profile membership check and copy `request.world_profile` into dependencies before constructing `WeekendPilotWorkflowNodes`. In `backend/app/workflow/nodes.py`, build the ToolGateway registry from `dependencies.world_profile`.

4. Expand benchmark fixture support and keep ordering deterministic.
   Create `backend/app/benchmark/cases/solo_afternoon_v1.json` with `tool_profile="mock_world"`, `world_profile="solo_afternoon"`, `failure_profile=null`, stable metadata, and existing expected execution/feedback semantics. Update `backend/app/benchmark/fixtures.py` to append `solo_afternoon_v1` after the current five family default case ids. Update `backend/app/benchmark/harness.py` so the support guard accepts any loader-supported Mock World profile and still returns the current typed error result for unsupported combinations.

5. Update unit tests around fixture loading and benchmark expectations.
   In `tests/test_mock_world_loader.py`, add an explicit `load_mock_world("solo_afternoon")` assertion for profile name, a stable location check, and required-key parity. In `tests/test_benchmark_harness.py`, update the ordered default case id tuple, the default-suite count, and the world-profile-set assertion to include `solo_afternoon`. Add or extend a benchmark harness case test so `load_benchmark_case("solo_afternoon_v1")` runs through `BenchmarkHarness.run_case(...)` with `status="passed"` and `workflow_status="completed"`.

6. Update the gateway-backed benchmark integration suite.
   In `tests/integration/test_benchmark_harness_gateway.py`, update the default suite case-id set and counts from five to six. Keep the existing per-case report sanitation assertions, but ensure they now also cover the new `solo_afternoon_v1` member of the default suite.

7. Run focused verification and keep the commit clean.
   Run the focused unit suite first, then PostgreSQL/Redis-backed integration verification. Before committing, confirm that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` remain unstaged. Commit only the Task 038 code/test files.

## 6. Testing Plan

- Unit tests: update `tests/test_mock_world_loader.py` to cover the new profile loader path.
- Unit tests: update `tests/test_benchmark_harness.py` to cover six default cases, mixed `world_profile` membership, and a passing `solo_afternoon_v1` benchmark run.
- Regression unit tests: run `tests/test_mock_world_provider.py` and `tests/test_langgraph_workflow.py` unchanged to catch loader/runner regressions on the existing family path.
- Integration tests: update and run `tests/integration/test_benchmark_harness_gateway.py` so the gateway-backed default suite passes with six cases.
- Smoke checks: verify benchmark case and suite reports remain sanitized and include the new profile in persisted run metadata.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_benchmark_harness.py tests/test_langgraph_workflow.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add solo afternoon mock world benchmark profile
```

Expected commands:

```bash
git status --short
git add backend/app/providers/mock_world/loader.py
git add backend/app/providers/mock_world/fixtures/solo_afternoon.json
git add backend/app/workflow/schemas.py backend/app/workflow/dependencies.py backend/app/workflow/runner.py backend/app/workflow/nodes.py
git add backend/app/benchmark/fixtures.py backend/app/benchmark/harness.py backend/app/benchmark/cases/solo_afternoon_v1.json
git add tests/test_mock_world_loader.py tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py
git commit -m "feat: add solo afternoon mock world benchmark profile"
git push
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not add multiple new scenario profiles in this task.
- Do not add planner heuristics for `friends`, `elder`, `rainy_day`, or budget scenarios yet.
- Do not expose `world_profile` selection in the public demo API or frontend.
- Do not change replay behavior, failure profiles, or chaos harness logic.
- Do not rewrite observability/report schemas.
- Do not edit completed historical task specs/plans `001`-`037`.
- Do not add new dependencies.
- Do not commit generated caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/038-solo-afternoon-mock-world-expansion-v0.md`.
- [ ] The change stayed scoped to one additional supported Mock World profile and one new default benchmark case.
- [ ] The workflow runner and workflow nodes now use the requested `world_profile` instead of a family-only default.
- [ ] The new `solo_afternoon_v1` case passes through the benchmark harness and the gateway-backed default suite.
- [ ] Existing family-path tests still pass.
- [ ] Public demo behavior remains family-only and unchanged.
- [ ] Required tests passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Report back with:

- The exact files changed.
- The final ordered default benchmark case list, showing that it moved from five family cases to six total cases with `solo_afternoon_v1` appended.
- The unit and integration verification commands that were run, plus their results.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any follow-up limitations, especially that future M3 work still needs additional profiles such as `friends`, `elder`, `rainy_day`, and benchmark case-matrix design.
