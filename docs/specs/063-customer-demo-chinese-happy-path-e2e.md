# Spec: 063 Customer Demo Chinese Happy Path E2E

## 1. Goal

在当前仓库里补上一条真正对准“中文现场 customer demo”主路径的浏览器级回归验证：desktop Playwright 套件需要有一个独立 smoke，用中文 prompt 启动 `http://127.0.0.1:5173/` 的 customer surface，并在同一页面内走完“直接等待确认”或“先澄清再等待确认”的路径，最终停在可确认方案状态。

当前 customer demo 相关任务已经连续完成了 task `058` 到 `062`：中文 customer surface、clarification panel、replan panel、selected plan replan index 都已落地；但 live desktop happy-path E2E 仍主要从英文 `stableHappyPathPrompt` 启动。现有中文 browser coverage 只验证了 vague clarification request，不足以证明“中文 reviewer demo 主路径”本身稳定可用。完成本任务后，英文稳定用例继续保留，同时新增一条明确针对中文 prompt 的 desktop smoke，防止英文路径通过而中文现场 demo 已回归。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 明确把 Minimal Web UI 定义为 MVP 的主要演示路径，并要求系统通过“理解需求 -> 生成方案 -> 等待确认”的闭环工作，而不是只给出静态推荐。`docs/NEXT_PHASE_ROADMAP.md` 的默认优先级仍然是 `M1. 评测与观测基础设施`，但它也要求在扩展能力前先做收敛与可验证性。

当前仓库里与本任务直接相关的事实是：

- task `058` 已将 customer-facing 文案和默认 reviewer prompt 收口为中文；
- task `059` 已让 customer page 可以在浏览器内完成 clarification continuation；
- task `060` 已让 customer page 可以在浏览器内完成 replan；
- task `062` 已修复 replan 时 `selected_plan_index` 与当前 tab 脱节的问题；
- `frontend/e2e/demo.spec.ts` 现有 desktop/mobile Playwright 套件覆盖了 happy path、clarification、replan、AMap read-only、redaction 等能力；
- 但 desktop happy-path helper 仍默认使用英文 `stableHappyPathPrompt`，所以 browser suite 并没有直接把“中文现场 demo prompt”作为一个独立回归面锁住。

因此，这个任务虽然不是新的 M1 基础设施扩展，但它是一个比继续开更大任务更小、更紧迫的 convergence slice。它主要归属 `M4. 多轮对话与方案版本`，因为新 smoke 需要接受 `awaiting_confirmation` 或 `awaiting_clarification -> clarification reply -> awaiting_confirmation` 这两条 customer-safe continuation 路径；同时它也为 `M2` 已完成的中文 customer surface 提供真实回归保护。

## 3. Requirements

- 在 `frontend/e2e/demo.spec.ts` 中新增一个独立的 `desktop-chromium` smoke，用中文 prompt 驱动真实本地 customer demo。
- 新 smoke 必须跑真实本地栈，不得通过 `page.route(...)` mock `POST /demo/runs` 或 `POST /demo/runs/{run_id}/clarify` 来伪造成功路径。
- 现有稳定英文 happy-path smoke 必须保留，不得替换或删除当前英文 `stableHappyPathPrompt` 路径。
- 新 smoke 必须使用一条明确的中文 reviewer-facing prompt；不得复用英文 prompt 再只断言中文 UI 文案。
- 新 smoke 必须准备一条中文 clarification reply，并且只在页面真的进入 `awaiting_clarification` 时提交该回复。
- 启动后允许的中间状态只有两种：
  - `awaiting_confirmation`
  - `awaiting_clarification`
- 如果启动后进入 `awaiting_clarification`，测试必须：
  - 等待 `clarification-panel` 出现；
  - 在 `clarification-reply-input` 输入中文补充信息；
  - 点击 `clarification-submit-button`；
  - 继续等待页面回到 `awaiting_confirmation`。
- 如果启动后直接进入 `awaiting_confirmation`，测试不得强行走 clarification 路径。
- 新 smoke 最终必须在浏览器中断言这些稳定结果：
  - `run-status` 为 `等待确认`
  - `plan-version` 为 `v1`
  - `action-count` 为 `0`
  - `confirm-button` 可见
- 新 smoke 必须继续走 `Mock World` 默认 customer demo 路径；不得把通过条件建立在 `AMap` 只读路径上。
- 新 smoke 的断言必须优先使用现有 public test ids 和状态标签，不得依赖具体 itinerary 标题、具体 POI 名称或脆弱的自然语言摘要。
- 如果需要抽取或参数化 helper，修改范围必须尽量限制在 `frontend/e2e/demo.spec.ts` 内；本任务不修改 `frontend/src/App.tsx` 的业务行为。
- `docs/WEB_DEMO_README.md` 必须更新，明确说明：
  - desktop browser suite 继续保留英文稳定 smoke；
  - 同时新增一条专门面向中文 reviewer prompt 的 desktop smoke；
  - 中文 smoke 会接受“直接等待确认”或“先澄清再等待确认”两种路径；
  - 文档给出一个 focused grep 命令用于本地迭代，以及一个完整 desktop 项目命令用于提交前验证。
- 本任务不得修改：
  - backend API schema
  - workflow routing
  - database schema
  - benchmark cases / suites
  - Playwright project matrix
  - internal observability surface
  - customer page 的业务 contract

## 4. Non-goals

- 不替换或重写现有英文稳定 happy-path smoke。
- 不新增新的 Playwright project、browser channel、移动端 smoke 或 internal surface smoke。
- 不改 `frontend/src/App.tsx` 的默认 prompt、clarification contract、replan contract 或确认边界逻辑。
- 不改 `backend/app/demo/service.py`、`backend/app/workflow/*`、数据库、Alembic、Redis、benchmark harness。
- 不为本任务引入新的 npm dependency、test helper package 或 i18n framework。
- 不在本任务里补做 README 大范围改写；如需文档更新，仅限 `docs/WEB_DEMO_README.md` 与这条 smoke 的运行说明。
- 不处理 `058` 到 `062` 分支合并到 `main` 的流程。
- 不暂存或提交当前工作区里与本任务无关的本地脏文件，例如 `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`。

## 5. Interfaces and Contracts

### Inputs

- Customer surface: `http://127.0.0.1:5173/`
- Public demo API routes used indirectly by the page:
  - `POST /demo/runs`
  - `POST /demo/runs/{run_id}/clarify`
- Existing customer page test ids:
  - `start-button`
  - `run-status`
  - `plan-version`
  - `action-count`
  - `clarification-panel`
  - `clarification-reply-input`
  - `clarification-submit-button`
  - `confirm-button`
- Playwright project:
  - `desktop-chromium`

### Outputs

- A passing desktop Playwright smoke that uses a Chinese customer-demo prompt and reaches a confirmable plan in-browser.
- Existing English stable smoke remains in the suite and continues to pass unchanged.
- Updated `docs/WEB_DEMO_README.md` that reflects the additive Chinese desktop smoke.

### Schemas

```json
{
  "scenario": "desktop_chinese_customer_demo_happy_path",
  "start_prompt_language": "zh-CN",
  "clarification_reply_language": "zh-CN",
  "allowed_intermediate_statuses": [
    "awaiting_confirmation",
    "awaiting_clarification"
  ],
  "required_final_status_before_confirm": "awaiting_confirmation",
  "required_final_public_fields": {
    "plan_version": "v1",
    "action_count": 0,
    "confirm_button_visible": true
  }
}
```

## 6. Observability

本任务不新增任何 backend telemetry、database 字段、LangSmith metadata、benchmark artifact 或 internal observability contract。

需要保持不变的事实：

- browser smoke 仍通过现有 customer-safe public surface 观察状态；
- 测试不得依赖 internal `trace_id`、`node_history`、`agent_roles`、`session_id` 或 internal observability page；
- Playwright 失败产物仍按现有配置落在本地生成目录中，不应被纳入 git；
- 这个任务的价值是补足回归覆盖，而不是新增观测面。

## 7. Failure Handling

- 如果中文 prompt 启动后直接进入 `awaiting_confirmation`，测试应立即进入最终断言，不再尝试 clarification。
- 如果中文 prompt 启动后进入 `awaiting_clarification`，测试必须在浏览器内提交中文 clarification reply，再等待 `awaiting_confirmation`。
- 如果启动后进入除上述两种之外的状态，测试必须失败。
- 如果 clarification submit 后仍未回到 `awaiting_confirmation`，测试必须失败。
- 如果最终 `plan-version` 不是 `v1`、`action-count` 不是 `0`、或 `confirm-button` 不可见，测试必须失败。
- 断言必须容忍实际方案标题、摘要、POI 名称的自然变化，但不得容忍 public status、plan version、confirmation boundary 的回归。
- 如果修改 helper，会影响现有英文 smoke 时，必须优先保持英文路径行为不变；本任务不能为了中文 smoke 稳定而牺牲现有英文稳定回归。

## 8. Acceptance Criteria

- [ ] `docs/specs` 与 `docs/plans` 当前保持 `001` 到 `062` 连续匹配，本任务使用新的 `063` 编号。
- [ ] 最新 commit `b5f0566 fix: use selected plan index for demo replans` 仍对应 task `062`，本任务是其后的新 task，而不是旧 task 返工。
- [ ] `frontend/e2e/demo.spec.ts` 新增一条独立的 desktop Chinese smoke。
- [ ] 现有英文稳定 happy-path smoke 继续存在且未被替换。
- [ ] 新 smoke 使用中文 prompt 启动 customer demo，而不是英文 prompt。
- [ ] 新 smoke 允许 `awaiting_confirmation` 或 `awaiting_clarification` 两种中间状态。
- [ ] 若进入 clarification，新 smoke 会在页面内提交中文 clarification reply，而不是依赖 `curl`。
- [ ] 新 smoke 最终在浏览器中达到 `awaiting_confirmation`。
- [ ] 新 smoke 最终断言 `plan-version = v1`、`action-count = 0`、`confirm-button` 可见。
- [ ] 新 smoke 基于真实本地 customer demo 路径运行，不 mock `start` 或 `clarify` API 成功返回。
- [ ] `docs/WEB_DEMO_README.md` 已说明英文稳定 smoke 仍保留，中文 smoke 为新增覆盖。
- [ ] `npm --prefix frontend run e2e -- --project=desktop-chromium` 通过。
- [ ] `git diff --check` 通过。
- [ ] 没有 `.env`、API key、token、secret 或无关本地脏文件被提交。
- [ ] 提交后工作树只保留本 task 之外原本就存在的本地脏文件。

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "Chinese reviewer prompt"
npm --prefix frontend run e2e -- --project=desktop-chromium
git diff --check
git status --short
```

## 10. Expected Commit

```text
test: add chinese customer demo happy-path smoke
```

## 11. Notes for the Implementer

当前仓库的任务链已经很明确：

- `docs/specs` 与 `docs/plans` 都连续到 `062`
- 最新 commit `b5f0566` 与 task `062` 的 expected commit 完全对应
- 当前 `git branch --no-merged main` 里仍有 `058` 到 `062` 的 customer-demo 任务链分支，但这些提交都已经包含在当前 `HEAD` 上
- `main` 不包含这条 customer-demo 连续任务链，所以 `063` 不能从 `main` 重开

执行时应基于当前 `HEAD` 继续，或等这条分支链合并后再做。当前工作树还有无关本地改动和未跟踪文件，必须显式按路径暂存，避免把无关文件带入本任务提交。
