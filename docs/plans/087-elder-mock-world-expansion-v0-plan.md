# Plan: 087 Elder Mock World Expansion v0

## 1. Spec Reference

Spec file:

```text
docs/specs/087-elder-mock-world-expansion-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/customer-demo-scenario-selector-v0`.
- Current working tree is clean.
- Latest committed task is `086-customer-demo-scenario-selector-v0`, and the latest commit `7317dc8 feat: add customer demo scenario selector` matches it.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `086`.
- Explicit public start-path profile routing is already implemented for the current six customer-visible Mock World profiles:
  - `family_afternoon`
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
- The current public demo must stay on that six-profile contract for this task.
- The current benchmark inventory has `21` registered cases and no `elder` scenario bucket coverage.
- The current `coverage_gate_v1_5` thresholds require `case_count >= 21` and do not yet include `elder`, `elder_afternoon`, or `elder_friendly`.
- `release_gate_v1` is already a stable 15-case contract and must remain unchanged.

## 3. Files to Add

- `backend/app/providers/mock_world/fixtures/elder_afternoon.json` - new deterministic elder-oriented Mock World fixture.
- `backend/app/benchmark/cases/elder_afternoon_v1.json` - new benchmark case for the elder Mock World profile.

## 4. Files to Modify

- `backend/app/providers/mock_world/loader.py` - add `elder_afternoon` to supported loader profiles.
- `backend/app/workflow/schemas.py` - extend `WeekendPilotWorkflowRequest.world_profile` literal set with `elder_afternoon`.
- `backend/app/benchmark/fixtures.py` - register `elder_afternoon_v1` in canonical case order after `budget_lite_v1`.
- `backend/app/benchmark/suites.py` - update `expanded`, `default`, and `all_registered` suite membership while keeping `release_gate_v1` unchanged.
- `backend/app/benchmark/coverage_gate.py` - add elder thresholds and update minimum case count to `22`.
- `README.md` - update suite counts and elder coverage-gate documentation.
- `tests/test_mock_world_loader.py` - add loader coverage and count expectations for `elder_afternoon`.
- `tests/test_mock_world_provider.py` - add deterministic activity/dining ordering expectations for `elder_afternoon`.
- `tests/test_langgraph_workflow.py` - add one request-schema acceptance check for `world_profile="elder_afternoon"`.
- `tests/test_benchmark_harness.py` - update registered/default/all_registered constants, matrix expectations, taxonomy payloads, and harness result expectations.
- `tests/test_benchmark_suites.py` - update suite membership, matrix-summary, and count expectations.
- `tests/test_benchmark_coverage_gate.py` - update coverage thresholds, counts, and expected ratios.
- `tests/integration/test_benchmark_harness_gateway.py` - update suite-count expectations and add one direct `elder_afternoon_v1` harness execution proof.
- `tests/integration/test_benchmark_coverage_gate.py` - update expected counts, thresholds, and ratios for the real gate run.

## 5. Implementation Steps

1. Add the new Mock World fixture file `backend/app/providers/mock_world/fixtures/elder_afternoon.json`.
   - Follow the current non-failure fixture shape used by `couple_afternoon.json` and `rainy_day_fallback.json`.
   - Use exactly 4 activity POIs and 4 dining POIs to match the current non-family profile density.
   - Use a new `601` identifier family to avoid collisions.
   - Use this exact deterministic ordering for activity POIs:
     - `activity_gardenhall_601`
     - `activity_teahouse_601`
     - `activity_gallery_601`
     - `activity_riverside_601`
   - Use this exact deterministic ordering for dining POIs:
     - `restaurant_soup_601`
     - `restaurant_light_601`
     - `restaurant_teahouse_601`
     - `restaurant_noodle_601`
   - Make the top activity quiet and indoor-first.
   - Make the top dining candidate support `lighter_options`.
   - Provide at least two short walking routes from the top activity path to the top dining path.
   - Keep the fixture benchmark-friendly:
     - valid opening windows
     - valid queue data
     - valid ticket and table availability
     - at least one feasible primary path that can pass without planner changes

2. Extend the shared Mock World loader and loader tests.
   - Add `elder_afternoon` to `backend/app/providers/mock_world/loader.py`.
   - Update `tests/test_mock_world_loader.py`:
     - include `elder_afternoon` in `SUPPORTED_PROFILES`
     - add `MINIMUM_CATEGORY_COUNTS["elder_afternoon"] = {"activity": 4, "dining": 4}`
     - keep default family behavior unchanged

3. Extend deterministic provider ordering coverage.
   - Update `tests/test_mock_world_provider.py` with exact expected activity and dining order for `elder_afternoon`.
   - Keep provider-name, route, weather, queue, table, and ticket API behavior unchanged.
   - Only add new profile expectations; do not refactor provider APIs.

4. Extend the workflow contract but not the public demo contract.
   - Add `elder_afternoon` to `backend/app/workflow/schemas.py`.
   - Add one focused acceptance check in `tests/test_langgraph_workflow.py` proving `WeekendPilotWorkflowRequest(world_profile="elder_afternoon")` validates.
   - Do not change:
     - `backend/app/demo/schemas.py`
     - `backend/app/demo/service.py`
     - `backend/app/demo/world_profile.py`
     - any frontend types or scenario presets

5. Add the new benchmark case file `backend/app/benchmark/cases/elder_afternoon_v1.json`.
   - Use this exact case title:
     - `Gentle elder-friendly afternoon with a short walk and light dinner`
   - Use this exact `user_input`:
     - `This afternoon I want to take my wife and older mother out nearby for a few hours. Keep the walking short, start with a quiet indoor stop, and then have a light early dinner.`
   - Use exact taxonomy:
     - `scenario_bucket="elder"`
     - `level="L2"`
     - `tags=["elder_friendly", "short_walk", "light_meal"]`
     - `failure_mode=null`
   - Use exact metadata focus:
     - `elder_gentle_afternoon`
   - Mirror the existing non-failure case contract for required tools and expected statuses.

6. Insert the new case into the canonical benchmark order.
   - Update `backend/app/benchmark/fixtures.py` so `_REGISTERED_CASE_IDS` becomes:
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
     11. `elder_afternoon_v1`
     12. `family_route_failure_v1`
     13. `family_route_and_dining_unavailable_v1`
     14. `rainy_day_ticket_sold_out_v1`
     15. `family_memory_advisory_fill_v1`
     16. `family_memory_expired_advisory_v1`
     17. `solo_clarification_continuation_v1`
     18. `family_replan_version_continuation_v1`
     19. `family_distractor_selection_v1`
     20. `friends_distractor_selection_v1`
     21. `rainy_day_stable_sorting_v1`
     22. `budget_indoor_fallback_v1`

7. Update suite membership in `backend/app/benchmark/suites.py`.
   - Extend `_EXPANDED_CASE_IDS` by appending `elder_afternoon_v1`.
   - Let `_DEFAULT_CASE_IDS` become baseline plus the 5-case expanded pack.
   - Let `_ALL_REGISTERED_CASE_IDS` become the new 22-case registered list via the existing suite composition pattern.
   - Keep these unchanged:
     - `_BASELINE_CASE_IDS`
     - `_RECOVERY_FOCUSED_CASE_IDS`
     - `_MEMORY_GOVERNANCE_CASE_IDS`
     - `_CONVERSATION_CONTINUATION_CASE_IDS`
     - `_ROBUSTNESS_FOCUSED_CASE_IDS`
     - `_RELEASE_GATE_V1_CASE_IDS`

8. Update benchmark unit expectations in `tests/test_benchmark_harness.py`.
   - Add `elder_afternoon_v1` to the registered/default constants.
   - Add `elder` to the expected `scenario_bucket_counts`.
   - Add `elder_afternoon` to the expected `world_profile_counts`.
   - Update exact expected counts:
     - `DEFAULT_CASE_IDS` length: `11`
     - `ALL_REGISTERED_CASE_IDS` length: `22`
     - `DEFAULT_SCENARIO_BUCKET_COUNTS`: `{"couple": 1, "elder": 1, "family": 5, "friends": 1, "mixed": 1, "solo": 1, "unknown": 1}`
     - `DEFAULT_LEVEL_COUNTS`: `{"L1": 3, "L2": 8}`
     - `DEFAULT_WORLD_PROFILE_COUNTS`: add `"elder_afternoon": 1`
     - `ALL_REGISTERED_SCENARIO_BUCKET_COUNTS`: `{"couple": 1, "elder": 1, "family": 11, "friends": 2, "mixed": 3, "solo": 2, "unknown": 2}`
     - `ALL_REGISTERED_LEVEL_COUNTS`: `{"L1": 3, "L2": 13, "L3": 4, "L5": 2}`
     - `ALL_REGISTERED_WORLD_PROFILE_COUNTS`: add `"elder_afternoon": 1`
     - `ALL_REGISTERED_FAILURE_MODE_COUNTS`: `none` becomes `19`
   - Add the elder taxonomy payload under the canonical-case taxonomy helper expectations.
   - Update tag-count expectations additively:
     - `elder_friendly: 1`
     - `short_walk: 1`
     - `light_meal` increments by `1` in suites that include the new case
   - Keep `release_gate_v1` constants unchanged.

9. Update suite-listing and suite-matrix tests in `tests/test_benchmark_suites.py`.
   - Mirror the same count and tag-count updates from the harness test file.
   - Ensure:
     - `expanded` now reports 5 cases and includes `elder`
     - `default` now reports 11 cases
     - `all_registered` now reports 22 cases
     - `release_gate_v1` still reports 15 cases

10. Update the coverage gate implementation and its unit tests.
    - In `backend/app/benchmark/coverage_gate.py`:
      - set `MINIMUM_CASE_COUNT = 22`
      - add `SCENARIO_BUCKET_MINIMUMS["elder"] = 1`
      - add `WORLD_PROFILE_MINIMUMS["elder_afternoon"] = 1`
      - add `CONSTRAINT_TAG_MINIMUMS["elder_friendly"] = 1`
    - Keep the family share caps unchanged.
    - Update `tests/test_benchmark_coverage_gate.py` expected observed values:
      - `case_count == 22`
      - `family_scenario_share == 0.5`
      - `family_afternoon_world_profile_share == 0.5`
      - `non_failure_share == 0.8636`
      - `scenario_bucket_counts` and `world_profile_counts` include elder
      - `constraint_tag_case_counts["elder_friendly"] == 1`

11. Update integration benchmark coverage.
    - In `tests/integration/test_benchmark_harness_gateway.py`:
      - update expected suite counts and world-profile counts
      - add one focused integration proof that `load_benchmark_case("elder_afternoon_v1")` runs through the harness and persists `run_summary.world_profile == "elder_afternoon"`
    - In `tests/integration/test_benchmark_coverage_gate.py`:
      - update expected counts from 21 to 22
      - update expected scenario/world/tag counts
      - update expected ratios to `0.5`, `0.5`, and `0.8636`

12. Update `README.md`.
    - Update the named-suite description section:
      - `expanded` should describe the added elder scenario
      - `default` should describe the 11-case non-failure union
      - `all_registered` should describe the 22-case full inventory
    - Update the benchmark coverage gate section:
      - `case_count >= 22`
      - add `elder >= 1`
      - add `elder_afternoon >= 1`
      - mention the elder-friendly coverage threshold

13. Run verification in this order.
    - Run unit tests first.
    - Start services and run integration tests second.
    - Run `python scripts/run_benchmark_coverage_gate.py` last.
    - Inspect `git diff --check` before staging.
    - Confirm no demo/public/frontend files were changed accidentally.

14. Create a fresh task branch before staging and committing.
    - Current branch is still the completed `086` branch.
    - Use `codex/elder-mock-world-expansion-v0` for implementation.

## 6. Testing Plan

- Unit tests:
  - `tests/test_mock_world_loader.py`
    - `elder_afternoon` loads successfully
    - minimum category counts updated
  - `tests/test_mock_world_provider.py`
    - deterministic activity ordering for `elder_afternoon`
    - deterministic dining ordering for `elder_afternoon`
  - `tests/test_langgraph_workflow.py`
    - workflow request accepts `world_profile="elder_afternoon"`
  - `tests/test_benchmark_harness.py`
    - registered/default/all_registered counts updated
    - elder taxonomy payload present
    - elder case runs through the harness
  - `tests/test_benchmark_suites.py`
    - suite membership and matrix counts updated
  - `tests/test_benchmark_coverage_gate.py`
    - thresholds, observed counts, and ratios updated

- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py`
    - direct `elder_afternoon_v1` run persists `world_profile="elder_afternoon"`
    - default/all_registered suite count expectations updated
  - `tests/integration/test_benchmark_coverage_gate.py`
    - real gate run passes with the 22-case inventory and elder thresholds

- Smoke tests:
  - `python scripts/run_benchmark_coverage_gate.py`
    - proves the real gate contract still passes after the new scenario is added

- Document review checks:
  - `README.md` now states:
    - `default` suite has 11 non-failure cases
    - `all_registered` has 22 cases
    - coverage gate includes elder thresholds
  - public demo docs and public demo code remain unchanged

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/test_benchmark_coverage_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_coverage_gate.py -q
python scripts/run_benchmark_coverage_gate.py
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add elder mock world benchmark coverage
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/elder-mock-world-expansion-v0
git add backend/app/providers/mock_world/fixtures/elder_afternoon.json
git add backend/app/benchmark/cases/elder_afternoon_v1.json
git add backend/app/providers/mock_world/loader.py backend/app/workflow/schemas.py
git add backend/app/benchmark/fixtures.py backend/app/benchmark/suites.py backend/app/benchmark/coverage_gate.py
git add README.md
git add tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_langgraph_workflow.py
git add tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/test_benchmark_coverage_gate.py
git add tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_coverage_gate.py
git commit -m "feat: add elder mock world benchmark coverage"
git push -u origin codex/elder-mock-world-expansion-v0
```

The implementer must confirm `.env`, `frontend/.env`, `frontend/dist/`, `var/`, Playwright artifacts, and benchmark output artifacts are not staged.

## 9. Out-of-scope Changes

- Do not add a customer-facing elder scenario chip.
- Do not modify `DemoStartRunRequest.mock_world_profile`.
- Do not touch `frontend/src/demoScenarioPresets.ts`, `frontend/src/App.tsx`, or frontend E2E tests.
- Do not change `backend/app/demo/service.py` or `backend/app/demo/world_profile.py`.
- Do not add elder-specific parser keywords or clarification policy.
- Do not change `release_gate_v1` membership, thresholds, or report semantics.
- Do not modify memory governance, recovery routing, replay tooling, or internal observability contracts.
- Do not update historical review-evidence docs or generated artifacts.
- Do not add dependencies, migrations, or unrelated cleanup.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `elder_afternoon` was added only as a benchmark/fixture/workflow profile, not as a public demo profile.
- [ ] `elder_afternoon_v1` exists and uses the exact taxonomy and focus values from the spec.
- [ ] `expanded`, `default`, and `all_registered` counts are updated correctly.
- [ ] `release_gate_v1` is still unchanged at 15 cases.
- [ ] `coverage_gate_v1_5` now enforces elder scenario, world-profile, and tag coverage.
- [ ] The observed coverage ratios are `0.5000`, `0.5000`, and `0.8636`.
- [ ] Required tests and the coverage-gate script passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- New profile ID and case ID:
  - `elder_afternoon`
  - `elder_afternoon_v1`
- Final suite counts:
  - `default = 11`
  - `all_registered = 22`
  - `release_gate_v1 = 15`
- Final coverage-gate observed ratios:
  - `family_scenario_share = 0.5000`
  - `family_afternoon_world_profile_share = 0.5000`
  - `non_failure_share = 0.8636`
- Confirmation that public demo files and public demo contracts were unchanged
- Known limitations or follow-up tasks:
  - no public elder scenario chip yet
  - no elder-specific parser semantics yet
  - future public-demo exposure should build on Task `086`’s explicit start-profile routing pattern, not redesign it
