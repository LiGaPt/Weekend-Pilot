# Spec: 115 Customer and Observability UI Split v0

## 1. Goal

Complete the next meaningful slice of frontend separation by splitting customer-facing content and internal review content, not just frontend entrypoints.

The repository already has two separate web surfaces: the customer demo on `http://127.0.0.1:5173/` and the internal observability review surface on `http://127.0.0.1:5174/`. However, the current customer surface still renders review-grade detail such as itinerary timeline, route and feasibility detail, pre-confirmation action detail, and post-confirmation execution timeline toggles. This leaves the semantic split unfinished even though the technical surface split already exists.

After this task, the customer page must show only customer-appropriate information: the conversation flow, the recommended plan summary, confirmation controls, replan/clarification affordances, and the final outcome summary. Detailed plan-review information must move to the internal observability surface, which must gain a reviewer-facing selected-plan detail panel with sanitized itinerary timeline and related plan context.

## 2. Project Context

This task belongs to milestone `M2. 前端分离` in `docs/NEXT_PHASE_ROADMAP.md`.

`docs/PROJECT_BLUEPRINT.md` requires WeekendPilot to keep customer-visible output and internal observability concerns separate. The roadmap defines M2 as the stage where customer-facing content and internal observability content stop being mixed in one user experience.

Relevant prior tasks already completed the surrounding foundation:

- `035` removed internal observability/debug fields from the public demo contract and kept them on the internal route.
- `056` split the frontend into two dedicated surfaces with separate dev/build entrypoints: customer on `5173`, internal on `5174`.
- `114` added a compact `Run Summary` digest to the internal observability route and page.

What remains unfinished is the content boundary. Today, the customer surface still exposes detailed plan-review content that belongs on the reviewer surface. This task completes the next smallest useful M2 slice by moving those details to the internal page while keeping the public flow intact.

This task directly touches these blueprint areas:

- Minimal Web UI customer demo surface
- Internal observability review surface
- Human confirmation boundary
- Action review and auditability
- Customer-safe vs internal-only information design

## 3. Requirements

- Keep the dedicated customer and internal frontend origins unchanged:
  - customer: `http://127.0.0.1:5173/`
  - internal: `http://127.0.0.1:5174/`

- Keep the current public demo API routes unchanged in this task.
- Keep the current internal observability API route unchanged:
  - `GET /internal/runs/{run_id}/observability`

- The customer page on `5173` must continue to support:
  - start run
  - clarification reply
  - replan reply
  - plan selection
  - confirm
  - decline
  - final result / feedback display

- The customer page on `5173` must keep showing:
  - conversation chronology
  - recommended plan summary
  - visible confirmation controls
  - final arrangement message or equivalent final result summary
  - readable status/progress information needed for the customer flow

- The customer page on `5173` must stop rendering detailed review panels and toggles for:
  - itinerary timeline
  - activity and dining detail panel
  - route and feasibility detail panel
  - pre-confirmation action manifest detail panel
  - post-confirmation execution timeline detail panel

- The customer page must not require a backend contract change to complete this task.
- Existing public `DemoRunSummary` payload fields may remain additive/backward compatible in this task, even if the customer UI no longer renders all of them.

- The internal observability route must add one additive top-level field:
  - `selected_plan_review`

- `selected_plan_review` must be `null` when the run has no selected plan.
- When present, `selected_plan_review` must use schema version:
  - `weekendpilot_internal_selected_plan_review_v1`

- `selected_plan_review` must contain sanitized selected-plan review data sufficient for internal plan inspection:
  - `plan_id`
  - `status`
  - `title`
  - `summary`
  - `activity`
  - `dining`
  - `timeline`
  - `route`
  - `feasibility`
  - `action_manifest`

- `selected_plan_review` must be derived from the already persisted selected plan JSON.
- `selected_plan_review` must not expose raw provider payloads, prompts, tokens, secrets, idempotency keys, action ledger request bodies, or tool-event request bodies.

- The internal observability page on `5174` must render a new `Selected Plan Review` section.
- The new section must be reviewer-facing and must display:
  - basic selected plan identity and summary
  - itinerary timeline
  - activity and dining detail
  - route and feasibility detail
  - confirmation-time action manifest detail

- The internal observability page must continue to render:
  - `Run Summary`
  - `Trace Summary`
  - `Tool Events`
  - `Action Ledger`
  - `Benchmark Artifacts`
  - `Recovery Visualization`

- The internal observability page must render a neutral empty state when `selected_plan_review` is `null`.

- Update active reviewer-facing docs so they describe:
  - customer page as result/confirmation-oriented
  - internal page as the location for timeline and detailed plan review

- No new dependencies may be added.
- No new API route may be added.
- No new database tables, columns, or migrations may be added.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not redo the frontend multi-entry split already completed by Task `056`.
- Do not redesign benchmark summary, system integrity summary, or recovery visualization.
- Do not remove or rename the existing internal observability sections.
- Do not change workflow routing, benchmark grading, action ledger persistence, or recovery behavior.
- Do not narrow the public demo backend contract in this task.
- Do not add authentication, RBAC, or admin access control.
- Do not stage generated runtime artifacts, build outputs, or unrelated local docs.

## 5. Interfaces and Contracts

### Inputs

- Existing customer demo UI data from `DemoRunSummary`
- Existing selected plan persistence in plan JSON
- Existing internal route:
  - `GET /internal/runs/{run_id}/observability`

### Outputs

- Customer UI no longer renders detailed timeline/route/action-review panels
- Internal observability route gains additive `selected_plan_review`
- Internal observability page gains reviewer-facing `Selected Plan Review` rendering

### Schemas

Example additive internal response excerpt:

```json
{
  "schema_version": "weekendpilot_internal_observability_run_v1",
  "run_id": "00000000-0000-0000-0000-000000000001",
  "run_summary": {
    "schema_version": "weekendpilot_internal_run_summary_v1",
    "run_id": "00000000-0000-0000-0000-000000000001",
    "trace_id": "trace-demo-1",
    "workflow_status": "awaiting_confirmation",
    "selected_plan_id": "11111111-1111-1111-1111-111111111111",
    "plan_status": "selected",
    "execution_status": null,
    "feedback_status": null,
    "stage_timing": {
      "present": true,
      "total_duration_ms": 420,
      "stage_count": 4,
      "slowest_stage_name": "execute_searches",
      "slowest_stage_duration_ms": 180
    },
    "tool_events": {
      "total_count": 5,
      "read_count": 5,
      "write_count": 0,
      "status_counts": {
        "completed": 4,
        "failed": 1
      },
      "provider_counts": {
        "mock_world": 5
      },
      "latest_event": null
    },
    "recovery": {
      "entered_recovery": false,
      "attempt_count": 0,
      "max_attempts": 0,
      "terminal_action": null,
      "terminal_status": null,
      "latest_error_type": null,
      "replay_case_id": null
    }
  },
  "selected_plan_review": {
    "schema_version": "weekendpilot_internal_selected_plan_review_v1",
    "plan_id": "11111111-1111-1111-1111-111111111111",
    "status": "selected",
    "title": "Family afternoon plan",
    "summary": "Start with an indoor activity, then wrap up with a lighter dinner.",
    "activity": {
      "name": "Family Science Center",
      "category": "activity",
      "address": "100 Mock Science Road",
      "tags": ["child_friendly", "indoor"]
    },
    "dining": {
      "name": "Light Table",
      "category": "dining",
      "address": "8 Mock Dining Street",
      "tags": ["lighter_options"]
    },
    "timeline": [
      {
        "sequence": 1,
        "item_type": "activity",
        "title": "Indoor activity",
        "start_label": "14:00",
        "end_label": "16:00",
        "duration_minutes": 120,
        "notes": ["Child-friendly indoor stop."]
      }
    ],
    "route": {
      "mode": "driving",
      "distance_meters": 3200,
      "duration_minutes": 18,
      "summary": "A short drive keeps the afternoon easy."
    },
    "feasibility": {
      "is_feasible": true,
      "reasons": ["Fits the requested afternoon window."],
      "warnings": [],
      "total_duration_minutes": 270,
      "route_duration_minutes": 18,
      "queue_wait_minutes": 5
    },
    "action_manifest": {
      "source": "proposed_actions",
      "action_count": 2,
      "actions": [
        {
          "action_ref": "reserve_restaurant",
          "execution_order": 1,
          "action_type": "reserve_restaurant",
          "target_id": "light-table"
        }
      ]
    }
  }
}
```

## 6. Observability

This task does not add a new observability recorder, new trace sink, or new benchmark artifact.

It extends reviewer-facing observability by exposing selected-plan detail on the internal review route and page. The new `selected_plan_review` field must be sanitized and derived from the persisted selected plan, and it must remain internal-only.

The task must not expose on the internal page:

- raw tool-event request/response/error payloads outside the existing dedicated panels
- prompts
- tokens
- secrets
- authorization headers
- idempotency keys
- raw provider request payloads
- debug trace blobs

## 7. Failure Handling

- If the run does not exist, the internal route must keep returning `404`.
- If the run exists but no selected plan exists, the internal route must still return `200` with `selected_plan_review = null`.
- If selected plan JSON is missing or malformed, the internal route must still return `200` with `selected_plan_review = null` rather than failing the entire page.
- If the customer page no longer shows detailed review sections, confirm/decline/replan/start behavior must still work.
- If customer tests fail because they still expect timeline or execution-detail toggles, update the tests to the new product intent rather than restoring the old UI.
- If the internal page fails to render because `selected_plan_review` is absent, fix the page to render a neutral reviewer fallback.
- If the internal page leaks raw payloads or sensitive fields from the selected plan review object, treat that as a task failure.

## 8. Acceptance Criteria

- [ ] `docs/specs/115-customer-observability-ui-split-v0.md` exists and matches this task.
- [ ] `docs/plans/115-customer-observability-ui-split-v0-plan.md` exists and matches this task.
- [ ] The customer page on `5173` still supports start, clarify, replan, confirm, decline, and final result display.
- [ ] The customer page no longer renders detailed timeline, activity/dining, route/feasibility, pre-confirmation action, or execution-timeline panels.
- [ ] The internal route `GET /internal/runs/{run_id}/observability` returns an additive `selected_plan_review` field.
- [ ] `selected_plan_review` is `null` when no selected plan exists.
- [ ] `selected_plan_review` is populated from persisted selected-plan data when a selected plan exists.
- [ ] The internal page on `5174` renders a reviewer-facing `Selected Plan Review` section.
- [ ] The internal page continues to render `Run Summary`, `Trace Summary`, `Tool Events`, `Action Ledger`, `Benchmark Artifacts`, and `Recovery Visualization`.
- [ ] The internal page renders a neutral fallback when `selected_plan_review` is absent.
- [ ] No new route was added.
- [ ] No database migration was added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] Focused backend, frontend, and E2E verification commands listed below pass, or blockers are reported clearly.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -q
npm --prefix frontend test -- --run src/App.test.tsx src/chat/ConversationThread.test.tsx src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
cd frontend && npx playwright test e2e/demo.spec.ts e2e/internal-observability.spec.ts --project=desktop-chromium
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: split customer and observability plan detail surfaces
```

## 11. Notes for the Implementer

Keep this task product-facing but small.

The key sequencing decision is:

1. do not redo the technical multi-entry split from Task `056`,
2. do not shrink the public backend contract yet,
3. remove detailed plan-review UI from the customer surface,
4. add the missing selected-plan detail surface to the internal observability route and page.

If implementation pressure appears to require public API narrowing, stop and split that into a follow-up task rather than widening this one.
