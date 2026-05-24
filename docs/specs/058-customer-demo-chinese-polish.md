# Spec: 058 Customer Demo Chinese Polish

## 1. Goal

WeekendPilot 的默认客户演示路径已经具备中文 Mock World 内容、分离后的 customer/internal 前端入口，以及 AMap 只读预览、plan version、action manifest 等能力；但当前 `http://127.0.0.1:5173/` 客户页面仍然保留了大量英文壳子文案、原始状态值和英文 fallback。这使仓库里“中文评审 demo”这一叙述与实际 reviewer 首屏体验不一致。

完成本任务后，客户演示面应在默认 Mock World 路径和 AMap 只读预览路径上都以中文展示 reviewer 可见信息，达到可直接演示的 v1 收口状态；同时保持现有 public API contract、customer/internal surface separation、确认边界、benchmark/observability 行为不变。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 明确把 Minimal Web UI 作为 MVP 的主要演示路径，并要求在真实评审场景中展示“规划 -> 确认 -> 执行”的闭环。`docs/NEXT_PHASE_ROADMAP.md` 中与本任务最相关的里程碑是 `M2. 前端分离`：客户可见页面与内部观测页面已经在 task `056` 被结构上拆开，但客户面本身还没有完成 reviewer-facing 收口。

仓库演进上，本任务建立在这些事实之上：

- Task `025` 已把默认 Mock World family-afternoon 内容本地化为中文。
- Task `056` 已把 customer surface 和 internal observability surface 分离为两个独立前端入口。
- Task `054` 到 `057` 给客户面增加了 read-profile selector、plan version、action manifest、AMap 只读预览和相关提示，但这些新增 customer 文案和显示映射仍有明显英文残留。
- 当前 `M1` 评测与观测基础设施已经具备基础收敛能力，因此继续扩 roadmap 新能力，不如先把公开客户演示面收口到与文档承诺一致。

本任务是一个面向 `M2` 的 convergence slice：不新增能力，只把现有 customer surface 调整到一致、可演示、中文为主的完成态。

## 3. Requirements

- 将 `frontend/src/App.tsx` 中仍然面向客户可见的英文壳子文案改为中文，包括页头、输入区、元数据区、empty state、plan detail、confirmation panel、result panel、按钮与 loading 文案、fallback 文案、helper 文案和 aria/heading 文案。
- 为 customer surface 增加显示层中文映射，覆盖当前直接暴露给用户的技术枚举或英文标签，包括：
  - run / plan / confirmation / execution / feedback 状态显示值
  - route mode
  - candidate category
  - candidate tags
  - action type
  - action manifest source 说明
  - feasibility 布尔结果
  - `N/A` / `None` / `Untitled` / `TBD` 等 fallback
  - 分钟、距离、步骤序号等展示文案
- 保持这些底层 contract 不变：
  - public API field names
  - backend status enum values
  - `run_id`
  - `plan_id`
  - `action_ref`
  - `Mock World`
  - `AMap`
  - `v1` / `v2` / `v3`
  - 现有 `data-testid`
- 保持默认中文 prompt 不变，并保持 AMap 只读预览相关 helper / notice / error 展示为中文。
- 保持 customer-safe boundary 不变：
  - 不新增 internal fields 暴露
  - AMap 只读路径仍不显示 confirm action
  - confirmation 前 `action_count = 0`
- 不修改 internal observability surface `http://127.0.0.1:5174/` 的文案或交互；该页面继续保留当前 developer/reviewer 导向的英文。
- 不新增 clarify / replan 的客户交互 UI；本任务只 polish 现有 happy-path customer 演示面，不扩展新的前台交互入口。
- 更新前端单测和 Playwright E2E，使其断言中文 customer surface，同时保留对 customer-safe redaction、action count 和 AMap confirm block 的检查。
- 仅在中文文案引发按钮、tab、metadata 或 action list 溢出时，才对 `frontend/src/styles.css` 做最小限度的适配修正；不得借机重做布局。
- 更新 `README.md` 与 `docs/WEB_DEMO_README.md` 中引用客户 UI 可见控件/文案的部分，使文档与实际中文 customer surface 一致。

## 4. Non-goals

- 不实现 unrelated modules。
- 不改变本 spec 未明确列出的 public interfaces。
- 不提交 `.env`、API key、token、secret。
- 不给 internal observability page 做中文化。
- 不新增 i18n framework、运行时语言切换、locale 选择器或新的依赖。
- 不新增 clarify / replan 输入框、会话历史 UI 或其他多轮会话前端能力。
- 不改 backend API schema、数据库 schema、workflow routing、benchmark、provider、observability 数据结构。
- 不重写 Mock World fixture、itinerary generation 或 feedback writer 的当前中文内容，除非发现本 task 直接相关的 customer-visible 回归。
- 不调整 customer/internal 双前端结构，不回退 task `056` 的分离结果。
- 不暂存或提交当前工作树里与本任务无关的预先本地文件：`.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/benchmark-all-registered-formal-report.json`、`qc`。

## 5. Interfaces and Contracts

### Inputs

- 现有 customer surface 入口：
  - `frontend/index.html`
  - `frontend/src/main.tsx`
  - `frontend/src/App.tsx`
- 现有 public demo API：
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
  - 以及已存在但本任务不新增 UI 的 clarify / replan routes
- 现有 public payload：
  - `DemoRunSummary`
  - `DemoPlanPreview`
  - `DemoActionManifestSummary`

### Outputs

- Public customer API JSON shape 不变。
- `frontend/src/App.tsx` 对相同 payload 做中文 display-only 渲染。
- `Mock World`、`AMap`、`run_id`、`plan_id`、`version_label` 等技术/品牌值保持原值。
- `data-testid` 不变，确保现有测试与后续自动化兼容。

### Schemas

```json
{
  "customer_display_labels": {
    "status.awaiting_confirmation": "等待确认",
    "status.awaiting_clarification": "等待补充信息",
    "status.completed": "已完成",
    "status.partially_completed": "部分完成",
    "status.declined": "已放弃",
    "confirmation.pending": "待确认",
    "route.walking": "步行",
    "route.driving": "驾车",
    "category.activity": "活动",
    "category.dining": "用餐",
    "category.addon": "加购",
    "fallback.na": "暂无",
    "fallback.none": "暂无",
    "fallback.untitled_plan": "未命名方案",
    "fallback.untitled_stop": "未命名站点",
    "fallback.tbd": "待定",
    "action.reserve_restaurant": "订座",
    "action.book_ticket": "订票",
    "action.join_queue": "排队取号"
  }
}
```

## 6. Observability

本任务不新增任何 telemetry、trace metadata、benchmark artifact 或数据库持久化字段。

必须保持这些行为不变：

- public customer payload 继续经过现有 redaction，不暴露 internal fields 或 sensitive keys。
- internal observability API 和 internal frontend 不因本任务发生 schema 变化。
- AMap preview diagnostics、benchmark guardrails 等 task `057` 既有 observability 行为保持不变。

如果需要验证 customer surface 是否仍安全，应通过现有 frontend tests、Playwright 和 demo API regression tests 完成，而不是新增新的 observability contract。

## 7. Failure Handling

- 如果 backend payload 里存在共享的技术 enum 或 status，必须在 customer display layer 翻译，而不是修改 API contract。
- 如果某个值既用于 customer surface 又用于 internal surface，本任务只允许修改 customer surface 的显示层，不允许改共享 schema。
- 如果某些值是 reviewer 需要识别的品牌/技术 token，例如 `Mock World`、`AMap`、`run_id`、`v1`，保留原值并翻译周围标签即可。
- 如果中文文案造成按钮、tab、metadata、action list 或移动端布局溢出，优先缩短 copy 或最小化调整 CSS；不得重做组件结构或引入新的布局系统。
- 如果现有测试用可见英文文案定位 customer 控件，应改为中文断言或保留 `data-testid` 断言，不要降低覆盖率。
- 如果实现过程中发现真正的 customer-visible bug 不属于纯 polish 范畴，例如 clarify / replan 缺失前端入口，应记录为 follow-up，而不是在本 task 内扩 scope。

## 8. Acceptance Criteria

- [ ] 最新完成基线保持为 task `057`，本任务是其后的新增收口 task。
- [ ] `http://127.0.0.1:5173/` 的客户页面不再显示当前 `frontend/src/App.tsx` 中剩余的英文壳子/回退文案，例如 `Weekend planning preview`、`Request`、`Start planning`、`Refresh run`、`Confirmation boundary`、`Action preview`、`Execution and feedback`、`Completed actions`、`N/A`、`Walking`、`Feasible`。
- [ ] customer-visible 的 run / plan / confirmation / execution / feedback 状态显示，以及 route / category / tag / action / fallback 文案，均使用中文 display labels。
- [ ] 默认 Mock World prompt 保持中文，默认 Mock World 方案标题、摘要、timeline、feedback 在 customer 页面上继续正确显示。
- [ ] AMap 只读预览路径继续显示中文只读提示，继续保持 `action_count = 0`，并且不渲染 confirm action。
- [ ] 现有 `data-testid` 保持不变。
- [ ] internal observability surface 与 internal API schema 不发生变化。
- [ ] 前端单测通过。
- [ ] 前端 build 通过。
- [ ] Playwright E2E 通过，包括 mobile no-horizontal-overflow smoke。
- [ ] `README.md` 与 `docs/WEB_DEMO_README.md` 中引用 customer UI 可见控件/文案的部分，与中文 customer surface 一致。
- [ ] 没有 `.env`、API key、token 或 secret 被 git 跟踪。
- [ ] 提交后工作树只包含本任务之外原本就存在的无关本地文件；本任务本身不新增额外脏文件。

## 9. Verification Commands

```powershell
npm --prefix frontend run test -- --run
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py tests/test_itinerary_generation.py tests/test_feedback_writer.py -q
npm --prefix frontend run e2e
if (rg -n "Weekend planning preview|Start planning|Confirmation boundary|Action preview|Execution and feedback|Completed actions|Refresh run|N/A|Walking|Feasible" frontend/src/App.tsx frontend/src/App.test.tsx frontend/e2e/demo.spec.ts) { throw "customer English copy still present" }
git diff --check
git status --short
```

## 10. Expected Commit

```text
fix: polish chinese customer demo surface
```

## 11. Notes for the Implementer

当前仓库的编号 spec / plan 已连续到 `057`，最新 feat commit `640bd73` 对应 task `057`，而且 `git branch --no-merged main` 为空，因此本任务应作为新的 `058` 执行，而不是续做旧编号任务。

实现时优先使用显示层映射，而不是修改 backend contract。保持 task `056` 的 customer/internal 分离边界不变，保持 task `057` 的 observability/benchmark guardrails 不变。注意当前工作树已有无关本地改动和未跟踪文件，本任务必须避免误暂存这些路径。
