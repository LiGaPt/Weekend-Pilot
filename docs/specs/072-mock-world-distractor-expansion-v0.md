# Spec: 072 Mock World Distractor Expansion v0

## 1. Goal

WeekendPilot 现在已经有 6 个稳定可跑的 Mock World profile 和 17 个已注册 benchmark case，但现有世界数据仍然明显偏“干净”。`family_afternoon` 只有 3 个 activity 和 3 个 dining，另外 5 个 world 都只有 2 个 activity 和 2 个 dining。结果是当前 deterministic query planner、candidate enrichment、route pairing、itinerary ranking、final review 虽然都有代码路径，但在 canonical Mock World 下几乎总是直接命中为 case 量身准备的候选，缺少真实噪声。

本任务不是继续扩 scenario family，也不是继续扩 suite catalog。本任务是在现有 6 个 world 里补一层小而确定的 distractor density：低质量但可用候选、不可用候选、跨场景候选，以及至少一部分不可路由 pair。完成后，现有 canonical 非失败 benchmark case 仍然要产出当前的 canonical first draft pair，但这个结果必须是在更宽的检索集、更脏的 top-3 enrichment 窗口和更真实的 route/filter 条件下得到的。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 WeekendPilot 定义成 benchmark-driven、deterministic-where-possible、observable-by-default 的本地生活规划系统。蓝图还明确要求 pre-flight availability 要先过滤 closed / full / unavailable POI，再做 plan generation，最终通过 final review 保证候选 ID、route 和 confirmation boundary 都可验证。

`docs/NEXT_PHASE_ROADMAP.md` 里默认优先的是 `M1. 评测与观测基础设施`，但当前仓库实际上已经把 M1 和 M2 的主要收口任务做完了：阶段 timing、suite summary、internal review、surface separation、release gate、latency SLO 都已落地。当前更合理的下一阶段是 `M3. 多场景与 benchmark 扩展`，而且不是继续做更大的 scenario family，而是先把已经存在的 6 个 world 变成真正能压测 retrieval / filtering / ranking / final review 的评测基座。

这个 task 直接依赖并约束这些现有边界：

- `MockWorldProvider.search_poi(...)` 继续使用 deterministic `sort_order`。
- `DeterministicQueryPlanner` 继续使用当前的 query / tags 组合，不新增 parser 或 planner 逻辑。
- `CandidateEnricher` 继续只 enrich top-3 activity 和 top-3 dining candidates，并构建 route matrix。
- `DeterministicItineraryGenerator` 继续通过 availability、queue、route 和原始 candidate index 排序 pair。
- `FinalReviewGate` 继续只验证 enriched evidence、route evidence、timeline 和 confirmation safety。
- `BenchmarkCase` inventory、suite catalog、`release_gate_v1` 阈值和 public demo contract 都保持不变。

## 3. Requirements

- 保持现有支持的 Mock World profile 集不变：
  - `family_afternoon`
  - `solo_afternoon`
  - `couple_afternoon`
  - `friends_gathering`
  - `rainy_day_fallback`
  - `budget_lite`
- `load_mock_world()` 的默认值仍然必须是 `family_afternoon`。
- 不新增 world profile，不删除 profile，不重命名 profile。
- 只在现有 6 个 fixture 文件内做数据扩展，不新增第 7 个 fixture 文件。
- 每个 world 都必须新增正好 2 个 activity POI 和 2 个 dining POI。
- 不允许删除或重命名当前 canonical first-draft pair 使用的既有 POI ID。
- 所有扩展后的 fixture 仍然必须通过当前 `_validate_world(...)` 校验，保留现有顶层结构、唯一 POI ID、routes、weather、queues、table_availability、ticket_availability、addons。

- 对下列 6 个 canonical 非失败 case/world truth set，执行当前 `DeterministicIntentParser -> DeterministicQueryPlanner(provider_profile="mock_world") -> QueryPlanExecutor.execute_initial_calls(...)` 后，必须至少收集到 `4` 个 activity candidates 和 `4` 个 dining candidates：
  - `family_afternoon_v1 -> family_afternoon`
  - `solo_afternoon_v1 -> solo_afternoon`
  - `couple_afternoon_v1 -> couple_afternoon`
  - `friends_gathering_v1 -> friends_gathering`
  - `rainy_day_fallback_v1 -> rainy_day_fallback`
  - `budget_lite_v1 -> budget_lite`

- 每个 world 的新增 distractor 必须同时覆盖这三类意图：
  - 低质量但仍可用的候选：会被检索到，也能通过基础可用性检查，但通过现有 `sort_order`、tags、description、queue/table/ticket evidence、route evidence 看起来明显弱于 canonical pair。
  - 不可用候选：会被检索到，并进入 top-3 enrichment 窗口，但会因为 `ticket_availability.available = false`、`table_availability.available = false` 且无 open queue、或 `queue.status != "open"` 而失去可用性。
  - 跨场景候选：会被检索到，但 persona / constraint fit 明显偏向别的 scenario family，不能取代当前 world 的 canonical 好 pair。

- 每个 world 的 top-3 activity candidates 与 top-3 dining candidates 之间，必须至少存在 1 个 non-usable route pair。
- 这里的 non-usable route pair 可以通过以下任一方式实现：
  - top-3 x top-3 组合里缺少 walking route，导致 `check_route` 失败
  - route response 不可用，导致该 pair 不进入 usable route set
- 与此相对，当前 canonical pair 的 walking route 必须继续存在且可用。

- 当前 canonical first draft pair 必须保持不变。`DeterministicItineraryGenerator().generate(...)` 的 `drafts[0]` 仍必须是下面的映射：
  - `family_afternoon_v1 -> activity_museum_001 + restaurant_light_001`
  - `solo_afternoon_v1 -> activity_gallery_001 + restaurant_light_001`
  - `couple_afternoon_v1 -> activity_citywalk_201 + restaurant_light_201`
  - `friends_gathering_v1 -> activity_lawn_301 + restaurant_yard_301`
  - `rainy_day_fallback_v1 -> activity_market_401 + restaurant_soup_401`
  - `budget_lite_v1 -> activity_park_501 + restaurant_bento_501`

- 对上面的 6 个 case/world truth set，`FinalReviewGate().review(...)` 仍必须返回：
  - `decision in {"approved", "approved_with_warnings"}`
  - `safe_to_present = true`

- 不允许改变以下 inventory / contract：
  - benchmark case IDs
  - benchmark taxonomy
  - benchmark suite IDs
  - suite membership
  - `release_gate_v1` blocking threshold
  - `MockWorldProvider` public tool names
  - `WeekendPilotWorkflowRequest.world_profile` public literal set
  - public demo API / frontend contract

- 默认实现策略必须是 fixture-first。
- 不允许主动修改下列逻辑实现：
  - `backend/app/providers/mock_world/provider.py`
  - `backend/app/planning/query_planner.py`
  - `backend/app/planning/enrichment.py`
  - `backend/app/planning/itinerary_generation.py`
  - `backend/app/review/final_review_gate.py`
- 只有在 focused test 证明 fixture-only 无法满足本 spec 时，才允许最小化逻辑补丁；一旦出现这种情况，实施会话必须先停止并报告冲突，而不是静默扩大任务范围。

- 必须补足或增强直接验证本任务目标的测试：
  - fixture / provider search breadth and order
  - candidate enrichment gateway behavior under noisy top-3 windows
  - itinerary generation under distractors
  - final review safety under distractors
  - benchmark / release-gate regression

- `README.md` 必须补一段简短说明：
  - canonical Mock World 仍然是 benchmark 默认 provider
  - 6 个现有 world 现在故意包含 distractor / unavailable candidates
  - 目标是让 screening 和 ranking 路径被真实 exercise，而不是改变 public demo contract

## 4. Non-goals

- 不实现无关模块。
- 不改动本 spec 未列出的 public interface。
- 不提交 `.env`、API key、token 或任何 secret。
- 不新增 benchmark case。
- 不新增 benchmark suite。
- 不新增 `elder`、多代同行、雨天以外的新 scenario family。
- 不改 parser、intent schema、memory policy、query planner search limit、candidate enricher max limits、itinerary generator ranking policy、final review rule 集。
- 不改 clarification、replan、plan version、action manifest、execution workflow、recovery policy、observability API、frontend 页面。
- 不改 `release_gate_v1` 阈值、matrix summary 规则、suite membership 或 deterministic runtime isolation。
- 不把这个任务扩成性能优化任务。
- 不把当前工作区里不相关的脏文件纳入本 task，例如 `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/V1_DEVELOPMENT_REPORT.md`、`docs/artifacts/`、`qc`。

## 5. Interfaces and Contracts

### Inputs

- `load_mock_world(profile: str = "family_afternoon") -> dict`
- `build_mock_world_registry(profile: str = "family_afternoon") -> ToolRegistry`
- `DeterministicIntentParser().parse(user_input) -> LocalLifeIntent`
- `DeterministicQueryPlanner().build(intent, provider_profile="mock_world") -> QueryPlan`
- `QueryPlanExecutor.execute_initial_calls(plan, run_id) -> CandidateCollectionResult`
- `CandidateEnricher.enrich(plan, collection) -> CandidateEnrichmentResult`
- `DeterministicItineraryGenerator().generate(plan, enrichment) -> ItineraryDraftResult`
- `FinalReviewGate().review(plan, enrichment, drafts) -> FinalReviewResult`
- Canonical benchmark case fixtures:
  - `family_afternoon_v1`
  - `solo_afternoon_v1`
  - `couple_afternoon_v1`
  - `friends_gathering_v1`
  - `rainy_day_fallback_v1`
  - `budget_lite_v1`

### Outputs

- 同一组 6 个 Mock World profile，数据更宽、更脏，但 public profile ID 不变。
- 同一组 canonical benchmark case/world 映射，不新增 case、不改 suite。
- 更宽的初始 candidate collection。
- 含有 unusable candidate 和 failed route pair 的 top-3 enrichment 窗口。
- 与当前一致的 canonical `drafts[0]` pair。
- 继续可安全展示的 final review 结果。

### Schemas

Canonical truth matrix for this task:

```text
family_afternoon_v1 -> family_afternoon -> activity_museum_001 + restaurant_light_001
solo_afternoon_v1 -> solo_afternoon -> activity_gallery_001 + restaurant_light_001
couple_afternoon_v1 -> couple_afternoon -> activity_citywalk_201 + restaurant_light_201
friends_gathering_v1 -> friends_gathering -> activity_lawn_301 + restaurant_yard_301
rainy_day_fallback_v1 -> rainy_day_fallback -> activity_market_401 + restaurant_soup_401
budget_lite_v1 -> budget_lite -> activity_park_501 + restaurant_bento_501
```

Example fixture addition shape:

```json
{
  "poi_id": "activity_example_999",
  "name": "Example Distractor",
  "category": "activity",
  "address": "Example Address",
  "tags": ["child_friendly", "indoor", "quiet"],
  "description": "Usable but weaker than the canonical activity.",
  "sort_order": 25
}
```

Example unusable evidence shape:

```json
{
  "activity_example_999": {
    "poi_id": "activity_example_999",
    "available": false,
    "time_slots": [],
    "remaining": 0
  }
}
```

Notes:

- 不新增 schema family。
- 不新增 top-level fixture keys。
- 可继续使用现有 POI payload 的自由文本字段和 tag 组合来表达跨场景或低质量语义。

## 6. Observability

本任务不新增 observability surface。

必须继续复用现有可观测性证据：

- `tool_events`
- `CandidateEnrichmentResult.failed_tool_results`
- `CandidateEnrichmentResult.route_matrix`
- `ItineraryDraftResult.drafts`
- `FinalReviewResult`
- benchmark case / suite reports
- `release_gate_v1` report

不得新增：

- 新的 LangSmith metadata family
- 新的 internal observability endpoint
- 新的 frontend observability panel
- 新的 benchmark summary schema

如果 README 更新涉及说明，也只说明现有可观测性如何验证 distractor 行为，不扩展新的存储结构。

## 7. Failure Handling

- 如果任何一个扩展后的 fixture 失去 loader 兼容性，继续沿用当前 `MockWorldError` 失败行为，不要静默容错。
- 如果某个 world 在当前 parser + query planner 语义下仍然收不到至少 `4` 个 activity 和 `4` 个 dining candidates，任务失败；不要通过改 parser / planner 来规避。
- 如果 distractor 扩展导致 canonical `drafts[0]` pair 变化，任务失败；优先调整 fixture 的 `sort_order`、availability、route coverage，而不是改 ranking 代码。
- 如果 final review 对 canonical case 开始阻塞展示，任务失败；优先调整 fixture evidence，而不是放松 final review 规则。
- 如果扩展后 `default` / `release_gate_v1` benchmark 回归失败，不允许改 suite membership、taxonomy 或 threshold；优先缩小或重排 distractor 数据。
- 如果扩展后的数据让 `release_gate_v1` latency SLO 超标，不允许放宽 `071` 的阈值；必须把性能影响视为后续独立任务。
- PostgreSQL / Redis 不可用时，现有 gateway / benchmark 集成验证仍可按当前方式失败，不新增 fallback。

## 8. Acceptance Criteria

- [ ] `docs/specs/072-mock-world-distractor-expansion-v0.md` 存在并与本任务一致。
- [ ] `docs/plans/072-mock-world-distractor-expansion-v0-plan.md` 存在并与本任务一致。
- [ ] `docs/specs/` 与 `docs/plans/` 在实现后继续连续且一一匹配到 `072`。
- [ ] 6 个既有 Mock World fixture 文件都完成 distractor 扩展并继续通过 loader 校验。
- [ ] 对 6 个 canonical 非失败 case/world truth set，初始 search collection 都至少包含 `4` 个 activity candidates 和 `4` 个 dining candidates。
- [ ] 对 6 个 canonical 非失败 case/world truth set，top-3 enrichment 窗口里都能观察到至少 1 个 unusable candidate signal。
- [ ] 对 6 个 canonical 非失败 case/world truth set，top-3 x top-3 route matrix 里都能观察到至少 1 个 non-usable route pair。
- [ ] 6 个 canonical 非失败 case/world truth set 的 `drafts[0]` pair 仍然严格匹配本 spec 列出的 canonical mapping。
- [ ] 6 个 canonical 非失败 case/world truth set 的 final review 仍然 `safe_to_present = true`。
- [ ] benchmark case inventory、taxonomy、suite IDs、suite membership、`release_gate_v1` 阈值都保持不变。
- [ ] `release_gate_v1` 仍然可以在现有仓库环境中通过。
- [ ] 没有新增 world profile、benchmark case、benchmark suite、public API field 或 frontend contract change。
- [ ] 除非出现明确定义的 blocker，否则不修改 query planner / enrichment / itinerary / final review 逻辑代码。
- [ ] `README.md` 更新了 Mock World distractor hardening 的简短说明。
- [ ] 没有 `.env`、API key、token 或 secret 被 git 跟踪。
- [ ] `git diff --check` 通过。
- [ ] commit 后工作区干净，允许保留本 task 之前就存在的不相关本地脏文件。

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: expand mock world distractor coverage
```

## 11. Notes for the Implementer

这是一个 fixture-first benchmark-hardening task，不是算法改造 task。

实施时应把下列 truth set 当成不可漂移的行为契约：

- 6 个既有 world profile 不变
- 6 个 canonical 非失败 case/world mapping 不变
- 6 个 canonical first draft pair 不变
- benchmark inventory / suite catalog / release gate contract 不变

最优先的杠杆应该是：

- `sort_order`
- 现有 tags / description
- ticket / queue / table availability
- route coverage

不应该先动代码。

如果你发现只有改 planner / generator / final review 逻辑才能满足这些要求，不要继续扩大实现范围；先停下来报告冲突。
