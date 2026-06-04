# Spec: 090 Add-on Order Action Reinforcement v0

## 1. Goal

This task closes the current gap between the existing `order_addon` execution infrastructure and the actual planning/demo path. The repository already supports `order_addon` in the Mock World provider, confirmation schema, execution workflow, feedback labeling, and frontend action labels, but the planner and final-review path never emit a valid add-on action today.

After this task is complete, at least one deterministic Mock World scenario with explicit add-on wording must produce a customer-visible `order_addon` preview before confirmation, preserve the action through confirmation and execution, and show the completed add-on action in feedback and demo action manifest output. The scope is intentionally narrow: one real, testable path is enough for v0.

## 2. Project Context

This task maps primarily to `docs/NEXT_PHASE_ROADMAP.md` milestone `M4. 多轮对话与方案版本`, because it strengthens the customer-facing confirmation boundary and the post-confirmation action chain. It is also a justified convergence task that temporarily outranks the roadmap default `M1` priority: the lower layers for add-on execution already exist, but the deterministic planning and review chain does not yet expose them.

Relevant blueprint areas in `docs/PROJECT_BLUEPRINT.md`:

- Bounded multi-agent workflow: the workflow must keep add-on discovery and selection inside the existing deterministic path.
- Deterministic service layer: the add-on action must be emitted by deterministic planner/generator logic, not by ad hoc frontend logic.
- Tool Gateway: all add-on discovery before confirmation must remain read-only and flow through the existing gateway.
- Human-in-the-loop: `order_addon` must remain confirm-first and must not execute before user confirmation.
- Final Review Gate: the new action type must be validated against selected draft evidence.
- Action Ledger: confirmed `order_addon` executions must continue to land in the existing execution ledger path.
- LocalLife-Bench / demo realism: at least one existing scenario path should finally demonstrate the optional add-on behavior already implied by current benchmark taxonomy.

## 3. Requirements

- The next task ID must be `090`, with spec and plan paths named `090-addon-order-action-reinforcement-v0`.
- The Mock World planning path must be able to collect add-on candidates when `LocalLifeIntent.raw_text` explicitly requests an add-on stop such as drinks, snacks, cake, flowers, or supplies.
- Add-on discovery before confirmation must remain read-only. The implementation may use existing read tools such as `search_poi`, `get_poi_detail`, `check_opening_hours`, and `check_route`, but must not invoke any write tool before confirmation.
- The query-planning / candidate-collection path must make at least one `addon` candidate reachable in the existing `other_candidates` bucket for an explicit add-on request.
- The pre-flight enrichment path must retain a bounded number of `other_candidates` for this feature, and must provide usable evidence for at least one dining-to-add-on route in the same existing enrichment flow.
- `backend/app/planning/itinerary_drafts.py` must extend `ProposedActionType` to include `order_addon`.
- The deterministic itinerary generator must be able to append at most one `order_addon` proposed action to an eligible draft when:
  - the user explicitly asked for an add-on stop,
  - an enriched `addon` candidate exists,
  - the add-on candidate has usable read-side evidence,
  - and a usable route exists from the selected dining candidate to that add-on candidate.
- The minimal v0 happy path must target the existing Mock World vendor `addon_drinks_001` in `family_afternoon`, using a deterministic payload built from existing fixture data.
- The proposed add-on payload must be compatible with the existing Mock World `order_addon` tool contract and must include `vendor_id` plus a non-empty `items` list.
- `FinalReviewGate` must accept valid `order_addon` actions only when the action target and payload are backed by selected-draft evidence. Unbacked or malformed add-on actions must fail review.
- `order_addon` must survive the existing public and internal data chain:
  - `draft.proposed_actions`
  - `confirmed_actions`
  - execution `action_results`
  - demo `action_manifest`
- Customer-visible feedback after execution must use a human-readable add-on target label when available, not only the raw vendor ID.
- At least one focused backend integration path and one frontend rendering path must assert confirmed `order_addon` behavior end to end.
- The implementation must keep scope narrow and deterministic. If add-on evidence is incomplete, the system should skip the add-on action rather than inventing a fallback write payload.

## 4. Non-goals

- Do not add new public API routes.
- Do not add new scenario preset chips or new customer-demo selection UI.
- Do not expand add-on support to AMAP or to every Mock World profile.
- Do not redesign benchmark schemas or add new benchmark expectation fields for required action types in this task.
- Do not introduce new write tools or execute any write action before confirmation.
- Do not change unrelated roadmap priorities or start `M1` observability work in this task.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

Define the interfaces this task introduces or depends on.

### Inputs

- `LocalLifeIntent.raw_text` with explicit add-on wording, for example a family/citywalk request that asks for a drink or snack stop if it fits.
- Existing Mock World `search_poi` results that classify add-on vendors as `category == "addon"`.
- Existing confirmation and execution structures that already support `order_addon`.
- Existing Mock World `order_addon` payload contract:
  - `vendor_id: str`
  - `items: list[{"sku": str, "quantity": int}]`

### Outputs

- A selected draft may include one extra `order_addon` entry in `draft.proposed_actions`.
- Confirmed actions preserve the same logical action with generated `idempotency_key`.
- Execution results include `tool_name == "order_addon"` when the action is confirmed and executed.
- Demo API `action_manifest` exposes the add-on action in both preview and confirmed states.
- Feedback output includes the add-on action in `completed_actions` or `failed_actions` and uses a readable target label when evidence exists.

### Schemas

The proposed-action shape for the minimal v0 path should look like this:

```json
{
  "action_ref": "draft_1_action_3",
  "action_type": "order_addon",
  "target_id": "addon_drinks_001",
  "payload": {
    "vendor_id": "addon_drinks_001",
    "items": [
      {
        "sku": "water",
        "quantity": 3
      }
    ]
  },
  "requires_confirmation": true,
  "reason": "补给点可顺路到达，确认后可提前下单补水或小食。"
}
```

For add-on POIs in Mock World, the read-side detail contract may be extended so that `get_poi_detail` returns enough menu/vendor information to build the deterministic payload without introducing a new tool. This extension must remain read-only and scoped to existing Mock World add-on POIs.

## 6. Observability

This task should reuse existing observability paths rather than adding new infrastructure.

Required behavior:

- Existing tool events must record any extra add-on read-side calls such as add-on `search_poi`, `get_poi_detail`, `check_opening_hours`, and any dining-to-add-on `check_route`.
- Existing action-ledger rows must record confirmed `order_addon` executions exactly like other write tools.
- Draft or plan JSON must retain enough evidence to explain the selected add-on, such as selected add-on candidate ID/name and the route evidence used to justify it.
- No new LangSmith schema or new observability storage layer is required in this task.

## 7. Failure Handling

Expected failure handling for this task:

- If no add-on search is triggered, the existing non-add-on planning path must remain unchanged.
- If add-on search is triggered but no add-on candidate is found, the system must simply omit `order_addon` and continue with the base draft.
- If an add-on candidate lacks usable menu/detail/opening/route evidence, the generator must skip `order_addon` rather than producing a guessed payload.
- If `FinalReviewGate` sees an `order_addon` action whose target is not backed by selected-draft evidence, or whose payload lacks valid `vendor_id` / `items`, the draft must fail review.
- If `order_addon` execution fails after confirmation, existing execution and feedback behavior for partial or failed actions must continue to apply.
- Replays after a successful `order_addon` execution must continue to use the existing idempotent execution path and must not create duplicate writes.

## 8. Acceptance Criteria

- [ ] `090-addon-order-action-reinforcement-v0` is the selected next task, and the spec/plan naming remains continuous after task `089`.
- [ ] An explicit Mock World add-on request can produce at least one `addon` candidate before confirmation using read-only tool calls only.
- [ ] For the family add-on path, the selected draft includes a valid `order_addon` proposed action that targets `addon_drinks_001`.
- [ ] The add-on payload is compatible with the existing Mock World `order_addon` contract and uses existing fixture menu data.
- [ ] `order_addon` survives from `draft.proposed_actions` to `confirmed_actions`, execution `action_results`, and demo `action_manifest`.
- [ ] `FinalReviewGate` accepts a valid backed `order_addon` action and rejects malformed or unbacked add-on actions.
- [ ] Customer-visible feedback and/or execution summaries show a readable add-on target label for the completed add-on action.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

List commands the implementer must run before committing.

```bash
python -m pytest tests/test_query_planner.py tests/test_mock_world_provider.py tests/test_candidate_enrichment.py tests/test_itinerary_generation.py tests/test_final_review_gate.py tests/test_feedback_writer.py tests/test_demo_action_manifest.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_itinerary_generation_gateway.py tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py tests/integration/test_feedback_writer_gateway.py tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --grep "order addon"
git status --short
```

## 10. Expected Commit

Use a conventional commit message.

```text
feat: add addon order action reinforcement
```

## 11. Notes for the Implementer

Keep this task deliberately narrow:

- Scope the feature to explicit add-on wording in Mock World, not to general recommendation behavior.
- Prefer extending existing read-side contracts and route evidence over adding new tools or new public fields.
- A deterministic single-vendor happy path is acceptable for v0, but it must be fully testable end to end.
- If this task starts requiring benchmark schema redesign, new public APIs, or broad provider-generalized add-on modeling, stop and report back because the task has grown beyond the intended unit.
