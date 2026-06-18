# Spec: 118 Recovery Replay Visualization v0

## 1. Goal

This task closes the smallest remaining gap between recovery replay evidence and the internal run visualization. The repository already has:

- bounded recovery-path visualization on `GET /internal/runs/{run_id}/observability`
- generic recovery replay review artifacts under `var/recovery-reviews/`
- reviewer-facing internal observability UI on `5174`

What is still missing is direct linkage. A reviewer can see that a run entered recovery, and can separately inspect replay review artifacts on disk, but the run visualization does not yet tell them which replay review artifact matches the current run, whether the latest alias is still aligned to the run’s benchmark report, or where the replay report lives.

After this task, a recovery-backed benchmark run loaded on `5174` must expose a reviewer-safe replay-link summary that points from the current run visualization to the matching latest recovery review alias, the concrete review artifact path, and the replay report path. The goal is faster and safer auditability: reviewers should be able to inspect a recovery branch from one place without manually stitching together paths.

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in these areas:

- Observability by default
- Failure handling and recovery auditability
- Harness / replay engineering
- LocalLife-Bench reviewer evidence

In `docs/NEXT_PHASE_ROADMAP.md`, the default strategic emphasis is still benchmark completeness, observability, recovery auditability, and memory-governance closure. Within that priority order, this task belongs to milestone `M5` and specifically matches the recommended direction around recovery-path visualization and replay linkage.

Relevant completed dependencies already exist:

- Task `042` added `recovery_path_summary`
- Task `067` added canonical recovery replay review closure
- Task `099` generalized recovery replay review
- Task `114` added structured run summary
- Task `115` split customer and observability surfaces
- Task `117` completed benchmark case matrix generation

That makes this the next smallest useful closure task before starting a broader memory CRUD follow-up. It reuses finished M1 observability foundations and finished recovery review artifacts instead of widening into new workflow, benchmark, or provider behavior.

## 3. Requirements

- Keep the existing route `GET /internal/runs/{run_id}/observability`.
- Keep the existing top-level response schema additive and backward compatible.
- Keep the existing `recovery_path_summary` and `run_summary` fields in place.

- Add one additive recovery replay linkage field to the internal observability response.
- The new field must be named `recovery_replay_link_summary`.
- `recovery_replay_link_summary` must be `null` when the current run does not have both:
  - a recovery path summary
  - a benchmark case id suitable for recovery replay linkage

- Add a typed backend/frontend contract for the new linkage summary.
- The linkage summary must include:
  - `status`
  - `case_id`
  - `source_report_path`
  - `latest_review_path`
  - `review_artifact_path`
  - `replay_report_path`
  - `review_status`
  - `check_count`
  - `passed_check_count`
  - `failed_check_count`
  - `mismatch_reason`

- `status` must use these values only:
  - `matched`
  - `missing`
  - `invalid`
  - `mismatch`

- The internal observability service must derive the new linkage summary by reading only the latest recovery review alias path for the current case:
  - `var/recovery-reviews/latest-<case_id>-review.json`
- The service must not scan arbitrary recovery review directories.
- The service must not read benchmark report JSON bodies.
- The service must not read replay report JSON bodies.
- The service must validate the latest review alias payload with the existing recovery review schema before exposing matched fields.

- Matching must require both:
  - recovery review `case_id == current benchmark case_id`
  - recovery review `source_report_path == current benchmark artifact report_path`

- If the latest review alias file does not exist:
  - `recovery_replay_link_summary.status` must be `missing`
  - `latest_review_path` must still be returned
  - all artifact-derived fields may be `null`
  - the API request must still return `200`

- If the latest review alias file exists but fails schema validation or JSON parsing:
  - `recovery_replay_link_summary.status` must be `invalid`
  - `latest_review_path` must be returned
  - `mismatch_reason` must explain that the alias payload is unreadable or invalid
  - the API request must still return `200`

- If the latest review alias file is readable but does not match the current run:
  - `recovery_replay_link_summary.status` must be `mismatch`
  - `latest_review_path` must be returned
  - `mismatch_reason` must explain which invariant failed
  - `review_artifact_path`, `replay_report_path`, and counts may still be returned if present in the alias payload
  - the API request must still return `200`

- If the latest review alias file matches the current run:
  - `recovery_replay_link_summary.status` must be `matched`
  - `review_artifact_path` must point at the concrete `recovery-review.json` artifact for that review
  - `replay_report_path` must be returned from the review payload
  - `review_status` must reflect the recovery review status
  - `check_count`, `passed_check_count`, and `failed_check_count` must be populated from the review checks

- The service must compute `review_artifact_path` deterministically from `run_directory`:
  - `review_artifact_path = <run_directory>/recovery-review.json`
- The service must not assume the alias payload already stores `review_artifact_path`.

- The `5174` page must render a new reviewer-facing section inside or immediately adjacent to the existing `Recovery Visualization` panel.
- The new UI block must show:
  - latest review alias path
  - source report path
  - replay report path
  - review artifact path
  - link status
  - review status
  - passed/failed check counts
  - mismatch or invalid reason when present

- The UI must provide copy buttons for each available path.
- The UI must render readable states for:
  - no replay link summary
  - missing latest alias
  - invalid latest alias
  - mismatched latest alias
  - matched latest alias

- The existing recovery attempt list must remain visible.
- The existing benchmark artifact panel must remain visible.
- This task must not remove the current `Replay Source` details already shown in the recovery panel.

- Update active reviewer-facing docs so they explain that the internal recovery visualization now links directly to the latest recovery replay review artifact chain when available.

- No new dependencies may be added.
- No new database tables, columns, or migrations may be added.
- No new API route may be added.
- No benchmark, replay, or workflow runtime behavior may be changed.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not change recovery routing behavior, retry budgets, or failure profiles.
- Do not change `run_recovery_replay_review.py` CLI behavior or artifact-writing semantics.
- Do not add replay execution buttons, rerun controls, or report browsers to the UI.
- Do not redesign benchmark artifacts, system integrity summary, or customer-facing pages.
- Do not widen this task into memory governance, benchmark expansion, or AMap work.
- Do not add filesystem browsing APIs or arbitrary file download APIs.

## 5. Interfaces and Contracts

### Inputs

- Existing route:
  - `GET /internal/runs/{run_id}/observability`
- Existing internal observability sources:
  - `benchmark_artifact_summary.case_id`
  - `benchmark_artifact_summary.report_path`
  - `recovery_path_summary`
- Existing latest recovery review alias convention:
  - `var/recovery-reviews/latest-<case_id>-review.json`
- Existing schema:
  - `RecoveryReplayReviewResult`

### Outputs

- Additive backend response field:
  - `recovery_replay_link_summary`
- Additive frontend type updates
- Additive recovery visualization UI block on `5174`
- Updated backend/frontend/E2E tests
- Updated reviewer-facing docs

### Schemas

Example additive response fragment:

```json
{
  "recovery_replay_link_summary": {
    "status": "matched",
    "case_id": "family_route_failure_v1",
    "source_report_path": "var/formal-benchmarks/family-route.json",
    "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
    "review_artifact_path": "var/recovery-reviews/recovery-review-123/recovery-review.json",
    "replay_report_path": "var/recovery-reviews/replay-family-route.json",
    "review_status": "passed",
    "check_count": 3,
    "passed_check_count": 3,
    "failed_check_count": 0,
    "mismatch_reason": null
  }
}
```

Mismatch example:

```json
{
  "recovery_replay_link_summary": {
    "status": "mismatch",
    "case_id": "family_route_failure_v1",
    "source_report_path": "var/formal-benchmarks/current-run-report.json",
    "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
    "review_artifact_path": "var/recovery-reviews/recovery-review-older/recovery-review.json",
    "replay_report_path": "var/recovery-reviews/replay-older.json",
    "review_status": "passed",
    "check_count": 3,
    "passed_check_count": 3,
    "failed_check_count": 0,
    "mismatch_reason": "latest review source_report_path does not match the current benchmark artifact report_path"
  }
}
```

Missing example:

```json
{
  "recovery_replay_link_summary": {
    "status": "missing",
    "case_id": "family_route_failure_v1",
    "source_report_path": "var/formal-benchmarks/current-run-report.json",
    "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
    "review_artifact_path": null,
    "replay_report_path": null,
    "review_status": null,
    "check_count": null,
    "passed_check_count": null,
    "failed_check_count": null,
    "mismatch_reason": "latest recovery review alias was not found"
  }
}
```

## 6. Observability

This task extends the internal observability surface only.

It must expose only reviewer-safe replay-link facts:

- case id
- repo-relative paths
- review status
- review check counts
- mismatch reason

It must not expose:

- raw benchmark report JSON bodies
- raw replay report JSON bodies
- prompts
- tokens
- secrets
- authorization headers
- tracebacks
- stack traces
- action ids
- tool event ids
- idempotency keys

The task intentionally allows a narrow new file-read path in the internal observability service:
- read the latest recovery review alias file for the current case only

That file-read path must remain bounded, deterministic, and additive.

## 7. Failure Handling

- If the run does not exist, the route must keep returning `404`.
- If the run is not a benchmark-backed recovery run, `recovery_replay_link_summary` must be `null`.
- If the benchmark artifact report path is missing, `recovery_replay_link_summary` must be `null`.
- If the latest review alias file is missing, the route must still return `200` with `status = "missing"`.
- If the latest review alias file cannot be parsed or validated, the route must still return `200` with `status = "invalid"`.
- If the latest review alias file belongs to the same case but a different source report, the route must still return `200` with `status = "mismatch"`.
- If the UI receives `recovery_replay_link_summary = null`, it must render a readable no-link state instead of crashing.
- If the UI receives `status = "missing" | "invalid" | "mismatch"`, it must surface the reason clearly and still keep the rest of the recovery visualization visible.
- This task must not cause `/internal/runs/{run_id}/observability` to fail solely because recovery review artifacts are absent or stale.

## 8. Acceptance Criteria

- [ ] `docs/specs/118-recovery-replay-visualization-v0.md` exists and matches this task.
- [ ] `docs/plans/118-recovery-replay-visualization-v0-plan.md` exists and matches this task.
- [ ] `docs/specs` and `docs/plans` remain paired and continuous through Task `118`.
- [ ] `GET /internal/runs/{run_id}/observability` returns an additive `recovery_replay_link_summary` field.
- [ ] Recovery benchmark runs with a matching latest review alias return `status = "matched"` and expose latest review, review artifact, and replay report paths.
- [ ] Recovery benchmark runs with no latest review alias return `status = "missing"` without failing the route.
- [ ] Recovery benchmark runs with an invalid latest review alias return `status = "invalid"` without failing the route.
- [ ] Recovery benchmark runs whose latest review alias points at a different source report return `status = "mismatch"` without failing the route.
- [ ] Non-recovery runs continue to work and return `recovery_replay_link_summary = null`.
- [ ] The `5174` page renders the new replay-link block alongside the existing recovery visualization.
- [ ] Reviewers can copy each available replay-link path from the UI.
- [ ] Existing recovery attempt visualization remains visible.
- [ ] No new API route, dependency, migration, benchmark case, or replay execution control is added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] Focused backend, frontend, and E2E verification commands listed below pass, or blockers are reported clearly.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py tests/test_recovery_replay_review.py -q
npm --prefix frontend test -- --run src/observability/ObservabilityPage.test.tsx
cd frontend && npx playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: connect recovery replay to visualization
```

## 11. Notes for the Implementer

Keep this task additive and narrow.

The key rule is that replay linkage must be derived from the existing latest recovery review alias for the current case, then validated against the current run’s benchmark artifact report path. Do not guess, do not scan directories, and do not treat a same-case but different-source review artifact as a valid match.

Recommended sequence:

1. add the new typed linkage summary schema
2. build a bounded loader in internal observability service for `latest-<case_id>-review.json`
3. enforce `case_id + source_report_path` matching
4. expose additive API output
5. render reviewer states in the existing recovery visualization
6. update focused tests and docs

If implementation pressure starts pulling in replay reruns, filesystem browsing, or benchmark report parsing, stop and keep that for a separate follow-up task.
