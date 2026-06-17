# Spec: 113 System Integrity Summary Current Evidence v0

## 1. Goal

Align the internal reviewer-facing integrity surface with the current canonical evidence story.

The repository has already refreshed its canonical evidence artifacts and updated most top-level docs to the current `30/20/8` narrative: `all_registered` is `30/30`, `v2_integrity_gate` is `20/20`, and `safe_stop_gate_v1` is `8/8`. However, the internal `System Integrity Summary` API and `5174` reviewer page still aggregate an older, narrower slice of evidence. They emphasize `v2_integrity`, pass-k, memory-governance subset counts, and one replay review, but they do not present the reviewer-facing breadth / gate state in the same structure the docs now describe. After this task, a reviewer should be able to open `5174` and see a summary that matches the current release story without mentally reconciling old fixture numbers or missing sections.

## 2. Project Context

This task belongs to roadmap milestone `M1. 评测与观测基础设施` in `docs/NEXT_PHASE_ROADMAP.md`.

`docs/PROJECT_BLUEPRINT.md` makes evaluation and observability first-class parts of the product. The roadmap also says M1 should be prioritized before new feature breadth. That priority is still correct here: the next bottleneck is not missing user functionality, but reviewer trust and evidence convergence.

This task builds directly on the already-completed chain:

- `102` added the system integrity summary API
- `103` surfaced it on `5174`
- `104` hardened evidence contracts
- `112` refreshed canonical evidence artifacts and doc truth

This task is the smallest useful follow-up because it closes the remaining gap between current evidence truth and the internal reviewer surface. It touches these blueprint areas:

- LocalLife-Bench evidence packaging
- reviewer-facing observability
- benchmark / recovery evidence interpretation
- release-readiness documentation discipline

## 3. Requirements

- The internal endpoint `GET /internal/system/integrity-summary` must continue to return one reviewer-facing aggregate payload.
- The payload must remain additive and backwards-compatible for existing consumers. Existing fields must not be removed or renamed in this task.
- The payload must expose reviewer-visible evidence state that matches the current canonical `30/20/8` story:
  - `v2_integrity_gate` current gate summary from `latest-v2_integrity_gate-run-report.json`
  - `all_registered` formal-verification breadth summary from `latest-all_registered-run-report.json`
  - `safe_stop_gate_v1` safe-stop recovery gate summary from `latest-safe_stop_gate_v1-run-report.json`
  - existing pass-k stability summary from `latest-v2_integrity-passk-v0-report.json`
  - existing canonical replay review summary from `latest-family_route_failure_v1-review.json`
- Add a new additive `formal_verification_summary` section to the API schema and frontend types.
  - It must report suite identity, case counts, pass/fail/error counts, overall score, and latest report path.
  - It must reflect the full `all_registered` suite, not only the subset of cases tagged for memory governance.
- Add a new additive `safe_stop_summary` section to the API schema and frontend types.
  - It must report gate identity, suite identity when available, `release_blocked`, case counts, pass/fail/error counts, and latest report path.
  - It must read from the canonical alias `var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json`.
- Keep the existing `memory_governance_summary` section, but it must remain explicitly scoped to memory-governance cases rather than being interpreted as the full formal-verification summary.
- Keep the existing `recovery_replay_summary` section, but it must remain explicitly scoped to the canonical replay review rather than the safe-stop gate.
- `evidence_paths` must include `safe_stop_gate_v1` as an explicit evidence entry.
- `evidence_paths` entries for the reviewer-critical story must mark these evidence IDs as required:
  - `v2_integrity_gate`
  - `formal_verification_all_registered`
  - `safe_stop_gate_v1`
  - `recovery_review_family_route_failure_v1`
- `status` derivation must treat missing or invalid `safe_stop_gate_v1` evidence the same way it treats other required reviewer-critical evidence.
- The `5174` `System Integrity Summary` panel must render the new sections without removing existing ones.
- The panel must present the reviewer-facing current-evidence story clearly:
  - `v2_integrity` remains the hero section
  - `Pass@k`, `Formal Verification`, `Safe Stop Gate`, `Memory Governance`, and `Recovery Replay` each have distinct reviewer-readable sections
  - evidence-path copy controls remain available
- Existing frontend copy / mock payloads / tests that still encode stale `18` or `28` counts for this surface must be updated to the current `20` / `30` / `8` baseline.
- `docs/submission/RECORDING_CHECKLIST.md` must no longer quote stale `18/18` or `28/28` values for the integrity summary narrative.
- This task must not rerun or redefine benchmark suites; it must consume the current alias files as truth.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not redesign plan versioning, replan behavior, or action manifest behavior.
- Do not add new benchmark cases, gates, failure profiles, or replay flows.
- Do not change benchmark grading logic or current canonical evidence generation scripts.
- Do not add new routes, new pages, or a new reviewer workflow beyond the existing `5174` panel.
- Do not refresh `var/` evidence artifacts as part of this task unless verification requires a local read of already-generated aliases.

## 5. Interfaces and Contracts

### Inputs

- `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`
- `var/formal-benchmarks/latest-all_registered-run-report.json`
- `var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json`
- `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`
- `var/recovery-reviews/latest-family_route_failure_v1-review.json`

### Outputs

- Extended `SystemIntegritySummary` API payload
- Updated TypeScript contract for the internal observability frontend
- Updated `5174` rendering for the new summary sections
- Updated backend / frontend / e2e tests and reviewer checklist text

### Schemas

The task adds these additive top-level sections to `SystemIntegritySummary`:

```json
{
  "formal_verification_summary": {
    "status": "ready",
    "suite_id": "all_registered",
    "case_count": 30,
    "passed_count": 30,
    "failed_count": 0,
    "error_count": 0,
    "overall_score": 1.0,
    "latest_report_path": "var/formal-benchmarks/latest-all_registered-run-report.json"
  },
  "safe_stop_summary": {
    "status": "ready",
    "gate_id": "safe_stop_gate_v1",
    "suite_id": "recovery_focused",
    "release_blocked": false,
    "case_count": 8,
    "passed_count": 8,
    "failed_count": 0,
    "error_count": 0,
    "latest_report_path": "var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json"
  }
}
```

The existing sections remain present and valid:

- `benchmark_summary`
- `stability_summary`
- `memory_governance_summary`
- `recovery_replay_summary`
- `timing_summary`
- `redaction_summary`
- `evidence_paths`

## 6. Observability

This task extends reviewer-facing observability only. It does not add new trace pipelines or database writes.

The system must continue to:

- read canonical latest alias files
- return relative evidence paths only
- avoid exposing secrets or internal-only execution keys
- degrade gracefully when evidence is missing or invalid

The API must make the current evidence story easier to audit, not more verbose.

## 7. Failure Handling

- If `latest-safe_stop_gate_v1-run-report.json` is missing, `safe_stop_summary.status` must become `missing`, its reason must explain the missing alias, and top-level `status` must degrade accordingly.
- If `latest-safe_stop_gate_v1-run-report.json` exists but fails schema validation, `safe_stop_summary.status` must become `invalid`, and top-level `status` must become `invalid_evidence`.
- If `latest-all_registered-run-report.json` exists but does not include a usable benchmark summary, `formal_verification_summary.status` must become `invalid`.
- If optional pass-k evidence is missing or invalid, the existing degraded behavior for stability must remain unchanged.
- The frontend must render missing / invalid reviewer sections as readable neutral states rather than crashing or hiding the whole panel.
- If canonical evidence paths exist but section-specific parsing fails, the raw path must still remain visible in `evidence_paths`.

## 8. Acceptance Criteria

- [ ] `GET /internal/system/integrity-summary` returns additive `formal_verification_summary` and `safe_stop_summary` sections.
- [ ] The API keeps existing integrity-summary fields intact.
- [ ] The API reads `all_registered` and `safe_stop_gate_v1` latest aliases and reports current reviewer-facing counts from them.
- [ ] `safe_stop_gate_v1` appears in `evidence_paths`.
- [ ] Missing or invalid `safe_stop_gate_v1` evidence degrades top-level status the same way other required reviewer evidence does.
- [ ] The `5174` `System Integrity Summary` panel renders reviewer-readable sections for `Formal Verification` and `Safe Stop Gate`.
- [ ] Existing `Pass@k`, `Memory Governance`, and `Recovery Replay` sections still render.
- [ ] Frontend fixtures and tests for this surface no longer use stale `18/18` or `28/28` reviewer counts.
- [ ] `docs/submission/RECORDING_CHECKLIST.md` no longer contradicts the current `30/20/8` reviewer story.
- [ ] Focused backend, frontend, and e2e tests for the integrity-summary surface pass.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_system_integrity_summary.py tests/integration/test_observability_gateway.py tests/test_review_evidence.py -q
npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend exec playwright test e2e/internal-observability.spec.ts --project=desktop-chromium
python scripts/show_submission_evidence.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
fix: align system integrity summary with current evidence
```

## 11. Notes for the Implementer

Keep this task additive and reviewer-focused.

Do not collapse `formal_verification_summary`, `memory_governance_summary`, `safe_stop_summary`, and `recovery_replay_summary` into one overloaded block. They represent different reviewer questions and map to different evidence aliases.

If current latest alias contents differ from the numbers used in this spec, the alias files win. Update fixtures and reviewer text to the actual alias truth, but keep the structural design from this spec.
