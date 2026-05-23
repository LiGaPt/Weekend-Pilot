# Spec: 049 Mock World Scenario Pack Expansion v1

## 1. Goal

Expand WeekendPilot's deterministic Mock World and LocalLife-Bench coverage beyond the current family-plus-solo baseline by adding a small, reviewable multi-scenario pack.

After this task, the repository should support four additional non-failure Mock World profiles and benchmark cases:

- `couple_afternoon`
- `friends_gathering`
- `rainy_day_fallback`
- `budget_lite`

This task is intentionally benchmark-first and fixture-first. It should make the system materially less centered on the family half-day path in internal evaluation and workflow-backed benchmark runs, while keeping the public demo, conversation flow, and deterministic planner contracts stable.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a benchmark-driven local-life planning system that should grow beyond a single family-afternoon path. `docs/NEXT_PHASE_ROADMAP.md` places this work in milestone `M3. 多场景与 benchmark 扩展`, with the explicit goal that benchmark coverage should no longer revolve around one family scenario.

The repository is already ahead of the roadmap in other areas:

- Tasks `033`-`042` covered the current M1/M2 timing, observability, and internal review baseline.
- Tasks `043`-`048` covered session persistence, replan, version lineage, action manifest, and clarification flow.
- The code for memory-query policy has already landed after Task `046`, even though the local `047` spec/plan pair is still untracked in the current workspace.

That means the next highest-value roadmap gap is no longer another conversation feature. The gap is broader deterministic scenario coverage. Current benchmark inventory still concentrates on:

- five `family_afternoon` non-failure cases
- one `solo_afternoon` non-failure case
- one `family_afternoon` failure-injection case

This task should close that M3 gap without widening into parser redesign, public demo changes, or new workflow semantics.

## 3. Requirements

- Add four new deterministic Mock World profiles with these exact profile IDs:
  - `couple_afternoon`
  - `friends_gathering`
  - `rainy_day_fallback`
  - `budget_lite`
- Store the new fixtures under:
  - `backend/app/providers/mock_world/fixtures/couple_afternoon.json`
  - `backend/app/providers/mock_world/fixtures/friends_gathering.json`
  - `backend/app/providers/mock_world/fixtures/rainy_day_fallback.json`
  - `backend/app/providers/mock_world/fixtures/budget_lite.json`
- `load_mock_world(profile)` must accept all six supported profiles after this task:
  - `family_afternoon`
  - `solo_afternoon`
  - `couple_afternoon`
  - `friends_gathering`
  - `rainy_day_fallback`
  - `budget_lite`
- `load_mock_world()` with no explicit profile must still return the existing `family_afternoon` fixture.
- `build_mock_world_registry(profile=...)` must accept the four new profiles without changing the current default.
- Do not change the public demo default away from `family_afternoon`.
- Do not widen the workflow request schema or routing unless a focused test proves a remaining hardcoded profile whitelist still exists.

- Each new Mock World fixture must continue to satisfy the existing loader schema validated by `_validate_world(...)`.
- Each new Mock World fixture must include:
  - at least 2 activity POIs
  - at least 2 dining POIs
  - deterministic `sort_order` values
  - at least 2 walking routes connecting a top-ranked activity to dining
  - valid `weather`
  - valid `queues`
  - valid `table_availability`
  - valid `ticket_availability`
  - valid `addons` list
- New POI IDs must continue to follow the current conventions:
  - activity POIs use `activity_...`
  - dining POIs use `restaurant_...`
- The new fixture design must remain compatible with the existing deterministic query planner and candidate collection path.

- `couple_afternoon` fixture requirements:
  - the top-ranked activity or activity set must support a nearby quieter outing with `citywalk` or another light date-style option
  - the top-ranked dining candidate must support a calmer follow-up meal
  - at least one top-ranked dining candidate must expose `lighter_options`
- `friends_gathering` fixture requirements:
  - the top-ranked activity path must support a friends-group outing
  - at least one top-ranked activity must use an `outdoor` tag
  - the top-ranked dining candidate must be group-friendly or casual in fixture content
- `rainy_day_fallback` fixture requirements:
  - the top-ranked activity path must support an indoor fallback
  - the fixture weather must be consistent with rain or a high precipitation warning
  - the weather advisory must nudge toward the indoor fallback interpretation
- `budget_lite` fixture requirements:
  - the top-ranked activity path must be free or low-ticket-cost in fixture data
  - the top-ranked dining candidate must be low-cost or quick-meal oriented in fixture data
  - this budget behavior must be achieved through fixture composition, tags, descriptions, sort order, and cost metadata already supported by the Mock World schema
  - do not introduce a new budget field into `LocalLifeIntent` or query planning in this task

- Add four new benchmark case fixtures with these exact case IDs:
  - `couple_afternoon_v1`
  - `friends_gathering_v1`
  - `rainy_day_fallback_v1`
  - `budget_lite_v1`
- Store the new case fixtures under:
  - `backend/app/benchmark/cases/couple_afternoon_v1.json`
  - `backend/app/benchmark/cases/friends_gathering_v1.json`
  - `backend/app/benchmark/cases/rainy_day_fallback_v1.json`
  - `backend/app/benchmark/cases/budget_lite_v1.json`

- Each new benchmark case must use:
  - `tool_profile="mock_world"`
  - `failure_profile=null`
  - `agent_version="agent-v1"`
  - `prompt_version="prompt-v1"`
  - the existing non-failure required tool set used by the current default cases
  - `min_tool_event_count=8`
  - `min_action_count=1`
  - `expected_workflow_status="completed"`
  - `expected_execution_status="succeeded"`
  - `expected_feedback_status="completed"`

- Each new benchmark case must use these exact `world_profile` mappings:
  - `couple_afternoon_v1 -> couple_afternoon`
  - `friends_gathering_v1 -> friends_gathering`
  - `rainy_day_fallback_v1 -> rainy_day_fallback`
  - `budget_lite_v1 -> budget_lite`

- Each new benchmark case must use these exact taxonomy values:
  - `couple_afternoon_v1`
    - `scenario_bucket="couple"`
    - `level="L2"`
    - `tags=["citywalk", "date_friendly", "light_meal"]`
    - `failure_mode=null`
  - `friends_gathering_v1`
    - `scenario_bucket="friends"`
    - `level="L2"`
    - `tags=["casual_dining", "friends_group", "outdoor_activity"]`
    - `failure_mode=null`
  - `rainy_day_fallback_v1`
    - `scenario_bucket="mixed"`
    - `level="L2"`
    - `tags=["fallback", "indoor_activity", "rainy_day"]`
    - `failure_mode=null`
  - `budget_lite_v1`
    - `scenario_bucket="unknown"`
    - `level="L2"`
    - `tags=["budget_limited", "free_activity", "quick_meal"]`
    - `failure_mode=null`

- Each new benchmark case must use these exact `metadata.focus` values:
  - `couple_afternoon_v1 -> baseline_couple_citywalk`
  - `friends_gathering_v1 -> friends_group_hangout`
  - `rainy_day_fallback_v1 -> rainy_day_indoor_fallback`
  - `budget_lite_v1 -> budget_lite_low_cost_route`

- Expand the canonical registered benchmark case order to this exact sequence:
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

- `load_default_benchmark_cases()` must return the first 10 case IDs above in that exact order.
- `load_failure_benchmark_cases()` must remain exactly:
  - `family_route_failure_v1`
- `load_benchmark_suite("all_registered")` must return all 11 cases in the exact registered order.
- `load_benchmark_case("missing_case")` must keep raising `BenchmarkHarnessError`.

- The `default` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"couple": 1, "family": 5, "friends": 1, "mixed": 1, "solo": 1, "unknown": 1}`
  - `level_counts={"L1": 3, "L2": 7}`
  - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 5, "friends_gathering": 1, "rainy_day_fallback": 1, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 10}`
  - `tag_counts={"addon_optional": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 5, "citywalk": 2, "date_friendly": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 3, "light_activity": 1, "light_meal": 5, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1}`

- The `all_registered` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"couple": 1, "family": 6, "friends": 1, "mixed": 1, "solo": 1, "unknown": 1}`
  - `level_counts={"L1": 3, "L2": 8}`
  - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 6, "friends_gathering": 1, "rainy_day_fallback": 1, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 10, "route_unavailable": 1}`
  - `tag_counts={"addon_optional": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 6, "citywalk": 2, "date_friendly": 1, "failure_injected": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 3, "light_activity": 1, "light_meal": 6, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1, "route_failure": 1}`

- `BenchmarkHarness.run_cases(load_default_benchmark_cases())` must return:
  - `10` case results
  - `run_status="passed"`
  - `passed_count=10`
  - `failed_count=0`
  - `error_count=0`
- `BenchmarkHarness.run_cases(load_benchmark_suite("all_registered"))` must return:
  - `11` case results
  - `run_status="passed"`
  - `passed_count=11`
  - `failed_count=0`
  - `error_count=0`

- Update focused unit and integration tests to cover:
  - new profile loading
  - registered/default/all_registered case ordering
  - taxonomy of the four new cases
  - default/all_registered suite matrix counts
  - benchmark harness pass status for the expanded suites

- Update `README.md` benchmark documentation to describe the expanded non-failure scenario pack and the new default-suite composition.
- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not change the public demo API, frontend, action manifest, clarification flow, replan flow, or memory-query policy in this task.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add elder同行 or `elder` benchmark coverage in this task.
- Do not add first-class `couple`, `rain`, or `budget` parsing to `LocalLifeIntent`.
- Do not change `ScenarioType`, `IntentConstraints`, `IntentParseSignals`, or `DeterministicQueryPlanner` behavior in this task.
- Do not add new public demo routes, frontend controls, or `world_profile` selection UI.
- Do not redesign benchmark suite IDs or add a new suite type beyond updating existing registered/default/all_registered membership.
- Do not modify recovery routing, replay behavior, failure injection semantics, or observability contracts.
- Do not mix unrelated local doc drafts, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, or generated `var/` artifacts into this task.
- Do not add new package dependencies or migrations.

## 5. Interfaces and Contracts

### Inputs

- Existing Mock World fixture loader:
  - `load_mock_world(profile: str = "family_afternoon")`
- Existing Mock World registry builder:
  - `build_mock_world_registry(profile: str = "family_afternoon")`
- Existing benchmark fixture entry points:
  - `load_benchmark_case(case_id: str) -> BenchmarkCase`
  - `load_registered_benchmark_cases() -> list[BenchmarkCase]`
  - `load_default_benchmark_cases() -> list[BenchmarkCase]`
  - `load_failure_benchmark_cases() -> list[BenchmarkCase]`
  - `load_benchmark_suite(suite_id) -> list[BenchmarkCase]`
- Existing workflow-backed benchmark harness:
  - `BenchmarkHarness.run_case(case)`
  - `BenchmarkHarness.run_cases(cases)`

### Outputs

- Four new supported Mock World profile IDs:
  - `couple_afternoon`
  - `friends_gathering`
  - `rainy_day_fallback`
  - `budget_lite`
- Four new benchmark cases:
  - `couple_afternoon_v1`
  - `friends_gathering_v1`
  - `rainy_day_fallback_v1`
  - `budget_lite_v1`
- Updated canonical registered benchmark inventory:
  - `11` total registered cases
- Updated non-failure default suite:
  - `10` total cases
- Existing `BenchmarkCase`, `BenchmarkSuiteDescription`, `BenchmarkSummary`, and `BenchmarkRunReport` schema shapes remain unchanged.
- Existing public demo schemas remain unchanged.

### Schemas

Example benchmark case fixture shape for this task:

```json
{
  "case_id": "couple_afternoon_v1",
  "title": "Couple citywalk afternoon with light dinner",
  "user_input": "This afternoon I want a nearby city walk with my partner for a few hours, then a lighter dinner.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "couple_afternoon",
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
    "expected_workflow_status": "completed",
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed"
  },
  "taxonomy": {
    "suite": "locallife_bench_v1",
    "scenario_bucket": "couple",
    "level": "L2",
    "tags": ["citywalk", "date_friendly", "light_meal"],
    "failure_mode": null
  },
  "metadata": {
    "focus": "baseline_couple_citywalk"
  }
}
```

Registered case order after this task:

```text
family_afternoon_v1
family_indoor_light_meal_v1
family_outdoor_quick_dinner_v1
family_memory_override_v1
family_citywalk_addon_v1
solo_afternoon_v1
couple_afternoon_v1
friends_gathering_v1
rainy_day_fallback_v1
budget_lite_v1
family_route_failure_v1
```

## 6. Observability

This task should not add a new observability surface.

It must preserve the current observability and benchmark-report behavior:

- per-case reports still include taxonomy
- suite reports still include `benchmark_summary.matrix_summary`
- benchmark report sanitization rules stay unchanged
- persisted benchmark artifact summaries and suite membership helpers continue to work with the expanded case inventory

This task must not add:

- new LangSmith fields
- new internal observability API routes
- new frontend observability pages
- new run-metadata schema families

## 7. Failure Handling

- If a requested new Mock World profile is missing from the loader registry, `load_mock_world(profile)` must keep raising `MockWorldError`.
- If a new Mock World fixture file is missing, malformed, or schema-invalid, the current loader error behavior must remain unchanged.
- If a new benchmark case fixture is missing, malformed, or schema-invalid, `load_benchmark_case(case_id)` must keep raising `BenchmarkHarnessError`.
- If one of the new world fixtures does not yield a feasible activity+dining route under the current deterministic workflow, tests should fail and the fixture data should be corrected. Do not widen planner logic in this task to compensate.
- If local PostgreSQL or Redis services are unavailable, integration verification may fail explicitly as existing benchmark integration tests do. Do not add silent fallbacks.
- Existing failure-suite behavior for `family_route_failure_v1` must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/049-mock-world-scenario-pack-expansion-v1.md` exists and matches this task.
- [ ] `docs/plans/049-mock-world-scenario-pack-expansion-v1-plan.md` exists and matches this task.
- [ ] `load_mock_world("couple_afternoon")` succeeds.
- [ ] `load_mock_world("friends_gathering")` succeeds.
- [ ] `load_mock_world("rainy_day_fallback")` succeeds.
- [ ] `load_mock_world("budget_lite")` succeeds.
- [ ] `load_mock_world()` still returns the existing `family_afternoon` profile by default.
- [ ] Four new benchmark case fixtures exist with the exact case IDs defined in this spec.
- [ ] The canonical registered benchmark case order is exactly the 11-case order defined in this spec.
- [ ] `load_default_benchmark_cases()` returns exactly the first 10 registered case IDs in order.
- [ ] `load_failure_benchmark_cases()` still returns only `family_route_failure_v1`.
- [ ] `load_benchmark_suite("all_registered")` returns all 11 registered case IDs in order.
- [ ] `load_benchmark_case("missing_case")` still raises `BenchmarkHarnessError`.
- [ ] The four new benchmark cases use the exact `world_profile`, taxonomy, and `metadata.focus` values defined in this spec.
- [ ] The `default` suite matrix summary exactly matches the counts defined in this spec.
- [ ] The `all_registered` suite matrix summary exactly matches the counts defined in this spec.
- [ ] `BenchmarkHarness.run_cases(load_default_benchmark_cases())` passes with 10 case results.
- [ ] `BenchmarkHarness.run_cases(load_benchmark_suite("all_registered"))` passes with 11 case results.
- [ ] Existing failure-suite semantics and `family_route_failure_v1` expectations remain unchanged.
- [ ] No public demo route, frontend route, parser contract, planner contract, or migration is changed.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit, excluding pre-existing unrelated local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
docker compose config
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: expand mock world scenario pack
```

## 11. Notes for the Implementer

Keep this task tightly scoped to deterministic Mock World fixture coverage and benchmark suite expansion.

The current codebase already supports:

- multiple Mock World `world_profile` values
- taxonomy-bearing benchmark cases
- named benchmark suites
- workflow-backed benchmark execution across the current registered case inventory

The important boundaries are:

- do not widen natural-language intent parsing just to make these scenarios more semantically explicit
- do not change the public demo family default
- do not mix unrelated local doc drafts or other local files into this task
- keep elder coverage for a later follow-up task after this 4-scenario pack lands cleanly

If implementation reveals a remaining hardcoded profile whitelist outside the loader introduced before Task `038`, update only that smallest blocking code path and do not turn this task into a broader workflow refactor.
