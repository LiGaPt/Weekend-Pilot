# Spec: 087 Elder Mock World Expansion v0

## 1. Goal

Add the first elder-oriented deterministic Mock World profile and benchmark case without changing the current public demo surface.

After this task, WeekendPilot should support one additional non-failure Mock World profile named `elder_afternoon` and one additional benchmark case named `elder_afternoon_v1`. The new profile must run end to end through the existing workflow-backed benchmark stack, appear in suite matrix summaries and coverage-gate evidence, and close the explicit `elder / 老人同行` gap that still exists in `docs/NEXT_PHASE_ROADMAP.md`. The public customer demo should remain pinned to the current six-chip contract from Task `086`.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a benchmark-driven local-life planning system that should expand beyond a single family demo path. This task maps directly to `docs/NEXT_PHASE_ROADMAP.md` milestone `M3. 多场景与 benchmark 扩展`, specifically the still-unfinished elder or multi-generational coverage gap.

The repository is no longer blocked on `M1. 评测与观测基础设施`. Tasks `033`, `034`, `036`, `065`, `071`, and `081` already landed stage timing, suite timing summaries, release-gate latency SLOs, internal observability APIs, and reviewer polish. Task `086` already added explicit public start-path routing for the existing six Mock World demo profiles, so “stable explicit demo profile routing” is not the next gap.

Tasks `049` and `074` explicitly deferred elder coverage. Current code, fixtures, suite counts, and coverage-gate thresholds still only cover:

- `family_afternoon`
- `solo_afternoon`
- `couple_afternoon`
- `friends_gathering`
- `rainy_day_fallback`
- `budget_lite`

This task closes that remaining named `M3` gap in the smallest benchmark-first slice, without widening into public demo UI, public API expansion, or elder-specific parser semantics.

## 3. Requirements

- Use new task ID `087`.
- Keep `docs/specs` and `docs/plans` continuous and slug-matched through `087`.
- Add a new deterministic Mock World profile with the exact ID `elder_afternoon`.
- Store the new fixture at `backend/app/providers/mock_world/fixtures/elder_afternoon.json`.
- `load_mock_world(profile)` must accept `elder_afternoon`.
- `load_mock_world()` with no explicit profile must still return `family_afternoon`.
- `build_mock_world_registry(profile=...)` must accept `elder_afternoon` without changing the existing default.
- `WeekendPilotWorkflowRequest.world_profile` must accept `elder_afternoon`.
- Do not widen any public demo request schema in this task.
- The new fixture must keep the existing top-level Mock World schema validated by `backend.app.providers.mock_world.loader._validate_world(...)`.
- The new fixture must include at least:
  - 4 activity POIs
  - 4 dining POIs
  - deterministic `sort_order`
  - valid `weather`
  - valid `queues`
  - valid `table_availability`
  - valid `ticket_availability`
  - valid `addons`
  - at least 2 short walking routes that connect the top-ranked activity path to the top-ranked dining path
- The primary fixture recommendation must represent an elder-friendly, low-walking, quiet or indoor-first afternoon with a lighter meal.
- That elder-friendly behavior must be achieved through existing fixture composition only:
  - POI ordering
  - route distances
  - descriptions
  - existing tags
  - availability data
- Do not add new elder-specific planner fields, accessibility fields, or intent schema fields in this task.
- Add a new benchmark case fixture with the exact ID `elder_afternoon_v1`.
- Store the new case at `backend/app/benchmark/cases/elder_afternoon_v1.json`.
- The new benchmark case must use:
  - `tool_profile="mock_world"`
  - `world_profile="elder_afternoon"`
  - `failure_profile=null`
  - `agent_version="agent-v1"`
  - `prompt_version="prompt-v1"`
  - the existing non-failure required tool set used by the current expanded scenario pack
  - `min_tool_event_count=8`
  - `min_action_count=1`
  - `expected_workflow_status="completed"`
  - `expected_execution_status="succeeded"`
  - `expected_feedback_status="completed"`
- The benchmark case `user_input` must use existing parser-recognizable signals for time window, distance, companion/family context, and light-meal preference so the task does not depend on new elder-specific parsing.
- The new benchmark case must use these exact taxonomy values:
  - `scenario_bucket="elder"`
  - `level="L2"`
  - `tags=["elder_friendly", "short_walk", "light_meal"]`
  - `failure_mode=null`
- The new benchmark case must use exact `metadata.focus="elder_gentle_afternoon"`.
- Insert `elder_afternoon_v1` into the canonical registered benchmark order immediately after `budget_lite_v1` and before the first failure-focused case.
- `expanded` suite membership must become the current four-case non-failure expansion pack plus `elder_afternoon_v1`.
- `default` suite membership must become the current ten-case non-failure suite plus `elder_afternoon_v1`, for a total of `11` cases.
- `all_registered` suite membership must become the current `21` registered cases plus `elder_afternoon_v1`, for a total of `22` cases.
- `baseline`, `recovery_focused`, `memory_governance`, `conversation_continuations`, and `robustness_focused` suite memberships must remain unchanged.
- `release_gate_v1` must remain exactly `15` cases and must not include `elder_afternoon_v1`.
- Update `coverage_gate_v1_5` to require elder coverage in addition to the current thresholds:
  - `minimum_case_count >= 22`
  - `scenario_bucket_counts["elder"] >= 1`
  - `world_profile_counts["elder_afternoon"] >= 1`
  - `constraint_tag_case_counts["elder_friendly"] >= 1`
- Existing family share caps in the coverage gate must remain unchanged:
  - `family / case_count <= 0.60`
  - `family_afternoon / case_count <= 0.60`
- Update focused unit and integration tests to cover:
  - new profile loading
  - deterministic provider ordering
  - workflow request acceptance
  - new benchmark case loading
  - suite ordering and counts
  - coverage-gate thresholds and observed ratios
  - end-to-end benchmark harness execution for the new case
- Update `README.md` benchmark documentation to reflect:
  - the new `elder_afternoon` profile
  - the new `elder_afternoon_v1` case
  - the `11`-case default suite
  - the `22`-case `all_registered` suite
  - the elder thresholds in `coverage_gate_v1_5`
- Do not add new dependencies.
- Do not add or modify Alembic revisions.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add a seventh customer-facing scenario chip.
- Do not extend `DemoStartRunRequest.mock_world_profile`.
- Do not change `frontend/src/demoScenarioPresets.ts`.
- Do not change `backend/app/demo/schemas.py`, `backend/app/demo/service.py`, or `backend/app/demo/world_profile.py`.
- Do not add elder-specific deterministic intent parsing, accessibility scoring, or new clarification rules.
- Do not change `release_gate_v1` membership, latency SLOs, or artifact semantics.
- Do not modify recovery routing, replay behavior, internal observability schemas, memory governance behavior, or AMap preview behavior.
- Do not update historical evidence or reporting documents such as `docs/V1_DEVELOPMENT_REPORT.md`, `docs/V1_5_REVIEW_EVIDENCE.md`, or `docs/artifacts/`.

## 5. Interfaces and Contracts

### Inputs

- `load_mock_world(profile: str = "family_afternoon")`
- `build_mock_world_registry(profile: str = "family_afternoon")`
- `WeekendPilotWorkflowRequest.world_profile`
- `load_benchmark_case(case_id: str) -> BenchmarkCase`
- `load_registered_benchmark_cases() -> list[BenchmarkCase]`
- `load_default_benchmark_cases() -> list[BenchmarkCase]`
- `load_benchmark_suite(suite_id) -> list[BenchmarkCase]`
- `run_benchmark_coverage_gate(...)`

### Outputs

- New supported workflow and Mock World profile:
  - `elder_afternoon`
- New benchmark case:
  - `elder_afternoon_v1`
- Updated suite memberships and matrix summaries for:
  - `expanded`
  - `default`
  - `all_registered`
- Updated coverage-gate evidence with elder counts and thresholds.
- Existing public demo API and UI contracts remain unchanged.

### Schemas

Workflow request example:

```json
{
  "user_input": "This afternoon I want to take my wife and older mother out nearby for a few hours. Keep the walking short, start with a quiet indoor stop, and then have a light early dinner.",
  "tool_profile": "mock_world",
  "world_profile": "elder_afternoon",
  "case_id": "elder_afternoon_v1",
  "auto_confirm": true
}
```

Benchmark case example:

```json
{
  "case_id": "elder_afternoon_v1",
  "title": "Gentle elder-friendly afternoon with a short walk and light dinner",
  "user_input": "This afternoon I want to take my wife and older mother out nearby for a few hours. Keep the walking short, start with a quiet indoor stop, and then have a light early dinner.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "elder_afternoon",
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
    "scenario_bucket": "elder",
    "level": "L2",
    "tags": ["elder_friendly", "short_walk", "light_meal"],
    "failure_mode": null
  },
  "metadata": {
    "focus": "elder_gentle_afternoon"
  }
}
```

Expected ordered suite membership after this task:

```json
{
  "expanded_suite_case_ids": [
    "couple_afternoon_v1",
    "friends_gathering_v1",
    "rainy_day_fallback_v1",
    "budget_lite_v1",
    "elder_afternoon_v1"
  ],
  "default_suite_case_count": 11,
  "all_registered_case_count": 22,
  "release_gate_v1_case_count": 15
}
```

Expected coverage-gate thresholds after this task:

```json
{
  "coverage_gate_thresholds": {
    "minimum_case_count": 22,
    "scenario_bucket_minimums": {
      "couple": 1,
      "elder": 1,
      "family": 5,
      "friends": 2,
      "mixed": 3,
      "solo": 2,
      "unknown": 2
    },
    "world_profile_minimums": {
      "budget_lite": 2,
      "couple_afternoon": 1,
      "elder_afternoon": 1,
      "family_afternoon": 5,
      "friends_gathering": 2,
      "rainy_day_fallback": 3,
      "solo_afternoon": 2
    },
    "constraint_tag_minimums": {
      "budget_limited": 2,
      "casual_dining": 2,
      "conversation_continuation": 2,
      "date_friendly": 1,
      "elder_friendly": 1,
      "friends_group": 2,
      "memory_governance": 2,
      "rainy_day": 3,
      "robustness_case": 4
    }
  }
}
```

Expected `all_registered` matrix summary after this task:

```json
{
  "expected_all_registered_matrix_summary": {
    "scenario_bucket_counts": {
      "couple": 1,
      "elder": 1,
      "family": 11,
      "friends": 2,
      "mixed": 3,
      "solo": 2,
      "unknown": 2
    },
    "level_counts": {
      "L1": 3,
      "L2": 13,
      "L3": 4,
      "L5": 2
    },
    "world_profile_counts": {
      "budget_lite": 2,
      "couple_afternoon": 1,
      "elder_afternoon": 1,
      "family_afternoon": 11,
      "friends_gathering": 2,
      "rainy_day_fallback": 3,
      "solo_afternoon": 2
    },
    "failure_mode_counts": {
      "none": 19,
      "route_and_dining_unavailable": 1,
      "route_unavailable": 1,
      "ticket_sold_out_and_bad_weather": 1
    },
    "share_checks": {
      "family_scenario_share": 0.5,
      "family_afternoon_world_profile_share": 0.5,
      "non_failure_share": 0.8636
    }
  }
}
```

## 6. Observability

This task should not add new observability schemas or new public response fields.

It must preserve and correctly populate the existing benchmark and run evidence fields for the new profile:

- `agent_runs.world_profile`
- per-case `run_summary.world_profile`
- benchmark suite `matrix_summary.world_profile_counts`
- benchmark suite `matrix_summary.scenario_bucket_counts`
- benchmark suite `outcome_rollup.constraint_tag_outcomes`
- coverage-gate `observed_coverage`
- coverage-gate share checks

When `elder_afternoon_v1` runs, the persisted run summary and generated suite reports must clearly show `world_profile="elder_afternoon"` and `scenario_bucket="elder"`.

## 7. Failure Handling

- If `elder_afternoon.json` is missing, malformed, or fails existing loader validation, the current `MockWorldError` path must surface unchanged.
- If `elder_afternoon_v1.json` is missing or fails `BenchmarkCase` validation, the current `BenchmarkHarnessError` path must surface unchanged.
- If a caller passes `world_profile="elder_afternoon"` through a workflow path that still hardcodes the previous supported profile set, tests must fail and that whitelist must be updated. Do not work around it by changing the case back to a legacy profile.
- If the new elder benchmark prompt still falls into clarification because the parser lacks elder semantics, fix the prompt wording to use already-supported signals. Do not widen parser scope in this task.
- If the elder case would require changing `release_gate_v1`, stop and split that work into a separate task instead. This task must keep the blocking release gate unchanged.
- If a coverage-gate run blocks, the latest-pass alias behavior must remain unchanged: the task should fix thresholds or counts, not weaken the alias semantics.

## 8. Acceptance Criteria

- [ ] `docs/specs/087-elder-mock-world-expansion-v0.md` exists and matches this task.
- [ ] `docs/plans/087-elder-mock-world-expansion-v0-plan.md` exists and matches this task.
- [ ] `docs/specs` and `docs/plans` are continuous and slug-matched through `087`.
- [ ] `load_mock_world("elder_afternoon")` returns a valid fixture, and `load_mock_world()` still defaults to `family_afternoon`.
- [ ] `WeekendPilotWorkflowRequest` accepts `world_profile="elder_afternoon"`.
- [ ] `BenchmarkHarness.run_case(load_benchmark_case("elder_afternoon_v1"))` returns `run_status="passed"` and `run_summary.world_profile == "elder_afternoon"`.
- [ ] `expanded` suite now includes `elder_afternoon_v1` and has `5` cases.
- [ ] `default` suite now has `11` cases.
- [ ] `all_registered` suite now has `22` cases.
- [ ] `release_gate_v1` remains unchanged at `15` cases and does not include `elder_afternoon_v1`.
- [ ] `coverage_gate_v1_5` requires `elder` scenario coverage, `elder_afternoon` world-profile coverage, and `elder_friendly` tag coverage.
- [ ] A passing coverage-gate run reports `family_scenario_share == 0.5000`, `family_afternoon_world_profile_share == 0.5000`, and `non_failure_share == 0.8636`.
- [ ] The public customer demo remains unchanged:
  - still six scenario chips
  - still no elder chip
  - still no public `elder_afternoon` start-profile contract
- [ ] `README.md` accurately documents the new profile, case counts, and elder coverage-gate thresholds.
- [ ] Focused unit and integration verification commands pass.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/test_benchmark_coverage_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_coverage_gate.py -q
python scripts/run_benchmark_coverage_gate.py
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
feat: add elder mock world benchmark coverage
```

## 11. Notes for the Implementer

Keep this task benchmark-first and profile-first.

Do not use Task `086` as a reason to widen the public demo contract now. The explicit public start-path routing pattern already exists for the current six profiles; a future public-demo follow-up can reuse that pattern after the elder profile is stable in Mock World and benchmark evidence.

Use prompt wording and fixture composition to make the elder case pass through the current deterministic flow. If the implementation starts drifting toward parser redesign, customer-facing chips, or release-gate changes, stop and split the work.
