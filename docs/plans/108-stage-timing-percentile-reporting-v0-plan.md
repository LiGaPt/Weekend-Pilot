# Plan: 108 Stage timing percentile reporting v0

## 1. Spec Reference

Spec file:

```text
docs/specs/108-stage-timing-percentile-reporting-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/107-benchmark-test-doc-count-convergence`.
- Latest completed numbered task is `107`.
- Latest commit is:

  ```text
  08b3892 test: align benchmark inventory expectations
  ```

- `docs/specs/` and `docs/plans/` are continuous and matched through `107`.
- There is no tracked `108` spec or plan yet.
- The working tree contains unrelated untracked files that must remain untouched:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Existing timing/reporting infrastructure is already implemented:
  - workflow results expose `workflow_timing_summary`
  - benchmark suite reports expose `benchmark_timing_summary`
  - case-level internal observability responses expose `workflow_timing_summary`
- Current practical gap:
  - `backend/app/benchmark/internal_summary.py` strips timing summary fields from the latest release-gate summary contract
  - `frontend/src/observability/ObservabilityPage.tsx` `Benchmark Summary` panel shows counts and matrices, but not suite timing percentiles
- Relevant focused tests currently pass:
  - backend timing/reporting unit tests
  - workflow/observability timing tests
  - benchmark timing integration tests
  - observability gateway tests

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/benchmark/internal_summary.py` - extend the release-gate summary contract with additive timing fields and harden timing extraction.
- `backend/app/api/observability.py` - keep the existing route, but return the expanded response model.
- `frontend/src/observability/types.ts` - add frontend types for suite timing stats and the new release-gate summary fields.
- `frontend/src/observability/ObservabilityPage.tsx` - render a compact benchmark timing section in the existing `Benchmark Summary` panel.
- `frontend/src/observability/api.test.ts` - update API contract tests for the new additive fields.
- `frontend/src/observability/ObservabilityPage.test.tsx` - add rendering tests for timing-present and timing-missing states.
- `tests/test_benchmark_internal_summary.py` - add unit coverage for valid, missing, and malformed timing-summary extraction.
- `tests/integration/test_observability_gateway.py` - verify the latest benchmark summary endpoint returns timing fields and degrades gracefully.
- `README.md` - mention that the internal `Benchmark Summary` includes suite timing percentile information.
- `docs/WEB_DEMO_README.md` - update reviewer flow notes for the timing section in `Benchmark Summary`.

## 5. Implementation Steps

1. Reconfirm baseline before editing.
   - Run:
     - `git status --short`
     - `git branch --show-current`
     - `git log --oneline -3`
   - Confirm the task starts after the committed `107` baseline and unrelated untracked files remain untouched.

2. Inspect the current internal latest release-gate summary contract.
   - Read:
     - `backend/app/benchmark/internal_summary.py`
     - `backend/app/api/observability.py`
     - `frontend/src/observability/types.ts`
     - `frontend/src/observability/ObservabilityPage.tsx`
   - Confirm:
     - backend latest summary loader currently returns counts/matrix only
     - benchmark suite report already contains `benchmark_timing_summary`
     - frontend benchmark hero has no suite timing rendering yet

3. Extend the backend internal summary model additively.
   - In `backend/app/benchmark/internal_summary.py`:
     - add frontend-facing backend models for suite timing response fields or reuse existing benchmark timing models directly
     - extend `ReleaseGateBenchmarkSummary` with:
       - `benchmark_timing_summary_present: bool = False`
       - `benchmark_timing_summary: BenchmarkTimingSummary | None = None`
   - Keep all existing fields and semantics unchanged.

4. Add a narrow timing-summary extraction helper.
   - In `backend/app/benchmark/internal_summary.py`, implement one private helper that:
     - prefers `report.benchmark_summary.benchmark_timing_summary`
     - falls back to top-level `report.benchmark_timing_summary`
     - returns `(present_flag, summary_or_none)`
   - Use existing validated models where possible.
   - If timing data is missing, return `False, None`.
   - If timing data is malformed, swallow only the timing-field validation failure and return `False, None`.
   - Do not swallow failures for the core summary contract.

5. Keep core report validation strict.
   - Continue validating the latest report strongly enough to preserve current 404 / invalid-report semantics.
   - Only relax behavior for the additive timing field.
   - Do not broaden degradation to `suite_id`, `suite_title`, `matrix_summary`, or core benchmark counts.

6. Return the expanded response from the existing route.
   - `backend/app/api/observability.py` should continue to use `ReleaseGateBenchmarkSummary` as the response model.
   - No new route should be added.
   - Preserve current 404 and 500 error text.

7. Add frontend type support for the additive timing fields.
   - In `frontend/src/observability/types.ts`:
     - add a type for overall percentile stats
     - add a type for stage percentile entries
     - add a type for suite timing summary
     - extend `InternalReleaseGateBenchmarkSummary` with:
       - `benchmark_timing_summary_present: boolean`
       - `benchmark_timing_summary: InternalBenchmarkTimingSummary | null`
   - Keep existing types backward compatible.

8. Render a minimal timing section in the `Benchmark Summary` panel.
   - In `frontend/src/observability/ObservabilityPage.tsx`:
     - keep the existing benchmark hero, metric cards, alias path, and count panels
     - add one compact timing section below the metric grid
   - When timing is present:
     - render overall total-duration metrics:
       - `p50`
       - `p95`
       - `p99`
       - `max`
     - render a table using `benchmark_timing_summary.stages`
     - include columns:
       - stage
       - samples
       - retry cases
       - `p50`
       - `p95`
       - `p99`
       - `max`
   - Preserve report order from the suite timing summary; do not re-rank or redesign the page.
   - When timing is absent:
     - show a neutral sentence such as “Suite timing summary is unavailable for this artifact.”
   - Do not add charts, tabs, filters, or a new panel.

9. Update backend unit tests.
   - In `tests/test_benchmark_internal_summary.py`:
     - add one test where a valid suite timing summary is present and returned
     - add one test where timing summary is absent and the summary still loads
     - add one test where timing summary is malformed and the summary still loads with `present=false`
   - Keep existing not-found and invalid-core-summary tests unchanged.

10. Update backend integration tests.
    - In `tests/integration/test_observability_gateway.py`:
      - extend the existing latest benchmark summary route test to assert:
        - `benchmark_timing_summary_present` is `true`
        - `benchmark_timing_summary.overall_total_duration_ms.p95_ms` is present
        - `benchmark_timing_summary.stages` is non-empty
      - add one integration test fixture/path where timing is omitted from the latest report and assert:
        - status `200`
        - `benchmark_timing_summary_present == false`
        - `benchmark_timing_summary == null`
   - Keep run-level observability timing assertions unchanged.

11. Update frontend tests.
   - In `frontend/src/observability/api.test.ts`:
     - extend mocked latest-release-gate summary payloads with the new timing fields
     - assert parsing keeps the additive fields intact
   - In `frontend/src/observability/ObservabilityPage.test.tsx`:
     - add one test that the benchmark panel renders:
       - `p50`
       - `p95`
       - `p99`
       - at least one stage row
     - add one test that missing timing summary shows the neutral fallback message
     - keep existing benchmark hero and load-run behavior assertions unchanged

12. Update active docs only where current reviewer-facing behavior changes.
   - In `README.md`:
     - update the internal `5174` description so `Benchmark Summary` explicitly includes suite timing percentile information
   - In `docs/WEB_DEMO_README.md`:
     - update the reviewer script wording so the first benchmark panel scan mentions timing percentiles and stage distribution
   - Do not rewrite archived specs/plans.

13. Run focused verification after edits.
   - Backend summary tests:
     ```bash
     python -m pytest tests/test_benchmark_internal_summary.py tests/integration/test_observability_gateway.py -q
     ```
   - Benchmark non-regression:
     ```bash
     python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -q
     ```
   - Frontend observability tests:
     ```bash
     npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
     ```
   - Final hygiene:
     ```bash
     git diff --check
     git status --short
     ```

14. Commit only task-relevant files.
   - Stage only the backend summary, frontend observability, docs, and test files touched by this task.
   - Commit with:
     ```bash
     git commit -m "feat: harden stage timing percentile reporting"
     ```

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_internal_summary.py`
    - valid timing summary is promoted into latest summary response
    - missing timing summary degrades to `present=false`
    - malformed timing summary degrades to `present=false`
- Integration tests:
  - `tests/integration/test_observability_gateway.py`
    - latest release-gate summary route returns additive timing fields
    - latest release-gate summary route still succeeds when timing summary is absent
  - `tests/integration/test_benchmark_harness_gateway.py`
    - benchmark suite reports still include timing summary at the raw report level
- Frontend component/API tests:
  - `frontend/src/observability/api.test.ts`
    - release-gate summary payload includes the new timing fields
  - `frontend/src/observability/ObservabilityPage.test.tsx`
    - benchmark panel renders timing summary when present
    - benchmark panel renders fallback copy when timing is absent
- Smoke/document checks:
  - `README.md` mentions suite timing in `Benchmark Summary`
  - `docs/WEB_DEMO_README.md` reviewer flow mentions the timing section

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_internal_summary.py tests/integration/test_observability_gateway.py -q
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -q
npm --prefix frontend test -- --run src/observability/api.test.ts src/observability/ObservabilityPage.test.tsx
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: harden stage timing percentile reporting
```

Expected commands:

```bash
git status --short
git switch -c codex/108-stage-timing-percentile-reporting-v0
git add backend/app/benchmark/internal_summary.py backend/app/api/observability.py frontend/src/observability/types.ts frontend/src/observability/ObservabilityPage.tsx frontend/src/observability/api.test.ts frontend/src/observability/ObservabilityPage.test.tsx tests/test_benchmark_internal_summary.py tests/integration/test_observability_gateway.py README.md docs/WEB_DEMO_README.md docs/specs/108-stage-timing-percentile-reporting-v0.md docs/plans/108-stage-timing-percentile-reporting-v0-plan.md
git diff --cached --check
git commit -m "feat: harden stage timing percentile reporting"
git push -u origin codex/108-stage-timing-percentile-reporting-v0
```

The implementer must confirm unrelated untracked files, generated `var/` artifacts, `.env`, and secrets are not staged.

## 9. Out-of-scope Changes

- Do not change workflow timing instrumentation in `backend/app/workflow/*`.
- Do not change benchmark percentile math in `backend/app/benchmark/timing.py`.
- Do not change benchmark suites, release-gate thresholds, or system-integrity formulas.
- Do not add a new benchmark endpoint or a new observability page.
- Do not redesign the `5174` layout beyond one compact timing section inside the existing `Benchmark Summary` panel.
- Do not touch public customer UI code.
- Do not rewrite archived specs/plans under `docs/specs/` or `docs/plans/`.
- Do not stage `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, `docs/superpowers/`, `var/`, caches, virtual environments, or other unrelated local files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/108-stage-timing-percentile-reporting-v0.md`.
- [ ] The implementation stayed within M1 hardening scope.
- [ ] The latest release-gate summary API gained additive timing fields only.
- [ ] Missing or malformed timing summary no longer breaks the entire latest summary endpoint.
- [ ] The `5174` `Benchmark Summary` panel shows overall timing percentiles and per-stage timing rows when available.
- [ ] The panel shows a neutral fallback when timing is unavailable.
- [ ] Existing benchmark hero count/matrix content remains visible.
- [ ] Existing case-level `workflow_timing_summary` visibility did not regress.
- [ ] Benchmark harness raw suite report timing behavior did not regress.
- [ ] Focused backend, integration, and frontend tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- exact files changed
- whether the backend chose `benchmark_summary.benchmark_timing_summary` first and whether fallback to top-level timing summary was needed
- verification commands run and their results
- screenshots or a brief note describing the new `Benchmark Summary` timing section behavior
- commit hash
- push result
- confirmation that unrelated untracked files stayed untouched
- any known limitation, especially if malformed timing fields still require broader artifact-shape assumptions than planned
