# Plan: 064 Friends Group Demo Path v1

## 1. Spec Reference

Spec file:

```text
docs/specs/064-friends-group-demo-path-v1.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/customer-demo-chinese-happy-path-e2e`.
- Latest numbered task on disk is `063`.
- `docs/specs/` and `docs/plans/` are continuous and matched through `063`.
- No `064` spec or plan draft exists yet.
- Latest commit is `f806844 test: add chinese customer demo happy-path smoke`, and it created both `063` docs plus the current family demo smoke.
- Current working tree is not clean because `.gitignore` is modified and several unrelated docs and artifacts are untracked:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/artifacts/`
  - `qc`
- Those unrelated local changes must remain unstaged throughout this task.
- The deterministic friends scenario already exists in code:
  - `backend/app/providers/mock_world/fixtures/friends_gathering.json`
  - `backend/app/benchmark/cases/friends_gathering_v1.json`
- The benchmark layer already recognizes `friends_gathering` and its focused loader and suite checks already pass.
- The current public demo start path does not use that world because `backend/app/demo/service.py` hardcodes Mock World starts to `family_afternoon`.
- The current public demo docs and Playwright coverage are still family-only.
- Focused planning-time checks already passed:
  - `python -m pytest tests/test_mock_world_loader.py tests/test_benchmark_suites.py -k "friends_gathering or friends" -q`
  - `python -m pytest tests/integration/test_demo_api_gateway.py -k "amap_preview or start_status_confirm_and_idempotent_replay" -q`

## 3. Files to Add

- `backend/app/demo/world_profile.py` - deterministic helper that resolves the Mock World demo start profile from public user input.
- `tests/test_demo_world_profile.py` - focused unit tests for friends-group profile resolution and fallback behavior.

## 4. Files to Modify

- `backend/app/demo/service.py` - use the new resolver during Mock World demo starts while preserving override precedence and AMAP behavior.
- `tests/integration/test_demo_api_gateway.py` - add a gateway-backed friends-group happy-path test that proves persisted `world_profile="friends_gathering"` and successful confirmation.
- `frontend/e2e/demo.spec.ts` - add an additive desktop smoke for the public friends-group demo sample.
- `docs/WEB_DEMO_README.md` - publish the friends-group sample and manual verification steps.
- `README.md` - add one public demo and API sample for the friends-group Mock World path and clarify that the default UI sample remains family-focused.

## 5. Implementation Steps

1. Add the deterministic demo-start profile resolver.
   Create `backend/app/demo/world_profile.py` with:
   - a default constant for `family_afternoon`
   - a friends constant for `friends_gathering`
   - a function `resolve_mock_world_demo_profile(user_input: str) -> str`
   - implementation rule: parse the input with `DeterministicIntentParser`; return `friends_gathering` only when `intent.scenario_type == "friends"`, otherwise return `family_afternoon`
   - no couple, solo, rainy, or budget routing in this task

2. Wire the resolver into the public demo start path only.
   Update `backend/app/demo/service.py` so that `DemoWorkflowService.start_run(...)`:
   - keeps `override.world_profile` as highest precedence
   - keeps `read_profile="amap"` -> `("amap", "amap_shanghai_live")`
   - resolves the Mock World `world_profile` from `request.user_input` when `read_profile=="mock_world"` and no explicit override is supplied
   - does not change `clarify_run(...)` or `replan_run(...)`; those must keep reusing the source run's stored `world_profile`

3. Add focused resolver unit tests.
   In `tests/test_demo_world_profile.py`, add cases for:
   - explicit friends prompt -> `friends_gathering`
   - existing family prompt -> `family_afternoon`
   - vague or non-friends prompt -> `family_afternoon`
   - an outdoor friends prompt still resolves to `friends_gathering` without any extra dining parsing rule

4. Add the gateway happy-path regression for the real product route.
   In `tests/integration/test_demo_api_gateway.py`:
   - add a dedicated friends-group prompt constant
   - start a run with that prompt on `read_profile="mock_world"`
   - assert the public response reaches `awaiting_confirmation`, exposes plans, keeps `action_count=0`, and does not expose internal keys
   - inspect the persisted `AgentRun` and assert:
     - `tool_profile == "mock_world"`
     - `world_profile == "friends_gathering"`
   - confirm the selected plan and assert:
     - the run reaches `completed`
     - Action Ledger row count becomes `> 0`
     - existing confirmation-boundary guarantees remain true before confirm

5. Add one desktop Playwright smoke for the published sample.
   In `frontend/e2e/demo.spec.ts`:
   - add a dedicated friends-group sample prompt constant
   - add a test title that contains `friends-group`
   - start the public page with that sample
   - assert `awaiting_confirmation`, `v1`, `action_count=0`, confirm button visible, and no AMAP read-only notice
   - click confirm and assert the run reaches `completed` and action count becomes `> 0`
   - keep the existing family smokes unchanged

6. Publish the sample in docs without changing the default UI sample.
   Update `docs/WEB_DEMO_README.md`:
   - add a `Friends Group Happy Path` subsection under `Manual Demo Flow`
   - include the exact published prompt
   - describe the expected public behavior and confirmation boundary
   Update `README.md`:
   - add one friends-group `curl` or sample start example in the Web Demo API section
   - clarify that the default UI sample remains the family afternoon review path, but explicit friends prompts on Mock World now route to the `friends_gathering` world

7. Verify and stage only task files.
   Run the commands in section 7.
   Before staging, confirm unrelated local changes remain unstaged:
   - `.gitignore`
   - `docs/NEXT_PHASE_ROADMAP.md`
   - `docs/TASK_WORKFLOW_PROMPTS.md`
   - `docs/COMPETITION_SUBMISSION_DESIGN.md`
   - `docs/artifacts/`
   - `qc`

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_world_profile.py` for deterministic friends-group routing and fallback behavior
- Integration tests:
  - `tests/integration/test_demo_api_gateway.py` for friends-group start plus confirm happy path and persisted `world_profile`
- Browser smoke tests:
  - `frontend/e2e/demo.spec.ts` desktop friends-group smoke
- Regression checks:
  - keep the existing family public demo flow unchanged
  - keep AMAP read-only preview unchanged
  - do not broaden into clarification or replan world switching

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_world_profile.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k "friends" -q
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "friends-group"
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add friends group demo path
```

Expected commands:

```bash
git status --short
git add backend/app/demo/world_profile.py
git add backend/app/demo/service.py
git add tests/test_demo_world_profile.py
git add tests/integration/test_demo_api_gateway.py
git add frontend/e2e/demo.spec.ts
git add docs/WEB_DEMO_README.md
git add README.md
git diff --cached --check
git commit -m "feat: add friends group demo path"
git push
```

The implementer must confirm that unrelated local docs, artifacts, `qc`, `.gitignore`, `.env`, secrets, and runtime files are not staged.

## 9. Out-of-scope Changes

- Do not generalize demo-world routing beyond the explicit friends-group mapping.
- Do not add or change public request fields, response fields, or UI scenario selectors.
- Do not change the default family sample in `frontend/src/App.tsx`.
- Do not change clarification flow, replan behavior, plan versioning, AMAP preview behavior, or benchmark suite membership.
- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not rewrite the `friends_gathering` fixture or benchmark case unless a focused failing verification proves it is required for this task.
- Do not stage unrelated local docs or generated artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/064-friends-group-demo-path-v1.md`.
- [ ] Mock World demo start resolution now routes explicit friends prompts to `friends_gathering`.
- [ ] Non-friends Mock World demo starts still fall back to `family_afternoon`.
- [ ] `override.world_profile` and AMAP behavior remain intact.
- [ ] The friends-group gateway test proves persisted `world_profile="friends_gathering"` and successful confirm-to-complete flow.
- [ ] The desktop Playwright smoke for the friends-group public sample passes.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` both publish the friends-group demo sample.
- [ ] The existing family default public demo path remains unchanged.
- [ ] The existing `friends_gathering_v1` benchmark case is still loadable and registered.
- [ ] Required verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, unrelated doc draft, or runtime artifact was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- the exact files changed
- the published friends-group sample text
- the verification commands and results
- the persisted `world_profile` observed in the gateway test
- the commit hash
- the push result
- confirmation that unrelated local changes remained unstaged
- any follow-up recommendation, especially whether future work should generalize demo-world routing beyond `friends`
