# Spec: 095 Memory Decision Log + Policy Summary v0

## 1. Goal

Standardize an additive memory decision audit contract that records how each governable memory item was evaluated during query shaping, whether it was used, ignored, downgraded, or overridden, and how strongly it influenced the effective intent.

WeekendPilot already persists `workflow.memory_policy` metadata and already proves memory-governance outcomes through benchmark cases. However, the current summary is still optimized for grading rather than auditability: it does not persist `memory_id`, it does not normalize high-level decision status across use/ignore/downgrade/override, and benchmark reports do not expose one compact case-level policy summary for reviewers. After this task, each run and each benchmark case report must provide a stable, sanitized, per-memory decision log plus a compact policy summary without changing existing memory-governance grading semantics.

## 2. Project Context

This task fits into two blueprint areas:

- `docs/PROJECT_BLUEPRINT.md` Section 10 memory rules:
  - current user input overrides long-term memory
  - low-confidence memory should not strongly influence plans
  - expired memory should be ignored or downgraded
- `docs/PROJECT_BLUEPRINT.md` Sections 14, 16, and 17:
  - observability by default
  - harness engineering as product infrastructure
  - benchmark scoring for memory usage and auditability

In `docs/NEXT_PHASE_ROADMAP.md`, the default current priority is `M1. 评测与观测基础设施`. This task belongs there because it strengthens auditable benchmark/reporting surfaces rather than expanding user-visible product behavior. It also prepares the repository for later `M5` memory-governance work by making current read-memory decisions explicitly inspectable.

The current implementation already contains:

- `memory_query_policy_v1`
- persisted `agent_runs.metadata_json["workflow"]["memory_policy"]`
- benchmark grading through `grade_memory_governance(...)`
- benchmark reports and benchmark artifact summaries

This task must extend those surfaces additively rather than redesign them.

## 3. Requirements

- Keep the current read-memory behavior deterministic and backward compatible.
- Keep the current supported memory scope unchanged:
  - `memory_type == "preference"`
  - `activity_style`
  - `spouse_lighter_meals`
- Keep existing `memory_decisions`, `dimension_outcomes`, and benchmark grading semantics valid.
- Add one additive `decision_log` list under `agent_runs.metadata_json["workflow"]["memory_policy"]`.
- Add one additive `policy_summary` object under `agent_runs.metadata_json["workflow"]["memory_policy"]`.
- `decision_log` must preserve loaded-memory order.
- Each `decision_log` entry must include at minimum:
  - `memory_id`
  - `key`
  - `status`
  - `decision`
  - `reason`
  - `influence_level`
- `decision_log` may also include additive audit fields required to interpret the decision:
  - `dimension`
  - `normalized_value`
  - `tier`
  - `expired`
- `status` must be normalized to one of:
  - `used`
  - `ignored`
  - `downgraded`
  - `overridden`
- `influence_level` must be normalized to one of:
  - `primary`
  - `advisory`
  - `none`
- `decision` must remain machine-readable and stable. The task must reuse the current decision surface rather than invent an unrelated vocabulary:
  - `applied_trusted`
  - `applied_advisory`
  - `suppressed_user_override`
  - `suppressed_weak_signal`
  - `unsupported_key`
  - `unrecognized_value`
- `reason` must be a stable lower-snake-case code, not free-form prose.
- `policy_summary` must provide one compact additive count/rollup surface suitable for case-report review.
- `policy_summary` must include at minimum:
  - `policy_version`
  - `considered_count`
  - `used_count`
  - `ignored_count`
  - `downgraded_count`
  - `overridden_count`
  - `primary_influence_count`
  - `advisory_influence_count`
  - `no_influence_count`
- `policy_summary` must be derivable directly from `decision_log`; it must not depend on a second independent classification path.
- Benchmark case reports must expose the compact memory policy summary additively.
- Benchmark artifact summary in run metadata must expose the compact memory policy summary additively.
- Internal observability summary may expose the compact memory policy summary additively, but must not expose raw memory payloads.
- Existing release gates, coverage gates, V2 integrity gate, and stability harness semantics must remain unchanged.

## 4. Non-goals

- Do not change memory retrieval scope or projected keys.
- Do not change query-planning behavior beyond additive metadata/reporting surfaces.
- Do not add memory CRUD, retention controls, or user-facing memory inspection.
- Do not add a database migration.
- Do not add new benchmark cases or change suite membership.
- Do not change `grade_memory_governance(...)` expected outcome semantics.
- Do not expand frontend or reviewer UI in this task.
- Do not commit `.env`, API keys, tokens, secrets, or generated artifacts under `var/`.

## 5. Interfaces and Contracts

### Inputs

- `LocalLifeIntent`
- `IntentParseSignals`
- ordered `WorkflowMemoryRecord` items from `load_memory`
- existing `MemoryQueryPolicySummary` generation path
- benchmark harness case finalization path
- internal observability summary path

### Outputs

- additive run metadata:
  - `agent_runs.metadata_json["workflow"]["memory_policy"]["decision_log"]`
  - `agent_runs.metadata_json["workflow"]["memory_policy"]["policy_summary"]`
- additive benchmark case report field:
  - `memory_policy_summary`
- additive benchmark artifact summary field:
  - `memory_policy_summary`
- additive internal observability artifact summary field:
  - `memory_policy_summary`

### Schemas

Required `decision_log` entry shape:

```json
{
  "memory_id": "4a87a9ee-2f2d-4f65-bae6-7d0af5194579",
  "key": "spouse_lighter_meals",
  "status": "downgraded",
  "decision": "applied_advisory",
  "reason": "low_confidence_downgraded_to_advisory",
  "influence_level": "advisory",
  "dimension": "dining_preferences",
  "normalized_value": "lighter_options",
  "tier": "advisory",
  "expired": false
}
```

Required `policy_summary` shape:

```json
{
  "policy_version": "memory_query_policy_v1",
  "considered_count": 1,
  "used_count": 0,
  "ignored_count": 0,
  "downgraded_count": 1,
  "overridden_count": 0,
  "primary_influence_count": 0,
  "advisory_influence_count": 1,
  "no_influence_count": 0
}
```

Required mapping rules:

- `applied_trusted`
  - `status = "used"`
  - `reason = "trusted_memory_applied"`
  - `influence_level = "primary"`
- `applied_advisory` with non-expired advisory tier from low confidence
  - `status = "downgraded"`
  - `reason = "low_confidence_downgraded_to_advisory"`
  - `influence_level = "advisory"`
- `applied_advisory` with expired high-confidence memory
  - `status = "downgraded"`
  - `reason = "expired_memory_downgraded_to_advisory"`
  - `influence_level = "advisory"`
- `suppressed_user_override`
  - `status = "overridden"`
  - `reason = "explicit_user_input_present"`
  - `influence_level = "none"`
- `suppressed_weak_signal`
  - `status = "ignored"`
  - `reason = "weak_signal_not_applied"`
  - `influence_level = "none"`
- `unsupported_key`
  - `status = "ignored"`
  - `reason = "unsupported_projected_key"`
  - `influence_level = "none"`
- `unrecognized_value`
  - `status = "ignored"`
  - `reason = "unrecognized_supported_value"`
  - `influence_level = "none"`

Sanitization constraints:

- `decision_log` may include `memory_id`
- do not include raw `text`
- do not include raw `value_json`
- do not include `source_langsmith_trace_id`
- do not include secrets, tokens, authorization values, or prompt/debug payloads

## 6. Observability

This task adds auditability only.

The system must record:

- one per-run memory decision log under workflow metadata
- one compact per-run policy summary under workflow metadata
- one additive benchmark case report summary for memory policy
- one additive benchmark artifact summary for memory policy

This task must not add:

- new LangSmith metadata families
- new database tables
- new Redis channels
- new public API fields
- new frontend panels

## 7. Failure Handling

- If no governable memory items exist, persist:
  - `decision_log = []`
  - a valid zero-count `policy_summary`
- If a memory entry has malformed confidence, unsupported key, or unrecognized value, the audit log must still record it with normalized `status`, `decision`, `reason`, and `influence_level`.
- If existing benchmark runs have no `memory_policy` block, additive report fields must fall back safely to `null` or an absent summary instead of failing report generation.
- If benchmark artifact summary enrichment cannot derive `policy_summary`, benchmark execution must still succeed; only the additive summary field may remain absent.
- If a report writer or observability path encounters malformed memory summary payloads, it must degrade safely rather than rewrite or delete existing benchmark metadata.

## 8. Acceptance Criteria

- [ ] `workflow.memory_policy.decision_log` exists and preserves loaded-memory order.
- [ ] Every logged decision includes `memory_id`, `key`, `status`, `decision`, `reason`, and `influence_level`.
- [ ] `status` is normalized to `used | ignored | downgraded | overridden`.
- [ ] `influence_level` is normalized to `primary | advisory | none`.
- [ ] Existing `memory_decisions` and `dimension_outcomes` remain present and backward compatible.
- [ ] `workflow.memory_policy.policy_summary` exists and aggregates counts from `decision_log`.
- [ ] Override, advisory-fill, expired-advisory, weak-signal, and unsupported-key cases all map to the expected normalized status/reason/influence combination.
- [ ] Benchmark case reports expose additive `memory_policy_summary` without breaking existing report schema consumers.
- [ ] Benchmark artifact summary exposes additive `memory_policy_summary` without removing existing fields.
- [ ] Internal observability summary can read the additive memory policy summary when present.
- [ ] Existing memory-governance benchmark grading continues to pass without expectation changes.
- [ ] No new benchmark suite thresholds, case memberships, or gate semantics change.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit, excluding pre-existing unrelated local changes.

## 9. Verification Commands

```bash
git status --short
python -m pytest tests/test_memory_query_policy.py tests/test_benchmark_harness.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -k "memory_policy or benchmark_artifact_summary" -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add memory decision audit log
```

## 11. Notes for the Implementer

Keep this task additive and audit-focused.

Do not replace the current memory-governance grading contract. The safest implementation is to derive `decision_log` and `policy_summary` from the existing policy decisions in one place, then reuse that summary in benchmark and observability layers. If implementation pressure suggests changing benchmark fixture expectations, suite membership, or public-facing routes, stop and report that scope expansion instead of folding it into this task.
