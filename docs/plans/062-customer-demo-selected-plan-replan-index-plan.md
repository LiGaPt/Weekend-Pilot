# Plan: 062 Customer Demo Selected Plan Replan Index

## 1. Spec Reference

Spec file:

```text
docs/specs/062-customer-demo-selected-plan-replan-index.md
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

- 当前分支是 `codex/formal-verification-script`，并且跟踪 `origin/codex/formal-verification-script`。
- 最新 commit 是 `057d3c0 feat: add formal verification script`，对应 task `061`。
- task `060` 的 replan 前端实现已经落地在当前分支祖先中，commit 为 `dbe50d9 feat: add customer demo replan flow`。
- `docs/specs` 与 `docs/plans` 从 `001` 到 `061` 连续且 slug 一一匹配，没有更晚的正式 task 文档需要继续。
- `origin/main` 不包含 `058-061` 这一段 customer demo / formal verification 收口链路，因此本任务不能从 `main` 开始执行。
- `frontend/src/App.tsx` 当前已经维护：
  - `selectedPlanId`
  - `choosePlan(run, selectedPlanId)`
  - `replanReply`
  - `handleReplan()`
- `frontend/src/App.tsx` 当前仍存在这个行为缺口：
  - `buildReplanRequest(reply)` 内部把 `selected_plan_index` 固定写成 `0`
  - UI 虽然允许切换第二个 plan tab，但 replan request body 不会随之变化
- `frontend/src/App.test.tsx` 当前已有两个 plans 的 `awaitingRun` fixture，并已有“切换 plan tabs 不调用 backend”的测试，可以直接复用为新增 replan-index 回归测试的基线。
- `frontend/e2e/demo.spec.ts` 当前已有 mocked replan request interception，但 mocked start run 只有一个 plan，因此还没有覆盖“选第二个 plan 后 body 为 1”的场景。
- 当前工作树已有无关本地脏文件：
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/`
  - `qc`
- 执行本计划时必须保持这些无关文件 unstaged，不得顺手清理或纳入提交。

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/src/App.tsx` - 计算当前有效 selected plan index，并在 replan request body 中使用该索引。
- `frontend/src/App.test.tsx` - 增加“切第二个 tab 后 replan 发送 index 1”的回归测试，并保持默认第一方案路径断言为 `0`。
- `frontend/e2e/demo.spec.ts` - 增加或更新 mocked browser 场景，拦截 `/replan` 请求并断言第二个 tab 发送 `selected_plan_index: 1`。

## 5. Implementation Steps

1. 从当前 `codex/formal-verification-script` HEAD 新建执行分支 `codex/customer-demo-selected-plan-replan-index`。
2. 不要从 `main` 开始。
3. 先用 `git status --short` 记录当前已存在的无关脏文件，后续提交时确保它们继续保持 unstaged。

4. 在 `frontend/src/App.tsx` 中新增一个内部 helper，建议放在 `choosePlan(...)` 附近，命名固定为 `resolveSelectedPlanIndex(run, selectedPlanId)`。
5. `resolveSelectedPlanIndex(run, selectedPlanId)` 的逻辑固定为：
   - 如果 `run` 不存在或 `run.plans.length === 0`，返回 `0`
   - 先尝试直接在 `run.plans` 中查找 `plan.plan_id === selectedPlanId`
   - 如果找到，返回该 plan 的零基数组索引
   - 如果没找到，调用既有 `choosePlan(run, selectedPlanId)`
   - 如果 `choosePlan(...)` 返回了有效 plan，再在 `run.plans` 中查找该 plan 的索引
   - 如果仍然找不到，返回 `0`
6. 该 helper 不得修改 `selectedPlanId`、`run.selected_plan_id` 或任何 plan 选择状态；它只负责把当前前端有效选中方案翻译成 request index。

7. 把 `buildReplanRequest(reply)` 改成 `buildReplanRequest(reply, selectedPlanIndex)`。
8. `buildReplanRequest(...)` 的行为固定为：
   - `user_input` 继续发送 `reply.trim()`
   - `selected_plan_index` 直接发送外部传入的 `selectedPlanIndex`
9. 不要在 `buildReplanRequest(...)` 内部重新查找 plan，也不要在那里再兜底写死 `0`。

10. 在 `handleReplan()` 中，调用 `resolveSelectedPlanIndex(run, selectedPlanId)`。
11. 把返回值保存到局部常量 `selectedPlanIndex`。
12. 用该值调用 `buildReplanRequest(replanReply, selectedPlanIndex)`。
13. 保持以下现有行为不变：
   - `handleStart()` 仍发送 `selected_plan_index: 0`
   - `handleClarify()` 仍发送 `selected_plan_index: 0`
   - `replanRun(...)` API client 不改
   - `confirmRun(...)` / `declineRun(...)` 不改
   - `showReplanPanel` / `canReplan` / `runAction(...)` 行为不改

14. 在 `frontend/src/App.test.tsx` 中保留现有默认 replan 回归测试。
15. 不修改现有“默认第一方案 replan 发送 `0`”断言，只在必要时适配新的函数签名影响。
16. 新增一条专门的测试，名称固定为类似：
   - `it("submits the selected second plan index when replanning", async () => { ... })`
17. 这条测试的步骤固定为：
   - `startRun` 返回当前已有的 `awaitingRun` 双方案 fixture
   - 如有需要，准备一个新的 `replannedRunV2FromPlan2` fixture，它的 `plan_version.source_selected_plan_id` 设为 `"plan-2"`
   - 渲染 `<App />`
   - 点击 start button
   - 点击第二个 plan tab
   - 在 replan textarea 输入 follow-up 文本
   - 点击 replan submit button
   - 断言 `replanRun` 被调用时 body 为 `{ user_input: "...", selected_plan_index: 1 }`
18. 这条测试还应额外断言在点击第二个 tab 后，页面确实显示第二方案内容，而不是沿用第一方案内容。
19. 保留现有 “switches plan tabs without calling the backend” 测试，不要把它改成 replan 测试；新增专门的 replan-index 测试即可。

20. 在 `frontend/e2e/demo.spec.ts` 中新增一条专门的 mocked 场景，不要把现有整条 v1 -> v2 -> v3 回归测试复杂化。
21. 为这条新测试准备一个双方案 mocked start run。
22. 实现方式固定为以下两者之一，优先选择改动更小的方案：
   - 新增一个专用 fixture `mockedStartRunWithTwoPlans`
   - 或新增一个小 helper 专门构造双方案 awaiting-confirmation run
23. 不要为了这张卡重构整个 E2E fixture 工具层。
24. 这条新 E2E 测试的步骤固定为：
   - route `POST /demo/runs`，返回双方案 mocked start run
   - route `POST /demo/runs/{run_id}/replan`，记录 `request.postDataJSON()`
   - 打开 customer page 并启动 run
   - 点击第二个 plan tab
   - 在 replan input 填写 follow-up 文本
   - 点击 replan submit button
   - 断言首次拦截到的 replan body 为 `{ user_input: "...", selected_plan_index: 1 }`
25. 如该测试需要一个 mocked replan response，保持 response shape 与现有 public contract 一致。
26. 如果返回的是新的 `v2` run，优先把它的 `plan_version.source_selected_plan_id` 设成第二方案 ID，使 mock 与 backend 语义保持一致。
27. 不要在这张卡里增加真实 backend 断言；E2E 仍保持 mocked request-body 验证即可。

28. 不修改 `frontend/src/api/demo.ts` 和 `frontend/src/types/demo.ts`，除非实现时发现编译器因为 `buildReplanRequest` 调整而要求最小伴随改动。
29. 预期正常实现下，这两个文件不需要改。
30. 不新增 backend tests。
31. 本任务的修复范围只在 frontend request 组包与 frontend 回归覆盖；backend contract 已由既有实现与既有测试承担。

32. 跑验证命令：
   - `npm --prefix frontend run test -- --run src/App.test.tsx`
   - `npm --prefix frontend run build`
   - `npm --prefix frontend run e2e`
   - `git diff --check`
   - `git status --short`
33. 如果 `npm --prefix frontend run e2e` 失败，先确认是否是 Playwright 环境问题；如果只是浏览器未安装，按现有仓库说明补装，不要改这张卡的代码范围。

34. 提交前只 stage 本任务文件与新落地的 spec / plan：
   - `frontend/src/App.tsx`
   - `frontend/src/App.test.tsx`
   - `frontend/e2e/demo.spec.ts`
   - `docs/specs/062-customer-demo-selected-plan-replan-index.md`
   - `docs/plans/062-customer-demo-selected-plan-replan-index-plan.md`
35. 不要 stage `.gitignore`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc` 或任何其他本地文件。

## 6. Testing Plan

- Unit tests: `frontend/src/App.test.tsx`
- Unit-test coverage must include the existing default first-plan replan path that still sends `selected_plan_index: 0`.
- Unit-test coverage must add a second-plan replan path that clicks the second tab and asserts `selected_plan_index: 1`.

- E2E tests: `frontend/e2e/demo.spec.ts`
- Add one mocked browser scenario that starts from a two-plan run, selects the second plan, submits replan, and asserts the intercepted `/replan` request body uses `1`.

- Integration tests: none
- Reason: this task does not change backend contract, persistence, or workflow behavior; it only changes frontend request composition and frontend regression coverage.

- Smoke tests:
- `npm --prefix frontend run build`
- `npm --prefix frontend run e2e`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
npm --prefix frontend run test -- --run src/App.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
fix: use selected plan index for demo replans
```

Expected commands:

```bash
git switch -c codex/customer-demo-selected-plan-replan-index
git status --short
git add frontend/src/App.tsx
git add frontend/src/App.test.tsx
git add frontend/e2e/demo.spec.ts
git add docs/specs/062-customer-demo-selected-plan-replan-index.md
git add docs/plans/062-customer-demo-selected-plan-replan-index-plan.md
git diff --cached --check
git commit -m "fix: use selected plan index for demo replans"
git push -u origin codex/customer-demo-selected-plan-replan-index
```

The implementer must confirm `.gitignore`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc` and any other pre-existing local dirty files remain unstaged.

## 9. Out-of-scope Changes

- Do not change backend API schema, request/response models, workflow routing, or database schema.
- Do not modify `backend/app/demo/service.py`, `backend/app/workflow/*`, or any benchmark / observability code.
- Do not add a new plan selector UI, source-plan persistence, history browser, or version-compare UI.
- Do not modify clarification flow behavior or its `selected_plan_index` handling.
- Do not edit README or `docs/WEB_DEMO_README.md` for this task.
- Do not rewrite task `060` or `061` history.
- Do not clean up or stage unrelated local draft files already present in the worktree.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/062-customer-demo-selected-plan-replan-index.md`.
- [ ] Replan request composition no longer hardcodes `selected_plan_index: 0`.
- [ ] The default first-plan path still sends `selected_plan_index: 0`.
- [ ] Selecting the second plan tab before replan sends `selected_plan_index: 1`.
- [ ] `frontend/src/App.test.tsx` includes the new second-plan replan regression.
- [ ] `frontend/e2e/demo.spec.ts` includes the new mocked second-plan request-body assertion.
- [ ] No backend, workflow, schema, README, or clarification-path changes slipped into the patch.
- [ ] Required verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status after commit shows no newly staged unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated draft file was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- The exact helper or logic used to derive `selected_plan_index`
- The new App test name and what it asserts
- The new mocked E2E scenario and what request body it asserted
- Verification commands run and whether each passed
- Commit hash
- Push result
- Confirmation that pre-existing dirty files stayed unstaged
- Any residual edge case, especially whether the defensive fallback-to-`0` path was exercised only as a guard and not as the normal selected-second-plan path
