# Spec: 055 Benchmark Multi-turn Continuations v0

## 1. Goal

Add the first true multi-turn benchmark path so WeekendPilot can evaluate clarification and follow-up replanning continuations instead of only one `user_input -> one workflow run`.

The repository already has the product-side continuation chain: durable conversation sessions, clarification turns, follow-up replans, visible plan version lineage, and execution-preview manifests. The missing gap is that LocalLife-Bench still cannot drive any of those behaviors. After this task, benchmark fixtures must be able to describe a small continuation chain, the harness must be able to execute that chain through the demo conversation service, and benchmark reports must make the observed status/version sequence reviewable.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a conversation-style planning system, not a single-shot response generator. `docs/NEXT_PHASE_ROADMAP.md` places this work under milestone `M4. 多轮对话与方案版本`, whose exit criteria explicitly require multi-turn user interaction and plan-version evolution.

This task is also the direct follow-up to existing completed groundwork:

- Task `021` aligned benchmark execution with the real workflow path.
- Task `043` added durable `conversation_sessions` and `conversation_turns`.
- Task `044` added follow-up `replan`.
- Task `045` added visible plan-version lineage.
- Task `046` added stable action-manifest summaries.
- Task `048` added clarification turns.
- Task `050` explicitly deferred genuine L3 multi-turn benchmark authoring to a later task.
- Tasks `051` through `054` extended recovery, chaos, memory, and provider preview work, but did not change the single-turn benchmark entry contract.

That means the next missing capability is not another product-side continuation endpoint. The missing capability is benchmark coverage for the continuation chain that already exists.

This task touches these blueprint areas directly:

- LocalLife-Bench
- PostgreSQL source of truth through durable session/turn persistence
- Minimal Web demo service as the current multi-turn product entry layer
- Human-in-the-loop confirmation boundary
- Plan version lineage
- Benchmark reporting and suite organization

## 3. Requirements

- Add additive typed continuation contracts in `backend/app/benchmark/schemas.py`.
- `BenchmarkCase` must keep the current `user_input` field and add:

```text
continuations: list[BenchmarkContinuationRequest] = []
```

- `BenchmarkContinuationRequest` must include exactly:
  - `mode: Literal["clarify", "replan"]`
  - `user_input: str`
  - `selected_plan_index: int = 0` with `ge=0`

- Add additive conversation expectations under `BenchmarkExpectedOutcome`:

```text
conversation: BenchmarkConversationExpectation | None = None
```

- `BenchmarkConversationExpectation` must include exactly:
  - `steps: list[BenchmarkConversationExpectedStep]`
  - `required_turn_types: list[str] = []`

- `BenchmarkConversationExpectedStep` must include exactly:
  - `mode: Literal["start", "clarify", "replan", "confirm"]`
  - `expected_status: str`
  - `expected_version_label: str | None = None`

- Add additive result/report summary fields to `BenchmarkCaseResult`:
  - `conversation_trace: list[BenchmarkConversationTraceStep] = []`
  - `conversation_turn_types: list[str] = []`

- `BenchmarkConversationTraceStep` must include exactly:
  - `mode: Literal["start", "clarify", "replan", "confirm"]`
  - `source_run_id: UUID | None`
  - `run_id: UUID | None`
  - `status: str`
  - `version_label: str | None = None`

- Existing benchmark fixtures without `continuations` and without `expected.conversation` must continue to validate unchanged.

- `BenchmarkHarness.run_case(case)` must preserve the current workflow-runner path unchanged when:
  - `case.continuations == []`

- `BenchmarkHarness.run_case(case)` must use a continuation path when:
  - `case.continuations != []`

- Continuation-path benchmark cases in this v0 task must be limited to:
  - `tool_profile == "mock_world"`
  - `failure_profile == null`
  - supported Mock World `world_profile`
- If a continuation-path case violates those limits, the harness must return a benchmark `error` result with a clear sanitized failure reason instead of trying to execute it.

- For continuation-path cases, the harness must:
  - create or reuse a benchmark user exactly as today
  - persist `case.memory_items` exactly as today
  - execute the conversation chain through `DemoWorkflowService`
  - call `start_run(...)` for the initial turn
  - call `clarify_run(...)` or `replan_run(...)` for each configured continuation in order
  - call `confirm_run(...)` exactly once after the last configured continuation only when the last summary status is `awaiting_confirmation`
  - skip auto-confirmation when the last configured continuation does not end in `awaiting_confirmation`

- The harness must not change public demo API request or response schemas in this task.
- To keep the benchmark path aligned with existing case fixtures, `DemoWorkflowService` may gain an additive internal-only start override so the harness can honor:
  - `case.tool_profile`
  - `case.world_profile`
  - `case.agent_version`
  - `case.prompt_version`
- That override must not change the public HTTP request contract.

- For continuation-path cases, the harness must record an ordered `conversation_trace`.
- The exact step order must be:
  - `start`
  - zero or more configured continuation modes in fixture order
  - optional final `confirm`
- Each trace step must record:
  - `source_run_id`
  - produced `run_id`
  - returned `status`
  - returned `plan_version.version_label` when available

- For continuation-path cases, benchmark scoring and reporting must aggregate `ToolEvent` rows across every run ID in the conversation chain.
- `BenchmarkCaseResult.tool_event_count` must be the aggregated count across the chain.
- `grade_trajectory(...)` and `grade_failure_injection(...)` must use the aggregated tool-event sequence.
- `BenchmarkCaseResult.action_count` must be the aggregated action count across the chain.

- The final benchmark run context for:
  - `run_id`
  - `trace_id`
  - `run_summary`
  - `workflow_status`
  - `workflow_timing_summary`
  - `plan_status`
  - `feedback_status`
  - `observability_status`
must come from the last run in the conversation chain.

- For continuation-path cases, the harness must collect ordered `conversation_turn_types` from the persisted session of the final run.
- `conversation_turn_types` must contain only turn-type labels.
- Case reports must not add:
  - `session_id`
  - raw turn payloads
  - full conversation text history
  - trace payloads
  - benchmark secrets or tokens

- Add a new benchmark grader:

```text
grade_conversation_path(case: BenchmarkCase, conversation_trace, conversation_turn_types) -> BenchmarkScore
```

- `grade_conversation_path(...)` must only run when `case.expected.conversation` is non-null.
- It must pass only when:
  - observed step count matches expected step count
  - observed step modes exactly match expected step modes in order
  - observed step statuses exactly match expected statuses in order
  - observed version labels exactly match expected version labels in order when a label is specified
  - every `required_turn_type` appears at least once in `conversation_turn_types`
- The score name must be exactly:
  - `conversation_path`

- Legacy single-turn cases must keep their current score set unchanged.
- Continuation-path cases must add `conversation_path` on top of the current existing score set.

- Add two new benchmark case fixtures with these exact IDs:
  - `solo_clarification_continuation_v1`
  - `family_replan_version_continuation_v1`

- `solo_clarification_continuation_v1` must use this exact benchmark shape:
  - `tool_profile = "mock_world"`
  - `world_profile = "solo_afternoon"`
  - `failure_profile = null`
  - `continuations = [{"mode": "clarify", "user_input": "This afternoon I want a nearby solo outing for a few hours.", "selected_plan_index": 0}]`
  - `expected.required_tool_names` must remain the canonical eight read/write-preconfirmation tool names already used by current non-failure cases
  - `expected.min_tool_event_count = 8`
  - `expected.min_action_count = 1`
  - `expected.expected_workflow_status = "completed"`
  - `expected.expected_execution_status = "succeeded"`
  - `expected.expected_feedback_status = "completed"`
  - `expected.conversation.steps` must be exactly:
    - `start -> awaiting_clarification -> v1`
    - `clarify -> awaiting_confirmation -> v1`
    - `confirm -> completed -> v1`
  - `expected.conversation.required_turn_types` must be exactly:
    - `user_request`
    - `assistant_clarification_request`
    - `user_clarification_reply`
    - `assistant_plan_options`
  - `taxonomy` must be exactly:
    - `suite = "locallife_bench_v1"`
    - `scenario_bucket = "solo"`
    - `level = "L3"`
    - `tags = ["clarification_turn", "conversation_continuation", "light_activity", "light_meal"]`
    - `failure_mode = null`
  - `metadata.focus` must be exactly:
    - `clarification_continuation_solo`

- `family_replan_version_continuation_v1` must use this exact benchmark shape:
  - `tool_profile = "mock_world"`
  - `world_profile = "family_afternoon"`
  - `failure_profile = null`
  - `continuations = [{"mode": "replan", "user_input": "Keep it nearby, but make it indoor this time.", "selected_plan_index": 0}]`
  - `expected.required_tool_names` must remain the canonical eight read/write-preconfirmation tool names already used by current non-failure cases
  - `expected.min_tool_event_count = 16`
  - `expected.min_action_count = 1`
  - `expected.expected_workflow_status = "completed"`
  - `expected.expected_execution_status = "succeeded"`
  - `expected.expected_feedback_status = "completed"`
  - `expected.conversation.steps` must be exactly:
    - `start -> awaiting_confirmation -> v1`
    - `replan -> awaiting_confirmation -> v2`
    - `confirm -> completed -> v2`
  - `expected.conversation.required_turn_types` must be exactly:
    - `user_request`
    - `assistant_plan_options`
    - `user_follow_up`
    - `assistant_replan_options`
  - `taxonomy` must be exactly:
    - `suite = "locallife_bench_v1"`
    - `scenario_bucket = "family"`
    - `level = "L3"`
    - `tags = ["child_friendly", "conversation_continuation", "light_meal", "plan_versioning", "replan_turn"]`
    - `failure_mode = null`
  - `metadata.focus` must be exactly:
    - `replan_version_continuation_family`

- Extend benchmark fixture registration and suite catalog:
  - `BenchmarkSuiteId` must add `conversation_continuations`
  - `_REGISTERED_CASE_IDS` must append the two new case IDs after the current `family_memory_expired_advisory_v1`
  - `conversation_continuations` suite must contain exactly:
    - `solo_clarification_continuation_v1`
    - `family_replan_version_continuation_v1`
  - `default` suite must remain unchanged at the current 10 non-failure cases
  - `all_registered` suite must append the two continuation cases after the current 15-case order and become 17 cases total
  - `list_benchmark_suites()` must return these exact suite IDs in this exact order:
    - `baseline`
    - `expanded`
    - `recovery_focused`
    - `memory_governance`
    - `conversation_continuations`
    - `default`
    - `all_registered`

- The `conversation_continuations` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"family": 1, "solo": 1}`
  - `level_counts={"L3": 2}`
  - `world_profile_counts={"family_afternoon": 1, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 2}`
  - `tag_counts={"child_friendly": 1, "clarification_turn": 1, "conversation_continuation": 2, "light_activity": 1, "light_meal": 2, "plan_versioning": 1, "replan_turn": 1}`

- The `conversation_continuations` suite constraint-tag rollup case counts must be exactly:
  - `{"child_friendly": 1, "clarification_turn": 1, "conversation_continuation": 2, "light_activity": 1, "light_meal": 2, "plan_versioning": 1, "replan_turn": 1}`

- The updated `all_registered` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"couple": 1, "family": 10, "friends": 1, "mixed": 2, "solo": 2, "unknown": 1}`
  - `level_counts={"L1": 3, "L2": 8, "L3": 4, "L5": 2}`
  - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 10, "friends_gathering": 1, "rainy_day_fallback": 2, "solo_afternoon": 2}`
  - `failure_mode_counts={"none": 14, "route_and_dining_unavailable": 1, "route_unavailable": 1, "ticket_sold_out_and_bad_weather": 1}`
  - `tag_counts={"addon_optional": 1, "bad_weather": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 10, "citywalk": 2, "clarification_turn": 1, "composite_failure": 2, "conversation_continuation": 2, "date_friendly": 1, "dining_unavailable": 1, "failure_injected": 3, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 4, "light_activity": 2, "light_meal": 9, "memory_advisory": 1, "memory_expired": 1, "memory_governance": 2, "memory_override": 1, "outdoor_activity": 2, "plan_versioning": 1, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 2, "replan_turn": 1, "route_failure": 2, "ticket_sold_out": 1}`

- The updated `all_registered` suite constraint-tag rollup case counts must be exactly:
  - `{"addon_optional": 1, "bad_weather": 1, "budget_limited": 1, "casual_dining": 1, "child_friendly": 10, "citywalk": 2, "clarification_turn": 1, "composite_failure": 2, "conversation_continuation": 2, "date_friendly": 1, "dining_unavailable": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 4, "light_activity": 2, "light_meal": 9, "memory_advisory": 1, "memory_expired": 1, "memory_governance": 2, "memory_override": 1, "outdoor_activity": 2, "plan_versioning": 1, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 2, "replan_turn": 1, "ticket_sold_out": 1}`

- `BenchmarkHarness.run_suite("conversation_continuations")` must return:
  - `2` case results
  - `run_status="passed"`
  - `passed_count=2`
  - `failed_count=0`
  - `error_count=0`
  - report filename ending in `suite-conversation_continuations-run-report.json`

- The current green repository state after this task must serialize:
  - `pass_rate == 1.0` for every emitted bucket in `conversation_continuations`
  - unchanged `default` suite semantics
  - updated `all_registered` counts and rollups matching the exact values above

- Update `README.md` benchmark documentation to describe:
  - the new `conversation_continuations` suite
  - that `default` remains the single-turn 10-case suite
  - that v0 continuation benchmarking is limited to non-failure Mock World cases
  - that continuation case reports now include step-by-step status/version summaries

- Add or update focused tests for:
  - schema validation of continuation contracts
  - legacy fixture backward compatibility
  - suite registration and ordering
  - exact `conversation_continuations` and updated `all_registered` matrix counts
  - exact `conversation_continuations` and updated `all_registered` outcome-rollup counts
  - harness branch selection for continuation cases
  - actual clarification continuation execution
  - actual replan/version continuation execution
  - suite execution for `conversation_continuations`

- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not change public demo HTTP request/response schemas.
- Do not change replay report contracts in this task.
- Do not change failure-injection profiles, Chaos Harness contracts, AMAP behavior, or frontend behavior.

## 4. Non-goals

- Do not add failure-injected multi-turn benchmark cases.
- Do not benchmark recovery-generated clarification loops in this task.
- Do not expand replay summaries or replay comparisons for continuation signatures yet.
- Do not move the benchmark entrypoint from the harness into HTTP route tests.
- Do not change `default` suite membership or `load_default_benchmark_cases()` semantics.
- Do not add public demo API fields for benchmark-only overrides.
- Do not add new database tables, columns, indexes, or migrations.
- Do not add new dependencies.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, `qc`, or unrelated local docs such as the current untracked roadmap draft.

## 5. Interfaces and Contracts

### Inputs

Existing benchmark entry inputs remain:

- `BenchmarkCase.user_input`
- `BenchmarkCase.memory_items`
- `BenchmarkCase.expected`
- `BenchmarkCase.taxonomy`
- `BenchmarkCase.metadata`

Additive continuation inputs:

```json
{
  "continuations": [
    {
      "mode": "clarify",
      "user_input": "This afternoon I want a nearby solo outing for a few hours.",
      "selected_plan_index": 0
    }
  ],
  "expected": {
    "conversation": {
      "steps": [
        {
          "mode": "start",
          "expected_status": "awaiting_clarification",
          "expected_version_label": "v1"
        },
        {
          "mode": "clarify",
          "expected_status": "awaiting_confirmation",
          "expected_version_label": "v1"
        },
        {
          "mode": "confirm",
          "expected_status": "completed",
          "expected_version_label": "v1"
        }
      ],
      "required_turn_types": [
        "user_request",
        "assistant_clarification_request",
        "user_clarification_reply",
        "assistant_plan_options"
      ]
    }
  }
}
```

### Outputs

Additive case-result/report fields:

```json
{
  "conversation_trace": [
    {
      "mode": "start",
      "source_run_id": null,
      "run_id": "00000000-0000-0000-0000-000000000010",
      "status": "awaiting_clarification",
      "version_label": "v1"
    },
    {
      "mode": "clarify",
      "source_run_id": "00000000-0000-0000-0000-000000000010",
      "run_id": "00000000-0000-0000-0000-000000000020",
      "status": "awaiting_confirmation",
      "version_label": "v1"
    },
    {
      "mode": "confirm",
      "source_run_id": "00000000-0000-0000-0000-000000000020",
      "run_id": "00000000-0000-0000-0000-000000000020",
      "status": "completed",
      "version_label": "v1"
    }
  ],
  "conversation_turn_types": [
    "user_request",
    "assistant_clarification_request",
    "user_clarification_reply",
    "assistant_plan_options"
  ]
}
```

### Schemas

Exact clarification fixture contract:

```json
{
  "case_id": "solo_clarification_continuation_v1",
  "title": "Vague nearby request clarifies into a solo afternoon before confirmation",
  "user_input": "Plan something nearby for later.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "solo_afternoon",
  "failure_profile": null,
  "memory_items": [],
  "continuations": [
    {
      "mode": "clarify",
      "user_input": "This afternoon I want a nearby solo outing for a few hours.",
      "selected_plan_index": 0
    }
  ],
  "expected": {
    "required_tool_names": [
      "search_poi",
      "check_weather",
      "get_poi_detail",
      "check_opening_hours",
      "check_queue",
      "check_table_availability",
      "check_ticket_availability",
      "check_route"
    ],
    "min_tool_event_count": 8,
    "min_action_count": 1,
    "expected_workflow_status": "completed",
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed",
    "conversation": {
      "steps": [
        {
          "mode": "start",
          "expected_status": "awaiting_clarification",
          "expected_version_label": "v1"
        },
        {
          "mode": "clarify",
          "expected_status": "awaiting_confirmation",
          "expected_version_label": "v1"
        },
        {
          "mode": "confirm",
          "expected_status": "completed",
          "expected_version_label": "v1"
        }
      ],
      "required_turn_types": [
        "user_request",
        "assistant_clarification_request",
        "user_clarification_reply",
        "assistant_plan_options"
      ]
    }
  },
  "taxonomy": {
    "suite": "locallife_bench_v1",
    "scenario_bucket": "solo",
    "level": "L3",
    "tags": [
      "clarification_turn",
      "conversation_continuation",
      "light_activity",
      "light_meal"
    ],
    "failure_mode": null
  },
  "metadata": {
    "focus": "clarification_continuation_solo"
  }
}
```

Exact replan/version fixture contract:

```json
{
  "case_id": "family_replan_version_continuation_v1",
  "title": "Family afternoon request replans into v2 before confirmation",
  "user_input": "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.",
  "agent_version": "agent-v1",
  "prompt_version": "prompt-v1",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": null,
  "memory_items": [
    {
      "memory_type": "family",
      "key": "child_age",
      "value_json": {
        "age": 5
      },
      "text": "The child is 5 years old.",
      "confidence": "1.0",
      "status": "active"
    },
    {
      "memory_type": "preference",
      "key": "spouse_lighter_meals",
      "value_json": {
        "preference": "lighter meals"
      },
      "text": "The spouse prefers lighter meals.",
      "confidence": "1.0",
      "status": "active"
    }
  ],
  "continuations": [
    {
      "mode": "replan",
      "user_input": "Keep it nearby, but make it indoor this time.",
      "selected_plan_index": 0
    }
  ],
  "expected": {
    "required_tool_names": [
      "search_poi",
      "check_weather",
      "get_poi_detail",
      "check_opening_hours",
      "check_queue",
      "check_table_availability",
      "check_ticket_availability",
      "check_route"
    ],
    "min_tool_event_count": 16,
    "min_action_count": 1,
    "expected_workflow_status": "completed",
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed",
    "conversation": {
      "steps": [
        {
          "mode": "start",
          "expected_status": "awaiting_confirmation",
          "expected_version_label": "v1"
        },
        {
          "mode": "replan",
          "expected_status": "awaiting_confirmation",
          "expected_version_label": "v2"
        },
        {
          "mode": "confirm",
          "expected_status": "completed",
          "expected_version_label": "v2"
        }
      ],
      "required_turn_types": [
        "user_request",
        "assistant_plan_options",
        "user_follow_up",
        "assistant_replan_options"
      ]
    }
  },
  "taxonomy": {
    "suite": "locallife_bench_v1",
    "scenario_bucket": "family",
    "level": "L3",
    "tags": [
      "child_friendly",
      "conversation_continuation",
      "light_meal",
      "plan_versioning",
      "replan_turn"
    ],
    "failure_mode": null
  },
  "metadata": {
    "focus": "replan_version_continuation_family"
  }
}
```

## 6. Observability

This task does not add a new telemetry backend or a new API route.

It must add only additive benchmark review data:

- `BenchmarkCaseResult.conversation_trace`
- `BenchmarkCaseResult.conversation_turn_types`

The benchmark harness may reuse the existing demo metadata already persisted on each run:

- `demo.initial_node_history`
- `demo.continuation_history`
- `demo.plan_version`
- existing run summary and observability summary metadata

This task must not add:

- new LangSmith contract requirements
- new Redis keys
- new database tables
- new internal observability endpoint fields
- public exposure of `session_id` or raw conversation payloads

Case reports must stay sanitized and must not include:

- session identifiers
- raw turn payload JSON
- secrets
- API keys
- tokens
- prompts
- debug traces

## 7. Failure Handling

- A fixture with malformed continuation schema must fail fixture validation.
- A continuation-path case with unsupported `tool_profile`, unsupported `world_profile`, or non-null `failure_profile` must return a benchmark `error` result with a clear sanitized reason.
- If `DemoWorkflowService.start_run(...)`, `clarify_run(...)`, `replan_run(...)`, or `confirm_run(...)` raises `DemoServiceError`, the harness must return a benchmark `error` result with a sanitized failure reason.
- If any continuation step returns no persisted run, the harness must return a benchmark `error` result.
- If the configured continuation sequence ends without `awaiting_confirmation`, the harness must not auto-confirm; it must finalize the benchmark result from the last run and let scoring fail naturally.
- Legacy single-turn cases must keep current failure handling unchanged.
- Replay contracts, recovery-path contracts, and failure-injection scoring must remain unchanged for legacy suites.

## 8. Acceptance Criteria

- [ ] `docs/specs/055-benchmark-multi-turn-continuations-v0.md` exists and matches this task.
- [ ] `docs/plans/055-benchmark-multi-turn-continuations-v0-plan.md` exists and matches this task.
- [ ] Existing single-turn benchmark fixtures still load without modification.
- [ ] `BenchmarkCase` supports additive continuation fixtures and conversation expectations.
- [ ] `BenchmarkHarness.run_case()` keeps the current workflow-runner path for legacy cases.
- [ ] `BenchmarkHarness.run_case()` uses the continuation path for cases with configured continuations.
- [ ] `solo_clarification_continuation_v1` runs through `start -> clarify -> confirm` and passes.
- [ ] `solo_clarification_continuation_v1` reports version labels `v1 -> v1 -> v1`.
- [ ] `family_replan_version_continuation_v1` runs through `start -> replan -> confirm` and passes.
- [ ] `family_replan_version_continuation_v1` reports version labels `v1 -> v2 -> v2`.
- [ ] Continuation case reports include `conversation_trace` and `conversation_turn_types`.
- [ ] Continuation case reports do not expose `session_id` or raw turn payloads.
- [ ] `conversation_path` is added only for cases with `expected.conversation`.
- [ ] `conversation_continuations` suite exists and contains exactly the two new continuation cases.
- [ ] `list_benchmark_suites()` returns `["baseline", "expanded", "recovery_focused", "memory_governance", "conversation_continuations", "default", "all_registered"]`.
- [ ] `default` suite remains the current 10-case single-turn suite.
- [ ] `all_registered` expands to 17 cases with the exact counts defined in this spec.
- [ ] `BenchmarkHarness.run_suite("conversation_continuations")` passes with 2 results and writes `suite-conversation_continuations-run-report.json`.
- [ ] `README.md` documents the new continuation suite and its v0 limitations.
- [ ] No public demo HTTP schema changes, replay contract changes, migrations, or new dependencies are introduced.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any blocker is reported clearly.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q
python -m pytest tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add benchmark multi-turn continuations
```

## 11. Notes for the Implementer

Keep this task intentionally narrow.

Important defaults chosen here:

- continuation benchmarking is `mock_world` only in v0
- continuation benchmarking is non-failure only in v0
- `default` remains the historical single-turn suite
- the new coverage lives in its own `conversation_continuations` suite and in `all_registered`
- public demo HTTP request/response schemas stay unchanged
- benchmark-only flexibility should come from an internal service override, not public API expansion

If the implementation starts to require public demo schema changes, multi-turn failure injection, replay-signature redesign, or AMAP continuation support, stop and split that into a later task.
