# Spec: 117 Benchmark Case Matrix Generation v0

## 1. Goal

当前仓库已经通过 Task `116` 把 Mock World scenario taxonomy 收口成稳定的 benchmark baseline：`30` 个 registered cases、`20` 个 `v2_integrity` cases、`8` 个 `recovery_focused` cases，以及与之对应的 suite counts、matrix summary 和 V2 taxonomy summary。现在的主要问题不再是“缺 case”，而是这些 case 的结构事实仍然分散在多个地方手工维护：`fixtures.py` 维护 registered case 顺序，`suites.py` 维护 suite membership，多个测试文件重复维护 case ID 列表与 coverage counts。这个结构会持续放大 drift 风险，也让后续扩展 case matrix 时成本偏高。

本任务的目标是引入一个声明式、可重复、可审计的 benchmark case matrix generation 层，把“场景、约束、失败注入、suite membership”的组合明确编码成单一来源，并从该 matrix 派生 canonical case 顺序与 suite membership。任务完成后，仓库应当能够用同一份 matrix 描述当前 `30` 个 canonical cases 的覆盖面与归属关系，并在不改变现有 benchmark runtime 行为的前提下，为后续新增 case 或扩展 suite 提供稳定生成策略。

## 2. Project Context

这个任务对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M3. Mock World 场景与 benchmark 完整性`，具体就是 roadmap 建议顺序中的下一项：`benchmark case matrix 与 case 生成策略`。

它也直接服务于 `docs/PROJECT_BLUEPRINT.md` 中的这些要求：

- `Benchmark-driven`：benchmark case 结构必须可枚举、可比较、可重复。
- `Deterministic where possible`：case inventory、suite membership、coverage summary 应是确定性的。
- `LocalLife-Bench`：每个 benchmark case 都应明确自身的 scenario、constraints、failure mode、interaction complexity。
- `Small, reviewable tasks`：本任务是 benchmark 结构层的最小可验证收敛单元，不涉及 workflow 或 provider 行为变更。

从当前仓库状态看，M1 评测与观测基础设施已通过近期任务显著收口，M2 前端分离也已完成当前主线切片；Task `116` 刚刚锁定 taxonomy baseline，因此此时进入 Task `117` 是最自然、最小、且风险可控的下一步。

## 3. Requirements

- 必须新增一个声明式 benchmark case matrix 模块，作为当前 `30` 个 canonical benchmark cases 的结构性单一来源。
- matrix 中每一行至少必须显式包含：
  - `case_id`
  - `world_profile`
  - `failure_profile`
  - `suite_ids`
  - `taxonomy`
- matrix 必须能稳定派生当前 canonical registered case 顺序，且顺序与当前 `load_registered_benchmark_cases()` 返回顺序完全一致。
- matrix 必须能稳定派生当前 suite membership，且与当前 baseline 完全一致：
  - `baseline = 6`
  - `expanded = 5`
  - `recovery_focused = 8`
  - `memory_governance = 6`
  - `conversation_continuations = 2`
  - `robustness_focused = 4`
  - `default = 11`
  - `release_gate_v1 = 15`
  - `v2_integrity = 20`
  - `all_registered = 30`
- `backend/app/benchmark/fixtures.py` 不得再手写另一份独立的 registered case ID 列表；它必须复用 matrix 派生结果。
- `backend/app/benchmark/suites.py` 不得再手写另一份独立的 suite case ID 列表；它必须复用 matrix 派生结果。
- `load_registered_benchmark_cases()`、`load_benchmark_suite()`、`list_benchmark_suites()`、`list_benchmark_suite_ids_for_case()` 的公开行为必须保持不变。
- 必须提供一个只读生成入口，用于导出当前 matrix manifest 或某个 suite 的 matrix preview，结果必须可重复、顺序稳定。
- 该导出入口至少必须支持：
  - 导出 `all_registered` 的完整 matrix manifest
  - 导出某个指定 suite 的 case rows
  - 导出 suite count 与 matrix summary 预览
- 必须新增 focused tests，覆盖：
  - matrix row 唯一性
  - case order 稳定性
  - suite membership 派生正确性
  - 与现有 fixture / suite 行为的 parity
  - 导出结果的确定性
- 当前 `BenchmarkCaseMatrixSummary`、`BenchmarkCaseV2MatrixSummary`、`BenchmarkIntegrityCoverageSummary` 的 schema version 与字段结构不得变更。
- 不得新增依赖。
- 不得新增 migration。
- 不得改变 benchmark fixture JSON 的业务内容，除非实现过程中发现某个 fixture 与当前 canonical taxonomy 事实直接矛盾；若出现这种情况，只能做最小修复。

## 4. Non-goals

- 不新增第 `31` 个 benchmark case。
- 不把现有 `backend/app/benchmark/cases/*.json` 改写成完全由代码生成的 payload。
- 不修改 benchmark run report、case report、replay report、recovery review report 的 schema。
- 不改 `release_gate_v1`、`coverage_gate_v1_5`、`v2_integrity_gate`、`safe_stop_gate_v1` 的 gate 逻辑或阈值。
- 不改 workflow、Tool Gateway、memory governance、frontend observability、AMap preview。
- 不提交 `.env`、token、API key、secret、`var/` 产物或本地缓存。

## 5. Interfaces and Contracts

### Inputs

- 一个新的声明式 matrix row 定义集合，代表当前 canonical benchmark inventory。
- 现有 fixture JSON：
  - `backend/app/benchmark/cases/*.json`
- 现有 suite/public helper：
  - `load_registered_benchmark_cases()`
  - `load_benchmark_suite(suite_id)`
  - `list_benchmark_suites()`
  - `list_benchmark_suite_ids_for_case(case_id)`

### Outputs

- 一个确定顺序的 benchmark case matrix manifest。
- 从 matrix 派生的 registered case ID 列表。
- 从 matrix 派生的 suite membership 映射。
- 一个只读导出入口，用于输出 matrix rows 与 suite coverage preview。
- 保持行为不变的现有 benchmark loading APIs。

### Schemas

任务应引入一个结构上足以表达当前 canonical inventory 的 row contract。字段名可以在实现时微调，但能力必须覆盖下面的最小 contract：

```json
{
  "case_id": "family_route_and_dining_unavailable_v1",
  "world_profile": "family_afternoon",
  "failure_profile": "route_and_dining_unavailable_v0",
  "suite_ids": [
    "recovery_focused",
    "v2_integrity",
    "all_registered"
  ],
  "taxonomy": {
    "suite": "locallife_bench_v1",
    "scenario_bucket": "family",
    "level": "L5",
    "tags": [
      "child_friendly",
      "composite_failure",
      "dining_unavailable",
      "failure_injected",
      "route_failure"
    ],
    "failure_mode": "route_and_dining_unavailable"
  }
}
```

导出入口返回的 manifest 至少必须包含以下顶层信息：

```json
{
  "registered_case_count": 30,
  "suite_counts": {
    "baseline": 6,
    "expanded": 5,
    "recovery_focused": 8,
    "memory_governance": 6,
    "conversation_continuations": 2,
    "robustness_focused": 4,
    "default": 11,
    "release_gate_v1": 15,
    "v2_integrity": 20,
    "all_registered": 30
  },
  "cases": [
    {
      "case_id": "family_afternoon_v1",
      "world_profile": "family_afternoon",
      "failure_profile": null,
      "suite_ids": [
        "baseline",
        "default",
        "release_gate_v1",
        "all_registered"
      ]
    }
  ]
}
```

## 6. Observability

这个任务不新增运行时 observability surface，也不新增 report schema。它的可审计性要求体现在静态生成与只读导出层：

- matrix manifest 必须能稳定导出，供人或脚本审阅。
- suite coverage preview 必须能稳定导出，便于检查 drift。
- 若 matrix 与 fixture / suite 事实不一致，错误必须在测试或导出时显式暴露，而不是静默回退。

## 7. Failure Handling

- 如果 matrix 存在重复 `case_id`，实现必须显式失败。
- 如果 matrix row 引用了未知 `suite_id`，实现必须显式失败。
- 如果 matrix 派生出的 registered case 顺序与当前 canonical fixture 顺序不一致，测试必须失败。
- 如果 matrix 派生出的 suite membership 与当前 suite baseline 不一致，测试必须失败。
- 如果某个 matrix row 的 taxonomy 与对应 fixture JSON 的 taxonomy 不一致，测试必须失败。
- 如果导出入口收到未知 `suite_id`，必须返回明确错误，而不是隐式返回空结果。
- 如果实现过程中发现现有 fixture / suite 已经真实漂移，优先修复最靠近 source of truth 的结构层；不得用补丁式测试绕过。

## 8. Acceptance Criteria

- [ ] `docs/specs/117-benchmark-case-matrix-generation-v0.md` 存在并匹配本任务。
- [ ] `docs/plans/117-benchmark-case-matrix-generation-v0-plan.md` 存在并匹配本任务。
- [ ] 仓库中存在一个新的声明式 benchmark case matrix source of truth，覆盖当前 `30` 个 canonical cases。
- [ ] `load_registered_benchmark_cases()` 仍返回当前 canonical `30` 个 case，且顺序不变。
- [ ] `load_benchmark_suite()` 仍返回当前 canonical suite membership，且各 suite counts 不变。
- [ ] `list_benchmark_suites()` 返回的 suite 顺序、suite counts、matrix summary 与当前 baseline 一致。
- [ ] `list_benchmark_suite_ids_for_case()` 的输出与当前 canonical membership 一致。
- [ ] 新增只读导出入口，能稳定导出 `all_registered` matrix manifest 与指定 suite preview。
- [ ] 新增 focused tests，明确覆盖 matrix generation 的唯一性、确定性、parity 与 suite derivation。
- [ ] benchmark runtime 行为未发生非必要变化。
- [ ] 未新增依赖、migration、public API 字段或 report schema version 变更。
- [ ] 没有 `.env`、API key、token 或 secret 被 git 跟踪。
- [ ] `git diff --check` 通过。
- [ ] commit 后工作树干净，除与本任务无关的既有未跟踪本地文件外无残留。

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_case_matrix_generation.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_v2_taxonomy.py -q
python scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json
python scripts/generate_benchmark_case_matrix.py --suite-id v2_integrity --format json
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: generate benchmark cases from taxonomy matrix
```

## 11. Notes for the Implementer

这个任务的关键是“收敛 source of truth”，不是“重写 benchmark 系统”。

建议执行顺序是：

1. 先把当前 `30` 个 case 与 suite membership 抽成 matrix row registry。
2. 再让 `fixtures.py` 与 `suites.py` 从 registry 派生 registered IDs 和 suite IDs。
3. 保持现有 fixture JSON 作为详细 payload source，不要在这个 task 里生成完整 `user_input`、`memory_items`、`expected`、`continuations`。
4. 用 focused parity tests 锁定行为不变。
5. 最后再补导出脚本，避免一开始把任务扩大成新的工具链。

如果实现过程中发现必须改 benchmark gate、workflow、frontend 或 report schema，说明任务切分已经失控，应该停止并回报。
