# Spec: 060 Customer Demo Replan Flow v0

## 1. Goal

为 `http://127.0.0.1:5173/` 的 customer surface 补上第一条真正可走通的 follow-up replan 前端路径：当页面已经拿到一个可评审方案后，用户不再需要切到命令行执行 `curl /replan`，而是可以直接在客户页输入新的限制或偏好，调用 `POST /demo/runs/{run_id}/replan`，并在同一页面继续查看新的方案版本。

当前仓库已经在 task `044` 完成了 `/replan` backend contract，在 task `045` 完成了公开 `plan_version`，在 task `046` 完成了 `action_manifest`，在 task `048` 和 `059` 完成了 clarification backend + customer frontend。现阶段缺的不是新的多轮后端能力，而是 customer surface 对 follow-up replan 的接入。完成本任务后，客户页可以直接演示 `v1 -> v2 -> v3` 的方案演进，而不是只靠 README 和 API 示例说明这个能力存在。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 Minimal Web UI 定义为 MVP 的主要演示路径，并要求系统具备会话式规划能力，而不是一次性输出静态推荐。`docs/NEXT_PHASE_ROADMAP.md` 将这类能力归入 `M4. 多轮对话与方案版本`，并明确列出：

- `7. 多轮澄清与 replan 工作流`
- `8. plan versioning 与执行前 action manifest`

当前工作区已经具备这两个条目的后端基础和半前端收口：

- Task `044` 已有 `POST /demo/runs/{run_id}/replan`
- Task `045` 已有公开 `plan_version`
- Task `046` 已有公开 `action_manifest`
- Task `048` 已有 clarification workflow
- Task `059` 已有 customer clarification panel

因此，这张卡是一个面向客户演示面的 convergence slice：它不新增 backend contract，只把已经存在的 replan / version lineage contract 真正接进 5173 customer page。它直接触达这些 blueprint 领域：

- Minimal Web UI / Web demo API path
- Human-in-the-loop conversation flow before confirmation
- Public plan version semantics
- Customer-safe public surface boundary

## 3. Requirements

- 前端类型层必须补齐 replan contract。
- `frontend/src/types/demo.ts` 必须新增：
  - `DemoReplanRunRequest`
- `DemoReplanRunRequest` 的前端字段必须与后端 public contract 保持一致：
  - `user_input: string`
  - `selected_plan_index: number`

- 前端 API client 必须新增 replan request。
- `frontend/src/api/demo.ts` 必须新增：
  - `replanRun(runId: string, input: DemoReplanRunRequest): Promise<DemoRunSummary>`
- `replanRun(...)` 必须调用：
  - `POST /demo/runs/{run_id}/replan`
- request body 在本 task 中必须固定只发送：
  - `user_input`
  - `selected_plan_index`
- 当前 customer frontend 必须继续保持：
  - `startRun(...)`
  - `getRun(...)`
  - `clarifyRun(...)`
  - `confirmRun(...)`
  - `declineRun(...)`
  行为不变。

- `frontend/src/api/demo.ts` 的本地化错误映射必须补齐 replan path 直接可见的 detail。
- 至少覆盖这些 backend detail：
  - `Source run status does not allow replanning.` -> `当前运行还不能继续调整方案，请刷新状态后重试。`
  - `Source run is missing session persistence for replanning.` -> `当前运行缺少继续规划会话，请重新开始规划。`
  - `Source run session is unavailable for replanning.` -> `当前运行缺少继续规划会话，请重新开始规划。`
  - `Source run user is unavailable for replanning.` -> `当前运行缺少关联用户，请重新开始规划。`
- 其余未知错误继续复用现有 generic fallback。

- customer surface 状态机必须显式支持 replan submit 过程。
- `frontend/src/App.tsx` 的 `RequestState` 必须新增：
  - `replanning`
- `isInFlight` 计算必须把 `replanning` 视为 in-flight。
- 顶部 `StatusBadge` 与按钮 loading 文案必须对 `replanning` 有一致中文显示，不允许回退成 `idle`。

- customer surface 必须新增独立的 replan draft state。
- replan draft 必须与这些现有输入严格分离：
  - 主请求 textarea
  - clarification reply textarea
- replan submit 不得覆盖主请求 textarea 的当前内容。
- replan submit 不得复用 clarification reply state。

- 本 task 的 replan 入口必须刻意收窄为最小可验证单元。
- 仅当同时满足这些条件时，customer page 才渲染 replan panel：
  - `run.status == "awaiting_confirmation"`
  - 当前页面存在 `selectedPlan`
- 本 task 不要求在这些状态暴露 replan panel：
  - `declined`
  - `completed`
  - `failed`
  - `awaiting_clarification`
- backend 已支持更宽 source status，但 frontend v0 不扩到这些路径。

- replan panel 必须是 customer-visible 的独立面板，而不是复用 clarification panel 或 side rail 的主输入区。
- replan panel 必须包含这些中文元素：
  - 标题：`继续调整方案`
  - 说明文案：`补充新的限制或偏好后，会基于当前运行创建新的方案版本，并切换到新的 run。`
  - 输入标签：`新的需求或限制`
  - 独立 textarea
  - 提交按钮：`重新规划当前方案`
  - 提交中按钮文案：`重新规划中...`
- replan panel 必须暴露稳定测试定位点：
  - `data-testid="replan-panel"`
  - `data-testid="replan-reply-input"`
  - `data-testid="replan-submit-button"`

- replan submit 行为必须满足：
  - 当 reply `trim()` 为空时，提交按钮禁用
  - 当已有 in-flight request 时，提交按钮禁用
  - 本 task 固定发送 `selected_plan_index = 0`
  - submit 成功后必须用返回的 `DemoRunSummary` 全量替换当前 loaded run
  - submit 成功后 replan draft 必须清空
  - submit 失败时必须保留用户当前 draft
  - submit 成功且返回 `awaiting_confirmation` 时，页面必须继续走既有方案评审流
  - submit 成功且返回 `awaiting_clarification` 时，页面必须自动切回已有 clarification panel，而不是报错或停在旧方案页

- 现有 run inspector 必须继续承担版本可见性。
- replan 成功后，页面必须可见这些已更新字段：
  - `run.run_id`
  - `run.status`
  - `run.read_profile`
  - `run.plan_version.version_label`
- 对连续 follow-up replan，客户页必须直接展示：
  - 第一次 replan 后 `v2`
  - 第二次 replan 后 `v3`
- 版本显示仍以既有 `run.plan_version.version_label` 为准，不新增第二套版本来源。

- 当前 public boundary 必须保持不变：
  - 不暴露 `session_id`
  - 不暴露 conversation turn payloads
  - 不暴露 internal observability fields
  - 不暴露 trace IDs / agent roles / node history
- internal observability surface `http://127.0.0.1:5174/` 不得改动。

- AMap 只读预览路径不得回归。
- 当当前 run 的 `read_profile == "amap"` 且状态为 `awaiting_confirmation` 时：
  - replan panel 仍可见并可提交 follow-up
  - 现有 confirm block 继续保持只读限制，不因 replan UI 出现而恢复 confirm
  - replan 返回的新 run 必须继续使用 backend 返回的 `read_profile`

- README 与 `docs/WEB_DEMO_README.md` 必须更新为 customer demo 真实现状：
  - 说明 5173 customer page 现在可以直接做 follow-up replan
  - Replan path 的主演示步骤改为前端表单，而不是只依赖 `curl`
  - `curl /replan` 示例可保留为 API-level 验证方式
  - 继续说明每次 replan 都返回新 `run_id`，并把 `plan_version.version_label` 推进到 `v2`、`v3`

- 必须新增或更新这些测试：
  - `frontend/src/api/demo.test.ts`
  - `frontend/src/App.test.tsx`
  - `frontend/e2e/demo.spec.ts`
- 必须继续跑现有 backend demo API 回归，确认 frontend 假设没有偏离既有 contract。

- 不得修改：
  - backend API schema
  - database schema
  - workflow routing
  - plan version rules
  - action manifest schema
  - internal observability schema
  - dependencies

## 4. Non-goals

- 不新增 conversation history、session browser 或版本对比页。
- 不把当前 UI 的 tab 切换持久化为 source selected plan。
- 不为 replan 新增 plan-index selector；本 task 固定发送 `selected_plan_index = 0`。
- 不在 v0 中暴露 `declined`、`completed`、`failed` run 的 replan 入口。
- 不修改 backend 的 `/replan`、`/clarify`、`/confirm`、`/decline` contract。
- 不改 `backend/app/demo/service.py`、数据库、Alembic、Redis 或 workflow 节点。
- 不改 internal observability page 的文案、结构或测试。
- 不引入 i18n framework、locale switcher 或新的 npm dependency。
- 不重做 App 的整体布局，只允许为 replan panel 做最小样式补充。
- 不暂存或提交 `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`、`var/`、`frontend/dist/` 等无关本地文件。

## 5. Interfaces and Contracts

### Inputs

- 现有 public demo run summary：
  - `DemoRunSummary`
- follow-up replan request：
  - `POST /demo/runs/{run_id}/replan`
- replan request body：
  - `user_input`
  - `selected_plan_index`
- customer page 当前已有 API actions：
  - `startRun`
  - `getRun`
  - `clarifyRun`
  - `confirmRun`
  - `declineRun`

### Outputs

- customer page 在 plan-bearing `awaiting_confirmation` run 上展示可交互的 replan panel。
- customer page 可以直接发起 follow-up replan，并接收新的 `DemoRunSummary`。
- replan 成功后的页面继续沿用既有 plan review / confirmation / clarification UI。
- public payload shape 保持不变，前端仅补消费。

### Schemas

Replan submit request:

```json
{
  "user_input": "Keep it nearby, but make it a solo outing this time.",
  "selected_plan_index": 0
}
```

Successful follow-up response excerpt:

```json
{
  "run_id": "00000000-0000-0000-0000-000000000011",
  "status": "awaiting_confirmation",
  "read_profile": "mock_world",
  "selected_plan_id": "00000000-0000-0000-0000-000000000021",
  "plan_version": {
    "version_number": 2,
    "version_label": "v2",
    "source_run_id": "00000000-0000-0000-0000-000000000010",
    "source_selected_plan_id": "00000000-0000-0000-0000-000000000020"
  },
  "clarification": null
}
```

Replan panel display contract:

```json
{
  "panel_title": "继续调整方案",
  "reply_label": "新的需求或限制",
  "submit_label": "重新规划当前方案",
  "submitting_label": "重新规划中..."
}
```

## 6. Observability

本任务不新增任何新的 observability contract、trace metadata、benchmark artifact 或数据库持久化字段。

需要保持不变的事实：

- customer page 继续仅消费公开 `DemoRunSummary`
- 版本切换继续通过已有 `run_id` 与 `plan_version` 可见
- public payload 仍保持 redacted
- internal review 仍使用既有 `GET /internal/runs/{run_id}/observability`

如果需要确认 replan path 行为，应依赖现有 public API contract、frontend tests 与 Playwright，而不是添加新的观测接口。

## 7. Failure Handling

- 如果 replan reply 为空，前端必须在客户端禁用提交按钮，而不是发送空请求。
- 如果当前 loaded run 不满足 replan panel 渲染条件，页面不得展示可点击 replan submit。
- 如果 `/replan` 返回 `404` 或 `409`，前端必须显示本地化错误文案，并保留当前 replan draft。
- 如果 `/replan` 成功但返回 `awaiting_clarification`，这属于有效成功路径；页面必须切到已有 clarification panel。
- 如果用户在 replan 成功后点击 `刷新状态`，并且后端返回同一新 run 的合法状态，页面必须继续显示对应的新 `run_id` 与 `plan_version`。
- replan path 不得破坏 AMap read-only 预览限制；AMap confirm block 继续只在 `awaiting_confirmation` 阶段生效。
- replan path 不得破坏现有 clarification、decline、refresh、public redaction path。

## 8. Acceptance Criteria

- [ ] `docs/specs/060-customer-demo-replan-flow-v0.md` 存在并匹配本任务。
- [ ] `docs/plans/060-customer-demo-replan-flow-v0-plan.md` 存在并匹配本任务。
- [ ] 当前编号链保持 `001` 到 `059` 连续匹配，本任务使用新的 `060` 编号。
- [ ] `frontend/src/types/demo.ts` 已支持 `DemoReplanRunRequest`。
- [ ] `frontend/src/api/demo.ts` 已支持 `replanRun(...)`，并调用 `POST /demo/runs/{run_id}/replan`。
- [ ] `frontend/src/api/demo.ts` 已补齐 replan path 的 customer-facing 错误本地化。
- [ ] customer page 在 plan-bearing `awaiting_confirmation` run 上显示 replan panel。
- [ ] replan panel 有独立 textarea 和提交按钮，不复用主请求输入区或 clarification reply。
- [ ] replan submit 空输入时按钮禁用。
- [ ] replan submit 成功后，页面用返回的新 `run_id` 更新当前 loaded run。
- [ ] 第一次 replan 成功后，customer page 显示 `plan_version.version_label = v2`。
- [ ] 第二次连续 replan 成功后，customer page 显示 `plan_version.version_label = v3`。
- [ ] replan submit 若返回 `awaiting_clarification`，页面会切到已有 clarification panel，而不是报错。
- [ ] public page 仍不暴露 `session_id`、conversation history、trace fields 或 internal labels。
- [ ] AMap 只读预览、clarification、confirm/decline、refresh、public redaction 现有行为不回归。
- [ ] README 与 `docs/WEB_DEMO_README.md` 已改成“customer page 可直接完成 replan”的演示说明。
- [ ] `frontend/src/api/demo.test.ts`、`frontend/src/App.test.tsx`、`frontend/e2e/demo.spec.ts` 已覆盖 replan path。
- [ ] `npm --prefix frontend run build` 通过。
- [ ] 后端 demo API contract regression 通过。
- [ ] `git diff --check` 通过。
- [ ] 没有 `.env`、API key、token、secret 或无关本地文件被提交。
- [ ] 提交后工作树只保留本任务外原本就存在的本地脏文件。

## 9. Verification Commands

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

## 10. Expected Commit

```text
feat: add customer demo replan flow
```

## 11. Notes for the Implementer

这张卡故意不碰会话历史、版本对比或 post-completion replan。原因不是这些能力不重要，而是当前 5173 主演示面上的真实断点，是“`/replan` 已有 contract 和文档，但前端无法直接走通”。

实现时保持几个边界：

- replan panel 只做确认前的 customer follow-up，不做 history browser
- 当前页面继续只持有一个 active run；`v1 -> v2 -> v3` 通过替换当前 loaded run 来展示
- 固定 `selected_plan_index = 0`，不把本地 tab 切换持久化为 backend source selection
- 如果当前执行基线不包含 task `059` 的 clarification customer UI，先补齐或换到包含等价内容的基线再做本任务
