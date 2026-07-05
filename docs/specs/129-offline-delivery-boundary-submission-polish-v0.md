# Spec: 129 Offline delivery boundary and submission polish v0

## 1. Goal

Complete the final delivery boundary and reviewer-facing submission polish for WeekendPilot.

After this task is complete, the repository must clearly state that the current formal delivery path is an offline, local, deterministic `Mock World` closed loop. The current version must not imply that the public demo depends on real-world map data, real booking/order side effects, or a real MCP integration. `AMap` remains a script/API-only read-only preview, and any future real MCP/provider work remains outside the current formal submission boundary.

This task must also make the submission documents usable for final review: README delivery positioning, `docs/WEB_DEMO_README.md`, function coverage, evidence map, demo script, and recording checklist must all agree on the version name, task number, evidence aliases, artifact paths, and `5173 -> 5174` review sequence.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a local-life planning, confirmation, execution, feedback, observability, and benchmark-driven system. The blueprint requires a runnable Web UI, mock API/tool implementation, human confirmation before side effects, Action Ledger evidence, LocalLife-Bench coverage, and stable review artifacts.

`docs/NEXT_PHASE_ROADMAP.md` says the next phase should prioritize evaluation and observability infrastructure before broader product expansion. This task maps to that direction as a release-closure task: it does not add new benchmark infrastructure, but it makes the existing M1/M2 evidence and demo surfaces reviewable and unambiguous. It also preserves the roadmap boundary that `Mock World` remains the stable benchmark base while real map/provider work stays read-only preview and guardrailed.

Current repository sequencing shows the latest committed task is Task `128` (`memory-governance-final-closure-v0`). `docs/specs` and `docs/plans` are matched through Task `128`, with historical numbering gaps such as `122` treated as existing repository facts rather than repaired in this task. Task `129` is therefore the next smallest review-closure unit.

## 3. Requirements

- Confirm the latest committed numbered task is `128`, and add Task `129` spec/plan files only when implementing this task.
- Preserve the existing spec/plan history; do not rewrite historical task documents to renumber gaps.
- Update `README.md` so the top delivery boundary states that `Mock World` is the current formal main chain for public demo, benchmark, evidence, and offline submission.
- Update `README.md` so it explicitly says current delivery does not connect to real-world write services and does not depend on true MCP integration.
- Update `README.md` so `AMap` is described only as optional API/script-only read-only preview, not a formal benchmark or customer demo dependency.
- Update `docs/WEB_DEMO_README.md` with a concise 3-minute reviewer path and the required `5173 -> 5174` demo order.
- Update `docs/WEB_DEMO_README.md` so the public page (`5173`) and internal review page (`5174`) have separate responsibilities.
- Update `docs/submission/OVERVIEW.md` to align the submission version name, Mock World delivery boundary, evidence commands, and recording/read order.
- Update `docs/submission/FUNCTION_COVERAGE_MAP.md` so every listed capability maps to either live demo (`5173` / `5174`) or canonical evidence.
- Update `docs/submission/EVIDENCE_MAP.md` so evidence aliases and artifact paths match `backend.app.benchmark.submission_evidence`, `scripts/show_submission_evidence.py`, and existing `var/...` latest aliases.
- Update `docs/submission/DEMO_SCRIPT.md` so the script supports a short 3-minute judge path and an optional longer backup path.
- Update `docs/submission/RECORDING_CHECKLIST.md` so it verifies services, evidence aliases, browser order, secrets hygiene, and the offline delivery boundary.
- Inspect untracked delivery/workflow files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- For each untracked file or directory, decide explicitly whether it should be incorporated into tracked docs, deleted as local scratch, or left untracked with a documented reason.
- Do not leave review-relevant untracked delivery files in `git status --short` after the final commit unless they are intentionally ignored local scratch files.
- Add or update focused tests that enforce the submission documentation contract where practical.
- Verify that no `.env`, API key, token, secret, generated cache, virtual environment, or unrelated artifact is staged or committed.

## 4. Non-goals

- Do not implement a real MCP integration.
- Do not connect the customer demo to real-world provider writes.
- Do not promote `AMap` to a formal customer UI main path or benchmark dependency.
- Do not add new benchmark suites or regenerate canonical benchmark evidence unless existing aliases are broken.
- Do not redesign the frontend.
- Do not change runtime planning behavior unless a documentation test exposes a concrete mismatch.
- Do not rewrite historical specs/plans to fill the historical Task `122` gap.
- Do not commit `.env`, API keys, tokens, secrets, generated caches, virtual environments, or local runtime dumps.

## 5. Interfaces and Contracts

### Inputs

- Repository state:
  - `git log --oneline -n 12`
  - `git status --short`
  - `docs/specs/`
  - `docs/plans/`
- Project documents:
  - `docs/PROJECT_BLUEPRINT.md`
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `README.md`
  - `docs/WEB_DEMO_README.md`
  - `docs/submission/OVERVIEW.md`
  - `docs/submission/FUNCTION_COVERAGE_MAP.md`
  - `docs/submission/EVIDENCE_MAP.md`
  - `docs/submission/DEMO_SCRIPT.md`
  - `docs/submission/RECORDING_CHECKLIST.md`
- Evidence and support scripts:
  - `scripts/show_submission_evidence.py`
  - `scripts/demo_preflight.py`
  - `scripts/demo_amap_preview.py`
  - `backend/app/benchmark/submission_evidence.py`
- Existing tests:
  - `tests/test_demo_support_scripts.py`

### Outputs

- Updated documentation that consistently communicates:
  - Formal delivery main chain: `Mock World`
  - Public demo: `http://127.0.0.1:5173/`
  - Internal review: `http://127.0.0.1:5174/`
  - Submission evidence command: `python scripts/show_submission_evidence.py`
  - Preflight command: `python scripts/demo_preflight.py`
  - Optional read-only preview: `python scripts/demo_amap_preview.py`
  - No real-world write path and no real MCP dependency in the current submission
- Updated tests or document checks that fail if the submission docs drift from the delivery boundary.

### Schemas

This is a documentation and verification task. It must not introduce new API schemas, database tables, or runtime event formats.

The canonical submission evidence alias contract should remain equivalent to:

```json
{
  "release_gate_v1": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
  "coverage_gate_v1_5": "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
  "v2_integrity_gate": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
  "v2_integrity_passk": "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
  "formal_verification_all_registered": "var/formal-benchmarks/latest-all_registered-run-report.json",
  "recovery_review_family_route_failure_v1": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
}
```

## 6. Observability

This task does not add runtime observability instrumentation.

It must preserve and document the existing reviewer-facing observability surfaces:

- `5174` `Benchmark Summary`
- `5174` `System Integrity Summary`
- `5174` `Run Summary`
- `5174` `Trace Summary`
- `5174` `Tool Events`
- `5174` `Action Ledger`
- `5174` `Benchmark Artifacts`
- `5174` `Recovery Visualization`
- `python scripts/show_submission_evidence.py`

The documentation must state that public `5173` hides internal trace/tool details while internal `5174` is the audit surface.

## 7. Failure Handling

- If `docs/WEB_DEMO_README.md` is found under `docs/` rather than repository root, update `docs/WEB_DEMO_README.md` and keep references consistent with the actual path.
- If evidence aliases are missing, stop implementation and report the broken aliases instead of inventing paths.
- If `python scripts/demo_preflight.py` fails because services are not running, record the failure as an environment readiness issue and still run document-contract tests and `python scripts/show_submission_evidence.py`.
- If untracked files are local scratch, delete them only after confirming they are not needed for delivery documentation.
- If untracked files contain useful task/workflow content, incorporate the useful content into tracked docs and then remove the scratch source from the final staged set.
- If documentation still implies real-world writes, real MCP dependency, or AMap as formal main chain, treat that as a blocking failure.

## 8. Acceptance Criteria

- [ ] `README.md` states at the top that current formal delivery is the `Mock World` local/offline closed loop.
- [ ] `README.md` states that current delivery does not connect to real-world write services and does not depend on true MCP integration.
- [ ] `README.md` describes `AMap` only as optional API/script-only read-only preview.
- [ ] `docs/WEB_DEMO_README.md` contains a concise 3-minute reviewer path with `5173 -> 5174` order.
- [ ] `docs/WEB_DEMO_README.md` separates public customer demo responsibilities from internal reviewer responsibilities.
- [ ] `docs/submission/OVERVIEW.md` aligns version name, Mock World boundary, evidence commands, and reading order.
- [ ] `docs/submission/FUNCTION_COVERAGE_MAP.md` maps every capability to a live surface or canonical evidence artifact.
- [ ] `docs/submission/EVIDENCE_MAP.md` matches the actual evidence alias contract used by `scripts/show_submission_evidence.py`.
- [ ] `docs/submission/DEMO_SCRIPT.md` includes both a short judge path and optional longer backup path.
- [ ] `docs/submission/RECORDING_CHECKLIST.md` includes browser order, preflight/evidence checks, secrets hygiene, and offline boundary checks.
- [ ] Untracked review-relevant files are either incorporated, removed, or intentionally documented as local scratch.
- [ ] Focused tests or document checks cover the final submission wording and evidence alias contract.
- [ ] `python -m pytest tests/test_demo_support_scripts.py -q` passes.
- [ ] `python scripts/show_submission_evidence.py` prints all required evidence aliases as `[OK]`.
- [ ] `git status --short` after commit does not contain unintended review-delivery files.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit, except for intentionally ignored local files if any are explicitly documented.

## 9. Verification Commands

```bash
git log --oneline -n 12
git status --short
python -m pytest tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
git status --short
```

Optional, only if an AMap key is configured and the implementer wants to show the preview boundary:

```bash
python scripts/demo_amap_preview.py
```

If services are unavailable for `python scripts/demo_preflight.py`, the implementer must report the exact failing check and still complete the document-contract and evidence-alias verification.

## 10. Expected Commit

```text
docs: polish offline delivery boundary and submission evidence
```

## 11. Notes for the Implementer

Start by confirming current sequencing: latest task docs are `128`, latest commit is Task `128`, and Task `129` is not already present.

Treat this task as final submission closure, not product expansion. The most important wording is the boundary: current formal chain is `Mock World` local closed loop; no true MCP integration; no real-world write-side integration; `AMap` is optional read-only preview only.

The implementer should stop and report back if this spec conflicts with existing code, evidence aliases, `docs/PROJECT_BLUEPRINT.md`, or `docs/NEXT_PHASE_ROADMAP.md`.
