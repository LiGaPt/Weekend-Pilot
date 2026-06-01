# Plan: 083 Public Demo SSE Search Count Milestones v0

## 1. Spec Reference

Spec file:

```text
docs/specs/083-public-demo-sse-search-count-milestones-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/public-demo-sse-progress-stream-v0`.
- Working tree is clean.
- Current `HEAD` is `d9eed54 feat: add public demo sse progress stream`.
- `docs/specs` and `docs/plans` are continuous and slug-matched through `082`.
- Relative to `main`, the current branch is `0` commits behind and `26` commits ahead, so this task should be implemented as a stacked follow-up from current `HEAD`, not from `main`.
- Task `079` already derives public search-count wording from persisted `search_poi` tool events in `backend/app/demo/progress.py`.
- Task `082` already added `/demo/runs/stream` and currently emits at most one derived public progress snapshot per streamed workflow state.
- No frontend code currently consumes `/demo/runs/stream`, so this task must stay backend-only and must harden the stream contract before later frontend work.

## 3. Files to Add

- `docs/specs/083-public-demo-sse-search-count-milestones-v0.md` - task spec for the search milestone follow-up.
- `docs/plans/083-public-demo-sse-search-count-milestones-v0-plan.md` - implementation plan for the search milestone follow-up.

## 4. Files to Modify

- `backend/app/demo/progress.py` - add a helper that can project ordered live search milestone summaries from the existing progress snapshot and persisted tool-event evidence.
- `backend/app/demo/streaming.py` - change the live-stream progress projection helper to return an ordered list of progress summaries instead of only one summary.
- `backend/app/demo/service.py` - emit one `progress` SSE frame per non-duplicate milestone summary while preserving final `summary` and `error` behavior.
- `tests/test_demo_streaming.py` - add focused unit coverage for ordered activity/dining milestone projection and fallback behavior.
- `tests/integration/test_demo_api_gateway.py` - assert ordered happy-path SSE milestone emission and exact reviewer-visible copy.
- `README.md` - document that `/demo/runs/stream` now emits ordered search milestone progress snapshots inside the existing `progress` event type.
- `docs/WEB_DEMO_README.md` - align the runbook and expected results with the ordered search milestone behavior.

## 5. Implementation Steps

1. Create a new stacked task branch from the current clean `HEAD`:

   ```bash
   git switch -c codex/public-demo-sse-search-count-milestones-v0
   ```

2. In `backend/app/demo/progress.py`, add one additive helper with this exact responsibility:

   - name it `build_live_demo_progress_milestones(...)`
   - input shape should mirror the current live-summary helper:
     - `state`
     - `tool_events`
     - optional `persisted_plan_count`
   - return type must be `list[DemoProgressSummary]`
   - call the existing `build_live_demo_progress_summary(...)` once to obtain the full current public snapshot
   - if the live state is not the combined search state, return a one-item list containing the existing full snapshot
   - if the live state corresponds to `execute_searches`, inspect the full snapshot and return ordered milestone snapshots instead of the one combined search snapshot:
     - first truncate the full snapshot to `searching_activities` when that stage is present
     - then truncate the full snapshot to `searching_dining` when that stage is present
   - do not append the original combined search snapshot after the milestone list
   - implement truncation by slicing the existing `stage_history` and `steps` from the full snapshot
   - when truncating, preserve all existing labels and summary strings and reset the last included step to `status="current"`
   - do not duplicate count logic in a second place; reuse the existing summary text already produced by the full progress projection

3. Keep the existing `build_live_demo_progress_summary(...)` function in place for any caller that still needs a single summary. This task must be additive rather than a breaking rename.

4. In `backend/app/demo/streaming.py`, replace the single-summary derivation helper with a multi-summary helper:

   - replace `derive_stream_progress_summary(...)` with `derive_stream_progress_summaries(...)`
   - delegate to `build_live_demo_progress_milestones(...)`
   - keep `encode_sse_event(...)`, `serialize_progress_summary(...)`, and `is_duplicate_progress_snapshot(...)` unchanged

5. In `backend/app/demo/service.py`, update `start_run_stream(...)` so each streamed workflow state can emit multiple ordered `progress` frames:

   - keep the existing `runner.stream(...)` loop
   - keep the existing `ToolEventRepository` and `PlanRepository` readback behavior
   - for each streamed state with a valid `run_id`, call `derive_stream_progress_summaries(...)`
   - iterate the returned summaries in order
   - for each summary:
     - compare it to `last_progress_snapshot`
     - emit a `progress` frame only when the serialized snapshot is not a duplicate
     - increment `event_index` once per emitted frame
     - update `last_progress_snapshot` after each emitted frame
   - keep the existing final `summary` event behavior unchanged
   - keep the existing `error` event behavior unchanged
   - do not change the synchronous `start_run(...)` path

6. In `tests/test_demo_streaming.py`, add or replace focused unit coverage so the streaming helper contract is explicit:

   - add one test where an `execute_searches` state has both activity and dining `search_poi` tool events
   - assert the helper returns two ordered summaries
   - assert the first summary has:
     - `current_stage == "searching_activities"`
     - stage history ending at `searching_activities`
     - current-step summary `已找到 2 个活动` in the fixture
   - assert the second summary has:
     - `current_stage == "searching_dining"`
     - stage history ending at `searching_dining`
     - activity step marked completed
     - current-step summary `已找到 3 个餐厅` in the fixture
   - add one test where only activity search evidence exists and assert exactly one milestone summary is returned
   - add one test where count data is malformed and assert the existing generic summary is used instead of raising

7. In `tests/integration/test_demo_api_gateway.py`, add one dedicated stream-happy-path test named for the milestone behavior, rather than overloading the existing summary-parity test:

   - start a normal Mock World `/demo/runs/stream` request
   - parse all `progress` events
   - find the first `progress` event with `progress.current_stage == "searching_activities"`
   - assert that event exists and its current-step summary is exactly `已找到 5 个活动`
   - find the first `progress` event with `progress.current_stage == "searching_dining"`
   - assert that event exists and its current-step summary is exactly `已找到 5 个餐厅`
   - assert the activity event appears earlier than the dining event
   - if a `checking_availability` event exists, assert it appears after the dining event
   - keep the existing happy-path test that checks final `summary` parity with `GET /demo/runs/{run_id}`

8. Update documentation:

   - in `README.md`, add one short note under the SSE section that the happy-path start stream now emits separate search milestones for activities and dining within the existing `progress` event type
   - in `docs/WEB_DEMO_README.md`, update:
     - the overview paragraph about `/demo/runs/stream`
     - the reviewer expectations
     - the expected-results section
   - keep all remaining non-goals from Task `082` unchanged

9. Run verification commands, confirm the working tree contains only task-relevant files, then commit and push the stacked branch.

## 6. Testing Plan

- `Unit tests:` `tests/test_demo_streaming.py` must prove combined-search-state splitting, single-category behavior, and malformed-count fallback.
- `Regression unit tests:` `tests/test_demo_progress.py` and `tests/test_demo_api.py` must still pass unchanged to prove the existing public progress contract and route shape did not regress.
- `Integration tests:` `tests/integration/test_demo_api_gateway.py -k stream -v` must prove ordered `searching_activities` then `searching_dining` milestone emission and preserve final summary parity.
- `Smoke check:` optional local `curl -N` on `/demo/runs/stream` should show search milestone `progress` events before itinerary/availability stages.
- `Docs review:` `README.md` and `docs/WEB_DEMO_README.md` must stay aligned with the actual stream contract.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_demo_progress.py tests/test_demo_streaming.py tests/test_demo_api.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k stream -v
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: emit sse search count milestones
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/public-demo-sse-search-count-milestones-v0
git add docs/specs/083-public-demo-sse-search-count-milestones-v0.md docs/plans/083-public-demo-sse-search-count-milestones-v0-plan.md
git add backend/app/demo/progress.py backend/app/demo/streaming.py backend/app/demo/service.py
git add tests/test_demo_streaming.py tests/integration/test_demo_api_gateway.py
git add README.md docs/WEB_DEMO_README.md
git commit -m "feat: emit sse search count milestones"
git push -u origin codex/public-demo-sse-search-count-milestones-v0
```

The implementer must confirm `.env`, secrets, `frontend/dist/`, Playwright artifacts, and `var/` runtime files are not staged.

## 9. Out-of-scope Changes

- Do not add a new SSE event name.
- Do not add frontend stream consumption or UI changes.
- Do not split `execute_searches` into separate workflow nodes.
- Do not add Redis-backed public replay, polling, WebSockets, or reconnect semantics.
- Do not change synchronous demo route behavior.
- Do not add new dependencies, new database schema, or unrelated refactors.
- Do not modify benchmark suites, internal observability routes, or unrelated task docs.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `/demo/runs/stream` still uses only `progress`, `summary`, and `error`.
- [ ] The happy-path stream emits `searching_activities` before `searching_dining`.
- [ ] The exact search milestone copy is `已找到 5 个活动` and `已找到 5 个餐厅`.
- [ ] Final streamed `summary` still matches `GET /demo/runs/{run_id}` for the same run.
- [ ] No frontend code, new dependency, or workflow-node split was introduced.
- [ ] Required tests and document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- Verification commands and results.
- A short description of the observed stream stage order in the happy path.
- Commit hash.
- Push result.
- Any remaining limitation, which should still be that only the initial start route streams and the frontend still does not consume `/demo/runs/stream`.
