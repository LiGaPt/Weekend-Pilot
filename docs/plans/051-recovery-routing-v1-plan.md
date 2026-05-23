# Plan: 051 Recovery Routing v1

## 1. Spec Reference

Spec file:

```text
docs/specs/051-recovery-routing-v1.md
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

- Current branch is `codex/benchmark-l2-l3-suite-expansion-v0`.
- Latest code commit is `6cf0c15 feat: add benchmark suite coverage rollups`.
- On disk, `docs/specs/` and `docs/plans/` are continuous and matched through `050`.
- At authoring time in git-tracked state, the numbered spec/plan chain was only tracked through `048`.
- At authoring time, Task `047`, `049`, and `050` docs still existed only as local doc drafts outside Task `051`.
- Additional unrelated untracked local files currently exist:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`
- Those paths must remain unstaged during Task `051`.
- Focused baseline checks are currently green in this workspace:
  - benchmark and observability units: `67 passed`
  - agent and workflow units: `35 passed`
- The current recovery v0 shell already exists:
  - graph routing after `semantic_validator`
  - persisted `workflow.recovery.attempts`
  - internal recovery-path observability
- The current product gap is that `DeterministicValidatorRecoveryAgent` still emits only `none` or `stop_safely`.
- The public demo already supports:
  - `awaiting_clarification`
  - `DemoRunSummary.clarification`
  - `POST /demo/runs/{run_id}/clarify`

## 3. Files to Add

- `backend/app/agents/recovery_policy.py` - pure deterministic v1 recovery decision matrix and recovery-generated clarification helper.
- `tests/test_recovery_policy.py` - focused unit coverage for `replace_candidate`, `expand_search_radius`, `ask_user`, and `stop_safely` action selection.

## 4. Files to Modify

- `backend/app/agents/schemas.py` - add additive internal recovery evaluation context models.
- `backend/app/agents/deterministic.py` - wire the validator/recovery agent to the new pure v1 recovery policy.
- `backend/app/planning/query_planner.py` - add bounded search-breadth override so mock-world search limits can move from `5` to `8`.
- `backend/app/workflow/state.py` - add `search_expansion_level`, `excluded_candidate_pairs`, and update default recovery attempt expectations.
- `backend/app/workflow/recovery.py` - support `awaiting_clarification` as a valid terminal recovery outcome and keep route metadata bounded and typed.
- `backend/app/workflow/nodes.py` - build recovery evaluation context, consume `search_expansion_level`, exclude blocked draft pairs, apply recovery state mutations, persist clarification metadata, and persist richer recovery metadata.
- `backend/app/workflow/graph.py` - end safely when `apply_recovery` returns `awaiting_clarification`.
- `backend/app/workflow/runner.py` - initialize the new recovery state defaults.
- `README.md` - note that bounded recovery can now lead to `awaiting_clarification`.
- `docs/WEB_DEMO_README.md` - note that `/clarify` also handles recovery-driven clarification runs.
- `tests/test_agents.py` - update validator/recovery assertions away from the v0 stop-only behavior.
- `tests/test_query_planner.py` - add explicit search-breadth limit assertions.
- `tests/test_langgraph_workflow.py` - add unit coverage for `replace_candidate`, `expand_search_radius`, `ask_user`, and new route outcomes.
- `tests/test_demo_api.py` - assert recovery-driven `awaiting_clarification` still serializes through the existing public clarification shape.
- `tests/test_benchmark_harness.py` - keep the existing recovery expectation coverage aligned with the unchanged `family_route_failure_v1` behavior.
- `tests/integration/test_langgraph_workflow_gateway.py` - add gateway-backed routing and safety assertions for all four v1 actions.
- `tests/integration/test_demo_api_gateway.py` - add one end-to-end recovery-driven clarification scenario.
- `tests/integration/test_workflow_agents_gateway.py` - extend metadata-sanitization assertions for the new recovery fields.

## 5. Implementation Steps

1. Write the new pure policy tests first.
   Create `tests/test_recovery_policy.py` and lock the decision matrix before touching implementation.
   Cover at least these cases:
   - safe review -> `none`
   - safety-boundary failure -> `stop_safely`
   - route-wide route failure with no usable routes -> `stop_safely`
   - blocked first draft with a second current draft available -> `replace_candidate`
   - no draft and no dominating route-wide failure with `search_expansion_level=0` -> `expand_search_radius`
   - no draft after expansion or no deterministic alternative left -> `ask_user`
   - exact recovery-generated clarification prompt and `missing_fields` for:
     - `distance_flexibility`
     - `preference_tradeoff`

2. Add additive internal recovery context models.
   In `backend/app/agents/schemas.py`, add:
   - `RecoveryExcludedCandidatePair`
   - `RecoveryEvaluationContext`
   Keep these internal-only and additive.
   Model exactly:
   - `attempted_actions: list[str]`
   - `search_expansion_level: int`
   - `excluded_candidate_pairs: list[RecoveryExcludedCandidatePair]`
   - `screened_candidate_ids: list[str]`
   - `route_failure_codes: list[str]`

3. Implement the pure recovery decision module.
   Add `backend/app/agents/recovery_policy.py`.
   Put all action-selection logic here, not inside the workflow node.
   Implement pure helpers that:
   - classify safety-boundary failure check names
   - inspect `FinalReviewResult`, `ItineraryDraftResult`, and `RecoveryEvaluationContext`
   - detect route-wide `route_infeasible` dominance
   - decide whether a replacement candidate pair exists inside the current draft window
   - decide whether search breadth may still expand
   - build the exact two clarification prompt variants
   Return `RecoveryDecision` only.
   Do not mutate workflow state in this file.

4. Update `DeterministicValidatorRecoveryAgent`.
   In `backend/app/agents/deterministic.py`:
   - extend `review(...)` with keyword-only `recovery_context: RecoveryEvaluationContext | None = None`
   - keep the existing pass path unchanged
   - delegate blocked-path action selection to the new pure policy helper
   - keep the result role, status, and metadata sanitization behavior unchanged
   - ensure the new output still serializes `recovery_decision` exactly as the typed model

5. Add bounded search-breadth support to query planning.
   In `backend/app/planning/query_planner.py`:
   - add a keyword-only input such as `search_limit_override: int | None = None`
   - keep the default mock-world limit at `5`
   - when recovery passes the expanded level, use limit `8`
   - keep AMAP behavior unchanged
   - keep all existing query strings and tags unchanged
   Add focused tests in `tests/test_query_planner.py` for:
   - default limit `5`
   - expanded limit `8`
   - unchanged tags and query strings

6. Extend workflow state and defaults.
   In `backend/app/workflow/state.py`:
   - add `search_expansion_level: int`
   - add `excluded_candidate_pairs: list[dict[str, str]]` or a typed equivalent that stays JSON-safe in state updates
   Keep the rest of the recovery state intact.
   In `backend/app/workflow/runner.py`:
   - initialize `search_expansion_level=0`
   - initialize `excluded_candidate_pairs=[]`
   - change the default `max_recovery_attempts` from `1` to `2`

7. Make `generate_queries(...)` consume expansion state.
   In `backend/app/workflow/nodes.py`:
   - keep the existing order:
     - parse intent
     - load memory
     - apply memory policy
     - apply clarification policy
   - after clarification is ruled out, pass `search_limit_override` based on `search_expansion_level`
   - level `0` must produce limit `5`
   - level `1` must produce limit `8`
   - do not alter explicit user preferences or tags during expansion
   Persist recovery metadata after later recovery attempts, not during the initial happy path.

8. Make `logical_planner_agent(...)` consume excluded draft pairs.
   In `backend/app/workflow/nodes.py`:
   - keep calling the existing itinerary planner agent
   - after draft generation, filter out any draft whose `(activity.candidate_id, dining.candidate_id)` matches an item in `excluded_candidate_pairs`
   - preserve draft order after filtering
   - do not invent new drafts beyond the current generator output window
   - if filtering removes the first blocked draft and another current draft remains, let the next validation pass inspect the remaining ordered drafts
   Keep the rest of the planning path unchanged.

9. Build real recovery evaluation context inside the workflow.
   In `backend/app/workflow/nodes.py`, before calling `validator_recovery_agent.review(...)`, derive:
   - `attempted_actions` from existing `recovery_attempts`
   - `search_expansion_level` from state
   - `excluded_candidate_pairs` from state
   - `screened_candidate_ids` from `candidate_blackboard`
   - `route_failure_codes` from failed route evidence and failed enrichment tool results
   Pass that context into the validator.
   Do not leak raw tool payloads or IDs into the context.

10. Update route resolution for recovery-driven clarification.
    In `backend/app/workflow/recovery.py`:
    - keep routed loopbacks for `generate_queries` and `logical_planner_agent`
    - add `awaiting_clarification` as a valid terminal recovery route target
    - map `ask_user` to `awaiting_clarification`
    - keep `stop_safely` mapped to `failed`
    - keep typed attempt records and budgets explicit
    - use a distinct attempt status for `ask_user`, such as `awaiting_user`
    Do not allow new unsafe route targets.

11. Apply the new recovery mutations in `apply_recovery(...)`.
    In `backend/app/workflow/nodes.py`:
    - for `replace_candidate`:
      - identify the first current draft pair
      - append it to `excluded_candidate_pairs`
      - persist updated recovery metadata
      - set `active_recovery_route="logical_planner_agent"`
    - for `expand_search_radius`:
      - increment `search_expansion_level` to `1`
      - persist updated recovery metadata
      - set `active_recovery_route="generate_queries"`
    - for `ask_user`:
      - build the exact clarification summary from the current effective intent
      - persist it under `metadata_json["workflow"]["clarification"]`
      - persist updated recovery metadata
      - update run status to `awaiting_clarification`
      - set `active_recovery_route=None`
      - keep `error_json=None`
    - for `stop_safely`:
      - persist updated recovery metadata
      - update run status to `failed`
      - set structured `error_json`
      - set `active_recovery_route=None`

12. Update graph routing and terminal handling.
    In `backend/app/workflow/graph.py`:
    - extend `route_after_recovery(...)` to return `awaiting_clarification` when state status is that value
    - extend the `apply_recovery` conditional map so `awaiting_clarification` ends the graph safely
    Do not add any new edge that bypasses the normal confirmation path.
    `present_to_user`, `wait_confirmation`, and execution must still only happen through the existing reviewed-plan path.

13. Update docs last.
    In `README.md` and `docs/WEB_DEMO_README.md`:
    - note that `awaiting_clarification` can now happen after bounded recovery as well as before planning
    - note that the same `/demo/runs/{run_id}/clarify` endpoint continues the run
    Keep the documentation short and do not widen it into a new UX design.

14. Add workflow and gateway tests in two layers.
    In unit tests:
    - `tests/test_agents.py` should assert the validator now emits:
      - `replace_candidate` for a blocked-first-draft-with-alternative case
      - `expand_search_radius` for a draft-shortage case
      - `ask_user` after expansion is already used
      - `stop_safely` for safety-boundary failures
    - `tests/test_langgraph_workflow.py` should assert:
      - `ask_user` routes to `awaiting_clarification`
      - `expand_search_radius` routes to `generate_queries`
      - `replace_candidate` routes to `logical_planner_agent`
      - `route_after_recovery(...)` never jumps to execution
    - `tests/test_demo_api.py` should assert a recovery-generated clarification still serializes through the existing public shape
    In integration tests:
    - `tests/integration/test_langgraph_workflow_gateway.py` should add:
      - one `replace_candidate` scenario using a monkeypatched validator decision, verifying:
        - `logical_planner_agent` runs again
        - zero actions are recorded
        - excluded pair metadata is persisted
      - one `expand_search_radius` scenario using a monkeypatched validator decision, verifying:
        - `generate_queries` runs again
        - query planner is called with limit `8`
        - zero actions are recorded
      - one `ask_user` scenario using a monkeypatched validator decision, verifying:
        - result status is `awaiting_clarification`
        - clarification metadata is present
        - zero actions are recorded
      - keep the existing `stop_safely` integration and update only the new attempt-budget expectations if needed
    - `tests/integration/test_demo_api_gateway.py` should add one recovery-driven clarification run and then continue it through `/clarify`
    - `tests/integration/test_workflow_agents_gateway.py` should assert the new recovery metadata fields stay sanitized

15. Keep benchmark compatibility explicit.
    In `tests/test_benchmark_harness.py`:
    - keep `family_route_failure_v1` expecting `stop_safely`
    - keep `expected_error_type="recovery_stopped"`
    - do not add new case fixtures in this task
    The purpose here is regression protection, not new benchmark authoring.

16. Run verification and stage only Task `051`.
    Before staging:
    - confirm `git status --short` still shows the pre-existing unrelated untracked docs and runtime paths
    - confirm the new task does not stage:
      - `docs/NEXT_PHASE_ROADMAP.md`
      - `docs/TASK_WORKFLOW_PROMPTS.md`
      - any unrelated local doc drafts
      - `qc`
      - `var/`

## 6. Testing Plan

- Unit tests: recovery decision matrix in `tests/test_recovery_policy.py`
- Unit tests: validator outputs in `tests/test_agents.py`
- Unit tests: query-planner limit override in `tests/test_query_planner.py`
- Unit tests: workflow recovery routing in `tests/test_langgraph_workflow.py`
- Unit tests: public clarification serialization in `tests/test_demo_api.py`
- Unit tests: benchmark recovery regression in `tests/test_benchmark_harness.py`
- Integration tests: recovery routing loopbacks and zero-action guarantees in `tests/integration/test_langgraph_workflow_gateway.py`
- Integration tests: recovery-driven clarification through the public demo API in `tests/integration/test_demo_api_gateway.py`
- Integration tests: metadata sanitization in `tests/integration/test_workflow_agents_gateway.py`
- Integration tests: observability compatibility in `tests/integration/test_observability_gateway.py`
- Smoke checks: `git diff --check`
- Smoke checks: `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_recovery_policy.py tests/test_agents.py tests/test_query_planner.py tests/test_langgraph_workflow.py tests/test_demo_api.py tests/test_observability.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_demo_api_gateway.py tests/integration/test_workflow_agents_gateway.py tests/integration/test_observability_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add bounded recovery routing v1
```

Expected commands:

```bash
git status --short
git switch -c codex/recovery-routing-v1
git add backend/app/agents/recovery_policy.py
git add tests/test_recovery_policy.py
git add backend/app/agents/schemas.py
git add backend/app/agents/deterministic.py
git add backend/app/planning/query_planner.py
git add backend/app/workflow/state.py
git add backend/app/workflow/recovery.py
git add backend/app/workflow/nodes.py
git add backend/app/workflow/graph.py
git add backend/app/workflow/runner.py
git add README.md
git add docs/WEB_DEMO_README.md
git add tests/test_agents.py
git add tests/test_query_planner.py
git add tests/test_langgraph_workflow.py
git add tests/test_demo_api.py
git add tests/test_benchmark_harness.py
git add tests/integration/test_langgraph_workflow_gateway.py
git add tests/integration/test_demo_api_gateway.py
git add tests/integration/test_workflow_agents_gateway.py
git diff --cached --check
git commit -m "feat: add bounded recovery routing v1"
git push -u origin codex/recovery-routing-v1
```

The implementer must confirm that `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, any unrelated local doc drafts, `qc`, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not add new benchmark case JSON fixtures.
- Do not add new benchmark suite IDs or new benchmark report surfaces.
- Do not add real provider recovery logic.
- Do not add LLM-backed recovery logic.
- Do not redesign the internal recovery-path UI.
- Do not add new routes, migrations, or dependencies.
- Do not change confirmation or execution semantics.
- Do not stage the current unrelated local task-doc drafts or runtime artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/051-recovery-routing-v1.md`.
- [ ] The validator/recovery layer emits real v1 actions instead of only stop-only behavior.
- [ ] The v1 policy emits only `replace_candidate`, `expand_search_radius`, `ask_user`, `stop_safely`, or `none`.
- [ ] The v1 policy does not newly emit `retry`.
- [ ] `replace_candidate` actually changes the next validation input by excluding the blocked pair.
- [ ] `expand_search_radius` actually changes mock-world search limits from `5` to `8`.
- [ ] `ask_user` ends in `awaiting_clarification` and reuses the existing public clarification contract.
- [ ] `stop_safely` still handles route-wide infrastructure failures such as `family_route_failure_v1`.
- [ ] Recovery remains bounded by explicit attempt count and retry budget.
- [ ] Recovery metadata persists `policy_version`, attempt counts, expansion level, excluded pairs, and attempts.
- [ ] Recovery metadata stays sanitized.
- [ ] No recovery path creates pre-confirmation write actions.
- [ ] No unsafe direct route to execution was added.
- [ ] The public clarification continuation flow still works for recovery-driven clarification runs.
- [ ] Required unit and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, runtime artifact, or unrelated local doc draft was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final default `max_recovery_attempts` value.
- The exact mock-world search limits used before and after expansion.
- One verified `replace_candidate` example and the excluded pair it persisted.
- One verified `ask_user` example and the exact clarification prompt it returned.
- Confirmation that `family_route_failure_v1` still ends with `stop_safely`.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that unrelated local doc drafts remained unstaged.
- Any remaining follow-up limitation, especially that real provider recovery and broader benchmark authoring remain separate tasks.
