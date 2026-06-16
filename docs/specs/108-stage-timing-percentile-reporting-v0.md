# Spec: 108 Stage timing percentile reporting v0

## 1. Goal

This task hardens the existing stage-timing and percentile-reporting infrastructure by making suite-level timing summaries stably consumable through the internal latest benchmark summary path and minimally visible in the reviewer-facing observability surface.

The repository already computes and persists `workflow_timing_summary` and `benchmark_timing_summary` for workflow-backed benchmark runs. However, the current reviewer-facing `GET /internal/benchmarks/release-gate-v1/summary` contract strips out the suite timing payload, and the `5174` `Benchmark Summary` panel only shows score/count rollups. After this task, the internal latest release-gate summary should expose additive timing summary fields, degrade safely when timing data is missing or malformed, and the reviewer UI should show overall timing percentiles plus per-stage percentile rows without changing workflow behavior or benchmark thresholds.

## 2. Project Context

This task belongs to milestone `M1. 评测与观测基础设施` in `docs/NEXT_PHASE_ROADMAP.md`.

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. That milestone’s goal is to turn “the workflow runs” into “the workflow can be measured and compared.” Tasks `033`, `036`, and `071` already established:

- workflow-stage timing capture
- suite-level percentile summaries
- run / trace / benchmark summary alignment
- release-gate latency SLO evaluation based on benchmark timing summaries

The remaining practical gap is not timing generation. The remaining gap is stable internal consumption. The latest release-gate summary API and its reviewer surface do not yet expose the suite timing summary that already exists in the suite run report artifact. This task closes that narrow gap without changing workflow routing, benchmark suites, or gate logic.

## 3. Requirements

- Treat existing benchmark suite run reports as the source of truth for suite-level timing summaries.
- Keep the existing `workflow_timing_summary` and `benchmark_timing_summary` schemas unchanged.
- Extend the internal latest release-gate summary response contract additively with:
  - `benchmark_timing_summary_present`
  - `benchmark_timing_summary`
- `benchmark_timing_summary_present` must be `true` only when a valid suite timing summary was successfully loaded.
- `benchmark_timing_summary` must reuse the existing suite timing summary shape already produced by benchmark reports.
- The internal latest release-gate summary loader must prefer `benchmark_summary.benchmark_timing_summary` when present and valid.
- If `benchmark_summary.benchmark_timing_summary` is missing, the loader may fall back to top-level `benchmark_timing_summary` from the suite report if it is present and valid.
- If timing summary data is missing or malformed, the latest release-gate summary endpoint must still succeed as long as the non-timing benchmark summary contract remains valid.
- In the missing or malformed timing case:
  - `benchmark_timing_summary_present` must be `false`
  - `benchmark_timing_summary` must be `null`
- The `GET /internal/benchmarks/release-gate-v1/summary` endpoint must return the new additive timing fields.
- The frontend `Benchmark Summary` panel on `5174` must render a compact timing section when `benchmark_timing_summary_present` is `true` and `benchmark_timing_summary` is not `null`.
- That timing section must display:
  - overall total-duration `p50`, `p95`, `p99`, and `max`
  - per-stage percentile rows from the suite timing summary
  - `sample_count` and `retry_case_count` for each stage row
- The panel must preserve existing matrix/count/score content.
- If suite timing summary is unavailable, the panel must render a neutral reviewer-facing fallback message instead of an error.
- Existing case-level internal observability responses must continue to expose `workflow_timing_summary` unchanged.
- Existing release-gate, benchmark harness, replay, and system-integrity contracts must remain backward compatible through additive changes only.
- Update active reviewer-facing documentation to mention that `Benchmark Summary` now exposes suite timing percentiles and stage timing distribution.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not change workflow routing, node timing instrumentation, retry budgets, or confirmation behavior.
- Do not change benchmark suite membership, grading logic, latency SLO thresholds, or release-blocking logic.
- Do not add new benchmark cases, new benchmark suites, or new benchmark report artifact formats.
- Do not add a new API endpoint or redesign the internal observability layout.
- Do not expose raw trace events, prompts, secrets, or unsanitized benchmark artifact data.
- Do not add large reviewer dashboard features beyond the minimal benchmark timing section.

## 5. Interfaces and Contracts

Define the interfaces this task introduces or depends on.

### Inputs

- Existing suite run report JSON loaded from the latest release-gate alias:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- Existing internal latest summary route:
  - `GET /internal/benchmarks/release-gate-v1/summary`
- Existing frontend reviewer page:
  - `frontend/src/observability/ObservabilityPage.tsx`
- Existing case-level observability route:
  - `GET /internal/runs/{run_id}/observability`

### Outputs

- Additive fields on the internal latest release-gate summary API response:
  - `benchmark_timing_summary_present: bool`
  - `benchmark_timing_summary: BenchmarkTimingSummary | null`
- Minimal timing display in the reviewer `Benchmark Summary` panel.
- Updated reviewer-facing documentation describing the timing section.

### Schemas

Updated internal latest release-gate summary response shape:

```json
{
  "schema_version": "weekendpilot_internal_benchmark_summary_v1",
  "suite_id": "release_gate_v1",
  "suite_title": "Release Gate v1",
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
      "family": 10
    }
  },
  "benchmark_timing_summary_present": true,
  "benchmark_timing_summary": {
    "schema_version": "benchmark_timing_summary_v1",
    "case_count": 15,
    "overall_total_duration_ms": {
      "sample_count": 15,
      "min_ms": 320,
      "p50_ms": 390,
      "p95_ms": 424,
      "p99_ms": 424,
      "max_ms": 424,
      "mean_ms": 387.8
    },
    "stages": [
      {
        "node_name": "pre_flight_check_availability",
        "sample_count": 15,
        "retry_case_count": 0,
        "min_ms": 12,
        "p50_ms": 20,
        "p95_ms": 36,
        "p99_ms": 36,
        "max_ms": 36,
        "mean_ms": 19.6
      }
    ]
  },
  "report_path": "var/formal-benchmarks/latest-release_gate_v1-run-report.json"
}
```

Degraded response shape when timing is unavailable:

```json
{
  "schema_version": "weekendpilot_internal_benchmark_summary_v1",
  "suite_id": "release_gate_v1",
  "suite_title": "Release Gate v1",
  "run_status": "passed",
  "case_count": 15,
  "passed_count": 15,
  "failed_count": 0,
  "error_count": 0,
  "overall_score": 1.0,
  "matrix_summary": {
    "level_counts": {},
    "tool_profile_counts": {},
    "failure_mode_counts": {},
    "tag_counts": {}
  },
  "benchmark_timing_summary_present": false,
  "benchmark_timing_summary": null,
  "report_path": "var/formal-benchmarks/latest-release_gate_v1-run-report.json"
}
```

## 6. Observability

This task does not add new runtime observability generation.

It only promotes already-generated benchmark timing summaries into a stable internal summary contract and reviewer-facing UI. The task must continue to use sanitized benchmark report data only. It must not expose:

- raw trace events
- prompts
- secrets
- tokens
- authorization headers
- debug-only payloads
- wall-clock timestamps beyond what current internal contracts already allow

## 7. Failure Handling

- If the latest release-gate report file is missing, the existing `404` behavior must remain unchanged.
- If the latest release-gate report is unreadable or non-JSON, the existing invalid-report error behavior must remain unchanged.
- If the report’s core benchmark summary fields are invalid, the existing invalid-report error behavior must remain unchanged.
- If only the timing summary field is missing, the summary endpoint must still succeed with:
  - `benchmark_timing_summary_present = false`
  - `benchmark_timing_summary = null`
- If the timing summary field exists but is malformed, the summary endpoint must still succeed with the same degraded timing response.
- The frontend must not show a hard error solely because timing summary is unavailable.
- Existing case-level `workflow_timing_summary` rendering must remain unchanged and must not depend on the latest release-gate summary call succeeding.

## 8. Acceptance Criteria

- [ ] `docs/specs/108-stage-timing-percentile-reporting-v0.md` exists and matches this task.
- [ ] The internal latest release-gate summary response includes additive `benchmark_timing_summary_present` and `benchmark_timing_summary` fields.
- [ ] When the suite report contains a valid timing summary, the response returns `benchmark_timing_summary_present = true` and exposes the timing payload.
- [ ] When the suite report timing summary is missing, the response still succeeds and returns `benchmark_timing_summary_present = false`.
- [ ] When the suite report timing summary is malformed, the response still succeeds and returns `benchmark_timing_summary_present = false`.
- [ ] The `5174` `Benchmark Summary` panel renders overall `p50 / p95 / p99 / max` and a per-stage percentile table when timing summary is present.
- [ ] The `5174` `Benchmark Summary` panel renders a neutral fallback message instead of failing when timing summary is unavailable.
- [ ] Existing matrix/count/score content in `Benchmark Summary` remains visible.
- [ ] Existing case-level internal observability responses still expose `workflow_timing_summary`.
- [ ] No workflow behavior changed.
- [ ] No benchmark suite membership changed.
- [ ] No release-gate thresholds or scoring semantics changed.
- [ ] No new API endpoint was added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The focused backend and frontend verification commands listed below pass, or any blocker is reported clearly.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_internal_summary.py tests/integration/test_observability_gateway.py -q
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -q
npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: harden stage timing percentile reporting
```

## 11. Notes for the Implementer

This is a hardening and surface-alignment task, not a timing-instrumentation task.

The safest sequence is:

1. reuse the existing suite timing summary contract as-is
2. extend the internal latest summary model additively
3. degrade gracefully when timing summary is absent or malformed
4. add one minimal reviewer-facing timing section in the existing `Benchmark Summary` panel
5. keep case-level observability timing behavior unchanged

Stop and report back if the latest release-gate artifact no longer contains `benchmark_summary` in the shape assumed by the current internal summary loader, because that would indicate a larger contract regression than this task is scoped to fix.
