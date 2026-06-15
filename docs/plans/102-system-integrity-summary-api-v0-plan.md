# Plan: 102 System Integrity Summary API v0

## 1. Spec Reference

Spec file:

```text
docs/specs/102-system-integrity-summary-api-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/101-benchmark-coverage-gate-convergence-v0`.
- Latest commit is `bc92eff test: align coverage gate integration expectations`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `101`.
- There is no tracked `102` spec or plan yet.
- Existing internal routes already exist and must remain backward compatible:
  - `GET /internal/benchmarks/release-gate-v1/summary`
  - `GET /internal/runs/{run_id}/observability`
- Existing latest aliases already exist at the code-contract level for:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Existing schemas already exist for the required source artifacts:
  - `BenchmarkRunReport`
  - `BenchmarkStabilityPassKReport`
  - `RecoveryReplayReviewResult`
  - `MemoryPolicyAuditSummary`
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- `backend/app/observability/integrity_summary.py` - load canonical latest aliases, validate artifact payloads, derive the aggregated system-integrity summary, and normalize degraded section status.
- `tests/test_system_integrity_summary.py` - focused unit tests for artifact loaders, section derivation, partial degradation, and redaction contract behavior.

## 4. Files to Modify

- `backend/app/api/observability.py` - add the new `/internal/system/integrity-summary` route and HTTP error handling.
- `backend/app/observability/schemas.py` - add typed response models for the aggregated system-integrity summary and its sub-sections.
- `backend/app/observability/__init__.py` - export the new summary loader/service symbols if the package already re-exports observability types.
- `tests/integration/test_observability_gateway.py` - add gateway tests for the new route across success and degraded states.
- `tests/test_demo_api.py` - assert the new route appears in the FastAPI schema.

## 5. Implementation Steps

1. Read the current observability route patterns in `backend/app/api/observability.py`.
2. Read the existing internal summary patterns in:
   - `backend/app/benchmark/internal_summary.py`
   - `backend/app/observability/service.py`
3. Read the existing artifact schemas in `backend/app/benchmark/schemas.py`.
4. Read the existing memory audit contract in `backend/app/planning/memory_query_policy.py`.
5. Create the new typed sub-models in `backend/app/observability/schemas.py` for:
   - top-level system-integrity summary
   - benchmark gate section
   - stability section
   - memory-governance section
   - recovery replay section
   - timing section
   - redaction section
   - evidence-path entry
6. Keep new models additive and do not modify `InternalObservabilityRunSummary`.
7. Create `backend/app/observability/integrity_summary.py`.
8. In that module, define canonical relative-path constants for every evidence alias the route will expose.
9. Add typed section status/error helpers so each section can independently report:
   - `ready`
   - `missing`
   - `invalid`
10. Add a small JSON file loader helper that:
    - reads UTF-8 JSON
    - returns parsed dict payloads
    - classifies missing and malformed errors without throwing route-breaking exceptions by default
11. Implement the V2 benchmark gate section loader:
    - read `latest-v2_integrity_gate-run-report.json`
    - validate with `BenchmarkRunReport`
    - extract the enriched `v2_integrity_gate_evaluation`
    - derive benchmark counts and gate flags
12. Do not re-implement V2 gate formulas if the report already contains the enriched evaluation block.
13. Implement the stability section loader:
    - read `stability/latest-v2_integrity-passk-v0-report.json`
    - validate with `BenchmarkStabilityPassKReport`
    - expose pass-k metrics and canonical latest alias path
14. Implement the memory-governance section loader:
    - read `latest-all_registered-run-report.json`
    - validate with `BenchmarkRunReport`
    - iterate `case_results`
    - detect memory-governance cases by presence of a score whose `name == "memory_governance"`
    - count passed/failed/error cases
    - collect `case_ids` and `failing_case_ids`
15. Keep memory-governance aggregation derived only from report content; do not inspect individual run database rows.
16. Implement the recovery section loader:
    - read `latest-family_route_failure_v1-review.json`
    - validate with `RecoveryReplayReviewResult`
    - derive overall review status, check counts, attempt counts, and recovery actions
17. Implement the timing section loader:
    - reuse `benchmark_summary.benchmark_timing_summary` from the V2 gate report when present
    - reuse stability metadata such as `window_size` and `executed_run_count`
    - mark timing partial when benchmark timing is absent but stability metadata exists
18. Implement the redaction section builder as deterministic API-owned metadata:
    - `internal_only = true`
    - `sanitized = true`
    - `relative_evidence_paths_only = true`
    - static forbidden markers list aligned with existing backend redaction rules
19. Implement the evidence-path entry builder:
    - include every canonical path
    - mark `exists`
    - mark `required_for_summary`
    - derive per-path status from file presence and section validation
20. Implement one top-level `load_system_integrity_summary()` function in `backend/app/observability/integrity_summary.py`.
21. Derive top-level status from section statuses:
    - all core required sections ready -> `ready`
    - at least one required section missing -> `missing_evidence`
    - at least one required section invalid -> `invalid_evidence`
    - any mix of ready and missing/invalid with partial usability -> `degraded`
22. Make sure the function returns a typed Pydantic model rather than raw dicts.
23. Add the route to `backend/app/api/observability.py`:
    - `GET /internal/system/integrity-summary`
    - `response_model=<new summary model>`
24. Map contract-handled partial states to `200`.
25. Reserve `500` only for unexpected exceptions escaping the summary builder.
26. Do not change the existing release-gate or per-run observability endpoints.
27. Add unit tests in `tests/test_system_integrity_summary.py` for:
    - fully ready summary
    - missing V2 gate alias
    - invalid stability report
    - memory-governance case derivation
    - recovery summary derivation
    - evidence paths stay relative
    - forbidden key markers are present in redaction summary
28. Use temporary directories and monkeypatch the path constants in the new summary module instead of touching real `var/`.
29. Add or update gateway tests in `tests/integration/test_observability_gateway.py` for:
    - `200` success path
    - `200` degraded path when one alias is missing
    - response shape and section statuses
30. Add or update `tests/test_demo_api.py` so the new path appears in the FastAPI OpenAPI schema.
31. Run focused unit tests first.
32. Run gateway tests after unit tests are green.
33. Run `git diff --check`.
34. Run `git status --short`.
35. Stage only the task-relevant backend and test files plus the `102` spec/plan files after they are saved later.
36. Commit with the expected message.

## 6. Testing Plan

- Unit tests:
  - summary builder returns `ready` when all latest aliases are present and valid
  - summary builder returns partial/degraded output when one alias is missing
  - summary builder returns invalid section status when one alias contains malformed JSON or invalid schema
  - memory-governance aggregation counts cases based on `memory_governance` score presence
  - recovery summary derives check counts and attempt counts from canonical review payload
  - evidence paths remain repository-relative
  - redaction summary exposes the expected forbidden-key markers
- Integration tests:
  - `/internal/system/integrity-summary` returns `200` and the expected response shape
  - missing/invalid artifact inputs degrade section status without changing the response route to `404`
  - existing observability routes still behave unchanged
- Smoke tests:
  - FastAPI schema includes the new route
  - no frontend test changes
- Non-goals for testing:
  - do not run or refresh benchmark artifacts
  - do not run stability harness or recovery review commands as part of this task’s verification unless needed to debug a schema mismatch
  - do not add browser/UI tests

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
git status --short
python -m pytest tests/test_system_integrity_summary.py tests/test_observability.py tests/test_benchmark_internal_summary.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_observability_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add system integrity summary api
```

Expected commands:

```bash
git status --short
git add backend/app/api/observability.py
git add backend/app/observability/schemas.py
git add backend/app/observability/__init__.py
git add backend/app/observability/integrity_summary.py
git add tests/test_system_integrity_summary.py
git add tests/integration/test_observability_gateway.py
git add tests/test_demo_api.py
git add docs/specs/102-system-integrity-summary-api-v0.md
git add docs/plans/102-system-integrity-summary-api-v0-plan.md
git diff --cached --check
git commit -m "feat: add system integrity summary api"
git push -u origin codex/102-system-integrity-summary-api-v0
```

The implementer must confirm the staged set does not include:

- `var/`
- `docs/NEW_WORKFLOW_PROMPT.md`
- `docs/TASK_INFO.md`
- `docs/superpowers/`
- any `.env` file
- any secrets or local-only artifacts

## 9. Out-of-scope Changes

- Do not add the `103` 5174 panel UI.
- Do not modify `frontend/`.
- Do not change benchmark suite membership, gate rules, or pass-k formulas.
- Do not change memory-query policy logic or lifecycle rules.
- Do not change recovery replay review checks or artifact-writing behavior.
- Do not modify `scripts/show_submission_evidence.py` unless a shared constant extraction is strictly necessary and kept backward compatible.
- Do not add new dependencies, migrations, or Redis/runtime contracts.
- Do not refresh or commit generated benchmark/recovery artifacts.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/102-system-integrity-summary-api-v0.md`.
- [ ] The route exists at `GET /internal/system/integrity-summary`.
- [ ] The response uses a dedicated typed schema.
- [ ] The route reads latest aliases only and does not trigger benchmark/recovery execution.
- [ ] The response includes benchmark, stability, memory-governance, recovery, timing, redaction, and evidence-path sections.
- [ ] Missing or invalid artifacts degrade section status without crashing the route.
- [ ] Paths returned by the route are repository-relative, not absolute.
- [ ] Sensitive raw payload fields are not exposed.
- [ ] Existing observability routes remain unchanged.
- [ ] Focused unit tests passed.
- [ ] Focused integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for unrelated pre-existing local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or generated artifact was committed.

## 11. Handoff Notes

After implementation, report back with:

- the final route path and top-level response schema version
- the exact files added and modified
- which aliases are treated as required vs optional/degradable
- how memory-governance cases are derived from `all_registered`
- how the top-level status is derived from section statuses
- the verification commands run and their results
- the commit hash
- the push result
- any follow-up tasks needed for `103-system-integrity-panel-v0` or `104-v2-evidence-contract-guardrail`
