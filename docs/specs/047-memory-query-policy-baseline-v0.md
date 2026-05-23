# Spec: 047 Memory Query Policy Baseline v0

## 1. Goal

Add the first real deterministic memory-query policy so WeekendPilot's loaded user memory can influence planning in a narrow, reviewable, and benchmark-verifiable way.

The current repository already persists memory rows, injects benchmark memory fixtures, and loads active memory into workflow state, but the planning path does not consume that memory at all. After this task, supported high-confidence preference memory must be able to fill in missing planning hints, while explicit user input must always override stored memory. This is the smallest useful slice of long-term memory governance because it makes the existing `load_memory` step and the `family_memory_override_v1` benchmark case materially meaningful without introducing memory writing, memory editing, or public UI changes.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` already defines long-term memory governance as a V1/V2 direction and states two relevant rules that this task must finally operationalize:

- Current user input overrides long-term memory.
- Low-confidence memory should not strongly influence plans.

`docs/NEXT_PHASE_ROADMAP.md` places memory work in milestone `M5. 恢复、真实 provider、记忆治理`. Although the roadmap lists multiple later directions in that milestone, this repository has already completed the earlier M1-M4 infrastructure chain through task `046`, and read-only AMAP support already exists from task `006`. That makes memory governance the next genuine roadmap gap.

This task also serves as a convergence fix for current repository behavior:

- `MemoryItemRepository.list_active_for_user(...)` exists.
- `WeekendPilotWorkflowNodes.load_memory(...)` populates `active_memories`.
- Benchmark cases such as `family_memory_override_v1` insert memory fixtures.
- `DeterministicQueryPlanner.build(...)` currently only consumes `LocalLifeIntent`, so loaded memory never affects planning.

This task touches these blueprint areas directly:

- PostgreSQL source of truth for durable memory rows
- LangGraph workflow state and deterministic planning path
- LocalLife-Bench truthfulness and benchmark reviewability
- Long-term memory governance, in a deliberately small read-only v0 slice

## 3. Requirements

- Add one new additive parse signal field to `IntentParseSignals`:
  - `activity_preferences: bool = False`
- `DeterministicIntentParser.parse_with_signals(...)` must detect explicit activity-style user input and normalize it into at most one style preference using this priority:
  1. `citywalk`
  2. `indoor`
  3. `outdoor`
- Supported explicit activity-style text fragments in v0 must be:
  - `citywalk`, `city walk`, `城市漫步`
  - `indoor`, `inside`, `室内`
  - `outdoor`, `outside`, `户外`, `室外`
- Auto-added `child_friendly` must not set `IntentParseSignals.activity_preferences = true`.
- `LocalLifeIntent.activity_preferences` must continue to include `child_friendly` when family/child signals are present.
- Add a new pure helper module for memory-query policy evaluation.
- The helper contract for v0 must be:

```text
apply_memory_query_policy(
    intent: LocalLifeIntent,
    signals: IntentParseSignals,
    active_memories: list[WorkflowMemoryRecord],
) -> tuple[LocalLifeIntent, MemoryQueryPolicySummary]
```

- Add a new compact summary model `MemoryQueryPolicySummary`.
- `MemoryQueryPolicySummary` must include exactly:
  - `policy_version: str`
  - `applied_memory_keys: list[str]`
  - `ignored_low_confidence_keys: list[str]`
  - `user_override_dimensions: list[str]`
  - `unsupported_memory_keys: list[str]`
  - `effective_activity_preferences: list[str]`
  - `effective_dining_preferences: list[str]`
- `policy_version` must be `memory_query_policy_v0`.
- The memory-query policy must only consider workflow memory records that are already active and loaded by `load_memory`.
- The memory-query policy must only project `memory_type == "preference"` records in v0.
- The exact confidence threshold for v0 must be `Decimal("0.8000")`.
- Memory records with malformed confidence values or confidence lower than `0.8000` must not affect planning.
- Supported projected memory keys in v0 must be exactly:
  - `activity_style`
  - `spouse_lighter_meals`
- `activity_style` memory must normalize from `value_json["preference"]` first, then fall back to `text`, using the same `citywalk > indoor > outdoor` priority as explicit user parsing.
- `spouse_lighter_meals` memory must normalize to `lighter_options` when `value_json["preference"]` or `text` clearly indicates lighter meals.
- No other memory keys may affect planning in this task.
- If `IntentParseSignals.activity_preferences` is `true`, activity-style memory must not be applied.
- If `IntentParseSignals.dining_preferences` is `true`, dining-preference memory must not be applied.
- User override behavior must be recorded in `user_override_dimensions`.
- Unsupported or malformed memory keys must be recorded in `unsupported_memory_keys` and ignored.
- The effective intent returned by the helper must:
  - preserve the original parsed intent fields by default
  - append supported projected preferences only when the user did not already provide that dimension
  - avoid duplicate preferences
- This task must not modify:
  - `scenario_type`
  - `participants`
  - `time_window`
  - `max_distance_km`
  - `origin_text`
- `WeekendPilotWorkflowNodes.parse_intent(...)` must store both:
  - `parsed_intent`
  - `intent_parse_signals`
- `WeekendPilotWorkflowNodes.generate_queries(...)` must apply the memory-query policy before calling `DeterministicQueryPlanner.build(...)`.
- `DeterministicQueryPlanner` must use supported activity-style preferences from the effective intent in Mock World search planning.
- For Mock World activity search, supported style preferences must affect both:
  - `payload["tags"]`
  - the activity query string chosen by `_mock_world_activity_query(...)`
- Mock World activity-style planning rules in v0 must be:
  - if `citywalk` is present, use query `citywalk`
  - else if `indoor` is present, use query `indoor`
  - else if `outdoor` is present, use query `outdoor`
  - else preserve existing fallback behavior
- Dining preference behavior must continue to flow through the existing `lighter_options` path once memory policy augments the effective intent.
- Persist the compact summary under `agent_runs.metadata_json["workflow"]["memory_policy"]`.
- The persisted summary must remain sanitized and must not include:
  - raw memory text
  - raw `value_json`
  - memory IDs
  - trace IDs
  - any sensitive/internal fields
- Add or update focused tests for:
  - parser activity-style extraction and signal behavior
  - pure memory-query policy apply/ignore/override behavior
  - query-planner style-tag propagation
  - benchmark integration around `family_memory_override_v1`
- Do not add or modify any Alembic revision in this task.
- Do not add new dependencies.
- Do not change public demo API schemas, public frontend schemas, replay contracts, recovery contracts, or AMAP contracts.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add memory write-back, memory learning, memory editing, or memory deletion flows.
- Do not add user-facing memory management API routes or frontend UI.
- Do not change benchmark suite membership, add new benchmark case files, or retag existing benchmark cases in this task.
- Do not change `MemoryItemRepository` persistence schema or add memory migrations.
- Do not widen memory projection to `origin_text`, `max_distance_km`, or other dimensions.
- Do not add LLM-based memory interpretation.
- Do not redesign recovery routing, replay, provider selection, or action-manifest behavior.
- Do not commit generated `var/` artifacts or unrelated local untracked files such as `docs/NEXT_PHASE_ROADMAP.md` and `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

- `LocalLifeIntent` from `DeterministicIntentParser`
- `IntentParseSignals` from `DeterministicIntentParser.parse_with_signals(...)`
- `list[WorkflowMemoryRecord]` from `WeekendPilotWorkflowNodes.load_memory(...)`
- Existing workflow call path:
  - `parse_intent`
  - `load_memory`
  - `generate_queries`

### Outputs

- An effective `LocalLifeIntent` used only for query planning
- A persisted compact summary under `agent_runs.metadata_json["workflow"]["memory_policy"]`
- Existing `QueryPlan` output shape remains unchanged
- Existing benchmark and demo external response contracts remain unchanged

### Schemas

Additive parse-signal excerpt:

```json
{
  "scenario_or_participants": true,
  "time_window": true,
  "max_distance_km": true,
  "dining_preferences": false,
  "activity_preferences": true
}
```

Persisted workflow metadata excerpt:

```json
{
  "workflow": {
    "memory_policy": {
      "policy_version": "memory_query_policy_v0",
      "applied_memory_keys": [],
      "ignored_low_confidence_keys": ["activity_style"],
      "user_override_dimensions": ["activity_preferences", "dining_preferences"],
      "unsupported_memory_keys": [],
      "effective_activity_preferences": ["child_friendly", "indoor"],
      "effective_dining_preferences": ["lighter_options"]
    }
  }
}
```

Pure helper contract:

```text
apply_memory_query_policy(
    intent: LocalLifeIntent,
    signals: IntentParseSignals,
    active_memories: list[WorkflowMemoryRecord],
) -> tuple[LocalLifeIntent, MemoryQueryPolicySummary]
```

## 6. Observability

This task must add only one new internal observability surface:

- `agent_runs.metadata_json["workflow"]["memory_policy"]`

The summary is for internal review, benchmark truthfulness, and future observability use. It must stay compact and sanitized. This task must not:

- add a new API route
- add a new run-summary schema
- add a new LangSmith field requirement
- add new PostgreSQL tables or Redis keys

## 7. Failure Handling

- If `active_memories` is empty, planning must proceed with the parsed intent and persist an empty-but-valid `MemoryQueryPolicySummary`.
- If a memory record has malformed confidence, missing `value_json`, unsupported key, or unrecognized value shape, that record must be ignored rather than failing the workflow.
- If all candidate memory records are ignored, the workflow must still succeed and use the parsed intent unchanged.
- If the user explicitly supplied an activity-style or dining-preference signal, conflicting memory must be ignored and recorded under `user_override_dimensions`.
- Existing database transaction behavior for run metadata persistence must remain unchanged.
- Existing unsupported-profile, benchmark, observability, replay, and provider failure behavior must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/047-memory-query-policy-baseline-v0.md` exists and matches this task.
- [ ] `docs/plans/047-memory-query-policy-baseline-v0-plan.md` exists and matches this task.
- [ ] `IntentParseSignals` includes additive field `activity_preferences`.
- [ ] The parser extracts explicit `indoor` / `outdoor` / `citywalk` activity-style signals deterministically.
- [ ] Auto-added `child_friendly` does not incorrectly mark `activity_preferences` as an explicit user signal.
- [ ] High-confidence supported preference memory can supplement a missing planning dimension in unit tests.
- [ ] Low-confidence memory below `0.8000` is ignored in unit tests.
- [ ] Explicit user input overrides conflicting memory in unit tests.
- [ ] Unsupported memory keys are ignored and recorded in the summary.
- [ ] `generate_queries` applies the memory-query policy before `DeterministicQueryPlanner.build(...)`.
- [ ] Mock World activity search planning uses effective activity-style preferences in both tags and query selection.
- [ ] `agent_runs.metadata_json["workflow"]["memory_policy"]` is persisted with the exact compact summary shape defined above.
- [ ] The persisted summary contains no raw memory text, raw `value_json`, memory IDs, or trace IDs.
- [ ] `family_memory_override_v1` benchmark integration now records a real memory-policy decision rather than silently ignoring memory.
- [ ] No Alembic migration, dependency, public API contract, replay contract, recovery contract, or frontend contract is changed.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any blocker is reported clearly.
- [ ] The working tree is clean after commit except for the pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_intent_parser.py tests/test_query_planner.py tests/test_memory_query_policy.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add memory query policy baseline
```

## 11. Notes for the Implementer

Keep this task intentionally narrow.

The important outcome is not “build full memory.” The important outcome is:

1. memory loaded into workflow is no longer dead data,
2. explicit user input still wins,
3. low-confidence memory is safely ignored, and
4. the benchmark case named `family_memory_override_v1` now has a real behavioral basis.

Do not widen this task into memory CRUD, memory learning, benchmark expansion, or public product changes. If implementation pressure appears to require changing database schema, public demo responses, or benchmark suite membership, stop and reassess because that is outside the intended scope of this v0 slice.
