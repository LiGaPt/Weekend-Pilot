# WeekendPilot Submission Overview

## Task 129 Delivery Boundary

Current formal submission is the `V2 Integrity Edition` offline/local `Mock World` closed loop. The official reviewer path uses `Mock World` for `5173` public demo, formal benchmark suites, canonical evidence aliases, recovery review, and `5174` internal observability. This submission does not connect to real-world write services and does not depend on true MCP integration.

The required review order is `5173 -> 5174`: first show the public customer flow and human confirmation boundary, then switch to the internal reviewer surface for `Benchmark Summary`, `System Integrity Summary`, run audit details, and canonical evidence. `AMap` remains optional API/script-only `read-only preview`; it is not part of the customer UI main chain and not part of formal benchmark scoring.

本次提交的目标不是继续扩功能，而是把现有能力收束成一套可以稳定演示、稳定录制、稳定提交的 `V2 Integrity Edition`。`V1.5 baseline` 保留为已完成基线背景；当前正式口径聚焦 benchmark 完整性、memory governance、observability 与 recovery 可审计性。建议视频时长控制在 `8-10 分钟`，主线展示 `5173` 公开用户流，证据展示放在 `5174` 内部评审页和终端脚本。

真实地图 provider 在当前提交中不是主线。AMap 继续只是 API/script-only 的 `read-only preview`，不进入 customer UI 主链，也不参与正式 benchmark。

建议把视频结构固定为两段主线：

1. `5173` 现场演示关键用户流：
   `happy path`、`clarification`、`replan`、`decline`
2. `5174 + 终端脚本` 补齐能力广度：
   `Benchmark Summary`、`System Integrity Summary`、`internal observability`、`release gate`、`v2 integrity gate`、`Pass@k stability`、`formal verification`、`recovery replay review`、可选 `AMap read-only preview`

当前可口播的 canonical evidence：

- `release_gate_v1`：`15/15 passed`，`overall_score=1.0`
- `coverage_gate_v1_5`：`30/30 passed`，`overall_score=1.0`
- `v2_integrity_gate`：`20/20 passed`，`release_blocked=false`
- `v2_integrity_passk`：`Success@1=1.0`，`Pass@4=1.0`，`Pass^4=1.0`
- `all_registered`：`30/30 passed`，`overall_score=1.0`
- `family_route_failure_v1` recovery review：`passed`，路线失败时安全停止且零写动作

录制前固定运行：

```bash
python scripts/demo_preflight.py
python scripts/show_submission_evidence.py
```

如果要演示 AMap，再额外运行：

```bash
python scripts/demo_amap_preview.py
```

阅读顺序建议：

1. [RECORDING_CHECKLIST.md](./RECORDING_CHECKLIST.md)
2. [DEMO_SCRIPT.md](./DEMO_SCRIPT.md)
3. [FUNCTION_COVERAGE_MAP.md](./FUNCTION_COVERAGE_MAP.md)
4. [EVIDENCE_MAP.md](./EVIDENCE_MAP.md)

提交口径：

- 主链 live 演示的是“规划 -> 澄清/重规划/拒绝 -> 确认边界 -> 执行结果”
- 广度与可靠性不现场重跑 benchmark，而是展示已生成的 canonical latest evidence
- reviewer 侧先看 `Benchmark Summary` 与 `System Integrity Summary`，再按 `run_id` 审计单次运行链路
- AMap 继续是 API/script-only 的只读预览，不进入 customer UI 主链，不参与正式 benchmark
- 不录 IDE，不录服务启动日志，不展示 `.env`、API key、token、secret
