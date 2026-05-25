# Spec: 064 Friends Group Demo Path v1

## 1. Goal

WeekendPilot already has a deterministic `friends_gathering` Mock World profile and a canonical benchmark case `friends_gathering_v1`, but the public demo path still hardcodes Mock World starts to `family_afternoon`. As a result, an explicit friends-group request can be evaluated through fixture and benchmark coverage, but not yet through a stable product demo path.

This task upgrades that gap into a product-grade v1 demo path. After this task, an explicit friends-group Mock World request on the public demo API and public demo UI should resolve to the `friends_gathering` world, the repository should publish at least one public demo input sample for that scenario, and automated happy-path verification should cover the same public route without changing the existing family default.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` lists the Friend group scenario as a V1 product item.

`docs/NEXT_PHASE_ROADMAP.md` places this work under `M3. 多场景与 benchmark 扩展`, whose goal is to stop evaluating and demonstrating only the family path.

The current repository is already materially ahead on parts of the roadmap that would normally precede this work:

- stage timing and benchmark summary alignment already exist
- internal observability API and review surfaces already exist
- benchmark suite coverage rollups already exist
- formal verification already exists
- the deterministic `friends_gathering` Mock World world and `friends_gathering_v1` benchmark case already exist

That means the smallest remaining gap is not more raw benchmark infrastructure. The gap is product convergence:

- `backend/app/demo/service.py` still hardcodes Mock World demo starts to `family_afternoon`
- `README.md`, `docs/WEB_DEMO_README.md`, and `frontend/e2e/demo.spec.ts` still present family-only public demo examples

This task closes that M3 gap without widening into a full multi-profile demo routing system.

## 3. Requirements

- Keep the public demo API request and response schema unchanged.
- Add a deterministic internal resolver for Mock World demo starts.
- When `DemoStartRunRequest.read_profile == "mock_world"` and no explicit `override.world_profile` is supplied, a start request whose parsed `scenario_type` is `friends` must run with `world_profile="friends_gathering"`.
- In this task, the resolver must add only one new scenario-specific mapping:
  - `friends -> friends_gathering`
- All other Mock World demo starts must continue to default to `family_afternoon` in this task.
- `read_profile="amap"` must keep mapping to the existing AMAP preview path with no behavior change.
- An explicit `override.world_profile` must continue to win over auto-resolution.
- Follow-up `clarify` and `replan` calls must continue to reuse the source run's persisted `world_profile`. Do not add continuation-time world switching in this task.
- Publish at least one public friends-group demo sample in:
  - `README.md`
  - `docs/WEB_DEMO_README.md`
- The published sample must describe:
  - friends-group participants
  - this afternoon or a few afternoon hours
  - nearby or not too far
  - an outdoor hangout first
  - a nearby casual or shareable dinner
- Add unit coverage for the demo Mock World profile resolver.
- Add a demo API gateway integration test that:
  - starts from an explicit friends-group Mock World prompt
  - reaches `awaiting_confirmation`
  - keeps `action_count = 0` before confirmation
  - persists `tool_profile="mock_world"` and `world_profile="friends_gathering"` on the created `AgentRun`
  - confirms successfully and produces at least one Action Ledger entry
- Add at least one Playwright desktop happy-path smoke that starts the public demo with the friends-group sample and reaches a confirmable or completed public run without exposing internal keys.
- Keep the existing `backend/app/benchmark/cases/friends_gathering_v1.json` benchmark case loadable and registered. Do not rename or remove it.
- Keep the existing `backend/app/providers/mock_world/fixtures/friends_gathering.json` fixture available as the canonical world for this path.
- Do not add new dependencies.
- Do not add or modify Alembic revisions.

## 4. Non-goals

- Do not implement general demo routing for `solo_afternoon`, `couple_afternoon`, `rainy_day_fallback`, or `budget_lite`.
- Do not add a public scenario selector, preset switcher, or new demo request field.
- Do not change the current default family sample out of the public UI.
- Do not change `DemoStartRunRequest`, `DemoRunSummary`, or public `action_manifest` contracts.
- Do not change benchmark suite membership, taxonomy, or benchmark scoring behavior.
- Do not rewrite the `friends_gathering` fixture or benchmark case unless a focused failing verification proves the current data is insufficient for a stable demo path.
- Do not change clarification policy, replan semantics, plan versioning, AMAP preview behavior, or internal observability routes.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- Existing public start request:
  - `DemoStartRunRequest`
- Existing internal start entry point:
  - `DemoWorkflowService.start_run(...)`
- Existing deterministic parser:
  - `DeterministicIntentParser`
- Existing canonical friends scenario assets:
  - `backend/app/providers/mock_world/fixtures/friends_gathering.json`
  - `backend/app/benchmark/cases/friends_gathering_v1.json`

### Outputs

- No new public API fields.
- New internal Mock World demo resolution behavior:
  - explicit friends start prompt -> `world_profile="friends_gathering"`
  - all other Mock World start prompts in this task -> `world_profile="family_afternoon"`
- Persisted `AgentRun.world_profile` for the friends-group public demo path.
- Published public demo sample text in `README.md` and `docs/WEB_DEMO_README.md`.
- One resolver unit test, one gateway integration happy-path check, and one Playwright desktop smoke for the friends path.

### Schemas

Internal resolution example for this task:

```json
{
  "user_input": "今天下午想和朋友在附近聚会几个小时，先去户外走走聊天，再找一家适合分享的晚餐，不要太远。",
  "read_profile": "mock_world",
  "selected_plan_index": 0,
  "resolved_world_profile": "friends_gathering"
}
```

Public demo response shape remains unchanged:

```json
{
  "run_id": "uuid",
  "status": "awaiting_confirmation",
  "read_profile": "mock_world",
  "selected_plan_id": "uuid",
  "plan_version": {
    "version_number": 1,
    "version_label": "v1",
    "source_run_id": null,
    "source_selected_plan_id": null
  },
  "plans": [],
  "action_count": 0,
  "execution_status": null,
  "feedback_status": null,
  "error": null,
  "clarification": null
}
```

`resolved_world_profile` is an internal behavior example only. It must not be added to the public response.

## 6. Observability

This task should not add a new observability surface.

It must preserve existing demo observability behavior while making the chosen Mock World profile auditable through existing persisted run metadata:

- the created `AgentRun.world_profile` must show `friends_gathering` for the explicit friends-group demo start
- existing internal observability review may already expose `world_profile`; keep that behavior unchanged
- keep trace recording, action ledger recording, and public redaction rules unchanged

## 7. Failure Handling

- If the start request uses `read_profile="amap"`, keep the current AMAP preview behavior unchanged.
- If the resolver cannot classify the prompt as `friends`, fall back to `family_afternoon` rather than adding broader routing heuristics in this task.
- If an explicit friends-group prompt resolves to `friends_gathering` but that fixture is missing or unsupported, fail with the current workflow error path. Do not silently swap to another world.
- If the published friends-group sample unexpectedly enters `awaiting_clarification`, treat that as a sample and test failure and tighten the sample wording instead of relaxing clarification policy in this task.
- Clarify and replan must keep using the source run's persisted `world_profile`.
- Existing public response redaction must remain intact.

## 8. Acceptance Criteria

- [ ] Starting `POST /demo/runs` with the published friends-group Mock World sample returns `status="awaiting_confirmation"`, `read_profile="mock_world"`, `plan_version.version_label="v1"`, `action_count=0`, and at least one public plan.
- [ ] The created `AgentRun` for that start request persists `tool_profile="mock_world"` and `world_profile="friends_gathering"`.
- [ ] Confirming that friends-group run succeeds through the existing confirmation boundary and produces at least one Action Ledger row.
- [ ] A dedicated resolver unit test passes for `friends -> friends_gathering`, while non-friends Mock World inputs still fall back to `family_afternoon`.
- [ ] A dedicated demo API gateway integration test passes for the friends-group happy path.
- [ ] A dedicated Playwright desktop smoke passes for the friends-group public demo sample.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` both publish a friends-group demo input sample.
- [ ] `backend/app/benchmark/cases/friends_gathering_v1.json` remains loadable and registered after the task.
- [ ] The existing family default public demo path remains unchanged.
- [ ] AMAP read-only preview behavior remains unchanged.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_world_profile.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k "friends" -q
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "friends-group"
git diff --check
git status --short
```

If the repo's Playwright grep label changes during implementation, use the exact new test title instead of a broader suite run.

## 10. Expected Commit

```text
feat: add friends group demo path
```

## 11. Notes for the Implementer

Keep this task start-path scoped.

The point is to make the existing `friends_gathering` world demoable through the public product surface, not to design a full scenario-routing framework.

Preferred defaults for this task:

- use the existing deterministic intent parser
- route only `scenario_type == "friends"` to `friends_gathering`
- keep everything else on `family_afternoon`
- keep the current family default sample in the UI
- publish the friends-group sample in docs and automated checks instead of adding new UI controls

The implementer should stop and report back if stable friends-group routing would require:

- changing public demo request or response contracts
- changing clarification or replan semantics
- widening into full multi-profile demo routing
- rewriting the benchmark suite layer
