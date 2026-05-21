# Plan: 042 Internal Recovery Path Visualization v0

## 1. Spec Reference

Spec file:

```text
docs/specs/042-internal-recovery-path-visualization-v0.md
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

- Current branch is `codex/internal-benchmark-artifact-panels-v0`.
- Latest completed numbered task is `041`.
- Latest commit is `b63cc6f feat: add internal benchmark artifact panels`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `041`.
- There is no `042` spec, `042` plan, or `codex/*042*` branch yet.
- The internal observability page currently renders real panels for:
  - run overview
  - workflow timing
  - node history
  - agent roles
  - observability summary
  - tool events
  - action ledger
  - benchmark artifacts
- The internal observability page still renders `Recovery Path` as a placeholder.
- Workflow recovery metadata is already persisted under `agent_runs.metadata_json["workflow"]["recovery"]`.
- Benchmark-backed runs already persist benchmark case report paths under `agent_runs.metadata_json["benchmark"]["artifact_summary"]["report_path"]`.
- The replay harness already accepts benchmark case report paths as replay input, but the current internal observability route does not surface recovery-path review data yet.
- This task must not add any report-file reading path or replay-execution path to the internal observability service.
- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/observability/schemas.py` - add recovery-path summary models and extend `InternalObservabilityRunSummary`.
- `backend/app/observability/service.py` - build a sanitized recovery-path summary from persisted workflow and benchmark metadata.
- `frontend/src/observability/types.ts` - add TypeScript types for the recovery-path summary.
- `frontend/src/observability/ObservabilityPage.tsx` - replace the recovery placeholder with a real recovery-path panel.
- `frontend/src/observability/ObservabilityPage.test.tsx` - update mocked payloads and add panel-state assertions.
- `frontend/src/observability/api.test.ts` - widen the internal observability fixture shape.
- `tests/test_observability.py` - add backend unit coverage for recovery-path summaries.
- `tests/integration/test_observability_gateway.py` - add route coverage for recovery-path summaries on benchmark-backed recovery runs.
- `README.md` - document recovery-path visibility on `/observability`.
- `docs/WEB_DEMO_README.md` - document recovery-path visibility on `/observability`.

## 5. Implementation Steps

1. Extend the backend internal observability schema.
   Add:
   - `InternalRecoveryAttemptSummary`
   - `InternalRecoveryReplaySourceSummary`
   - `InternalRecoveryPathSummary`
   - optional `recovery_path_summary` on `InternalObservabilityRunSummary`
   Keep the top-level internal observability schema version unchanged. Use `weekendpilot_internal_recovery_path_v1` as the nested recovery schema version.

2. Implement backend recovery-path summary parsing in `backend/app/observability/service.py`.
   Add a helper that:
   - reads `metadata["workflow"]["recovery"]`
   - returns `None` when the recovery block is absent
   - validates each stored recovery attempt in order
   - skips malformed attempts instead of raising
   - sets returned `attempt_count` to `len(valid_attempts)`
   - sets returned `max_attempts` to a non-negative integer, defaulting to `attempt_count` when missing or invalid
   - builds optional `replay_source` only when both persisted benchmark `case_id` and persisted benchmark `artifact_summary.report_path` are present
   - never reads report files from disk

3. Keep the recovery summary fully additive.
   Do not remove or rename any existing field on `InternalObservabilityRunSummary`.
   Do not change benchmark artifact parsing.
   Do not introduce new routes.
   The only backend API surface change in this task is the additive `recovery_path_summary` field.

4. Add backend unit tests in `tests/test_observability.py`.
   Cover at least these cases:
   - run with no recovery metadata returns `recovery_path_summary is None`
   - run with valid recovery metadata returns a populated summary
   - run with malformed recovery attempts returns a non-null summary with only valid attempts
   - benchmark-backed recovery run exposes `replay_source` when persisted benchmark `case_id` and `report_path` are both present

5. Add integration coverage in `tests/integration/test_observability_gateway.py`.
   Create a real benchmark-backed recovery run using `BenchmarkHarness.run_case(load_benchmark_case("family_route_failure_v1"))`, then call `GET /internal/runs/{run_id}/observability` and assert:
   - `recovery_path_summary` is present
   - `attempt_count` is `1`
   - the first attempt has `recovery_action == "stop_safely"`
   - the first attempt has `status == "stopped"`
   - `replay_source.case_id == "family_route_failure_v1"`
   - `replay_source.benchmark_report_path == result.report_path`
   - no forbidden keys leak into the response payload

6. Update frontend types and the internal observability page.
   In `frontend/src/observability/types.ts`, add TypeScript equivalents for the new backend models.
   In `frontend/src/observability/ObservabilityPage.tsx`, replace the placeholder with `RecoveryPathPanel`.
   The panel must support exactly three states:
   - no recovery metadata
   - recovery metadata present but zero valid attempts
   - populated recovery summary
   The populated panel must render:
   - attempt count and max attempts
   - each attempt’s action, status, route, error type, reason, retry budget before, and retry budget after
   - replay source case ID and benchmark report path when `replay_source` is present
   Keep the benchmark artifact panel unchanged.

7. Update frontend tests.
   In `frontend/src/observability/ObservabilityPage.test.tsx`, add assertions for:
   - the non-recovery empty state
   - the zero-valid-attempt partial state
   - a populated recovery summary
   - a benchmark-backed replay source hint
   In `frontend/src/observability/api.test.ts`, widen the mocked summary shape with `recovery_path_summary: null` so the API client fixture still compiles against the widened response.

8. Update documentation.
   In `README.md` and `docs/WEB_DEMO_README.md`, add a short note that `/observability` now surfaces recovery-path review data for runs that entered bounded recovery. Mention that the benchmark report path is shown only as replay input context; replay execution itself remains separate tooling.

9. Run verification and stage only task-relevant files.
   Run the focused backend, integration, frontend test, and frontend build commands from section 7.
   Before staging, confirm that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` artifacts remain unstaged.

## 6. Testing Plan

- Unit tests: internal observability returns `recovery_path_summary=None` when no recovery metadata exists.
- Unit tests: internal observability returns a populated recovery-path summary for valid persisted recovery metadata.
- Unit tests: malformed recovery attempts are skipped without failing the service.
- Unit tests: benchmark-backed recovery metadata exposes `replay_source` only when both persisted `case_id` and persisted benchmark `report_path` exist.
- Integration tests: a real `family_route_failure_v1` benchmark run returns a populated `recovery_path_summary` through the internal observability route.
- Frontend tests: `/observability` renders the no-recovery empty state.
- Frontend tests: `/observability` renders the zero-valid-attempt partial state.
- Frontend tests: `/observability` renders a populated recovery-path summary and replay source hint.
- Frontend tests: the benchmark artifact panel remains unchanged.
- Smoke tests: frontend build succeeds.
- Smoke tests: `git diff --check` succeeds.

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add internal recovery path visualization
```

Expected commands:

```bash
git status --short
git switch -c codex/internal-recovery-path-visualization-v0
git add README.md
git add docs/WEB_DEMO_README.md
git add backend/app/observability/schemas.py
git add backend/app/observability/service.py
git add frontend/src/observability/types.ts
git add frontend/src/observability/ObservabilityPage.tsx
git add frontend/src/observability/ObservabilityPage.test.tsx
git add frontend/src/observability/api.test.ts
git add tests/test_observability.py
git add tests/integration/test_observability_gateway.py
git add docs/specs/042-internal-recovery-path-visualization-v0.md
git add docs/plans/042-internal-recovery-path-visualization-v0-plan.md
git diff --cached --check
git commit -m "feat: add internal recovery path visualization"
git push -u origin codex/internal-recovery-path-visualization-v0
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not change recovery-routing logic, retry-budget handling, or workflow graph topology.
- Do not add replay execution, replay browsing, replay file parsing, or replay rerun APIs.
- Do not modify benchmark artifact contracts or benchmark scoring.
- Do not add new benchmark cases, new suites, or new failure profiles.
- Do not change the public demo API or the public `/` page.
- Do not add new routes, database tables, Alembic migrations, or dependencies.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `frontend/dist/`, `.env`, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/042-internal-recovery-path-visualization-v0.md`.
- [ ] Runs with no recovery metadata return `recovery_path_summary: null`.
- [ ] Runs with recovery metadata return a populated or partial `recovery_path_summary` instead of failing the route.
- [ ] Returned `attempt_count` equals the number of returned attempts.
- [ ] Returned `max_attempts` is non-negative.
- [ ] Benchmark-backed recovery runs expose a replay input hint only from persisted metadata.
- [ ] The internal observability service does not read benchmark or replay report files from disk.
- [ ] The `/observability` page renders the recovery panel instead of the old placeholder.
- [ ] The benchmark artifact panel remains unchanged.
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
- The final shape of `recovery_path_summary`.
- The recovery cases used for verification.
- Whether `family_route_failure_v1` exposed the expected replay source hint.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files were not staged.
- Any follow-up limitation, especially that replay execution, replay browsing, and broader session-model work remain separate future tasks.
