# Spec: 031 LLM-Backed Bounded Agents v0

## 1. Goal

Add the first LLM-backed implementation path for selected bounded agents while preserving WeekendPilot's deterministic default behavior.

Task 031 should replace the internal implementation of Discovery, Dining, and Itinerary Planner with optional LLM-backed adapters behind the existing bounded-agent contracts. These adapters must remain typed, policy-checked, observable, and safe to fallback to deterministic behavior. The default local and test path must continue to run without live LLM credentials.

After this task, reviewers should be able to enable LLM-backed bounded agents locally with generic OpenAI-compatible environment variables, inspect sanitized model usage and fallback metadata, and still rely on deterministic recovery, confirmation, execution, benchmark, and replay behavior.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a centralized bounded multi-agent system with no more than five LLM agents, deterministic routing/execution where possible, and observable agent calls, tool calls, token usage, latency, and recovery decisions.

The current repository already has:

- A bounded-agent contract layer from Task 020.
- Deterministic adapters for Supervisor, Discovery, Dining, Itinerary Planner, and Validator/Recovery.
- LangGraph workflow wiring that stores sanitized agent results in workflow state and `agent_runs.metadata_json["agents"]`.
- Local JSONL observability and optional LangSmith summary recording.
- LocalLife-Bench harness, failure injection, and replay infrastructure.

Task 031 should make only the semantically useful bounded agents LLM-backed in v0. Supervisor and Validator/Recovery must stay deterministic. Deterministic routing, recovery, confirmation, execution, action ledger writes, benchmark grading, and replay must remain unchanged.

## 3. Requirements

- Add generic LLM configuration using `LLM_ENABLED`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_ID`, and `LLM_TIMEOUT`.
- Do not require `OPENAI_API_KEY` for the new LLM-backed agent path.
- Support OpenAI-compatible `/chat/completions` providers, including DashScope compatible mode at `https://dashscope.aliyuncs.com/compatible-mode/v1`.
- Keep `LLM_ENABLED=false` as the default behavior.
- When LLM is disabled, workflow behavior and adapter versions must remain deterministic.
- When LLM is enabled, only these roles may use LLM-backed adapters:
  - `discovery`
  - `dining`
  - `itinerary_planner`
- Supervisor must remain deterministic in Task 031.
- Validator/Recovery must remain deterministic in Task 031.
- LLM-backed adapters must keep the existing public method signatures and return the existing typed outputs.
- LLM-backed adapters must not call Tool Gateway, raw Mock World providers, raw AMap providers, or write tools.
- LLM-backed adapters must validate all tool-name references through the existing bounded-agent policy.
- LLM-backed Discovery and Dining outputs must reference only candidate IDs that already exist in the current workflow inputs.
- LLM-backed Itinerary Planner must only select or reorder deterministic draft IDs; it must not create new candidates, timelines, proposed actions, route data, write-tool payloads, or durable state.
- Deterministic fallback is mandatory for:
  - LLM disabled
  - missing or incomplete LLM config
  - timeout
  - provider HTTP error
  - malformed provider response
  - malformed assistant JSON
  - schema mismatch
  - policy mismatch
  - invalid candidate IDs
  - invalid draft IDs
  - no deterministic drafts
- Fallback must keep the workflow runnable and must not raise into the user workflow unless an existing deterministic path would have raised.
- LLM usage metadata must be normalized to safe field names:
  - `input_count`
  - `output_count`
  - `total_count`
- Raw provider usage keys such as `prompt_tokens`, `completion_tokens`, and `total_tokens` must not be persisted in agent metadata, local trace buffers, LangSmith payloads, or benchmark reports.
- Persisted LLM metadata must include only safe observability fields:
  - provider kind
  - model ID
  - base URL host
  - latency in milliseconds
  - normalized usage counts
  - status
  - fallback reason when fallback occurs
  - safe error type when applicable
- Do not persist raw prompts, raw provider responses, raw provider headers, raw usage details, API keys, authorization headers, tokens, secrets, `tool_event_id`, `action_id`, `debug_trace`, or traceback text.
- Update local observability summary generation so latest sanitized agent metadata is included in local JSONL trace summaries.
- Add unit tests for LLM client behavior, usage normalization, adapter selection, fallback behavior, policy validation, ID validation, and sanitization.
- Add integration tests that use a fake injected LLM client; default tests must not call live LLM providers.
- Existing bounded-agent, workflow, observability, benchmark harness, and benchmark replay tests must keep passing.
- Update README with disabled-by-default LLM-backed bounded-agent setup and verification commands.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not implement AMap MCP integration.
- Do not call MCP tools from agents.
- Do not make Supervisor LLM-backed.
- Do not make Validator/Recovery LLM-backed.
- Do not change LangGraph topology, node names, recovery routing, confirmation boundary, execution workflow, or action ledger behavior.
- Do not execute write tools from any agent.
- Do not add new database tables or Alembic migrations.
- Do not add new package dependencies.
- Do not add frontend UI, Web API endpoints, CLI commands, background jobs, or automations.
- Do not require live LLM credentials for default tests.
- Do not add live-provider tests unless explicitly requested later.
- Do not depend on `OPENAI_API_KEY`.
- Do not persist raw prompts, raw provider responses, raw provider usage keys, raw headers, secrets, action IDs, or tool event IDs.
- Do not loosen benchmark graders, replay comparisons, final review checks, or confirmation-boundary assertions.
- Do not modify benchmark fixtures unless a test-only fixture is required for this task and explicitly scoped.
- Do not commit generated traces, benchmark reports, `var/`, caches, virtual environments, frontend build output, or unrelated untracked files such as `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

Runtime configuration:

```text
LLM_ENABLED=false
LLM_API_KEY=
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=
LLM_TIMEOUT=10
```

Workflow dependency injection:

- Existing `WeekendPilotWorkflowDependencies`.
- Optional settings injection for tests.
- Optional fake LLM client injection for tests.

Agent adapter inputs remain the same as the current deterministic adapters:

- Discovery:
  - `QueryPlan`
  - `CandidateCollectionResult`
  - `CandidateEnrichmentResult`
  - optional `AgentInvocationContext`
- Dining:
  - `QueryPlan`
  - `CandidateCollectionResult`
  - `CandidateEnrichmentResult`
  - optional `AgentInvocationContext`
- Itinerary Planner:
  - `QueryPlan`
  - `CandidateEnrichmentResult`
  - optional `AgentInvocationContext`

### Outputs

Discovery and Dining must return an `AgentResult`.

Itinerary Planner must return:

- `AgentResult`
- `ItineraryDraftResult`

The public workflow result shape should remain compatible with the current `WeekendPilotWorkflowResult`.

### Schemas

Add normalized LLM metadata similar to:

```json
{
  "provider_kind": "openai_compatible",
  "model_id": "qwen3.6-plus",
  "base_url_host": "dashscope.aliyuncs.com",
  "latency_ms": 1234,
  "usage": {
    "input_count": 100,
    "output_count": 40,
    "total_count": 140
  },
  "status": "completed",
  "fallback_reason": null,
  "error_type": null
}
```

Fallback metadata should use the same shape with `status="fallback"` and a normalized fallback reason:

```json
{
  "provider_kind": "openai_compatible",
  "model_id": "qwen3.6-plus",
  "base_url_host": "dashscope.aliyuncs.com",
  "latency_ms": null,
  "usage": {
    "input_count": null,
    "output_count": null,
    "total_count": null
  },
  "status": "fallback",
  "fallback_reason": "llm_timeout",
  "error_type": "LLMProviderError"
}
```

Allowed fallback reasons:

```text
llm_disabled
llm_config_incomplete
llm_timeout
llm_provider_error
llm_bad_json
llm_schema_mismatch
agent_policy_mismatch
invalid_candidate_ids
invalid_draft_ids
no_deterministic_drafts
```

Provider usage normalization must map raw provider keys internally only:

```json
{
  "prompt_tokens": "input_count",
  "completion_tokens": "output_count",
  "total_tokens": "total_count"
}
```

The raw keys on the left side must not appear in persisted metadata or traces.

## 6. Observability

Task 031 must add safe LLM observability through existing metadata channels.

Persist under each relevant `AgentResult.output_json["llm"]`:

- provider kind
- model ID
- base URL host
- latency in milliseconds
- normalized usage counts
- status
- fallback reason
- safe error type

Existing `agent_runs.metadata_json["agents"]` must remain sanitized by `sanitized_agent_payload`.

The local trace buffer and optional LangSmith summary should include the latest persisted sanitized run metadata, including LLM agent metadata when available.

Observability must not include:

- raw prompts
- raw provider responses
- raw provider headers
- raw provider usage keys
- API keys
- authorization headers
- tokens
- secrets
- `tool_event_id`
- `action_id`
- `debug_trace`
- traceback text

LangSmith upload failure must not fail the workflow.

## 7. Failure Handling

- If `LLM_ENABLED=false`, use deterministic adapters and do not create a live LLM client.
- If `LLM_ENABLED=true` but `LLM_API_KEY`, `LLM_BASE_URL`, or `LLM_MODEL_ID` is missing, fallback deterministically with `llm_config_incomplete`.
- If the provider request times out, fallback deterministically with `llm_timeout`.
- If the provider returns an HTTP or network error, fallback deterministically with `llm_provider_error`.
- If the provider returns invalid JSON or the assistant content is not parseable JSON, fallback deterministically with `llm_bad_json`.
- If the assistant JSON is parseable but does not match the expected adapter schema, fallback deterministically with `llm_schema_mismatch`.
- If the assistant references unknown tools or write tools, fallback deterministically with `agent_policy_mismatch`.
- If Discovery or Dining references unknown candidate IDs, fallback deterministically with `invalid_candidate_ids`.
- If Itinerary Planner references unknown draft IDs, fallback deterministically with `invalid_draft_ids`.
- If the deterministic itinerary generator cannot produce any draft, fallback deterministically with `no_deterministic_drafts`.
- Fallback must preserve current deterministic workflow behavior and should be visible through sanitized metadata.
- LLM failures must not execute write tools, change recovery routing, skip final review, or bypass user confirmation.

## 8. Acceptance Criteria

- [ ] `docs/specs/031-llm-backed-bounded-agents-v0.md` exists and matches this task.
- [ ] Generic `LLM_*` settings are available through `backend.app.core.config.Settings`.
- [ ] The new LLM-backed path does not require `OPENAI_API_KEY`.
- [ ] `.env.example` documents `LLM_ENABLED`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_ID`, and `LLM_TIMEOUT` without real secrets.
- [ ] An OpenAI-compatible chat client can call `/chat/completions` through an injected fake HTTP transport in tests.
- [ ] Provider usage is normalized to `input_count`, `output_count`, and `total_count`.
- [ ] Raw provider usage keys are not persisted.
- [ ] Default workflow behavior remains deterministic when `LLM_ENABLED=false`.
- [ ] When `LLM_ENABLED=true`, only Discovery, Dining, and Itinerary Planner use LLM-backed adapters.
- [ ] Supervisor remains deterministic.
- [ ] Validator/Recovery remains deterministic.
- [ ] LLM-backed adapters keep existing typed method signatures and return types.
- [ ] Discovery and Dining validate tool policies and candidate IDs.
- [ ] Itinerary Planner only selects or reorders existing deterministic draft IDs.
- [ ] Deterministic fallback works for missing config, timeout, provider error, bad JSON, schema mismatch, policy mismatch, invalid candidate IDs, invalid draft IDs, and no deterministic drafts.
- [ ] Fallback metadata includes a normalized fallback reason.
- [ ] Agent metadata records model ID, provider kind, base URL host, latency, normalized usage, status, and fallback reason.
- [ ] Agent metadata does not contain raw prompts, raw responses, raw headers, raw provider usage keys, secrets, action IDs, tool event IDs, debug traces, or traceback text.
- [ ] Local trace buffer summaries include latest sanitized LLM agent metadata when available.
- [ ] Human confirmation boundary remains unchanged.
- [ ] No write tools execute before confirmation.
- [ ] Existing bounded-agent tests pass.
- [ ] Existing workflow integration tests pass.
- [ ] Existing observability tests pass.
- [ ] Existing benchmark harness tests pass.
- [ ] Existing benchmark replay tests pass.
- [ ] No frontend, Web API, CLI, MCP, migration, or dependency changes are added.
- [ ] `python -m pytest -q` passes.
- [ ] `docker compose config` passes.
- [ ] `git diff --check` passes.
- [ ] No `.env`, API key, token, secret, `var/`, cache, virtual environment, frontend build artifact, or unrelated untracked file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_llm_client.py tests/test_llm_agents.py tests/test_agents.py tests/test_observability.py -v
python -m pytest tests/integration/test_workflow_llm_agents_gateway.py tests/integration/test_workflow_agents_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest tests/test_benchmark_replay.py tests/integration/test_benchmark_replay_gateway.py -v
python -m pytest -q
docker compose config
git diff --check
git status --short
```

If PostgreSQL or Redis is not running, start required services and apply migrations before integration verification:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 10. Expected Commit

```text
feat: add llm-backed bounded agents v0
```

## 11. Notes for the Implementer

Keep Task 031 scoped to optional LLM-backed adapters behind existing bounded-agent contracts.

The safest implementation path is to add a small OpenAI-compatible client, a factory that selects deterministic or LLM-backed adapters, and LLM wrappers that always validate structured model output before using it. The model should improve semantic summaries and draft ordering only; deterministic services still own retrieval, route/time math, recovery, final review, confirmation, execution, benchmark grading, and replay.

Do not add AMAP MCP integration, live-provider tests, frontend controls, prompt management UI, Supervisor LLM behavior, Validator/Recovery LLM behavior, or any database migration in this task.

The current untracked `docs/TASK_WORKFLOW_PROMPTS.md` and `var/` directory are unrelated to Task 031. Do not stage or commit them unless the user explicitly adds them to this task.
