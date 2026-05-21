# Spec: 044 Demo Follow-up Replan Workflow v0

## 1. Goal

Add the first public follow-up replanning path for the Web demo without expanding into full plan versioning, session browsing, or frontend work.

Task 043 added durable `conversation_sessions` and `conversation_turns`, but the current product path is still single-shot: `POST /demo/runs` creates exactly one run, and the user cannot submit a follow-up clarification or changed requirement that reuses the same conversation session. After this task, the demo API must support a run-anchored follow-up request that creates a new workflow run in the same session, preserves the same user, appends the follow-up conversation turns, and returns a new `DemoRunSummary` for the replanned run.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines PostgreSQL as the durable source of truth and describes the product goal as a conversation-style planning and execution system rather than a one-shot recommendation response. `docs/NEXT_PHASE_ROADMAP.md` places `M4. 多轮对话与方案版本` after the earlier observability, frontend separation, and benchmark-expansion slices, and lists `7. 多轮澄清与 replan 工作流` immediately after `6. session / conversation 数据模型`.

The repository now has task `043` complete and committed. That task created the durable session and turn baseline, but it intentionally did not add session reuse or follow-up runs. This task is the smallest useful first slice of roadmap item `7` because it makes the stored conversation model executable without jumping ahead into plan versioning or exposing new public history surfaces.

This task touches these blueprint areas directly:

- PostgreSQL source of truth
- Minimal Web UI / Web demo API path
- Human-in-the-loop presentation boundary
- Future multi-turn planning and plan version evolution

## 3. Requirements

- Add a new public request model `DemoReplanRunRequest` with:
  - `user_input: str` with `min_length=1`
  - `selected_plan_index: int = 0` with `ge=0`
- Add a new public endpoint:
  - `POST /demo/runs/{run_id}/replan`
  - response model remains `DemoRunSummary`
- `POST /demo/runs/{run_id}/replan` must create a new workflow run rather than mutating the source run in place.
- The source run must remain queryable through `GET /demo/runs/{run_id}` with its original status, plans, and selected plan unchanged.
- The new replan run must reuse:
  - the source `user_id`
  - the source `session_id`
  - the source `case_id`
  - the source `tool_profile`
  - the source `world_profile`
  - the source `agent_version`
  - the source `prompt_version`
  - the source `failure_profile`
- The new replan run must use the new request’s `selected_plan_index`.
- The new replan run must have a new `run_id`.
- Add additive internal workflow request support for:
  - `existing_user_id: UUID | None`
  - `session_id: UUID | None`
  - `intent_override: LocalLifeIntent | None`
- `WeekendPilotWorkflowNodes.initialize(...)` must:
  - reuse `existing_user_id` when provided
  - raise a workflow error if `existing_user_id` is provided but the user row does not exist
  - pass `session_id` through to `AgentRunRepository.create(...)`
  - keep existing start-run behavior unchanged when the additive fields are omitted
- `WeekendPilotWorkflowNodes.parse_intent(...)` must use `intent_override` directly when provided and must not reparse `user_input` in that branch.
- Add a demo-only follow-up replan helper module responsible for deterministic merge of conversation user turns into one `LocalLifeIntent`.
- The follow-up replan helper must:
  - parse each user-authored turn independently with `DeterministicIntentParser`
  - merge in chronological order
  - let the latest explicit supported signal win
  - only support override/merge for fields that the current deterministic parser already understands:
    - scenario / participant shape
    - child-friendly implication
    - time window / duration
    - max distance
    - dining preferences
  - keep unsupported fields out of scope in this task, including:
    - origin parsing
    - budget parsing
    - plan-version semantics
    - assistant-turn semantic merge
- The merged `LocalLifeIntent` used for `intent_override` must:
  - include all user turns in chronological order in `raw_text`
  - set `parser_version` to the current deterministic parser version
  - keep `origin_text = None` in this task
- `POST /demo/runs/{run_id}/replan` must validate the source run before starting the new run:
  - source run exists
  - source run has non-null `user_id`
  - source run has non-null `session_id`
  - source session row exists
  - source session belongs to the source user
  - source run status is one of:
    - `awaiting_confirmation`
    - `declined`
    - `completed`
    - `failed`
- The replan flow must append one new user conversation turn to the existing session with:
  - `speaker_role = "user"`
  - `turn_type = "user_follow_up"`
  - `content_text = request.user_input`
  - `run_id = new run_id`
  - compact `payload_json` containing:
    - `mode = "replan"`
    - `source_run_id`
    - `source_selected_plan_id` when available, otherwise `null`
- The replan flow must append one assistant turn for the new run only when the new run has a selected plan, with:
  - `speaker_role = "assistant"`
  - `turn_type = "assistant_replan_options"`
  - `content_text` from selected plan summary, or title when summary is missing, or a fixed fallback string when both are missing
  - compact `payload_json` limited to:
    - `mode = "replan"`
    - `source_run_id`
    - `selected_plan_id`
    - `plan_ids`
    - `plan_count`
    - `run_status`
- The assistant replan turn must not store:
  - full `plan_json`
  - full tool payloads
  - full action-ledger payloads
  - raw observability metadata
- If the new run exists but ends without a selected plan, the request must still persist the new run and the `user_follow_up` turn, and must not fabricate an assistant replan turn.
- If the new workflow call fails before creating a new run (`run_id is None`), the request must roll back and must not leave a partial follow-up turn behind.
- Add compact conversation-lineage metadata to the new run under `metadata_json["demo"]["conversation"]` with:
  - `mode = "follow_up_replan_v0"`
  - `source_run_id`
  - `trigger_turn_id`
  - `source_selected_plan_id`
- Public `DemoRunSummary` must remain unchanged:
  - no `session_id`
  - no conversation history payload
  - no new internal observability fields
- Refactor the existing start-run conversation helper so assistant-turn deduplication is run-scoped rather than session-global.
- The current `POST /demo/runs`, `GET /demo/runs/{run_id}`, `POST /demo/runs/{run_id}/confirm`, and `POST /demo/runs/{run_id}/decline` contracts must continue to work.
- Do not add or modify any database migration in this task.
- Update `README.md` and `docs/WEB_DEMO_README.md` to document the new replan endpoint and note that it returns a new `run_id` while reusing the internal session.
- Add or update focused tests for:
  - route exposure
  - request validation
  - parser signal extraction or equivalent merge support
  - follow-up intent merge
  - workflow override behavior
  - demo API follow-up replanning behavior

## 4. Non-goals

- Do not expose `session_id` or conversation history in `DemoRunSummary`.
- Do not add `GET /demo/sessions`, `GET /demo/runs/{run_id}/conversation`, or any other public history endpoint.
- Do not add plan version numbers, plan lineage tables, or version-selection APIs.
- Do not add execution-manifest exposure yet.
- Do not add frontend UI changes, frontend routing changes, or new frontend state for follow-up flows.
- Do not widen this task into benchmark harness, replay harness, recovery visualization, AMAP provider work, or long-term memory governance.
- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, or unrelated local untracked files.

## 5. Interfaces and Contracts

### Inputs

- Existing public start-run request remains unchanged:
  - `POST /demo/runs`
- New public follow-up request:
  - `POST /demo/runs/{run_id}/replan`
- New request body:
  - `user_input`
  - `selected_plan_index`
- Additive internal workflow request fields:
  - `existing_user_id`
  - `session_id`
  - `intent_override`

### Outputs

- Existing `DemoRunSummary` remains the public response shape for both start and replan paths.
- Existing `conversation_sessions` rows are reused.
- New `conversation_turns` rows are appended for follow-up requests.
- Existing `agent_runs` rows for follow-up requests are created with the reused `session_id`.
- Existing public run routes keep their current response shape.

### Schemas

Public replan request:

```json
{
  "user_input": "Keep the outing nearby, but make it just me this time.",
  "selected_plan_index": 0
}
```

Follow-up user turn payload:

```json
{
  "mode": "replan",
  "source_run_id": "00000000-0000-0000-0000-000000000010",
  "source_selected_plan_id": "00000000-0000-0000-0000-000000000020"
}
```

Assistant replan turn payload:

```json
{
  "mode": "replan",
  "source_run_id": "00000000-0000-0000-0000-000000000010",
  "selected_plan_id": "00000000-0000-0000-0000-000000000030",
  "plan_ids": [
    "00000000-0000-0000-0000-000000000030"
  ],
  "plan_count": 1,
  "run_status": "awaiting_confirmation"
}
```

Additive workflow request contract:

```json
{
  "existing_user_id": "00000000-0000-0000-0000-000000000001",
  "session_id": "00000000-0000-0000-0000-000000000002",
  "intent_override": {
    "raw_text": "Original request...\nFollow-up request...",
    "scenario_type": "solo",
    "participants": {
      "adults": 1,
      "children_ages": []
    },
    "time_window": {
      "label": "this_afternoon",
      "start_at": null,
      "end_at": null,
      "duration_hours_min": 4,
      "duration_hours_max": 6
    },
    "constraints": {
      "child_friendly": false,
      "max_distance_km": 8
    },
    "activity_preferences": [],
    "dining_preferences": [
      "lighter_options"
    ],
    "origin_text": null,
    "parser_version": "deterministic_intent_parser_v1"
  }
}
```

## 6. Observability

This task does not add a new public observability surface.

The new replan run must continue to use the existing workflow timing, local trace buffer, and run summary recording already present in the workflow and demo paths. The only new persisted internal metadata in this task is compact conversation-lineage context under `metadata_json["demo"]["conversation"]` for the new replan run. No new public observability fields, no new internal observability endpoint fields, and no frontend observability panels should be added here.

## 7. Failure Handling

- If the source run does not exist, `POST /demo/runs/{run_id}/replan` must return `404`.
- If the source run has no `user_id`, no `session_id`, or the referenced session row is missing or belongs to a different user, the endpoint must return `409`.
- If the source run status is outside the allowed follow-up set, the endpoint must return `409`.
- If the workflow call returns `run_id = None`, the endpoint must fail and roll back, leaving no partial follow-up turn behind.
- If the workflow creates a new run that later ends in `failed`, the endpoint must return the new run summary for that failed run, preserve the new `user_follow_up` turn, and omit the assistant replan turn.
- If the source run has no selected plan, the endpoint must still allow follow-up replanning and must store `source_selected_plan_id = null` in the user follow-up turn payload.
- If the additive workflow contract receives an unknown `existing_user_id`, workflow initialization must fail rather than silently creating a different user.
- Existing start, get, confirm, and decline behaviors must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/044-demo-follow-up-replan-v0.md` exists and matches this task.
- [ ] `docs/plans/044-demo-follow-up-replan-v0-plan.md` exists and matches this task.
- [ ] `POST /demo/runs/{run_id}/replan` exists and validates `user_input` plus `selected_plan_index`.
- [ ] A successful replan request returns a new `DemoRunSummary` with a new `run_id`.
- [ ] The source run remains unchanged after a successful replan request.
- [ ] The new replan run reuses the source `user_id` and `session_id`.
- [ ] A successful replan request appends `user_follow_up` and `assistant_replan_options` turns in the same session with stable chronological ordering.
- [ ] The assistant replan turn stores only the compact linkage payload and does not embed full plan JSON.
- [ ] If the new run ends without a selected plan, the `user_follow_up` turn is still stored and no assistant replan turn is fabricated.
- [ ] Workflow initialization can reuse an existing user and session through additive override fields even when `external_user_id` is absent.
- [ ] The deterministic follow-up merge keeps earlier supported constraints unless a later turn explicitly overrides them.
- [ ] Public `DemoRunSummary` remains free of `session_id`, conversation history, and new internal observability fields.
- [ ] No Alembic revision is added or modified in this task.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` describe the new replan endpoint.
- [ ] No benchmark, replay, frontend, or provider contracts are changed.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_replan.py tests/test_intent_parser.py tests/test_langgraph_workflow.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_langgraph_workflow_gateway.py tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add demo follow-up replan workflow
```

## 11. Notes for the Implementer

Keep this task as the first slice of roadmap item `7. 多轮澄清与 replan 工作流`, not the whole `M4` milestone.

The key constraint is that task `043` created session persistence but still assumes one start-run baseline per session. Refactor the conversation-turn helper so deduplication is run-scoped, then add the replan path on top of that. Do not widen this task into plan versioning, public conversation history, execution manifests, or frontend controls. Those belong to later tasks after this run-anchored replan slice exists and is verified.
