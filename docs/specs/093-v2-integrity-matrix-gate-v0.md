# Spec: 093 V2 Integrity Matrix Gate v0

## 1. Goal

WeekendPilot 当前已经有稳定的 `release_gate_v1`、`coverage_gate_v1_5`、`all_registered` formal verification，以及可运行的 `v2_integrity` suite 和 `v2_taxonomy_summary`。但仓库还缺少一个直接面向 `V2 Integrity Edition` 的完整性证明面：`v2_integrity` suite 还不能输出系统完整性覆盖结果，也没有独立的 `v2_integrity gate` 作为正式 sign-off surface。

本任务要补齐这两个缺口：

- 扩展 benchmark matrix / suite summary，让 `v2_integrity` suite 能输出系统完整性覆盖结果
- 新增独立 `v2_integrity gate`，用于检查 memory / recovery / continuation / robustness / L4-style 覆盖是否达标

完成后，仓库应能在不影响现有 V1 正式交付边界的前提下，提供一条独立的 V2 integrity formal evidence 路径。

## 2. Project Context

本任务属于 `docs/PROJECT_BLUEPRINT.md` 和 `docs/NEXT_PHASE_ROADMAP.md` 所定义的 `V2 Integrity Edition` 路线。该路线的重点不是更深的真实地图 provider 集成，也不是 customer UI 扩展，而是：

- benchmark 完整性
- memory governance evidence
- 系统可审计性
- recovery 与稳定性证据
- Mock World 上的可复现正式 benchmark 基座

当前仓库中与本任务直接相关的 benchmark 基础设施已经存在：

- `backend/app/benchmark/suites.py`
  - 已定义 `v2_integrity` suite
- `backend/app/benchmark/schemas.py`
  - 已定义 `BenchmarkCaseV2Taxonomy`
  - 已定义 `BenchmarkCaseV2MatrixSummary`
- `backend/app/benchmark/matrix.py`
  - 已提供 `build_case_v2_matrix_summary(...)`
- `backend/app/benchmark/harness.py`
  - 已把 `v2_taxonomy_summary` 写入 suite-level `benchmark_summary`
- `backend/app/benchmark/release_gate.py`
  - 当前 V1 blocking gate
- `backend/app/benchmark/coverage_gate.py`
  - 当前 inventory breadth gate

本任务必须复用这些现有结构，而不是替换它们。

## 3. Requirements

- `v2_integrity` suite 必须输出一个 additive 的系统完整性覆盖结果。
- 完整性覆盖结果必须可序列化到 suite report，并可被后续 gate 直接消费。
- 新增独立 `v2_integrity gate`，运行对象是 `v2_integrity` suite。
- gate 必须检查以下覆盖维度：
  - memory
  - recovery
  - continuation
  - robustness
  - L4-style
- gate 必须在 suite 本身全部通过的前提下，再评估上述覆盖阈值。
- gate 成功时必须刷新独立 latest alias。
- gate 失败时不得覆盖已有 latest alias。
- `scripts/show_submission_evidence.py` 必须纳入该新 gate 证据入口。
- `scripts/demo_preflight.py` 必须把该新 latest alias 纳入正式 preflight 检查。
- `release_gate_v1` 的 suite membership、阈值、输出契约、latest alias 语义都必须保持不变。
- `coverage_gate_v1_5` 的 suite membership、阈值、输出契约、latest alias 语义都必须保持不变。

## 4. Non-goals

- 不修改 `release_gate_v1`。
- 不修改 `coverage_gate_v1_5` 的阈值或通过/失败语义。
- 不修改 `all_registered` 的 case 顺序或 formal verification 语义。
- 不新增内部 benchmark summary API。
- 不修改 reviewer UI 或 internal review page。
- 不把 AMap 接入正式 benchmark 主链。
- 不刷新 `var/` 下任何 canonical benchmark artifact。
- 不修改 workflow、memory lifecycle、provider integration 等与本任务无关的功能。
- 不提交 `.env`、API key、token、secret、`var/`、`.venv`、`node_modules`、`frontend/dist` 或 Playwright artifacts。

## 5. Interfaces and Contracts

本任务应保持现有 `matrix_summary` 与 `v2_taxonomy_summary` 契约不变，并新增一层 additive 的 integrity coverage contract。

### Inputs

- `BenchmarkHarness.run_suite("v2_integrity")` 的 suite report
- `BenchmarkSummary.matrix_summary`
- `BenchmarkSummary.v2_taxonomy_summary`
- case-level taxonomy / v2 taxonomy 数据

### Outputs

- suite report 中新增的 `integrity_coverage_summary`
- suite report 中新增的 `v2_integrity_gate_evaluation`
- latest alias:
  - `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`

### Schemas

建议新增 additive summary：

```json
{
  "schema_version": "weekendpilot_benchmark_integrity_coverage_v1",
  "case_count": 12,
  "memory_case_count": 3,
  "recovery_case_count": 3,
  "continuation_case_count": 2,
  "robustness_case_count": 4,
  "l4_case_count": 1
}
```

建议新增 gate evaluation payload：

```json
{
  "schema_version": "weekendpilot_v2_integrity_gate_evaluation_v1",
  "gate_id": "v2_integrity_gate",
  "suite_id": "v2_integrity",
  "release_blocked": false,
  "blocking_failures": [],
  "coverage_thresholds": {
    "minimum_case_count": 12,
    "minimum_memory_case_count": 3,
    "minimum_recovery_case_count": 3,
    "minimum_continuation_case_count": 2,
    "minimum_robustness_case_count": 4,
    "minimum_l4_case_count": 1
  },
  "observed_coverage": {
    "integrity_coverage_summary": {},
    "v2_taxonomy_summary": {}
  }
}
```

建议 coverage 口径如下：

- `memory_case_count`
  - `v2_taxonomy.memory_mode != "none"`
- `recovery_case_count`
  - `v2_taxonomy.failure_mode != "none"`
- `continuation_case_count`
  - `v2_taxonomy.conversation_mode != "single_turn"`
- `robustness_case_count`
  - `taxonomy.tags` 含 `robustness_case`，或 `expected.robustness` 非空
- `l4_case_count`
  - `v2_taxonomy.level == "L4"`

建议 gate minimums：

- `case_count >= 12`
- `memory_case_count >= 3`
- `recovery_case_count >= 3`
- `continuation_case_count >= 2`
- `robustness_case_count >= 4`
- `l4_case_count >= 1`
- `memory_mode_counts.override_guarded >= 1`
- `memory_mode_counts.advisory_fill >= 1`
- `memory_mode_counts.expired_advisory >= 1`
- `conversation_mode_counts.clarification >= 1`
- `conversation_mode_counts.replan_versioned >= 1`
- `failure_mode_counts.route_unavailable >= 1`
- `failure_mode_counts.route_and_dining_unavailable >= 1`
- `failure_mode_counts.ticket_sold_out_and_bad_weather >= 1`

## 6. Observability

本任务新增的 observability 只限于 benchmark artifact 层，不新增运行时 tracing 或业务日志路径。

必须新增：

- suite report 内 `integrity_coverage_summary`
- suite report 内 `v2_integrity_gate_evaluation`
- `latest-v2_integrity_gate-run-report.json` latest alias

必须保持：

- 现有 report sanitization 规则不变
- 不向 report 暴露 secret、token、authorization、debug trace、traceback 等敏感字段

本任务不要求新增：

- LangSmith metadata
- PostgreSQL benchmark 表结构
- Redis events
- internal API observability surface

## 7. Failure Handling

预期失败模式：

- `v2_integrity` suite 自身 `run_status != "passed"`
- `failed_count != 0`
- `error_count != 0`
- `integrity_coverage_summary` 缺失
- `v2_taxonomy_summary` 缺失
- 任一完整性 coverage 下限不足
- latest alias 无法写入
- suite report 无法 enrich

响应要求：

- gate 失败时返回 `release_blocked=True`
- 将失败原因写入 `blocking_failures`
- 失败时不覆盖已有 latest alias
- enrich 失败要以 gate failure 形式显式暴露，而不是静默吞掉

## 8. Acceptance Criteria

- [ ] `v2_integrity` suite description 和 suite run summary 都包含 additive 的 `integrity_coverage_summary`。
- [ ] `integrity_coverage_summary` 不替换、不修改现有 `matrix_summary`。
- [ ] `integrity_coverage_summary` 不替换、不修改现有 `v2_taxonomy_summary`。
- [ ] 存在独立 `v2_integrity gate`，其执行对象为 `v2_integrity` suite。
- [ ] gate 成功时刷新 `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`。
- [ ] gate 失败时保留已有 latest alias。
- [ ] gate 检查 memory / recovery / continuation / robustness / L4-style 覆盖。
- [ ] `scripts/show_submission_evidence.py` 显示 `v2_integrity_gate` 证据入口。
- [ ] `scripts/demo_preflight.py` 检查新 latest alias。
- [ ] `release_gate_v1` 现有测试和行为不变。
- [ ] `coverage_gate_v1_5` 现有测试和行为不变。
- [ ] 不跟踪 `.env`、API key、token、secret、`var/` 或其他受限产物。

## 9. Verification Commands

```powershell
git status --short
git branch --show-current
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py tests/test_benchmark_coverage_gate.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/integration/test_benchmark_release_gate.py tests/integration/test_benchmark_coverage_gate.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_v2_integrity_gate.py -q
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
git diff --check
git status --short
```

如果实现阶段为了聚焦测试拆分了测试文件名，可以调整命令，但必须覆盖：

- suite summary contract
- gate contract
- latest alias behavior
- old gate non-regression

## 10. Expected Commit

```text
feat: add v2 integrity benchmark gate
```

本次文档任务不应 commit；该 commit message 仅供后续实现任务使用。

## 11. Notes for the Implementer

建议实现顺序：

1. 先补 schema / summary contract
2. 再补 suite-level integrity coverage builder
3. 再实现独立 `v2_integrity gate`
4. 最后接入 evidence / preflight，并回归旧 gate

实现注意点：

- 保持所有新增行为 additive
- 不修改 `backend/app/benchmark/release_gate.py`
- 不修改 `backend/app/benchmark/coverage_gate.py`
- 不修改 `backend/app/benchmark/cases/*.json` 作为默认路径
- 不刷新 `var/` 下 benchmark artifacts

如果实现中发现必须触碰上述边界，应停止并单独说明原因，而不是扩大 scope。

