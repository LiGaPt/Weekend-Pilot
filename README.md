# WeekendPilot

WeekendPilot is a benchmark-driven local-life planning and execution system for short weekend activities.

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

## LocalLife-Bench Harness

The benchmark harness runs file-based cases through the official LangGraph workflow and bounded deterministic agent adapters, then writes local JSON reports. It does not require LangSmith credentials or live provider access.

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

Read status:

```bash
curl http://127.0.0.1:8000/demo/runs/<run_id>
```

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
```

Open `http://127.0.0.1:5173`.

The frontend defaults to `http://127.0.0.1:8000` for the API. To override it locally, set `VITE_API_BASE_URL` in `frontend/.env`.

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
