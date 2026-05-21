# Plan: 044 Demo Follow-up Replan Workflow v0

## 1. Spec Reference

Spec file:

```text
docs/specs/044-demo-follow-up-replan-v0.md
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

- Current branch is `codex/session-conversation-data-model-v0`.
- Latest completed numbered task is `043`.
- Latest commit is `315f20e feat: add session conversation data model`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `043`.
- There is no `044` spec, `044` plan, or `codex/*044*` branch yet.
- Focused `043` unit verification already passed in this planning session:
  - `python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_api.py -q`
- The demo API currently exposes only:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- Task `043` added durable `conversation_sessions`, `conversation_turns`, and nullable `agent_runs.session_id`, but it did not add follow-up reuse or a public replan API.
- `DemoWorkflowService._ensure_conversation_baseline(...)` currently checks for an assistant turn at the session level, which will block multi-run assistant turns unless refactored.
- `WeekendPilotWorkflowNodes.initialize(...)` currently reuses users only by `external_user_id`; if a caller omits `external_user_id`, a second run would create a new user unless this task adds explicit `existing_user_id` support.
- There is no existing migration work required for this task.
- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.

## 3. Files to Add

- `backend/app/demo/replan.py` - deterministic follow-up intent merge helpers for demo conversation turns.
- `tests/test_demo_replan.py` - unit tests for follow-up intent merge behavior.

## 4. Files to Modify

- `backend/app/api/demo.py` - add `POST /demo/runs/{run_id}/replan`.
- `backend/app/demo/__init__.py` - export the new replan request schema.
- `backend/app/demo/schemas.py` - add `DemoReplanRunRequest`.
- `backend/app/demo/service.py` - implement `replan_run(...)`, refactor conversation turn helpers to be run-scoped, and persist compact conversation-lineage metadata.
- `backend/app/planning/schemas.py` - add any additive parser-signal model needed by the merge helper.
- `backend/app/planning/intent_parser.py` - expose parser signal extraction or equivalent additive support required by deterministic follow-up merge.
- `backend/app/workflow/schemas.py` - add additive `existing_user_id`, `session_id`, and `intent_override` request fields.
- `backend/app/workflow/state.py` - add additive state fields for the new workflow overrides.
- `backend/app/workflow/runner.py` - carry the new workflow override fields into the initial state.
- `backend/app/workflow/nodes.py` - reuse existing users/sessions and honor `intent_override`.
- `README.md` - add the new demo replan endpoint example and behavior note.
- `docs/WEB_DEMO_README.md` - add the new follow-up manual/API flow and regression command context.
- `tests/test_demo_api.py` - route exposure, request validation, and public-payload regression.
- `tests/test_intent_parser.py` - additive parser-signal regression coverage if parser helpers are exposed.
- `tests/integration/test_langgraph_workflow_gateway.py` - workflow override integration coverage for existing user plus session reuse.
- `tests/integration/test_demo_api_gateway.py` - demo API follow-up replan integration coverage.

## 5. Implementation Steps

1. Add the failing public API contract tests first.
   Update `tests/test_demo_api.py` to assert:
   - `/demo/runs/{run_id}/replan` exists
   - `DemoReplanRunRequest(user_input="")` fails validation
   - the public `DemoRunSummary` shape still omits `session_id` and conversation fields

2. Add the failing follow-up merge unit tests.
   Create `tests/test_demo_replan.py` for the deterministic follow-up merge helper.
   Cover at least:
   - a base family request plus a solo follow-up, where the latest explicit scenario/participant signal wins
   - a vague follow-up with no supported override signals, where earlier supported constraints remain
   - a dining-preference follow-up where the later supported dining signal wins
   Keep the merge helper focused on user-authored turn text only.

3. Add additive parser support for merge signals.
   In `backend/app/planning/intent_parser.py`, add a public additive helper that returns both:
   - the parsed `LocalLifeIntent`
   - signal flags or equivalent metadata showing which supported fields were explicitly present in that turn
   Keep `parse(...)` backward-compatible for all existing callers.
   If needed, add the additive signal model in `backend/app/planning/schemas.py`.
   Extend `tests/test_intent_parser.py` only for the new additive helper behavior; do not rewrite existing parser semantics.

4. Implement the demo follow-up merge helper.
   Add `backend/app/demo/replan.py`.
   It should:
   - accept ordered user-turn texts
   - parse each turn with the additive parser helper
   - merge chronologically
   - let the latest explicit supported signal win for:
     - scenario / participants / child-friendly implication
     - time window / duration
     - max distance
     - dining preferences
   - ignore unsupported domains such as origin and budget
   - produce a final `LocalLifeIntent` whose `raw_text` is all user turns joined in chronological order
   Keep this helper demo-only; do not move multi-turn logic into the benchmark or generic workflow packages in this task.

5. Add the failing workflow integration test for overrides.
   In `tests/integration/test_langgraph_workflow_gateway.py`, add one test that:
   - creates a user row with no `external_id`
   - creates a `conversation_sessions` row for that user
   - runs `WeekendPilotWorkflowRunner.run(...)` with `existing_user_id`, `session_id`, and an `intent_override`
   - asserts the persisted `agent_runs` row reuses the provided user and session
   - asserts no replacement user is created
   This test should prove the additive workflow contract independent of the demo API.

6. Implement additive workflow override support.
   Update:
   - `backend/app/workflow/schemas.py`
   - `backend/app/workflow/state.py`
   - `backend/app/workflow/runner.py`
   - `backend/app/workflow/nodes.py`
   Required behavior:
   - `existing_user_id` is optional and additive
   - `session_id` is optional and additive
   - `intent_override` is optional and additive
   - `initialize(...)` reuses `existing_user_id` when present and passes `session_id` into the new run row
   - `parse_intent(...)` uses `intent_override` directly when present
   Keep all existing workflow callers working unchanged.

7. Add the failing demo API gateway replan test.
   In `tests/integration/test_demo_api_gateway.py`, add one end-to-end flow:
   - start an initial run through `POST /demo/runs`
   - capture the original `run_id`
   - call `POST /demo/runs/{run_id}/replan` with a supported follow-up message
   - assert the response returns a different `run_id`
   - assert the new run shares the same `session_id` and `user_id`
   - assert the source run remains unchanged
   - assert the session now contains exactly four ordered turns:
     - `user_request`
     - `assistant_plan_options`
     - `user_follow_up`
     - `assistant_replan_options`
   - assert the assistant replan turn payload is compact and does not embed full plan JSON
   - assert the public response still omits session and conversation fields

8. Refactor `DemoWorkflowService` conversation helpers before adding the replan endpoint.
   In `backend/app/demo/service.py`:
   - split the current baseline logic into smaller run-scoped helpers
   - replace session-global assistant-turn deduplication with a per-run check using `ConversationTurnRepository.list_for_run(...)`
   - keep `start_run(...)` behavior unchanged for initial runs
   This refactor is required so a second run in the same session can append its own assistant turn.

9. Implement the replan request schema and route.
   In:
   - `backend/app/demo/schemas.py`
   - `backend/app/demo/__init__.py`
   - `backend/app/api/demo.py`
   Add `DemoReplanRunRequest` and `POST /demo/runs/{run_id}/replan`.
   Keep the response model as `DemoRunSummary`.

10. Implement `DemoWorkflowService.replan_run(...)`.
    In `backend/app/demo/service.py`, add the new public method and wire it to the route.
    Exact flow:
    - load the source run and validate the allowed statuses
    - require `user_id` and `session_id`
    - load the session row and verify it belongs to the source user
    - load the source user row for `display_name` and `external_id`
    - load the source selected plan if one exists
    - append one `user_follow_up` turn with compact payload referencing the source run and source selected plan
    - build the merged `LocalLifeIntent` from the full ordered session user-turn list including the new follow-up
    - invoke `WeekendPilotWorkflowRunner.run(...)` with:
      - latest `user_input`
      - source case/tool/world/agent/prompt/failure profiles
      - `auto_confirm=False`
      - new `selected_plan_index`
      - `existing_user_id=source_run.user_id`
      - `session_id=source_run.session_id`
      - `intent_override=merged_intent`
      - `display_name` and `external_user_id` copied from the source user row
    - if `run_id is None`, raise `DemoServiceError(500, ...)` and rely on rollback to remove the provisional follow-up turn
    - load the new run
    - write `metadata_json["demo"]["conversation"]` with:
      - `mode`
      - `source_run_id`
      - `trigger_turn_id`
      - `source_selected_plan_id`
    - append `assistant_replan_options` only if the new run has a selected plan
    - commit and return `build_summary(new_run_id)`
    - if the new run exists but has no selected plan, commit the new run and the `user_follow_up` turn, skip the assistant turn, and still return `build_summary(new_run_id)`

11. Update user-facing docs for the new API slice.
    Update `README.md` and `docs/WEB_DEMO_README.md` with:
    - one `curl` example for `POST /demo/runs/{run_id}/replan`
    - a short note that the response returns a new `run_id`
    - a short note that the internal conversation session is reused and remains non-public

12. Run the focused verification suite and stage only relevant files.
    Run the commands from section 7.
    Before staging, confirm that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` remain unstaged.

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_api.py` for route exposure, request validation, and public response shape
  - `tests/test_demo_replan.py` for deterministic follow-up merge rules
  - `tests/test_intent_parser.py` for additive parser signal extraction if introduced
  - `tests/test_langgraph_workflow.py` for any additive workflow request validation impact
- Integration tests:
  - `tests/integration/test_langgraph_workflow_gateway.py` for `existing_user_id` plus `session_id` plus `intent_override`
  - `tests/integration/test_demo_api_gateway.py` for one initial run plus one follow-up replan run in the same session
- Smoke tests:
  - `README.md` and `docs/WEB_DEMO_README.md` examples reflect the new endpoint
  - `git diff --check` passes
- Regression guard:
  - existing start/get/confirm/decline demo API flows remain green

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_replan.py tests/test_intent_parser.py tests/test_langgraph_workflow.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add demo follow-up replan workflow
```

Expected commands:

```bash
git status --short
git switch -c codex/demo-follow-up-replan-v0
git add backend/app/api/demo.py
git add backend/app/demo/__init__.py
git add backend/app/demo/schemas.py
git add backend/app/demo/service.py
git add backend/app/demo/replan.py
git add backend/app/planning/schemas.py
git add backend/app/planning/intent_parser.py
git add backend/app/workflow/schemas.py
git add backend/app/workflow/state.py
git add backend/app/workflow/runner.py
git add backend/app/workflow/nodes.py
git add README.md
git add docs/WEB_DEMO_README.md
git add tests/test_demo_api.py
git add tests/test_demo_replan.py
git add tests/test_intent_parser.py
git add tests/integration/test_langgraph_workflow_gateway.py
git add tests/integration/test_demo_api_gateway.py
git add docs/specs/044-demo-follow-up-replan-v0.md
git add docs/plans/044-demo-follow-up-replan-v0-plan.md
git diff --cached --check
git commit -m "feat: add demo follow-up replan workflow"
git push -u origin codex/demo-follow-up-replan-v0
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not expose `session_id` or conversation history in public demo responses.
- Do not add session-listing or conversation-history endpoints.
- Do not add plan version fields, version tables, or version-selection APIs.
- Do not add execution-manifest payloads yet.
- Do not change frontend code or frontend routes in this task.
- Do not add benchmark, replay, provider, recovery-visualization, or memory-governance changes.
- Do not add or modify Alembic revisions.
- Do not add new dependencies.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `.env`, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/044-demo-follow-up-replan-v0.md`.
- [ ] `POST /demo/runs/{run_id}/replan` exists and returns `DemoRunSummary`.
- [ ] The new run reuses the source user and session but has a distinct `run_id`.
- [ ] The source run remains unchanged after replan.
- [ ] The follow-up merge uses only supported deterministic parser fields.
- [ ] The workflow additive overrides work when `external_user_id` is absent.
- [ ] Conversation-turn deduplication is run-scoped, not session-global.
- [ ] The assistant replan turn stores only compact linkage payload.
- [ ] Public demo payload shape remains unchanged except for the new endpoint path.
- [ ] No Alembic migration was added or edited.
- [ ] Docs were updated for the new endpoint.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The new public endpoint path and request body shape.
- The additive workflow request fields that were introduced.
- The final conversation turn sequence observed in the demo API integration test.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no Alembic migration changed.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any remaining follow-up limitation, especially that public conversation history, plan versioning, and execution-manifest work remain future tasks.
