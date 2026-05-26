# Spec: 069 Playwright E2E Rate-Limit Isolation v0

## 1. Goal

Fix the current full Playwright E2E stability gap where browser tests share the same Redis Tool Gateway rate-limit counters during one E2E server run.

The observed failure is not a frontend click or assertion problem. Earlier browser tests consume the shared `search_poi` rate-limit key, then the later clarification-flow test can receive `rate_limited` tool events and remain in `awaiting_clarification` instead of reaching `awaiting_confirmation`. After this task, full Playwright E2E must be stable without weakening the real Tool Gateway rate-limit contract.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines Redis as the runtime layer for cache, progress events, locks, and rate limits, and requires the Tool Gateway to support rate limits. It also makes Web UI and browser-level verification part of the demo and V1 review path.

This task maps to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`. Although the roadmap’s next default direction is broader evaluation and observability infrastructure, this is the smallest higher-priority convergence task because the full Playwright suite is currently not reliable enough to serve as V1 release evidence.

Current repository facts:

- Task chain is continuous through `068`.
- `docs/specs` and `docs/plans` contain matching files from `001` through `068`.
- Latest commit is `4a6b707 feat: close richer web ui v1 surface`, matching task `068`.
- Current branch is `codex/richer-web-ui-v1-closure`.
- Existing dirty or untracked local files are unrelated and must not be staged.

## 3. Requirements

- Add a reusable runtime rate-limiter wrapper that scopes rate-limit names before delegating to the existing `FixedWindowRateLimiter`.
- The wrapper must preserve the existing fixed-window behavior within one scope.
- The wrapper must isolate the same tool name across different scopes.
- Use the scoped rate limiter for Web demo workflows started through `DemoWorkflowService`.
- The demo scope must be derived from the persisted demo user identity, using `external_user_id` when available.
- The Redis key component must not expose raw `external_user_id`; use a deterministic short hash or equivalent sanitized opaque scope.
- Apply the same demo scope to:
  - initial planning runs
  - clarification continuation runs
  - replan continuation runs
  - confirmation/execution write-tool runs
- Keep direct Tool Gateway behavior unchanged when callers pass the base `FixedWindowRateLimiter`.
- Keep benchmark behavior unchanged; benchmark case isolation already has its own wrapper and must continue to pass.
- Do not change default `ToolRateLimit` values:
  - `search_poi`: `limit=10`, `window_seconds=60`
  - `reserve_restaurant`: `limit=3`, `window_seconds=60`
- Do not add a test-only API route, public request field, Playwright-only backend branch, or Redis flush workaround.
- Add regression tests proving scoped rate limits isolate two demo users while preserving limits within a scope.
- The full Playwright E2E suite must pass after the fix.

## 4. Non-goals

- Do not disable Tool Gateway rate limits.
- Do not increase the default rate-limit thresholds.
- Do not change workflow routing, recovery policy, clarification policy, benchmark grading, benchmark suite membership, or frontend UI behavior.
- Do not add public API fields, headers, admin endpoints, or test-only routes.
- Do not make Playwright flush Redis between tests.
- Do not modify Docker Compose, Alembic migrations, database schema, or frontend Playwright project matrix.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, Playwright reports, `frontend/dist/`, or unrelated local files.

## 5. Interfaces and Contracts

### Inputs

- Existing `DemoStartRunRequest.external_user_id`.
- Existing persisted `User.external_id` for clarification, replan, and confirmation flows.
- Existing Tool Gateway rate-limit names such as:
  - `tool:mock_world:search_poi`
  - `tool:mock_world:reserve_restaurant`

### Outputs

- A scoped rate-limit name passed to the existing base limiter, for example:

```text
demo-user:<opaque-hash>:tool:mock_world:search_poi
demo-user:<opaque-hash>:tool:mock_world:reserve_restaurant
```

- Existing Redis key structure remains owned by `RedisKeyBuilder`, for example:

```text
WeekendPilot:<APP_ENV>:rate-limit:<scoped-rate-limit-name>
```

### Schemas

No public API schema changes are allowed.

Internal contract example:

```json
{
  "base_tool_limit_name": "tool:mock_world:search_poi",
  "demo_scope_source": "external_user_id",
  "scoped_tool_limit_name": "demo-user:<opaque-hash>:tool:mock_world:search_poi",
  "raw_external_user_id_in_redis_key": false
}
```

## 6. Observability

This task does not add new telemetry, LangSmith metadata, benchmark artifacts, frontend panels, or database fields.

Existing Tool Gateway tool events must remain unchanged. A `rate_limited` event should still be recorded when one demo scope exceeds its limit. The intended observable behavior change is that unrelated Web demo users or Playwright tests no longer create cross-test `rate_limited` events through a shared Redis key.

## 7. Failure Handling

- If Redis is unavailable, behavior remains unchanged: the existing runtime dependency fails as before.
- If a demo request has no `external_user_id` and no persisted user external ID, use the existing base limiter rather than inventing a public contract.
- If the same demo user exceeds a tool limit within the window, the Tool Gateway must still return `rate_limited`.
- If two different demo users call the same rate-limited tool within the same window, their limits must not interfere.
- If scope hashing fails unexpectedly, the implementation should fall back to the base limiter only by explicit code path, not by silently producing malformed keys.

## 8. Acceptance Criteria

- [ ] `docs/specs/069-playwright-e2e-rate-limit-isolation-v0.md` exists.
- [ ] `docs/plans/069-playwright-e2e-rate-limit-isolation-v0-plan.md` exists.
- [ ] A reusable scoped rate-limiter wrapper exists in the runtime layer.
- [ ] Scoped limiter tests prove two scopes do not share counters.
- [ ] Scoped limiter tests prove one scope still enforces its own fixed-window limit.
- [ ] Web demo initial runs use a scoped limiter when `external_user_id` is available.
- [ ] Web demo clarification and replan continuations reuse the source user’s scoped limiter.
- [ ] Web demo confirmation/execution uses the same demo user scope for write-tool limits.
- [ ] Redis rate-limit key names do not include raw `external_user_id`.
- [ ] Direct Tool Gateway rate-limit tests still prove the base limiter blocks after the configured limit.
- [ ] The focused clarification Playwright test passes when run alone.
- [ ] The full Playwright E2E suite passes.
- [ ] No public API schema, frontend UI behavior, benchmark suite, or workflow routing changes are introduced.
- [ ] No `.env`, API key, token, secret, generated artifact, or unrelated dirty file is staged.
- [ ] The working tree is clean after commit except for pre-existing unrelated local files.

## 9. Verification Commands

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_redis_runtime.py tests/integration/test_demo_api_gateway.py -q
python -m pytest tests/test_tool_gateway_registry.py tests/integration/test_tool_gateway.py -q
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "continues a vague request through the clarification flow"
npm --prefix frontend run e2e
git diff --check
git status --short
```

## 10. Expected Commit

```text
fix: isolate web demo rate limits
```

## 11. Notes for the Implementer

Do not solve this by sleeping for the 60-second Redis window, flushing Redis, weakening assertions, increasing `search_poi` limits, or mocking the failing browser test. The root cause is shared Redis rate-limit state across independent Web demo users inside one full Playwright run.

Use the existing benchmark `_BenchmarkCaseRateLimiter` pattern as a reference, but keep the implementation narrow and reusable in the runtime layer. Do not refactor benchmark harness unless absolutely necessary.
