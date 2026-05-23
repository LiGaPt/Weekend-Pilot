# Spec: 051 Recovery Routing v1

## 1. Goal

Move WeekendPilot's bounded recovery layer from "safe stop only" to "deterministic recover or ask the user" without widening the confirmation boundary.

Task 027 added the recovery-routing shell: the workflow can consume `RecoveryDecision`, record bounded attempts, and loop only through deterministic read/planning nodes. What is still missing is a real decision policy and the smallest state mutations that make those routes do useful work. After this task, the deterministic validator/recovery layer must be able to emit one of four structured actions:

- `replace_candidate`
- `expand_search_radius`
- `ask_user`
- `stop_safely`

Each action must carry an explicit reason, must stay within a bounded attempt budget, and must remain traceable in persisted workflow metadata and benchmark artifacts.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` allows dynamic recovery routing only through structured Validator & Recovery decisions, requires explicit retry budgets, requires confirmation boundaries to remain intact, and treats recovery behavior as benchmark-visible product logic rather than optional glue code.

`docs/NEXT_PHASE_ROADMAP.md` places this task in milestone `M5. 恢复、真实 provider、记忆治理`. The repository is already ahead of the roadmap's earlier M1-M4 baseline:

- M1 observability and benchmark infrastructure already landed through Tasks `033`, `036`, `037`, `041`, and `050`.
- M2 customer/internal view separation already landed through Tasks `034` and `035`.
- M3 scenario and benchmark expansion already landed through Tasks `038`, `039`, `040`, `049`, and `050`.
- M4 multi-turn conversation and plan-version work already landed through Tasks `043`, `044`, `045`, `046`, and `048`.

That means the next real product gap is not more benchmark packaging or more conversation scaffolding. The next real gap is M5 recovery behavior itself.

This task builds directly on:

- Task `027` bounded recovery routing v0
- Task `042` internal recovery-path visualization
- Task `048` clarification-turn continuation
- Task `050` benchmark suite/report expansion

## 3. Requirements

- Keep `RecoveryDecision` backward compatible as the typed recovery contract.
- Keep `WeekendPilotWorkflowRequest`, `WeekendPilotWorkflowResult`, `DemoRunSummary`, and the existing `/demo/runs/*` route shapes backward compatible.
- Keep the current official workflow topology and confirmation boundary intact.
- Keep the current public clarification flow shape intact:
  - `status="awaiting_clarification"`
  - `DemoRunSummary.clarification`
  - `POST /demo/runs/{run_id}/clarify`

- The deterministic validator/recovery policy in v1 must emit only these non-pass actions:
  - `replace_candidate`
  - `expand_search_radius`
  - `ask_user`
  - `stop_safely`

- Legacy internal support for `retry` in `resolve_recovery_route(...)` may remain for compatibility, but the v1 deterministic policy must not newly emit `retry`.

- Add workflow state needed to make routed recovery actions materially change behavior:
  - `search_expansion_level: int`
  - `excluded_candidate_pairs: list[dict[str, str]]`
  - keep `recovery_attempts`
  - keep `max_recovery_attempts`
  - keep `active_recovery_route`

- The default v1 workflow recovery attempt budget must be:
  - `max_recovery_attempts = 2`

- `search_expansion_level` must start at `0`.
- `excluded_candidate_pairs` must start empty.
- `expand_search_radius` may consume only one bounded expansion step in v1:
  - level `0` -> default breadth
  - level `1` -> expanded breadth
  - no level `2+` behavior in this task

- `generate_queries(...)` must consume `search_expansion_level`.
- For `tool_profile="mock_world"`, the exact v1 search-breadth behavior must be:
  - level `0`: activity and dining `search_poi` limit stays `5`
  - level `1`: activity and dining `search_poi` limit becomes `8`
- No other query broadening rule is allowed in this task.
- Do not drop explicit user constraints or explicit user preferences during expansion.
- Do not add provider-specific radius parameters in this task.
- Do not pretend there is real geo-radius expansion for `mock_world`.

- `replace_candidate` must be materially consumed by the planning path.
- In v1, `replace_candidate` means:
  - identify the first currently blocked draft pair
  - store its `(activity_candidate_id, dining_candidate_id)` in `excluded_candidate_pairs`
  - rerun `logical_planner_agent`
  - filter out excluded pairs before the next validation pass
- v1 replacement is intentionally narrow:
  - it only excludes already-produced blocked draft pairs
  - it does not search for new combinations beyond the generator's normal ordered draft window

- `DeterministicValidatorRecoveryAgent.review(...)` must accept additive recovery context that includes enough information to choose among the four actions deterministically.
- The recovery decision policy must consider at least:
  - `FinalReviewResult`
  - `ItineraryDraftResult`
  - `CandidateBlackboard`
  - prior `recovery_attempts`
  - `search_expansion_level`

- The v1 deterministic decision matrix must follow these rules:

- If final review is safe to present:
  - emit `verdict="passed"`
  - emit `recovery_action="none"`

- If the blocking failure is a safety-boundary or integrity failure:
  - emit `stop_safely`
- v1 safety-boundary or integrity failures are:
  - `run_id_consistency`
  - `pre_confirmation_no_actions`
  - `actions_require_confirmation`
  - `actions_reference_draft_objects`
  - `actions_have_no_execution_fields`
  - `sensitive_payload_scan`

- If no draft exists and route-wide failure evidence shows the workflow has no usable routes because route checks failed:
  - emit `stop_safely`
- Route-wide failure evidence in v1 means:
  - `draft_exists` failed
  - and either itinerary failure reasons include `missing_usable_route`
  - or screened candidate / route evidence contains `route_infeasible`
- The benchmark recovery case `family_route_failure_v1` must continue to follow this path.

- If at least two current drafts exist, the first current draft is blocked, and no previous replacement has been consumed for that pair:
  - emit `replace_candidate`
  - route to `logical_planner_agent`
  - use `retry_budget=1`

- If the run failed because candidate breadth is too narrow, no route-wide infrastructure failure dominates, and `search_expansion_level == 0`:
  - emit `expand_search_radius`
  - route to `generate_queries`
  - use `retry_budget=1`

- If deterministic recovery has already used its single search expansion or the next safe deterministic alternative is exhausted, but continuing is still possible with user tradeoff input:
  - emit `ask_user`
  - do not emit a routed loopback
  - do not mark the run as failed

- If no safe deterministic recovery rule matches:
  - emit `stop_safely`

- `ask_user` must reuse the existing workflow clarification contract.
- Recovery-generated clarification metadata must still use:
  - `policy_version`
  - `missing_fields`
  - `question_text`
- The public `DemoRunSummary.clarification` response must keep the current shape.
- The exact recovery-generated clarification variants for v1 must be:

- When `query_plan.intent.constraints.max_distance_km` is present:
  - `policy_version = "recovery_clarification_v1"`
  - `missing_fields = ["distance_flexibility"]`
  - `question_text = "为了继续规划，请告诉我是否可以接受更远一点，或者仍然需要控制在当前距离内。"`

- Otherwise:
  - `policy_version = "recovery_clarification_v1"`
  - `missing_fields = ["preference_tradeoff"]`
  - `question_text = "为了继续规划，请补充更偏好的活动或用餐方向，或说明哪些约束可以放宽。"`

- `apply_recovery(...)` must support four concrete v1 outcomes:

- `replace_candidate`
  - append one excluded pair
  - persist recovery metadata
  - route to `logical_planner_agent`

- `expand_search_radius`
  - increment `search_expansion_level` from `0` to `1`
  - persist recovery metadata
  - route to `generate_queries`

- `ask_user`
  - persist recovery metadata
  - persist `workflow.clarification`
  - update run status to `awaiting_clarification`
  - return zero write actions
  - end the current graph execution safely

- `stop_safely`
  - persist recovery metadata
  - update run status to `failed`
  - return structured `error_json`
  - end the current graph execution safely

- `route_after_recovery(...)` must support `awaiting_clarification` as a valid terminal workflow status.
- Recovery must never route directly to:
  - `present_to_user`
  - `wait_confirmation`
  - `saga_execution_engine`
  - `generate_summary_message`

- Persist sanitized recovery metadata under `agent_runs.metadata_json["workflow"]["recovery"]`.
- The persisted v1 recovery metadata must include:
  - `policy_version`
  - `attempt_count`
  - `max_attempts`
  - `search_expansion_level`
  - `excluded_candidate_pairs`
  - `attempts`

- Recovery metadata must remain sanitized and must not include:
  - raw prompt internals beyond the existing user-visible clarification text
  - raw tool request or response bodies
  - raw action payloads
  - tool event IDs
  - action IDs
  - secrets
  - API keys
  - tracebacks

- Keep internal recovery-path observability compatible with the current `workflow.recovery.attempts` structure.
- Keep benchmark recovery grading compatible with the current `observed_recovery_actions` behavior.
- Do not add new benchmark case fixtures in this task.
- Do not add new provider integration, new frontend pages, new routes, new migrations, or new dependencies.

- Update `README.md` and `docs/WEB_DEMO_README.md` to note that `awaiting_clarification` may now be reached both before planning and from bounded recovery.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add LLM-generated recovery decisions.
- Do not add real provider recovery behavior.
- Do not add new benchmark case JSON fixtures or new suite IDs.
- Do not redesign the internal observability page.
- Do not change confirmation, execution, or Action Ledger semantics.
- Do not add automatic write-action retries.
- Do not widen `expand_search_radius` into real geo-radius logic for `mock_world`.
- Do not convert this task into a general conversation redesign.
- Do not stage or commit unrelated local task-doc drafts for Tasks `047`, `049`, or `050`.

## 5. Interfaces and Contracts

### Inputs

- `DeterministicValidatorRecoveryAgent.review(...)`
- `FinalReviewResult`
- `ItineraryDraftResult`
- `CandidateBlackboard`
- current workflow recovery state
- current effective `QueryPlan`

### Outputs

- Existing `RecoveryDecision` remains the emitted recovery contract.
- Existing `WeekendPilotWorkflowResult` remains the workflow output contract.
- Existing `DemoRunSummary.clarification` remains the public clarification contract.
- Existing recovery metadata path remains:
  - `agent_runs.metadata_json["workflow"]["recovery"]`

### Schemas

Additive recovery evaluation context for the deterministic validator may be modeled internally like this:

```json
{
  "attempted_actions": [
    "expand_search_radius"
  ],
  "search_expansion_level": 1,
  "excluded_candidate_pairs": [
    {
      "activity_candidate_id": "activity_museum_001",
      "dining_candidate_id": "restaurant_light_001"
    }
  ],
  "screened_candidate_ids": [
    "activity_museum_001",
    "restaurant_light_001"
  ],
  "route_failure_codes": [
    "route_infeasible"
  ]
}
```

Persisted workflow recovery metadata after one routed expansion may look like this:

```json
{
  "workflow": {
    "workflow_version": "recovery_routing_v1",
    "recovery": {
      "policy_version": "recovery_routing_v1",
      "attempt_count": 1,
      "max_attempts": 2,
      "search_expansion_level": 1,
      "excluded_candidate_pairs": [],
      "attempts": [
        {
          "attempt_index": 1,
          "source_node": "semantic_validator",
          "recovery_action": "expand_search_radius",
          "route_to": "generate_queries",
          "error_type": "draft_exists",
          "reason": "Current candidate breadth is too narrow for a safe draft.",
          "retry_budget_before": 1,
          "retry_budget_after": 0,
          "status": "routed"
        }
      ]
    }
  }
}
```

Recovery-generated clarification metadata must reuse the current clarification contract:

```json
{
  "workflow": {
    "clarification": {
      "policy_version": "recovery_clarification_v1",
      "missing_fields": [
        "distance_flexibility"
      ],
      "question_text": "为了继续规划，请告诉我是否可以接受更远一点，或者仍然需要控制在当前距离内。"
    }
  }
}
```

## 6. Observability

This task must not add a new telemetry backend.

It must preserve the current recovery-path observability pipeline and keep recovery behavior inspectable through persisted metadata. Recovery attempts must remain serializable, replay-safe, and benchmark-safe.

This task must keep these existing observability properties intact:

- recovery decisions remain visible through `workflow.recovery.attempts`
- benchmark harness can still read `observed_recovery_actions`
- internal observability can still render the existing attempt list
- clarification runs remain visible as valid workflow outcomes rather than exceptions

## 7. Failure Handling

- If recovery state is missing or malformed, the workflow must stop safely rather than run an unbounded or ambiguous loop.
- If `replace_candidate` is selected but there is no current draft pair to exclude, fall back to `stop_safely`.
- If `expand_search_radius` is selected when `search_expansion_level` is already `1`, fall back to `ask_user` or `stop_safely` according to the deterministic policy.
- If recovery-generated clarification metadata cannot be built, fall back to `stop_safely`.
- If the workflow reaches `awaiting_clarification` through recovery, it must still record zero write actions before confirmation.
- If the user later clarifies and the continuation run still cannot recover, normal clarification and failure behavior may continue unchanged.
- Existing unsupported-profile, benchmark, replay, and observability error handling must remain unchanged.

## 8. Acceptance Criteria

- [ ] The deterministic validator/recovery policy emits real v1 actions instead of only `none` or `stop_safely`.
- [ ] The v1 deterministic policy emits only `replace_candidate`, `expand_search_radius`, `ask_user`, `stop_safely`, or `none`.
- [ ] The v1 deterministic policy does not newly emit `retry`.
- [ ] `replace_candidate` excludes the first blocked draft pair and reruns `logical_planner_agent`.
- [ ] `expand_search_radius` reruns `generate_queries` and changes mock-world `search_poi` limits from `5` to `8`.
- [ ] `expand_search_radius` can be consumed at most once per run in v1.
- [ ] `ask_user` ends the workflow in `awaiting_clarification` and reuses the existing clarification response shape.
- [ ] `stop_safely` still returns structured typed failure metadata.
- [ ] Recovery remains bounded by explicit workflow attempt count and per-decision retry budget.
- [ ] The default workflow recovery attempt budget is `2`.
- [ ] Recovery metadata persists `policy_version`, `attempt_count`, `max_attempts`, `search_expansion_level`, `excluded_candidate_pairs`, and `attempts`.
- [ ] Recovery metadata remains sanitized.
- [ ] No recovery path executes write tools before explicit confirmation.
- [ ] Recovery never routes directly to `present_to_user`, `wait_confirmation`, `saga_execution_engine`, or `generate_summary_message`.
- [ ] The existing benchmark recovery case `family_route_failure_v1` still ends with `expected_error_type="recovery_stopped"` and `expected_recovery_action="stop_safely"`.
- [ ] Gateway integration coverage exists for `replace_candidate`, `expand_search_radius`, `ask_user`, and `stop_safely`.
- [ ] Public clarification continuation through `/demo/runs/{run_id}/clarify` still works for recovery-generated `awaiting_clarification` runs.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` mention recovery-driven clarification.
- [ ] No new benchmark case JSON, provider integration, dependency, or migration is added.
- [ ] No `.env`, API key, token, secret, generated runtime artifact, or unrelated local task draft is committed.
- [ ] `git diff --check` passes.
- [ ] The listed verification commands pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_recovery_policy.py tests/test_agents.py tests/test_query_planner.py tests/test_langgraph_workflow.py tests/test_demo_api.py tests/test_observability.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_demo_api_gateway.py tests/integration/test_workflow_agents_gateway.py tests/integration/test_observability_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add bounded recovery routing v1
```

## 11. Notes for the Implementer

Keep this task tightly scoped to deterministic recovery behavior.

Important defaults chosen here:

- v1 recovery is bounded to at most two attempts per run
- mock-world expansion is modeled as search breadth increase, not true geo-radius logic
- replacement excludes already-produced blocked draft pairs only
- recovery `ask_user` must reuse the existing clarification contract and continuation route
- the current untracked local docs for Tasks `047`, `049`, and `050` are not part of this task and must not be staged with it

If the implementation seems to require new provider contracts, new public schema shapes, or new benchmark fixtures, stop and narrow the change back down. Those are separate tasks.
