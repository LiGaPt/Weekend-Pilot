# Spec: 061 Formal Verification Script

## 1. Goal

在当前仓库里补上一条真正可复现的“正式验证”入口：从 repo root 执行一个命令，就能启动本地依赖、确认 PostgreSQL/Redis 就绪、应用 Alembic 迁移、跑完整的 `all_registered` benchmark suite，并把这次正式验证的 suite 报告、case 报告和 trace 输出到专用目录下。

当前仓库已经具备完整的 benchmark harness、suite catalog、timing summary、continuation case、recovery case 和 Web demo 收口能力；但“正式验证”仍停留在手工操作层，工作区中甚至已经出现了未纳入任务链的 submission 草稿和 formal report 草稿。完成本任务后，正式验证应从“手工跑若干命令并手工整理结果”变成“仓库内有一个受测试保护的一键执行脚本，能够稳定地产出当前注册 benchmark 套件的正式验证结果”。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 明确要求 WeekendPilot 是 benchmark-driven、observable-by-default 的系统，并要求每个 task 都保持小范围、可验证、可提交。`docs/NEXT_PHASE_ROADMAP.md` 进一步说明当前阶段默认优先 `M1. 评测与观测基础设施`，先把“能跑”收口成“能量化比较、能稳定复现”。

仓库当前已经具备本任务所依赖的基础：

- `backend.app.benchmark.harness.BenchmarkHarness` 已支持 `run_suite("all_registered")`
- benchmark suite catalog 已收口到 `all_registered` 等规范命名套件
- suite run report 已包含 `benchmark_summary`、`benchmark_timing_summary`、matrix summary、outcome rollup
- benchmark case 与 suite report 已通过 `backend.app.benchmark.reporting` 做过敏感字段清洗
- PostgreSQL / Redis / Alembic / local trace buffer 都已在 README 中有明确本地使用方式
- 最新编号任务已经到 `060`，并完成 customer replan flow；当前没有更晚的编号 task

当前最直接的缺口不是继续扩功能，而是把现有 benchmark/observability 基础设施封装成正式验证入口。这一缺口与以下 blueprint 领域直接相关：

- PostgreSQL source of truth
- Redis runtime layer
- LocalLife-Bench
- LangSmith / local trace observability fallback
- Small, reviewable tasks
- Development workflow中的 verification 阶段

这个 task 对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M1. 评测与观测基础设施`，属于收口型任务，而不是新增产品能力任务。

## 3. Requirements

- 新增一个可复用的正式验证 orchestration 模块，建议放在：
  - `backend/app/benchmark/formal_verification.py`
- 新增一个 repo-root 一键脚本，路径固定为：
  - `scripts/run_formal_verification.py`
- 正式验证的标准入口命令固定为：
  - `python scripts/run_formal_verification.py`
- 该脚本必须基于现有仓库能力工作，不得引入新的环境变量、数据库表、依赖或外部服务。
- 脚本必须在默认路径下调用：
  - `docker compose up -d postgres redis`
- 脚本必须在 benchmark 运行前等待 PostgreSQL 和 Redis 可连接；若在超时窗口内不可连接，必须失败退出而不是继续执行。
- 脚本必须在 benchmark 运行前执行 Alembic 升级到当前 head。
- 脚本必须只运行现有 canonical suite：
  - `all_registered`
- 脚本不得在本 task 内增加 suite selector、case selector、benchmark browser 或新的 benchmark contract。
- 每次正式验证必须写入一个唯一运行目录，根目录固定在：
  - `var/formal-benchmarks/`
- 唯一运行目录命名必须是：
  - `var/formal-benchmarks/formal-<unique-id>/`
- 该运行目录必须包含：
  - 现有 harness 产出的 case reports
  - 现有 harness 产出的 suite report
  - 这次正式验证使用的 trace buffer 文件
- trace buffer 文件必须放在同一正式验证运行目录下，不得复用 README 默认的共享 `var/traces/weekendpilot-traces.jsonl` 路径。
- 脚本必须额外刷新一个稳定别名文件：
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
- `latest-all_registered-run-report.json` 必须是本次成功 suite report 的字节级拷贝，不得重写其内部 `report_path`、case `report_path` 或其他嵌套字段。
- 成功运行后，脚本必须在 stdout 打印简洁摘要，至少包括：
  - suite ID
  - case count
  - passed count
  - failed count
  - error count
  - overall score
  - p50 / p95 总耗时
  - unique run directory
  - suite report path
  - latest report alias path
- 脚本必须在这些条件全部满足时返回退出码 `0`：
  - `suite_id == "all_registered"`
  - `run_status == "passed"`
  - `failed_count == 0`
  - `error_count == 0`
  - `report_path` 存在
  - `latest-all_registered-run-report.json` 已刷新
- 只要发生以下任一情况，脚本必须返回非零退出码：
  - `docker compose up` 失败
  - PostgreSQL / Redis readiness 超时
  - Alembic upgrade 失败
  - benchmark suite run_status 不是 `passed`
  - suite report 路径不存在
  - latest alias 写入失败
- 如果 benchmark 运行产生了唯一运行目录，但 suite 最终失败或报错：
  - 该唯一运行目录应保留，便于事后检查
  - `latest-all_registered-run-report.json` 不得被失败结果覆盖
- 正式验证 runner 必须复用现有 `BenchmarkHarness`，不得复制 benchmark 执行逻辑，不得重新实现 suite summary 生成。
- 正式验证 runner 产生的 JSON 报告必须继续依赖现有清洗逻辑，不得绕过 `backend.app.benchmark.reporting` 直接写未经清洗的报告。
- 正式验证 runner 不得要求 LangSmith 凭据，也不得要求 live AMap。
- 新增单元测试覆盖正式验证编排逻辑。
- 新增集成测试覆盖正式验证成功路径。
- 更新 `README.md`，加入正式验证脚本的用途、命令、依赖前提和输出路径说明。
- 本 task 不得修改：
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/artifacts/benchmark-all-registered-formal-report.json`
  - benchmark suite 内容
  - benchmark score 规则
  - public API contract
  - frontend customer/internal surface

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- 不新增 benchmark case、suite、taxonomy、failure profile 或 replay 规则。
- 不修改 `docs/COMPETITION_SUBMISSION_DESIGN.md` 或当前 `docs/artifacts/benchmark-all-registered-formal-report.json` 草稿。
- 不把正式验证结果发布到 `docs/artifacts/`，本 task 只负责在 `var/` 下生成可复现输出。
- 不新增 CI workflow、GitHub Actions、pre-commit hook 或 package console entry point。
- 不修改 frontend、Web demo、internal observability page、database schema、Alembic migration 内容或 Tool Gateway 行为。
- 不引入 live AMap、LangSmith 必需依赖、认证或额外运维组件。
- 不暂存或提交当前工作树里与本 task 无关的本地文件：`.gitignore`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/artifacts/`、`qc`、`var/`、`frontend/dist/` 等。

## 5. Interfaces and Contracts

### Inputs

- Repo-root command:
  - `python scripts/run_formal_verification.py`
- Existing runtime configuration:
  - `database_url`
  - `redis_url`
- Existing local infrastructure:
  - `docker compose` service names `postgres` and `redis`
  - `alembic.ini`
- Existing benchmark execution surface:
  - `BenchmarkHarness.run_suite("all_registered")`

### Outputs

- Unique formal verification run directory:
  - `var/formal-benchmarks/formal-<unique-id>/`
- Unique suite report:
  - `var/formal-benchmarks/formal-<unique-id>/suite-all_registered-run-report.json`
- Stable latest alias:
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
- Human-readable stdout summary
- Process exit code:
  - `0` on success
  - non-zero on failure

### Schemas

Internal orchestration result example:

```json
{
  "suite_id": "all_registered",
  "run_status": "passed",
  "case_count": 17,
  "passed_count": 17,
  "failed_count": 0,
  "error_count": 0,
  "overall_score": 1.0,
  "run_directory": "var/formal-benchmarks/formal-12345678-1234-1234-1234-123456789abc",
  "suite_report_path": "var/formal-benchmarks/formal-12345678-1234-1234-1234-123456789abc/suite-all_registered-run-report.json",
  "latest_report_path": "var/formal-benchmarks/latest-all_registered-run-report.json",
  "trace_buffer_path": "var/formal-benchmarks/formal-12345678-1234-1234-1234-123456789abc/formal-traces.jsonl"
}
```

CLI success summary example:

```text
Formal verification passed.
Suite: all_registered
Cases: 17 (17 passed, 0 failed, 0 error)
Overall score: 1.0
Timing: p50=446ms, p95=1564ms
Run directory: var/formal-benchmarks/formal-12345678-1234-1234-1234-123456789abc
Suite report: var/formal-benchmarks/formal-12345678-1234-1234-1234-123456789abc/suite-all_registered-run-report.json
Latest report: var/formal-benchmarks/latest-all_registered-run-report.json
```

## 6. Observability

本 task 不新增新的 telemetry backend，也不新增新的数据库持久化字段。

它必须复用并保留现有 observability 行为：

- formal verification 产生的 case report 和 suite report 继续使用现有 benchmark report sanitization
- trace buffer 继续走现有 local JSONL trace 路径，只是本 task 为每次 formal run 生成独立 trace 文件
- 不要求 LangSmith 成功；LangSmith 不可用时 formal verification 仍可完成
- 不允许在 stdout、stderr 或 JSON 报告中暴露：
  - API key
  - token
  - secret
  - authorization
  - prompt
  - debug trace
  - raw action IDs
  - raw tool event IDs
  - traceback bodies

如果 formal verification 失败，唯一运行目录中的已生成报告可以保留用于排查，但脚本不得把失败结果伪装成 latest passing alias。

## 7. Failure Handling

- 如果 `docker compose up -d postgres redis` 返回非零退出码，脚本必须立即失败并返回非零退出码。
- 如果 PostgreSQL 或 Redis 在等待窗口内仍不可连接，脚本必须失败退出，并给出明确的 readiness timeout 信息。
- 如果 Alembic upgrade 失败，脚本必须失败退出，不得继续跑 benchmark。
- 如果 `BenchmarkHarness.run_suite("all_registered")` 返回：
  - `run_status != "passed"`
  - 或 `failed_count > 0`
  - 或 `error_count > 0`
  脚本必须失败退出。
- 如果 harness 返回了 `report_path` 但文件不存在，脚本必须失败退出。
- 如果唯一运行目录已经写入，但 final success 条件不满足：
  - 保留该目录
  - 不刷新 `latest-all_registered-run-report.json`
- 如果 latest alias 写入失败，脚本必须失败退出，并保留唯一运行目录。
- 如果脚本失败，stderr 必须提供 reviewer/developer 可读的失败原因；不得只抛裸异常栈。
- 本 task 不需要自动重试 benchmark suite，也不需要自动清理历史 formal run 目录。

## 8. Acceptance Criteria

- [ ] `docs/specs/061-formal-verification-script.md` exists and matches this task.
- [ ] `docs/plans/061-formal-verification-script-plan.md` exists and matches this task.
- [ ] 最新已落地编号仍是 `060`，本任务使用新的 `061` 编号。
- [ ] `python scripts/run_formal_verification.py` 是正式验证的 repo-root 标准入口。
- [ ] 脚本会自动启动 `postgres` 和 `redis`、等待依赖可连接，并在 benchmark 前执行 Alembic upgrade。
- [ ] 脚本只运行 `all_registered` suite。
- [ ] 每次成功执行都会生成唯一运行目录 `var/formal-benchmarks/formal-<unique-id>/`。
- [ ] 成功执行会生成 suite report 与 case reports，并在同目录下生成本次 trace buffer 文件。
- [ ] 成功执行会刷新 `var/formal-benchmarks/latest-all_registered-run-report.json`。
- [ ] latest alias 是 suite report 的字节级拷贝，不会重写内部 `report_path` 字段。
- [ ] 如果 suite 失败或报错，脚本返回非零退出码，且不会覆盖上一次成功的 latest alias。
- [ ] 成功执行的 stdout 会输出 suite ID、通过/失败统计、overall score、P50/P95、run directory、suite report path 和 latest alias path。
- [ ] 本 task 新增单元测试覆盖 formal verification orchestration。
- [ ] 本 task 新增集成测试覆盖 formal verification success path。
- [ ] `README.md` 已加入正式验证脚本说明。
- [ ] `docs/COMPETITION_SUBMISSION_DESIGN.md` 与 `docs/artifacts/benchmark-all-registered-formal-report.json` 在本 task 中保持不变。
- [ ] 不新增 benchmark case、suite、frontend、public API、migration 或 dependency 变更。
- [ ] 没有 `.env`、API key、token、secret、`var/` 输出、或无关本地文件被 git 跟踪。
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_formal_verification.py tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_formal_verification.py tests/integration/test_benchmark_harness_gateway.py -k "formal_verification or all_registered" -v
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add formal verification script
```

## 11. Notes for the Implementer

当前仓库事实已经很清楚：

- `docs/specs` 与 `docs/plans` 从 `001` 到 `060` 连续且匹配
- 最新 task commit 是 `dbe50d9 feat: add customer demo replan flow`
- 当前分支仍是 `codex/customer-demo-replan-flow-v0`
- `docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/artifacts/benchmark-all-registered-formal-report.json`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`.gitignore`、`qc` 都是当前 worktree 里的非本 task 正式产物

因此，本 task 应作为新的 `061` 执行，而不是继续在 `060` 上做文档或 artifact 收尾。

实现时保持两个边界：

- 正式验证脚本只负责“复现 formal benchmark 结果并落在 `var/` 下”，不负责“发布 submission 文档或发布 docs artifact”
- benchmark 执行逻辑必须复用现有 harness，而不是复制现有 benchmark 实现

如果实现过程中发现必须修改 benchmark suite 定义、public API、frontend、submission 草稿文档，说明 scope 已经偏离本任务，应停止并汇报。
