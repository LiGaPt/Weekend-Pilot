# WeekendPilot 项目评估报告

## 1. 评估结论

WeekendPilot 当前已经不是一个简单 demo，而是一个围绕“本地生活规划 -> 人工确认 -> 模拟执行 -> 审计验证”构建的较完整工程样板。项目的核心优势在于交付边界清晰、默认路径可离线复现、benchmark 与 evidence 体系较完整，并且把“确认前不执行副作用动作”作为产品安全边界贯穿到了 API、工作流、工具网关和评审材料中。

综合评估：

| 维度 | 评级 | 说明 |
| --- | --- | --- |
| 产品完整度 | 高 | 已覆盖公开用户流、内部评审流、确认/拒绝/澄清/重规划/执行结果 |
| 工程完整度 | 高 | 后端、前端、数据库、Redis、迁移、测试、benchmark、脚本和文档均已成体系 |
| 可复现性 | 中高 | Mock World 主链可复现；原 README 存在本地绝对路径和信息过载问题，已在本次优化中修正 |
| 可审计性 | 高 | Benchmark Summary、System Integrity Summary、Trace Summary、Action Ledger、Recovery Review 形成闭环 |
| 真实业务可用性 | 中 | 当前正式边界是 Mock World 离线闭环，真实地图和真实写服务仍不是主链 |
| 可维护性 | 中高 | 模块分层细，spec/plan 完整；但历史任务文档数量多，README 曾过于冗长，需要持续维护文档入口层级 |

## 2. 项目定位

WeekendPilot 的定位是一个 benchmark-driven local-life planning and execution system。它不是传统“推荐几个地点”的列表工具，而是试图证明一个更完整的 agentic workflow：

```text
理解用户需求
-> 查询和搜索候选
-> 检查开放时间、路线、排队、桌位、票务等可行性
-> 生成可执行方案
-> 等待用户确认
-> 执行模拟写动作
-> 写入 Action Ledger
-> 生成反馈和审计证据
```

当前正式提交口径是 `V2 Integrity Edition`，评审重点是：

- benchmark 完整性
- memory governance
- observability
- recovery 可审计性
- Mock World 下的稳定复现能力

真实 AMap 只读能力被明确降级为可选 preview，这个边界判断是合理的。它避免了 demo 依赖外部服务、密钥、网络质量和第三方数据波动，从而使评审重点回到产品闭环与工程可靠性。

## 3. 当前完成情况

### 3.1 产品链路

已完成的用户可见链路包括：

- 公开客户页面 `5173`
- 六个 Mock World 场景入口：亲子、朋友、单人、情侣、雨天、预算
- 自然语言需求输入
- SSE 初始规划进度流
- 澄清问题和补充回答
- follow-up replan 与 visible versioning
- 方案确认和拒绝
- 确认前 action manifest
- 确认后模拟执行结果
- 运行信息折叠展示和 `run_id` 审计入口

这说明项目已经具备完整 demo 演示能力，而不是只有后端逻辑或静态页面。

### 3.2 内部评审链路

已完成的 reviewer / developer 链路包括：

- 内部评审页面 `5174`
- `Benchmark Summary`
- `System Integrity Summary`
- `Run Summary`
- `Selected Plan Review`
- `Trace Summary`
- `Tool Events`
- `Action Ledger`
- `Benchmark Artifacts`
- `Recovery Visualization`

这套内部页面对于比赛或技术评审很有价值，因为它把“系统为什么这样决策、是否越过确认边界、失败时是否安全停机”变成可展示证据。

### 3.3 Benchmark 与 evidence

当前 benchmark case 数量为 30 个，覆盖亲子、朋友、单人、情侣、雨天、预算、老人等场景，也覆盖 clarification、replan、memory governance、robustness、failure injection 和 recovery。

当前 README 与 submission 文档引用的 canonical evidence 包括：

- `release_gate_v1`：`15/15 passed`
- `coverage_gate_v1_5`：`30/30 passed`
- `v2_integrity_gate`：`20/20 passed`
- `v2_integrity_passk`：`Success@1=1.0`、`Pass@4=1.0`、`Pass^4=1.0`
- `all_registered`：`30/30 passed`
- `family_route_failure_v1` recovery review：`passed`

这些数字来自仓库中的 evidence contract 和文档口径；最终可信状态仍应以 `python scripts/show_submission_evidence.py` 的即时输出为准。

## 4. 工程规模

基于当前仓库扫描：

| 区域 | 文件数量 |
| --- | ---: |
| `backend/` | 349 |
| `frontend/src/` | 24 |
| `tests/` | 186 |
| `backend/app/benchmark/cases/` | 30 |
| `docs/specs/` | 129 |
| `docs/plans/` | 129 |

这反映出项目已经有较强的工程沉淀，尤其是任务 spec / plan 和测试资产非常多。风险是文档入口容易变复杂，新评审者可能不知道该从 README、WEB_DEMO_README、submission overview、design document 还是 evidence map 开始读。因此 README 应该保持“入口文档”定位，把细节下沉到专题文档。

## 5. 主要优势

### 5.1 交付边界清晰

项目明确声明正式主链是离线、本地、确定性的 Mock World 闭环，不把 AMap、真实写服务或 MCP 作为正式交付依赖。这降低了复现失败概率，也更适合竞赛评审。

### 5.2 安全边界设计扎实

确认前只读、确认后才写动作的约束贯穿多个层级：

- Tool Gateway 区分读写工具
- API 提供 confirm / decline 边界
- Action Ledger 记录确认后的动作
- AMap read-only preview 对确认返回 `409`
- Benchmark 检查 forbidden write before confirmation

这是项目最值得强调的工程亮点之一。

### 5.3 Benchmark 不是附属品

项目把 benchmark 当成系统设计的一部分，而不是最后补测试。`release_gate_v1`、`coverage_gate_v1_5`、`v2_integrity_gate`、`safe_stop_gate_v1`、`recovery replay review` 形成了比较完整的质量门槛。

### 5.4 可观测性面向评审

`5174` 内部评审页把 run、trace、tool、action、benchmark artifact 和 recovery link 放到一个页面上，降低了评审成本。相比只提供日志或 JSON 报告，这种 reviewer-facing observability 更容易展示价值。

### 5.5 文档资产丰富

`docs/specs/`、`docs/plans/`、`docs/submission/` 和设计文档非常完整，能证明项目是按任务持续演进出来的，而不是一次性堆代码。

## 6. 主要问题

### 6.1 README 原先不适合作为复现入口

原 README 存在以下问题：

- 在启动示例中写入了个人本地绝对路径，例如 `cd <absolute-local-project-path>`
- 信息过长，README 同时承担状态汇报、设计说明、benchmark 汇总、runbook 和测试记录
- 部分命令没有明确“从仓库根目录运行”
- Windows、macOS、Linux 的环境初始化差异不够清楚
- `.env.example`、`frontend/.env`、可选 key 的关系需要更清晰

本次已将 README 调整为更标准的项目入口文档。

### 6.2 文档层级需要持续治理

项目文档多是优势，但也带来导航成本。建议保持如下层级：

- `README.md`：快速理解、安装、启动、验证、文档索引
- `docs/PROJECT_ASSESSMENT_REPORT.md`：项目状态、价值、风险、改进建议
- `docs/TECHNICAL_REPORT.md`：架构、模块、数据流、API、测试、运维
- `docs/WEB_DEMO_README.md`：详细演示 runbook
- `docs/submission/*`：比赛提交和录制材料
- `docs/specs/`、`docs/plans/`：历史任务资产，不作为第一阅读入口

### 6.3 当前主链仍是模拟执行

这不是缺陷，而是边界限制。当前系统证明的是 agent workflow、confirmation boundary、mock provider、benchmark、observability 和 recovery。如果要进入真实业务，需要新增真实 provider、真实写动作补偿、权限授权、用户账户和风控策略。

### 6.4 依赖服务较多

本地完整运行需要 Python、Node、Docker、PostgreSQL、Redis、Alembic、Vite。对评审者来说，这比纯前端 demo 或单进程后端复杂。`demo_preflight.py` 能缓解这个问题，但 README 必须明确依赖顺序。

### 6.5 代码中存在历史中文编码显示风险

从 UTF-8 读取看，主要 Markdown 文件内容正常。但在普通 PowerShell `Get-Content` 默认输出中出现过乱码，说明 Windows 控制台编码可能影响阅读体验。建议文档中统一 UTF-8，并在需要时使用编辑器或显式 UTF-8 读取。

## 7. 风险评估

| 风险 | 等级 | 说明 | 建议 |
| --- | --- | --- | --- |
| 新人复现失败 | 中 | 依赖 PostgreSQL、Redis、Alembic、前后端双服务 | README 保持简洁，preflight 脚本作为标准检查入口 |
| 文档过载 | 中 | spec/plan 数量多，入口不清会影响评审 | README 只放入口，细节跳转专题文档 |
| evidence 过期 | 中 | README 中引用的 passed 数字可能随代码变化过期 | 以 `show_submission_evidence.py` 为准，提交前刷新 |
| 真实 provider 落差 | 中 | 当前正式路径不依赖真实地图和真实写服务 | 明确 Mock World 交付边界，不夸大真实服务能力 |
| E2E 成本 | 中 | E2E 依赖服务、迁移、Playwright 浏览器 | 将 unit、build、E2E 分层列出，不要求每次都全跑 |
| LLM 不确定性 | 低到中 | 默认 LLM disabled，LLM-backed 只是可选 preview | 继续保持确定性路径为默认 |

## 8. 建议优先级

### P0：保持当前正式提交稳定

- 保持 Mock World 作为默认主链
- 提交前运行 `demo_preflight.py` 和 `show_submission_evidence.py`
- 避免在 README 中写本机路径、个人配置或不可复现命令
- 不把 AMap preview 描述为正式主链能力

### P1：改善新评审者体验

- 保持 README 简洁
- 将演示步骤固定为 `5173 -> 5174 -> evidence script`
- 在 `docs/submission/OVERVIEW.md` 中继续维护录制口径
- 为常见失败补充 troubleshooting，例如端口占用、Docker 未启动、迁移未执行

### P2：增强真实服务演进能力

- 为 AMap/Baidu provider 增加独立 capability matrix
- 将真实写服务保持在 sandbox / dry-run / permissioned adapter 之后
- 增加 provider contract tests，避免真实 provider 改动影响 Mock World benchmark

### P3：长期工程治理

- 对 specs/plans 做索引或归档分组
- 把 canonical evidence 刷新策略写成 release checklist
- 定期检查 README 与 `.env.example`、`package.json`、`pyproject.toml` 是否一致

## 9. 总体评价

WeekendPilot 当前最强的地方不是“调用了多少外部服务”，而是把一个 local-life agent 产品拆成了可复现、可审计、可评分的工程闭环。对于比赛或技术展示，它的叙事应该聚焦在：

1. 用户只看到简单规划和确认体验
2. 系统内部严格维护确认边界
3. Mock World 保证稳定复现
4. Benchmark 和 recovery review 证明系统不是只会 happy path
5. 内部评审页把运行证据展示给 reviewer

经过 README 优化后，项目入口更适合作为开源/评审复现文档，也避免了个人本地路径带来的不专业问题。
