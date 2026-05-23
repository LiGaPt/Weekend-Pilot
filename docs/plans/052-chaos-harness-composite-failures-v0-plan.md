# Plan: 052 Chaos Harness Composite Failures v0

## 1. Spec Reference

Spec file:

```text
docs/specs/052-chaos-harness-composite-failures-v0.md
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

- Current branch is `codex/recovery-routing-v1`.
- Latest code commit is `3c2822b feat: add bounded recovery routing v1`.
- Latest completed product task in code history is `051`.
- `docs/specs/` and `docs/plans/` on disk are matched but not continuous; both are missing `047`, `049`, and `050`.
- The missing `047`, `049`, and `050` docs already exist on unmerged doc-only branch tips:
  - `a5ce24f docs: add task 047 spec and plan`
  - `2865960 docs: add task 049 spec and plan`
  - `e7a98d9 docs: add task 050 spec and plan`
- Those doc-only branches are convergence debt and must stay out of Task `052`.
- Current benchmark suite state before this task is:
  - `default`: 10 non-failure cases
  - `recovery_focused`: 1 failure case
  - `all_registered`: 11 total cases
- Current benchmark failure profile state before this task is:
  - only `route_unavailable_v0`
- Current replay stable summary compares:
  - benchmark status
  - workflow status
  - observed tool names
  - action count
  - injected failure count
  - recovery actions
- Current deterministic workflow captures weather but does not use weather to block or reroute plans.
- Current repository does not expose a benchmark-visible cross-provider fallback contract.
- Therefore Task `052` must stay benchmark-only and must not invent provider fallback or weather-aware planning semantics.
- Pre-existing unrelated local paths must remain unstaged:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`

## 3. Files to Add

- `backend/app/benchmark/failure_chain.py` - deterministic helper that builds `failure_chain_summary` from tool events and persisted recovery metadata.
- `backend/app/benchmark/cases/family_route_and_dining_unavailable_v1.json` - composite failure benchmark case using `family_afternoon` plus the `route_and_dining_unavailable_v0` profile.
- `backend/app/benchmark/cases/rainy_day_ticket_sold_out_v1.json` - composite failure benchmark case using `rainy_day_fallback` plus the `ticket_sold_out_and_bad_weather_v0` profile.

## 4. Files to Modify

- `backend/app/tool_gateway/failure_injection.py` - extend benchmark read-tool injection to support response overrides, placeholder substitution, and injected-response metadata.
- `backend/app/benchmark/failure_profiles.py` - define the two new composite benchmark failure profiles and sanitized metadata.
- `backend/app/benchmark/schemas.py` - add `BenchmarkFailureChainSummary` and additive replay `failure_chain_signature`.
- `backend/app/benchmark/graders.py` - count both injected hard failures and injected response overrides.
- `backend/app/benchmark/harness.py` - attach `failure_chain_summary` to case results and keep suite/report behavior deterministic.
- `backend/app/benchmark/replay.py` - include `failure_chain_signature` in stable replay comparison.
- `backend/app/benchmark/fixtures.py` - register the two new composite case IDs in exact canonical order.
- `backend/app/benchmark/suites.py` - expand `recovery_focused` and `all_registered` with exact new memberships while leaving `default` unchanged.
- `tests/test_failure_injection.py` - add unit coverage for response-override rules and sanitized metadata.
- `tests/test_benchmark_suites.py` - update exact suite order and matrix expectations.
- `tests/test_benchmark_harness.py` - add exact `failure_chain_summary` assertions and updated recovery/all_registered suite counts.
- `tests/test_benchmark_replay.py` - extend replay stable-summary assertions to include `failure_chain_signature`.
- `tests/integration/test_tool_gateway.py` - prove response-override injections return `status="succeeded"` with injected-response metadata and no provider call.
- `tests/integration/test_benchmark_harness_gateway.py` - run the two new composite benchmark cases through the real harness and assert bounded safe-stop behavior plus case-report contents.
- `README.md` - document composite chaos profiles, updated failure suite size, and additive failure-chain reporting/replay behavior.

## 5. Implementation Steps

1. Extend the read-tool injection contract first and lock it with unit tests.
   In `tests/test_failure_injection.py`, add failing tests for:
   - a hard injected error rule still returns `status="failed"` with `error_type="failure_injected"`
   - a response-override rule returns `status="succeeded"` with `error_type="failure_injected_response"`
   - full-token placeholder substitution resolves `{poi_id}`, `{restaurant_id}`, and `{location}`
   - malformed or unknown profiles still raise `BenchmarkHarnessError`
   Then update `backend/app/tool_gateway/failure_injection.py` to support:
   - `effect_kind`
   - `gateway_status`
   - `effect_type`
   - `response_json_template`
   Keep the implementation read-tool only.

2. Add a focused benchmark failure-chain helper instead of embedding the logic inside `BenchmarkHarness`.
   Create `backend/app/benchmark/failure_chain.py` with one public helper that accepts:
   - the case `failure_profile`
   - ordered tool events for the run
   - persisted recovery metadata
   - final workflow status
   The helper must return `BenchmarkFailureChainSummary`.
   Build `injected_effects` as ordered unique first-occurrence strings in exact format `<tool_name>:<effect_type>:<status>`.
   Mark `bounded=true` when `attempt_count <= max_attempts`.

3. Define the exact composite profiles in `backend/app/benchmark/failure_profiles.py`.
   Keep `route_unavailable_v0` unchanged.
   Add:
   - `route_and_dining_unavailable_v0`
   - `ticket_sold_out_and_bad_weather_v0`
   For `route_and_dining_unavailable_v0`, use three rules:
   - `check_queue` response override with `effect_type="dining_unavailable"`
   - `check_table_availability` response override with `effect_type="dining_unavailable"`
   - `check_route` hard failure with `effect_type="route_infeasible"`
   For `ticket_sold_out_and_bad_weather_v0`, use two rules:
   - `check_ticket_availability` response override with `effect_type="ticket_sold_out"`
   - `check_weather` response override with `effect_type="bad_weather"`
   Expose sanitized rule metadata with exact fields:
   - `profile_id`
   - `rule_id`
   - `tool_name`
   - `effect_kind`
   - `effect_type`
   - `gateway_status`

4. Add the additive benchmark schema fields before touching suite fixtures.
   In `backend/app/benchmark/schemas.py`:
   - add `BenchmarkFailureChainSummary`
   - add `failure_chain_summary: BenchmarkFailureChainSummary | None = None` to `BenchmarkCaseResult`
   - add `failure_chain_signature: list[str] = Field(default_factory=list)` to `BenchmarkReplaySummary`
   Keep all existing fields backward compatible.

5. Wire the new summary into the harness and keep grading behavior stable.
   In `backend/app/benchmark/harness.py`:
   - build `failure_chain_summary` after tool events and run metadata are available
   - attach it to every case result when `failure_profile` is non-null
   - keep `family_route_failure_v1` working with the same final benchmark result
   In `backend/app/benchmark/graders.py`:
   - treat both `failure_injected` and `failure_injected_response` tool events as injected benchmark events
   - keep `expected_recovery_action` legacy behavior unchanged
   Do not change workflow or recovery logic in this task.

6. Register the two new cases and lock exact suite membership.
   Add these exact case files:
   - `family_route_and_dining_unavailable_v1.json`
   - `rainy_day_ticket_sold_out_v1.json`
   Use the exact spec values for:
   - `world_profile`
   - `failure_profile`
   - taxonomy
   - `metadata.focus`
   - expected statuses and counts
   Update `backend/app/benchmark/fixtures.py` so registered case order is exactly:
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
   12. `family_route_and_dining_unavailable_v1`
   13. `rainy_day_ticket_sold_out_v1`
   Update `backend/app/benchmark/suites.py` so:
   - `default` stays the first 10 cases unchanged
   - `recovery_focused` is exactly the last 3 cases above
   - `all_registered` is exactly all 13 cases

7. Lock exact suite-count expectations in unit tests.
   In `tests/test_benchmark_suites.py`, replace the existing failure-suite expectations with:
   - `recovery_focused` case count `3`
   - `all_registered` case count `13`
   Assert the exact `recovery_focused` matrix summary:
   - `scenario_bucket_counts={"family": 2, "mixed": 1}`
   - `level_counts={"L2": 1, "L5": 2}`
   - `world_profile_counts={"family_afternoon": 2, "rainy_day_fallback": 1}`
   - `failure_mode_counts={"route_and_dining_unavailable": 1, "route_unavailable": 1, "ticket_sold_out_and_bad_weather": 1}`
   - `tag_counts={"bad_weather": 1, "child_friendly": 2, "composite_failure": 2, "dining_unavailable": 1, "failure_injected": 3, "light_meal": 1, "rainy_day": 1, "route_failure": 2, "ticket_sold_out": 1}`
   Assert the exact `all_registered` matrix summary:
   - `scenario_bucket_counts={"couple": 1, "family": 7, "friends": 1, "mixed": 2, "solo": 1, "unknown": 1}`
   - `level_counts={"L1": 3, "L2": 8, "L5": 2}`
   - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 7, "friends_gathering": 1, "rainy_day_fallback": 2, "solo_afternoon": 1}`
   - `failure_mode_counts={"none": 10, "route_and_dining_unavailable": 1, "route_unavailable": 1, "ticket_sold_out_and_bad_weather": 1}`
   - exact tag counts from the spec

8. Add harness-level assertions for explainability and boundedness.
   In `tests/test_benchmark_harness.py`:
   - keep `family_route_failure_v1` unchanged
   - add explicit assertions that both new composite cases serialize `failure_chain_summary`
   - assert exact `profile_id`
   - assert exact `recovery_actions == ["stop_safely"]`
   - assert `attempt_count == 1`
   - assert `max_attempts == 2`
   - assert `bounded is True`
   - assert exact `injected_effects` ordering:
     - `family_route_and_dining_unavailable_v1`:
       - `check_queue:dining_unavailable:succeeded`
       - `check_table_availability:dining_unavailable:succeeded`
       - `check_route:route_infeasible:failed`
     - `rainy_day_ticket_sold_out_v1`:
       - `check_weather:bad_weather:succeeded`
       - `check_ticket_availability:ticket_sold_out:succeeded`
   Also update suite run counts:
   - `recovery_focused`: `3`
   - `all_registered`: `13`

9. Extend replay stability only where needed.
   In `backend/app/benchmark/replay.py`:
   - populate `failure_chain_signature` from `result.failure_chain_summary.injected_effects`
   - add `failure_chain_signature` to `_COMPARE_FIELDS`
   In `tests/test_benchmark_replay.py`:
   - add one passing replay test where the signature matches
   - add one failing replay test where the signature differs but other stable fields are the same
   Keep replay path/report sanitization unchanged.

10. Prove the new behavior through gateway-backed integration tests.
    In `tests/integration/test_tool_gateway.py`:
    - add a benchmark-style response-override injector test that returns `status="succeeded"`
    - assert a tool event row is created
    - assert the provider was not invoked
    - assert `error_json.error_type == "failure_injected_response"`
    In `tests/integration/test_benchmark_harness_gateway.py`:
    - run `family_route_and_dining_unavailable_v1`
    - assert benchmark `status="passed"`
    - assert workflow `status="failed"`
    - assert `action_count == 0`
    - assert case report contains the expected `failure_chain_summary`
    - run `rainy_day_ticket_sold_out_v1` with the same style of assertions
    - update `load_failure_benchmark_cases()` and `run_suite("recovery_focused")` expectations to 3 cases
    - update `run_suite("all_registered")` expectations to 13 cases
    Do not add new workflow-node integration tests unless one is strictly needed to diagnose a benchmark regression.

11. Update README last and keep staging tight.
    In `README.md`, update the LocalLife-Bench section so it states:
    - `recovery_focused` now contains the legacy route failure case plus two composite chaos cases
    - `all_registered` now contains 13 cases
    - composite failure case reports include `failure_chain_summary`
    - replay stable comparison now also covers `failure_chain_signature`
    Before staging, confirm that these remain unstaged:
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `qc`
    - `var/`
    - any local backfill docs for Tasks `047`, `049`, or `050`

## 6. Testing Plan

- Unit tests: `tests/test_failure_injection.py` for hard-failure and response-override benchmark rules.
- Unit tests: `tests/test_benchmark_suites.py` for exact `recovery_focused` and `all_registered` memberships and matrix counts.
- Unit tests: `tests/test_benchmark_harness.py` for exact `failure_chain_summary` values and suite-run case counts.
- Unit tests: `tests/test_benchmark_replay.py` for `failure_chain_signature` replay stability and mismatch reporting.
- Integration tests: `tests/integration/test_tool_gateway.py` for response-override event recording without provider execution.
- Integration tests: `tests/integration/test_benchmark_harness_gateway.py` for both new composite cases, 3-case failure suite, and 13-case all_registered suite.
- Smoke checks: `docker compose config`, `git diff --check`, `git status --short`.
- Explicit non-tests: no frontend tests, no public API tests, no AMAP tests, no new workflow-route tests unless benchmark execution forces them.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_failure_injection.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_tool_gateway.py tests/integration/test_benchmark_harness_gateway.py -q
docker compose config
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add chaos harness composite failures
```

Expected commands:

```bash
git status --short
git switch -c codex/chaos-harness-composite-failures-v0
git add backend/app/tool_gateway/failure_injection.py
git add backend/app/benchmark/failure_chain.py
git add backend/app/benchmark/failure_profiles.py
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/graders.py
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/replay.py
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/suites.py
git add backend/app/benchmark/cases/family_route_and_dining_unavailable_v1.json
git add backend/app/benchmark/cases/rainy_day_ticket_sold_out_v1.json
git add tests/test_failure_injection.py
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/test_benchmark_replay.py
git add tests/integration/test_tool_gateway.py
git add tests/integration/test_benchmark_harness_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: add chaos harness composite failures"
git push -u origin codex/chaos-harness-composite-failures-v0
```

The implementer must confirm that `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, and any local backfill docs for `047`, `049`, and `050` are not staged.

## 9. Out-of-scope Changes

- Do not add provider fallback or provider-switch recovery behavior.
- Do not make weather a deterministic feasibility gate in workflow logic.
- Do not modify Task `051` recovery policy or recovery attempt routing.
- Do not add new Mock World fixture files.
- Do not change the default 10-case non-failure suite.
- Do not add public API routes, frontend UI, or observability page changes.
- Do not add new dependencies or migrations.
- Do not backfill or merge the missing `047`, `049`, or `050` docs in this task.
- Do not stage unrelated local docs or runtime artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/052-chaos-harness-composite-failures-v0.md`.
- [ ] `route_unavailable_v0` still works unchanged.
- [ ] Response-override benchmark rules work with `status="succeeded"` and sanitized injected-response metadata.
- [ ] No injected benchmark rule calls the underlying provider.
- [ ] The two new composite cases exist with exact IDs, profiles, taxonomy, and focus values from the spec.
- [ ] `load_failure_benchmark_cases()` returns exactly 3 cases in the correct order.
- [ ] `default` remains the same 10-case suite.
- [ ] `recovery_focused` and `all_registered` exact counts and matrix summaries match the spec.
- [ ] Both new composite cases finish with workflow `status="failed"`, benchmark `status="passed"`, and `action_count=0`.
- [ ] Both new composite case reports include the exact `failure_chain_summary` shape and values from the spec.
- [ ] Replay stable comparison now includes `failure_chain_signature`.
- [ ] `family_route_failure_v1` remains green and unchanged.
- [ ] Required verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, unrelated doc draft, or runtime artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final 3-case `recovery_focused` order.
- The final 13-case `all_registered` count and canonical order.
- The exact `failure_chain_summary` for `family_route_and_dining_unavailable_v1`.
- The exact `failure_chain_summary` for `rainy_day_ticket_sold_out_v1`.
- The exact `failure_chain_signature` values observed in replay tests.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no provider fallback or weather-aware workflow logic was added.
- Confirmation that unrelated local doc drafts and runtime artifacts remained unstaged.
