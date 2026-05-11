# Plan: 003 Core Runtime Repositories

## 1. Spec Reference

Spec file:

```text
docs/specs/003-core-runtime-repositories.md
```

Related files:

```text
docs/PROJECT_BLUEPRINT.md
docs/specs/002-postgresql-schema-baseline.md
```

## 2. Current Repository Assumptions

- Work starts from Task 002 schema baseline.
- Work happens on a dedicated `task3` branch.
- Existing DB infrastructure:
  - `backend/app/db/session.py`
  - `backend/app/db/base.py`
  - `backend/app/models/runtime.py`
  - `alembic/versions/0001_create_core_runtime_tables.py`
- No repository package exists yet.
- Repository methods should use synchronous SQLAlchemy because Task 002 created sync DB infrastructure.

## 3. Files to Add

- `backend/app/repositories/__init__.py` - exports repository classes.
- `backend/app/repositories/users.py` - `UserRepository`.
- `backend/app/repositories/runs.py` - `AgentRunRepository`.
- `backend/app/repositories/memory.py` - `MemoryItemRepository`.
- `backend/app/repositories/tool_events.py` - `ToolEventRepository`.
- `backend/app/repositories/action_ledger.py` - `ActionLedgerRepository`.
- `tests/integration/test_repositories.py` - real PostgreSQL repository integration tests.

## 4. Files to Modify

- `README.md` - add a short repository integration test prerequisite note if useful.

Do not modify schema, models, or migrations unless a blocking Task 002 defect is found.

## 5. Implementation Steps

1. Confirm branch and baseline:

```bash
git status --short --branch
rg --files backend/app/db backend/app/models alembic docs/specs docs/plans
```

Expected:

- Branch is `task3`.
- Task 002 schema files exist.
- `backend/app/repositories` does not exist yet.

2. Write failing integration tests in `tests/integration/test_repositories.py` before repository implementation.

Test setup requirements:

- Use `SessionLocal` from `backend.app.db.session`.
- Use a pytest fixture that opens a session and transaction for each test.
- Roll back after each test.
- Require the developer to run `python -m alembic upgrade head` before tests.

Test cases:

- User create and get by `external_id`.
- Agent run create, get by id, and status update.
- Memory item create and active listing.
- Tool event create and list by run.
- Action ledger create, lookup by `idempotency_key`, and status update.
- Repository methods do not self-commit: create a record, roll back, then confirm it is not visible from a new session.

3. Run the new test file and confirm it fails because repositories are missing:

```bash
python -m pytest tests/integration/test_repositories.py -v
```

4. Create `backend/app/repositories/__init__.py` and export:

```text
UserRepository
AgentRunRepository
MemoryItemRepository
ToolEventRepository
ActionLedgerRepository
```

5. Implement `UserRepository` in `backend/app/repositories/users.py`:

- Constructor: `__init__(self, session: Session)`.
- `create(external_id: str | None, display_name: str | None) -> User`.
- `get_by_id(user_id: UUID) -> User | None`.
- `get_by_external_id(external_id: str) -> User | None`.
- Use `select(User)` for lookups.
- `create` should `add`, `flush`, `refresh`, and return the ORM instance.
- Do not call `commit()` or `rollback()`.

6. Implement `AgentRunRepository` in `backend/app/repositories/runs.py`:

- Constructor receives `Session`.
- `create(...) -> AgentRun`.
- `get_by_id(run_id: UUID) -> AgentRun | None`.
- `update_status(run_id: UUID, status: str) -> AgentRun | None`.
- `update_status` should return `None` if the run is missing.
- Update only status in this task.

7. Implement `MemoryItemRepository` in `backend/app/repositories/memory.py`:

- Constructor receives `Session`.
- `create(...) -> MemoryItem`.
- `get_by_id(memory_id: UUID) -> MemoryItem | None`.
- `list_active_for_user(user_id: UUID) -> list[MemoryItem]`.
- Active filter: `MemoryItem.status == "active"` and `MemoryItem.expires_at.is_(None) OR MemoryItem.expires_at > func.now()`.
- Order active memory deterministically by `created_at`.

8. Implement `ToolEventRepository` in `backend/app/repositories/tool_events.py`:

- Constructor receives `Session`.
- `create(...) -> ToolEvent`.
- `get_by_id(event_id: UUID) -> ToolEvent | None`.
- `list_for_run(run_id: UUID) -> list[ToolEvent]`.
- Order events deterministically by `created_at`.

9. Implement `ActionLedgerRepository` in `backend/app/repositories/action_ledger.py`:

- Constructor receives `Session`.
- `create(...) -> ActionLedger`.
- `get_by_id(action_id: UUID) -> ActionLedger | None`.
- `get_by_idempotency_key(idempotency_key: str) -> ActionLedger | None`.
- `update_status(action_id: UUID, status: str, response_json=None, error_json=None) -> ActionLedger | None`.
- `update_status` should only update fields passed by the caller.

10. Re-run focused integration tests:

```bash
python -m pytest tests/integration/test_repositories.py -v
```

11. Re-run full test suite:

```bash
python -m pytest
```

12. Update README only if the integration test workflow is not already clear:

```bash
docker compose up -d postgres
python -m alembic upgrade head
python -m pytest
```

13. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

14. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, generated logs, and Docker volumes are not tracked.

## 6. Testing Plan

- Existing tests:
  - `tests/test_health.py`
  - `tests/test_db_metadata.py`
  - `tests/test_alembic_config.py`
- New integration tests:
  - User create/get.
  - Agent run create/status update.
  - Memory active listing.
  - Tool event create/list.
  - Action ledger idempotency lookup/update.
  - Transaction rollback proves repositories do not self-commit.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

If PostgreSQL cannot start or Alembic migration fails, stop and report the blocker. Do not replace real PostgreSQL integration tests with SQLite.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add core runtime repositories
```

Expected commands:

```bash
git status --short
git add backend/app/repositories tests/integration README.md docs/specs/003-core-runtime-repositories.md docs/plans/003-core-runtime-repositories-plan.md
git status --short
git commit -m "feat: add core runtime repositories"
git push -u origin task3
```

Task 3 should be merged only after review.

## 9. Out-of-scope Changes

- Do not implement APIs.
- Do not implement services.
- Do not implement Tool Gateway.
- Do not implement Execution Workflow.
- Do not implement Redis runtime logic.
- Do not implement LangGraph or agents.
- Do not add new tables or migrations.
- Do not create repositories for `plans` or `user_profiles`.
- Do not commit `.env`, secrets, caches, virtual environments, generated logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task3`.
- [ ] Spec and plan exist in `docs/specs` and `docs/plans`.
- [ ] Scope is limited to repository layer.
- [ ] Five repository classes exist.
- [ ] Repositories use injected `Session`.
- [ ] Repositories do not call `commit()` or `rollback()`.
- [ ] Repositories return ORM instances.
- [ ] Integration tests use real PostgreSQL.
- [ ] `python -m alembic upgrade head` passed.
- [ ] `python -m pytest` passed.
- [ ] No secrets are committed.
- [ ] Commit message is `feat: add core runtime repositories`.
- [ ] Push to `origin/task3` succeeds.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Verification command outputs.
- Alembic upgrade result.
- pytest result.
- Commit hash.
- Push branch.
- Any deviations from this spec or plan.
