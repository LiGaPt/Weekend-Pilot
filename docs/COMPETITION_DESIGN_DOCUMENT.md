# WeekendPilot 竞赛设计文档

## 1. 产品目标和演示范围

WeekendPilot 是一个面向周末本地生活场景的规划与执行系统。用户只需要输入一句自然语言需求，例如“今天下午想和爱人、5 岁的孩子出门玩几个小时，别离家太远，晚餐想清淡一点”，系统会完成从理解需求、搜索候选、检查可行性、生成方案、等待确认，到模拟订座、排队、购票、点单和发送消息的完整链路。

当前 MVP 的主路径是中文亲子半日出行演示。演示通过 React/Vite Web UI 调用 FastAPI 后端，使用 Mock World 作为默认本地生活世界，不依赖真实本地生活平台、真实地图密钥或 LangSmith 在线服务。演示重点不是返回推荐列表，而是展示“生成可执行方案并在用户确认后执行动作”的闭环。

## 2. 系统架构

当前实现由以下组件组成：

- React/Vite Web UI：提供中文演示界面，用户可以输入需求、查看方案、确认或拒绝执行。
- FastAPI：提供 Web demo API，包括启动运行、查询状态、确认方案和拒绝方案。
- LangGraph：承载主工作流，保证规划、验证、确认和执行按固定节点推进。
- PostgreSQL：保存用户、记忆、运行、方案、工具事件和 Action Ledger 等持久状态。
- Redis：用于运行期缓存、限流和短期状态，不作为持久事实来源。
- Tool Gateway：所有工具调用的统一入口，负责工具注册、读写分类、缓存、限流、失败注入和事件记录。
- Mock World：默认确定性本地生活提供方，覆盖搜索、详情、营业时间、天气、队列、桌位、票务、路线和模拟写动作。
- AMAP：可选只读提供方，目前覆盖部分读工具，默认测试不会调用真实服务。
- 确定性规划服务：负责意图解析、查询计划、候选收集、候选增强、路线和时间计算、最终审查、执行和反馈。
- 有界 Agent 层：包含 Supervisor、Discovery、Dining、Itinerary Planner、Validator/Recovery 五类角色。
- 可选 LLM-backed Agent：Task 031 后，Discovery、Dining 和 Itinerary Planner 可以在配置启用时使用 LLM-backed 适配器；Supervisor 和 Validator/Recovery 仍保持确定性。
- Observability：默认写本地 JSONL 摘要，可选上传 LangSmith 摘要；核心流程不依赖 LangSmith 可用性。
- LocalLife-Bench：通过默认用例、失败注入用例和 replay harness 验证完整行为轨迹。

整体架构遵循“确定性优先，语义判断受控使用”的原则。路由、执行、安全边界、计分和持久化都由确定性代码控制；LLM 只用于更适合语义判断的候选摘要和方案排序，并且必须通过类型契约和回退逻辑保护。

## 3. 规划策略

主工作流由 LangGraph 控制，当前实现路径是：

```text
用户输入
-> 意图解析
-> 读取记忆
-> 生成查询
-> 执行搜索
-> 填充候选黑板
-> 可用性预检查
-> 逻辑规划
-> 路线和时间汇总
-> 语义验证
-> 最终审查
-> 展示给用户
-> 等待确认
-> 确定性执行
-> 生成反馈
```

意图解析、查询生成、工具执行、路线和时间计算、最终审查、确认边界、执行和反馈由确定性服务负责。这样做可以让 benchmark 验证具体轨迹，而不是只评价最终文本质量。

有界 Agent 层承担语义判断：

- Supervisor 负责把查询计划分配给后续角色，当前保持确定性。
- Discovery 聚合活动候选的语义摘要。
- Dining 聚合餐饮候选的语义摘要。
- Itinerary Planner 对已有确定性草案进行语义选择或排序。
- Validator/Recovery 检查方案并给出结构化恢复决策，当前保持确定性。

当 LLM-backed Agent 启用时，它们只能在已有输入范围内选择候选或草案，不能创建新工具调用、不能绕过确定性路线计算、不能写入业务状态，也不能执行副作用动作。

## 4. Tool Gateway 和工具调用链

所有工具调用都必须经过 Tool Gateway。Agent、规划服务和执行服务都不能直接调用 Mock World、AMAP 或其他提供方。

当前读工具包括：

- `search_poi`
- `get_poi_detail`
- `check_route`
- `check_opening_hours`
- `check_weather`
- `check_queue`
- `check_table_availability`
- `check_ticket_availability`

当前写工具包括：

- `join_queue`
- `reserve_restaurant`
- `book_ticket`
- `order_addon`
- `send_message`

确认前只允许读工具运行。系统可以搜索地点、读取详情、检查营业时间、天气、队列、桌位、票务和路线；这些调用会写入工具事件，用于审计和 benchmark 评分。

确认后才允许写工具运行。写工具由确定性执行工作流发起，并通过 Action Ledger 记录动作状态、请求摘要、响应摘要和错误摘要。Tool Gateway 会检查写工具是否携带用户确认状态，未确认写工具会被阻止。

Mock World 是默认提供方，保证本地演示和测试可重复。AMAP 是可选只读能力，用于后续真实地图集成方向；当前 MVP 不依赖它。

## 5. 人工确认和执行安全

WeekendPilot 的核心安全边界是人工确认。规划阶段只产生可审查方案和待执行动作列表，不执行订座、排队、购票、点单或消息发送。

Web demo 在方案生成后进入 `awaiting_confirmation` 状态。用户可以确认所选方案，也可以拒绝继续。拒绝后不会执行写动作。

用户确认后，确定性执行工作流才会读取已确认动作列表并调用写工具。每个写动作会进入 Action Ledger，执行结果会被反馈写入方案记录。重复确认或重复点击由幂等键保护，避免重复订座、重复取号或重复发送消息。

Agent 层不持有执行权限。即使启用 LLM-backed Agent，模型也只能返回结构化摘要或已有候选/草案选择，不能直接调用工具、不能发起写动作、不能越过确认边界。

## 6. 异常处理和恢复

系统把异常分为工具失败、工作流失败、验证失败、执行失败、观测失败和 LLM-backed Agent 回退等类型。目标是在可恢复时走有界恢复，在不可恢复时安全停止，并保留可审计元数据。

当前 recovery routing v0 由 Validator/Recovery 产生结构化决策，再由 LangGraph 根据决策路由。恢复动作包括重试读路径、扩大搜索、替换候选、重新规划、询问用户或安全停止。恢复尝试有最大次数和预算约束，不允许无界循环，也不允许恢复路由跳转到执行节点。

LocalLife-Bench 支持失败注入。当前内置 `route_unavailable_v0` 会让 Mock World 的路线检查读工具失败，用于验证路线不可用时系统能安全停止、记录失败、保持写动作数量为零，并输出可验证报告。

LLM-backed Agent 有强制确定性回退。以下情况都会回退到确定性适配器：未启用 LLM、配置不完整、请求超时、提供方错误、响应不是合法 JSON、结构不匹配、工具策略不匹配、候选 ID 无效、草案 ID 无效或没有确定性草案。回退元数据只保存安全字段，例如模型标识、提供方类型、主机、延迟、规范化用量、状态和回退原因。

Observability 失败不会使主流程失败。系统会尽量写本地摘要或 PostgreSQL 运行元数据；如果 LangSmith 不可用，Mock World 演示和 benchmark 仍可运行。

## 7. Observability 和 LocalLife-Bench 验证

系统默认记录本地 JSONL trace 摘要，并把工作流、Agent、工具、动作、benchmark 和 LLM 元数据写入受控字段。可选 LangSmith 摘要用于可视化追踪和评估，但不是运行依赖。

元数据会做脱敏处理。对外文档、Web demo 响应、benchmark 报告和 replay 报告不应暴露密钥、凭据、原始调试轨迹、原始提供方响应或内部原始标识。

LocalLife-Bench 目前包含：

- 五个默认 Mock World 家庭场景用例。
- 一个非默认路线失败注入用例。
- workflow-backed harness，用真实工作流跑完规划、确认、执行和反馈。
- replay harness，用已生成的安全报告重新运行同一用例并比较稳定字段。

评分维度覆盖工作流路径、Agent 覆盖、工具轨迹、方案质量、执行安全、反馈安全、失败注入和恢复预期。这样可以检查完整行为轨迹，而不只检查最终回答。

## 8. 运行和验证

完整本地说明见：

- `README.md`
- `docs/WEB_DEMO_README.md`

最小演示启动流程：

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
```

打开：

```text
http://127.0.0.1:5173
```

聚焦验证命令：

```bash
python -m pytest tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_llm_agents.py -q
npm --prefix frontend run build
```

浏览器端到端测试需要先准备 PostgreSQL、Redis 和 Alembic 迁移，再运行：

```bash
npm --prefix frontend run e2e
```

运行过程中产生的 trace、benchmark report、replay report 和其他 `var/` 产物都是本地运行产物，不应提交到版本库。

## 9. 当前限制和下一步

当前 MVP 已覆盖中文亲子半日 Mock World 演示、确定性工具链、确认后执行、Action Ledger、基础观测、LocalLife-Bench 默认用例、失败注入、replay，以及可选 LLM-backed Discovery、Dining 和 Itinerary Planner。

仍属于后续任务的方向包括：

- 更丰富的恢复智能，例如候选替换、重新规划和用户澄清的更细粒度策略。
- Chaos Harness 和更多失败组合。
- L3-L5 benchmark 用例、更多稳定性指标和更完整的报告。
- 更深入的真实地图提供方集成，例如 AMAP 或 Baidu MCP。
- 更丰富的 Web UI，包括执行时间线、trace 摘要、benchmark 报告和恢复可视化。
- 长期记忆治理，包括过期、置信度、敏感信息最小化和用户可控编辑。

这些方向不影响当前 MVP 演示。当前系统的默认路径仍以 Mock World、确定性执行和人工确认安全边界为核心。
