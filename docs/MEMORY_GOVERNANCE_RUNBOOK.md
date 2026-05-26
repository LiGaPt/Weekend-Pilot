# Memory Governance Runbook

## Overview

WeekendPilot already ships one narrow but releasable memory-governance slice for V1. That slice is not full memory lifecycle management. It is a deterministic, read-only query-shaping policy that decides when stored preference memory may influence planning and when it must be suppressed.

The current implementation is already benchmark-backed:

- runtime policy version: `memory_query_policy_v1`
- focused suite: `memory_governance`
- blocking release suite: `release_gate_v1`
- broader supporting suite: `all_registered`

This runbook is the canonical release-facing description of that slice. Use it to answer:

1. what the V1 memory slice actually does
2. which benchmark evidence proves it
3. what remains future work

## V1 Scope Boundary

The current V1 memory-governance slice is intentionally narrow.

- It is read-only. It does not write, edit, delete, or merge memory.
- It only governs workflow query shaping before planning.
- It only considers memory rows where `memory_type == "preference"`.
- It only projects two supported keys:
  - `activity_style` -> `activity_preferences`
  - `spouse_lighter_meals` -> `dining_preferences`
- It only emits these normalized values:
  - `activity_style -> citywalk | indoor | outdoor`
  - `spouse_lighter_meals -> lighter_options`
- It persists a compact audit summary at `agent_runs.metadata_json["workflow"]["memory_policy"]`.
- It keeps the persisted summary sanitized. The governed summary does not expose raw memory text or raw `value_json`.

The current V1 slice is explicitly not:

- memory CRUD
- user-facing memory review or editing
- retention policy redesign
- sensitive-data minimization beyond the existing compact audit summary
- broader projected keys or broader memory types

## Rule Matrix

| Rule | Runtime Contract | Evidence Level | Evidence Surface | Persisted Evidence Fields |
| --- | --- | --- | --- | --- |
| Explicit user-input override | If the user explicitly supplies `activity_preferences` or `dining_preferences`, that dimension keeps `winner_source = "user_input"` and conflicting memory is suppressed. | Benchmark-backed | `family_memory_override_v1`; `tests/test_memory_query_policy.py::test_memory_query_policy_explicit_user_override_beats_memory_for_both_dimensions`; `tests/integration/test_benchmark_harness_gateway.py::test_benchmark_harness_records_memory_policy_for_override_case` | `run_summary.workflow.memory_policy.dimension_outcomes[*].winner_source`; `run_summary.workflow.memory_policy.memory_decisions[*].outcome`; `scores[*].name == "memory_governance"` |
| Advisory memory fill for vague requests | If the user is vague and a supported memory has confidence `0.5000 <= confidence < 0.8000` and is not expired, that memory is `advisory` and may fill the matching dimension. | Benchmark-backed | `family_memory_advisory_fill_v1`; `tests/test_memory_query_policy.py::test_memory_query_policy_applies_advisory_dining_preference_when_user_is_vague`; `tests/integration/test_benchmark_harness_gateway.py::test_benchmark_harness_records_memory_policy_for_advisory_fill_case` | `run_summary.workflow.memory_policy.advisory_memory_keys`; `dimension_outcomes[*].winner_tier`; `memory_decisions[*].outcome`; `scores[*].details.observed_dimension_tiers` |
| Expired high-confidence downgrade | If a supported memory is expired but confidence is still `>= 0.8000`, the memory is downgraded to `advisory` instead of disappearing before evaluation. It may still apply when the user is vague. | Benchmark-backed | `family_memory_expired_advisory_v1`; `tests/test_memory_query_policy.py::test_memory_query_policy_applies_expired_high_confidence_activity_as_advisory`; `tests/integration/test_benchmark_harness_gateway.py::test_benchmark_harness_records_memory_policy_for_expired_advisory_case` | `run_summary.workflow.memory_policy.downgraded_expired_keys`; `dimension_outcomes[*].winner_tier`; `memory_decisions[*].expired`; `scores[*].details.observed_dimension_tiers` |
| Supported-key boundary | Only `activity_style` and `spouse_lighter_meals` may influence intent. Other preference keys stay visible for audit but must not change the effective intent. | Unit-test-backed | `backend/app/planning/memory_query_policy.py`; `tests/test_memory_query_policy.py::test_memory_query_policy_records_unsupported_keys_and_sanitizes_summary` | `run_summary.workflow.memory_policy.unsupported_memory_keys`; `memory_decisions[*].outcome == "unsupported_key"` |
| Weak / unsupported suppression | Malformed confidence, confidence `< 0.5000`, or expired memory below `0.8000` is `weak` and cannot mutate intent. Unrecognized supported values also cannot mutate intent. | Unit-test-backed | `backend/app/planning/memory_query_policy.py`; `tests/test_memory_query_policy.py::test_memory_query_policy_suppresses_weak_memory_without_mutating_intent`; `tests/test_memory_query_policy.py::test_memory_query_policy_records_unsupported_keys_and_sanitizes_summary` | `run_summary.workflow.memory_policy.downgraded_low_confidence_keys`; `memory_decisions[*].tier == "weak"`; `memory_decisions[*].outcome in {"suppressed_weak_signal", "unrecognized_value", "unsupported_key"}` |

## Benchmark Evidence

Use these three benchmark cases as the canonical benchmark-backed proof points for the V1 memory slice.

### 1. `family_memory_override_v1`

This case proves that explicit user input beats stored memory.

- expected policy version: `memory_query_policy_v1`
- expected dimension sources:
  - `activity_preferences -> user_input`
  - `dining_preferences -> user_input`
- expected dimension tiers: none
- expected memory outcomes:
  - `activity_style -> suppressed_user_override`
  - `spouse_lighter_meals -> suppressed_user_override`

Inspect:

- `case_results[*].run_summary.workflow.memory_policy.dimension_outcomes`
- `case_results[*].run_summary.workflow.memory_policy.memory_decisions`
- `case_results[*].scores[*]` where `name == "memory_governance"`

### 2. `family_memory_advisory_fill_v1`

This case proves that an advisory dining preference can help when the user stays vague.

- expected policy version: `memory_query_policy_v1`
- expected dimension sources:
  - `dining_preferences -> memory`
- expected dimension tiers:
  - `dining_preferences -> advisory`
- expected memory outcomes:
  - `spouse_lighter_meals -> applied_advisory`

Inspect:

- `case_results[*].run_summary.workflow.memory_policy.advisory_memory_keys`
- `case_results[*].run_summary.workflow.memory_policy.dimension_outcomes`
- `case_results[*].run_summary.workflow.memory_policy.memory_decisions`
- `case_results[*].scores[*]` where `name == "memory_governance"`

### 3. `family_memory_expired_advisory_v1`

This case proves that expired high-confidence activity memory is downgraded to advisory but remains visible and usable.

- expected policy version: `memory_query_policy_v1`
- expected dimension sources:
  - `activity_preferences -> memory`
- expected dimension tiers:
  - `activity_preferences -> advisory`
- expected memory outcomes:
  - `activity_style -> applied_advisory`

Inspect:

- `case_results[*].run_summary.workflow.memory_policy.downgraded_expired_keys`
- `case_results[*].run_summary.workflow.memory_policy.dimension_outcomes`
- `case_results[*].run_summary.workflow.memory_policy.memory_decisions`
- `case_results[*].scores[*]` where `name == "memory_governance"`

### Suite and tag interpretation

All three cases are already inside the blocking `release_gate_v1` suite.

The memory-related release-gate tag counts are intentionally:

- `memory_override == 1`
- `memory_advisory == 1`
- `memory_expired == 1`
- `memory_governance == 2`

`memory_governance` is `2`, not `3`, because:

- `family_memory_override_v1` is tagged `memory_override`
- `family_memory_advisory_fill_v1` is tagged `memory_governance`
- `family_memory_expired_advisory_v1` is tagged `memory_governance`

## Release Acceptance

### Canonical evidence inputs

Treat these files as the canonical generated evidence inputs for this slice:

- `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- `var/formal-benchmarks/latest-all_registered-run-report.json`

Do not treat `docs/artifacts/` as the source of truth for release decisions in this task.

### Blocking release acceptance

The blocking V1 memory-governance acceptance boundary is the existing `release_gate_v1` suite.

Current expected release-gate summary:

- `suite_id == "release_gate_v1"`
- `case_count == 15`
- `passed_count == 15`
- `failed_count == 0`
- `error_count == 0`
- `overall_score == 1.0`
- `level_counts == {"L1": 3, "L2": 8, "L3": 4}`
- `tag_counts.memory_override == 1`
- `tag_counts.memory_advisory == 1`
- `tag_counts.memory_expired == 1`
- `tag_counts.memory_governance == 2`

Run:

```bash
python scripts/run_benchmark_release_gate.py
```

Release is blocked if those values drift.

### Broader supporting evidence

`all_registered` is broader supporting evidence, not the blocking V1 bar.

Current expected formal-verification summary:

- `suite_id == "all_registered"`
- `case_count == 17`
- `passed_count == 17`
- `failed_count == 0`
- `error_count == 0`
- `overall_score == 1.0`
- `tag_counts.memory_override == 1`
- `tag_counts.memory_advisory == 1`
- `tag_counts.memory_expired == 1`
- `tag_counts.memory_governance == 2`

Run:

```bash
python scripts/run_formal_verification.py
```

This broader suite intentionally includes the two current `L5` composite chaos cases that stay outside the blocking V1 release gate.

### Practical release checklist

1. Run `python scripts/run_benchmark_release_gate.py`.
2. Confirm `var/formal-benchmarks/latest-release_gate_v1-run-report.json` refreshed and still matches the counts above.
3. Confirm all three memory benchmark cases still show `memory_query_policy_v1` and the expected memory-governance outcomes.
4. Optionally run `python scripts/run_formal_verification.py` and confirm `latest-all_registered-run-report.json` still matches the broader counts above.
5. Confirm no secrets, `var/`, or unrelated local artifacts are staged.

## Open Follow-ups

The current V1 slice is intentionally incomplete. These are still future work:

- memory CRUD and user-facing review/edit flows
- stronger sensitive-data minimization and retention controls
- broader supported memory keys or memory types
- user-controllable expiration, suppression, or deletion actions

Those follow-ups belong to broader M5 memory-governance work, not to the current read-memory V1 slice.
