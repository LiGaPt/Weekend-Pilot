# Spec: 048 Demo Clarification Turn Workflow v0

## 1. Goal

Add the first deterministic clarification-turn workflow for the Web demo so WeekendPilot can stop before planning when key supported constraints are missing, ask the user a focused follow-up question, and continue planning in the same durable conversation session after the user replies.

The current repository already supports durable conversation sessions, same-session follow-up replanning, visible plan version lineage, and stable action manifests. However, it still skips the earlier conversation step that `docs/PROJECT_BLUEPRINT.md` calls out explicitly: asking for clarification before planning when the request is too underspecified. After this task, a vague demo request must be able to end in `awaiting_clarification` instead of `failed` or premature plan generation, and a clarification reply must be able to create a new run in the same session and continue the planning path.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` describes WeekendPilot as a conversation-style planning system and explicitly states that the Supervisor decides when to ask the user for clarification. `docs/NEXT_PHASE_ROADMAP.md` places this work under milestone `M4. 多轮对话与方案版本`, specifically the unfinished half of roadmap item `7. 多轮澄清与 replan 工作流`.

The repository has already completed the adjacent groundwork:

- Task `043` added durable `conversation_sessions`, `conversation_turns`, and `agent_runs.session_id`.
- Task `044` added same-session follow-up replanning after a run already has plan output.
- Task `045` added public plan-version lineage.
- Task `046` added the stable action-manifest summary.
- Task `047` added deterministic memory-query policy, so pre-planning intent shaping now has one real read-only memory layer.

That means the next missing product behavior is not another generic replan slice. The next missing behavior is the earlier branch where the system must ask for missing information before it generates plans.

This task touches these blueprint areas directly:

- LangGraph workflow state and routing
- PostgreSQL source of truth through durable session turns and run metadata
- Minimal Web UI / Web demo API path
- Human-in-the-loop conversation flow before confirmation
- Plan version lineage semantics for multi-run conversations

## 3. Requirements

- Add a new valid workflow terminal status:
  - `awaiting_clarification`
- `WorkflowStatus` must support:
  - `awaiting_clarification`
  - `awaiting_confirmation`
  - `completed`
  - `failed`
  - `error`
- `WeekendPilotWorkflowRunner` must preserve `awaiting_clarification` as a valid result status instead of coercing it to `error`.
- Workflow observability recording must treat `awaiting_clarification` as a valid completed run boundary, the same way it already treats `awaiting_confirmation`, `completed`, and `failed`.

- Add one new pure deterministic clarification helper module.
- The helper contract for v0 must be:

```text
apply_clarification_policy(intent: LocalLifeIntent) -> ClarificationPolicySummary | None
```

- Add a new compact summary model `ClarificationPolicySummary`.
- `ClarificationPolicySummary` must include exactly:
  - `policy_version: str`
  - `missing_fields: list[str]`
  - `question_text: str`
- `policy_version` must be `clarification_policy_v0`.

- The clarification policy must only block on these supported dimensions in v0:
  - `scenario_or_participants`
  - `time_window`
- The clarification policy must not block on these dimensions in v0:
  - `max_distance_km`
  - `dining_preferences`
  - `activity_preferences`
  - `origin_text`
  - budget or price constraints

- `scenario_or_participants` must be considered missing only when all of these are true:
  - `intent.scenario_type == "unknown"`
  - `intent.participants.adults == 1`
  - `intent.participants.children_ages == []`
  - `intent.constraints.child_friendly == false`
- `time_window` must be considered missing only when all of these are `None`:
  - `intent.time_window.label`
  - `intent.time_window.start_at`
  - `intent.time_window.end_at`
  - `intent.time_window.duration_hours_min`
  - `intent.time_window.duration_hours_max`

- The exact public clarification question text must be:
  - when both dimensions are missing:
    - `为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。`
  - when only `scenario_or_participants` is missing:
    - `为了继续规划，请补充这次是谁一起去。`
  - when only `time_window` is missing:
    - `为了继续规划，请补充大概什么时间出发、准备玩多久。`

- `WeekendPilotWorkflowNodes.generate_queries(...)` must:
  - apply the existing memory-query policy first
  - evaluate the clarification policy on the effective intent
  - when clarification is required:
    - persist the compact summary under `agent_runs.metadata_json["workflow"]["clarification"]`
    - update `agent_runs.status` to `awaiting_clarification`
    - return workflow state with `status = "awaiting_clarification"`
    - skip `DeterministicQueryPlanner.build(...)`
    - skip supervisor assignment generation
    - skip search execution and everything downstream
  - when clarification is not required:
    - keep the current behavior unchanged

- `backend/app/workflow/graph.py` must no longer route unconditionally from `generate_queries` to `execute_searches`.
- Add a conditional route after `generate_queries` so the graph:
  - continues to `execute_searches` when planning should proceed
  - ends immediately when status is `awaiting_clarification`
  - still ends safely for `failed` or `error`

- Add a new public response model `DemoClarificationSummary`.
- `DemoClarificationSummary` must include exactly:
  - `prompt: str`
  - `missing_fields: list[str]`
- Add a new nullable field `clarification` to public `DemoRunSummary`.
- `DemoRunSummary.clarification` must be:
  - populated from the persisted workflow clarification summary when `run.status == "awaiting_clarification"`
  - `null` for all other run statuses

- Add a new public request model `DemoClarifyRunRequest` with:
  - `user_input: str` with `min_length=1`
  - `selected_plan_index: int = 0` with `ge=0`
- Add a new public endpoint:
  - `POST /demo/runs/{run_id}/clarify`
  - response model remains `DemoRunSummary`

- `POST /demo/runs/{run_id}/clarify` must validate the source run before starting the continuation run:
  - source run exists
  - source run status is exactly `awaiting_clarification`
  - source run has non-null `user_id`
  - source run has non-null `session_id`
  - source session row exists
  - source session belongs to the same user as the source run

- The clarification continuation run must create a new workflow run rather than mutating the source run in place.
- The clarification continuation run must reuse:
  - the source `user_id`
  - the source `session_id`
  - the source `case_id`
  - the source `tool_profile`
  - the source `world_profile`
  - the source `agent_version`
  - the source `prompt_version`
  - the source `failure_profile`
- The clarification continuation run must use the new request’s `selected_plan_index`.

- The clarification continuation run must build `intent_override` from all user-authored turns in the session plus the new clarification reply.
- Reuse `build_follow_up_intent(...)` for this merge path.
- `build_follow_up_intent(...)` must additionally merge explicit `activity_preferences` when a later user turn contains supported explicit style text.
- The supported explicit activity-style merge for follow-up intent remains limited to:
  - `citywalk`
  - `indoor`
  - `outdoor`
- Existing follow-up merge behavior for scenario, participants, time window, max distance, and dining preferences must remain intact.

- Conversation-turn persistence for clarification must follow these exact rules:
  - an initial vague start-run request persists:
    - `user_request`
    - `assistant_clarification_request`
  - a clarification reply persists:
    - `user_clarification_reply`
  - a clarification continuation run that reaches plan presentation persists:
    - `assistant_plan_options`
  - a clarification continuation run that still lacks required fields persists:
    - `assistant_clarification_request`
- `assistant_clarification_request` must use:
  - `speaker_role = "assistant"`
  - `turn_type = "assistant_clarification_request"`
  - `content_text = question_text`
  - compact `payload_json` limited to:
    - `missing_fields`
    - `run_status`
- `user_clarification_reply` must use:
  - `speaker_role = "user"`
  - `turn_type = "user_clarification_reply"`
  - `content_text = request.user_input`
  - compact `payload_json` limited to:
    - `mode = "clarify"`
    - `source_run_id`
    - `source_missing_fields`
- The clarification turns must not store:
  - full `plan_json`
  - full workflow state
  - raw observability payloads
  - session IDs
  - trace IDs
  - prompt text beyond the user-visible clarification question itself

- Clarification-pending runs must not fabricate plan state.
- When a run ends in `awaiting_clarification`:
  - `selected_plan_id` must remain `null`
  - no `assistant_plan_options` turn may be written for that run
  - `plans` must remain empty in the public summary
  - `action_count` must remain `0`

- Persist compact clarification continuation metadata on the new reply-generated run under `metadata_json["demo"]["conversation"]` with:
  - `mode = "clarification_turn_v0"`
  - `source_run_id`
  - `trigger_turn_id`
  - `source_missing_fields`

- Plan-version semantics for clarification must be plan-based, not run-count-based.
- A source run that ends in `awaiting_clarification` and has no selected plan must still serialize as `v1`.
- A clarification continuation run spawned from a source run with `selected_plan_id = null` must keep the same `version_number` as the source run instead of incrementing.
- For clarification continuations, `plan_version.source_run_id` must point to the immediate clarification source run.
- For clarification continuations from a no-plan source run, `plan_version.source_selected_plan_id` must remain `null`.
- Existing replan behavior from a plan-bearing run must keep the current increment semantics from task `045`.

- `POST /demo/runs/{run_id}/replan` must remain unchanged in this task.
- Clarification-pending source runs must continue to be rejected by the replan path.
- Existing `POST /demo/runs`, `GET /demo/runs/{run_id}`, `POST /demo/runs/{run_id}/confirm`, and `POST /demo/runs/{run_id}/decline` behavior must remain unchanged apart from the additive clarification field and the new clarification status path.

- Update `README.md` and `docs/WEB_DEMO_README.md` to document:
  - the `awaiting_clarification` run state
  - the new `POST /demo/runs/{run_id}/clarify` endpoint
  - the fact that clarification-only runs stay on the same visible `v1` until the first actual plan is produced

- Add or update focused tests for:
  - clarification policy detection
  - follow-up intent merge for `activity_preferences`
  - workflow routing into `awaiting_clarification`
  - route exposure and request validation for `/demo/runs/{run_id}/clarify`
  - clarification-specific version semantics
  - demo API clarification workflow integration

- Do not add or modify any Alembic revision in this task.
- Do not add new dependencies.

## 4. Non-goals

- Do not add a Web demo clarification form or any frontend clarification controls in this task.
- Do not add `GET /demo/runs/{run_id}/conversation`, `GET /demo/sessions`, or any public conversation-history API.
- Do not widen clarification detection to origin parsing, budget parsing, or broader preference elicitation.
- Do not convert validator/recovery `ask_user` decisions from later workflow stages into the same public clarification workflow in this task.
- Do not change benchmark harness contracts, replay contracts, provider contracts, or internal observability response contracts.
- Do not redesign public replan behavior, plan version lineage, or action-manifest shape beyond the clarification-specific version rule described above.
- Do not add or modify database tables, columns, indexes, or migrations.
- Do not add new dependencies.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, `qc`, or unrelated untracked local documentation files.

## 5. Interfaces and Contracts

### Inputs

- Existing public start-run request:
  - `POST /demo/runs`
- New public clarification reply request:
  - `POST /demo/runs/{run_id}/clarify`
- Existing same-session user-turn history from `conversation_turns`
- Existing deterministic follow-up merge helper:
  - `build_follow_up_intent(...)`
- Existing workflow pre-planning path:
  - `parse_intent`
  - `load_memory`
  - `generate_queries`

### Outputs

- A new workflow terminal status:
  - `awaiting_clarification`
- A new public additive response field:
  - `DemoRunSummary.clarification`
- A new public continuation endpoint:
  - `POST /demo/runs/{run_id}/clarify`
- New clarification conversation turns in existing `conversation_turns`
- New compact run metadata:
  - `agent_runs.metadata_json["workflow"]["clarification"]`
  - `agent_runs.metadata_json["demo"]["conversation"]` for clarification reply-generated runs

### Schemas

Public clarification summary response excerpt:

```json
{
  "run_id": "00000000-0000-0000-0000-000000000010",
  "status": "awaiting_clarification",
  "selected_plan_id": null,
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
  "clarification": {
    "prompt": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
    "missing_fields": [
      "scenario_or_participants",
      "time_window"
    ]
  }
}
```

Public clarification reply request:

```json
{
  "user_input": "今天下午一个人出门玩几个小时，别太远。",
  "selected_plan_index": 0
}
```

Persisted workflow clarification metadata excerpt:

```json
{
  "workflow": {
    "clarification": {
      "policy_version": "clarification_policy_v0",
      "missing_fields": [
        "scenario_or_participants",
        "time_window"
      ],
      "question_text": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。"
    }
  }
}
```

Clarification reply turn payload excerpt:

```json
{
  "mode": "clarify",
  "source_run_id": "00000000-0000-0000-0000-000000000010",
  "source_missing_fields": [
    "scenario_or_participants",
    "time_window"
  ]
}
```

Clarification continuation demo metadata excerpt:

```json
{
  "demo": {
    "conversation": {
      "mode": "clarification_turn_v0",
      "source_run_id": "00000000-0000-0000-0000-000000000010",
      "trigger_turn_id": "00000000-0000-0000-0000-000000000099",
      "source_missing_fields": [
        "scenario_or_participants",
        "time_window"
      ]
    }
  }
}
```

## 6. Observability

This task must add only one new internal observability-shaped metadata block:

- `agent_runs.metadata_json["workflow"]["clarification"]`

That block must stay compact and sanitized. It exists to explain why the workflow stopped before planning and which supported dimensions were still missing.

This task must not add:

- a new public observability field
- a new internal observability endpoint field
- a new PostgreSQL table
- a new Redis key
- a new LangSmith contract requirement

The workflow runner must still record the normal run summary path for clarification-pending runs so internal review can see that the run stopped intentionally instead of crashing.

## 7. Failure Handling

- If the source run for `POST /demo/runs/{run_id}/clarify` does not exist, return `404`.
- If the source run does not have status `awaiting_clarification`, return `409`.
- If the source run has no `user_id`, no `session_id`, or the referenced session row is missing or belongs to a different user, return `409`.
- If the workflow call for a clarification reply returns `run_id = null`, roll back and do not leave a partial `user_clarification_reply` turn behind.
- If the clarification reply is still too vague, the new continuation run may also end in `awaiting_clarification`; that is a valid success path, not an error.
- If a clarification continuation run reaches planning and later fails through normal workflow behavior, existing failure handling must remain unchanged.
- Existing start, get, replan, confirm, and decline status-code behavior must remain unchanged outside the clarification-specific additions in this spec.

## 8. Acceptance Criteria

- [ ] `docs/specs/048-demo-clarification-turn-workflow-v0.md` exists and matches this task.
- [ ] `docs/plans/048-demo-clarification-turn-workflow-v0-plan.md` exists and matches this task.
- [ ] Workflow status typing and runner result handling now support `awaiting_clarification`.
- [ ] A vague start-run request can end successfully in `awaiting_clarification` instead of `failed`.
- [ ] An `awaiting_clarification` run returns `plans = []`, `selected_plan_id = null`, and a non-null `clarification` summary.
- [ ] The persisted workflow clarification metadata contains only `policy_version`, `missing_fields`, and `question_text`.
- [ ] `POST /demo/runs/{run_id}/clarify` exists and validates `user_input` plus `selected_plan_index`.
- [ ] A clarification reply creates a new run in the same session instead of mutating the source run.
- [ ] The clarification reply-generated run reuses the source `user_id` and `session_id`.
- [ ] The clarification conversation turns are appended with the exact new turn types defined in this spec.
- [ ] `build_follow_up_intent(...)` now preserves later explicit activity-style signals.
- [ ] A clarification-only source run stays at `v1`, and the first plan-bearing clarification continuation run also stays at `v1`.
- [ ] Later replans from that first plan-bearing run still increment normally to `v2`, `v3`, and so on.
- [ ] `POST /demo/runs/{run_id}/replan` continues to reject clarification-pending source runs.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the clarification path.
- [ ] No Alembic revision, dependency, benchmark contract, replay contract, provider contract, or frontend UI contract is changed.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, `qc`, or unrelated local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any blocker is reported clearly.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py tests/test_langgraph_workflow.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add demo clarification turn workflow
```

## 11. Notes for the Implementer

Keep this task intentionally narrow. This is the pre-planning clarification slice that the current conversation roadmap is missing.

The key boundaries are:

- clarification is deterministic and pre-planning in v0
- only `scenario_or_participants` and `time_window` are blocking fields in this slice
- no frontend clarify UI belongs here
- no generic recovery `ask_user` conversion belongs here
- clarification-only runs must not consume a new visible plan version number

If the current working tree still contains unrelated local files or doc drafts, do not mix them into this task’s staged set.
