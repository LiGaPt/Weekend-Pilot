# Spec: 043 Session and Conversation Data Model v0

## 1. Goal

Add the first durable session and turn model for WeekendPilot without changing the current public demo API or jumping ahead into multi-turn workflow behavior.

The repository currently persists users, runs, plans, tool events, and action ledger rows, but it does not persist conversation sessions or ordered conversation turns. That means later roadmap work for multi-turn clarification, replan, and plan versioning has no reliable source of truth for dialogue history. After this task, PostgreSQL must store conversation sessions and turns, `agent_runs` must be able to link to a session, and each new Web demo start request must persist the first conversation baseline: the initiating user request and, when a selected plan is available, the initial assistant plan-presentation turn.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines PostgreSQL as the durable source of truth and calls out a future conversation-style planning flow where one run can eventually include multiple user turns and multiple plan versions. `docs/NEXT_PHASE_ROADMAP.md` places `session / conversation 数据模型` ahead of `多轮澄清与 replan 工作流` and `plan versioning 与执行前 action manifest`.

Tasks `033` through `042` completed the current M1 and M2 convergence work around benchmark visibility, internal observability, and recovery-path inspection. The latest task chain is closed and reviewable, but the current product path is still structurally run-centric: `POST /demo/runs` creates a new run, and all later actions hang off that run. This task is the smallest useful first slice of milestone `M4. 多轮对话与方案版本` because it adds the missing durable session layer without changing workflow behavior, benchmark behavior, or the public demo UI.

This task touches these blueprint areas directly:

- PostgreSQL source of truth
- Minimal Web UI / Web demo API path
- Human-in-the-loop presentation boundary
- Future multi-turn planning and plan version evolution

## 3. Requirements

- Add SQLAlchemy runtime models and one new Alembic revision for:
  - `conversation_sessions`
  - `conversation_turns`
  - nullable `agent_runs.session_id`
- `conversation_sessions` must include:
  - `session_id`
  - `user_id`
  - `channel`
  - `status`
  - `metadata_json`
  - `created_at`
  - `updated_at`
- `conversation_turns` must include:
  - `turn_id`
  - `session_id`
  - `run_id`
  - `turn_index`
  - `speaker_role`
  - `turn_type`
  - `content_text`
  - `payload_json`
  - `created_at`
- `agent_runs.session_id` must be nullable so existing rows and non-demo runs remain valid.
- `agent_runs.session_id` must reference `conversation_sessions.session_id` through a foreign key with `ON DELETE SET NULL`.
- `conversation_sessions.user_id` must reference `users.user_id`.
- `conversation_turns.session_id` must reference `conversation_sessions.session_id`.
- `conversation_turns.run_id` must reference `agent_runs.run_id` with `ON DELETE SET NULL`.
- `conversation_turns` must enforce uniqueness for `(session_id, turn_index)`.
- Add a `ConversationSessionRepository`.
- Add a `ConversationTurnRepository`.
- `ConversationSessionRepository` must provide at least:
  - `create(...)`
  - `get_by_id(...)`
  - `list_for_user(...)`
  - `update_status(...)`
- `ConversationTurnRepository` must provide at least:
  - `append(...)`
  - `get_by_id(...)`
  - `list_for_session(...)`
  - `list_for_run(...)`
- `ConversationTurnRepository.append(...)` must assign `turn_index` as `1` for the first turn in a session and otherwise `max(turn_index) + 1` inside the current SQLAlchemy session.
- `AgentRunRepository.create(...)` must accept an optional `session_id`.
- Add an additive `AgentRunRepository.update_session_id(...)` helper.
- `POST /demo/runs` must create one `conversation_sessions` row for a new persisted demo run when that run has a non-null `user_id` and `session_id` is still null.
- New demo-created sessions must use:
  - `channel = "web_demo"`
  - `status = "active"`
- New demo-created session metadata must include:
  - `source = "demo_api_v1"`
  - `case_id`
  - `selected_plan_index`
- `POST /demo/runs` must append a first turn with:
  - `speaker_role = "user"`
  - `turn_type = "user_request"`
  - `content_text = request.user_input`
  - `run_id = created run_id`
- If the run has a selected plan when the start request completes, `POST /demo/runs` must append a second turn with:
  - `speaker_role = "assistant"`
  - `turn_type = "assistant_plan_options"`
  - `content_text` derived from the selected plan summary, or the selected plan title when summary is missing
  - `payload_json` limited to:
    - `selected_plan_id`
    - `plan_ids`
    - `plan_count`
    - `run_status`
- The assistant turn must not duplicate the full `plan_json`, full tool payloads, action-ledger payloads, or raw observability metadata into `conversation_turns.payload_json`.
- If the run does not have a selected plan at start-run completion, the service must persist only the initiating user turn and must not fabricate an assistant turn.
- This task must not add session or turn persistence to benchmark harness runs, internal observability routes, or workflow-only callers.
- `DemoRunSummary` and `/demo/runs*` response fields must remain unchanged in this task.
- Existing frontend code and public demo UX must continue to work without requiring a session identifier.
- Update or add focused tests for metadata contracts, Alembic metadata exposure, repositories, and demo API integration.
- Do not add new dependencies, new frontend routes, new public endpoints, or new request fields.

## 4. Non-goals

- Do not add `session_id` or conversation history to the public `DemoRunSummary`.
- Do not add `POST /demo/sessions`, `GET /demo/sessions/{id}`, or any other new API route.
- Do not allow `POST /demo/runs` to reuse an existing session yet.
- Do not implement multi-turn clarification, user follow-up turns, replan loops, or plan versioning.
- Do not append confirmation, decline, execution, or feedback turns in this task.
- Do not backfill existing `agent_runs` rows with session links.
- Do not move session persistence into `WeekendPilotWorkflowRunner` or benchmark harness code.
- Do not change internal observability contracts, benchmark contracts, or replay contracts.
- Do not change the frontend, the public `/` page, or the `/observability` page.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, or unrelated untracked files.

## 5. Interfaces and Contracts

### Inputs

- Existing `POST /demo/runs` request payload:
  - `user_input`
  - `external_user_id`
  - `display_name`
  - `case_id`
  - `selected_plan_index`
- Existing workflow-created `AgentRun` row returned through the current start-run path.
- Existing selected plan rows persisted by the workflow presentation step.

### Outputs

- New durable tables:
  - `conversation_sessions`
  - `conversation_turns`
- One additive nullable column:
  - `agent_runs.session_id`
- New repository APIs:
  - `ConversationSessionRepository`
  - `ConversationTurnRepository`
  - `AgentRunRepository.update_session_id(...)`
- Existing public demo API responses remain unchanged.

### Schemas

Repository-level baseline shape:

```json
{
  "conversation_session": {
    "channel": "web_demo",
    "status": "active",
    "metadata_json": {
      "source": "demo_api_v1",
      "case_id": "web-demo",
      "selected_plan_index": 0
    }
  },
  "conversation_turns": [
    {
      "turn_index": 1,
      "speaker_role": "user",
      "turn_type": "user_request",
      "content_text": "This afternoon I want to go out with my wife and child for a few hours.",
      "payload_json": {}
    },
    {
      "turn_index": 2,
      "speaker_role": "assistant",
      "turn_type": "assistant_plan_options",
      "content_text": "A nearby family-friendly afternoon with a lighter dinner option.",
      "payload_json": {
        "selected_plan_id": "00000000-0000-0000-0000-000000000001",
        "plan_ids": [
          "00000000-0000-0000-0000-000000000001"
        ],
        "plan_count": 1,
        "run_status": "awaiting_confirmation"
      }
    }
  ]
}
```

Expected repository signatures:

```text
ConversationSessionRepository.create(user_id, channel, status, metadata_json) -> ConversationSession
ConversationSessionRepository.get_by_id(session_id) -> ConversationSession | None
ConversationSessionRepository.list_for_user(user_id) -> list[ConversationSession]
ConversationSessionRepository.update_status(session_id, status) -> ConversationSession | None

ConversationTurnRepository.append(session_id, run_id, speaker_role, turn_type, content_text, payload_json) -> ConversationTurn
ConversationTurnRepository.get_by_id(turn_id) -> ConversationTurn | None
ConversationTurnRepository.list_for_session(session_id) -> list[ConversationTurn]
ConversationTurnRepository.list_for_run(run_id) -> list[ConversationTurn]

AgentRunRepository.update_session_id(run_id, session_id) -> AgentRun | None
```

## 6. Observability

This task does not add a new observability surface.

The new session and turn rows are durable product state, not a new telemetry channel. This task must not add new LangSmith fields, local trace buffer fields, internal observability API fields, or frontend observability panels. Existing observability behavior must remain unchanged.

## 7. Failure Handling

- If the workflow start path still returns no `run_id`, current start-run failure behavior remains unchanged.
- If the workflow-created run disappears before session persistence, the request must fail as it does today.
- If the workflow-created run has `user_id = null` at the session-persistence step, `POST /demo/runs` must fail and the database session must roll back. The task depends on a durable user-linked session.
- If conversation-session creation, turn append, or `agent_runs.session_id` update fails during `POST /demo/runs`, the request must roll back and must not leave partial committed run, session, or turn rows behind.
- If the run has no selected plan at start-run completion, the service must still create the session and first user turn, and must simply omit the assistant turn.
- Existing runs with `session_id = null` must continue to work for `GET /demo/runs/{run_id}`, `POST /demo/runs/{run_id}/confirm`, and `POST /demo/runs/{run_id}/decline`.
- Repository list methods must return empty lists rather than raising for unknown user, session, or run identifiers.

## 8. Acceptance Criteria

- [ ] `docs/specs/043-session-conversation-data-model-v0.md` exists and matches this task.
- [ ] `docs/plans/043-session-conversation-data-model-v0-plan.md` exists and matches this task.
- [ ] SQLAlchemy metadata includes `conversation_sessions` and `conversation_turns`.
- [ ] Alembic target metadata includes `conversation_sessions` and `conversation_turns`.
- [ ] `agent_runs` includes a nullable `session_id` column.
- [ ] The new Alembic revision upgrades cleanly on top of `0001_create_core_runtime_tables`.
- [ ] Repository coverage proves session creation, turn append ordering, run-linked turn listing, and rollback behavior.
- [ ] A happy-path `POST /demo/runs` creates one `conversation_sessions` row linked from `agent_runs.session_id`.
- [ ] A happy-path `POST /demo/runs` creates turn index `1` as the initiating `user_request`.
- [ ] A happy-path `POST /demo/runs` creates turn index `2` as `assistant_plan_options` when a selected plan exists.
- [ ] The assistant turn stores only the compact selected-plan linkage payload, not the full persisted plan JSON.
- [ ] Existing public `/demo/runs*` response shape remains unchanged.
- [ ] Existing confirm and decline API flows continue to pass without session-specific request changes.
- [ ] No benchmark harness path, internal observability route, or frontend route is changed.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated untracked file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing intentionally untracked local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_repositories.py tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add session conversation data model
```

## 11. Notes for the Implementer

Keep this task as the narrow first slice of roadmap item `6. session / conversation 数据模型`.

The key sequencing decision is to persist session data only in `DemoWorkflowService.start_run`. Do not move that logic into `WeekendPilotWorkflowRunner`, because the workflow runner is also used by benchmark and internal paths that are not ready to opt into conversation persistence yet.

Create a new `0002` Alembic revision rather than modifying `0001`. Keep the public demo API stable in this task. Session reuse, follow-up turns, multi-turn replan, plan versioning, and execution-manifest exposure belong to later tasks after this durable baseline exists.
