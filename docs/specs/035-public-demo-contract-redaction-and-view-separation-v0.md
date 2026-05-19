# Spec: 035 Public Demo Contract Redaction and View Separation v0

## 1. Goal

Redact internal observability/debug data from the customer-facing demo surface while preserving the internal review surface introduced in Task 034.

After this task, the public `/demo/runs*` API and the main `/` web demo should only expose customer-safe run information: plan content, confirmation status, execution result, feedback, and the coarse `action_count` progress indicator. Internal observability details such as `trace_id`, `tool_event_count`, `node_history`, `observability_status`, and `agent_roles` must no longer appear in the public demo contract or customer UI. Those details must remain available through `GET /internal/runs/{run_id}/observability` and the `/observability` page.

This task closes the next smallest piece of `docs/NEXT_PHASE_ROADMAP.md` M2 "frontend separation" after Task 034 created the dedicated internal observability contract. It is intentionally narrower than a broader schema-normalization task because the current customer-facing surface still leaks internal implementation details.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` and `docs/NEXT_PHASE_ROADMAP.md` define the product direction. Task 034 added the internal observability API and review console skeleton, but the customer-facing demo page still mirrors internal execution metadata from the public `DemoRunSummary`.

Current implemented behavior shows the split is incomplete:

- `/internal/runs/{run_id}/observability` already exists and exposes internal run inspection data.
- `/observability` already exists as the internal reviewer page.
- The customer-facing `/` page still renders trace ID, node history, agent roles, observability status, and tool-event counts.
- The public `/demo/runs*` responses still serialize those internal fields.

This task is the smallest follow-up that finishes the public-side half of M2 without changing workflow behavior, benchmark behavior, confirmation safety, or the internal observability contract.

## 3. Requirements

- Remove internal observability/debug fields from the public `DemoRunSummary` contract.
- The public `DemoRunSummary` must no longer include:
  - `trace_id`
  - `tool_event_count`
  - `node_history`
  - `observability_status`
  - `agent_roles`
- The public `DemoRunSummary` must continue to include:
  - `run_id`
  - `status`
  - `selected_plan_id`
  - `plans`
  - `action_count`
  - `execution_status`
  - `feedback_status`
  - `error`
- The public `/demo/runs`, `/demo/runs/{run_id}`, `/demo/runs/{run_id}/confirm`, and `/demo/runs/{run_id}/decline` responses must all follow the narrowed customer-safe schema.
- The customer-facing `/` page must stop rendering the removed internal fields.
- The customer-facing `/` page must continue to render the plan content, confirmation controls, execution result, and feedback content.
- The internal `/observability` page and `GET /internal/runs/{run_id}/observability` endpoint must remain unchanged in behavior and still expose internal observability data.
- Update frontend TypeScript types so the public demo app compiles against the narrowed schema.
- Update backend and integration tests so the public route asserts redaction rather than internal field exposure.
- Update `README.md` and `docs/WEB_DEMO_README.md` to state that internal trace and node history inspection now lives on `/observability`, not on the public demo page.
- Do not add a second public endpoint or compatibility shim for the removed fields.

## 4. Non-goals

- Do not change the internal observability API or review console.
- Do not add authentication, RBAC, or admin-only access control.
- Do not split the frontend into separate apps or deployables yet.
- Do not add new database tables, migrations, or package dependencies.
- Do not change workflow routing, benchmark grading, replay behavior, or Action Ledger semantics.
- Do not remove `action_count` from the public demo contract yet.
- Do not add new telemetry or new local trace formats.
- Do not commit `.env`, API keys, tokens, secrets, generated build output, or runtime artifacts.

## 5. Interfaces and Contracts

### Inputs

- Existing persisted run metadata and plan records used by `DemoWorkflowService`.
- The public demo UI at `/`.
- The existing internal observability contract from Task 034.

### Outputs

Public backend response shape:

```json
{
  "run_id": "4dfb35e8-f5a4-4cb8-a2b9-e9c8bd4d4d7a",
  "status": "awaiting_confirmation",
  "selected_plan_id": "a4c5b2d1-3fe3-4f0a-9d2f-5c7a1a3b5d44",
  "plans": [],
  "action_count": 0,
  "execution_status": null,
  "feedback_status": null,
  "error": null
}
```

The removed fields must be absent from the serialized public response, not just hidden in the UI.

### Schemas

- `backend/app/demo/schemas.py` must define the narrowed `DemoRunSummary`.
- `frontend/src/types/demo.ts` must match the narrowed public contract.
- `backend/app/observability/schemas.py` remains unchanged for the internal schema.

## 6. Observability

This task removes internal observability data from the public surface only. It does not change telemetry collection or internal trace recording.

The internal observability endpoint and local trace buffer remain the authoritative places for:

- `trace_id`
- `tool_event_count`
- `node_history`
- `observability_status`
- `agent_roles`

The public customer page must no longer expose those values.

## 7. Failure Handling

- If a public caller or UI component still expects one of the removed fields, the build or tests should fail and the callsite should be updated.
- If the internal observability endpoint loses its fields during this task, treat that as a regression and restore it.
- If the customer UI loses access to `action_count`, `plans`, or confirmation/execution state, fix that in the same task.
- If docs still instruct reviewers to look for trace IDs on the public page, update the docs rather than restoring the leak.

## 8. Acceptance Criteria

- [ ] The public `DemoRunSummary` no longer serializes `trace_id`, `tool_event_count`, `node_history`, `observability_status`, or `agent_roles`.
- [ ] The public demo API routes still work for start, refresh, confirm, and decline.
- [ ] The public `/` page no longer renders internal observability/debug fields.
- [ ] The public `/` page still renders the plan, confirmation, execution, and feedback flow.
- [ ] The internal `/observability` page and `/internal/runs/{run_id}/observability` endpoint still expose the internal inspection data.
- [ ] Frontend unit tests pass with the narrowed public types.
- [ ] Backend public-demo tests pass with the redacted payload assertions.
- [ ] Internal observability tests still pass unchanged.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` point internal reviewers to `/observability`.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated untracked file is staged.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except pre-existing ignored runtime files.

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/test_observability.py -q
python -m pytest tests/integration/test_demo_api_gateway.py tests/integration/test_observability_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: redact public demo observability fields
```

## 11. Notes for the Implementer

Keep the internal observability route intact. This task is about removing internal inspection data from the public customer-facing contract, not about weakening the new internal review surface.

The safest implementation shape is:

1. narrow the public demo schema in the backend,
2. update the customer UI and frontend types to match,
3. assert the redaction in public API tests,
4. keep the internal observability tests as regression coverage,
5. update docs to direct reviewers to `/observability` for trace and node history inspection.

Do not add a compatibility field alias or a second public API path for the removed data.
