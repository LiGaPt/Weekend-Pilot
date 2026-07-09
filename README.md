# WeekendPilot

WeekendPilot 是一个面向周末本地生活场景的规划、确认与执行系统。用户输入一句自然语言需求后，系统会完成需求理解、候选搜索、可行性检查、方案生成、人工确认、模拟执行和审计记录。

当前交付口径是 `V2 Integrity Edition`：正式演示、benchmark、recovery review 和 reviewer 证据都基于 `offline/local`、离线、本地、确定性的 `Mock World` 闭环。This submission does not connect to real-world write services and does not depend on true MCP integration. 默认主链不连接真实写服务，不依赖真实地图密钥，也不依赖真实 MCP 集成。当前正式评审重点是 benchmark 完整性、memory governance、observability 与 recovery 可审计性。

## 核心能力

- **公开演示主链**：`planning`、`clarification`、`replan`、`confirm / decline`、`execution result`
- **人工确认边界**：确认前只允许读工具，确认后才模拟写动作并写入 Action Ledger
- **Mock World 数据面**：覆盖亲子、朋友、单人、情侣、雨天、预算等本地生活场景
- **Memory governance**：覆盖长期记忆启用、禁用、过期、覆盖、敏感信息最小化和用户可控治理
- **内部评审台**：展示 benchmark、system integrity、run audit、trace、tool events、action ledger、recovery visualization
- **可审计 benchmark**：包含 release gate、coverage gate、V2 integrity gate、Pass@k stability、formal verification、recovery review
- **可选 AMap 预览**：只作为 API/script-only read-only preview，不进入默认客户 UI 主链，也不参与正式 benchmark

## 当前版本路线图

![WeekendPilot current version roadmap](docs/assets/readme-current-version-roadmap.svg)

这张图概括了公开主链、系统分层、Mock World 数据面、benchmark evidence 和内部评审链路。

## Mock World

`Mock World` 是当前正式演示、benchmark、recovery review 和 reviewer evidence 的默认数据面。它提供确定性的本地生活候选、可用性检查、路线检查和模拟写动作，使规划、确认、执行模拟、失败恢复与审计证据都能在本地稳定复现。

当前公开场景包括 `亲子`、`朋友`、`单人`、`情侣`、`雨天` 和 `预算`。这些场景映射到已注册 world profile，并包含额外候选、`distractor`、不可用候选和失败注入组合，用来验证筛选、fallback、排序稳定性、确认边界和安全停机。

`AMap` 仍然只是可选 API/script-only read-only preview；它不进入 `5173` customer UI 主链，不参与正式 benchmark，也不是 `V2 Integrity Edition` 的交付依赖。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| Backend | Python 3.11+、FastAPI、LangGraph、SQLAlchemy、Alembic、Pydantic Settings |
| Runtime | PostgreSQL、Redis、Docker Compose |
| Frontend | React 19、Vite 7、TypeScript、Vitest、Playwright |
| Observability | 本地 JSONL trace、PostgreSQL run metadata、可选 LangSmith |
| Benchmark | LocalLife-Bench harness、Mock World fixtures、failure injection、recovery replay |

## 项目结构

```text
backend/                  # FastAPI、工作流、工具网关、规划、benchmark、providers
frontend/                 # React/Vite 客户演示页和内部评审页
tests/                    # 后端单元测试与集成测试
alembic/                  # PostgreSQL 迁移
scripts/                  # demo、preflight、benchmark、evidence 脚本
docs/                     # 设计文档、提交材料、spec、plan、报告
docker-compose.yml        # 本地 PostgreSQL / Redis
pyproject.toml            # Python 包和测试配置
```

当前仓库规模概览：

- `backend/`：349 个文件
- `frontend/src/`：24 个文件
- `tests/`：186 个测试文件
- `backend/app/benchmark/cases/`：30 个 benchmark case
- `docs/specs/` 与 `docs/plans/`：各 129 个任务文档

## 本地启动

以下命令均假设你已经位于项目根目录。不要把个人电脑上的绝对路径写进文档或脚本；不同开发者只需要进入自己克隆出来的仓库目录即可。

### 1. 克隆并进入项目

```bash
git clone <your-repo-url>
cd <repo-directory>
```

如果你已经在仓库根目录，可以直接从下一步开始。

### 2. 准备 Python 环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### 3. 准备环境变量

复制示例文件：

```bash
cp .env.example .env
```

Windows PowerShell 也可以使用：

```powershell
Copy-Item .env.example .env
```

默认 `Mock World` 演示、benchmark 和测试不需要真实 API key。只有在你要演示 AMap 只读预览时，才需要在 `.env` 中配置：

```text
AMAP_MAPS_API_KEY=your-local-key
```

不要提交 `.env`、API key、token 或 secret。

### 4. 启动基础服务并迁移数据库

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

### 5. 启动后端 API

```bash
uvicorn backend.app.main:app --reload
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
http://127.0.0.1:8000/health
```

### 6. 启动前端

安装前端依赖：

```bash
npm --prefix frontend install
```

启动公开客户演示页：

```bash
npm --prefix frontend run dev
```

启动内部评审页：

```bash
npm --prefix frontend run dev:internal
```

访问地址：

- 公开演示页：`http://127.0.0.1:5173/`
- 内部评审页：`http://127.0.0.1:5174/`

前端默认调用 `http://127.0.0.1:8000`。如需覆盖，创建 `frontend/.env`：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 推荐演示路径

1. 打开 `http://127.0.0.1:5173/`
2. 选择一个 Mock World 场景，例如 `亲子`
3. 提交需求，等待系统进入 `awaiting_confirmation`
4. 展示方案、确认前动作和人工确认边界
5. 点击确认，展示模拟执行结果
6. 复制或查看 `run_id`
7. 打开 `http://127.0.0.1:5174/`
8. 查看 `Benchmark Summary`、`System Integrity Summary`
9. 粘贴 `run_id`，审计 `Run Summary`、`Trace Summary`、`Tool Events`、`Action Ledger`、`Recovery Visualization`

正式提交或录制前建议运行：

```bash
python scripts/demo_preflight.py
python scripts/show_submission_evidence.py
```

如果要展示 AMap 只读预览：

```bash
python scripts/demo_amap_preview.py
```

## 关键 API

公开 demo API：

- `POST /demo/runs`
- `POST /demo/runs/stream`
- `GET /demo/runs/{run_id}`
- `POST /demo/runs/{run_id}/clarify`
- `POST /demo/runs/{run_id}/replan`
- `POST /demo/runs/{run_id}/confirm`
- `POST /demo/runs/{run_id}/decline`

内部评审 API：

- `GET /internal/runs/{run_id}/observability`
- `GET /internal/benchmarks/release-gate-v1/summary`
- `GET /internal/system/integrity-summary`

## Benchmark 与 evidence

当前正式证据口径：

| 入口 | 证明内容 | Canonical alias |
| --- | --- | --- |
| `release_gate_v1` | 主产品路径、确认边界、执行链路、基础失败恢复 | `var/formal-benchmarks/latest-release_gate_v1-run-report.json` |
| `coverage_gate_v1_5` | 场景广度、tag 覆盖、failure mode 覆盖 | `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json` |
| `v2_integrity_gate` | V2 完整性 gate | `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json` |
| `v2_integrity_passk` | repeated-run stability | `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json` |
| `all_registered` | 全量 30 个注册 case formal verification | `var/formal-benchmarks/latest-all_registered-run-report.json` |
| `family_route_failure_v1` | 固定失败恢复审查链 | `var/recovery-reviews/latest-family_route_failure_v1-review.json` |

当前 canonical latest evidence 摘要：

- `release_gate_v1`：`15/15` passed，`overall_score=1.0`
- `coverage_gate_v1_5`：`30/30` passed，`overall_score=1.0`
- `v2_integrity_gate`：`20/20` passed，`release_blocked=false`
- `v2_integrity_passk`：`Success@1=1.0`，`Pass@4=1.0`，`Pass^4=1.0`
- `all_registered`：`30/30` passed，`overall_score=1.0`
- `family_route_failure_v1` recovery review：`3/3` checks passed

快速查看 evidence：

```bash
python scripts/show_submission_evidence.py
```

刷新主要 evidence：

```bash
python scripts/run_benchmark_release_gate.py
python scripts/run_benchmark_coverage_gate.py
python scripts/run_benchmark_v2_integrity_gate.py
python scripts/run_benchmark_stability_passk.py
python scripts/run_formal_verification.py
python scripts/run_recovery_replay_review.py
```

## 测试与验证

后端聚焦测试：

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
```

后端核心工作流测试：

```bash
python -m pytest tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_llm_agents.py -q
```

前端单元测试：

```bash
npm --prefix frontend run test -- --run
```

前端聚焦单元测试：

```bash
npm --prefix frontend test -- --run src/chat/ConversationThread.test.tsx src/App.test.tsx
```

前端构建：

```bash
npm --prefix frontend run build
```

浏览器 E2E 测试需要先准备 PostgreSQL、Redis、Alembic 迁移，并安装 Playwright Chromium：

```bash
npm --prefix frontend run e2e:install
npm --prefix frontend run e2e
```

当前 README 对应的聚焦验证记录：

- `python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q`：`23 passed`
- `npm --prefix frontend test -- --run src/chat/ConversationThread.test.tsx src/App.test.tsx`：`24 passed`

## 配置说明

主要环境变量见 `.env.example`：

- `DATABASE_URL`：PostgreSQL 连接串
- `REDIS_URL`：Redis 连接串
- `LLM_ENABLED`：是否启用可选 LLM-backed agent
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_ID`：可选 LLM provider 配置
- `LANGSMITH_TRACING` / `LANGSMITH_API_KEY`：可选 LangSmith tracing
- `LOCAL_TRACE_BUFFER_PATH`：本地 trace JSONL 路径
- `AMAP_MAPS_API_KEY`：可选 AMap 只读预览 key

默认 Mock World 路径不需要 LLM、LangSmith、AMap 或 Baidu key。

## 详细文档

- 项目评估报告：[docs/PROJECT_ASSESSMENT_REPORT.md](docs/PROJECT_ASSESSMENT_REPORT.md)
- 技术报告：[docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md)
- 竞赛设计文档：[docs/COMPETITION_DESIGN_DOCUMENT.md](docs/COMPETITION_DESIGN_DOCUMENT.md)
- Web demo runbook：[docs/WEB_DEMO_README.md](docs/WEB_DEMO_README.md)
- Reviewer evidence 入口：[docs/V1_5_REVIEW_EVIDENCE.md](docs/V1_5_REVIEW_EVIDENCE.md)
- 提交总览：[docs/submission/OVERVIEW.md](docs/submission/OVERVIEW.md)
- 功能覆盖：[docs/submission/FUNCTION_COVERAGE_MAP.md](docs/submission/FUNCTION_COVERAGE_MAP.md)
- Evidence map：[docs/submission/EVIDENCE_MAP.md](docs/submission/EVIDENCE_MAP.md)

## 不应提交的内容

- `.env`、`frontend/.env`
- API keys、tokens、secrets、credentials
- `node_modules/`
- `frontend/dist/`
- `frontend/playwright-report/`
- `frontend/test-results/`
- `frontend/blob-report/`
- screenshots、videos、traces 等临时测试产物
- `var/` 下的本地运行产物，除非某次提交明确要求刷新 canonical evidence
