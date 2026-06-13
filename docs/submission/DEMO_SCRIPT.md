# WeekendPilot 比赛演示录制脚本

这份脚本按 `8-10 分钟` 设计。录制时主线放在 `5173` 公开用户流，证据放在 `5174` 内部评审页和终端脚本。不要现场跑完整 benchmark，用已生成的 canonical evidence 展示稳定性。

版本口径固定为 `V1.5 baseline / V2 Integrity candidate`。口播时可以说明后续 `V2 Integrity Edition` 不把真实地图深度集成作为主线，而是继续增强 benchmark 完整性、memory governance、observability 与 recovery 可审计性；AMap 仍是 API-only read-only preview，不进入 customer UI 主链，不参与正式 benchmark。

## 演示目标

这次视频要证明 WeekendPilot 已经不只是“地点推荐”，而是一个本地生活规划与执行闭环：

- 自然语言输入可以生成活动、餐厅、路线和可执行性完整方案。
- 确认前只运行读工具，确认后才执行写动作。
- 支持 clarification、follow-up replan、decline。
- 内部可审计：trace、tool events、action ledger、benchmark artifacts、recovery visualization。
- 当前 benchmark evidence：`release_gate_v1 15/15 passed`，`coverage_gate_v1_5 22/22 passed`，`all_registered 22/22 passed`，`overall_score=1.0`。
- AMap 是 `API-only read-only preview`，有 key 就演示，没有 key 就跳过；它不参与正式 benchmark。

## 演示入口与边界

- 公开用户页：`http://127.0.0.1:5173/`
- 内部评审页：`http://127.0.0.1:5174/`
- API 健康检查：`http://127.0.0.1:8000/health`
- 主链默认使用 `Mock World`。
- 不录 IDE，不录服务启动日志，不展示 `.env`、API key、token、secret。
- AMap 不进入公开用户页主链，只作为可选终端脚本演示。

## 录制前准备

先启动服务，但不要把启动过程录进视频：

```powershell
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
npm --prefix frontend run dev:internal
```

正式录制前运行：

```powershell
python scripts/demo_preflight.py
python scripts/show_submission_evidence.py
```

如果你有 AMap key，再预检查：

```powershell
python scripts/demo_amap_preview.py
```

录制前把浏览器标签页顺序固定为：`5173 -> 5174`。终端停在项目根目录。正式开录前先手动跑一遍 `亲子 happy path` 预热，避免把第一次请求等待时间录进去。

## 分镜脚本

### 0:00-0:35 开场

口播：

“WeekendPilot 是一个面向周末本地生活的短时规划与执行 Agent。它不是只返回地点推荐，而是把用户一句话需求变成可执行安排：理解需求、搜索候选、检查可用性、生成方案、等待用户确认，然后再执行订座、排队、购票、点单或发送消息等动作。今天我会展示公开用户流、人工确认边界、重规划和澄清能力，以及内部 benchmark 和 recovery 证据。”

### 0:35-2:40 公开 happy path

操作：

1. 打开 `5173`。
2. 点击 `亲子` chip。
3. 点击 `开始规划`。
4. 等待流式进度和推荐方案出现。
5. 展开 `时间线`、`活动与餐厅`、`路线与可执行性`、`确认前动作`。
6. 展开 `运行信息`，点击 `复制 Run ID`。
7. 点击 `确认当前方案`。
8. 展示 `执行结果`、`复制安排消息`、`执行时间线`。

口播：

“这里我用亲子场景发起规划。页面先展示流式进度，再进入待确认方案。方案不是一句文本，而是包含时间线、活动、餐厅、路线、可执行性和确认前动作。这里的关键边界是：确认前系统只做读工具，比如搜索、可用性、路线和桌位检查；不会执行任何写动作。现在我展开运行信息，复制这个 `run_id`，后面会拿到内部评审页审计。接着我确认当前方案。确认后才进入执行链路，并生成最终安排消息和执行时间线。”

### 2:40-4:00 Clarification

操作：

1. 刷新 `5173`，让画面干净。
2. 输入：`周末想出去玩一下，帮我安排。`
3. 点击 `开始规划`。
4. 等到 `还需要补充一点信息`。
5. 输入：`今天下午一个人出门玩几个小时，别太远，想轻松一点。`
6. 点击 `提交补充`。
7. 展示回到待确认方案，展开 `运行信息` 看版本仍为 `v1`。

口播：

“现在我演示模糊请求。系统不会硬猜，而是进入 clarification，明确告诉用户缺哪些信息。补充后它继续同一条对话，生成可确认方案。这里版本语义也保持清楚：澄清只是补足信息，不是一次新的重规划版本。”

### 4:00-5:25 Replan

操作：

1. 保持当前待确认方案，或刷新后重新用 `单人` / `亲子` 跑到待确认。
2. 在底部输入：`保持附近，但这次改成一个人，尽量少走路。`
3. 点击 `继续调整`。
4. 展开 `运行信息`，展示新 `run_id` 和 `v2`。

口播：

“接下来是 follow-up replan。用户可以基于当前方案追加新限制。这里系统生成新的 `run_id`，版本从 `v1` 到 `v2`，说明它不是覆盖旧结果，而是一次可追踪的继续规划。”

### 5:25-6:10 Decline

操作：

1. 刷新 `5173`。
2. 点击 `预算` chip。
3. 点击 `开始规划`。
4. 等待待确认方案。
5. 点击 `暂不继续`。

口播：

“如果用户不想继续，可以拒绝方案。拒绝会停在人工确认边界，不会触发订座、排队、购票、点单或消息发送。这是执行安全的核心。”

### 6:10-7:45 Internal Review

操作：

1. 切到 `5174`。
2. 先展示顶部 `Benchmark Summary`。
3. 在 `Load Run` 粘贴刚才 happy path 的 `run_id`。
4. 点击 `Load Run`。
5. 展示 `Trace Summary`、`Tool Events`、`Action Ledger`、`Benchmark Artifacts`。
6. 如果有 recovery run，可展示 `Recovery Visualization`；没有就只说明终端 evidence 会补齐。

口播：

“现在切到内部评审页。顶部 Benchmark Summary 展示当前 release gate 的 canonical evidence。然后我加载刚才公开页的 `run_id`，这里能看到运行身份、trace、workflow timing、tool events 和 action ledger。公开页对用户隐藏内部细节，但内部页可以审计完整链路。”

### 7:45-8:45 Evidence Summary

操作：切到终端，运行：

```powershell
python scripts/show_submission_evidence.py
```

口播：

“这里我不现场等待完整 benchmark 执行，而是展示已经生成好的 canonical latest evidence。`release_gate_v1` 是当前正式基线，`15/15 passed`；`coverage_gate_v1_5` 和 `all_registered` 覆盖 `22/22` case，证明场景广度和 formal verification；`recovery_review_family_route_failure_v1` 证明失败恢复链。恢复审查里，路线失败时 workflow 是安全失败，并且零写动作。”

### 可选 8:45-9:30 AMap read-only preview

如果 `demo_amap_preview.py` 可用，录：

```powershell
python scripts/demo_amap_preview.py
```

口播：

“AMap 当前不是公开用户页主链，而是 API-only 的只读预览。脚本会发起 `read_profile=amap` 的 run，然后尝试 confirm。预期 confirm 返回 `409`，说明真实地图读取能力可以用于规划预览，但不会越过确认后的写动作边界。”

如果没有 key，跳过这段，别录 `.env`。

### 9:30-10:00 收尾

口播：

“总结一下，WeekendPilot 当前已经具备三层能力：第一，能完成本地生活规划、确认和执行；第二，有明确的人类确认边界、拒绝路径和 AMap 只读约束；第三，有 observability、benchmark 和 recovery evidence 证明系统稳定、可追踪、可审计。这个 demo 展示的是一个可执行闭环，而不是普通推荐列表。”

## 录制验收

- `demo_preflight.py` 至少通过 PostgreSQL、Redis、Alembic、API、`5173`、`5174` 和 Evidence Aliases。
- 公开页至少录到：`happy path`、`确认当前方案`、`执行结果`、`clarification`、`replan v2`、`decline`。
- 内部页至少录到：`Benchmark Summary`、`Trace Summary`、`Tool Events` 或 `Action Ledger`、`Benchmark Artifacts`。
- 终端 evidence 至少显示四个 `[OK]`。
- 如果 AMap key 缺失，跳过 AMap，不影响主视频。

## 假设

- 视频目标时长按 `8-10 分钟` 设计。
- 主评审口径是 `Mock World` 稳定复现，AMap 只是可选只读预览。
- 不现场重跑耗时 benchmark，只展示当前 canonical latest evidence。
- 录制时按现有功能执行，不需要临时修改业务代码。
