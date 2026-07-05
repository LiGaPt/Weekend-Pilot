# Spec: 127 Recovery and Safe-Stop Evidence Closure v0

## 1. Goal

Complete the recovery and safe-stop evidence closure so WeekendPilot can prove that recovery failures stop safely instead of executing write actions. After this task, route unavailable, ticket sold out, dining unavailable, combined failure, and safe-stop gate paths must be explainable, replayable, observable, and covered by focused tests.

This task should make the reviewer-facing recovery story mechanically trustworthy: the latest recovery replay aliases and safe-stop summaries must come from generated artifacts, failure paths must include failure reason, recovery attempt, terminal status, and zero write action evidence, and the internal observability page must link to the latest alias, review artifact, source report, and replay report.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` requires recovery decisions to be bounded, traceable, and safe, with no write-side effects before confirmation. It also defines recovery capability and observability as core benchmark dimensions.

`docs/NEXT_PHASE_ROADMAP.md` places this work primarily under `M5. Recovery and Memory Governance`, specifically the remaining recovery routing, recovery visualization, and chaos harness auditability loop. It also depends on the M1 evaluation and observability foundation because the proof must be visible through benchmark reports, run summaries, artifact aliases, and the internal review page.

The repository is currently complete through Task `126` (`conversation-plan-versioning-closure-v0`). Task `126` explicitly left recovery and safe-stop coverage to a follow-up closure task, making Task `127` the next smallest useful recovery evidence slice.

## 3. Requirements

- Refresh recovery replay review evidence for the canonical recovery case and the `recovery_focused` suite:
  - default canonical review remains `family_route_failure_v1`
  - suite review covers the current 8 recovery-focused cases
  - latest aliases are refreshed only when review results pass
- Verify the recovery-focused failure inventory includes:
  - route unavailable
  - ticket sold out
  - dining unavailable
  - combined route/dining or ticket/route failures
  - safe-stop gate coverage
- Ensure every covered failed path exposes:
  - typed or human-readable failure reason
  - at least one recovery attempt
  - terminal recovery action ending in `stop_safely`
  - terminal workflow status of `failed`
  - explicit zero write action guarantee
- Ensure the safe-stop gate summary is derived from `var/formal-benchmarks/latest-safe_stop_gate_v1-run-report.json` and not from stale hardcoded counts or manually maintained README text.
- Ensure internal observability can display recovery visualization and link to:
  - latest recovery review alias
  - review artifact
  - source benchmark report
  - replay report
- Add or tighten focused tests proving safe-stop and recovery summaries remain artifact-driven when alias payload contents change.
- Keep generated evidence artifacts as verification outputs unless the repository already tracks the exact artifact being refreshed.

## 4. Non-Goals

- Do not add new recovery policy or change recovery routing semantics.
- Do not add new benchmark cases, new Mock World profiles, or new suites.
- Do not change action ledger execution behavior except to fix a proven regression.
- Do not add provider integrations or make AMap part of formal benchmark recovery evidence.
- Do not redesign the internal observability UI.
- Do not change public demo contracts, customer UI behavior, or confirmation boundaries.
- Do not commit generated `var/` artifacts unless they are already tracked and intentionally versioned.
- Do not stage unrelated untracked files such as `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, or `docs/superpowers/`.

## 5. Technical Approach

Use the existing recovery review and safe-stop infrastructure rather than creating new mechanisms.

The implementation should first add focused tests around the current artifact-loading and summary paths. If those tests expose stale or hardcoded behavior, make minimal production changes in the existing loaders and serializers. The expected source of truth is the latest generated alias file for each evidence family, not README prose or frontend fixtures.

The recovery review checks should remain additive and reviewer-facing. They should validate the current evidence contract for failed paths: failure reason, recovery attempt, terminal failed status, bounded chain, and zero action count. The internal observability page should continue consuming the existing API shape unless a small additive field is required to expose missing evidence.

## 6. Files Likely to Change

- `tests/test_recovery_replay_review.py`
- `tests/test_benchmark_safe_stop_gate.py`
- `tests/test_system_integrity_summary.py`
- `tests/test_benchmark_internal_summary.py`
- `backend/app/benchmark/recovery_review.py`
- `backend/app/benchmark/safe_stop_gate.py`
- `backend/app/observability/integrity_summary.py`
- `backend/app/observability/service.py`
- `backend/app/observability/schemas.py`
- `frontend/src/observability/types.ts`
- `frontend/src/observability/api.test.ts`
- `frontend/src/observability/ObservabilityPage.test.tsx`
- `frontend/e2e/internal-observability.spec.ts`
- `README.md`
- `docs/WEB_DEMO_README.md`

Production code should change only where focused tests show missing evidence, stale artifact dependency, or incomplete internal visualization/linking.

## 7. Testing Strategy

- Add focused tests proving recovery review output for canonical and suite cases includes failure reason, recovery attempts, terminal status, and zero write action evidence.
- Add focused tests proving `safe_stop_summary` reads the latest safe-stop alias payload and changes when the alias payload changes.
- Keep existing safe-stop gate tests green for all 8 recovery-focused cases.
- Keep existing internal observability tests green, including recovery visualization and replay link rendering.
- Run recovery replay review and safe-stop scripts to refresh local evidence and verify current artifacts are reproducible.
- Run frontend focused tests only if frontend observability files change.

## 8. Risks

- Existing generated artifacts may be old while tests pass against hardcoded summaries; this task must distinguish artifact freshness from manually maintained text.
- Recovery review scripts may require local database/Redis services. If environment services are unavailable, report the blocker explicitly and keep focused unit tests passing.
- Frontend E2E fixtures may hide backend artifact-loading drift. Prefer backend artifact-loader tests as the source of truth and update frontend fixtures only if API output changes.
- The task can easily grow into new recovery behavior. Keep it limited to evidence closure and regression coverage.

## 9. Acceptance Criteria

- [ ] Task `127` spec and plan exist at the expected paths.
- [ ] Recovery-focused suite evidence covers the current 8 recovery-focused cases.
- [ ] Canonical recovery replay review still works for `family_route_failure_v1`.
- [ ] Suite recovery replay review works for `recovery_focused`.
- [ ] Failed recovery paths expose failure reason, recovery attempt, terminal `failed` status, terminal `stop_safely`, and zero write action evidence.
- [ ] Safe-stop summary is loaded from the latest safe-stop alias and is not a hardcoded/manual result.
- [ ] Internal observability recovery visualization links latest alias, review artifact, source report, and replay report.
- [ ] Focused backend tests cover stale/manual artifact regression risk.
- [ ] Existing safe-stop gate and recovery replay tests pass.
- [ ] No unrelated untracked files or generated artifacts are staged.
- [ ] Expected commit message is used.

## 10. Verification Commands

```bash
git status --short
git log --oneline -5
python -m pytest tests/test_recovery_replay_review.py tests/test_benchmark_safe_stop_gate.py tests/test_system_integrity_summary.py tests/test_benchmark_internal_summary.py -q
python scripts/run_benchmark_safe_stop_gate.py
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
python scripts/run_recovery_replay_review.py
git diff --check
git status --short
```

If frontend observability files change, also run:

```bash
npm --prefix frontend run test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run e2e -- internal-observability.spec.ts
```

If integration recovery paths change, also run:

```bash
python -m pytest tests/integration/test_recovery_replay_review.py tests/integration/test_observability_gateway.py -q
```

## 11. Expected Commit

```text
test: consolidate recovery safe-stop evidence
```
