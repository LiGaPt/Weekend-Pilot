# Spec: 111 Session and Conversation Turn Trace Snapshots v0

## 1. Goal

Add the smallest missing durable linkage in the multi-turn conversation model so that each persisted demo conversation turn can be traced back to the run that produced it, the run's trace identifier when available, and a compact public-safe state snapshot captured at that moment.

The repository already persists `conversation_sessions`, `conversation_turns`, `agent_runs.session_id`, follow-up replans, clarification turns, version lineage, and benchmark-driven continuation paths. However, the current turn model still stops at `run_id` plus a compact payload. A reviewer or later product/API slice can tell which run produced a turn, but cannot read a stable per-turn trace link or the turn-time run state without joining through multiple runtime tables and reconstructing state from later data. After this task, `conversation_turns` must store additive `trace_id` and `state_snapshot_json` fields, and demo-created turns must persist a compact sanitized state snapshot without changing public demo response shapes.

## 2. Project Context

This task belongs to milestone `M4. 多轮对话与方案版本` in `docs/NEXT_PHASE_ROADMAP.md`.

`docs/PROJECT_BLUEPRINT.md` defines PostgreSQL as the durable source of truth and describes WeekendPilot as a conversation-style planning system rather than a single-shot response generator. The roadmap's original session/conversation baseline is already complete through tasks `043`, `044`, `045`, `048`, and `055`:

- `043` added `conversation_sessions`, `conversation_turns`, and `agent_runs.session_id`
- `044` added same-session follow-up replanning
- `045` added visible plan version lineage
- `048` added clarification-turn workflow
- `055` added benchmark coverage for continuation chains

Recent work through tasks `108`, `109`, and `110` closed the currently higher-priority timing, memory-control, and recovery-chaos slices. The next smallest useful task is therefore not another benchmark expansion and not a repeat of the old session baseline. The remaining gap is persistence quality inside the existing conversation model: turns should carry the producing run's `trace_id` and a compact state snapshot so later review, history APIs, and replay-oriented features can rely on one stable turn-level source of truth.

This task touches these blueprint areas directly:

- PostgreSQL source of truth
- Minimal Web UI / Web demo API path
- LangSmith / local observability linkage
- Future multi-turn planning and session-history surfaces

## 3. Requirements

- Add one new Alembic revision on top of `0003_add_memory_item_metadata_json.py`.
- The new revision must add these additive columns to `conversation_turns`:
  - `trace_id`
  - `state_snapshot_json`
- `conversation_turns.trace_id` must be:
  - nullable
  - `String(255)`
  - indexed
- `conversation_turns.state_snapshot_json` must be:
  - non-null
  - JSONB
  - default `{}` for new rows
- The migration must backfill existing `conversation_turns.state_snapshot_json` rows to `{}`.
- Existing turn rows must remain valid when `trace_id` is null.

- Extend `ConversationTurnRepository.append(...)` to accept additive optional fields:
  - `trace_id: str | None = None`
  - `state_snapshot_json: dict[str, Any] | None = None`
- Add one additive repository helper:
  - `update_snapshot(turn_id, trace_id, state_snapshot_json) -> ConversationTurn | None`
- Existing callers that do not pass the new fields must remain backward compatible.

- Add one dedicated helper module for building compact turn snapshots.
- The helper must build a snapshot from a `DemoRunSummary` or equivalent demo-safe summary inputs.
- The exact stored `state_snapshot_json` contract in this task must include:
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
- `schema_version` must be exactly:
  - `conversation_turn_state_snapshot_v0`
- `selected_plan_id` must serialize as a string when present, otherwise `null`.
- `plan_count` must be the count of serialized plan previews in the summary.
- `plan_version_label` must come from `DemoRunSummary.plan_version.version_label`.
- `clarification_missing_fields` must be an empty list when clarification is absent.

- The stored `progress` field must reuse the current public-safe `DemoProgressSummary` shape.
- The stored `state_snapshot_json` must not include:
  - `session_id`
  - `node_history`
  - `agent_roles`
  - raw workflow state
  - raw `plan_json`
  - raw tool-event payloads
  - action-ledger payloads
  - prompts
  - tokens
  - secrets
  - local trace-buffer payloads

- `DemoWorkflowService.start_run(...)` and `start_run_stream(...)` must persist trace-linked state snapshots on every turn they write for the created run.
- The start-run flow must write snapshot-bearing turns for:
  - `user_request`
  - `assistant_plan_options` when a selected plan exists
  - `assistant_clarification_request` when the run ends in `awaiting_clarification`
- If the run ends with no selected plan and no clarification turn beyond the initiating user request, the `user_request` turn must still store the run-linked snapshot.

- `DemoWorkflowService.clarify_run(...)` must persist trace-linked state snapshots on every turn it writes for the continuation run.
- The clarification flow must write snapshot-bearing turns for:
  - `user_clarification_reply`
  - `assistant_plan_options` when planning succeeds
  - `assistant_clarification_request` when the continuation still ends in `awaiting_clarification`

- `DemoWorkflowService.replan_run(...)` must persist trace-linked state snapshots on every turn it writes for the continuation run.
- The replan flow must write snapshot-bearing turns for:
  - `user_follow_up`
  - `assistant_replan_options` when a selected plan exists

- The trace ID stored on a turn must use the run's current demo/observability trace selection logic.
- If a run has no trace ID, the turn persistence must still succeed with:
  - `trace_id = null`
  - a populated `state_snapshot_json`

- Turn deduplication must remain run-scoped, not session-global.
- When an existing turn for the same run and turn type is reused by a helper, that turn's `trace_id` and `state_snapshot_json` must be refreshed to the latest snapshot for that run instead of remaining stale.

- Public demo HTTP contracts must remain unchanged in this task:
  - no new request fields
  - no new response fields
  - no new public or internal route

- Benchmark harness, replay harness, system-integrity rollups, and frontend demo rendering must remain backward compatible.
- No new dependencies may be added.

## 4. Non-goals

- Do not redesign or replace `conversation_sessions` or `conversation_turns`.
- Do not add `GET /demo/sessions`, `GET /demo/runs/{run_id}/conversation`, or any other history API.
- Do not add confirm, decline, execution, or feedback turn types in this task.
- Do not persist raw workflow-state blobs, trace buffers, prompt text, or internal observability payloads into conversation turns.
- Do not add a new benchmark suite, provider path, or replay schema.
- Do not change public `/demo/runs*` response shapes.
- Do not add or modify unrelated Alembic revisions.
- Do not commit `.env`, API keys, tokens, secrets, generated artifacts, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- Existing `conversation_turns` rows with:
  - `turn_id`
  - `session_id`
  - `run_id`
  - `turn_index`
  - `speaker_role`
  - `turn_type`
  - `content_text`
  - `payload_json`
- Existing demo run summaries produced by:
  - `DemoWorkflowService.build_summary(...)`
- Existing trace lookup behavior from run metadata:
  - `metadata_json["demo"]["trace_id"]`
  - fallback `metadata_json["observability"]["trace_id"]`

### Outputs

- Additive columns on `conversation_turns`:
  - `trace_id: str | None`
  - `state_snapshot_json: dict`
- Additive repository API:
  - `ConversationTurnRepository.update_snapshot(...)`
- Snapshot persistence in start, clarify, and replan turn-writing flows
- No public API schema changes

### Schemas

Example persisted turn shape after this task:

```json
{
  "turn_type": "assistant_replan_options",
  "run_id": "00000000-0000-0000-0000-000000000020",
  "trace_id": "trace-123",
  "state_snapshot_json": {
    "schema_version": "conversation_turn_state_snapshot_v0",
    "run_status": "awaiting_confirmation",
    "selected_plan_id": "00000000-0000-0000-0000-000000000030",
    "plan_count": 2,
    "plan_version_label": "v2",
    "action_count": 0,
    "execution_status": null,
    "feedback_status": null,
    "clarification_missing_fields": [],
    "progress": {
      "schema_version": "public_demo_progress_v1",
      "current_stage": "ready_for_confirmation",
      "current_label": "Ready for confirmation",
      "stage_history": [
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
        "checking_availability",
        "building_itinerary",
        "checking_route_time",
        "reviewing_plan",
        "ready_for_confirmation"
      ],
      "steps": []
    }
  }
}
```

Example clarification-pending snapshot excerpt:

```json
{
  "schema_version": "conversation_turn_state_snapshot_v0",
  "run_status": "awaiting_clarification",
  "selected_plan_id": null,
  "plan_count": 0,
  "plan_version_label": "v1",
  "action_count": 0,
  "execution_status": null,
  "feedback_status": null,
  "clarification_missing_fields": [
    "scenario_or_participants",
    "time_window"
  ],
  "progress": {
    "schema_version": "public_demo_progress_v1",
    "current_stage": "planning_queries",
    "current_label": "Planning queries",
    "stage_history": [
      "understanding_request",
      "planning_queries"
    ],
    "steps": []
  }
}
```

## 6. Observability

This task does not add a new public observability surface.

It adds durable turn-level linkage to already-existing observability context:

- `conversation_turns.trace_id`
- compact `conversation_turns.state_snapshot_json`

The task must continue to treat the public demo contract as customer-safe. Stored state snapshots must remain sanitized and compact. The implementation must not introduce new prompt, token, secret, trace-event, or raw provider-payload leakage into durable conversation rows.

## 7. Failure Handling

- If the Alembic migration is not applied, integration verification must fail loudly rather than silently dropping snapshot persistence.
- If a run has no trace ID, turn persistence must still succeed with `trace_id = null`.
- If snapshot building encounters malformed run metadata, it must fall back to the current `DemoRunSummary`-derived safe fields rather than raising a public API error.
- If conversation turn persistence fails during start, clarify, or replan, the enclosing request must roll back as it does today.
- Existing rows with null `trace_id` and `{}` snapshot content must remain readable without repair jobs.
- Existing benchmark and observability paths that only read `conversation_turns.turn_type` must continue to work unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/111-session-conversation-turn-trace-snapshots-v0.md` exists and matches this task.
- [ ] `docs/plans/111-session-conversation-turn-trace-snapshots-v0-plan.md` exists and matches this task.
- [ ] `conversation_turns` includes additive `trace_id` and `state_snapshot_json` columns.
- [ ] The new Alembic revision upgrades cleanly on top of `0003_add_memory_item_metadata_json.py`.
- [ ] Existing conversation turn rows backfill `state_snapshot_json = {}`.
- [ ] `ConversationTurnRepository.append(...)` remains backward compatible and supports the new optional fields.
- [ ] `ConversationTurnRepository.update_snapshot(...)` can refresh an existing turn's trace/snapshot fields.
- [ ] Start-run persistence writes a trace-linked state snapshot onto the initiating `user_request` turn.
- [ ] Start-run persistence writes a trace-linked state snapshot onto `assistant_plan_options` or `assistant_clarification_request` when those turns are present.
- [ ] Clarify-run persistence writes trace-linked state snapshots onto `user_clarification_reply` and its assistant continuation turn.
- [ ] Replan-run persistence writes trace-linked state snapshots onto `user_follow_up` and `assistant_replan_options`.
- [ ] Persisted snapshots include the exact safe fields listed in this spec and exclude raw workflow state, prompts, and secrets.
- [ ] Public `/demo/runs*` request and response shapes remain unchanged.
- [ ] Existing benchmark continuation and observability flows remain backward compatible.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing unrelated local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_conversation_snapshots.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_repositories.py tests/integration/test_demo_api_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add conversation turn trace snapshots
```

## 11. Notes for the Implementer

Keep this task intentionally additive and persistence-scoped.

The main sequencing constraint is that turn snapshots should be derived from the same public-safe summary logic already used by the demo surface. Do not invent a parallel raw workflow snapshot format, and do not widen the task into session history APIs or post-confirmation turn modeling. If implementation pressure suggests storing whole workflow state, trace buffers, or confirm/decline execution turns, stop and split that into a later task.
