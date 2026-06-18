# Spec: 116 Mock World Scenario Taxonomy Expansion v0

## 1. Goal

WeekendPilot 的 Mock World 多场景能力已经不再局限于家人主线。当前仓库里已经存在朋友、单人轻度周末、老人同行、雨天备选、预算受限等 profile、benchmark case 和 suite 计数，但这些扩展并没有被一个统一、收口后的 taxonomy 验证面完整锁定。至少有一处聚焦测试仍然保留旧的 `28` / `18` 口径，这会让“当前到底什么才是 canonical Mock World inventory”重新变得模糊。

这个任务的目标不是再新增一轮 profile，而是把已经落地的 Mock World 场景扩展正式收敛成当前仓库的 taxonomy 基线。任务完成后，仓库应当能稳定证明当前 Mock World inventory、suite membership、V2 taxonomy summary 和文档表述是一致的，且不会因为陈旧测试或旧口径描述而回退到家人主线中心的旧状态。

## 2. Project Context

这个任务对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M3. Mock World 多场景覆盖与 benchmark 完整性`。

`docs/PROJECT_BLUEPRINT.md` 要求 WeekendPilot 是 benchmark-driven 的本地生活规划系统，不能长期只围绕 family 主链来定义系统能力。此前相关任务已经分阶段落地了多场景资产：

- Task `049` 扩展了 non-failure Mock World scenario pack
- Task `087` 补齐了 `elder_afternoon` 的 benchmark 覆盖
- Task `110` 把 recovery-focused 与 all_registered inventory 扩展到当前 `30 / 20 / 8` 基线
- Task `115` 刚完成 customer / observability UI 收口，M2 已经不是主阻塞点

因此，下一个最小且合理的任务不是继续做前端或再引入新的 provider，而是把已经存在的 Mock World 多场景覆盖收敛成稳定、可验证、可审计的 taxonomy 基线。

## 3. Requirements

- 任务必须保持当前已经支持的 Mock World profile 集合不变：
  - `family_afternoon`
  - `solo_afternoon`
  - `couple_afternoon`
  - `friends_gathering`
  - `rainy_day_fallback`
  - `budget_lite`
  - `elder_afternoon`

- 任务必须保持当前 canonical benchmark inventory 不变：
  - `load_registered_benchmark_cases()` 仍返回当前 `30` 个 case
  - `load_benchmark_suite("default")` 仍返回当前 `11` 个 case
  - `load_benchmark_suite("expanded")` 仍返回当前 `5` 个 case
  - `load_benchmark_suite("recovery_focused")` 仍返回当前 `8` 个 case
  - `load_benchmark_suite("v2_integrity")` 仍返回当前 `20` 个 case
  - `load_benchmark_suite("all_registered")` 仍返回当前 `30` 个 case

- 任务必须把当前已落地的多场景覆盖作为 source of truth，而不是回退到旧的 `family + solo` 心智模型。
- 任务必须清理 taxonomy 相关测试中的陈旧口径，特别是旧的 `28` / `18` 断言。
- 任务必须补一个 focused taxonomy regression surface，直接证明当前 Mock World 场景扩展已经被仓库显式覆盖，而不是分散隐含在多个大测试文件里。
- 这个 focused regression surface 至少要覆盖：
  - supported profile set
  - registered / default / expanded / recovery / v2_integrity / all_registered suite counts
  - 当前 scenario bucket 分布
  - 当前 world profile 分布
  - 当前 V2 taxonomy summary count

- 如果验证发现当前 profile、fixture、suite membership、taxonomy summary 之间存在真实不一致，任务必须修复最小的 source-of-truth 位置。
- 如果验证发现只是测试或文档保留了陈旧口径，任务必须只修这些 stale consumers，不改 runtime behavior。
- `README.md` 和 `docs/WEB_DEMO_README.md` 中如果仍存在 family-only 或旧 inventory 表述，必须更新到当前 Mock World taxonomy 基线。
- 不得新增依赖。
- 不得新增或修改 Alembic migration。
- 不得修改 public demo API、frontend scenario chip 集合、intent parser、workflow routing、confirmation boundary、recovery policy、benchmark gate policy。

## 4. Non-goals

- 不实现新的 Mock World profile。
- 不新增新的 benchmark case ID。
- 不把 `elder_afternoon` 变成新的 public demo chip。
- 不修改 `release_gate_v1`、`coverage_gate_v1_5`、`v2_integrity_gate`、`safe_stop_gate_v1` 的规则或阈值。
- 不重写 `BenchmarkCaseTaxonomy` 或 `BenchmarkCaseV2Taxonomy` schema。
- 不改 benchmark artifact schema version。
- 不改 AMap preview、memory CRUD、conversation workflow 或 observability UI。
- 不提交 `.env`、token、API key、secret、`var/` 产物或本地缓存。

## 5. Interfaces and Contracts

### Inputs

- `load_mock_world(profile: str = "family_afternoon")`
- `load_registered_benchmark_cases()`
- `load_default_benchmark_cases()`
- `load_benchmark_suite(suite_id)`
- `build_case_matrix_summary(cases)`
- `build_case_v2_matrix_summary(cases)`
- `resolve_benchmark_case_v2_taxonomy(case)`

### Outputs

- 一个与当前仓库事实一致的 Mock World taxonomy regression surface
- 更新后的 taxonomy / suite / docs 断言，统一到当前 `30 / 20 / 8` 基线
- 不改变 runtime benchmark 行为的前提下，清除 stale taxonomy expectations

### Schemas

当前任务不新增 schema。当前 canonical inventory 在实现后应继续满足下列最小 contract：

```json
{
  "registered_case_count": 30,
  "default_case_count": 11,
  "expanded_case_count": 5,
  "recovery_focused_case_count": 8,
  "v2_integrity_case_count": 20,
  "supported_world_profiles": [
    "family_afternoon",
    "solo_afternoon",
    "couple_afternoon",
    "friends_gathering",
    "rainy_day_fallback",
    "budget_lite",
    "elder_afternoon"
  ]
}
```

## 6. Observability

这个任务不新增 observability surface，也不新增 benchmark artifact schema。

它只要求现有 benchmark summary、matrix summary 和 V2 taxonomy summary 的测试与文档表述跟当前仓库事实保持一致。任何修复都必须继续复用现有的：

- `matrix_summary`
- `v2_taxonomy_summary`
- `integrity_coverage_summary`
- suite report
- run report

## 7. Failure Handling

- 如果发现当前 suite 定义和测试断言不一致，优先把 suite 定义视为 source of truth，再修最小的 stale test。
- 如果发现当前 suite 定义本身与 fixture inventory 不一致，必须修 suite source of truth，并补回归测试。
- 如果发现某个当前支持的 Mock World profile 不可加载，必须修复最小 blocking path，并保持 profile ID 不变。
- 如果验证发现当前 docs 已经准确，允许不改 docs，但不得为了“有改动”而做无意义文案重写。
- 如果修复需要扩大到 parser、workflow 或 gate policy，必须停止并报告，因为这已经超出本任务的最小收敛范围。

## 8. Acceptance Criteria

- [ ] `docs/specs/116-mock-world-scenario-taxonomy-v0.md` 存在并匹配本任务。
- [ ] `docs/plans/116-mock-world-scenario-taxonomy-v0-plan.md` 存在并匹配本任务。
- [ ] `load_registered_benchmark_cases()` 仍返回当前 canonical `30` 个 case。
- [ ] `load_benchmark_suite("default")` 仍返回 `11` 个 case。
- [ ] `load_benchmark_suite("expanded")` 仍返回 `5` 个 case。
- [ ] `load_benchmark_suite("recovery_focused")` 仍返回 `8` 个 case。
- [ ] `load_benchmark_suite("v2_integrity")` 仍返回 `20` 个 case。
- [ ] `load_benchmark_suite("all_registered")` 仍返回 `30` 个 case。
- [ ] 所有当前支持的 Mock World profile 仍可通过 loader 成功加载。
- [ ] focused taxonomy regression surface 明确覆盖当前 supported profiles、suite counts 和当前 scenario breadth。
- [ ] taxonomy 相关 focused tests 中不再保留陈旧 `28` / `18` 口径。
- [ ] `README.md` 和 `docs/WEB_DEMO_README.md` 不再与当前 Mock World taxonomy 基线矛盾。
- [ ] runtime benchmark behavior 未发生非必要变化。
- [ ] 未新增依赖、migration、public API 字段或 frontend scenario chip。
- [ ] 没有 `.env`、API key、token 或 secret 被 git 跟踪。
- [ ] `git diff --check` 通过。
- [ ] commit 后工作树干净，除与本任务无关的既有本地未跟踪文件外无残留。

## 9. Verification Commands

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_benchmark_suites.py tests/test_benchmark_v2_taxonomy.py tests/test_benchmark_harness.py -q
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
rg -n "28|18" tests README.md docs/WEB_DEMO_README.md
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: expand mock world scenario taxonomy
```

## 11. Notes for the Implementer

这是一个收敛任务，不是新的大范围功能扩展。

推荐做法是：

1. 先确认当前 suite definitions、fixture inventory 和 README 口径
2. 把当前 `30 / 20 / 8` 作为 canonical baseline
3. 只修 stale tests / stale docs，除非 focused verification 证明 source of truth 本身已经漂移
4. 如需 production code 改动，只改最小 blocking path
5. 不要把任务扩大成新的 scenario 设计、public demo 扩展或 benchmark gate 重写

如果实现过程中发现必须新增 profile、改 parser 或改 gate 阈值，应该立即停下并回报，因为那说明任务切分已经不再是最小可验证单元。
