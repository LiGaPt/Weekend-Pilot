# Evidence Map

当前 evidence map 对应 `V1.5 baseline / V2 Integrity candidate`。后续 `V2 Integrity Edition` 的证据重点是 benchmark 完整性、memory governance、observability 与 recovery 可审计性；AMap 只作为 API-only read-only preview，不进入 customer UI 主链，不参与正式 benchmark。

## Canonical Latest Aliases

| Alias | 证明什么 | 当前口径 | 演示方式 |
| --- | --- | --- | --- |
| `var/formal-benchmarks/latest-release_gate_v1-run-report.json` | 当前正式阻塞基线 | `15/15 passed`, `overall_score=1.0` | `5174` Benchmark Summary hero + evidence summary 脚本 |
| `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json` | 多样性 / 覆盖面 | `22/22 passed`, `overall_score=1.0` | evidence summary 脚本 |
| `var/formal-benchmarks/latest-all_registered-run-report.json` | 全量注册 case / formal verification | `22/22 passed`, `overall_score=1.0` | evidence summary 脚本 |
| `var/recovery-reviews/latest-family_route_failure_v1-review.json` | 失败恢复链 | `passed`，路线失败时安全停止且零写动作 | evidence summary 脚本 + `5174` Recovery Visualization |

## 录制原则

- 不在视频里 live 跑完整 benchmark。
- benchmark 相关内容统一用“已经生成好的 canonical latest evidence”展示。
- `5174` 负责展示 reviewer-facing UI 证据。
- `python scripts/show_submission_evidence.py` 负责在终端里把 alias 和意义说清楚。
- AMap 是可选只读预览，不进入 customer UI 主链，也不作为 benchmark 依据。

## Evidence Summary 命令

```powershell
python scripts/show_submission_evidence.py
```

期望看到四个 `[OK]`：

```text
[OK] release_gate_v1
[OK] coverage_gate_v1_5
[OK] formal_verification_all_registered
[OK] recovery_review_family_route_failure_v1
```

## 录制口播建议

“这里我不现场等待 benchmark 执行，而是展示已经生成好的 canonical latest evidence。`release_gate_v1` 是当前正式基线，`15/15 passed`；`coverage_gate_v1_5` 和 `all_registered` 覆盖 `22/22` case，证明场景广度和 formal verification；`recovery_review_family_route_failure_v1` 证明失败恢复链。恢复审查里，路线失败时 workflow 是安全失败，并且零写动作。”
