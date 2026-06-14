# Spec: 100 Chaos Failure Combination Cases v0

## 1. Goal

Add the next combination-failure benchmark slice after Task `099` so WeekendPilot can validate a broader set of bounded recovery outcomes than the current three-case recovery suite. The repository already supports one single-point route failure and two composite failure cases, plus generic replay review over the whole `recovery_focused` suite. What is still missing is a fuller combination-failure pack and a focused gate that proves those failure cases all end safely, execute no write actions, and serialize an explainable failure chain.

After this task, the benchmark layer must support three additional combination-failure cases, `recovery_focused` must expand from `3` to `6` cases, `v2_integrity` and `all_registered` must reflect the new recovery inventory, and a new `safe_stop_gate_v1` artifact must verify that every recovery-focused case finishes as a bounded safe-stop outcome with zero write actions and an explainable failure-chain summary.

## 2. Project Context

This task primarily fits milestone `M5. Recovery / Chaos Harness` in `docs/NEXT_PHASE_ROADMAP.md`, because it expands recovery-oriented chaos coverage and turns that coverage into a stable benchmark artifact. It also directly supports `M1` integrity evidence, because Task `101` is supposed to aggregate existing gates and latest artifacts rather than inventing them on the fly.

It aligns with `docs/PROJECT_BLUEPRINT.md` in these areas:

- Failure handling and recovery
- Harness engineering
- LocalLife-Bench
- Human confirmation and execution safety
- Observability and replayable evidence

Relevant current repository state:

- `docs/specs` and `docs/plans` are continuous and matched through Task `099`.
- Task `052` already added the first composite-failure benchmark support.
- Task `099` already generalized replay review over the `recovery_focused` suite.
- Current registered benchmark inventory is `25` cases.
- Current suites are:
  - `default = 11`
  - `recovery_focused = 3`
  - `v2_integrity = 15`
  - `all_registered = 25`
- Current developer docs still contain stale `22/22` text and should be corrected where this task already touches benchmark inventory descriptions.

## 3. Requirements

- Keep `load_default_benchmark_cases()` unchanged.
- Keep `release_gate_v1` membership unchanged.
- Keep public workflow, benchmark report, replay report, and frontend contracts backward compatible.
- Keep the existing latest family replay alias behavior unchanged:
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Do not remove or rename the existing three recovery-focused cases.

- Add these exact benchmark failure profiles:
  - `ticket_sold_out_and_route_unavailable_v0`
  - `queue_closed_and_budget_constraint_v0`
  - `table_unavailable_and_replan_required_v0`

- `ticket_sold_out_and_route_unavailable_v0` must inject:
  - `check_ticket_availability` response override with `effect_type="ticket_sold_out"`
  - `check_route` hard failure with `effect_type="route_infeasible"`

- `queue_closed_and_budget_constraint_v0` must inject:
  - `check_queue` response override with `effect_type="queue_closed"`

- `table_unavailable_and_replan_required_v0` must inject:
  - `check_table_availability` response override with `effect_type="table_unavailable"`

- The exact injected response payloads must be:
  - `ticket_sold_out_and_route_unavailable_v0.check_ticket_availability`
    - top-level key `ticket_availability`
    - `poi_id="{poi_id}"`
    - `available=false`
    - `time_slots=[]`
    - `remaining=0`
    - `price_cents=0`
  - `queue_closed_and_budget_constraint_v0.check_queue`
    - top-level key `queue`
    - `poi_id="{poi_id}"`
    - `status="closed"`
    - `wait_minutes=120`
    - `parties_ahead=24`
  - `table_unavailable_and_replan_required_v0.check_table_availability`
    - top-level key `table_availability`
    - `restaurant_id="{restaurant_id}"`
    - `available=false`
    - `time_slots=[]`
    - `max_party_size=0`
    - `notes="Chaos profile injected unavailable table capacity."`

- `failure_profile_metadata(...)` must expose sanitized metadata for all six supported failure profiles after this task.
- Response overrides must remain read-tool only.
- None of the injected rules may call the provider.

- Add these exact benchmark cases:
  - `family_ticket_sold_out_and_route_unavailable_v1`
  - `budget_queue_closed_constraint_v1`
  - `family_table_unavailable_replan_required_v1`

- `family_ticket_sold_out_and_route_unavailable_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `failure_profile="ticket_sold_out_and_route_unavailable_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_action_count=0`
  - `min_injected_failure_count=2`
  - taxonomy:
    - `scenario_bucket="family"`
    - `level="L5"`
    - `failure_mode="ticket_sold_out_and_route_unavailable"`
    - tags must include:
      - `child_friendly`
      - `composite_failure`
      - `failure_injected`
      - `route_failure`
      - `ticket_sold_out`

- `budget_queue_closed_constraint_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="budget_lite"`
  - `failure_profile="queue_closed_and_budget_constraint_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_action_count=0`
  - `min_injected_failure_count=1`
  - taxonomy:
    - `scenario_bucket="mixed"`
    - `level="L5"`
    - `failure_mode="queue_closed_and_budget_constraint"`
    - tags must include:
      - `budget_limited`
      - `composite_failure`
      - `failure_injected`

- `family_table_unavailable_replan_required_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="family_afternoon"`
  - `failure_profile="table_unavailable_and_replan_required_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_action_count=0`
  - `min_injected_failure_count=1`
  - taxonomy:
    - `scenario_bucket="family"`
    - `level="L5"`
    - `failure_mode="table_unavailable_and_replan_required"`
    - tags must include:
      - `child_friendly`
      - `composite_failure`
      - `failure_injected`
      - `replan_turn`

- The new canonical `recovery_focused` order must be exactly:
  1. `family_route_failure_v1`
  2. `family_route_and_dining_unavailable_v1`
  3. `rainy_day_ticket_sold_out_v1`
  4. `family_ticket_sold_out_and_route_unavailable_v1`
  5. `budget_queue_closed_constraint_v1`
  6. `family_table_unavailable_replan_required_v1`

- `load_failure_benchmark_cases()` must return exactly those six case IDs in that order.
- `v2_integrity` must expand from `15` to exactly `18` cases by inheriting the expanded `recovery_focused` inventory.
- `all_registered` must expand from `25` to exactly `28` cases.
- `default` and `release_gate_v1` must remain unchanged.

- Add a new focused gate:
  - module: `backend/app/benchmark/safe_stop_gate.py`
  - CLI wrapper: `scripts/run_benchmark_safe_stop_gate.py`
  - gate id: `safe_stop_gate_v1`
  - suite id: `recovery_focused`
  - latest alias path: `var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json`

- `safe_stop_gate_v1` must validate:
  - suite `run_status == "passed"`
  - `case_count == 6`
  - `passed_count == 6`
  - `failed_count == 0`
  - `error_count == 0`
  - every case result has `workflow_status == "failed"`
  - every case result has `action_count == 0`
  - every case result has `failure_chain_summary`
  - every case result has `failure_chain_summary.bounded == true`
  - every case result has final recovery action `stop_safely`
  - at least one case has a multi-step recovery chain that contains `replace_candidate` before terminal safe stop
  - exact failure-mode coverage includes one case each for:
    - `route_unavailable`
    - `route_and_dining_unavailable`
    - `ticket_sold_out_and_bad_weather`
    - `ticket_sold_out_and_route_unavailable`
    - `queue_closed_and_budget_constraint`
    - `table_unavailable_and_replan_required`

- The gate report enrichment must be additive only and must write `safe_stop_gate_evaluation` into the suite report with:
  - `schema_version`
  - `gate_id`
  - `suite_id`
  - `release_blocked`
  - `blocking_failures`
  - `zero_action_case_count`
  - `bounded_case_count`
  - `terminal_safe_stop_case_count`
  - `multistep_recovery_case_count`
  - `failure_mode_counts`

- Recovery replay must stay green for the expanded `recovery_focused` suite.
- The existing no-arg recovery replay flow must remain unchanged.

- Update benchmark-facing gate constants and tests so they reflect the expanded inventory:
  - `coverage_gate_v1_5` must treat `all_registered` as `28` cases
  - `v2_integrity_gate` must treat `v2_integrity` as `18` cases
  - both gate families must include the three new failure modes in their expected minimums or expected passing maps

- Update developer-facing benchmark inventory text in `README.md` to remove stale `22/22` references touched by this task.
- Do not refresh the broader submission package in this task.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add frontend UI, internal dashboard UI, or public API changes.
- Do not add provider fallback, provider switching, or AMap changes.
- Do not redesign recovery policy beyond what is needed to express the three new deterministic benchmark cases.
- Do not change `default` or `release_gate_v1` membership.
- Do not widen this task into submission-doc package refresh, evidence-contract guardrails, or release verification.
- Do not commit generated `var/` benchmark artifacts.

## 5. Interfaces and Contracts

### Inputs

- `build_benchmark_failure_injector(profile_id)`
- `load_failure_benchmark_cases()`
- `load_benchmark_suite("recovery_focused")`
- `run_generic_recovery_replay_review(..., suite_id="recovery_focused")`
- `python scripts/run_benchmark_safe_stop_gate.py`

### Outputs

- New failure profiles:
  - `ticket_sold_out_and_route_unavailable_v0`
  - `queue_closed_and_budget_constraint_v0`
  - `table_unavailable_and_replan_required_v0`
- New benchmark cases:
  - `family_ticket_sold_out_and_route_unavailable_v1`
  - `budget_queue_closed_constraint_v1`
  - `family_table_unavailable_replan_required_v1`
- Expanded suites:
  - `recovery_focused = 6`
  - `v2_integrity = 18`
  - `all_registered = 28`
- New latest gate alias:
  - `var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json`

### Schemas

Safe-stop gate evaluation example:

```json
{
  "schema_version": "weekendpilot_safe_stop_gate_evaluation_v1",
  "gate_id": "safe_stop_gate_v1",
  "suite_id": "recovery_focused",
  "release_blocked": false,
  "blocking_failures": [],
  "zero_action_case_count": 6,
  "bounded_case_count": 6,
  "terminal_safe_stop_case_count": 6,
  "multistep_recovery_case_count": 1,
  "failure_mode_counts": {
    "route_unavailable": 1,
    "route_and_dining_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 1,
    "queue_closed_and_budget_constraint": 1,
    "table_unavailable_and_replan_required": 1
  }
}
```

Expected failure-chain signatures for the new cases:

```json
{
  "family_ticket_sold_out_and_route_unavailable_v1": [
    "check_ticket_availability:ticket_sold_out:succeeded",
    "check_route:route_infeasible:failed"
  ],
  "budget_queue_closed_constraint_v1": [
    "check_queue:queue_closed:succeeded"
  ],
  "family_table_unavailable_replan_required_v1": [
    "check_table_availability:table_unavailable:succeeded"
  ]
}
```

## 6. Observability

This task must not add a new telemetry backend.

It must continue using:

- benchmark case reports
- replay reports
- `failure_chain_summary`
- internal observability summaries
- latest gate aliases under `var/formal-benchmarks/`

Add one new additive artifact only:

- `safe_stop_gate_evaluation` embedded in the suite report written by `safe_stop_gate_v1`

The new artifact must remain sanitized and must not include:

- raw `action_id`
- raw `tool_event_id`
- secrets
- API keys
- tokens
- authorization headers
- raw provider payload dumps beyond the defined injected summaries
- tracebacks or debug traces

## 7. Failure Handling

- Unknown new failure profiles must raise `BenchmarkHarnessError`.
- If a new profile is malformed, benchmark execution must fail explicitly.
- If any new combination case runs write actions, the safe-stop gate must fail and must not refresh the latest alias.
- If a recovery-focused case is missing `failure_chain_summary`, the safe-stop gate must fail explicitly.
- If the multistep replan-required case does not record a recovery-action chain containing `replace_candidate` before terminal safe stop, the safe-stop gate must fail explicitly.
- If a gate run is blocked or errors, `latest-safe_stop_gate_v1-run-report.json` must not be overwritten.
- Existing family replay alias handling must remain unchanged.

## 8. Acceptance Criteria

- [ ] `ticket_sold_out_and_route_unavailable_v0` is supported.
- [ ] `queue_closed_and_budget_constraint_v0` is supported.
- [ ] `table_unavailable_and_replan_required_v0` is supported.
- [ ] `family_ticket_sold_out_and_route_unavailable_v1` loads and passes as a benchmark case.
- [ ] `budget_queue_closed_constraint_v1` loads and passes as a benchmark case.
- [ ] `family_table_unavailable_replan_required_v1` loads and passes as a benchmark case.
- [ ] `recovery_focused` expands from `3` to exactly `6` cases in canonical order.
- [ ] `load_failure_benchmark_cases()` returns those `6` recovery cases in canonical order.
- [ ] `v2_integrity` expands from `15` to exactly `18` cases.
- [ ] `all_registered` expands from `25` to exactly `28` cases.
- [ ] `default` remains exactly `11` cases.
- [ ] `release_gate_v1` remains unchanged.
- [ ] The three new cases finish with benchmark `status="passed"`, workflow `status="failed"`, and `action_count=0`.
- [ ] The three new cases write explainable `failure_chain_summary` values with the expected injected effect signatures.
- [ ] The table-unavailable replan-required case records a bounded multi-step recovery chain that includes `replace_candidate` before terminal safe stop.
- [ ] `python scripts/run_recovery_replay_review.py --suite-id recovery_focused` remains green against the expanded six-case suite.
- [ ] `safe_stop_gate_v1` exists and writes an additive `safe_stop_gate_evaluation`.
- [ ] `safe_stop_gate_v1` passes only when all six recovery-focused cases are bounded safe-stop outcomes with zero write actions.
- [ ] `coverage_gate_v1_5` and `v2_integrity_gate` expected counts and failure-mode expectations match the expanded inventory.
- [ ] `README.md` no longer contains stale `22/22` benchmark inventory text in the sections touched by this task.
- [ ] No `.env`, API key, token, secret, or generated `var/` artifact is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_failure_injection.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_recovery_replay_review.py tests/test_benchmark_coverage_gate.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/integration/test_tool_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_recovery_replay_review.py -q
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
python scripts/run_benchmark_safe_stop_gate.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add combination failure benchmark cases
```

## 11. Notes for the Implementer

Keep this task narrowly on benchmark inventory, recovery evidence, and one new gate artifact.

Important scope decisions:

- The new combinations extend the existing `recovery_focused` suite instead of creating a second overlapping recovery suite.
- `table unavailable + replan required` must stay inside the current bounded recovery system by producing a deterministic `replace_candidate -> stop_safely` chain, not a new multi-turn UI flow.
- Update `README.md` where this task already changes benchmark inventory wording, but leave broader submission-package refresh for later tasks.
- If the implementation starts pulling in frontend, provider fallback, or submission-doc overhaul, stop and narrow the change back down.
