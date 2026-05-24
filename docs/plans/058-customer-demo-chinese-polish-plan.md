# Plan: 058 Customer Demo Chinese Polish

## 1. Spec Reference

Spec file:

```text
docs/specs/058-customer-demo-chinese-polish.md
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

- 当前分支是 `main`。
- 最新完成的编号 task 是 `057`。
- 最新 task commit 是 `640bd73 feat: add amap preview diagnostics and benchmark guardrails`，并已在当前 `main` 上。
- `docs/specs/` 与 `docs/plans/` 从 `001` 到 `057` 连续且一一匹配，没有缺号和错配。
- `git branch --no-merged main` 为空，没有应优先续做的未合并编号 task branch。
- Task `025` 已把默认 Mock World 内容本地化为中文，但后续 task `054` 到 `057` 引入的 customer-facing 文案和显示层仍有明显英文残留。
- Task `056` 已完成 customer/internal 双前端分离；本任务只处理 `5173` customer surface。
- 默认 Mock World itinerary generation 与 feedback writer 的 customer-visible 内容已经是中文，剩余 gap 主要在 `frontend/src/App.tsx`、相关前端测试和演示文档。
- 当前工作树已有无关本地改动和未跟踪文件：
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/benchmark-all-registered-formal-report.json`
  - `qc`
- 这些现有本地文件必须保持 unstaged，不属于本任务。

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/src/App.tsx` - 将 remaining customer-visible 英文壳子文案、状态映射、fallback、section heading、button/loading labels、本地 helper 文案改为中文显示层。
- `frontend/src/App.test.tsx` - 把 mock customer run data 与 visible assertions 调整为中文 customer surface，并补足中文状态/提示断言。
- `frontend/e2e/demo.spec.ts` - 将 customer-visible heading/button assertions 改为中文，同时保留 `data-testid` 驱动的状态、run id、action count 与 redaction 检查。
- `frontend/src/styles.css` - 仅在中文文案引发布局溢出时做最小修正。
- `README.md` - 仅在引用 customer-visible UI 文案或 customer 启动步骤时与中文 UI 对齐。
- `docs/WEB_DEMO_README.md` - 对齐手动演示步骤里的 customer-visible 控件文案。

## 5. Implementation Steps

1. 先确认基线与暂存边界。
   - 运行 `git status --short --branch` 和 `git log --oneline -5`，确认当前基线是 `main` 上的 task `057`。
   - 明确本任务不处理也不暂存这些现有本地文件：`.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/benchmark-all-registered-formal-report.json`、`qc`。

2. 在 `frontend/src/App.tsx` 中统一 customer shell copy，使用下面这组目标文案。
   - 仅改 customer surface。
   - 保留 `Mock World`、`AMap`、`run_id`、`plan_id`、`v1/v2/v3` 原值。
   - 同步更新可见 heading、button text、label、helper、empty state 与相关 aria 文案。

```text
WeekendPilot Demo -> WeekendPilot 演示版
Weekend planning preview -> 周末出行规划预览
Request and run summary -> 需求输入与运行摘要
Request -> 需求
Planning prompt -> 规划需求
Read path -> 规划路径
Start planning -> 开始规划
Planning... -> 规划中...
Reset example -> 恢复示例
Ready for preview -> 准备预览
Run summary -> 运行摘要
Run status -> 运行状态
Run ID -> 运行 ID
Action count -> 动作数
Execution status -> 执行状态
Feedback status -> 反馈状态
Plan version -> 方案版本
Refresh run -> 刷新状态
Refreshing... -> 刷新中...
Returned plans -> 返回方案
Plan N -> 方案 N
Selected plan -> 已选方案
Untitled plan -> 未命名方案
No summary available. -> 暂无摘要。
Activity -> 活动
Dining -> 用餐
Timeline -> 行程时间线
Untitled stop -> 未命名站点
No timeline yet. -> 暂无时间线。
Route -> 路线
Mode -> 出行方式
Distance -> 距离
Duration -> 时长
Summary -> 摘要
Feasibility -> 可执行性
Result -> 结果
Total duration -> 总时长
Route duration -> 路线耗时
Queue wait -> 排队等待
Reasons -> 依据
Warnings -> 提醒
Action preview -> 执行动作预览
No pending actions. -> 暂无待执行动作。
Name -> 名称
Category -> 类别
Address -> 地址
Tags -> 标签
Confirmation boundary -> 确认边界
Confirm selected plan -> 确认当前方案
Confirming... -> 确认中...
Do not continue -> 暂不继续
Declining... -> 处理中...
Declined -> 已放弃
Execution and feedback -> 执行与反馈
Execution result -> 执行结果
Completed actions -> 已完成动作
Failed actions -> 失败动作
Next steps -> 后续建议
Ready state body copy -> 默认使用 Mock World，也可以切换到 AMap 只读预览查看只读规划结果。
Confirmation body copy -> 工作流会在这里暂停，等待确认或放弃当前方案。
Declined fallback body -> 已在执行前放弃当前方案。
```

3. 在 `frontend/src/App.tsx` 中把当前直接暴露给用户的英文/原始枚举改成 display-only 中文映射，不改 payload 原值。
   - 使用显示函数或映射表完成。
   - `StatusBadge` 和 metadata value 都要走同一套 display label，而不是继续直接输出 raw status。
   - 这些映射必须覆盖当前 customer surface 会触达的值。

```text
awaiting_confirmation -> 等待确认
awaiting_clarification -> 等待补充信息
completed -> 已完成
partially_completed -> 部分完成
failed -> 失败
skipped -> 已跳过
declined -> 已放弃
reviewed -> 已审核
selected -> 已选中
draft -> 草案
executed -> 已执行
pending -> 待确认
confirmed -> 已确认
written -> 已生成
succeeded -> 成功
error -> 请求失败

walking -> 步行
driving -> 驾车

activity -> 活动
dining -> 用餐
addon -> 加购

child_friendly -> 亲子友好
indoor -> 室内
museum -> 博物馆
educational -> 益智科普
outdoor -> 户外
playground -> 游乐场
citywalk -> 城市漫步
light_activity -> 轻量活动
lighter_options -> 清淡选项
quiet -> 安静
vegetable_forward -> 多蔬轻食
family_tables -> 家庭座位
balanced_menu -> 均衡菜单
quick_meal -> 快速用餐
simple -> 简单餐食
drinks -> 饮品
snacks -> 小食
family -> 家庭友好

book_ticket -> 订票
reserve_restaurant -> 订座
join_queue -> 排队取号
order_addon -> 加购
send_message -> 发送消息

confirmed_actions source copy -> 以下为确认后将执行的动作清单。
proposed_actions source copy -> 以下为确认前的动作预览，尚未执行任何写操作。
none source copy -> 当前方案没有可公开展示的动作预览。

Feasible -> 可执行
Not feasible -> 不可执行

N/A -> 暂无
None. -> 暂无
TBD -> 待定
Action -> 动作
Unknown -> 未知
No details available. -> 暂无详情。
Step N -> 第 N 步
Execution order pending -> 待确定执行顺序

minutes -> <n> 分钟
distance >= 1000 -> <n> 公里
distance < 1000 -> <n> 米
```

4. 保持这些东西不变，不要误改 contract。
   - `data-testid`
   - API field names
   - backend raw enum values
   - `Mock World`
   - `AMap`
   - `run_id`
   - `plan_id`
   - `action_ref`
   - `version_label`
   - internal observability page 与其测试

5. 更新 `frontend/src/App.test.tsx`。
   - 把 mock 方案标题、摘要、地址、route summary、feedback headline/message、decline reason 等 customer-visible mock 文案改成中文。
   - 把断言改为中文 customer surface，例如：
     - 默认 prompt 中文
     - 页面标题中文
     - `等待确认` / `已完成` / `已放弃`
     - `行程时间线`
     - `执行动作预览`
     - `确认边界`
     - `执行与反馈`
     - `已完成动作`
   - 保留 `data-testid` 驱动的断言：
     - `start-button`
     - `read-profile-select`
     - `run-status`
     - `run-id`
     - `action-count`
     - `plan-version`
     - `confirm-button`
     - `decline-button`
     - `refresh-button`
   - AMap 只读场景继续断言中文只读 notice 存在且 `confirm-button` 不存在。

6. 更新 `frontend/e2e/demo.spec.ts`。
   - 将当前英文 heading/text assertion 替换成中文 customer-visible 文案。
   - 继续使用 `data-testid` 检查状态、run id、action count。
   - 保留 redaction 检查逻辑不变。
   - Mobile smoke 继续检查 document-level horizontal overflow 为 `false`。

7. 仅当中文 copy 导致布局问题时，最小调整 `frontend/src/styles.css`。
   - 只允许修复 customer copy fit。
   - 优先关注：
     - `.button-row`
     - `.plan-tabs`
     - `.metadata-list`
     - `.action-list`
     - `.compact-list`
     - `.app-header`
   - 不做视觉重构、不改 internal page 样式。

8. 更新 `README.md` 与 `docs/WEB_DEMO_README.md`。
   - 只改 customer-visible 控件或步骤描述会与中文 UI 冲突的部分。
   - 不重写无关架构说明。
   - internal observability 页面继续保留当前英文名称与地址说明。

9. 跑验证命令并清理 diff。
   - 前端单测、build、后端 demo/itinerary/feedback regression、Playwright、`rg` sentinel 检查、`git diff --check`、`git status --short` 全部通过后再提交。

## 6. Testing Plan

- Unit tests:
  - `frontend/src/App.test.tsx` 覆盖中文默认 prompt、中文壳子文案、中文状态映射、AMap 只读提示、completed/declined 分支。
- Browser E2E:
  - `frontend/e2e/demo.spec.ts` 覆盖 start/confirm、decline、refresh、forbidden visible text、mobile no-horizontal-overflow。
- Build verification:
  - `npm --prefix frontend run build` 必须通过。
- Backend regression:
  - `tests/test_demo_api.py`
  - `tests/integration/test_demo_api_gateway.py`
  - `tests/test_itinerary_generation.py`
  - `tests/test_feedback_writer.py`
  - 这些测试应继续通过，证明 public payload 和默认中文 backend 内容未被破坏。

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
fix: polish chinese customer demo surface
```

Expected commands:

```bash
git switch -c codex/customer-demo-chinese-polish
git status --short
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/e2e/demo.spec.ts README.md docs/WEB_DEMO_README.md docs/specs/058-customer-demo-chinese-polish.md docs/plans/058-customer-demo-chinese-polish-plan.md
git add frontend/src/styles.css
git diff --cached --check
git commit -m "fix: polish chinese customer demo surface"
git push -u origin codex/customer-demo-chinese-polish
```

The implementer must unstage `frontend/src/styles.css` if no CSS changes were actually needed. The implementer must also confirm that `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/benchmark-all-registered-formal-report.json`、`qc` remain unstaged.

## 9. Out-of-scope Changes

- 不新增 i18n framework、runtime locale switching 或新的前端依赖。
- 不修改 internal observability page、internal API schema 或其测试语义。
- 不新增 clarify / replan customer UI。
- 不修改 backend API schema、database schema、workflow routing、provider、benchmark、observability summary。
- 不重写 Mock World fixture 或 AMap provider 数据。
- 不重做 customer 布局或视觉语言。
- 不改 task `056` 的双前端入口结构。
- 不暂存当前工作树中与本任务无关的预先本地文件。

## 10. Review Checklist

- [ ] 实现与 `docs/specs/058-customer-demo-chinese-polish.md` 一致。
- [ ] 变更只落在 customer surface、相关测试和必要文档。
- [ ] customer-visible 剩余英文壳子文案已被清掉，保留的英文仅限品牌/技术 token。
- [ ] raw API enums 与 IDs 未被改写，中文仅发生在 display layer。
- [ ] AMap 只读 confirm block 仍成立。
- [ ] internal observability surface 未被误改。
- [ ] 前端单测通过。
- [ ] 前端 build 通过。
- [ ] Playwright E2E 通过。
- [ ] backend regression tests 通过。
- [ ] `git diff --check` 通过。
- [ ] Git status 在提交后没有新增无关脏文件。
- [ ] Commit message 与计划一致。
- [ ] Push 成功。
- [ ] 没有 `.env`、API key、token、secret 或无关本地文件被提交。

## 11. Handoff Notes

完成后需要回报：

- 实际修改的文件列表
- 哪些 customer-visible 英文被替换成了哪些中文
- 哪些英文被有意保留为品牌/技术 token，例如 `Mock World`、`AMap`、`run_id`、`v1`
- 运行过的验证命令与结果
- commit hash
- push 结果
- `frontend/src/styles.css` 是否真的需要修改
- 预先存在的本地文件是否保持 unstaged
- 是否发现 clarify / replan customer UI 仍缺失，并作为后续 follow-up 记录
