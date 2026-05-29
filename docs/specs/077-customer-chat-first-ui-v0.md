# Spec: 077 Customer Chat-First UI v0

## 1. Goal

Refactor the customer-facing Web demo at `http://127.0.0.1:5173/` from an inspector-first two-column layout into a chat-first single-column experience without changing the existing public demo API contract.

After this task, the first screen must show only one primary prompt composer plus a small set of example entries. User requests, system progress, clarification prompts, follow-up replans, recommended plan summaries, and final execution results must all appear in one chronological chat stream. The selected plan must no longer dump all detail blocks at once: the assistant should first present a recommended summary, then let the user expand timeline, activity/dining, route/feasibility, and confirmation-action details on demand. `run_id`, `action_count`, and similar internal/reviewer fields must not be visible by default on the customer surface.

## 2. Project Context

This task fits directly into `docs/PROJECT_BLUEPRINT.md` and the next-phase roadmap.

Relevant blueprint areas:

- Minimal Web UI as the primary demo surface
- Human-in-the-loop confirmation before side effects
- Customer-safe public surface boundary
- Multi-turn planning flow with clarification and follow-up replanning

Roadmap milestone alignment:

- Primary milestone: `M4. 多轮对话与方案版本`
- Secondary constraint: preserve the already-completed `M2. 前端分离` boundary

Current repository state matters here:

- Task `056` already separated customer and internal frontend surfaces.
- Tasks `059`, `060`, and `062` already made clarification, replan, and selected-plan replan indexing work on the customer page.
- Task `068` already closed the richer Web UI V1 slice and made execution timeline, trace summary, benchmark summary, and recovery visualization reviewer-verifiable.
- Tasks `071`, `074`, and `076` recently closed the default roadmap priority around M1 review evidence, latency/coverage gating, and contract guardrails.

Because those M1 closures are already in place and the current working tree is clean, the next smallest meaningful task is not more benchmark plumbing. The most visible remaining product gap is that the customer page still behaves like a form + inspector console instead of a conversation-style planner.

## 3. Requirements

### A. Replace the default customer layout with a chat-first entry

- The customer page must stop using the current default two-column “left rail + right workspace” presentation.
- The first render must show one primary prompt composer and a small example-entry area.
- The first render must not show a default-visible run summary card, plan detail panel, or reviewer-style metadata panel.
- The primary composer may remain multiline, but it must behave as one single main input area.
- Example entries must be clickable and must populate the main composer instead of auto-submitting.
- The read-path selector must no longer be default-visible on first render.
- If the read-path selector remains on the customer page, it must move behind an explicit collapsed advanced-options disclosure.
- `Mock World` must remain the default read path.
- The existing AMap read-only preview path must remain reachable from the customer page.

### B. Render the customer flow as one chronological chat stream

- Starting a run must append a user message item for the submitted request.
- While a start, clarify, replan, refresh, confirm, or decline request is in flight, the page must show a visible system-progress item in the same stream.
- Clarification responses must render as assistant clarification cards in the same stream, not as a separate inspector panel.
- Clarification replies must be entered inline from the chat flow and must continue using `POST /demo/runs/{run_id}/clarify`.
- Follow-up replans must render as part of the same chat flow and must continue using `POST /demo/runs/{run_id}/replan`.
- Confirmation results and execution feedback must render as assistant result cards in the same chat flow.
- The customer page must keep clarification, replan, confirm, decline, and refresh behavior working from the existing public API.
- Refreshing a run must update the latest visible state without appending duplicate historical assistant cards.

### C. Present plans summary-first instead of panel-first

- When a run reaches `awaiting_confirmation`, the assistant must first show one recommended-plan summary card instead of immediately rendering all detail sections fully expanded.
- The recommended summary card must show:
  - plan title or a safe fallback title
  - summary text or a safe fallback summary
  - current visible plan version label
  - customer-safe status wording
- Timeline, activity/dining, route/feasibility, and confirmation-action details must be hidden behind explicit expand/disclosure controls by default.
- The execution timeline for completed runs must also be hidden behind disclosure by default until the user expands it.
- The action-manifest preview must remain customer-visible, but it must appear under the progressive disclosure flow instead of as a default full panel.
- If multiple plans exist, the customer page must keep plan switching available through compact in-chat controls.
- Selecting a non-default plan must still update the selected plan used by confirm and replan flows.
- This task must not remove the current ability to replan from the selected non-default plan.

### D. Hide reviewer/internal metadata by default on the customer surface

- The customer page must stop showing `run_id` as a default-visible field.
- The customer page must stop showing `action_count` as a default-visible field.
- The customer page must stop showing raw `execution_status` and raw `feedback_status` as default-visible metadata rows.
- The customer page must not expose `trace_id`, `node_history`, `agent_roles`, `session_id`, or internal observability labels.
- If customer-visible debug metadata is retained at all, it must live behind an explicit disclosure that is closed by default.
- The optional closed-by-default disclosure may contain only customer-safe debugging fields such as:
  - `run_id`
  - visible plan version
  - current read path
  - refresh control
- The default-visible customer experience must remain human-readable and not require internal field literacy.

### E. Keep all existing customer capabilities working inside the new UI

- Clarification flows must still reach `awaiting_confirmation` without leaving the customer page.
- Replan flows must still advance visible version labels from `v1` to `v2`, `v3`, and so on.
- AMap preview runs must remain non-confirmable and must still show the existing read-only notice.
- Decline flows must remain available where they are currently supported.
- Execution result cards must still show completed and failed actions using customer-safe wording.
- The mobile customer surface must still avoid document-level horizontal scrolling.

### F. Keep the task frontend-scoped and additive

- Do not change public demo request or response schemas.
- Do not add a public conversation-history endpoint.
- Do not expose persisted internal conversation turns on the customer API.
- Do not redesign or modify the internal observability page at `5174`.
- Do not change benchmark routes, recovery routes, or reviewer-only evidence contracts.
- Do not change workflow routing, confirmation rules, execution rules, or AMap gating behavior.
- Do not add new dependencies.

### G. Update customer-facing docs and regression coverage

- Update `docs/WEB_DEMO_README.md` so the customer reviewer flow reflects the chat-first surface.
- Update `docs/RICHER_WEB_UI_V1_CHECKLIST.md` so the customer-side evidence wording matches the new summary-first chat flow.
- Add focused frontend regression coverage for:
  - first-screen composer + example entries
  - hidden default metadata
  - clarification in chat
  - replan in chat
  - selected-plan switching still affecting replan index
  - summary-first disclosure behavior
  - AMap path through advanced options
  - execution result rendering in the chat flow
- Keep the existing internal observability smoke coverage passing.

## 4. Non-goals

- Do not add or expose public conversation history from the backend.
- Do not redesign the internal observability frontend.
- Do not change the public demo API schema, request body shape, or response body shape.
- Do not add new benchmark, recovery, or AMap backend behavior.
- Do not add authentication, RBAC, or admin-only controls.
- Do not add a new frontend dependency, design system, or i18n framework.
- Do not change repository-wide styling beyond what is needed for the customer chat-first page.
- Do not commit `.env`, secrets, `frontend/dist/`, Playwright artifacts, `var/`, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- Existing customer API routes:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/clarify`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- Existing public frontend contracts:
  - `DemoRunSummary`
  - `DemoPlanPreview`
  - `DemoClarificationSummary`
  - `DemoActionManifestSummary`
  - `DemoExecutionSummary`

### Outputs

- A new frontend-local chat-thread projection layer built only from:
  - current local user submissions
  - current local action state
  - existing `DemoRunSummary` responses
- A refactored customer page that renders:
  - hero composer + example entries
  - chronological chat stream
  - summary-first plan cards with progressive disclosure
  - default-hidden run metadata
- Updated customer-facing reviewer docs and tests

### Schemas

This task does not add a new backend schema. It introduces a frontend-local projection shape similar to:

```json
{
  "chat_item": {
    "kind": "assistant_plan_card",
    "run_id": "00000000-0000-0000-0000-000000000011",
    "plan_id": "00000000-0000-0000-0000-000000000021",
    "version_label": "v2",
    "summary": "Recommended nearby family afternoon with one clear dinner reservation step.",
    "alternative_plan_ids": [
      "00000000-0000-0000-0000-000000000021",
      "00000000-0000-0000-0000-000000000022"
    ],
    "sections": [
      {
        "id": "timeline",
        "title": "时间线",
        "collapsed_by_default": true
      },
      {
        "id": "activity_dining",
        "title": "活动与餐厅",
        "collapsed_by_default": true
      },
      {
        "id": "route_feasibility",
        "title": "路线与可执行性",
        "collapsed_by_default": true
      },
      {
        "id": "pre_confirmation_actions",
        "title": "确认前动作",
        "collapsed_by_default": true
      }
    ]
  }
}
```

## 6. Observability

This task does not add new backend observability, new run metadata, or new internal reviewer routes.

It must keep using the current public run contract and customer-safe redaction boundary. No trace IDs, internal workflow history, agent roles, or persisted internal conversation-turn payloads may be surfaced on the default customer view.

The only customer-visible run-state signals added or reshaped in this task must come from existing public fields that are already safe to expose.

## 7. Failure Handling

- If a start, clarify, replan, confirm, decline, or refresh request fails, the customer page must keep the relevant user draft text intact and show the existing user-readable error banner.
- If the backend returns `awaiting_clarification` again after a clarification reply or replan, the customer page must continue the chat flow with the new clarification prompt instead of breaking back to an empty or panel-first state.
- If the selected plan changes, the plan summary card and confirm/replan behavior must switch with it without requiring a reload.
- If execution exists but `action_results` is empty, the result card must keep the existing neutral empty state wording.
- If the AMap preview path is active, the chat-first UI must still block confirmation and keep the read-only notice visible.
- Because this task does not add a public conversation-history API, a full browser reload may rebuild only from the latest loaded run state rather than reconstructing the full prior transcript. That limitation is acceptable in this v0 task and must not trigger scope creep into backend history exposure.

## 8. Acceptance Criteria

- [ ] `docs/specs/077-customer-chat-first-ui-v0.md` exists and matches this task.
- [ ] `docs/plans/077-customer-chat-first-ui-v0-plan.md` exists and matches this task.
- [ ] The repository remains continuous and matched through `076`, and this task uses new task ID `077`.
- [ ] The customer page first render shows one main composer plus example-entry UI.
- [ ] The customer page first render does not show the current default run-summary inspector.
- [ ] The read-path selector is not default-visible on first render.
- [ ] Starting a run adds a visible user message and a visible system-progress state in the same chat flow.
- [ ] Clarification prompts render inside the chat flow and clarification replies are submitted inline from that flow.
- [ ] Replan prompts render inside the chat flow and keep advancing visible plan versions.
- [ ] The recommended plan is shown summary-first before timeline, activity/dining, route/feasibility, and pre-confirmation action details.
- [ ] Those detail areas are collapsed by default and must be expandable on demand.
- [ ] Multiple plans remain selectable from the customer page.
- [ ] Selecting a non-default plan still affects confirm and replan behavior correctly.
- [ ] `run_id`, `action_count`, raw `execution_status`, and raw `feedback_status` are not visible by default on the customer page.
- [ ] `trace_id`, `node_history`, `agent_roles`, and `session_id` remain absent from the customer page.
- [ ] AMap preview runs remain non-confirmable and reachable through advanced options.
- [ ] The internal observability page remains unchanged in behavior.
- [ ] Existing public API request and response schemas remain unchanged.
- [ ] Customer frontend unit tests pass.
- [ ] Internal observability frontend regression tests pass.
- [ ] Existing backend demo API regression tests pass.
- [ ] Customer and internal Playwright E2E coverage pass.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated local file is staged.

## 9. Verification Commands

```bash
npm --prefix frontend run test -- --run src/chat/thread.test.ts src/App.test.tsx src/observability/ObservabilityPage.test.tsx src/api/demo.test.ts
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add chat-first customer ui
```

## 11. Notes for the Implementer

The implementation should stay frontend-only.

Important constraints:

- Extract a pure chat-thread projection helper instead of burying all new flow logic directly inside `App.tsx`.
- Do not widen this task into a backend history-exposure task.
- Preserve the current selected-plan semantics for confirm and replan.
- Preserve the internal/customer surface separation already established by tasks `056` and `068`.
- If the redesign starts to require a new public API to reconstruct full transcript history after hard reload, stop and split that into a separate follow-up task instead of quietly widening `077`.
