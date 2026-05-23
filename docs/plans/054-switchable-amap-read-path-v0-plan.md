# Plan: 054 Switchable AMAP Read Path v0

## 1. Spec Reference

Spec file:

```text
docs/specs/054-switchable-amap-read-path-v0.md
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

- Current branch is `codex/memory-governance-v1`.
- Latest code commit is `2c8e6f0 feat: add memory governance v1`.
- The latest completed task on this branch is `053`.
- `docs/specs/` and `docs/plans/` are matched but not continuous on this branch; both are missing `047`, `049`, and `050`.
- The missing `047`, `049`, and `050` docs already exist on separate doc-only branches:
  - `codex/memory-query-policy-baseline-v0`
  - `codex/mock-world-scenario-pack-expansion-v1`
  - `codex/benchmark-l2-l3-suite-expansion-v0`
- Those branches are documentation convergence debt only and must not be folded into Task `054`.
- The runtime state before this task is:
  - `backend/app/providers/amap` already exists and its unit/integration tests pass.
  - the deterministic query planner already accepts `provider_profile="amap"`.
  - query execution and candidate enrichment already contain AMAP-aware read handling.
  - `WeekendPilotWorkflowRunner` still rejects AMAP workflow requests.
  - `WeekendPilotWorkflowNodes` still hard-code `build_mock_world_registry(...)`.
  - `DemoWorkflowService.start_run(...)` still hard-codes Mock World.
  - `DemoWorkflowService.confirm_run(...)` would attempt normal execution if the run ever reached confirmation.
  - AMAP search results currently normalize into `other_candidates`, so the path is not yet usable for plan generation.
- Focused baseline tests already pass before implementation:
  - `tests/test_amap_provider.py`
  - `tests/test_query_planner.py`
  - `tests/test_query_plan_execution.py`
  - `tests/test_candidate_enrichment.py`
  - `tests/test_langgraph_workflow.py`
- Pre-existing unrelated local paths must remain unstaged:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`

## 3. Files to Add

- None.

## 4. Files to Modify

- `docs/specs/054-switchable-amap-read-path-v0.md` - save the spec before implementation.
- `docs/plans/054-switchable-amap-read-path-v0-plan.md` - save the implementation plan before implementation.
- `backend/app/workflow/dependencies.py` - carry `tool_profile` alongside `world_profile` so node construction can resolve the correct registry.
- `backend/app/workflow/schemas.py` - allow AMAP workflow requests and add the exact `amap_shanghai_live` profile.
- `backend/app/workflow/runner.py` - allow only the supported AMAP preview combo and continue rejecting unsafe combinations.
- `backend/app/workflow/nodes.py` - resolve the gateway registry from `tool_profile` instead of hard-coding Mock World.
- `backend/app/planning/query_planner.py` - add canonical source-call category hints to AMAP `search_poi` calls.
- `backend/app/planning/execution.py` - use the AMAP source-call hint to bucket search results into activity/dining candidates.
- `backend/app/demo/schemas.py` - add `read_profile` to the public start and summary contracts.
- `backend/app/demo/service.py` - map `read_profile` to internal workflow profiles, surface safe AMAP setup errors, preserve read profile across follow-ups, and block AMAP confirmation.
- `frontend/src/types/demo.ts` - add the new public read-profile field to the frontend contracts.
- `frontend/src/api/demo.ts` - send `read_profile` and localize the new AMAP-specific backend messages.
- `frontend/src/api/demo.test.ts` - lock the updated request payload and response typing.
- `frontend/src/App.tsx` - add the explicit read-path selector, show the active profile, and keep the AMAP path pre-confirmation only.
- `frontend/src/App.test.tsx` - cover the selector and the AMap read-only confirmation boundary.
- `frontend/src/styles.css` - style the new selector and profile status copy without disturbing the existing layout.
- `tests/test_query_planner.py` - update AMAP query-plan assertions to cover canonical category hints.
- `tests/test_query_plan_execution.py` - replace the current “AMAP goes to other_candidates” expectation with the new activity/dining bucketing behavior.
- `tests/test_langgraph_workflow.py` - update profile validation coverage for the AMAP preview combo and rejection cases.
- `tests/test_demo_api.py` - update schema serialization tests for `read_profile`.
- `tests/integration/test_langgraph_workflow_gateway.py` - add a fake-registry AMAP preview workflow integration case.
- `tests/integration/test_demo_api_gateway.py` - add public API integration coverage for starting an AMap preview run and rejecting confirmation.
- `README.md` - document the explicit local AMAP preview path and the unchanged benchmark defaults.
- `docs/WEB_DEMO_README.md` - document the UI selection flow and the read-only boundary.

## 5. Implementation Steps

1. Save the new spec and plan docs first.
   Make sure `docs/specs/054-switchable-amap-read-path-v0.md` and `docs/plans/054-switchable-amap-read-path-v0-plan.md` exist exactly as written before changing code. This keeps the repo aligned with the existing task workflow.

2. Extend the internal workflow profile contract before touching the demo API.
   In `backend/app/workflow/dependencies.py`, add `tool_profile: str = "mock_world"` next to `world_profile`.
   In `backend/app/workflow/schemas.py`, update `WeekendPilotWorkflowRequest` so:
   - `tool_profile` accepts `"mock_world"` and `"amap"`
   - `world_profile` keeps the current Mock World literals and additionally accepts `"amap_shanghai_live"`
   In `backend/app/workflow/runner.py`, copy both `tool_profile` and `world_profile` into dependencies before constructing nodes.

3. Replace the current runtime profile gate with an exact supported-combo gate.
   Update `WeekendPilotWorkflowRunner._unsupported_profile_result(...)` to allow exactly:
   - Mock World + supported Mock World profile
   - AMap + `amap_shanghai_live` + `auto_confirm=False`
   Keep the return shape typed and non-raising.
   Add the exact AMAP read-only rejection message for unsupported execution combinations.
   Update `tests/test_langgraph_workflow.py` to cover:
   - accepted AMap preview request
   - rejected AMap `auto_confirm=True`
   - rejected AMap wrong-world-profile request
   - preserved Mock World behavior

4. Switch node construction from “always Mock World” to “selected profile.”
   In `backend/app/workflow/nodes.py`, replace the hard-coded `build_mock_world_registry(...)` call with:
   - `build_mock_world_registry(dependencies.world_profile)` when `dependencies.tool_profile == "mock_world"`
   - `build_amap_registry()` when `dependencies.tool_profile == "amap"`
   Do not add fallback.
   Keep the rest of the workflow graph unchanged.
   This step should not touch write execution logic because the supported AMap path remains `auto_confirm=False`.

5. Fix the minimum AMAP candidate bucketing gap so the preview path can actually generate plans.
   In `backend/app/planning/query_planner.py`, change the two AMAP `search_poi` planned calls so each carries an internal canonical bucket hint:
   - activity search -> activity hint
   - dining search -> dining hint
   Keep the live provider request fields intact.
   In `backend/app/planning/execution.py`, when normalizing `search_poi` results for provider `"amap"`, use the source call hint to assign the candidate to the activity or dining bucket.
   Preserve the raw AMAP provider category/type string in `raw_payload`.
   Update:
   - `tests/test_query_planner.py`
   - `tests/test_query_plan_execution.py`
   so the new bucketing behavior is locked in.

6. Add the public demo read-profile contract and map it to the internal workflow profiles.
   In `backend/app/demo/schemas.py`:
   - add `read_profile` to `DemoStartRunRequest` with default `"mock_world"`
   - add `read_profile` to `DemoRunSummary`
   In `backend/app/demo/service.py`:
   - map `read_profile="mock_world"` to `tool_profile="mock_world"` and `world_profile="family_afternoon"`
   - map `read_profile="amap"` to `tool_profile="amap"` and `world_profile="amap_shanghai_live"`
   - derive `DemoRunSummary.read_profile` from the persisted run `tool_profile`
   - keep `clarify_run(...)` and `replan_run(...)` inheriting the source run `tool_profile` / `world_profile`
   Also add the safe AMAP setup failure surface:
   - when a workflow start/clarify/replan fails because the AMAP key is missing, raise `DemoServiceError` with the exact safe message from the spec instead of the current generic “did not create a run” error.

7. Enforce the read-only confirmation boundary explicitly in the demo service.
   In `backend/app/demo/service.py`, add an early guard in `confirm_run(...)`:
   - if `run.tool_profile == "amap"`, raise `DemoServiceError(409, "AMAP read-only demo runs cannot be confirmed.")`
   This guard must run before `HumanConfirmationService(...)` or `DeterministicExecutionWorkflow(...)`.
   Do not change `decline_run(...)`.
   Add an integration assertion that the rejected confirm path creates no new `ActionLedger` rows and no write-tool `ToolEvent` rows.

8. Update the frontend contract, request payload, and local demo UX.
   In `frontend/src/types/demo.ts`, add `read_profile: "mock_world" | "amap"` to `DemoRunSummary` and `read_profile?: "mock_world" | "amap"` to `DemoStartRunRequest`.
   In `frontend/src/api/demo.ts`, make sure `startRun(...)` sends `read_profile`.
   Add localized frontend API messages for:
   - `AMAP read path is not configured for this environment.`
   - `AMAP read-only demo runs cannot be confirmed.`
   In `frontend/src/App.tsx`:
   - add local state for the selected read profile, default `"mock_world"`
   - render a simple explicit selector near the request composer
   - include `read_profile` in the start request
   - display the active profile in the run inspector
   - when `run.read_profile === "amap"` and `run.status === "awaiting_confirmation"`, hide or disable the confirm button and show explanatory copy that this is a read-only preview
   - keep decline and refresh behavior usable
   In `frontend/src/styles.css`, add only the minimal styles needed for the selector and helper text.

9. Add backend integration coverage using a fake AMAP registry instead of live network access.
   In `tests/integration/test_langgraph_workflow_gateway.py`, add one AMAP preview workflow case.
   Use `monkeypatch` on `backend.app.workflow.nodes.build_amap_registry` to return a registry with a fake provider that supplies:
   - one activity search result with AMAP-shaped payload and string location
   - one dining search result with AMAP-shaped payload and string location
   - working detail, weather, and route responses
   Assert:
   - the run reaches `awaiting_confirmation`
   - the selected run persists reviewed plans
   - the recorded pre-confirmation tool events all use `provider="amap"`
   - `action_count == 0`
   In `tests/integration/test_demo_api_gateway.py`, add:
   - one start-run case with `read_profile="amap"` that returns `read_profile="amap"` and `awaiting_confirmation`
   - one confirm case on that run that returns HTTP 409 and leaves action/write-event counts unchanged
   - one follow-up case (replan or clarify) that proves the source run’s read profile is preserved

10. Update the lightweight public schema tests and frontend unit tests.
    In `tests/test_demo_api.py`, update the summary/request fixtures to require and serialize `read_profile`.
    In `frontend/src/api/demo.test.ts`, assert the start payload now contains `read_profile`.
    In `frontend/src/App.test.tsx`, add a run fixture with `read_profile="amap"` and assert:
    - the active read profile label is rendered
    - confirm is unavailable for the AMAP preview path
    - the explanatory read-only text is shown
    Keep the existing default Mock World tests passing unchanged.

11. Update documentation last and keep the README boundary explicit.
    In `README.md`, document:
    - the default Mock World demo path
    - the optional local AMAP preview path
    - the fact that benchmark defaults remain Mock World
    In `docs/WEB_DEMO_README.md`, add:
    - the selector flow
    - AMAP key prerequisite
    - confirm is unavailable for the AMap preview path
    Do not rewrite the benchmark sections into live-provider guidance.

## 6. Testing Plan

- Unit tests:
  - `tests/test_langgraph_workflow.py` for supported and rejected profile combinations
  - `tests/test_query_planner.py` for AMAP activity/dining source-call hints
  - `tests/test_query_plan_execution.py` for AMAP candidate bucketing into activity/dining
  - `tests/test_demo_api.py` for `read_profile` serialization
  - `frontend/src/api/demo.test.ts` for the updated start payload
  - `frontend/src/App.test.tsx` for the selector and AMAP read-only confirmation boundary
- Integration tests:
  - `tests/integration/test_langgraph_workflow_gateway.py` with a fake AMAP registry and no live network
  - `tests/integration/test_demo_api_gateway.py` for public API start, preview, confirm rejection, and read-profile persistence
- Regression checks:
  - `tests/test_amap_provider.py` to make sure the provider package itself still behaves as before
  - `tests/test_benchmark_harness.py` and `tests/test_benchmark_suites.py` to prove benchmark defaults remain Mock World
- Explicit non-tests:
  - no new live AMAP test requirement
  - no benchmark harness provider-expansion test
  - no frontend E2E dependency on live AMAP

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_langgraph_workflow.py tests/test_query_planner.py tests/test_query_plan_execution.py tests/test_demo_api.py tests/test_amap_provider.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_demo_api_gateway.py tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q
npm --prefix frontend run test -- --run src/App.test.tsx src/api/demo.test.ts
npm --prefix frontend run build
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add switchable amap read path
```

Expected commands:

```bash
git status --short
git switch -c codex/switchable-amap-read-path-v0
git add docs/specs/054-switchable-amap-read-path-v0.md docs/plans/054-switchable-amap-read-path-v0-plan.md
git add backend/app/workflow/dependencies.py backend/app/workflow/schemas.py backend/app/workflow/runner.py backend/app/workflow/nodes.py
git add backend/app/planning/query_planner.py backend/app/planning/execution.py
git add backend/app/demo/schemas.py backend/app/demo/service.py
git add frontend/src/types/demo.ts frontend/src/api/demo.ts frontend/src/api/demo.test.ts frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git add tests/test_langgraph_workflow.py tests/test_query_planner.py tests/test_query_plan_execution.py tests/test_demo_api.py
git add tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_demo_api_gateway.py
git add README.md docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: add switchable amap read path"
git push -u origin codex/switchable-amap-read-path-v0
```

- If Task `053` is not yet merged upstream, branch from the current `2c8e6f0` tip or its merged equivalent.
- Do not stage `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, or the separate `047/049/050` doc-only backfill work.

## 9. Out-of-scope Changes

- Do not implement AMAP write tools or AMAP confirmation execution.
- Do not add provider fallback or mixed-provider execution behavior.
- Do not allow the benchmark harness to execute AMAP cases.
- Do not add new benchmark fixtures, suites, or live-provider benchmark scoring.
- Do not generalize the live provider path beyond the single explicit `amap_shanghai_live` profile.
- Do not change recovery routing, replay behavior, Chaos Harness semantics, or observability API shapes.
- Do not add dependencies or Alembic revisions.
- Do not backfill the missing `047`, `049`, or `050` docs here.
- Do not commit generated caches, secrets, or unrelated local files.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/054-switchable-amap-read-path-v0.md`.
- [ ] Mock World remains the default demo path.
- [ ] `DemoStartRunRequest` and `DemoRunSummary` now carry `read_profile`.
- [ ] The workflow runner allows only the exact supported AMAP preview profile.
- [ ] `WeekendPilotWorkflowNodes` no longer hard-code Mock World for all runs.
- [ ] AMAP search results are bucketed into activity/dining candidates deterministically by source-call hint.
- [ ] An AMAP preview workflow integration test can reach `awaiting_confirmation` with persisted plans.
- [ ] AMAP preview runs never create write-tool side effects.
- [ ] `confirm_run(...)` rejects AMAP preview runs before execution begins.
- [ ] Frontend shows an explicit selector and disables/hides confirmation for the AMap preview path.
- [ ] Benchmark harness defaults remain Mock World and regression checks still pass.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final public `DemoStartRunRequest` and `DemoRunSummary` read-profile contract.
- One AMAP preview integration result showing:
  - `status="awaiting_confirmation"`
  - `read_profile="amap"`
  - `action_count=0`
- The confirm-rejection result for an AMap preview run, including confirmation that no new `ActionLedger` rows or write-tool `ToolEvent` rows were created.
- The benchmark-default regression command results.
- The frontend unit test and build results.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, and the `047/049/050` doc-only work were not staged.