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
