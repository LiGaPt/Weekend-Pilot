# Spec: 068 Richer Web UI V1 Closure

## 1. Goal

Close the remaining V1 release-readiness gap around WeekendPilot's richer Web UI by turning the current customer demo, internal review surface, and benchmark/recovery artifacts into one explicit reviewer-verifiable V1 slice.

The repository already has most of the underlying pieces: customer-side planning and confirmation, internal observability panels, benchmark release artifacts, recovery review closure, clarification/replan/versioning, and customer/internal surface separation. What is still missing is a single V1 UI acceptance boundary that proves the blueprint's richer Web UI is actually present as a product surface, rather than “many related features scattered across pages, scripts, and artifacts.” After this task, a reviewer must be able to follow one checklist and confirm these six capabilities with explicit evidence:

- planning
- confirmation
- execution timeline
- trace summary
- benchmark summary
- recovery visualization

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` places **Richer Web UI with planning, explicit confirmation, execution timeline, trace summaries, benchmark reports, and recovery visualization** inside the V1 target, beyond the earlier MVP minimal Web UI.

This closure task sits across several roadmap milestones in `docs/NEXT_PHASE_ROADMAP.md`:

- `M1. 评测与观测基础设施`
- `M2. 前端分离`
- `M4. 多轮对话与方案版本`
- `M5. 恢复、真实 provider、记忆治理`

The repository is already materially ahead on the underlying building blocks:

- Task `033` added workflow timing and benchmark percentile summaries.
- Task `036` aligned canonical `run_summary` and `benchmark_summary` envelopes.
- Task `041` surfaced benchmark artifact context on the internal review surface.
- Task `042` surfaced recovery-path details on the internal review surface.
- Task `056` hardened customer/internal frontend separation.
- Tasks `058` through `064` closed customer-facing Chinese polish, clarification, replan, selected-plan correctness, happy-path browser coverage, and friends-group demo support.
- Task `065` added the formal `release_gate_v1`.
- Task `067` added the canonical recovery replay review closure flow.

Because those foundations already exist, the highest-value next task is no longer new M1 plumbing or a larger new capability slice. The smallest meaningful gap is a convergence task that makes the richer V1 UI explicit, reviewer-friendly, and testable.

## 3. Requirements

### A. Add one canonical richer-web-ui V1 checklist

- Add `docs/RICHER_WEB_UI_V1_CHECKLIST.md`.
- The checklist must define these exact V1 UI capability buckets:
  - planning
  - confirmation
  - execution timeline
  - trace summary
  - benchmark summary
  - recovery visualization
- For each capability, the checklist must identify:
  - which surface is authoritative (`5173` customer or `5174` internal)
  - which command or action a reviewer must use
  - which visible evidence the reviewer must confirm
- The checklist must explicitly separate:
  - public customer-safe evidence
  - internal reviewer-only evidence
- The checklist must link to the existing benchmark and recovery commands where needed.
- The checklist must not become a generic product spec rewrite or a duplicate of `docs/PROJECT_BLUEPRINT.md`.

### B. Make execution timeline explicit on the customer surface

- The customer surface at `http://127.0.0.1:5173/` must render an explicit execution-timeline section after confirmation/execution data exists.
- The new section title must be reviewer-visible Chinese copy, not an internal/debug label.
- The section must be driven only by existing public execution data already present on `DemoPlanPreview.execution`.
- The section must use `execution.action_results` as the primary data source.
- Timeline entries must be ordered by `execution_order`.
- Each visible entry must include:
  - execution order
  - action/tool label
  - target
  - status
- If `started_at` and `finished_at` are present, the section must show a compact start/finish summary.
- If execution exists but `action_results` is empty, the page must show a neutral empty state instead of failing.
- The existing planning, confirmation, and feedback sections must remain visible and valid.
- This task must not add new public API fields for execution timeline.

### C. Make trace summary explicit on the internal review surface

- The internal surface at `http://127.0.0.1:5174/` must expose one explicit reviewer-facing `Trace Summary` section or heading.
- That trace summary must be built from the existing internal run data already returned by `GET /internal/runs/{run_id}/observability`.
- The trace summary must make these review concepts explicit:
  - run identity
  - trace identity
  - workflow timing
  - observability status
- This task may reorganize or relabel the existing internal panels, but it must not remove the existing run-ID load workflow.
- This task must not add new public fields to the customer page to satisfy trace summary.

### D. Add one narrow benchmark-summary surface for the V1 release gate

- Add one read-only internal endpoint:

  ```text
  GET /internal/benchmarks/release-gate-v1/summary
  ```

- The endpoint must read only the canonical latest release-gate report:

  ```text
  var/formal-benchmarks/latest-release_gate_v1-run-report.json
  ```

- The endpoint must validate and extract the existing `benchmark_summary` contract from that report rather than rebuilding benchmark logic.
- The endpoint must return a compact typed reviewer summary that includes:
  - `schema_version`
  - `suite_id`
  - `suite_title`
  - `run_status`
  - `case_count`
  - `passed_count`
  - `failed_count`
  - `error_count`
  - `overall_score`
  - `matrix_summary.level_counts`
  - `matrix_summary.tool_profile_counts`
  - `matrix_summary.failure_mode_counts`
  - `matrix_summary.tag_counts`
  - `report_path`
- The endpoint must stay narrow to `release_gate_v1`.
- The endpoint must not become:
  - a generic benchmark report browser
  - an arbitrary file-path reader
  - a suite rerun endpoint
  - a benchmark artifact mutation route
- The internal review surface must render one explicit `Benchmark Summary` panel using this endpoint.
- The benchmark summary panel must be visible without first loading a run ID.
- The panel must render a neutral reviewer-readable state when the latest release-gate report is not available locally.
- The panel must not require a running benchmark suite to render its empty state.

### E. Keep recovery visualization explicit and reviewer-facing

- The internal review surface must label the recovery section as reviewer-facing recovery visualization, not as a placeholder or future-work area.
- The existing bounded-recovery data returned by `GET /internal/runs/{run_id}/observability` must remain the source of truth.
- The recovery visualization must continue to show:
  - attempt count
  - max attempts
  - per-attempt action/status/route/error/reason/retry budget
  - replay source when present
- This task must not add replay execution controls or replay report browsing to the UI.

### F. Lock the richer-web-ui V1 slice with tests and docs

- Update `README.md` with one concise `Richer Web UI V1` note that links to the new checklist.
- Update `docs/WEB_DEMO_README.md` so reviewer steps explicitly cover:
  - customer planning and confirmation
  - customer execution timeline after confirmation
  - internal trace summary
  - internal benchmark summary
  - internal recovery visualization
- Update or add focused tests for:
  - customer execution timeline rendering
  - internal trace/benchmark/recovery headings and states
  - internal benchmark-summary endpoint success path
  - internal benchmark-summary endpoint missing-report path
  - browser-level reviewer coverage for the new visible panels
- Existing customer-safe redaction, confirmation boundary, and internal/public separation behavior must remain unchanged.

### G. Keep the task additive and narrow

- Do not change workflow routing, recovery policy, benchmark suite membership, benchmark grading rules, or release-gate pass/fail logic.
- Do not add new benchmark cases, new benchmark suites, or new recovery fixtures.
- Do not redesign the customer page layout beyond the minimum needed to add the execution timeline cleanly.
- Do not add authentication, RBAC, admin-only access control, or a generic internal console framework.
- Do not expose internal IDs, secrets, tokens, raw prompts, raw trace payloads, `action_id`, `tool_event_id`, or `idempotency_key` on the customer page.

## 4. Non-goals

- Do not implement new planning, execution, recovery, or benchmark behavior.
- Do not add a new public API route.
- Do not create a generic benchmark report browser or file explorer.
- Do not merge the customer and internal frontend surfaces back together.
- Do not add benchmark rerun buttons, replay-run buttons, or UI-triggered formal verification.
- Do not change `release_gate_v1` membership, thresholds, or scripts.
- Do not add new dependencies.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` outputs, `frontend/dist/`, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- Existing public customer run payload:
  - `DemoRunSummary`
  - `DemoPlanPreview.execution`
  - `DemoPlanPreview.feedback`
- Existing internal run route:
  - `GET /internal/runs/{run_id}/observability`
- Existing release-gate artifact:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- Existing benchmark summary schema:
  - `BenchmarkRunReport.benchmark_summary`

### Outputs

- New reviewer checklist:
  - `docs/RICHER_WEB_UI_V1_CHECKLIST.md`
- Updated customer page execution-timeline section
- Updated internal review page headings/panels for:
  - `Trace Summary`
  - `Benchmark Summary`
  - `Recovery Visualization`
- New read-only internal benchmark-summary route:
  - `GET /internal/benchmarks/release-gate-v1/summary`

### Schemas

Execution-timeline input excerpt:

```json
{
  "execution": {
    "status": "succeeded",
    "started_at": "2026-05-26T11:00:00+08:00",
    "finished_at": "2026-05-26T11:02:00+08:00",
    "succeeded_count": 2,
    "failed_count": 0,
    "action_results": [
      {
        "action_ref": "draft_1_action_1",
        "execution_order": 1,
        "tool_name": "reserve_restaurant",
        "target_id": "green-table",
        "status": "succeeded"
      }
    ]
  }
}
```

Internal benchmark-summary endpoint response excerpt:

```json
{
  "schema_version": "weekendpilot_internal_benchmark_summary_v1",
  "suite_id": "release_gate_v1",
  "suite_title": "Benchmark release gate v1",
  "run_status": "passed",
  "case_count": 15,
  "passed_count": 15,
  "failed_count": 0,
  "error_count": 0,
  "overall_score": 1.0,
  "matrix_summary": {
    "level_counts": {
      "L1": 3,
      "L2": 8,
      "L3": 4
    },
    "tool_profile_counts": {
      "mock_world": 15
    },
    "failure_mode_counts": {
      "none": 14,
      "route_unavailable": 1
    },
    "tag_counts": {
      "memory_override": 1,
      "memory_advisory": 1,
      "memory_expired": 1,
      "memory_governance": 2
    }
  },
  "report_path": "var/formal-benchmarks/latest-release_gate_v1-run-report.json"
}
```

## 6. Observability

This task does not add a new telemetry backend or new benchmark-generation logic.

It reuses and surfaces existing evidence:

- public demo execution summaries already persisted into plan JSON
- `GET /internal/runs/{run_id}/observability`
- `agent_runs.metadata_json["summary"]`
- `agent_runs.metadata_json["benchmark"]["artifact_summary"]`
- `agent_runs.metadata_json["workflow"]["recovery"]`
- `var/formal-benchmarks/latest-release_gate_v1-run-report.json`

The new internal benchmark-summary endpoint is a read-only reviewer endpoint over existing local benchmark evidence. It must not mutate reports, rerun suites, or add new persisted metadata.

## 7. Failure Handling

- If the latest release-gate report is missing, the internal benchmark-summary endpoint must return a reviewer-readable missing-state error rather than a generic server failure.
- If the latest release-gate report exists but is malformed, the endpoint must fail clearly and must not fabricate summary values.
- If the customer run contains execution metadata but no `action_results`, the execution-timeline section must render a neutral empty state.
- If the customer run has no execution metadata yet, the execution-timeline section must not render.
- If the internal run has no benchmark or recovery metadata, the existing neutral states must remain intact.
- If the benchmark-summary endpoint is unavailable, the internal page must keep the run-ID observability flow usable.
- This task must not degrade the existing internal observability route when benchmark-summary loading fails.

## 8. Acceptance Criteria

- [ ] `docs/RICHER_WEB_UI_V1_CHECKLIST.md` exists.
- [ ] The checklist explicitly maps planning, confirmation, execution timeline, trace summary, benchmark summary, and recovery visualization to concrete reviewer-visible evidence.
- [ ] The customer page renders an explicit execution-timeline section after execution data exists.
- [ ] The execution-timeline section is ordered by `execution_order`.
- [ ] The execution-timeline section uses only existing public execution data and does not expose internal IDs or raw payloads.
- [ ] The customer page still preserves the existing planning and confirmation boundary behavior.
- [ ] The internal review page renders an explicit `Trace Summary` reviewer heading or section.
- [ ] The internal review page renders an explicit `Benchmark Summary` panel fed by the latest `release_gate_v1` report.
- [ ] The new internal benchmark-summary endpoint returns the current `release_gate_v1` summary when the latest report exists.
- [ ] The benchmark-summary panel shows a neutral state when the latest report is unavailable.
- [ ] The internal review page renders an explicit recovery-visualization heading/section while keeping the existing bounded-recovery details.
- [ ] Existing public demo API shapes remain unchanged.
- [ ] Existing internal run observability API shapes remain backward compatible.
- [ ] No benchmark suite logic, release-gate thresholds, workflow routing, or recovery behavior changes in this task.
- [ ] Focused frontend unit tests pass.
- [ ] Focused backend unit and integration tests pass.
- [ ] Focused browser E2E checks pass.
- [ ] `python scripts/run_benchmark_release_gate.py` still passes and refreshes the latest release-gate artifact used by the benchmark-summary panel.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, `frontend/dist/`, or unrelated local file is staged by this task.
- [ ] The post-commit working tree contains no newly introduced unrelated changes beyond the pre-existing local files outside this task.

## 9. Verification Commands

```bash
npm --prefix frontend run test -- --run src/App.test.tsx src/observability/ObservabilityPage.test.tsx
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/test_observability.py tests/test_benchmark_release_gate.py tests/test_benchmark_internal_summary.py tests/integration/test_demo_api_gateway.py tests/integration/test_observability_gateway.py -q
python scripts/run_benchmark_release_gate.py
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "starts a run|Chinese reviewer prompt|internal observability surface"
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: close richer web ui v1 surface
```

## 11. Notes for the Implementer

This is a convergence task, not a new-capability task.

Important repository facts already established before this task:

- numbered `docs/specs` and `docs/plans` are continuous and matching through `067`
- latest task baseline is `067`
- latest commit `ec8cca8 feat: add recovery replay review closure` matches that task
- focused customer/internal frontend unit tests currently pass
- `main` does not yet contain the `058-067` stack, so implementation must use the current `067`-containing baseline or the first merged equivalent baseline, not stale main

Keep the benchmark-summary scope narrow to the canonical V1 blocking suite. If the implementation starts drifting toward a generic benchmark browser, replay UI, or dashboard framework, stop and narrow it back to this release-closure slice.
