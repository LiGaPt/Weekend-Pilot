# Plan: 101 Benchmark Coverage Gate Convergence v0

## 1. Spec Reference

Spec file:

```text
docs/specs/101-benchmark-coverage-gate-convergence-v0.md
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

- Current branch is `codex/100-chaos-failure-combination-cases-v0`.
- Latest commit is `71f6ac5 feat: add combination failure benchmark cases`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `100`.
- There is no tracked `101` spec or plan yet.
- The repository code already reflects the expanded post-Task-100 benchmark inventory:
  - `all_registered = 28`
  - `v2_integrity = 18`
  - `recovery_focused = 6`
- A focused verification run currently fails:
  - `python -m pytest tests/integration/test_benchmark_coverage_gate.py tests/test_benchmark_suites.py tests/test_benchmark_v2_integrity_gate.py -q`
- The observed failure is:
  - `tests/integration/test_benchmark_coverage_gate.py` still expects `case_count == 22`
  - actual runtime result is `case_count == 28`
- Other nearby focused tests already pass:
  - `tests/test_benchmark_suites.py`
  - `tests/test_benchmark_v2_integrity_gate.py`
  - `tests/test_demo_support_scripts.py`
  - `tests/test_benchmark_internal_summary.py`
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- None.

## 4. Files to Modify

- `tests/integration/test_benchmark_coverage_gate.py` - update stale post-Task-100 benchmark coverage expectations.
- `docs/specs/101-benchmark-coverage-gate-convergence-v0.md` - save the approved spec.
- `docs/plans/101-benchmark-coverage-gate-convergence-v0-plan.md` - save the approved plan.

## 5. Implementation Steps

1. Read the current benchmark source-of-truth files before editing.
2. Confirm the canonical suite counts from `tests/test_benchmark_suites.py`.
3. Confirm the current gate thresholds and share-check logic from `backend/app/benchmark/coverage_gate.py`.
4. Reproduce the red test with:
   - `python -m pytest tests/integration/test_benchmark_coverage_gate.py -q`
5. Update `tests/integration/test_benchmark_coverage_gate.py` so its expected counts match the post-Task-100 repository contract.
6. Change `case_count` and `passed_count` assertions from `22` to `28`.
7. Change `benchmark_summary.case_count` assertions from `22` to `28`.
8. Change `coverage_gate_evaluation.coverage_thresholds.minimum_case_count` from `22` to `28`.
9. Change `coverage_gate_evaluation.observed_coverage.case_count` from `22` to `28`.
10. Replace the stale scenario bucket expectation map with:
    - `couple=1`
    - `elder=1`
    - `family=16`
    - `friends=2`
    - `mixed=4`
    - `solo=2`
    - `unknown=2`
11. Replace the stale world profile expectation map with:
    - `budget_lite=3`
    - `couple_afternoon=1`
    - `elder_afternoon=1`
    - `family_afternoon=16`
    - `friends_gathering=2`
    - `rainy_day_fallback=3`
    - `solo_afternoon=2`
12. Replace the stale failure mode expectation map with:
    - `none=22`
    - `queue_closed_and_budget_constraint=1`
    - `route_and_dining_unavailable=1`
    - `route_unavailable=1`
    - `table_unavailable_and_replan_required=1`
    - `ticket_sold_out_and_bad_weather=1`
    - `ticket_sold_out_and_route_unavailable=1`
13. Replace the stale constraint-tag expectation map with the current post-Task-100 counts already implied by the suite inventory:
    - `budget_limited=3`
    - `casual_dining=2`
    - `conversation_continuation=2`
    - `date_friendly=1`
    - `elder_friendly=1`
    - `friends_group=2`
    - `memory_governance=5`
    - `rainy_day=3`
    - `robustness_case=4`
14. Replace the stale share-ratio assertions with:
    - `family_scenario_share.observed_ratio == 0.5714`
    - `family_afternoon_world_profile_share.observed_ratio == 0.5714`
    - `non_failure_share.observed_ratio == 0.7857`
15. Keep the rest of the integration test unchanged if it already matches the current runtime contract.
16. Do not change `backend/app/benchmark/coverage_gate.py` unless the refreshed test still fails for a real code-contract mismatch.
17. Re-run:
    - `python -m pytest tests/integration/test_benchmark_coverage_gate.py -q`
18. Re-run the broader focused regression command:
    - `python -m pytest tests/integration/test_benchmark_coverage_gate.py tests/test_benchmark_suites.py tests/test_benchmark_v2_integrity_gate.py -q`
19. Re-run adjacent confidence checks:
    - `python -m pytest tests/test_demo_support_scripts.py tests/test_benchmark_internal_summary.py -q`
20. Run `git diff --check`.
21. Run `git status --short`.
22. Stage only:
    - `tests/integration/test_benchmark_coverage_gate.py`
    - the new `101` spec and plan files after they are saved in a later document-only step
23. Commit with the expected message.

## 6. Testing Plan

- Unit regressions:
  - `tests/test_benchmark_suites.py`
  - `tests/test_benchmark_v2_integrity_gate.py`
- Integration regression:
  - `tests/integration/test_benchmark_coverage_gate.py`
- Confidence checks:
  - `tests/test_demo_support_scripts.py`
  - `tests/test_benchmark_internal_summary.py`
- Non-tests:
  - no frontend tests
  - no API-route tests
  - no benchmark artifact refresh
  - no replay review or stability harness reruns unless convergence unexpectedly spills over

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
git status --short
git branch --show-current
python -m pytest tests/integration/test_benchmark_coverage_gate.py -q
python -m pytest tests/integration/test_benchmark_coverage_gate.py tests/test_benchmark_suites.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/test_demo_support_scripts.py tests/test_benchmark_internal_summary.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
test: align coverage gate integration expectations
```

Expected commands:

```bash
git status --short
git add tests/integration/test_benchmark_coverage_gate.py
git add docs/specs/101-benchmark-coverage-gate-convergence-v0.md
git add docs/plans/101-benchmark-coverage-gate-convergence-v0-plan.md
git diff --cached --check
git commit -m "test: align coverage gate integration expectations"
git push -u origin codex/101-benchmark-coverage-gate-convergence-v0
```

The implementer must confirm the staged set does not include:

- `var/`
- `docs/NEW_WORKFLOW_PROMPT.md`
- `docs/TASK_INFO.md`
- `docs/superpowers/`
- any `.env` file
- any secrets or local-only artifacts

## 9. Out-of-scope Changes

- Do not start `System Integrity Summary API`.
- Do not modify `backend/app/api/observability.py`.
- Do not modify `backend/app/benchmark/internal_summary.py`.
- Do not change benchmark suite membership, benchmark fixtures, or gate schemas.
- Do not update README, submission docs, or roadmap docs in this task.
- Do not add dependencies or migrations.
- Do not commit generated benchmark artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/101-benchmark-coverage-gate-convergence-v0.md`.
- [ ] The focused red test is green.
- [ ] Integration assertions now reflect `all_registered = 28`.
- [ ] Integration assertions now reflect the six recovery failure modes plus `none = 22`.
- [ ] Integration assertions now reflect the current share ratios `0.5714`, `0.5714`, and `0.7857`.
- [ ] `coverage_gate.py` runtime behavior was not changed unnecessarily.
- [ ] `tests/test_benchmark_suites.py` still passes.
- [ ] `tests/test_benchmark_v2_integrity_gate.py` still passes.
- [ ] `tests/test_demo_support_scripts.py` still passes.
- [ ] `tests/test_benchmark_internal_summary.py` still passes.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for unrelated pre-existing local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or generated artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- the exact assertions changed in `tests/integration/test_benchmark_coverage_gate.py`
- the final expected `case_count`
- the final expected scenario bucket counts
- the final expected failure mode counts
- the final expected share ratios
- the verification commands run and their results
- the commit hash
- the push result
- confirmation that no benchmark runtime code was changed unless a real contract defect was discovered
- confirmation that `System Integrity Summary API` work was not started in this task
