# Plan: 073 Benchmark Robustness Cases v0

## 1. Spec Reference

Spec file:

```text
docs/specs/073-benchmark-robustness-cases-v0.md
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

- 当前分支是 `codex/mock-world-distractor-expansion-v0`。
- 最新已完成的编号 task 是 `072`。
- `docs/specs/` 和 `docs/plans/` 当前连续且匹配到 `072`。
- 最新 commit 是：

  ```text
  3fd9228 feat: expand mock world distractor coverage
  ```

- 该 commit 与最新 task 对齐，并且当前分支已经跟踪远端同一 commit。
- 2026-05-28 已验证下列事实：
  - `python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/test_benchmark_suites.py -q` 通过
  - `python -m pytest tests/test_benchmark_harness.py -q` 通过
  - `python -m pytest tests/integration/test_candidate_enrichment_gateway.py tests/integration/test_itinerary_generation_gateway.py tests/integration/test_final_review_gate_gateway.py -q` 通过
  - `python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/test_benchmark_release_gate.py tests/test_benchmark_internal_summary.py -q` 通过
  - `python scripts/run_benchmark_release_gate.py` 通过，结果为 `15/15 passed`，`p50=391ms`，`p95=410ms`，`max=410ms`
- 当前工作区存在 pre-existing unrelated dirty files：
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `docs/artifacts/`
  - `qc`
- 这些文件不属于 Task `073`，必须保持 unstaged。
- Task `073` 依赖 `072` 的 fixture 数据。实现会话必须从一个已经包含 `3fd9228` 的基线开始：
  - 如果 `072` 还没 merge 到 `main`，就从当前 `072` head 创建新分支。
  - 如果 `072` 已经 merge 到 `main`，就从包含该 merge 的最新 `main` 创建新分支。
- 当前 canonical benchmark inventory 是 17 cases、8 suites，其中：
  - `default` = 10 cases
  - `release_gate_v1` = 15 cases
  - `all_registered` = 17 cases
- Task `073` 只允许新增：
  - 4 个 new registered cases
  - 1 个 new suite `robustness_focused`
- Task `073` 不允许修改：
  - Mock World fixture payloads
  - `default` suite membership
  - `release_gate_v1` suite membership
  - release gate threshold / artifact semantics

## 3. Files to Add

- `backend/app/benchmark/cases/family_distractor_selection_v1.json` - family noisy-candidate robustness case with fixed selected pair and unavailable-candidate evidence.
- `backend/app/benchmark/cases/friends_distractor_selection_v1.json` - friends outdoor robustness case with group-friendly winner under noisy activity/dining candidates.
- `backend/app/benchmark/cases/rainy_day_stable_sorting_v1.json` - rainy-day indoor stable-sorting case using noisy top-3 activity and dining results.
- `backend/app/benchmark/cases/budget_indoor_fallback_v1.json` - budget indoor fallback case where the top matched activity is unavailable and the final pair falls back deterministically.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add additive `BenchmarkRobustnessExpectation` model, wire it into `BenchmarkExpectedOutcome`, and add `robustness_focused` to `BenchmarkSuiteId`.
- `backend/app/benchmark/graders.py` - add `grade_robustness_expectation(...)` and helper extractors for selected pair, search result prefixes, unavailable candidate IDs, and failed route count.
- `backend/app/benchmark/harness.py` - call the robustness grader when `case.expected.robustness` is present, without changing legacy scoring behavior.
- `backend/app/benchmark/fixtures.py` - append the 4 new case IDs to `_REGISTERED_CASE_IDS`.
- `backend/app/benchmark/suites.py` - define `_ROBUSTNESS_FOCUSED_CASE_IDS`, add `robustness_focused` to suite order and suite definitions, and append the new case IDs only to `_ALL_REGISTERED_CASE_IDS`.
- `tests/test_benchmark_suites.py` - update registered case order, canonical suite list, new suite metadata, and `all_registered` counts.
- `tests/test_benchmark_harness.py` - add unit tests for robustness grading and update suite / matrix summary expectations.
- `tests/integration/test_benchmark_harness_gateway.py` - add case-level gateway integration assertions for the 4 new robustness cases and suite-level assertions for `robustness_focused`.
- `README.md` - update benchmark suite documentation and inventory counts.

## 5. Implementation Steps

1. 先把 4 个新 case 的 canonical truth set 固化成测试常量，避免实现时 case truth 漂移。

   使用这一组固定 truth set：

   ```text
   family_distractor_selection_v1
     prompt: This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.
     world_profile: family_afternoon
     selected_pair: activity_museum_001 + restaurant_light_001
     counts: activity>=5, dining>=5
     activity_prefix: activity_museum_001, activity_story_atelier_001, activity_riverside_reading_001
     dining_prefix: restaurant_light_001, restaurant_picnic_001, restaurant_garden_001
     unavailable_ids: activity_story_atelier_001, restaurant_picnic_001
     failed_route_pairs>=1
     taxonomy: family / L2 / child_friendly, light_meal, robustness_case, distractor_selection

   friends_distractor_selection_v1
     prompt: This afternoon I want to hang out with friends nearby for a few hours, keep the activity outdoors first, and then find a casual dinner place for sharing.
     world_profile: friends_gathering
     selected_pair: activity_lawn_301 + restaurant_yard_301
     counts: activity>=4, dining>=4
     activity_prefix: activity_lawn_301, activity_arcade_301, activity_promenade_301
     dining_prefix: restaurant_yard_301, restaurant_patio_301, restaurant_bistro_301
     unavailable_ids: activity_arcade_301, restaurant_patio_301
     failed_route_pairs>=1
     taxonomy: friends / L2 / casual_dining, friends_group, outdoor_activity, robustness_case, distractor_selection

   rainy_day_stable_sorting_v1
     prompt: This afternoon I want to go out with a friend for a few hours, not too far, but since it is rainy please keep the plan indoor with a nearby warm meal.
     world_profile: rainy_day_fallback
     selected_pair: activity_market_401 + restaurant_soup_401
     counts: activity>=4, dining>=4
     activity_prefix: activity_market_401, activity_arcade_401, activity_gardenhall_401
     dining_prefix: restaurant_soup_401, restaurant_hotpot_401, restaurant_cafe_401
     unavailable_ids: activity_arcade_401, restaurant_hotpot_401
     failed_route_pairs>=1
     taxonomy: mixed / L2 / rainy_day, indoor_activity, robustness_case, stable_sorting

   budget_indoor_fallback_v1
     prompt: This afternoon I want a nearby indoor activity and a quick low-cost meal after that.
     world_profile: budget_lite
     selected_pair: activity_gallery_501 + restaurant_bento_501
     counts: activity>=3, dining>=4
     activity_prefix: activity_workshop_501, activity_designmall_501, activity_gallery_501
     dining_prefix: restaurant_bento_501, restaurant_cafe_501, restaurant_bistro_501
     unavailable_ids: activity_workshop_501, restaurant_cafe_501
     failed_route_pairs>=1
     taxonomy: unknown / L2 / budget_limited, indoor_activity, robustness_case, fallback_selection
   ```

2. 先从 test constants 开始，锁定 suite membership 和 inventory 变化。

   在 `tests/test_benchmark_suites.py` 和 `tests/test_benchmark_harness.py` 先更新这些固定结果：

   - registered case count: `17 -> 21`
   - canonical suite count: `8 -> 9`
   - new suite: `robustness_focused`
   - `default`: 仍是 `10`
   - `release_gate_v1`: 仍是 `15`
   - `all_registered`: `17 -> 21`

   新 suite 的固定 matrix summary：

   ```text
   scenario_bucket_counts = {"family": 1, "friends": 1, "mixed": 1, "unknown": 1}
   level_counts = {"L2": 4}
   tool_profile_counts = {"mock_world": 4}
   world_profile_counts = {
     "family_afternoon": 1,
     "friends_gathering": 1,
     "rainy_day_fallback": 1,
     "budget_lite": 1
   }
   failure_mode_counts = {"none": 4}
   tag_counts = {
     "budget_limited": 1,
     "casual_dining": 1,
     "child_friendly": 1,
     "distractor_selection": 2,
     "fallback_selection": 1,
     "friends_group": 1,
     "indoor_activity": 2,
     "light_meal": 1,
     "outdoor_activity": 1,
     "rainy_day": 1,
     "robustness_case": 4,
     "stable_sorting": 1
   }
   ```

3. 扩展 benchmark schema，但保持完全 additive。

   在 `backend/app/benchmark/schemas.py`：

   - 为 `BenchmarkSuiteId` 加入 `robustness_focused`
   - 新增 `BenchmarkRobustnessExpectation` model
   - 在 `BenchmarkExpectedOutcome` 中新增可选字段 `robustness: BenchmarkRobustnessExpectation | None = None`

   `BenchmarkRobustnessExpectation` 的字段固定为：

   ```text
   expected_selected_activity_id: str
   expected_selected_dining_id: str
   minimum_activity_search_results: int
   minimum_dining_search_results: int
   expected_activity_search_prefix: list[str]
   expected_dining_search_prefix: list[str]
   required_unavailable_candidate_ids: list[str]
   minimum_failed_route_pairs: int
   ```

   不要改已有 `memory_governance` 或 `conversation` expectation contract。

4. 新建 4 个 case JSON，全部复用现有 non-failure benchmark 结构。

   每个 case 都要包含：

   - canonical `required_tool_names`
   - `min_tool_event_count = 8`
   - `min_action_count = 1`
   - `expected_workflow_status = "completed"`
   - `expected_execution_status = "succeeded"`
   - `expected_feedback_status = "completed"`
   - 新增 `expected.robustness`
   - 固定 taxonomy 与 metadata focus

   不要给这 4 个 case 增加 `failure_profile`、`continuations`、`memory_governance` 或 `conversation` expectation。

5. 注册 cases 和 suite，但严格控制 membership 范围。

   在 `backend/app/benchmark/fixtures.py`：

   - 仅把 4 个新 case ID 追加到 `_REGISTERED_CASE_IDS` 尾部
   - 原前 17 个 case 的顺序不动

   在 `backend/app/benchmark/suites.py`：

   - 新增 `_ROBUSTNESS_FOCUSED_CASE_IDS`
   - 在 `_ORDERED_SUITE_IDS` 中插入 `robustness_focused`
   - 在 `_SUITE_DEFINITIONS` 中补充 `robustness_focused` 的 title / description / case_ids
   - `_ALL_REGISTERED_CASE_IDS` 追加这 4 个 case
   - `_DEFAULT_CASE_IDS` 不变
   - `_RELEASE_GATE_V1_CASE_IDS` 不变

6. 实现 robustness grader，使用现有 selected plan 和 tool events，不新增 workflow metadata。

   在 `backend/app/benchmark/graders.py` 新增 `grade_robustness_expectation(case, selected_plan, tool_events)`，按下面规则实现：

   - selected pair:
     - 从 `selected_plan.plan_json["draft"]["activity"]["candidate_id"]` 和 `["draft"]["dining"]["candidate_id"]` 读取
   - search results:
     - 找出 `tool_name == "search_poi"` 的 tool events
     - 用 `event.request_json["payload"]["category"]` 区分 `activity` 和 `dining`
     - 从 `event.response_json["results"]` 提取 `poi_id`
   - unavailable candidate IDs:
     - `check_ticket_availability.response_json["ticket_availability"]["available"] == false`
     - 或 `check_table_availability.response_json["table_availability"]["available"] == false`
     - 或 `check_queue.response_json["queue"]["status"] != "open"`
   - failed route pair count:
     - 统计 `tool_name == "check_route"` 且 `status not in {"succeeded", "cached"}` 的 tool events 数量

   grader 必须返回：

   - `BenchmarkScore.name == "robustness"`
   - `passed = True` 仅当所有 robustness assertions 都满足
   - `details` 至少包含：
     - `selected_activity_id`
     - `selected_dining_id`
     - `observed_activity_search_results`
     - `observed_dining_search_results`
     - `observed_unavailable_candidate_ids`
     - `failed_route_pair_count`

7. 把 robustness grader 接到 harness，但只在 case 声明了 robustness expectation 时启用。

   在 `backend/app/benchmark/harness.py`：

   - `_run_legacy_case` 中，在已有 score 列表里，`grade_plan_quality(...)` 之后追加 `grade_robustness_expectation(...)`，前提是 `case.expected.robustness is not None`
   - `_run_continuation_case` 也按同样条件接入，保持 contract 通用；当前 4 个新 case 不使用 continuation，但实现不要写成 legacy-only dead end
   - legacy cases 没有 `expected.robustness` 时，score list 保持当前逻辑

8. 更新单测，先验证 contract，再验证 counts。

   在 `tests/test_benchmark_harness.py`：

   - 新增 `grade_robustness_expectation` 的 pass case
   - 新增 `grade_robustness_expectation` 的 fail case
   - 更新 `ALL_REGISTERED_*` counts 到 21-case inventory
   - 增加 `robustness_focused` suite 的 matrix summary 断言

   在 `tests/test_benchmark_suites.py`：

   - 更新 `REGISTERED_CASE_IDS`
   - 增加 `ROBUSTNESS_FOCUSED_CASE_IDS`
   - 更新 `CANONICAL_SUITE_IDS`
   - 增加 `robustness_focused` membership 和 description assertions
   - 更新 `all_registered` expected order
   - 更新 new suite / all_registered matrix summary constants

9. 更新 gateway integration tests，确认不是只在纯单测对象上成立。

   在 `tests/integration/test_benchmark_harness_gateway.py`：

   - 对 4 个新 case 参数化 `BenchmarkHarness.run_case(...)`
   - 断言每个 case：
     - `result.status == "passed"`
     - `result.taxonomy` 与 case taxonomy 一致
     - `result.scores` 里恰好有一个 `name == "robustness"` 的 score
     - `robustness` score `passed is True`
     - `robustness.details.selected_activity_id` / `selected_dining_id` 与 truth set 一致
     - search result prefix 和 unavailable candidate IDs 与 truth set 一致
     - `failed_route_pair_count >= 1`
   - 新增 `BenchmarkHarness.run_suite("robustness_focused")` 集成断言：
     - `suite_id == "robustness_focused"`
     - `case_count == 4`
     - `passed_count == 4`
     - matrix summary 与 step 2 的固定值一致
   - 现有 `release_gate_v1` 和 `all_registered` assertions 保持，但把 `all_registered` case count / matrix counts 更新到 21-case inventory
   - `release_gate_v1` case count 仍必须是 15

10. 更新 README，只写 benchmark inventory 变化，不扩展到 UI 或 provider 叙述。

   在 `README.md` 的 LocalLife-Bench 段落：

   - suite 数从 8 改为 9
   - 新增 `robustness_focused`
   - `all_registered` 从 17 cases 改为 21 cases
   - 明确说明 robustness cases 是基于 `072` 的 expanded Mock World，用于验证 noisy candidate selection / fallback / stable ordering
   - 明确说明 `default` 和 `release_gate_v1` 不受影响

11. 按固定顺序验证，先轻后重，避免把 release gate 当成第一道反馈。

   必须按这个顺序执行：

   1. `python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q`
   2. `docker compose up -d postgres redis`
   3. `python -m alembic upgrade head`
   4. `python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/test_benchmark_release_gate.py tests/test_benchmark_internal_summary.py -q`
   5. `python scripts/run_benchmark_release_gate.py`
   6. `python scripts/run_formal_verification.py`
   7. `git diff --check`
   8. `git status --short`

12. 如果 release gate 或 formal verification 失败，处理原则固定。

   - 不改 `release_gate_v1` membership
   - 不改 latency SLO
   - 不删新 case 来“恢复绿色”
   - 优先修 robustness grader、case truth 或 suite wiring
   - 如果失败必须回到 Mock World fixture 才能解决，就停止并报告冲突

13. 只 stage Task `073` 相关文件。

   不要 stage：

   - `.gitignore`
   - `docs/COMPETITION_SUBMISSION_DESIGN.md`
   - `docs/TASK_WORKFLOW_PROMPTS.md`
   - `docs/V1_DEVELOPMENT_REPORT.md`
   - `docs/artifacts/`
   - `qc`
   - `var/` 下运行生成物

## 6. Testing Plan

- Unit tests: `tests/test_benchmark_suites.py` 校验 21-case registered inventory、9-suite catalog、`robustness_focused` membership、`all_registered` counts。
- Unit tests: `tests/test_benchmark_harness.py` 校验 additive robustness schema、robustness grader pass/fail、new suite matrix summary、legacy score behavior unchanged。
- Integration tests: `tests/integration/test_benchmark_harness_gateway.py` 参数化 4 个新 case，验证真实 workflow + tool events + selected plan 下 robustness score 正确生成。
- Integration tests: 同文件新增 `run_suite("robustness_focused")` 断言，并更新 `all_registered` suite 断言到 21 cases。
- Regression tests: `tests/test_benchmark_release_gate.py` 和 `tests/test_benchmark_internal_summary.py` 继续保持 release gate unchanged contract。
- Smoke tests: `python scripts/run_benchmark_release_gate.py` 继续通过。
- Smoke tests: `python scripts/run_formal_verification.py` 在 expanded `all_registered` 21-case inventory 下继续通过。

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/test_benchmark_release_gate.py tests/test_benchmark_internal_summary.py -q
python scripts/run_benchmark_release_gate.py
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark robustness cases
```

Expected commands:

```bash
git status --short
git branch --show-current
git log --oneline -n 1
git switch -c codex/benchmark-robustness-cases-v0
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/graders.py
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/suites.py
git add backend/app/benchmark/cases/family_distractor_selection_v1.json
git add backend/app/benchmark/cases/friends_distractor_selection_v1.json
git add backend/app/benchmark/cases/rainy_day_stable_sorting_v1.json
git add backend/app/benchmark/cases/budget_indoor_fallback_v1.json
git add tests/test_benchmark_suites.py
git add tests/test_benchmark_harness.py
git add tests/integration/test_benchmark_harness_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: add benchmark robustness cases"
git push -u origin codex/benchmark-robustness-cases-v0
```

The implementer must confirm the branch base already contains `3fd9228` or the merge commit that brought `072` into the chosen base branch. The implementer must also confirm unrelated local docs, `docs/artifacts/`, `qc`, and runtime `var/` outputs are not staged.

## 9. Out-of-scope Changes

- 不修改 `backend/app/providers/mock_world/fixtures/*.json`。
- 不修改 `backend/app/providers/mock_world/provider.py`。
- 不修改 planner / enrichment / itinerary / final review 的业务逻辑。
- 不把 4 个新 robustness cases 加进 `default`。
- 不把 4 个新 robustness cases 加进 `release_gate_v1`。
- 不修改 `run_benchmark_release_gate.py`、`run_formal_verification.py` 的 contract。
- 不新增 benchmark CLI script。
- 不修改 public demo API、frontend、customer/internal surfaces。
- 不提交 generated caches、virtualenv、`var/` artifacts、`docs/artifacts/` 或任何 secret。

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] 新增的 4 个 case ID、prompt、taxonomy、truth set 与 spec 完全一致。
- [ ] `BenchmarkExpectedOutcome.robustness` 是 additive contract，legacy cases 仍能加载。
- [ ] `robustness_focused` suite 已加入 canonical suite catalog。
- [ ] `default` 仍是 10 cases。
- [ ] `release_gate_v1` 仍是 15 cases。
- [ ] `all_registered` 已扩成 21 cases。
- [ ] 4 个新 case 的 `BenchmarkHarness.run_case(...)` 都产生 `robustness` score，且该 score 通过。
- [ ] 4 个新 case 的 selected pair 与 spec truth set 完全一致。
- [ ] `release_gate_v1` 继续通过。
- [ ] `all_registered` formal verification 继续通过。
- [ ] README 的 suite 列表和 counts 已同步更新。
- [ ] 任务范围没有扩展到 world fixture 或 workflow logic 改造。
- [ ] 必要测试和命令都已执行通过。
- [ ] `git diff --check` 通过。
- [ ] Git status 在 commit 后干净，排除 pre-existing unrelated local files。
- [ ] Commit message 与 plan 一致。
- [ ] Push 成功。
- [ ] 没有 `.env`、API key、token 或 secret 被提交。

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- 新增的 4 个 case 文件路径。
- 修改过的 benchmark schema / grader / harness / suite / test 文件列表。
- `robustness_focused` suite 的最终 case IDs 和 matrix summary。
- `all_registered` 的最终 case count。
- 4 个新 case 的最终 selected pair、search prefix、unavailable candidate IDs、failed route pair count。
- `run_benchmark_release_gate.py` 的结果。
- `run_formal_verification.py` 的结果。
- 运行过的 verification commands 与结果。
- commit hash。
- push 结果。
- 是否发现必须另拆 task 的 follow-up gap。
