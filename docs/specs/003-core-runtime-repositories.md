# Spec: 003 Core Runtime Repositories

## 1. Goal

Build the first core PostgreSQL repository layer for WeekendPilot so future Tool Gateway, Execution Workflow, Memory Retriever, and run tracking work can persist durable state through stable, testable interfaces.

After this task is complete, the system should have repositories for the core write path: users, agent runs, memory items, tool events, and action ledger records. Repositories must accept a SQLAlchemy `Session`, return ORM instances, and leave transaction boundaries to the caller.

## 2. Project Context

Task 002 established the PostgreSQL schema baseline, including SQLAlchemy models, Alembic migration, synchronous DB session infrastructure, and Docker PostgreSQL verification.

Task 003 builds on that schema by adding repository interfaces only. It must not implement business services, API endpoints, Tool Gateway, Execution Workflow, Redis services, LangGraph, or agents. The repository layer is a deterministic building block for later workflow and tool execution tasks.

## 3. Requirements

- Create a repository package under `backend/app/repositories`.
- Add repositories for:
  - `users`
  - `agent_runs`
  - `memory_items`
  - `tool_events`
  - `action_ledger`
- Repository constructors must accept an injected SQLAlchemy `Session`.
- Repository methods must return SQLAlchemy ORM instances or `None`.
- Repository methods must not call `commit()` or `rollback()`.
- Repository methods may call `add()`, `flush()`, `refresh()`, and `select()`.
- Add user creation and lookup by `user_id` and `external_id`.
- Add agent run creation, lookup by `run_id`, and status update.
- Add memory item creation, lookup by `memory_id`, and active memory listing for a user.
- Add tool event creation, lookup by `event_id`, and list-by-run query.
- Add action ledger creation, lookup by `action_id`, lookup by `idempotency_key`, and status/result/error update.
- Add real PostgreSQL integration tests for all repositories.
- Run Alembic migration before repository integration tests.
- Keep `.env`, API keys, tokens, and secrets out of git.

## 4. Non-goals

- Do not implement FastAPI endpoints.
- Do not implement business service layer.
- Do not implement Tool Gateway.
- Do not implement Execution Workflow.
- Do not implement Redis runtime logic.
- Do not implement LangGraph or agents.
- Do not add repositories for `plans` or `user_profiles`.
- Do not add new database tables or migrations unless Task 002 has a blocking defect.
- Do not change Task 002 schema semantics.
- Do not add Pydantic DTOs for repository returns.

## 5. Interfaces and Contracts

### Inputs

- SQLAlchemy `Session`
- ORM creation fields
- UUID identifiers
- Idempotency key string

### Outputs

- SQLAlchemy ORM instances
- `None` for missing records
- Lists of SQLAlchemy ORM instances for scoped list queries

### Repository Classes

Expected modules and classes:

```text
backend/app/repositories/users.py -> UserRepository
backend/app/repositories/runs.py -> AgentRunRepository
backend/app/repositories/memory.py -> MemoryItemRepository
backend/app/repositories/tool_events.py -> ToolEventRepository
backend/app/repositories/action_ledger.py -> ActionLedgerRepository
```

### Transaction Contract

```text
Repositories may flush and refresh.
Repositories must not commit.
Repositories must not rollback.
Callers own commit, rollback, and transaction scope.
```

### Required Methods

`UserRepository`:

```text
create(external_id: str | None, display_name: str | None) -> User
get_by_id(user_id: UUID) -> User | None
get_by_external_id(external_id: str) -> User | None
```

`AgentRunRepository`:

```text
create(user_id, case_id, agent_version, prompt_version, tool_profile, world_profile, failure_profile, status, metadata_json) -> AgentRun
get_by_id(run_id: UUID) -> AgentRun | None
update_status(run_id: UUID, status: str) -> AgentRun | None
```

`MemoryItemRepository`:

```text
create(user_id, memory_type, key, value_json, text, confidence, source_run_id, source_langsmith_trace_id, expires_at, status) -> MemoryItem
get_by_id(memory_id: UUID) -> MemoryItem | None
list_active_for_user(user_id: UUID) -> list[MemoryItem]
```

Active memory means `status == "active"` and `expires_at` is either `NULL` or later than the current database time.

`ToolEventRepository`:

```text
create(run_id, tool_name, tool_type, provider, request_json, response_json, error_json, status, cache_hit, latency_ms, langsmith_trace_id) -> ToolEvent
get_by_id(event_id: UUID) -> ToolEvent | None
list_for_run(run_id: UUID) -> list[ToolEvent]
```

`ActionLedgerRepository`:

```text
create(run_id, action_type, target_id, idempotency_key, status, request_json, response_json=None, error_json=None) -> ActionLedger
get_by_id(action_id: UUID) -> ActionLedger | None
get_by_idempotency_key(idempotency_key: str) -> ActionLedger | None
update_status(action_id: UUID, status: str, response_json=None, error_json=None) -> ActionLedger | None
```

## 6. Observability

This task does not add logging, tracing, or LangSmith integration.

It enables future observability by making `agent_runs`, `tool_events`, and `action_ledger` writable through stable repository interfaces.

## 7. Failure Handling

- Missing records must return `None`.
- Database integrity errors must propagate to the caller.
- Duplicate `action_ledger.idempotency_key` should be handled by caller lookup-before-create or by catching the propagated integrity error.
- Repository methods must not hide database failures.
- Repository methods must not rollback caller-managed transactions.
- Repository methods must not commit partial work.

## 8. Acceptance Criteria

- [ ] Repository package exists under `backend/app/repositories`.
- [ ] Five core repository classes are implemented.
- [ ] Repository classes use injected SQLAlchemy `Session`.
- [ ] Repository methods return ORM instances or `None`.
- [ ] Repository methods do not call `commit()` or `rollback()`.
- [ ] `ActionLedgerRepository` supports lookup by `idempotency_key`.
- [ ] Integration tests exercise all repository classes against real PostgreSQL.
- [ ] Integration tests verify repositories do not self-commit.
- [ ] `python -m alembic upgrade head` passes before integration tests.
- [ ] `python -m pytest` passes.
- [ ] Work happens on `task3` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
git switch task2
git switch -c task3
python -m pip install -e ".[dev]"
docker compose up -d postgres
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

If PostgreSQL cannot start or Alembic migration fails, stop and report the blocker. Do not replace real PostgreSQL integration tests with SQLite.

## 10. Expected Commit

```text
feat: add core runtime repositories
```

## 11. Notes for the Implementer

If Task 002 schema files are missing, stop and report the branch/base mismatch.

Keep this task focused on repositories. APIs, service layer, Tool Gateway, Execution Workflow, Redis runtime logic, LangGraph, agents, `plans` repository, and `user_profiles` repository belong to later tasks.
