# Spec: 054 Switchable AMAP Read Path v0

## 1. Goal

Expose the already-implemented AMAP read provider as a controlled, explicitly selectable local demo path instead of leaving it as unreachable infrastructure.

After this task, the local demo must be able to start a run with an explicit AMAP read profile, execute only the read-side workflow stages through AMAP, produce reviewed plans for preview, and stop at the confirmation boundary without executing any write tools. The default demo path and the benchmark harness must still stay on Mock World so evaluation stability is not polluted by live provider behavior.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` explicitly requires the Tool Gateway to support both mock and real providers, while also stating that Mock World must remain available even when real provider integration is added. It also requires human confirmation before side effects and keeps deterministic benchmarking as a core architecture principle.

`docs/NEXT_PHASE_ROADMAP.md` places this work in milestone `M5. 恢复、真实 provider、记忆治理`, and the roadmap's recommended order makes this the next still-open product task after Task `053` completed `10. 长期记忆治理`. Task `052` already covered the roadmap's Chaos Harness direction, so the next M5 gap is the controlled read-only provider path.

The repository is already partially prepared for this task:

- Task `006` added the AMAP read provider package and fake/live provider tests.
- The deterministic query planner already accepts `provider_profile="amap"`.
- Query execution and candidate enrichment already contain AMAP-aware route and response handling.

However, the runtime path is still blocked:

- `WeekendPilotWorkflowRunner` rejects non-Mock-World workflow profiles.
- `WeekendPilotWorkflowNodes` always builds a Mock World registry.
- `DemoWorkflowService.start_run(...)` hard-codes Mock World.
- The public frontend has no explicit provider selector.
- AMAP search results currently normalize into `other_candidates` instead of usable `activity` / `dining` buckets, so even a simple profile toggle would not produce plans.

`docs/specs/` and `docs/plans/` on the current branch are matched but not continuous because `047`, `049`, and `050` are missing. Those gaps already exist on separate doc-only branches and are not the runtime blocker this task should solve.

## 3. Requirements

### Repository defaults and roadmap intent

- Keep Mock World as the default demo path when no explicit read profile is requested.
- Keep the benchmark harness, benchmark fixtures, benchmark suite defaults, and benchmark README guidance on Mock World only.
- Do not add any implicit fallback from AMAP to Mock World inside this task.
- Do not widen this task into benchmark-provider support or cross-provider recovery.

### Public demo contract

- Add `read_profile` to `DemoStartRunRequest`.
- `read_profile` must accept exactly:
  - `"mock_world"`
  - `"amap"`
- `read_profile` must default to `"mock_world"`.
- Keep `DemoClarifyRunRequest` unchanged.
- Keep `DemoReplanRunRequest` unchanged.
- Add `read_profile` to `DemoRunSummary`.
- `DemoRunSummary.read_profile` must always reflect the persisted run path:
  - `"mock_world"` when the run uses Mock World
  - `"amap"` when the run uses the AMAP read-only preview path

### Internal workflow profile contract

- `WeekendPilotWorkflowRequest.tool_profile` must accept exactly:
  - `"mock_world"`
  - `"amap"`
- `WeekendPilotWorkflowRequest.world_profile` must continue accepting the existing Mock World profiles and must additionally accept exactly:
  - `"amap_shanghai_live"`
- `WeekendPilotWorkflowDependencies` must carry both the selected `tool_profile` and `world_profile` so node construction can resolve the correct registry before graph execution begins.
- `WeekendPilotWorkflowRunner._unsupported_profile_result(...)` must allow exactly these combinations:
  - `tool_profile="mock_world"` with `world_profile` in the existing Mock World supported profile set
  - `tool_profile="amap"` with `world_profile="amap_shanghai_live"` and `auto_confirm=False`
- Any other combination must still return a typed `unsupported_profile` workflow result.
- The typed AMAP rejection message for unsupported execution combinations must explicitly state that the supported AMAP path is read-only and pre-confirmation only.

### Registry selection and provider boundary

- `WeekendPilotWorkflowNodes` must stop hard-coding `build_mock_world_registry(...)`.
- Registry resolution must branch on the selected workflow `tool_profile`:
  - `"mock_world"` -> `build_mock_world_registry(world_profile)`
  - `"amap"` -> `build_amap_registry()`
- This task must not add any new registry default that silently switches providers later in the run.
- If the selected AMAP registry cannot be built because the API key is missing, the run must fail explicitly. It must not silently downgrade to Mock World.

### Minimal AMap candidate bucketing required for a usable preview path

- The deterministic query planner must attach explicit canonical category hints to the two AMAP `search_poi` initial tool calls:
  - the activity search call must carry a canonical activity hint
  - the dining search call must carry a canonical dining hint
- The provider payload sent to AMAP may still ignore that hint, but the hint must remain available to the query executor.
- `QueryPlanExecutor` must use the source call's canonical hint when normalizing AMAP `search_poi` results into candidate buckets.
- For AMAP search results, candidate bucketing must therefore become:
  - activity search results -> `activity_candidates`
  - dining search results -> `dining_candidates`
- The raw AMAP POI type/category string must still remain preserved in `raw_payload`.
- This task must not add a semantic classifier that guesses activity vs dining from arbitrary AMAP text. The bucket decision must remain deterministic and source-call-based.

### Read-only AMAP preview behavior

- A demo run started with `read_profile="amap"` must map internally to:
  - `tool_profile="amap"`
  - `world_profile="amap_shanghai_live"`
- The workflow must execute only the existing read-side stages through AMAP:
  - query generation
  - search execution
  - candidate enrichment
  - route calculation
  - plan generation
  - final review
  - presentation
- The supported AMAP path must stop at `awaiting_confirmation`.
- The AMAP path must be able to persist reviewed plans and return them through the public demo summary.
- The AMAP path must not execute write tools.
- The AMAP path must not support `auto_confirm=True`.

### Demo confirmation boundary for AMAP

- `DemoWorkflowService.confirm_run(...)` must reject runs whose persisted `tool_profile` is `"amap"`.
- The rejection must happen before `HumanConfirmationService` or `DeterministicExecutionWorkflow` is invoked.
- The rejection message must be exactly:

```text
AMAP read-only demo runs cannot be confirmed.
```

- Rejecting confirmation for an AMAP run must not:
  - create Action Ledger rows
  - create `tool_events` rows with `tool_type="write"`
  - mutate the selected plan into a confirmed or executed state
- `DemoWorkflowService.decline_run(...)` may remain available for AMAP preview runs because it does not execute external write tools.

### Safe error surfacing for explicit AMAP enablement

- If the user explicitly requests `read_profile="amap"` and the local environment is not configured for AMAP, the demo API must return a safe user-visible error instead of the current generic "run did not create a run" failure.
- The safe message for missing AMAP configuration must be exactly:

```text
AMAP read path is not configured for this environment.
```

- It is acceptable to derive that safe message by recognizing `AMapConfigurationError`.
- This task does not need to redesign every workflow error path. It must at least make the explicit AMAP-enable path diagnosable.

### Frontend behavior

- The public demo UI must expose an explicit selector for the read path before the run starts.
- The selector must show exactly two options:
  - Mock World
  - AMap 只读预览
- The selector must default to Mock World.
- The start request sent by the frontend must include the selected `read_profile`.
- The run inspector must show the currently active read profile.
- When a run is in `awaiting_confirmation` and `read_profile="amap"`:
  - the UI must clearly communicate that this is a read-only preview path
  - the confirm action must not be available
  - refresh must remain available
  - decline may remain available
- The frontend API layer must localize the new AMAP-specific backend messages into user-readable Chinese copy.

### Documentation

- Update `README.md` to document:
  - the default Mock World behavior
  - the explicit AMAP local demo preview path
  - the fact that benchmark defaults remain Mock World
- Update `docs/WEB_DEMO_README.md` to document:
  - how to select the AMAP preview path
  - that it is read-only and stops before confirmation
  - that `AMAP_MAPS_API_KEY` is required only for that local preview path

## 4. Non-goals

- Do not implement any AMAP write tools.
- Do not let AMAP runs enter deterministic execution, action ledger writes, or feedback writing.
- Do not add provider fallback, provider switching, or mixed AMAP-read plus Mock-World-write execution behavior.
- Do not modify benchmark case JSON, benchmark suite membership, or benchmark harness provider support.
- Do not add live-provider replay behavior, provider-specific recovery routing, or Chaos Harness provider failover.
- Do not generalize the live provider path beyond the single explicit local profile `amap_shanghai_live`.
- Do not add new dependencies or Alembic revisions.
- Do not backfill missing `047`, `049`, or `050` docs in this task.
- Do not stage `.env`, API keys, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, or `var/`.

## 5. Interfaces and Contracts

### Inputs

- Public demo start request:

```json
{
  "user_input": "今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。",
  "external_user_id": "web-demo-user",
  "display_name": "Web Demo User",
  "case_id": "web-demo",
  "selected_plan_index": 0,
  "read_profile": "amap"
}
```

- Internal workflow request for the AMAP preview path:

```json
{
  "user_input": "今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。",
  "tool_profile": "amap",
  "world_profile": "amap_shanghai_live",
  "auto_confirm": false
}
```

### Outputs

- Public demo summary must include the selected read profile:

```json
{
  "run_id": "00000000-0000-0000-0000-000000000000",
  "status": "awaiting_confirmation",
  "read_profile": "amap",
  "selected_plan_id": "11111111-1111-1111-1111-111111111111",
  "plan_version": {
    "version_number": 1,
    "version_label": "v1",
    "source_run_id": null,
    "source_selected_plan_id": null
  }
}
```

- Confirmation attempt for an AMAP preview run must fail with an HTTP 409 detail string:

```json
{
  "detail": "AMAP read-only demo runs cannot be confirmed."
}
```

### Schemas

- Public enum values introduced by this task:

```json
{
  "demo_read_profile_values": ["mock_world", "amap"],
  "workflow_tool_profile_values": ["mock_world", "amap"],
  "workflow_amap_world_profile": "amap_shanghai_live"
}
```

- The supported workflow combinations after this task are:

```json
{
  "supported_workflow_profiles": [
    {
      "tool_profile": "mock_world",
      "world_profile": "family_afternoon | solo_afternoon | couple_afternoon | friends_gathering | rainy_day_fallback | budget_lite",
      "auto_confirm": true,
      "notes": "existing benchmark and demo-compatible path"
    },
    {
      "tool_profile": "amap",
      "world_profile": "amap_shanghai_live",
      "auto_confirm": false,
      "notes": "read-only pre-confirmation demo preview path"
    }
  ]
}
```

## 6. Observability

- Keep using the existing `agent_runs.tool_profile` and `agent_runs.world_profile` columns as the durable source of truth for the selected path.
- Keep using existing `tool_events.provider` values to distinguish Mock World vs AMAP read calls.
- For AMAP demo runs, all recorded pre-confirmation tool events must use `provider="amap"`.
- AMAP demo runs must not create write-tool `tool_events`.
- This task does not add new public internal observability endpoints or new benchmark metadata.
- The only public demo-facing contract addition is `read_profile`.

## 7. Failure Handling

- If `read_profile="amap"` is requested without AMAP configuration, the demo API must fail safely with:

```text
AMAP read path is not configured for this environment.
```

- If a workflow request uses `tool_profile="amap"` with `world_profile != "amap_shanghai_live"`, the workflow must return a typed `unsupported_profile` error.
- If a workflow request uses `tool_profile="amap"` with `auto_confirm=True`, the workflow must return a typed `unsupported_profile` error stating that the AMAP path is read-only and pre-confirmation only.
- If AMAP read calls fail during planning, the system must not silently switch to Mock World.
- If the user attempts to confirm an AMAP preview run, the API must return:

```text
AMAP read-only demo runs cannot be confirmed.
```

- Rejecting AMAP confirmation must leave the run with zero executed actions and no write-tool side effects.
- Default Mock World behavior must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/054-switchable-amap-read-path-v0.md` exists and matches this task.
- [ ] `docs/plans/054-switchable-amap-read-path-v0-plan.md` exists and matches this task.
- [ ] Latest task progression remains coherent: Task `053` is still the latest completed task and this new task is `054`.
- [ ] `DemoStartRunRequest` accepts `read_profile` with default `"mock_world"`.
- [ ] `DemoRunSummary` exposes `read_profile`.
- [ ] Starting a demo run without `read_profile` still uses Mock World and the existing `family_afternoon` default.
- [ ] Starting a demo run with `read_profile="amap"` maps internally to `tool_profile="amap"` and `world_profile="amap_shanghai_live"`.
- [ ] The workflow runner accepts the AMAP preview combination only when `auto_confirm=False`.
- [ ] The workflow runner still rejects unsupported profile combinations with typed `unsupported_profile` errors.
- [ ] AMAP search results are bucketed into activity and dining candidates by deterministic source-call hints so the path can produce plans.
- [ ] A fake-registry integration test can run the AMAP preview workflow to `awaiting_confirmation` with persisted plans and `action_count == 0`.
- [ ] A public demo API integration test can start an AMAP preview run and return `read_profile="amap"` in `DemoRunSummary`.
- [ ] AMAP preview runs show only read-side provider activity and no write-tool execution.
- [ ] `confirm_run` rejects AMAP preview runs with `HTTP 409` and the exact read-only message.
- [ ] Rejecting confirmation for an AMAP run does not create Action Ledger rows or write-tool `tool_events`.
- [ ] Replan and clarify continuations inherit the source run read profile.
- [ ] The public frontend exposes an explicit selector and defaults it to Mock World.
- [ ] The public frontend does not offer confirmation when the run is on the AMAP preview path.
- [ ] The benchmark harness remains Mock World only.
- [ ] Default benchmark suites, case inventory, and benchmark commands remain unchanged.
- [ ] No AMap write execution, provider fallback, migration, or benchmark-provider expansion is added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except for the known unrelated local untracked files outside this task.

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: add switchable amap read path
```

## 11. Notes for the Implementer

Keep the task narrow and honest.

The product gap is not “support all providers everywhere.” The gap is that the repository already contains a real read provider path, but it still behaves like dead code because the workflow and demo surface cannot select it safely. This task should therefore do exactly three things:

1. make the path selectable,
2. make it actually produce preview plans,
3. keep it strictly pre-confirmation and read-only.

If implementation pressure starts pulling in write execution, provider fallback, benchmark-provider support, or generalized live geography support, stop and narrow the change back down.