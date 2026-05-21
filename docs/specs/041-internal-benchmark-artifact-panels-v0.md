# Spec: 041 Internal Benchmark Artifact Panels v0

## 1. Goal

Add the first real benchmark-artifact inspection surface to the existing internal observability workflow without changing the customer-facing demo flow.

After this task, a workflow-backed benchmark run should expose a sanitized `benchmark_artifact_summary` through `GET /internal/runs/{run_id}/observability`, and the `/observability` page should render that summary instead of the current benchmark placeholder copy. Reviewers should be able to see the benchmark case identity, taxonomy, suite membership derived from the Task 040 suite catalog, benchmark status, overall score, score breakdown, failure reasons, and the persisted case report path. Non-benchmark runs must continue to work and should render a clear empty state.

This task is intentionally a convergence task, not a new scenario-expansion or case-generation task. The repository already generates benchmark reports and benchmark structure artifacts. The missing piece is making those existing artifacts directly reviewable through the internal observability surface.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. `docs/NEXT_PHASE_ROADMAP.md` says the current phase should prioritize `M1. 评测与观测基础设施` before larger UX or capability expansion.

The repository has already completed the main infrastructure chain that makes this possible:

- Task `033` added workflow stage timing and benchmark percentile summaries.
- Task `034` added the internal observability API and `/observability` page skeleton.
- Task `035` removed internal observability/debug fields from the public demo surface.
- Task `036` aligned run, trace, and benchmark summary envelopes.
- Task `037` replaced the tool-event and action-ledger placeholders with real internal panels, but explicitly left the benchmark-artifacts and recovery-path panels as placeholders.
- Task `038` added the first non-family benchmark scenario.
- Task `039` added typed benchmark taxonomy and suite matrix summaries.
- Task `040` added the canonical named benchmark suite catalog.

That means the repository is already ahead of the roadmap in raw benchmark structure, but the internal observability surface still does not expose benchmark artifact details. The next smallest useful step is therefore not broader case generation yet. The next smallest useful step is to surface the benchmark artifacts that already exist, so internal reviewers can actually consume the current benchmark infrastructure.

This task corresponds to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施` as a convergence follow-up that also leverages the M3 benchmark structure work from Tasks `038`-`040`.

## 3. Requirements

- Add an additive `benchmark_artifact_summary` field to the internal observability backend contract and the frontend internal observability view model.
- `benchmark_artifact_summary` must be `null` for non-benchmark runs.
- Add a typed `InternalBenchmarkArtifactSummary` contract.
- Add a typed `InternalBenchmarkTaxonomySummary` contract.
- Add a typed `InternalBenchmarkScoreSummary` contract.
- `InternalBenchmarkArtifactSummary` must include:
  - `schema_version`
  - `case_id`
  - `title`
  - `workflow_backed`
  - `registered_suite_ids`
  - `taxonomy`
  - `benchmark_status`
  - `overall_score`
  - `workflow_status`
  - `tool_event_count`
  - `action_count`
  - `failure_reasons`
  - `score_summaries`
  - `report_path`
- `InternalBenchmarkTaxonomySummary` must include:
  - `suite`
  - `scenario_bucket`
  - `level`
  - `tags`
  - `failure_mode`
- Each `score_summaries` entry must include only:
  - `name`
  - `status`
  - `score`
  - `reason`
- `score_summaries` must preserve the original `BenchmarkCaseResult.scores` ordering from the benchmark harness.
- Persist additive benchmark artifact metadata under:

  ```text
  agent_runs.metadata_json["benchmark"]["artifact_summary"]
  ```

- Persisted `artifact_summary` must be written only after the case report path is known, so the stored `report_path` matches the report path returned by the benchmark harness.
- Persisted `artifact_summary` must include:
  - `schema_version`
  - `benchmark_status`
  - `overall_score`
  - `workflow_status`
  - `tool_event_count`
  - `action_count`
  - `failure_reasons`
  - `score_summaries`
  - `report_path`
- Existing `agent_runs.metadata_json["benchmark"]` fields from earlier tasks must remain intact:
  - `case_id`
  - `title`
  - `failure_profile`
  - `failure_profile_metadata`
  - `benchmark_harness_version`
  - `harness_version`
  - `taxonomy`
  - `metadata`
  - `workflow_backed`
- The internal observability service must build `benchmark_artifact_summary` from persisted database metadata only.
- The internal observability service must not read benchmark report JSON files from disk.
- If `agent_runs.metadata_json["benchmark"]` exists but `artifact_summary` is missing or malformed, the internal observability service must return a partial benchmark summary using existing persisted benchmark identity and taxonomy fields instead of failing the route.
- Add deterministic helper logic that derives `registered_suite_ids` from the Task 040 suite catalog.
- `registered_suite_ids` must follow the Task 040 suite order:
  - `default`
  - `failures`
  - `all_registered`
- For the current catalog:
  - `family_afternoon_v1`, `family_indoor_light_meal_v1`, `family_outdoor_quick_dinner_v1`, `family_memory_override_v1`, `family_citywalk_addon_v1`, and `solo_afternoon_v1` must map to `["default", "all_registered"]`
  - `family_route_failure_v1` must map to `["failures", "all_registered"]`
- The existing `GET /internal/runs/{run_id}/observability` endpoint must remain the only backend route used for this task.
- The existing internal observability response must remain additive; no existing fields may be removed or renamed.
- The `/observability` page must replace the `Benchmark Artifacts` placeholder with a real benchmark artifact panel.
- The benchmark artifact panel must render:
  - case identity
  - taxonomy
  - registered suite IDs
  - benchmark status
  - overall score
  - report path
  - failure reasons
  - score summaries
- The benchmark artifact panel must show a reviewer-readable empty state for non-benchmark runs.
- The benchmark artifact panel must show a reviewer-readable partial state when benchmark identity exists but no persisted artifact summary exists yet.
- The `Recovery Path` panel must remain a placeholder in this task.
- The public `/` page and the public `/demo/runs*` API contract must remain unchanged.
- Update `README.md` and `docs/WEB_DEMO_README.md` to mention benchmark artifact availability on the internal observability page.
- Do not add new benchmark cases, new suite definitions, new routes, new frontend pages beyond the existing `/observability` page, new database tables, new Alembic migrations, or new dependencies.

## 4. Non-goals

- Do not implement the recovery-path panel in this task.
- Do not implement benchmark suite report browsing or a suite report index.
- Do not implement replay artifact browsing or replay linkage in the UI.
- Do not add case-generation tooling, case templates, or prompt-driven benchmark synthesis.
- Do not change benchmark scoring rules, taxonomy values, or Task 040 suite definitions.
- Do not change public demo API contracts or the customer-facing `/` page.
- Do not parse benchmark report JSON files from the internal observability service.
- Do not add authentication, RBAC, admin login, or internal-user management.
- Do not commit `.env`, API keys, tokens, secrets, generated runtime artifacts, or unrelated untracked files.

## 5. Interfaces and Contracts

### Inputs

This task depends on the existing benchmark and observability infrastructure:

- `agent_runs.metadata_json["benchmark"]`
- `BenchmarkHarness.run_case(case)`
- `BenchmarkCaseResult`
- Task 039 `taxonomy`
- Task 040 named suite catalog
- existing `GET /internal/runs/{run_id}/observability`
- existing `/observability` frontend page

### Outputs

Additive persisted metadata:

```text
agent_runs.metadata_json["benchmark"]["artifact_summary"]
```

Additive internal API field:

```text
benchmark_artifact_summary
```

Updated internal frontend panel:

```text
/observability -> Benchmark Artifacts panel
```

### Schemas

The internal observability response should add this fragment:

```json
{
  "benchmark_artifact_summary": {
    "schema_version": "weekendpilot_internal_benchmark_artifact_v1",
    "case_id": "solo_afternoon_v1",
    "title": "Solo afternoon local-life plan",
    "workflow_backed": true,
    "registered_suite_ids": [
      "default",
      "all_registered"
    ],
    "taxonomy": {
      "suite": "locallife_bench_v1",
      "scenario_bucket": "solo",
      "level": "L1",
      "tags": [
        "baseline",
        "light_activity",
        "light_meal"
      ],
      "failure_mode": null
    },
    "benchmark_status": "passed",
    "overall_score": 0.9583,
    "workflow_status": "completed",
    "tool_event_count": 8,
    "action_count": 1,
    "failure_reasons": [],
    "score_summaries": [
      {
        "name": "workflow_path",
        "status": "passed",
        "score": 1.0,
        "reason": "Workflow reached the expected path."
      },
      {
        "name": "trajectory",
        "status": "passed",
        "score": 1.0,
        "reason": "Required benchmark tools were used."
      }
    ],
    "report_path": "var/benchmarks/solo_afternoon_v1.json"
  }
}
```

The persisted benchmark metadata should include this additive fragment:

```json
{
  "benchmark": {
    "case_id": "solo_afternoon_v1",
    "title": "Solo afternoon local-life plan",
    "workflow_backed": true,
    "taxonomy": {
      "suite": "locallife_bench_v1",
      "scenario_bucket": "solo",
      "level": "L1",
      "tags": [
        "baseline",
        "light_activity",
        "light_meal"
      ],
      "failure_mode": null
    },
    "artifact_summary": {
      "schema_version": "weekendpilot_benchmark_artifact_summary_v1",
      "benchmark_status": "passed",
      "overall_score": 0.9583,
      "workflow_status": "completed",
      "tool_event_count": 8,
      "action_count": 1,
      "failure_reasons": [],
      "score_summaries": [
        {
          "name": "workflow_path",
          "status": "passed",
          "score": 1.0,
          "reason": "Workflow reached the expected path."
        }
      ],
      "report_path": "var/benchmarks/solo_afternoon_v1.json"
    }
  }
}
```

Notes:

- `benchmark_artifact_summary` is optional and may be `null`.
- `taxonomy` inside `benchmark_artifact_summary` may be `null` only for malformed older metadata; the route should not fail because of that.
- `report_path` must stay a repository-local path string. This task does not add file browsing or file reading through the API.
- The top-level internal observability response may remain `weekendpilot_internal_observability_run_v1` because the change is additive.

## 6. Observability

This task extends the internal observability surface and benchmark metadata persistence only.

It must add:

- persisted benchmark artifact summary under `agent_runs.metadata_json["benchmark"]["artifact_summary"]`
- one additive `benchmark_artifact_summary` field on the internal observability API response
- one real benchmark artifact panel on `/observability`

It must keep all new data sanitized and must not expose:

- secrets
- API keys
- tokens
- authorization headers
- raw prompt content
- raw benchmark report JSON bodies
- raw `score.details` payloads
- raw tool request/response bodies
- raw action request/response bodies
- internal row IDs

The internal API may expose the relative benchmark `report_path` string only. It must not expose raw file contents in this task.

## 7. Failure Handling

- If the run is not benchmark-backed, `benchmark_artifact_summary` must be `null` and the frontend must show a non-benchmark empty state.
- If benchmark identity metadata exists but `artifact_summary` is missing or malformed, the service must return a partial benchmark summary instead of failing the route.
- If a benchmark `case_id` is not present in the current suite catalog, `registered_suite_ids` must be an empty list rather than an error.
- If additive benchmark artifact metadata cannot be persisted after a case report is already written, the benchmark harness must still return the benchmark result and report path; the internal benchmark artifact panel may simply be absent for that run.
- If the frontend receives `benchmark_artifact_summary: null`, it must not render an error state.
- This task does not need to recover or display suite run reports, replay reports, or recovery-path traces.

## 8. Acceptance Criteria

- [ ] `docs/specs/041-internal-benchmark-artifact-panels-v0.md` exists and matches this task.
- [ ] Workflow-backed benchmark runs persist additive `agent_runs.metadata_json["benchmark"]["artifact_summary"]`.
- [ ] Persisted `artifact_summary.report_path` matches the case report path returned by the benchmark harness.
- [ ] `GET /internal/runs/{run_id}/observability` returns `benchmark_artifact_summary` for benchmark-backed runs.
- [ ] `GET /internal/runs/{run_id}/observability` returns `benchmark_artifact_summary: null` for non-benchmark runs.
- [ ] Benchmark artifact summaries include case identity, taxonomy, registered suite IDs, benchmark status, overall score, failure reasons, score summaries, and report path.
- [ ] `registered_suite_ids` are derived from the Task 040 suite catalog in deterministic order.
- [ ] `solo_afternoon_v1` resolves to `["default", "all_registered"]`.
- [ ] `family_route_failure_v1` resolves to `["failures", "all_registered"]`.
- [ ] The internal observability service does not add a benchmark report file-reading path.
- [ ] The `/observability` page renders a real benchmark artifact panel instead of the previous placeholder.
- [ ] The benchmark artifact panel renders a non-benchmark empty state without failing the page.
- [ ] The benchmark artifact panel renders a partial benchmark state when identity metadata exists but scored artifact data does not.
- [ ] The `Recovery Path` panel remains a placeholder.
- [ ] The public `/` page and public `/demo/runs*` contracts remain unchanged.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` mention benchmark artifact visibility on `/observability`.
- [ ] No new benchmark case, new suite definition, new route, migration, or dependency is added.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated untracked file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: add internal benchmark artifact panels
```

## 11. Notes for the Implementer

Keep this task narrow.

The safest implementation path is:

1. reuse the Task 040 suite catalog for deterministic suite membership,
2. persist a compact benchmark artifact summary only after the case report path exists,
3. expose that compact summary through the existing internal observability route,
4. replace only the benchmark placeholder panel in the frontend,
5. leave the recovery-path placeholder alone.

Do not widen this task into a benchmark browser, replay UI, recovery visualization, or case-generation tooling. If older benchmark runs only have partial persisted metadata, degrade gracefully instead of adding file parsing or migrations.
