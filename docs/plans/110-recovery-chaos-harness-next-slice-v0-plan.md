# Recovery Chaos Harness Next Slice v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 2 new composite-failure benchmark cases that broaden recovery-chaos coverage, keep the safe-stop gate green, and preserve the canonical no-arg recovery-review path.

**Architecture:** Reuse the existing benchmark fixture, failure-profile, replay-review, and safe-stop gate patterns. Add 2 case JSON fixtures that reference existing failure profiles, widen the recovery suite memberships transitively, and update the count-based tests and docs so they all agree on the new inventory. Do not change recovery policy or introduce new providers.

**Tech Stack:** Python, FastAPI backend, Pydantic, pytest, Docker Compose, Mock World benchmark harness.

---

## 1. Spec Reference

Spec file:

```text
docs/specs/110-recovery-chaos-harness-next-slice-v0.md
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

- Current branch: `codex/memory-user-control-baseline-v0`
- Latest completed numbered task: `109`
- Latest commit:
  ```text
  3a90433 feat: add memory user control baseline
  ```
- `docs/specs/` and `docs/plans/` are continuous and matched through `109`.
- There is no tracked `110` spec or plan yet.
- Untracked local files that are unrelated to this task must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Current recovery stack already exists:
  - `route_unavailable_v0`
  - `route_and_dining_unavailable_v0`
  - `ticket_sold_out_and_bad_weather_v0`
  - `ticket_sold_out_and_route_unavailable_v0`
  - `queue_closed_and_budget_constraint_v0`
  - `table_unavailable_and_replan_required_v0`
- Current recovery suite size is 6, and the safe-stop gate currently asserts that 6-case inventory.
- Current benchmark counts in code/tests still reflect:
  - `recovery_focused = 6`
  - `v2_integrity = 18`
  - `all_registered = 28`
- The recovery-review tooling already supports suite selection, so this task should only adjust suite membership and count assertions.

## 3. Files to Add

- `backend/app/benchmark/cases/friends_route_and_dining_unavailable_v1.json` - new friends persona composite failure case.
- `backend/app/benchmark/cases/elder_ticket_sold_out_and_route_unavailable_v1.json` - new elder persona composite failure case.
- `docs/specs/110-recovery-chaos-harness-next-slice-v0.md` - save the spec from this task.
- `docs/plans/110-recovery-chaos-harness-next-slice-v0-plan.md` - save this implementation plan.

## 4. Files to Modify

- `backend/app/benchmark/suites.py` - add the 2 new case IDs to `recovery_focused`, `v2_integrity`, and `all_registered`.
- `backend/app/benchmark/safe_stop_gate.py` - update the expected safe-stop counts and failure-mode counts for the expanded 8-case suite.
- `README.md` - update the recovery/gate count text that mentions `recovery_focused`, `safe_stop_gate_v1`, `v2_integrity`, and `all_registered`.
- `docs/WEB_DEMO_README.md` - clarify that the canonical no-arg recovery review path remains family-first, while `--suite-id recovery_focused` is additive engineering verification.
- `tests/test_benchmark_suites.py` - update exact suite memberships and matrix summaries.
- `tests/test_benchmark_harness.py` - update suite expectations and add assertions for the 2 new case fixtures.
- `tests/test_benchmark_safe_stop_gate.py` - update the 6-case expectations to 8-case expectations.
- `tests/test_recovery_replay_review.py` - update recovery-suite expectations and add assertions for the new cases if needed.
- `tests/test_benchmark_internal_summary.py` - update recovery/v2/all-registered counts and rollups.
- `tests/test_benchmark_coverage_gate.py` - update `all_registered` count expectations.
- `tests/test_benchmark_v2_integrity_gate.py` - update `v2_integrity` count expectations.
- `tests/integration/test_benchmark_harness_gateway.py` - add gateway-backed assertions for the 2 new cases and the expanded suite counts.
- `tests/integration/test_recovery_replay_review.py` - verify the suite selector stays green with the expanded 8-case suite.
- `tests/integration/test_benchmark_coverage_gate.py` - update the count-based integration assertions.
- `tests/integration/test_benchmark_v2_integrity_gate.py` - update the count-based integration assertions.

## 5. Implementation Steps

1. Add the 2 new benchmark case fixtures.
   - Create both JSON files under `backend/app/benchmark/cases/`.
   - Reuse existing failure profiles only.
   - Keep the same required read-tool set and zero-action safe-stop expectations as the existing recovery cases.
   - Make the friends case use `friends_gathering`.
   - Make the elder case use `elder_afternoon`.

2. Update the canonical suite catalog.
   - Edit `backend/app/benchmark/suites.py`.
   - Insert the 2 new case IDs into `recovery_focused` in the exact canonical order from the spec.
   - Let `v2_integrity` and `all_registered` inherit the new recovery inventory.
   - Keep `default` and `release_gate_v1` unchanged.
   - Keep the `failures -> recovery_focused` alias unchanged.

3. Update the safe-stop gate for the expanded recovery suite.
   - Edit `backend/app/benchmark/safe_stop_gate.py`.
   - Change the expected recovery suite case count from 6 to 8.
   - Update the exact failure-mode counts to reflect the 2 additional cases.
   - Preserve the existing additive evaluation payload structure.
   - Do not change the gate schema or the alias behavior.

4. Update count-based tests and benchmark expectations.
   - Edit `tests/test_benchmark_suites.py`, `tests/test_benchmark_harness.py`, `tests/test_benchmark_internal_summary.py`, `tests/test_benchmark_coverage_gate.py`, and `tests/test_benchmark_v2_integrity_gate.py`.
   - Update any hard-coded suite sizes and matrix summaries from `6/18/28` to `8/20/30` where applicable.
   - Add exact assertions that both new cases remain benchmark `passed`, workflow `failed`, `action_count == 0`, and `failure_chain_summary.terminal_workflow_status == "failed"`.

5. Update recovery/replay and gateway regression coverage.
   - Edit `tests/test_recovery_replay_review.py` and `tests/integration/test_recovery_replay_review.py`.
   - Ensure the expanded `recovery_focused` suite still runs green with 8 cases.
   - Keep the canonical no-arg `family_route_failure_v1` path unchanged.
   - Add or update assertions that the new cases preserve the expected failure-chain signatures.
   - Edit `tests/integration/test_benchmark_harness_gateway.py` to assert:
     - `workflow_node_history` includes `apply_recovery`
     - `workflow_node_history` excludes `wait_confirmation`
     - `workflow_node_history` excludes `saga_execution_engine`
     - `action_count == 0`
   - Use the same style already present in the repository for gateway-backed regression checks.

6. Update the docs that describe recovery review and benchmark counts.
   - Edit `README.md` and `docs/WEB_DEMO_README.md`.
   - Keep the canonical family no-arg reviewer flow as the default.
   - Explain that `--suite-id recovery_focused` is an additive engineering verification path.
   - Update any visible `recovery_focused`, `safe_stop_gate_v1`, `v2_integrity`, or `all_registered` counts that changed because of this task.

7. Run verification and prepare the commit.
   - Run the focused pytest selection first.
   - Start PostgreSQL and Redis, run Alembic, then run the integration tests.
   - Run `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`.
   - Run `python scripts/run_benchmark_safe_stop_gate.py`.
   - Check `git diff --check` and `git status --short`.
   - Commit only task-relevant files with `feat: expand recovery chaos harness coverage`.

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_suites.py`
    - exact `recovery_focused`, `v2_integrity`, and `all_registered` memberships
    - exact matrix summaries
  - `tests/test_benchmark_harness.py`
    - the 2 new cases load correctly
    - both cases have `action_count == 0`
    - both cases end in safe-stop recovery
  - `tests/test_benchmark_safe_stop_gate.py`
    - 8-case gate expectations
    - updated failure-mode counts
  - `tests/test_recovery_replay_review.py`
    - suite selector stays green
    - canonical no-arg reviewer path remains family-first
  - `tests/test_benchmark_internal_summary.py`
    - updated suite counts and rollups
  - `tests/test_benchmark_coverage_gate.py`
    - updated all-registered count expectations
  - `tests/test_benchmark_v2_integrity_gate.py`
    - updated v2 integrity count expectations
- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py`
    - both new cases
    - no human-confirmation crossing
    - no write-side effects
  - `tests/integration/test_recovery_replay_review.py`
    - expanded `recovery_focused` suite
  - `tests/integration/test_benchmark_coverage_gate.py`
    - updated all-registered count expectations
  - `tests/integration/test_benchmark_v2_integrity_gate.py`
    - updated v2 integrity count expectations
- Smoke tests:
  - `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`
  - `python scripts/run_benchmark_safe_stop_gate.py`

## 7. Verification Commands

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: expand recovery chaos harness coverage
```

Expected commands:

```bash
git status --short
git switch -c codex/110-recovery-chaos-harness-next-slice-v0
git add backend/app/benchmark/suites.py backend/app/benchmark/safe_stop_gate.py backend/app/benchmark/cases/friends_route_and_dining_unavailable_v1.json backend/app/benchmark/cases/elder_ticket_sold_out_and_route_unavailable_v1.json README.md docs/WEB_DEMO_README.md tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_safe_stop_gate.py tests/test_recovery_replay_review.py tests/test_benchmark_internal_summary.py tests/test_benchmark_coverage_gate.py tests/test_benchmark_v2_integrity_gate.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_recovery_replay_review.py tests/integration/test_benchmark_coverage_gate.py tests/integration/test_benchmark_v2_integrity_gate.py docs/specs/110-recovery-chaos-harness-next-slice-v0.md docs/plans/110-recovery-chaos-harness-next-slice-v0-plan.md
git diff --cached --check
git commit -m "feat: expand recovery chaos harness coverage"
git push -u origin codex/110-recovery-chaos-harness-next-slice-v0
```

The implementer must confirm unrelated untracked files, generated artifacts, `.env`, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not add new failure profiles.
- Do not change recovery policy or retry semantics.
- Do not add real-provider or AMap behavior.
- Do not add frontend/UI changes.
- Do not add new benchmark gate types.
- Do not change `default` or `release_gate_v1`.
- Do not widen this task into broader memory-governance work.
- Do not stage `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, `docs/superpowers/`, `var/`, caches, virtual environments, or other unrelated local files.

## 10. Review Checklist

- [ ] Both new case fixtures exist and use existing failure profiles only.
- [ ] `recovery_focused` contains exactly 8 cases in the specified canonical order.
- [ ] `default` and `release_gate_v1` remained unchanged.
- [ ] `v2_integrity` became 20 cases and `all_registered` became 30 cases.
- [ ] Both new cases stay at `action_count == 0` and do not cross human confirmation.
- [ ] `safe_stop_gate_v1` still passes.
- [ ] `run_recovery_replay_review.py --suite-id recovery_focused` still passes.
- [ ] Recovery-review docs now explain the additive suite selector and preserve the canonical family no-arg path.
- [ ] Tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:
- changed files
- the exact 2 new case IDs
- updated `recovery_focused`, `v2_integrity`, and `all_registered` counts
- verification commands run and their results
- commit hash
- push result
- confirmation that the canonical family no-arg reviewer path stayed unchanged
- confirmation that both new cases stayed before human confirmation and had zero write actions
- any residual risk or follow-up task
