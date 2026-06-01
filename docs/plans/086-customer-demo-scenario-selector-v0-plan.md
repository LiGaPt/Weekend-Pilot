# Plan: 086 Customer Demo Scenario Selector v0

## 1. Spec Reference

Spec file:

```text
docs/specs/086-customer-demo-scenario-selector-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- 当前分支是 `codex/customer-start-run-sse-fallback-v0`。
- 当前工作树是干净的。
- 当前 `HEAD` 是 `ab2490a fix: add customer start-run stream fallback`，对应最新 task `085`。
- `docs/specs` 与 `docs/plans` 已连续且 slug-matched 到 `085`。
- backend 已支持六个 Mock World world profile：
  - `family_afternoon`
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
- benchmark case 与 fixture 已存在，上述六个 profile 并不是新建能力。
- customer page 当前是 chat-first，但 `frontend/src/App.tsx` 没有渲染 example-entry strip；`frontend/src/styles.css` 已有 `.example-chip-row` / `.example-chip` 样式可复用。
- 当前 public start request 只有 `read_profile`，没有显式 Mock World profile 字段。
- 当前 start path 是 `startRunStream(...)` 优先，Task `085` 已确保 pre-progress 失败时回退到 sync `startRun(...)`。
- 当前 customer UI 没有 first-screen AMap selector；本计划默认不恢复它。

## 3. Files to Add

- `frontend/src/demoScenarioPresets.ts` - 定义六个固定 scenario chip 的 label、prompt、`mock_world_profile`、显示顺序，供 `App.tsx` 和前端测试复用。

## 4. Files to Modify

- `backend/app/demo/schemas.py` - 新增 `DemoMockWorldProfile` literal，并给 `DemoStartRunRequest` 增加可选 `mock_world_profile`。
- `backend/app/demo/service.py` - 调整 start path 的 profile 选择优先级：显式 `mock_world_profile` 优先于现有 resolver，但只作用于 `read_profile="mock_world"`。
- `backend/app/planning/intent_parser.py` - 为 couple preset 的中文 prompt 增加最小 spouse/couple 关键词识别，避免落入 clarification。
- `tests/test_demo_api.py` - 覆盖新 request field 的模型验证与默认行为。
- `tests/test_intent_parser.py` - 覆盖 `伴侣` 类 couple 关键词的最小识别行为。
- `tests/integration/test_demo_api_gateway.py` - 参数化验证显式 `mock_world_profile` 的 start path 持久化与 status。
- `frontend/src/types/demo.ts` - 新增 `DemoMockWorldProfile` 类型，并给 `DemoStartRunRequest` 增加可选 `mock_world_profile`。
- `frontend/src/api/demo.test.ts` - 校验 `startRun` / `startRunStream` 请求体会带上 `mock_world_profile`，以及 Task `085` fallback 会复用它。
- `frontend/src/App.tsx` - 渲染 chip row、维护选中态、填充 prompt、把显式 profile 带入 start request。
- `frontend/src/App.test.tsx` - 覆盖 chip 渲染、点击行为、选中切换、请求体。
- `frontend/src/styles.css` - 复用并必要时微调 scenario chip 的样式与移动端排版。
- `frontend/e2e/demo.spec.ts` - 新增或改写一个 desktop smoke，验证非默认 chip 的真实入口链路。
- `README.md` - 更新 Web demo 说明，写清六个 Mock World preset。
- `docs/WEB_DEMO_README.md` - 更新 reviewer runbook，使其与实际 chip 行为一致，并移除当前不准确的 first-screen AMap selector 描述。

## 5. Implementation Steps

1. 在 backend start request schema 上增加显式 Mock World profile 字段。
   - 在 `backend/app/demo/schemas.py` 新增 `DemoMockWorldProfile = Literal[...]`，值严格限定为：
     - `family_afternoon`
     - `friends_gathering`
     - `solo_afternoon`
     - `couple_afternoon`
     - `rainy_day_fallback`
     - `budget_lite`
   - 给 `DemoStartRunRequest` 增加：
     - `mock_world_profile: DemoMockWorldProfile | None = None`
   - 不修改 `DemoRunSummary`、`DemoClarifyRunRequest`、`DemoReplanRunRequest`。

2. 在 backend start path 实现明确的 profile 选择优先级。
   - 修改 `backend/app/demo/service.py` 的 `_workflow_profiles_for_start_request(...)`。
   - 逻辑必须固定为：
     1. `if request.read_profile == "amap": return ("amap", "amap_shanghai_live")`
     2. `elif request.mock_world_profile is not None: return ("mock_world", request.mock_world_profile)`
     3. `else: return ("mock_world", resolve_mock_world_demo_profile(request.user_input))`
   - 不要把 `mock_world_profile` 传到 clarify/replan。
   - 不要新增 response field 回显它。

3. 为中文 `情侣` preset 补最小 parser 识别，而不是扩 planner。
   - 在 `backend/app/planning/intent_parser.py` 中把以下词汇加入 spouse/couple 识别集合：
     - `伴侣`
     - `另一半`
     - `爱人`
     - `partner`
   - 目标不是新增 `ScenarioType = "couple"`。
   - 目标只是让本 task 的 couple preset prompt 在 clarification policy 看来属于“已识别同行人”，并让 `participants.adults == 2`。
   - 不修改 query planner 的主逻辑。

4. 新增一个前端共享 preset 常量文件。
   - 新建 `frontend/src/demoScenarioPresets.ts`。
   - 导出一个固定有序数组，顺序和内容必须与 spec 一致：
     1. `family_afternoon / 亲子 / 今天下午想和妻子、5 岁孩子在附近出门玩几个小时，先安排室内亲子活动，再吃一顿清淡晚餐，不要太远。`
     2. `friends_gathering / 朋友 / 今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。`
     3. `solo_afternoon / 单人 / 今天下午想一个人在附近轻松待几个小时，先安排轻量活动，再吃一顿清淡的简餐，不要太远。`
     4. `couple_afternoon / 情侣 / 今天下午想和伴侣在附近出门几个小时，先安排 citywalk，再吃一顿清淡晚餐，不要太远。`
     5. `rainy_day_fallback / 雨天 / 今天下午想和朋友在附近待几个小时，外面下雨，优先安排室内活动，再找一家热一点的简餐，不要太远。`
     6. `budget_lite / 预算 / 今天下午想一个人在附近待几个小时，尽量控制预算，先安排免费或低价活动，再吃一顿便宜简餐，不要太远。`
   - 同时导出类型辅助，避免在 `App.tsx` 里手写重复常量。

5. 在 customer page 渲染 chip row，并把它做成 start-only 显式入口。
   - 在 `frontend/src/App.tsx` 增加本地 state：
     - `selectedMockWorldProfile: DemoMockWorldProfile | null`
   - 在 `composerMode === "start"` 时渲染 chip row：
     - 容器 `data-testid="scenario-selector"`
     - 每个 chip `data-testid="scenario-chip-<profile>"`
   - 点击行为固定为：
     - 点击未选中 chip：设选中 profile、覆盖 `userInput` 为 preset prompt、清掉当前错误 banner
     - 点击已选中 chip：清除 `selectedMockWorldProfile`，保留当前 `userInput`
   - clarification / replan 模式下不渲染 chip row。
   - 保持现有 sticky composer、thread、follow-up 逻辑不动。

6. 让 start request 带上显式 profile，并保证 fallback 也带同样字段。
   - 在 `frontend/src/types/demo.ts` 增加：
     - `export type DemoMockWorldProfile = ...`
     - `DemoStartRunRequest.mock_world_profile?: DemoMockWorldProfile`
   - 在 `frontend/src/App.tsx` 的 `handleStart()` 中，把 `mock_world_profile` 放进 `startRunStream(...)` body：
     - 仅当 `selectedMockWorldProfile` 非空时发送
   - 不要在 `clarifyRun` / `replanRun` body 中加入这个字段。
   - `frontend/src/api/demo.ts` 无需特判；它已经把整个 `DemoStartRunRequest` 透传给 stream 和 sync fallback。
   - 重点在测试里验证 Task `085` 的 fallback 第二次请求体也包含相同 `mock_world_profile`。

7. 前端测试按最小但完整的方式补齐。
   - 在 `frontend/src/api/demo.test.ts` 增加/更新这些断言：
     - `startRun(...)` 会序列化 `mock_world_profile`
     - `startRunStream(...)` 会序列化 `mock_world_profile`
     - stream `404` / no-body fallback 时，第二次 `/demo/runs` 请求体保留相同 `mock_world_profile`
   - 在 `frontend/src/App.test.tsx` 增加/更新这些断言：
     - first render 的 start composer 可见 6 个 chip，顺序正确
     - 点击 `朋友` chip 会把固定 prompt 写入主输入框
     - 点击 `朋友` chip 后发起 start，会以 `mock_world_profile: "friends_gathering"` 调用 `startRunStream`
     - 再次点击同一 chip 会取消显式 profile
     - clarification/replan 模式下 chip row 不显示
   - 不要删掉现有 progress / confirmation / result regression。

8. backend 测试按“schema + parser + start integration”三层补齐。
   - 在 `tests/test_demo_api.py` 增加：
     - `test_start_request_accepts_supported_mock_world_profile_values`
     - `test_start_request_rejects_unknown_mock_world_profile`
   - 在 `tests/test_intent_parser.py` 增加：
     - `test_parser_recognizes_partner_word_for_couple_preset`
     - 断言 `participants.adults == 2`
     - 断言 `signals.scenario_or_participants is True`
     - 断言时间/距离/偏好信号仍可被 couple preset prompt 识别
   - 在 `tests/integration/test_demo_api_gateway.py` 增加一个参数化 start-path 测试，例如：
     - `test_demo_run_start_with_explicit_mock_world_profile_persists_selected_world`
   - 参数集使用六个 profile 对应的固定 prompt。
   - 每组断言至少包含：
     - HTTP `200`
     - `status == "awaiting_confirmation"`
     - `read_profile == "mock_world"`
     - `action_count == 0`
     - 持久化 `AgentRun.world_profile == request.mock_world_profile`
   - 保留现有 `friends_group_start` 自动解析测试，确保 explicit-field 逻辑没有破坏旧兼容。

9. browser smoke 只补一个非默认入口的真实回归。
   - 在 `frontend/e2e/demo.spec.ts` 新增或改写一个 desktop test，标题固定包含 `scenario preset selector`。
   - 这个测试要：
     - 进入 customer page
     - 点击 `朋友` chip
     - 监听并记录 `/demo/runs/stream` 的 POST body，再 `route.fallback()`
     - 断言 body 中有 `mock_world_profile: "friends_gathering"`
     - 继续走真实本地栈到 confirm boundary，必要时完成确认
   - 继续复用现有 mobile no-horizontal-overflow smoke，不新开全量移动端场景。

10. 文档按“真实 UI”收口，而不是沿用当前失真的说法。
    - `README.md`：
      - 在 Web demo/customer flow 小节新增六个 Mock World scenario chips 的说明
      - 明确 chip 只填充输入框，不自动提交
      - 明确显式 profile 只作用于 start path
    - `docs/WEB_DEMO_README.md`：
      - Happy Path 改成“点击 `亲子` chip 或输入等价 prompt”
      - Friends path 改成使用 `朋友` chip，而不是手动覆盖整段 prompt
      - 新增 `单人` / `情侣` / `雨天` / `预算` 入口的简短 reviewer 说明
      - 删除或改写当前不准确的“customer first-screen AMap selector”描述
      - 保留 AMap 为已有 backend/API 能力，但明确不属于本 task 的 customer visible entry
    - 不要借机重写整份 runbook。

11. 运行验证命令，检查 diff scope，再提交和推送。
    - 确认没有把 `frontend/dist/`、Playwright artifact、`.env`、`var/` 带进暂存区。
    - 提交前复查 docs 是否与实际 UI 保持一致，尤其是 AMap selector 描述。

## 6. Testing Plan

- Unit tests:
  - `tests/test_demo_api.py`
    - `DemoStartRunRequest` 接受六个合法 `mock_world_profile`
    - 非法 `mock_world_profile` 被拒绝
  - `tests/test_intent_parser.py`
    - `伴侣` / `partner` couple 关键词能形成有效同行人信号
  - `frontend/src/api/demo.test.ts`
    - stream/sync start body 带 `mock_world_profile`
    - Task `085` fallback 复用 `mock_world_profile`
  - `frontend/src/App.test.tsx`
    - 6 个 chip 可见且顺序固定
    - 点击 chip 填充 prompt
    - 点击活跃 chip 取消显式 profile
    - clarification/replan 模式不显示 chip row

- Integration tests:
  - `tests/integration/test_demo_api_gateway.py`
    - 参数化 start path 覆盖六个显式 `mock_world_profile`
    - 现有 friends auto-resolution 回归继续通过

- Smoke tests:
  - `frontend/e2e/demo.spec.ts`
    - `scenario preset selector` desktop smoke：点击 `朋友` chip，断言请求体并跑通真实 flow
  - 现有 mobile 横向溢出 smoke 复跑，确认 chip row 没把布局撑坏

- Document review checks:
  - `README.md` 与 `docs/WEB_DEMO_README.md` 都准确写出：
    - 六个 Mock World chips
    - chip 只填充 composer
    - start-only 显式 profile
    - 本 task 不恢复 customer-side AMap selector

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add customer demo scenario selector
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/customer-demo-scenario-selector-v0
git add backend/app/demo/schemas.py backend/app/demo/service.py backend/app/planning/intent_parser.py
git add tests/test_demo_api.py tests/test_intent_parser.py tests/integration/test_demo_api_gateway.py
git add frontend/src/demoScenarioPresets.ts frontend/src/types/demo.ts frontend/src/api/demo.test.ts
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css frontend/e2e/demo.spec.ts
git add README.md docs/WEB_DEMO_README.md
git commit -m "feat: add customer demo scenario selector"
git push -u origin codex/customer-demo-scenario-selector-v0
```

The implementer must confirm `.env`, `frontend/.env`, `frontend/dist/`, Playwright artifacts, `node_modules/`, and `var/` are not staged.

## 9. Out-of-scope Changes

- 不恢复 customer-side AMap selector。
- 不给 `DemoRunSummary` 新增 `mock_world_profile` 回显字段。
- 不修改 clarify / replan / confirm / decline 请求体。
- 不新增 generic `world_profile` public override。
- 不修改 benchmark case、suite、score 或 release gate。
- 不引入新的 parser 主枚举或 planner 主分支。
- 不改 internal observability 页面和 API。
- 不引入新依赖、migration、生成产物或无关清理。

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] 实现与 spec 一致。
- [ ] 实现范围保持在 start-path scenario selector。
- [ ] customer page 在 start 模式下显示 6 个固定顺序 chip。
- [ ] 点击 chip 会填充固定 prompt，并让 start request 带上对应 `mock_world_profile`。
- [ ] 再次点击活跃 chip 会清除显式 profile，而不会清空当前文本。
- [ ] Task `085` 的 sync fallback 仍会复用相同 `mock_world_profile`。
- [ ] 六个显式 profile 的 start path 都能持久化到对应 `AgentRun.world_profile`。
- [ ] friends 自动解析旧行为仍然保持。
- [ ] couple 中文 prompt 不会因为同行人未识别而进入 clarification。
- [ ] clarify / replan / confirm / decline contract 没变。
- [ ] 文档已准确反映当前 customer UI，不再声称有 first-screen AMap selector。
- [ ] 所需 tests、build、E2E 都通过。
- [ ] `git diff --check` 通过。
- [ ] 提交信息匹配计划。
- [ ] push 成功。
- [ ] 没有 `.env`、API key、token、secret 或生成产物被提交。

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- 六个 chip 的最终 label / prompt / profile 映射
- 是否保留了当前 `DemoRunSummary` shape 不变
- 是否验证了 Task `085` fallback 对 `mock_world_profile` 的透传
- 是否更新了 docs 中关于 AMap first-screen selector 的不准确描述
- Known limitations or follow-up tasks:
  - customer page 仍未恢复 AMap first-screen selector
  - `mock_world_profile` 仍然只作用于 start path
  - follow-up 场景切换仍然依赖 source run 持久化的 `world_profile`
