# WeekendPilot 技术报告

## 1. 系统概览

WeekendPilot 是一个以 FastAPI + LangGraph 为核心的本地生活规划与执行系统。系统默认使用 `Mock World` 作为确定性数据和工具提供方，通过 PostgreSQL 持久化业务事实，通过 Redis 承担运行期缓存、限流和短期状态，通过 React/Vite 提供公开客户演示页与内部评审页。

正式运行边界：

- 默认读写 provider：`Mock World`
- 默认演示页面：`http://127.0.0.1:5173/`
- 默认内部评审页面：`http://127.0.0.1:5174/`
- 默认 API：`http://127.0.0.1:8000`
- 默认外部依赖：PostgreSQL、Redis
- 可选能力：LLM-backed agent、LangSmith tracing、AMap read-only preview

## 2. 架构分层

```text
React/Vite UI
  -> FastAPI routers
  -> DemoWorkflowService
  -> LangGraph workflow / deterministic planning services
  -> Tool Gateway
  -> Mock World / optional AMap read provider
  -> PostgreSQL + Redis + local trace buffer
```

### 2.1 Frontend

前端位于 `frontend/`，主要包含两个 Vite 入口：

- `npm --prefix frontend run dev`：公开客户演示页，默认端口 `5173`
- `npm --prefix frontend run dev:internal`：内部评审页，默认端口 `5174`

关键文件：

- `frontend/src/App.tsx`：公开客户演示主页面
- `frontend/src/internal-main.tsx`：内部评审页面入口
- `frontend/src/api/demo.ts`：demo API client
- `frontend/src/api/sse.ts`：`POST /demo/runs/stream` 的 fetch stream SSE 解析
- `frontend/src/chat/*`：对话流、进度卡、方案卡等客户侧组件逻辑
- `frontend/src/observability/*`：内部评审页 API、类型和 UI

公开页的设计重点是 customer-safe：

- 默认只展示用户可理解的信息
- 内部 trace、tool event、action id、debug key 不在客户页默认暴露
- `run_id` 等审计信息折叠到运行信息区域
- 确认动作由用户显式触发

### 2.2 Backend API

后端入口是 `backend/app/main.py`。应用加载配置后注册以下 router：

- `health_router`
- `demo_router`
- `memory_router`
- `observability_router`

核心 demo API 位于 `backend/app/api/demo.py`：

- `POST /demo/runs`
- `POST /demo/runs/stream`
- `GET /demo/runs/{run_id}`
- `POST /demo/runs/{run_id}/clarify`
- `POST /demo/runs/{run_id}/replan`
- `POST /demo/runs/{run_id}/confirm`
- `POST /demo/runs/{run_id}/decline`

每次请求通过 `_build_service()` 创建 `DemoWorkflowService`，注入：

- SQLAlchemy `Session`
- Redis client
- `JsonRedisCache`
- `FixedWindowRateLimiter`
- `RedisKeyBuilder`
- local trace buffer path
- workflow settings

### 2.3 Configuration

配置定义在 `backend/app/core/config.py`，使用 `pydantic-settings` 从 `.env` 加载。主要配置包括：

- 应用信息：`APP_NAME`、`APP_ENV`、`APP_VERSION`
- 数据库：`DATABASE_URL`
- Redis：`REDIS_URL`
- CORS：`demo_cors_origins`
- LLM：`LLM_ENABLED`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID`
- LangSmith：`LANGSMITH_TRACING`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`
- 本地 trace：`LOCAL_TRACE_BUFFER_PATH`
- 地图 preview：`AMAP_MAPS_API_KEY`、`BAIDU_MAP_API_KEY`

默认 Mock World 路径不需要 LLM、LangSmith 或地图 key。

## 3. 核心工作流

系统主工作流由 LangGraph 和确定性服务共同承载。设计文档中的目标路径是：

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

关键技术原则：

- 路由、执行、确认边界、benchmark grading 尽量确定性
- LLM-backed agent 只作为可选语义增强
- Agent 不直接持有写工具执行权限
- 工具调用必须经过 Tool Gateway
- 写动作只能在用户确认后进入执行工作流

## 4. Tool Gateway

Tool Gateway 是所有工具调用的统一入口。它负责：

- 工具注册
- provider 选择
- 读写工具分类
- 缓存
- 限流
- 失败注入
- 工具事件记录
- 确认边界检查

当前读工具：

- `search_poi`
- `get_poi_detail`
- `check_route`
- `check_opening_hours`
- `check_weather`
- `check_queue`
- `check_table_availability`
- `check_ticket_availability`

当前写工具：

- `join_queue`
- `reserve_restaurant`
- `book_ticket`
- `order_addon`
- `send_message`

确认前系统只能运行读工具；确认后写工具通过 deterministic execution workflow 发起，并写入 Action Ledger。

## 5. Provider 设计

### 5.1 Mock World

Mock World 位于 `backend/app/providers/mock_world/`，是默认 provider。它提供确定性的本地生活世界，包括：

- 活动和餐饮搜索
- POI 详情
- 营业时间
- 天气
- 排队
- 桌位
- 票务
- 路线
- 模拟写动作

fixture 覆盖：

- `family_afternoon`
- `friends_gathering`
- `solo_afternoon`
- `couple_afternoon`
- `rainy_day_fallback`
- `budget_lite`
- `elder_afternoon`

Mock World 的价值是稳定复现、稳定 benchmark 和稳定 recovery review。

### 5.2 AMap

AMap 位于 `backend/app/providers/amap/`，当前定位为 API-only read-only preview：

- 可用于本地演示只读 provider guardrails
- 不进入 `5173` 客户 UI 主链
- 不参与正式 benchmark
- 不作为 V2 Integrity Edition 的交付依赖
- 确认后写动作会被阻断

这种设计避免真实 provider 波动影响正式评审。

## 6. 数据层

### 6.1 PostgreSQL

PostgreSQL 是 durable source of truth。迁移位于 `alembic/versions/`，当前包括：

- core runtime tables
- conversation session tables
- memory item metadata JSON
- conversation turn trace snapshots

典型持久化对象包括：

- users
- memory items
- runs
- plans
- tool events
- action ledger
- conversation sessions
- conversation turns

### 6.2 Redis

Redis 用于运行期能力，不作为持久事实来源：

- JSON cache
- rate limiting
- runtime locks
- progress / short-lived state
- key prefix 隔离

### 6.3 Local Trace Buffer

默认 trace buffer 路径由 `LOCAL_TRACE_BUFFER_PATH` 控制，示例值：

```text
var/traces/weekendpilot-traces.jsonl
```

它是本地运行产物，不应作为常规代码提交内容。

## 7. Demo Service 与状态流

`DemoWorkflowService` 是公开 demo API 的应用服务层，承担：

- start run
- streamed start run
- clarify
- replan
- confirm
- decline
- get run
- run summary 投影
- public-safe progress snapshot
- local trace 写入

关键状态包括：

- `awaiting_clarification`
- `awaiting_confirmation`
- `completed`
- `partially_completed`
- `failed`
- `declined`

初始规划支持 `POST /demo/runs/stream`，事件类型包括：

- `progress`
- `summary`
- `error`

clarify、replan、confirm、decline 仍是同步 API。

## 8. Benchmark 体系

Benchmark 代码位于 `backend/app/benchmark/`，case 位于 `backend/app/benchmark/cases/`。当前扫描到 30 个 case。

主要入口：

- release gate：`scripts/run_benchmark_release_gate.py`
- coverage gate：`scripts/run_benchmark_coverage_gate.py`
- V2 integrity gate：`scripts/run_benchmark_v2_integrity_gate.py`
- stability Pass@k：`scripts/run_benchmark_stability_passk.py`
- formal verification：`scripts/run_formal_verification.py`
- recovery replay review：`scripts/run_recovery_replay_review.py`
- evidence summary：`scripts/show_submission_evidence.py`

当前 evidence contract 在 `backend/app/benchmark/submission_evidence.py` 中定义，并由 `scripts/show_submission_evidence.py` 读取和汇总。

## 9. Observability

Observability 分成三层：

1. 本地 JSONL trace：便于离线保留摘要
2. PostgreSQL run metadata：用于内部评审页查询
3. 可选 LangSmith：用于外部 trace 可视化，不是默认运行依赖

内部评审页通过 observability API 展示：

- workflow outcome
- stage timing
- node history
- tool event rollup
- action ledger
- selected plan review
- benchmark artifact context
- recovery path summary

这使 reviewer 能够检查完整轨迹，而不仅是最终回答。

## 10. 安全设计

### 10.1 人工确认边界

规划阶段只产生方案和拟执行动作，不执行副作用。用户确认后，执行工作流才运行写工具。

### 10.2 写工具幂等

写动作进入 Action Ledger，并使用 idempotency key 防止重复确认或重复点击造成重复订座、取号、购票、点单或发消息。

### 10.3 Public-safe 响应

客户页面不默认暴露：

- internal trace
- raw provider response
- secret / token / api key
- tool_event_id
- action_id
- idempotency_key
- debug trace

内部评审页展示的是面向 reviewer 的受控摘要。

### 10.4 Recovery safe stop

失败恢复有最大次数和预算，不允许无界循环。无法恢复时进入 safe stop，保持零写动作，并生成 recovery review 证据。

## 11. 测试体系

测试分层：

- 后端单元测试：planning、tool gateway、providers、workflow、benchmark、memory、observability
- 后端集成测试：database、Redis、gateway、workflow-backed benchmark
- 前端单元测试：API client、SSE parser、chat thread、observability page
- 前端 E2E：公开客户页、内部评审页、desktop/mobile smoke
- 脚本测试：submission evidence、demo support scripts、review evidence

常用验证命令：

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
python -m pytest tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_llm_agents.py -q
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run e2e
```

E2E 前需要 PostgreSQL、Redis 和 Alembic migration 已就绪。

## 12. 部署与运行假设

当前项目面向本地演示和评审，不是生产部署模板。运行假设：

- 开发者已安装 Python 3.11+
- 开发者已安装 Node.js 和 npm
- Docker Compose 可运行 PostgreSQL 和 Redis
- 仓库根目录下存在 `.env`
- 数据库已执行 `python -m alembic upgrade head`
- 后端、公开前端、内部前端分别运行在 `8000`、`5173`、`5174`

生产化前还需要补充：

- deployment manifests
- secret management
- authn/authz
- real provider permission model
- observability backend
- error alerting
- data retention policy

## 13. 技术风险与改进建议

| 风险 | 影响 | 建议 |
| --- | --- | --- |
| 文档和 evidence 口径漂移 | README 引用结果可能过期 | 提交前固定运行 `show_submission_evidence.py` |
| 本地依赖多 | 新人启动成本高 | 保持 README quickstart 简洁，强化 preflight |
| provider 边界误解 | 评审者可能误以为接入真实写服务 | 所有文档明确 Mock World 正式边界 |
| E2E 易受环境影响 | 端口、Docker、浏览器依赖可能失败 | unit/build/evidence 分层验证，E2E 作为完整门禁 |
| 真实 provider 扩展复杂 | 外部 API 不稳定且权限风险高 | 先做 read-only provider contract，再考虑 permissioned writes |
| 文档资产过多 | 导航困难 | README 做入口，专题文档承载细节 |

## 14. 后续技术路线

建议按以下顺序推进：

1. **文档治理**：维护 README、assessment report、technical report、submission docs 的边界
2. **Evidence release checklist**：把 evidence 刷新和验证变成固定发布步骤
3. **Provider contract**：为真实地图 provider 建立只读 contract tests
4. **Recovery 强化**：丰富候选替换、重新规划、用户澄清策略
5. **Production readiness**：补认证、权限、secret 管理、部署、监控和数据保留

## 15. 技术结论

WeekendPilot 的技术路线是合理的：用 Mock World 稳定证明闭环，用 Tool Gateway 和 Action Ledger 保证确认边界，用 benchmark 和 recovery replay 证明行为轨迹，用内部评审页降低审计成本。

当前项目已经适合作为比赛或技术展示中的完整工程案例。后续如果要从“竞赛交付”走向“真实产品”，重点不应是简单增加 LLM 能力，而应优先补真实 provider contract、权限模型、生产部署和异常补偿机制。
