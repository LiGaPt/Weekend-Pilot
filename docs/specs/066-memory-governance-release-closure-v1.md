# Spec: 066 Memory Governance Release Closure v1

## 1. Goal

Close the release-readiness gap around the existing memory governance slice by turning the current implementation, tests, and benchmark evidence into one explicit V1 release contract.

WeekendPilot already has a governed read-memory policy in code, dedicated benchmark fixtures, dedicated grading, and blocking release-gate coverage. However, that capability is still not documented as a clearly releasable V1 surface. The roadmap still reads as if memory governance is broadly unfinished, the root README only mentions the suite in passing, and there is no dedicated runbook that states the exact rules, evidence sources, and acceptance boundary. After this task, a reviewer should be able to answer three questions quickly and deterministically: what the V1 memory slice actually does, which benchmark evidence proves it, and what still remains future work.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` places long-term memory governance in the V1/V2 evolution path and defines the product principles this task must now publish clearly:

- current user input overrides long-term memory
- low-confidence memory should not strongly influence plans
- expired memory should be ignored or downgraded
- memory should be governable, auditable, and bounded

`docs/NEXT_PHASE_ROADMAP.md` groups memory work under milestone `M5. 恢复、真实 provider、记忆治理`. That milestone remains open overall, but this repository already contains one concrete read-memory V1 slice:

- Task `047` introduced the initial read-memory query policy.
- Task `053` upgraded it to `memory_query_policy_v1`, added governed summaries, and added the `memory_governance` benchmark suite and score.
- Task `065` added `release_gate_v1`, and that blocking suite already includes all three memory-governance benchmark cases.

The repository also already contains the M1-style benchmark and observability infrastructure that would normally outrank later roadmap work:

- stage timing summaries and benchmark percentiles
- formal verification runner
- blocking release gate runner
- current `latest-release_gate_v1-run-report.json` and `latest-all_registered-run-report.json` evidence under `var/formal-benchmarks/`

Because that infrastructure already exists, the next smallest, highest-value task is not new instrumentation. It is a convergence task that closes the documentation and release-contract gap around the existing memory-governance slice.

## 3. Requirements

### A. Add one canonical memory governance runbook

- Add `docs/MEMORY_GOVERNANCE_RUNBOOK.md`.
- The runbook must define the exact V1 scope boundary for memory governance.
- The runbook must state that V1 is a read-only query-shaping capability, not full memory lifecycle management.
- The runbook must explicitly state that V1 only governs:
  - `memory_type == "preference"`
  - key `activity_style` for `activity_preferences`
  - key `spouse_lighter_meals` for `dining_preferences`
- The runbook must explicitly state the current normalized target values:
  - `activity_style -> citywalk | indoor | outdoor`
  - `spouse_lighter_meals -> lighter_options`
- The runbook must explicitly state that memory CRUD, user-editable memory controls, write-back, retention policy redesign, and broader projected keys are out of scope for this V1 slice.

### B. Publish one exact rule matrix

- The runbook must include one canonical rule matrix table for the V1 memory slice.
- The rule matrix must include, at minimum, rows for:
  - explicit user-input override
  - advisory memory fill for vague requests
  - expired high-confidence memory downgrade to advisory
  - supported-key boundary
  - weak or unsupported memory suppression
- The rule matrix must identify, per row:
  - the relevant memory key or dimension
  - the runtime rule
  - whether the rule is benchmark-backed or unit-test-backed only
  - the exact benchmark case or test surface used as evidence
  - the exact persisted evidence fields to inspect
- The rule matrix must use the current `memory_query_policy_v1` contract and must not invent broader V2 behavior.

### C. Map benchmark-backed release claims to current evidence

- The runbook must include an evidence section that maps each benchmark-backed V1 claim to an exact case ID and exact expected result.
- The benchmark-backed mapping must include these exact cases:

  1. `family_memory_override_v1`
     - `policy_version == "memory_query_policy_v1"`
     - `dimension_sources == {"activity_preferences": "user_input", "dining_preferences": "user_input"}`
     - `memory_outcomes == {"activity_style": "suppressed_user_override", "spouse_lighter_meals": "suppressed_user_override"}`

  2. `family_memory_advisory_fill_v1`
     - `policy_version == "memory_query_policy_v1"`
     - `dimension_sources == {"dining_preferences": "memory"}`
     - `dimension_tiers == {"dining_preferences": "advisory"}`
     - `memory_outcomes == {"spouse_lighter_meals": "applied_advisory"}`

  3. `family_memory_expired_advisory_v1`
     - `policy_version == "memory_query_policy_v1"`
     - `dimension_sources == {"activity_preferences": "memory"}`
     - `dimension_tiers == {"activity_preferences": "advisory"}`
     - `memory_outcomes == {"activity_style": "applied_advisory"}`

- The runbook must state that these three cases are already part of the blocking V1 release gate surface.
- The runbook must explain why the release-gate `tag_counts.memory_governance` value is `2`, not `3`:
  - the override case is tagged `memory_override`
  - the advisory-fill and expired-advisory cases are tagged `memory_governance`

### D. Use current release reports as canonical evidence inputs

- The runbook must define the canonical evidence inputs as:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
- The runbook must not declare `docs/artifacts/` as the source of truth for generated benchmark evidence in this task.
- The runbook must state the exact current blocking release-gate expectations:
  - `suite_id == "release_gate_v1"`
  - `case_count == 15`
  - `passed_count == 15`
  - `failed_count == 0`
  - `error_count == 0`
  - `overall_score == 1.0`
  - `level_counts == {"L1": 3, "L2": 8, "L3": 4}`
  - `tag_counts.memory_override == 1`
  - `tag_counts.memory_advisory == 1`
  - `tag_counts.memory_expired == 1`
  - `tag_counts.memory_governance == 2`
- The runbook must also state the exact broader formal-verification expectations:
  - `suite_id == "all_registered"`
  - `case_count == 17`
  - `passed_count == 17`
  - `failed_count == 0`
  - `error_count == 0`
  - `overall_score == 1.0`
  - `tag_counts.memory_override == 1`
  - `tag_counts.memory_advisory == 1`
  - `tag_counts.memory_expired == 1`
  - `tag_counts.memory_governance == 2`
- The runbook must clearly distinguish:
  - blocking release acceptance: `release_gate_v1`
  - broader supporting evidence: `all_registered`

### E. Converge README and roadmap wording

- Update `README.md` with one concise `Memory Governance V1` section.
- The README section must:
  - describe the V1 scope in one short paragraph
  - link to `docs/MEMORY_GOVERNANCE_RUNBOOK.md`
  - state that V1 uses the existing blocking release gate plus broader formal verification evidence
  - state that V1 is read-only and does not include memory CRUD or user-facing controls
- Update `docs/NEXT_PHASE_ROADMAP.md` so it no longer implies that the read-memory V1 slice is absent.
- The roadmap update must:
  - mark the current read-memory governance slice as already implemented and benchmarked
  - keep M5 open overall
  - list remaining open follow-up areas such as memory CRUD, user controls, and sensitive-data minimization as future work

### F. Keep the task documentation-only

- Do not change memory-policy runtime behavior in `backend/app/planning/memory_query_policy.py`.
- Do not change benchmark fixtures, suite membership, grading, or release-gate scripts.
- Do not add new tests unless a document mismatch reveals a real missing assertion and the user explicitly broadens scope later.
- Do not back-edit historical task docs only to make them match current suite counts.

## 4. Non-goals

- Do not implement memory writing, editing, deletion, retention controls, or user-facing memory management.
- Do not widen supported keys beyond `activity_style` and `spouse_lighter_meals`.
- Do not change benchmark case IDs, suite membership, or report schema.
- Do not add a new release-gate script for memory governance.
- Do not commit raw benchmark reports from `var/`.
- Do not commit generated or local-only files from `docs/artifacts/`.
- Do not back-edit historical task docs only to make them match current suite counts.
- Do not stage unrelated local files such as:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/`
  - `qc`

## 5. Interfaces and Contracts

### Inputs

- Current implementation contract in `backend/app/planning/memory_query_policy.py`
- Current benchmark fixtures:
  - `family_memory_override_v1`
  - `family_memory_advisory_fill_v1`
  - `family_memory_expired_advisory_v1`
- Current benchmark suite definitions in `backend/app/benchmark/suites.py`
- Current unit and integration tests for memory governance
- Current latest formal benchmark reports under `var/formal-benchmarks/`

### Outputs

- New runbook:
  - `docs/MEMORY_GOVERNANCE_RUNBOOK.md`
- Updated release-facing README section for memory governance
- Updated roadmap wording for the current memory-governance status

### Schemas

Release-evidence excerpt the runbook must align with:

```json
{
  "suite_id": "release_gate_v1",
  "case_count": 15,
  "overall_score": 1.0,
  "memory_cases": [
    {
      "case_id": "family_memory_advisory_fill_v1",
      "policy_version": "memory_query_policy_v1",
      "dimension_sources": {
        "dining_preferences": "memory"
      },
      "dimension_tiers": {
        "dining_preferences": "advisory"
      },
      "memory_outcomes": {
        "spouse_lighter_meals": "applied_advisory"
      }
    }
  ]
}
```

## 6. Observability

This task does not add new observability.

It consumes and documents existing observability and benchmark evidence already persisted by the product:

- `agent_runs.metadata_json["workflow"]["memory_policy"]`
- benchmark `scores[*].name == "memory_governance"`
- `latest-release_gate_v1-run-report.json`
- `latest-all_registered-run-report.json`

The task must not add new metadata fields, routes, traces, or artifact formats.

## 7. Failure Handling

- If the latest benchmark reports do not match the current tests or code, do not document the capability as closed; stop and report the mismatch.
- If `python scripts/run_benchmark_release_gate.py` fails, do not update the runbook or README as if blocking evidence were refreshed.
- If `python scripts/run_formal_verification.py` fails, do not claim broader supporting evidence was refreshed.
- If `docs/NEXT_PHASE_ROADMAP.md` is meant to stay local-only, stop before staging it and report that the roadmap convergence portion cannot be completed without user confirmation.
- If the current implementation differs from `053` historical wording, treat current code, current tests, and current benchmark reports as the canonical runtime truth for this release-closure task. Do not silently rewrite historical task docs.

## 8. Acceptance Criteria

- [ ] `docs/MEMORY_GOVERNANCE_RUNBOOK.md` exists.
- [ ] The runbook defines the V1 memory governance scope as read-only query shaping only.
- [ ] The runbook includes one explicit rule matrix that covers override, advisory-fill, expired-downgrade, supported-key boundary, and weak/unsupported suppression.
- [ ] The runbook distinguishes benchmark-backed rules from unit-test-backed-only rules.
- [ ] The runbook maps the three benchmark-backed memory cases to the exact expected policy version, dimension source/tier, and memory outcome values.
- [ ] The runbook documents the canonical evidence inputs as `var/formal-benchmarks/latest-release_gate_v1-run-report.json` and `var/formal-benchmarks/latest-all_registered-run-report.json`.
- [ ] The runbook documents the exact release-gate summary values `case_count=15`, `passed_count=15`, `failed_count=0`, `error_count=0`, `overall_score=1.0`, and the current memory-related tag counts.
- [ ] The runbook documents the exact formal-verification summary values `case_count=17`, `passed_count=17`, `failed_count=0`, `error_count=0`, `overall_score=1.0`, and the current memory-related tag counts.
- [ ] `README.md` contains a concise `Memory Governance V1` section that links to the runbook and states the acceptance boundary.
- [ ] `docs/NEXT_PHASE_ROADMAP.md` no longer frames the current read-memory slice as entirely unfinished.
- [ ] No runtime code, benchmark fixtures, suite membership, report schema, or release-gate scripts change in this task.
- [ ] Focused memory-governance unit tests still pass.
- [ ] Focused benchmark-harness integration checks still pass.
- [ ] `python scripts/run_benchmark_release_gate.py` passes and refreshes `latest-release_gate_v1-run-report.json`.
- [ ] `python scripts/run_formal_verification.py` passes and refreshes `latest-all_registered-run-report.json`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] No raw generated report under `var/` or `docs/artifacts/` is staged by this task.
- [ ] The post-commit working tree contains no newly introduced unrelated changes beyond the pre-existing local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_memory_query_policy.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -k "memory_policy or release_gate_v1" -v
python scripts/run_benchmark_release_gate.py
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
docs: close memory governance v1 release scope
```

## 11. Notes for the Implementer

Keep this task narrow and documentation-led.

The point is to close the release-contract gap around an existing capability, not to redesign memory governance. Treat the current code, the current tests, and the current latest benchmark reports as the implementation truth. If those surfaces disagree, stop and report instead of widening this task into a behavior change.

Do not turn this task into:

- memory policy v2
- new fixtures or suites
- new release automation
- a historical doc-rewrite sweep
- generated artifact commits
