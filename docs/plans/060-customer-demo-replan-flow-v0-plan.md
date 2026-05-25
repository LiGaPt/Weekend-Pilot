# Plan: 060 Customer Demo Replan Flow v0

## 1. Spec Reference

Spec file:

```text
docs/specs/060-customer-demo-replan-flow-v0.md
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

- 当前工作区分支是 `codex/customer-demo-clarification-flow-v0`。
- 当前工作区最新提交是 `65c9d17 feat: add customer demo clarification flow`，它与 task `059` 对齐。
- `docs/specs/` 与 `docs/plans/` 从 `001` 到 `059` 连续且 slug 一一匹配。
- `origin/main` 当前仍停在已合入 `057` 的基线上，不包含当前工作区的 `058/059` customer demo 收口。
- customer frontend 当前已经具备：
  - clarification 类型、API client、panel、测试
  - `plan_version` 可见性
  - `action_manifest` 渲染
  - AMap read-only 预览约束
- customer frontend 当前仍缺这些内容：
  - `frontend/src/types/demo.ts` 没有 `DemoReplanRunRequest`
  - `frontend/src/api/demo.ts` 没有 `replanRun`
  - `frontend/src/App.tsx` 没有 replan draft state、replan panel 或 replan submit 状态
  - `frontend/src/App.test.tsx` 和 `frontend/e2e/demo.spec.ts` 没有 customer-side replan coverage
  - `README.md` 与 `docs/WEB_DEMO_README.md` 的 replan 演示仍以 `curl` 为主
- 本任务应以当前 `65c9d17` 为执行基线新开分支 `codex/customer-demo-replan-flow-v0`；如果先回到别的基线，必须确保已有等价的 `058/059` 内容。
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

- `frontend/src/types/demo.ts` - 补齐 `DemoReplanRunRequest` 类型。
- `frontend/src/api/demo.ts` - 新增 `replanRun(...)` 并补 replan-path 错误本地化映射。
- `frontend/src/api/demo.test.ts` - 增加 `replanRun(...)` request body 与 replan-specific error localization 测试。
- `frontend/src/App.tsx` - 扩展 request state、replan reply state、replan panel、submit flow、view switching 和按钮状态。
- `frontend/src/App.test.tsx` - 覆盖 replan panel、submit disabled、`v1 -> v2 -> v3`、新 `run_id`、clarification handoff 等行为。
- `frontend/src/styles.css` - 只为 replan panel 增加最小样式，如 textarea 高度和 panel spacing。
- `frontend/e2e/demo.spec.ts` - 增加 customer-page replan browser flow。
- `README.md` - 把 Web Demo API / Minimal Web UI 说明同步到“customer page 已可直接 replan”。
- `docs/WEB_DEMO_README.md` - 把 Replan Path 主演示步骤从 `curl` 改成 customer page 表单，并保留 `curl` 作为 API 验证备选。

## 5. Implementation Steps

1. 先补前端类型，再写 API client 失败测试。
   - 在 `frontend/src/types/demo.ts` 中定义 `DemoReplanRunRequest`。
   - 保持其他既有类型不变，不动 backend shape。
   - 在 `frontend/src/api/demo.test.ts` 先补失败用例，确保 `replanRun("run-1", { user_input, selected_plan_index: 0 })` 会打到 `/demo/runs/run-1/replan`。

2. 在 `frontend/src/api/demo.test.ts` 增加 replan-path 错误本地化测试。
   - 至少覆盖：
     - `Source run status does not allow replanning.`
     - `Source run is missing session persistence for replanning.`
     - `Source run session is unavailable for replanning.`
     - `Source run user is unavailable for replanning.`
   - 保持现有 clarify/confirm/start/get 测试不回退。

3. 实现 `replanRun(...)` 和错误本地化。
   - 在 `frontend/src/api/demo.ts` 中新增 `replanRun(...)`。
   - 复用现有 `request<T>(...)` helper，不引入新 transport。
   - 在 `localizedResponseMessage(...)` 中加入 replan-path detail 映射。

4. 先写 `frontend/src/App.test.tsx` 的 replan 失败用例和 fixture。
   - 新增 `replannedRunV2`、`replannedRunV3` fixture：
     - 新 `run_id`
     - `status = "awaiting_confirmation"`
     - `plan_version.version_label = "v2"` / `"v3"`
   - 新增一个 `replannedAwaitingClarificationRun` fixture：
     - `status = "awaiting_clarification"`
     - `plans = []`
     - `clarification` 非空
     - `plan_version.version_label = "v2"`
   - 至少覆盖这些断言：
     - `awaiting_confirmation` run 会显示 `replan-panel`
     - replan submit 空输入时按钮禁用
     - replan submit 成功后调用 `replanRun(run_id, { user_input, selected_plan_index: 0 })`
     - replan success 后 `run-id` 更新为新的 run id
     - replan success 后 `plan-version` 依次显示 `v2`、`v3`
     - replan success 后 `confirm-button` 仍可见
     - replan 若返回 `awaiting_clarification`，页面切回 `clarification-panel`

5. 在 `frontend/src/App.tsx` 中补 replan 状态与本地 state。
   - 把 `RequestState` 扩成：
     - `idle`
     - `starting`
     - `awaiting_clarification`
     - `clarifying`
     - `awaiting_confirmation`
     - `replanning`
     - `refreshing`
     - `confirming`
     - `declining`
     - `completed`
     - `declined`
     - `error`
   - 新增 `replanReply` state。
   - `isInFlight` 必须包含 `replanning`。
   - `statusLabel(...)` 补 `replanning -> 重新规划中`。

6. 在 `frontend/src/App.tsx` 中实现 replan eligibility 和 submit handler。
   - 新增辅助布尔：
     - `showReplanPanel = Boolean(run?.status === "awaiting_confirmation" && selectedPlan)`
     - `replanReplyIsEmpty`
     - `canReplan`
   - `canReplan` 规则：
     - `showReplanPanel`
     - `run.run_id` 存在
     - `replanReply.trim().length > 0`
     - 当前不在任何 in-flight 状态
   - 新增 `handleReplan()`：
     - 调用 `runAction("replanning", () => replanRun(run.run_id, { user_input: replanReply.trim(), selected_plan_index: 0 }), () => setReplanReply(""))`
   - submit 失败时不清空 `replanReply`。

7. 在 `frontend/src/App.tsx` 中加入独立 `ReplanPanel` 子组件。
   - `ReplanPanel` 仍放在当前文件内，不拆新文件。
   - 使用固定文案：
     - 标题 `继续调整方案`
     - 说明 `补充新的限制或偏好后，会基于当前运行创建新的方案版本，并切换到新的 run。`
     - 标签 `新的需求或限制`
     - 按钮 `重新规划当前方案`
     - loading `重新规划中...`
   - 使用这些 test ids：
     - `replan-panel`
     - `replan-reply-input`
     - `replan-submit-button`

8. 调整 workspace 渲染顺序，但不要重做页面结构。
   - 维持 clarification panel 优先级最高：
     1. `awaiting_clarification` 且 `clarification` 有效 -> `ClarificationPanel`
     2. 否则如果 `run && selectedPlan` -> 既有 plan review / confirm / execution 视图
   - 在 plan review 视图内，把 `ReplanPanel` 放在 `ConfirmationControls` 后、`ExecutionResult` 前。
   - 这样 replan 成功如果返回 `awaiting_clarification`，现有顶层 render 分支会自动切回 clarification panel。

9. 为 replan panel 做最小样式补充。
   - 在 `frontend/src/styles.css` 中新增：
     - `.replan-panel`
     - `.replan-textarea`
   - `replan-textarea` 可沿用 clarification textarea 的更短高度，不要继承主请求 textarea 的大高度。
   - 不改整体 grid，不碰 internal surface 样式。

10. 更新 `frontend/e2e/demo.spec.ts`。
    - 保留现有 happy path、decline、refresh、clarification、redaction、mobile smoke。
    - 新增一条 replan browser flow：
      - 打开 `/`
      - 启动一个正常 `awaiting_confirmation` run
      - 断言 `plan-version == v1`
      - 断言 `replan-panel` 可见
      - 记录当前 `run-id`
      - 填写 follow-up 输入并提交
      - 断言状态仍是 `awaiting_confirmation`
      - 断言新的 `run-id` 不同于旧值
      - 断言 `plan-version == v2`
      - 再次提交 follow-up
      - 断言 `plan-version == v3`
    - 继续沿用现有 Playwright runner，不加新 server。

11. 更新文档。
    - `README.md`
      - Web Demo API 段落增加“customer page 已可直接做 follow-up replan”
      - Minimal Web UI 段落增加 replan panel 说明
      - 保留 `curl /replan` 作为 API-level 示例
    - `docs/WEB_DEMO_README.md`
      - Replan Path 改成先走 5173 页面
      - 再给 `curl /replan` 作为 fallback 验证
      - 明确说明连续 replan 让 `plan_version.version_label` 变成 `v2`、`v3`

12. 跑验证并仅 stage 本任务文件。
    - 先跑 frontend unit tests、build。
    - 再跑 backend demo API regression 和 Playwright。
    - 最后跑 `git diff --check` 与 `git status --short`。
    - staging 时确认无关本地文件仍未被纳入。

## 6. Testing Plan

- Unit tests:
  - `frontend/src/api/demo.test.ts`
  - `replanRun(...)` request path/body
  - replan-path localized 409 messages
  - `frontend/src/App.test.tsx`
  - replan panel 初始渲染
  - submit button disabled on empty reply
  - replan success -> new run id + `v2`
  - second replan success -> `v3`
  - replan -> `awaiting_clarification` handoff
- Integration tests:
  - backend contract regression only
  - `tests/test_demo_api.py`
  - `tests/integration/test_demo_api_gateway.py`
- Smoke tests:
  - `frontend/e2e/demo.spec.ts` 新增 customer-page replan flow
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
feat: add customer demo replan flow
```

Expected commands:

```bash
git switch -c codex/customer-demo-replan-flow-v0
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
git add docs/specs/060-customer-demo-replan-flow-v0.md
git add docs/plans/060-customer-demo-replan-flow-v0-plan.md
git diff --cached --check
git commit -m "feat: add customer demo replan flow"
git push -u origin codex/customer-demo-replan-flow-v0
```

The implementer must verify that `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`、`var/` and any local build artifacts remain unstaged.

## 9. Out-of-scope Changes

- 不新增 conversation history UI、session browser 或版本对比页。
- 不为 `declined`、`completed`、`failed` run 暴露 replan panel。
- 不新增 source-plan persistence 或 plan-index selector。
- 不修改 backend API schema、database schema、workflow routing、plan version 规则、provider、benchmark 或 internal observability schema。
- 不重做页面布局，不顺手大规模改 CSS。
- 不引入新的 npm dependency 或 i18n framework。
- 不修改 internal review surface `5174` 的任何行为。
- 不暂存当前工作区已有的无关本地文件。

## 10. Review Checklist

- [ ] 实现与 `docs/specs/060-customer-demo-replan-flow-v0.md` 一致。
- [ ] replan contract 只在 frontend 消费层补齐，没有误改 backend。
- [ ] customer page 在 plan-bearing `awaiting_confirmation` run 上显示 replan panel。
- [ ] replan panel 有独立 textarea，且不覆盖主请求输入区或 clarification reply。
- [ ] submit 空输入禁用、submit 成功切到新 run、submit 失败保留 draft。
- [ ] 连续 replan 后版本标签按 `v1 -> v2 -> v3` 可见。
- [ ] replan 若返回 `awaiting_clarification`，页面会切回 clarification panel。
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
- replan panel 的最终 customer-visible 文案。
- 一条真实 UI 路径示例：
  - 初始 `v1` run
  - follow-up replan 文本
  - 新 `run_id`
  - `v2`
  - 第二次 follow-up 后的 `v3`
- 新增或修改的测试及结果。
- 运行过的验证命令与结果。
- commit hash 与 push 结果。
- 是否需要了 `frontend/src/styles.css` 的 replan-specific 样式。
- 无关本地文件是否保持 unstaged。
- 后续 follow-up：post-completion / declined replan 入口、history / version compare 仍未做，应保留为后续更小 task。
