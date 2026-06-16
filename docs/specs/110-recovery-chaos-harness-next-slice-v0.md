# Spec: 110 Recovery Chaos Harness Next Slice v0

## 1. Goal

Add the next smallest recovery-chaos slice so WeekendPilot can validate more bounded safe-stop outcomes without changing recovery policy. This task extends the current `recovery_focused` benchmark inventory with 2 new composite-failure cases that broaden persona coverage beyond the current family-heavy mix, while keeping replay stability, human-confirmation safety, and write-side-effect safety intact.

After this task, the benchmark layer must:
- reuse existing failure-profile machinery
- add 2 new composite failure cases
- expand `recovery_focused`, `v2_integrity`, and `all_registered`
- keep `default` and `release_gate_v1` unchanged
- keep the canonical no-arg recovery review flow unchanged
- keep the safe-stop gate green with zero write actions and explainable failure chains

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in the failure-handling, harness-engineering, LocalLife-Bench, and observability areas. It stays inside the existing bounded recovery model: read-tool failure injection, deterministic recovery routing, replayable benchmark reports, and confirmation-safe execution boundaries.

`docs/NEXT_PHASE_ROADMAP.md` places this work in milestone `M5. Recovery / Chaos Harness`. Tasks `101` through `109` already closed the higher-priority benchmark/integrity/memory baseline slices, and Task `100` already established the first safe-stop composite recovery pack. This task is the next small M5 follow-up because it improves recovery coverage without introducing new policy, new providers, or new UI.

## 3. Requirements

- Add exactly 2 new benchmark cases, both using existing failure profiles:
  - `friends_route_and_dining_unavailable_v1`
  - `elder_ticket_sold_out_and_route_unavailable_v1`
- `friends_route_and_dining_unavailable_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="friends_gathering"`
  - `failure_profile="route_and_dining_unavailable_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_action_count=0`
  - `min_injected_failure_count=3`
  - taxonomy:
    - `scenario_bucket="friends"`
    - `level="L5"`
    - `tags=["composite_failure","dining_unavailable","failure_injected","friends_group","route_failure"]`
    - `failure_mode="route_and_dining_unavailable"`
  - metadata:
    - `focus="friends_route_and_dining_unavailable_safe_stop"`
- `elder_ticket_sold_out_and_route_unavailable_v1` must use:
  - `tool_profile="mock_world"`
  - `world_profile="elder_afternoon"`
  - `failure_profile="ticket_sold_out_and_route_unavailable_v0"`
  - `expected_workflow_status="failed"`
  - `expected_execution_status=null`
  - `expected_feedback_status=null`
  - `expected_error_type="recovery_stopped"`
  - `expected_recovery_action="stop_safely"`
  - `min_action_count=0`
  - `min_injected_failure_count=2`
  - taxonomy:
    - `scenario_bucket="elder"`
    - `level="L5"`
    - `tags=["composite_failure","elder_friendly","failure_injected","route_failure","ticket_sold_out"]`
    - `failure_mode="ticket_sold_out_and_route_unavailable"`
  - metadata:
    - `focus="elder_ticket_sold_out_route_unavailable_safe_stop"`
- Keep the required read-tool set unchanged for both new cases:
  - `search_poi`
  - `check_weather`
  - `get_poi_detail`
  - `check_opening_hours`
  - `check_queue`
  - `check_table_availability`
  - `check_ticket_availability`
  - `check_route`
- Expand `recovery_focused` to exactly 8 cases in this order:
  1. `family_route_failure_v1`
  2. `family_route_and_dining_unavailable_v1`
  3. `friends_route_and_dining_unavailable_v1`
  4. `rainy_day_ticket_sold_out_v1`
  5. `family_ticket_sold_out_and_route_unavailable_v1`
  6. `elder_ticket_sold_out_and_route_unavailable_v1`
  7. `budget_queue_closed_constraint_v1`
  8. `family_table_unavailable_replan_required_v1`
- `load_failure_benchmark_cases()` must return exactly those 8 cases in that order.
- `default` must remain exactly unchanged.
- `release_gate_v1` must remain exactly unchanged.
- `all_registered` must expand to exactly 30 cases.
- `v2_integrity` must expand to exactly 20 cases.
- The safe-stop gate must remain additive only and must not change recovery policy.
- The new cases must remain safe-stop only:
  - workflow result must fail
  - benchmark result must pass
  - `action_count == 0`
  - `failure_chain_summary.recovery_actions` must end in `stop_safely`
  - `failure_chain_summary.terminal_workflow_status == "failed"`
- The new cases must not cross the human confirmation boundary:
  - `workflow_node_history` must include `apply_recovery`
  - `workflow_node_history` must not include `wait_confirmation`
  - `workflow_node_history` must not include `saga_execution_engine`
- The new cases must not produce write-side effects:
  - no execution actions
  - no Action Ledger writes
  - no write tools before confirmation
- Keep replay stability intact:
  - canonical no-arg recovery review remains `family_route_failure_v1`
  - `--suite-id recovery_focused` must remain supported and green
- Update recovery-review docs so they state clearly that the canonical reviewer path remains the family no-arg flow and the suite selector is additive engineering verification only.

## 4. Non-goals

- Do not add new failure profiles.
- Do not change recovery routing policy, retry budgets, or confirmation behavior.
- Do not add real-provider or AMap dependencies.
- Do not change public demo routes or frontend UI.
- Do not add new benchmark gate types.
- Do not redesign the replay report schema.
- Do not change `default` or `release_gate_v1`.
- Do not widen this task into broader memory-governance or provider-fallback work.

## 5. Interfaces and Contracts

### Inputs

- Existing benchmark case loaders and suite loaders
- Existing failure profiles:
  - `route_and_dining_unavailable_v0`
  - `ticket_sold_out_and_route_unavailable_v0`
- Existing benchmark harness and replay harness
- Existing safe-stop gate runner

### Outputs

- Two new benchmark case JSON fixtures
- Updated benchmark suite memberships
- Updated safe-stop gate expectations
- Updated recovery-review and benchmark-count documentation
- Updated tests for suite counts, safe-stop behavior, and replay stability

### Schemas

New case fixture example:

```json
{
  "case_id": "friends_route_and_dining_unavailable_v1",
  "world_profile": "friends_gathering",
  "failure_profile": "route_and_dining_unavailable_v0",
  "expected": {
    "expected_workflow_status": "failed",
    "expected_recovery_action": "stop_safely",
    "min_action_count": 0,
    "min_injected_failure_count": 3
  }
}
```

## 6. Observability

No new telemetry backend is needed. This task must reuse:
- benchmark case reports
- replay reports
- `failure_chain_summary`
- safe-stop gate evaluation embedded in the suite report
- existing recovery-review artifacts

The added cases must remain fully sanitized and must not expose prompts, secrets, tokens, action IDs, tool-event IDs, or raw provider payload dumps.

## 7. Failure Handling

- Unknown case IDs or unknown failure profiles must keep failing explicitly.
- If the new cases ever reach `wait_confirmation` or write tools, tests must fail.
- If the new cases produce any write actions, the safe-stop gate must fail.
- If the suite counts drift from the specified 8/20/30 inventory, tests must fail.
- If the latest recovery alias is overwritten by a failed run, tests must fail.

## 8. Acceptance Criteria

- [ ] `docs/specs/110-recovery-chaos-harness-next-slice-v0.md` exists and matches this task.
- [ ] `docs/plans/110-recovery-chaos-harness-next-slice-v0-plan.md` exists and matches this task.
- [ ] `friends_route_and_dining_unavailable_v1` loads and passes as a benchmark case.
- [ ] `elder_ticket_sold_out_and_route_unavailable_v1` loads and passes as a benchmark case.
- [ ] `recovery_focused` contains exactly 8 cases in the canonical order defined above.
- [ ] `load_failure_benchmark_cases()` returns exactly those 8 cases.
- [ ] `default` remains unchanged.
- [ ] `release_gate_v1` remains unchanged.
- [ ] `v2_integrity` expands to exactly 20 cases.
- [ ] `all_registered` expands to exactly 30 cases.
- [ ] Both new cases finish with benchmark `status="passed"`, workflow `status="failed"`, and `action_count=0`.
- [ ] Both new cases serialize `failure_chain_summary` with `bounded == true` and `terminal_workflow_status == "failed"`.
- [ ] Both new cases stay before human confirmation and do not execute write actions.
- [ ] `python scripts/run_recovery_replay_review.py --suite-id recovery_focused` stays green with the expanded 8-case suite.
- [ ] `python scripts/run_benchmark_safe_stop_gate.py` stays green with the expanded 8-case suite.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` explain the expanded recovery slice and keep the canonical no-arg family path unchanged.
- [ ] No `.env`, API key, token, secret, or unrelated local artifact is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except pre-existing unrelated local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_safe_stop_gate.py tests/test_recovery_replay_review.py tests/test_benchmark_internal_summary.py tests/test_benchmark_coverage_gate.py tests/test_benchmark_v2_integrity_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_recovery_replay_review.py tests/integration/test_benchmark_coverage_gate.py tests/integration/test_benchmark_v2_integrity_gate.py -q
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
python scripts/run_benchmark_safe_stop_gate.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: expand recovery chaos harness coverage
```

## 11. Notes for the Implementer

This task is intentionally narrow:
- reuse the existing failure-profile machinery
- add only 2 new cases
- keep all recovery and confirmation semantics unchanged
- update suite counts and docs/tests only where the inventory changes

If implementation pressure starts pulling in new recovery policy, new provider behavior, or broader M5 memory work, stop and split that into a separate task.
