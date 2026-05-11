# Spec: 001 Project Scaffold

## 1. Goal

Deliver the first runnable project scaffold for WeekendPilot without implementing business planning logic.

After this task is complete, the repository should have a minimal Python/FastAPI backend structure, basic configuration management, a health check endpoint, PostgreSQL and Redis services in Docker Compose, a minimal README startup path, and a pytest suite that can run successfully. This unlocks later tasks for durable state, runtime cache, Tool Gateway, LangGraph workflow, and benchmark harness work.

## 2. Project Context

This task implements the foundation described in `docs/PROJECT_BLUEPRINT.md` sections 4, 5, and 18. It should prepare the repository for a benchmark-driven, centralized bounded multi-agent architecture, but it must not implement agents or workflow behavior yet.

Relevant architecture areas:

- FastAPI becomes the backend entry point for future CLI/Web/API integration.
- PostgreSQL is introduced only as a Docker Compose service and future durable source of truth.
- Redis is introduced only as a Docker Compose service and future runtime cache/progress/lock/rate-limit layer.
- Configuration management is introduced so future LangSmith, database, Redis, and provider settings have a safe typed home.
- Tests are introduced so future tasks can stay independently verifiable.

## 3. Requirements

- Create a backend Python package layout under `backend/app`.
- Create a root-level Python project configuration with runtime and test dependencies.
- Add a FastAPI application object importable by `uvicorn backend.app.main:app`.
- Add `GET /health` returning a stable JSON response with service metadata.
- Add typed settings using `pydantic-settings`, reading from environment variables and optional `.env`.
- Ensure settings provide safe defaults for local development and do not require real API keys.
- Add Docker Compose services for PostgreSQL and Redis with named volumes and health checks.
- Add a `tests` directory with at least one pytest test that exercises the health endpoint.
- Add or update README startup instructions for installing dependencies, starting infrastructure, running the API, and running tests.
- Keep `.env` ignored and ensure `.env.example` contains only placeholder or non-secret values.
- Keep the task independently verifiable with `pytest` and Docker Compose validation.

## 4. Non-goals

- Do not implement LangGraph workflow nodes.
- Do not implement Supervisor, Discovery, Dining, Itinerary Planner, or Validator & Recovery agents.
- Do not implement Tool Gateway, mock providers, real providers, or tool schemas.
- Do not implement PostgreSQL tables, SQLAlchemy models, Alembic migrations, or repositories.
- Do not implement Redis runtime services beyond Docker Compose.
- Do not implement LangSmith tracing beyond configuration placeholders.
- Do not implement Action Ledger, Human-in-the-loop, Final Review Gate, Execution Workflow, LocalLife-Bench, CLI, or Web UI.
- Do not add real `.env` files, API keys, tokens, or secrets.
- Do not change `docs/PROJECT_BLUEPRINT.md` unless a blocking conflict is discovered and reported.

## 5. Interfaces and Contracts

### Inputs

- Environment variables from the shell and optional `.env` file.
- HTTP request:

```text
GET /health
```

### Outputs

- HTTP response:

```json
{
  "status": "ok",
  "service": "weekend-pilot",
  "environment": "local",
  "version": "0.1.0"
}
```

### Schemas

The scaffold should introduce a `Settings` object with at least these fields:

```text
app_name: str
app_env: str
app_version: str
log_level: str
database_url: str
redis_url: str
langsmith_project: str
langchain_tracing_v2: bool
openai_api_key: optional secret
langsmith_api_key: optional secret
amap_maps_api_key: optional secret
baidu_map_api_key: optional secret
```

Secrets must not be returned by API responses, logged in startup output, or committed in any tracked file.

## 6. Observability

This task should not add LangSmith tracing or durable observability tables yet.

It should establish configuration fields that future observability work can use. The health endpoint may return non-sensitive service metadata only. Local pytest output is sufficient for this task.

## 7. Failure Handling

- Missing optional API keys must not prevent local startup or tests.
- Missing `.env` must not prevent local startup or tests because defaults should exist for scaffold settings.
- Malformed typed environment values, such as a non-boolean tracing flag, may fail fast during settings validation.
- PostgreSQL or Redis being unavailable must not cause `GET /health` or unit tests to fail in this task, because no database or Redis client is introduced yet.
- Docker port conflicts should be handled by documenting the relevant Compose environment overrides, not by changing application behavior.

## 8. Acceptance Criteria

- [ ] Backend package directories exist under `backend/app`.
- [ ] `pyproject.toml` or equivalent Python project configuration exists at the repository root.
- [ ] `uvicorn backend.app.main:app --reload` can start the FastAPI application after dependencies are installed.
- [ ] `GET /health` returns HTTP 200 with the agreed JSON shape.
- [ ] Configuration is typed, has local defaults, reads optional `.env`, and does not expose secrets.
- [ ] Docker Compose defines PostgreSQL and Redis services with named volumes and health checks.
- [ ] README contains minimal local startup, test, and infrastructure commands.
- [ ] At least one pytest test verifies the health endpoint.
- [ ] `pytest` passes.
- [ ] Docker Compose configuration validates.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
python -m pip install -e ".[dev]"
python -m pytest
docker compose config
git status --short
```

If Docker is unavailable in the execution environment, the implementer must still run `python -m pytest` and report that Docker Compose validation could not be executed locally.

## 10. Expected Commit

```text
chore: scaffold backend project
```

## 11. Notes for the Implementer

Keep this task deliberately small. The implementation should create a runnable shell around the future system, not the system itself.

Stop and report back if the existing repository already contains conflicting app structure, dependency tooling, or Docker Compose decisions that are not visible in the current blueprint and templates.
