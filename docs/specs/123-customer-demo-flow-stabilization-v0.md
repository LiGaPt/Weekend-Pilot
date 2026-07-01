# Spec: 123 Customer demo flow stabilization v0

## 1. Goal

Stabilize the public customer demo flow on `5173` so the repository’s main Mock World V2 presentation path is predictable, concise, and user-facing instead of engineer-facing. The backend, benchmark, recovery, and observability layers are already substantially built out, but the next delivery risk is not missing capability. It is drift in the visible customer flow: too many state variants, inconsistent result presentation, and fallback behavior that can remain technically correct while still looking unstable in the public demo.

After this task, the public customer surface must present one stable main chain for Mock World V2:
- start
- optional clarification
- optional replan
- confirm or decline
- execution result or safe fallback result

The page must keep internal detail hidden, keep the user-visible states bounded, and make the final result and fallback outcomes feel consistent across the main demo scenarios.

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in these areas:

- minimal Web UI as the primary demo surface
- deterministic service layer and public API contract reuse
- human-in-the-loop confirmation boundary
- Action Ledger and execution workflow, but only through existing public summaries
- LocalLife-Bench-driven delivery discipline
- separation between customer-facing UI and internal observability UI

This task corresponds to `docs/NEXT_PHASE_ROADMAP.md` after the earlier `M1. 评测与观测基础设施` and `M2. 前端分离` slices have already been implemented. The repository now has separate customer and internal surfaces, stable benchmark/integrity reporting, and hardened execution safety. The next smallest useful gap is convergence of the customer-facing flow itself so the public `5173` path matches the delivery story described in `README.md`.

Task selection notes that inform this spec:

- `docs/specs` and `docs/plans` are continuous and matched through Task `121`.
- The latest branch and latest documented commit correspond to Task `121`, so that task is currently in closure rather than leaving a tracked gap.
- The proposed Task `122` recovery-chaos expansion is already materially present in code and tests, so the next useful task is not another recovery-chaos slice.
- The highest-value next slice is a bounded customer-flow stabilization task that tightens the visible happy path and fallback path without changing the underlying benchmark/recovery architecture.

## 3. Requirements

- Keep the public customer surface scoped to one stable conversation-first flow:
  - start request
  - clarification reply when required
  - replan from an awaiting-confirmation state
  - confirm selected plan
  - decline selected plan
  - show final result or safe fallback result
- The customer page must continue to hide internal-only metadata and reviewer controls, including but not limited to:
  - trace identifiers
  - node history
  - tool event details
  - raw action IDs
  - raw target IDs when user-facing labels already exist
  - observability/debug wording
- The start-state composer must remain the only primary input on the page.
- The scenario-selector chips may appear only in start mode and must disappear once the run enters clarification, replan, confirmation, decline, or result progression.
- The customer page must preserve these bounded composer modes only:
  - `start`
  - `clarify`
  - `replan`
- Composer labels, placeholders, helper copy, and button text must stay user-facing Chinese and must not expose internal workflow terminology.
- The visible in-flight states must be bounded and consistent:
  - starting
  - clarifying
  - replanning
  - confirming
  - declining
  - one generic localized error state
- The page must show at most one active progress representation for the current run:
  - transient local spinner before the first streamed progress event
  - then one persistent progress card
- The progress card must stay above the active clarification, plan, or result card in thread order.
- The main plan card must remain summary-first:
  - show title
  - show concise summary
  - show bounded visible badges
  - keep reviewer-style structured detail panels hidden on the customer surface
- The customer plan card must not expose expandable detail sections for:
  - timeline internals
  - candidate raw IDs
  - route/debug summaries aimed at reviewers
  - proposed-action payload details
- The AMap read-only preview path must remain blocked from confirmation on the customer surface and must show one bounded read-only notice instead of a confirm button.
- Confirmation behavior must remain additive on top of existing APIs:
  - no new customer API routes
  - no response-shape redesign
  - only customer-surface presentation tightening
- Result presentation must be stabilized into one bounded result card shape:
  - one localized headline
  - one bounded outcome label
  - optional final arrangement message
  - completed actions
  - failed actions
  - next steps
- Result cards must not expose execution timeline internals, raw tool names when a user-facing label exists, or observability-only vocabulary.
- Fallback path handling must stay user-facing and bounded:
  - streamed-start failure shows one generic/localized error banner
  - clarification-required flow stays inside the same thread and same composer
  - replan stays inside the same thread and same composer
  - decline stays inside the customer thread and does not expose internal run mechanics
  - safe-stop style failed results may still render as a bounded result card if already represented by the public run summary
- The public docs must describe the stabilized customer flow in the same terms as the implemented UI and tests.
- Add or update focused unit, integration, and browser regressions that make the public flow stable across family/friends/solo/couple/rainy/budget presets.

## 4. Non-goals

- Do not add new benchmark cases, new suites, or change benchmark gate semantics.
- Do not add new recovery routing policy or new recovery UI concepts.
- Do not modify the internal observability page on `5174` except where docs need to distinguish it from `5173`.
- Do not redesign the public API contract outside additive compatibility work required to keep existing tests green.
- Do not add new providers, new write tools, or real-map execution behavior.
- Do not implement a new frontend information architecture beyond tightening the existing chat-first customer surface.
- Do not commit `.env`, API keys, tokens, secrets, generated artifacts, or caches.

## 5. Interfaces and Contracts

### Inputs

- Existing public demo API responses returned from:
  - `POST /demo/runs`
  - `POST /demo/runs/stream`
  - `POST /demo/runs/{run_id}/clarify`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- Existing frontend public run summary models in `frontend/src/types/demo.ts`
- Existing conversation-thread projection logic in `frontend/src/chat/thread.ts`

### Outputs

- Stabilized customer thread rendering for:
  - start state
  - clarification state
  - replan state
  - awaiting confirmation
  - declined result
  - completed/partially completed/failed/skipped terminal result
- Updated focused tests and docs that describe the customer demo flow in its stabilized form

### Schemas

This task must not redesign the public run schema. It depends on the current additive public shape and must keep these categories stable:

```json
{
  "run_id": "string",
  "status": "awaiting_clarification | awaiting_confirmation | completed | partially_completed | failed | skipped | declined",
  "read_profile": "mock_world | amap",
  "selected_plan_id": "string | null",
  "progress": {
    "schema_version": "public_demo_progress_v1"
  },
  "plans": [],
  "clarification": null,
  "action_count": 0,
  "execution_status": null,
  "feedback_status": null,
  "error": null
}
```

Customer-surface presentation contract constraints:

```json
{
  "customer_surface_rules": {
    "single_primary_composer": true,
    "hide_internal_debug_controls": true,
    "hide_reviewer_detail_panels": true,
    "one_active_progress_representation": true,
    "amap_preview_confirmation_blocked": true
  }
}
```

## 6. Observability

This task must not add a new observability surface.

Required behavior:

- The customer page continues consuming only the redacted public run summary contract.
- Customer tests must continue asserting that public responses do not expose internal-only fields.
- The customer surface may show bounded `Run ID` disclosure as already supported, but it must not surface trace/debug internals.
- No new benchmark artifact, trace panel, or internal telemetry block should be added to the customer surface.

## 7. Failure Handling

- If streamed start fails, the UI must show one bounded localized error banner and must not leave duplicate pending progress UI behind.
- If clarification payload is malformed or missing while the run claims `awaiting_clarification`, the UI must fall back to the generic localized error banner instead of exposing broken internal data.
- If a run enters `amap` read-only preview, confirm must remain unavailable and the user must see one bounded notice.
- If confirm, decline, clarify, or replan requests fail, the UI must return to a safe customer-visible error state without exposing internal exception details unless the current public API error message is already intended for user display.
- If terminal public statuses differ across happy path and fallback path, the result card must still render one bounded customer-visible result shape rather than branching into reviewer/debug layouts.
- If browser tests reveal unstable ordering between progress and plan/result cards, implementation must prefer deterministic thread ordering over additional new UI states.

## 8. Acceptance Criteria

- [ ] The public customer page on `5173` keeps one bottom composer as the only primary input.
- [ ] Scenario-selector chips appear only in start mode and disappear once the run leaves start mode.
- [ ] The customer surface keeps the existing conversation-first flow for start, clarification, replan, confirm, decline, and result display.
- [ ] The page shows at most one active progress representation for the current run.
- [ ] The persistent progress card renders above the active clarification, plan, or result card in thread order.
- [ ] The main plan card remains summary-first and does not expose reviewer detail panels on the customer surface.
- [ ] The customer surface continues hiding internal-only metadata and debug/reviewer controls.
- [ ] The AMap read-only preview path blocks confirmation and shows a bounded read-only notice.
- [ ] Happy path and fallback path both end in bounded, user-facing visible states without reviewer/debug leakage.
- [ ] Result cards use one stabilized customer-facing shape for completed, partial, failed, skipped, or declined outcomes.
- [ ] Focused frontend tests cover composer modes, scenario-selector visibility, progress-card ordering, plan-card constraints, result-card behavior, and read-only preview blocking.
- [ ] Focused API integration tests continue verifying the redacted public contract used by the customer page.
- [ ] Focused browser regression covers the stable customer flow for happy path, clarification, replan, confirm, and at least one fallback/error path.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` describe the public customer flow consistently with the implemented behavior.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
npm --prefix frontend test -- --run src/App.test.tsx src/chat/ConversationThread.test.tsx
python -m pytest tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend run test:e2e -- --grep "customer demo|happy path|clarification|replan|confirm"
git diff --check
git status --short
```

If the Playwright command name differs in the current repository, use the existing customer demo browser-test command already documented in the repo and keep the scenario scope equivalent.

## 10. Expected Commit

```text
feat: stabilize customer demo flow
```

## 11. Notes for the Implementer

Keep this task as a convergence slice, not a feature-expansion slice.

The core rule is: stabilize the public customer experience by tightening visible states and result presentation while reusing the current API and workflow behavior. If implementation pressure suggests changing benchmark semantics, adding recovery policy, redesigning internal observability, or introducing a new public API contract, stop and split that work into another task.

If execution uncovers that Task `122` is missing only numbering/doc alignment rather than implementation, record that as a follow-up documentation cleanup and do not widen this task.
