# WeekendPilot Submission Overview

本次初步交付的目标不是继续扩功能，而是把现有能力收束成一套可以稳定演示、稳定录制、稳定提交的版本。建议视频时长控制在 `8-10 分钟`，主线展示 `5173` 公开用户流，证据展示放在 `5174` 内部评审页和终端脚本。

当前提交口径固定为 `V1.5 baseline / V2 Integrity candidate`。后续 `V2 Integrity Edition` 的重点是 benchmark 完整性、memory governance、observability 与 recovery 可审计性；AMap 继续只是 API/script-only 的 read-only preview，不进入 customer UI 主链，也不参与正式 benchmark。

建议你把视频结构固定为两段主线：

1. `5173` 现场演示关键用户流：
   `happy path`、`clarification`、`replan`、`decline`
2. `5174 + 终端脚本` 补齐能力广度：
   `AMap read-only preview`、`internal observability`、`release gate`、`coverage gate`、`formal verification`、`recovery replay review`

当前可口播的 evidence 结果：

- `release_gate_v1`：`15/15 passed`，`overall_score=1.0`
- `coverage_gate_v1_5`：`22/22 passed`，`overall_score=1.0`
- `all_registered`：`22/22 passed`，`overall_score=1.0`
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
- 广度与可靠性不现场重跑 benchmark，而是展示已生成 evidence
- AMap 继续是 API/script-only 的只读预览，不进入 customer UI 主链，不参与正式 benchmark
- 不录 IDE，不录服务启动日志，不展示 `.env`、API key、token、secret
