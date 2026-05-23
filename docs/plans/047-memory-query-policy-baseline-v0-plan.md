# Plan: 047 Memory Query Policy Baseline v0

## 1. Spec Reference

Spec file:

```text
docs/specs/047-memory-query-policy-baseline-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/demo-action-manifest-v0`.
- Latest completed numbered task is `046`.
- Latest commit is `8480cc9 feat: add demo action manifest summary`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `046`.
- There is no existing `047` spec, `047` plan, or `codex/memory-query-policy-baseline-v0` branch yet.
- `WeekendPilotWorkflowNodes.load_memory(...)` already loads active memory into workflow state, but `generate_queries(...)` does not consume that memory before calling `DeterministicQueryPlanner.build(...)`.
- `DeterministicQueryPlanner.build(...)` currently accepts only `LocalLifeIntent` plus `provider_profile`, so memory is not part of planning today.
- The benchmark harness currently injects `case.memory_items` into PostgreSQL before each run, including `family_memory_override_v1`.
- The repository already contains the semantic gap this task should close:
  - `backend/app/benchmark/cases/family_memory_override_v1.json` claims memory override coverage.
  - the workflow currently ignores loaded memory during planning.
- Focused baseline check already passed in the current workspace:

```text
python -m pytest tests/test_query_planner.py tests/test_benchmark_harness.py tests/test_langgraph_workflow.py -q
56 passed in 2.91s
```

- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.

## 3. Files to Add

- `backend/app/planning/memory_query_policy.py` - pure deterministic helper and compact summary model for memory-query policy application.
- `tests/test_memory_query_policy.py` - unit tests for supported projection, confidence threshold, explicit override, and unsupported-key behavior.

## 4. Files to Modify

- `backend/app/planning/schemas.py` - add `IntentParseSignals.activity_preferences`.
- `backend/app/planning/intent_parser.py` - parse explicit `indoor` / `outdoor` / `citywalk` activity-style signals and set the new parse signal.
- `backend/app/planning/query_planner.py` - use effective activity-style preferences in Mock World activity search tags and query selection.
- `backend/app/planning/__init__.py` - export the new memory-query policy helper and summary model if tests/importers need them.
- `backend/app/workflow/state.py` - add `intent_parse_signals` to workflow state.
- `backend/app/workflow/nodes.py` - store parse signals, apply memory-query policy before query planning, and persist the compact workflow memory-policy summary.
- `tests/test_intent_parser.py` - add explicit activity-style parsing and signal assertions.
- `tests/test_query_planner.py` - add assertions for style-tag propagation in Mock World planning.
- `tests/integration/test_benchmark_harness_gateway.py` - assert `family_memory_override_v1` now records a real `workflow.memory_policy` summary.

## 5. Implementation Steps

1. Add failing parser tests first.
   In `tests/test_intent_parser.py`, add exact assertions for:
   - explicit `indoor` text produces `intent.activity_preferences` containing `indoor`
   - explicit `citywalk` text produces `citywalk` instead of a broader outdoor style
   - `parsed.signals.activity_preferences` is `true` only for explicit style text
   - existing family/child parsing still leaves `child_friendly` behavior intact

2. Add failing pure memory-policy tests before implementation.
   Create `tests/test_memory_query_policy.py` with focused cases for:
   - a vague request plus high-confidence `spouse_lighter_meals` memory adds `lighter_options`
   - a vague request plus high-confidence `activity_style=indoor` adds `indoor`
   - low-confidence `activity_style` memory below `0.8000` is ignored
   - explicit user `indoor` request blocks conflicting high-confidence `activity_style=citywalk` memory
   - unsupported memory key is ignored and recorded under `unsupported_memory_keys`
   - summary contains no raw `text` or raw `value_json`

3. Add the failing query-planner regression tests.
   In `tests/test_query_planner.py`, add a focused case where an intent with `activity_preferences=["child_friendly", "indoor"]` produces:
   - a Mock World activity search call whose tags include `indoor`
   - `_mock_world_activity_query(...)` behavior that uses `indoor`
   Keep the existing dining preference and write-tool assertions unchanged.

4. Implement the pure memory-query policy helper.
   Add `backend/app/planning/memory_query_policy.py` with:
   - `MemoryQueryPolicySummary`
   - `apply_memory_query_policy(...)`
   Rules to implement exactly:
   - policy version is `memory_query_policy_v0`
   - supported keys are only `activity_style` and `spouse_lighter_meals`
   - confidence threshold is `Decimal("0.8000")`
   - normalize `activity_style` using `citywalk > indoor > outdoor`
   - normalize `spouse_lighter_meals` to `lighter_options`
   - explicit user signals win over memory
   - no duplicate preferences
   - summary stores only compact key/dimension lists and effective preference lists

5. Export the helper cleanly.
   Update `backend/app/planning/__init__.py` so the new helper and summary model are importable from the planning package for tests and workflow code. Do not add unrelated exports.

6. Extend parse signals and activity-style parsing.
   In `backend/app/planning/schemas.py`, add `activity_preferences: bool = False` to `IntentParseSignals`.
   In `backend/app/planning/intent_parser.py`:
   - keep existing `child_friendly` derivation
   - detect only explicit style text fragments
   - add at most one normalized style preference using the fixed priority
   - set `signals.activity_preferences = true` only when explicit style text was detected

7. Make query planning consume effective activity-style preferences.
   In `backend/app/planning/query_planner.py`:
   - treat supported style preferences `citywalk`, `indoor`, and `outdoor` as additional activity tags for Mock World activity search
   - update `_mock_world_activity_query(...)` to prefer those explicit/effective style values before existing fallbacks
   - leave AMAP logic unchanged in this task

8. Wire the memory-query policy into workflow state and run metadata.
   In `backend/app/workflow/state.py`, add `intent_parse_signals`.
   In `backend/app/workflow/nodes.py`:
   - change `parse_intent(...)` to use `parse_with_signals(...)`
   - persist both `parsed_intent` and `intent_parse_signals` into state
   - in `generate_queries(...)`, call `apply_memory_query_policy(...)` with:
     - `parsed_intent`
     - `intent_parse_signals`
     - `active_memories`
   - build the `QueryPlan` from the returned effective intent
   - persist the compact summary to `agent_runs.metadata_json["workflow"]["memory_policy"]`
   Keep all existing routing, agent assignment, and run-status behavior unchanged.

9. Add the benchmark integration proof.
   In `tests/integration/test_benchmark_harness_gateway.py`, add a dedicated case for `family_memory_override_v1` that:
   - runs the benchmark case through the real harness
   - asserts the case still passes
   - loads the persisted `AgentRun`
   - asserts `run.metadata_json["workflow"]["memory_policy"]["policy_version"] == "memory_query_policy_v0"`
   - asserts `ignored_low_confidence_keys` contains `activity_style`
   - asserts `user_override_dimensions` includes `activity_preferences`
   Do not make the integration assertion depend on exact plan ordering or public response wording.

10. Run focused verification and stage only task files.
    Run the commands from section 7.
    Before staging, confirm `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` remain unstaged.

## 6. Testing Plan

- Unit tests:
  - `tests/test_intent_parser.py` for explicit style parsing and signal behavior
  - `tests/test_memory_query_policy.py` for pure apply/ignore/override logic
  - `tests/test_query_planner.py` for style-tag propagation into Mock World planning
  - `tests/test_benchmark_harness.py` as a regression guard for benchmark metadata/report stability
- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py` for persisted `workflow.memory_policy` behavior on `family_memory_override_v1`
- Smoke tests:
  - run the full focused verification command set below
- Regression guard:
  - no change to public demo API shape
  - no change to replay/recovery/provider behavior
  - no new migration or dependency

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_intent_parser.py tests/test_query_planner.py tests/test_memory_query_policy.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add memory query policy baseline
```

Expected commands:

```bash
git status --short
git switch -c codex/memory-query-policy-baseline-v0
git add backend/app/planning/schemas.py
git add backend/app/planning/intent_parser.py
git add backend/app/planning/query_planner.py
git add backend/app/planning/__init__.py
git add backend/app/planning/memory_query_policy.py
git add backend/app/workflow/state.py
git add backend/app/workflow/nodes.py
git add tests/test_intent_parser.py
git add tests/test_query_planner.py
git add tests/test_memory_query_policy.py
git add tests/integration/test_benchmark_harness_gateway.py
git diff --cached --check
git commit -m "feat: add memory query policy baseline"
git push -u origin codex/memory-query-policy-baseline-v0
```

If task `046` has already been merged elsewhere before execution, recreate the new branch from the merged tip that already contains `8480cc9` or equivalent `046` content. Otherwise, branch from the current `046` tip.

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not add memory write-back, feedback learning, or user-editable memory features.
- Do not change benchmark suite membership or add new benchmark case files.
- Do not modify public demo API responses, frontend contracts, replay contracts, recovery contracts, or provider contracts.
- Do not add or modify Alembic revisions, database columns, or indexes.
- Do not add new dependencies.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `.env`, or other unrelated local files.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/047-memory-query-policy-baseline-v0.md`.
- [ ] `IntentParseSignals.activity_preferences` is additive and correct.
- [ ] Explicit `indoor` / `outdoor` / `citywalk` parsing works deterministically.
- [ ] High-confidence supported memory can supplement missing planning preferences.
- [ ] Low-confidence memory is ignored.
- [ ] Explicit user input overrides conflicting memory.
- [ ] `generate_queries(...)` now applies memory policy before query planning.
- [ ] Mock World activity search planning uses effective activity-style preferences.
- [ ] `workflow.memory_policy` metadata is persisted and sanitized.
- [ ] `family_memory_override_v1` integration coverage now proves memory-policy behavior.
- [ ] No migration, dependency, public API, replay, recovery, or frontend contract changed.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final `workflow.memory_policy` metadata shape.
- One example where memory was applied and one example where user input overrode memory.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no Alembic migration changed.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any remaining follow-up limitation, especially that memory write-back, memory CRUD, broader benchmark expansion, and user-facing memory controls remain future tasks.
