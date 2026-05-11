# Spec: 002 PostgreSQL Schema Baseline

## 1. Goal

Establish the PostgreSQL schema baseline for WeekendPilot so future Tool Gateway, Action Ledger, Memory, Run, and Plan tracking work can rely on a durable source of truth.

After this task is complete, the repository should have SQLAlchemy 2.x declarative models, Alembic migration configuration, the first core runtime tables, and a verification path that can run `alembic upgrade head` against the local Docker PostgreSQL service.

## 2. Project Context

This task implements the database foundation described in `docs/PROJECT_BLUEPRINT.md`, especially PostgreSQL as source of truth, Action Ledger durability, Tool Gateway observability, memory governance, and run tracking.

Task 001 created the FastAPI scaffold, typed settings, Docker Compose PostgreSQL/Redis services, README startup notes, and a health test. Task 002 builds on that scaffold by adding database schema infrastructure only. It must not implement repositories, business workflow, agents, Tool Gateway, Redis services, or API endpoints.

## 3. Requirements

- Add SQLAlchemy, Alembic, and psycopg dependencies.
- Update the default `DATABASE_URL` to SQLAlchemy psycopg3 format: `postgresql+psycopg://postgres:postgres@localhost:5432/weekend_pilot`.
- Add synchronous database engine/session infrastructure.
- Add Alembic configuration that reads `database_url` from `backend.app.core.config.Settings`.
- Add SQLAlchemy models and one initial migration for these core runtime tables:
  - `users`
  - `user_profiles`
  - `memory_items`
  - `agent_runs`
  - `plans`
  - `tool_events`
  - `action_ledger`
- Use UUID primary keys for all tables.
- Use PostgreSQL `JSONB` for JSON payload fields.
- Add important foreign keys, indexes, and uniqueness constraints.
- Make `action_ledger.idempotency_key` unique.
- Add tests for SQLAlchemy metadata table coverage, key columns, key constraints, and Alembic metadata importability.
- Update README with migration commands.
- Keep `.env.example` free of secrets.

## 4. Non-goals

- Do not implement repository classes or CRUD helpers.
- Do not create benchmark, world fixture, or failure injection tables in this task.
- Do not implement SQLAlchemy async engine/session.
- Do not connect to Redis.
- Do not implement Tool Gateway, Mock World, Action Ledger writer, LangGraph, agents, business APIs, or workflow nodes.
- Do not add real `.env` files, API keys, tokens, or secrets.
- Do not change architecture decisions in `docs/PROJECT_BLUEPRINT.md`.

## 5. Interfaces and Contracts

### Inputs

- `DATABASE_URL` from environment or `.env`.
- Local Docker Compose PostgreSQL service.
- Alembic CLI commands.

### Outputs

- SQLAlchemy `Base.metadata`.
- Alembic revision `0001_create_core_runtime_tables`.
- PostgreSQL tables listed in the requirements.

### Schemas

Core table contracts:

- `users`: `user_id`, `external_id`, `display_name`, `created_at`, `updated_at`
- `user_profiles`: `profile_id`, `user_id`, `preferences_json`, `constraints_json`, `created_at`, `updated_at`
- `agent_runs`: `run_id`, `user_id`, `case_id`, `agent_version`, `prompt_version`, `tool_profile`, `world_profile`, `failure_profile`, `status`, `metadata_json`, `created_at`, `updated_at`
- `memory_items`: `memory_id`, `user_id`, `memory_type`, `key`, `value_json`, `text`, `confidence`, `source_run_id`, `source_langsmith_trace_id`, `last_used_at`, `expires_at`, `status`, `created_at`, `updated_at`
- `plans`: `plan_id`, `run_id`, `status`, `plan_json`, `selected`, `created_at`, `updated_at`
- `tool_events`: `event_id`, `run_id`, `tool_name`, `tool_type`, `provider`, `request_json`, `response_json`, `error_json`, `status`, `cache_hit`, `latency_ms`, `langsmith_trace_id`, `created_at`
- `action_ledger`: `action_id`, `run_id`, `action_type`, `target_id`, `idempotency_key`, `status`, `request_json`, `response_json`, `error_json`, `created_at`, `updated_at`

The ORM attribute for `agent_runs.metadata_json` must not be named `metadata`, because `metadata` is reserved by SQLAlchemy declarative models.

## 6. Observability

This task only establishes future observability storage primitives:

- `agent_runs` stores run-level metadata.
- `tool_events` stores tool call metadata.
- `action_ledger` stores future write-tool side effect records.

This task must not add LangSmith runtime tracing, trace upload code, or local JSONL trace buffering.

## 7. Failure Handling

- If PostgreSQL is unavailable, migration commands should fail clearly with a connection error.
- If `.env` is missing, local defaults should allow Alembic to target the Docker PostgreSQL service.
- Alembic env must import project metadata without requiring FastAPI startup.
- Migration downgrade must exist and drop tables in dependency-safe reverse order.
- Regular verification does not need to run downgrade because it can delete local data.

## 8. Acceptance Criteria

- [ ] SQLAlchemy, Alembic, and psycopg dependencies are added.
- [ ] DB session infrastructure is importable.
- [ ] Alembic configuration reads `backend.app.core.config.Settings.database_url`.
- [ ] The 7 core runtime tables exist in SQLAlchemy metadata.
- [ ] The initial migration creates the same 7 core runtime tables.
- [ ] Key foreign keys, indexes, and uniqueness constraints exist.
- [ ] `action_ledger.idempotency_key` is unique.
- [ ] README documents migration commands.
- [ ] `python -m pytest` passes.
- [ ] `docker compose up -d postgres` followed by `python -m alembic upgrade head` passes.
- [ ] `python -m alembic current` shows the head revision.
- [ ] `docker compose config` validates.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
python -m pip install -e ".[dev]"
python -m pytest
docker compose up -d postgres
python -m alembic upgrade head
python -m alembic current
docker compose config
git status --short
```

If Docker emits local config permission warnings but exits with code 0, record the warning and continue. If PostgreSQL cannot start or migration fails, do not commit.

## 10. Expected Commit

```text
feat: add postgres schema baseline
```

## 11. Notes for the Implementer

Use a dedicated Task 002 branch, such as `task2`. Future tasks should also use their own task branches and merge back only after review.

If Task 001 scaffold files are missing from the implementation branch, stop and report the branch/base mismatch before writing code.

Keep this task deliberately focused. Repository classes, CRUD helpers, benchmark tables, and Tool Gateway behavior belong to later tasks.
