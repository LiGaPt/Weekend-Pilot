# Spec: 046 Demo Action Manifest v0

## 1. Goal

Add the first stable public action-manifest contract for the Web demo so reviewers can see, in one normalized structure, what a specific plan will execute after confirmation.

The current demo already exposes `draft.proposed_actions`, but that payload is still a draft-internal structure and diverges from the later `confirmed_actions` structure that confirmation and execution actually use. After this task, every public `DemoPlanPreview` must include a compact `action_manifest` object that normalizes ordered action preview data across pre-confirmation, decline, confirmation, and execution states without exposing internal execution IDs or adding any new API routes.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a human-confirmed planning and execution system, not a one-shot recommendation endpoint. The blueprint requires a confirmation boundary before side effects and a deterministic execution workflow after confirmation. That makes the “what will execute if the user confirms this plan?” contract part of the product surface, not just an internal implementation detail.

`docs/NEXT_PHASE_ROADMAP.md` places the current repository in milestone `M4. 多轮对话与方案版本` and lists `8. plan versioning 与执行前 action manifest` after session persistence and follow-up replanning. Tasks `043`, `044`, and `045` already completed the first three connected slices of that chain:

- durable session and conversation persistence
- follow-up replan workflow
- public plan version lineage

Task `045` explicitly left action-manifest normalization for a follow-up task. This task is the smallest useful second half of roadmap item `8` because it formalizes an execution-preview contract using data the repository already has, without widening into new workflow behavior, new storage, or new demo routes.

This task touches these blueprint areas directly:

- Human-in-the-loop confirmation boundary
- Deterministic execution workflow
- Minimal Web UI / Web demo API path
- PostgreSQL source of truth through existing persisted plan JSON
- Future multi-turn planning and execution-preview evolution

## 3. Requirements

- Add a new public response model `DemoActionManifestItemSummary`.
- Add a new public response model `DemoActionManifestSummary`.
- Add a new required field `action_manifest` to every public `DemoPlanPreview`.
- `DemoActionManifestSummary` must include:
  - `source: str`
  - `action_count: int`
  - `actions: list[DemoActionManifestItemSummary]`
- `DemoActionManifestSummary.source` must use only:
  - `proposed_actions`
  - `confirmed_actions`
  - `none`
- `DemoActionManifestItemSummary` must include:
  - `action_ref: str | None`
  - `execution_order: int | None`
  - `action_type: str | None`
  - `target_id: str | None`
  - `payload_preview: dict[str, Any]`
  - `reason: str | None`
- `execution_order` must be `>= 1` when present.
- Every public demo response from these existing routes must include `plans[*].action_manifest`:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- For a plan that is still using draft preview data, `action_manifest.source` must be `proposed_actions`.
- For the `proposed_actions` source:
  - `actions` must derive from `plan_json["draft"]["proposed_actions"]`
  - `execution_order` must be assigned from the list position starting at `1`
  - `action_type` must come from the draft action `action_type`
  - `payload_preview` must come from the draft action payload after public sanitization
- For a plan that has been confirmed and has valid confirmed action data, `action_manifest.source` must be `confirmed_actions`.
- For the `confirmed_actions` source:
  - `actions` must derive from `plan_json["confirmed_actions"]`
  - `execution_order` must come from the stored confirmed action `execution_order`
  - `action_type` must come from the confirmed action `tool_name`
  - `payload_preview` must come from the confirmed action payload after public sanitization
  - actions must be sorted by `execution_order`
- A declined plan that does not have valid `confirmed_actions` must continue to expose the safe preview from `proposed_actions` rather than dropping the manifest entirely.
- If valid confirmed action data is unavailable and valid proposed action data is also unavailable, `action_manifest.source` must be `none`, `action_count` must be `0`, and `actions` must be an empty list.
- Confirmed action manifest items must not expose:
  - `idempotency_key`
  - `user_confirmed`
  - `action_id`
  - `tool_event_id`
  - `confirmation_id`
  - raw observability metadata
- Proposed action manifest items must not expose internal execution fields even if malformed plan JSON contains them.
- If `confirmed_actions` is malformed, incomplete, duplicated by `execution_order`, or otherwise invalid for public normalization, the summary builder must ignore that source and fall back to `proposed_actions` when possible.
- If `proposed_actions` is malformed or not a list, the summary builder must not fail the public response. It must fall back to `source = "none"` when no valid fallback exists.
- Keep the existing `DemoPlanPreview.proposed_actions` field unchanged in this task.
- Keep the existing `DemoRunSummary` top-level shape unchanged apart from the additive nested `plans[*].action_manifest`.
- The public frontend must render the action list from `plan.action_manifest.actions` instead of reading `plan.proposed_actions` directly.
- The public frontend must continue to support plan tab switching, and the rendered action manifest must always reflect the currently displayed plan tab.
- Update `README.md` and `docs/WEB_DEMO_README.md` to document the new public `action_manifest` contract and explain that it is the stable execution-preview surface.
- Do not add or modify any Alembic revision in this task.
- Do not add new dependencies.

## 4. Non-goals

- Do not add a new API route such as `GET /demo/runs/{run_id}/action-manifest`.
- Do not redesign `draft.proposed_actions`, `confirmed_actions`, or the persisted reviewed-plan schema in this task.
- Do not modify `HumanConfirmationService` business rules or `DeterministicExecutionWorkflow` business rules.
- Do not add replan controls, history browsing, or session exposure to the public frontend.
- Do not add plan-history lists, version browsers, or execution-preview diff views.
- Do not remove or rename `DemoPlanPreview.proposed_actions` in this task.
- Do not change benchmark harness contracts, replay contracts, internal observability contracts, or workflow request/response contracts.
- Do not add or modify database tables, columns, indexes, or migrations.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, or unrelated local untracked files such as `docs/NEXT_PHASE_ROADMAP.md` and `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

- Existing public demo routes:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- Existing persisted reviewed-plan JSON:
  - `draft.proposed_actions`
  - `confirmed_actions`
- Existing frontend `DemoRunSummary` payloads.

### Outputs

- Additive nested public response field:
  - `DemoPlanPreview.action_manifest`
- New public schema types:
  - `DemoActionManifestSummary`
  - `DemoActionManifestItemSummary`
- Existing `DemoPlanPreview.proposed_actions` remains present and unchanged.
- Existing public demo routes keep their current paths and request bodies.

### Schemas

Public plan-preview excerpt with proposed-action source:

```json
{
  "plan_id": "00000000-0000-0000-0000-000000000020",
  "status": "selected",
  "selected": true,
  "action_manifest": {
    "source": "proposed_actions",
    "action_count": 2,
    "actions": [
      {
        "action_ref": "draft_1_action_1",
        "execution_order": 1,
        "action_type": "book_ticket",
        "target_id": "activity_museum_001",
        "payload_preview": {
          "poi_id": "activity_museum_001",
          "quantity": 3
        },
        "reason": "Tickets are available, so confirmation can lock entry."
      },
      {
        "action_ref": "draft_1_action_2",
        "execution_order": 2,
        "action_type": "reserve_restaurant",
        "target_id": "restaurant_light_001",
        "payload_preview": {
          "restaurant_id": "restaurant_light_001",
          "party_size": 3
        },
        "reason": "Table availability is open, so confirmation can lock dinner seating."
      }
    ]
  },
  "proposed_actions": [
    {
      "action_ref": "draft_1_action_1",
      "action_type": "book_ticket"
    }
  ]
}
```

Public plan-preview excerpt with confirmed-action source:

```json
{
  "plan_id": "00000000-0000-0000-0000-000000000020",
  "status": "confirmed",
  "selected": true,
  "action_manifest": {
    "source": "confirmed_actions",
    "action_count": 2,
    "actions": [
      {
        "action_ref": "draft_1_action_1",
        "execution_order": 1,
        "action_type": "book_ticket",
        "target_id": "activity_museum_001",
        "payload_preview": {
          "poi_id": "activity_museum_001",
          "quantity": 3
        },
        "reason": "Tickets are available, so confirmation can lock entry."
      },
      {
        "action_ref": "draft_1_action_2",
        "execution_order": 2,
        "action_type": "reserve_restaurant",
        "target_id": "restaurant_light_001",
        "payload_preview": {
          "restaurant_id": "restaurant_light_001",
          "party_size": 3
        },
        "reason": "Table availability is open, so confirmation can lock dinner seating."
      }
    ]
  }
}
```

Expected helper contract:

```text
summarize_action_manifest(plan_json: dict[str, Any] | None, sanitizer: Callable[[Any], Any]) -> DemoActionManifestSummary
```

## 6. Observability

This task does not add a new observability surface.

The action manifest must be derived from already persisted reviewed-plan JSON and confirmed-action JSON. Do not add new LangSmith fields, new local trace-buffer fields, new PostgreSQL tables, or new run metadata just to support this summary. Existing observability behavior must remain unchanged.

## 7. Failure Handling

- If a plan has no `draft.proposed_actions` and no `confirmed_actions`, the public response must still succeed with `action_manifest.source = "none"` and an empty `actions` list.
- If `confirmed_actions` exists but is malformed, duplicated by `execution_order`, missing required fields, or not a list, the summary builder must ignore that source and fall back to `proposed_actions` when possible.
- If `proposed_actions` exists but is malformed or not a list, the summary builder must not fail the route. It must return `source = "none"` when there is no valid fallback.
- If a stored action payload is not an object, the candidate source must be treated as invalid rather than partially serialized.
- If a stored action contains forbidden internal execution keys, the public summary must sanitize them out and must not expose them to the client.
- Existing start, get, replan, confirm, and decline HTTP status-code behavior must remain unchanged.
- Existing confirmation and execution persistence behavior must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/046-demo-action-manifest-v0.md` exists and matches this task.
- [ ] `docs/plans/046-demo-action-manifest-v0-plan.md` exists and matches this task.
- [ ] Every public `DemoPlanPreview` includes `action_manifest`.
- [ ] Pre-confirmation demo responses expose `action_manifest.source = "proposed_actions"` when valid draft actions exist.
- [ ] Confirmed or executed demo responses expose `action_manifest.source = "confirmed_actions"` when valid confirmed actions exist.
- [ ] The manifest action list is ordered by `execution_order` and starts at `1`.
- [ ] Confirmed-action manifests do not expose `idempotency_key`, `user_confirmed`, `action_id`, `tool_event_id`, or other internal execution-only fields.
- [ ] Declined plans without confirmed actions still expose the safe preview from `proposed_actions`.
- [ ] Malformed or legacy action structures do not break public summary serialization and fall back safely to `source = "none"` when needed.
- [ ] Existing `DemoPlanPreview.proposed_actions` remains present and unchanged in this task.
- [ ] The public frontend renders the action manifest from `plan.action_manifest`.
- [ ] The public frontend still does not expose session, conversation, trace, or internal observability fields.
- [ ] No new endpoint, no new dependency, and no Alembic revision is added.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the stable execution-preview contract.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_action_manifest.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add demo action manifest summary
```

## 11. Notes for the Implementer

Keep this task as the second half of roadmap item `8. plan versioning 与执行前 action manifest`, not as a broader execution or frontend redesign task.

The key boundary is that this manifest should be plan-scoped, not run-scoped. The current public UI allows the reviewer to switch plan tabs, and confirmation can target the currently viewed plan. A run-level manifest would drift from the active plan tab. Build the normalized manifest inside `DemoPlanPreview` so the summary remains accurate for each displayed plan.

Keep the implementation inside the demo summary layer. Do not persist a separate manifest structure, do not add new database state, and do not refactor confirmation or execution internals just to support this view.
