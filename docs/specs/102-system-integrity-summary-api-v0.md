# Spec: 102 System Integrity Summary API v0

## 1. Goal

Add one internal-only backend summary API that aggregates the repository's current V2 integrity evidence into a single stable response contract.

WeekendPilot already exposes several separate internal and artifact-level evidence surfaces:

- latest `release_gate_v1` summary
- latest `v2_integrity_gate` suite report and coverage evaluation
- latest `v2_integrity` pass-k stability report
- latest `all_registered` formal verification report
- latest canonical recovery replay review
- per-run internal observability summaries with benchmark and recovery sub-blocks
- memory-policy audit summaries embedded inside workflow and benchmark metadata

The current gap is not missing evidence generation. The gap is that reviewers and later internal UI work still have to stitch multiple files and contracts together manually. After this task, the backend must provide one internal summary endpoint that reads the existing latest aliases, derives a compact system-integrity view, and returns a sanitized, reviewer-oriented response without changing benchmark logic, replay logic, or frontend behavior.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

It directly continues the current repository sequence after Task `101` and fits the roadmap guidance to strengthen measurable, comparable, and reviewable internal evidence before expanding frontend surfaces further. It also provides the backend contract required for the next likely task, `103-system-integrity-panel-v0`, so the internal 5174 page can consume one summary API instead of re-implementing artifact stitching in the frontend.

This task fits these `docs/PROJECT_BLUEPRINT.md` architecture areas:

- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- failure handling and recovery auditability
- memory-governance auditability
- small, reviewable tasks

Relevant current repository facts:

- `docs/specs/` and `docs/plans/` are continuous and slug-matched through Task `101`.
- The latest commit is `bc92eff test: align coverage gate integration expectations`.
- The current branch is `codex/101-benchmark-coverage-gate-convergence-v0`.
- Existing internal routes already expose:
  - `GET /internal/benchmarks/release-gate-v1/summary`
  - `GET /internal/runs/{run_id}/observability`
- Existing artifact writers already publish latest aliases for:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `all_registered`
  - `v2_integrity` stability pass-k
  - canonical recovery replay review
- Existing benchmark and recovery code already computes the source data needed for:
  - benchmark gate status
  - pass-k stability metrics
  - memory-governance counts and per-case score outcomes
  - recovery replay status
  - benchmark timing summaries
  - evidence file paths

## 3. Requirements

- Add one new internal-only API route at:

  ```text
  GET /internal/system/integrity-summary
  ```

- The route must return a dedicated, typed response model distinct from:
  - `ReleaseGateBenchmarkSummary`
  - `InternalObservabilityRunSummary`

- The route must not trigger benchmark execution, recovery replay execution, or any artifact refresh.
- The route must be read-only and derive its response only from:
  - existing latest alias files under `var/`
  - existing benchmark report schemas
  - existing recovery review schemas
  - existing memory-policy audit schema contracts
  - existing redaction rules already enforced in backend observability/reporting code

- The route must aggregate these sections in one response:
  - benchmark gate summary
  - stability summary
  - memory-governance summary
  - recovery replay summary
  - timing summary
  - redaction summary
  - evidence paths

### A. Benchmark gate summary

- The benchmark section must read the latest `v2_integrity_gate` alias.
- It must validate the payload through the existing benchmark report schema.
- It must extract and expose at minimum:
  - `suite_id`
  - `gate_id`
  - `run_status`
  - `release_blocked`
  - `case_count`
  - `passed_count`
  - `failed_count`
  - `error_count`
  - `overall_score`
  - `blocking_failures`
  - `integrity_coverage_summary`
  - `memory_mode_counts`
  - `conversation_mode_counts`
  - `failure_mode_counts`
  - canonical latest alias path

- The route must not recompute V2 gate thresholds independently from scratch if the enriched gate payload already contains them.

### B. Stability summary

- The stability section must read the latest `v2_integrity` pass-k alias.
- It must validate the payload through the existing `BenchmarkStabilityPassKReport` schema.
- It must expose at minimum:
  - `suite_id`
  - `gate_id`
  - `metric_version`
  - `requested_run_count`
  - `executed_run_count`
  - `window_size`
  - `window_count`
  - `discarded_tail_run_count`
  - `success_count`
  - `failure_count`
  - `error_count`
  - `success_at_1`
  - `pass_at_4`
  - `pass_pow_4`
  - canonical latest alias path

- The API may include additive reviewer-friendly derived booleans such as:
  - `stable_enough`
  - `has_required_window`

### C. Memory-governance summary

- The memory-governance section must read the latest `all_registered` alias.
- It must validate the payload through the existing benchmark report schema.
- It must derive a compact summary from case results and summary metadata instead of introducing a second memory-grading algorithm.
- A case counts as a memory-governance case when its case-result scores include `name == "memory_governance"`.
- The memory-governance section must expose at minimum:
  - `source_suite_id`
  - `memory_case_count`
  - `passed_case_count`
  - `failed_case_count`
  - `error_case_count`
  - `all_memory_cases_passed`
  - `case_ids`
  - `failing_case_ids`
  - canonical latest alias path

- The section may expose additive aggregate signals derived from score details when available, but it must not depend on raw workflow metadata from individual runs.

### D. Recovery replay summary

- The recovery-replay section must read the canonical latest alias:
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`

- It must validate the payload through the existing `RecoveryReplayReviewResult` schema.
- It must expose at minimum:
  - `case_id`
  - `status`
  - `check_count`
  - `passed_check_count`
  - `failed_check_count`
  - `latest_review_path`
  - `source_report_path`
  - `replay_report_path`
  - `recovery_actions`
  - `attempt_count`
  - `max_attempts`

- The route must not require the generic suite run report from Task `099` to exist for the canonical summary flow.

### E. Timing summary

- The response must include one timing section derived from already-available benchmark artifacts.
- The timing section must expose:
  - latest `v2_integrity_gate` benchmark timing summary when present
  - latest stability run window size and executed-run count
  - whether timing data is fully available, partially available, or missing

- The task must not add new timing instrumentation or new persisted timing metadata.

### F. Redaction summary

- The response must include one compact redaction/contract section that states the intended sanitization posture of this internal summary API.
- The redaction section must be deterministic and must expose at minimum:
  - `internal_only`
  - `sanitized`
  - `relative_evidence_paths_only`
  - `forbidden_key_markers`

- `forbidden_key_markers` must include the existing backend-sensitive markers relevant to this summary surface, such as:
  - `api_key`
  - `token`
  - `secret`
  - `authorization`
  - `prompt`
  - `debug_trace`
  - `action_id`
  - `tool_event_id`
  - `idempotency_key`

- The API must not expose raw prompts, tokens, secrets, stack traces, tracebacks, provider payload bodies, or raw debug blobs.

### G. Evidence paths

- The response must include the canonical evidence paths it used or expected.
- The evidence-paths list must cover at minimum:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `formal_verification_all_registered`
  - `v2_integrity_passk`
  - `recovery_review_family_route_failure_v1`

- Each evidence-path entry must include:
  - `evidence_id`
  - `path`
  - `exists`
  - `required_for_summary`
  - `status`

- Paths must be returned as repository-relative strings, not absolute machine-local paths.

### H. Partial availability and degradation

- The route must support partial summary responses.
- Missing or invalid optional sections must not automatically cause the whole response to fail.
- The route must return a top-level summary status such as:
  - `ready`
  - `degraded`
  - `missing_evidence`
  - `invalid_evidence`

- The top-level status must be derived from section-level statuses.
- If one source artifact is missing or invalid, the response must still return `200` with:
  - section status
  - clear missing/invalid reason
  - empty or null section payload where appropriate

- Only unexpected, non-contract exceptions should return `500`.

### I. Compatibility and scope constraints

- Keep existing routes unchanged:
  - `GET /internal/benchmarks/release-gate-v1/summary`
  - `GET /internal/runs/{run_id}/observability`

- Do not change:
  - benchmark suite membership
  - gate thresholds
  - stability metric formulas
  - memory-governance grading
  - recovery replay review checks
  - public demo API contracts
  - frontend behavior

## 4. Non-goals

- Do not build the 5174 System Integrity panel UI in this task.
- Do not add any customer-facing route or customer-facing payload field.
- Do not refresh, rewrite, or commit artifacts under `var/`.
- Do not add new benchmark cases, suites, gates, or replay modes.
- Do not redesign redaction infrastructure.
- Do not centralize all evidence-path logic across scripts and backend if that requires widening scope into Task `104`.
- Do not add database tables, Alembic migrations, Redis channels, or new package dependencies.
- Do not change `show_submission_evidence.py` output in this task unless strictly required for shared constants and kept backward compatible.
- Do not commit `.env`, API keys, tokens, secrets, or generated runtime artifacts.

## 5. Interfaces and Contracts

### Inputs

This task depends on existing code and artifacts:

- `BenchmarkRunReport`
- `BenchmarkStabilityPassKReport`
- `RecoveryReplayReviewResult`
- `MemoryPolicyAuditSummary`
- latest alias files under:
  - `var/formal-benchmarks/`
  - `var/formal-benchmarks/stability/`
  - `var/recovery-reviews/`

New backend input route:

```text
GET /internal/system/integrity-summary
```

This route requires no request body and no query parameters in v0.

### Outputs

New backend output:

```text
GET /internal/system/integrity-summary
```

The response must be a typed internal summary contract.

### Schemas

Representative response shape:

```json
{
  "schema_version": "weekendpilot_system_integrity_summary_v1",
  "status": "ready",
  "benchmark_summary": {
    "status": "ready",
    "suite_id": "v2_integrity",
    "gate_id": "v2_integrity_gate",
    "run_status": "passed",
    "release_blocked": false,
    "case_count": 18,
    "passed_count": 18,
    "failed_count": 0,
    "error_count": 0,
    "overall_score": 1.0,
    "blocking_failures": [],
    "latest_report_path": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json"
  },
  "stability_summary": {
    "status": "ready",
    "suite_id": "v2_integrity",
    "metric_version": "passk_v0",
    "executed_run_count": 4,
    "success_at_1": 1.0,
    "pass_at_4": 1.0,
    "pass_pow_4": 1.0,
    "latest_report_path": "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json"
  },
  "memory_governance_summary": {
    "status": "ready",
    "source_suite_id": "all_registered",
    "memory_case_count": 6,
    "passed_case_count": 6,
    "failed_case_count": 0,
    "error_case_count": 0,
    "all_memory_cases_passed": true,
    "case_ids": [
      "family_memory_override_v1",
      "family_memory_advisory_fill_v1"
    ],
    "failing_case_ids": [],
    "latest_report_path": "var/formal-benchmarks/latest-all_registered-run-report.json"
  },
  "recovery_replay_summary": {
    "status": "ready",
    "case_id": "family_route_failure_v1",
    "review_status": "passed",
    "check_count": 3,
    "passed_check_count": 3,
    "failed_check_count": 0,
    "attempt_count": 1,
    "max_attempts": 2,
    "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
  },
  "timing_summary": {
    "status": "ready",
    "benchmark_timing_summary_present": true,
    "stability_window_size": 4,
    "stability_executed_run_count": 4
  },
  "redaction_summary": {
    "internal_only": true,
    "sanitized": true,
    "relative_evidence_paths_only": true,
    "forbidden_key_markers": [
      "api_key",
      "token",
      "secret",
      "authorization",
      "prompt",
      "debug_trace",
      "action_id",
      "tool_event_id",
      "idempotency_key"
    ]
  },
  "evidence_paths": [
    {
      "evidence_id": "v2_integrity_gate",
      "path": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
      "exists": true,
      "required_for_summary": true,
      "status": "ready"
    }
  ]
}
```

Notes:

- section `status` values may be `ready`, `missing`, or `invalid`
- top-level `status` may be `ready`, `degraded`, `missing_evidence`, or `invalid_evidence`
- evidence paths must stay relative
- the route may include additive detail fields when they remain sanitized and derived from existing contracts

## 6. Observability

This task adds one internal aggregation read surface only.

It must not add new telemetry recording, new trace upload behavior, or new persistence. It must reuse existing observability and artifact-generation paths.

The API must remain sanitized and must not expose:

- API keys
- tokens
- secrets
- authorization headers
- prompts
- debug traces
- stack traces
- tracebacks
- raw provider request/response payloads
- raw action-ledger payload bodies
- raw benchmark case payload dumps

The API may expose stable relative artifact paths and aggregate reviewer-facing status/count/metric fields only.

## 7. Failure Handling

Expected failure modes and required behavior:

- If the latest `v2_integrity_gate` alias is missing:
  - return `200`
  - set top-level status to at least `missing_evidence`
  - mark `benchmark_summary.status = "missing"`
  - include the expected canonical path in `evidence_paths`

- If the latest stability alias is missing:
  - return `200`
  - keep the summary partial
  - mark `stability_summary.status = "missing"`

- If the latest `all_registered` alias is missing or invalid:
  - return `200`
  - mark `memory_governance_summary.status = "missing"` or `"invalid"`

- If the latest canonical recovery review is missing or invalid:
  - return `200`
  - mark `recovery_replay_summary.status = "missing"` or `"invalid"`

- If one section payload is malformed but readable:
  - degrade that section only
  - do not fail the whole route unless the exception escapes contract handling

- If the route encounters an unexpected non-contract exception:
  - return `500`
  - do not leak stack traces or raw exception internals in the response body

- If timing data is absent in the latest V2 gate summary:
  - return a valid `timing_summary`
  - mark timing as partial or missing
  - do not fail the route

- If a section has no case results to summarize:
  - return zero counts and a clear degraded status
  - do not invent synthetic passing data

## 8. Acceptance Criteria

- [ ] `docs/specs/102-system-integrity-summary-api-v0.md` exists and matches this task.
- [ ] `docs/plans/102-system-integrity-summary-api-v0-plan.md` exists and matches this task.
- [ ] A new internal route exists at `GET /internal/system/integrity-summary`.
- [ ] The route returns a dedicated typed response model.
- [ ] The route reads existing latest aliases only and does not trigger artifact generation.
- [ ] The route aggregates benchmark gate status from the latest `v2_integrity_gate` alias.
- [ ] The route aggregates stability metrics from the latest `v2_integrity` pass-k alias.
- [ ] The route aggregates memory-governance case status from the latest `all_registered` alias.
- [ ] The route aggregates canonical recovery replay status from the latest family recovery review alias.
- [ ] The route exposes a timing section derived from existing benchmark timing data and stability metadata.
- [ ] The route exposes a deterministic redaction summary and does not leak forbidden sensitive keys.
- [ ] The route exposes repository-relative canonical evidence paths with per-path status.
- [ ] The route supports partial degraded responses when one or more artifacts are missing or invalid.
- [ ] Existing internal observability routes remain unchanged.
- [ ] Existing public demo API routes remain unchanged.
- [ ] No benchmark, memory-policy, replay, or frontend behavior changes in this task.
- [ ] Focused unit and gateway tests cover:
  - success path
  - missing artifact degradation
  - invalid artifact degradation
  - memory-case derivation
  - recovery summary derivation
  - route registration
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
git status --short
python -m pytest tests/test_system_integrity_summary.py tests/test_observability.py tests/test_benchmark_internal_summary.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_observability_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add system integrity summary api
```

## 11. Notes for the Implementer

Keep this task backend-only and contract-first.

Preferred implementation shape:

1. add one focused summary-builder module that knows the canonical evidence paths and section derivations
2. define one typed response schema for the aggregated summary
3. wire one route in `backend/app/api/observability.py`
4. verify degradation behavior with unit tests before gateway tests
5. stop if implementation pressure starts pulling in:
   - 5174 UI rendering
   - evidence verifier redesign
   - artifact refresh logic
   - benchmark/replay execution changes

The implementer should stop and report back if:

- the latest alias contracts in code differ materially from the current repository evidence paths
- deriving memory-governance status from `all_registered` would require changing benchmark report schemas
- the route cannot remain partial/degraded without breaking existing consumers
