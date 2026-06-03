# Spec: 088 Customer Demo Multi-Scenario Chinese Display v0

## 1. Goal

WeekendPilot 的 customer-facing Web demo 已经在 Task `086` 公开提供六个 Mock World 场景入口，并在 Task `087` 补齐了 elder benchmark 覆盖；但当前 reviewer 真正看到的 customer thread 仍未完成多场景中文收口。`friends_gathering`、`solo_afternoon`、`couple_afternoon`、`rainy_day_fallback`、`budget_lite` 这五类公开场景仍会暴露英文标题片段、英文地址、英文 route summary、未翻译 tag、未翻译 target id，且后端 itinerary 生成文案仍对所有场景写死为“亲子活动 + 清淡晚餐”。

完成本任务后，customer page 对当前六个公开 Mock World scenario chips 中的五个非亲子 profile，必须在 reviewer 可见层完整显示中文 `title`、`summary`、`tag`、`target/action label`、route/feedback 文案，同时保持现有 public API、six-chip contract、benchmark suite、workflow DAG、confirmation boundary 和 internal observability contract 不变。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 Minimal Web UI 明确定位为 MVP 的主演示路径，并要求系统不仅能“给建议”，还要把规划、确认、执行和反馈的闭环以可演示的方式交付出来。当前 customer page 已经是主要 reviewer surface，因此多场景中文一致性属于产品完成度，而不是前端装饰。

这个任务直接对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M3. 多场景与 benchmark 扩展`。路线图默认强调 `M1. 评测与观测基础设施` 优先，但当前仓库已经拥有足以支持此判断的 M1 基线：spec/plan 已连续到 `087`，latest commit `1e7c361` 与 `087` 对应，release-gate 与 coverage-gate 也已在 README 中可审计。当前更紧急的 gap 已不是再加一层新 infra，而是 Task `086` 已公开的多场景 customer surface 与实际 reviewer 可见输出不一致。

从架构上，这个任务属于：

- Minimal Web UI / customer-safe surface 的 reviewer-facing convergence
- deterministic service layer 的文案收口
- 不改变 bounded multi-agent workflow
- 不改变 Tool Gateway、PostgreSQL、Redis、LangSmith、Action Ledger、Final Review Gate、LocalLife-Bench 的接口边界

## 3. Requirements

- 使用新 task ID `088`。
- 保持 `docs/specs` 与 `docs/plans` 连续且 slug-matched 到 `088`。
- 保持 public API schema 不变：
  - 不修改 `DemoStartRunRequest`
  - 不修改 `DemoRunSummary`
  - 不修改 `DemoPlanPreview`
  - 不新增 public field 用于回传 scenario display profile
- 当前 customer page 的六个公开 Mock World start path 中，下列五个 profile 必须完成 reviewer-visible 中文显示收口：
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
- `backend/app/planning/itinerary_generation.py` 不得再对所有 scenario 输出 family-only 文案。它必须将下列用户可见字段改成场景感知：
  - `draft.summary`
  - `draft.feasibility.reasons`
  - `timeline[activity].notes`
  - `timeline[dining].notes`
- 后端场景 copy 推断必须是内部实现细节，不得新增 public enum。该内部 `display_copy_profile` 必须按如下优先级推断：
  1. `family`
  2. `rainy`
  3. `budget`
  4. `friends`
  5. `couple`
  6. `solo`
  7. `generic`
- `family` 命中条件：
  - `participants.children_ages` 非空，或
  - `constraints.child_friendly == true`
- `rainy` 命中条件：
  - `intent.raw_text` 包含 `雨`、`下雨`、`rain`、`rainy`，或
  - 被选 activity / dining tag 命中 `comfort_food`、`warm_food`、`market`、`nearby`
- `budget` 命中条件：
  - `intent.raw_text` 包含 `预算`、`便宜`、`低价`、`免费`、`budget`、`cheap`、`free`，或
  - 被选 activity / dining tag 命中 `budget_limited`、`free_activity`、`value_set`
- `friends` 命中条件：
  - `intent.scenario_type == "friends"`
- `couple` 命中条件：
  - 无 child signal
  - `participants.adults >= 2`
  - 且 `intent.raw_text` 或被选 pair tag 命中 `伴侣`、`爱人`、`另一半`、`wife`、`husband`、`partner`、`date_friendly`、`couple_friendly`、`gallery`、`citywalk`
- `solo` 命中条件：
  - `intent.scenario_type == "solo"`，或
  - 无 child signal 且 `participants.adults == 1`
- 当前五个非亲子 profile 的场景 copy 模板必须精确采用本 spec `Interfaces and Contracts -> Schemas` 中定义的文本，不留执行时再设计。
- `frontend/src/chat/thread.ts` 必须补齐 customer display-layer 中文映射，覆盖当前五个公开非亲子 fixture 会在 customer thread 中暴露的可见字段：
  - candidate `name`
  - candidate `address`
  - route `summary`
  - feedback `target_label` / `message`
  - tag labels
  - target id labels
- `tagLabel()` 必须覆盖当前五个 fixture 真实输出中的缺失 tag，不允许继续将这些 tag 原样渲染给 reviewer：
  - `hangout`
  - `sports`
  - `casual_dining`
  - `friends_group`
  - `sharing_plates`
  - `slow_service`
  - `couple_friendly`
  - `date_friendly`
  - `casual`
  - `social`
  - `gallery`
  - `light_meal`
  - `family_pause`
  - `comfort_food`
  - `market`
  - `nearby`
  - `warm_food`
  - `restaurant`
  - `budget_limited`
  - `free_activity`
  - `premium`
  - `value_set`
- `actionTargetLabel()` 和 `userFacingText()` 必须保证上述五个 profile 的 pre-confirmation action row、execution/feedback row 不再显示原始 target id 或英文 fallback name/address。
- `ConversationThread` 现有 customer-safe redaction 规则必须保持不变：
  - 不暴露 internal ids
  - 不暴露 action ledger internals
  - 不暴露 trace / session / tool-event internals
- 更新 focused tests：
  - `tests/test_itinerary_generation.py`
  - `tests/integration/test_demo_api_gateway.py`
  - `frontend/src/chat/thread.test.ts`
  - `frontend/src/chat/ConversationThread.test.tsx`
  - `frontend/e2e/demo.spec.ts`
- 更新 `README.md` 和 `docs/WEB_DEMO_README.md` 的 reviewer 文案，使其准确表达“当前六个公开 Mock World start path 中，customer-visible 文案都已中文化”，而不是只强调 family path。
- 不新增依赖。
- 不新增或修改 Alembic migration。
- 不重写五个 mock fixture 的结构；优先通过 display-layer mapping 和最小后端 copy inference 收口。

## 4. Non-goals

- 不新增新的 public scenario chip、public field、public enum、public route。
- 不把 elder 场景加入 customer page。
- 不新增 `ScenarioType = "couple" | "rainy" | "budget"`。
- 不重写 deterministic intent parser、query planner、candidate enrichment 或 workflow DAG。
- 不新增通用 i18n framework、locale switcher 或运行时翻译层。
- 不修改 internal observability UI、internal API、benchmark suite membership、coverage-gate 阈值、release-gate contract。
- 不把所有 backend fixture 数据都改成中文源数据；本任务只收口当前 reviewer 可见 surface。
- 不修改 Action Ledger、confirmation boundary、execution workflow、feedback writer 的业务 contract。
- 不提交 `.env`、API key、token、secret、Playwright artifacts、`frontend/dist/`、`var/` 或其他无关本地产物。

## 5. Interfaces and Contracts

### Inputs

- 现有 public start path：
  - `DemoStartRunRequest.mock_world_profile`
  - `POST /demo/runs`
  - `POST /demo/runs/stream`
- 现有 deterministic itinerary generation:
  - `DeterministicItineraryGenerator.generate(plan, enrichment)`
- 现有 customer thread projection:
  - `frontend/src/chat/thread.ts`
  - `frontend/src/chat/ConversationThread.tsx`
- 当前五个非亲子 fixture 作为 display mapping 的 source of truth：
  - `backend/app/providers/mock_world/fixtures/friends_gathering.json`
  - `backend/app/providers/mock_world/fixtures/solo_afternoon.json`
  - `backend/app/providers/mock_world/fixtures/couple_afternoon.json`
  - `backend/app/providers/mock_world/fixtures/rainy_day_fallback.json`
  - `backend/app/providers/mock_world/fixtures/budget_lite.json`

### Outputs

- Public API shape 不变。
- Internal-only `display_copy_profile` 推断帮助后端生成场景感知文案，但不写入 API。
- Customer thread 对当前五个公开非亲子 profile 的 reviewer-visible 文本全部显示中文。
- Raw target ids、英文 fallback names、英文 route summaries 不再出现在 customer thread 的可见区域。

### Schemas

后端内部场景 copy 推断与模板必须满足：

```json
{
  "display_copy_profile_precedence": [
    "family",
    "rainy",
    "budget",
    "friends",
    "couple",
    "solo",
    "generic"
  ],
  "copy_templates": {
    "family": {
      "summary": "先去{activity}做亲子活动，再去{dining}吃清淡晚餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和票务信息安排亲子活动。",
      "dining_note": "结合清淡偏好、亲子友好度和桌位信息安排晚餐。",
      "reasons": [
        "已选择亲子活动",
        "已选择清淡用餐",
        "活动到餐厅路线已验证"
      ]
    },
    "friends": {
      "summary": "先去{activity}和朋友散步聊天，再去{dining}吃适合分享的轻松晚餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和聚会氛围安排朋友同行活动。",
      "dining_note": "结合分享型用餐、朋友聚会氛围和桌位信息安排晚餐。",
      "reasons": [
        "已选择适合朋友聚会的活动",
        "已选择适合分享的用餐",
        "活动到餐厅路线已验证"
      ]
    },
    "solo": {
      "summary": "先去{activity}一个人轻松逛逛，再去{dining}吃一顿简餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和轻松节奏安排单人活动。",
      "dining_note": "结合简餐偏好、安静程度和桌位信息安排用餐。",
      "reasons": [
        "已选择适合单人放松的活动",
        "已选择轻量简餐",
        "活动到餐厅路线已验证"
      ]
    },
    "couple": {
      "summary": "先去{activity}和伴侣慢慢逛，再去{dining}吃一顿轻松晚餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和两人同行节奏安排活动。",
      "dining_note": "结合约会氛围、轻食偏好和桌位信息安排晚餐。",
      "reasons": [
        "已选择适合两人同行的活动",
        "已选择适合约会节奏的用餐",
        "活动到餐厅路线已验证"
      ]
    },
    "rainy": {
      "summary": "先去{activity}安排室内避雨活动，再去{dining}吃一顿热一点的简餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和室内可行性安排雨天活动。",
      "dining_note": "结合热食偏好、就近便利度和桌位信息安排雨天用餐。",
      "reasons": [
        "已选择雨天可行的室内活动",
        "已选择适合雨天的热食简餐",
        "活动到餐厅路线已验证"
      ]
    },
    "budget": {
      "summary": "先去{activity}安排低预算活动，再去{dining}吃一顿平价简餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和价格友好度安排低预算活动。",
      "dining_note": "结合预算限制、出餐效率和桌位信息安排平价用餐。",
      "reasons": [
        "已选择免费或低价活动",
        "已选择预算友好的用餐",
        "活动到餐厅路线已验证"
      ]
    },
    "generic": {
      "summary": "先去{activity}安排活动，再去{dining}用餐，{route_text}。",
      "activity_note": "根据候选详情、营业时间和可用性安排活动。",
      "dining_note": "结合用餐偏好和桌位信息安排用餐。",
      "reasons": [
        "已选择可行活动",
        "已选择可行用餐",
        "活动到餐厅路线已验证"
      ]
    }
  }
}
```

前端必须覆盖的新增 tag label 精确映射：

```json
{
  "tag_labels": {
    "hangout": "轻松聚会",
    "sports": "轻运动",
    "casual_dining": "轻松用餐",
    "friends_group": "朋友同行",
    "sharing_plates": "适合分享",
    "slow_service": "出餐较慢",
    "couple_friendly": "适合两人同行",
    "date_friendly": "适合约会",
    "casual": "轻松氛围",
    "social": "适合社交",
    "gallery": "画廊",
    "light_meal": "轻食",
    "family_pause": "适合短暂休息",
    "comfort_food": "暖胃热食",
    "market": "市集",
    "nearby": "就近",
    "warm_food": "热食",
    "restaurant": "餐饮",
    "budget_limited": "预算有限",
    "free_activity": "免费活动",
    "premium": "价格偏高",
    "value_set": "平价套餐"
  }
}
```

前端必须覆盖的新增 target id source groups：

```json
{
  "target_id_groups": {
    "solo_afternoon": [
      "activity_gallery_001",
      "activity_walk_001",
      "activity_studio_001",
      "activity_boardgame_001",
      "restaurant_light_001",
      "restaurant_noodle_001",
      "restaurant_counter_001",
      "restaurant_sharedplates_001"
    ],
    "couple_afternoon": [
      "activity_citywalk_201",
      "activity_gallery_201",
      "activity_conservatory_201",
      "activity_courtyard_201",
      "restaurant_light_201",
      "restaurant_bistro_201",
      "restaurant_patio_201",
      "restaurant_sharing_201"
    ],
    "friends_gathering": [
      "activity_lawn_301",
      "activity_sports_301",
      "activity_arcade_301",
      "activity_promenade_301",
      "restaurant_yard_301",
      "restaurant_noodle_301",
      "restaurant_patio_301",
      "restaurant_bistro_301"
    ],
    "rainy_day_fallback": [
      "activity_market_401",
      "activity_booklounge_401",
      "activity_arcade_401",
      "activity_gardenhall_401",
      "restaurant_soup_401",
      "restaurant_rice_401",
      "restaurant_hotpot_401",
      "restaurant_cafe_401"
    ],
    "budget_lite": [
      "activity_park_501",
      "activity_gallery_501",
      "activity_workshop_501",
      "activity_designmall_501",
      "restaurant_bento_501",
      "restaurant_noodle_501",
      "restaurant_cafe_501",
      "restaurant_bistro_501"
    ]
  }
}
```

display mapping 的 source-of-truth scope：

```json
{
  "visible_english_source_files": [
    "backend/app/providers/mock_world/fixtures/friends_gathering.json",
    "backend/app/providers/mock_world/fixtures/solo_afternoon.json",
    "backend/app/providers/mock_world/fixtures/couple_afternoon.json",
    "backend/app/providers/mock_world/fixtures/rainy_day_fallback.json",
    "backend/app/providers/mock_world/fixtures/budget_lite.json"
  ],
  "visible_fields_to_translate": [
    "poi name",
    "poi address",
    "route summary",
    "feedback target label",
    "feedback message"
  ]
}
```

## 6. Observability

本任务不新增 trace schema、Redis event、database 字段或 benchmark artifact 字段。

必须保持不变的部分：

- public `DemoRunSummary` redaction 规则
- internal observability API
- `AgentRun.world_profile`
- benchmark / release / coverage gate contracts
- customer page 的 internal-id hiding 规则

如果需要验证收口是否完成，应依赖现有单测、集成测试和 customer e2e，而不是新增 observability 合同。

## 7. Failure Handling

- 如果后端场景 copy 推断无法明确命中 `family / rainy / budget / friends / couple / solo`，必须回落到 `generic`，而不是继续输出 family-only 文案。
- 如果某个可见英文字符串来自五个 fixture 之一且仍未被 `userFacingText()` 覆盖，必须补映射；不得接受 reviewer 可见英文 fallback 继续存在。
- 如果某个 target id 仍在 pre-confirmation action row、execution row 或 feedback row 可见，必须补 `TARGET_ID_LABELS` 或 candidate-name resolution，不得用 UI 遮盖绕过。
- 如果实施过程中发现必须变更 public API 才能完成任务，应停止并报告；本任务不允许靠扩 public schema 收口。
- 如果某个场景 copy 推断需要重新设计 `ScenarioType` 或 parser 主枚举，应停止并拆 follow-up；本任务只允许最小内部 copy inference。
- 如果文档示例与真实 UI 不一致，必须更新文档，而不是放宽 acceptance。

## 8. Acceptance Criteria

- [ ] 最新完成基线保持为 task `087`，本任务是新的 `088`；`docs/specs` 与 `docs/plans` 在任务完成后连续且 slug-matched 到 `088`。
- [ ] `backend/app/planning/itinerary_generation.py` 不再对 `friends_gathering / solo_afternoon / couple_afternoon / rainy_day_fallback / budget_lite` 输出 family-only `summary / reasons / timeline notes`。
- [ ] 对上述五个 profile，selected plan 的 `summary`、`feasibility.reasons`、activity note、dining note 都是中文且场景语义正确，不再出现 `亲子活动` 或 `清淡晚餐` 的硬编码泄漏。
- [ ] customer thread 对上述五个 profile 的 reviewer 可见区域不再显示当前 fixture 中残留的英文 `name / address / route summary / feedback target text`。
- [ ] `tagLabel()` 覆盖本 spec 列出的 22 个新增 tag，customer thread 不再直接显示这些英文 tag。
- [ ] `actionTargetLabel()` 和相关 feedback 渲染不再对上述五个 profile 显示 raw target id。
- [ ] 现有 public API shape 不变。
- [ ] six-chip customer start path、stream-first start flow、sync fallback、clarify/replan/confirm/decline contract 保持不变。
- [ ] internal observability surface 与 benchmark gates 保持不变。
- [ ] `README.md` 与 `docs/WEB_DEMO_README.md` 已准确表述当前公开多场景 customer surface 的中文化状态。
- [ ] `tests/test_itinerary_generation.py` 通过。
- [ ] `tests/integration/test_demo_api_gateway.py` 的 focused profile assertions 通过。
- [ ] `frontend/src/chat/thread.test.ts` 与 `frontend/src/chat/ConversationThread.test.tsx` 通过。
- [ ] `frontend` build 通过。
- [ ] 现有 desktop smoke 与 mobile no-horizontal-overflow smoke 通过。
- [ ] 没有 `.env`、API key、token 或 secret 被 git 跟踪。
- [ ] 提交后工作树干净。

## 9. Verification Commands

```bash
python -m pytest tests/test_itinerary_generation.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k "mock_world_profile" -q
npm --prefix frontend run test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "friends-group|scenario preset selector"
npm --prefix frontend run e2e -- --project=mobile-chromium --grep "loads the main flow without document-level horizontal overflow"
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
fix: localize multi-scenario customer demo display
```

## 11. Notes for the Implementer

当前仓库的最新 task 是 `087`，spec/plan 连续且最新 commit 对应 `087`，当前分支也是已完成的 `087` 分支。因此本任务必须作为新的 `088` 执行，而不是续做现有分支。

优先策略必须是：

- 后端只做最小内部场景 copy inference
- 前端只做 display-layer mapping 补齐
- 不扩 public contract
- 不扩 benchmark / workflow / parser 主设计

如果实现过程中发现需要：

- 改 public API
- 增加新的 scenario enum
- 重做 fixture 源数据
- 修改 benchmark gate

则应停止并回报，因为那已经超出本任务的 convergence scope。