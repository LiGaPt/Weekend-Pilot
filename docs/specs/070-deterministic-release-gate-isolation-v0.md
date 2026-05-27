# Spec: 070 Deterministic Release Gate Isolation v0

## 1. Goal

WeekendPilot 已经有正式的 blocking benchmark release gate，也已经有可选的 LLM-backed bounded agents preview path。但这两条能力目前没有被明确隔离：`python scripts/run_benchmark_release_gate.py` 通过 `BenchmarkHarness` 进入 workflow 时，没有显式注入固定 runtime settings，仍会沿着 `get_settings()` 读取本地 `.env` / process env。这样一来，只要本地打开 `LLM_ENABLED=true`，blocking gate 就可能悄悄切到 LLM-backed adapters，而不是纯 deterministic path。

Task 070 要把这个风险收口掉。完成后，`release_gate_v1` 必须始终以 deterministic bounded agents 运行，不继承本地 LLM preview 配置，也不把 LangSmith preview settings 视为 gate runtime 的一部分。LLM-backed agents 继续保留为显式 preview 能力，但不参与 V1.5 blocking benchmark gate。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 把 WeekendPilot 定义为 benchmark-driven、deterministic-where-possible、observable-by-default 的系统；`docs/NEXT_PHASE_ROADMAP.md` 也明确当前阶段默认优先 `M1. 评测与观测基础设施`，先保证评测与观测基座可信，再继续扩展能力。

仓库当前的相关前置已经具备：

- Task `031` 已引入可选 LLM-backed bounded agents，通过显式 workflow settings injection at the workflow dependency layer.
- Task `065` 已把 `release_gate_v1` 变成正式 blocking gate。
- Task `069` 已修复 Playwright E2E 的 rate-limit 污染问题，最新 task 链路与 commit 已收口到 `069`。
- `WeekendPilotWorkflowDependencies` 已经支持 `settings` 和 `llm_client` 注入，但 `BenchmarkHarness` 与 `DemoWorkflowService` 还没有把这条显式注入链路完整用起来。

因此，本任务对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M1. 评测与观测基础设施`，但它不是新增能力，而是对现有 blocking gate 的 determinism 进行收敛修复。优先级高于继续做新 milestone feature，因为它影响当前 release evidence 的可信度。

## 3. Requirements

### A. Thread explicit workflow settings through benchmark paths

- `BenchmarkHarness` must accept optional explicit workflow settings and optional workflow LLM client injection.
- The legacy benchmark case path must pass those explicit settings into `WeekendPilotWorkflowDependencies`.
- The continuation benchmark case path must pass the same explicit settings into `DemoWorkflowService`.
- `DemoWorkflowService` must accept optional explicit workflow settings and optional workflow LLM client injection.
- `DemoWorkflowService.start_run(...)`, `clarify_run(...)`, and `replan_run(...)` must pass those explicit settings into `WeekendPilotWorkflowDependencies`.
- If explicit settings are omitted, existing non-gate behavior must remain unchanged.
- No public demo API request or response schema may change in this task.

### B. Force deterministic settings in the release gate runner

- `run_benchmark_release_gate(...)` must construct one explicit settings object for workflow execution instead of relying on ambient `get_settings()` lookup inside the workflow nodes.
- That release-gate settings object must force all of the following values regardless of local `.env` or process env:
  - `llm_enabled = false`
  - `llm_api_key = null`
  - `llm_base_url = null`
  - `llm_model_id = null`
  - `langsmith_tracing = false`
  - `langchain_tracing_v2 = false`
  - `langsmith_api_key = null`
  - `langsmith_endpoint = null`
- The release-gate settings object may preserve unrelated infrastructure values such as database URL, Redis URL, app name, app env, and local trace buffer path from the current runtime settings.
- `run_benchmark_release_gate(...)` must pass that explicit deterministic settings object into `BenchmarkHarness`.
- The implementation must not rely on mutating process env, unsetting env vars globally, or clearing the global settings cache as the primary isolation mechanism.

### C. Keep the blocking gate deterministic even under preview env

- When the process environment contains a complete fake `LLM_*` configuration, `release_gate_v1` must still run only deterministic agent adapters.
- For all persisted run rows created by a `release_gate_v1` execution, agent metadata must not contain:
  - `adapter_version = "llm_discovery_v0"`
  - `adapter_version = "llm_dining_v0"`
  - `adapter_version = "llm_itinerary_planner_v0"`
- The blocking gate must continue to use the existing deterministic Supervisor and Validator/Recovery adapters.
- Existing release-gate thresholds, suite membership, matrix-summary checks, artifact paths, and latest-alias behavior from Task `065` must remain unchanged.
- LLM-backed agents must remain available for explicit preview or direct workflow testing outside the blocking release gate.

### D. Keep LangSmith out of the gate contract

- This task must not add new LangSmith network posting to the benchmark or release-gate path.
- The injected release-gate settings object must explicitly disable LangSmith-related flags and credentials so that future settings-aware recorder wiring cannot silently change blocking gate behavior.
- Existing local JSONL trace writing and persisted run-summary behavior must remain unchanged.

### E. Update documentation

- Update the `README.md` benchmark release gate section to state that:
  - `python scripts/run_benchmark_release_gate.py` always uses deterministic bounded agents
  - local `LLM_*` preview settings are ignored by the blocking gate
  - local LangSmith preview settings are ignored by the blocking gate
  - LLM-backed bounded agents remain optional preview behavior and are not part of the V1.5 blocking gate contract

### F. Add regression coverage

- Add unit tests for explicit settings propagation through the benchmark paths.
- Add unit tests that capture the deterministic settings object passed by `run_benchmark_release_gate(...)`.
- Add an integration test that sets fake complete `LLM_*` env, monkeypatches the OpenAI-compatible client, runs the release gate, and proves the fake client is not used.
- Existing workflow LLM preview integration tests must keep passing without behavioral change.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not change `release_gate_v1` case membership, pass thresholds, matrix-summary rules, artifact filenames, or latest-alias semantics.
- Do not change `all_registered` suite membership or `python scripts/run_formal_verification.py` scope in this task.
- Do not change LLM adapter prompt logic, output schema, or fallback policy.
- Do not add new LangSmith runtime plumbing, new observability API routes, or new frontend surfaces.
- Do not change public demo API request/response shapes.
- Do not modify unrelated local files such as `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, `docs/artifacts/`, or `qc`.

## 5. Interfaces and Contracts

### Inputs

- `python scripts/run_benchmark_release_gate.py`
- `run_benchmark_release_gate(output_root=None, start_services=True, ...)`
- `BenchmarkHarness(..., workflow_settings=None, workflow_llm_client=None)`
- `DemoWorkflowService(..., workflow_settings=None, workflow_llm_client=None)`
- Local environment variables:
  - `LLM_ENABLED`
  - `LLM_API_KEY`
  - `LLM_BASE_URL`
  - `LLM_MODEL_ID`
  - `LANGSMITH_TRACING`
  - `LANGSMITH_API_KEY`
  - `LANGSMITH_ENDPOINT`

### Outputs

- The blocking gate still writes:
  - `suite-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- The blocking gate now also has an explicit internal runtime contract:
  - deterministic workflow settings are injected for all gate-triggered workflow executions
- Persisted run metadata for gate-created runs continues to include sanitized `agents` metadata, but those gate runs must use deterministic adapter versions only

### Schemas

Example deterministic gate settings contract:

```json
{
  "release_gate_settings": {
    "llm_enabled": false,
    "llm_api_key": null,
    "llm_base_url": null,
    "llm_model_id": null,
    "langsmith_tracing": false,
    "langchain_tracing_v2": false,
    "langsmith_api_key": null,
    "langsmith_endpoint": null
  }
}
```

Example persisted agent metadata excerpt for a gate-created run:

```json
{
  "role": "discovery",
  "adapter_version": "deterministic_discovery_v1",
  "output_json": {
    "candidate_count": 3
  }
}
```

## 6. Observability

This task reuses the existing local JSONL trace buffer, persisted run metadata, and benchmark report pipeline.

Requirements:

- No new observability API route is added.
- No new benchmark artifact file type is added.
- Gate-created runs must continue to persist sanitized `metadata_json["agents"]`, `metadata_json["workflow"]`, and `metadata_json["observability"]` as they do now.
- The blocking gate must not depend on LangSmith posting.
- The blocking gate must not persist raw prompts, provider responses, API keys, tokens, authorization headers, debug traces, `tool_event_id`, or `action_id`.
- For this task, LangSmith isolation is enforced at the settings-contract layer. Do not widen scope into new recorder wiring.

## 7. Failure Handling

- If explicit deterministic settings are not threaded through both the legacy benchmark path and the continuation benchmark path, the implementation is incomplete.
- If local `LLM_*` env is set, the blocking gate must ignore it rather than fail or silently switch to preview adapters.
- If the release gate still emits any `llm_*` adapter version in persisted agent metadata, the implementation must be treated as a contract failure.
- If future code later wires settings-aware LangSmith posting into the benchmark path, the deterministic release-gate settings from this task must still keep that behavior disabled.
- Existing bootstrap, readiness timeout, Alembic, suite-failure, latest-alias, and artifact-preservation behavior from Task `065` must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/070-deterministic-release-gate-isolation-v0.md` exists and matches this task.
- [ ] `docs/plans/070-deterministic-release-gate-isolation-v0-plan.md` exists and matches this task.
- [ ] `docs/specs/` and `docs/plans/` remain continuous and matched through `070`.
- [ ] `BenchmarkHarness` accepts optional explicit workflow settings and optional workflow LLM client injection.
- [ ] `DemoWorkflowService` accepts optional explicit workflow settings and optional workflow LLM client injection.
- [ ] The legacy benchmark path passes explicit settings into `WeekendPilotWorkflowDependencies`.
- [ ] The continuation benchmark path passes the same explicit settings into `DemoWorkflowService`, and that service passes them into `WeekendPilotWorkflowDependencies`.
- [ ] `run_benchmark_release_gate(...)` constructs and passes a deterministic settings object that forces LLM and LangSmith preview settings off.
- [ ] The release gate implementation does not depend on process-wide env mutation or settings-cache clearing as its main isolation mechanism.
- [ ] Under complete fake `LLM_*` env, `python scripts/run_benchmark_release_gate.py` still finishes with deterministic adapter versions only.
- [ ] No gate-created run persists `llm_discovery_v0`, `llm_dining_v0`, or `llm_itinerary_planner_v0` as an executed adapter version.
- [ ] Existing `release_gate_v1` thresholds, suite membership, and artifact contracts remain unchanged.
- [ ] Existing direct workflow LLM preview tests still pass.
- [ ] `README.md` documents that the blocking gate ignores local LLM/LangSmith preview settings.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except for pre-existing unrelated local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_release_gate.py tests/integration/test_workflow_llm_agents_gateway.py -q
python scripts/run_benchmark_release_gate.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
fix: isolate release gate runtime settings
```

## 11. Notes for the Implementer

Keep this task narrow and gate-focused.

Important implementation cautions:

- `release_gate_v1` contains continuation cases, so deterministic settings must flow through both `BenchmarkHarness` and `DemoWorkflowService`.
- `WeekendPilotWorkflowDependencies` already supports `settings` and `llm_client`; prefer threading that existing contract instead of inventing a second global switch.
- Do not solve this by mutating process env, unsetting preview vars globally, or clearing `get_settings()` cache as the main mechanism.
- Current benchmark/runtime code does not actively instantiate `LangSmithRecorder`; keep LangSmith scope at the settings-contract boundary and do not expand into new runtime observability features.
- Stop and report back if isolating the release gate would require changing benchmark suite semantics, release thresholds, or public demo API contracts.
