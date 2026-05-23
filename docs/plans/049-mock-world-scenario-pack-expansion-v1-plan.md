# Plan: 049 Mock World Scenario Pack Expansion v1

## 1. Spec Reference

Spec file:

```text
docs/specs/049-mock-world-scenario-pack-expansion-v1.md
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

- Current branch is `codex/demo-clarification-turn-workflow-v0`.
- Latest tracked numbered task is `048`.
- Latest commit is `5c1d227 feat: add demo clarification turn workflow`, and it matches Task `048`.
- In the current workspace, `docs/specs/` and `docs/plans/` are continuous and matched through `048`.
- At authoring time in git-tracked history, the doc chain was not fully converged because the Task `047` spec/plan pair still existed only as local state.
- Those local-only Task `047` docs were not part of Task `049` and had to remain unstaged.
- Additional unrelated local paths currently outside this task also remain unstaged:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`
- Current supported non-failure benchmark inventory is:
  - five `family_afternoon` cases
  - one `solo_afternoon` case
- Current registered benchmark inventory is:
  - six non-failure cases
  - one failure case
- Current Mock World loader supports only:
  - `family_afternoon`
  - `solo_afternoon`
- Current benchmark suite catalog supports:
  - `default`
  - `failures`
  - `all_registered`
- Current deterministic parser supports only `family`, `friends`, `solo`, and `unknown` scenario typing.
- Current planning contracts do not have first-class budget or rain fields.
- This task must therefore stay world-profile and benchmark-fixture scoped.
- Focused baseline checks already pass in the current workspace:
  - `python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_intent_parser.py tests/test_query_planner.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q`
  - `python -m pytest tests/integration/test_benchmark_harness_gateway.py -q`

## 3. Files to Add

- `backend/app/providers/mock_world/fixtures/couple_afternoon.json` - deterministic couple-oriented Mock World profile.
- `backend/app/providers/mock_world/fixtures/friends_gathering.json` - deterministic friends-group Mock World profile.
- `backend/app/providers/mock_world/fixtures/rainy_day_fallback.json` - deterministic rainy-day indoor fallback Mock World profile.
- `backend/app/providers/mock_world/fixtures/budget_lite.json` - deterministic budget-oriented Mock World profile.
- `backend/app/benchmark/cases/couple_afternoon_v1.json` - benchmark case for the couple scenario pack entry.
- `backend/app/benchmark/cases/friends_gathering_v1.json` - benchmark case for the friends scenario pack entry.
- `backend/app/benchmark/cases/rainy_day_fallback_v1.json` - benchmark case for the rainy-day fallback scenario pack entry.
- `backend/app/benchmark/cases/budget_lite_v1.json` - benchmark case for the budget-lite scenario pack entry.

## 4. Files to Modify

- `backend/app/providers/mock_world/loader.py` - register the four new supported profile IDs while keeping `family_afternoon` as the default.
- `backend/app/benchmark/fixtures.py` - expand the canonical registered case order from 7 to 11 cases.
- `backend/app/benchmark/suites.py` - expand `default` to 10 non-failure cases and `all_registered` to 11 cases in exact order.
- `tests/test_mock_world_loader.py` - add explicit loader coverage for the four new profiles and preserve the family default assertion.
- `tests/test_benchmark_suites.py` - update named-suite membership and matrix-summary expectations.
- `tests/test_benchmark_harness.py` - update case order, taxonomy, and default/all_registered matrix expectations.
- `tests/integration/test_benchmark_harness_gateway.py` - update workflow-backed suite pass/count assertions for the expanded benchmark inventory.
- `README.md` - update benchmark-suite documentation to reflect the expanded scenario pack.

## 5. Implementation Steps

1. Update the Mock World loader registry first.
   In `backend/app/providers/mock_world/loader.py`, add these exact entries to `SUPPORTED_PROFILES`:
   - `couple_afternoon: "couple_afternoon.json"`
   - `friends_gathering: "friends_gathering.json"`
   - `rainy_day_fallback: "rainy_day_fallback.json"`
   - `budget_lite: "budget_lite.json"`

   Keep:
   - `family_afternoon` registered
   - `solo_afternoon` registered
   - `load_mock_world()` defaulting to `family_afternoon`

2. Create the four new Mock World fixture files.
   Use the same top-level schema as the existing fixtures and keep each file independently valid under `_validate_world(...)`.

   Required design rules for all four fixtures:
   - include at least 2 activity POIs and 2 dining POIs
   - keep activity IDs prefixed `activity_`
   - keep dining IDs prefixed `restaurant_`
   - add deterministic `sort_order`
   - provide at least 2 walking routes from likely top-ranked activities to dining
   - keep `weather`, `queues`, `table_availability`, `ticket_availability`, and `addons` present
   - make the top-ranked activity+dining pair feasible under the current deterministic harness

   Required profile-level design:
   - `couple_afternoon.json`
     - primary activity should support `citywalk` or a quieter light outing
     - primary dining should include `lighter_options` and quiet/date-friendly copy
   - `friends_gathering.json`
     - primary activity should support an outdoor or group hangout
     - at least one primary dining candidate should read as casual/group-friendly
   - `rainy_day_fallback.json`
     - weather should signal rain or high precipitation
     - top-ranked activity should be indoor-first
     - dining should stay nearby and compatible with the indoor fallback
   - `budget_lite.json`
     - top-ranked activity should be free or low-ticket-cost
     - dining should be low-cost or quick-meal oriented through existing description/tag/cost patterns
     - do not invent new budget fields in the fixture schema

3. Create the four new benchmark case fixtures with exact IDs and mappings.
   Add:
   - `couple_afternoon_v1.json`
   - `friends_gathering_v1.json`
   - `rainy_day_fallback_v1.json`
   - `budget_lite_v1.json`

   For each new case:
   - use `tool_profile="mock_world"`
   - use `failure_profile=null`
   - use `agent_version="agent-v1"`
   - use `prompt_version="prompt-v1"`
   - reuse the current non-failure `required_tool_names`
   - set `min_tool_event_count=8`
   - set `min_action_count=1`
   - set `expected_workflow_status="completed"`
   - set `expected_execution_status="succeeded"`
   - set `expected_feedback_status="completed"`

   Use these exact `world_profile` values:
   - `couple_afternoon_v1 -> couple_afternoon`
   - `friends_gathering_v1 -> friends_gathering`
   - `rainy_day_fallback_v1 -> rainy_day_fallback`
   - `budget_lite_v1 -> budget_lite`

   Use these exact taxonomy blocks:
   - `couple_afternoon_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="couple"`
     - `level="L2"`
     - `tags=["citywalk", "date_friendly", "light_meal"]`
     - `failure_mode=null`
   - `friends_gathering_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="friends"`
     - `level="L2"`
     - `tags=["casual_dining", "friends_group", "outdoor_activity"]`
     - `failure_mode=null`
   - `rainy_day_fallback_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="mixed"`
     - `level="L2"`
     - `tags=["fallback", "indoor_activity", "rainy_day"]`
     - `failure_mode=null`
   - `budget_lite_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="unknown"`
     - `level="L2"`
     - `tags=["budget_limited", "free_activity", "quick_meal"]`
     - `failure_mode=null`

   Use these exact `metadata.focus` values:
   - `baseline_couple_citywalk`
   - `friends_group_hangout`
   - `rainy_day_indoor_fallback`
   - `budget_lite_low_cost_route`

4. Expand the canonical registered benchmark order in `backend/app/benchmark/fixtures.py`.
   Replace the current 7-case registered order with this exact 11-case sequence:
   1. `family_afternoon_v1`
   2. `family_indoor_light_meal_v1`
   3. `family_outdoor_quick_dinner_v1`
   4. `family_memory_override_v1`
   5. `family_citywalk_addon_v1`
   6. `solo_afternoon_v1`
   7. `couple_afternoon_v1`
   8. `friends_gathering_v1`
   9. `rainy_day_fallback_v1`
   10. `budget_lite_v1`
   11. `family_route_failure_v1`

   Keep `load_benchmark_case("missing_case")` behavior unchanged.

5. Expand the named suite catalog in `backend/app/benchmark/suites.py`.
   Update:
   - `default` to the first 10 case IDs above
   - `failures` to remain only `family_route_failure_v1`
   - `all_registered` to all 11 registered cases in canonical order

   Do not add a new suite ID in this task.
   Do not change suite titles or descriptions unless needed to stay accurate.

6. Update `tests/test_mock_world_loader.py`.
   Add explicit assertions that:
   - `load_mock_world("couple_afternoon")` returns a world whose `profile` is `couple_afternoon`
   - `load_mock_world("friends_gathering")` returns a world whose `profile` is `friends_gathering`
   - `load_mock_world("rainy_day_fallback")` returns a world whose `profile` is `rainy_day_fallback`
   - `load_mock_world("budget_lite")` returns a world whose `profile` is `budget_lite`
   - the zero-argument loader still returns `family_afternoon`

   Keep the loader tests fixture-shape focused. Do not turn them into end-to-end planner tests.

7. Update `tests/test_benchmark_suites.py`.
   Replace the current registered/default/all_registered expectations with the exact new order and counts from the spec.
   Assert:
   - registered case IDs are exactly the 11-case canonical sequence
   - `default` contains exactly the first 10 cases
   - `failures` still contains exactly one case
   - `all_registered` contains all 11 cases
   - `default.matrix_summary` matches the exact scenario/level/world/failure/tag counts from the spec
   - `all_registered.matrix_summary` matches the exact scenario/level/world/failure/tag counts from the spec

8. Update `tests/test_benchmark_harness.py`.
   Expand:
   - default case ID expectations from 6 to 10
   - registered case expectations from 7 to 11
   - taxonomy expectations to include the four new cases
   - default matrix counts to the exact new values
   - all_registered matrix counts to the exact new values

   Keep:
   - failure-suite assertions around `family_route_failure_v1`
   - report-sanitization checks
   - existing benchmark schema validation behavior

9. Update `tests/integration/test_benchmark_harness_gateway.py`.
   Expand the workflow-backed benchmark expectations so that:
   - `load_default_benchmark_cases()` now yields 10 cases
   - `BenchmarkHarness.run_cases(load_default_benchmark_cases())` passes with 10 results
   - `BenchmarkHarness.run_cases(load_benchmark_suite("all_registered"))` passes with 11 results
   - the persisted suite report matrix counts match the exact values from the spec
   - the failure case remains unchanged as the only member of `failures`

   Do not add new integration coverage outside the benchmark harness.

10. Update `README.md`.
    In the LocalLife-Bench section:
    - describe that the non-failure default suite now includes 10 cases
    - mention the new scenario pack entries:
      - couple
      - friends
      - rainy-day fallback
      - budget-lite
    - keep the public demo documentation family-default and unchanged

11. Run focused verification and keep the staging set clean.
    Run the commands in section 7.
    Before staging, confirm that these unrelated local files remain unstaged:
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/specs/047-memory-query-policy-baseline-v0.md`
    - `docs/plans/047-memory-query-policy-baseline-v0-plan.md`
    - `qc`
    - `var/`

## 6. Testing Plan

- Unit tests:
  - `tests/test_mock_world_loader.py` for explicit loading of all four new profiles
  - `tests/test_benchmark_suites.py` for registered/default/all_registered membership and exact matrix counts
  - `tests/test_benchmark_harness.py` for expanded case inventory, taxonomy expectations, and suite-report summaries
- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py` for 10-case default-suite and 11-case all_registered workflow-backed harness runs
- Smoke checks:
  - `docker compose config`
  - `git diff --check`
  - `git status --short`
- Regression boundary:
  - no demo API tests
  - no frontend tests
  - no parser/planner tests unless implementation accidentally touches those paths
  - no migration tests because this task must not alter schema

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
docker compose config
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: expand mock world scenario pack
```

Expected commands:

```bash
git status --short
git switch -c codex/mock-world-scenario-pack-expansion-v1
git add backend/app/providers/mock_world/loader.py
git add backend/app/providers/mock_world/fixtures/couple_afternoon.json
git add backend/app/providers/mock_world/fixtures/friends_gathering.json
git add backend/app/providers/mock_world/fixtures/rainy_day_fallback.json
git add backend/app/providers/mock_world/fixtures/budget_lite.json
git add backend/app/benchmark/cases/couple_afternoon_v1.json
git add backend/app/benchmark/cases/friends_gathering_v1.json
git add backend/app/benchmark/cases/rainy_day_fallback_v1.json
git add backend/app/benchmark/cases/budget_lite_v1.json
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/suites.py
git add tests/test_mock_world_loader.py
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/integration/test_benchmark_harness_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: expand mock world scenario pack"
git push -u origin codex/mock-world-scenario-pack-expansion-v1
```

The implementer must confirm that `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, and any unrelated local doc drafts are not staged.

## 9. Out-of-scope Changes

- Do not add elder同行 or `elder` benchmark coverage in this task.
- Do not add couple/budget/rain first-class parsing to `LocalLifeIntent`.
- Do not change `ScenarioType`, `IntentConstraints`, `IntentParseSignals`, or `DeterministicQueryPlanner`.
- Do not change the public demo API, frontend, clarification flow, replan flow, versioning, or action-manifest behavior.
- Do not add a new benchmark suite ID.
- Do not change failure-injection semantics, replay semantics, or observability/report schema shapes.
- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not stage unrelated local docs or runtime artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/049-mock-world-scenario-pack-expansion-v1.md`.
- [ ] The four new Mock World profiles load successfully and the family default remains unchanged.
- [ ] The four new benchmark cases use the exact IDs, `world_profile` values, taxonomy blocks, and `metadata.focus` values defined in the spec.
- [ ] The canonical registered benchmark order is exactly 11 cases.
- [ ] The `default` suite is exactly the first 10 registered non-failure cases.
- [ ] The `failures` suite still contains exactly `family_route_failure_v1`.
- [ ] The `default` and `all_registered` matrix summaries exactly match the spec counts.
- [ ] The expanded default suite passes through the workflow-backed benchmark harness.
- [ ] The all_registered suite passes through the workflow-backed benchmark harness.
- [ ] No public demo, parser, planner, migration, or frontend contract changed.
- [ ] Required verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, unrelated local doc, or runtime artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final 11-case registered benchmark order.
- The final 10-case default-suite order.
- The exact `default` and `all_registered` matrix summary counts as serialized by the implementation.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that unrelated local doc drafts and other unrelated local files remained unstaged.
- The follow-up recommendation that elder coverage and first-class couple/budget/rain parsing remain separate future tasks.
