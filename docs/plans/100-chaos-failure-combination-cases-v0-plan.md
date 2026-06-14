# 100 Chaos Failure Combination Cases v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand recovery-focused benchmark coverage with three new combination-failure cases and add a dedicated safe-stop gate that proves those cases fail safely, perform zero writes, and produce explainable recovery chains.

**Architecture:** Reuse the existing benchmark fixture, failure-profile, replay-review, and gate patterns. Add three new failure profiles plus three case JSON fixtures, widen the existing recovery suite and downstream aggregate suites, then add one focused gate module that evaluates `recovery_focused` results using already-serialized `failure_chain_summary` and case metadata rather than inventing a new report type.

**Tech Stack:** Python, Pydantic, FastAPI backend benchmark modules, pytest, SQLAlchemy-backed benchmark harness, Redis-backed runtime services, existing benchmark/replay scripts.

---

## 1. Spec Reference

Spec file:

```text
docs/specs/100-chaos-failure-combination-cases-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/generic-recovery-replay-v0`.
- Latest code commit is `ac408ec feat: generalize recovery replay review`.
- Latest completed task is `099`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `099`.
- Existing recovery inventory is:
  - `recovery_focused = 3`
  - `v2_integrity = 15`
  - `all_registered = 25`
- Existing recovery-focused cases are:
  - `family_route_failure_v1`
  - `family_route_and_dining_unavailable_v1`
  - `rainy_day_ticket_sold_out_v1`
- Existing first-generation composite failure support already exists in:
  - `backend/app/benchmark/failure_profiles.py`
  - `backend/app/tool_gateway/failure_injection.py`
  - `backend/app/benchmark/failure_chain.py`
- Existing generic recovery replay suite handling already exists from Task `099`.
- `README.md` still contains stale `22/22` benchmark text even though actual registered case count is already `25`.
- Unrelated local files must remain unstaged:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- `backend/app/benchmark/safe_stop_gate.py` - focused gate runner for the expanded `recovery_focused` suite that validates bounded safe-stop behavior and writes additive gate evaluation payloads.
- `scripts/run_benchmark_safe_stop_gate.py` - thin CLI wrapper for the new gate.
- `backend/app/benchmark/cases/family_ticket_sold_out_and_route_unavailable_v1.json` - family recovery case combining sold-out tickets and route failure.
- `backend/app/benchmark/cases/budget_queue_closed_constraint_v1.json` - budget-limited recovery case combining queue closure and tight budget constraints.
- `backend/app/benchmark/cases/family_table_unavailable_replan_required_v1.json` - family recovery case that forces a bounded `replace_candidate -> stop_safely` chain.

## 4. Files to Modify

- `backend/app/benchmark/failure_profiles.py` - register the three new failure profiles and their sanitized metadata.
- `backend/app/benchmark/fixtures.py` - register the three new case IDs in canonical order.
- `backend/app/benchmark/suites.py` - expand `recovery_focused`, transitively expand `v2_integrity` and `all_registered`, keep `default` and `release_gate_v1` unchanged.
- `backend/app/benchmark/__init__.py` - export the new gate entrypoint if the benchmark package surface should expose it.
- `backend/app/benchmark/coverage_gate.py` - update passing case-count and failure-mode minimums for the expanded inventory.
- `backend/app/benchmark/v2_integrity_gate.py` - update passing case-count, recovery-case-count, and failure-mode expectations.
- `tests/test_failure_injection.py` - add unit coverage for the three new profiles and their injected payloads.
- `tests/test_benchmark_suites.py` - lock canonical suite membership and exact counts after the expansion.
- `tests/test_benchmark_harness.py` - add new case fixture assertions, expected failure-chain signatures, and updated integrity summary counts.
- `tests/test_recovery_replay_review.py` - update `recovery_focused` suite expectations from `3` to `6` and add assertions for the new cases.
- `tests/test_benchmark_coverage_gate.py` - update mocked passing totals from `25/22-era` assumptions to the new `28`-case inventory and failure-mode map.
- `tests/test_benchmark_v2_integrity_gate.py` - update mocked passing totals from `15` to `18` and recovery minimums from `3` to `6`.
- `tests/integration/test_tool_gateway.py` - verify the new response-override and hard-failure profiles do not call the provider.
- `tests/integration/test_benchmark_harness_gateway.py` - run the three new recovery cases through the real harness and assert zero-write safe outcomes.
- `tests/integration/test_recovery_replay_review.py` - verify the generic replay review suite path remains green for the six-case recovery suite.
- `README.md` - update benchmark inventory counts and mention the new safe-stop gate artifact.

## 5. Implementation Steps

1. Lock the suite-shape changes in unit tests first.
   - [ ] Update `tests/test_benchmark_suites.py` expected case ID lists for:
     - `recovery_focused = 6`
     - `v2_integrity = 18`
     - `all_registered = 28`
   - [ ] Keep `default = 11` and `release_gate_v1` unchanged in tests.
   - [ ] Run the focused suite test module and confirm it fails before code changes.

2. Add the three new failure profiles without changing the failure-injection contract.
   - [ ] In `backend/app/benchmark/failure_profiles.py`, add:
     - `ticket_sold_out_and_route_unavailable_v0`
     - `queue_closed_and_budget_constraint_v0`
     - `table_unavailable_and_replan_required_v0`
   - [ ] Reuse existing `ToolFailureInjectionRule` capabilities only:
     - response override for ticket, queue, and table
     - hard failure for route
   - [ ] Do not add new injector semantics or write-tool injection.
   - [ ] Add failing tests in `tests/test_failure_injection.py` for each profile’s exact payload and effect metadata.
   - [ ] Run the focused failure-injection tests and make them pass.

3. Add the three new benchmark case fixtures.
   - [ ] Create `family_ticket_sold_out_and_route_unavailable_v1.json` with:
     - `world_profile = family_afternoon`
     - `scenario_bucket = family`
     - `failure_profile = ticket_sold_out_and_route_unavailable_v0`
     - final expected recovery action `stop_safely`
   - [ ] Create `budget_queue_closed_constraint_v1.json` with:
     - `world_profile = budget_lite`
     - `scenario_bucket = mixed`
     - `failure_profile = queue_closed_and_budget_constraint_v0`
     - final expected recovery action `stop_safely`
   - [ ] Create `family_table_unavailable_replan_required_v1.json` with:
     - `world_profile = family_afternoon`
     - `scenario_bucket = family`
     - `failure_profile = table_unavailable_and_replan_required_v0`
     - final expected recovery action `stop_safely`
     - taxonomy tag set including `replan_turn`
   - [ ] Keep all three cases `min_action_count = 0`.
   - [ ] Use titles and metadata focus strings that match the spec.

4. Register the new fixtures and widen the existing recovery suite.
   - [ ] Append the new case IDs to `backend/app/benchmark/fixtures.py` in canonical repository order.
   - [ ] Update `backend/app/benchmark/suites.py` so `recovery_focused` is exactly:
     1. `family_route_failure_v1`
     2. `family_route_and_dining_unavailable_v1`
     3. `rainy_day_ticket_sold_out_v1`
     4. `family_ticket_sold_out_and_route_unavailable_v1`
     5. `budget_queue_closed_constraint_v1`
     6. `family_table_unavailable_replan_required_v1`
   - [ ] Let `v2_integrity` and `all_registered` expand by reusing the shared suite constants.
   - [ ] Re-run `tests/test_benchmark_suites.py` and make exact membership assertions pass.

5. Prove the new cases through harness-level assertions.
   - [ ] In `tests/test_benchmark_harness.py`, add load assertions for the three new case fixtures.
   - [ ] Add new harness expectations:
     - `family_ticket_sold_out_and_route_unavailable_v1`
       - injected effects exactly:
         - `check_ticket_availability:ticket_sold_out:succeeded`
         - `check_route:route_infeasible:failed`
       - recovery actions exactly `["stop_safely"]`
     - `budget_queue_closed_constraint_v1`
       - injected effects exactly:
         - `check_queue:queue_closed:succeeded`
       - recovery actions exactly `["stop_safely"]`
     - `family_table_unavailable_replan_required_v1`
       - injected effects exactly:
         - `check_table_availability:table_unavailable:succeeded`
       - recovery actions end with `stop_safely`
       - chain includes `replace_candidate`
   - [ ] Update integrity-coverage expectations in harness tests:
     - `recovery_case_count = 6`
     - `v2_integrity case_count = 18`
     - `all_registered case_count = 28`

6. Keep replay review generic and update only suite-size expectations.
   - [ ] In `tests/test_recovery_replay_review.py`, update suite-run assertions from `3` to `6`.
   - [ ] Add explicit checks that the three new cases can participate in `--suite-id recovery_focused`.
   - [ ] Do not change the no-arg canonical family flow.
   - [ ] In `tests/integration/test_recovery_replay_review.py`, verify the six-case suite run writes all per-case artifacts and remains green.

7. Add the focused safe-stop gate using the existing gate pattern.
   - [ ] Create `backend/app/benchmark/safe_stop_gate.py`.
   - [ ] Mirror the structure of `coverage_gate.py` / `v2_integrity_gate.py`:
     - bootstrap runtime through existing formal-verification helpers or equivalent harness startup
     - run suite `recovery_focused`
     - compute case-level and aggregate safe-stop evaluation
     - write additive `safe_stop_gate_evaluation` into the suite report
     - refresh `latest-safe_stop_gate_v1-run-report.json` only on passing runs
   - [ ] Define exact gate checks:
     - `case_count == 6`
     - `passed_count == 6`
     - `failed_count == 0`
     - `error_count == 0`
     - `zero_action_case_count == 6`
     - `bounded_case_count == 6`
     - `terminal_safe_stop_case_count == 6`
     - `multistep_recovery_case_count >= 1`
     - `failure_mode_counts` includes the six expected recovery failure modes with count `1` each
   - [ ] Keep the gate report additive; do not add a new core benchmark schema type unless strictly required.

8. Add a thin CLI wrapper for the gate.
   - [ ] Create `scripts/run_benchmark_safe_stop_gate.py`.
   - [ ] Keep the script as a minimal import-and-exit wrapper.
   - [ ] Match existing script style from other benchmark gates.

9. Update gate and integration tests around aggregate inventory counts.
   - [ ] In `tests/test_benchmark_coverage_gate.py`, update mocked passing payloads to reflect:
     - `case_count = 28`
     - new failure-mode map with six non-`none` modes
   - [ ] In `tests/test_benchmark_v2_integrity_gate.py`, update mocked passing payloads to reflect:
     - `case_count = 18`
     - `recovery_case_count = 6`
     - expanded failure-mode counts
   - [ ] Add a focused unit test for `safe_stop_gate.py` that validates:
     - report enrichment
     - alias refresh rules
     - blocked-run behavior when any case writes actions or lacks bounded failure-chain data
   - [ ] In `tests/integration/test_benchmark_harness_gateway.py`, add real harness assertions for the three new cases and, if practical, a focused safe-stop gate smoke test.

10. Update developer-facing docs only where this task already touches benchmark inventory.
    - [ ] In `README.md`, replace stale `22/22` references with current inventory wording consistent with the expanded suite.
    - [ ] Mention:
      - `recovery_focused = 6`
      - `all_registered = 28`
      - new `safe_stop_gate_v1` latest alias
    - [ ] Do not update the broader submission-package docs in this task.

11. Run focused verification and inspect git state carefully.
    - [ ] Run unit tests.
    - [ ] Run integration tests.
    - [ ] Run `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`.
    - [ ] Run `python scripts/run_benchmark_safe_stop_gate.py`.
    - [ ] Run `git diff --check`.
    - [ ] Confirm no `var/` output and no unrelated local docs are staged.

## 6. Testing Plan

- Unit tests:
  - `tests/test_failure_injection.py`
  - `tests/test_benchmark_suites.py`
  - `tests/test_benchmark_harness.py`
  - `tests/test_recovery_replay_review.py`
  - `tests/test_benchmark_coverage_gate.py`
  - `tests/test_benchmark_v2_integrity_gate.py`
  - new safe-stop gate unit coverage
- Integration tests:
  - `tests/integration/test_tool_gateway.py`
  - `tests/integration/test_benchmark_harness_gateway.py`
  - `tests/integration/test_recovery_replay_review.py`
- Smoke tests:
  - `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`
  - `python scripts/run_benchmark_safe_stop_gate.py`
- Explicit non-tests:
  - no frontend tests
  - no new public API tests
  - no AMap or provider-fallback tests
  - no submission-package evidence refresh in this task

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_failure_injection.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_recovery_replay_review.py tests/test_benchmark_coverage_gate.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/integration/test_tool_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_recovery_replay_review.py -q
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
python scripts/run_benchmark_safe_stop_gate.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add combination failure benchmark cases
```

Expected commands:

```bash
git status --short
git switch -c codex/100-chaos-failure-combination-cases-v0
git add backend/app/benchmark/failure_profiles.py
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/suites.py
git add backend/app/benchmark/safe_stop_gate.py
git add backend/app/benchmark/__init__.py
git add backend/app/benchmark/coverage_gate.py
git add backend/app/benchmark/v2_integrity_gate.py
git add backend/app/benchmark/cases/family_ticket_sold_out_and_route_unavailable_v1.json
git add backend/app/benchmark/cases/budget_queue_closed_constraint_v1.json
git add backend/app/benchmark/cases/family_table_unavailable_replan_required_v1.json
git add scripts/run_benchmark_safe_stop_gate.py
git add tests/test_failure_injection.py
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/test_recovery_replay_review.py
git add tests/test_benchmark_coverage_gate.py
git add tests/test_benchmark_v2_integrity_gate.py
git add tests/integration/test_tool_gateway.py
git add tests/integration/test_benchmark_harness_gateway.py
git add tests/integration/test_recovery_replay_review.py
git add README.md
git diff --cached --check
git commit -m "feat: add combination failure benchmark cases"
git push -u origin codex/100-chaos-failure-combination-cases-v0
```

The implementer must confirm the staged set does not include:

- `var/`
- `docs/NEW_WORKFLOW_PROMPT.md`
- `docs/TASK_INFO.md`
- `docs/superpowers/`
- any `.env` file
- any secrets or local-only artifacts

## 9. Out-of-scope Changes

- Do not add frontend surfaces or internal observability panels.
- Do not modify public API routes.
- Do not add provider fallback or AMap behavior.
- Do not redesign the core recovery policy beyond what is needed for deterministic benchmark expectations.
- Do not change `default` or `release_gate_v1`.
- Do not update submission-package docs, evidence-map docs, or release scripts beyond the minimal README benchmark inventory corrections.
- Do not add dependencies or migrations.
- Do not commit generated benchmark artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/100-chaos-failure-combination-cases-v0.md`.
- [ ] The three new failure profiles exist with the expected injected payloads and metadata.
- [ ] The three new benchmark cases exist with the expected IDs, world profiles, failure profiles, and final recovery action `stop_safely`.
- [ ] `recovery_focused` now contains exactly six cases in canonical order.
- [ ] `v2_integrity` now contains exactly eighteen cases.
- [ ] `all_registered` now contains exactly twenty-eight cases.
- [ ] The three new cases finish with `action_count == 0`.
- [ ] The new cases produce the expected `failure_chain_summary` signatures.
- [ ] The replan-required case records a bounded chain containing `replace_candidate` before terminal stop.
- [ ] `run_recovery_replay_review.py --suite-id recovery_focused` remains green.
- [ ] `safe_stop_gate_v1` writes an additive evaluation payload and latest alias only on pass.
- [ ] Coverage-gate and v2-integrity-gate expectations match the expanded inventory.
- [ ] README benchmark inventory text touched by this task is no longer stale.
- [ ] Required verification commands passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, unrelated local doc draft, or generated `var/` artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final canonical six-case `recovery_focused` order.
- The final `v2_integrity` case count.
- The final `all_registered` case count.
- The exact injected-effect signatures observed for the three new cases.
- The exact recovery-action chain observed for `family_table_unavailable_replan_required_v1`.
- The path to the generated `latest-safe_stop_gate_v1-run-report.json` alias during verification.
- The verification commands run and their results.
- The commit hash and push result.
- Confirmation that the no-arg family replay-review alias remained unchanged.
- Confirmation that no provider fallback, frontend work, or generated `var/` artifacts were committed.
