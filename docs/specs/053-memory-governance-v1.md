# Spec: 053 Memory Governance v1

## 1. Goal

Upgrade Task `047`'s `memory_query_policy_v0` baseline into a governed read-memory policy that can evaluate expired memory, down-rank weaker memory, preserve explicit user-input precedence, and expose conflict sources in a compact audit-friendly summary.

Today the workflow already persists memory rows, loads them into state, and applies a narrow memory policy before query planning. However, that policy is still too coarse for M5 memory governance: expired memory is filtered before the policy can see it, low-confidence memory is treated as a flat threshold decision rather than a governed source, and internal metadata does not make dimension-level winners and suppressed sources directly visible. After this task, WeekendPilot must still stay read-only and deterministic, but the benchmark harness must be able to prove that memory can help when the user is vague and stay bounded when the user is explicit.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` places long-term memory governance in the V1/V2 evolution path and states the exact principles this task must operationalize:

- current user input overrides long-term memory
- low-confidence memory should not strongly influence plans
- expired memory should be ignored or downgraded
- memory should be governable and auditable, not only stored

`docs/NEXT_PHASE_ROADMAP.md` places this work in milestone `M5. 恢复、真实 provider、记忆治理`, and roadmap item `10. 长期记忆治理` is the next still-open suggested task. Earlier roadmap work is already materially covered in code:

- M1 observability / benchmark infrastructure landed through Tasks `033`, `036`, `037`, `041`, and `050`
- M2 customer/internal separation landed through Tasks `034` and `035`
- M3 scenario / benchmark expansion landed through Tasks `038`, `039`, `040`, `049`, and `050`
- M4 multi-turn / version work landed through Tasks `043`, `044`, `045`, `046`, and `048`
- M5 recovery/chaos work landed through Tasks `051` and `052`

This task builds directly on Task `047`, which introduced `memory_query_policy_v0` and made memory query shaping real but deliberately narrow. The next product gap is not more conversation scaffolding or more chaos profiles. The next gap is making read-memory behavior governable, visible, and benchmark-verifiable.

## 3. Requirements

- Keep public demo API, public frontend contracts, and workflow topology backward compatible.
- Keep the read-memory path deterministic and read-only.
- Do not add memory write-back, editing, deletion, or user-facing memory management in this task.
- Do not add or modify any Alembic revision.

### Repository and workflow loading

- Keep `MemoryItemRepository.list_active_for_user(user_id)` unchanged.
- Add `MemoryItemRepository.list_governable_for_user(user_id)`.
- `list_governable_for_user(...)` must:
  - return rows with `status == "active"`
  - not filter on `expires_at`
  - preserve deterministic ordering by `created_at`, then `memory_id`
- `WeekendPilotWorkflowNodes.load_memory(...)` must switch from `list_active_for_user(...)` to `list_governable_for_user(...)`.
- Keep the internal workflow state key `active_memories` unchanged in this task.
- `active_memories` may therefore include active-but-expired rows in v1, and governance must decide what to do with them.

### Governed memory policy contract

- Keep the helper entry point name `apply_memory_query_policy(...)`.
- Keep the helper module path `backend/app/planning/memory_query_policy.py`.
- Change the persisted policy version to `memory_query_policy_v1`.
- Keep the v1 policy scope narrow:
  - only `memory_type == "preference"` may influence planning
  - only `activity_style` and `spouse_lighter_meals` are supported projected keys
- Keep the existing normalization targets:
  - `activity_style -> citywalk | indoor | outdoor`
  - `spouse_lighter_meals -> lighter_options`
- Keep current explicit-user precedence rules:
  - `IntentParseSignals.activity_preferences == true` means user input wins for `activity_preferences`
  - `IntentParseSignals.dining_preferences == true` means user input wins for `dining_preferences`

### Tiering and downgrade rules

- v1 must classify each normalized supported memory candidate into exactly one tier:
  - `trusted`
  - `advisory`
  - `weak`
- The exact tiering rules must be:

  - `trusted`
    - confidence parses successfully
    - confidence `>= Decimal("0.8000")`
    - `expires_at` is null or in the future

  - `advisory`
    - confidence parses successfully
    - and either:
      - `Decimal("0.5000") <= confidence < Decimal("0.8000")` and memory is not expired
      - or confidence `>= Decimal("0.8000")` and memory is expired

  - `weak`
    - confidence is malformed
    - or confidence `< Decimal("0.5000")`
    - or memory is expired and confidence `< Decimal("0.8000")`

- Expired memory must therefore be visible to the policy instead of disappearing before evaluation.
- Low-confidence memory must therefore be down-ranked instead of being treated as a single opaque ignore bucket.

### Selection rules

- Evaluate `activity_preferences` and `dining_preferences` independently.
- For each dimension, the winner selection rules must be exactly:

  1. If the user explicitly provided that dimension, `winner_source = "user_input"` and no memory may change the effective intent for that dimension.
  2. Otherwise, if a `trusted` candidate exists for that dimension, apply the first such candidate in loaded-memory order.
  3. Otherwise, if an `advisory` candidate exists for that dimension, apply the first such candidate in loaded-memory order.
  4. Otherwise, apply no memory for that dimension.

- `weak` candidates must never change the effective intent.
- Unsupported keys and unrecognized values must never change the effective intent.
- Avoid duplicate preferences in the resulting effective intent.
- Keep the policy read-only; it may not mutate stored memory rows.

### Persisted summary shape

- Persist the compact governed summary at `agent_runs.metadata_json["workflow"]["memory_policy"]`.
- Replace the v0 flat-only summary with a v1 summary that includes exactly:

  - `policy_version: str`
  - `applied_memory_keys: list[str]`
  - `advisory_memory_keys: list[str]`
  - `downgraded_low_confidence_keys: list[str]`
  - `downgraded_expired_keys: list[str]`
  - `user_override_dimensions: list[str]`
  - `unsupported_memory_keys: list[str]`
  - `effective_activity_preferences: list[str]`
  - `effective_dining_preferences: list[str]`
  - `dimension_outcomes: list[MemoryGovernanceDimensionOutcome]`
  - `memory_decisions: list[MemoryGovernanceDecision]`

- `MemoryGovernanceDimensionOutcome` must include exactly:
  - `dimension: "activity_preferences" | "dining_preferences"`
  - `winner_source: "user_input" | "memory" | "none"`
  - `winner_memory_key: str | None`
  - `winner_tier: "trusted" | "advisory" | None`
  - `effective_values: list[str]`
  - `suppressed_memory_keys: list[str]`

- `MemoryGovernanceDecision` must include exactly:
  - `memory_key: str`
  - `dimension: "activity_preferences" | "dining_preferences"`
  - `normalized_value: str | None`
  - `confidence: str | None`
  - `tier: "trusted" | "advisory" | "weak"`
  - `expired: bool`
  - `outcome: "applied_trusted" | "applied_advisory" | "suppressed_user_override" | "suppressed_weak_signal" | "unsupported_key" | "unrecognized_value"`

- `memory_decisions` must preserve loaded-memory order.
- `dimension_outcomes` must be emitted in this order when present:
  1. `activity_preferences`
  2. `dining_preferences`

- The summary must stay sanitized:
  - do not persist raw memory text
  - do not persist raw `value_json`
  - do not persist `memory_id`
  - do not persist `source_langsmith_trace_id`

- It is acceptable to persist normalized projected values such as `indoor` or `lighter_options`.

### Benchmark schema and grading

- Add an additive optional benchmark expectation block `expected.memory_governance`.
- `BenchmarkExpectedOutcome` must gain:
  - `memory_governance: BenchmarkMemoryGovernanceExpectation | None = None`
- Add `BenchmarkMemoryGovernanceExpectation` with exactly:
  - `expected_policy_version: str`
  - `expected_dimension_sources: dict[str, str]`
  - `expected_dimension_tiers: dict[str, str]`
  - `expected_memory_outcomes: list[BenchmarkMemoryDecisionExpectation]`
- Add `BenchmarkMemoryDecisionExpectation` with exactly:
  - `memory_key: str`
  - `expected_outcome: str`

- Add a new benchmark score `memory_governance`.
- Only cases that define `expected.memory_governance` should receive that score.
- The score must pass only when:
  - `workflow.memory_policy.policy_version` matches the expected version
  - every expected dimension source matches `dimension_outcomes[*].winner_source`
  - every expected dimension tier matches `dimension_outcomes[*].winner_tier`
  - every expected memory outcome matches `memory_decisions[*].outcome`

### Benchmark cases and suites

- Keep `load_default_benchmark_cases()` unchanged.
- Keep `load_failure_benchmark_cases()` unchanged.
- Keep `default` suite membership unchanged at the current 10 non-failure cases.
- Keep `recovery_focused` suite membership unchanged at the current 3 recovery cases.
- Add a new named benchmark suite:
  - `memory_governance`
- `memory_governance` suite case order must be exactly:

```text
family_memory_override_v1
family_memory_advisory_fill_v1
family_memory_expired_advisory_v1
```

- Registered benchmark case order after this task must be exactly:

```text
family_afternoon_v1
family_indoor_light_meal_v1
family_outdoor_quick_dinner_v1
family_memory_override_v1
family_citywalk_addon_v1
solo_afternoon_v1
couple_afternoon_v1
friends_gathering_v1
rainy_day_fallback_v1
budget_lite_v1
family_route_failure_v1
family_route_and_dining_unavailable_v1
rainy_day_ticket_sold_out_v1
family_memory_advisory_fill_v1
family_memory_expired_advisory_v1
```

- `all_registered` must therefore contain exactly 15 cases.
- `family_memory_override_v1` must stay in the existing `default` suite and also appear in `memory_governance`.
- Update `family_memory_override_v1` by adding this exact expectation block under `expected`:

```json
{
  "memory_governance": {
    "expected_policy_version": "memory_query_policy_v1",
    "expected_dimension_sources": {
      "activity_preferences": "user_input",
      "dining_preferences": "user_input"
    },
    "expected_dimension_tiers": {},
    "expected_memory_outcomes": [
      {"memory_key": "activity_style", "expected_outcome": "suppressed_user_override"},
      {"memory_key": "spouse_lighter_meals", "expected_outcome": "suppressed_user_override"}
    ]
  }
}
```

- Add `backend/app/benchmark/cases/family_memory_advisory_fill_v1.json` with these exact task-specific fields:

  - `case_id = "family_memory_advisory_fill_v1"`
  - `title = "Family request uses advisory dining memory when the user is vague"`
  - `user_input = "This afternoon please arrange a nearby outing for my partner and our 5-year-old for a few hours."`
  - `tool_profile = "mock_world"`
  - `world_profile = "family_afternoon"`
  - `failure_profile = null`
  - one memory item:
    - `memory_type = "preference"`
    - `key = "spouse_lighter_meals"`
    - `value_json = {"preference": "lighter meals"}`
    - `text = "The spouse often prefers lighter meals."`
    - `confidence = "0.7000"`
    - `status = "active"`
  - expected statuses remain the normal successful non-failure path
  - `expected.memory_governance` must be:

```json
{
  "expected_policy_version": "memory_query_policy_v1",
  "expected_dimension_sources": {
    "dining_preferences": "memory"
  },
  "expected_dimension_tiers": {
    "dining_preferences": "advisory"
  },
  "expected_memory_outcomes": [
    {"memory_key": "spouse_lighter_meals", "expected_outcome": "applied_advisory"}
  ]
}
```

  - taxonomy must be:
    - `scenario_bucket = "family"`
    - `level = "L3"`
    - `tags = ["child_friendly", "light_meal", "memory_advisory", "memory_governance"]`
    - `failure_mode = null`
  - `metadata.focus = "memory_advisory_fill"`

- Add `backend/app/benchmark/cases/family_memory_expired_advisory_v1.json` with these exact task-specific fields:

  - `case_id = "family_memory_expired_advisory_v1"`
  - `title = "Expired family activity memory is downgraded to advisory but still visible"`
  - `user_input = "This afternoon please arrange a nearby outing for my partner and our 5-year-old for a few hours, then dinner afterward."`
  - `tool_profile = "mock_world"`
  - `world_profile = "family_afternoon"`
  - `failure_profile = null`
  - one memory item:
    - `memory_type = "preference"`
    - `key = "activity_style"`
    - `value_json = {"preference": "indoor activities"}`
    - `text = "The family recently preferred indoor plans."`
    - `confidence = "1.0"`
    - `expires_at = "2026-05-01T12:00:00+00:00"`
    - `status = "active"`
  - expected statuses remain the normal successful non-failure path
  - `expected.memory_governance` must be:

```json
{
  "expected_policy_version": "memory_query_policy_v1",
  "expected_dimension_sources": {
    "activity_preferences": "memory"
  },
  "expected_dimension_tiers": {
    "activity_preferences": "advisory"
  },
  "expected_memory_outcomes": [
    {"memory_key": "activity_style", "expected_outcome": "applied_advisory"}
  ]
}
```

  - taxonomy must be:
    - `scenario_bucket = "family"`
    - `level = "L3"`
    - `tags = ["child_friendly", "indoor_activity", "memory_expired", "memory_governance"]`
    - `failure_mode = null`
  - `metadata.focus = "memory_expired_advisory"`

- `memory_governance` suite matrix summary must be exactly:

```json
{
  "scenario_bucket_counts": {"family": 3},
  "level_counts": {"L2": 1, "L3": 2},
  "world_profile_counts": {"family_afternoon": 3},
  "failure_mode_counts": {"none": 3},
  "tag_counts": {
    "child_friendly": 3,
    "indoor_activity": 2,
    "light_meal": 2,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1
  }
}
```

## 4. Non-goals

- Do not add memory write-back, feedback learning, or user-editable memory flows.
- Do not add public API routes or frontend UI for inspecting or editing memory.
- Do not widen projected memory dimensions beyond `activity_style` and `spouse_lighter_meals`.
- Do not change query planner behavior outside what naturally follows from the effective intent it already consumes.
- Do not change recovery routing, replay, failure injection, provider selection, or action-manifest behavior.
- Do not remove or loosen the existing `memory_items` uniqueness constraint.
- Do not merge or backfill unrelated task-doc convergence work inside this implementation.
- Do not stage `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, or `var/`.

## 5. Interfaces and Contracts

### Inputs

- `LocalLifeIntent` from the deterministic parser
- `IntentParseSignals` from `parse_with_signals(...)`
- workflow-loaded `active_memories`
- existing benchmark fixture JSON files
- existing benchmark suite loader contract

### Outputs

- an effective `LocalLifeIntent` used for query planning
- persisted governed memory summary at `agent_runs.metadata_json["workflow"]["memory_policy"]`
- benchmark score `memory_governance` for cases that opt into expectation checking
- additive benchmark suite `memory_governance`

### Schemas

Persisted workflow metadata excerpt:

```json
{
  "workflow": {
    "memory_policy": {
      "policy_version": "memory_query_policy_v1",
      "applied_memory_keys": ["spouse_lighter_meals"],
      "advisory_memory_keys": ["spouse_lighter_meals"],
      "downgraded_low_confidence_keys": ["spouse_lighter_meals"],
      "downgraded_expired_keys": [],
      "user_override_dimensions": [],
      "unsupported_memory_keys": [],
      "effective_activity_preferences": ["child_friendly"],
      "effective_dining_preferences": ["lighter_options"],
      "dimension_outcomes": [
        {
          "dimension": "dining_preferences",
          "winner_source": "memory",
          "winner_memory_key": "spouse_lighter_meals",
          "winner_tier": "advisory",
          "effective_values": ["lighter_options"],
          "suppressed_memory_keys": []
        }
      ],
      "memory_decisions": [
        {
          "memory_key": "spouse_lighter_meals",
          "dimension": "dining_preferences",
          "normalized_value": "lighter_options",
          "confidence": "0.7000",
          "tier": "advisory",
          "expired": false,
          "outcome": "applied_advisory"
        }
      ]
    }
  }
}
```

Benchmark expectation excerpt:

```json
{
  "expected": {
    "memory_governance": {
      "expected_policy_version": "memory_query_policy_v1",
      "expected_dimension_sources": {
        "activity_preferences": "user_input"
      },
      "expected_dimension_tiers": {},
      "expected_memory_outcomes": [
        {
          "memory_key": "activity_style",
          "expected_outcome": "suppressed_user_override"
        }
      ]
    }
  }
}
```

## 6. Observability

This task must keep observability internal and compact.

- Persist the governed summary only at `agent_runs.metadata_json["workflow"]["memory_policy"]`.
- Add benchmark score details for `memory_governance` so benchmark case reports explain why the case passed or failed.
- Do not add a new public route, new frontend view, or new external response field.
- Do not persist raw memory text, raw `value_json`, memory IDs, or trace IDs in the governed summary.

## 7. Failure Handling

- If no governable memory exists, planning must proceed with the parsed intent unchanged and still persist a valid `memory_query_policy_v1` summary.
- If a memory key is unsupported, it must appear in `unsupported_memory_keys` and produce `outcome = "unsupported_key"` when evaluated.
- If a supported key cannot be normalized, it must produce `outcome = "unrecognized_value"` and must not change the effective intent.
- If confidence is malformed or too weak, the memory must remain visible in `memory_decisions` with `tier = "weak"` and `outcome = "suppressed_weak_signal"`.
- If the user explicitly supplied a dimension, conflicting memory must not change that dimension and must produce `outcome = "suppressed_user_override"`.
- Cases without `expected.memory_governance` must keep current benchmark behavior unchanged.
- Existing unsupported-profile, replay, recovery, observability-failure, and provider-failure behavior must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/053-memory-governance-v1.md` exists and matches this task.
- [ ] `docs/plans/053-memory-governance-v1-plan.md` exists and matches this task.
- [ ] `MemoryItemRepository.list_active_for_user(...)` behavior is unchanged.
- [ ] `MemoryItemRepository.list_governable_for_user(...)` exists and includes active expired rows.
- [ ] `load_memory(...)` now uses the governable repository method.
- [ ] The persisted workflow summary version is `memory_query_policy_v1`.
- [ ] Explicit user input still wins over stored memory for both supported dimensions.
- [ ] An active `0.7000` preference memory can be applied as `advisory` when the user is vague.
- [ ] An expired `1.0` preference memory can be applied as `advisory` when the user is vague.
- [ ] Weak or malformed memory never mutates the effective intent.
- [ ] The persisted summary includes `dimension_outcomes` and `memory_decisions`.
- [ ] The persisted summary contains no raw memory text, raw `value_json`, `memory_id`, or `source_langsmith_trace_id`.
- [ ] The benchmark harness emits a `memory_governance` score for opted-in cases.
- [ ] `family_memory_override_v1` passes with memory-governance expectations proving user override.
- [ ] `family_memory_advisory_fill_v1` passes with memory-governance expectations proving helpful advisory memory.
- [ ] `family_memory_expired_advisory_v1` passes with memory-governance expectations proving expired-memory downgrade visibility.
- [ ] `default` suite remains unchanged at 10 cases.
- [ ] `recovery_focused` suite remains unchanged at 3 cases.
- [ ] `memory_governance` suite exists with exactly 3 cases.
- [ ] `all_registered` contains exactly 15 cases in the specified order.
- [ ] No migration, public API contract, frontend contract, or provider contract changes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except for the known unrelated local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_memory_query_policy.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_repositories.py tests/integration/test_benchmark_harness_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add memory governance v1
```

## 11. Notes for the Implementer

Keep this task intentionally narrow.

The point is not to build full memory management. The point is to make the existing read-memory path governable and benchmark-visible by adding:

1. expiry-aware evaluation,
2. low-confidence down-ranking,
3. explicit user-input precedence,
4. compact conflict visibility.

If implementation pressure suggests changing database schema, public demo responses, or frontend behavior, stop and reassess. That is outside the intended v1 slice.
