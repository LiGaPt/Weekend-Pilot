# Plan: 001 Project Scaffold

## 1. Spec Reference

Spec file:

```text
docs/specs/001-project-scaffold.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch: `feat/locallife-agent`, tracking `origin/feat/locallife-agent`.
- Current status before this task: clean working tree.
- Existing tracked files:
  - `docs/PROJECT_BLUEPRINT.md`
  - `docs/templates/TASK_SPEC_TEMPLATE.md`
  - `docs/templates/TASK_PLAN_TEMPLATE.md`
  - `题目描述.txt`
  - `.env.example`
  - `.gitignore`
- Recent commits:
  - `3c7484e docs: add task spec and plan templates`
  - `0ab3396 docs: add project blueprint`
  - `1eb89e9 chore: initialize repository`
- Existing `.gitignore` already ignores `.env`, `.env.*`, Python caches, pytest cache, virtual environments, build outputs, logs, and editor files.
- There is no backend package, test suite, Python project configuration, Docker Compose file, or README yet.

## 3. Files to Add

- `README.md` - minimal local setup, run, test, and Docker Compose instructions.
- `pyproject.toml` - Python project metadata, runtime dependencies, dev dependencies, and pytest config.
- `docker-compose.yml` - PostgreSQL and Redis local services with named volumes and health checks.
- `backend/__init__.py` - package marker.
- `backend/app/__init__.py` - application package marker.
- `backend/app/main.py` - FastAPI app factory and module-level `app`.
- `backend/app/api/__init__.py` - API package marker.
- `backend/app/api/health.py` - health route.
- `backend/app/core/__init__.py` - core package marker.
- `backend/app/core/config.py` - typed settings and cached settings provider.
- `tests/__init__.py` - test package marker.
- `tests/test_health.py` - health endpoint pytest coverage.

## 4. Files to Modify

- `.env.example` - add non-secret app defaults if needed, such as `APP_NAME`, `APP_ENV`, `APP_VERSION`, and `LOG_LEVEL`.
- `.gitignore` - modify only if implementation discovers `.env` or scaffold-generated files are not already ignored.

## 5. Implementation Steps

1. Confirm the working tree is clean:

```bash
git status --short --branch
```

2. Create the backend and test directories:

```text
backend/app/api
backend/app/core
tests
```

3. Add `pyproject.toml` with:

```toml
[project]
name = "weekend-pilot"
version = "0.1.0"
description = "Benchmark-driven local-life weekend planning and execution system."
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111,<1.0",
  "uvicorn[standard]>=0.29,<1.0",
  "pydantic-settings>=2.2,<3.0"
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27,<1.0",
  "pytest>=8,<9"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

4. Add package marker files with no behavior:

```text
backend/__init__.py
backend/app/__init__.py
backend/app/api/__init__.py
backend/app/core/__init__.py
tests/__init__.py
```

5. Implement `backend/app/core/config.py`:

- Use `pydantic_settings.BaseSettings`.
- Use `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`.
- Include the fields listed in the spec.
- Use `SecretStr | None` for API keys.
- Provide local defaults for `app_name`, `app_env`, `app_version`, `log_level`, `database_url`, `redis_url`, and `langsmith_project`.
- Add an `@lru_cache` wrapped `get_settings()` function.
- Do not print or expose secret values.

6. Implement `backend/app/api/health.py`:

- Create an `APIRouter`.
- Add `GET /health`.
- Depend on `get_settings`.
- Return exactly:

```json
{
  "status": "ok",
  "service": "weekend-pilot",
  "environment": "<settings.app_env>",
  "version": "<settings.app_version>"
}
```

7. Implement `backend/app/main.py`:

- Define `create_app() -> FastAPI`.
- Load settings through `get_settings()`.
- Create `FastAPI(title=settings.app_name, version=settings.app_version)`.
- Include the health router.
- Expose module-level `app = create_app()`.

8. Add `docker-compose.yml`:

- Compose project name: `weekend-pilot`.
- PostgreSQL service:
  - image `postgres:16-alpine`
  - database `weekend_pilot`
  - user/password defaults `postgres`/`postgres`
  - port `${POSTGRES_PORT:-5432}:5432`
  - named volume `postgres_data`
  - `pg_isready` health check
- Redis service:
  - image `redis:7-alpine`
  - port `${REDIS_PORT:-6379}:6379`
  - named volume `redis_data`
  - `redis-cli ping` health check

9. Update `.env.example` if needed so it contains non-secret defaults:

```text
APP_NAME=WeekendPilot
APP_ENV=local
APP_VERSION=0.1.0
LOG_LEVEL=INFO
```

Keep existing placeholder keys for OpenAI, LangSmith, PostgreSQL, Redis, AMap, and Baidu. Do not add real secrets.

10. Add `tests/test_health.py`:

- Import `TestClient` from `fastapi.testclient`.
- Import `app` from `backend.app.main`.
- Assert `GET /health` returns HTTP 200.
- Assert response has `status == "ok"`, `service == "weekend-pilot"`, `environment`, and `version`.

11. Add `README.md` with minimal commands:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
uvicorn backend.app.main:app --reload
python -m pytest
docker compose down
```

Mention that `.env` is optional for local scaffold defaults and must not be committed.

12. Run formatting only if a formatter has been added by this task. Do not introduce additional lint tools in this task.

13. Run verification commands from this plan.

14. Inspect staged changes before commit and confirm no `.env` or secrets are present.

## 6. Testing Plan

- Unit/API tests:
  - `tests/test_health.py::test_health_check_returns_service_metadata` verifies `GET /health`.
- Configuration tests:
  - Covered indirectly by importing the app and calling health.
  - Do not add database or Redis connection tests in this task.
- Smoke tests:
  - `python -m pytest`
  - `docker compose config`
  - Optional manual API smoke after install: `uvicorn backend.app.main:app --reload`, then request `GET /health`.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
python -m pytest
docker compose config
git status --short
```

Optional manual smoke command:

```bash
uvicorn backend.app.main:app --reload
```

If Docker is unavailable, report the Docker limitation explicitly and include the successful pytest output.

## 8. Commit and Push Plan

Expected commit message:

```text
chore: scaffold backend project
```

Expected commands:

```bash
git status --short
git add README.md pyproject.toml docker-compose.yml backend tests .env.example
git status --short
git commit -m "chore: scaffold backend project"
git push origin feat/locallife-agent
```

The implementer must confirm `.env`, API keys, tokens, secrets, virtual environments, caches, and Docker volumes are not staged.

## 9. Out-of-scope Changes

- Do not implement business planning, recommendation, itinerary, execution, or benchmark logic.
- Do not add LangGraph, LangSmith runtime instrumentation, SQLAlchemy, Alembic, Redis client code, or agent prompts.
- Do not create database tables or migrations.
- Do not add CLI or frontend UI.
- Do not add mock world fixtures or provider code.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md`.
- Do not add dependencies beyond FastAPI, Uvicorn, Pydantic Settings, pytest, and httpx.
- Do not commit `.env`, API keys, tokens, virtual environments, caches, or generated logs.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/001-project-scaffold.md`.
- [ ] Scope stayed limited to backend scaffold, config, Docker Compose, README, and tests.
- [ ] `GET /health` returns the expected stable JSON response.
- [ ] Settings use typed configuration and do not expose secrets.
- [ ] PostgreSQL and Redis are present in Docker Compose with health checks.
- [ ] `.env.example` contains placeholders only.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed or Docker unavailability was reported.
- [ ] Commit message is `chore: scaffold backend project`.
- [ ] Push to `origin/feat/locallife-agent` succeeded.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Verification commands and results.
- Whether Docker Compose validation succeeded.
- Commit hash.
- Push result.
- Any deviations from the spec or plan.
- Any recommended follow-up tasks, especially if dependency or Docker availability affected verification.
