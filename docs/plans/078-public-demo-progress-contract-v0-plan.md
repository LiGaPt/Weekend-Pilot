# Plan: 078 Public Demo Progress Contract v0

## 1. Spec Reference

Spec file:

```text
docs/specs/078-public-demo-progress-contract-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/customer-chat-first-ui-v0`.
- `git status --short` is clean in this workspace.
- `docs/specs` and `docs/plans` are continuous and slug-matched from `001` through `077`.
- Latest commit is `65d3267 feat: add chat-first customer ui`, and it matches the latest task docs in `077`.
- There is no draft `078` spec, draft `078` plan, or dirty working-tree evidence that a different unfinished task should be resumed first.
- `docs/plans/077-customer-chat-first-ui-v0-plan.md` contains a stale branch-name assumption, but the actual workspace state is clean and aligned to Task `077`.
- `backend/app/demo/service.py` already persists enough evidence for reconstruction:
  - `demo.initial_node_history`
  - `demo.continuation_history`
  - plan version metadata
  - clarification metadata
- `ToolEventRepository.list_for_run(...)` already returns ordered tool events with searchable request payloads.
- The current customer page progress text is frontend-local only in `frontend/src/chat/thread.ts`; there is no backend `DemoRunSummary.progress` contract yet.
- This task should stay contract-only. It should not introduce async background execution or a live progress transport path.

## 3. Files to Add

- `backend/app/demo/progress.py` - public progress stage enum, stable labels, read-time mapping helpers, and safe fallback reconstruction.
- `tests/test_demo_progress.py` - focused unit coverage for progress mapping, decline/confirm behavior, and malformed-metadata fallback.

## 4. Files to Modify

- `backend/app/demo/schemas.py` - add `DemoProgressSummary` models and the additive `DemoRunSummary.progress` field.
- `backend/app/demo/service.py` - load ordered tool events, build the public progress snapshot, and attach it to `DemoRunSummary`.
- `tests/test_demo_api.py` - extend schema serialization and validation coverage for the additive `progress` field.
- `tests/integration/test_demo_api_gateway.py` - assert progress snapshots across start/get/clarify/replan/confirm/decline/AMAP flows.
- `README.md` - document the additive public `progress` object in the Web demo API section.
- `docs/WEB_DEMO_README.md` - document the additive public `progress` object and the explicit non-goal that live transport is a later task.

## 5. Implementation Steps

1. Write the failing pure mapping tests first in `tests/test_demo_progress.py`.
   Cover these exact scenarios:
   - normal `awaiting_confirmation` run with ordered activity and dining search events yields a stage history ending in `ready_for_confirmation`
   - early clarification run yields `planning_queries` as the current stage and does not invent a new enum value
   - recovery-driven clarification after review work yields `reviewing_plan`
   - completed confirmed run yields `executing_confirmed_actions`
   - declined run stays at `ready_for_confirmation`
   - malformed or missing metadata falls back safely without raising

2. Add `backend/app/demo/progress.py`.
   Implement one contract-focused helper module with:
   - the exact public stage order from the spec
   - the exact stable Chinese label map from the spec
   - helpers to read `demo.initial_node_history`, `demo.continuation_history`, and ordered `ToolEvent` rows
   - tool-event classification for `search_poi` activity vs dining using:
     - `request_json.payload.category`
     - `request_json.payload.canonical_category`
   - a deduplicated ordered `stage_history` builder
   - a `current_stage` resolver with this precedence:
     - execution continuation history -> `executing_confirmed_actions`
     - declined run -> `ready_for_confirmation`
     - `wait_confirmation` or `awaiting_confirmation` -> `ready_for_confirmation`
     - otherwise the last mapped planning/review stage
     - otherwise the safest status-based fallback

3. Keep the task read-time only.
   Do not add new persistence for progress snapshots in this task.
   Do not update workflow nodes, Tool Gateway, or Redis runtime services.
   Do not add a new progress route or a Redis-only dependency for public readback.

4. Extend `backend/app/demo/schemas.py`.
   Add:
   - `DemoProgressStage` type or equivalent enum-constrained contract
   - `DemoProgressSummary`
   - `progress` on `DemoRunSummary`
   Keep the new field additive only.
   Do not remove, rename, or widen existing public fields.

5. Update `backend/app/demo/service.py::build_summary(...)`.
   Load ordered tool events once for the current run.
   Build `progress` from:
   - the current `AgentRun`
   - ordered tool events
   - existing selected plan / execution context already loaded by the method
   Return the additive `progress` object on every successful summary.
   Do not leak raw node names, raw tool names, or event identifiers into the serialized response.

6. Extend `tests/test_demo_api.py`.
   Add or update assertions so `DemoRunSummary.model_dump(mode="json")` includes:
   - `progress.schema_version`
   - `progress.current_stage`
   - `progress.current_label`
   - `progress.stage_history`
   Keep the existing redaction expectations intact.

7. Extend `tests/integration/test_demo_api_gateway.py`.
   Add focused assertions for:
   - normal start run returns progress ending in `ready_for_confirmation`
   - `GET /demo/runs/{run_id}` preserves the same progress snapshot
   - clarification start returns a pre-confirmation planning-stage snapshot plus the existing `clarification` payload
   - clarification continuation run returns its own progress snapshot
   - replan run returns its own progress snapshot and still advances `plan_version`
   - confirm/completed run returns `executing_confirmed_actions`
   - decline run stays on `ready_for_confirmation`
   - AMap preview still reaches `ready_for_confirmation` and remains non-confirmable
   Keep all existing public redaction assertions unchanged.

8. Update docs last.
   In `README.md`, add one short paragraph in the Web demo API section stating that public `DemoRunSummary` now includes an additive `progress` object derived from backend workflow evidence.
   In `docs/WEB_DEMO_README.md`, update the overview and expected-results sections so reviewer guidance mentions the new public `progress` contract and explicitly says that live mid-request transport is still out of scope here.

9. Run focused verification only.
   Do not widen this task into frontend tests or E2E unless a backend contract change unexpectedly breaks them.
   If a frontend type sync is required for compilation in a later branch, split that into the later consumer task instead of silently widening this task.

## 6. Testing Plan

- Unit tests: `tests/test_demo_progress.py` for stage mapping, execution/decline rules, and fallback behavior.
- Unit tests: `tests/test_demo_api.py` for additive `DemoRunSummary.progress` serialization and validation.
- Integration tests: `tests/integration/test_demo_api_gateway.py` for start, refresh, clarification, replan, confirm, decline, and AMAP preview progress snapshots.
- Document checks: review `README.md` and `docs/WEB_DEMO_README.md` to confirm they describe the additive `progress` field and the explicit non-goal that live transport is still pending.
- No frontend or Playwright checks are required unless this backend-only contract task unexpectedly forces them.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_progress.py tests/test_demo_api.py -q
python -m pytest tests/integration/test_demo_api_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add public demo progress contract
```

Expected commands:

```bash
git status --short
git switch -c codex/public-demo-progress-contract-v0
git add backend/app/demo/progress.py backend/app/demo/schemas.py backend/app/demo/service.py
git add tests/test_demo_progress.py tests/test_demo_api.py tests/integration/test_demo_api_gateway.py
git add README.md docs/WEB_DEMO_README.md
git commit -m "feat: add public demo progress contract"
git push -u origin codex/public-demo-progress-contract-v0
```

The implementer must confirm `.env`, secrets, generated runtime artifacts, and unrelated files are not staged.

If Task `077` has not merged upstream yet, create this branch from the merged equivalent of `65d3267` before applying the changes.

## 9. Out-of-scope Changes

- Do not change the customer UI to consume the new field.
- Do not make `POST /demo/runs` asynchronous.
- Do not add polling, SSE, WebSockets, or background jobs.
- Do not change internal observability routes or schemas.
- Do not change benchmark, replay, or workflow-routing behavior.
- Do not add Redis-only public read dependencies, new metadata persistence, new database schema, or new package dependencies.
- Do not commit generated artifacts, caches, secrets, or unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the contract-only scope.
- [ ] `DemoRunSummary.progress` is additive and present on successful public demo responses.
- [ ] `progress.current_stage` and `stage_history` use only the allowed public enum values.
- [ ] Raw workflow node names, raw tool names, event IDs, trace IDs, and provider payloads remain absent from the public contract.
- [ ] Clarification, replan, confirm, decline, and AMAP preview flows still behave correctly.
- [ ] Declined runs do not advance to `executing_confirmed_actions`.
- [ ] Existing public redaction assertions still pass.
- [ ] Required tests and document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or generated artifact was committed.

## 11. Handoff Notes

The implementer should report back with:

- Changed files.
- The exact stage-mapping rules implemented, including the fallback precedence.
- Verification commands and results.
- Confirmation that no async transport, polling route, SSE stream, or frontend consumer change was added.
- Commit hash.
- Push result.
- Any remaining follow-up note that real mid-request progress display still requires a later async/polling transport task on top of this contract.
