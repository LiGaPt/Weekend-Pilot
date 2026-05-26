# 下一阶段路线图

## 1. 结论

WeekendPilot 的初版已经不是“只有一个 demo”的状态了。仓库里已经完成了从 001 到 032 的一整套 spec / plan 链路，覆盖了核心 runtime、workflow、confirmation、execution、observability、benchmark、failure injection、replay、LLM-backed bounded agents，以及 competition design document。

所以，`docs/PROJECT_BLUEPRINT.md` 里的初始任务路线图可以视为基本完成；但蓝图里的 V1 / V2 演进项还没有全部收口，尤其是多场景、多轮对话、阶段级 P95/P99、前台与观测端分离、L3-L5 benchmark、Chaos Harness、真实 provider 渐进接入、长期记忆治理的剩余闭环这些方向，还属于下一阶段。

这份文档不是重写蓝图，而是作为后续分 task 和执行的总路线图。

## 2. 当前完成度

### 已完成的主线

- 核心 backend scaffold、PostgreSQL、Redis、Tool Gateway、Mock World。
- 确定性规划、candidate enrichment、itinerary draft、final review、human confirmation、execution workflow、feedback writer。
- LangSmith / local trace observability。
- workflow-backed LocalLife-Bench、benchmark expansion、failure injection、replay。
- V1 workflow state / DAG alignment、bounded recovery routing、LLM-backed bounded agents。
- Minimal Web UI、Web demo API、Web e2e 基础、competition design document。

### 仍然未完成的方向

- 多场景覆盖，不再只围绕亲子半日场景。
- 多轮对话，不再是单次输入 prompt 直接出结果。
- benchmark 的阶段级延迟、P95 / P99、跨案例稳定性。
- 客户前端与内部观测前端分离。
- 更完整的恢复能力、Chaos Harness、失败组合。
- 更丰富的真实 provider 渐进接入。
- 长期记忆治理的剩余闭环：当前 read-memory governance V1 slice 已实现并有 benchmark 证据，但 memory CRUD、用户可控编辑和更强的敏感信息最小化仍未完成。

## 3. 路线图原则

- 先把评测和观测做硬，再扩展用户体验。
- 客户可见内容与内部可观测内容分离，不再混在同一个前端里。
- Mock World 继续作为稳定评测基座，真实 provider 采用渐进接入。
- 保持确认边界和 Action Ledger 安全不变。
- 后续仍然坚持“一 task 一 spec、一 plan、一实现、一验证、一提交”。

## 4. 下一阶段里程碑

### M1. 评测与观测基础设施

目标是把“能跑”变成“能量化比较”。

建议优先做：

- 为 workflow 的各阶段补埋点和耗时统计。
- 在 benchmark report 中输出阶段级统计与分位数，如 P50 / P95 / P99。
- 统一 run summary、trace summary、benchmark summary 的输出结构。
- 让每个 case 的性能、稳定性、失败原因都可以直接对比。

阶段退出条件：

- 可以按阶段看到耗时分布。
- 可以按 case / suite 汇总 benchmark 性能指标。
- 后续前端和评估都能直接消费这些数据。

### M2. 前端分离

目标是把“给客户看”的页面和“给开发/评审看”的页面拆开。

建议拆成两套前端：

- 客户端前端：只展示需求输入、方案、确认、执行结果、必要的反馈信息。
- 观测前端：展示 trace、node history、tool events、action ledger、benchmark 结果、恢复路径。

阶段退出条件：

- 客户端不再直接暴露 trace_id、node_history、agent_roles 等内部信息。
- 内部观测端可以完整查看链路和运行细节。
- 两套前端共享后端基础 API，但视图层职责清晰。

### M3. 多场景与 benchmark 扩展

目标是让系统不再只在亲子场景上表现得好看。

建议引入的场景族：

- 情侣 / 朋友聚会。
- 单人轻量周末活动。
- 老人同行或多代同行。
- 雨天备选方案。
- 预算受限方案。
- 排队过长、售罄、路线不可用等失败场景。

阶段退出条件：

- benchmark 不再只覆盖单一亲子场景。
- 能用不同 persona + constraint + failure 组合检验系统。
- 可以看出系统在不同场景下的稳定性差异。

### M4. 多轮对话与方案版本

目标是把一次性生成方案改成真正的会话式规划。

建议支持：

- 澄清轮：补齐出发地、预算、时间、偏好等缺失信息。
- 改需求轮：用户中途修改约束后重新规划。
- 方案版本：v1 / v2 / v3 这样记录计划演化。
- 执行前 action manifest：确认后会执行什么，提前可见。

阶段退出条件：

- 一个 run 可以包含多个 user turn。
- 一个 run 可以产生多个 plan version。
- 最终方案是对话过程的结果，而不是一次 prompt 的静态输出。

### M5. 恢复、真实 provider、记忆治理

目标是把系统从“可演示”推进到“可扩展”。

当前状态：

- read-memory governance V1 slice 已经实现并进入 benchmark 体系。
- 现有能力已经覆盖显式用户输入优先、advisory memory 补全模糊请求、以及 expired high-confidence memory downgrade 的可审计行为。
- 这意味着 M5 并不是“从零开始做 memory governance”，而是继续补齐更完整的治理闭环。

建议继续做：

- 更细粒度的 recovery routing 和 recovery visualization。
- Chaos Harness，覆盖更多失败组合。
- 真实地图 provider 的只读渐进接入。
- 长期记忆治理剩余闭环：更强的敏感信息最小化、用户可控编辑 / 删除、以及更完整的生命周期治理。

阶段退出条件：

- 恢复策略可解释、可回放、可评测。
- 真实 provider 不破坏 Mock World 的稳定评测。
- 记忆不再只是“存起来”，而是可治理、可审计、可控。

## 5. 建议的 task 顺序

下面是建议的后续 task 方向，后面可以继续拆成正式 spec / plan：

1. 阶段耗时埋点与 benchmark 分位数报告。
2. 内部观测 API 与观测端页面骨架。
3. 客户端 / 观测端前端拆分。
4. 场景 taxonomy 与 Mock World 场景扩展。
5. benchmark case matrix 与 case 生成策略。
6. session / conversation 数据模型。
7. 多轮澄清与 replan 工作流。
8. plan versioning 与执行前 action manifest。
9. 恢复路径可视化与 replay 联动。
10. 长期记忆治理剩余闭环（memory CRUD / 用户控制 / 敏感信息最小化）。
11. AMAP read-only 渐进接入。
12. Chaos Harness。

## 6. 执行规则

- 每个 task 仍然只做一个清晰目标。
- 每个 task 仍然要有 spec、plan、实现、验证和提交。
- 不在路线图里一次性展开所有细节，细节留给后续 task spec。
- 先做能提高评估质量和可观测性的事，再做更花哨的展示和更复杂的能力扩展。
