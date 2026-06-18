# Spec: 114 Internal Observability Run Summary v0

## 1. Goal

This task adds the smallest missing structured digest to the internal observability surface so a reviewer can understand one run’s key facts without scanning multiple panels and manually reconciling timing, tool-event, and recovery details.

The repository already persists a canonical `weekendpilot_run_summary_v1` into run metadata and already exposes detailed internal observability sections through `GET /internal/runs/{run_id}/observability`: run identity, workflow timing, tool-event previews, action-ledger previews, benchmark artifact context, and recovery-path visualization. The remaining gap is that these facts are not yet normalized into one reviewer-facing structured summary contract. After this task, the internal observability response must include an additive structured `run_summary` digest that directly reports stage-timing facts, tool-event rollups, and recovery-path outcome, and the `5174` page must render that digest prominently before the detailed sections.

## 2. Project Context

This task belongs to milestone `M1. 评测与观测基础设施` in `docs/NEXT_PHASE_ROADMAP.md`.

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. The roadmap explicitly lists these M1 priorities:

- stage timing and percentile visibility
- direct benchmark / case comparability
- unified run summary / trace summary / benchmark summary structure

The repository has already completed the surrounding foundation:

- `033` added workflow stage timing summaries
- `034` added the internal observability API and review console skeleton
- `037` added real tool-event and action-ledger detail panels
- `041` added benchmark artifact visibility
- `042` added recovery-path visualization
- `108` hardened suite timing percentile reporting
- `113` aligned integrity summary evidence
- `113.5` stabilized the focused observability E2E gate

So the next smallest useful step is not another evidence doc or a larger frontend redesign. The remaining gap is structure: one internal run should expose a stable, reviewer-friendly digest of the already-available facts.

This task directly touches these blueprint areas:

- LangSmith / local observability
- Tool Gateway observability consumption
- Harness / reviewer-facing inspection
- Failure handling and recovery auditability
- Minimal Web UI internal review surface

## 3. Requirements

- Keep the existing route `GET /internal/runs/{run_id}/observability`.
- Keep all existing top-level response fields backward compatible in this task.
- Add one additive top-level field to `InternalObservabilityRunSummary`:
  - `run_summary`
- `run_summary` must be nullable only if the service cannot build even a degraded digest from the run and existing observability data.
- In normal cases, `run_summary` must always be present for existing runs, including runs with no recovery and runs with no workflow timing summary.

- `run_summary` must use this schema version:
  - `weekendpilot_internal_run_summary_v1`

- `run_summary` must include a stage-timing digest section.
- The stage-timing digest must be derived from the same workflow timing source currently used by the internal observability response.
- The stage-timing digest must include:
  - `present`
  - `total_duration_ms`
  - `stage_count`
  - `slowest_stage_name`
  - `slowest_stage_duration_ms`
- If workflow timing is missing or malformed:
  - `present` must be `false`
  - numeric fields must be `null`
  - no request should fail only because timing is unavailable

- `run_summary` must include a tool-event digest section.
- The tool-event digest must be derived from the same sanitized ordered tool-event list currently loaded by `InternalObservabilityService`.
- The tool-event digest must include:
  - `total_count`
  - `read_count`
  - `write_count`
  - `status_counts`
  - `provider_counts`
  - `latest_event`
- `latest_event` must be `null` when the run has no tool events.
- When present, `latest_event` must include only reviewer-safe summary fields:
  - `tool_name`
  - `tool_type`
  - `provider`
  - `status`
  - `latency_ms`
  - `created_at`
- The tool-event digest must not include raw request / response / error payloads.

- `run_summary` must include a recovery digest section.
- The recovery digest must be derived from the same recovery metadata currently used by `recovery_path_summary`.
- The recovery digest must include:
  - `entered_recovery`
  - `attempt_count`
  - `max_attempts`
  - `terminal_action`
  - `terminal_status`
  - `latest_error_type`
  - `replay_case_id`
- If the run never entered recovery:
  - `entered_recovery` must be `false`
  - `attempt_count` must be `0`
  - `max_attempts` must be `0`
  - remaining fields must be `null`

- `run_summary` must also include the key run identity and outcome fields needed for reviewer scanability:
  - `run_id`
  - `trace_id`
  - `workflow_status`
  - `execution_status`
  - `feedback_status`
  - `selected_plan_id`
  - `plan_status`

- The internal observability service must prefer the existing canonical stored `weekendpilot_run_summary_v1` values for:
  - `trace_id`
  - `execution_status`
  - `feedback_status`
  - `selected_plan_id`
  - `plan_status`
  when those are present and valid.
- The additive structured digest may derive rollups from current live tool events and recovery metadata even when the canonical stored summary does not include them.

- The `5174` internal observability page must render a new `Run Summary` section above or at the start of the current run-detail workspace.
- The new section must let a reviewer see, without opening other sections:
  - workflow status and trace identity
  - whether timing exists, plus total duration and slowest stage
  - whether recovery happened, plus terminal recovery action/status
  - tool-event totals and provider / status rollups
- Existing `Trace Summary`, `Tool Events`, `Action Ledger`, `Benchmark Artifacts`, and `Recovery Visualization` sections must remain present.
- This task must not remove or rename the current `Trace Summary` section.

- Update active reviewer-facing documentation to mention that the internal review page now exposes a compact `Run Summary` digest before the detailed panels.

- No new dependencies may be added.
- No new database tables, columns, or migrations may be added.
- No new API route may be added.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not redesign the entire internal observability page.
- Do not change benchmark suite membership, scoring, or evidence aliases.
- Do not add a new benchmark summary route or a new system-integrity route.
- Do not change the detailed `tool_event_summaries`, `action_ledger_summaries`, or `recovery_path_summary` payload shapes except for additive compatibility if absolutely necessary.
- Do not expose raw provider payloads, prompts, secrets, ids for tool events, ids for action ledger rows, or internal-only tokens inside the new `run_summary` digest.
- Do not widen this task into reviewer runbook / submission-package cleanup.

## 5. Interfaces and Contracts

### Inputs

- Existing internal route:
  - `GET /internal/runs/{run_id}/observability`
- Existing stored canonical summary:
  - `metadata_json["summary"]` with schema `weekendpilot_run_summary_v1`
- Existing workflow timing source:
  - current internal observability timing extraction logic
- Existing ordered tool events for the run
- Existing recovery metadata:
  - current `workflow.recovery`-derived path summary inputs

### Outputs

- Additive `run_summary` field on the internal observability response
- Additive TypeScript type updates for the internal frontend
- New compact `Run Summary` rendering on `5174`
- Updated backend / frontend / E2E tests
- Updated reviewer-facing docs for the internal page

### Schemas

Example additive response excerpt:

```json
{
  "schema_version": "weekendpilot_internal_observability_run_v1",
  "run_id": "00000000-0000-0000-0000-000000000001",
  "trace_id": "trace-demo-1",
  "status": "failed",
  "workflow_timing_summary": {
    "schema_version": "workflow_timing_summary_v1",
    "total_duration_ms": 420,
    "stage_count": 4,
    "stages": [
      {
        "node_name": "execute_searches",
        "attempt_count": 1,
        "total_duration_ms": 180
      }
    ]
  },
  "recovery_path_summary": {
    "schema_version": "weekendpilot_internal_recovery_path_v1",
    "attempt_count": 1,
    "max_attempts": 2,
    "attempts": [
      {
        "attempt_index": 1,
        "source_node": "semantic_validator",
        "recovery_action": "stop_safely",
        "route_to": null,
        "error_type": "route_unavailable",
        "reason": "Recovery stopped after route failure.",
        "retry_budget_before": 0,
        "retry_budget_after": 0,
        "status": "stopped"
      }
    ],
    "replay_source": {
      "case_id": "family_route_failure_v1",
      "benchmark_report_path": "var/benchmarks/family_route_failure_v1.json"
    }
  },
  "run_summary": {
    "schema_version": "weekendpilot_internal_run_summary_v1",
    "run_id": "00000000-0000-0000-0000-000000000001",
    "trace_id": "trace-demo-1",
    "workflow_status": "failed",
    "selected_plan_id": null,
    "plan_status": null,
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
      "latest_event": {
        "tool_name": "check_route",
        "tool_type": "read",
        "provider": "mock_world",
        "status": "failed",
        "latency_ms": 12,
        "created_at": "2026-06-18T09:00:00Z"
      }
    },
    "recovery": {
      "entered_recovery": true,
      "attempt_count": 1,
      "max_attempts": 2,
      "terminal_action": "stop_safely",
      "terminal_status": "stopped",
      "latest_error_type": "route_unavailable",
      "replay_case_id": "family_route_failure_v1"
    }
  }
}
```

Degraded no-recovery, no-timing excerpt:

```json
{
  "run_summary": {
    "schema_version": "weekendpilot_internal_run_summary_v1",
    "run_id": "00000000-0000-0000-0000-000000000002",
    "trace_id": null,
    "workflow_status": "completed",
    "selected_plan_id": "00000000-0000-0000-0000-000000000010",
    "plan_status": "selected",
    "execution_status": "succeeded",
    "feedback_status": "completed",
    "stage_timing": {
      "present": false,
      "total_duration_ms": null,
      "stage_count": null,
      "slowest_stage_name": null,
      "slowest_stage_duration_ms": null
    },
    "tool_events": {
      "total_count": 0,
      "read_count": 0,
      "write_count": 0,
      "status_counts": {},
      "provider_counts": {},
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
  }
}
```

## 6. Observability

This task extends reviewer-facing observability structure only. It does not add a new recorder, a new local trace file, or a new LangSmith integration path.

The task must continue to reuse sanitized existing sources:

- canonical stored run summary
- workflow timing summary
- ordered sanitized tool events
- bounded recovery metadata

The new structured `run_summary` digest must remain reviewer-safe. It must not expose:

- raw tool-event request / response / error payloads
- raw action-ledger payloads
- prompts
- tokens
- secrets
- tool-event ids
- action ids
- idempotency keys
- raw workflow state blobs

## 7. Failure Handling

- If the run does not exist, the route must keep returning `404`.
- If the canonical stored `metadata_json["summary"]` is missing or malformed, the route must still succeed by deriving the additive structured digest from the run row, selected plan, tool events, workflow timing, and recovery metadata.
- If workflow timing is missing or malformed, the route must still succeed with `run_summary.stage_timing.present = false`.
- If tool events are missing, the route must still succeed with zeroed tool-event rollups and `latest_event = null`.
- If recovery metadata is missing or malformed, the route must still succeed with `entered_recovery = false` and null recovery outcome fields.
- The frontend must render empty / degraded summary states as readable reviewer copy instead of crashing or hiding the whole run detail view.
- If detailed sections load successfully, the additive `run_summary` digest must not contradict those sections for the same run.

## 8. Acceptance Criteria

- [ ] `docs/specs/114-internal-observability-run-summary-v0.md` exists and matches this task.
- [ ] `docs/plans/114-internal-observability-run-summary-v0-plan.md` exists and matches this task.
- [ ] `GET /internal/runs/{run_id}/observability` returns an additive `run_summary` field.
- [ ] Existing top-level internal observability response fields remain intact and backward compatible.
- [ ] `run_summary` directly reports stage-timing digest fields.
- [ ] `run_summary` directly reports tool-event rollup fields.
- [ ] `run_summary` directly reports recovery outcome digest fields.
- [ ] Runs with missing workflow timing still return `200` and a degraded `stage_timing.present = false`.
- [ ] Runs with no tool events still return `200` and zeroed tool-event rollups.
- [ ] Runs with no recovery still return `200` and `entered_recovery = false`.
- [ ] The `5174` page renders a compact `Run Summary` section before or at the start of the detailed run panels.
- [ ] Existing `Trace Summary`, `Tool Events`, `Action Ledger`, `Benchmark Artifacts`, and `Recovery Visualization` sections still render.
- [ ] No new route was added.
- [ ] No database migration was added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] Focused backend, frontend, and E2E verification commands listed below pass, or blockers are reported clearly.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -q
npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
cd frontend && npx playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add run summary observability
```

## 11. Notes for the Implementer

Keep this task additive and structure-focused.

The main design rule is that `run_summary` is a compact digest, not a second detailed observability payload. Reuse the canonical stored run summary where it is already authoritative, then derive the missing rollups from the existing tool-event and recovery data already being loaded for the page.

Do not widen this task into:

- benchmark-summary redesign
- system-integrity redesign
- reviewer runbook cleanup
- action-ledger rollup redesign
- new persistence formats

If `docs/TASK_INFO.md` is treated as authoritative task numbering by the human owner, stop before saving and confirm whether this task should stay `114` or be renumbered.
