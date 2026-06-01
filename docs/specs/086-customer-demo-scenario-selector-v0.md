# Spec: 086 Customer Demo Scenario Selector v0

## 1. Goal

为 customer-facing Web demo 增加一个显式、可点击、可验证的 Mock World 场景选择器，让评审不再只能依赖自由输入 prompt 才能触达已经存在的多场景资产。

完成后，`http://127.0.0.1:5173/` 的 customer page 必须在 start 场景下提供六个明确入口：亲子、朋友、单人、情侣、雨天、预算。点击任一入口后，前端要填充对应的 canonical prompt，并在启动 `POST /demo/runs/stream` / sync fallback 时携带显式 `mock_world_profile`，从而稳定命中对应的 Mock World fixture，而不是继续依赖模糊文本启发式。这个任务只收口 start path 的场景入口能力，不扩展 follow-up API、AMap UI、benchmark 结构或 workflow 语义。

## 2. Project Context

这个任务直接对应 `docs/PROJECT_BLUEPRINT.md` 中 V1 的多场景目标，也对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M3. 多场景与 benchmark 扩展`。路线图已经明确指出系统不应只在亲子场景上“表现得好看”，而仓库当前也已经具备这项任务所需的大部分前置资产：

- Task `049` 已经扩展出 `family_afternoon`、`friends_gathering`、`solo_afternoon`、`couple_afternoon`、`rainy_day_fallback`、`budget_lite` 六个 Mock World profile。
- Task `064` 已经把朋友场景打通到公共 demo start path。
- Task `077` 已经把 customer surface 改成 chat-first。
- Tasks `082` 到 `085` 已经把 start path 切到 stream-first，并补了 sync fallback。

因此当前最小缺口已经不是再做新的 M1 基础设施，而是把现成的多场景能力收口到公共 customer 入口。当前仓库里 `frontend/src/styles.css` 已经存在 `.example-chip-row` / `.example-chip`，`docs/WEB_DEMO_README.md` 也已经把 example-entry strip 写进了 reviewer runbook，但当前 `frontend/src/App.tsx` 并没有把这个入口真正渲染出来。这使得当前最合理的下一 task 是一个小而清晰的 M3 convergence slice：补齐 customer demo 的显式场景入口，并让它对既有 Mock World profile 稳定生效。

## 3. Requirements

- 使用新的 task ID `086`。
- 保持 `docs/specs` 与 `docs/plans` 的编号连续性。
- 在 customer page 的 `start` composer 模式下渲染一个 Mock World 场景入口 chip row。
- 这个 chip row 必须使用六个且仅六个入口，顺序必须固定为：
  - `亲子`
  - `朋友`
  - `单人`
  - `情侣`
  - `雨天`
  - `预算`
- 每个入口都必须映射到一个显式的 `mock_world_profile` 和一个固定 prompt，精确矩阵见本 spec 的 `Interfaces and Contracts -> Schemas`。
- 点击某个未选中的 chip 时，前端必须：
  - 将主输入框内容替换为该入口的固定 prompt
  - 将本地选中的 `mock_world_profile` 设为该入口对应值
  - 显示该 chip 的选中态
- 点击当前已选中的 chip 时，前端必须：
  - 清除本地选中的 `mock_world_profile`
  - 保留当前输入框文本不变
  - 取消该 chip 的选中态
- 这个 selector 只在 `composerMode === "start"` 时显示。
- 在 clarification / replan composer 模式下，这个 selector 不得显示。
- 为 `DemoStartRunRequest` 增加一个可选字段 `mock_world_profile`。
- `mock_world_profile` 必须只接受这六个值：
  - `family_afternoon`
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
- `mock_world_profile` 只加在 start request 上：
  - `POST /demo/runs`
  - `POST /demo/runs/stream`
- 不得把 `mock_world_profile` 加到：
  - `DemoClarifyRunRequest`
  - `DemoReplanRunRequest`
  - `DemoRunSummary`
- 当 `read_profile == "mock_world"` 且请求里带了 `mock_world_profile` 时，start path 必须直接使用该 profile，且不得再回退到当前的文本解析 resolver。
- 当 `read_profile == "mock_world"` 且请求里未带 `mock_world_profile` 时，必须保持当前行为：
  - 显式朋友 prompt 仍可自动命中 `friends_gathering`
  - 其他 prompt 仍默认回到 `family_afternoon`
- 当 `read_profile == "amap"` 时，必须保持当前 AMAP path 语义不变；这个 task 不新增 customer-side AMap selector，也不把 `mock_world_profile` 用到 AMap path 上。
- 当前 start flow 仍然必须是 stream-first；当 Task `085` 的 sync fallback 触发时，sync retry 必须复用完全相同的 start request body，包括 `mock_world_profile`。
- 为了让中文 `情侣` preset 不落入 clarification，`DeterministicIntentParser` 必须把本 task 使用到的 couple/spouse 中文词识别为有效的同行人信号。最小支持集必须覆盖本 task 固定 prompt 中实际使用的词。
- 这个 task 不得改变：
  - clarification / replan / confirm / decline 的 API shape
  - `DemoRunSummary` 结构
  - workflow 路由
  - confirmation boundary
  - benchmark case / suite / scoring
  - database schema / Alembic migration
  - npm dependencies
- `README.md` 与 `docs/WEB_DEMO_README.md` 必须更新为与当前真实 UI 一致：
  - customer page 有六个 Mock World 场景入口 chip
  - chip 只填充 composer，不自动提交
  - chip 只作用于 start path
  - 这个 task 不恢复 customer-side AMap selector
  - AMap 仍是现有 API / backend 能力，不是本 task 的 customer entry
- 前端和 E2E 必须覆盖至少一个非默认 preset 的真实入口链路。
- 后端集成测试必须覆盖显式 `mock_world_profile` 能持久化到 `AgentRun.world_profile`。

## 4. Non-goals

- 不恢复或新增 customer-side `AMap` read-path selector。
- 不把 `mock_world_profile` 暴露到 `DemoRunSummary`。
- 不把 public start API 扩展成任意 `world_profile` 覆盖器。
- 不新增 `clarify` / `replan` 的场景切换能力。
- 不修改 benchmark fixture、benchmark suite、benchmark score、formal verification 或 release gate。
- 不新增 `ScenarioType = "couple"`、`"rainy"`、`"budget"` 这类新的 planner 主枚举。
- 不重写 query planner、candidate enrichment、itinerary generation 或 workflow DAG。
- 不修改 internal observability surface。
- 不提交 `.env`、secret、token、Playwright artifact、`frontend/dist/`、`var/` 或其他无关本地文件。

## 5. Interfaces and Contracts

### Inputs

- 现有 customer start request：
  - `DemoStartRunRequest`
- 现有 customer start transport：
  - `POST /demo/runs/stream`
  - `POST /demo/runs`
- 现有 backend start-path world selection：
  - `DemoWorkflowService._workflow_profiles_for_start_request(...)`
- 现有 Task `085` start fallback：
  - `frontend/src/api/demo.ts -> startRunStream(...) -> startRun(...)`
- 现有 frontend customer composer：
  - `frontend/src/App.tsx`

### Outputs

- 新增 start-only public request field：
  - `DemoStartRunRequest.mock_world_profile?: DemoMockWorldProfile`
- 新增 customer UI start-only selector：
  - `data-testid="scenario-selector"`
  - `data-testid="scenario-chip-<mock_world_profile>"`
- 既有 `DemoRunSummary` 保持不变。
- 既有 follow-up requests 保持不变。
- 既有 persisted `AgentRun.world_profile` 继续作为真实运行 profile 的 durable source of truth。

### Schemas

`DemoStartRunRequest` 新增字段后应满足这个形状：

```json
{
  "user_input": "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
  "external_user_id": "web-demo-user",
  "display_name": "Web Demo User",
  "case_id": "web-demo",
  "selected_plan_index": 0,
  "read_profile": "mock_world",
  "mock_world_profile": "friends_gathering"
}
```

本 task 的固定场景入口矩阵必须是：

```json
{
  "scenario_presets": [
    {
      "label": "亲子",
      "mock_world_profile": "family_afternoon",
      "prompt": "今天下午想和妻子、5 岁孩子在附近出门玩几个小时，先安排室内亲子活动，再吃一顿清淡晚餐，不要太远。"
    },
    {
      "label": "朋友",
      "mock_world_profile": "friends_gathering",
      "prompt": "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。"
    },
    {
      "label": "单人",
      "mock_world_profile": "solo_afternoon",
      "prompt": "今天下午想一个人在附近轻松待几个小时，先安排轻量活动，再吃一顿清淡的简餐，不要太远。"
    },
    {
      "label": "情侣",
      "mock_world_profile": "couple_afternoon",
      "prompt": "今天下午想和伴侣在附近出门几个小时，先安排 citywalk，再吃一顿清淡晚餐，不要太远。"
    },
    {
      "label": "雨天",
      "mock_world_profile": "rainy_day_fallback",
      "prompt": "今天下午想和朋友在附近待几个小时，外面下雨，优先安排室内活动，再找一家热一点的简餐，不要太远。"
    },
    {
      "label": "预算",
      "mock_world_profile": "budget_lite",
      "prompt": "今天下午想一个人在附近待几个小时，尽量控制预算，先安排免费或低价活动，再吃一顿便宜简餐，不要太远。"
    }
  ]
}
```

UI test id contract：

```json
{
  "scenario_selector_test_ids": [
    "scenario-selector",
    "scenario-chip-family_afternoon",
    "scenario-chip-friends_gathering",
    "scenario-chip-solo_afternoon",
    "scenario-chip-couple_afternoon",
    "scenario-chip-rainy_day_fallback",
    "scenario-chip-budget_lite"
  ]
}
```

显式 profile 选择优先级：

```json
{
  "start_profile_resolution": [
    "if read_profile == amap -> use amap_shanghai_live and ignore mock_world_profile",
    "else if mock_world_profile is present -> use it exactly",
    "else -> keep existing text-based resolver behavior"
  ]
}
```

## 6. Observability

这个任务不新增新的 observability surface，也不新增新的 public response 字段。

它必须继续使用既有 durable 数据作为真实 profile 的审计来源：

- `agent_runs.tool_profile`
- `agent_runs.world_profile`

当 start request 显式带了 `mock_world_profile` 时，existing internal observability / DB review 必须能继续看到该 run 最终持久化的 `world_profile`。这个任务不新增：

- 新的 trace metadata
- 新的 benchmark artifact 字段
- 新的 internal route
- 新的 Redis event schema

前端选中的 chip 状态仅为本地 UI state，不需要持久化到新的 public payload。

## 7. Failure Handling

- 如果 `mock_world_profile` 不是允许值，start request 必须按现有 request validation 路径返回 `422`，而不是静默降级。
- 如果 `read_profile == "mock_world"` 且显式 `mock_world_profile` 对应 fixture / runtime path 异常，必须走现有错误路径，不得静默回退到 `family_afternoon`。
- 只有在 `mock_world_profile` 缺失时，才允许沿用当前 resolver 的 friends/family fallback 逻辑。
- 如果 `POST /demo/runs/stream` 在收到有效 `progress` 前失败并触发 Task `085` 的 sync fallback，sync fallback 必须原样复用 `mock_world_profile`。
- clarification / replan path 必须继续复用 source run 的持久化 `world_profile`，不得重新读取 chip state 或要求客户端重复传 profile。
- couple preset 的中文 prompt 不得因为“同行人未识别”而直接落入 clarification；如果发生这种情况，应通过最小 parser keyword 补齐修复，而不是在本 task 里扩大 clarification policy。
- 这个 task 不得改变 AMap preview path 的确认阻断行为。

## 8. Acceptance Criteria

- [ ] `docs/specs/086-customer-demo-scenario-selector-v0.md` 存在并匹配本任务。
- [ ] `docs/plans/086-customer-demo-scenario-selector-v0-plan.md` 存在并匹配本任务。
- [ ] `docs/specs` 与 `docs/plans` 在任务完成后连续且 slug 对齐到 `086`。
- [ ] customer page 在 `composerMode == "start"` 时渲染六个场景入口 chip，且顺序与本 spec 完全一致。
- [ ] 点击某个未选中 chip 会填充对应 prompt、设置对应 `mock_world_profile`、显示选中态。
- [ ] 再次点击当前已选中 chip 会清除显式 profile 选择，但保留当前输入文本。
- [ ] clarification / replan composer 模式下不显示场景入口 chip。
- [ ] `DemoStartRunRequest` 接受可选 `mock_world_profile`，且仅接受本 spec 定义的六个值。
- [ ] 当 start request 带显式 `mock_world_profile` 时，backend 持久化的 `AgentRun.world_profile` 与之完全一致。
- [ ] 六个 preset start path 都能以 `read_profile="mock_world"` 启动并到达可继续 review 的 run 状态，而不是被错误地重定向到其他 profile。
- [ ] 当 `mock_world_profile` 缺失时，既有 friends auto-resolution 和 family default 仍保持不变。
- [ ] Task `085` 的 start sync fallback 会原样复用 `mock_world_profile`。
- [ ] 中文 `情侣` preset 不会仅因为 `伴侣` 词汇未识别而进入 clarification。
- [ ] `DemoRunSummary`、`DemoClarifyRunRequest`、`DemoReplanRunRequest`、confirm/decline contract 保持不变。
- [ ] `README.md` 与 `docs/WEB_DEMO_README.md` 准确描述六个 Mock World preset，并且不再声称 customer page 当前提供 AMap first-screen selector。
- [ ] focused backend / frontend / E2E verification commands 通过。
- [ ] `git diff --check` 通过。
- [ ] 没有 `.env`、API key、token、secret 或无关产物被 git 跟踪。
- [ ] 提交后工作树干净。

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_api.py tests/test_intent_parser.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k "mock_world_profile or friends_group_start" -q
npm --prefix frontend run test -- --run src/api/demo.test.ts src/App.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "scenario preset selector"
npm --prefix frontend run e2e -- --project=mobile-chromium --grep "loads the main flow without document-level horizontal overflow"
git diff --check
git status --short --branch
```

## 10. Expected Commit

```text
feat: add customer demo scenario selector
```

## 11. Notes for the Implementer

保持这个任务是一个 start-path 的 product convergence slice，不要把它扩成“任意 profile 的通用 public 控制台”。

优先级和边界要守住：

- 显式 `mock_world_profile` 只用于 start request。
- continuation 一律复用 source run 的持久化 `world_profile`。
- 不在这个任务里恢复 AMap customer-side selector。
- 不在这个任务里新增 public summary 字段去回显当前 scenario profile。
- 如果 preset prompt 与当前 deterministic workflow 不稳定，优先收紧 prompt 文案或补最小 parser 关键词，不要借机重写 planner / workflow。
- 如果实现中发现需要修改 benchmark fixture、suite、score 或 internal observability，说明 scope 已经失控，应中止并拆分 follow-up task。
