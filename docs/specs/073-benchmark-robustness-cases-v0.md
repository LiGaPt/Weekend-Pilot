# Spec: 073 Benchmark Robustness Cases v0

## 1. Goal

Task `072` 已经把 6 个 canonical Mock World profiles 扩成了真正带有 distractor、不可用候选和部分缺失 route 的评测基座，但当前 benchmark inventory 仍然只能证明“流程跑通、工具轨迹基本对、安全边界没破”。它还不能正式表达并评分这些更细的 robustness 结论：

- noisy candidate set 下最终是否仍选中了预期 pair
- unavailable top candidate 出现后是否发生了预期 fallback
- search 结果前缀在 deterministic Mock World 下是否仍稳定
- top-3 x top-3 route noise 是否真实进入了 benchmark 证据链

本任务的目标是补一个最小、additive 的 benchmark robustness contract，并基于现有 `072` world 数据新增 4 个 focused Mock World benchmark cases。完成后，reviewer 可以单独运行一个 focused suite，也可以继续运行 `all_registered`，并从标准 benchmark score 里直接看见 robustness 结论，而不是只靠 ad hoc integration test 或手工读 trace。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 WeekendPilot 定义成 benchmark-driven、deterministic-where-possible、observable-by-default 的系统。对 benchmark 而言，这意味着不仅要能跑通 workflow，还要能把 deterministic candidate selection、availability filtering、route feasibility 和 final reviewed plan 是否稳定这些行为固化成可回归验证的 contract。

`docs/NEXT_PHASE_ROADMAP.md` 当前最合理的对应里程碑是 `M3. 多场景与 benchmark 扩展`。`M1. 评测与观测基础设施` 的主干闭环已经基本完成：阶段 timing、matrix summary、outcome rollup、internal review、release gate 和 latency SLO 都已落地并在 2026-05-28 的 release gate 实跑中保持通过。所以下一个最小增量不再是继续补 infra，而是把 `072` 引入的 Mock World robustness 真正收进 benchmark inventory。

本任务直接依赖这些既有边界：

- 继续只用 `mock_world` provider。
- 继续复用 `072` 后的 6 个 world fixtures，不再改 world profile inventory。
- 继续复用现有 benchmark harness、case report、suite report 和 score 机制。
- 继续保持 `default` suite 和 `release_gate_v1` contract 不变。
- 不改 public demo API / frontend contract。

## 3. Requirements

- 为 `BenchmarkExpectedOutcome` 增加一个 additive、可选的 `robustness` expectation block。已有 case 没有这个 block 时，schema 仍然有效，benchmark 行为仍与当前一致。
- 为 benchmark suite catalog 增加一个新的 suite ID：`robustness_focused`。
- 新增且只新增以下 4 个 registered benchmark case：
  - `family_distractor_selection_v1`
  - `friends_distractor_selection_v1`
  - `rainy_day_stable_sorting_v1`
  - `budget_indoor_fallback_v1`
- `load_registered_benchmark_cases()` 必须把这 4 个 case 追加到当前 17-case canonical order 之后，使 registered inventory 变成 21 cases。
- `load_benchmark_suite("robustness_focused")` 必须只返回这 4 个 case，顺序与上面的列表严格一致。
- `all_registered` 必须从当前 17 cases 扩成 21 cases，并把这 4 个 case 追加到尾部。
- `default` suite membership 必须保持 10 cases，不纳入这 4 个新 case。
- `release_gate_v1` membership 必须保持 15 cases，不纳入这 4 个新 case。
- `run_benchmark_release_gate.py` 的 blocking threshold、matrix summary contract、latest alias 语义和 deterministic runtime isolation 必须保持不变。
- robustness grading 必须只使用现有 benchmark 可获得的事实来源：
  - `selected_plan.plan_json`
  - `ToolEvent.request_json`
  - `ToolEvent.response_json`
  - `ToolEvent.status`
- robustness grading 至少必须校验这些维度：
  - expected selected activity ID
  - expected selected dining ID
  - minimum activity search result count
  - minimum dining search result count
  - expected activity search prefix
  - expected dining search prefix
  - required unavailable candidate IDs
  - minimum failed route pair count
- 4 个新 case 的 exact truth set 必须固定为：

```text
family_distractor_selection_v1
  world_profile: family_afternoon
  selected_pair: activity_museum_001 + restaurant_light_001
  minimum_activity_search_results: 5
  minimum_dining_search_results: 5
  expected_activity_search_prefix:
    activity_museum_001
    activity_story_atelier_001
    activity_riverside_reading_001
  expected_dining_search_prefix:
    restaurant_light_001
    restaurant_picnic_001
    restaurant_garden_001
  required_unavailable_candidate_ids:
    activity_story_atelier_001
    restaurant_picnic_001
  minimum_failed_route_pairs: 1

friends_distractor_selection_v1
  world_profile: friends_gathering
  selected_pair: activity_lawn_301 + restaurant_yard_301
  minimum_activity_search_results: 4
  minimum_dining_search_results: 4
  expected_activity_search_prefix:
    activity_lawn_301
    activity_arcade_301
    activity_promenade_301
  expected_dining_search_prefix:
    restaurant_yard_301
    restaurant_patio_301
    restaurant_bistro_301
  required_unavailable_candidate_ids:
    activity_arcade_301
    restaurant_patio_301
  minimum_failed_route_pairs: 1

rainy_day_stable_sorting_v1
  world_profile: rainy_day_fallback
  selected_pair: activity_market_401 + restaurant_soup_401
  minimum_activity_search_results: 4
  minimum_dining_search_results: 4
  expected_activity_search_prefix:
    activity_market_401
    activity_arcade_401
    activity_gardenhall_401
  expected_dining_search_prefix:
    restaurant_soup_401
    restaurant_hotpot_401
    restaurant_cafe_401
  required_unavailable_candidate_ids:
    activity_arcade_401
    restaurant_hotpot_401
  minimum_failed_route_pairs: 1

budget_indoor_fallback_v1
  world_profile: budget_lite
  selected_pair: activity_gallery_501 + restaurant_bento_501
  minimum_activity_search_results: 3
  minimum_dining_search_results: 4
  expected_activity_search_prefix:
    activity_workshop_501
    activity_designmall_501
    activity_gallery_501
  expected_dining_search_prefix:
    restaurant_bento_501
    restaurant_cafe_501
    restaurant_bistro_501
  required_unavailable_candidate_ids:
    activity_workshop_501
    restaurant_cafe_501
  minimum_failed_route_pairs: 1
```

- 这 4 个 case 的 `expected` generic contract 继续沿用现有 non-failure benchmark case 约束：
  - `required_tool_names` 仍为 canonical 8-tool read path
  - `min_tool_event_count >= 8`
  - `min_action_count >= 1`
  - `expected_workflow_status == "completed"`
  - `expected_execution_status == "succeeded"`
  - `expected_feedback_status == "completed"`
- 这 4 个 case 的 taxonomy 必须固定为：

```text
family_distractor_selection_v1
  scenario_bucket: family
  level: L2
  tags:
    child_friendly
    light_meal
    robustness_case
    distractor_selection

friends_distractor_selection_v1
  scenario_bucket: friends
  level: L2
  tags:
    casual_dining
    friends_group
    outdoor_activity
    robustness_case
    distractor_selection

rainy_day_stable_sorting_v1
  scenario_bucket: mixed
  level: L2
  tags:
    rainy_day
    indoor_activity
    robustness_case
    stable_sorting

budget_indoor_fallback_v1
  scenario_bucket: unknown
  level: L2
  tags:
    budget_limited
    indoor_activity
    robustness_case
    fallback_selection
```

- 对这 4 个 case，`BenchmarkHarness.run_case(...)` 的 `scores` 里必须新增一个 `BenchmarkScore`，其 `name` 固定为 `robustness`。
- 对没有 `expected.robustness` 的 legacy cases，不得强制新增 `robustness` score，也不得改变既有 pass/fail 语义。
- `README.md` 必须更新 benchmark suite 列表与说明：
  - suite 数从 8 变 9
  - 新增 `robustness_focused`
  - `all_registered` case count 从 17 变 21
  - `default` 和 `release_gate_v1` count 不变

## 4. Non-goals

- 不实现无关模块。
- 不改动本 spec 未列出的 public interface。
- 不提交 `.env`、API key、token 或任何 secret。
- 不新增真实 provider。
- 不改 public demo API、customer/internal frontend、clarification/replan/plan version/action manifest。
- 不改 `backend/app/providers/mock_world/fixtures/*.json`。
- 不改 `backend/app/providers/mock_world/provider.py`、`backend/app/planning/query_planner.py`、`backend/app/planning/enrichment.py`、`backend/app/planning/itinerary_generation.py`、`backend/app/review/final_review_gate.py` 的业务逻辑。
- 不把这次 task 扩成 `release_gate_v1` suite 扩容任务。
- 不改 `release_gate_v1` threshold、matrix summary contract、artifact latest alias 语义、deterministic runtime isolation 或 `run_benchmark_release_gate.py` 的 gate 规则。
- 不新增新的 benchmark CLI script；继续复用现有 harness 和 scripts。
- 不把当前工作区里不相关的脏文件纳入本 task，例如 `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/V1_DEVELOPMENT_REPORT.md`、`docs/artifacts/`、`qc`。

## 5. Interfaces and Contracts

### Inputs

- `backend/app/benchmark/cases/*.json` fixture payloads
- `BenchmarkExpectedOutcome`
- `BenchmarkHarness.run_case(case)`
- `BenchmarkHarness.run_suite(suite_id)`
- persisted `selected_plan.plan_json`
- persisted `ToolEvent.request_json`
- persisted `ToolEvent.response_json`
- persisted `ToolEvent.status`

### Outputs

- 4 个新的 registered benchmark cases
- 1 个新的 canonical suite：`robustness_focused`
- `all_registered` expanded to 21 cases
- 对 robustness cases 生效的 additive `BenchmarkScore(name="robustness", ...)`
- 不改变 legacy case report / suite report 的顶层 schema

### Schemas

Additive expectation shape:

```json
{
  "expected": {
    "required_tool_names": [
      "search_poi",
      "check_weather",
      "get_poi_detail",
      "check_opening_hours",
      "check_queue",
      "check_table_availability",
      "check_ticket_availability",
      "check_route"
    ],
    "min_tool_event_count": 8,
    "min_action_count": 1,
    "expected_workflow_status": "completed",
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed",
    "robustness": {
      "expected_selected_activity_id": "activity_gallery_501",
      "expected_selected_dining_id": "restaurant_bento_501",
      "minimum_activity_search_results": 3,
      "minimum_dining_search_results": 4,
      "expected_activity_search_prefix": [
        "activity_workshop_501",
        "activity_designmall_501",
        "activity_gallery_501"
      ],
      "expected_dining_search_prefix": [
        "restaurant_bento_501",
        "restaurant_cafe_501",
        "restaurant_bistro_501"
      ],
      "required_unavailable_candidate_ids": [
        "activity_workshop_501",
        "restaurant_cafe_501"
      ],
      "minimum_failed_route_pairs": 1
    }
  }
}
```

Observed robustness score details must at least expose:

```json
{
  "selected_activity_id": "activity_gallery_501",
  "selected_dining_id": "restaurant_bento_501",
  "observed_activity_search_results": [
    "activity_workshop_501",
    "activity_designmall_501",
    "activity_gallery_501"
  ],
  "observed_dining_search_results": [
    "restaurant_bento_501",
    "restaurant_cafe_501",
    "restaurant_bistro_501",
    "restaurant_noodle_501"
  ],
  "observed_unavailable_candidate_ids": [
    "activity_workshop_501",
    "restaurant_cafe_501"
  ],
  "failed_route_pair_count": 7
}
```

Suite contract after this task:

```text
robustness_focused = 4 cases
default = 10 cases (unchanged)
release_gate_v1 = 15 cases (unchanged)
all_registered = 21 cases
```

## 6. Observability

本任务不新增新的 observability endpoint、frontend panel 或 benchmark top-level report schema。

必须复用并扩展现有 benchmark 可观测性：

- per-case `scores[]`
- per-case `run_summary`
- persisted `ToolEvent` rows
- suite-level `matrix_summary`
- suite-level `outcome_rollup`

新增的 robustness 证据只通过现有 `BenchmarkScore.details` 暴露，不新增新的 report top-level block。

## 7. Failure Handling

- 如果 case fixture 带有 `expected.robustness`，但 selected plan 缺失、tool events 缺失、search response 结构异常或无法提取 selected pair，robustness score 必须失败，不能静默跳过。
- 如果 legacy case 没有 `expected.robustness`，benchmark harness 必须继续按当前逻辑运行，不能因为新 contract 而报错。
- 如果新增 case 导致 `default` 或 `release_gate_v1` membership 被意外改动，任务失败。
- 如果新增 case 导致 `run_benchmark_release_gate.py` 不再通过，任务失败；不得通过改 gate 阈值或删 case 来绕过。
- 如果 `run_formal_verification.py` 因新 case 失败，优先修正 case expectation / robustness grader；不得借机修改核心 workflow 或 Mock World fixture 数据。
- 如果实现过程中发现只有继续改 `072` 的 fixture 数据才能让 case 稳定，先停下来报告冲突，而不是扩大范围。

## 8. Acceptance Criteria

- [ ] `docs/specs/073-benchmark-robustness-cases-v0.md` 存在并与本任务一致。
- [ ] `docs/plans/073-benchmark-robustness-cases-v0-plan.md` 存在并与本任务一致。
- [ ] `BenchmarkExpectedOutcome` 新增 additive `robustness` block，legacy cases 继续可加载。
- [ ] `BenchmarkSuiteId` 新增 `robustness_focused`。
- [ ] 新增 4 个 registered case，case ID、taxonomy、truth set 与本 spec 完全一致。
- [ ] `load_registered_benchmark_cases()` 返回 21 cases，且原 17-case 顺序保持不变，新 4 个 case 追加在尾部。
- [ ] `load_benchmark_suite("robustness_focused")` 返回且只返回这 4 个 case。
- [ ] `default` suite 仍然是 10 cases。
- [ ] `release_gate_v1` suite 仍然是 15 cases。
- [ ] `all_registered` suite 变成 21 cases。
- [ ] 4 个 robustness cases 的 `BenchmarkHarness.run_case(...)` 结果里都包含 `BenchmarkScore(name="robustness")`。
- [ ] 4 个 robustness cases 都通过，并且 `robustness` score 为 pass。
- [ ] legacy cases 没有因为本任务而改变既有 pass/fail 语义。
- [ ] `python scripts/run_benchmark_release_gate.py` 仍然通过。
- [ ] `python scripts/run_formal_verification.py` 仍然通过。
- [ ] `README.md` 已更新 suite 列表和 all_registered count。
- [ ] 没有 `.env`、API key、token 或 secret 被 git 跟踪。
- [ ] `git diff --check` 通过。
- [ ] commit 后工作区干净，允许保留本 task 之前就存在的不相关本地脏文件。

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: add benchmark robustness cases
```

## 11. Notes for the Implementer

这个任务的关键不是“多加 4 个 JSON”，而是让这些 JSON 能被 benchmark 正式判分。

因此实现优先级必须是：

1. 先补 additive robustness expectation contract。
2. 再补 robustness grader。
3. 再注册 4 个新 case 和新 suite。
4. 最后再更新 tests 与 README。

不要把这个任务做成新的 world 扩展、release gate 扩容、或 workflow 逻辑改造。`072` 已经把 world 噪声做好；`073` 只负责把这层噪声收进 benchmark contract。
