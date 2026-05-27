# Spec: 071 Release Gate Latency SLO v0

## 1. Goal

WeekendPilot 已经具备三块相关基础：

- Task `033` 已把 workflow stage timing 和 benchmark percentile summary 写进 workflow 结果、benchmark case report 和 suite report。
- Task `065` 已把 `release_gate_v1` 变成正式 blocking benchmark gate，但当时明确把 latency SLO enforcement 留作 non-goal。
- Task `070` 已把 release gate runtime 固定到 deterministic bounded-agent path，使 gate timing 不再受本地 `LLM_*` / LangSmith preview 配置污染。

当前缺口已经非常窄：`release_gate_v1` 的 timing 仍然只是“报告里有、stdout 会打印”，不是正式阻塞标准。与此同时，工作区里的 submission / report 草稿已经开始手工引用这些 latency 数字，说明发布口径正在形成，但还没有被仓库 contract 固化。

本任务要把这个缺口收口。完成后，`release_gate_v1` 必须同时具备：

- 明确的 blocking latency SLO：`p50 <= 2000ms`、`p95 <= 5000ms`、`max <= 8000ms`
- 可调试的慢 case / 慢 stage 排名
- 对 `pre_flight_check_availability` 和 `logical_planner_agent` 的稳定重点追踪

这个 task 不做性能优化本身。它做的是把“已有 timing 观测”升级成正式 release evidence contract。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 WeekendPilot 定义为 benchmark-driven、deterministic-where-possible、observable-by-default 的系统。`docs/NEXT_PHASE_ROADMAP.md` 则明确当前阶段默认优先 `M1. 评测与观测基础设施`，先把“能跑”收口成“能量化比较、能稳定复现、能直接作为评审基线”。

仓库当前已经具备本任务所需的所有前置：

- Task `033`：workflow stage timing、suite percentile summary、`max_ms` 已存在。
- Task `065`：`release_gate_v1` 已是正式 blocking suite，但 timing 仍是 informational only。
- Task `070`：release gate runtime settings 已 deterministic-isolated，timing 数据现在具备可信 gate 基础。

因此，本任务仍然属于 `docs/NEXT_PHASE_ROADMAP.md` 的 `M1. 评测与观测基础设施`，但它不是新增观测面，而是把已有 timing 证据收口成正式 release threshold。它的优先级高于继续做新 UI 或更大范围能力扩展，因为 release evidence 现在已经可用，只差最后的 blocking contract。

## 3. Requirements

### A. Add blocking latency SLO enforcement to `release_gate_v1`

- `run_benchmark_release_gate(...)` must evaluate latency using:
  - `report.benchmark_timing_summary.overall_total_duration_ms`
- The blocking latency thresholds must be exactly:
  - `p50_ms <= 2000`
  - `p95_ms <= 5000`
  - `max_ms <= 8000`
- The existing Task `065` gate checks must remain unchanged:
  - `suite_id`
  - `run_status`
  - `case_count`
  - `passed_count`
  - `failed_count`
  - `error_count`
  - `overall_score`
  - matrix summary expectations
  - latest alias semantics
- Missing timing data must block release. At minimum, the gate must fail if any of the following are missing:
  - `benchmark_timing_summary`
  - `overall_total_duration_ms`
  - `p50_ms`
  - `p95_ms`
  - `max_ms`
- The gate must continue to record `p99_ms`, but `p99_ms` remains non-blocking in this task.

### B. Preserve latency diagnostics inside the release-gate report

- The unique run report file:
  - `suite-release_gate_v1-run-report.json`
  must be enriched with one additive top-level block:
  - `release_gate_evaluation`
- `release_gate_evaluation.schema_version` must be:
  - `weekendpilot_release_gate_evaluation_v1`
- `release_gate_evaluation` must include:
  - `gate_id`
  - `suite_id`
  - `release_blocked`
  - `blocking_failures`
  - `latency_slo`
  - `slow_cases`
  - `slow_stages`
  - `focus_stages`
- `release_gate_evaluation.latency_slo` must include:
  - `schema_version = "weekendpilot_release_gate_latency_slo_v1"`
  - `p50_threshold_ms`
  - `p95_threshold_ms`
  - `max_threshold_ms`
  - `observed_p50_ms`
  - `observed_p95_ms`
  - `observed_p99_ms`
  - `observed_max_ms`
  - `status`
- `status` must be:
  - `"passed"` when all three thresholds pass
  - `"failed"` otherwise

### C. Persist full slow-case ranking

- `release_gate_evaluation.slow_cases` must preserve a full ranking, not just one top item.
- For a passing `release_gate_v1` run, `slow_cases` must contain exactly 15 entries, one per case in the suite.
- Each slow-case entry must include:
  - `rank`
  - `case_id`
  - `workflow_status`
  - `total_duration_ms`
  - `report_path`
- Ranking rule must be exact:
  1. sort by `total_duration_ms` descending
  2. tie-break by `case_id` ascending
- `total_duration_ms` must come from each case result’s:
  - `workflow_timing_summary.total_duration_ms`
- If any `release_gate_v1` case result lacks `workflow_timing_summary.total_duration_ms`, the gate must fail and the missing case must not be silently ignored.

### D. Persist full slow-stage ranking and focus-stage tracking

- `release_gate_evaluation.slow_stages` must preserve a full ranking of all available stage percentile entries from:
  - `report.benchmark_timing_summary.stages`
- Each slow-stage entry must include:
  - `rank`
  - `node_name`
  - `sample_count`
  - `retry_case_count`
  - `min_ms`
  - `p50_ms`
  - `p95_ms`
  - `p99_ms`
  - `max_ms`
  - `mean_ms`
- Ranking rule must be exact:
  1. sort by `p95_ms` descending
  2. tie-break by `max_ms` descending
  3. tie-break by `mean_ms` descending
  4. tie-break by `node_name` ascending
- `release_gate_evaluation.focus_stages` must preserve exact entries for:
  - `pre_flight_check_availability`
  - `logical_planner_agent`
- Each focus-stage entry must use the same field set as a slow-stage entry except `rank` is optional.
- If either focus stage is missing from the suite timing summary, the gate must fail.

### E. Update the in-memory gate result and human-readable summary

- `BenchmarkReleaseGateResult` must expose:
  - `max_duration_ms`
  - structured slow-case diagnostics
  - structured slow-stage diagnostics
  - structured focus-stage diagnostics
- The success and failure CLI summaries must include:
  - the existing gate/suite/case/score lines
  - one timing line with `p50`, `p95`, `p99`, and `max`
  - one explicit latency-SLO line showing thresholds and pass/fail status
  - a `Focus stages` section that prints both:
    - `pre_flight_check_availability`
    - `logical_planner_agent`
  - a `Slow cases` section that prints the top 3 ranked entries
  - a `Slow stages` section that prints the top 5 ranked entries
- The CLI summary may stay human-readable text only; the full ranking must live in the enriched report JSON.

### F. Preserve latest-alias semantics

- The unique suite report in the run directory must be enriched before any latest-alias copy is attempted.
- On a fully passing run, the copied latest alias:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  must include the same `release_gate_evaluation` block as the unique report.
- On any blocked run, the gate must preserve the unique run directory and must not overwrite the prior latest alias.
- If report enrichment fails, the gate must fail.

### G. Add regression coverage

- Add focused unit tests for:
  - passing latency SLO evaluation
  - blocking on `p50` breach
  - blocking on `p95` breach
  - blocking on `max` breach
  - blocking when case timing is missing
  - blocking when a focus stage is missing
  - deterministic slow-case ranking order
  - deterministic slow-stage ranking order
  - report enrichment into the suite report JSON
  - latest alias remains unchanged on blocked run
  - CLI summary includes `max` and focus-stage diagnostics
- Add focused integration coverage for:
  - a real `release_gate_v1` run still passes
  - the unique suite report contains `release_gate_evaluation`
  - the latest alias contains `release_gate_evaluation`
  - `slow_cases` is sorted descending by `total_duration_ms`
  - `focus_stages.pre_flight_check_availability` exists
  - `focus_stages.logical_planner_agent` exists

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not re-instrument workflow timing or change Task `033` timing math.
- Do not change `release_gate_v1` suite membership, case order, matrix-summary rules, artifact directory layout, or deterministic runtime isolation.
- Do not change `all_registered` suite behavior or `python scripts/run_formal_verification.py`.
- Do not optimize workflow latency in this task.
- Do not add frontend panels, internal observability APIs, or benchmark APIs.
- Do not widen this task into CI, GitHub Actions, or general benchmark-schema redesign.
- Do not modify unrelated local files such as `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, `docs/artifacts/`, or `qc`.

## 5. Interfaces and Contracts

### Inputs

- `python scripts/run_benchmark_release_gate.py`
- `run_benchmark_release_gate(output_root=None, start_services=True, ...)`
- `BenchmarkHarness.run_suite("release_gate_v1")`
- existing `suite-release_gate_v1-run-report.json` generated by the benchmark harness
- existing per-case `workflow_timing_summary`
- existing suite-level `benchmark_timing_summary`

### Outputs

- Blocking latency-SLO enforcement for `release_gate_v1`
- Enriched unique release-gate suite report JSON with:
  - `release_gate_evaluation`
- Enriched latest passing alias:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- Human-readable CLI summary that includes `max`, focus stages, and ranked slow diagnostics

### Schemas

Example additive report block:

```json
{
  "release_gate_evaluation": {
    "schema_version": "weekendpilot_release_gate_evaluation_v1",
    "gate_id": "release_gate_v1",
    "suite_id": "release_gate_v1",
    "release_blocked": false,
    "blocking_failures": [],
    "latency_slo": {
      "schema_version": "weekendpilot_release_gate_latency_slo_v1",
      "p50_threshold_ms": 2000,
      "p95_threshold_ms": 5000,
      "max_threshold_ms": 8000,
      "observed_p50_ms": 446,
      "observed_p95_ms": 1564,
      "observed_p99_ms": 2011,
      "observed_max_ms": 2011,
      "status": "passed"
    },
    "slow_cases": [
      {
        "rank": 1,
        "case_id": "family_route_failure_v1",
        "workflow_status": "completed",
        "total_duration_ms": 2011,
        "report_path": "var/formal-benchmarks/release-gate-v1-123/.../family_route_failure_v1-report.json"
      }
    ],
    "slow_stages": [
      {
        "rank": 1,
        "node_name": "pre_flight_check_availability",
        "sample_count": 15,
        "retry_case_count": 0,
        "min_ms": 138,
        "p50_ms": 162,
        "p95_ms": 1224,
        "p99_ms": 1224,
        "max_ms": 1224,
        "mean_ms": 232.41
      }
    ],
    "focus_stages": {
      "pre_flight_check_availability": {
        "node_name": "pre_flight_check_availability",
        "sample_count": 15,
        "retry_case_count": 0,
        "min_ms": 138,
        "p50_ms": 162,
        "p95_ms": 1224,
        "p99_ms": 1224,
        "max_ms": 1224,
        "mean_ms": 232.41
      },
      "logical_planner_agent": {
        "node_name": "logical_planner_agent",
        "sample_count": 15,
        "retry_case_count": 0,
        "min_ms": 2,
        "p50_ms": 31,
        "p95_ms": 36,
        "p99_ms": 36,
        "max_ms": 36,
        "mean_ms": 26.24
      }
    }
  }
}
```

Example summary excerpt:

```text
Benchmark release gate passed.
Timing: p50=446ms, p95=1564ms, p99=2011ms, max=2011ms
Latency SLO: p50<=2000ms, p95<=5000ms, max<=8000ms (passed)
Focus stages:
- pre_flight_check_availability: mean=232.41ms, p95=1224ms, max=1224ms
- logical_planner_agent: mean=26.24ms, p95=36ms, max=36ms
```

## 6. Observability

This task must reuse existing benchmark timing and report infrastructure.

Requirements:

- No new API route is added.
- No new frontend surface is added.
- No new database table or Redis structure is added.
- The enriched `release_gate_evaluation` block lives only inside the release-gate suite report JSON.
- The task must continue to rely on the existing sanitized benchmark reporting path.
- The enriched report must not expose:
  - secrets
  - API keys
  - tokens
  - authorization headers
  - prompts
  - raw provider responses
  - debug traces
  - traceback bodies
  - raw action IDs
  - raw tool event IDs

## 7. Failure Handling

- If the release gate cannot read `benchmark_timing_summary.overall_total_duration_ms`, the gate must fail.
- If `p50_ms > 2000`, the gate must fail.
- If `p95_ms > 5000`, the gate must fail.
- If `max_ms > 8000`, the gate must fail.
- If any `release_gate_v1` case lacks `workflow_timing_summary.total_duration_ms`, the gate must fail.
- If `pre_flight_check_availability` is missing from stage timing summary, the gate must fail.
- If `logical_planner_agent` is missing from stage timing summary, the gate must fail.
- If release-gate report enrichment fails, the gate must fail.
- If the gate is blocked for any reason, the prior latest alias must not be overwritten.
- Existing bootstrap, readiness timeout, Alembic, suite-count, matrix-summary, and deterministic-runtime failures from Tasks `065` and `070` must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/071-release-gate-latency-slo-v0.md` exists and matches this task.
- [ ] `docs/plans/071-release-gate-latency-slo-v0-plan.md` exists and matches this task.
- [ ] `docs/specs/` and `docs/plans/` remain continuous and matched through `071`.
- [ ] `release_gate_v1` blocks release when `p50_ms > 2000`.
- [ ] `release_gate_v1` blocks release when `p95_ms > 5000`.
- [ ] `release_gate_v1` blocks release when `max_ms > 8000`.
- [ ] `release_gate_v1` blocks release when required timing data is missing.
- [ ] The unique `suite-release_gate_v1-run-report.json` contains additive top-level `release_gate_evaluation`.
- [ ] A passing latest alias copy of `latest-release_gate_v1-run-report.json` also contains `release_gate_evaluation`.
- [ ] `release_gate_evaluation.slow_cases` preserves a deterministic full ranking for passing `release_gate_v1` runs.
- [ ] `release_gate_evaluation.slow_stages` preserves a deterministic full ranking.
- [ ] `release_gate_evaluation.focus_stages` includes both `pre_flight_check_availability` and `logical_planner_agent`.
- [ ] Existing Task `065` suite-count and matrix-summary gate rules remain unchanged.
- [ ] Existing Task `070` deterministic runtime isolation remains unchanged.
- [ ] `README.md` documents the blocking latency thresholds and report diagnostics.
- [ ] Focused unit and integration tests listed below pass, or any environment blocker is reported clearly.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except for pre-existing unrelated local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_release_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_release_gate.py -q
python scripts/run_benchmark_release_gate.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add release gate latency slo
```

## 11. Notes for the Implementer

Keep this task release-gate-only.

Important defaults for this task:

- Reuse the existing timing artifacts from Task `033`.
- Reuse the existing deterministic release-gate boundary from Task `070`.
- Enrich the release-gate suite report in place with a top-level `release_gate_evaluation` block instead of widening into a generic benchmark-schema redesign.
- Do not weaken the thresholds if the current implementation misses them. If the observed gate run exceeds the spec values, the correct behavior is to keep the gate blocked and report the numbers.
- Do not stage unrelated local doc drafts or artifacts.
- Stop and report back if implementing this task would require changing benchmark fixture payloads, suite membership, deterministic workflow settings, or the semantics of `all_registered`.
