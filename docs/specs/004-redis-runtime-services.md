# Spec: 004 Redis Runtime Services

## 1. Goal

Establish the minimal Redis runtime layer for WeekendPilot so future Tool Gateway, workflow progress reporting, distributed locks, and rate limiting can use deterministic infrastructure.

After this task is complete, the system should have Redis-backed JSON cache, distributed lock, fixed-window rate limiter, and run progress stream services. These services must be verified against the real Docker Redis service.

## 2. Project Context

Task 001 introduced the Redis Docker Compose service and `redis_url` configuration. Tasks 002 and 003 established PostgreSQL schema and core repositories. Task 004 adds Redis runtime primitives only.

Redis must remain a runtime layer for short-lived cache, progress events, locks, and rate limits. Durable business state must remain in PostgreSQL.

## 3. Requirements

- Add the `redis` Python dependency.
- Use `backend.app.core.config.Settings.redis_url` to create a synchronous Redis client.
- Add a runtime package under `backend/app/runtime`.
- Add a key namespace helper to avoid collisions between app environments and tests.
- Implement JSON cache:
  - set value with TTL
  - get value
  - delete value
  - return `None` for missing keys
- Implement distributed lock:
  - acquire with generated token and TTL
  - fail to acquire when a lock already exists
  - release only when token matches
  - wrong token must not delete the lock
- Implement fixed-window rate limiter:
  - return allow/deny decision
  - return remaining count
  - return reset TTL
- Implement run progress stream:
  - append event for `run_id`
  - read events after `last_id`
  - store payload as JSON string
- Add real Redis integration tests.
- Update README with Redis runtime test prerequisites.
- Keep `.env`, API keys, tokens, and secrets out of git.

## 4. Non-goals

- Do not implement Tool Gateway.
- Do not implement Mock World.
- Do not implement business workflow.
- Do not implement LangGraph or agents.
- Do not use Redis as durable fact storage.
- Do not implement Redis-backed repositories.
- Do not implement pub/sub.
- Do not implement sliding-window rate limiting.
- Do not implement lock auto-renew.
- Do not implement cache stampede protection.
- Do not modify PostgreSQL schema or migrations.

## 5. Interfaces and Contracts

### Inputs

- `REDIS_URL`
- Redis key names
- JSON-serializable payloads
- `run_id`
- lock name
- lock token
- rate-limit name, limit, and window

### Outputs

- JSON cache values or `None`
- lock token string or `None`
- rate-limit decision object
- progress stream event objects

### Public Interfaces

Expected modules and public objects:

```text
backend.app.runtime.redis_client.get_redis_client
backend.app.runtime.keys.RedisKeyBuilder
backend.app.runtime.cache.JsonRedisCache
backend.app.runtime.locks.RedisLockManager
backend.app.runtime.rate_limit.FixedWindowRateLimiter
backend.app.runtime.rate_limit.RateLimitDecision
backend.app.runtime.progress.RedisProgressStream
backend.app.runtime.progress.ProgressEvent
```

### Cache Contract

```text
set_json(key: str, value: dict | list | str | int | float | bool | None, ttl_seconds: int) -> None
get_json(key: str) -> dict | list | str | int | float | bool | None
delete(key: str) -> int
```

### Lock Contract

```text
acquire(name: str, ttl_seconds: int) -> str | None
release(name: str, token: str) -> bool
```

### Rate Limit Contract

```text
allow(name: str, limit: int, window_seconds: int) -> RateLimitDecision
```

`RateLimitDecision` fields:

```text
allowed: bool
remaining: int
reset_after_seconds: int
```

### Progress Stream Contract

```text
append(run_id: str, event_type: str, payload: dict, maxlen: int = 1000) -> str
read(run_id: str, last_id: str = "0-0", count: int = 100) -> list[ProgressEvent]
```

`ProgressEvent` fields:

```text
event_id: str
event_type: str
payload: dict
```

## 6. Observability

This task must not add LangSmith integration or PostgreSQL writes.

The Redis progress stream is a runtime progress channel for short-lived UI/CLI feedback. It is not a durable audit log and must not replace PostgreSQL `tool_events` or `action_ledger`.

## 7. Failure Handling

- Redis unavailable should surface connection errors.
- Invalid JSON payloads should fail during serialization.
- Expired cache keys should behave as missing.
- Expired lock keys should be acquirable again.
- Lock release with the wrong token must return `False`.
- Rate-limit decisions must be deterministic inside a fixed window.
- Progress stream reads with no events must return an empty list.

## 8. Acceptance Criteria

- [ ] `redis` dependency is added.
- [ ] Redis client uses configured `redis_url`.
- [ ] Runtime key namespace helper exists.
- [ ] JSON cache works with TTL, get, delete, and missing-key behavior.
- [ ] Lock manager protects release with token comparison.
- [ ] Fixed-window rate limiter returns allowed, remaining, and reset TTL.
- [ ] Progress stream appends and reads JSON payload events.
- [ ] Integration tests use real Docker Redis.
- [ ] `docker compose up -d redis` is part of verification.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` validates.
- [ ] Work happens on `task4` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
git switch task3
git switch -c task4
python -m pip install -e ".[dev]"
docker compose up -d redis
python -m pytest
docker compose config
git status --short
```

If Redis cannot start, stop and report the blocker. Do not replace real Redis integration tests with FakeRedis.

## 10. Expected Commit

```text
feat: add redis runtime services
```

## 11. Notes for the Implementer

If Task 003 repository files are missing, stop and report the branch/base mismatch.

Do not connect these Redis runtime services to Tool Gateway yet. Task 004 only creates primitives and tests them.
