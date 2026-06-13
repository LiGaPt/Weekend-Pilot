# Plan: 095 Memory Decision Log + Policy Summary v0

## 1. Spec Reference

Spec file:

```text
docs/specs/095-memory-decision-log-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/094-stability-harness-passk-v0`.
- Latest completed task chain is `001` through `094`; specs and plans are continuous and matched.
- Latest commit is `4e43cd2 feat: add benchmark stability passk metrics`, which matches Task `094`.
- Existing memory governance already persists:
  - `workflow.memory_policy`
  - `memory_decisions`
  - `dimension_outcomes`
- Existing benchmark and observability surfaces already persist:
  - case reports
  - suite reports
  - `benchmark.artifact_summary`
  - internal observability benchmark artifact summaries
- There are pre-existing untracked local docs outside this task:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- No existing spec/plan/commit mismatch requires a higher-priority convergence task before `095`.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/planning/memory_query_policy.py` - add normalized decision-log and policy-summary models plus derivation logic.
- `backend/app/benchmark/schemas.py` - add additive benchmark report schema fields for memory policy summary.
- `backend/app/benchmark/harness.py` - attach compact memory policy summary to case results and benchmark artifact summary.
- `backend/app/observability/schemas.py` - extend internal benchmark artifact summary with additive memory policy summary shape.
- `backend/app/observability/service.py` - read additive memory policy summary from benchmark/workflow metadata.
- `tests/test_memory_query_policy.py` - cover normalized audit mapping and summary counts.
- `tests/test_benchmark_harness.py` - cover additive report schema fields and case-result export.
- `tests/integration/test_benchmark_harness_gateway.py` - verify persisted metadata and benchmark artifact summary for memory benchmark cases.
- `tests/test_observability.py` - verify internal observability summary reads additive memory policy summary safely.

## 5. Implementation Steps

1. Read the spec plus current `memory_query_policy.py`, `benchmark/schemas.py`, `benchmark/harness.py`, and observability summary code together before editing.
2. In `backend/app/planning/memory_query_policy.py`, add two additive Pydantic models:
   - `MemoryDecisionLogEntry`
   - `MemoryPolicyAuditSummary`
3. Keep the existing `MemoryGovernanceDecision` model untouched for backward compatibility.
4. Add `decision_log` and `policy_summary` fields to `MemoryQueryPolicySummary`.
5. Implement one internal helper that maps each current memory evaluation outcome to:
   - normalized `status`
   - normalized `reason`
   - normalized `influence_level`
6. Ensure the helper uses `memory.memory_id` directly and never reads raw text/value payload into the audit entry.
7. Build each `decision_log` entry at the same decision point where `memory_decisions` is already appended, so both surfaces stay aligned.
8. Build `policy_summary` only from the finalized `decision_log`, not from independent branching logic.
9. Keep `decision_log` ordered exactly as memory items are processed.
10. Keep existing `dimension_outcomes` ordering unchanged.
11. In `tests/test_memory_query_policy.py`, add focused assertions for:
   - trusted application -> `used` / `primary`
   - low-confidence advisory application -> `downgraded` / `advisory`
   - expired advisory application -> `downgraded` / `advisory`
   - explicit user override -> `overridden` / `none`
   - weak suppression -> `ignored` / `none`
   - unsupported key -> `ignored` / `none`
   - zero-memory path -> empty `decision_log` and zero-count `policy_summary`
12. Run the focused memory policy tests and confirm they fail before wiring all callers if following strict TDD is practical in-session.
13. In `backend/app/benchmark/schemas.py`, add one additive compact schema for benchmark-exported memory policy summary if needed; prefer a minimal mirror of the policy-summary count fields rather than reusing the full workflow model directly.
14. Add an optional `memory_policy_summary` field to `BenchmarkCaseResult`.
15. In `backend/app/benchmark/harness.py`, after loading run metadata, extract `workflow.memory_policy.policy_summary` and attach it to:
   - `BenchmarkCaseResult`
   - `benchmark.artifact_summary`
16. Do not attach the full `decision_log` to benchmark artifact summary; keep benchmark artifact summary compact.
17. Preserve current benchmark case report and suite report writing flow; only add the new field additively.
18. In `backend/app/observability/schemas.py`, extend `InternalBenchmarkArtifactSummary` with an optional compact `memory_policy_summary` field.
19. In `backend/app/observability/service.py`, read the summary from:
   - `benchmark.artifact_summary.memory_policy_summary` first
   - optionally fall back to `workflow.memory_policy.policy_summary` if artifact summary lacks it
20. Keep observability sanitization behavior unchanged; the summary should be numeric/count-based only.
21. In `tests/test_benchmark_harness.py`, add unit tests asserting:
   - run/case report serialization includes `memory_policy_summary`
   - existing schema fields remain unchanged
22. In `tests/test_observability.py`, add tests asserting:
   - internal benchmark artifact summary returns `memory_policy_summary` when present
   - missing summary falls back safely without failure
23. In `tests/integration/test_benchmark_harness_gateway.py`, extend the three benchmark-backed memory cases:
   - `family_memory_override_v1`
   - `family_memory_advisory_fill_v1`
   - `family_memory_expired_advisory_v1`
   Verify persisted `decision_log` and `policy_summary` plus benchmark artifact summary export.
24. Re-run focused unit tests.
25. Start `postgres` and `redis`, run Alembic, then execute focused integration tests.
26. Run `git diff --check` and `git status --short`.
27. Stage only task-relevant files; do not stage the pre-existing untracked docs.
28. Commit with the expected message.

## 6. Testing Plan

- Unit tests:
  - trusted memory produces `used` / `primary`
  - low-confidence advisory memory produces `downgraded` / `advisory`
  - expired advisory memory produces `downgraded` / `advisory`
  - explicit user override produces `overridden` / `none`
  - weak and unsupported memory produce `ignored` / `none`
  - zero-memory path emits empty `decision_log` and zeroed `policy_summary`
  - benchmark case result schema accepts and serializes additive `memory_policy_summary`
  - internal observability summary reads additive summary when present
- Integration tests:
  - override benchmark case persists normalized decision log and summary
  - advisory benchmark case persists normalized decision log and summary
  - expired advisory benchmark case persists normalized decision log and summary
  - benchmark artifact summary exposes compact memory policy summary
- Smoke tests:
  - no gate/report schema regression in focused benchmark harness paths
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
git status --short
python -m pytest tests/test_memory_query_policy.py tests/test_benchmark_harness.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -k "memory_policy or benchmark_artifact_summary" -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add memory decision audit log
```

Expected commands:

```bash
git status --short
git add backend/app/planning/memory_query_policy.py backend/app/benchmark/schemas.py backend/app/benchmark/harness.py backend/app/observability/schemas.py backend/app/observability/service.py tests/test_memory_query_policy.py tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py tests/test_observability.py
git commit -m "feat: add memory decision audit log"
git push
```

The implementer must confirm `.env`, secrets, and the pre-existing unrelated untracked docs are not staged.

## 9. Out-of-scope Changes

- Do not change supported memory keys or projected dimensions.
- Do not change benchmark fixture JSON.
- Do not change suite membership or gate thresholds.
- Do not change workflow routing or execution behavior.
- Do not add new database schema or migrations.
- Do not add frontend or internal review UI work.
- Do not stage or modify unrelated local docs:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The task stayed additive and did not replace existing `memory_decisions` or benchmark grading logic.
- [ ] `decision_log` contains `memory_id`, `key`, `status`, `decision`, `reason`, and `influence_level`.
- [ ] `policy_summary` counts match the emitted `decision_log`.
- [ ] Benchmark case reports include additive `memory_policy_summary`.
- [ ] Benchmark artifact summary includes additive `memory_policy_summary`.
- [ ] Internal observability summary reads the compact memory policy summary safely.
- [ ] Focused unit tests passed.
- [ ] Focused integration tests passed.
- [ ] Git status was clean after commit, excluding pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Report back with:

- changed files
- exact normalized status/reason/influence mapping implemented
- verification commands and results
- commit hash
- push result
- whether any pre-existing local files remained unstaged
- any follow-up work, especially if a later task should expose `decision_log` in reviewer-facing UI or add suite-level memory audit rollups
