# Spec: 128 Memory governance final closure v0

## 1. Goal

Complete the final delivery closure for WeekendPilot memory governance. The goal is to prove that long-term memory is not just stored and reused, but is governed through explicit user-input precedence, advisory influence, lifecycle controls, sensitive-data minimization, local audit metadata, and benchmark-backed regression evidence.

After this task is complete, the repository must have a focused regression and documentation surface showing that memory can be created, queried, updated, disabled, logically deleted, lifecycle-controlled, minimized, audited, and safely excluded from active planning when it is disabled, ignored, candidate-only, weak, unsupported, or sensitive. The task must close the delivery surface without adding a new memory product, frontend UI, external account system, or broader personalization layer.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines long-term memory as part of the V1/V2 product direction and sets the memory governance rules that this task must prove:

- Current user input overrides long-term memory.
- Low-confidence memory should not strongly influence plans.
- Expired memory should be ignored or downgraded.
- Sensitive details should be structured and minimized rather than stored as raw text when possible.
- PostgreSQL remains the durable source of truth.
- Memory behavior must be observable, benchmarkable, and auditable.

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M5. Recovery and memory governance`. Although the roadmap says the default next-phase priority is M1 evaluation and observability infrastructure, the current repository has already advanced through benchmark timing, integrity gates, system integrity panels, scenario coverage, conversation/versioning closure, and recovery safe-stop evidence closure. The latest committed task is Task `127`, so the smallest next closure unit is Task `128`, focused on final memory governance evidence and regression hardening.

This task builds on the completed memory chain:

- Task `095` added memory decision logs and compact policy summaries.
- Task `096` added explicit memory lifecycle states.
- Task `097` added sensitive feedback candidate minimization.
- Task `098` expanded the memory governance benchmark suite.
- Task `109` added baseline user control for disable/suppress behavior.
- Task `119` added internal memory CRUD and lifecycle controls.
- Task `120` added audit preview and canonical minimized storage.
- Later closure tasks hardened execution safety, Mock World coverage, conversation/versioning, and recovery evidence.

Task `128` is therefore not a new feature expansion. It is the final memory-governance delivery closure: tests, evidence linkage, runbook updates, and submission-facing explanation.

## 3. Requirements

### A. Confirm task sequencing and repository boundary

- The implementation must confirm the latest committed numbered task is `127`.
- The implementation must confirm `docs/specs` and `docs/plans` are matched through Task `127`, with the known historical numbering gap at `122` treated as an existing repository fact rather than fixed in this task.
- The implementation must not create or rewrite historical specs/plans other than adding the approved Task `128` files.
- Existing unrelated untracked files must remain unstaged:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

### B. Preserve the existing memory governance contracts

The implementation must preserve these existing contracts:

- `memory_query_policy_v1` remains the runtime policy version.
- Explicit user input wins over conflicting memory.
- Advisory memory may fill vague requests.
- Expired high-confidence memory is downgraded to advisory when current rules allow.
- Disabled, ignored, and candidate memory must not enter active query shaping.
- Unsupported keys and unrecognized supported values must not mutate planning intent.
- Sensitive or extra free-form data must not be stored in active governable memory when a supported preference can be represented as a normalized enum.
- Internal memory CRUD and lifecycle controls remain backend-only and internal.
- Logical delete remains suppression to `ignored`, not physical deletion.

### C. Lock CRUD, lifecycle, and audit regression coverage

Focused regression coverage must prove:

- Internal memory create persists canonical minimized supported preference memory.
- Internal memory list/detail query exposes lifecycle state and governance audit preview.
- Internal memory update preserves immutable provenance fields while updating allowed mutable fields.
- Internal memory delete behaves as logical suppression to `ignored`.
- Internal memory lifecycle control supports the existing action set:
  - `activate`
  - `disable`
  - `suppress`
  - `expire`
  - `mark_candidate`
- Lifecycle control and delete remain idempotent.
- Governance control events remain durable and additive.
- Minimization events remain durable and additive for create/applied update.
- Disabled, ignored, and candidate rows remain excluded from later workflow `active_memories`, memory decisions, and decision logs.

### D. Lock read-memory policy regression coverage

Focused regression coverage must prove the existing read-memory governance rules continue to hold:

- Explicit user input suppresses conflicting memory for the same dimension.
- Advisory memory can fill a vague request when confidence is in the advisory range.
- Expired high-confidence memory is downgraded to advisory according to the current policy.
- Weak or unsupported memory is visible for audit but cannot mutate effective intent.
- Sensitive minimization cases do not leak sensitive raw fields into active planning.
- The memory governance benchmark suite still includes the current memory cases:
  - explicit override
  - advisory fill
  - expired advisory downgrade
  - disabled/ignored exclusion
  - candidate not auto-active
  - sensitive minimization

### E. Ensure final delivery evidence includes memory governance

The implementation must ensure reviewer-facing evidence can answer what memory governance proves. At minimum, the evidence surface must identify:

- the focused `memory_governance` benchmark suite
- memory-related coverage in `all_registered`
- memory-related coverage in `v2_integrity_gate`
- canonical evidence aliases used for submission
- commands used to refresh or inspect evidence
- the distinction between local governed memory and real external user-profile/account systems

If existing system integrity summary or evidence-summary tests already prove this, the implementation may only tighten tests/docs. If they are stale or incomplete, update the smallest relevant summary or script path.

### F. Update memory governance runbook

`docs/MEMORY_GOVERNANCE_RUNBOOK.md` must be updated from the older V1 read-only framing to the current local governance closure framing.

The runbook must explain:

- current memory is a local, repository-owned governance loop
- it does not depend on real user profiles, external accounts, third-party identity, vector databases, or real personalization services
- supported governable memory remains intentionally narrow
- CRUD/control/delete/lifecycle/audit/minimization are available through internal backend surfaces
- planning remains governed by explicit user-input priority and lifecycle filtering
- disabled, ignored, candidate, unsupported, weak, or sensitive memory must not become active planning influence
- canonical evidence and verification commands for memory governance closure

### G. Update final delivery/submission documentation where stale

If current submission-facing docs do not clearly include the final memory governance evidence, update them narrowly. Candidate docs include:

- `README.md`
- `docs/WEB_DEMO_README.md`
- `docs/V1_5_REVIEW_EVIDENCE.md`
- `docs/submission/EVIDENCE_MAP.md`
- `docs/submission/FUNCTION_COVERAGE_MAP.md`
- `docs/submission/DEMO_SCRIPT.md`
- `docs/submission/RECORDING_CHECKLIST.md`

Updates must be limited to memory governance closure and final delivery evidence. Do not rewrite the broader submission package.

### H. Keep generated evidence ownership unchanged

- Canonical generated benchmark/recovery evidence remains under `var/`.
- `var/` artifacts must not be staged unless already tracked and explicitly required.
- `docs/artifacts/` must not become the source of truth for this task.
- This task may run evidence-inspection or evidence-refresh commands during verification, but generated runtime artifacts must remain unstaged unless the implementation discovers a tracked artifact intentionally needs updating.

## 4. Non-goals

- Do not implement frontend memory-management UI.
- Do not implement authentication, authorization, external user accounts, or real user-profile integration.
- Do not introduce vector databases, embeddings, external personalization providers, or account synchronization.
- Do not add new memory types, new projected memory keys, or broader extraction rules.
- Do not redesign retention policy or add physical hard deletion.
- Do not change `memory_query_policy_v1` output names, score semantics, or benchmark grading semantics.
- Do not change workflow topology, confirmation boundaries, Tool Gateway behavior, Action Ledger behavior, or recovery routing.
- Do not add a new formal benchmark suite unless an existing test proves the current suite cannot express the closure.
- Do not rewrite unrelated submission docs.
- Do not commit `.env`, API keys, tokens, secrets, generated caches, virtual environments, `node_modules`, frontend build output, Playwright artifacts, or generated `var/` evidence.

## 5. Interfaces and Contracts

### Inputs

- Existing memory CRUD/control internal API:
  - `GET /internal/users/{user_id}/memory`
  - `GET /internal/users/{user_id}/memory/{memory_id}`
  - `POST /internal/users/{user_id}/memory`
  - `PATCH /internal/users/{user_id}/memory/{memory_id}`
  - `POST /internal/users/{user_id}/memory/{memory_id}/control`
  - `DELETE /internal/users/{user_id}/memory/{memory_id}`
- Existing durable `memory_items` fields and metadata:
  - `memory_type`
  - `key`
  - `value_json`
  - `text`
  - `confidence`
  - `status`
  - `expires_at`
  - `source_run_id`
  - `source_langsmith_trace_id`
  - `metadata_json.governance.control_events`
  - `metadata_json.governance.minimization_events`
- Existing workflow memory path:
  - repository governable-memory loading
  - `apply_memory_query_policy(...)`
  - `agent_runs.metadata_json.workflow.memory_policy`
- Existing benchmark memory-governance cases and suites.
- Existing submission/evidence docs.

### Outputs

- Focused tests proving final memory governance delivery behavior.
- Updated runbook and submission-facing docs where needed.
- Stable local evidence references for memory governance in final delivery materials.
- No changed public customer API behavior.
- No broadened memory schema or planner influence.

### Schemas

No new public schema is required.

Existing internal memory item responses must continue to include the additive governance audit shape introduced by Task `120`:

```json
{
  "memory_id": "00000000-0000-0000-0000-000000000001",
  "memory_type": "preference",
  "key": "activity_style",
  "value_json": {
    "preference": "indoor"
  },
  "text": null,
  "confidence": "0.7000",
  "status": "active",
  "lifecycle_state": "active",
  "governance_audit": {
    "policy_version": "memory_query_policy_v1",
    "normalized_value": "indoor",
    "governable": true,
    "expired": false,
    "tier": "advisory",
    "audit_status": "advisory",
    "audit_reason": "low_confidence_downgraded_to_advisory"
  }
}
```

Existing governance metadata must remain additive and sanitized:

```json
{
  "governance": {
    "control_events": [
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
    ],
    "minimization_events": [
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
    ]
  }
}
```

## 6. Observability

This task must not add a new tracing backend or external observability dependency.

It must verify and document the existing memory observability surfaces:

- row-level lifecycle state and governance metadata on `memory_items`
- internal memory API `governance_audit`
- run-level compact memory policy summary at `agent_runs.metadata_json.workflow.memory_policy`
- benchmark memory-governance score details in formal benchmark reports
- system integrity / submission evidence surfaces that summarize current memory-governance status

All memory-governance evidence must remain sanitized. It must not expose raw sensitive text, addresses, phone numbers, tokens, secrets, prompts, provider payloads, or irrelevant debug data.

## 7. Failure Handling

- If current tests reveal a memory-governance regression, fix the smallest root cause that restores the existing contract.
- If evidence-summary docs or scripts cite stale memory counts or stale runbook language, update the stale source rather than adding duplicate explanations elsewhere.
- If canonical generated evidence aliases are missing locally, verification may rerun the relevant scripts, but generated artifacts must remain unstaged unless explicitly tracked.
- If local PostgreSQL/Redis availability blocks integration tests, report the blocked command and run all non-service-dependent focused tests.
- If existing unrelated untracked files are present, do not modify or stage them.
- If implementation pressure suggests adding frontend UI, auth, new memory keys, or retention redesign, stop and report scope expansion instead of folding it into this task.

## 8. Acceptance Criteria

- [ ] Task `128` spec and plan are added under the standard numbered paths.
- [ ] Focused memory governance tests prove explicit override, advisory fill, expired downgrade, weak/unsupported suppression, disabled/ignored/candidate exclusion, and sensitive minimization.
- [ ] Focused CRUD/control tests prove create, list/detail query, update, disable, logical delete, lifecycle control, governance events, and minimization events.
- [ ] Workflow regression coverage proves non-governable memory does not enter active planning.
- [ ] Benchmark/suite tests prove the current memory governance cases remain registered and visible in integrity coverage.
- [ ] Reviewer-facing evidence docs or scripts clearly include memory governance status and canonical evidence paths.
- [ ] `docs/MEMORY_GOVERNANCE_RUNBOOK.md` reflects the current local governance closure, not the older read-only V1-only boundary.
- [ ] Documentation states that current memory governance is local and does not depend on real user profiles, external accounts, or third-party identity systems.
- [ ] No new memory UI, auth system, external account integration, vector DB, memory key, memory type, retention redesign, or hard delete is introduced.
- [ ] Generated `var/` evidence, caches, virtual environments, secrets, and unrelated local docs are not staged.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
git status --short
git branch --show-current
git log --oneline -5

python -m pytest tests/test_memory_governance_audit.py tests/test_memory_query_policy.py tests/test_memory_user_control.py tests/test_memory_crud_governance.py tests/test_feedback_memory_candidates.py tests/test_benchmark_suites.py -q
python -m pytest tests/integration/test_memory_api_gateway.py tests/integration/test_memory_crud_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "memory" -q
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py

git diff --check
git status --short
```

If implementation changes system integrity summary or observability summary code, also run:

```bash
python -m pytest tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py tests/test_observability.py -q
python -m pytest tests/integration/test_observability_gateway.py -q
```

## 10. Expected Commit

```text
test: close memory governance delivery surface
```

## 11. Notes for the Implementer

Keep Task `128` as a closure task. The implementation should primarily add or tighten tests and documentation around already-built memory capabilities.

Do not widen the memory product. The right proof is a small set of strong regressions plus clear evidence/runbook wording:

- memory is locally governable
- explicit user input wins
- advisory and expired memory are bounded
- disabled/ignored/candidate memory is excluded
- sensitive data is minimized
- CRUD/control/delete lifecycle actions are audited
- final delivery materials explain the boundary

If this spec conflicts with existing code or with `docs/PROJECT_BLUEPRINT.md`, stop and report the conflict before implementing.
