每个 Task 的通用 Prompt Workflow
下面是你之后可以复用的三段模板。你只需要把 {TASK_INFO} 替换成对应 task 信息。
Prompt A：Plan 模式，制定 Spec 和 Plan 草稿
用于新开 Codex 会话的 Plan 模式。
你现在在仓库：

E:\ai项目\面试准备\hackathon

请进入规划模式，只制定 task 的 spec 和 implementation plan 草稿，不要写入文件，不要实现代码。

任务信息：

{TASK_INFO}

项目背景：
- 当前项目是 WeekendPilot。
- 当前版本目标是 V2 Integrity Edition。
- 真实地图 provider 深度集成和真实世界泛化暂时降级。
- V2 重点是 benchmark 完整性、记忆治理、系统可审计、恢复与稳定性证据。
- Mock World 继续作为正式 benchmark 基座。
- AMap 只保留 API-only read-only preview，不进入 customer UI 主链，不参与正式 benchmark。

请先阅读相关上下文：
- README.md
- docs/NEXT_PHASE_ROADMAP.md
- docs/PROJECT_BLUEPRINT.md
- docs/templates/TASK_SPEC_TEMPLATE.md
- docs/templates/TASK_PLAN_TEMPLATE.md
- backend/app/benchmark/suites.py
- backend/app/benchmark/schemas.py
- backend/app/benchmark/matrix.py
- tests/test_benchmark_suites.py

根据任务需要再读取更具体文件。

请先运行并报告：
- git status --short
- git branch --show-current

要求：
- 不要实现代码。
- 不要写文件。
- 不要 commit。
- 输出两个部分：
  1. Spec 草稿
  2. Implementation Plan 草稿
- Spec 必须包含：
  - Problem
  - Goal
  - In scope
  - Non-goals
  - Current state
  - Proposed behavior
  - Data/schema contract
  - Acceptance criteria
  - Verification commands
  - Risks / rollback
- Plan 必须包含：
  - 修改文件清单
  - 测试优先顺序
  - 实现步骤
  - 验证命令
  - 不应修改的文件
  - commit message 建议

严格限制：
- 不提交 .env、API key、token、secret、var/、.venv、node_modules、frontend/dist、Playwright artifacts。
- 不修改和本 task 无关的功能。
- 如果发现工作区不干净，先说明哪些改动可能影响本 task。
Prompt B：正常模式，保存 Spec 和 Plan
Plan 模式确认后，新开正常模式或继续正常模式，用这段。
你现在在仓库：

E:\ai项目\面试准备\hackathon

请根据刚才确认过的 spec 草稿和 implementation plan 草稿，把文档保存到仓库中。只保存 spec 和 plan，不实现代码。

任务信息：

{TASK_INFO}

请保存到：
- docs/specs/{SPEC_FILENAME}.md
- docs/plans/{PLAN_FILENAME}.md

要求：
- 遵循 docs/templates/TASK_SPEC_TEMPLATE.md 和 docs/templates/TASK_PLAN_TEMPLATE.md 的风格。
- 内容要足够具体，后续实现会话可以只读这两个文件完成任务。
- 不要实现代码。
- 不要修改业务代码。
- 不要刷新 benchmark artifact。
- 不要 commit，除非我明确要求。

完成后运行：
- git status --short
- git diff --stat

最后报告：
- 创建或修改的文档路径
- 文档摘要
- 下一步实现会话应读取的文件
如果你希望每个 task 的 spec/plan 单独提交，可以把最后一句改成：
如果只修改了 spec 和 plan，请创建 commit：
docs: add {TASK_SLUG} spec and plan
然后通过 SSH 推送当前分支到 GitHub。
Prompt C：正常模式，实现、验证、提交、SSH Push
这是每个 task 的执行会话主 prompt。
你现在在仓库：

E:\ai项目\面试准备\hackathon

请执行这个 task 的实现、验证、提交和 SSH push。

任务信息：

{TASK_INFO}

请先阅读：
- docs/specs/{SPEC_FILENAME}.md
- docs/plans/{PLAN_FILENAME}.md
- README.md
- docs/NEXT_PHASE_ROADMAP.md

再根据 plan 读取相关代码和测试文件。

开始前请运行并报告：
- git status --short
- git branch --show-current

分支要求：
- 如果当前不在本 task 分支，请创建或切换到：
  codex/{TASK_SLUG}
- 如果工作区有与本 task 无关的未提交改动，请停止并报告，不要覆盖。
- 不要 revert 用户已有改动。

执行要求：
- 严格按 spec 和 plan 实现。
- 优先补测试，再实现。
- 不扩大范围。
- 不做后续 task 的内容。
- 不提交 .env、API key、token、secret、var/、.venv、node_modules、frontend/dist、Playwright artifacts。
- 不刷新 canonical benchmark artifacts，除非 spec/plan 明确要求。

验证要求：
先运行 plan 中列出的聚焦测试。
如果通过，再运行：
- python scripts/show_submission_evidence.py
- git status --short
- git diff --stat

提交要求：
- 只 stage 本 task 相关文件。
- commit message 使用：
  {COMMIT_MESSAGE}
- commit 后通过 SSH 推送：
  git push -u origin codex/{TASK_SLUG}

完成后报告：
- commit hash
- push 结果
- 修改文件摘要
- 验证命令和结果
- 是否还有未提交文件
- 下一 task 建议