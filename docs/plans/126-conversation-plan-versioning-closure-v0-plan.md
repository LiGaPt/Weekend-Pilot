# Plan: 126 Conversation and Plan Versioning Closure v0

## 1. Spec Reference

Spec file:

```text
docs/specs/126-conversation-plan-versioning-closure-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
M4. 多轮对话与方案版本
```

## 2. Current Repository Assumptions

- Current branch is `codex/125-mock-world-scenario-coverage-closure-v0`.
- Latest observed commit is `f046090 test: lock mock world scenario coverage closure`.
- Latest tracked task is Task `125`.
- `docs/specs/` and `docs/plans/` match through Task `125`.
- The repository has a historical Task `122` numbering gap and a special `113.5` task; do not backfill or renumber either.
- Existing untracked local files are unrelated and must remain unstaged:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Existing conversation/versioning foundations are already implemented:
  - clarification route and summary models
  - follow-up replan route
  - visible plan version metadata
  - selected-plan index propagation
  - action manifest summary on public plan previews
  - Action Ledger writes after confirmation
  - benchmark multi-turn continuation support
- There is no `tests/test_action_manifest.py`; action manifest coverage is currently embedded in demo schema/service/frontend paths.
- The task should add proof, not redesign runtime behavior.

## 3. Files to Add

- `docs/specs/126-conversation-plan-versioning-closure-v0.md` - task spec created from the approved content.
- `docs/plans/126-conversation-plan-versioning-closure-v0-plan.md` - implementation plan created from the approved content.
- `tests/test_demo_conversation_versioning_closure.py` - preferred focused backend closure regression if an in-memory or existing fixture path can cover the full chain without requiring external services.

If the existing integration helper is the only reliable path, add the test to `tests/integration/test_demo_api_gateway.py` instead of creating `tests/test_demo_conversation_versioning_closure.py`.

## 4. Files to Modify

- `tests/integration/test_demo_api_gateway.py` - add the full-chain closure regression here if the current integration setup already provides database-backed demo service coverage.
- `tests/test_demo_api.py` - modify only if a missing public-safe assertion is better added to existing summary serialization coverage.
- `frontend/src/App.test.tsx` - modify only if backend integration cannot prove selected-plan index binding and the existing unit test needs a stronger non-default-plan branch.
- `frontend/e2e/demo.spec.ts` - modify only if the selected-plan index closure must be proven through the customer UI rather than backend/service tests.
- `README.md` - update only if it does not mention the automated closure verification command after this task.
- `docs/WEB_DEMO_README.md` - update only if it still describes clarification/replan/action manifest closure as manual-only verification.

Do not modify production code unless the new closure test exposes a real regression. If production code must change, keep the fix minimal and stay within the spec.

## 5. Implementation Steps

1. Confirm repository state before editing.
   - Run `git status --short`.
   - Run `git branch --show-current`.
   - Run `git log --oneline -5`.
   - Confirm latest task docs are Task `125`.
   - Confirm unrelated untracked docs remain unstaged.

2. Inspect existing test helpers and service contracts.
   - Read `tests/integration/test_demo_api_gateway.py`.
   - Read `tests/test_demo_clarification.py`.
   - Read `tests/test_demo_replan.py`.
   - Read `tests/test_demo_versioning.py`.
   - Read `tests/test_demo_api.py`.
   - Read `frontend/src/App.test.tsx` and `frontend/e2e/demo.spec.ts` only if frontend selected-plan binding needs additional coverage.
   - Identify whether the full chain should be tested through:
     - FastAPI `TestClient`
     - `DemoWorkflowService`
     - existing integration gateway fixture
     - frontend mocked E2E

3. Inspect implementation entrypoints before writing the test.
   - Read `backend/app/demo/service.py`.
   - Read `backend/app/demo/schemas.py`.
   - Read `backend/app/demo/versioning.py`.
   - Read `backend/app/demo/action_manifest.py`.
   - Read plan and action ledger repositories used by demo confirmation.
   - Locate the existing helper or repository method for counting Action Ledger rows by run or chain.

4. Choose the closure test location.
   - Prefer `tests/test_demo_conversation_versioning_closure.py` if the current non-integration tests can create a database-backed demo service with existing fixtures.
   - Prefer `tests/integration/test_demo_api_gateway.py` if the chain requires PostgreSQL/Redis/alembic integration that is already established there.
   - Do not create duplicate partial tests across both locations unless each covers a distinct necessary layer.

5. Add the closure regression.
   - Name the test `test_conversation_clarify_replan_manifest_confirm_closure`.
   - Start with a vague Mock World request expected to enter clarification:
     - user input: `Plan something nearby for later.`
     - `read_profile = "mock_world"`
     - `mock_world_profile = "solo_afternoon"` unless existing tests prove another profile is more stable.
   - Assert start summary:
     - `status == "awaiting_clarification"`
     - `plans == []`
     - `selected_plan_id is None`
     - `action_count == 0`
     - `clarification is not None`
     - `plan_version.version_label == "v1"`

6. Continue from clarification.
   - Call `clarify_run` or `POST /demo/runs/{run_id}/clarify` with:
     - `This afternoon I want a nearby solo outing for a few hours.`
     - `selected_plan_index = 0`
   - Assert clarify summary:
     - `status == "awaiting_confirmation"`
     - `plan_version.version_label == "v1"`
     - `selected_plan_id is not None`
     - `len(plans) >= 2`
   - Fail with a clear assertion message if fewer than two plans are returned, because non-default selected-plan binding cannot be proven.

7. Select the non-default source plan.
   - Use `source_plan_index = 1`.
   - Store `source_plan_id = clarify_summary.plans[1].plan_id`.
   - If needed, call the existing select-plan service/helper before replan only if current backend semantics require source plan selection separate from `selected_plan_index`.
   - Do not mutate old runs manually.

8. Replan from the non-default source plan.
   - Call `replan_run` or `POST /demo/runs/{clarify_run_id}/replan` with:
     - `Keep it nearby, but make it indoor this time.`
     - `selected_plan_index = 1`
   - Assert replan summary:
     - `status == "awaiting_confirmation"`
     - `plan_version.version_label == "v2"`
     - `plan_version.source_run_id == clarify_run_id`
     - `plan_version.source_selected_plan_id == source_plan_id`
     - `selected_plan_id is not None`
     - selected public plan has non-null `action_manifest`

9. Assert pre-confirmation action manifest.
   - Find the selected plan in the replan summary.
   - Assert:
     - `action_manifest.source == "proposed_actions"`
     - `action_manifest.action_count >= 1`
     - `len(action_manifest.actions) >= 1`
     - each action has valid `execution_order`, `action_type`, and `target_id`
   - Avoid brittle assertions on generated action refs or full payload previews.

10. Assert no writes before confirmation.
    - Use existing repositories or test helper to count Action Ledger rows for all run IDs in the chain:
      - start clarification run
      - clarify plan-bearing run
      - replan v2 run
    - Assert no successful write-side execution rows exist before confirm.
    - If the repository stores proposed actions separately from executed ledger rows, assert only executed/confirmed ledger rows are absent.

11. Confirm the final v2 run.
    - Call `confirm_run` or `POST /demo/runs/{replan_run_id}/confirm`.
    - Assert final summary:
      - `status == "completed"`
      - `execution_status == "succeeded"`
      - `feedback_status == "completed"`
      - `plan_version.version_label == "v2"`
      - selected plan remains tied to the final replan run
    - If current contract changes manifest source after confirmation, assert selected plan manifest has `source == "confirmed_actions"`.

12. Assert writes occur only after confirmation.
    - Count Action Ledger rows for the final run after confirm.
    - Assert at least one confirmed action row exists.
    - Assert no action rows were attached to the initial clarification-only run.
    - Assert executed actions correspond to the final selected plan's confirmed actions where current repository fields make that check possible.

13. Assert old runs remain readable and unchanged.
    - Read back the original clarification source run.
    - Read back the v1 plan-bearing run.
    - Assert the original source remains `awaiting_clarification`.
    - Assert the v1 plan-bearing run remains `awaiting_confirmation` with `version_label == "v1"`.
    - Assert v2 did not overwrite v1 selected plan metadata.

14. Assert public-safe redaction remains intact.
    - Dump every public summary with `model_dump(mode="json")`.
    - Assert the dumped payload does not contain:
      - `session_id`
      - `conversation`
      - `tool_events`
      - `tool_event_count`
      - `node_history`
      - `trace`
      - `trace_id`
      - `agent_roles`
      - `observability_status`
    - Keep this assertion local to public summary payloads, not internal repository state.

15. Run the new focused test.
    - If added as `tests/test_demo_conversation_versioning_closure.py`, run:
      - `python -m pytest tests/test_demo_conversation_versioning_closure.py -q`
    - If added to integration tests, run the specific test node with `-v`.
    - Fix only actual implementation or test-fixture issues required by the spec.

16. Run existing backend focused tests.
    - Run:
      - `python -m pytest tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py tests/test_demo_api.py -q`
    - Run:
      - `python -m pytest tests/test_benchmark_harness.py -q`
    - Run integration command if the test requires it:
      - `python -m pytest tests/integration/test_demo_api_gateway.py -v`

17. Run frontend focused tests if frontend files changed.
    - If `frontend/src/App.test.tsx` changed, run:
      - `npm --prefix frontend run test -- --run src/App.test.tsx`
    - If `frontend/e2e/demo.spec.ts` changed, run:
      - `npm --prefix frontend run e2e`
    - If no frontend files changed, do not require frontend E2E unless the project convention already requires it for this closure.

18. Update docs only if needed.
    - If adding a new backend closure test, consider adding one concise verification-command line to `docs/WEB_DEMO_README.md`.
    - Do not rewrite existing feature docs or historical task docs.
    - Do not modify `docs/TASK_INFO.md` unless explicitly requested; it is currently untracked local context.

19. Run hygiene checks.
    - Run `git diff --check`.
    - Run `git status --short`.
    - Confirm only intended files changed.
    - Confirm untracked local docs remain unstaged.

20. Stage and commit.
    - Stage only:
      - Task 126 spec
      - Task 126 plan
      - new or modified closure test
      - any intentionally updated README/demo docs
      - any minimal production fix if the closure test exposed a real bug
    - Run `git diff --cached --check`.
    - Commit with:
      - `test: lock conversation and plan versioning closure`

21. Push.
    - If still on `codex/125-mock-world-scenario-coverage-closure-v0`, create a new branch before committing:
      - `git switch -c codex/126-conversation-plan-versioning-closure-v0`
    - Push with:
      - `git push -u origin codex/126-conversation-plan-versioning-closure-v0`

## 6. Testing Plan

- Unit / service tests:
  - Add `test_conversation_clarify_replan_manifest_confirm_closure` to the chosen backend test module.
  - Verify clarification status, v1 continuation, v2 replan, selected source plan binding, pre-confirmation action manifest, confirmation boundary, and post-confirmation execution.

- Existing backend regression tests:
  - `tests/test_demo_clarification.py`
  - `tests/test_demo_replan.py`
  - `tests/test_demo_versioning.py`
  - `tests/test_demo_api.py`
  - `tests/test_benchmark_harness.py`

- Integration tests:
  - `tests/integration/test_demo_api_gateway.py` if the closure path uses the integration gateway/database setup.

- Frontend tests:
  - `frontend/src/App.test.tsx` only if selected-plan index coverage is strengthened at UI unit level.
  - `frontend/e2e/demo.spec.ts` only if selected-plan index closure must be proven through browser/request interception.

- Documentation checks:
  - Confirm any changed docs mention the new verification command accurately.
  - Confirm docs do not expose internal session/conversation payloads as public API.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py tests/test_demo_api.py -q
python -m pytest tests/test_benchmark_harness.py -q
python -m pytest tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

If the closure test is added as a new non-integration module, also run:

```bash
python -m pytest tests/test_demo_conversation_versioning_closure.py -q
```

If frontend files change, also run:

```bash
npm --prefix frontend run test -- --run src/App.test.tsx
npm --prefix frontend run e2e
```

Commands to run after staging:

```bash
git diff --cached --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
test: lock conversation and plan versioning closure
```

Expected commands:

```bash
git status --short
git switch -c codex/126-conversation-plan-versioning-closure-v0
git add docs/specs/126-conversation-plan-versioning-closure-v0.md docs/plans/126-conversation-plan-versioning-closure-v0-plan.md
git add tests/test_demo_conversation_versioning_closure.py tests/integration/test_demo_api_gateway.py tests/test_demo_api.py frontend/src/App.test.tsx frontend/e2e/demo.spec.ts README.md docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "test: lock conversation and plan versioning closure"
git push -u origin codex/126-conversation-plan-versioning-closure-v0
```

Only stage files that actually changed. Do not stage unrelated untracked files or generated artifacts.

## 9. Out-of-scope Changes

- Do not add migrations.
- Do not add dependencies.
- Do not change public API schemas.
- Do not change action manifest schema.
- Do not change plan versioning rules.
- Do not change benchmark report schemas.
- Do not add Mock World profiles or benchmark cases.
- Do not alter recovery/safe-stop behavior.
- Do not alter AMap preview behavior.
- Do not rewrite existing task history.
- Do not run formatters that rewrite unrelated files.
- Do not commit generated `var/` artifacts, caches, virtual environments, `.env`, credentials, or secrets.
- Do not stage:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/126-conversation-plan-versioning-closure-v0.md`.
- [ ] The task stayed a closure/regression slice and did not become a feature expansion.
- [ ] The automated test covers `start -> clarify -> replan -> confirm`.
- [ ] The clarification source run remains `v1` and has no plans or selected plan.
- [ ] The clarification continuation reaches plan-bearing `v1`.
- [ ] The replan run reaches `v2`.
- [ ] The replan source selected plan ID matches the non-default v1 plan selected by index.
- [ ] The v2 selected plan exposes `action_manifest.source = proposed_actions` before confirmation.
- [ ] No write-side Action Ledger rows exist before confirmation.
- [ ] Confirmation executes only after confirming the final v2 run.
- [ ] Post-confirmation execution and feedback succeed.
- [ ] Public summaries do not expose session IDs, raw conversation history, raw tool events, trace payloads, or internal node history.
- [ ] Existing focused demo and benchmark tests passed.
- [ ] Frontend tests passed if frontend files changed.
- [ ] `git diff --check` and `git diff --cached --check` passed.
- [ ] No generated artifacts, secrets, or unrelated local docs were committed.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.

## 11. Handoff Notes

After finishing, report back:

- changed files
- whether production code changed or the task was tests/docs only
- location and name of the new closure regression
- exact conversation chain covered by the test
- selected non-default source plan index used in the test
- final confirmed version sequence, expected `v1 -> v1 -> v2 -> v2`
- verification commands and results
- whether frontend tests were needed
- commit hash
- push result
- confirmation that unrelated untracked files were not staged
- any follow-up recommendation, likely Task `127 Recovery and safe-stop evidence closure`
