# Plan: 002 PostgreSQL Schema Baseline

## 1. Spec Reference

Spec file:

```text
docs/specs/002-postgresql-schema-baseline.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work should happen on a dedicated Task 002 branch, such as `task2`.
- Task 001 scaffold is present on the branch:
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `docker-compose.yml`
  - `pyproject.toml`
  - `.env.example`
  - `README.md`
  - `tests/test_health.py`
- `backend/app/core/config.py` already exposes `database_url`.
- `docker-compose.yml` already defines a PostgreSQL service named `postgres`.
- The repository does not yet contain SQLAlchemy models, Alembic configuration, database sessions, or migrations.

## 3. Files to Add

- `alembic.ini` - Alembic CLI configuration.
- `alembic/env.py` - Alembic runtime environment that loads app settings and SQLAlchemy metadata.
- `alembic/versions/0001_create_core_runtime_tables.py` - initial schema migration.
- `backend/app/db/__init__.py` - database package marker.
- `backend/app/db/base.py` - SQLAlchemy declarative base and naming convention.
- `backend/app/db/session.py` - sync engine, `SessionLocal`, and `get_db()` dependency.
- `backend/app/models/__init__.py` - model exports.
- `backend/app/models/runtime.py` - core runtime ORM models.
- `tests/test_db_metadata.py` - SQLAlchemy metadata and constraint tests.
- `tests/test_alembic_config.py` - Alembic metadata import/config test.

## 4. Files to Modify

- `pyproject.toml` - add SQLAlchemy, Alembic, and psycopg dependencies.
- `backend/app/core/config.py` - update default `database_url`.
- `.env.example` - update `DATABASE_URL`.
- `README.md` - add migration commands.

## 5. Implementation Steps

1. Confirm branch and baseline:

```bash
git status --short --branch
rg --files
```

Expected:

- Branch is the dedicated Task 002 branch.
- Task 001 scaffold files are present.
- No Alembic or SQLAlchemy model files exist yet.

2. Add dependencies to `pyproject.toml`:

```toml
"sqlalchemy>=2.0,<3.0",
"alembic>=1.13,<2.0",
"psycopg[binary]>=3.1,<4.0",
```

3. Update default database URL in both `backend/app/core/config.py` and `.env.example`:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/weekend_pilot
```

4. Write failing metadata tests in `tests/test_db_metadata.py` before adding models:

- Assert metadata includes exactly these task-owned table names:
  - `users`
  - `user_profiles`
  - `memory_items`
  - `agent_runs`
  - `plans`
  - `tool_events`
  - `action_ledger`
- Assert important columns exist on each table.
- Assert `action_ledger.idempotency_key` has a unique constraint or unique index.
- Assert representative foreign keys exist:
  - `user_profiles.user_id -> users.user_id`
  - `agent_runs.user_id -> users.user_id`
  - `memory_items.user_id -> users.user_id`
  - `memory_items.source_run_id -> agent_runs.run_id`
  - `plans.run_id -> agent_runs.run_id`
  - `tool_events.run_id -> agent_runs.run_id`
  - `action_ledger.run_id -> agent_runs.run_id`

5. Run the metadata tests and confirm they fail because DB modules/models are missing:

```bash
python -m pytest tests/test_db_metadata.py -v
```

6. Add `backend/app/db/base.py`:

- Define SQLAlchemy 2.x `DeclarativeBase`.
- Add a stable naming convention to `MetaData` for indexes, unique constraints, check constraints, foreign keys, and primary keys.

7. Add `backend/app/models/runtime.py`:

- Use SQLAlchemy 2.x typed ORM with `Mapped[...]` and `mapped_column(...)`.
- Use UUID primary keys with `uuid.uuid4`.
- Use PostgreSQL `UUID(as_uuid=True)` and `JSONB`.
- Use timezone-aware timestamps with `DateTime(timezone=True)` and `func.now()`.
- Keep model classes focused on schema only; do not add repository methods.
- Avoid an ORM attribute named `metadata`.

8. Export models in `backend/app/models/__init__.py`.

9. Re-run metadata tests and make them pass:

```bash
python -m pytest tests/test_db_metadata.py -v
```

10. Add `backend/app/db/session.py`:

- Load settings via `get_settings()`.
- Create sync engine with `create_engine(settings.database_url, pool_pre_ping=True)`.
- Create `SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)`.
- Add `get_db()` generator that yields a session and closes it in `finally`.

11. Add `tests/test_alembic_config.py` before Alembic implementation:

- Assert `alembic.ini` exists.
- Assert Alembic script location is `alembic`.
- Assert importing Alembic env/metadata path can access `Base.metadata` with the 7 tables.

12. Run Alembic config test and confirm it fails before adding Alembic files:

```bash
python -m pytest tests/test_alembic_config.py -v
```

13. Add `alembic.ini`:

- `script_location = alembic`
- Keep logging minimal.
- Do not hardcode production secrets.

14. Add `alembic/env.py`:

- Import `backend.app.models.runtime` so metadata is populated.
- Import `Base` from `backend.app.db.base`.
- Import `get_settings` from `backend.app.core.config`.
- Set `target_metadata = Base.metadata`.
- In online migration, set URL from `get_settings().database_url`.
- Support offline migration by configuring with the same URL.

15. Add migration `alembic/versions/0001_create_core_runtime_tables.py`:

- Set `revision = "0001_create_core_runtime_tables"`.
- Set `down_revision = None`.
- In `upgrade()`, create the 7 core runtime tables.
- Add `JSONB`, UUID primary keys, timestamps, foreign keys, indexes, and `action_ledger.idempotency_key` uniqueness.
- In `downgrade()`, drop tables in reverse dependency order.

16. Re-run focused tests:

```bash
python -m pytest tests/test_db_metadata.py tests/test_alembic_config.py -v
```

17. Update README with migration commands:

```bash
docker compose up -d postgres
python -m alembic upgrade head
python -m alembic current
```

18. Run full verification:

```bash
python -m pip install -e ".[dev]"
python -m pytest
docker compose up -d postgres
python -m alembic upgrade head
python -m alembic current
docker compose config
git status --short
```

19. Inspect tracked and staged files before commit:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, and Docker volumes are not tracked.

## 6. Testing Plan

- Unit/static tests:
  - `tests/test_db_metadata.py` verifies table set, key columns, representative foreign keys, and `action_ledger.idempotency_key` uniqueness.
  - `tests/test_alembic_config.py` verifies Alembic config and metadata import path.
- Existing regression tests:
  - `tests/test_health.py` must still pass.
- Integration verification:
  - Start Docker PostgreSQL.
  - Run `python -m alembic upgrade head`.
  - Run `python -m alembic current`.

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add postgres schema baseline
```

Expected commands:

```bash
git status --short
git add pyproject.toml .env.example README.md alembic.ini alembic backend tests docs/specs/002-postgresql-schema-baseline.md docs/plans/002-postgresql-schema-baseline-plan.md
git status --short
git commit -m "feat: add postgres schema baseline"
git push -u origin task2
```

After review, merge the task branch back into the target development branch.

## 9. Out-of-scope Changes

- Do not implement repositories.
- Do not implement CRUD APIs.
- Do not implement Redis services.
- Do not implement Tool Gateway.
- Do not implement Mock World.
- Do not implement Action Ledger writer.
- Do not add benchmark, world fixture, or failure injection tables.
- Do not add LangGraph workflow or agent code.
- Do not commit `.env`, secrets, caches, virtual environments, generated logs, or database volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/002-postgresql-schema-baseline.md`.
- [ ] Work happened on a dedicated Task 002 branch.
- [ ] Scope stayed limited to SQLAlchemy/Alembic/schema infrastructure.
- [ ] No repository, CRUD API, Tool Gateway, Redis service, benchmark table, or business logic was added.
- [ ] The 7 core runtime tables exist in metadata and migration.
- [ ] Alembic reads app settings for `database_url`.
- [ ] `action_ledger.idempotency_key` is unique.
- [ ] `python -m pytest` passed.
- [ ] `python -m alembic upgrade head` passed against Docker PostgreSQL.
- [ ] `python -m alembic current` showed the head revision.
- [ ] README migration commands are accurate.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] Commit message is `feat: add postgres schema baseline`.
- [ ] Push to the Task 002 branch succeeded.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Verification commands and results.
- Alembic upgrade/current output.
- Docker Compose status or limitations.
- Commit hash.
- Push target branch.
- Any deviations from the spec or plan.
- Any recommended follow-up, especially for Task 003 repository layer.
