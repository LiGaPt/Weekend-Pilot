Task 01
Task 01: V2 benchmark suite + taxonomy

Slug: 092-v2-integrity-benchmark-suite-taxonomy-v0
Spec: docs/specs/092-v2-integrity-benchmark-suite-taxonomy-v0.md
Plan: docs/plans/092-v2-integrity-benchmark-suite-taxonomy-v0-plan.md
Branch: codex/092-v2-integrity-benchmark-suite-taxonomy-v0
Commit: feat: add v2 integrity benchmark taxonomy

目标：
新增 additive `v2_integrity` benchmark suite，并定义 V2 taxonomy 字段：
scenario_bucket、level、failure_mode、memory_mode、conversation_mode、stability_required。

范围：
- 不破坏 release_gate_v1
- 不改变已有 suite 顺序
- 优先复用现有 22 个 benchmark case
- taxonomy 要有 fallback 或 derive 规则
Task 02
Task 02: V2 benchmark matrix + integrity gate

Slug: 093-v2-integrity-matrix-gate-v0
Commit: feat: add v2 integrity benchmark gate

目标：
扩展 benchmark matrix，让 v2_integrity suite 能输出系统完整性覆盖结果，并新增 v2_integrity gate。

范围：
- matrix 覆盖 taxonomy 维度
- gate 检查 memory/recovery/continuation/robustness/L4-style 覆盖
- 不替代 release_gate_v1


Task 03
Task 03: Stability harness + Pass@k v0

Slug: 094-stability-harness-passk-v0
Commit: feat: add benchmark stability passk metrics

目标：
支持对指定 suite 重复运行 N 次，输出 Success@1、Pass@4、Pass^4 v0。

范围：
- 先支持 v2_integrity 小规模 suite
- 输出 deterministic report
- 不做大规模昂贵全量矩阵


Task 04
Task 04: Memory decision log + policy summary

Slug: 095-memory-decision-log-v0
Commit: feat: add memory decision audit log

目标：
标准化 memory 使用、忽略、降权、覆盖的决策日志，并写入 run metadata / benchmark report。

字段建议：
memory_id、key、status、decision、reason、influence_level。

Task 05
Task 05: Memory lifecycle v1

Slug: 096-memory-lifecycle-v1
Commit: feat: add memory lifecycle states

目标：
支持 active / expired / disabled / ignored / candidate 这些记忆状态，并保证 workflow 和 repository 行为一致。

范围：
- 后端服务和测试
- 不做完整 UI
done！！

Task 06
Task 06: Sensitive memory + feedback candidate

Slug: 097-sensitive-memory-feedback-candidate-v0
Commit: feat: add sensitive memory minimization

目标：
敏感信息最小化；feedback writer 只生成 candidate memory，不自动生成高置信 active memory。

范围：
- sensitive-like 字段过滤或结构化
- feedback -> candidate memory
- 测试覆盖 secret/token/phone/address-like 输入
done！

Task 07
Task 07: Memory governance suite v2

Slug: 098-memory-governance-suite-v2
Commit: feat: expand memory governance benchmark suite

目标：
扩展 memory governance benchmark 到 5-6 个 case，并让 grader 检查 memory decision 是否正确。

覆盖：
- explicit override
- expired downgrade
- disabled ignored
- candidate not auto-active
- sensitive minimization
done

Task 08
Task 08: Generic recovery replay

Slug: 099-generic-recovery-replay-v0
Commit: feat: generalize recovery replay review

目标：
recovery replay 不再只固定 family_route_failure_v1，支持指定 case id 或 recovery suite。

范围：
- CLI/script 参数
- report schema 兼容
- existing latest recovery alias 不破坏
done！

Task 09
Task 09: Chaos/failure combination cases

Slug: 100-chaos-failure-combination-cases-v0
Commit: feat: add combination failure benchmark cases

目标：
新增组合失败 case 和 safe-stop gate。

建议组合：
- ticket sold out + route unavailable
- queue closed + budget constraint
- table unavailable + replan required

验收：
失败时不错误执行，写动作安全，报告可解释。
done

补：/101-benchmark-coverage-gate-convergence-v0

Task 10
Task 10: System Integrity Summary API

Slug: 102-system-integrity-summary-api-v0
Commit: feat: add system integrity summary api

目标：
新增或扩展 internal API，汇总 benchmark、memory governance、recovery replay、timing、redaction、evidence path。

范围：
- 后端 API/schema/service
- 不做前端 UI
done

Task 11
Task 11: 5174 System Integrity panel

Slug: 103-system-integrity-panel-v0
Commit: feat: add system integrity review panel

目标：
在 5174 internal observability page 展示 System Integrity Summary。

展示：
- v2_integrity status
- Pass@k
- memory governance status
- recovery replay status
- latest evidence paths
done

Task 12
Task 12: Evidence summary + contract guardrail v2

Slug: 104-v2-evidence-contract-guardrail
Commit: feat: add v2 evidence guardrails

目标：
升级 show_submission_evidence.py 和 evidence verifier，覆盖 V2 integrity artifacts，防止 latest alias、schema、suite id 漂移。

范围：
- evidence summary
- contract verifier
- tests
done

Task 13
Task 13: V2 Integrity docs + submission package

Slug: 105-v2-integrity-docs-submission
Commit: docs: document v2 integrity submission flow

目标：
更新 README、design doc、submission docs、demo script，统一 V2 Integrity Edition 口径。

明确：
- 真实地图 provider 降级
- AMap read-only preview
- V2 主打 benchmark / memory / observability / recovery
done

Task 14
Task 14: Final release verification + push

Slug: 106-v2-integrity-release-verification
Commit: chore: refresh v2 integrity release evidence

目标：
最终刷新 evidence，跑 preflight，确认提交包稳定。

范围：
- 运行 release gate / coverage gate / formal verification / recovery review / v2 integrity scripts
- 更新文档中的最终结果
- 不再新增功能
done


Task 15
Task 15: Benchmark test/doc count convergence
Slug: 107-benchmark-test-doc-count-convergence
Commit: test: align benchmark inventory expectations
目标：
修复当前 benchmark case 数量已经扩展到 v2_integrity=18、all_registered=28 后，测试和文档里残留的旧数量断言，先让后端回归测试重新收敛。
范围：  
更新 stale 测试断言：15 -> 18、17 -> 28、25 -> 28
更新相关文档中的旧 case count 和版本口径
核对 README 中 focused test 结果，从旧的 15 passed 改为当前实际结果
不修改 benchmark suite membership
不修改 benchmark 评分逻辑
不新增功能
done



Task 16
Task 16: Stage timing percentile report hardening
Slug: 108-stage-timing-percentile-reporting-v0
Commit: feat: add benchmark stage percentile reporting
目标：
继续路线图 M1，把 benchmark 从“整体通过”推进到“可以按 workflow stage 量化比较”，输出阶段级 p50 / p95 / p99 和 case/suite 汇总。
范围：  
梳理现有 workflow timing 与 benchmark timing 数据结构
在 benchmark report 中稳定输出 stage-level duration summary
给 suite summary 增加阶段级分位数统计
补充测试，确认每个 case 和 suite 都能看到阶段耗时分布
如内部观测 API 已有可消费字段，只做最小展示或 schema 对齐
不改变 workflow 行为
不改变 benchmark 评分阈值
不做 UI 大改版
done



Task 17
Task 17: Memory user control baseline
Slug: 109-memory-user-control-baseline-v0
Commit: feat: add memory user control baseline
目标：
补齐 memory governance 的最小用户控制闭环，让长期记忆不只是 read-only policy，而是具备可审计的禁用/删除基础能力。
范围：  
增加 memory item 的用户可控状态变更服务
支持最小可验证操作：list、disable 或 delete/suppress
所有变更写入可审计 metadata 或 repository 层状态
确认 disabled memory 不再参与 query shaping
补充 repository/service/unit tests
不做前端记忆管理 UI
不做复杂权限系统
不引入向量库或 embedding
不扩大 memory key 支持范围
done



Task 18
Task 18: Recovery chaos harness next slice
Slug: 110-recovery-chaos-harness-next-slice-v0
Commit: feat: expand recovery chaos harness coverage
目标：
在现有 recovery replay 和 safe-stop gate 基础上，继续补齐组合失败覆盖，让失败恢复能力更可审计、更接近路线图 M5。
范围：  
选择 1 到 2 个新的组合失败 case，保持小任务边界
明确每个 case 的 failure chain、expected recovery action、terminal status
确认失败路径不会越过 human confirmation
确认失败路径不会产生 write-side effects
扩展 recovery-focused 或 safe-stop 相关测试
更新 recovery review 文档说明
不重写 recovery policy
不新增真实地图 provider 依赖
不把 AMap 纳入正式 benchmark 主链
done

Task 111
Task 111: Session and conversation model
Slug: 111-session-conversation-model-v0
Commit: feat: add session and conversation persistence  
目标：
补齐多轮会话的持久化边界。  
范围：  
增加 session / conversation / turn 数据模型  
关联 run_id、trace_id、state snapshot
done


Task 112
Task 112: Multi-turn clarify and replan loop
Slug: 112-multi-turn-clarify-replan-loop-v0
Commit: feat: support multi-turn clarification and replanning  
目标：
让用户中途改需求后可以稳定重算方案。  
范围：  
支持澄清轮和 bounded replan  
保持确认边界不被绕过
done


Task 113
Task 113: Plan versioning and action manifest
Slug: 113-plan-versioning-action-manifest-v0
Commit: feat: version plans and emit action manifests  
目标：
把方案从“一次性输出”变成可追踪的版本链。  
范围：  
增加 v1 / v2 / v3 方案版本  
在执行前生成 action manifest
done


Task 114
Task 114: Internal observability run summary
Slug: 114-internal-observability-run-summary-v0
Commit: feat: add run summary observability  
目标：
让内部观测能直接看到一次 run 的关键事实。  
范围：  
输出 stage timing、tool events、recovery path  
提供结构化 run summary
done


Task 115
Task 115: Customer and observability UI split
Slug: 115-customer-observability-ui-split-v0
Commit: feat: separate customer and observability web surfaces  
目标：
把给用户看的页面和给内部看的页面分开。  
范围：  
客户端只显示结果和确认信息  
观测端显示 trace、ledger、timeline
done


Task 116
Task 116: Mock world scenario taxonomy expansion
Slug: 116-mock-world-scenario-taxonomy-v0
Commit: feat: expand mock world scenario taxonomy  
目标：
把场景覆盖从家人主线扩到更完整的 Mock World。  
范围：  
增加朋友、单人轻度周末、老人同行、雨天备选、预算受限等场景  
补 fixture 和测试用例
done


Task 117
Task 117: Benchmark case matrix generation
Slug: 117-benchmark-case-matrix-generation-v0
Commit: feat: generate benchmark cases from taxonomy matrix  
目标：
把场景、约束、失败注入组合成系统化 case matrix。  
范围：  
增加 case 生成策略  
保证覆盖面和可重复性
done


Task 118
Task 118: Recovery replay visualization link
Slug: 118-recovery-replay-visualization-v0
Commit: feat: connect recovery replay to visualization  
目标：
让失败恢复路径能被直接回放和检查。  
范围：  
串起 replay artifact 和 run visualization  
方便定位 recovery 分支
done


Task 119
Task 119: Memory CRUD governance
Slug: 119-memory-crud-governance-v0
Commit: feat: add memory CRUD and lifecycle controls  
目标：
把长期记忆从“只能读”补成可治理。  
范围：  
增加 memory 的增删改查和生命周期状态  
保留来源、置信度、过期信息
done


Task 120
Task 120: Memory audit and minimization
Slug: 120-memory-audit-minimization-v0
Commit: feat: tighten memory audit and minimization  
目标：
让记忆更可审计、更少敏感信息。  
范围：  
增加审计记录和最小化存储规则  
补 expired / low-confidence downgrade 逻辑
done



Task 121
Task 121: Execution safety and ledger hardening
Slug: 121-execution-safety-ledger-hardening-v0
Commit: feat: harden execution safety and action ledger  
目标：
把执行层的幂等性和安全边界补扎实。  
范围：  
强化 Action Ledger 和 idempotency  
覆盖重复确认、部分成功、失败回滚语义
//done


Task 122
Task 122: Recovery chaos harness expansion
Slug: 122-recovery-chaos-harness-expansion-v0
Commit: feat: expand recovery chaos harness coverage  
目标：
继续补组合失败覆盖，让恢复路径更可信。  
范围：  
新增 1-2 个组合 failure chain  
明确 recovery action 和 terminal status
//done



Task 123
Task 123: Customer demo flow stabilization
Slug: 123-customer-demo-flow-stabilization-v0
Commit: feat: stabilize customer demo flow  
目标：
把主要演示路径收成稳定的 Mock World V2 体验。  
范围：  
收紧 happy path 和 fallback path  
清理用户可见状态和结果展示



Task 124
Task 124: Review evidence entrypoint convergence
Slug: 124-review-evidence-entrypoint-convergence-v0
Commit: chore: converge review evidence entrypoint  
目标：
把 reviewer evidence 入口、verifier 规则、focused tests 和 Task 124 spec / plan 文档收敛到同一套 canonical evidence contract，避免实现已经完成但任务文档缺失或编号漂移。  
范围：
保存并跟踪 Task 124 spec 和 implementation plan。
确认 Task 124 表述为 reviewer evidence entrypoint convergence，而不是最终 Mock World V2 verification。
保留六个 canonical evidence entries：release gate、coverage gate、v2 integrity gate、pass@k、formal verification、recovery review。
运行 evidence verifier 和 focused tests，确认 reviewer-facing evidence 入口可稳定复用。
不启动 Task 125，不刷新完整 Mock World V2 final delivery evidence。
done




Task 125
Task 125: Mock World scenario coverage closure
Slug: 125-mock-world-scenario-coverage-closure-v0
Commit: test: lock mock world scenario coverage closure  
目标：
完成 Mock World 多场景覆盖的最终收口，证明当前系统不只依赖亲子主链，而是可以在多个本地模拟场景中稳定规划、确认、执行和评测。  
范围：
核对 family_afternoon、friends_gathering、solo_afternoon、couple_afternoon、rainy_day_fallback、budget_lite、elder_afternoon 等 profile。
确认所有公开 Mock World profile 都能加载并进入可评审规划状态。
核对 benchmark case、suite membership、taxonomy summary、case matrix 是否一致。
补充或收口 focused regression，防止 profile、suite、文档数量再次漂移。
更新仍然暗示只支持亲子场景的文档表述。
done





Task 126
Task 126: Conversation and plan versioning closure
Slug: 126-conversation-plan-versioning-closure-v0
Commit: test: lock conversation and plan versioning closure  
目标：
完成多轮对话和方案版本能力的收口，证明系统不是一次性 prompt 输出，而是支持澄清、改需求、重新规划、方案版本追踪和确认前动作预览的会话式规划系统。  
范围：
验证 clarification flow：缺少关键信息时进入澄清，用户补充后继续生成方案。
验证 replan flow：用户修改约束后生成新 plan version。
验证 selected plan index：用户选择不同方案后，replan 和 confirm 仍绑定正确方案。
验证 action manifest：确认前展示将要执行的动作，确认前不产生写动作。
补充一条完整多轮路径的 integration test 或 E2E test。  
done




Task 127
Task 127: Recovery and safe-stop evidence closure
Slug: 127-recovery-safe-stop-evidence-closure-v0
Commit: test: consolidate recovery safe-stop evidence  
目标：
完成恢复链路和安全停机能力的收口，证明系统在路线不可用、票务售罄、餐厅不可用、组合失败等情况下，不会错误执行写动作，而是可解释、可回放、可评测地安全停止。  
范围：
刷新 recovery replay review artifact。
核对 route unavailable、ticket sold out、dining unavailable、combined failure、safe-stop gate 等失败场景。
确认失败路径包含 failure reason、recovery attempt、terminal status、zero write action guarantee。
确认内部观测页可以展示 recovery visualization，并链接到最新 alias、report 和 artifact。
补充 focused test，验证 safe-stop summary 不依赖过期 artifact 或手工维护结果。  
done



Task 128
Task 128: Memory governance final closure
Slug: 128-memory-governance-final-closure-v0
Commit: test: close memory governance delivery surface  
目标：
完成记忆治理能力的最终收口，证明记忆不是简单存储，而是具备用户可控、生命周期治理、敏感信息最小化和审计能力。  
范围：
核对 explicit user input 优先、advisory memory、expired memory downgrade、sensitive memory minimization 等治理规则。
验证 memory CRUD、用户禁用、编辑、删除和 lifecycle audit。
补充最终 regression surface，覆盖 memory 创建、查询、更新、删除、禁用和敏感信息不进入 active planning。
整理 memory governance evidence，确保其进入最终交付说明。
更新 runbook，说明当前 memory 是本地治理闭环，不依赖真实用户画像或外部账户系统。  
done



Task 129
Task 129: Offline delivery boundary and submission polish
Slug: 129-offline-delivery-boundary-submission-polish-v0
Commit: docs: polish offline delivery boundary and submission evidence  
目标：
完成最终交付口径和评审材料收口，明确当前版本不接真实世界、不接真正 MCP，正式主链基于 Mock World 本地闭环完成。  
范围：
更新 README 顶部交付口径，明确 Mock World 是当前正式主链。
更新 WEB_DEMO_README，整理 3 分钟评审路径和 5173 -> 5174 演示顺序。
更新 submission docs，包括 function coverage map、evidence map、demo script、recording checklist。
清理或纳入未跟踪交付文件，避免正式评审时仓库状态不干净。
核对所有文档中的 task 编号、版本名、evidence path 和实际 artifact 一致。
done
