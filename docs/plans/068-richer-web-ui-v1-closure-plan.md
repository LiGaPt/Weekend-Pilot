# Plan: 068 Richer Web UI V1 Closure

## 1. Spec Reference

Spec file:

```text
docs/specs/068-richer-web-ui-v1-closure.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/recovery-replay-review-closure-v0`, tracking `origin/codex/recovery-replay-review-closure-v0`.
- `docs/specs` and `docs/plans` are continuous and slug-matched from `001` through `067`.
- Latest commit is `ec8cca8 feat: add recovery replay review closure`, which matches task `067`.
- `main` is behind the `058-067` customer-demo and release-closure stack. This task must be executed on top of the current `067`-containing baseline or the first merged equivalent baseline, not from stale `main`.
- Pre-existing unrelated local changes already exist at `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/`, and `qc`; this task must not stage or modify them.
- Focused frontend UI tests already pass on the current baseline:
  - `npm --prefix frontend run test -- --run src/App.test.tsx src/observability/ObservabilityPage.test.tsx`

## 3. Files to Add

- `docs/RICHER_WEB_UI_V1_CHECKLIST.md` - canonical reviewer-facing V1 UI acceptance checklist across `5173`, `5174`, and existing scripts.
- `backend/app/benchmark/internal_summary.py` - narrow loader/validator for the latest `release_gate_v1` benchmark summary artifact.
- `tests/test_benchmark_internal_summary.py` - unit coverage for latest release-gate summary loading, extraction, and missing-file behavior.

## 4. Files to Modify

- `backend/app/api/observability.py` - add the narrow internal benchmark-summary route.
- `frontend/src/App.tsx` - add the explicit customer execution-timeline section using existing public execution data.
- `frontend/src/styles.css` - minimal layout/support styles for the new execution timeline and internal summary panel content.
- `frontend/src/observability/api.ts` - add the client for the latest release-gate benchmark summary route.
- `frontend/src/observability/types.ts` - add the internal benchmark-summary TypeScript contract.
- `frontend/src/observability/ObservabilityPage.tsx` - render explicit `Trace Summary`, `Benchmark Summary`, and `Recovery Visualization` reviewer sections.
- `frontend/src/App.test.tsx` - add/update customer execution-timeline assertions.
- `frontend/src/observability/ObservabilityPage.test.tsx` - add/update internal benchmark-summary and reviewer-heading assertions.
- `frontend/e2e/demo.spec.ts` - assert execution timeline is visible after confirmation/execution.
- `frontend/e2e/internal-observability.spec.ts` - extend the internal surface smoke to verify benchmark-summary and recovery/trace reviewer panels.
- `tests/test_observability.py` - preserve existing internal-observability behavior while verifying compatibility with the new reviewer framing.
- `tests/integration/test_observability_gateway.py` - cover the new internal benchmark-summary endpoint.
- `README.md` - add a concise richer-web-ui V1 note pointing to the checklist.
- `docs/WEB_DEMO_README.md` - add the reviewer flow for the richer-web-ui V1 closure slice.

## 5. Implementation Steps

1. Add the narrow backend artifact loader in `backend/app/benchmark/internal_summary.py`.
   It should load `var/formal-benchmarks/latest-release_gate_v1-run-report.json`, validate the file through the existing `BenchmarkRunReport` schema, extract `benchmark_summary`, and expose a compact internal reviewer model plus typed missing/malformed errors.
   Do not rebuild release-gate logic. Reuse the existing serialized summary as the source of truth.

2. Extend `backend/app/api/observability.py` with `GET /internal/benchmarks/release-gate-v1/summary`.
   Return the compact reviewer summary from step 1.
   On missing latest artifact, return a reviewer-readable `404` that tells the caller to run `python scripts/run_benchmark_release_gate.py`.
   Keep `GET /internal/runs/{run_id}/observability` unchanged except for any minimal imports needed.

3. Add backend test coverage before touching the frontend.
   In `tests/test_benchmark_internal_summary.py`, cover:
   - happy path loading of a valid latest release-gate report
   - missing-file behavior
   - malformed report behavior
   In `tests/integration/test_observability_gateway.py`, cover:
   - the new route returning the expected suite counts from a temporary latest report
   - the missing-report `404` path
   Keep existing observability route assertions intact.

4. Add the internal benchmark-summary client and type contracts on the frontend.
   In `frontend/src/observability/types.ts`, add a narrow TypeScript type for the new release-gate summary payload.
   In `frontend/src/observability/api.ts`, add a fetch helper for the new route and map reviewer-readable 404 messages cleanly through the existing `FrontendApiError` path.

5. Reframe the internal reviewer page in `frontend/src/observability/ObservabilityPage.tsx`.
   Keep the run-ID load flow intact.
   Add one explicit `Trace Summary` section name around the existing run/timing/observability information.
   Add one independent `Benchmark Summary` panel fed by the new route and rendered even before a run ID is loaded.
   Relabel the existing recovery area as reviewer-facing recovery visualization while preserving the current attempt and replay-source content.
   Keep the current tool-event and action-ledger panels intact.

6. Add the customer execution timeline in `frontend/src/App.tsx`.
   Render it only when `selectedPlan.execution` exists.
   Build the display from `execution.action_results`, sorted by `execution_order`.
   Show a compact start/finish summary when present.
   Keep it clearly separate from the existing pre-confirmation itinerary timeline and from the feedback lists.
   Do not expose any internal or forbidden fields even if they appear in the payload shape.

7. Add the minimal style changes in `frontend/src/styles.css`.
   Only add or adjust rules needed for:
   - the new execution-timeline section
   - the internal benchmark-summary panel content
   - any new reviewer section headings
   Avoid broad layout rewrites.

8. Update frontend tests.
   In `frontend/src/App.test.tsx`, add or update assertions that a completed run renders the new execution timeline and that ordering/status labels come from public-safe execution data.
   In `frontend/src/observability/ObservabilityPage.test.tsx`, add:
   - benchmark-summary loaded state
   - benchmark-summary missing state
   - explicit reviewer headings for trace summary and recovery visualization
   Keep existing current-panel assertions rather than replacing them.

9. Update browser smoke coverage.
   In `frontend/e2e/demo.spec.ts`, extend the confirm/completion path so it asserts the execution timeline becomes visible after execution completes.
   In `frontend/e2e/internal-observability.spec.ts`, intercept the new benchmark-summary route and the run-summary route with stable mocked payloads, then assert:
   - page loads on `5174`
   - `Trace Summary` is visible
   - `Benchmark Summary` is visible
   - recovery visualization content is visible
   Keep the test narrow and reviewer-focused.

10. Write the reviewer checklist and runbook updates.
    Create `docs/RICHER_WEB_UI_V1_CHECKLIST.md` and map the six required capabilities to exact reviewer steps and evidence.
    Update `docs/WEB_DEMO_README.md` so the manual reviewer flow explicitly covers:
    - customer planning
    - confirmation
    - execution timeline
    - internal trace summary
    - internal benchmark summary
    - internal recovery visualization
    Update `README.md` with a short note and link, not a full second runbook.

11. Run the focused verification commands and stage only task-related files.
    Confirm the new benchmark-summary route works against a refreshed latest release-gate artifact.
    Confirm the customer and internal pages still preserve the public/internal boundary.
    Do not stage the pre-existing unrelated local files listed in section 2.

## 6. Testing Plan

- Unit tests: `tests/test_benchmark_internal_summary.py` covers latest release-gate summary loading; `frontend/src/App.test.tsx` covers execution timeline rendering; `frontend/src/observability/ObservabilityPage.test.tsx` covers trace/benchmark/recovery reviewer sections.
- Integration tests: `tests/integration/test_observability_gateway.py` covers the new internal benchmark-summary endpoint; existing `tests/integration/test_demo_api_gateway.py` and `tests/test_observability.py` remain focused regression checks for unchanged public/internal contracts.
- Smoke tests: `frontend/e2e/demo.spec.ts` verifies the customer confirm path now visibly includes execution timeline; `frontend/e2e/internal-observability.spec.ts` verifies the internal reviewer surface shows trace, benchmark, and recovery reviewer panels.
- Manual reviewer checks: `python scripts/run_benchmark_release_gate.py` refreshes the canonical latest report used by the new benchmark-summary panel before final UI verification.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/App.test.tsx src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/test_observability.py tests/test_benchmark_release_gate.py tests/test_benchmark_internal_summary.py tests/integration/test_demo_api_gateway.py tests/integration/test_observability_gateway.py -q
python scripts/run_benchmark_release_gate.py
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "starts a run|Chinese reviewer prompt|internal observability surface"
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: close richer web ui v1 surface
```

Expected commands:

```bash
git status --short
git switch -c codex/richer-web-ui-v1-closure
git add backend/app/benchmark/internal_summary.py
git add backend/app/api/observability.py
git add frontend/src/App.tsx frontend/src/styles.css frontend/src/App.test.tsx
git add frontend/src/observability/api.ts frontend/src/observability/types.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/ObservabilityPage.test.tsx
git add frontend/e2e/demo.spec.ts frontend/e2e/internal-observability.spec.ts
git add tests/test_benchmark_internal_summary.py tests/test_observability.py tests/integration/test_observability_gateway.py
git add README.md docs/WEB_DEMO_README.md docs/RICHER_WEB_UI_V1_CHECKLIST.md
git commit -m "feat: close richer web ui v1 surface"
git push -u origin codex/richer-web-ui-v1-closure
```

The implementer must confirm `.env`, secrets, `var/`, `frontend/dist/`, and the pre-existing unrelated local files are not staged.

## 9. Out-of-scope Changes

- Do not change public demo request or response schemas.
- Do not change workflow routing, confirmation logic, execution logic, benchmark grading, or recovery policy.
- Do not widen the new benchmark-summary endpoint into a generic benchmark browser or arbitrary file reader.
- Do not add replay controls, benchmark rerun controls, or formal-verification controls to the UI.
- Do not redesign the customer/internal page architecture or merge the two surfaces.
- Do not add dependencies, migrations, or auth/access-control features.
- Do not commit generated `var/` artifacts, `frontend/dist/`, Playwright outputs, or unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] The customer surface now shows explicit execution timeline after execution completes.
- [ ] The internal surface now shows explicit trace summary, benchmark summary, and recovery visualization reviewer sections.
- [ ] The benchmark-summary panel is fed from the canonical latest `release_gate_v1` artifact and handles missing-report state cleanly.
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit, excluding only the pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or generated artifact was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- Verification commands and results.
- Whether the benchmark-summary endpoint was verified against a real refreshed `latest-release_gate_v1-run-report.json`.
- The run ID or concrete browser path used to verify internal trace/recovery reviewer content.
- Commit hash.
- Push result.
- Any residual limitations, especially if the internal benchmark-summary panel intentionally stays scoped to `release_gate_v1` only.
