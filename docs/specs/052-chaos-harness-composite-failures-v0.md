# Spec: 052 Chaos Harness Composite Failures v0

## 1. Goal

Add the first composite-failure chaos slice to LocalLife-Bench so WeekendPilot can validate bounded safety and explainability under multi-factor benchmark failures, not only single-point failures.

Today the repository can inject one hard read-tool failure, stop safely through bounded recovery, write sanitized benchmark reports, and replay stable benchmark fields. What it still cannot do is express a benchmark case where multiple adverse conditions are present at once and then explain that multi-step failure chain in the report and replay contract. After this task, the benchmark harness must support composite benchmark failure profiles that combine hard injected failures with injected response overrides, must ship two deterministic composite benchmark cases, and must serialize a compact `failure_chain_summary` that makes the injected chain and recovery outcome directly reviewable and replay-stable.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` treats Failure Handling, Harness Engineering, LocalLife-Bench, and Replay Harness as product engineering concerns, not optional tests. It explicitly calls out Chaos Harness as part of the intended harness stack and requires recovery behavior to stay bounded, traceable, confirmation-safe, and replayable.

`docs/NEXT_PHASE_ROADMAP.md` places Chaos Harness work in milestone `M5. 恢复、真实 provider、记忆治理`. The earlier roadmap gaps are already covered in code:

- M1 evaluation and observability infrastructure is already present through workflow timing, suite summaries, internal observability, benchmark artifact panels, and replay linkage.
- M2 view separation is already present through internal observability API and customer-safe demo contracts.
- M3 scenario and benchmark expansion is already present through the expanded Mock World pack and canonical benchmark suites.
- M4 multi-turn and plan-version work is already present through session state, replan, version lineage, action manifest, and clarification turns.
- M5 bounded recovery routing itself landed in Task `051`.

That makes composite-failure validation the next real benchmark/recovery gap. This task deliberately stays inside existing deterministic contracts. It does not introduce cross-provider fallback, new public APIs, or new weather-aware planning logic. v0 focuses on composite benchmark failure expression, report explainability, and replay stability using the current Mock World workflow.

## 3. Requirements

- Keep `load_default_benchmark_cases()` unchanged.
- Keep `load_benchmark_suite("default")` unchanged.
- The existing default suite must remain exactly the current 10 non-failure cases in the same order.
- Keep `route_unavailable_v0` supported and backward compatible.
- Keep `family_route_failure_v1` supported and backward compatible.
- Keep the public workflow request/response contracts unchanged.
- Keep the public demo API and frontend contracts unchanged.
- Keep all chaos behavior benchmark-only through `failure_profile`.

- Extend benchmark-only read-tool injection so a rule can produce either:
  - a hard injected tool failure with no provider call, or
  - a successful response override with no provider call.
- Response override injection must stay read-tool only in v0.
- Response override injection must not be allowed for write tools in v0.
- Response override injection only needs full-token placeholder substitution for values that are exactly:
  - `{poi_id}`
  - `{restaurant_id}`
  - `{location}`
- Partial string interpolation is not required in this task.
- For hard injected failures, Tool Gateway must keep writing tool events with:
  - `status="failed"`
  - `error_json.error_type="failure_injected"`
- For injected response overrides, Tool Gateway must write tool events with:
  - `status="succeeded"`
  - `error_json.error_type="failure_injected_response"`
- Both injected event types must keep writing normal `tool_events` rows.
- Neither injected event type may call the underlying provider.
- Existing read-cache bypass behavior for injected benchmark calls must remain intact.

- Add these exact new composite benchmark failure profiles:
  - `route_and_dining_unavailable_v0`
  - `ticket_sold_out_and_bad_weather_v0`

- `route_and_dining_unavailable_v0` must inject these exact effects:
  - `check_queue` response override with `effect_type="dining_unavailable"`
  - `check_table_availability` response override with `effect_type="dining_unavailable"`
  - `check_route` hard failure with `effect_type="route_infeasible"`

- The exact `check_queue` override payload must serialize as:
  - top-level key `queue`
  - `poi_id="{poi_id}"`
  - `status="closed"`
  - `wait_minutes=90`
  - `parties_ahead=18`
- The exact `check_table_availability` override payload must serialize as:
  - top-level key `table_availability`
  - `restaurant_id="{restaurant_id}"`
  - `available=false`
  - `time_slots=[]`
  - `max_party_size=0`
  - `notes="Chaos profile injected unavailable dining capacity."`

- `ticket_sold_out_and_bad_weather_v0` must inject these exact effects:
  - `check_ticket_availability` response override with `effect_type="ticket_sold_out"`
  - `check_weather` response override with `effect_type="bad_weather"`

- The exact `check_ticket_availability` override payload must serialize as:
  - top-level key `ticket_availability`
  - `poi_id="{poi_id}"`
  - `available=false`
  - `time_slots=[]`
  - `remaining=0`
  - `price_cents=0`
- The exact `check_weather` override payload must serialize as:
  - top-level key `weather`
  - `location="{location}"`
  - `date="2026-05-16"`
  - `condition="中雨"`
  - `temperature_c=20`
  - `precipitation_chance=0.92`
  - `advisory="强降雨，建议室内或取消户外活动。"`

- `failure_profile_metadata(...)` must expose sanitized rule metadata for all three supported profiles.
- Rule metadata must include:
  - `profile_id`
  - `rule_id`
  - `tool_name`
  - `effect_kind`
  - `effect_type`
  - `gateway_status`

- Add these exact new benchmark cases:
  - `family_route_and_dining_unavailable_v1`
  - `rainy_day_ticket_sold_out_v1`

- `family_route_and_dining_unavailable_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `failure_profile="route_and_dining_unavailable_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_injected_failure_count=3`
  - taxonomy:
    - `scenario_bucket="family"`
    - `level="L5"`
    - `tags=["child_friendly", "composite_failure", "dining_unavailable", "failure_injected", "route_failure"]`
    - `failure_mode="route_and_dining_unavailable"`
  - `metadata.focus="route_and_dining_unavailable_safe_stop"`

- `rainy_day_ticket_sold_out_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="rainy_day_fallback"`
  - `failure_profile="ticket_sold_out_and_bad_weather_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_injected_failure_count=3`
  - taxonomy:
    - `scenario_bucket="mixed"`
    - `level="L5"`
    - `tags=["bad_weather", "composite_failure", "failure_injected", "rainy_day", "ticket_sold_out"]`
    - `failure_mode="ticket_sold_out_and_bad_weather"`
  - `metadata.focus="ticket_sold_out_bad_weather_safe_stop"`

- Both new composite cases must keep the current default required tool set:
  - `search_poi`
  - `check_weather`
  - `get_poi_detail`
  - `check_opening_hours`
  - `check_queue`
  - `check_table_availability`
  - `check_ticket_availability`
  - `check_route`

- Registered benchmark case order after this task must be exactly:

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
family_route_and_dining_unavailable_v1
rainy_day_ticket_sold_out_v1
```

- `load_failure_benchmark_cases()` must return exactly:

```text
family_route_failure_v1
family_route_and_dining_unavailable_v1
rainy_day_ticket_sold_out_v1
```

- `recovery_focused` suite must contain exactly the same three case IDs in the same order.
- `default` suite must remain unchanged.
- `all_registered` suite must contain exactly all 13 registered cases in canonical order.

- The `recovery_focused` suite matrix summary must be exactly:

```json
{
  "scenario_bucket_counts": {"family": 2, "mixed": 1},
  "level_counts": {"L2": 1, "L5": 2},
  "world_profile_counts": {"family_afternoon": 2, "rainy_day_fallback": 1},
  "failure_mode_counts": {
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1
  },
  "tag_counts": {
    "bad_weather": 1,
    "child_friendly": 2,
    "composite_failure": 2,
    "dining_unavailable": 1,
    "failure_injected": 3,
    "light_meal": 1,
    "rainy_day": 1,
    "route_failure": 2,
    "ticket_sold_out": 1
  }
}
```

- The `all_registered` suite matrix summary must be exactly:

```json
{
  "scenario_bucket_counts": {"couple": 1, "family": 7, "friends": 1, "mixed": 2, "solo": 1, "unknown": 1},
  "level_counts": {"L1": 3, "L2": 8, "L5": 2},
  "world_profile_counts": {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 7,
    "friends_gathering": 1,
    "rainy_day_fallback": 2,
    "solo_afternoon": 1
  },
  "failure_mode_counts": {
    "none": 10,
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1
  },
  "tag_counts": {
    "addon_optional": 1,
    "bad_weather": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 7,
    "citywalk": 2,
    "composite_failure": 2,
    "date_friendly": 1,
    "dining_unavailable": 1,
    "failure_injected": 3,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 3,
    "light_activity": 1,
    "light_meal": 6,
    "memory_override": 1,
    "outdoor_activity": 2,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 2,
    "route_failure": 2,
    "ticket_sold_out": 1
  }
}
```

- Keep the benchmark outcome rollup exclusion list unchanged for bookkeeping tags:
  - `baseline`
  - `failure_injected`
  - `route_failure`
- `composite_failure` is not a bookkeeping tag in this task and must remain visible in constraint-tag rollups.

- Add an additive `failure_chain_summary` to `BenchmarkCaseResult`.
- `failure_chain_summary` must include exactly:
  - `profile_id`
  - `injected_effects`
  - `recovery_actions`
  - `attempt_count`
  - `max_attempts`
  - `bounded`
  - `terminal_workflow_status`
- `injected_effects` must serialize as ordered unique strings in this exact format:
  - `<tool_name>:<effect_type>:<status>`
- Order must follow the first observed occurrence in tool-event order.
- `bounded` must be `true` when `attempt_count <= max_attempts`.
- `terminal_workflow_status` must come from the workflow result, not from benchmark grading.

- Add an additive `failure_chain_signature` to `BenchmarkReplaySummary`.
- `failure_chain_signature` must equal `failure_chain_summary.injected_effects`.
- Replay stable comparison must include `failure_chain_signature`.
- Replay must continue comparing:
  - benchmark status
  - workflow status
  - observed tool names
  - action count
  - injected failure count
  - recovery actions
- Replay must continue ignoring:
  - run IDs
  - trace IDs
  - report paths
  - timestamps
  - latencies
  - raw database IDs

- `BenchmarkHarness.run_case(load_benchmark_case("family_route_and_dining_unavailable_v1"))` must return:
  - benchmark `status="passed"`
  - workflow `status="failed"`
  - `action_count=0`
  - `failure_chain_summary.profile_id="route_and_dining_unavailable_v0"`
  - `failure_chain_summary.recovery_actions=["stop_safely"]`
  - `failure_chain_summary.bounded=true`

- `BenchmarkHarness.run_case(load_benchmark_case("rainy_day_ticket_sold_out_v1"))` must return:
  - benchmark `status="passed"`
  - workflow `status="failed"`
  - `action_count=0`
  - `failure_chain_summary.profile_id="ticket_sold_out_and_bad_weather_v0"`
  - `failure_chain_summary.recovery_actions=["stop_safely"]`
  - `failure_chain_summary.bounded=true`

- `BenchmarkHarness.run_cases(load_failure_benchmark_cases())` must return:
  - `3` case results
  - `run_status="passed"`
  - `passed_count=3`
  - `failed_count=0`
  - `error_count=0`

- `BenchmarkHarness.run_suite("recovery_focused")` must return:
  - `3` case results
  - `run_status="passed"`
  - report filename ending in `suite-recovery_focused-run-report.json`

- `BenchmarkHarness.run_suite("all_registered")` must return:
  - `13` case results
  - `run_status="passed"`

- Report sanitization rules must remain unchanged.
- Replay-report sanitization rules must remain unchanged.
- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not add new public routes, frontend UI, provider fallback behavior, or weather-aware routing semantics.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add cross-provider fallback, AMAP failover, or `provider timeout + fallback` product behavior.
- Do not make weather a first-class workflow routing or feasibility input in this task.
- Do not change deterministic recovery policy in `Task 051`.
- Do not add new Mock World fixture files.
- Do not change default non-failure suite membership.
- Do not add new frontend observability panels or public benchmark endpoints.
- Do not backfill or stage the missing `047`, `049`, or `050` spec/plan docs as part of this task.
- Do not commit local `var/` artifacts, `qc`, or unrelated local docs such as `docs/NEXT_PHASE_ROADMAP.md` and `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

- `BenchmarkCase.failure_profile`
- `build_benchmark_failure_injector(profile_id)`
- `ToolGateway.invoke(...)` for read tools during benchmark runs
- `load_failure_benchmark_cases()`
- `load_benchmark_suite("recovery_focused")`
- existing `BenchmarkReplayHarness`

### Outputs

- New supported benchmark failure profiles:
  - `route_and_dining_unavailable_v0`
  - `ticket_sold_out_and_bad_weather_v0`
- New benchmark cases:
  - `family_route_and_dining_unavailable_v1`
  - `rainy_day_ticket_sold_out_v1`
- Additive case-report field:
  - `BenchmarkCaseResult.failure_chain_summary`
- Additive replay-summary field:
  - `BenchmarkReplaySummary.failure_chain_signature`

### Schemas

Injected response-override tool event metadata example:

```json
{
  "error_type": "failure_injected_response",
  "message": "Benchmark response override injected for tool call.",
  "details": {
    "profile_id": "ticket_sold_out_and_bad_weather_v0",
    "rule_id": "ticket_sold_out_and_bad_weather_v0.check_weather",
    "tool_name": "check_weather",
    "effect_kind": "response_override",
    "effect_type": "bad_weather"
  }
}
```

Failure-chain summary example:

```json
{
  "profile_id": "route_and_dining_unavailable_v0",
  "injected_effects": [
    "check_queue:dining_unavailable:succeeded",
    "check_table_availability:dining_unavailable:succeeded",
    "check_route:route_infeasible:failed"
  ],
  "recovery_actions": ["stop_safely"],
  "attempt_count": 1,
  "max_attempts": 2,
  "bounded": true,
  "terminal_workflow_status": "failed"
}
```

Replay summary example:

```json
{
  "status": "passed",
  "workflow_status": "failed",
  "observed_tool_names": [
    "check_opening_hours",
    "check_queue",
    "check_route",
    "check_table_availability",
    "check_ticket_availability",
    "check_weather",
    "get_poi_detail",
    "search_poi"
  ],
  "action_count": 0,
  "injected_failure_count": 3,
  "recovery_actions": ["stop_safely"],
  "failure_chain_signature": [
    "check_queue:dining_unavailable:succeeded",
    "check_table_availability:dining_unavailable:succeeded",
    "check_route:route_infeasible:failed"
  ]
}
```

## 6. Observability

This task must not add a new telemetry backend.

It must preserve the existing benchmark-report and replay-report sanitization model while adding one additive explainability surface:

- `BenchmarkCaseResult.failure_chain_summary`

This summary is for benchmark report clarity and replay stability. It must remain sanitized and must not include:

- raw `tool_event_id`
- raw `action_id`
- secrets
- API keys
- tokens
- authorization headers
- raw tracebacks
- raw provider payload dumps outside the explicitly defined effect summaries

This task does not need to add a new internal API route or a new frontend panel.

## 7. Failure Handling

- Unknown `failure_profile` values must keep raising `BenchmarkHarnessError`.
- If a response-override rule is malformed or missing its response template, benchmark execution must fail explicitly rather than silently calling the provider.
- If a response-override rule resolves a required placeholder to an empty value, benchmark execution must fail explicitly rather than silently falling back to provider data.
- If a rule targets a write tool, failure profile construction must fail explicitly.
- If a composite failure case does not produce any bounded recovery metadata, the benchmark case must fail rather than silently passing.
- If a composite case report cannot build `failure_chain_summary`, benchmark execution must fail explicitly rather than omitting the field.
- Replay must fail when `failure_chain_signature` differs, even if the final benchmark status still matches.
- Existing database, Redis, LangSmith, and report-writing failure behavior must remain unchanged outside these additive checks.

## 8. Acceptance Criteria

- [ ] `docs/specs/052-chaos-harness-composite-failures-v0.md` exists and matches this task.
- [ ] `docs/plans/052-chaos-harness-composite-failures-v0-plan.md` exists and matches this task.
- [ ] `route_unavailable_v0` remains supported and unchanged.
- [ ] `route_and_dining_unavailable_v0` is supported.
- [ ] `ticket_sold_out_and_bad_weather_v0` is supported.
- [ ] Response-override injections write `tool_events` with `status="succeeded"` and `error_json.error_type="failure_injected_response"`.
- [ ] Hard injected failures still write `tool_events` with `status="failed"` and `error_json.error_type="failure_injected"`.
- [ ] No injected benchmark rule calls the underlying provider.
- [ ] `family_route_failure_v1` still passes unchanged as the legacy single-point failure case.
- [ ] `family_route_and_dining_unavailable_v1` loads and passes as a benchmark case.
- [ ] `rainy_day_ticket_sold_out_v1` loads and passes as a benchmark case.
- [ ] `load_failure_benchmark_cases()` returns exactly 3 cases in the order defined in this spec.
- [ ] `load_benchmark_suite("recovery_focused")` returns exactly the same 3 cases in the same order.
- [ ] `load_benchmark_suite("default")` remains exactly the current 10 non-failure cases.
- [ ] `load_benchmark_suite("all_registered")` returns exactly 13 cases in canonical order.
- [ ] The `recovery_focused` matrix summary exactly matches the counts defined in this spec.
- [ ] The `all_registered` matrix summary exactly matches the counts defined in this spec.
- [ ] Both new composite cases finish with workflow `status="failed"`, benchmark `status="passed"`, and `action_count=0`.
- [ ] Both new composite cases serialize `failure_chain_summary` with the exact field set defined in this spec.
- [ ] `failure_chain_summary.bounded` is `true` for both new composite cases.
- [ ] Replay stable comparison includes `failure_chain_signature`.
- [ ] Replaying either composite case report from disk produces replay `status="passed"` when the failure chain matches.
- [ ] Replay reports remain sanitized.
- [ ] No public API, frontend contract, provider fallback behavior, weather-aware planning logic, dependency, or migration is added.
- [ ] No `.env`, API key, token, secret, or unrelated local artifact is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The listed verification commands pass, or any blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing unrelated local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_failure_injection.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_replay.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_tool_gateway.py tests/integration/test_benchmark_harness_gateway.py -q
docker compose config
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add chaos harness composite failures
```

## 11. Notes for the Implementer

Keep this task intentionally inside the benchmark and tool-injection layer.

The user examples include `route unavailable + long queue`, `sold out + weather change`, and `provider timeout + fallback`. This v0 narrows that down on purpose:

1. `provider timeout + fallback` is out of scope because the repository does not yet have a benchmark-visible cross-provider fallback contract.
2. weather is currently captured but not consumed by deterministic workflow routing, so the weather override in `ticket_sold_out_and_bad_weather_v0` is for chaos-chain explainability and replay stability, not for new planning semantics.
3. the task should validate that multi-factor adverse inputs still produce bounded safe behavior and an explainable serialized chain, not redesign recovery itself.

If implementation pressure starts pulling in provider fallback, frontend work, or broader weather-aware routing logic, stop and narrow the change back down.
