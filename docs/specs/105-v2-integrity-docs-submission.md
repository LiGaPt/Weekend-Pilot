# Spec: 105 V2 Integrity docs + submission package

## 1. Goal

Update the public README, the competition design doc, the submission package docs, and the demo script so they describe the current V2 Integrity Edition consistently.

The repository should read as:
- current submission posture: V2 Integrity Edition / V2 Integrity candidate
- real map provider support: API-only read-only preview, not the customer UI main path
- primary focus: benchmark completeness, memory governance, observability, recovery
- canonical evidence set: `release_gate_v1`, `coverage_gate_v1_5`, `v2_integrity_gate`, `v2_integrity_passk`, `all_registered`, `family_route_failure_v1`

This task is documentation-only. It must not change code paths, benchmark behavior, or generated artifacts.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 璇勬祴涓庤娴嬪熀纭€璁炬柦`.

It follows Tasks `102-104` and closes the submission-facing narrative gap after the backend summary API, the internal integrity panel, and the evidence-contract guardrail. The implementation work for those tasks already exists; this task makes the written submission package match the committed V2 posture.

This task fits these `docs/PROJECT_BLUEPRINT.md` architecture areas:
- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- failure handling and recovery auditability
- small, reviewable tasks

## 3. Requirements

- `README.md` must describe the current posture as V2 Integrity Edition or V2 Integrity candidate and explicitly call out AMap as API-only read-only preview.
- `docs/COMPETITION_DESIGN_DOCUMENT.md` must distinguish current behavior from future roadmap items and keep the V2 emphasis on benchmark completeness, memory governance, observability, and recovery.
- `docs/submission/OVERVIEW.md`, `docs/submission/EVIDENCE_MAP.md`, `docs/submission/FUNCTION_COVERAGE_MAP.md`, and `docs/submission/DEMO_SCRIPT.md` must agree on the same canonical evidence aliases and the same demo/reviewer story.
- The submission docs must mention `v2_integrity_passk` wherever the current V2 evidence set is enumerated.
- The demo script must describe `System Integrity Summary` as part of the reviewer flow and must not imply that AMap is a benchmark dependency or customer UI path.
- Historical V1.5 wording may remain only when it is clearly labeled as historical context; it must not be the current submission framing.
- All path names, command names, and alias names must match the committed scripts and artifact layout.

## 4. Non-goals

- Do not modify backend or frontend code.
- Do not rerun or regenerate benchmark or recovery artifacts.
- Do not change the shared evidence contract from Task `104`.
- Do not add new docs templates, dependencies, or CI jobs.
- Do not change the customer demo flow beyond wording in the docs listed in scope.
- Do not commit `.env`, API keys, tokens, secrets, or `var/` artifacts.

## 5. Interfaces and Contracts

### Inputs

- Current canonical docs under `README.md`, `docs/COMPETITION_DESIGN_DOCUMENT.md`, and `docs/submission/`.
- Current evidence aliases and script outputs from `scripts/show_submission_evidence.py` and `scripts/verify_review_evidence.py`.
- Current V2 reviewer surfaces from Tasks `102-104`, especially `System Integrity Summary`.

### Outputs

- Updated markdown docs with one consistent V2 Integrity Edition story.

### Canonical doc claims

- Current version posture: V2 Integrity Edition
- Real map provider role: API-only read-only preview
- Evidence aliases:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `v2_integrity_passk`
  - `all_registered`
  - `family_route_failure_v1`
- Reviewer scan order:
  - `Benchmark Summary`
  - `System Integrity Summary`
  - `Load Run`
  - `Trace Summary`
  - `Benchmark Artifacts`
  - `Recovery Visualization`

## 6. Observability

No runtime observability. The only verification is text consistency between docs and the already-implemented evidence scripts.

## 7. Failure Handling

- If a doc line conflicts with the current code or current canonical evidence output, rewrite the doc to match the repo truth.
- If a doc would imply AMap is part of the customer UI main path or formal benchmark path, treat that as a blocking wording error.
- If a doc omits `v2_integrity_passk` from the current V2 evidence set, treat that as incomplete.
- If a doc needs to mention a capability that is not actually backed by the current artifacts, do not invent it.

## 8. Acceptance Criteria

- [ ] `README.md` describes the current posture as V2 Integrity Edition / V2 Integrity candidate and keeps AMap as API-only read-only preview.
- [ ] `docs/COMPETITION_DESIGN_DOCUMENT.md` states the current V2 focus on benchmark completeness, memory governance, observability, and recovery.
- [ ] The submission docs use one canonical evidence list that includes `v2_integrity_passk`.
- [ ] The demo script mentions `System Integrity Summary` and the reviewer evidence-path flow.
- [ ] No doc says AMap is part of the customer UI main path or formal benchmark dependency.
- [ ] No doc contradicts the current `show_submission_evidence.py` / `verify_review_evidence.py` contract.
- [ ] `python scripts/show_submission_evidence.py` and `python scripts/verify_review_evidence.py` still match the documented alias set.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

- `python scripts/show_submission_evidence.py`
- `python scripts/verify_review_evidence.py`
- `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`
- `rg -n "V2 Integrity Edition|v2_integrity_passk|System Integrity Summary|API-only read-only preview|Mock World" README.md docs/COMPETITION_DESIGN_DOCUMENT.md docs/submission docs/WEB_DEMO_README.md`
- `git diff --check`
- `git status --short`

## 10. Expected Commit

`docs: document v2 integrity submission flow`

## 11. Notes for the Implementer

Keep the edit set narrow and synchronized. Update the submission package in one pass so README, design doc, evidence map, function coverage map, overview, and demo script all tell the same story.

Prefer preserving historical V1.5 references only in places where they are clearly historical, not current posture.

Stop and report if any current doc wording cannot be reconciled with the committed evidence contract or the existing reviewer surfaces.
