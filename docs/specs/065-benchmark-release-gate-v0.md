# Spec: 065 Benchmark Release Gate v0

## 1. Goal

WeekendPilot 已经具备强 benchmark 基础设施：命名 suite、matrix summary、outcome rollup、formal verification runner、L1-L3 continuation/memory coverage，以及可复现的 `all_registered` 报告输出。但这些能力仍然更像“工程验证能力”，还不是“V1 是否可以正式发布”的明确标准。

本任务要把这个缺口收口成一个正式的 benchmark release gate。完成后，仓库必须同时具备两层清晰边界：

1. 一个明确的、可执行的 `release_gate_v1` 阻塞门槛，只覆盖当前 LocalLife-Bench 的 `L1-L3` 用例。
2. 一个与之并存但更广的 `all_registered` formal verification 口径，继续覆盖已注册全量用例，包括当前的 `L5` composite chaos cases。

换句话说，这个 task 不是再去“增强 benchmark”，而是把已经存在的 benchmark 能力转成正式的 release 标准、失败判定规则和 release checklist，避免发布判断继续停留在手工解读 report 或非正式草稿层面。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 明确要求 WeekendPilot 是 benchmark-driven、observable-by-default 的系统；`docs/NEXT_PHASE_ROADMAP.md` 也把当前阶段默认优先级放在 `M1. 评测与观测基础设施`，强调要先把“能跑”收口成“能量化比较、能稳定复现、能作为后续评审基线”。

仓库当前已经具备本任务所依赖的关键前置：

- Task `050` 已把 benchmark suite 组织成可比较的命名套件。
- Task `053` 已把 memory governance 用例纳入 suite catalog。
- Task `055` 已把多轮 continuation 的 `L3` 用例纳入 benchmark。
- Task `061` 已提供 `python scripts/run_formal_verification.py`，可一键跑 `all_registered`。
- Task `064` 已完成当前最新的 product-facing friends demo 路径，且最新 commit 与最新 task 对齐。

当前更直接的缺口不是功能实现，而是 benchmark 治理：

- 仓库里已有 `all_registered` 17-case 全量验证，但它把 `L5` composite chaos cases 也包含进来了。
- 用户当前要收口的是“LocalLife-Bench L1-L3 cases”的 V1 正式发布门槛，而不是把更激进的 `L5` chaos case 直接当成 V1 阻塞门槛。
- 当前工作区已经出现了未纳入 task 链路的 submission / formal report 草稿，这说明“发布标准”正在手工形成，但还没有正式编码到仓库 contract 中。

因此，本 task 对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M1. 评测与观测基础设施`，是一个 benchmark governance / release convergence task。

## 3. Requirements

### A. Add a canonical V1 release suite

- Add a new canonical benchmark suite ID:
  - `release_gate_v1`

- Extend `BenchmarkSuiteId` and the canonical suite catalog so `list_benchmark_suites()` returns these exact suite IDs in this exact order:
  - `baseline`
  - `expanded`
  - `recovery_focused`
  - `memory_governance`
  - `conversation_continuations`
  - `default`
  - `release_gate_v1`
  - `all_registered`

- `load_benchmark_suite("release_gate_v1")` must return exactly these 15 cases in this exact order:

  1. `family_afternoon_v1`
  2. `family_indoor_light_meal_v1`
  3. `family_outdoor_quick_dinner_v1`
  4. `family_memory_override_v1`
  5. `family_citywalk_addon_v1`
  6. `solo_afternoon_v1`
  7. `couple_afternoon_v1`
  8. `friends_gathering_v1`
  9. `rainy_day_fallback_v1`
  10. `budget_lite_v1`
  11. `family_route_failure_v1`
  12. `family_memory_advisory_fill_v1`
  13. `family_memory_expired_advisory_v1`
  14. `solo_clarification_continuation_v1`
  15. `family_replan_version_continuation_v1`

- `release_gate_v1` must therefore include all currently registered `L1-L3` benchmark cases and exclude the two current `L5` composite chaos cases:
  - excluded:
    - `family_route_and_dining_unavailable_v1`
    - `rainy_day_ticket_sold_out_v1`

- `load_benchmark_suite("all_registered")` must remain unchanged and keep returning the current 17 registered cases in canonical order.

- `list_benchmark_suite_ids_for_case(case_id)` must include `release_gate_v1` where appropriate. Representative expectations:
  - `family_afternoon_v1` -> `["baseline", "default", "release_gate_v1", "all_registered"]`
  - `family_memory_override_v1` -> `["baseline", "memory_governance", "default", "release_gate_v1", "all_registered"]`
  - `family_memory_advisory_fill_v1` -> `["memory_governance", "release_gate_v1", "all_registered"]`
  - `solo_clarification_continuation_v1` -> `["conversation_continuations", "release_gate_v1", "all_registered"]`
  - `family_route_failure_v1` -> `["recovery_focused", "release_gate_v1", "all_registered"]`
  - `family_route_and_dining_unavailable_v1` -> `["recovery_focused", "all_registered"]`
  - `rainy_day_ticket_sold_out_v1` -> `["recovery_focused", "all_registered"]`
  - `missing_case_v1` -> `[]`

- The exact `release_gate_v1` matrix summary must be:
  - `case_count = 15`
  - `scenario_bucket_counts = {"couple": 1, "family": 9, "friends": 1, "mixed": 1, "solo": 2, "unknown": 1}`
  - `level_counts = {"L1": 3, "L2": 8, "L3": 4}`
  - `tool_profile_counts = {"mock_world": 15}`
  - `world_profile_counts = {"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 9, "friends_gathering": 1, "rainy_day_fallback": 1, "solo_afternoon": 2}`
  - `failure_mode_counts = {"none": 14, "route_unavailable": 1}`
  - `tag_counts = {"addon_optional": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 9, "citywalk": 2, "clarification_turn": 1, "conversation_continuation": 2, "date_friendly": 1, "failure_injected": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 4, "light_activity": 2, "light_meal": 9, "memory_advisory": 1, "memory_expired": 1, "memory_governance": 2, "memory_override": 1, "outdoor_activity": 2, "plan_versioning": 1, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1, "replan_turn": 1, "route_failure": 1}`

### B. Add a formal benchmark release gate runner

- Add a new orchestration module:
  - `backend/app/benchmark/release_gate.py`

- Add a new repo-root entrypoint:
  - `scripts/run_benchmark_release_gate.py`

- The standard release-gate command must be:
  - `python scripts/run_benchmark_release_gate.py`

- The new runner must:
  - start `postgres` and `redis` with `docker compose up -d postgres redis`
  - wait for PostgreSQL and Redis readiness before running the suite
  - run `python -m alembic upgrade head`
  - construct `BenchmarkHarness`
  - run exactly `BenchmarkHarness.run_suite("release_gate_v1")`
  - write artifacts under `var/formal-benchmarks/`
  - create a unique run directory named:
    - `var/formal-benchmarks/release-gate-v1-<unique-id>/`
  - write the suite report filename:
    - `suite-release_gate_v1-run-report.json`
  - write a stable latest alias file:
    - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`

- The new runner may follow the implementation pattern of `backend/app/benchmark/formal_verification.py`, but it must not change the public contract of:
  - `python scripts/run_formal_verification.py`
  - `backend.app.benchmark.formal_verification.run_formal_verification(...)`
  - `FORMAL_SUITE_ID = "all_registered"`

- The release gate runner must return exit code `0` only when all of these are true:
  - the executed `suite_id` is exactly `release_gate_v1`
  - `run_status == "passed"`
  - `case_count == 15`
  - `passed_count == 15`
  - `failed_count == 0`
  - `error_count == 0`
  - `overall_score == 1.0`
  - the suite report path exists
  - the latest alias file is refreshed successfully
  - `benchmark_summary.matrix_summary.level_counts == {"L1": 3, "L2": 8, "L3": 4}`
  - `benchmark_summary.matrix_summary.tool_profile_counts == {"mock_world": 15}`
  - `benchmark_summary.matrix_summary.failure_mode_counts == {"none": 14, "route_unavailable": 1}`

- The release gate runner must return a non-zero exit code if any of the above conditions are false.

- The runner must preserve the unique run directory on failure and must not overwrite `latest-release_gate_v1-run-report.json` with a failed result.

- The runner must print a concise human-readable summary on success, including at least:
  - gate ID
  - suite ID
  - case count
  - passed count
  - failed count
  - error count
  - overall score
  - p50 / p95 / p99 total duration
  - unique run directory
  - suite report path
  - latest alias path

- Timing is required to be emitted and recorded, but in this v0 release-gate task timing is informational only, not a blocking threshold.

### C. Define the formal scope boundary between release gate and formal verification

- `release_gate_v1` must be documented as the V1 blocking suite for LocalLife-Bench `L1-L3`.
- `all_registered` must remain documented as the broader engineering / formal verification suite that still includes the two current `L5` composite chaos cases.
- The repository documentation must explicitly state that:
  - `python scripts/run_benchmark_release_gate.py` is the V1 blocking gate
  - `python scripts/run_formal_verification.py` remains the broader full-inventory formal verification entrypoint

### D. Update README with the release standard and checklist

- Update `README.md` to add a benchmark release gate section that includes:
  - the exact `release_gate_v1` purpose
  - the distinction between `release_gate_v1` and `all_registered`
  - the exact release-gate command
  - the exact formal-verification command
  - the release-gate pass threshold
  - the failure determination rules
  - a flat release checklist

- The README release checklist must include at least:
  - run `python scripts/run_benchmark_release_gate.py`
  - confirm exit code `0`
  - confirm `latest-release_gate_v1-run-report.json` was refreshed
  - confirm no secrets or unrelated local artifacts are staged
  - retain or reference the latest release-gate report path for review
  - optionally run `python scripts/run_formal_verification.py` for the broader full-inventory validation

### E. Update tests and observability expectations

- Update focused unit tests to cover:
  - `release_gate_v1` suite ordering
  - `release_gate_v1` exact membership
  - `release_gate_v1` exact matrix-summary counts
  - representative per-case suite memberships after adding `release_gate_v1`
  - release gate runner success path
  - latest alias refresh behavior
  - failure path does not overwrite latest alias
  - CLI exit code semantics

- Update focused integration tests to cover:
  - `BenchmarkHarness.run_suite("release_gate_v1")`
  - exact suite report filename `suite-release_gate_v1-run-report.json`
  - exact `release_gate_v1` summary counts
  - the real release-gate runner using PostgreSQL/Redis
  - updated observability `registered_suite_ids` expectations

- Existing observability code does not need a new API surface, but tests must reflect that benchmark-backed runs now include `release_gate_v1` in `registered_suite_ids` when appropriate.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add new benchmark case fixtures, failure profiles, suites beyond `release_gate_v1`, world fixtures, or migrations.
- Do not change any benchmark case payload, taxonomy payload, grader rule, or workflow behavior.
- Do not include `L4` or `L5` cases in the blocking V1 release gate.
- Do not change the semantics of `default` or `all_registered`.
- Do not rewrite `python scripts/run_formal_verification.py` into a parameterized generic tool in this task.
- Do not modify `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/artifacts/`, frontend behavior, demo APIs, AMap preview behavior, or memory/replan feature logic.
- Do not introduce latency SLO enforcement in this v0 task.

## 5. Interfaces and Contracts

### Inputs

- Existing suite loader:
  - `load_benchmark_suite(suite_id)`
- Existing benchmark runner:
  - `BenchmarkHarness.run_suite(suite_id)`
- New release-gate command:
  - `python scripts/run_benchmark_release_gate.py`
- Existing formal-verification command:
  - `python scripts/run_formal_verification.py`

### Outputs

- New canonical suite:
  - `release_gate_v1`
- New release-gate suite report:
  - `suite-release_gate_v1-run-report.json`
- New latest alias:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- Human-readable CLI summary
- Non-zero exit code when the gate is blocked

### Schemas

Example release-gate result shape:

```json
{
  "gate_id": "release_gate_v1",
  "suite_id": "release_gate_v1",
  "release_blocked": false,
  "blocking_failures": [],
  "run_status": "passed",
  "case_count": 15,
  "passed_count": 15,
  "failed_count": 0,
  "error_count": 0,
  "overall_score": 1.0,
  "run_directory": "var/formal-benchmarks/release-gate-v1-12345678-1234-1234-1234-123456789abc",
  "suite_report_path": "var/formal-benchmarks/release-gate-v1-12345678-1234-1234-1234-123456789abc/suite-release_gate_v1-run-report.json",
  "latest_report_path": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
  "trace_buffer_path": "var/formal-benchmarks/release-gate-v1-12345678-1234-1234-1234-123456789abc/release-gate-traces.jsonl",
  "p50_duration_ms": 1000,
  "p95_duration_ms": 2000,
  "p99_duration_ms": 2500
}
```

Example success summary:

```text
Benchmark release gate passed.
Gate: release_gate_v1
Suite: release_gate_v1
Cases: 15 (15 passed, 0 failed, 0 error)
Overall score: 1.0
Timing: p50=1000ms, p95=2000ms, p99=2500ms
Run directory: var/formal-benchmarks/release-gate-v1-12345678-1234-1234-1234-123456789abc
Suite report: var/formal-benchmarks/release-gate-v1-12345678-1234-1234-1234-123456789abc/suite-release_gate_v1-run-report.json
Latest report: var/formal-benchmarks/latest-release_gate_v1-run-report.json
```

## 6. Observability

This task must reuse the existing benchmark reporting and sanitization path.

Requirements:

- release-gate suite reports must still be written through the existing benchmark reporting layer
- no new observability API route is added
- no new frontend page is added
- existing internal observability benchmark artifact summaries may show `release_gate_v1` inside `registered_suite_ids`
- release-gate artifacts must stay under `var/`, not under `docs/artifacts/`

The new runner and reports must not expose:

- secrets
- API keys
- tokens
- authorization headers
- raw prompts
- raw tool payloads
- raw action payloads
- raw traceback bodies

## 7. Failure Handling

- If `docker compose up -d postgres redis` fails, the release gate must fail with a non-zero exit code.
- If PostgreSQL or Redis readiness times out, the release gate must fail.
- If Alembic upgrade fails, the release gate must fail before running the suite.
- If the runner executes any suite other than `release_gate_v1`, the release gate must fail.
- If the returned suite report is missing or cannot be copied to the latest alias, the release gate must fail.
- If `failed_count > 0` or `error_count > 0`, the release gate must fail.
- If `case_count != 15`, the release gate must fail.
- If `overall_score != 1.0`, the release gate must fail.
- If the matrix summary drifts away from the exact `L1/L2/L3` and failure-mode counts defined in this spec, the release gate must fail.
- If the release gate fails after creating a unique run directory, that directory must remain available for debugging.
- On failure, `latest-release_gate_v1-run-report.json` must not be overwritten.
- Existing `python scripts/run_formal_verification.py` behavior must remain unchanged even if the new release gate fails.

## 8. Acceptance Criteria

- [ ] `docs/specs/065-benchmark-release-gate-v0.md` exists and matches this task.
- [ ] `docs/plans/065-benchmark-release-gate-v0-plan.md` exists and matches this task.
- [ ] `docs/specs/` and `docs/plans/` remain continuous and matched through `065`.
- [ ] `release_gate_v1` is added to the canonical suite catalog in the exact order defined in this spec.
- [ ] `load_benchmark_suite("release_gate_v1")` returns exactly the 15 specified `L1-L3` case IDs in order.
- [ ] `load_benchmark_suite("all_registered")` remains unchanged at 17 cases.
- [ ] `family_route_and_dining_unavailable_v1` and `rainy_day_ticket_sold_out_v1` are excluded from `release_gate_v1`.
- [ ] `list_benchmark_suite_ids_for_case(...)` returns the updated memberships including `release_gate_v1` for representative default, recovery, memory, and continuation cases.
- [ ] The `release_gate_v1` matrix summary exactly matches the counts defined in this spec.
- [ ] `python scripts/run_benchmark_release_gate.py` runs exactly `release_gate_v1`.
- [ ] A green run of the release gate exits `0`, writes `suite-release_gate_v1-run-report.json`, and refreshes `var/formal-benchmarks/latest-release_gate_v1-run-report.json`.
- [ ] A failing release-gate evaluation does not overwrite the prior latest alias.
- [ ] `python scripts/run_formal_verification.py` continues to run `all_registered` unchanged.
- [ ] `README.md` documents the V1 blocking gate, the broader formal-verification scope, the failure rules, and the release checklist.
- [ ] Focused unit and integration tests listed below pass, or any environment blocker is reported clearly.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except pre-existing unrelated local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_release_gate.py tests/integration/test_observability_gateway.py -k "release_gate_v1 or benchmark_release_gate or registered_suite_ids" -v
python scripts/run_benchmark_release_gate.py
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add benchmark release gate
```

## 11. Notes for the Implementer

Keep this task governance-first.

Important boundaries:

- `release_gate_v1` is the blocking V1 standard.
- `all_registered` remains the broader engineering / formal verification sweep.
- The two current `L5` composite chaos cases stay outside the blocking gate in this task.
- Timing data must still be emitted, but timing thresholds are intentionally non-blocking in this v0 task.
- Do not widen into CI, GitHub Actions, submission-doc publication, or benchmark fixture authoring.
- Do not stage the current unrelated local files in the working tree.
- Stop and report back if implementing this task would require changing benchmark behavior, case payloads, or the semantics of `all_registered`.
