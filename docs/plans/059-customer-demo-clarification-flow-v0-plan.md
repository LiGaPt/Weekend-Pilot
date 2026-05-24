# Plan: 059 Customer Demo Clarification Flow v0

## 1. Spec Reference

Spec file:

```text
docs/specs/059-customer-demo-clarification-flow-v0.md
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

- 当前工作区分支是 `codex/customer-demo-chinese-polish`。
- 当前工作区最新提交是 `4f63bd1 fix: polish chinese customer demo surface`，它与 task `058` 对齐。
- `docs/specs/` 与 `docs/plans/` 从 `001` 到 `058` 连续且 slug 一一匹配。
- `origin/main` 当前已合并到 task `057`，而当前工作区还承载着 task `058` 的未合并分支状态。
- clarification backend contract 已存在并已被 Python tests 覆盖：
  - `awaiting_clarification`
  - `DemoRunSummary.clarification`
  - `POST /demo/runs/{run_id}/clarify`
  - clarification-only `v1`
- customer frontend 当前仍缺这些内容：
  - `frontend/src/types/demo.ts` 没有 `clarification`
  - `frontend/src/api/demo.ts` 没有 `clarifyRun`
  - `frontend/src/App.tsx` 没有 clarification panel 或 clarification submit 状态
  - `frontend/src/App.tsx` 的 header `RequestState` 也没有 `awaiting_clarification` / `clarifying`
  - `docs/WEB_DEMO_README.md` 的 Clarification Path 仍要求 reviewer 用 `curl`
- 本任务应以当前 `4f63bd1` 为执行基线新开分支 `codex/customer-demo-clarification-flow-v0`；如果 task `058` 先合入，则改为从包含等价内容的 `main` 开始。
- 当前工作树已有无关本地改动或未跟踪文件：
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/`
  - `qc`
- 这些路径都不属于本任务，必须保持 unstaged。

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/src/types/demo.ts` - 补齐 clarification summary / request 类型，并把 `DemoRunSummary` 扩成与 backend contract 对齐。
- `frontend/src/api/demo.ts` - 新增 `clarifyRun(...)` 并补 clarification-path 错误本地化映射。
- `frontend/src/api/demo.test.ts` - 增加 `clarifyRun(...)` request body 与 clarification-specific error localization 测试。
- `frontend/src/App.tsx` - 扩展 request state、clarification reply state、clarification panel、submit flow、view switching 和 field label helpers。
- `frontend/src/App.test.tsx` - 覆盖 clarification pending、submit disabled、clarify success、repeat clarify、run-id 更新、v1 保持、无 confirm button 等行为。
- `frontend/src/styles.css` - 只为 clarification panel 增加最小样式，如 chip list 和较矮的 clarification textarea。
- `frontend/e2e/demo.spec.ts` - 增加 vague request -> clarification -> clarify -> awaiting_confirmation 的浏览器流程。
- `README.md` - 把 Minimal Web UI / Web Demo API 说明同步到“customer page 已可直接补充信息”。
- `docs/WEB_DEMO_README.md` - 把 Clarification Path 主演示步骤从 `curl` 改成 customer page 表单，并保留 `curl` 作为 API 验证备选。

## 5. Implementation Steps

1. 先补前端类型，再写失败测试。
   - 在 `frontend/src/types/demo.ts` 中先定义：
     - `DemoClarificationSummary`
     - `DemoClarifyRunRequest`
     - `DemoRunSummary.clarification: DemoClarificationSummary | null`
   - 让所有现有测试 fixture 明确带上 `clarification: null` 或 clarification object，避免后续改动时出现隐式 any 或 shape 漏洞。

2. 先写 `frontend/src/api/demo.test.ts` 的失败用例。
   - 新增 `clarifyRun("run-1", { user_input: "...", selected_plan_index: 0 })` 必须发到 `/demo/runs/run-1/clarify` 的断言。
   - 新增 clarification-path 409 detail localization 断言：
     - `Source run status does not allow clarification.`
     - `Source run is missing session persistence for clarification.`
     - `Source run session is unavailable for clarification.`
     - `Source run user is unavailable for clarification.`
   - 保留现有 start/get/confirm/decline tests 不动，只做 additive coverage。

3. 实现 `clarifyRun(...)` 和错误本地化。
   - 在 `frontend/src/api/demo.ts` 中新增 `clarifyRun(...)`。
   - 复用现有 `request<T>(...)` helper，不新增新 transport 抽象。
   - 在 `localizedResponseMessage(...)` 中加入 clarification-path detail 映射，未知错误继续回落到 `statusFallbackMessage(...)`。

4. 先写 `frontend/src/App.test.tsx` 的 clarification 失败用例。
   - 增加一个 `awaiting_clarification` mock run：
     - `plans = []`
     - `selected_plan_id = null`
     - `clarification.prompt` 非空
     - `clarification.missing_fields = ["scenario_or_participants", "time_window"]`
     - `plan_version.version_label = "v1"`
   - 至少覆盖这些断言：
     - start 返回 clarification run 后出现 `clarification-panel`
     - 页面显示 prompt
     - 页面显示 `出行人/场景` 和 `时间安排`
     - 页面没有 `confirm-button`
     - clarification submit 空输入时按钮禁用
     - clarification submit 成功后调用 `clarifyRun(run_id, { user_input, selected_plan_index: 0 })`
     - clarify success 后页面回到 `awaiting_confirmation`
     - clarify success 后 `run-id` 更新为新的 run id
     - clarify success 后 `plan-version` 仍是 `v1`
     - clarify 若再次返回 `awaiting_clarification`，页面继续显示新的 prompt，而不是报错或切回 empty state

5. 在 `frontend/src/App.tsx` 中补状态机与本地 state。
   - 把 `RequestState` 扩成：
     - `idle`
     - `starting`
     - `awaiting_clarification`
     - `clarifying`
     - `awaiting_confirmation`
     - `refreshing`
     - `confirming`
     - `declining`
     - `completed`
     - `declined`
     - `error`
   - 新增 clarification reply state：
     - `clarificationReply`
   - 新增辅助布尔：
     - `isAwaitingClarification`
     - `clarificationReplyIsEmpty`
     - `canClarify`
   - 在 `stateFromRun(...)` 中把 `awaiting_clarification` 显式映射回来，避免 header badge 错误显示成 `idle`。

6. 在 `frontend/src/App.tsx` 中实现 `handleClarify()`。
   - 它只允许在当前 `run.run_id` 存在且 `canClarify` 为 true 时触发。
   - 调用 `runAction("clarifying", () => clarifyRun(run.run_id, { user_input: clarificationReply.trim(), selected_plan_index: 0 }))`。
   - clarification success 后：
     - 继续复用 `runAction(...)` 的 run 替换逻辑
     - 清空 `clarificationReply`
   - clarification failure 后：
     - 保留 `clarificationReply`
     - 继续复用现有 `error-banner`

7. 在 `frontend/src/App.tsx` 中加入 clarification view 分支。
   - 在 workspace render 逻辑中把渲染顺序改成：
     1. `run.status === "awaiting_clarification"` 且 `run.clarification` 存在时，渲染 `ClarificationPanel`
     2. 否则如果 `run && selectedPlan`，渲染现有 plan / confirm / execution 内容
     3. 否则渲染 empty workspace
   - 不要把 clarification panel 挤进 `PlanDetail` 或 `RunInspector`，保持它是独立 panel。

8. 在 `frontend/src/App.tsx` 中新增本地 helper 和 panel 组件。
   - 增加 `clarificationFieldLabel(...)`：
     - `scenario_or_participants` -> `出行人/场景`
     - `time_window` -> `时间安排`
     - `distance_flexibility` -> `距离取舍`
     - `preference_tradeoff` -> `偏好取舍`
     - unknown -> 原 token
   - 新增 `ClarificationPanel` 子组件，放在当前文件内，不拆新文件。
   - `ClarificationPanel` 使用这些固定文案：
     - 标题 `需要补充信息`
     - 字段标签 `待补充项`
     - 输入标签 `补充说明`
     - helper `补充后会继续当前规划流程，仍会在确认前停下。`
     - 按钮 `提交补充信息`
     - loading `提交中...`
   - `ClarificationPanel` 必须带这些 test ids：
     - `clarification-panel`
     - `clarification-fields`
     - `clarification-reply-input`
     - `clarification-submit-button`

9. 为 clarification panel 做最小样式补充。
   - 在 `frontend/src/styles.css` 中新增：
     - `.clarification-panel`
     - `.clarification-chip-list`
     - `.clarification-chip`
     - `.clarification-textarea`
   - `clarification-textarea` 必须覆盖全局 `textarea` 的 `min-height: 184px`，把 clarification reply 控件压到更合理的高度，例如 96px 左右。
   - 不改整体布局栅格，不动 internal surface 样式。

10. 更新 `frontend/e2e/demo.spec.ts`。
    - 保留现有 happy path、decline、refresh、redaction、mobile smoke。
    - 新增一条 clarification browser flow：
      - 打开 `/`
      - 清空默认 prompt，输入 `想周末出去玩一下。`
      - 点击开始规划
      - 断言 `run-status == 等待补充信息`
      - 断言 `plan-version == v1`
      - 断言 `action-count == 0`
      - 断言 `clarification-panel` 可见
      - 记录当前 `run-id`
      - 输入 `今天下午一个人出门玩几个小时，别太远。`
      - 点击 `clarification-submit-button`
      - 断言 `run-status == 等待确认`
      - 断言新的 `run-id` 不同于旧值
      - 断言 `plan-version` 仍然是 `v1`
      - 断言 `confirm-button` 可见
    - 这一条测试必须继续跑在现有 Playwright 配置下，不加新 server。

11. 更新文档。
    - `README.md`：
      - Web Demo API 段落增加“customer page 已可直接补充信息”
      - Minimal Web UI 段落增加 clarification panel 说明
    - `docs/WEB_DEMO_README.md`：
      - Clarification Path 改成先走 5173 页面
      - `curl /clarify` 作为 API 验证备选
      - 继续强调 clarification-only run 与首个真实方案 run 都显示 `v1`

12. 跑验证并仅 stage 本任务文件。
    - 先跑 frontend unit tests、build。
    - 再跑 backend demo API regression 和 Playwright。
    - 最后跑 `git diff --check` 与 `git status --short`。
    - staging 时确认无关本地文件仍未被纳入。

## 6. Testing Plan

- `frontend/src/api/demo.test.ts`
  - `clarifyRun(...)` request path/body
  - clarification-path localized 409 messages
- `frontend/src/App.test.tsx`
  - `awaiting_clarification` 初始渲染
  - localized missing fields
  - submit button disabled on empty reply
  - clarify success -> new run id + `awaiting_confirmation` + `v1`
  - repeated clarify -> still shows clarification panel
  - no confirm button while clarification is pending
- `frontend/e2e/demo.spec.ts`
  - vague request -> `awaiting_clarification` -> submit clarification -> `awaiting_confirmation`
- Backend regression checks
  - `tests/test_demo_api.py`
  - `tests/integration/test_demo_api_gateway.py`
- Build check
  - `npm --prefix frontend run build`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/api/demo.test.ts src/App.test.tsx
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -q
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add customer demo clarification flow
```

Expected commands:

```bash
git switch -c codex/customer-demo-clarification-flow-v0
git status --short
git add frontend/src/types/demo.ts
git add frontend/src/api/demo.ts
git add frontend/src/api/demo.test.ts
git add frontend/src/App.tsx
git add frontend/src/App.test.tsx
git add frontend/src/styles.css
git add frontend/e2e/demo.spec.ts
git add README.md
git add docs/WEB_DEMO_README.md
git add docs/specs/059-customer-demo-clarification-flow-v0.md
git add docs/plans/059-customer-demo-clarification-flow-v0-plan.md
git diff --cached --check
git commit -m "feat: add customer demo clarification flow"
git push -u origin codex/customer-demo-clarification-flow-v0
```

The implementer must verify that `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`、`var/` and any local build artifacts remain unstaged.

## 9. Out-of-scope Changes

- 不新增 replan customer UI。
- 不新增 conversation history UI 或 session browser。
- 不修改 backend API schema、database schema、workflow routing、provider、benchmark 或 internal observability schema。
- 不重做页面布局，不顺手大规模改 CSS。
- 不引入新的 npm dependency 或 i18n framework。
- 不修改 internal review surface `5174` 的任何行为。
- 不暂存当前工作区已有的无关本地文件。

## 10. Review Checklist

- [ ] 实现与 `docs/specs/059-customer-demo-clarification-flow-v0.md` 一致。
- [ ] clarification contract 只在 frontend 消费层补齐，没有误改 backend。
- [ ] customer page 在 `awaiting_clarification` 时显示 clarification panel，而不是 empty workspace。
- [ ] clarification panel 能正确显示 prompt 和已知 missing fields 的中文标签。
- [ ] submit 空输入禁用、submit 成功能切到下一 run、submit 失败保留 draft。
- [ ] clarification 首次成功产出真实方案时仍显示 `v1`。
- [ ] `confirm-button` 不会在 clarification-pending 状态下出现。
- [ ] AMap read-only、decline、refresh、redaction 现有行为无回归。
- [ ] frontend unit tests 通过。
- [ ] frontend build 通过。
- [ ] Playwright E2E 通过。
- [ ] backend demo API regression 通过。
- [ ] `git diff --check` 通过。
- [ ] Git status 在提交后没有新增无关 staged 文件。
- [ ] commit message 与计划一致。
- [ ] push 成功。
- [ ] 没有 `.env`、API key、token、secret 或本地 runtime artifact 被提交。

## 11. Handoff Notes

完成后需要回报：

- 实际修改的文件列表。
- clarification panel 的最终 customer-visible 文案。
- clarification flow 的一个真实 UI 路径示例：
  - 起始模糊请求
  - clarification prompt
  - clarification reply
  - 新 run id
  - 仍保持 `v1`
- 新增或修改的测试及结果。
- 运行过的验证命令与结果。
- commit hash 与 push 结果。
- 是否需要了 `frontend/src/styles.css` 的 clarification-specific 样式。
- 无关本地文件是否保持 unstaged。
- 后续 follow-up：replan customer UI 仍未做，仍应保留为下一张更小的 task。
