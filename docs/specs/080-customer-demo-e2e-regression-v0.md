# Spec: 080 Customer Demo E2E Regression v0

## 1. Goal

补齐 customer Web demo 在最近一轮大 UI 改动后的真实浏览器回归保护。Task `077` 到 `079` 已把 customer surface 改成 chat-first、引入了 public progress contract 与 progress stepper，但当前 Playwright 套件对最关键的用户路径仍然存在 live 与 mocked 混用：happy path 与 clarification 主要走真实本地栈，replan、redaction、AMap 等则仍有大量 `page.route(...)` 兜底。

完成本任务后，customer browser regression 必须能稳定保护这几个当前最容易被 UI 改动打断的能力：chat start happy path、clarification path、live replan path、confirm execution path、progress steps 可见且默认折叠、不暴露敏感/internal 字段、mobile viewport 不横向崩坏。这个任务是收敛型测试任务，不引入新产品能力。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 将 Minimal Web UI 定义为 MVP 的主要演示路径，并要求系统在 customer surface 上保持：

- Human-in-the-loop confirmation boundary
- Customer-safe public surface boundary
- Minimal Web UI as the primary demo surface
- Multi-turn planning flow before confirmation

`docs/NEXT_PHASE_ROADMAP.md` 的默认优先级仍然是 `M1. 评测与观测基础设施`。但当前仓库状态表明，先做一个收敛型回归任务更合理：

- `docs/specs` 与 `docs/plans` 已连续且 slug 匹配到 `079`
- 最新 task ID 是 `079`
- 最新 commit `e78138d feat: add customer progress stepper and search counts` 与 `079` 对应
- `git status` 当前为空，说明没有未提交的 080 草稿或脏工作树需要优先续做
- 当前分支 `codex/customer-progress-stepper-and-search-counts-v0` 对应 `079`，没有显示出一个尚未收口的后续 task

最近已完成的 customer-facing 变化集中在：

- Task `077`: chat-first customer UI
- Task `078`: public progress contract
- Task `079`: customer progress stepper and search counts

因此，这个任务属于一个“优先于新 M1 开工的收敛补齐”：

- 主要保护 `M2. 前端分离` 的 customer-safe public surface
- 同时验证 `M4. 多轮对话与方案版本` 的 clarification / replan / version flow
- 并消费 `078` / `079` 已交付的 progress contract，而不是再开新的 backend 基建面

## 3. Requirements

- 使用新的 task ID `080`，不复用或返工现有 task 编号。
- `frontend/e2e/demo.spec.ts` 必须继续作为 customer Web demo 的主 Playwright 回归入口，不新增新的 Playwright project 或平行 suite 文件。
- core customer regressions 必须跑真实本地栈，不允许通过 `page.route(...)` mock 成功响应来伪造这些主路径：
  - start happy path
  - clarification continuation
  - live replan
  - confirm execution
  - progress stepper visible/collapsed behavior
  - customer-surface redaction
  - mobile viewport overflow smoke
- 允许保留 targeted mocked desktop checks，但只能用于 live 栈里不易稳定强制触发的 contract 场景：
  - selected second-plan replan index 必须仍可验证 `selected_plan_index = 1`
  - AMap read-only preview 必须仍可验证 confirm blocked 与 read-only notice
- 不允许把上面两个 targeted mock 扩大成整条 customer 主路径都依赖 mock。

- live desktop happy-path regression 必须覆盖这些断言：
  - 从 `Mock World` 默认 customer path 启动
  - 页面进入可确认状态前，先显示用户消息与系统 progress
  - 成功 summary 返回后，显示 persistent progress stepper
  - `progress stepper` 默认只展开当前步骤，completed steps 需要点击 disclosure 才显示
  - `confirm-button` 可见
  - `run_id` 默认不可见
  - 推荐方案卡片仍是 summary-first，execution timeline 在确认后默认折叠
  - 点击确认后出现后续 assistant result card，并能展开 execution timeline
- live desktop clarification regression 必须覆盖这些断言：
  - 从一个模糊 prompt 启动
  - 页面进入 `awaiting_clarification`
  - clarification card 在 customer conversation 流中可见
  - 用户可在页面内提交 clarification reply
  - continuation 返回新的 `run_id`
  - 第一条真正产出计划的 continuation 仍显示 `plan_version.version_label = v1`
  - progress stepper 仍在 clarification / plan card 之前可见
- live desktop replan regression 必须覆盖这些断言：
  - 从一个真实可确认 run 出发
  - 页面内的 inline replan panel 可直接提交 follow-up
  - 返回新的 `run_id`
  - visible version 从 `v1` 变成 `v2`
  - progress stepper 仍存在，且出现在新 plan card 之前
  - confirm boundary 仍然存在，没有因为 replan 回归到执行前已写动作
- live desktop redaction regression 必须覆盖这些断言：
  - customer 默认可见 surface 不显示：
    - `run_id`
    - `action_count`
    - raw `execution_status`
    - raw `feedback_status`
    - `trace_id`
    - `session_id`
    - `node_history`
    - `agent_roles`
    - `action_id`
    - `tool_event_id`
    - `event_id`
    - `idempotency_key`
    - obvious secret-like keys such as `api_key`, `token`, `secret`, `authorization`
  - 打开 `运行信息` disclosure 后，只允许出现 customer-safe 字段；internal-only 字段仍不得出现在页面文本里
- mobile regression 必须继续使用真实 customer path，并断言：
  - 页面最终至少进入 clarification 或 confirmation 两种 customer-safe 状态之一
  - 对应交互控件可见
  - progress stepper 或 clarification card 可见
  - `document.documentElement.scrollWidth <= clientWidth`
- 所有新断言必须优先使用现有 public-safe test ids 与稳定的 customer-facing heading/label：
  - `progress-stepper-card`
  - `progress-completed-toggle`
  - `progress-completed-list`
  - `clarification-card`
  - `clarification-reply-input`
  - `clarification-submit-button`
  - `replan-panel`
  - `replan-reply-input`
  - `replan-submit-button`
  - `confirm-button`
  - `assistant-result-card`
  - `execution-timeline-toggle`
  - `run-info-toggle`
  - `run-id`
  - `plan-version`
- 本任务不新增新的 public API 字段、backend test hook、fixture route、Playwright browser project、NPM dependency 或 database schema。
- `docs/WEB_DEMO_README.md` 必须更新，明确写出：
  - 哪些 customer regressions 现在是 live desktop/mobile checks
  - 哪些场景仍保留 targeted mocked checks
  - 本地 focused 命令与提交前命令
  - Docker / Postgres / Redis / Alembic 仍是前置条件

## 4. Non-goals

- 不修改 backend public demo API schema。
- 不修改 workflow routing、Tool Gateway、benchmark suite、replay、LangSmith、数据库 schema 或 Redis contract。
- 不实现 async start、polling、SSE、WebSocket 或后台 worker。
- 不重写 internal observability surface，也不扩展 `frontend/e2e/internal-observability.spec.ts` 的 scope。
- 不新增 Playwright project、device matrix 或新的测试基础设施。
- 不为测试方便而放宽 customer-safe public boundary。
- 不把 selected-plan-index 与 AMap read-only 这类 deterministic contract checks 强行改成脆弱的 live 场景。
- 不修改顶层 `README.md`、`docs/RICHER_WEB_UI_V1_CHECKLIST.md` 或无关文档。
- 不提交 `.env`、API keys、tokens、secrets、Playwright artifacts、`frontend/dist/`、`var/` 或其他无关本地文件。

## 5. Interfaces and Contracts

### Inputs

- Customer surface: `http://127.0.0.1:5173/`
- Existing Playwright projects:
  - `desktop-chromium`
  - `mobile-chromium`
- Existing public customer flow routes used indirectly by the page:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/clarify`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- Existing public-safe test ids and disclosures already present on the customer page

### Outputs

- A strengthened `frontend/e2e/demo.spec.ts` suite that clearly separates:
  - live customer regression paths
  - targeted mocked contract checks
- An updated `docs/WEB_DEMO_README.md` that documents the regression matrix and verification commands

### Schemas

Regression scenario matrix for this task:

```json
{
  "scenarios": [
    {
      "name": "happy_path_confirm_execution",
      "project": "desktop-chromium",
      "mode": "live",
      "must_assert": [
        "progress_stepper_visible",
        "completed_steps_collapsed_by_default",
        "confirm_boundary_preserved",
        "result_card_visible_after_confirm",
        "execution_timeline_collapsed_by_default"
      ]
    },
    {
      "name": "clarification_path",
      "project": "desktop-chromium",
      "mode": "live",
      "must_assert": [
        "clarification_card_visible",
        "inline_reply_submission",
        "new_run_id",
        "version_v1_until_first_real_plan",
        "progress_stepper_before_follow_up_card"
      ]
    },
    {
      "name": "replan_path",
      "project": "desktop-chromium",
      "mode": "live",
      "must_assert": [
        "inline_replan_panel",
        "new_run_id",
        "version_v2",
        "progress_stepper_persists"
      ]
    },
    {
      "name": "customer_redaction_boundary",
      "project": "desktop-chromium",
      "mode": "live",
      "must_assert": [
        "no_trace_id",
        "no_session_id",
        "no_node_history",
        "no_agent_roles",
        "no_secret_like_keys"
      ]
    },
    {
      "name": "mobile_overflow_smoke",
      "project": "mobile-chromium",
      "mode": "live",
      "must_assert": [
        "customer_controls_visible",
        "no_document_horizontal_overflow"
      ]
    },
    {
      "name": "selected_plan_index_contract",
      "project": "desktop-chromium",
      "mode": "targeted_mock",
      "must_assert": [
        "selected_plan_index_equals_1"
      ]
    },
    {
      "name": "amap_read_only_contract",
      "project": "desktop-chromium",
      "mode": "targeted_mock",
      "must_assert": [
        "read_only_notice_visible",
        "confirm_blocked"
      ]
    }
  ]
}
```

## 6. Observability

本任务不新增任何 backend observability、trace metadata、benchmark artifact 或数据库持久化字段。

它只依赖现有的 customer-safe DOM、现有 public API 返回以及 Playwright failure artifacts。需要保持不变的边界：

- customer suite 不依赖 internal observability route
- customer suite 不读取 trace payload、session payload 或 raw node history
- Playwright artifacts 继续落在本地生成目录，不纳入 git
- `运行信息` disclosure 继续只暴露 customer-safe 字段，不成为 internal 调试面板

## 7. Failure Handling

- 如果 live happy-path start 因业务澄清进入一次 `awaiting_clarification`，测试 helper 可以在页面内提交一次 inline clarification reply，然后必须回到可确认方案；如果仍不能回到 confirmable plan，则测试失败。
- live clarification regression 如果提交 reply 后没有产生新的 `run_id`，必须失败。
- live replan regression 如果 follow-up 提交后没有产生新的 `run_id` 或 visible version 没有前进到 `v2`，必须失败。
- mobile smoke 如果在超时内既没有 clarification card 也没有 confirmable customer state，必须失败。
- 如果某条 core regression 只能依赖 `page.route(...)` 才能通过，应视为任务失败，而不是继续扩大 mock 覆盖。
- targeted mocked tests 必须保持范围最小，并继续只验证 deterministic contract，不得扩展成替代 live customer smoke。
- 文档更新如果与当前真实 suite 行为不一致，必须以真实 suite 为准修正文档，不得反过来放宽断言去迁就旧文档。

## 8. Acceptance Criteria

- [ ] `docs/specs/080-customer-demo-e2e-regression-v0.md` exists and matches this task.
- [ ] `docs/plans/080-customer-demo-e2e-regression-v0-plan.md` exists and matches this task.
- [ ] The repository remains continuous and slug-matched through `079`, and this task uses new task ID `080`.
- [ ] Core customer regressions for happy path, clarification, live replan, confirm execution, redaction, and mobile overflow run against the real local stack rather than mocked API success responses.
- [ ] The desktop happy-path regression asserts visible progress stepper behavior, collapsed completed steps, hidden-by-default run info, confirm boundary, result card rendering, and collapsed execution timeline.
- [ ] The desktop clarification regression asserts inline clarification, new `run_id`, visible `v1`, and return to a confirmable plan.
- [ ] The desktop live replan regression asserts inline replan, new `run_id`, visible `v2`, and persistent progress stepper above the new plan card.
- [ ] The customer redaction regression asserts the page does not visibly expose `trace_id`, `session_id`, `node_history`, `agent_roles`, or secret-like keys.
- [ ] The mobile regression still passes on the real customer flow and shows no document-level horizontal overflow.
- [ ] The deterministic mocked checks for selected second-plan index and AMap read-only preview remain present and passing.
- [ ] `docs/WEB_DEMO_README.md` documents the live versus targeted mocked regression matrix and focused commands.
- [ ] No public API shape, backend workflow rule, Playwright project matrix, or internal observability behavior is changed by this task.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium
npm --prefix frontend run e2e -- --project=mobile-chromium
git diff --check
git status --short
```

## 10. Expected Commit

```text
test: expand customer demo e2e regression coverage
```

## 11. Notes for the Implementer

从当前干净的 `079` 之后继续开新 branch，不要把 `080` 直接叠加到 `codex/customer-progress-stepper-and-search-counts-v0` 的同一提交里。

实现时要坚持两个边界：

- core customer flows 用 live local stack
- selected second-plan index 与 AMap read-only 这类 deterministic contract checks 继续允许 targeted mock

如果 live replan 或 live redaction 需要改 backend contract、加测试后门、或明显放宽 public boundary，停止并回报，而不是偷偷扩大任务范围。
