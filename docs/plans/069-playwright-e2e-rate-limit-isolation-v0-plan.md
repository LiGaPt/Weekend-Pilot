# Plan: 069 Playwright E2E Rate-Limit Isolation v0

## 1. Spec Reference

Spec file:

```text
docs/specs/069-playwright-e2e-rate-limit-isolation-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/richer-web-ui-v1-closure`.
- Current latest commit is `4a6b707 feat: close richer web ui v1 surface`, matching task `068`.
- `docs/specs` and `docs/plans` are continuous and slug-matched from `001` through `068`.
- Full Playwright E2E is known to be unstable because shared Redis rate-limit keys can make `search_poi` return `rate_limited` in later tests.
- Focused clarification E2E passes when run alone, which confirms this is shared-suite state rather than the clarification UI itself.
- `backend/app/benchmark/harness.py` already has a private `_BenchmarkCaseRateLimiter` wrapper that proves scoped delegation is an accepted local pattern.
- Pre-existing unrelated local changes exist at `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/`, and `qc`; do not stage them.

## 3. Files to Add

- `docs/specs/069-playwright-e2e-rate-limit-isolation-v0.md` - task specification.
- `docs/plans/069-playwright-e2e-rate-limit-isolation-v0-plan.md` - implementation plan.

## 4. Files to Modify

- `backend/app/runtime/rate_limit.py` - add the reusable scoped rate-limiter wrapper.
- `backend/app/runtime/__init__.py` - export the new wrapper.
- `backend/app/demo/service.py` - apply scoped rate limits to start, clarify, replan, and confirm execution paths.
- `tests/integration/test_redis_runtime.py` - add scoped limiter integration tests.
- `tests/integration/test_demo_api_gateway.py` - add demo-level regression for cross-user rate-limit isolation.

## 5. Implementation Steps

1. Create the implementation branch from current `HEAD`.

```bash
git switch -c codex/playwright-e2e-rate-limit-isolation-v0
```

2. Write the failing runtime integration tests first in `tests/integration/test_redis_runtime.py`.

Add tests for these behaviors:

- `ScopedRateLimiter(base, "scope-a").allow("tool:mock_world:search_poi", limit=1, window_seconds=60)` allows once and denies the second call in the same scope.
- `ScopedRateLimiter(base, "scope-b")` still allows the same tool name after `scope-a` has exhausted its limit.
- The Redis keys created by the scoped limiter do not contain an unsanitized raw namespace string.

Run:

```bash
python -m pytest tests/integration/test_redis_runtime.py::test_scoped_rate_limiter_isolates_same_name_by_namespace -q
```

Expected before implementation: fail because `ScopedRateLimiter` does not exist.

3. Write the failing demo API regression in `tests/integration/test_demo_api_gateway.py`.

Add a test named:

```text
test_demo_rate_limits_are_scoped_by_external_user
```

Test shape:

- Monkeypatch `backend.app.tool_gateway.registry._read_rate_limit` so `search_poi` uses `ToolRateLimit(limit=2, window_seconds=60)`.
- Start one explicit happy-path demo run for external user A.
- Start a second explicit happy-path demo run for external user B within the same Redis window.
- Assert both responses are `200`.
- Assert both bodies end in `awaiting_confirmation`.
- Query tool events for both run IDs and assert neither run has `search_poi` with status `rate_limited`.

Run:

```bash
python -m pytest tests/integration/test_demo_api_gateway.py::test_demo_rate_limits_are_scoped_by_external_user -q
```

Expected before implementation: second run fails to reach `awaiting_confirmation` or records a `rate_limited` `search_poi`.

4. Implement `ScopedRateLimiter` in `backend/app/runtime/rate_limit.py`.

Required behavior:

- Subclass `FixedWindowRateLimiter`, following the existing `_BenchmarkCaseRateLimiter` delegation pattern.
- Constructor accepts:
  - `base: FixedWindowRateLimiter`
  - `namespace: str`
- `allow(name, limit, window_seconds)` delegates to `base.allow(scoped_name, limit, window_seconds)`.
- Normalize/hash the namespace so raw external IDs are not embedded in Redis keys.
- Preserve the original `RateLimitDecision` returned by the base limiter.
- Do not modify `FixedWindowRateLimiter.allow`.

5. Export the wrapper in `backend/app/runtime/__init__.py`.

Add `ScopedRateLimiter` to imports and `__all__`.

6. Apply scoped limiting in `backend/app/demo/service.py`.

Add a private helper:

```text
_rate_limiter_for_external_user(external_user_id: str | None) -> FixedWindowRateLimiter
```

Required behavior:

- If `external_user_id` is present, return `ScopedRateLimiter(self.rate_limiter, f"demo-user:{external_user_id}")`.
- If `external_user_id` is missing, return `self.rate_limiter` to preserve existing anonymous behavior.
- The wrapper itself must ensure the raw external ID does not appear in Redis keys.

7. Use the scoped limiter in `start_run`.

When constructing `WeekendPilotWorkflowDependencies`, pass:

```text
rate_limiter=self._rate_limiter_for_external_user(request.external_user_id)
```

Do not change the request model or workflow request fields.

8. Use the scoped limiter in `clarify_run` and `replan_run`.

After loading the persisted user, pass:

```text
rate_limiter=self._rate_limiter_for_external_user(user.external_id)
```

This keeps a conversation’s continuation runs in the same demo user scope while isolating unrelated Playwright users.

9. Use the scoped limiter in `confirm_run`.

Load the run’s persisted user or reuse an existing helper, then pass the scoped limiter into the `ToolGateway` used by deterministic execution.

A minimal implementation is to update `_gateway(...)` so it accepts an optional `rate_limiter` parameter and defaults to `self.rate_limiter` when omitted. In `confirm_run`, call `_gateway(..., rate_limiter=self._rate_limiter_for_run_user(run))`.

10. Re-run the focused tests from steps 2 and 3.

```bash
python -m pytest tests/integration/test_redis_runtime.py::test_scoped_rate_limiter_isolates_same_name_by_namespace tests/integration/test_demo_api_gateway.py::test_demo_rate_limits_are_scoped_by_external_user -q
```

Expected: both pass.

11. Run the Tool Gateway regression tests.

```bash
python -m pytest tests/test_tool_gateway_registry.py tests/integration/test_tool_gateway.py -q
```

Expected: existing direct Tool Gateway rate-limit behavior still passes.

12. Run the broader demo API regression.

```bash
python -m pytest tests/integration/test_demo_api_gateway.py -q
```

Expected: all demo API tests pass.

13. Run frontend unit tests and build.

```bash
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

Expected: both pass. These should not require frontend source changes; failures indicate accidental contract drift.

14. Prepare browser prerequisites.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

15. Run the focused Playwright clarification test.

```bash
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "continues a vague request through the clarification flow"
```

Expected: pass.

16. Run the full Playwright E2E suite.

```bash
npm --prefix frontend run e2e
```

Expected: full suite passes. This is the release-signoff command for this task.

17. Check formatting and working tree.

```bash
git diff --check
git status --short
```

Only task-related files should be staged. Do not stage pre-existing unrelated files.

## 6. Testing Plan

- Unit/runtime integration:
  - scoped limiter isolates equal tool names by namespace
  - scoped limiter preserves same-scope fixed-window denial
  - scoped limiter does not expose raw scope text in Redis keys
- Backend integration:
  - two Web demo users can both complete a happy-path run under a low `search_poi` test limit
  - existing direct Tool Gateway rate-limit test still blocks provider calls after the configured limit
- Frontend regression:
  - unit tests and build pass unchanged
- Browser E2E:
  - focused clarification test passes
  - full `npm --prefix frontend run e2e` passes

## 7. Verification Commands

Commands the implementer must run before committing:

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

## 8. Commit and Push Plan

Expected commit message:

```text
fix: isolate web demo rate limits
```

Expected commands:

```bash
git status --short
git add docs/specs/069-playwright-e2e-rate-limit-isolation-v0.md
git add docs/plans/069-playwright-e2e-rate-limit-isolation-v0-plan.md
git add backend/app/runtime/rate_limit.py backend/app/runtime/__init__.py backend/app/demo/service.py
git add tests/integration/test_redis_runtime.py tests/integration/test_demo_api_gateway.py
git commit -m "fix: isolate web demo rate limits"
git push -u origin codex/playwright-e2e-rate-limit-isolation-v0
```

The implementer must confirm `.env`, secrets, generated artifacts, `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/`, and `qc` are not staged.

## 9. Out-of-scope Changes

- Do not change `ToolRateLimit` defaults.
- Do not disable rate limiting for `APP_ENV=e2e`.
- Do not add Playwright sleeps, retries, or Redis flush logic to hide the issue.
- Do not modify frontend behavior or public API schemas.
- Do not change workflow recovery behavior, clarification policy, benchmark harness behavior, or benchmark reports.
- Do not add dependencies, migrations, Docker changes, or test-only routes.
- Do not clean or revert unrelated local changes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The scoped limiter is implemented in the runtime layer, not as a Playwright workaround.
- [ ] Raw `external_user_id` values are not embedded in Redis key names.
- [ ] The same scope still enforces rate limits.
- [ ] Different demo users no longer share rate-limit counters.
- [ ] Existing direct Tool Gateway rate-limit tests still pass.
- [ ] Focused clarification E2E passes.
- [ ] Full Playwright E2E passes.
- [ ] Required tests and build commands passed.
- [ ] Git status after commit excludes only pre-existing unrelated files.
- [ ] Commit message matches the plan.
- [ ] No `.env`, API key, token, secret, or generated artifact was committed.

## 11. Handoff Notes

After finishing, report back with:

- Changed files.
- The exact scoped limiter behavior implemented.
- Focused backend test results.
- Direct Tool Gateway regression result.
- Focused clarification Playwright result.
- Full Playwright E2E result.
- Commit hash.
- Push result.
- Any remaining e2e stability caveats, especially if failures remain outside rate-limit isolation.
