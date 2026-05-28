# WeekendPilot 参赛提交版设计说明

## 项目摘要

WeekendPilot 面向周末 2-6 小时的本地生活安排，目标不是只给出推荐列表，而是把“理解需求 -> 生成可执行方案 -> 用户确认 -> 执行动作”做成可审计闭环。参赛版默认使用 Mock World 做确定性演示；AMap 仅作为只读预览，不进入确认后的执行链路。

## 1. Planning 策略

- **固定工作流**：用户输入 -> 意图解析 -> 记忆读取 -> 查询生成 -> 搜索与候选收集 -> 可用性预检查 -> 逻辑规划 -> 路线/时间汇总 -> 语义验证 -> 最终审查 -> 向用户展示 -> 等待确认 -> 确定性执行 -> 反馈生成。
- **确定性优先**：路线计算、状态流转、执行、安全边界、计分和持久化都由确定性代码负责，避免系统在关键节点“自由发挥”。
- **语义能力受控使用**：有界 Agent 只负责候选摘要、方案排序和恢复判断，不直接发起工具调用，也不直接写入业务状态。即使启用 LLM-backed Agent，也只能在已有候选范围内做选择。
- **面向评测的意义**：系统被验证的是完整行为链路，而不是单次回答文案，因此结果可复现、可审计、可比较。

## 2. Tool Gateway 与调用链

| 阶段 | 调用链 | 关键约束 |
| --- | --- | --- |
| 规划阶段 | Web UI -> FastAPI -> LangGraph -> Planning/Agent 节点 -> Tool Gateway -> 读工具 -> Mock World 或 AMap | 只允许读工具 |
| 执行阶段 | 已确认方案 -> Saga Execution Engine -> Tool Gateway -> 写工具 -> Action Ledger | 必须携带用户确认状态 |

- **统一入口**：所有工具都必须经过 Tool Gateway，Agent 和规划节点不能直接访问 provider。
- **读写隔离**：规划阶段可调用地点搜索、详情、路线、天气、队列、桌位、票务等读工具；订座、排队、购票、加单、发消息等写工具只能在确认后进入执行。
- **审计留痕**：Tool Gateway 记录工具事件，Action Ledger 记录副作用动作的状态、请求摘要、响应摘要和错误摘要。
- **提供方边界清晰**：Mock World 是默认评测和演示路径；AMap 只读预览可以生成方案，但不能被确认执行。

## 3. 确认边界与异常恢复

- **确认边界**：系统在 `awaiting_confirmation` 之前不会执行任何写动作；用户拒绝后，动作数量保持为 0。
- **澄清边界**：当用户约束不足，或恢复流程需要用户给出取舍时，系统进入 `awaiting_clarification`，而不是编造不完整方案。
- **有界恢复**：Validator/Recovery 负责产生结构化恢复决策，LangGraph 负责执行路由。恢复动作包括重试读路径、扩大搜索、替换候选、重新规划、询问用户或安全停止。
- **预算控制**：恢复有最大次数和预算限制，不允许无界循环，也不允许绕过确认边界直接进入执行。
- **确定性回退**：LLM-backed Agent 遇到未启用、超时、返回结构不合法、候选 ID 无效等情况时，会强制回退到确定性适配器。
- **观测不阻塞主链路**：即使 LangSmith 或附加观测失败，系统仍会保留本地 JSONL / 数据库摘要，Mock World 演示和 benchmark 继续可运行。

## 4. V1.5 评审证据

正式评审请以 `docs/V1_5_REVIEW_EVIDENCE.md` 为 reviewer 入口；该文档固定了命令、最新报告路径以及提交材料归属规则。

- **V1 blocking release gate**：运行 `python scripts/run_benchmark_release_gate.py`，引用 `var/formal-benchmarks/latest-release_gate_v1-run-report.json`。
- **V1.5 coverage gate**：运行 `python scripts/run_benchmark_coverage_gate.py`，引用 `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`。
- **Full formal verification**：运行 `python scripts/run_formal_verification.py`，引用 `var/formal-benchmarks/latest-all_registered-run-report.json`。
- **Recovery replay review**：运行 `python scripts/run_recovery_replay_review.py`，引用 `var/recovery-reviews/latest-family_route_failure_v1-review.json`。
- **提交材料边界**：`docs/artifacts/` 不是 benchmark 或 recovery evidence 的 source of truth；正式引用应始终指向 `var/` 下的 canonical latest aliases。
- **评审目标**：评委可以据此分别核对 blocking 发布门槛、全量注册用例覆盖、V1.5 多样性覆盖门槛，以及标准失败恢复链条的闭环证据。

## 结论

WeekendPilot 的参赛价值不在于“再做一个会推荐地点的聊天机器人”，而在于把规划、工具调用、人工确认和异常恢复放进了同一条可验证链路里。对评委而言，这意味着它既能展示 Agent 的规划能力，也能展示进入真实执行前必须具备的安全边界与可审计性。
