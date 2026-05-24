# Spec: 059 Customer Demo Clarification Flow v0

## 1. Goal

为 `http://127.0.0.1:5173/` 的 customer surface 补上第一条真正可走通的 clarification continuation 路径：当后端返回 `awaiting_clarification` 时，客户页不再停在空白态或只能靠 `curl`，而是直接展示补充信息提示、收集用户回复、调用 `POST /demo/runs/{run_id}/clarify`，并在同一页面里继续后续规划流程。

仓库已经在 task `048` 完成了 clarification backend contract，在 task `044`、`045`、`046` 完成了 follow-up run、plan version 和 action manifest，在 task `056`、`058` 把 customer/internal surface 分离并收口中文 customer demo。当前真正缺的不是新的后端能力，而是 customer surface 对既有 clarification contract 的接入。完成本任务后，模糊请求的主演示路径可以在 Web UI 内完整走完“开始规划 -> 等待补充信息 -> 提交补充信息 -> 等待确认”，而不是被迫切换到命令行。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 Minimal Web UI 定义为 MVP 的主要演示路径，并要求系统能够通过多轮交互完成“理解需求 -> 生成方案 -> 等待确认”的闭环，而不是只做一次性推荐。`docs/NEXT_PHASE_ROADMAP.md` 把多轮澄清、replan、版本演进归到 `M4. 多轮对话与方案版本`。

当前仓库状态已经具备本任务所依赖的所有后端基础：

- Task `044` 已有同会话 follow-up run 与 `/replan`
- Task `045` 已有公开 `plan_version`
- Task `046` 已有稳定 `action_manifest`
- Task `048` 已有 `awaiting_clarification`、`clarification` summary 和 `POST /demo/runs/{run_id}/clarify`
- Task `056` 已完成 customer/internal 前端分离
- Task `058` 已把 customer surface reviewer-facing 文案收口为中文

因此，这张卡是一个典型的 convergence slice：它不新增后端能力，只把已有 clarification contract 真正接到客户演示面上。它直接触达这些 blueprint 领域：

- Minimal Web UI / Web demo API path
- Human-in-the-loop conversation flow before confirmation
- Public plan version semantics
- Customer-safe public surface boundary

## 3. Requirements

- 前端类型层必须补齐 clarification contract。
- `frontend/src/types/demo.ts` 必须新增：
  - `DemoClarificationSummary`
  - `DemoClarifyRunRequest`
- `DemoRunSummary` 必须新增：
  - `clarification: DemoClarificationSummary | null`
- `DemoClarificationSummary` 的前端字段必须与后端 public contract 保持一致：
  - `prompt: string`
  - `missing_fields: string[]`
- `DemoClarifyRunRequest` 的前端字段必须与后端 public contract 保持一致：
  - `user_input: string`
  - `selected_plan_index: number`

- 前端 API client 必须新增 clarification request。
- `frontend/src/api/demo.ts` 必须新增：
  - `clarifyRun(runId: string, input: DemoClarifyRunRequest): Promise<DemoRunSummary>`
- `clarifyRun(...)` 必须调用：
  - `POST /demo/runs/{run_id}/clarify`
- request body 必须只发送：
  - `user_input`
  - `selected_plan_index`
- 现有 `startRun/getRun/confirmRun/declineRun` 行为必须保持不变。

- customer surface 状态机必须显式支持 clarification。
- `frontend/src/App.tsx` 的 `RequestState` 必须新增：
  - `awaiting_clarification`
  - `clarifying`
- `stateFromRun(...)` 在 `run.status == "awaiting_clarification"` 时必须返回：
  - `awaiting_clarification`
- 顶部 `StatusBadge`、运行摘要区和 clarifying submit 按钮必须使用一致的中文状态显示，不允许 clarification run 被错误回落成 `idle`。

- 当 `run.status == "awaiting_clarification"` 时，workspace 必须渲染专用 clarification panel，而不是：
  - 默认 empty workspace
  - 方案 tabs
  - plan detail
  - confirmation controls
  - execution result
- clarification panel 必须包含这些 customer-visible 元素：
  - 中文 section 标题：`需要补充信息`
  - 后端返回的 `clarification.prompt` 原样展示
  - `clarification.missing_fields` 的可见列表
  - 中文字段标签：`待补充项`
  - 中文输入标签：`补充说明`
  - 独立的 clarification reply 输入区
  - 中文 helper：`补充后会继续当前规划流程，仍会在确认前停下。`
  - 中文提交按钮：`提交补充信息`
  - 提交中按钮文案：`提交中...`

- clarification panel 必须暴露稳定测试定位点：
  - `data-testid="clarification-panel"`
  - `data-testid="clarification-fields"`
  - `data-testid="clarification-reply-input"`
  - `data-testid="clarification-submit-button"`
- 现有 `data-testid` 必须保持不变。

- clarification field list 必须本地化当前已知 supported values：
  - `scenario_or_participants` -> `出行人/场景`
  - `time_window` -> `时间安排`
  - `distance_flexibility` -> `距离取舍`
  - `preference_tradeoff` -> `偏好取舍`
- 如果后端未来返回未知 `missing_fields` token，前端可以回退显示原 token，但不能静默隐藏该项。

- clarification reply 输入必须与主请求输入区分离。
- 主请求 textarea 继续保留在 side rail。
- clarification reply 不得自动覆盖主请求 textarea 的当前内容。
- clarification reply submit 只消费专用 clarification input state。

- clarification submit 行为必须满足：
  - 当 reply `trim()` 为空时，提交按钮禁用
  - 当已有 in-flight request 时，提交按钮禁用
  - clarification submit 固定发送 `selected_plan_index = 0`
  - submit 成功后必须用返回的 `DemoRunSummary` 全量替换当前 loaded run
  - submit 成功且返回 `awaiting_clarification` 时，页面必须留在 clarification panel，并展示新的 prompt / missing_fields
  - submit 成功且返回有 plans 的 run 时，页面必须切回既有 plan review 流程
  - submit 成功后 clarification reply draft 必须清空
  - submit 失败时必须保留用户当前 draft，不得清空

- run inspector 必须继续对 clarification run 可用，并正确显示：
  - `run.status`
  - `run.run_id`
  - `run.read_profile`
  - `run.action_count`
  - `run.execution_status`
  - `run.feedback_status`
  - `run.plan_version.version_label`
- clarification-pending run 仍必须显示 `action_count = 0` 和当前 `v1`。

- clarification path 必须保持 customer-safe boundary：
  - 不暴露 `session_id`
  - 不暴露 conversation turn payloads
  - 不暴露 internal observability fields
  - 不暴露 trace IDs / agent roles / node history
- internal observability surface `http://127.0.0.1:5174/` 不得改动。

- clarification path 的前端错误文案必须 customer-facing。
- `frontend/src/api/demo.ts` 的本地化错误映射必须至少覆盖 clarification UI 可能直接触发的这些 detail：
  - `Source run status does not allow clarification.` -> `当前运行已不能继续补充信息，请刷新状态后重试。`
  - `Source run is missing session persistence for clarification.` -> `当前运行缺少补充信息会话，请重新开始规划。`
  - `Source run session is unavailable for clarification.` -> `当前运行缺少补充信息会话，请重新开始规划。`
  - `Source run user is unavailable for clarification.` -> `当前运行缺少关联用户，请重新开始规划。`
- 其余未知错误继续走现有 generic fallback。

- README 与 `docs/WEB_DEMO_README.md` 必须更新为 customer demo 真实现状：
  - 说明 5173 customer page 现在可以直接处理 `awaiting_clarification`
  - Clarification path 的主演示步骤改为前端表单，而不是只依赖 `curl`
  - `curl /clarify` 示例可保留为 API-level 验证方式
  - 继续说明 clarification continuation 复用同一内部会话且首次产出真实方案前仍显示 `v1`

- 必须新增或更新这些测试：
  - `frontend/src/api/demo.test.ts`
  - `frontend/src/App.test.tsx`
  - `frontend/e2e/demo.spec.ts`
- 必须继续跑现有 backend demo API 回归，确认 clarification contract 没被错误假设。

- 不得修改：
  - backend API schema
  - database schema
  - workflow routing
  - internal observability schema
  - replan frontend
  - conversation history frontend
  - dependencies

## 4. Non-goals

- 不新增 replan customer UI。
- 不新增 conversation history、session browser 或任何 public history endpoint。
- 不修改 backend 的 `/clarify`、`/replan`、`/confirm`、`/decline` contract。
- 不改 `backend/app/demo/service.py`、数据库、Alembic、Redis 或 workflow 节点。
- 不改 internal observability page 的文案、结构或测试。
- 不引入 i18n framework、locale switcher 或新的 npm dependency。
- 不重做 App 的整体布局，只允许为 clarification panel 做最小样式补充。
- 不暂存或提交 `.gitignore`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/artifacts/`、`qc`、`var/`、`frontend/dist/` 等无关本地文件。

## 5. Interfaces and Contracts

### Inputs

- 现有 public demo run summary：
  - `DemoRunSummary`
- clarification continuation request：
  - `POST /demo/runs/{run_id}/clarify`
- clarification response body：
  - `clarification.prompt`
  - `clarification.missing_fields`
- customer page 当前已有 API actions：
  - `startRun`
  - `getRun`
  - `confirmRun`
  - `declineRun`

### Outputs

- customer page 在 clarification-pending run 上展示可交互的 clarification panel。
- customer page 可以直接发起 clarification continuation，并接收新的 `DemoRunSummary`。
- clarification 成功后的页面继续沿用既有 plan review / confirmation / execution UI。
- customer-safe public payload shape 保持不变，前端仅补消费。

### Schemas

Clarification-pending public response excerpt:

```json
{
  "run_id": "00000000-0000-0000-0000-000000000010",
  "status": "awaiting_clarification",
  "read_profile": "mock_world",
  "selected_plan_id": null,
  "plan_version": {
    "version_number": 1,
    "version_label": "v1",
    "source_run_id": null,
    "source_selected_plan_id": null
  },
  "plans": [],
  "action_count": 0,
  "execution_status": null,
  "feedback_status": null,
  "error": null,
  "clarification": {
    "prompt": "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。",
    "missing_fields": [
      "scenario_or_participants",
      "time_window"
    ]
  }
}
```

Clarification submit request:

```json
{
  "user_input": "今天下午一个人出门玩几个小时，别太远。",
  "selected_plan_index": 0
}
```

Clarification panel display contract:

```json
{
  "panel_title": "需要补充信息",
  "field_list_label": "待补充项",
  "reply_label": "补充说明",
  "submit_label": "提交补充信息",
  "submitting_label": "提交中..."
}
```

## 6. Observability

本任务不新增任何新的 observability contract、trace metadata、benchmark artifact 或数据库持久化字段。

需要保持不变的事实：

- clarification run 继续通过既有 `run_id`、`status`、`plan_version` 体现状态
- customer page 不新增任何 internal observability surface
- public payload 仍保持 redacted
- internal review 仍使用既有 `GET /internal/runs/{run_id}/observability`

如果需要确认 clarification path 行为，应依赖现有 public API contract、frontend tests 与 Playwright，而不是添加新的观测接口。

## 7. Failure Handling

- 如果 clarification reply 为空，前端必须在客户端禁用提交按钮，而不是发送空请求。
- 如果当前 loaded run 是 `awaiting_clarification` 但 `clarification` payload 缺失或不合法，前端必须显示 generic error banner，并保留 `刷新状态` 能力；不得伪造 prompt 或错误渲染方案页。
- 如果 `/clarify` 返回 `404` 或 `409`，前端必须显示本地化错误文案，并保留当前 clarification draft。
- 如果 `/clarify` 返回另一个 `awaiting_clarification` run，这属于有效成功路径，不是错误。
- 如果用户在 clarification state 点击 `刷新状态`，并且后端返回其他合法 run 状态，页面必须切换到新的正确视图。
- clarification path 不得破坏 AMap read-only 预览限制；AMap confirm block 继续只在 `awaiting_confirmation` 阶段生效。
- clarification path 不得破坏现有 happy-path、decline path、refresh path、customer-safe redaction path。

## 8. Acceptance Criteria

- [ ] `docs/specs/059-customer-demo-clarification-flow-v0.md` 存在并匹配本任务。
- [ ] `docs/plans/059-customer-demo-clarification-flow-v0-plan.md` 存在并匹配本任务。
- [ ] 当前编号链保持 `001` 到 `058` 连续匹配，本任务使用新的 `059` 编号。
- [ ] `frontend/src/types/demo.ts` 已支持 `DemoClarificationSummary`、`DemoClarifyRunRequest` 和 `DemoRunSummary.clarification`。
- [ ] `frontend/src/api/demo.ts` 已支持 `clarifyRun(...)`，并调用 `POST /demo/runs/{run_id}/clarify`。
- [ ] customer page 在 `awaiting_clarification` run 上显示 clarification panel，而不是 empty workspace。
- [ ] clarification panel 会显示后端 prompt、可见 missing fields、reply input 和可点击 submit button。
- [ ] `scenario_or_participants`、`time_window`、`distance_flexibility`、`preference_tradeoff` 在 customer page 上有中文显示。
- [ ] clarification submit 空输入时按钮禁用。
- [ ] clarification submit 成功后，页面用返回的新 `run_id` 更新当前 loaded run。
- [ ] clarification submit 若继续返回 `awaiting_clarification`，页面仍可继续补充，不报错。
- [ ] clarification submit 若返回方案，页面回到既有 plan review / confirmation flow。
- [ ] clarification 首次成功产出真实方案时，customer page 仍显示 `plan_version.version_label = v1`。
- [ ] clarification-pending page 不暴露 `session_id`、conversation history、trace fields 或 internal labels。
- [ ] AMap 只读预览、confirm/decline、refresh、public redaction 现有行为不回归。
- [ ] README 与 `docs/WEB_DEMO_README.md` 已改成“customer page 可直接完成 clarification”的演示说明。
- [ ] `frontend/src/api/demo.test.ts`、`frontend/src/App.test.tsx`、`frontend/e2e/demo.spec.ts` 已覆盖 clarification path。
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
feat: add customer demo clarification flow
```

## 11. Notes for the Implementer

这张卡故意不碰 replan UI。原因不是 replan 不重要，而是 clarification 是当前 5173 主演示面上的真实断点，而 `/replan` 还没有形成同等级的“文档已公开但 UI 不可走通”的阻塞。

实现时保持几个边界：

- prompt 文本直接信任并显示后端返回值，这样 pre-planning clarification 和 recovery clarification 都能共用同一前端面板
- clarification UI 是 customer-safe conversation continuation，不是 conversation history browser
- 除了 clarification panel 需要的最小样式外，不做新的布局系统或页面重构
- 如果当前执行基线不包含 task `058` 的中文 customer surface，先补齐或换到包含等价内容的基线再做本任务
