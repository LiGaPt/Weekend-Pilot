# Plan: 041 Internal Benchmark Artifact Panels v0

## 1. Spec Reference

Spec file:

```text
docs/specs/041-internal-benchmark-artifact-panels-v0.md
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

- Current branch is `codex/benchmark-suite-catalog-v0`.
- Latest completed numbered task is `040`.
- Latest commit is `8fb6b8f feat: add benchmark suite catalog`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `040`.
- There is no `041` spec, `041` plan, or `041` branch yet.
- The current branch already contains Task `040` benchmark suite catalog code and tests.
- The internal observability page currently renders real tool-event and action-ledger panels, but still shows placeholders for `Benchmark Artifacts` and `Recovery Path`.
- Benchmark harness already writes per-case report files and suite run reports, and already persists benchmark identity metadata under `agent_runs.metadata_json["benchmark"]`.
- Current focused baseline checks are green:
  - `python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q` passed with `40` tests.
  - `python -m pytest tests/test_observability.py -q` passed with `14` tests.
  - `npm --prefix frontend run test -- --run ObservabilityPage.test.tsx` passed with `6` tests.
- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.
- This task should not add file-reading logic to the internal observability service for benchmark report JSON files.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/benchmark/harness.py` - persist compact benchmark artifact summary into run metadata after case report creation.
- `backend/app/benchmark/suites.py` - add deterministic helper to derive registered suite IDs for a benchmark case ID.
- `backend/app/observability/schemas.py` - add internal benchmark artifact summary models and extend `InternalObservabilityRunSummary`.
- `backend/app/observability/service.py` - parse persisted benchmark metadata into the new internal benchmark artifact summary with graceful fallback.
- `frontend/src/observability/types.ts` - add TypeScript types for the benchmark artifact summary.
- `frontend/src/observability/ObservabilityPage.tsx` - replace the benchmark placeholder with a real benchmark artifact panel and empty-state handling.
- `tests/test_benchmark_suites.py` - add unit coverage for suite-membership derivation.
- `tests/test_observability.py` - add unit coverage for full, partial, and absent benchmark artifact summaries.
- `tests/integration/test_benchmark_harness_gateway.py` - assert benchmark artifact summary persistence in run metadata after a real benchmark run.
- `tests/integration/test_observability_gateway.py` - assert the internal observability API returns benchmark artifact summaries for a real benchmark-backed run.
- `frontend/src/observability/ObservabilityPage.test.tsx` - update the mocked payload and assert the new benchmark artifact panel states.
- `README.md` - document benchmark artifact visibility on `/observability`.
- `docs/WEB_DEMO_README.md` - document benchmark artifact visibility on `/observability`.
- `docs/specs/041-internal-benchmark-artifact-panels-v0.md` - stage with the implementation.
- `docs/plans/041-internal-benchmark-artifact-panels-v0-plan.md` - stage with the implementation.

## 5. Implementation Steps

1. Add a deterministic suite-membership helper in `backend/app/benchmark/suites.py`.
   Create `list_benchmark_suite_ids_for_case(case_id: str) -> list[str]` that returns suite IDs in `_ORDERED_SUITE_IDS` order for suites whose `case_ids` contain the requested case. Unknown case IDs must return `[]`. Reuse existing suite-definition validation. Do not duplicate matrix logic or create a new suite registry.

2. Add backend schema models for the internal benchmark artifact payload.
   In `backend/app/observability/schemas.py`, add:
   - `InternalBenchmarkTaxonomySummary`
   - `InternalBenchmarkScoreSummary`
   - `InternalBenchmarkArtifactSummary`
   - optional `benchmark_artifact_summary` on `InternalObservabilityRunSummary`
   Keep the top-level internal observability schema version unchanged. Use `weekendpilot_internal_benchmark_artifact_v1` as the nested benchmark artifact schema version.

3. Persist benchmark artifact summary in benchmark run metadata after report creation.
   In `backend/app/benchmark/harness.py`, factor the repeated report-writing path so each benchmark case result gets its `report_path` first and then, if `result.run_id` is not `None`, merges a compact `artifact_summary` into `agent_runs.metadata_json["benchmark"]`.
   Persist exactly these fields:
   - `schema_version`
   - `benchmark_status`
   - `overall_score`
   - `workflow_status`
   - `tool_event_count`
   - `action_count`
   - `failure_reasons`
   - `score_summaries`
   - `report_path`
   Build `score_summaries` from `BenchmarkCaseResult.scores` in their current order and include only `name`, `status`, `score`, and `reason`. Do not persist raw `details`. Preserve all existing `metadata_json["benchmark"]` keys.

4. Make artifact-summary persistence best-effort after report writing.
   If the case report has already been written successfully and the additive metadata merge fails, do not replace the benchmark result with a new benchmark error. Return the existing `BenchmarkCaseResult` with `report_path` intact and allow the internal panel to be absent for that run. This protects the benchmark harness output from a UI-only metadata failure.

5. Build the internal benchmark artifact summary in `backend/app/observability/service.py`.
   Add helper logic that reads `metadata["benchmark"]`.
   - If no benchmark block exists, return `None`.
   - If the benchmark block exists, construct a summary with `case_id`, `title`, `workflow_backed`, taxonomy, and `registered_suite_ids`.
   - If `artifact_summary` is present and valid, include `benchmark_status`, `overall_score`, `workflow_status`, `tool_event_count`, `action_count`, `failure_reasons`, `score_summaries`, and `report_path`.
   - If `artifact_summary` is missing or malformed, return a partial summary with the identity fields filled and the scored/report fields set to `null` or empty lists.
   Do not open benchmark report files from `var/benchmarks/`.

6. Add backend unit coverage.
   In `tests/test_benchmark_suites.py`, add assertions for:
   - `family_afternoon_v1 -> ["default", "all_registered"]`
   - `solo_afternoon_v1 -> ["default", "all_registered"]`
   - `family_route_failure_v1 -> ["failures", "all_registered"]`
   - unknown case ID -> `[]`
   In `tests/test_observability.py`, add assertions for:
   - non-benchmark run returns `benchmark_artifact_summary is None`
   - benchmark run with full persisted `artifact_summary` returns the expected internal payload
   - benchmark run with only `metadata["benchmark"]` returns a partial summary instead of failing

7. Add benchmark-harness integration coverage for metadata persistence.
   In `tests/integration/test_benchmark_harness_gateway.py`, after a real benchmark case run, load the persisted `AgentRun` and assert:
   - `metadata_json["benchmark"]["artifact_summary"]` exists
   - the stored `report_path` matches `result.report_path`
   - the stored `benchmark_status` matches `result.status`
   - the stored `overall_score` matches `result.overall_score`
   - the stored `score_summaries` length matches `len(result.scores)`

8. Add internal observability API integration coverage for a real benchmark run.
   In `tests/integration/test_observability_gateway.py`, run one real benchmark case through `BenchmarkHarness.run_case(...)`, then call `GET /internal/runs/{run_id}/observability` and assert:
   - `benchmark_artifact_summary` is present
   - `benchmark_artifact_summary.case_id` matches the benchmark case
   - `benchmark_artifact_summary.registered_suite_ids` matches the Task 040 suite catalog
   - `benchmark_artifact_summary.benchmark_status` matches the benchmark result
   - `benchmark_artifact_summary.report_path` matches the benchmark result report path
   - the serialized payload still does not expose forbidden keys

9. Replace the frontend benchmark placeholder with a real panel.
   In `frontend/src/observability/types.ts`, add the TypeScript equivalents for the new backend models.
   In `frontend/src/observability/ObservabilityPage.tsx`, replace the benchmark placeholder with `BenchmarkArtifactsPanel`.
   The panel must support exactly three states:
   - non-benchmark run
   - benchmark identity only, without persisted scored artifact summary
   - full benchmark artifact summary
   The full panel must render:
   - title and case ID
   - benchmark status and overall score
   - registered suite IDs
   - taxonomy fields
   - report path
   - failure reasons
   - score summary rows
   Keep the recovery placeholder text unchanged.

10. Update frontend tests for the new panel behavior.
    In `frontend/src/observability/ObservabilityPage.test.tsx`, update the mocked summary fixture to include `benchmark_artifact_summary` and assert the panel renders benchmark case data, suite memberships, score summary content, and report path. Add one test where `benchmark_artifact_summary` is `null` and assert the non-benchmark empty state is shown. Keep the recovery placeholder assertion.

11. Update documentation.
    In `README.md` and `docs/WEB_DEMO_README.md`, document that `/observability` now surfaces benchmark artifact context for benchmark-backed runs. Keep the note high-level. Do not add instructions for direct file browsing or new routes.

12. Run verification and stage only task-relevant files.
    Run the focused backend, integration, frontend test, and frontend build commands from section 7. Before staging, confirm that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` artifacts remain unstaged.

## 6. Testing Plan

- Unit tests: `list_benchmark_suite_ids_for_case(...)` returns deterministic memberships for default, failure, and unknown cases.
- Unit tests: `InternalObservabilityService` returns `benchmark_artifact_summary=None` for non-benchmark runs.
- Unit tests: `InternalObservabilityService` returns a full benchmark artifact summary when `metadata["benchmark"]["artifact_summary"]` is present and valid.
- Unit tests: `InternalObservabilityService` returns a partial benchmark artifact summary when `metadata["benchmark"]` exists but `artifact_summary` is missing or invalid.
- Integration tests: a real benchmark harness run persists `metadata_json["benchmark"]["artifact_summary"]` with a matching `report_path`.
- Integration tests: the internal observability API returns benchmark artifact data for a real benchmark-backed run.
- Frontend tests: `/observability` renders the full benchmark artifact panel for a populated benchmark summary.
- Frontend tests: `/observability` renders the non-benchmark empty state when `benchmark_artifact_summary` is `null`.
- Frontend tests: the `Recovery Path` placeholder remains present.
- Smoke tests: frontend build succeeds.
- Smoke tests: `git diff --check` succeeds.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_observability_gateway.py -v
npm --prefix frontend run test -- --run ObservabilityPage.test.tsx
npm --prefix frontend run build
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add internal benchmark artifact panels
```

Expected commands:

```bash
git status --short
git switch -c codex/internal-benchmark-artifact-panels-v0
git add README.md
git add docs/WEB_DEMO_README.md
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/suites.py
git add backend/app/observability/schemas.py
git add backend/app/observability/service.py
git add frontend/src/observability/types.ts
git add frontend/src/observability/ObservabilityPage.tsx
git add frontend/src/observability/ObservabilityPage.test.tsx
git add tests/test_benchmark_suites.py
git add tests/test_observability.py
git add tests/integration/test_benchmark_harness_gateway.py
git add tests/integration/test_observability_gateway.py
git add docs/specs/041-internal-benchmark-artifact-panels-v0.md
git add docs/plans/041-internal-benchmark-artifact-panels-v0-plan.md
git diff --cached --check
git commit -m "feat: add internal benchmark artifact panels"
git push -u origin codex/internal-benchmark-artifact-panels-v0
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not implement the recovery-path panel.
- Do not add benchmark suite report browsing or replay report browsing.
- Do not add case-generation tooling or new benchmark fixtures.
- Do not change benchmark scoring rules, taxonomy values, or suite definitions.
- Do not add a benchmark file-reading path to the internal observability service.
- Do not change the public demo API or the public `/` page.
- Do not add new routes, database tables, Alembic migrations, or dependencies.
- Do not commit generated caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/041-internal-benchmark-artifact-panels-v0.md`.
- [ ] Benchmark-backed runs persist `metadata_json["benchmark"]["artifact_summary"]`.
- [ ] Persisted `artifact_summary.report_path` matches the benchmark harness case report path.
- [ ] The internal observability API returns `benchmark_artifact_summary` for benchmark runs and `null` for non-benchmark runs.
- [ ] `registered_suite_ids` are derived from the Task 040 suite catalog in deterministic order.
- [ ] The `/observability` page renders the benchmark artifact panel instead of the old placeholder.
- [ ] The `/observability` page still keeps the recovery placeholder.
- [ ] The public demo surface remains unchanged.
- [ ] Required backend tests, integration tests, frontend tests, and frontend build passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/` artifact, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The benchmark cases used for verification.
- The final shape of `benchmark_artifact_summary`.
- Whether `registered_suite_ids` matched the expected Task 040 memberships.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files were not staged.
- Any follow-up limitation, especially that benchmark suite browsing, replay browsing, and recovery-path visualization still remain separate future tasks.
