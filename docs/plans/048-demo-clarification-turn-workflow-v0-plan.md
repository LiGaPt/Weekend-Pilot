# Plan: 048 Demo Clarification Turn Workflow v0

## 1. Spec Reference

Spec file:

```text
docs/specs/048-demo-clarification-turn-workflow-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/memory-query-policy-baseline-v0`.
- Latest code commit is `6103c44 feat: add memory query policy baseline`.
- In the working tree, `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `047`.
- In git-tracked history, the numbered spec/plan chain is continuous and matched only through `046`; the `047` doc pair is currently untracked local state.
- The current repository already has the M4 foundations needed for clarification continuation:
  - durable `conversation_sessions`
  - durable `conversation_turns`
  - same-session `POST /demo/runs/{run_id}/replan`
  - public `plan_version`
  - public `action_manifest`
- The current repository does not yet have:
  - workflow status `awaiting_clarification`
  - a deterministic pre-planning clarification gate
  - a public `POST /demo/runs/{run_id}/clarify` endpoint
- The current workflow still routes every successful `generate_queries` step into search execution, and `ask_user` recovery still collapses to `failed`.
- A focused non-integration smoke check already passed in the current workspace:

```text
python -m pytest tests/test_demo_api.py tests/test_demo_replan.py tests/test_langgraph_workflow.py tests/test_memory_query_policy.py -q
34 passed in 1.04s
```

- Pre-existing unrelated untracked paths currently include:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/specs/047-memory-query-policy-baseline-v0.md`
  - `docs/plans/047-memory-query-policy-baseline-v0-plan.md`
  - `qc`
  - `var/`
- Those paths must remain unstaged during task `048`.

## 3. Files to Add

- `backend/app/planning/clarification_policy.py` - pure deterministic pre-planning clarification gate and compact clarification summary model.
- `tests/test_demo_clarification.py` - unit tests for clarification-policy detection and public clarification-summary behavior.

## 4. Files to Modify

- `backend/app/planning/__init__.py` - export the new clarification policy helper and summary model.
- `backend/app/demo/__init__.py` - export the new clarify request and clarification summary models.
- `backend/app/demo/replan.py` - extend `build_follow_up_intent(...)` so later turns can merge explicit activity-style signals.
- `backend/app/demo/schemas.py` - add `DemoClarificationSummary`, `DemoClarifyRunRequest`, and nullable `DemoRunSummary.clarification`.
- `backend/app/demo/service.py` - add clarification summary building, start-run clarification turn persistence, clarify endpoint workflow, and clarification-specific plan-version behavior.
- `backend/app/demo/versioning.py` - add a clarification-specific version helper that preserves the source version number when the source run has no selected plan.
- `backend/app/api/demo.py` - expose `POST /demo/runs/{run_id}/clarify`.
- `backend/app/workflow/graph.py` - add conditional routing after `generate_queries`.
- `backend/app/workflow/nodes.py` - apply clarification policy after memory policy, persist workflow clarification metadata, and stop early in `awaiting_clarification`.
- `backend/app/workflow/runner.py` - treat `awaiting_clarification` as a valid workflow result and observability boundary.
- `backend/app/workflow/state.py` - extend `WorkflowStatus` with `awaiting_clarification`.
- `tests/test_demo_api.py` - add route exposure, request validation, and summary serialization checks for clarification.
- `tests/test_demo_replan.py` - add or update follow-up intent merge coverage for explicit activity-style replies.
- `tests/test_demo_versioning.py` - add coverage for clarification-only runs preserving `v1`.
- `tests/test_langgraph_workflow.py` - add graph-route and runner-status coverage for `awaiting_clarification`.
- `tests/integration/test_demo_api_gateway.py` - add end-to-end clarification workflow coverage with same-session persistence.
- `README.md` - document `awaiting_clarification` and the new clarify endpoint.
- `docs/WEB_DEMO_README.md` - document the clarify request path and same-session continuation semantics.

## 5. Implementation Steps

1. Write the failing unit tests first.
   Update `tests/test_demo_api.py` to require:
   - `/demo/runs/{run_id}/clarify` is exposed
   - `DemoClarifyRunRequest(user_input="")` fails validation
   - `DemoRunSummary` can serialize a clarification-pending payload with `clarification.prompt` and `clarification.missing_fields`
   - non-clarification runs still allow `clarification = null`

2. Add failing clarification-policy unit coverage before implementation.
   Create `tests/test_demo_clarification.py` with exact assertions for:
   - an input with no explicit scenario and no explicit time window returns `missing_fields == ["scenario_or_participants", "time_window"]`
   - an input with explicit solo/family but no time returns only `["time_window"]`
   - an input with explicit time but no participants returns only `["scenario_or_participants"]`
   - a sufficiently specific request returns `None`
   - the exact Chinese question text matches the spec for each missing-field combination

3. Extend follow-up intent merge tests before touching the helper.
   In `tests/test_demo_replan.py`, add a case where:
   - the base turn already establishes scenario/time
   - the follow-up turn only adds an explicit supported style such as `indoor`
   - the merged intent preserves prior scenario/time and now includes `indoor`
   Keep existing merge tests unchanged.

4. Add the failing workflow/runner tests.
   In `tests/test_langgraph_workflow.py`:
   - add a test for the new route after `generate_queries`
   - add a graph-level stub case where `generate_queries` returns `status = "awaiting_clarification"` and the graph ends before `execute_searches`
   - add a runner-status test so `awaiting_clarification` is not coerced to `error`

5. Add the failing versioning tests.
   In `tests/test_demo_versioning.py`, add exact assertions for:
   - a clarification continuation from a `v1` source with no selected plan stays at `version_number = 1`
   - the returned metadata still records `source_run_id`
   - normal replan increment behavior remains unchanged

6. Implement the pure clarification policy.
   Add `backend/app/planning/clarification_policy.py` with:
   - `ClarificationPolicySummary`
   - `apply_clarification_policy(intent)`
   Rules to implement exactly:
   - policy version is `clarification_policy_v0`
   - only `scenario_or_participants` and `time_window` can block
   - missing detection logic must match the spec exactly
   - question text must match the exact Chinese strings from the spec
   - return `None` when nothing is missing
   Then export the helper from `backend/app/planning/__init__.py`.

7. Extend follow-up intent merging.
   In `backend/app/demo/replan.py`, keep the current chronological “latest explicit signal wins” model and add one more explicit branch:
   - if `signals.activity_preferences` is true, replace `merged_intent.activity_preferences` with the later turn’s supported explicit activity-style preferences
   Do not widen merge behavior beyond currently supported parser fields.

8. Wire clarification into workflow state and routing.
   In `backend/app/workflow/state.py`, add `awaiting_clarification` to `WorkflowStatus`.
   In `backend/app/workflow/nodes.py`:
   - keep the existing parse-intent and memory-policy behavior
   - in `generate_queries(...)`, call `apply_clarification_policy(...)` after `apply_memory_query_policy(...)`
   - when clarification is required:
     - persist the compact clarification summary under `metadata_json["workflow"]["clarification"]`
     - update the run status to `awaiting_clarification`
     - return early with `status="awaiting_clarification"`
     - do not build a query plan
     - do not create supervisor assignments
   - when clarification is not required, keep the current query-planning path unchanged
   In `backend/app/workflow/graph.py`:
   - replace the unconditional `generate_queries -> execute_searches` edge with a conditional route
   - end the graph immediately on `awaiting_clarification`
   In `backend/app/workflow/runner.py`:
   - accept `awaiting_clarification` in `_status_or_error(...)`
   - include `awaiting_clarification` in the set of statuses that trigger `_record_observability(...)`

9. Extend demo schemas, versioning, and service behavior.
   In `backend/app/demo/schemas.py` and `backend/app/demo/__init__.py`:
   - add `DemoClarificationSummary`
   - add `DemoClarifyRunRequest`
   - add nullable `DemoRunSummary.clarification`
   In `backend/app/demo/versioning.py`:
   - add a dedicated helper for clarification continuations from source runs with no selected plan
   - keep the returned `version_number` unchanged from the source run
   - keep `source_selected_plan_id = null`
   In `backend/app/demo/service.py`:
   - update start-run post-processing so a run in `awaiting_clarification` writes:
     - `user_request`
     - `assistant_clarification_request`
   - do not write `assistant_plan_options` for clarification-pending runs
   - build public `clarification` from persisted workflow metadata
   - add a new `clarify_run(...)` method that:
     - validates the source run
     - merges all session user turns plus the new reply through `build_follow_up_intent(...)`
     - starts a new workflow run in the same session using `existing_user_id`, `session_id`, and `intent_override`
     - appends `user_clarification_reply`
     - appends `assistant_plan_options` when the new run reaches plan presentation
     - appends `assistant_clarification_request` when the new run still lacks required fields
     - persists `demo.conversation.mode = "clarification_turn_v0"`
     - uses the clarification-specific plan-version helper when the source run has no selected plan
   - keep existing replan, confirm, and decline behavior unchanged
   In `backend/app/api/demo.py`, add `POST /demo/runs/{run_id}/clarify`.

10. Add the integration proof in one focused gateway test.
    In `tests/integration/test_demo_api_gateway.py`, add a single end-to-end flow that:
    - starts a vague run such as `想周末出去玩一下。`
    - asserts the response is `awaiting_clarification`
    - asserts `plans == []`, `selected_plan_id == null`, and `clarification.missing_fields` match the spec
    - verifies the source run has a session plus `user_request` and `assistant_clarification_request` turns
    - posts `POST /demo/runs/{run_id}/clarify` with a sufficiently specific reply such as `今天下午一个人出门玩几个小时，别太远。`
    - asserts the continuation run has a new `run_id`, reuses the same `session_id`, and reaches `awaiting_confirmation`
    - asserts the continuation run still reports `plan_version.version_number == 1`
    - asserts `user_clarification_reply` plus `assistant_plan_options` were appended in order
    - asserts the source run remains unchanged and still queryable

11. Update documentation last.
    In `README.md` and `docs/WEB_DEMO_README.md`:
    - document that start-run can now return `awaiting_clarification`
    - add the `POST /demo/runs/{run_id}/clarify` curl example
    - note that clarification-only runs do not advance the visible plan version number

12. Run focused verification and stage only task files.
    Run the commands from section 7 exactly.
    Before staging, confirm these unrelated paths remain unstaged if they still exist:
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/specs/047-memory-query-policy-baseline-v0.md`
    - `docs/plans/047-memory-query-policy-baseline-v0-plan.md`
    - `qc`
    - `var/`

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_api.py` for route exposure, request validation, and response serialization
  - `tests/test_demo_clarification.py` for pure clarification-policy behavior
  - `tests/test_demo_replan.py` for follow-up intent merge with explicit activity-style replies
  - `tests/test_demo_versioning.py` for clarification-specific version semantics
  - `tests/test_langgraph_workflow.py` for graph routing and runner status handling
- Integration tests:
  - `tests/integration/test_demo_api_gateway.py` for same-session clarification continuation and conversation-turn persistence
- Smoke tests:
  - run the full verification command set from section 7
- Regression guard:
  - no Alembic changes
  - no dependency changes
  - no frontend UI changes
  - no benchmark or provider contract changes

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py tests/test_langgraph_workflow.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add demo clarification turn workflow
```

Expected commands:

```bash
git status --short
git add backend/app/planning/clarification_policy.py
git add backend/app/planning/__init__.py
git add backend/app/demo/__init__.py
git add backend/app/demo/replan.py
git add backend/app/demo/schemas.py
git add backend/app/demo/service.py
git add backend/app/demo/versioning.py
git add backend/app/api/demo.py
git add backend/app/workflow/graph.py
git add backend/app/workflow/nodes.py
git add backend/app/workflow/runner.py
git add backend/app/workflow/state.py
git add tests/test_demo_api.py
git add tests/test_demo_clarification.py
git add tests/test_demo_replan.py
git add tests/test_demo_versioning.py
git add tests/test_langgraph_workflow.py
git add tests/integration/test_demo_api_gateway.py
git add README.md
git add docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: add demo clarification turn workflow"
git push -u origin codex/demo-clarification-turn-workflow-v0
```

The implementer must confirm that `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/specs/047-memory-query-policy-baseline-v0.md`, `docs/plans/047-memory-query-policy-baseline-v0-plan.md`, `qc`, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not add frontend clarification controls in `frontend/`.
- Do not add origin parsing, budget parsing, or richer preference elicitation.
- Do not convert semantic-validator or recovery `ask_user` decisions into the same clarification flow.
- Do not add or modify Alembic revisions, tables, columns, or indexes.
- Do not add new dependencies.
- Do not change benchmark harness, replay, provider, or observability API contracts.
- Do not stage unrelated local documentation files or runtime artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/048-demo-clarification-turn-workflow-v0.md`.
- [ ] `awaiting_clarification` is a real workflow status, not an overloaded error path.
- [ ] Clarification detection blocks only `scenario_or_participants` and `time_window`.
- [ ] The exact Chinese clarification prompts match the spec.
- [ ] A vague start-run request returns `plans = []` and a non-null clarification summary.
- [ ] `POST /demo/runs/{run_id}/clarify` creates a new run in the same session.
- [ ] Clarification-only runs keep `v1` instead of incrementing to `v2`.
- [ ] `build_follow_up_intent(...)` now preserves later explicit activity-style signals.
- [ ] No Alembic revision or dependency changed.
- [ ] Required unit and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, runtime artifact, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- One example request that now returns `awaiting_clarification`.
- One example clarification reply that continues the same session into `awaiting_confirmation`.
- The exact persisted `workflow.clarification` metadata shape.
- Confirmation that clarification-only runs kept `plan_version.version_number = 1`.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that unrelated untracked files remained unstaged.
- Any remaining follow-up limitation, especially that frontend clarify UI, origin/budget parsing, and general recovery `ask_user` handling remain future tasks.
