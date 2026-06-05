# Spec: 091 Pre-confirmation Action List Upgrade v0

## 1. Goal

This task closes the remaining gap in the public confirmation contract for executable actions. The repository already has a stable confirmation boundary, deterministic execution workflow, demo action manifest, and lower-layer support for write tools including `send_message`. However, the actual planning path still does not expose the full intended pre-confirmation action list: `send_message` never appears in a real selected draft, and action ordering is still an implementation detail rather than a stable product contract.

After this task is complete, an eligible Mock World family run must be able to show the full pre-confirmation action list in one deterministic, backend-driven order: `reserve_restaurant -> book_ticket -> join_queue -> order_addon -> send_message`, omitting any action types that do not apply. The system must continue to execute none of them before explicit confirmation, and the same ordered contract must survive confirmation, execution, and feedback.

## 2. Project Context

This task primarily belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M4. 多轮对话与方案版本`, specifically the existing execution-preview / action-manifest chain. It is a convergence task that temporarily outranks the roadmap’s default `M1` priority because the user-visible confirmation contract is still incomplete even though the lower-layer execution stack already supports the missing action type.

Relevant blueprint areas in `docs/PROJECT_BLUEPRINT.md`:

- Human-in-the-loop: the system must clearly show what will happen before any write tool runs.
- Deterministic service layer: action sequencing and eligibility must come from deterministic backend logic.
- Tool Gateway: all write actions remain gated behind confirmation.
- Final Review Gate: any new pre-confirmation action type must be backed by selected-draft evidence.
- Execution Workflow: confirmed actions must keep the same deterministic sequence.
- Feedback Writer: user-visible results must describe completed message actions in readable text.
- Minimal Web UI / Web demo API path: the public confirmation preview must be complete and stable.

Project-context milestone mapping:

- Primary milestone: `M4. 多轮对话与方案版本`
- Secondary classification: convergence / closure task for the existing confirmation boundary and action manifest contract

## 3. Requirements

- The next task ID must be `091`, with spec and plan paths named `091-pre-confirmation-action-list-upgrade-v0`.
- The implementation must keep scope narrow and must not expand beyond the existing public confirmation/action-manifest contract.
- `send_message` must be added to the deterministic pre-confirmation planning path, not only to lower-layer execution-only paths.
- The planning stack must stop guessing world-profile capability from candidate IDs. The implementation must explicitly thread `world_profile` from workflow runtime into `CandidateCollectionResult` and `CandidateEnrichmentResult`.
- `backend/app/planning/itinerary_drafts.py` must extend `ProposedActionType` to include `send_message`.
- `send_message` generation must be enabled only when all of the following are true:
  - `world_profile == "family_afternoon"`
  - the user request contains one of the allowed spouse keywords for this v0 path
  - at least one earlier write action already exists in the draft
  - a deterministic non-empty message can be assembled from selected-draft content
- The allowed spouse trigger keywords for this task must remain fixed and explicit:
  - `wife`
  - `妻子`
  - `老婆`
  - `爱人`
- The deterministic `send_message` payload must target `wife` and must contain:
  - `payload.recipient == "wife"`
  - `payload.message` as a non-empty deterministic summary string
- The message body must be composed from existing selected-draft content only. Minimal v0 may use the first usable departure/start-time label, the selected activity name, and the selected dining name. The implementation must not introduce LLM-generated or provider-generated message text for this task.
- When `send_message` is generated, the draft must persist message evidence in `draft.evidence["post_confirmation_message"]` with recipient, recipient label, message preview, and trigger rule.
- The itinerary generator must emit actions using a fixed backend-driven priority order:
  - `reserve_restaurant`
  - `book_ticket`
  - `join_queue`
  - `order_addon`
  - `send_message`
- The fixed priority must omit absent actions while preserving existing mutual-exclusion rules, especially the existing `reserve_restaurant` versus `join_queue` behavior.
- `FinalReviewGate` must accept a `send_message` action only when the action target and payload are backed by selected-draft evidence. Unbacked, malformed, or mismatched message actions must fail review.
- `DeterministicExecutionWorkflow` must continue to execute confirmed `send_message` actions through Tool Gateway only after confirmation.
- The public demo action manifest must continue to summarize actions from stored draft/confirmed data only. It must not invent ordering or inject extra client-side actions.
- The frontend confirmation-preview list must continue rendering from `plan.action_manifest.actions`.
- The frontend must render `send_message` with a readable target label rather than raw `wife`.
- `DeterministicFeedbackWriter` must use a readable target label for `send_message` action summaries. For this task:
  - `wife -> 妻子`
  - `self -> 自己`
- No write tool, including `send_message`, may execute before explicit confirmation.

## 4. Non-goals

- Do not add new public demo endpoints.
- Do not redesign the public action-manifest schema.
- Do not add a new frontend panel, route, or workflow mode.
- Do not add message-recipient support to non-`family_afternoon` Mock World fixtures.
- Do not expand `send_message` generation to `friends_gathering`, `couple_afternoon`, `solo_afternoon`, `rainy_day_fallback`, `budget_lite`, or `elder_afternoon`.
- Do not add AMAP messaging support.
- Do not infer arbitrary partner/recipient types beyond the fixed wife keyword set in this task.
- Do not add LLM-generated message content.
- Do not change recovery routing, benchmark schemas, or observability schemas.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- Existing deterministic planning inputs:
  - `LocalLifeIntent`
  - `QueryPlan`
  - `CandidateCollectionResult`
  - `CandidateEnrichmentResult`
- Existing workflow runtime input:
  - active `world_profile`
- Existing Mock World provider contract for `send_message`:
  - `recipient: str`
  - `message: str`

### Outputs

- Ordered `draft.proposed_actions`
- Ordered `confirmed_actions`
- Ordered public `action_manifest.actions`
- Ordered execution `action_results`
- Draft evidence for message preview:
  - `draft.evidence["post_confirmation_message"]`

### Schemas

New planning runtime metadata fields:

```json
{
  "candidate_collection": {
    "world_profile": "family_afternoon"
  },
  "candidate_enrichment": {
    "world_profile": "family_afternoon"
  }
}
```

Expected `send_message` proposed action shape:

```json
{
  "action_ref": "draft_1_action_4",
  "action_type": "send_message",
  "target_id": "wife",
  "payload": {
    "recipient": "wife",
    "message": "搞定了，下午 2 点出发，先去徐汇亲子科学馆，再到绿碗家庭轻食。"
  },
  "requires_confirmation": true,
  "reason": "确认后会把安排消息发给同行家人，方便同步行程。"
}
```

Expected draft evidence shape:

```json
{
  "post_confirmation_message": {
    "recipient": "wife",
    "recipient_label": "妻子",
    "message_preview": "搞定了，下午 2 点出发，先去徐汇亲子科学馆，再到绿碗家庭轻食。",
    "trigger_rule": "family_spouse_confirmation_v0"
  }
}
```

Expected ordered public action-manifest example when all applicable actions exist:

```json
{
  "source": "proposed_actions",
  "action_count": 4,
  "actions": [
    {
      "execution_order": 1,
      "action_type": "reserve_restaurant",
      "target_id": "restaurant_light_001"
    },
    {
      "execution_order": 2,
      "action_type": "book_ticket",
      "target_id": "activity_museum_001"
    },
    {
      "execution_order": 3,
      "action_type": "order_addon",
      "target_id": "addon_drinks_001"
    },
    {
      "execution_order": 4,
      "action_type": "send_message",
      "target_id": "wife"
    }
  ]
}
```

## 6. Observability

This task must reuse existing observability paths.

Required behavior:

- No new tracing or benchmark schema is required.
- Existing Tool Gateway / Tool Event behavior remains the only source of write execution observability.
- `draft.evidence["post_confirmation_message"]` must persist enough deterministic evidence to justify the `send_message` action in review and feedback.
- No pre-confirmation Tool Event or Action Ledger row may be created for `send_message`.
- Existing confirmed execution must continue to produce Tool Events and Action Ledger rows only after confirmation.

## 7. Failure Handling

- If `world_profile` is missing or not `family_afternoon`, the generator must skip `send_message`.
- If the request does not contain one of the allowed wife/spouse keywords, the generator must skip `send_message`.
- If no earlier write action exists in the eligible draft, the generator must skip `send_message`.
- If the deterministic message template cannot produce a non-empty message, the generator must skip `send_message`.
- If `FinalReviewGate` sees a `send_message` action without matching draft evidence, it must block the draft.
- If `FinalReviewGate` sees empty or malformed `payload.recipient` / `payload.message`, it must block the draft.
- If `send_message` execution fails after confirmation, the existing partial-success / failure feedback path must continue to apply.
- No fallback path may execute `send_message` before confirmation.

## 8. Acceptance Criteria

- [ ] `091-pre-confirmation-action-list-upgrade-v0` is selected as the next task after completed task `090`.
- [ ] `CandidateCollectionResult` and `CandidateEnrichmentResult` carry `world_profile` without requiring candidate-ID guessing.
- [ ] The workflow search path passes the active `world_profile` into planning runtime results.
- [ ] `send_message` is a valid proposed action type in itinerary drafts.
- [ ] For the eligible Mock World family spouse path, the selected draft includes a `send_message` proposed action.
- [ ] The eligible `send_message` action targets `wife` and uses a deterministic non-empty `message` payload.
- [ ] The draft stores `post_confirmation_message` evidence with recipient, label, preview, and trigger rule.
- [ ] Proposed actions follow the fixed order `reserve_restaurant -> book_ticket -> join_queue -> order_addon -> send_message`, omitting absent actions.
- [ ] The same order survives into `confirmed_actions`, public `action_manifest`, and execution `action_results`.
- [ ] `FinalReviewGate` accepts a valid evidence-backed `send_message` action and rejects malformed or unbacked ones.
- [ ] No `send_message` write executes before confirmation.
- [ ] Frontend preview shows a readable `send_message` target label instead of raw `wife`.
- [ ] Feedback summaries use readable target labels for completed or failed `send_message`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_itinerary_generation.py tests/test_final_review_gate.py tests/test_feedback_writer.py tests/test_demo_action_manifest.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_itinerary_generation_gateway.py tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py tests/integration/test_feedback_writer_gateway.py tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx src/App.test.tsx src/api/demo.test.ts
npm --prefix frontend run build
git status --short
```

## 10. Expected Commit

```text
feat: complete pre-confirmation action list
```

## 11. Notes for the Implementer

Keep this task narrowly focused on closing the action-list contract.

Important implementation constraints:

- Do not solve generic recipient modeling here.
- Do not add new fixture recipients to other world profiles.
- Do not let the frontend invent action ordering.
- Do not let the generator infer recipient support from candidate IDs alone.
- If the task starts requiring new public routes, new fixture families, or generalized message-recipient architecture, stop and report back because the task has grown beyond the intended unit.
