# Plan: 004 Redis Runtime Services

## 1. Spec Reference

Spec file:

```text
docs/specs/004-redis-runtime-services.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from Task 003 repository baseline.
- Work happens on a dedicated `task4` branch.
- Existing config includes `backend/app/core/config.py` with `redis_url`.
- Existing Docker Compose includes a Redis service named `redis`.
- No Redis runtime package exists yet.
- The project currently uses synchronous SQLAlchemy and synchronous repositories, so Task 004 should use synchronous redis-py.

## 3. Files to Add

- `backend/app/runtime/__init__.py` - exports runtime service classes.
- `backend/app/runtime/redis_client.py` - configured synchronous Redis client.
- `backend/app/runtime/keys.py` - Redis key namespace helper.
- `backend/app/runtime/cache.py` - JSON cache service.
- `backend/app/runtime/locks.py` - token-safe distributed lock manager.
- `backend/app/runtime/rate_limit.py` - fixed-window rate limiter.
- `backend/app/runtime/progress.py` - run progress stream service.
- `tests/integration/test_redis_runtime.py` - real Redis integration tests.

## 4. Files to Modify

- `pyproject.toml` - add `redis>=5.0,<6.0`.
- `README.md` - add Redis runtime test commands.
- `.env.example` - modify only if `REDIS_URL` is missing or inconsistent.

## 5. Implementation Steps

1. Confirm branch and baseline:

```bash
git status --short --branch
rg --files backend/app docs/specs docs/plans
```

Expected:

- Branch is `task4`.
- Task 003 repository files exist.
- `backend/app/runtime` does not exist yet.

2. Add dependency to `pyproject.toml`:

```toml
"redis>=5.0,<6.0",
```

3. Write failing integration tests in `tests/integration/test_redis_runtime.py`.

Test setup requirements:

- Use `get_redis_client()`.
- Call `ping()` at test start so Redis connectivity failure is explicit.
- Use `RedisKeyBuilder(prefix="weekendpilot:test")`.
- Clean only keys under the test prefix before and after each test.
- Do not use FakeRedis.

Test cases:

- JSON cache stores, reads, deletes, and expires values.
- Lock acquire returns token; second acquire fails; wrong release fails; correct release succeeds.
- Rate limiter allows first N calls and denies N+1 inside the same window.
- Progress stream appends events and reads them in order.
- Progress stream read with no events returns `[]`.

4. Run focused test and confirm failure before implementation:

```bash
docker compose up -d redis
python -m pytest tests/integration/test_redis_runtime.py -v
```

5. Implement `backend/app/runtime/redis_client.py`:

- Import `Redis` from `redis`.
- Load URL from `get_settings().redis_url`.
- Implement `get_redis_client() -> Redis`.
- Use `Redis.from_url(settings.redis_url, decode_responses=True)`.

6. Implement `backend/app/runtime/keys.py`:

- Add `RedisKeyBuilder`.
- Constructor accepts `prefix: str`.
- Add `from_settings()` classmethod that builds a default prefix from app name and environment, for example `weekendpilot:{app_env}`.
- Add methods:
  - `cache(name: str) -> str`
  - `lock(name: str) -> str`
  - `rate_limit(name: str) -> str`
  - `progress(run_id: str) -> str`
- Do not include secrets or raw user text in keys.

7. Implement `backend/app/runtime/cache.py`:

- Add `JsonRedisCache`.
- Constructor accepts Redis client and key builder.
- `set_json(key, value, ttl_seconds)` serializes with `json.dumps` and uses `SET EX`.
- `get_json(key)` returns `None` when missing and deserializes with `json.loads`.
- `delete(key)` returns Redis delete count.

8. Implement `backend/app/runtime/locks.py`:

- Add `RedisLockManager`.
- `acquire(name, ttl_seconds)` generates token with `uuid.uuid4().hex`.
- Use Redis `SET key token NX EX ttl_seconds`.
- Return token if acquired, otherwise `None`.
- `release(name, token)` uses Lua compare-and-delete so a caller cannot delete another holder's lock.
- Return `True` only when deletion happened.

9. Implement `backend/app/runtime/rate_limit.py`:

- Add frozen dataclass `RateLimitDecision`.
- Add `FixedWindowRateLimiter`.
- `allow(name, limit, window_seconds)`:
  - `INCR` the rate-limit key.
  - Set `EXPIRE` only when count is first created.
  - Allow when count is `<= limit`.
  - Remaining should never be negative.
  - Reset TTL should use Redis `TTL`, normalized to `0` if Redis returns negative values.

10. Implement `backend/app/runtime/progress.py`:

- Add frozen dataclass `ProgressEvent`.
- Add `RedisProgressStream`.
- `append(run_id, event_type, payload, maxlen=1000)`:
  - Use `XADD`.
  - Store fields `event_type` and `payload_json`.
  - Use approximate maxlen trimming.
- `read(run_id, last_id="0-0", count=100)`:
  - Use `XRANGE`.
  - If `last_id != "0-0"`, read strictly after the known id.
  - Return events in Redis order.
  - Parse `payload_json` with `json.loads`.

11. Export public classes/functions in `backend/app/runtime/__init__.py`.

12. Run focused Redis tests:

```bash
python -m pytest tests/integration/test_redis_runtime.py -v
```

13. Run full tests:

```bash
python -m pytest
```

14. Update README with Redis runtime test commands:

```bash
docker compose up -d redis
python -m pytest tests/integration/test_redis_runtime.py -v
```

15. Run final verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d redis
python -m pytest
docker compose config
git status --short
```

16. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, generated logs, and Docker volumes are not tracked.

## 6. Testing Plan

- Existing tests continue to pass:
  - health test
  - DB metadata test
  - Alembic config test
  - repository integration test
- New Redis integration tests:
  - cache set/get/delete/TTL
  - lock acquire/conflict/token-safe release
  - fixed-window rate limiting
  - progress stream append/read order
  - empty progress stream read
- Tests must use real Redis from Docker Compose.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d redis
python -m pytest
docker compose config
git status --short
```

If Redis cannot start, stop and report the blocker. Do not replace integration tests with FakeRedis.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add redis runtime services
```

Expected commands:

```bash
git status --short
git add pyproject.toml README.md backend/app/runtime tests/integration/test_redis_runtime.py docs/specs/004-redis-runtime-services.md docs/plans/004-redis-runtime-services-plan.md
git status --short
git commit -m "feat: add redis runtime services"
git push -u origin task4
```

Task 4 should be merged only after review.

## 9. Out-of-scope Changes

- Do not implement Tool Gateway.
- Do not implement Mock World.
- Do not implement APIs.
- Do not implement business services.
- Do not implement LangGraph or agents.
- Do not modify PostgreSQL schema or migrations.
- Do not store durable business facts in Redis.
- Do not implement Redis-backed repositories.
- Do not commit `.env`, secrets, caches, virtual environments, generated logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task4`.
- [ ] Spec and plan exist in `docs/specs` and `docs/plans`.
- [ ] Redis client uses configured `redis_url`.
- [ ] Runtime package exposes cache, lock, rate limiter, and progress stream.
- [ ] Lock release is token-safe.
- [ ] Rate limiter is fixed-window and deterministic.
- [ ] Progress stream payloads are JSON.
- [ ] Integration tests use real Redis.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] No secrets are committed.
- [ ] Commit message is `feat: add redis runtime services`.
- [ ] Push to `origin/task4` succeeds.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Redis integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviations from this spec or plan.
