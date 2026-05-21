# Plan: 046 Demo Action Manifest v0

## 1. Spec Reference

Spec file:

```text
docs/specs/046-demo-action-manifest-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/demo-plan-version-lineage-v0`.
- Latest completed numbered task is `045`.
- Latest commit is `1ae2860 feat: add demo plan version lineage`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `045`.
- There is no existing `046` spec, `046` plan, or `codex/demo-action-manifest-v0` branch yet.
- Tasks `043`, `044`, and `045` already cover session persistence, follow-up replanning, and public plan version lineage.
- The public demo API currently exposes `plans[*].proposed_actions`, but it does not expose a normalized execution-preview contract.
- The public frontend currently renders “待确认操作” from `plan.proposed_actions` directly.
- Confirmation persists `confirmed_actions` in reviewed plan JSON, and execution consumes that internal structure.
- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.

## 3. Files to Add

- `backend/app/demo/action_manifest.py` - pure helper that normalizes plan JSON into a public-safe action manifest.
- `tests/test_demo_action_manifest.py` - unit tests for proposed-source, confirmed-source, fallback, and malformed-data behavior.

## 4. Files to Modify

- `backend/app/demo/schemas.py` - add `DemoActionManifestItemSummary`, `DemoActionManifestSummary`, and `DemoPlanPreview.action_manifest`.
- `backend/app/demo/service.py` - build and attach `action_manifest` to every public plan preview.
- `tests/test_demo_api.py` - require `action_manifest` in public serialization and keep redaction assertions intact.
- `tests/integration/test_demo_api_gateway.py` - assert manifest behavior for start, replan, confirm, and decline flows.
- `frontend/src/types/demo.ts` - add TS types for the manifest contract.
- `frontend/src/App.tsx` - render the public action preview from `plan.action_manifest`.
- `frontend/src/App.test.tsx` - update fixtures and assert the normalized manifest is rendered.
- `frontend/src/api/demo.test.ts` - update typed mock payloads to include `action_manifest`.
- `README.md` - document the stable execution-preview contract.
- `docs/WEB_DEMO_README.md` - document how the public action manifest behaves before and after confirmation.

## 5. Implementation Steps

1. Update the failing backend API serialization test first.
   In `tests/test_demo_api.py`, extend the minimal `DemoRunSummary` fixture so each `plan` includes `action_manifest`, then add assertions that:
   - `action_manifest` is present
   - `source`, `action_count`, and `actions` serialize correctly
   - no session or internal observability fields appear

2. Add the failing pure manifest-helper tests before implementation.
   Create `tests/test_demo_action_manifest.py` with focused cases for:
   - valid `draft.proposed_actions` becomes `source = "proposed_actions"` with one-based `execution_order`
   - valid `confirmed_actions` becomes `source = "confirmed_actions"` and uses stored `execution_order`
   - malformed `confirmed_actions` falls back to valid `proposed_actions`
   - malformed `proposed_actions` with no valid fallback returns `source = "none"`
   - forbidden internal execution fields are removed from `payload_preview`

3. Extend the failing gateway integration tests.
   In `tests/integration/test_demo_api_gateway.py`, add assertions that:
   - start and replan responses expose `plans[*].action_manifest.source = "proposed_actions"` for plans with preview actions
   - confirm responses expose `plans[*].action_manifest.source = "confirmed_actions"` on the selected confirmed plan
   - decline responses keep the preview source when the plan was never confirmed
   - confirmed manifests expose stable order and do not expose internal keys such as `idempotency_key`

4. Add the backend public schema types.
   In `backend/app/demo/schemas.py`:
   - add `DemoActionManifestItemSummary`
   - add `DemoActionManifestSummary`
   - add required `action_manifest: DemoActionManifestSummary` to `DemoPlanPreview`
   Keep `proposed_actions` in place and unchanged.

5. Implement the pure manifest normalizer.
   Add `backend/app/demo/action_manifest.py` with a pure helper such as:
   - `summarize_action_manifest(plan_json, sanitizer) -> DemoActionManifestSummary`
   The helper must:
   - validate `confirmed_actions` as the first-choice source
   - sort confirmed items by `execution_order`
   - map confirmed `tool_name` to public `action_type`
   - fall back to `draft.proposed_actions` only when confirmed data is missing or invalid
   - derive proposed `execution_order` from list position
   - sanitize `payload_preview` through the injected sanitizer
   - return `source = "none"` with empty actions when neither source is valid

6. Wire the manifest builder into demo plan previews.
   In `backend/app/demo/service.py`, update `_plan_preview(...)` so it builds:
   - `action_manifest = summarize_action_manifest(plan.plan_json, sanitizer=sanitize_demo_payload)`
   Then attach that value to `DemoPlanPreview(...)`.
   Do not alter `build_summary(...)` route flow or any HTTP status handling.

7. Keep confirmation and execution logic unchanged.
   Do not modify `HumanConfirmationService` or `DeterministicExecutionWorkflow` business behavior.
   The new public contract must adapt to the already persisted `confirmed_actions` structure rather than changing how confirmation or execution writes plan JSON.

8. Update frontend types and rendering.
   In `frontend/src/types/demo.ts`, add the action-manifest types and require `action_manifest` on `DemoPlanPreview`.
   In `frontend/src/App.tsx`:
   - replace direct rendering of `plan.proposed_actions` with `plan.action_manifest.actions`
   - keep the same section placement in the public plan detail
   - add a short source-aware caption if needed, but do not add new workflow controls
   - keep plan-tab switching behavior unchanged so the rendered manifest follows the displayed plan

9. Update frontend tests and client fixtures.
   In `frontend/src/App.test.tsx`:
   - add `action_manifest` to all mocked plan fixtures
   - assert the manifest section renders normalized actions
   - keep existing confirm, decline, and redaction expectations
   In `frontend/src/api/demo.test.ts`:
   - add `action_manifest` to typed mock payloads so TS contract checks remain current

10. Update docs for the new contract.
    In `README.md` and `docs/WEB_DEMO_README.md`, document that:
    - `plans[*].action_manifest` is now the stable public execution-preview contract
    - pre-confirmation runs use the proposed-action source
    - confirmed or executed plans use the confirmed-action source
    - this task does not expose session history or internal execution IDs

11. Run focused verification and stage only task files.
    Run the commands from section 7.
    Before staging, confirm `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` remain unstaged.

## 6. Testing Plan

- Unit tests: `tests/test_demo_api.py` for public serialization and `tests/test_demo_action_manifest.py` for manifest normalization and fallback behavior.
- Integration tests: `tests/integration/test_demo_api_gateway.py` for start, replan, confirm, and decline manifest behavior on real persisted plan JSON.
- Frontend tests: `frontend/src/App.test.tsx` and `frontend/src/api/demo.test.ts` for the new TS contract and rendered action preview.
- Smoke tests: `npm --prefix frontend run build` and document review of `README.md` plus `docs/WEB_DEMO_README.md`.
- Regression guard: public redaction behavior, plan version behavior, and existing route paths remain unchanged.

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add demo action manifest summary
```

Expected commands:

```bash
git status --short
git switch -c codex/demo-action-manifest-v0
git add backend/app/demo/schemas.py
git add backend/app/demo/service.py
git add backend/app/demo/action_manifest.py
git add tests/test_demo_api.py
git add tests/test_demo_action_manifest.py
git add tests/integration/test_demo_api_gateway.py
git add frontend/src/types/demo.ts
git add frontend/src/App.tsx
git add frontend/src/App.test.tsx
git add frontend/src/api/demo.test.ts
git add README.md
git add docs/WEB_DEMO_README.md
git add docs/specs/046-demo-action-manifest-v0.md
git add docs/plans/046-demo-action-manifest-v0-plan.md
git diff --cached --check
git commit -m "feat: add demo action manifest summary"
git push -u origin codex/demo-action-manifest-v0
```

If task `045` has already been merged elsewhere before execution, recreate the new branch from the merged tip that already contains `1ae2860` or equivalent `045` content. Otherwise, branch from the current `045` tip.

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not add a new public action-manifest endpoint.
- Do not remove or rename `proposed_actions`.
- Do not modify confirmation or execution persistence formats beyond what is strictly required to read them.
- Do not add replan buttons, history browsers, or session-aware public UI.
- Do not change benchmark harness, replay, workflow-core, or internal observability contracts.
- Do not add or modify Alembic revisions, indexes, or database columns.
- Do not add new dependencies.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `.env`, or other unrelated local files.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/046-demo-action-manifest-v0.md`.
- [ ] Every public `DemoPlanPreview` includes `action_manifest`.
- [ ] Start and replan paths expose `source = "proposed_actions"` when valid preview actions exist.
- [ ] Confirmed or executed plans expose `source = "confirmed_actions"` when valid confirmed actions exist.
- [ ] Declined plans without confirmed actions still expose the safe preview manifest.
- [ ] Confirmed-action manifests do not expose `idempotency_key`, `user_confirmed`, `action_id`, or `tool_event_id`.
- [ ] Invalid or legacy action structures fall back safely without breaking public serialization.
- [ ] The public frontend renders the manifest from `plan.action_manifest`.
- [ ] `proposed_actions` remains unchanged in this task.
- [ ] No endpoint, dependency, or Alembic migration was added.
- [ ] Docs were updated for the stable action-manifest contract.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final `plans[*].action_manifest` response shape.
- One example of a pre-confirmation manifest and one example of a confirmed manifest.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no Alembic migration changed.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any remaining follow-up limitation, especially that replan UI controls, public history browsing, and deeper action-preview redesign remain future tasks.
