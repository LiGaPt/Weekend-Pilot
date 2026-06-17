# Recording Checklist

这份清单用于正式录屏前逐项核对，避免视频里出现环境等待、错误页面或证据缺失。

本次录制口径聚焦 `V2 Integrity Edition`。`V1.5 baseline` 只作为已完成基线背景保留；当前主线是 benchmark 完整性、memory governance、observability 与 recovery 可审计性。AMap 仍是 API-only read-only preview，不进入 customer UI 主链，也不参与正式 benchmark。

## 服务启动

不要录服务启动日志。正式录制前确认这些进程已经启动：

```powershell
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
npm --prefix frontend run dev
npm --prefix frontend run dev:internal
```

## 录制前

1. 终端切到 repo root。
2. 浏览器标签页顺序固定为：`5173 -> 5174`。
3. 不打开 IDE，不展示 `.env`、API key、token、secret。
4. 先手动预热一遍 `亲子 happy path`，避免第一次请求把等待时间录进去。
5. 运行：

```powershell
python scripts/demo_preflight.py
python scripts/show_submission_evidence.py
```

6. 如果要演示 AMap，再确认：

```powershell
python scripts/demo_amap_preview.py
```

如果脚本提示 `AMAP_MAPS_API_KEY is not configured`，直接跳过 AMap 段，不影响主线录制。

## 窗口布局

- 主画面：浏览器。
- 辅助画面：终端。
- 不录服务启动日志。
- 不现场跑完整 benchmark。

## 公开页检查

- `5173` 可打开。
- 六个 scenario chips 可见：`亲子`、`朋友`、`单人`、`情侣`、`雨天`、`预算`。
- `亲子 happy path` 可到 `awaiting_confirmation`。
- 可展开 `时间线`、`活动与餐饮`、`路线与可执行性`、`确认前动作`。
- `运行信息` 可展开并复制 `Run ID`。
- 点击 `确认当前方案` 后能展示 `执行结果`、`复制安排消息`、`执行时间线`。
- 模糊请求可进入 clarification，并可通过 `提交补充` 回到待确认方案。
- replan 可生成新 `run_id` 和 `v2`。
- decline 可进入拒绝态，并且不触发写动作。

## 内部页检查

- `5174` 可打开。
- `Benchmark Summary` hero 首屏可见。
- `System Integrity Summary` 首屏可见，并能展示 `v2_integrity`、`Pass@k`、`Formal Verification`、`Safe Stop Gate`、`Memory Governance`、`Recovery Replay`、`Evidence Paths`。
- 可粘贴公开 run 的 `run_id` 并点击 `Load Run`。
- `Trace Summary` 可加载。
- `Tool Events` 或 `Action Ledger` 至少一个有可讲解内容。
- `Benchmark Artifacts` 可见。
- `Recovery Visualization` 如果当前 run 没有 recovery，也可以用终端 evidence summary 补齐。

## 证据检查

- `python scripts/show_submission_evidence.py` 输出六个 `[OK]`：
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `v2_integrity_passk`
  - `formal_verification_all_registered`
  - `recovery_review_family_route_failure_v1`
- `release_gate_v1` 当前口径：`15/15 passed`，`overall_score=1.0`。
- `coverage_gate_v1_5` 当前口径：`30/30 passed`，`overall_score=1.0`。
- `v2_integrity_gate` 当前口径：`20/20 passed`，`release_blocked=false`。
- `v2_integrity_passk` 当前口径：`Success@1=1.0`，`Pass@4=1.0`，`Pass^4=1.0`。
- `all_registered` 当前口径：`30/30 passed`，`overall_score=1.0`。
- `safe_stop_gate_v1` 当前口径：`8/8 passed`，`release_blocked=false`。
- recovery review 当前口径：失败路径安全停止、零写动作、replay 与源报告一致。

## 最终验收

- 视频主线展示：规划 -> 澄清 / 重规划 / 拒绝 -> 确认边界 -> 执行结果。
- 视频证据展示：内部 observability -> benchmark evidence -> recovery evidence。
- AMap 缺 key 时不作为失败项。
- 结尾明确说明这是“可执行闭环”，不是普通推荐列表。
