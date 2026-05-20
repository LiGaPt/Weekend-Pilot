# Spec: 037 Internal Observability Detail Panels v0

## 1. Goal

Add real internal inspection data to the existing `/observability` review page so reviewers can inspect tool events and action ledger entries without exposing raw sensitive payloads.

After this task, the internal observability API should return sanitized tool-event and action-ledger summaries alongside the existing run overview, timing summary, node history, agent roles, and observability summary. The `/observability` page should render those summaries instead of placeholder copy for the tool-event and action-ledger sections.

This task is the smallest useful continuation of `docs/NEXT_PHASE_ROADMAP.md` M2. Task 034 created the internal review surface, Task 035 redacted the public customer surface, and Task 036 aligned run/trace/benchmark summaries. The remaining gap is that two core internal panels are still placeholders, so the review surface is not yet fully useful.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. `docs/NEXT_PHASE_ROADMAP.md` prioritizes M2 frontend separation after the M1 observability work. The repository already has a route-based split between the public demo page and the internal `/observability` page, but the internal page still shows placeholder copy for the most important runtime details.

The current state is:

- Task 034 added `GET /internal/runs/{run_id}/observability` and the `/observability` page.
- Task 035 redacted internal observability fields from the public demo surface.
- Task 036 aligned run/trace/benchmark summary contracts.
- The internal page currently renders placeholders for:
  - tool events
  - action ledger
  - benchmark artifacts
  - recovery path

The next smallest useful step is to replace the tool-event and action-ledger placeholders with real sanitized data sourced from existing database rows. That makes the internal review page meaningfully actionable without broadening into a full frontend split or into later benchmark/recovery work.

## 3. Requirements

- Extend the internal observability API response with sanitized tool-event summaries for the requested run.
- Extend the internal observability API response with sanitized action-ledger summaries for the requested run.
- The new summaries must be additive and must not remove or rename existing response fields.
- The new summaries must be returned from the existing `GET /internal/runs/{run_id}/observability` endpoint.
- Tool-event summaries must be loaded from existing `tool_events` rows for the run.
- Action-ledger summaries must be loaded from existing `action_ledger` rows for the run.
- The summaries must be ordered chronologically and deterministically.
- The summaries must include only sanitized preview data and must not expose:
  - `action_id`
  - `event_id`
  - `tool_event_id`
  - `idempotency_key`
  - raw request bodies
  - raw response bodies
  - raw error payloads
  - secrets
  - API keys
  - tokens
  - authorization headers
- The `/observability` page must render real tool-event and action-ledger panels from the new response fields.
- The page must continue to render:
  - run overview
  - workflow timing summary
  - node history
  - agent roles
  - observability summary
- The page must keep the benchmark-artifacts and recovery-path panels as placeholders for later tasks.
- The public `/` page and public `/demo/runs*` contracts must remain unchanged.
- No new routes, database tables, Alembic migrations, or package dependencies may be added.

## 4. Non-goals

- Do not implement benchmark artifact browsing.
- Do not implement recovery-path visualization or replay linkage yet.
- Do not split the frontend into separate apps or deployables.
- Do not change workflow routing, confirmation behavior, execution behavior, or benchmark grading.
- Do not add authentication, RBAC, or admin login.
- Do not add new telemetry backends or trace formats.
- Do not change the public demo contract or customer-facing UI.
- Do not commit `.env`, API keys, tokens, secrets, generated artifacts, or runtime files.

## 5. Interfaces and Contracts

### Inputs

- Existing persisted `AgentRun` rows.
- Existing `ToolEvent` rows for the run.
- Existing `ActionLedger` rows for the run.
- Existing internal observability route inputs:
  - `run_id` path parameter.

### Outputs

- Existing internal observability response, extended with:
  - `tool_event_summaries`
  - `action_ledger_summaries`
- Existing internal observability page, extended to render those summaries.

### Schemas

The internal run summary should add these additive fields:

```json
{
  "tool_event_summaries": [
    {
      "tool_name": "search_poi",
      "tool_type": "read",
      "provider": "mock_world",
      "status": "completed",
      "cache_hit": false,
      "latency_ms": 12,
      "created_at": "2026-05-19T13:01:33+08:00",
      "request_preview": { "query": "museum" },
      "response_preview": { "candidate_count": 2 },
      "error_preview": null
    }
  ],
  "action_ledger_summaries": [
    {
      "action_type": "reserve_restaurant",
      "target_id": "green-table",
      "status": "succeeded",
      "created_at": "2026-05-19T13:01:33+08:00",
      "updated_at": "2026-05-19T13:01:40+08:00",
      "request_preview": { "party_size": 3 },
      "response_preview": { "reservation_id": "[REDACTED]" },
      "error_preview": null
    }
  ]
}
```

Preview objects must be sanitized with the existing redaction rules and may be omitted or null when no safe preview exists.

## 6. Observability

This task stays inside the existing internal observability surface.

It must:

- reuse existing persisted database data
- sanitize all previews with the same redaction rules used elsewhere in observability
- keep the existing run summary fields intact
- keep the public surface unchanged

It must not:

- add a new telemetry backend
- expose raw payloads
- expose internal row IDs or idempotency keys
- log secrets, tokens, or auth headers into the new summaries

## 7. Failure Handling

- If the run does not exist, return `404` as before.
- If the run exists but has no tool events or no action-ledger rows, return empty lists for those sections and show the empty state in the UI.
- If a preview cannot be sanitized, omit that preview rather than exposing raw payloads.
- If an unexpected repository or service error occurs while loading the run, preserve the existing `500` behavior for the internal route.
- If the frontend cannot load the internal summary, show the existing generic failure state.

## 8. Acceptance Criteria

- [ ] `docs/specs/037-internal-observability-detail-panels-v0.md` exists and matches this task.
- [ ] The internal observability API returns sanitized tool-event summaries for a run.
- [ ] The internal observability API returns sanitized action-ledger summaries for a run.
- [ ] The existing internal observability fields still return unchanged.
- [ ] The internal observability page renders tool-event details instead of placeholder copy.
- [ ] The internal observability page renders action-ledger details instead of placeholder copy.
- [ ] The benchmark-artifacts and recovery-path panels still remain placeholders.
- [ ] The public demo API and public customer page remain unchanged.
- [ ] No raw IDs, idempotency keys, secrets, tokens, or raw request/response payloads leak into the internal summaries.
- [ ] Backend unit and integration tests pass.
- [ ] Frontend unit tests pass.
- [ ] The frontend build passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored runtime files.

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add internal observability detail panels
```

## 11. Notes for the Implementer

Keep this task narrow.

The safest shape is:

1. add sanitized list summaries in the internal observability service,
2. render those summaries in the existing `/observability` page,
3. keep benchmark-artifact and recovery-path placeholders for later,
4. leave the public demo contract alone.

Do not widen this into a full frontend split or into benchmark/recovery work.
