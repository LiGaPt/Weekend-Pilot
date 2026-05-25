# Spec: 062 Customer Demo Selected Plan Replan Index

## 1. Goal

在当前 customer demo 的 replan 路径里补上一个真实的“所见即所发”保证：当用户在 `http://127.0.0.1:5173/` 的方案 tabs 中切到第二个方案后，再点击“重新规划当前方案”，前端必须把当前选中的方案索引作为 `selected_plan_index` 发给 `POST /demo/runs/{run_id}/replan`，而不是继续硬编码 `0`。

当前仓库已经在 task `060` 交付了 customer replan panel，但 `frontend/src/App.tsx` 里的 `buildReplanRequest(...)` 仍固定发送 `selected_plan_index: 0`。这意味着 UI 虽然允许切换到第二个方案，实际 follow-up replan 仍以第一个方案为源选择，造成前端可见选择与 backend request contract 脱节。完成本任务后，customer demo 的 replan 请求必须与当前选中的 tab 保持一致，并且由 App test 与 E2E mock 场景覆盖该行为，防止再次回归。

## 2. Project Context

本任务对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M4. 多轮对话与方案版本`，具体属于“多轮澄清与 replan 工作流”这一组能力的收口修复，而不是新的 M1 基础设施扩展。虽然路线图默认建议当前阶段优先 M1，但当前仓库已经在 task `060` 交付了 customer replan 前端路径，且这个路径存在明确的用户可见正确性缺口，因此应优先用一个最小补丁 task 收口该问题，再继续新的 M1 任务。

它直接关联 `docs/PROJECT_BLUEPRINT.md` 中这些架构与产品边界：

- Minimal Web UI / Web demo API path
- Human-in-the-loop conversation flow before confirmation
- Public plan version semantics
- Customer-safe public surface boundary

同时，本任务还要尊重已有任务链的既有契约：

- task `044` 明确规定 follow-up replan run 必须使用新请求里的 `selected_plan_index`
- task `060` 交付了 customer replan panel，但把 `selected_plan_index = 0` 作为刻意收窄的 v0 决策
- task `061` 已经作为最新正式 task 落地并提交，因此本任务应作为新的 `062` 编号执行，而不是回填到 `060` 或继续 `061`

## 3. Requirements

- `frontend/src/App.tsx` 必须在提交 replan 前，根据当前 run 的 `plans` 和当前前端选中的 plan 计算零基 `selected_plan_index`。
- 当 `selectedPlanId` 能直接匹配到 `run.plans[*].plan_id` 时，必须使用该匹配项在 `run.plans` 里的索引。
- 当 `selectedPlanId` 为 `null`，或因为 run 已替换而变成陈旧值时，必须复用当前 `choosePlan(...)` 的解析结果，找到当前实际展示 plan 在 `run.plans` 中的索引。
- 只有在当前 run 是 plan-bearing run，但仍然无法导出有效索引时，才允许作为防御性兜底回退到 `0`；不得发送 `-1`、`undefined`、`null` 或其他非法值。
- `buildReplanRequest(...)` 必须改为接收 `selectedPlanIndex` 参数，不得继续在函数内部硬编码 `selected_plan_index: 0`。
- `handleReplan()` 必须把计算出的索引传给 `buildReplanRequest(...)`，再调用 `replanRun(...)`。
- `selected_plan_index` 的修复范围只限 replan path。
- 以下现有路径必须保持不变：
  - `handleStart()` 继续发送 `selected_plan_index: 0`
  - `handleClarify()` 继续发送 `selected_plan_index: 0`
  - `confirmRun(...)`
  - `declineRun(...)`
  - `replanRun(...)` 的 API client contract
- 本任务不得新增新的 plan-index selector UI；必须继续复用已有 plan tabs 作为前端唯一的方案选择来源。
- 本任务不得把当前 tab 选择写回 source run，也不得新增“重新选择 source selected plan”的 backend 能力。
- `frontend/src/App.test.tsx` 必须新增一条回归测试：
  - 先启动一个含两个 plans 的 `awaiting_confirmation` run
  - 切换到第二个 plan tab
  - 提交 replan
  - 断言 `replanRun(...)` 收到的 body 为 `selected_plan_index: 1`
- `frontend/src/App.test.tsx` 现有默认路径回归必须继续保留：
  - 不切换 tabs 时，replan body 仍然是 `selected_plan_index: 0`
- `frontend/e2e/demo.spec.ts` 必须新增或更新一个 mocked replan 场景：
  - mocked start run 至少包含两个 plans
  - 浏览器中点击第二个 plan tab
  - 提交 replan
  - 拦截 `/demo/runs/{run_id}/replan` 请求
  - 断言 body 为 `selected_plan_index: 1`
- 该 E2E mock 场景必须保持 frontend-only 验证性质：
  - 不要求修改 backend API tests
  - 不要求引入新的真实后端行为
  - 只验证 customer page 组包与 request body 是否正确
- 以下内容不得修改：
  - backend API schema
  - `backend/app/demo/service.py`
  - `backend/app/workflow/*`
  - database schema
  - Alembic migrations
  - README / `docs/WEB_DEMO_README.md`
  - `docs/specs/060-customer-demo-replan-flow-v0.md`
  - `docs/plans/060-customer-demo-replan-flow-v0-plan.md`

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- 不修改 replan backend contract、response shape、plan version 规则或 action manifest schema。
- 不修改 clarification UI / clarify request 的 `selected_plan_index` 语义。
- 不为 `declined`、`completed`、`failed` run 扩展新的 replan 入口。
- 不引入新的 plan 选择持久化、history browser、version compare 或 source-plan reselection API。
- 不改 task `060` / `061` 的历史 spec、plan、commit 信息。
- 不暂存或提交当前工作区里与本任务无关的本地脏文件：`.gitignore`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc` 等。

## 5. Interfaces and Contracts

### Inputs

- 当前 frontend 状态：
  - `run: DemoRunSummary | null`
  - `selectedPlanId: string | null`
- 当前 plan 解析逻辑：
  - `choosePlan(run, selectedPlanId)`
- 现有 public request contract：
  - `DemoReplanRunRequest`
  - `POST /demo/runs/{run_id}/replan`

### Outputs

- replan request body 中的 `selected_plan_index` 与当前 customer page 选中的 plan tab 对齐。
- 不切换 tab 的默认路径继续发送 `0`。
- response handling、plan version 可见性、clarification handoff、confirmation controls 行为保持不变。

### Schemas

当用户在 customer page 选中第二个 plan 后提交 replan，请求体必须形如：

```json
{
  "user_input": "Keep it nearby, but make it indoor this time.",
  "selected_plan_index": 1
}
```

默认未切换 tabs 的第一方案路径仍然保持：

```json
{
  "user_input": "Keep it nearby, but make it indoor this time.",
  "selected_plan_index": 0
}
```

## 6. Observability

本任务不新增任何新的 observability contract、trace metadata、数据库持久化字段、benchmark artifact 或 internal review 字段。

需要保持不变的事实：

- customer page 继续只消费既有 public `DemoRunSummary`
- internal observability surface `http://127.0.0.1:5174/` 不改动
- 不新增 trace IDs、session IDs、agent roles、node history、conversation payloads 的公开暴露
- 行为验证依赖 App test 与 Playwright mock，而不是增加新的日志或诊断接口

## 7. Failure Handling

- 如果 `selectedPlanId` 在当前 run 中找不到对应 plan，前端必须回退到当前 `choosePlan(...)` 解析出的实际展示 plan，再计算索引。
- 如果经过上述回退后仍然无法得到索引，前端必须发送 `0` 作为防御性兜底；不得发送非法索引值。
- 如果当前 run 没有可展示的 plans，则本任务不改变现有行为：
  - replan panel 是否显示仍由既有条件控制
  - 不新增新的错误文案
- 本任务不得改变现有 `/replan` API 错误本地化逻辑。
- 本任务不得破坏已有这些路径：
  - 默认第一方案 replan
  - repeated replan
  - replan -> awaiting_clarification handoff
  - AMap read-only preview confirm block
  - confirm / decline / refresh

## 8. Acceptance Criteria

- [ ] `docs/specs/062-customer-demo-selected-plan-replan-index.md` 存在并匹配本任务。
- [ ] `docs/plans/062-customer-demo-selected-plan-replan-index-plan.md` 存在并匹配本任务。
- [ ] `docs/specs` 与 `docs/plans` 在 `001` 到 `061` 上保持连续且匹配，本任务使用新的 `062` 编号。
- [ ] `frontend/src/App.tsx` 不再在 replan path 上硬编码 `selected_plan_index: 0`。
- [ ] 当不切换 tabs 时，replan request body 继续发送 `selected_plan_index: 0`。
- [ ] 当切换到第二个 plan tab 后提交 replan 时，replan request body 发送 `selected_plan_index: 1`。
- [ ] `buildReplanRequest(...)` 接收外部传入的 `selectedPlanIndex`，而不是内部固定写死 `0`。
- [ ] `frontend/src/App.test.tsx` 覆盖“选第二个 plan 后 replan -> body 为 1”的回归场景。
- [ ] `frontend/e2e/demo.spec.ts` 覆盖 mocked customer-page 场景：选第二个 plan 后 replan，拦截 body 为 `1`。
- [ ] replan response handling、plan version 可见性、clarification handoff、confirm / decline / refresh 行为不回归。
- [ ] 不修改 backend API schema、workflow routing、database schema、README 或 `docs/WEB_DEMO_README.md`。
- [ ] `npm --prefix frontend run test -- --run src/App.test.tsx` 通过。
- [ ] `npm --prefix frontend run build` 通过。
- [ ] `npm --prefix frontend run e2e` 通过。
- [ ] `git diff --check` 通过。
- [ ] 没有 `.env`、API key、token、secret 或无关本地脏文件被提交。
- [ ] 提交后工作树只保留本任务外原本已存在的本地脏文件。

## 9. Verification Commands

```bash
npm --prefix frontend run test -- --run src/App.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 10. Expected Commit

```text
fix: use selected plan index for demo replans
```

## 11. Notes for the Implementer

当前仓库事实已经明确：

- 最新正式 task 是 `061`
- `057d3c0 feat: add formal verification script` 对应 `061`
- `dbe50d9 feat: add customer demo replan flow` 对应 `060`
- `main` 仍停在更早基线，不包含 `058-061`

因此，本任务必须从当前这条包含 `058-061` 的分支链继续，而不是回到 `main` 重新做。

实现时保持这几个边界：

- 这是一张补丁卡，不是重做 task `060`
- 不新增新的 plan selection API，只把当前已有 tab 选择正确映射到 replan request
- 计算索引时要复用 `choosePlan(...)` 的语义做兜底，避免 `selectedPlanId` 因 run 替换而变成陈旧值
- 如果实现过程中发现必须改 backend、README、workflow 或文档历史，说明 scope 已经偏离本任务，应停止并汇报
