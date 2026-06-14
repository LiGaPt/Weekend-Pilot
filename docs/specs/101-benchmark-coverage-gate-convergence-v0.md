# Spec: 101 Benchmark Coverage Gate Convergence v0

## 1. Goal

WeekendPilot has already advanced the benchmark inventory through Task `100`, expanding the registered Mock World cases to `28`, the `recovery_focused` suite to `6`, and the `v2_integrity` suite to `18`. The repository code reflects those counts, but at least one focused integration test still asserts the older pre-Task-100 `22`-case coverage assumptions.

This task closes that convergence gap. After this task is complete, the benchmark coverage gate verification surface must be internally consistent again: focused integration tests must assert the current post-Task-100 suite counts, failure-mode coverage, and share ratios without forcing the code back to the obsolete inventory.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven, deterministic where possible, and observable by default. A red benchmark gate verification test means the repository can no longer reliably prove that its benchmark infrastructure is coherent. That makes this convergence task higher priority than adding new internal aggregation APIs.

Relevant current repository facts:

- `docs/specs/` and `docs/plans/` are continuous and matched through Task `100`.
- The latest commit is `71f6ac5 feat: add combination failure benchmark cases`.
- The current branch is `codex/100-chaos-failure-combination-cases-v0`.
- `backend/app/benchmark/suites.py` already defines:
  - `all_registered = 28`
  - `v2_integrity = 18`
  - `recovery_focused = 6`
- `backend/app/benchmark/coverage_gate.py` already expects the expanded post-Task-100 inventory.
- `tests/integration/test_benchmark_coverage_gate.py` still pins at least one obsolete `22`-case expectation and currently fails.

## 3. Requirements

- The implementation must restore green focused verification for the benchmark coverage gate after Task `100`.
- The implementation must treat the current code-level benchmark inventory as the source of truth unless a focused test proves the code contract itself is wrong.
- The implementation must update stale integration-test expectations from the obsolete `22`-case inventory to the current `28`-case inventory.
- The implementation must align integration assertions for:
  - `case_count`
  - `passed_count`
  - `benchmark_summary.case_count`
  - `coverage_gate_evaluation.coverage_thresholds.minimum_case_count`
  - `coverage_gate_evaluation.observed_coverage.case_count`
  - `scenario_bucket_counts`
  - `world_profile_counts`
  - `failure_mode_counts`
  - `constraint_tag_case_counts`
  - `family_scenario_share`
  - `family_afternoon_world_profile_share`
  - `non_failure_share`
- The implementation must use the same canonical post-Task-100 counts already validated in `tests/test_benchmark_suites.py`.
- The implementation must keep `coverage_gate.py` behavior unchanged if the failure is caused only by stale test expectations.
- If a focused verification run shows the production gate output is inconsistent with `tests/test_benchmark_suites.py`, the implementer must stop and report a broader contract drift instead of silently changing both sides.
- No public API, internal API, schema version, benchmark artifact format, or frontend behavior may change in this task.

## 4. Non-goals

- Do not implement `System Integrity Summary API`.
- Do not add or modify any frontend UI.
- Do not change `backend/app/api/observability.py`.
- Do not change benchmark suite membership or benchmark case fixtures.
- Do not change `release_gate_v1`, `v2_integrity_gate`, `safe_stop_gate_v1`, or stability-harness semantics.
- Do not refresh or commit canonical artifacts under `var/`.
- Do not modify unrelated docs, roadmap ordering, or submission-package content.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- `run_benchmark_coverage_gate(...)`
- `BenchmarkCoverageGateResult`
- suite metadata from `backend/app/benchmark/suites.py`
- focused integration assertions in `tests/integration/test_benchmark_coverage_gate.py`

### Outputs

- Updated focused integration assertions that match the current repository benchmark contract.
- A green verification surface for:
  - `tests/integration/test_benchmark_coverage_gate.py`
  - adjacent benchmark suite and gate regression checks

### Schemas

This task must not introduce a new runtime schema.

The expected post-Task-100 coverage surface is:

```json
{
  "case_count": 28,
  "scenario_bucket_counts": {
    "couple": 1,
    "elder": 1,
    "family": 16,
    "friends": 2,
    "mixed": 4,
    "solo": 2,
    "unknown": 2
  },
  "world_profile_counts": {
    "budget_lite": 3,
    "couple_afternoon": 1,
    "elder_afternoon": 1,
    "family_afternoon": 16,
    "friends_gathering": 2,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2
  },
  "failure_mode_counts": {
    "none": 22,
    "queue_closed_and_budget_constraint": 1,
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "table_unavailable_and_replan_required": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 1
  }
}
```

Expected share ratios for the focused integration assertion surface:

```json
{
  "family_scenario_share": 0.5714,
  "family_afternoon_world_profile_share": 0.5714,
  "non_failure_share": 0.7857
}
```

## 6. Observability

This task does not add new observability.

It only restores consistency for an existing verification surface that already depends on:

- benchmark suite reports
- coverage gate evaluation payloads
- deterministic count maps
- latest alias handling already implemented by `coverage_gate.py`

## 7. Failure Handling

Expected failure modes and required behavior:

- If only the integration assertions are stale:
  - update the assertions
  - keep gate code unchanged
- If the test failure reveals gate output drift from the canonical suite definitions:
  - stop and report the mismatch
  - do not silently modify code and tests together without identifying the source of truth
- If additional focused benchmark gate tests fail after the first update:
  - keep scope limited to post-Task-100 convergence
  - do not widen into unrelated benchmark refactors
- If verification requires changing artifact schemas, API routes, or suite membership:
  - stop and report that the task is no longer the minimal convergence fix

## 8. Acceptance Criteria

- [ ] `tests/integration/test_benchmark_coverage_gate.py` passes against the current post-Task-100 code.
- [ ] The focused regression command below passes without forcing code back to the obsolete `22`-case inventory.
- [ ] Integration assertions reflect `all_registered = 28`.
- [ ] Integration assertions reflect the current six recovery failure modes plus `none = 22`.
- [ ] Integration assertions reflect the current canonical share ratios:
  - `family_scenario_share = 0.5714`
  - `family_afternoon_world_profile_share = 0.5714`
  - `non_failure_share = 0.7857`
- [ ] `coverage_gate.py` runtime behavior is unchanged unless a focused test proves a real contract defect.
- [ ] No public or internal API response model changes.
- [ ] No benchmark suite membership changes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except for unrelated pre-existing local files.

## 9. Verification Commands

```bash
git status --short
git branch --show-current
python -m pytest tests/integration/test_benchmark_coverage_gate.py tests/test_benchmark_suites.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/test_demo_support_scripts.py tests/test_benchmark_internal_summary.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
test: align coverage gate integration expectations
```

## 11. Notes for the Implementer

Keep this task minimal and convergence-only.

Preferred sequencing:

1. use `tests/test_benchmark_suites.py` as the canonical count source
2. update only the stale coverage-gate integration assertions
3. rerun the focused gate and suite regression commands
4. stop if the code output itself no longer matches the suite contract

Do not begin Task `101-system-integrity-summary-api-v0` behavior in this change. The next API aggregation task should start only after this verification surface is green again.
