# Plan: 045 Demo Plan Version Lineage v0

## 1. Spec Reference

Spec file:

```text
docs/specs/045-demo-plan-version-lineage-v0.md
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

- Current branch is `codex/demo-follow-up-replan-v0`.
- Latest completed numbered task is `044`.
- Latest commit is `c1231b7 feat: add demo follow-up replan workflow`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `044`.
- There is no existing `045` spec, `045` plan, or `codex/demo-plan-version-lineage-v0` branch yet.
- Tasks `033` through `042` already cover the current M1/M2/M3 timing, benchmark, internal observability, and public/internal view-separation baseline.
- Task `043` added durable session and turn persistence.
- Task `044` added `POST /demo/runs/{run_id}/replan`, same-session follow-up runs, and compact conversation linkage metadata.
- The public demo API currently has no explicit plan-version field in `DemoRunSummary`.
- The public frontend already renders `proposed_actions` under `待确认操作`, so there is already a pre-confirmation action-preview surface.
- Pre-existing local untracked files remain outside this task:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `var/`
- Those untracked files must remain unstaged.

## 3. Files to Add

- `backend/app/demo/versioning.py` - pure helpers for version fallback, increment, label derivation, and metadata encoding.
- `tests/test_demo_versioning.py` - unit tests for default `v1`, legacy fallback, and repeated increment behavior.

## 4. Files to Modify

- `backend/app/demo/schemas.py` - add `DemoPlanVersionSummary` and make `DemoRunSummary.plan_version` required.
- `backend/app/demo/__init__.py` - export the new public schema if needed by callers/tests.
- `backend/app/demo/service.py` - persist `demo.plan_version` metadata on start/replan and always include `plan_version` in `build_summary(...)`.
- `tests/test_demo_api.py` - update summary serialization expectations and public-shape assertions.
- `tests/integration/test_demo_api_gateway.py` - assert `v1`, `v2`, `v3`, source lineage, and source-run stability.
- `frontend/src/types/demo.ts` - add the `DemoPlanVersionSummary` type and `plan_version` field.
- `frontend/src/App.tsx` - render the visible plan version label in the public demo.
- `frontend/src/App.test.tsx` - update fixtures and assert the version label is rendered.
- `frontend/src/api/demo.test.ts` - update typed mock summaries to include `plan_version`.
- `README.md` - document visible version behavior for initial and follow-up runs.
- `docs/WEB_DEMO_README.md` - document visible version behavior in the manual and automated demo flow.

## 5. Implementation Steps

1. Add the failing public summary tests first.
   Update `tests/test_demo_api.py` so serialized `DemoRunSummary` now requires a `plan_version` object and still omits `session_id`, conversation payloads, trace fields, and internal observability fields.

2. Add the failing pure version-helper tests.
   Create `tests/test_demo_versioning.py` with focused cases for:
   - missing metadata returns `v1`
   - malformed or zero/negative version metadata sanitizes to `v1`
   - a `v1` source produces a `v2` follow-up summary
   - a `v2` source produces a `v3` follow-up summary
   - missing source metadata is treated as `v1`

3. Add the failing gateway integration assertions before implementation.
   Extend `tests/integration/test_demo_api_gateway.py` so:
   - `POST /demo/runs` returns `plan_version.version_number == 1`
   - the first `replan` returns `v2` with `source_run_id` and `source_selected_plan_id`
   - a second `replan` from the `v2` run returns `v3`
   - the earlier run summaries remain unchanged when reloaded with `GET /demo/runs/{run_id}`

4. Add the public backend schema for version lineage.
   In `backend/app/demo/schemas.py`:
   - define `DemoPlanVersionSummary`
   - add `plan_version: DemoPlanVersionSummary` to `DemoRunSummary`
   In `backend/app/demo/__init__.py`, export the new schema if external imports or tests need it.

5. Implement a dedicated demo versioning helper module.
   In `backend/app/demo/versioning.py`, add pure helpers that:
   - read compact version metadata from `run.metadata_json["demo"]["plan_version"]`
   - sanitize legacy or malformed metadata to a `v1` default
   - derive `version_label` from `version_number`
   - build the next follow-up version from a source run plus source selected plan ID
   Keep this module demo-specific. Do not move versioning into workflow-core or repository layers.

6. Wire version persistence into `DemoWorkflowService.start_run(...)`.
   After the initial run exists and before commit:
   - ensure `demo.plan_version` is present with `version_number = 1`
   - keep source fields `null`
   - preserve existing `demo.trace_id`, `demo.initial_status`, `demo.initial_node_history`, and conversation-baseline behavior

7. Wire version persistence into `DemoWorkflowService.replan_run(...)`.
   After the follow-up run exists and before commit:
   - compute the source version from the source run using the helper fallback rules
   - persist the new follow-up `demo.plan_version` metadata with `source_run_id` and `source_selected_plan_id`
   - leave the source run’s metadata unchanged
   - keep all existing `044` replan validation and rollback semantics intact

8. Make `build_summary(...)` always return a public `plan_version`.
   Update `backend/app/demo/service.py` so every public summary path uses the helper to:
   - read persisted version metadata
   - fall back to `v1` for older runs
   - include the derived `version_label`
   This must apply equally to start, get, replan, confirm, and decline responses because they all use `build_summary(...)`.

9. Update frontend types and render the visible version label.
   In `frontend/src/types/demo.ts`, add `DemoPlanVersionSummary` and the required `plan_version` field.
   In `frontend/src/App.tsx`, render `run.plan_version.version_label` in the public run inspector with a user-facing label such as `方案版本`.
   Do not add replan controls, history browsing, or source-run IDs to the public UI in this task.

10. Update frontend tests to match the new contract.
    In `frontend/src/App.test.tsx` and `frontend/src/api/demo.test.ts`:
    - add `plan_version` to all mocked `DemoRunSummary` fixtures
    - assert the rendered version label appears after a successful start
    - keep all current public-page redaction assertions intact

11. Update docs for the visible version behavior.
    In `README.md` and `docs/WEB_DEMO_README.md`:
    - note that an initial run starts at `v1`
    - note that each follow-up replan returns a new `run_id` and increments the visible plan version label
    - keep the existing statement that session state remains internal and non-public

12. Run focused verification and stage only task files.
    Run the commands from section 7.
    Before staging, confirm `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` remain unstaged.

## 6. Testing Plan

- Unit tests: `tests/test_demo_api.py` for public summary shape and `tests/test_demo_versioning.py` for version fallback/increment logic.
- Integration tests: `tests/integration/test_demo_api_gateway.py` for `v1 -> v2 -> v3` behavior and source-run stability.
- Frontend tests: `frontend/src/App.test.tsx` and `frontend/src/api/demo.test.ts` for the new TS contract and visible label rendering.
- Smoke tests: `npm --prefix frontend run build` plus doc review of `README.md` and `docs/WEB_DEMO_README.md`.
- Regression guard: existing confirm/decline/demo preview behavior stays unchanged except for the additive `plan_version` field.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_versioning.py -q
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
feat: add demo plan version lineage
```

Expected commands:

```bash
git status --short
git switch -c codex/demo-plan-version-lineage-v0
git add backend/app/demo/schemas.py
git add backend/app/demo/__init__.py
git add backend/app/demo/service.py
git add backend/app/demo/versioning.py
git add tests/test_demo_api.py
git add tests/test_demo_versioning.py
git add tests/integration/test_demo_api_gateway.py
git add frontend/src/types/demo.ts
git add frontend/src/App.tsx
git add frontend/src/App.test.tsx
git add frontend/src/api/demo.test.ts
git add README.md
git add docs/WEB_DEMO_README.md
git add docs/specs/045-demo-plan-version-lineage-v0.md
git add docs/plans/045-demo-plan-version-lineage-v0-plan.md
git diff --cached --check
git commit -m "feat: add demo plan version lineage"
git push -u origin codex/demo-plan-version-lineage-v0
```

If task `044` has already been merged elsewhere before execution, recreate the new branch from the merged tip that already contains `c1231b7` or equivalent `044` content. Otherwise, branch from the current `044` tip.

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not add public replan controls to the frontend.
- Do not add public history or lineage-list endpoints.
- Do not redesign `proposed_actions` into a new `action_manifest` contract.
- Do not change the current “one follow-up equals one new run” model.
- Do not change workflow-core request/response schemas, benchmark schemas, or internal observability schemas.
- Do not add or modify Alembic revisions, indexes, or database columns.
- Do not add new dependencies.
- Do not stage `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `var/`, `.env`, or other unrelated local files.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/045-demo-plan-version-lineage-v0.md`.
- [ ] `DemoRunSummary.plan_version` is always present on public demo responses.
- [ ] A brand-new run returns `v1`.
- [ ] A first follow-up replan returns `v2`.
- [ ] A second follow-up replan from the `v2` run returns `v3`.
- [ ] `source_run_id` and `source_selected_plan_id` point to the immediate predecessor when applicable.
- [ ] Older source runs remain unchanged after replans.
- [ ] Legacy runs without version metadata still serialize safely as `v1`.
- [ ] The public frontend renders the version label.
- [ ] The public frontend still does not expose session or internal observability fields.
- [ ] `proposed_actions` behavior is unchanged in this task.
- [ ] No Alembic migration was added or edited.
- [ ] Docs were updated for the new visible version behavior.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final public `plan_version` response shape.
- The observed version chain from the gateway integration test, such as `v1 -> v2 -> v3`.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no Alembic migration changed.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/` were not staged.
- Any remaining follow-up limitation, especially that public replan UI controls and action-manifest normalization remain future tasks.
