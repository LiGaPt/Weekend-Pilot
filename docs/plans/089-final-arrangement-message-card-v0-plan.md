# Plan: 089 Final Arrangement Message Card v0

## 1. Spec Reference

Spec file:

```text
docs/specs/089-final-arrangement-message-card-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is the post-`088` branch state, with latest commit `6c6b5a3 fix: localize multi-scenario customer demo display`.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `088`.
- The current workflow already contains `generate_summary_message` and persists feedback into reviewed plan JSON.
- The public customer surface already renders a post-confirmation `assistant_result_card`.
- `DeterministicFeedbackWriter` already computes:
  - `headline`
  - `message`
  - `completed_actions`
  - `failed_actions`
  - `next_steps`
- The frontend currently renders generic result messaging from `feedback.headline` and `feedback.message`.
- No unfinished spec/plan sequence or in-progress branch takes precedence over this task based on the current repository evidence provided by the latest commit and continuous docs chain.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/feedback/schemas.py` - add additive typed field for `final_arrangement_message` if the feedback schema layer needs explicit support.
- `backend/app/feedback/writer.py` - deterministically derive and persist the final arrangement message from reviewed plan + execution result.
- `backend/app/demo/service.py` - ensure existing demo projection keeps exposing the persisted additive feedback field if explicit filtering currently drops it.
- `backend/app/demo/schemas.py` - add additive public schema support only if the current typed response model requires it.
- `tests/integration/test_feedback_writer_gateway.py` - verify persisted and returned `final_arrangement_message` for successful and partial cases.
- `tests/integration/test_demo_api_gateway.py` - verify confirm/readback path exposes the final arrangement message.
- `frontend/src/types/demo.ts` - add additive type field under feedback summary if needed.
- `frontend/src/chat/thread.ts` - project the final arrangement message into the result-card view model with fallback behavior.
- `frontend/src/chat/ConversationThread.tsx` - render the final arrangement message prominently and add copy interaction.
- `frontend/src/chat/thread.test.ts` - verify projection logic and fallback behavior.
- `frontend/src/chat/ConversationThread.test.tsx` - verify rendered card content and copy control behavior.
- `frontend/e2e/demo.spec.ts` - extend the existing confirm-result smoke with final arrangement message assertions.
- `README.md` - update customer demo/result description.
- `docs/WEB_DEMO_README.md` - document the final arrangement message in the confirm flow.

## 5. Implementation Steps

1. Confirm the current typed feedback contract.
   - Inspect `backend/app/feedback/schemas.py`, `backend/app/demo/schemas.py`, and `frontend/src/types/demo.ts`.
   - Determine whether `feedback` is passed through as typed fields or generic dict fragments.
   - Choose the smallest additive field change needed so `final_arrangement_message` can persist end to end.

2. Implement deterministic backend message composition in `backend/app/feedback/writer.py`.
   - Add a private helper that derives a final arrangement message from:
     - feedback status
     - reviewed draft activity/dining names
     - timeline first activity start label
     - completed and failed action summaries
   - Keep the helper conservative:
     - only use “搞定了” for full success
     - partial success must explicitly note remaining follow-up
     - failure must not sound complete
   - Normalize time wording:
     - parse common `14:00` / `2:00 PM` style labels into a simple Chinese departure cue when reliable
     - otherwise omit the departure clause
   - Prefer candidate names already present in reviewed draft data.
   - Persist the result under `feedback.final_arrangement_message`.

3. Keep persistence and readback additive.
   - Update the persisted `feedback` payload to include `final_arrangement_message` without changing existing keys.
   - If typed response schemas require explicit fields, add only this one additive field under feedback.
   - Verify `GET /demo/runs/{run_id}` returns the new field after confirm + refresh.

4. Update backend tests first.
   - In `tests/integration/test_feedback_writer_gateway.py`:
     - add a successful execution assertion that `final_arrangement_message` exists and contains arranged wording
     - assert persisted plan JSON also contains the same value
     - add a partial-success case with cautious wording
     - if an existing failure fixture is available, assert no “搞定了” wording on failure
   - In `tests/integration/test_demo_api_gateway.py`:
     - extend the confirm path assertions to check the returned/read-back plan feedback includes `final_arrangement_message`
     - assert the message is stable across re-fetch, not only immediate response

5. Update frontend types and thread projection.
   - Add `final_arrangement_message?: string | null` to the relevant feedback type if needed.
   - In `frontend/src/chat/thread.ts`:
     - add a `finalArrangementMessage` field to `AssistantResultCardItem`
     - source it from `plan.feedback.final_arrangement_message`
     - keep fallback to existing `feedback.message` when the new field is absent
   - Do not introduce a new card kind; keep using `assistant_result_card`.

6. Update result-card rendering in `frontend/src/chat/ConversationThread.tsx`.
   - Render the final arrangement message as the primary visible body text when present.
   - Keep lower-level execution summary/details available below it.
   - Add a copy button for the final arrangement message only when the message exists.
   - Implement copy feedback as local ephemeral component state.
   - Keep the existing execution timeline disclosure collapsed by default.
   - Do not alter unrelated cards or redaction behavior.

7. Update frontend tests.
   - In `frontend/src/chat/thread.test.ts`:
     - verify result-card projection prefers `final_arrangement_message`
     - verify fallback to `feedback.message` when absent
   - In `frontend/src/chat/ConversationThread.test.tsx`:
     - verify the rendered result card shows the final arrangement message prominently
     - verify the copy control renders only when the message exists
     - verify copy failure/success feedback if existing test patterns support clipboard mocking
   - Avoid widening test scope beyond result-card behavior.

8. Extend the existing customer e2e confirmation smoke.
   - Reuse the current desktop test that confirms a plan and shows feedback.
   - Add assertions that:
     - the result card includes a final arrangement message
     - the message contains a stable Chinese arranged phrase
     - the copy control is visible
     - execution timeline remains behind the disclosure by default
   - Do not add a new full scenario matrix for this task.

9. Update docs.
   - In `README.md`, revise the customer demo result description so confirmed runs now end with a copyable final arrangement message.
   - In `docs/WEB_DEMO_README.md`, update the confirmation walkthrough to mention the final arrangement message and where reviewers should look after confirming.

10. Run focused verification and inspect diff scope.
   - Run backend integration tests first.
   - Then run frontend focused tests and build.
   - Then run the targeted Playwright confirmation smoke.
   - Finish with `git diff --check` and `git status --short --branch`.
   - Ensure no local artifacts or secrets are staged.

## 6. Testing Plan

- Unit / schema-level checks:
  - typed feedback models accept the additive `final_arrangement_message` field
- Integration tests:
  - `tests/integration/test_feedback_writer_gateway.py`
    - full success persists final arrangement message
    - partial success uses cautious wording
    - failure path does not overclaim completion
  - `tests/integration/test_demo_api_gateway.py`
    - confirm flow returns and re-reads the final arrangement message
- Frontend unit tests:
  - `frontend/src/chat/thread.test.ts`
    - result-card projection prioritizes `final_arrangement_message`
    - projection falls back to generic feedback message when absent
  - `frontend/src/chat/ConversationThread.test.tsx`
    - result card renders the final arrangement message
    - copy button visibility and local feedback
- Smoke tests:
  - `frontend/e2e/demo.spec.ts`
    - confirmed run shows the final arrangement message and copy affordance
- Document review:
  - `README.md` and `docs/WEB_DEMO_README.md` accurately describe the final arrangement message behavior

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add final arrangement message card
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/final-arrangement-message-card-v0
git add backend/app/feedback/schemas.py backend/app/feedback/writer.py
git add backend/app/demo/service.py backend/app/demo/schemas.py
git add tests/integration/test_feedback_writer_gateway.py tests/integration/test_demo_api_gateway.py
git add frontend/src/types/demo.ts frontend/src/chat/thread.ts frontend/src/chat/ConversationThread.tsx
git add frontend/src/chat/thread.test.ts frontend/src/chat/ConversationThread.test.tsx
git add frontend/e2e/demo.spec.ts
git add README.md docs/WEB_DEMO_README.md
git commit -m "feat: add final arrangement message card"
git push -u origin codex/final-arrangement-message-card-v0
```

The implementer must confirm `.env`, `frontend/dist/`, Playwright artifacts, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not add a new workflow node or alter graph routing.
- Do not redesign the whole assistant result card system.
- Do not refactor unrelated feedback wording across the app.
- Do not change benchmark harness behavior, release gates, or observability summaries.
- Do not widen this into a generic clipboard utility refactor.
- Do not add migrations, dependencies, or new API families.
- Do not change internal observability UI.
- Do not modify unrelated multi-scenario localization logic from task `088`.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Task numbering remains continuous, with `089` as the new task after `088`.
- [ ] The backend persists `feedback.final_arrangement_message` additively.
- [ ] The message is derived conservatively from plan/execution state and does not overclaim success.
- [ ] Successful confirmed runs visibly show a final arrangement message similar to “搞定了，下午 2 点出发...”.
- [ ] Partial and failed outcomes use appropriately cautious wording.
- [ ] The customer result card promotes the final arrangement message and keeps timeline/details available.
- [ ] The copy action works or degrades gracefully.
- [ ] Existing execution timeline collapse behavior remains intact.
- [ ] Existing customer-safe redaction behavior remains unchanged.
- [ ] Required tests and smoke checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Whether the public API needed an additive typed field update under `feedback`
- One example successful final arrangement message from a confirmed run
- One example cautious wording from a partial-success or failed run
- Any remaining limitations, such as:
  - departure wording omitted when timeline start labels are unavailable or unparseable
  - copy interaction exists only on the final arrangement message, not all result-card text
