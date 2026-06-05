# Plan: 091 Pre-confirmation Action List Upgrade v0

## 1. Spec Reference

Spec file:

```text
docs/specs/091-pre-confirmation-action-list-upgrade-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/addon-order-action-reinforcement-v0`.
- Latest completed task is `090-addon-order-action-reinforcement-v0`.
- Latest commit is `4e9b117 feat: add addon order action reinforcement`.
- `docs/specs` and `docs/plans` are continuous and matched through `090`.
- `git status --short --branch` shows no tracked in-progress task work; only `.git-ssh-known-hosts` is untracked.
- The public confirmation preview contract already exists through `action_manifest`, but the planning path still lacks real `send_message` generation.
- Lower layers already support `send_message`:
  - Mock World provider implements `send_message`
  - confirmation schemas accept `send_message`
  - execution workflow accepts `send_message`
  - feedback writer labels `send_message`
- The current gap is only in the planning / review / user-visible preview chain.
- Mock World fixture capability is intentionally narrow:
  - `family_afternoon.json` contains `message_recipients: ["wife", "self"]`
  - the other current profile fixtures do not expose message recipients
- Because of that fixture shape, this task must keep `send_message` generation limited to the `family_afternoon` spouse path.

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/planning/candidates.py` - add optional `world_profile` to `CandidateCollectionResult`.
- `backend/app/planning/enriched_candidates.py` - add optional `world_profile` to `CandidateEnrichmentResult`.
- `backend/app/planning/execution.py` - accept `world_profile` in `execute_initial_calls(...)` and persist it into `CandidateCollectionResult`.
- `backend/app/planning/enrichment.py` - copy `collection.world_profile` into the enrichment result.
- `backend/app/workflow/nodes.py` - pass workflow `world_profile` into `QueryPlanExecutor.execute_initial_calls(...)`.
- `backend/app/planning/itinerary_drafts.py` - add `send_message` to `ProposedActionType`.
- `backend/app/planning/itinerary_generation.py` - generate deterministic `send_message`, persist message evidence, and enforce the fixed action order.
- `backend/app/review/final_review_gate.py` - validate evidence-backed `send_message` payloads and continue blocking arbitrary ones.
- `backend/app/feedback/writer.py` - add readable target labels for message recipients.
- `frontend/src/chat/thread.ts` - render readable `send_message` target labels in the action list.
- `tests/test_itinerary_generation.py` - cover action ordering and `send_message` generation / skip rules.
- `tests/test_final_review_gate.py` - cover valid and invalid `send_message` review cases.
- `tests/test_feedback_writer.py` - cover readable message-recipient labels.
- `tests/integration/test_itinerary_generation_gateway.py` - cover family spouse path draft generation with ordered actions.
- `tests/integration/test_execution_workflow_gateway.py` - cover confirmed `send_message` execution ordering and replay behavior.
- `tests/integration/test_feedback_writer_gateway.py` - cover readable `send_message` feedback.
- `tests/integration/test_demo_api_gateway.py` - cover public preview and confirmed manifest ordering with `send_message`.
- `frontend/src/chat/thread.test.ts` - cover label mapping and projected ordering expectations.
- `frontend/src/chat/ConversationThread.test.tsx` - cover readable `send_message` target rendering in the preview list.
- `frontend/src/App.test.tsx` - cover visible confirmation preview behavior in the app shell.
- `frontend/src/api/demo.test.ts` - keep client contract aligned if fixture payloads gain ordered `send_message` preview.

## 5. Implementation Steps

1. Create a fresh task branch from the current latest-task branch.

2. Thread `world_profile` through planning runtime results.
   - Add `world_profile: str | None = None` to `CandidateCollectionResult`.
   - Add `world_profile: str | None = None` to `CandidateEnrichmentResult`.
   - Extend `QueryPlanExecutor.execute_initial_calls(...)` with `world_profile: str | None = None`.
   - Set `CandidateCollectionResult.world_profile` from that argument.
   - In `CandidateEnricher.enrich(...)`, copy `collection.world_profile` into the created `CandidateEnrichmentResult`.
   - In `WeekendPilotWorkflowNodes.execute_searches(...)`, pass `state["world_profile"]` to `execute_initial_calls(...)`.

3. Extend draft schemas for message actions.
   - Add `send_message` to `ProposedActionType` in `backend/app/planning/itinerary_drafts.py`.
   - Do not change confirmation schemas or execution schemas; they already accept `send_message`.

4. Refactor itinerary action assembly into a fixed priority pipeline.
   - In `backend/app/planning/itinerary_generation.py`, stop treating append order as incidental.
   - Build candidate actions into named slots or buckets.
   - Emit actions only in this exact priority:
     1. `reserve_restaurant`
     2. `book_ticket`
     3. `join_queue`
     4. `order_addon`
     5. `send_message`
   - Preserve the existing availability rules:
     - `join_queue` only when no reservation action exists
     - `order_addon` only when the existing addon evidence path qualifies

5. Add deterministic `send_message` eligibility logic.
   - Add a narrow helper that returns `True` only when:
     - `enrichment.world_profile == "family_afternoon"`
     - `intent.raw_text.casefold()` contains one of:
       - `wife`
       - `妻子`
       - `老婆`
       - `爱人`
     - at least one earlier write action already exists in the draft
   - Do not broaden the keyword list beyond the spec.

6. Add deterministic `send_message` payload generation.
   - Build `target_id = "wife"`.
   - Build payload:
     - `recipient = "wife"`
     - `message = <deterministic summary string>`
   - Compose the message from existing draft content only:
     - departure clause from the first usable timeline `start_label`
     - activity name
     - dining name
   - Reuse the existing time-normalization approach already present in `DeterministicFeedbackWriter` rather than inventing a second time format rule.
   - Use one fixed reason string:
     - `确认后会把安排消息发给同行家人，方便同步行程。`

7. Persist explicit message evidence into the draft.
   - When `send_message` is emitted, add `draft.evidence["post_confirmation_message"]`.
   - Use exactly:
     - `recipient = "wife"`
     - `recipient_label = "妻子"`
     - `message_preview = <same deterministic message>`
     - `trigger_rule = "family_spouse_confirmation_v0"`

8. Extend final review validation.
   - In `FinalReviewGate`, keep arbitrary `send_message` blocked by default.
   - Add a new validation path for `send_message` inside `_check_actions_reference_draft_objects(...)`.
   - Accept only when:
     - `draft.evidence.post_confirmation_message` exists and is a dict
     - `action.target_id == evidence.recipient`
     - `payload.recipient == action.target_id`
     - `payload.message` is a non-empty string
   - Keep malformed or unbacked `send_message` as a blocking failure.

9. Improve readable labels for message recipients.
   - In `DeterministicFeedbackWriter`, extend target-label extraction so:
     - `draft.evidence.post_confirmation_message.recipient -> recipient_label`
     - fallback static labels map `wife -> 妻子`, `self -> 自己`
   - In `frontend/src/chat/thread.ts`, update `actionTargetLabel(...)` so `send_message` displays readable recipient text instead of raw `wife`.

10. Update backend unit tests first.
    - `tests/test_itinerary_generation.py`
      - add one eligible family spouse test that emits `send_message`
      - assert exact ordered action list
      - assert message evidence fields
      - add skip tests:
        - wrong world profile
        - missing wife keyword
        - zero earlier actions
    - `tests/test_final_review_gate.py`
      - valid backed `send_message` passes
      - missing evidence blocks
      - mismatched recipient blocks
      - empty message blocks
    - `tests/test_feedback_writer.py`
      - readable `send_message` target label appears in summaries

11. Update integration tests next.
    - `tests/integration/test_itinerary_generation_gateway.py`
      - add family spouse prompt that yields ordered preview including `send_message`
    - `tests/integration/test_human_confirmation_gateway.py`
      - assert confirmed action order matches proposed action order after adding `send_message`
    - `tests/integration/test_execution_workflow_gateway.py`
      - assert `send_message` executes in the last slot for the eligible flow
      - assert replay stays idempotent
    - `tests/integration/test_feedback_writer_gateway.py`
      - assert readable message-recipient text in feedback summaries
    - `tests/integration/test_demo_api_gateway.py`
      - assert preview `action_manifest` includes `send_message` in ordered position
      - assert confirmed manifest preserves the same order
      - assert no pre-confirmation action ledger rows exist

12. Update frontend tests last.
    - `frontend/src/chat/thread.test.ts`
      - assert `actionTargetLabel(..., "wife", "send_message") == "妻子"`
      - assert projected result ordering remains stable
    - `frontend/src/chat/ConversationThread.test.tsx`
      - assert confirmation-preview list renders `发送消息` with readable recipient label
    - `frontend/src/App.test.tsx`
      - assert visible confirmation preview remains summary-first but can render the new last-step message action when fixture data includes it
    - `frontend/src/api/demo.test.ts`
      - keep typed sample payloads aligned with ordered action lists

13. Run focused verification commands.
    - Fix failures with the smallest scoped change.
    - Do not widen recipient support or add new fixtures to avoid test churn.

14. Confirm git state and prepare the single task commit.

## 6. Testing Plan

- Unit tests:
  - `tests/test_itinerary_generation.py`
    - fixed action ordering
    - eligible family spouse `send_message` generation
    - skip rules when world profile or spouse keyword is missing
  - `tests/test_final_review_gate.py`
    - valid evidence-backed `send_message`
    - malformed or unbacked `send_message`
  - `tests/test_feedback_writer.py`
    - readable `wife` / `self` labels in feedback action summaries
  - `tests/test_demo_action_manifest.py`
    - existing manifest summary remains valid with ordered stored actions

- Integration tests:
  - `tests/integration/test_itinerary_generation_gateway.py`
    - selected draft includes ordered `send_message`
  - `tests/integration/test_human_confirmation_gateway.py`
    - confirmation preserves ordering into `confirmed_actions`
  - `tests/integration/test_execution_workflow_gateway.py`
    - `send_message` executes only after confirmation and preserves order
    - rerun produces idempotent replay
  - `tests/integration/test_feedback_writer_gateway.py`
    - feedback uses readable recipient label
  - `tests/integration/test_demo_api_gateway.py`
    - preview and confirmed manifests expose the complete ordered contract

- Smoke tests:
  - `npm --prefix frontend test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx src/App.test.tsx src/api/demo.test.ts`
  - `npm --prefix frontend run build`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_itinerary_generation.py tests/test_final_review_gate.py tests/test_feedback_writer.py tests/test_demo_action_manifest.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_itinerary_generation_gateway.py tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py tests/integration/test_feedback_writer_gateway.py tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx src/App.test.tsx src/api/demo.test.ts
npm --prefix frontend run build
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: complete pre-confirmation action list
```

Expected commands:

```bash
git status --short
git switch -c codex/pre-confirmation-action-list-upgrade-v0
git add backend/app/planning/candidates.py backend/app/planning/enriched_candidates.py backend/app/planning/execution.py backend/app/planning/enrichment.py backend/app/workflow/nodes.py backend/app/planning/itinerary_drafts.py backend/app/planning/itinerary_generation.py backend/app/review/final_review_gate.py backend/app/feedback/writer.py frontend/src/chat/thread.ts tests/test_itinerary_generation.py tests/test_final_review_gate.py tests/test_feedback_writer.py tests/test_demo_action_manifest.py tests/integration/test_itinerary_generation_gateway.py tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py tests/integration/test_feedback_writer_gateway.py tests/integration/test_demo_api_gateway.py frontend/src/chat/thread.test.ts frontend/src/chat/ConversationThread.test.tsx frontend/src/App.test.tsx frontend/src/api/demo.test.ts
git commit -m "feat: complete pre-confirmation action list"
git push -u origin codex/pre-confirmation-action-list-upgrade-v0
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not add new API routes.
- Do not add new Mock World recipients to non-family fixtures.
- Do not redesign the action-manifest schema.
- Do not change AMAP behavior.
- Do not expand spouse detection beyond the fixed wife-keyword set in the spec.
- Do not build a generalized notification subsystem.
- Do not start M1 observability work.
- Do not add new dependencies.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `world_profile` is threaded explicitly instead of inferred from candidate IDs.
- [ ] The proposed action order is fixed and backend-driven.
- [ ] `send_message` is generated only for the intended `family_afternoon` spouse path.
- [ ] `send_message` remains confirmation-gated and never executes pre-confirmation.
- [ ] `FinalReviewGate` blocks arbitrary or malformed `send_message`.
- [ ] Feedback and frontend both use readable message-recipient labels.
- [ ] Required tests passed.
- [ ] Frontend build passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, the implementer should report back with:

- Changed files.
- Exact family spouse prompt used to prove the new `send_message` preview path.
- Ordered action list observed in preview and confirmed states.
- Verification commands run and their results.
- Commit hash.
- Push result.
- Any follow-up tasks discovered, especially if broader recipient/profile support is still needed.
