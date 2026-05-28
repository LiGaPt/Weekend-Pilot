# Plan: 072 Mock World Distractor Expansion v0

## 1. Spec Reference

Spec file:

```text
docs/specs/072-mock-world-distractor-expansion-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- 当前分支是 `codex/release-gate-latency-slo-v0`。
- 最新已完成编号 task 是 `071`。
- 最新 commit 是：

  ```text
  bdf64fd feat: add release gate latency slo
  ```

- 这个 commit 直接更新了 `docs/specs/071-release-gate-latency-slo-v0.md`、`docs/plans/071-release-gate-latency-slo-v0-plan.md`、对应实现和测试，所以最新 commit 与最新 task 对齐。
- `docs/specs/` 和 `docs/plans/` 当前连续且匹配到 `071`。
- 当前工作区没有新的编号 spec / plan 要优先续做。
- 当前脏工作树是非本 task 文件：
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `docs/artifacts/`
  - `qc`
- 这些文件不属于 Task `072`，必须保持 unstaged。
- 当前支持的 Mock World profile 仍然只有 6 个：
  - `family_afternoon`
  - `solo_afternoon`
  - `couple_afternoon`
  - `friends_gathering`
  - `rainy_day_fallback`
  - `budget_lite`
- 当前 POI 密度偏低：
  - `family_afternoon` 只有 `3 activity + 3 dining + 1 addon`
  - 其余 5 个 world 都只有 `2 activity + 2 dining`
- 当前 canonical first-draft pair 基线是：
  - `family_afternoon_v1 -> activity_museum_001 + restaurant_light_001`
  - `solo_afternoon_v1 -> activity_gallery_001 + restaurant_light_001`
  - `couple_afternoon_v1 -> activity_citywalk_201 + restaurant_light_201`
  - `friends_gathering_v1 -> activity_lawn_301 + restaurant_yard_301`
  - `rainy_day_fallback_v1 -> activity_market_401 + restaurant_soup_401`
  - `budget_lite_v1 -> activity_park_501 + restaurant_bento_501`
- 当前候选链和 benchmark 的只读验证是绿的：
  - `python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_query_plan_execution.py tests/test_candidate_enrichment.py tests/test_final_review_gate.py -q`
  - `python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/test_benchmark_release_gate.py tests/test_benchmark_internal_summary.py -q`
- 当前 benchmark inventory 是 17 cases，`release_gate_v1` 是 15 cases，`all_registered` 是 17 cases；这个 task 不能改这些 counts。

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/providers/mock_world/fixtures/family_afternoon.json` - 为 family world 增加 2 个 activity distractor 和 2 个 dining distractor。
- `backend/app/providers/mock_world/fixtures/solo_afternoon.json` - 为 solo world 增加 2 个 activity distractor 和 2 个 dining distractor。
- `backend/app/providers/mock_world/fixtures/couple_afternoon.json` - 为 couple world 增加 2 个 activity distractor 和 2 个 dining distractor。
- `backend/app/providers/mock_world/fixtures/friends_gathering.json` - 为 friends world 增加 2 个 activity distractor 和 2 个 dining distractor。
- `backend/app/providers/mock_world/fixtures/rainy_day_fallback.json` - 为 rainy-day world 增加 2 个 activity distractor 和 2 个 dining distractor。
- `backend/app/providers/mock_world/fixtures/budget_lite.json` - 为 budget-lite world 增加 2 个 activity distractor 和 2 个 dining distractor。
- `tests/test_mock_world_loader.py` - 增加每个 profile 的最小 activity/dining candidate 密度断言。
- `tests/test_mock_world_provider.py` - 增加 per-profile search breadth / deterministic order 回归断言。
- `tests/integration/test_candidate_enrichment_gateway.py` - 参数化 6 个 canonical case/world，对 noisy top-3 enrichment 做真实 gateway 验证。
- `tests/integration/test_itinerary_generation_gateway.py` - 参数化 6 个 canonical case/world，锁定 `drafts[0]` canonical pair 不变。
- `tests/integration/test_final_review_gate_gateway.py` - 参数化 6 个 canonical case/world，确认 distractor 条件下 final review 仍安全通过。
- `README.md` - 增加 Mock World distractor hardening 的简短说明。

## 5. Implementation Steps

1. 先把 6 个 canonical truth set 固化成测试常量，避免 fixture 改动后测试语义漂移。

   在相关测试文件里复用同一组映射：

   ```text
   family_afternoon_v1 -> family_afternoon -> activity_museum_001 + restaurant_light_001
   solo_afternoon_v1 -> solo_afternoon -> activity_gallery_001 + restaurant_light_001
   couple_afternoon_v1 -> couple_afternoon -> activity_citywalk_201 + restaurant_light_201
   friends_gathering_v1 -> friends_gathering -> activity_lawn_301 + restaurant_yard_301
   rainy_day_fallback_v1 -> rainy_day_fallback -> activity_market_401 + restaurant_soup_401
   budget_lite_v1 -> budget_lite -> activity_park_501 + restaurant_bento_501
   ```

   不要新造 prompt truth source。优先直接复用 canonical benchmark case ID 和其 `world_profile`。

2. 按“每个 world 固定加 2 个 activity + 2 个 dining”扩展 6 个 fixture。

   所有世界都遵守这几个共同规则：

   - 现有 canonical POI ID 不动。
   - canonical activity 的排序优势不变。
   - canonical dining 的排序优势和可用性优势不变。
   - 新增 1 个“可用但较差”的 activity distractor。
   - 新增 1 个“不可用或不可路由”的 activity distractor。
   - 新增 1 个“可用但较差”的 dining distractor。
   - 新增 1 个“不可用”的 dining distractor。
   - 至少让一个新 distractor 进入 top-3 enrichment window。
   - 至少让 top-3 x top-3 route matrix 里出现一个 non-usable pair。
   - 只用现有字段表达差异：`sort_order`、`tags`、`description`、`routes`、`queues`、`table_availability`、`ticket_availability`。

3. 对 6 个 world 用统一的排序布局，避免实现会话自由发挥。

   使用下面的排序策略：

   - 保留现有 canonical activity / dining 的 `sort_order` 不变。
   - 新增的“不可用 distractor”放在当前 canonical 后、但尽量进入 top-3。
   - 新增的“可用但较差 distractor”放在当前 canonical 好候选之后，但仍在前 4 或前 5。
   - family world 现有是 `3 + 3`，扩展后应变成 `5 activity + 5 dining`。
   - 其他 5 个 worlds 现有是 `2 + 2`，扩展后应变成 `4 activity + 4 dining`。

4. 用每个 world 的既有 scenario 语义来定义 distractor 类型，不新增 parser 能力。

   具体要求如下：

   - `family_afternoon`
     - activity: 保留 `activity_museum_001` 为最优；新增一个 child-friendly 但 `ticket_availability.available=false` 的 distractor；新增一个可用但更偏 quiet/citywalk/couple 风格的 cross-scene distractor。
     - dining: 保留 `restaurant_light_001` 为最优；新增一个 child-friendly + lighter-options 但 `table_availability.available=false` 且 queue 不可用的 distractor；新增一个 child-friendly + lighter-options 但更弱的 usable distractor。
   - `solo_afternoon`
     - activity: 保留 `activity_gallery_001` 为最优；新增一个更偏 family/friends 的 usable distractor；新增一个 sold-out 或 closed 的 distractor。
     - dining: 保留 `restaurant_light_001` 为最优；新增一个 usable 但更偏 casual/group 的 distractor；新增一个 unavailable dining distractor。
   - `couple_afternoon`
     - activity: 保留 `activity_citywalk_201` 为最优；新增一个 family-leaning quiet indoor distractor；新增一个不可用的 date-style distractor。
     - dining: 保留 `restaurant_light_201` 为最优；新增一个 friends-group 或 casual sharing usable distractor；新增一个 lighter-options 但不可预订且无 open queue 的 distractor。
   - `friends_gathering`
     - activity: 保留 `activity_lawn_301` 为最优；新增一个 quiet/couple-style usable distractor；新增一个不可用 group activity distractor。
     - dining: 保留 `restaurant_yard_301` 为最优；新增一个 quiet/date-style usable distractor；新增一个 queue 风险高或不可用的 distractor。
   - `rainy_day_fallback`
     - activity: 保留 `activity_market_401` 为最优；新增一个 weather-misaligned outdoor usable distractor；新增一个 indoor 但 ticket unavailable 的 distractor。
     - dining: 保留 `restaurant_soup_401` 为最优；新增一个 usable 但更弱的 warm-food distractor；新增一个 nearby 但 unavailable 的 distractor。
   - `budget_lite`
     - activity: 保留 `activity_park_501` 为最优；新增一个更贵但 usable 的 distractor；新增一个低价但 unavailable 的 distractor。
     - dining: 保留 `restaurant_bento_501` 为最优；新增一个更贵但 usable 的 distractor；新增一个 budget-ish 但 unavailable 的 distractor。

5. 更新 routes、queues、table availability、ticket availability 时只做支持性补丁，不动 canonical 成功链。

   具体执行规则：

   - canonical pair 的 route 继续存在。
   - canonical pair 的 queue / table / ticket 继续可用。
   - 至少制造一个 top-3 x top-3 组合缺少 usable walking route。
   - 不要把所有 distractor 都做成完全不可路由；至少保留一部分“可用但较差”候选，确保排序逻辑仍被 exercise，而不只是纯过滤。

6. 更新 `tests/test_mock_world_loader.py`，把 fixture 密度约束变成仓库规则。

   增加参数化断言：

   - family world 至少 `5 activity` 和 `5 dining`
   - 其他 5 个 worlds 至少 `4 activity` 和 `4 dining`
   - 所有新增 POI ID 仍唯一
   - 所有 profile 仍然能 `load_mock_world(profile)` 成功

7. 更新 `tests/test_mock_world_provider.py`，锁定 provider 级检索广度与排序。

   增加 per-profile 参数化测试，使用真实 provider：

   - `search_poi({"category": "activity"})` 返回扩展后的 deterministic 顺序
   - `search_poi({"category": "dining"})` 返回扩展后的 deterministic 顺序
   - 第一名 activity 和第一名 dining 仍是 canonical winners
   - family world 的无过滤 category search 至少返回 5 个 activity 和 5 个 dining
   - 其余 5 个 worlds 的无过滤 category search 至少返回 4 个 activity 和 4 个 dining

   不要删除现有 family-focused exact assertions；如果 exact list 需要扩展，就直接扩成新的列表。

8. 强化 `tests/integration/test_candidate_enrichment_gateway.py`，把 noisy top-3 窗口跑通真实 gateway。

   参数化 6 个 canonical case/world：

   - 根据 case 的 `world_profile` 创建 run 和 registry。
   - 使用 case 的 `user_input` 走现有 parser + planner + executor。
   - 断言 `len(collection.activity_candidates)` 和 `len(collection.dining_candidates)` 达到 spec 最低值。
   - 断言 enrichment 的 top activity / dining 中至少有一个 unusable signal：
     - activity `ticket_availability.available is False`
     - 或 dining `table_availability.available is False` 且 queue 不可用
   - 断言 `route_matrix` 中至少有一个条目 `status not in {"succeeded", "cached"}` 或带 `error_json`。
   - 同时断言 canonical pair 对应的 route 仍存在 usable entry。

9. 强化 `tests/integration/test_itinerary_generation_gateway.py`，把排序结果锁成 canonical first draft。

   对同一组 6 个 case/world：

   - 复用真实 gateway enrichment 结果。
   - 断言 `result.drafts` 非空。
   - 断言 `result.drafts[0].activity.candidate_id` 和 `result.drafts[0].dining.candidate_id` 精确匹配 canonical mapping。
   - 断言 `result.drafts[0].feasibility.is_feasible is True`。
   - 断言 proposed actions 仍全部 `requires_confirmation=True`，没有 execution fields。
   - 断言 route matrix 不止一个组合，避免测试退化回单一路径。

10. 强化 `tests/integration/test_final_review_gate_gateway.py`，确认 distractor 条件下 final review 不回退成 blocked。

    对同一组 6 个 case/world：

    - 在调用 review 前先检查 `drafts[0]` pair 仍是 canonical mapping。
    - 调用 `FinalReviewGate().review(...)`。
    - 断言 `decision in {"approved", "approved_with_warnings"}`。
    - 断言 `safe_to_present is True`。
    - 断言至少有一个 reviewed draft `safe_to_present is True`。
    - 不把 test 目标扩大成检查文案或全部 warnings 内容；只锁安全性与 canonical pair 稳定性。

11. 更新 `README.md`，只补足本 task 的真实变化。

    在 Mock World / benchmark 相关段落里增加 2 到 4 句：

    - Mock World 仍是 canonical benchmark provider。
    - 6 个已支持 worlds 现在故意包含 distractor / unavailable candidates。
    - 目标是 exercise retrieval、screening、ranking、final review，而不是改变 public world profile 或 suite catalog。

12. 不改 benchmark inventory 和 suite catalog。

    明确保持这些文件不变：

    - `backend/app/benchmark/fixtures.py`
    - `backend/app/benchmark/suites.py`

    除非实现过程证明测试辅助必须读取这些文件；那也只是 inspect，不是 modify。

13. 按固定顺序做验证，避免先跑重集成再发现 provider 层断言没收紧。

    顺序必须是：

    1. `tests/test_mock_world_loader.py` + `tests/test_mock_world_provider.py`
    2. `tests/test_benchmark_harness.py` + `tests/test_benchmark_suites.py`
    3. `docker compose up -d postgres redis`
    4. `python -m alembic upgrade head`
    5. gateway integration tests
    6. `python scripts/run_benchmark_release_gate.py`
    7. `git diff --check`
    8. `git status --short`

14. 如果 `release_gate_v1` 失败，处理原则固定。

    - 不修改 `071` 的 latency threshold。
    - 不修改 suite membership。
    - 优先减少 distractor 数量之外的“额外组合爆炸”。
    - 如果需要更大的数据规模优化，作为后续独立 task，不在本 task 里继续扩大。

15. 只 stage 本 task 相关文件。

    不要 stage：

    - `.gitignore`
    - `docs/COMPETITION_SUBMISSION_DESIGN.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/V1_DEVELOPMENT_REPORT.md`
    - `docs/artifacts/`
    - `qc`
    - `var/` 下运行生成物

## 6. Testing Plan

- Unit tests: `tests/test_mock_world_loader.py` 校验 6 个 profile 的最小 candidate 密度和 fixture 可加载性。
- Unit tests: `tests/test_mock_world_provider.py` 校验 per-profile activity / dining search breadth 与 deterministic ordering。
- Unit tests: `tests/test_benchmark_harness.py` 和 `tests/test_benchmark_suites.py` 只做 benchmark inventory / suite regression，不新增 suite 语义。
- Integration tests: `tests/integration/test_candidate_enrichment_gateway.py` 参数化 6 个 canonical case/world，验证 noisy top-3 enrichment、unusable candidate signal 和 failed route pair。
- Integration tests: `tests/integration/test_itinerary_generation_gateway.py` 参数化 6 个 canonical case/world，锁定 `drafts[0]` canonical pair。
- Integration tests: `tests/integration/test_final_review_gate_gateway.py` 参数化 6 个 canonical case/world，验证 final review 继续安全通过。
- Smoke tests: `python scripts/run_benchmark_release_gate.py` 继续通过。
- Regression boundary: 不改 benchmark case IDs、suite IDs、public demo contract、release gate threshold。

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py -q
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_mock_world_gateway.py tests/integration/test_candidate_enrichment_gateway.py tests/integration/test_itinerary_generation_gateway.py tests/integration/test_final_review_gate_gateway.py tests/integration/test_benchmark_harness_gateway.py -q
python scripts/run_benchmark_release_gate.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: expand mock world distractor coverage
```

Expected commands:

```bash
git status --short
git switch -c codex/mock-world-distractor-expansion-v0
git add backend/app/providers/mock_world/fixtures/family_afternoon.json
git add backend/app/providers/mock_world/fixtures/solo_afternoon.json
git add backend/app/providers/mock_world/fixtures/couple_afternoon.json
git add backend/app/providers/mock_world/fixtures/friends_gathering.json
git add backend/app/providers/mock_world/fixtures/rainy_day_fallback.json
git add backend/app/providers/mock_world/fixtures/budget_lite.json
git add tests/test_mock_world_loader.py
git add tests/test_mock_world_provider.py
git add tests/integration/test_candidate_enrichment_gateway.py
git add tests/integration/test_itinerary_generation_gateway.py
git add tests/integration/test_final_review_gate_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: expand mock world distractor coverage"
git push -u origin codex/mock-world-distractor-expansion-v0
```

The implementer must confirm `.env`, secrets, unrelated local docs, `docs/artifacts/`, `qc`, and runtime `var/` outputs are not staged.

## 9. Out-of-scope Changes

- 不新增 world profile。
- 不新增 benchmark case。
- 不新增 benchmark suite。
- 不改 `backend/app/benchmark/fixtures.py` 或 `backend/app/benchmark/suites.py` 的 inventory / suite membership。
- 不改 parser、query planner、candidate enricher、itinerary generator、final review gate 的业务逻辑，除非遇到 spec 明确允许先报告的 blocker。
- 不改 demo route、frontend、clarification、replan、plan version、action manifest、execution workflow、memory governance、observability API。
- 不改 `release_gate_v1` threshold、deterministic runtime isolation、formal verification 脚本。
- 不提交 generated caches、virtualenv、`var/` artifacts、`docs/artifacts/`、或任何 secret。

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] 6 个既有 Mock World fixture 都新增了 2 个 activity 和 2 个 dining distractor。
- [ ] canonical 6-case truth set 仍然映射到相同的 `drafts[0]` pair。
- [ ] 每个 canonical case/world 的初始搜索至少拿到 `4` 个 activity 和 `4` 个 dining candidates。
- [ ] 每个 canonical case/world 的 top-3 enrichment 窗口里都出现了 unusable candidate signal。
- [ ] 每个 canonical case/world 的 top-3 x top-3 route matrix 里都出现了 non-usable route pair。
- [ ] `FinalReviewGate` 在 distractor 条件下仍然 `safe_to_present = true`。
- [ ] benchmark inventory、suite membership、release gate threshold 都没有变化。
- [ ] `python scripts/run_benchmark_release_gate.py` 仍然通过。
- [ ] `README.md` 已更新 Mock World distractor hardening 的简短说明。
- [ ] 任务范围没有扩展到 parser/planner/review 逻辑重写。
- [ ] 必要测试和命令都已执行通过。
- [ ] `git diff --check` 通过。
- [ ] Git status 在 commit 后干净，排除 pre-existing unrelated local files。
- [ ] Commit message 与 plan 一致。
- [ ] Push 成功。
- [ ] 没有 `.env`、API key、token 或 secret 被提交。

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- 修改的 fixture 文件和测试文件列表。
- 每个 canonical case/world 的最终 candidate counts：
  - activity count
  - dining count
- 每个 canonical case/world 的 `drafts[0]` pair。
- 每个 canonical case/world 是否观察到 unusable candidate signal 和 failed route pair。
- release gate 验证结果。
- 运行过的 verification commands 与结果。
- commit hash。
- push 结果。
- 是否出现需要独立拆出的性能 follow-up。
