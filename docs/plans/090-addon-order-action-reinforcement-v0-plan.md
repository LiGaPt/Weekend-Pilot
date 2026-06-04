# Plan: 090 Add-on Order Action Reinforcement v0

## 1. Spec Reference

Spec file:

```text
docs/specs/090-addon-order-action-reinforcement-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is still `codex/final-arrangement-message-card-v0`, which is a leftover branch from task `089`; the implementer should create a fresh branch for task `090` before editing.
- Latest completed task is `089-final-arrangement-message-card-v0`, and the latest commit is `1f87691 feat: add final arrangement message card`.
- `docs/specs` and `docs/plans` are continuous and matched through `089`.
- `git status --short --branch` currently shows no repo-tracked in-progress work; only `.git-ssh-known-hosts` is untracked.
- `order_addon` already exists in lower layers:
  - Mock World provider accepts `order_addon`
  - confirmation schemas allow `order_addon`
  - execution workflow treats it as a valid confirmed write action
  - feedback writer has an `order_addon` tool label
  - frontend action labels and target-id labels already contain `order_addon` / `addon_drinks_001`
- The current gap is in the planning chain:
  - query planning does not explicitly search addon POIs
  - candidate enrichment defaults `max_other_candidates=0`
  - itinerary drafts do not allow `order_addon`
  - deterministic itinerary generation never emits `order_addon`
  - final review rejects unknown action types and does not validate addon-backed targets
- Existing fixture evidence already supports a narrow happy path:
  - `family_afternoon` contains POI `addon_drinks_001`
  - that POI has menu SKUs `water` and `fruit_cup`
  - a walking route already exists from `restaurant_light_001` to `addon_drinks_001`
  - benchmark case `family_citywalk_addon_v1` already asks for a drink/snack stop if it fits

## 3. Files to Add

None.

## 4. Files to Modify

- `backend/app/planning/query_planner.py` - append a bounded addon `search_poi` call for explicit add-on wording in Mock World requests.
- `backend/app/providers/mock_world/provider.py` - extend addon `get_poi_detail` responses so add-on menu/vendor data is available through an existing read tool.
- `backend/app/planning/enrichment.py` - retain one `other_candidate` for addon use and add dining-to-addon route evidence into the existing route matrix flow.
- `backend/app/workflow/nodes.py` - instantiate `CandidateEnricher` with bounded `max_other_candidates` in the pre-flight node.
- `backend/app/planning/itinerary_drafts.py` - extend `ProposedActionType` with `order_addon`.
- `backend/app/planning/itinerary_generation.py` - choose an eligible add-on and emit a deterministic `order_addon` action plus draft evidence.
- `backend/app/review/final_review_gate.py` - validate backed `order_addon` target/payload rules.
- `backend/app/feedback/writer.py` - include selected add-on label evidence in customer-visible feedback summaries.
- `tests/test_query_planner.py` - add planner coverage for explicit add-on requests.
- `tests/test_mock_world_provider.py` - verify addon detail includes menu/vendor read-side data.
- `tests/test_candidate_enrichment.py` - verify `other_candidates` enrichment and dining-to-addon route evidence.
- `tests/test_itinerary_generation.py` - verify deterministic `order_addon` emission and skip behavior.
- `tests/test_final_review_gate.py` - verify valid and invalid addon action review cases.
- `tests/test_feedback_writer.py` - verify readable add-on target output.
- `tests/test_demo_action_manifest.py` - verify action manifest summarization handles `order_addon`.
- `tests/integration/test_itinerary_generation_gateway.py` - verify the selected draft contains `order_addon` for the explicit add-on path.
- `tests/integration/test_human_confirmation_gateway.py` - verify confirmation preserves `order_addon`.
- `tests/integration/test_execution_workflow_gateway.py` - verify `order_addon` executes and replays idempotently.
- `tests/integration/test_feedback_writer_gateway.py` - verify feedback output includes add-on completion.
- `tests/integration/test_demo_api_gateway.py` - verify preview/confirm action manifest visibility for `order_addon`.
- `frontend/src/chat/thread.test.ts` - verify action labels / target labels for add-on actions.
- `frontend/src/chat/ConversationThread.test.tsx` - verify add-on action rendering in customer-visible lists.
- `frontend/e2e/demo.spec.ts` - add one explicit add-on request flow that confirms and surfaces the add-on result.

## 5. Implementation Steps

1. Create a new task branch before editing.
2. In `backend/app/planning/query_planner.py`, add a narrow Mock World-only helper that detects explicit add-on wording from `intent.raw_text`.
3. Keep the trigger deterministic and explicit. Use direct keyword matching only, not broad inference. Include both English and Chinese words that clearly indicate add-on intent, such as drink, snack, cake, flower, supplies, 饮品, 零食, 蛋糕, 鲜花, 补给, 补水.
4. When the helper returns true, append a third `search_poi` initial tool call after dining search with:
   - `tool_name == "search_poi"`
   - `category == "addon"`
   - a small limit such as `3`
   - a deterministic query string derived from the explicit wording or a fallback like `addon`
5. Do not change AMAP planning or non-add-on prompts in this task.
6. In `backend/app/providers/mock_world/provider.py`, extend `_get_poi_detail(...)` so that when `poi_id` also matches an add-on vendor entry, the returned `poi` includes enough read-side add-on data to build an `order_addon` payload without introducing a new tool.
7. Keep that extension minimal. Return vendor/menu data only for existing add-on POIs, and do not change write-tool behavior.
8. In `backend/app/workflow/nodes.py`, update the pre-flight enrichment call to use `CandidateEnricher(self.gateway, max_other_candidates=1)` so exactly one add-on candidate can flow through this path.
9. In `backend/app/planning/enrichment.py`, keep the existing `activity -> dining` route-matrix behavior intact, but add a second bounded route pass for `dining -> other` candidates using the same route template and same `route_matrix` collection.
10. Do not add a new public stage or a second public route field. Reuse the existing internal `route_matrix`.
11. In `backend/app/planning/itinerary_drafts.py`, extend `ProposedActionType` to include `order_addon`.
12. In `backend/app/planning/itinerary_generation.py`, change proposed-action building to receive the full enrichment result so add-on candidates and route evidence are available during action generation.
13. Add a helper that selects at most one eligible add-on candidate for the chosen draft. Eligibility must require all of the following:
   - the request explicitly asked for an add-on stop
   - the candidate category is `addon`
   - opening-hours evidence is usable
   - a usable route exists from the selected dining candidate to that add-on candidate
   - menu/vendor data needed for payload construction is present
14. Build the v0 payload deterministically from existing fixture data. Prefer SKU `water` when available and use `quantity == party_size`. If the eligible candidate does not expose SKU `water`, skip add-on emission in v0 instead of inventing alternate ordering logic.
15. Append the add-on action after ticket / dining actions so the execution order stays intuitive:
   - `book_ticket`
   - `reserve_restaurant` or `join_queue`
   - `order_addon`
16. Use a fixed reason string for the add-on action so tests can assert it directly.
17. Record enough draft evidence to label and explain the selected add-on later. At minimum, store selected add-on candidate ID, name, and the dining-to-addon route tool event ID or route key in `draft.evidence`.
18. In `backend/app/review/final_review_gate.py`, extend the internal indexes to include enriched `other_candidates`, especially `addon` IDs.
19. Update `_check_actions_reference_draft_objects(...)` so `order_addon` is valid only when:
   - `target_id` is a selected add-on candidate backed by enrichment
   - `payload.vendor_id == target_id`
   - `payload.items` is a non-empty list
   - every item contains a non-empty `sku` and a positive integer `quantity`
   - a usable `dining -> addon` route exists in route evidence
20. Keep all other unknown action types invalid.
21. In `backend/app/feedback/writer.py`, extend target-label extraction so it can use the selected add-on evidence recorded in the draft and produce a readable add-on name in completed/failed action summaries.
22. Do not change public feedback schema in this task. Only improve the label source.
23. Add focused unit tests in backend first, then integration tests, then frontend tests.
24. In frontend tests, use the existing `order_addon` and `addon_drinks_001` labels rather than redesigning UI behavior.
25. In `frontend/e2e/demo.spec.ts`, add one new test title that contains the phrase `order addon` so the verification command can target it directly with Playwright grep.
26. Keep the task narrow. Do not add a new scenario chip, a new benchmark schema field, or a generalized add-on recommendation engine.

## 6. Testing Plan

- Unit tests:
  - `tests/test_query_planner.py`
    - explicit add-on wording appends an addon `search_poi` call
    - a normal prompt without add-on wording does not append addon search
  - `tests/test_mock_world_provider.py`
    - `get_poi_detail` for `addon_drinks_001` returns menu/vendor read-side data
  - `tests/test_candidate_enrichment.py`
    - one `other_candidate` is enriched when the limit is enabled
    - route matrix includes `dining -> addon` walking evidence
  - `tests/test_itinerary_generation.py`
    - eligible add-on evidence emits `order_addon` after the existing base actions
    - missing menu or missing route evidence skips add-on emission
  - `tests/test_final_review_gate.py`
    - valid backed `order_addon` passes
    - malformed `items`
    - mismatched `vendor_id`
    - missing dining-to-addon route
    - unknown add-on target
  - `tests/test_feedback_writer.py`
    - completed add-on action uses readable target label when draft evidence exists
  - `tests/test_demo_action_manifest.py`
    - proposed and/or confirmed `order_addon` survives manifest summary
- Integration tests:
  - `tests/integration/test_itinerary_generation_gateway.py`
    - explicit family add-on prompt yields selected draft with `order_addon`
  - `tests/integration/test_human_confirmation_gateway.py`
    - `confirmed_actions` preserves execution order and payload for `order_addon`
  - `tests/integration/test_execution_workflow_gateway.py`
    - `order_addon` executes successfully
    - replay returns idempotent status
  - `tests/integration/test_feedback_writer_gateway.py`
    - final arrangement output includes add-on completion
  - `tests/integration/test_demo_api_gateway.py`
    - preview action manifest shows add-on action before confirmation
    - confirmed action manifest and feedback still show add-on action after confirmation
- Smoke tests:
  - `npm --prefix frontend test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx`
  - `npm --prefix frontend run build`
  - `npm --prefix frontend run e2e -- --grep "order addon"`

## 7. Verification Commands

Commands the implementer must run before committing:

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

Prefer fixing failures with the smallest scoped change possible. Do not broaden the task to unrelated cleanup while chasing test issues.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add addon order action reinforcement
```

Expected commands:

```bash
git status --short
git switch -c codex/addon-order-action-reinforcement-v0
git add backend/app/planning/query_planner.py backend/app/providers/mock_world/provider.py backend/app/planning/enrichment.py backend/app/workflow/nodes.py backend/app/planning/itinerary_drafts.py backend/app/planning/itinerary_generation.py backend/app/review/final_review_gate.py backend/app/feedback/writer.py tests/test_query_planner.py tests/test_mock_world_provider.py tests/test_candidate_enrichment.py tests/test_itinerary_generation.py tests/test_final_review_gate.py tests/test_feedback_writer.py tests/test_demo_action_manifest.py tests/integration/test_itinerary_generation_gateway.py tests/integration/test_human_confirmation_gateway.py tests/integration/test_execution_workflow_gateway.py tests/integration/test_feedback_writer_gateway.py tests/integration/test_demo_api_gateway.py frontend/src/chat/thread.test.ts frontend/src/chat/ConversationThread.test.tsx frontend/e2e/demo.spec.ts
git commit -m "feat: add addon order action reinforcement"
git push -u origin codex/addon-order-action-reinforcement-v0
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not add new public demo endpoints.
- Do not add new benchmark schema fields such as required action types.
- Do not add a generalized addon recommendation subsystem.
- Do not expand the implementation to AMAP.
- Do not touch unrelated M1 observability infrastructure.
- Do not redesign the customer UI beyond what is necessary to surface and test the existing add-on labels.
- Do not add new dependencies unless they are already required by existing repo tooling.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Explicit add-on wording is required to trigger addon planning in v0.
- [ ] `order_addon` is backed by read-side evidence and a dining-to-addon route, not by guessed payloads.
- [ ] Required tests passed.
- [ ] Frontend build passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- Exact scenario or prompt used to prove `order_addon` behavior.
- Verification commands run and their results.
- Commit hash.
- Push result.
- Whether the final implementation stayed on the narrow v0 rule set:
  - Mock World only
  - explicit add-on wording only
  - one bounded add-on candidate
  - deterministic `water` payload for the current family add-on fixture
- Any follow-up tasks discovered, especially if broader benchmark enforcement or provider-generalized add-on modeling is still missing.
