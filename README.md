# WeekendPilot

WeekendPilot is a benchmark-driven local-life planning and execution system for short weekend activities.

For the competition architecture and design overview, see `docs/COMPETITION_DESIGN_DOCUMENT.md`.

## Local Setup

Create and activate a virtual environment, then install the backend with development dependencies:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

The `.env` file is optional for the scaffold because local defaults are provided. Do not commit `.env`, API keys, tokens, or secrets.

## AMAP Read Provider

AMAP support is optional and currently covers read tools only: `search_poi`, `get_poi_detail`, `check_route`, and `check_weather`.
Set the key in local `.env` only:

```bash
AMAP_MAPS_API_KEY=your-local-key
```

The local demo still defaults to `Mock World`. `AMap` is available only as an explicit read-only preview path for local review, and that path stops before confirmation instead of executing write tools. Internal observability review now also exposes a compact `preview_diagnostics` block for these AMAP runs so provider names, sanitized provider error types, and write-tool absence stay directly auditable. Benchmark cases, benchmark suites, and benchmark defaults remain on `Mock World`.

Default tests do not call live AMAP APIs:

```bash
python -m pytest
```

Optional live smoke tests require `RUN_AMAP_LIVE_TESTS=1` and `AMAP_MAPS_API_KEY`:

```bash
$env:RUN_AMAP_LIVE_TESTS="1"
python -m pytest tests/integration/test_amap_live.py -v
```

## Mock World Provider

Mock World is the deterministic default provider for benchmark-style local-life tests. It covers canonical read tools, availability checks, and simulated write tools without external APIs or secrets.

Focused Mock World tests require PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/integration/test_mock_world_gateway.py -v
```

## Query Plan Execution

Focused query-plan execution tests require PostgreSQL and Redis for the gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_query_plan_execution.py tests/integration/test_query_plan_execution_gateway.py -v
```

## Candidate Enrichment

Focused candidate enrichment and route matrix tests require PostgreSQL and Redis for the gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_candidate_enrichment.py tests/integration/test_candidate_enrichment_gateway.py -v
```

## Itinerary Draft Generation

Focused itinerary draft tests require PostgreSQL and Redis for the gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_itinerary_generation.py tests/integration/test_itinerary_generation_gateway.py -v
```

## Final Review Gate

Focused final review tests require PostgreSQL and Redis for the gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_final_review_gate.py tests/integration/test_final_review_gate_gateway.py -v
```

## Reviewed Plan Persistence

Focused reviewed plan persistence tests require PostgreSQL and Redis for the upstream gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_plan_persistence.py tests/integration/test_plan_persistence_gateway.py -v
```

## Human Confirmation Boundary

Focused human confirmation tests require PostgreSQL and Redis for the upstream gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_human_confirmation.py tests/integration/test_human_confirmation_gateway.py -v
```

## Deterministic Execution Workflow

Focused execution workflow tests require PostgreSQL and Redis for the gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_execution_workflow.py tests/integration/test_execution_workflow_gateway.py -v
```

## Deterministic Feedback Writer

Focused feedback writer tests require PostgreSQL and Redis for the upstream gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_feedback_writer.py tests/integration/test_feedback_writer_gateway.py -v
```

## LangSmith Observability Baseline

Default observability tests use a local JSONL trace buffer and do not require LangSmith credentials or live uploads.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py -v
```

Optional LangSmith tracing can be enabled locally with `.env` values only:

```bash
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=weekend-pilot
LANGSMITH_API_KEY=your-local-key
LOCAL_TRACE_BUFFER_PATH=var/traces/weekendpilot-traces.jsonl
```

Local trace JSONL summaries now also embed the canonical `run_summary` envelope, which is persisted to `agent_runs.metadata_json["summary"]` for workflow-backed runs.

## LocalLife-Bench Harness

The benchmark harness runs file-based cases through the official LangGraph workflow and bounded deterministic agent adapters, then writes local JSON reports. Case reports stay under `var/benchmarks/`. Ad hoc `run_cases(...)` runs still write `var/benchmarks/run-report.json`, while named `run_suite(...)` runs write `var/benchmarks/suite-<suite_id>-run-report.json`. It does not require LangSmith credentials or live provider access.

Canonical benchmark fixtures and suites remain `Mock World` only in this v0 task. Registered benchmark cases now fail fast during fixture or suite loading if `tool_profile != "mock_world"`, and ad hoc harness calls also reject non-Mock-World cases before workflow execution. Suite `matrix_summary` payloads now include `tool_profile_counts` so this provider boundary stays auditable in reports.

Each benchmark case fixture now requires a structured `taxonomy` block that captures suite, scenario bucket, benchmark level, tags, and failure mode. Each benchmark case report now includes both `run_summary` and `taxonomy`. Failure-profile cases also add a sanitized `failure_chain_summary` so injected effects, bounded recovery actions, and terminal workflow state stay directly reviewable in case reports. Memory-governed cases now also persist `workflow.memory_policy` as `memory_query_policy_v1`, including per-dimension winners and per-memory outcomes so memory behavior stays auditable without exposing raw memory text or payloads. Continuation cases now also add sanitized `conversation_trace` step summaries and ordered `conversation_turn_types` so status transitions and plan-version evolution stay reviewable without exposing raw conversation payloads. Each suite summary now includes both `matrix_summary` coverage counts and additive `outcome_rollup` pass-rate buckets by scenario family, constraint tag, and failure mode so coverage and benchmark pass rate can be compared directly as the suite catalog expands.

The repository now keeps seven canonical named benchmark suites in code:

- `baseline` for the historical six-case family-plus-solo non-failure baseline
- `expanded` for the added couple, friends-group, rainy-day fallback, and budget-lite scenario pack
- `recovery_focused` for the explicit three-case failure-injection recovery pack: the legacy route failure case plus two composite chaos cases
- `memory_governance` for the focused three-case suite that proves explicit user input beats memory, advisory memory helps vague requests, and expired high-confidence memory is downgraded but still visible
- `conversation_continuations` for the focused two-case multi-turn clarification and replan/version suite
- `default` for the ten-case non-failure union of `baseline + expanded`
- `all_registered` for the full 17-case registered fixture inventory

The legacy `failures` suite name remains loadable as a compatibility alias to `recovery_focused`, and `load_failure_benchmark_cases()` now resolves to that canonical recovery-focused suite. The `default` suite remains the historical single-turn ten-case suite. Continuation benchmarking in this v0 task is intentionally limited to non-failure `Mock World` cases, and it uses the demo conversation service only to drive clarification/replan chains before writing benchmark reports. Replay stable comparison now also includes `failure_chain_signature`, which mirrors the ordered injected-effect chain from `failure_chain_summary.injected_effects`. Suite descriptions still derive their `matrix_summary` from the existing case taxonomy so expansion stays reviewable.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
```

## LangGraph Workflow Skeleton

The workflow package provides the shared product route for the deterministic Mock World flow. It pauses before write-tool execution unless `auto_confirm=True` is supplied by a test or demo caller.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
```

## Bounded Agent Contracts

Task 020 adds deterministic bounded-agent adapters for Supervisor, Discovery, Dining, Itinerary Planner, and Validator/Recovery. These adapters do not call LLMs and do not execute write tools.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_agents.py tests/integration/test_workflow_agents_gateway.py -v
```

## LLM-Backed Bounded Agents

LLM-backed bounded agents are disabled by default. When enabled, v0 only replaces Discovery, Dining, and Itinerary Planner behind the existing typed contracts; Supervisor, Validator/Recovery, routing, confirmation, execution, benchmark grading, and replay stay deterministic.

Set generic OpenAI-compatible values in local `.env` only:

```bash
LLM_ENABLED=true
LLM_API_KEY=your-local-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=your-compatible-model
LLM_TIMEOUT=10
```

Default tests use fake clients and do not call live LLM providers:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_llm_client.py tests/test_llm_agents.py tests/integration/test_workflow_llm_agents_gateway.py -v
```

## Infrastructure

Start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

Stop local infrastructure:

```bash
docker compose down
```

If default ports conflict, override them when running Compose:

```bash
POSTGRES_PORT=15432 REDIS_PORT=16379 docker compose up -d postgres redis
```

## Database Migrations

Start PostgreSQL, then apply the Alembic migrations:

```bash
docker compose up -d postgres
python -m alembic upgrade head
python -m alembic current
```

## Run The API

```bash
uvicorn backend.app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "weekend-pilot",
  "environment": "local",
  "version": "0.1.0"
}
```

## Web Demo API

The Web demo API starts the official workflow, pauses before write tools, and continues execution only after explicit confirmation. The MVP review path uses Chinese Mock World demo content for the family afternoon scenario.
The default start path stays on `Mock World`. To preview the live read provider locally, send `read_profile="amap"` and keep `AMAP_MAPS_API_KEY` in local `.env`; that AMAP path is read-only and cannot be confirmed into execution.
When a start request is still missing key supported constraints, or when bounded recovery needs an explicit user tradeoff, the workflow stops in `awaiting_clarification` instead of fabricating a plan. In that state the public `DemoRunSummary` returns `plans = []`, `selected_plan_id = null`, and a compact `clarification` object with the user-visible follow-up prompt plus the missing supported fields.
Every public demo run summary includes a compact `plan_version` object. The initial run starts at `v1`, and each follow-up replan increments the visible version label.
Clarification-only turns do not advance the visible plan version. A vague `v1` run that stops in `awaiting_clarification` stays at `v1`, and the first clarification continuation that produces actual plans also remains at `v1`.
Every public `DemoPlanPreview` now also includes `action_manifest`, which is the stable execution-preview contract for the Web demo. Before confirmation it summarizes `draft.proposed_actions` as `source = "proposed_actions"`. After confirmation or execution it summarizes persisted `confirmed_actions` as `source = "confirmed_actions"`. The older `proposed_actions` field remains present for compatibility, but the public frontend now renders action previews from `action_manifest.actions`.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
```

Start a run:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"今天下午想和爱人、5岁的孩子出门玩几个小时，别离家太远。孩子要适合亲子活动，爱人最近想吃清淡一点，帮我安排一下。\"}"
```

Start an explicit AMap read-only preview run:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"Plan a light family afternoon nearby.\",\"external_user_id\":\"web-demo-user\",\"display_name\":\"Web Demo User\",\"case_id\":\"web-demo\",\"selected_plan_index\":0,\"read_profile\":\"amap\"}"
```

Read status:

```bash
curl http://127.0.0.1:8000/demo/runs/<run_id>
```

Reply to a clarification request in the same internal conversation session:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/clarify \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"今天下午一个人出门玩几个小时，别太远。\",\"selected_plan_index\":0}"
```

Internal observability review:

```bash
curl http://127.0.0.1:8000/internal/runs/<run_id>/observability
```

For successful AMAP preview runs, this internal review route now returns `preview_diagnostics` directly from the canonical persisted run summary, with a recomputed fallback when stored diagnostics are missing or malformed.

Confirm the selected plan:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/confirm \
  -H "Content-Type: application/json" \
  -d "{\"confirmed_by\":\"web-demo-user\"}"
```

Decline the selected plan:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/decline \
  -H "Content-Type: application/json" \
  -d "{\"declined_by\":\"web-demo-user\",\"reason\":\"用户选择暂不继续。\"}"
```

Replan the current run with a follow-up:

```bash
curl -X POST http://127.0.0.1:8000/demo/runs/<run_id>/replan \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"Keep it nearby, but make it a solo outing this time.\",\"selected_plan_index\":0}"
```

The replan response returns a new `run_id`. The internal conversation session is reused across the original run and the follow-up run, but that session state remains non-public and is not exposed in `DemoRunSummary`.
Each replan also advances the public version label to `v2`, `v3`, and so on.
If the source run is `awaiting_clarification`, use `/clarify` instead of `/replan`. This applies to both pre-planning clarification stops and recovery-driven clarification stops. The clarification continuation also returns a new `run_id`, reuses the same internal session, and keeps the public version label at `v1` until the first real plan is produced.

## Minimal Web UI Demo

Run the backend first:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
uvicorn backend.app.main:app --reload
```

Run the frontend:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
npm --prefix frontend run dev:internal
```

Open the customer surface at `http://127.0.0.1:5173/`.
Open the internal review surface at `http://127.0.0.1:5174/`.

The frontend defaults to `http://127.0.0.1:8000` for the API. To override it locally, set `VITE_API_BASE_URL` in `frontend/.env`.
The public demo page only shows customer-safe run details. Internal trace and node history review now lives on the separate internal frontend surface at `http://127.0.0.1:5174/`.
The visible run inspector includes the current plan version label for the loaded run.
The visible action preview for each plan tab now comes from `plans[*].action_manifest`, so pre-confirmation and post-confirmation states share one normalized public shape.
The page now also exposes an explicit read-path selector. Leave it on `Mock World` for the default deterministic demo and benchmark-aligned checks. Switch it to `AMap 只读预览` only when you want a local live-provider preview that stays pre-confirmation and does not execute writes.

For internal review, open `http://127.0.0.1:5174/` and paste a `run_id` to inspect the internal run summary, workflow timing, tool-event details, action-ledger details, benchmark artifact context, and bounded recovery-path details. Benchmark-backed recovery runs also surface the persisted benchmark case report path as replay input context for later inspection tooling.

Frontend surface scripts:

```bash
npm --prefix frontend run dev:customer
npm --prefix frontend run dev:internal
npm --prefix frontend run build
```

Build outputs:

- customer: `frontend/dist/customer/index.html`
- internal: `frontend/dist/internal/index.html`

For the full Web demo runbook, see `docs/WEB_DEMO_README.md`.

## Tests

Repository integration tests require PostgreSQL to be running with migrations applied:

```bash
docker compose up -d postgres
python -m alembic upgrade head
```

Redis runtime integration tests require Redis to be running:

```bash
docker compose up -d redis
python -m pytest tests/integration/test_redis_runtime.py -v
```

Tool Gateway integration tests require both PostgreSQL and Redis, with migrations applied:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_tool_gateway.py -v
```

```bash
python -m pytest
```

Validate Docker Compose configuration:

```bash
docker compose config
```
