# Plan: 093 V2 Integrity Matrix Gate v0

## 1. Spec Reference

Spec file:

```text
docs/specs/093-v2-integrity-matrix-gate-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- 当前分支：

```text
codex/pre-confirmation-action-list-upgrade-v0
```

- 当前工作区不干净：
  - `?? docs/superpowers/`
- 该未跟踪目录预计不会阻塞本 task，但实现时必须避免把该目录中的草稿或无关文件混入提交。
- 当前 `v2_integrity` suite 已存在：
  - `backend/app/benchmark/suites.py`
- 当前 `v2_taxonomy_summary` 已存在并接入 suite run summary：
  - `backend/app/benchmark/schemas.py`
  - `backend/app/benchmark/matrix.py`
  - `backend/app/benchmark/harness.py`
- 当前独立正式 gate 只有：
  - `release_gate_v1`
  - `coverage_gate_v1_5`
- 当前 evidence / preflight 只覆盖：
  - `latest-release_gate_v1-run-report.json`
  - `latest-coverage_gate_v1_5-run-report.json`
  - `latest-all_registered-run-report.json`
  - `latest-family_route_failure_v1-review.json`

## 3. Files to Add

- `backend/app/benchmark/v2_integrity_gate.py` - 独立 V2 integrity gate 模块
- `scripts/run_benchmark_v2_integrity_gate.py` - 独立 CLI runner
- `tests/test_benchmark_v2_integrity_gate.py` - gate 单元测试
- `tests/integration/test_benchmark_v2_integrity_gate.py` - gate 集成测试

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - 新增 additive integrity coverage summary schema
- `backend/app/benchmark/matrix.py` - 新增 integrity coverage summary builder
- `backend/app/benchmark/harness.py` - 把 integrity coverage summary 挂到 suite description / run summary
- `backend/app/benchmark/suites.py` - 如果 suite description 需要暴露新 summary，则补齐 wiring
- `backend/app/benchmark/__init__.py` - 导出新 gate 或相关 schema（如有必要）
- `tests/test_benchmark_suites.py` - suite description 新字段与非回归断言
- `tests/test_benchmark_harness.py` - suite run summary 新字段与非回归断言
- `scripts/show_submission_evidence.py` - 纳入 `v2_integrity_gate` evidence entry
- `scripts/demo_preflight.py` - 纳入 `latest-v2_integrity_gate-run-report.json` alias 检查

## 5. Implementation Steps

1. 在 `backend/app/benchmark/schemas.py` 中新增 additive `integrity_coverage_summary` contract。
2. 在 `backend/app/benchmark/matrix.py` 中新增独立 builder，例如 `build_case_integrity_coverage_summary(...)`，只聚合完整性覆盖，不修改现有 `build_case_matrix_summary(...)` 和 `build_case_v2_matrix_summary(...)` 行为。
3. 在 `backend/app/benchmark/harness.py` 中把 `integrity_coverage_summary` 挂到 `BenchmarkSummary`，并按需要挂到 `BenchmarkSuiteDescription`。
4. 先写 `tests/test_benchmark_harness.py` 与 `tests/test_benchmark_suites.py` 的 failing tests，锁定：
   - `v2_integrity` 存在新 summary
   - 旧 `matrix_summary` 和 `v2_taxonomy_summary` 保持不变
   - `release_gate_v1` / `all_registered` / `default` 旧计数不变
5. 新建 `backend/app/benchmark/v2_integrity_gate.py`，复用 `release_gate.py` / `coverage_gate.py` 的模式实现：
   - 独立 result dataclass
   - 运行 `BenchmarkHarness.run_suite("v2_integrity")`
   - 校验 suite pass/fail
   - 校验 integrity coverage minimums
   - enrich suite report
   - 成功时刷新 latest alias
6. 新建 `scripts/run_benchmark_v2_integrity_gate.py` runner。
7. 编写 `tests/test_benchmark_v2_integrity_gate.py`，覆盖：
   - unique run dir
   - latest alias refresh
   - blocked 时不覆盖 alias
   - threshold fail path
   - `main()` exit code / stdout / stderr
8. 编写 `tests/integration/test_benchmark_v2_integrity_gate.py`，覆盖真实 gate 执行与 report payload。
9. 修改 `scripts/show_submission_evidence.py`，新增 `v2_integrity_gate` evidence item。
10. 修改 `scripts/demo_preflight.py`，把新 latest alias 纳入 formal alias checklist。
11. 最后回归旧 gate 相关测试，确认 `release_gate_v1` 与 `coverage_gate_v1_5` 没有行为变化。

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_suites.py`
    - `v2_integrity` suite description 含 integrity coverage summary
    - 旧 suite order 与 membership 不变
  - `tests/test_benchmark_harness.py`
    - `run_suite("v2_integrity")` 结果含 integrity coverage summary
    - `matrix_summary` / `v2_taxonomy_summary` 非回归
  - `tests/test_benchmark_v2_integrity_gate.py`
    - gate result contract
    - latest alias behavior
    - blocking_failures 行为
  - `tests/test_benchmark_release_gate.py`
    - 非回归
  - `tests/test_benchmark_coverage_gate.py`
    - 非回归

- Integration tests:
  - `tests/integration/test_benchmark_v2_integrity_gate.py`
    - 真实 gate execution
    - suite report enrich
    - latest alias refresh
  - `tests/integration/test_benchmark_release_gate.py`
    - 非回归
  - `tests/integration/test_benchmark_coverage_gate.py`
    - 非回归
  - `tests/integration/test_benchmark_harness_gateway.py`
    - `v2_integrity` suite summary 路径非回归

- Smoke tests:
  - `python scripts/run_benchmark_v2_integrity_gate.py`
  - `python scripts/show_submission_evidence.py`
  - `python scripts/demo_preflight.py`

## 7. Verification Commands

```powershell
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
python -m pytest tests/test_benchmark_v2_integrity_gate.py tests/test_benchmark_release_gate.py tests/test_benchmark_coverage_gate.py -q
python -m pytest tests/integration/test_benchmark_v2_integrity_gate.py tests/integration/test_benchmark_release_gate.py tests/integration/test_benchmark_coverage_gate.py tests/integration/test_benchmark_harness_gateway.py -q
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add v2 integrity benchmark gate
```

Expected commands for the later implementation task:

```bash
git status --short
git add docs/specs/093-v2-integrity-matrix-gate-v0.md docs/plans/093-v2-integrity-matrix-gate-v0-plan.md backend/app/benchmark/... scripts/... tests/...
git commit -m "feat: add v2 integrity benchmark gate"
git push
```

本次文档落盘任务不应执行 `git add`、`git commit` 或 `git push`。

## 9. Out-of-scope Changes

- 不修改 `backend/app/benchmark/release_gate.py`
- 不修改 `backend/app/benchmark/coverage_gate.py`
- 不修改 `backend/app/api/observability.py`
- 不修改 `backend/app/benchmark/internal_summary.py`
- 不修改 `backend/app/benchmark/cases/*.json` 作为默认实现路径
- 不刷新 `var/` 下 benchmark artifacts
- 不修改前端、provider、workflow、memory lifecycle 等无关功能
- 不新增 AMap formal benchmark 路径
- 不引入新依赖
- 不提交任何 secret 或生成物

## 10. Review Checklist

- [ ] 实现与 `docs/specs/093-v2-integrity-matrix-gate-v0.md` 一致。
- [ ] `v2_integrity` suite 能输出 additive `integrity_coverage_summary`。
- [ ] `v2_integrity gate` 独立存在，不替代 `release_gate_v1`。
- [ ] `release_gate_v1` 旧测试全部保持通过。
- [ ] `coverage_gate_v1_5` 旧测试全部保持通过。
- [ ] gate 失败时不会覆盖已有 latest alias。
- [ ] evidence / preflight 已接入新 latest alias。
- [ ] 未修改业务代码范围外文件。
- [ ] 未刷新 `var/` 下 benchmark artifact。
- [ ] 未提交 `.env`、token、key、secret、`var/` 等受限内容。

## 11. Handoff Notes

后续实现会话完成后应回报：

- 变更文件清单
- `integrity_coverage_summary` 的最终字段名与挂载位置
- `v2_integrity_gate` 的 latest alias 路径
- 覆盖阈值最终实现值
- 运行过的验证命令及结果
- `release_gate_v1` 与 `coverage_gate_v1_5` 非回归结论
- 是否触碰了任何本计划标记为不应修改的文件

