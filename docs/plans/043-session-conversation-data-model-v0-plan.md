# Plan: 043 Session and Conversation Data Model v0

## 1. Spec Reference

Spec file:

```text
docs/specs/043-session-conversation-data-model-v0.md
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

- Current branch is `codex/internal-recovery-path-visualization-v0`.
- Latest completed numbered task is `042`.
- Latest commit is `6d615f1 feat: add internal recovery path visualization`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `042`.
- There is no `043` spec, `043` plan, or `codex/*043*` branch yet.
- The repository currently has only one Alembic revision: `alembic/versions/0001_create_core_runtime_tables.py`.
- Runtime durable tables currently cover users, profiles, runs, memory, plans, tool events, and action ledger only.
- There is no existing `conversation_sessions` table, `conversation_turns` table, `agent_runs.session_id` column, or conversation repository layer.
- The public demo API is still run-centric:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- `DemoRunSummary` currently does not expose any session identifier or conversation history.
- The workflow runner is also used by benchmark and internal paths, so this task should not move conversation persistence into workflow core.
- Lightweight contract checks already passed in this planning session:
  - `python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_api.py -q`
- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.

## 3. Files to Add

- `alembic/versions/0002_add_conversation_session_tables.py` - add `conversation_sessions`, `conversation_turns`, and nullable `agent_runs.session_id`.
- `backend/app/repositories/conversation_sessions.py` - repository for session create/get/list/update operations.
- `backend/app/repositories/conversation_turns.py` - repository for ordered turn append/get/list operations.

## 4. Files to Modify

- `backend/app/models/runtime.py` - add conversation models and `AgentRun.session_id`.
- `backend/app/models/__init__.py` - export the new runtime models.
- `backend/app/repositories/__init__.py` - export the new repositories.
- `backend/app/repositories/runs.py` - accept optional `session_id` and add `update_session_id(...)`.
- `backend/app/demo/service.py` - persist the initial conversation baseline inside `start_run(...)`.
- `tests/test_db_metadata.py` - add expected tables, columns, and foreign keys.
- `tests/test_alembic_config.py` - update expected Alembic target metadata table set.
- `tests/test_demo_api.py` - lock the public summary shape so no `session_id` or conversation payload leaks into the response.
- `tests/integration/test_repositories.py` - add repository coverage for sessions and turns and extend rollback coverage.
- `tests/integration/test_demo_api_gateway.py` - assert that demo run start creates one session and the expected initial turns without changing the public payload.

## 5. Implementation Steps

1. Extend the runtime SQLAlchemy models in `backend/app/models/runtime.py`.
   Add `ConversationSession` and `ConversationTurn`.
   Add nullable `session_id` to `AgentRun`.
   Use the existing naming convention and timestamp pattern.
   Add the foreign keys and the `(session_id, turn_index)` uniqueness rule on `conversation_turns`.

2. Export the new models.
   Update `backend/app/models/__init__.py` so Alembic target metadata continues to see the full runtime model set through the existing import path.

3. Add the Alembic migration in `alembic/versions/0002_add_conversation_session_tables.py`.
   The upgrade must:
   - create `conversation_sessions`
   - create indexes on `conversation_sessions.user_id` and `conversation_sessions.status`
   - add nullable `agent_runs.session_id`
   - add an index on `agent_runs.session_id`
   - create `conversation_turns`
   - add an index on `conversation_turns.session_id`
   - add an index on `conversation_turns.run_id`
   - add a unique constraint on `(session_id, turn_index)`
   The downgrade must reverse those changes cleanly without editing `0001`.

4. Add the repository layer.
   In `backend/app/repositories/conversation_sessions.py`, implement:
   - `create(user_id, channel, status, metadata_json)`
   - `get_by_id(session_id)`
   - `list_for_user(user_id)` ordered by `created_at`, then `session_id`
   - `update_status(session_id, status)`
   In `backend/app/repositories/conversation_turns.py`, implement:
   - `append(session_id, run_id, speaker_role, turn_type, content_text, payload_json)`
   - `get_by_id(turn_id)`
   - `list_for_session(session_id)` ordered by `turn_index`, then `turn_id`
   - `list_for_run(run_id)` ordered by `created_at`, then `turn_id`
   `append(...)` must compute `turn_index` from the current max in the same session and must flush and refresh the row like the existing repositories.

5. Extend the run repository and exports.
   In `backend/app/repositories/runs.py`, add:
   - optional `session_id` parameter to `create(...)`, defaulting to `None`
   - `update_session_id(run_id, session_id)`
   Update `backend/app/repositories/__init__.py` to export `ConversationSessionRepository` and `ConversationTurnRepository`.

6. Integrate the baseline only into `DemoWorkflowService.start_run(...)`.
   After the workflow result and persisted run are loaded:
   - require a non-null `run.user_id`
   - if `run.session_id` is null, create a `conversation_sessions` row with:
     - `channel = "web_demo"`
     - `status = "active"`
     - `metadata_json = {"source": "demo_api_v1", "case_id": request.case_id, "selected_plan_index": request.selected_plan_index}`
   - update `agent_runs.session_id`
   - append the initiating user turn with the original `request.user_input`
   - load the selected plan and all plan rows for the run
   - if a selected plan exists, append one assistant turn with:
     - `turn_type = "assistant_plan_options"`
     - `content_text = selected plan summary`, or `title` if summary is missing, or a fixed fallback sentence if both are missing
     - `payload_json = {"selected_plan_id": ..., "plan_ids": [...], "plan_count": ..., "run_status": run.status}`
   - if no selected plan exists, stop after the user turn
   Keep the existing `metadata["demo"]` write and public summary return path unchanged.
   Do not add session writes to `confirm_run(...)` or `decline_run(...)`.

7. Keep benchmark and workflow core untouched.
   Do not modify `WeekendPilotWorkflowRunner`, workflow nodes, benchmark harness, or internal observability services in this task.

8. Update metadata and Alembic tests.
   In `tests/test_db_metadata.py`, add the new expected tables, columns, and representative foreign keys.
   In `tests/test_alembic_config.py`, update the expected target metadata tables.

9. Extend repository integration coverage.
   In `tests/integration/test_repositories.py`:
   - create a session for a user
   - append two turns
   - assert `turn_index` ordering is `1`, then `2`
   - assert `list_for_session(...)` and `list_for_run(...)` return the expected rows
   - extend the rollback test so session and turn rows disappear after `session.rollback()`
   - assert `AgentRunRepository.update_session_id(...)` persists the linkage when used

10. Extend demo API tests without changing the public payload.
    In `tests/test_demo_api.py`, add assertions that the serialized public summary still does not contain `session_id` or conversation history fields.
    In `tests/integration/test_demo_api_gateway.py`, after `POST /demo/runs`:
    - load the run from the database
    - assert `run.session_id` is not null
    - load the linked `conversation_sessions` row and assert channel, status, and metadata
    - load the linked `conversation_turns` rows and assert the happy path creates:
      - turn `1` as `user_request`
      - turn `2` as `assistant_plan_options`
    - assert the assistant turn payload contains only the compact selected-plan linkage fields
    Keep the existing confirm and decline assertions as regression coverage for unchanged public behavior.

11. Run verification and stage only relevant files.
    Run the commands from section 7.
    Before staging, confirm that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` artifacts remain unstaged.

## 6. Testing Plan

- Unit tests: SQLAlchemy metadata exposes the new tables, columns, and foreign keys.
- Unit tests: Alembic target metadata includes the new tables.
- Unit tests: public `DemoRunSummary` serialization still omits session fields.
- Integration tests: `ConversationSessionRepository` creates and lists sessions for a user.
- Integration tests: `ConversationTurnRepository.append(...)` assigns ordered `turn_index` values starting at `1`.
- Integration tests: `ConversationTurnRepository.list_for_session(...)` and `list_for_run(...)` return stable ordered results.
- Integration tests: repository writes still do not self-commit after rollback.
- Integration tests: happy-path `POST /demo/runs` creates one linked conversation session and two initial turns.
- Integration tests: existing confirm and decline flows still pass without public API changes.
- Smoke tests: Alembic upgrade succeeds on top of the existing schema.
- Smoke tests: `git diff --check` succeeds.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_repositories.py tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add session conversation data model
```

Expected commands:

```bash
git status --short
git switch -c codex/session-conversation-data-model-v0
git add alembic/versions/0002_add_conversation_session_tables.py
git add backend/app/models/runtime.py
git add backend/app/models/__init__.py
git add backend/app/repositories/conversation_sessions.py
git add backend/app/repositories/conversation_turns.py
git add backend/app/repositories/runs.py
git add backend/app/repositories/__init__.py
git add backend/app/demo/service.py
git add tests/test_db_metadata.py
git add tests/test_alembic_config.py
git add tests/test_demo_api.py
git add tests/integration/test_repositories.py
git add tests/integration/test_demo_api_gateway.py
git add docs/specs/043-session-conversation-data-model-v0.md
git add docs/plans/043-session-conversation-data-model-v0-plan.md
git diff --cached --check
git commit -m "feat: add session conversation data model"
git push -u origin codex/session-conversation-data-model-v0
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not add new public API endpoints or request fields.
- Do not expose `session_id` or turn history in `DemoRunSummary`.
- Do not add frontend state, frontend routing, or frontend UI changes.
- Do not implement session reuse, multi-turn continuation, replan logic, or plan versioning.
- Do not append confirmation, decline, execution, or feedback turns.
- Do not move conversation persistence into workflow core or benchmark harness code.
- Do not backfill old rows or write migration data fixes.
- Do not add new dependencies, benchmark cases, observability fields, or replay behavior.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `.env`, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/043-session-conversation-data-model-v0.md`.
- [ ] The new Alembic revision creates `conversation_sessions`, `conversation_turns`, and `agent_runs.session_id`.
- [ ] The SQLAlchemy metadata and Alembic target metadata include the new tables.
- [ ] `ConversationTurnRepository.append(...)` produces ordered `turn_index` values.
- [ ] Repository rollback behavior still holds for sessions and turns.
- [ ] A happy-path `POST /demo/runs` creates one linked session and the expected initial turns.
- [ ] The assistant turn stores only compact selected-plan linkage data.
- [ ] The public `/demo/runs*` response shape remains unchanged.
- [ ] Confirm and decline flows still pass without session-specific request changes.
- [ ] Benchmark and internal observability paths were not modified.
- [ ] Required tests and migration verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The new Alembic revision ID and whether upgrade succeeded.
- The final table and foreign-key shape for `conversation_sessions`, `conversation_turns`, and `agent_runs.session_id`.
- The verification commands that were run and their results.
- The demo API integration evidence that one session and the expected initial turns were created.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files were not staged.
- Any follow-up limitation, especially that session reuse, multi-turn replan, plan versioning, and execution-manifest work remain future tasks.
