# Plan: 031 LLM-Backed Bounded Agents v0

## 1. Spec Reference

Spec file:

```text
docs/specs/031-llm-backed-bounded-agents-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

If the spec file is still missing at implementation time, stop and save the approved Task 031 spec first.

## 2. Current Repository Assumptions

- Current branch is `task30`.
- Latest completed commit is `8f29410 feat: add locallife bench replay harness v0`.
- Latest completed task files are:
  - `docs/specs/030-locallife-bench-replay-harness-v0.md`
  - `docs/plans/030-locallife-bench-replay-harness-v0-plan.md`
- Existing untracked files include `docs/TASK_WORKFLOW_PROMPTS.md` and `var/`; do not stage them unless explicitly requested.
- `backend.app.agents` already contains deterministic bounded adapters for Supervisor, Discovery, Dining, Itinerary Planner, and Validator/Recovery.
- `backend.app.workflow` still instantiates those deterministic adapters directly.
- `agent_runs.metadata_json["agents"]` already stores sanitized bounded-agent summaries through `sanitized_agent_payload`.
- `ObservabilityRecorder._summary_payload()` currently relies on the trace-context metadata snapshot, so it will miss later agent metadata unless updated.
- Local environment variables already favor `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_ID`, and `LLM_TIMEOUT`; Task 031 must not require `OPENAI_API_KEY`.
- The repo already has `httpx`, `pydantic-settings`, and `langgraph` installed; no new package is expected.
- Existing regression coverage includes `tests/test_agents.py`, `tests/test_observability.py`, `tests/integration/test_workflow_agents_gateway.py`, `tests/test_benchmark_harness.py`, and `tests/test_benchmark_replay.py`.

## 3. Files to Add

- `docs/plans/031-llm-backed-bounded-agents-v0-plan.md` - this implementation plan.
- `backend/app/llm/__init__.py` - public exports for the local LLM client package.
- `backend/app/llm/errors.py` - typed LLM configuration, provider, response, and validation errors.
- `backend/app/llm/schemas.py` - OpenAI-compatible chat request/result metadata and normalized usage schemas.
- `backend/app/llm/client.py` - OpenAI-compatible `/chat/completions` client using `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL_ID`.
- `backend/app/agents/factory.py` - bounded-agent factory that selects deterministic or LLM-backed adapters.
- `backend/app/agents/llm_adapters.py` - LLM-backed Discovery, Dining, and Itinerary Planner adapters with deterministic fallback.
- `tests/test_llm_client.py` - unit tests for config completeness, request shape, provider errors, JSON parsing, and usage normalization.
- `tests/test_llm_agents.py` - unit tests for LLM adapter success, fallback, policy enforcement, ID validation, and metadata sanitization.
- `tests/integration/test_workflow_llm_agents_gateway.py` - workflow integration tests using a fake LLM client with PostgreSQL and Redis.

## 4. Files to Modify

- `backend/app/core/config.py` - add typed `LLM_*` settings and stop using `OPENAI_API_KEY` in the new code path.
- `.env.example` - document `LLM_ENABLED`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_ID`, and `LLM_TIMEOUT`.
- `backend/app/agents/__init__.py` - export the agent factory and LLM-backed adapters if consistent with package exports.
- `backend/app/workflow/dependencies.py` - add optional `settings` and `llm_client` injection points.
- `backend/app/workflow/nodes.py` - replace direct deterministic adapter construction with the bounded-agent factory.
- `backend/app/observability/context.py` - make run-summary payloads read the latest persisted run metadata.
- `tests/test_observability.py` - add assertions for sanitized LLM agent metadata in trace summaries.
- `tests/integration/test_workflow_agents_gateway.py` - keep the default deterministic path stable and add additive assertions only if needed.
- `README.md` - document the LLM-backed bounded-agent mode and focused verification commands.

## 5. Implementation Steps

1. Confirm preconditions.
   - Run:
     ```bash
     git status --short --branch
     git log --oneline -5
     Test-Path docs/specs/031-llm-backed-bounded-agents-v0.md
     ```
   - Confirm `task30` baseline, latest commit, and that the Task 031 spec exists before implementation starts.

2. Add LLM settings in `backend/app/core/config.py`.
   - Add:
     - `llm_enabled: bool = False`
     - `llm_api_key: SecretStr | None = None`
     - `llm_base_url: str | None = None`
     - `llm_model_id: str | None = None`
     - `llm_timeout: float = 10.0`
   - Keep existing unrelated settings unchanged.
   - New runtime code must only read `LLM_*` fields; do not depend on `openai_api_key`.

3. Update `.env.example`.
   - Replace the `OPENAI_API_KEY` example with `LLM_*` examples.
   - Document the DashScope-compatible base URL used locally:
     - `LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
   - Keep secrets blank in the example file.

4. Add the `backend/app/llm` package.
   - Create typed errors for configuration, provider, and response failures.
   - Add schemas for:
     - chat messages
     - normalized usage counts
     - call metadata
     - chat completion results
   - Implement an OpenAI-compatible chat client that:
     - posts to `<LLM_BASE_URL>/chat/completions`
     - sends bearer auth
     - requests JSON-only output
     - measures latency
     - parses assistant JSON
     - normalizes usage to `input_count`, `output_count`, and `total_count`
   - The client must not persist raw prompts, raw responses, raw headers, or raw provider usage keys.

5. Add `backend/app/agents/factory.py` and `backend/app/agents/llm_adapters.py`.
   - Add an `AgentAdapterSet` dataclass for `supervisor`, `discovery`, `dining`, `itinerary_planner`, and `validator_recovery`.
   - Implement `build_agent_adapters(settings, llm_client=None) -> AgentAdapterSet`.
   - Rules:
     - `LLM_ENABLED=false` returns the existing deterministic adapters.
     - `LLM_ENABLED=true` returns LLM-backed Discovery, Dining, and Itinerary Planner adapters.
     - Supervisor and Validator/Recovery remain deterministic in v0.
     - If config is incomplete, return LLM wrappers with `client=None` so they can fallback deterministically and record `llm_config_incomplete`.
   - Discovery and Dining must validate candidate IDs and allowed tool names.
   - Itinerary Planner must only reorder or select from existing deterministic `draft_id` values; it must not create new drafts, timelines, action payloads, or route data.
   - Any timeout, provider failure, malformed JSON, schema mismatch, policy mismatch, invalid candidate IDs, invalid draft IDs, or missing deterministic drafts must fallback safely.

6. Wire the factory into workflow dependencies and nodes.
   - Extend `WeekendPilotWorkflowDependencies` with optional `settings` and `llm_client`.
   - In `WeekendPilotWorkflowNodes.__init__`, build the adapter set once from `get_settings()` unless injected settings are provided.
   - Keep graph topology, node names, confirmation boundary, and execution flow unchanged.
   - Continue persisting sanitized `agent_results`; do not change the workflow result schema.

7. Update observability summary collection.
   - Modify `ObservabilityRecorder._summary_payload()` so it reads the latest `agent_runs.metadata_json` from the database when building the summary payload.
   - Ensure the local trace buffer and optional LangSmith summary see the latest sanitized `metadata.agents.results[*].output_json.llm`.
   - Keep existing redaction behavior intact; do not allow raw prompts, raw responses, raw usage keys, secrets, or debug traces into the summary payload.

8. Add tests for the client and adapters.
   - `tests/test_llm_client.py` should cover:
     - settings loading
     - request shape
     - JSON parsing
     - usage normalization
     - timeout/provider/bad JSON failure mapping
     - absence of raw token keys in serialized metadata
   - `tests/test_llm_agents.py` should cover:
     - factory selection
     - deterministic default path
     - LLM-enabled path
     - fallback reasons
     - candidate/draft validation
     - metadata sanitization
   - `tests/integration/test_workflow_llm_agents_gateway.py` should inject a fake client, verify the LLM-enabled workflow path, and confirm `auto_confirm=False` still stops before execution.

9. Update existing regression tests only where additive assertions are needed.
   - `tests/test_observability.py` should assert the summary payload includes latest agent metadata and normalized usage when persisted.
   - `tests/integration/test_workflow_agents_gateway.py` should keep deterministic assertions stable for the default path.

10. Update `README.md`.
   - Add a short section explaining the LLM-backed bounded agents, the `LLM_*` environment variables, default-disabled behavior, and focused verification commands.
   - Do not document `OPENAI_API_KEY` as required runtime input.

11. Run focused checks, then review git status before commit.
   - Confirm only intended files are staged.
   - Confirm `.env`, API keys, tokens, `var/`, and unrelated untracked files are not staged.
   - Confirm no raw prompts or raw provider responses are persisted.

## 6. Testing Plan

- Unit tests:
  - client request/response normalization
  - client timeout, provider error, malformed JSON handling
  - adapter factory selection by `LLM_ENABLED`
  - LLM-backed Discovery/Dining/Itinerary behavior
  - deterministic fallback behavior and fallback reasons
  - candidate ID and draft ID validation
  - metadata sanitization for normalized usage and safe LLM fields
- Integration tests:
  - default workflow remains deterministic with `LLM_ENABLED=false`
  - LLM-enabled workflow uses a fake client for Discovery/Dining/Itinerary only
  - confirmation boundary still prevents write tools before confirmation
  - persisted agent metadata and local trace summary include safe LLM metadata
- Regression tests:
  - existing bounded-agent tests
  - existing observability tests
  - benchmark harness tests
  - benchmark replay tests

## 7. Verification Commands

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

If PostgreSQL or Redis is not running, start them first:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add llm-backed bounded agents v0
```

Expected commands:

```bash
git status --short
git switch task30
git switch -c task31
git add docs/specs/031-llm-backed-bounded-agents-v0.md docs/plans/031-llm-backed-bounded-agents-v0-plan.md
git add backend/app/core/config.py .env.example README.md
git add backend/app/llm backend/app/agents backend/app/workflow backend/app/observability
git add tests/test_llm_client.py tests/test_llm_agents.py tests/test_agents.py tests/test_observability.py
git add tests/integration/test_workflow_llm_agents_gateway.py tests/integration/test_workflow_agents_gateway.py
git diff --cached --check
git commit -m "feat: add llm-backed bounded agents v0"
git push -u origin task31
```

Before committing, confirm `.env`, API keys, tokens, secrets, `var/`, `.venv`, caches, `node_modules`, `frontend/dist`, Playwright artifacts, and unrelated `docs/TASK_WORKFLOW_PROMPTS.md` are not staged.

## 9. Out-of-scope Changes

- Do not add AMAP MCP integration.
- Do not make Supervisor or Validator/Recovery LLM-backed.
- Do not change workflow graph topology, node names, confirmation boundary, or execution flow.
- Do not execute write tools from any agent.
- Do not add new database tables or Alembic migrations.
- Do not add dependencies.
- Do not add frontend UI or Web API endpoints.
- Do not call live LLM providers from default tests.
- Do not depend on `OPENAI_API_KEY`.
- Do not persist raw prompts, raw provider responses, raw usage keys, secrets, `action_id`, or `tool_event_id`.
- Do not loosen existing benchmark graders or replay checks.
- Do not commit generated traces, benchmark reports, caches, virtual environments, or local secrets.

## 10. Review Checklist

- [ ] Task 031 spec exists at `docs/specs/031-llm-backed-bounded-agents-v0.md`.
- [ ] Task 031 plan exists at `docs/plans/031-llm-backed-bounded-agents-v0-plan.md`.
- [ ] `LLM_ENABLED`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_ID`, and `LLM_TIMEOUT` are supported.
- [ ] Runtime code does not require `OPENAI_API_KEY`.
- [ ] Default behavior remains deterministic when LLM is disabled.
- [ ] Only Discovery, Dining, and Itinerary Planner are LLM-backed when enabled.
- [ ] Supervisor remains deterministic.
- [ ] Validator/Recovery remains deterministic.
- [ ] LLM requests use an OpenAI-compatible `/chat/completions` endpoint.
- [ ] Usage metadata is normalized to `input_count`, `output_count`, and `total_count`.
- [ ] Raw token usage keys are not persisted.
- [ ] Fallback works for incomplete config, timeout, provider failure, malformed JSON, schema mismatch, invalid candidate IDs, and invalid draft IDs.
- [ ] Observability records model ID, provider kind, base URL host, latency, normalized usage, and fallback reason.
- [ ] Local trace buffer receives sanitized current agent metadata.
- [ ] No raw prompts, raw responses, secrets, action IDs, or tool event IDs are persisted.
- [ ] Existing workflow and benchmark regression tests pass.
- [ ] `python -m pytest -q` passed.
- [ ] `docker compose config` passed.
- [ ] `git diff --check` passed.
- [ ] No `.env`, secret, generated artifact, or unrelated untracked file was staged.
- [ ] Commit message is `feat: add llm-backed bounded agents v0`.
- [ ] Push succeeded or a clear reason for not pushing was reported.

## 11. Handoff Notes

Report back with:

- Branch name.
- Commit hash.
- Files changed.
- Verification commands and results.
- Whether PostgreSQL and Redis were needed or already running.
- Confirmation that default behavior stayed deterministic.
- Confirmation that `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL_ID` were used instead of `OPENAI_API_KEY`.
- Confirmation that only Discovery, Dining, and Itinerary Planner are LLM-backed in v0.
- Confirmation that fallback reasons are recorded safely.
- Confirmation that normalized usage metadata is recorded without raw provider usage keys.
- Confirmation that local trace and metadata sanitization still block secrets and raw debug data.
- Confirmation that no `.env`, secret, `var/`, or unrelated untracked file was committed.
- Known limitation: Task 031 does not add AMAP MCP, live-provider tests, prompt management UI, frontend controls, LLM-backed Supervisor/Validator behavior, or any new database schema.
