# Plan: 111 Session and Conversation Turn Trace Snapshots v0

## 1. Spec Reference

Spec file:

```text
docs/specs/111-session-conversation-turn-trace-snapshots-v0.md
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

- Current branch is `codex/110-recovery-chaos-harness-next-slice-v0`.
- Latest completed numbered task is `110`.
- Latest commit is:

```text
924df50 feat: expand recovery chaos harness coverage
```

- `docs/specs/` and `docs/plans/` are continuous and matched through `110`.
- The originally proposed session/conversation baseline is already implemented:
  - `043` added `conversation_sessions`, `conversation_turns`, and `agent_runs.session_id`
  - `044` added same-session replan
  - `045` added plan version lineage
  - `048` added clarification-turn workflow
  - `055` added benchmark continuation coverage
- Current Alembic revisions are:
  - `0001_create_core_runtime_tables.py`
  - `0002_add_conversation_session_tables.py`
  - `0003_add_memory_item_metadata_json.py`
- Current gap:
  - `conversation_turns` persist `run_id`, `turn_type`, and compact payloads
  - turns do not yet persist `trace_id`
  - turns do not yet persist a compact turn-time run state snapshot
- Existing public demo contracts must remain unchanged.
- Existing untracked local files must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 3. Files to Add

- `alembic/versions/0004_add_conversation_turn_trace_snapshots.py` - add `trace_id` and `state_snapshot_json` to `conversation_turns`.
- `backend/app/demo/conversation_snapshots.py` - build compact public-safe state snapshots for persisted conversation turns.
- `tests/test_demo_conversation_snapshots.py` - unit coverage for snapshot shape and sanitization.

## 4. Files to Modify

- `backend/app/models/runtime.py` - add additive `trace_id` and `state_snapshot_json` columns to `ConversationTurn`.
- `backend/app/repositories/conversation_turns.py` - accept snapshot fields on append and add `update_snapshot(...)`.
- `backend/app/demo/service.py` - build one summary-backed snapshot per run and persist it onto turns created by start, clarify, and replan flows.
- `tests/test_db_metadata.py` - update expected table/column/index contract for `conversation_turns`.
- `tests/test_alembic_config.py` - ensure target metadata still includes the updated conversation table shape.
- `tests/integration/test_repositories.py` - verify new repository fields, defaults, and update semantics.
- `tests/integration/test_demo_api_gateway.py` - verify start/clarify/replan write trace-linked snapshots while public payloads stay unchanged.

## 5. Implementation Steps

1. Add the schema fields to the runtime model.
   Update `backend/app/models/runtime.py` so `ConversationTurn` includes:
   - `trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)`
   - `state_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)`

2. Add Alembic revision `0004_add_conversation_turn_trace_snapshots.py`.
   The upgrade must:
   - add `trace_id` to `conversation_turns`
   - add an index on `conversation_turns.trace_id`
   - add `state_snapshot_json` to `conversation_turns`
   - backfill existing rows to `{}` before enforcing non-null if needed by the chosen SQL
   The downgrade must:
   - drop the trace index
   - drop `trace_id`
   - drop `state_snapshot_json`
   Do not modify `0001`, `0002`, or `0003`.

3. Add a dedicated snapshot helper module.
   Create `backend/app/demo/conversation_snapshots.py` with one focused helper such as:
   - `build_conversation_turn_state_snapshot(summary: DemoRunSummary) -> dict[str, Any]`
   Keep the output contract exactly aligned to the spec:
   - `schema_version`
   - `run_status`
   - `selected_plan_id`
   - `plan_count`
   - `plan_version_label`
   - `action_count`
   - `execution_status`
   - `feedback_status`
   - `clarification_missing_fields`
   - `progress`
   Reuse `sanitize_demo_payload(...)` so the stored snapshot stays public-safe.

4. Extend the conversation-turn repository.
   In `backend/app/repositories/conversation_turns.py`:
   - add optional `trace_id` and `state_snapshot_json` parameters to `append(...)`
   - default missing `state_snapshot_json` to `{}`
   - add `update_snapshot(turn_id, trace_id, state_snapshot_json)`
   Keep existing order/list behavior unchanged.

5. Refactor demo turn persistence to attach snapshots after summary-safe fields are available.
   In `backend/app/demo/service.py`:
   - keep `_persist_demo_metadata(...)` first so `demo.trace_id` and `plan_version` are present
   - build `summary = self.build_summary(run_id)` before final commit
   - derive `turn_trace_id = self._trace_id(run)` or the current run result trace ID when already available
   - derive `state_snapshot_json` with the new helper
   - pass those fields into every new turn append for the current run

6. Make turn reuse refresh snapshots instead of leaving stale state.
   Update `_ensure_run_turn(...)`, `_ensure_selected_plan_turn(...)`, and `_ensure_clarification_turn(...)` so:
   - when a run-scoped existing turn already exists, call `update_snapshot(...)`
   - when the turn does not exist, call `append(...)` with trace/snapshot fields
   Do not change the existing run-scoped dedup rules.

7. Apply the snapshot logic to all demo continuation paths.
   Ensure these flows persist the run-linked snapshot:
   - `start_run(...)`
   - `start_run_stream(...)`
   - `clarify_run(...)`
   - `replan_run(...)`
   Required turn coverage:
   - `user_request`
   - `assistant_plan_options`
   - `assistant_clarification_request`
   - `user_clarification_reply`
   - `user_follow_up`
   - `assistant_replan_options`
   When a run ends with only the initiating user turn, that user turn must still receive the snapshot.

8. Add unit coverage for the snapshot helper.
   In `tests/test_demo_conversation_snapshots.py`, cover:
   - awaiting-confirmation snapshot
   - awaiting-clarification snapshot
   - selected-plan UUID string serialization
   - empty clarification fallback
   - exclusion of unsafe fields such as `session_id`, `trace_id` inside the snapshot body, and raw prompt/debug keys

9. Update metadata and Alembic tests.
   In `tests/test_db_metadata.py`:
   - add `trace_id` and `state_snapshot_json` to expected `conversation_turns` columns
   - assert `trace_id` index exists if the test currently checks indexes
   In `tests/test_alembic_config.py`:
   - keep target metadata expectations aligned to the updated model set

10. Extend repository integration coverage.
    In `tests/integration/test_repositories.py`:
    - append a turn with explicit `trace_id` and snapshot payload
    - assert those values round-trip
    - call `update_snapshot(...)` and assert replacement behavior
    - assert rows created without explicit snapshot fields get `state_snapshot_json == {}`
    - keep rollback coverage intact

11. Extend demo API integration coverage without changing public payloads.
    In `tests/integration/test_demo_api_gateway.py`:
    - after `POST /demo/runs`, load turns from the DB and assert:
      - the initiating turn has `run_id`, `trace_id`, and a populated `state_snapshot_json`
      - assistant presentation or clarification turns for that run also have trace-linked snapshots
    - after `POST /demo/runs/{run_id}/clarify`, assert:
      - `user_clarification_reply` and the assistant continuation turn for the new run carry the new run's trace-linked snapshot
    - after `POST /demo/runs/{run_id}/replan`, assert:
      - `user_follow_up` and `assistant_replan_options` carry the new run's trace-linked snapshot
    - keep existing public payload assertions unchanged so no `trace_id` or `session_id` leaks into `/demo/runs*`

12. Run focused verification and stage only task-relevant files.
    Run the commands from section 7.
    Before staging, confirm unrelated local docs and generated files remain unstaged.

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_conversation_snapshots.py`
    - snapshot schema shape
    - clarification fallback behavior
    - selected-plan string serialization
    - sanitization of unsafe fields
  - `tests/test_db_metadata.py`
    - updated `conversation_turns` schema contract
  - `tests/test_alembic_config.py`
    - target metadata alignment
  - `tests/test_demo_api.py`
    - public payload remains unchanged and still omits internal conversation persistence fields

- Integration tests:
  - `tests/integration/test_repositories.py`
    - append with trace/snapshot
    - update snapshot on an existing turn
    - default `{}` snapshot behavior
    - rollback behavior
  - `tests/integration/test_demo_api_gateway.py`
    - start-run turn snapshots
    - clarify-run turn snapshots
    - replan-run turn snapshots
    - public payload remains unchanged

- Smoke checks:
  - Alembic upgrade succeeds on top of `0003`
  - `git diff --check` passes
  - git status remains clean except unrelated pre-existing local files

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_conversation_snapshots.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_repositories.py tests/integration/test_demo_api_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add conversation turn trace snapshots
```

Expected commands:

```bash
git status --short
git switch -c codex/111-session-conversation-turn-trace-snapshots-v0
git add alembic/versions/0004_add_conversation_turn_trace_snapshots.py backend/app/models/runtime.py backend/app/repositories/conversation_turns.py backend/app/demo/conversation_snapshots.py backend/app/demo/service.py tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_conversation_snapshots.py tests/test_demo_api.py tests/integration/test_repositories.py tests/integration/test_demo_api_gateway.py docs/specs/111-session-conversation-turn-trace-snapshots-v0.md docs/plans/111-session-conversation-turn-trace-snapshots-v0-plan.md
git diff --cached --check
git commit -m "feat: add conversation turn trace snapshots"
git push -u origin codex/111-session-conversation-turn-trace-snapshots-v0
```

The implementer must confirm unrelated untracked files, generated artifacts, `.env`, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not add new public or internal API routes.
- Do not add confirm, decline, execution, or feedback turn types.
- Do not store raw workflow state, prompts, trace buffers, or provider payloads in conversation turns.
- Do not redesign benchmark suites, replay contracts, or observability endpoints.
- Do not change public `/demo/runs*` schemas.
- Do not add new dependencies.
- Do not stage `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, `docs/superpowers/`, `var/`, caches, virtual environments, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/111-session-conversation-turn-trace-snapshots-v0.md`.
- [ ] The new Alembic revision adds only additive `conversation_turns` fields.
- [ ] The snapshot helper stores exactly the agreed safe fields.
- [ ] No raw workflow state, prompt, secret, or trace-buffer payload leaked into `state_snapshot_json`.
- [ ] Start, clarify, and replan flows all persist trace-linked snapshots on the expected turn types.
- [ ] Existing turn reuse refreshes snapshot fields instead of leaving stale values.
- [ ] Public `/demo/runs*` payloads remain unchanged.
- [ ] Repository and demo API integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- exact files changed
- the new Alembic revision name and whether upgrade succeeded
- the final `conversation_turns` column shape
- one example persisted `state_snapshot_json` for:
  - a normal awaiting-confirmation run
  - an awaiting-clarification run
- verification commands run and their results
- commit hash
- push result
- confirmation that public `/demo/runs*` payloads stayed unchanged
- any follow-up limitation, especially that confirm/decline post-planning state capture remains future work
