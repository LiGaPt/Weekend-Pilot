# Spec: 042 Internal Recovery Path Visualization v0

## 1. Goal

Add the first real recovery-path inspection surface to the existing internal observability workflow without changing the customer-facing demo flow or the underlying recovery-routing behavior.

After this task, a run that used bounded recovery routing should expose a sanitized `recovery_path_summary` through `GET /internal/runs/{run_id}/observability`, and the `/observability` page should render that summary instead of the current `Recovery Path` placeholder copy. Reviewers should be able to see recovery attempt count, retry-budget consumption, route targets, recovery actions, failure reasons, and, for benchmark-backed recovery runs, the persisted benchmark case report path that can later be used as replay input by existing replay tooling. Runs that never entered recovery must continue to work and should render a clear empty state.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven, observable by default, and explicit about bounded recovery behavior. It also requires recovery decisions to remain traceable and benchmark-compatible.

The repository already has the main infrastructure chain needed for this task:

- Task `027` added bounded recovery routing and persisted sanitized recovery metadata under `agent_runs.metadata_json["workflow"]["recovery"]`.
- Task `030` added the benchmark replay harness and replay report contracts.
- Task `034` added `GET /internal/runs/{run_id}/observability` and the `/observability` page skeleton.
- Task `037` replaced the tool-event and action-ledger placeholders with real internal panels.
- Task `041` replaced the benchmark-artifacts placeholder with a real benchmark artifact panel and surfaced persisted benchmark case report paths.

That means the internal observability page is one panel away from being structurally complete for current review workflows. This task corresponds primarily to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施` because it makes recovery behavior inspectable and comparable across failure cases. It also closes the last missing internal-review panel expected by `M2. 前端分离`, and it intentionally takes only the smallest slice of roadmap item `9. 恢复路径可视化与 replay 联动`.

## 3. Requirements

- Add an additive `recovery_path_summary` field to the internal observability backend contract and the frontend internal observability view model.
- `recovery_path_summary` must be `null` when `agent_runs.metadata_json["workflow"]["recovery"]` is absent.
- Add a typed `InternalRecoveryAttemptSummary` contract.
- Add a typed `InternalRecoveryReplaySourceSummary` contract.
- Add a typed `InternalRecoveryPathSummary` contract.
- `InternalRecoveryAttemptSummary` must include:
  - `attempt_index`
  - `source_node`
  - `recovery_action`
  - `route_to`
  - `error_type`
  - `reason`
  - `retry_budget_before`
  - `retry_budget_after`
  - `status`
- `InternalRecoveryReplaySourceSummary` must include:
  - `case_id`
  - `benchmark_report_path`
- `InternalRecoveryPathSummary` must include:
  - `schema_version`
  - `attempt_count`
  - `max_attempts`
  - `attempts`
  - `replay_source`
- `recovery_path_summary.attempt_count` returned by the internal API must equal the number of returned `attempts`.
- `recovery_path_summary.max_attempts` must be a non-negative integer. If stored metadata is missing or invalid, the service must set `max_attempts` to `attempt_count`.
- `replay_source` must be `null` unless both of these persisted values are available:
  - benchmark `case_id`
  - benchmark case `report_path`
- The internal observability service must build `recovery_path_summary` from persisted database metadata only.
- The internal observability service must not read benchmark case report JSON files from disk.
- The internal observability service must not read replay report JSON files from disk.
- If `agent_runs.metadata_json["workflow"]["recovery"]` exists but contains malformed attempts, the service must skip invalid attempts and return the remaining valid attempts instead of failing the route.
- If `agent_runs.metadata_json["workflow"]["recovery"]` exists but no valid attempts remain after validation, the service must still return a non-null `recovery_path_summary` with `attempt_count: 0`.
- The existing `GET /internal/runs/{run_id}/observability` endpoint must remain the only backend route used for this task.
- The existing internal observability response must remain additive; no existing fields may be removed or renamed.
- The `/observability` page must replace the `Recovery Path` placeholder with a real recovery-path panel.
- The recovery-path panel must render:
  - attempt count
  - max attempts
  - per-attempt action
  - per-attempt status
  - per-attempt route target
  - per-attempt error type
  - per-attempt reason
  - per-attempt retry budget before and after
- If `replay_source` is present, the recovery-path panel must render:
  - benchmark case ID
  - benchmark case report path
- The recovery-path panel must show a reviewer-readable empty state for runs that never entered recovery.
- The recovery-path panel must show a reviewer-readable partial state when recovery metadata exists but yields zero valid attempts after sanitization.
- The existing `Benchmark Artifacts` panel must remain unchanged in this task.
- The public `/` page and the public `/demo/runs*` API contract must remain unchanged.
- Update `README.md` and `docs/WEB_DEMO_README.md` to mention recovery-path visibility on the internal observability page.
- Do not add new benchmark cases, new suite definitions, new routes, new frontend pages beyond the existing `/observability` page, new database tables, new Alembic migrations, or new dependencies.

## 4. Non-goals

- Do not change recovery-routing behavior, retry-budget logic, or workflow topology.
- Do not add replay execution, replay triggering, replay report browsing, or replay artifact parsing.
- Do not add benchmark suite browsing, benchmark reruns, or recovery-path export features.
- Do not add new benchmark cases, new failure profiles, or new benchmark graders.
- Do not change the benchmark artifact panel, benchmark score summaries, or Task `041` benchmark contracts.
- Do not change public demo API contracts or the customer-facing `/` page.
- Do not add authentication, RBAC, admin login, or internal-user management.
- Do not commit `.env`, API keys, tokens, secrets, generated runtime artifacts, or unrelated untracked files.

## 5. Interfaces and Contracts

### Inputs

This task depends on the existing persisted runtime and benchmark metadata:

- `agent_runs.metadata_json["workflow"]["recovery"]`
- `agent_runs.metadata_json["benchmark"]["case_id"]`
- `agent_runs.metadata_json["benchmark"]["artifact_summary"]["report_path"]`
- existing `GET /internal/runs/{run_id}/observability`
- existing `/observability` frontend page

### Outputs

Additive internal API field:

```text
recovery_path_summary
```

Updated internal frontend panel:

```text
/observability -> Recovery Path panel
```

### Schemas

The internal observability response should add this fragment:

```json
{
  "recovery_path_summary": {
    "schema_version": "weekendpilot_internal_recovery_path_v1",
    "attempt_count": 1,
    "max_attempts": 1,
    "attempts": [
      {
        "attempt_index": 1,
        "source_node": "semantic_validator",
        "recovery_action": "stop_safely",
        "route_to": null,
        "error_type": "route_infeasible",
        "reason": "Recovery stopped after route failure.",
        "retry_budget_before": 0,
        "retry_budget_after": 0,
        "status": "stopped"
      }
    ],
    "replay_source": {
      "case_id": "family_route_failure_v1",
      "benchmark_report_path": "var/benchmarks/family_route_failure_v1.json"
    }
  }
}
```

Notes:

- `recovery_path_summary` is optional and may be `null`.
- `replay_source` is optional and may be `null`.
- `benchmark_report_path` must stay a repository-local path string. This task does not add file browsing or file reading through the API.
- The top-level internal observability response may remain `weekendpilot_internal_observability_run_v1` because the change is additive.

## 6. Observability

This task extends the internal observability surface only.

It must add:

- one additive `recovery_path_summary` field on the internal observability API response
- one real recovery-path panel on `/observability`

It must keep all new data sanitized and must not expose:

- secrets
- API keys
- tokens
- authorization headers
- raw prompts
- raw benchmark report JSON bodies
- raw replay report JSON bodies
- raw tool request or response bodies
- raw action request or response bodies
- internal row IDs
- tool event IDs
- action IDs
- tracebacks

The internal API may expose the relative benchmark `report_path` string only as a replay input hint. It must not expose raw file contents in this task.

## 7. Failure Handling

- If the run never entered recovery, `recovery_path_summary` must be `null` and the frontend must show a non-recovery empty state.
- If recovery metadata exists but some attempts are malformed, the service must skip the malformed attempts instead of failing the route.
- If recovery metadata exists but no valid attempts remain after sanitization, the service must return a non-null summary with `attempt_count: 0` and the frontend must show a partial-state message.
- If benchmark metadata is missing, or if benchmark `artifact_summary.report_path` is missing, `replay_source` must be `null` rather than an error.
- If a benchmark `report_path` exists but `case_id` is missing or malformed, `replay_source` must be `null`.
- The service must not attempt to read report files to repair missing replay linkage.
- If the frontend receives `recovery_path_summary: null`, it must not render an error state.
- This task does not need to display replay mismatch details, replay report status, benchmark rerun status, or benchmark suite results.

## 8. Acceptance Criteria

- [ ] `docs/specs/042-internal-recovery-path-visualization-v0.md` exists and matches this task.
- [ ] `docs/plans/042-internal-recovery-path-visualization-v0-plan.md` exists and matches this task.
- [ ] `GET /internal/runs/{run_id}/observability` returns `recovery_path_summary` for runs with persisted recovery metadata.
- [ ] `GET /internal/runs/{run_id}/observability` returns `recovery_path_summary: null` for runs that never entered recovery.
- [ ] Returned recovery attempts preserve the persisted attempt ordering.
- [ ] Returned `attempt_count` equals the number of returned attempts.
- [ ] Returned `max_attempts` is always non-negative.
- [ ] Malformed recovery attempts are skipped without failing the internal observability route.
- [ ] Benchmark-backed recovery runs expose a replay input hint only when both `case_id` and benchmark `report_path` are already persisted.
- [ ] The internal observability service does not add any benchmark or replay file-reading path.
- [ ] The `/observability` page renders a real recovery-path panel instead of the previous placeholder.
- [ ] The recovery-path panel renders a non-recovery empty state without failing the page.
- [ ] The recovery-path panel renders a partial state when recovery metadata exists but yields zero valid attempts.
- [ ] The existing benchmark artifact panel remains unchanged.
- [ ] The public `/` page and public `/demo/runs*` contracts remain unchanged.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` mention recovery-path visibility on `/observability`.
- [ ] No new route, migration, dependency, benchmark case, or replay-execution feature is added.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated untracked file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/test_langgraph_workflow.py tests/test_benchmark_replay.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_observability_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add internal recovery path visualization
```

## 11. Notes for the Implementer

Keep this task narrow.

The safest implementation path is:

1. reuse the existing persisted `workflow.recovery` metadata,
2. expose it through the existing internal observability route,
3. render it on the existing `/observability` page,
4. surface the persisted benchmark case report path only as a replay input hint,
5. leave replay execution, replay browsing, and workflow behavior unchanged.

Do not widen this task into replay orchestration, report browsing, benchmark reruns, or session-model work. If older runs have missing or malformed recovery metadata, degrade gracefully instead of adding file parsing, migrations, or workflow rewrites.
