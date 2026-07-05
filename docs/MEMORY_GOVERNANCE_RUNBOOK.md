# Memory Governance Runbook

## Overview

WeekendPilot's current memory capability is a local governance loop, not a raw preference store. It combines query-shaping policy, internal CRUD controls, lifecycle state, sensitive-data minimization, row-level audit metadata, workflow audit summaries, and benchmark evidence.

The current delivery surface is intentionally local:

- It uses repository-owned PostgreSQL rows and Mock World benchmark cases.
- It does not depend on real user profiles, external accounts, third-party identity, vector databases, embeddings, or real personalization services.
- It does not expose a user-facing memory-management UI.
- It keeps the governable memory domain narrow so behavior remains deterministic and auditable.

Use this runbook to verify what the memory governance closure proves, which commands refresh evidence, and which capabilities remain out of scope.

## Current Scope Boundary

Current governed memory is intentionally narrow:

- Supported `memory_type`: `preference`
- Supported keys:
  - `activity_style` -> `activity_preferences`
  - `spouse_lighter_meals` -> `dining_preferences`
- Supported normalized values:
  - `activity_style -> citywalk | indoor | outdoor`
  - `spouse_lighter_meals -> lighter_options`
- Runtime policy version: `memory_query_policy_v1`
- Focused benchmark suite: `memory_governance`
- Blocking/system evidence suites:
  - `release_gate_v1`
  - `v2_integrity`
  - `all_registered`

The current governance surface includes:

- query-time policy that applies, downgrades, suppresses, or ignores memory
- internal list/detail/create/update/control/delete routes
- lifecycle states `active`, `expired`, `disabled`, `ignored`, and `candidate`
- logical delete as suppression to `ignored`
- additive governance control events
- additive minimization events
- additive `governance_audit` preview on internal memory responses
- sanitized run-level memory policy summaries under `agent_runs.metadata_json["workflow"]["memory_policy"]`

The current governance surface does not include:

- public memory-management UI
- auth or permission modeling
- hard physical deletion
- broad retention-policy redesign
- external account/profile sync
- vector DB or embedding-backed memory
- new memory types or projected keys

## Rule Matrix

| Rule | Runtime Contract | Evidence Surface |
| --- | --- | --- |
| Explicit user input wins | If the user explicitly supplies `activity_preferences` or `dining_preferences`, conflicting memory is suppressed with `winner_source = "user_input"`. | `family_memory_override_v1`; `tests/test_memory_query_policy.py`; `memory_governance` score |
| Advisory memory can fill vague requests | Supported memory with advisory confidence may fill a missing dimension when user input is vague. | `family_memory_advisory_fill_v1`; `tests/test_memory_query_policy.py`; run-level `advisory_memory_keys` |
| Expired high-confidence memory is downgraded | Expired high-confidence supported memory is downgraded to advisory rather than treated as primary. | `family_memory_expired_advisory_v1`; `downgraded_expired_keys`; `governance_audit.audit_reason` |
| Disabled and ignored memory are excluded | Disabled/ignored rows remain visible to internal read surfaces but do not enter active planning. | `family_memory_disabled_ignored_v1`; `tests/integration/test_langgraph_workflow_gateway.py -k memory` |
| Candidate memory is not auto-active | Feedback-generated candidate memory is not promoted into active planning during the same run. | `family_memory_candidate_not_auto_active_v1`; candidate lifecycle tests |
| Sensitive details are minimized | Feedback candidates and internal CRUD-supported preferences store normalized structured values and avoid raw sensitive text. | `family_memory_sensitive_minimization_v1`; `tests/test_feedback_memory_candidates.py`; minimization events |
| CRUD and lifecycle are audited | Create/update/control/delete operations preserve provenance and append governance/minimization events when applied. | `tests/test_memory_crud_governance.py`; `tests/test_memory_user_control.py`; internal memory API tests |

## Internal Governance API

The current internal backend surface is:

- `GET /internal/users/{user_id}/memory`
- `GET /internal/users/{user_id}/memory/{memory_id}`
- `POST /internal/users/{user_id}/memory`
- `PATCH /internal/users/{user_id}/memory/{memory_id}`
- `POST /internal/users/{user_id}/memory/{memory_id}/control`
- `DELETE /internal/users/{user_id}/memory/{memory_id}`

Supported lifecycle control actions:

- `activate -> active`
- `disable -> disabled`
- `suppress -> ignored`
- `expire -> expired`
- `mark_candidate -> candidate`

Delete is logical suppression. It sets the row to `ignored` and does not physically remove the row.

Each returned memory item includes durable row fields plus `governance_audit`, which previews how the current read-memory policy would classify the row. This preview is derived from current row state and does not store raw free-form sensitive text.

## Audit and Minimization Fields

Row-level audit metadata lives under `memory_items.metadata_json["governance"]`.

Control events are appended for applied create/update/control/delete lifecycle operations:

```json
{
  "schema_version": "memory_crud_governance_v0",
  "action": "disable",
  "from_status": "active",
  "to_status": "disabled",
  "actor": "user",
  "source": "internal_memory_api_v1",
  "reason": "user_requested_control",
  "acted_at": "2026-07-05T12:00:00+00:00",
  "changed_fields": ["status"]
}
```

Minimization events are appended for create and applied update when supported preference memory is canonicalized:

```json
{
  "schema_version": "memory_audit_minimization_v0",
  "action": "create",
  "actor": "user",
  "source": "internal_memory_api_v1",
  "reason": "manual_memory_seed",
  "normalized_value": "indoor",
  "dropped_text": true,
  "dropped_value_keys": ["address", "note"],
  "acted_at": "2026-07-05T12:00:00+00:00"
}
```

Run-level policy evidence remains compact and sanitized:

- `policy_version`
- applied/advisory/downgraded/unsupported memory keys
- dimension outcomes
- memory decisions
- decision log
- policy summary counts

It does not expose raw memory text, raw `value_json`, provider secrets, prompts, or debug payloads.

## Benchmark Evidence

The focused `memory_governance` suite currently covers six memory cases:

1. `family_memory_override_v1`
2. `family_memory_advisory_fill_v1`
3. `family_memory_expired_advisory_v1`
4. `family_memory_disabled_ignored_v1`
5. `family_memory_candidate_not_auto_active_v1`
6. `family_memory_sensitive_minimization_v1`

These cases are also represented in broader delivery evidence:

- `all_registered` verifies the full registered case inventory and currently includes all memory governance cases.
- `v2_integrity` verifies V2 memory-mode coverage, including override, advisory, expired, disabled/ignored, candidate-not-active, and sensitive-minimization modes.
- `release_gate_v1` keeps the blocking baseline memory checks for override, advisory, and expired downgrade.
- `System Integrity Summary` exposes memory-governance status from canonical `all_registered` evidence.

Canonical generated evidence aliases:

- `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`
- `var/formal-benchmarks/latest-all_registered-run-report.json`

Do not treat `docs/artifacts/` as the source of truth.

## Verification Commands

Run focused memory regression tests:

```bash
python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/test_feedback_memory_candidates.py tests/test_benchmark_suites.py -q
```

Run focused memory integration tests:

```bash
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
```

Run reviewer/evidence checks:

```bash
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py
```

Refresh evidence only when needed:

```bash
python scripts/run_benchmark_release_gate.py
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/run_formal_verification.py
```

Generated `var/` artifacts should remain unstaged unless a task explicitly says otherwise.

## Practical Review Checklist

- Confirm explicit user input suppresses conflicting memory.
- Confirm advisory memory only fills vague requests.
- Confirm expired high-confidence memory is downgraded to advisory.
- Confirm disabled, ignored, and candidate rows are excluded from active planning.
- Confirm supported preference CRUD stores canonical minimized `value_json` and `text = null`.
- Confirm governance control events and minimization events are durable and additive.
- Confirm sensitive strings such as addresses, phone numbers, tokens, secrets, prompts, and debug traces do not enter active planning summaries.
- Confirm `System Integrity Summary` and `show_submission_evidence.py` can point reviewers to canonical evidence.
- Confirm no `.env`, API key, token, secret, generated `var/`, virtualenv, `node_modules`, frontend build, or Playwright artifact is staged.

## Open Follow-ups

Future work may add a public memory-management UI, stronger retention policy, broader memory types, or account-linked personalization. Those are intentionally outside the current local governance closure.
