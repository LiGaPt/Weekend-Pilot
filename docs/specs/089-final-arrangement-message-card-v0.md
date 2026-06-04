# Spec: 089 Final Arrangement Message Card v0

## 1. Goal

This task adds a customer-facing final arrangement message card for the confirmed execution path.

The repository already has the full post-confirmation chain: `wait_confirmation -> saga_execution_engine -> generate_summary_message`, persisted execution feedback, and a frontend assistant result card. The remaining gap is product closure. After a reviewer confirms a plan on the customer page, the visible result should not stop at a generic execution summary. It should show one concise, user-copyable final arrangement message such as “搞定了，下午 2 点出发……”, derived from the selected plan and the confirmed execution result.

After this task is complete, the customer surface should present a stable “final arrangement message” as the primary post-confirmation takeaway, while keeping existing execution evidence, confirmation safety, and workflow structure intact.

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in two direct ways:

- It completes the user-facing intent of `generate_summary_message` in the V1 optimized workflow DAG.
- It improves the Minimal Web UI primary demo path without changing workflow routing, confirmation rules, or execution safety.

This task maps most directly to `docs/NEXT_PHASE_ROADMAP.md` milestone `M4. 多轮对话与方案版本`, because it strengthens the conversation-style planning flow by making the final post-confirmation state read like a finished arrangement rather than a raw execution log.

Relevant architecture areas:

- Deterministic service layer
- Human-in-the-loop confirmation boundary
- Execution workflow
- Feedback writing
- Minimal Web UI / customer-safe surface

This task must not change:

- Tool Gateway behavior
- PostgreSQL source-of-truth boundaries
- Redis runtime contract
- benchmark gate rules
- internal observability contracts

## 3. Requirements

- Use new task ID `089`.
- Keep `docs/specs` and `docs/plans` continuous and slug-matched through `089`.
- Keep the current workflow node sequence unchanged:
  - `wait_confirmation`
  - `saga_execution_engine`
  - `generate_summary_message`
- Do not add a new workflow node for this task.
- The backend must produce one customer-facing final arrangement message for confirmed runs with persisted feedback.
- The final arrangement message must be derived from the selected reviewed plan plus execution/feedback state, not from ad hoc frontend-only reconstruction.
- The final arrangement message must be stored in persisted plan feedback metadata so `GET /demo/runs/{run_id}` can reconstruct it after refresh.
- The final arrangement message must be additive and must not remove the existing feedback fields:
  - `headline`
  - `message`
  - `completed_actions`
  - `failed_actions`
  - `next_steps`
- The final arrangement message must be concise, Chinese, and directly user-copyable.
- The default happy-path family copy must include an explicit departure cue equivalent to “下午 2 点出发”.
- The message must reflect actual execution outcome:
  - full success -> arranged tone
  - partial success -> arranged with follow-up needed tone
  - failed -> no false “搞定了” wording
  - declined -> no final-arranged wording
- The message must not claim any write action succeeded unless execution feedback shows it succeeded or was already completed.
- The frontend assistant result card must visually promote the final arrangement message above the lower-level execution detail.
- The frontend assistant result card must provide a one-click copy action for the final arrangement message.
- The copy action must show brief inline success or failure feedback without page reload.
- Existing execution timeline disclosure must remain available and collapsed by default.
- Existing completed/failed action lists must remain available.
- Existing customer-safe redaction rules must remain unchanged.
- `frontend/src/chat/thread.ts` must project the final arrangement message into the result card view model.
- `frontend/src/chat/ConversationThread.tsx` must render the final arrangement message as the primary body of the result card when present.
- The public API may change only additively if required.
- If a new public field is added, it must be additive under the existing feedback object rather than reshaping the top-level run schema.
- The final arrangement message contract must be documented in `README.md` and `docs/WEB_DEMO_README.md`.
- Update focused tests covering:
  - feedback persistence
  - demo API readback
  - thread projection
  - result-card rendering
  - customer e2e confirmation flow

## 4. Non-goals

- Do not add a new conversation card type separate from the existing assistant result card.
- Do not redesign the customer page layout beyond the result-card refinement needed for this task.
- Do not add generic clipboard infrastructure for unrelated cards.
- Do not change confirmation, execution, or Action Ledger semantics.
- Do not change benchmark grading or release-gate rules.
- Do not add a new workflow persistence table or migration.
- Do not add new dependencies.
- Do not commit `.env`, API keys, tokens, secrets, generated `dist/`, or runtime artifacts.

## 5. Interfaces and Contracts

### Inputs

- `DeterministicFeedbackWriter.write_execution_feedback(run_id, plan_id)`
- Persisted reviewed plan JSON with:
  - `draft`
  - `timeline`
  - `execution`
  - `feedback`
- Public demo readback through:
  - `GET /demo/runs/{run_id}`

### Outputs

- Persisted feedback metadata includes one new additive field for the final arrangement message.
- Public demo response includes that same persisted field under the existing feedback object.
- Customer assistant result card renders the message and exposes copy interaction.

### Schemas

This task introduces one additive persisted/public field inside `feedback`:

```json
{
  "feedback": {
    "schema_version": "execution_feedback_v1",
    "writer_version": "deterministic_feedback_writer_v1",
    "status": "completed",
    "run_status": "completed",
    "headline": "安排已完成",
    "message": "安排已完成，2 项操作已完成，0 项需要处理。",
    "final_arrangement_message": "搞定了，下午 2 点出发，先去亲子科学中心，再到轻食餐厅吃晚餐；订座和后续消息都已安排好。",
    "completed_actions": [],
    "failed_actions": [],
    "next_steps": [
      "按确认后的时间出发，出门前再看一眼天气和路况。"
    ],
    "generated_at": "2026-06-03T12:00:00Z"
  }
}
```

Required message behavior by status:

```json
{
  "status_rules": {
    "completed": {
      "must_sound_arranged": true,
      "must_not_hide_success_scope": true
    },
    "partially_completed": {
      "must_sound_partially_arranged": true,
      "must_call_out_follow_up_needed": true
    },
    "failed": {
      "must_not_use": ["搞定了", "已安排好", "都已安排好"]
    },
    "declined": {
      "result_card_stays_existing": true,
      "no_final_arrangement_message_required": true
    }
  }
}
```

### Message Composition Rules

The implementation must follow these defaults unless source data is missing:

- Start with:
  - `completed`: `搞定了，`
  - `partially_completed`: `先帮你安排了可完成的部分，`
  - `failed`: `这次还没安排成功，`
- Departure cue:
  - Prefer timeline first activity `start_label`
  - For common `14:00`-like values, render `下午 2 点出发`
  - If no parsable start time exists, omit departure sentence rather than inventing one
- Plan summary:
  - Prefer `draft.activity.name` and `draft.dining.name`
  - Render as `先去{activity}，再到{dining}`
- Outcome suffix:
  - If `completed_actions` contains both dining reservation and message send success, allow wording equivalent to `订座和后续消息都已安排好`
  - If only some actions succeeded, say which were completed and note remaining follow-up
  - If no actions succeeded, do not present it as arranged

## 6. Observability

This task does not add new trace schemas, benchmark artifact fields, Redis events, or database tables.

It only adds one additive persisted feedback field inside existing plan JSON and exposes it through the existing demo read path. Existing workflow node history, observability summaries, and benchmark reports remain unchanged.

## 7. Failure Handling

- If the selected plan is missing reviewed draft data, the writer must fall back to the existing generic feedback fields and may omit `final_arrangement_message`.
- If execution metadata is malformed, keep current feedback-writer failure behavior.
- If no reliable departure time can be derived, omit the departure clause rather than inventing one.
- If action success scope is partial or failed, the message must degrade conservatively and must not overclaim success.
- If clipboard copy fails in the frontend, show non-blocking inline failure feedback.
- If older persisted plans do not contain `final_arrangement_message`, the frontend must fall back to the existing result-card message rendering.

## 8. Acceptance Criteria

- [ ] The latest completed baseline remains task `088`, and this task is a new `089`.
- [ ] `docs/specs` and `docs/plans` are continuous and slug-matched through `089`.
- [ ] The workflow graph still ends with existing `generate_summary_message`; no new node is added.
- [ ] Confirmed happy-path runs persist `feedback.final_arrangement_message`.
- [ ] `GET /demo/runs/{run_id}` returns `feedback.final_arrangement_message` for confirmed runs after refresh.
- [ ] The default successful customer happy path shows a copyable Chinese final arrangement message equivalent to “搞定了，下午 2 点出发...”.
- [ ] The final arrangement message is derived from persisted plan/execution state and does not overclaim unexecuted actions.
- [ ] Partial-success runs use cautious wording and clearly indicate follow-up is still needed.
- [ ] Failed runs do not use “搞定了” or equivalent fully-arranged wording.
- [ ] Declined runs keep existing behavior and do not require a final arrangement message.
- [ ] The assistant result card promotes the final arrangement message above the lower-level execution timeline.
- [ ] The result card provides a one-click copy action for the final arrangement message.
- [ ] Existing execution timeline disclosure remains available and collapsed by default.
- [ ] Existing customer-safe redaction behavior remains unchanged.
- [ ] `tests/integration/test_feedback_writer_gateway.py` passes.
- [ ] Focused confirm/readback assertions in `tests/integration/test_demo_api_gateway.py` pass.
- [ ] `frontend/src/chat/thread.test.ts` and `frontend/src/chat/ConversationThread.test.tsx` pass.
- [ ] `npm --prefix frontend run build` passes.
- [ ] Customer confirmation Playwright smoke passes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/integration/test_feedback_writer_gateway.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k "confirm" -q
npm --prefix frontend run test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "confirms, and shows feedback"
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
feat: add final arrangement message card
```

## 11. Notes for the Implementer

Current repository facts relevant to this task:

- `docs/specs` and `docs/plans` are continuous and matched through `088`.
- Latest commit is `6c6b5a3 fix: localize multi-scenario customer demo display`, which aligns with task `088`.
- The repo already contains the exact adjacent product seam for this task:
  - workflow node `generate_summary_message`
  - persisted `feedback`
  - customer `assistant_result_card`

Implementation should stay minimal:

- Prefer one additive field under `feedback`
- Reuse the existing result card instead of inventing a second post-confirmation card
- Keep the message-generation logic deterministic and conservative

The implementer should stop and report back if completing this task appears to require:

- a new workflow node
- a new database table or migration
- a broad public API reshape
- scenario-specific copy policy beyond the existing reviewed-plan and execution data
