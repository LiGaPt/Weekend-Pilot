# Function Coverage Map

当前功能覆盖表对应 `V1.5 baseline / V2 Integrity candidate`。后续 `V2 Integrity Edition` 聚焦 benchmark 完整性、memory governance、observability 与 recovery 可审计性；AMap 仍是 API-only read-only preview，不进入 customer UI 主链，不参与正式 benchmark。

| 功能 | 视频里如何展示 |
| --- | --- |
| 亲子 happy path | `5173` live：点击 `亲子`，提交、确认、执行、最终安排 |
| 朋友 / 单人 / 情侣 / 雨天 / 预算 场景广度 | `5173` 可见 scenario chips + `coverage_gate_v1_5` / `latest-all_registered-run-report.json` 证明 |
| clarification | `5173` live：模糊输入 -> `awaiting_clarification` -> 补充 -> 回到待确认方案 |
| replan / versioning | `5173` live：follow-up 修改需求 -> 新 `run_id` -> `v1 -> v2` |
| decline / human confirmation boundary | `5173` live：待确认方案点击 `暂不继续`，口播“不会触发写动作” |
| action manifest | `5173` live：展开 `确认前动作` |
| execution result | `5173` live：确认后展示结果卡与执行时间线 |
| AMap read-only preview | 终端 live：`python scripts/demo_amap_preview.py` |
| internal observability | `5174` live：粘贴 `run_id` 后展示 `Trace Summary`、`Tool Events`、`Action Ledger` |
| benchmark release gate | `5174` live：页面顶部 `Benchmark Summary` hero |
| coverage gate | 终端 live：`python scripts/show_submission_evidence.py` 输出 `latest-coverage_gate_v1_5-run-report.json` |
| formal verification | 终端 live：`python scripts/show_submission_evidence.py` 输出 `latest-all_registered-run-report.json` |
| recovery replay review | `5174` 的 `Recovery Visualization` + evidence summary 脚本中的 recovery alias |

判定标准：

- 在主链里 live 演示的，优先用 `5173` 或 `5174`
- 不适合现场等待的，用 canonical latest evidence 补齐
- 不再靠记忆判断是否讲到，而是按这张表逐项核对
