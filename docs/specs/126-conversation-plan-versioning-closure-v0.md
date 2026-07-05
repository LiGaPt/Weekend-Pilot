# Spec: 126 Conversation and Plan Versioning Closure v0

## 1. Goal

Complete the closure pass for WeekendPilot's multi-turn conversation and plan-versioning behavior. The system should be able to prove, with a focused automated regression, that it is not a one-shot prompt generator: it can ask for clarification, continue after the user's answer, accept changed constraints, generate a new plan version, preserve selected-plan binding, expose an action manifest before confirmation, and avoid write actions until the user explicitly confirms.

This task is a convergence and regression-lock task, not a new product capability. The repository already contains durable conversation sessions, clarification workflow, replan workflow, selected-plan index handling, visible plan version lineage, action manifest summaries, and multi-turn benchmark support. After this task, those separate slices must be covered by one complete end-to-end path that reviewers and future implementers can trust as the canonical conversation/versioning closure proof.

## 2. Project Context

This task maps to `docs/NEXT_PHASE_ROADMAP.md` milestone `M4. 多轮对话与方案版本`.

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a conversation-style local-life planning and execution system with a strict human confirmation boundary. The relevant blueprint areas are:

- Human-in-the-loop planning before side effects
- Durable PostgreSQL-backed run/session state
- Public Web demo API and customer demo path
- Plan persistence and selected-plan handling
- Action Ledger safety after confirmation
- LocalLife-Bench and integration evidence for behavior trajectories

Current repository context:

- Task `043` added durable conversation sessions and turns.
- Task `044` added follow-up replan workflow.
- Task `045` added visible plan version lineage.
- Task `046` added action manifest summaries.
- Task `048` added clarification turns.
- Task `055` added benchmark multi-turn continuations.
- Task `059` and Task `060` hardened customer clarification and replan flows.
- Task `062` fixed selected plan index propagation for replans.
- Task `091` upgraded the pre-confirmation action list.
- Task `125` closed Mock World scenario coverage.
- Latest tracked task is `125`, and latest commit is expected to correspond to `test: lock mock world scenario coverage closure`.

This task should be the next smallest useful closure slice because it ties the already-built M4 behavior into one complete regression path without expanding runtime scope.

## 3. Requirements

- Add one focused full-path regression for the conversation/versioning closure.
- The regression must use the current Mock World path and must not depend on AMap, external map APIs, LangSmith availability, or real write providers.
- The regression must prove a vague request can enter `awaiting_clarification`.
- The clarification-pending summary must include:
  - `status = "awaiting_clarification"`
  - `plans = []`
  - `selected_plan_id = null`
  - `action_count = 0`
  - non-null `clarification`
  - `plan_version.version_label = "v1"`
- The regression must continue through `POST /demo/runs/{run_id}/clarify` or the equivalent in-process service helper.
- The clarification continuation must produce a plan-bearing run with:
  - `status = "awaiting_confirmation"`
  - at least one public plan
  - non-null `selected_plan_id`
  - `plan_version.version_label = "v1"`
  - no confirmation-side write actions already executed
- The selected plan used for replan must be non-default when at least two plans are available.
- If the fixture or service path produces only one plan, the test must fail with a clear assertion instead of silently testing index `0`.
- The replan continuation must use the selected non-default plan index.
- The replan continuation must produce a new run with:
  - `status = "awaiting_confirmation"`
  - `plan_version.version_label = "v2"`
  - `plan_version.source_run_id` pointing to the plan-bearing source run
  - `plan_version.source_selected_plan_id` matching the selected source plan
- The selected plan in the replan result must expose an `action_manifest`.
- The pre-confirmation action manifest must include:
  - `source = "proposed_actions"`
  - `action_count >= 1`
  - at least one action with `action_type`, `target_id`, and `execution_order`
- Before confirmation, no write-side Action Ledger execution rows may exist for the conversation chain.
- Confirmation must run against the current selected plan of the final replan run, not against the original v1 run.
- After confirmation, the final summary must show:
  - `status = "completed"`
  - `execution_status = "succeeded"`
  - `feedback_status = "completed"`
  - `plan_version.version_label = "v2"`
  - selected plan action manifest source changed to `confirmed_actions` when the current contract supports that source
- After confirmation, Action Ledger rows must exist only for confirmed actions from the final selected plan.
- The test must assert that the original clarification source run and original v1 plan-bearing run remain readable and are not overwritten by the v2 replan result.
- The test must assert that public summaries still do not expose:
  - `session_id`
  - raw conversation history
  - raw tool events
  - internal node history
  - trace payloads
- The test must use existing demo service or API test infrastructure. Do not add a new public endpoint or production-only test hook.
- If implemented as backend integration, the test should live in the existing integration test area or in a focused new test module.
- If implemented as frontend E2E, it must intercept or inspect real request bodies and still validate selected-plan index, version labels, action manifest preview, and confirmation behavior.
- Update README or `docs/WEB_DEMO_README.md` only if they lack a concise reference to the new closure verification command or still describe the behavior as manually verified only.
- Do not add migrations, new dependencies, new public schema fields, new action manifest schema fields, new benchmark report fields, or new Mock World cases.

## 4. Non-goals

- Do not implement a new conversation model.
- Do not change `conversation_sessions`, `conversation_turns`, `agent_runs`, `plans`, or `action_ledger` schemas.
- Do not change public request or response contracts for start, clarify, replan, confirm, decline, or run readback.
- Do not change plan version numbering rules.
- Do not change action manifest shape or action execution semantics.
- Do not add a new benchmark suite unless the existing test infrastructure cannot cover this closure path.
- Do not add AMap coverage.
- Do not add recovery or safe-stop coverage; that belongs to a later recovery closure task.
- Do not change memory governance behavior.
- Do not refresh or commit generated `var/` artifacts unless a verification command intentionally changes a tracked artifact and the change is required for this task.
- Do not commit `.env`, API keys, tokens, secrets, caches, virtual environments, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

Use the existing public demo contracts or their in-process service equivalents:

- `POST /demo/runs`
- `POST /demo/runs/{run_id}/clarify`
- `POST /demo/runs/{run_id}/replan`
- `POST /demo/runs/{run_id}/confirm`
- `GET /demo/runs/{run_id}`

The start input must be intentionally vague enough to trigger clarification, for example:

```json
{
  "user_input": "Plan something nearby for later.",
  "external_user_id": "conversation-closure-user",
  "display_name": "Conversation Closure User",
  "case_id": "conversation-closure-v0",
  "selected_plan_index": 0,
  "read_profile": "mock_world",
  "mock_world_profile": "solo_afternoon"
}
```

The clarification input must be specific enough to produce plans, for example:

```json
{
  "user_input": "This afternoon I want a nearby solo outing for a few hours.",
  "selected_plan_index": 0
}
```

The replan input must select a non-default source plan index when at least two plans exist, for example:

```json
{
  "user_input": "Keep it nearby, but make it indoor this time.",
  "selected_plan_index": 1
}
```

### Outputs

The closure regression must verify public-safe summaries across the chain:

```json
[
  {
    "mode": "start",
    "status": "awaiting_clarification",
    "version_label": "v1",
    "selected_plan_id": null
  },
  {
    "mode": "clarify",
    "status": "awaiting_confirmation",
    "version_label": "v1",
    "selected_plan_id": "source-plan-id"
  },
  {
    "mode": "replan",
    "status": "awaiting_confirmation",
    "version_label": "v2",
    "source_selected_plan_id": "source-plan-id"
  },
  {
    "mode": "confirm",
    "status": "completed",
    "version_label": "v2",
    "execution_status": "succeeded"
  }
]
```

### Schemas

This task introduces no new runtime schema.

Expected pre-confirmation selected-plan action manifest shape:

```json
{
  "source": "proposed_actions",
  "action_count": 1,
  "actions": [
    {
      "action_ref": "draft_1_action_1",
      "execution_order": 1,
      "action_type": "reserve_restaurant",
      "target_id": "restaurant_light_001",
      "payload_preview": {
        "party_size": 1
      },
      "reason": "Confirm to lock the selected action."
    }
  ]
}
```

The exact values inside `action_ref`, `target_id`, `payload_preview`, and `reason` may follow existing implementation output. The regression should assert the stable contract fields and non-empty action list, not brittle copy.

## 6. Observability

This task does not add a new observability backend, API endpoint, telemetry schema, LangSmith requirement, Redis key, or database table.

It must preserve existing public-safety redaction:

- no `session_id` in public summaries
- no raw conversation turn history in public summaries
- no raw tool events in public summaries
- no trace payloads in public summaries
- no internal node history in public summaries

The new test is itself the evidence surface. If documentation is updated, it should point to the verification command rather than creating a new report format.

## 7. Failure Handling

- If the vague start request does not enter `awaiting_clarification`, the test must fail and report the actual status.
- If the clarification reply does not produce at least two plans, the selected-plan-index branch cannot be proven and the test must fail with a clear message.
- If replan returns `v1` instead of `v2`, the test must fail because version advancement is broken.
- If `source_selected_plan_id` does not match the selected non-default v1 plan, the test must fail because the replan source binding is broken.
- If any write action exists before confirmation, the test must fail because the confirmation boundary is broken.
- If confirmation executes against the wrong run or wrong selected plan, the test must fail through action ledger or summary assertions.
- If local integration prerequisites are missing, the implementer must run all non-integration focused tests and report the exact blocker.

## 8. Acceptance Criteria

- [ ] `docs/specs/126-conversation-plan-versioning-closure-v0.md` exists and matches this task.
- [ ] `docs/plans/126-conversation-plan-versioning-closure-v0-plan.md` exists and matches this task.
- [ ] A focused automated regression covers `start -> clarify -> replan -> confirm`.
- [ ] The start step proves `awaiting_clarification`, empty plans, no selected plan, no actions, and visible `v1`.
- [ ] The clarify step proves plan generation resumes in the conversation and remains visible `v1`.
- [ ] The replan step proves a non-default selected source plan index is honored.
- [ ] The replan step proves visible version advances to `v2`.
- [ ] The replan step proves `source_selected_plan_id` matches the selected source plan.
- [ ] The selected v2 plan exposes a pre-confirmation action manifest with `source = "proposed_actions"`.
- [ ] No write-side Action Ledger rows are created before confirmation.
- [ ] Confirmation executes only after the final v2 run is confirmed.
- [ ] The confirmed final summary reaches `completed` with successful execution and feedback.
- [ ] Public summaries still do not expose session IDs, raw conversation history, raw tool events, trace payloads, or internal node history.
- [ ] Existing focused clarification, replan, versioning, action manifest, and demo API tests remain green.
- [ ] No public API schema, database schema, migration, action manifest schema, benchmark report schema, dependency, or Mock World fixture is added.
- [ ] No `.env`, API key, token, secret, cache, virtual environment, generated artifact, or unrelated local file is staged.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except pre-existing unrelated untracked files.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py tests/test_demo_api.py -q
python -m pytest tests/integration/test_demo_api_gateway.py -v
python -m pytest tests/test_benchmark_harness.py -q
npm --prefix frontend run test -- --run src/App.test.tsx
npm --prefix frontend run e2e
git diff --check
git status --short
```

If the new closure test is added outside `tests/integration/test_demo_api_gateway.py`, include that exact test module in the focused pytest command.

## 10. Expected Commit

```text
test: lock conversation and plan versioning closure
```

## 11. Notes for the Implementer

Keep this task as a closure test. Prefer adding one complete regression over changing production behavior.

Current known repository facts from planning:

- `docs/specs` and `docs/plans` currently match through Task `125`.
- There is a historical Task `122` numbering gap and a special `113.5`; do not backfill or renumber them.
- The current branch observed during planning is `codex/125-mock-world-scenario-coverage-closure-v0`.
- Latest commit observed during planning is `f046090 test: lock mock world scenario coverage closure`.
- Existing untracked local files include `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, and `docs/superpowers/`; do not stage them unless the user gives a separate instruction.
- There is no `tests/test_action_manifest.py` in the current tree; action manifest assertions should use the actual existing service/API/frontend tests or a new focused closure test.
