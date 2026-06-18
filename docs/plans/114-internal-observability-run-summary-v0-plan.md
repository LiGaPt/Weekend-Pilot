# Plan: 114 Internal Observability Run Summary v0

## 1. Spec Reference

Spec file:

```text
docs/specs/114-internal-observability-run-summary-v0.md
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

- Current branch is:

```text
codex/113.5-playwright-internal-observability-e2e-teardown-exit-v0
```

- Latest completed spec / plan pair is:

```text
113.5-playwright-internal-observability-e2e-teardown-exit-v0
```

- Latest commit is:

```text
8ff8cba fix: stabilize internal observability e2e teardown
```

- `docs/specs/` and `docs/plans/` are continuous and matched through `113.5`.
- Latest commit corresponds to the latest completed task.
- The worktree currently contains unrelated untracked local docs that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- The internal observability route and page already exist and are working:
  - `GET /internal/runs/{run_id}/observability`
  - `frontend/src/observability/ObservabilityPage.tsx`
- The backend already persists a canonical stored summary:
  - `metadata_json["summary"]` with schema `weekendpilot_run_summary_v1`
- The backend already exposes detailed sections for:
  - workflow timing
  - tool-event summaries
  - action-ledger summaries
  - benchmark artifact summary
  - recovery path summary
- The practical gap is structure, not missing raw data:
  - reviewers must scan multiple panels to understand one run
  - there is no additive structured digest that unifies timing, tool-event rollups, and recovery outcome
- `docs/TASK_INFO.md` currently assigns `114` to a docs-only reviewer-runbook polish task, but the tracked spec/plan chain does not yet contain a `114` task; this implementation plan assumes the next numbered task will instead be the M1 run-summary convergence slice.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/observability/schemas.py` - add additive Pydantic models for the structured internal `run_summary` digest and add the new top-level field to `InternalObservabilityRunSummary`.
- `backend/app/observability/service.py` - compute the new structured digest from canonical stored summary, workflow timing, tool events, and recovery metadata.
- `frontend/src/observability/types.ts` - mirror the additive `run_summary` contract in TypeScript.
- `frontend/src/observability/ObservabilityPage.tsx` - render a compact `Run Summary` section in the internal page before the detailed panels.
- `frontend/src/observability/api.test.ts` - update the mocked response shape for the additive field.
- `frontend/src/observability/ObservabilityPage.test.tsx` - add rendering coverage for the new summary section, degraded timing, and no-recovery state.
- `frontend/e2e/internal-observability.spec.ts` - extend the internal-page mocked payload and assertions so the new `Run Summary` section is visible in the smoke path.
- `tests/test_observability.py` - add backend unit coverage for structured digest generation and degraded cases.
- `tests/integration/test_observability_gateway.py` - assert the route returns the additive digest and that it stays consistent with detailed sections.
- `docs/WEB_DEMO_README.md` - mention the reviewer-facing `Run Summary` digest in the internal observability walkthrough.

## 5. Implementation Steps

1. Confirm the baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Verify the repo is currently on top of task `113.5`.
   - Do not touch the unrelated untracked docs.

2. Inspect the current internal observability contract and its data sources.
   - Read:
     - `backend/app/observability/schemas.py`
     - `backend/app/observability/service.py`
     - `backend/app/observability/summary.py`
     - `frontend/src/observability/types.ts`
     - `frontend/src/observability/ObservabilityPage.tsx`
     - `tests/test_observability.py`
     - `tests/integration/test_observability_gateway.py`
   - Confirm:
     - top-level payload already has detailed timing / tool / recovery sections
     - canonical stored `weekendpilot_run_summary_v1` already exists
     - there is no additive compact digest yet

3. Extend backend schemas first.
   - In `backend/app/observability/schemas.py`, add additive models for:
     - `InternalRunSummaryStageTimingDigest`
     - `InternalRunSummaryLatestToolEvent`
     - `InternalRunSummaryToolEventDigest`
     - `InternalRunSummaryRecoveryDigest`
     - `InternalStructuredRunSummary`
   - Add `run_summary: InternalStructuredRunSummary | None = None` to `InternalObservabilityRunSummary`.
   - Keep all existing response fields unchanged.

4. Add failing backend unit tests before implementing logic.
   - In `tests/test_observability.py`, add tests that require:
     - a run with timing, tool events, and recovery gets a populated `run_summary`
     - a run with no workflow timing returns `stage_timing.present == false`
     - a run with no tool events returns zeroed tool rollups and `latest_event is None`
     - a run with no recovery returns `entered_recovery == false`
     - canonical stored summary values are preferred for `trace_id`, `execution_status`, `feedback_status`, `selected_plan_id`, and `plan_status`
   - Keep the tests focused on the new additive digest and compatibility.

5. Implement digest builders in `InternalObservabilityService`.
   - Add one private helper to build the structured digest from:
     - run row
     - canonical stored summary
     - selected plan
     - workflow timing summary
     - ordered tool events
     - recovery path summary
   - Keep the helper additive; do not change the existing detailed-section helpers.
   - The helper must:
     - prefer canonical stored summary fields when valid
     - compute timing digest from the current timing summary object
     - compute tool rollups from the current ordered tool events
     - compute recovery digest from the current `recovery_path_summary`
   - Return a fully degraded but non-null digest whenever the run exists.

6. Implement timing digest logic.
   - Reuse the current workflow timing parsing already used by the service.
   - Compute:
     - `present`
     - `total_duration_ms`
     - `stage_count`
     - `slowest_stage_name`
     - `slowest_stage_duration_ms`
   - If timing is missing or malformed:
     - return `present=false`
     - return null numeric/name fields
   - Do not raise.

7. Implement tool-event digest logic.
   - Reuse the already-loaded ordered tool events list.
   - Compute:
     - `total_count`
     - `read_count`
     - `write_count`
     - `status_counts`
     - `provider_counts`
     - `latest_event`
   - `latest_event` must use only:
     - `tool_name`
     - `tool_type`
     - `provider`
     - `status`
     - `latency_ms`
     - `created_at`
   - Do not include request / response / error previews in the digest.

8. Implement recovery digest logic.
   - Reuse the service’s existing `recovery_path_summary`.
   - If no recovery path exists:
     - return `entered_recovery=false`
     - `attempt_count=0`
     - `max_attempts=0`
     - all other fields null
   - If recovery exists:
     - use the last attempt by `attempt_index` as terminal outcome
     - set:
       - `terminal_action`
       - `terminal_status`
       - `latest_error_type`
       - `replay_case_id`
   - Keep the full `recovery_path_summary` field unchanged.

9. Wire the additive field into the route response.
   - Update `InternalObservabilityService.get_run_summary(...)` to populate the new `run_summary` field.
   - Do not change `backend/app/api/observability.py` route shape or status handling beyond the additive response model behavior.

10. Extend backend integration tests.
   - In `tests/integration/test_observability_gateway.py`:
     - update the happy-path route assertion to include `run_summary`
     - assert the digest matches the detailed sections:
       - timing totals align with `workflow_timing_summary`
       - tool-event counts align with `tool_event_summaries`
       - recovery digest aligns with `recovery_path_summary`
     - add one route test for a run with missing timing and no recovery
   - Keep 404 behavior unchanged.

11. Extend frontend types and API tests.
   - In `frontend/src/observability/types.ts`, add the TypeScript shapes for the new digest and extend `InternalObservabilityRunSummary`.
   - In `frontend/src/observability/api.test.ts`, update the mocked internal observability response payload to include the additive `run_summary`.
   - Assert the client still parses the whole payload successfully.

12. Render the new compact `Run Summary` section.
   - In `frontend/src/observability/ObservabilityPage.tsx`:
     - add a new `Run Summary` section at the start of the loaded run workspace
     - keep `Trace Summary` intact and below it or immediately after it
   - The new section must show:
     - run / trace identity and top outcome fields
     - timing digest cards:
       - total duration
       - stage count
       - slowest stage
     - tool rollup cards:
       - total events
       - read events
       - write events
       - latest event status or provider summary
     - recovery digest cards:
       - entered recovery
       - attempt count / max attempts
       - terminal action / terminal status
   - Add compact provider/status count chips or lists for the tool-event digest.
   - Show neutral fallback copy for missing timing and no-recovery cases.

13. Extend frontend component tests.
   - In `frontend/src/observability/ObservabilityPage.test.tsx`, add assertions that:
     - `Run Summary` heading renders
     - timing metrics render from `run_summary.stage_timing`
     - tool rollups render from `run_summary.tool_events`
     - recovery digest renders from `run_summary.recovery`
     - missing timing renders a fallback message
     - no-recovery renders a neutral “no bounded recovery” style state
   - Keep existing `Trace Summary`, `Tool Events`, `Action Ledger`, `Benchmark Artifacts`, and `Recovery Visualization` assertions intact.

14. Extend the Playwright smoke fixture.
   - In `frontend/e2e/internal-observability.spec.ts`:
     - add the additive `run_summary` field to the mocked route payload
     - assert the page shows `Run Summary`
     - assert at least one timing value and one recovery/tool digest value are visible
   - Do not broaden the E2E beyond this focused smoke path.

15. Update the active reviewer doc.
   - In `docs/WEB_DEMO_README.md`, update the internal observability walkthrough so it says the run page now starts with a compact `Run Summary` digest before the detailed panels.
   - Do not widen this into a general reviewer runbook rewrite.

16. Run focused verification.
   - Backend:
     ```bash
     python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -q
     ```
   - Frontend:
     ```bash
     npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
     ```
   - E2E:
     ```bash
     cd frontend && npx playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
     ```
   - Hygiene:
     ```bash
     git diff --check
     git status --short
     ```

17. Commit only task-relevant files.
   - Stage only the observability backend, frontend, tests, docs, and task docs touched by this task.
   - Commit with:
     ```bash
     git commit -m "feat: add run summary observability"
     ```

## 6. Testing Plan

- Unit tests:
  - `tests/test_observability.py`
    - populated `run_summary` with timing + tools + recovery
    - degraded timing digest when timing missing
    - zeroed tool digest when no tool events
    - no-recovery digest when recovery metadata absent
    - canonical stored summary fields preferred where available

- Integration tests:
  - `tests/integration/test_observability_gateway.py`
    - route returns additive `run_summary`
    - digest aligns with detailed route fields
    - degraded route response still succeeds for no-timing / no-recovery run
    - missing run still returns `404`

- Frontend tests:
  - `frontend/src/observability/api.test.ts`
    - additive response shape parses cleanly
  - `frontend/src/observability/ObservabilityPage.test.tsx`
    - `Run Summary` renders timing/tool/recovery digest
    - missing timing and no-recovery states render readable fallback copy

- E2E smoke:
  - `frontend/e2e/internal-observability.spec.ts`
    - internal page shows `Run Summary` from mocked route payload
    - existing internal observability smoke path still passes

- Documentation check:
  - `docs/WEB_DEMO_README.md` reflects the new reviewer-facing `Run Summary` digest

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -q
npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
cd frontend && npx playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add run summary observability
```

Expected commands:

```bash
git status --short
git switch -c codex/114-internal-observability-run-summary-v0
git add backend/app/observability/schemas.py backend/app/observability/service.py frontend/src/observability/types.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.test.tsx frontend/e2e/internal-observability.spec.ts tests/test_observability.py tests/integration/test_observability_gateway.py docs/WEB_DEMO_README.md docs/specs/114-internal-observability-run-summary-v0.md docs/plans/114-internal-observability-run-summary-v0-plan.md
git diff --cached --check
git commit -m "feat: add run summary observability"
git push -u origin codex/114-internal-observability-run-summary-v0
```

The implementer must confirm:
- unrelated untracked docs remain unstaged
- no `var/` artifacts are staged
- no secrets are staged
- task numbering is acceptable before saving if `docs/TASK_INFO.md` is later reconciled

## 9. Out-of-scope Changes

- Do not change benchmark summary or system-integrity summary contracts.
- Do not redesign the full internal observability page.
- Do not add a new route, new database schema, or new persistence format.
- Do not change public demo API contracts.
- Do not change detailed tool-event preview, action-ledger preview, or recovery-attempt payloads beyond additive compatibility.
- Do not update reviewer submission docs broadly.
- Do not touch `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, or `docs/superpowers/`.
- Do not stage generated caches, virtual environments, or `var/` output artifacts.
- Do not add dependencies.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/114-internal-observability-run-summary-v0.md`.
- [ ] The task stayed within M1 observability-structure scope.
- [ ] `GET /internal/runs/{run_id}/observability` gained an additive `run_summary` field only.
- [ ] Existing route fields stayed backward compatible.
- [ ] The new digest exposes timing, tool-event, and recovery key facts without leaking raw payloads or ids.
- [ ] Missing timing does not break the route.
- [ ] No-recovery runs still return a usable digest.
- [ ] The `5174` page clearly shows `Run Summary` before or at the start of detailed sections.
- [ ] Existing `Trace Summary`, `Tool Events`, `Action Ledger`, `Benchmark Artifacts`, and `Recovery Visualization` sections still work.
- [ ] Focused backend, frontend, and E2E checks passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- exact files changed
- the final `run_summary` schema fields added
- whether canonical stored summary values or live-derived values were used for each digest subsection
- verification commands run and results
- whether the E2E smoke assertion needed any fixture-only updates
- commit hash
- push result
- confirmation that unrelated untracked local docs stayed untouched
- any follow-up task suggested by implementation, especially if `docs/TASK_INFO.md` numbering needs reconciliation
