# Spec: 057 AMap Preview Diagnostics and Benchmark Guardrails v0

## 1. Goal

Harden the operational boundary of the already-landed AMap read-only preview path so that it is diagnosable in internal observability and cannot silently leak into canonical Mock World benchmark flows.

Task `054` made the AMap path reachable as an explicit read-only preview. That solved path selection, preview planning, and confirmation blocking. It did not yet make the path a stable V1 endpoint from an engineering perspective: internal review still lacks a preview-specific diagnostic summary, and canonical benchmark fixtures and suite summaries still rely on convention instead of explicit provider guardrails. After this task, AMap preview runs must carry a compact, reviewable diagnostics block, and canonical benchmark loading/reporting must fail fast or report explicitly if any non-Mock-World provider ever appears.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` requires three things that are directly relevant here:

- Mock World must remain available even when real provider integration is added.
- Observability must keep failures traceable without breaking the main product flow.
- LocalLife-Bench is a core product engineering surface, not optional test scaffolding.

`docs/NEXT_PHASE_ROADMAP.md` places real-provider gradual rollout under milestone `M5. 恢复、真实 provider、记忆治理`, while also making observability-first engineering a standing principle from `M1. 评测与观测基础设施`. This task is therefore an `M5` convergence slice that deliberately builds on the repository's existing `M1` observability base.

Repository history matters here:

- Task `054` added the switchable AMap read-only preview path.
- Task `056` hardened customer/internal frontend separation, so internal observability is now the correct place to expose preview diagnostics.
- Canonical benchmark suites, benchmark fixtures, and benchmark defaults still assume Mock World by policy, but that policy is not yet enforced and reported as tightly as it should be.

This task does not introduce new product capability. It closes an operational gap around an already-exposed path.

## 3. Requirements

### A. Public demo behavior must stay stable

- Keep `DemoStartRunRequest.read_profile` unchanged.
- Keep `DemoRunSummary.read_profile` unchanged.
- Keep the AMAP confirmation rejection behavior unchanged.
- Keep the exact public confirmation rejection message unchanged:
  - `AMAP read-only demo runs cannot be confirmed.`
- Keep the existing safe public configuration error message unchanged:
  - `AMAP read path is not configured for this environment.`
- Do not add new public demo response fields in this task.

### B. Canonical run summary must carry preview diagnostics for AMap runs

- Extend the canonical observability run summary model with a new optional field:
  - `preview_diagnostics`
- `preview_diagnostics` must be `null` for non-preview Mock World runs.
- For runs with `tool_profile="amap"`, `preview_diagnostics` must be present and must use this exact schema contract:
  - `schema_version = "weekendpilot_preview_diagnostics_v1"`
  - `read_profile = "amap"`
  - `mode = "read_only_preview"`
  - `confirmation_allowed = false`
  - `confirmation_block_reason = "AMAP read-only demo runs cannot be confirmed."`
  - `benchmark_eligible = false`
  - `benchmark_block_reason = "Canonical benchmark suites support Mock World only."`
  - `observed_provider_names = <sorted unique provider names from tool events>`
  - `provider_event_count = <count of tool events where provider == "amap">`
  - `write_tool_event_count = <count of tool events where tool_type == "write">`
  - `provider_error_types = <sorted unique sanitized error type/code values from AMAP tool-event errors>`
  - `cross_provider_fallback_detected = true` when any observed provider name is not `"amap"`, otherwise `false`
- For the current preview path, successful integration tests must show:
  - `observed_provider_names == ["amap"]`
  - `write_tool_event_count == 0`
  - `cross_provider_fallback_detected == false`

### C. Internal observability must expose preview diagnostics directly

- Extend the internal observability response model with:
  - `preview_diagnostics`
- `GET /internal/runs/{run_id}/observability` must return the same preview diagnostics block for AMap runs that is stored in the canonical run summary.
- If the stored canonical summary is missing or malformed for `preview_diagnostics`, the internal observability service must recompute the block from the run row and tool-event rows instead of failing the route.
- Mock World runs must continue to return `preview_diagnostics = null`.

### D. Canonical benchmark fixtures and suite loading must reject non-Mock-World providers early

- Canonical registered benchmark fixtures loaded through `load_benchmark_case(...)` and `load_registered_benchmark_cases()` must reject any registered case whose `tool_profile != "mock_world"`.
- The rejection must raise `BenchmarkHarnessError` with this exact message format:
  - `Canonical benchmark case must use tool_profile='mock_world': <case_id> -> <tool_profile>`
- `load_benchmark_suite(...)` and `list_benchmark_suites()` must fail fast through the same validation path.
- This validation must happen before benchmark harness execution begins.
- Do not silently coerce or downgrade non-Mock-World canonical benchmark cases.

### E. Benchmark harness must keep a defensive runtime guardrail

- `BenchmarkHarness.run_case(...)` must defensively reject ad hoc non-canonical cases whose `tool_profile != "mock_world"`, even if they were constructed in memory and bypassed fixture loading.
- That guardrail must return a deterministic `BenchmarkCaseResult(status="error")` instead of raising.
- The returned failure reason list must contain exactly one item:
  - `Unsupported benchmark tool_profile: <tool_profile>`
- The harness must reject the case before calling `DemoWorkflowService.start_run(...)`.
- The harness must not create a run row, write benchmark metadata, or write action/tool events for that rejected ad hoc case.

### F. Benchmark matrix and suite/report outputs must make provider policy auditable

- Extend `BenchmarkCaseMatrixSummary` with:
  - `tool_profile_counts: dict[str, int]`
- `build_case_matrix_summary(...)` must populate `tool_profile_counts` from the supplied cases.
- `list_benchmark_suites()` must surface `tool_profile_counts` inside every suite description's `matrix_summary`.
- `BenchmarkSummary.matrix_summary` in suite run reports must include `tool_profile_counts`.
- For all current canonical repository suites, `tool_profile_counts` must contain only Mock World entries.
- Focused tests must verify:
  - `default` suite reports `{"mock_world": 10}`
  - `all_registered` suite reports only `mock_world` entries

### G. Documentation must state the boundary explicitly

- Update `README.md` so the AMap preview section explains that internal observability now exposes preview diagnostics for local review.
- Update `README.md` so the benchmark section explicitly states that canonical benchmark fixtures and suites remain Mock World only and reject AMap provider cases by design in this v0 task.

## 4. Non-goals

- Do not implement AMap write execution.
- Do not change the public demo API request or response shape beyond existing behavior.
- Do not add provider fallback from AMap to Mock World.
- Do not add live-provider benchmark cases, live-provider benchmark suites, or benchmark harness support for non-Mock-World providers.
- Do not add or redesign frontend UI surfaces.
- Do not widen this task into recovery-routing changes, replay changes, or new observability endpoints.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Inputs

- Workflow-backed demo runs that already use:
  - `tool_profile="amap"`
  - `world_profile="amap_shanghai_live"`
- Internal observability requests:
  - `GET /internal/runs/{run_id}/observability`
- Canonical benchmark fixture loading via:
  - `load_benchmark_case(case_id)`
  - `load_registered_benchmark_cases()`
  - `load_benchmark_suite(suite_id)`
  - `list_benchmark_suites()`
- Ad hoc benchmark execution via:
  - `BenchmarkHarness.run_case(case)`

### Outputs

- Canonical stored run summary gains:
  - `preview_diagnostics`
- Internal observability response gains:
  - `preview_diagnostics`
- Benchmark matrix summaries gain:
  - `tool_profile_counts`
- Canonical benchmark fixture and suite validation may raise:
  - `BenchmarkHarnessError`
- Ad hoc non-Mock-World benchmark execution returns:
  - `BenchmarkCaseResult(status="error")` with deterministic failure reason

### Schemas

AMap preview diagnostics example:

```json
{
  "schema_version": "weekendpilot_preview_diagnostics_v1",
  "read_profile": "amap",
  "mode": "read_only_preview",
  "confirmation_allowed": false,
  "confirmation_block_reason": "AMAP read-only demo runs cannot be confirmed.",
  "benchmark_eligible": false,
  "benchmark_block_reason": "Canonical benchmark suites support Mock World only.",
  "observed_provider_names": ["amap"],
  "provider_event_count": 3,
  "write_tool_event_count": 0,
  "provider_error_types": [],
  "cross_provider_fallback_detected": false
}
```

Benchmark matrix summary example:

```json
{
  "schema_version": "weekendpilot_benchmark_case_matrix_v1",
  "case_count": 10,
  "scenario_bucket_counts": {
    "family": 5,
    "solo": 1,
    "couple": 1,
    "friends": 1,
    "unknown": 0
  },
  "level_counts": {
    "L1": 2,
    "L2": 8
  },
  "tool_profile_counts": {
    "mock_world": 10
  },
  "world_profile_counts": {
    "family_afternoon": 5,
    "solo_afternoon": 1,
    "couple_afternoon": 1,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "budget_lite": 1
  },
  "failure_mode_counts": {
    "none": 10
  },
  "tag_counts": {
    "child_friendly": 5
  }
}
```

Canonical benchmark fixture validation error example:

```json
{
  "error_type": "BenchmarkHarnessError",
  "message": "Canonical benchmark case must use tool_profile='mock_world': family_afternoon_v1 -> amap"
}
```

Ad hoc benchmark guardrail result example:

```json
{
  "case_id": "ad_hoc_preview_case",
  "status": "error",
  "failure_reasons": ["Unsupported benchmark tool_profile: amap"]
}
```

## 6. Observability

- Store `preview_diagnostics` inside the canonical persisted run summary under `metadata_json["summary"]`.
- Expose `preview_diagnostics` from the internal observability route for AMap preview runs.
- Keep using existing `tool_events.provider`, `tool_events.tool_type`, and sanitized `tool_events.error_json` as the data source for diagnostic aggregation.
- `provider_error_types` must be derived from sanitized error metadata only. It must not expose secrets, raw tokens, or raw upstream payloads.
- Do not add new LangSmith requirements in this task.
- Do not add a new public endpoint in this task.

## 7. Failure Handling

- If stored `preview_diagnostics` data is malformed, internal observability must recompute it from run/tool-event data instead of failing the request.
- If an AMAP tool event has malformed or missing `error_json`, ignore that event for `provider_error_types` aggregation instead of failing summary generation.
- If a canonical benchmark fixture is registered with `tool_profile != "mock_world"`, fail fast with `BenchmarkHarnessError` before suite listing or harness execution.
- If an ad hoc benchmark case is passed directly to `BenchmarkHarness.run_case(...)` with `tool_profile != "mock_world"`, return a deterministic error result and do not create run state.
- If this task encounters pressure to redesign public error payloads for no-run startup failures, stop and narrow scope. That redesign is outside this task.

## 8. Acceptance Criteria

- [ ] `docs/specs/057-amap-preview-diagnostics-and-benchmark-guardrails-v0.md` exists and matches this task.
- [ ] `docs/plans/057-amap-preview-diagnostics-and-benchmark-guardrails-v0-plan.md` exists and matches this task.
- [ ] Public AMap preview start behavior remains unchanged.
- [ ] Public AMap confirmation rejection remains unchanged and still returns `AMAP read-only demo runs cannot be confirmed.`
- [ ] Successful AMap preview runs store `preview_diagnostics` in the canonical run summary with schema version `weekendpilot_preview_diagnostics_v1`.
- [ ] Internal observability returns non-null `preview_diagnostics` for AMap preview runs and `null` for Mock World runs.
- [ ] Successful AMap preview integration coverage proves:
  - `observed_provider_names == ["amap"]`
  - `write_tool_event_count == 0`
  - `cross_provider_fallback_detected == false`
- [ ] A failing AMap tool-event path can aggregate sanitized `provider_error_types` without exposing secrets.
- [ ] Canonical registered benchmark cases with `tool_profile != "mock_world"` are rejected during fixture/suite loading with the exact `Canonical benchmark case must use tool_profile='mock_world': <case_id> -> <tool_profile>` message format.
- [ ] `BenchmarkHarness.run_case(...)` rejects ad hoc non-Mock-World cases before calling the demo service and returns `failure_reasons == ["Unsupported benchmark tool_profile: <tool_profile>"]`.
- [ ] Benchmark matrix summaries and suite reports include `tool_profile_counts`.
- [ ] Current canonical suites still report only Mock World tool-profile counts.
- [ ] `README.md` documents both the preview diagnostics path and the mock-world-only benchmark guardrail.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -q
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/integration/test_benchmark_harness_gateway.py -q
git status --short
```

## 10. Expected Commit

```text
feat: add amap preview diagnostics and benchmark guardrails
```

## 11. Notes for the Implementer

- Preferred execution baseline is a fresh task branch from updated `main` after Task `056` lands.
- Keep the public demo contract stable. This task is intentionally internal-observability-heavy and benchmark-guardrail-heavy.
- Reuse existing sanitization helpers for error aggregation. Do not create a second redaction policy.
- Use existing tool-event data rather than inventing new persistence tables.
- Stop and report back if implementation starts requiring benchmark-provider support, public error-schema redesign, or frontend UI work. Those are out of scope for this convergence task.
