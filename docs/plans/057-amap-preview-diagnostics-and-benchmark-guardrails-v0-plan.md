# Plan: 057 AMap Preview Diagnostics and Benchmark Guardrails v0

## 1. Spec Reference

Spec file:

```text
docs/specs/057-amap-preview-diagnostics-and-benchmark-guardrails-v0.md
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

- Current branch is `codex/frontend-surface-separation-hardening-v0`.
- Latest completed numbered task is `056`.
- Latest task commit is `349e4c2 feat: harden frontend surface separation`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `056`.
- Focused AMap, workflow, observability, and benchmark tests currently pass on this workspace baseline.
- Task `054` already landed:
  - explicit `read_profile="amap"` selection
  - read-only preview workflow path
  - confirmation rejection for AMap preview runs
- Current remaining gap is operational, not path-selection:
  - canonical run summaries do not expose an AMap-preview-specific diagnostics block
  - internal observability does not expose a preview-specific diagnostics block
  - canonical benchmark fixture/suite loading does not reject non-Mock-World providers before runtime
  - benchmark matrix summaries do not report `tool_profile_counts`
- The current worktree has unrelated untracked local paths:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`
- Those paths must remain unstaged.
- Preferred execution baseline for this task is a fresh branch from updated `main` after Task `056` lands. If the task is intentionally stacked on the current branch, keep the diff scoped to this task only.

## 3. Files to Add

- `docs/specs/057-amap-preview-diagnostics-and-benchmark-guardrails-v0.md` - task spec.
- `docs/plans/057-amap-preview-diagnostics-and-benchmark-guardrails-v0-plan.md` - task plan.

## 4. Files to Modify

- `README.md` - document preview diagnostics availability and canonical benchmark mock-world-only guardrail.
- `backend/app/observability/context.py` - pass full tool-event data into canonical run-summary construction.
- `backend/app/observability/summary.py` - add typed preview diagnostics model and canonical summary generation logic.
- `backend/app/observability/schemas.py` - add internal API schema field for preview diagnostics.
- `backend/app/observability/service.py` - expose preview diagnostics, preferring canonical summary and recomputing when missing or malformed.
- `backend/app/benchmark/schemas.py` - extend benchmark matrix schema with `tool_profile_counts`.
- `backend/app/benchmark/matrix.py` - compute `tool_profile_counts`.
- `backend/app/benchmark/fixtures.py` - enforce canonical fixture guardrail for `tool_profile='mock_world'`.
- `backend/app/benchmark/suites.py` - ensure suite loading/listing flows exercise the canonical provider guardrail.
- `backend/app/benchmark/harness.py` - add defensive ad hoc non-Mock-World rejection before demo-service execution.
- `tests/test_observability.py` - unit coverage for canonical summary preview diagnostics and fallback behavior.
- `tests/integration/test_observability_gateway.py` - internal observability API coverage for preview diagnostics.
- `tests/integration/test_demo_api_gateway.py` - verify public AMap behavior remains unchanged.
- `tests/integration/test_langgraph_workflow_gateway.py` - verify workflow-backed AMap preview summary stays read-only and carries diagnostics.
- `tests/test_benchmark_harness.py` - unit coverage for matrix `tool_profile_counts` and ad hoc harness guardrail.
- `tests/test_benchmark_suites.py` - suite/fixture guardrail coverage and updated matrix expectations.
- `tests/integration/test_benchmark_harness_gateway.py` - suite report coverage for `tool_profile_counts` and mock-world-only canonical suites.

## 5. Implementation Steps

1. Save the new task spec and plan to the repository before touching code.

2. Extend canonical observability summary models in `backend/app/observability/summary.py`.
   - Add a typed preview diagnostics model with the exact fields defined in the spec.
   - Add `preview_diagnostics` to `RunSummary`.
   - Implement one helper that derives preview diagnostics from:
     - the run row
     - the run's tool events
   - Return `None` when `tool_profile != "amap"`.

3. Thread tool-event data into canonical run-summary generation.
   - Update `backend/app/observability/context.py` so `build_run_summary(...)` receives the full run tool-event list, not just counts.
   - Keep existing total `tool_event_count` and `action_count` behavior unchanged.
   - Ensure summary generation remains tolerant of malformed tool-event error payloads.

4. Expose preview diagnostics on the internal observability API.
   - Add `preview_diagnostics` to `InternalObservabilityRunSummary` in `backend/app/observability/schemas.py`.
   - In `backend/app/observability/service.py`, prefer the canonical summary value when it validates cleanly.
   - If the stored canonical summary is absent or has malformed `preview_diagnostics`, recompute the diagnostics from the run row plus tool-event rows instead of failing the route.
   - Keep Mock World responses returning `preview_diagnostics = None`.

5. Keep public demo behavior unchanged while verifying the new internal diagnostics path.
   - Do not change `DemoRunSummary`.
   - Do not change `DemoStartRunRequest`.
   - Do not change the AMAP configuration error string or confirmation rejection string.
   - Use integration tests to prove the public behavior stayed stable while the new internal diagnostics appear on the internal route.

6. Harden canonical benchmark provider guardrails in fixture and suite loading.
   - In `backend/app/benchmark/fixtures.py`, add a canonical-case validation helper that raises:
     - `Canonical benchmark case must use tool_profile='mock_world': <case_id> -> <tool_profile>`
     when a registered fixture resolves to a non-Mock-World provider.
   - Call that helper from canonical fixture loading so:
     - `load_benchmark_case(...)`
     - `load_registered_benchmark_cases()`
     fail early for invalid canonical cases.
   - Let `load_benchmark_suite(...)` and `list_benchmark_suites()` inherit the same fast-fail behavior through canonical fixture loading.

7. Add a defensive runtime harness guardrail for ad hoc benchmark cases.
   - In `backend/app/benchmark/harness.py`, reject `case.tool_profile != "mock_world"` before creating or starting the demo workflow service.
   - Return `BenchmarkCaseResult(status="error")` with:
     - `failure_reasons == ["Unsupported benchmark tool_profile: <tool_profile>"]`
   - Ensure that guardrail does not create a run row and does not append benchmark metadata.

8. Extend benchmark matrix/reporting outputs with provider counts.
   - Add `tool_profile_counts` to `BenchmarkCaseMatrixSummary` in `backend/app/benchmark/schemas.py`.
   - Compute it in `backend/app/benchmark/matrix.py`.
   - Verify that suite descriptions and suite run reports automatically include the new field through existing `matrix_summary` wiring.
   - Do not change suite membership in this task.

9. Update repository documentation.
   - In `README.md`, update the AMap preview section to mention internal preview diagnostics.
   - Update the benchmark section to say canonical benchmark fixtures and suites are mock-world-only by design and reject AMap provider cases in this v0 task.

10. Run the focused backend verification commands from this plan.
   - Fix failures until they pass.
   - Confirm that unrelated untracked local files are still unstaged.

11. Commit and push the task branch with the expected conventional commit message.

## 6. Testing Plan

- Unit tests:
  - `tests/test_observability.py`
    - add coverage that AMap run summaries persist `preview_diagnostics`
    - add coverage that Mock World run summaries keep `preview_diagnostics = None`
    - add coverage that malformed stored preview diagnostics do not break canonical summary loading or internal recomputation
    - add coverage that provider error aggregation sanitizes error type/code extraction
  - `tests/test_benchmark_harness.py`
    - add `tool_profile_counts` matrix assertions
    - add ad hoc non-Mock-World harness guardrail test
  - `tests/test_benchmark_suites.py`
    - update matrix expectations for `tool_profile_counts`
    - add canonical fixture/suite rejection coverage for a monkeypatched non-Mock-World registered case

- Integration tests:
  - `tests/integration/test_langgraph_workflow_gateway.py`
    - extend the existing AMap preview test to assert stored preview diagnostics
  - `tests/integration/test_observability_gateway.py`
    - add/extend AMap preview observability route coverage for `preview_diagnostics`
  - `tests/integration/test_demo_api_gateway.py`
    - confirm public AMap behavior remains unchanged while internal diagnostics are now available via run metadata/observability
  - `tests/integration/test_benchmark_harness_gateway.py`
    - assert suite report `matrix_summary.tool_profile_counts`
    - assert default and all_registered suites remain mock-world-only

- Smoke tests:
  - no new live AMap network smoke test is required
  - optional live test behavior must remain unchanged if `RUN_AMAP_LIVE_TESTS=1`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_observability.py tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py -q
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/integration/test_benchmark_harness_gateway.py -q
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add amap preview diagnostics and benchmark guardrails
```

Expected commands:

```bash
git switch -c codex/amap-preview-diagnostics-and-benchmark-guardrails-v0
git status --short
git add README.md backend/app/observability/context.py backend/app/observability/summary.py backend/app/observability/schemas.py backend/app/observability/service.py backend/app/benchmark/schemas.py backend/app/benchmark/matrix.py backend/app/benchmark/fixtures.py backend/app/benchmark/suites.py backend/app/benchmark/harness.py tests/test_observability.py tests/integration/test_observability_gateway.py tests/integration/test_demo_api_gateway.py tests/integration/test_langgraph_workflow_gateway.py tests/test_benchmark_harness.py tests/test_benchmark_suites.py tests/integration/test_benchmark_harness_gateway.py docs/specs/057-amap-preview-diagnostics-and-benchmark-guardrails-v0.md docs/plans/057-amap-preview-diagnostics-and-benchmark-guardrails-v0-plan.md
git commit -m "feat: add amap preview diagnostics and benchmark guardrails"
git push -u origin codex/amap-preview-diagnostics-and-benchmark-guardrails-v0
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, and `var/` are not staged.

## 9. Out-of-scope Changes

- Do not change public demo API contracts or error payload shape.
- Do not add AMap write execution.
- Do not add provider fallback.
- Do not add live-provider benchmark support.
- Do not add new benchmark cases or change canonical suite membership.
- Do not modify frontend source files for this task.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md` unless the spec explicitly requires it.
- Do not add new dependencies.
- Do not commit generated caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Public AMap preview behavior is unchanged.
- [ ] Internal observability now exposes `preview_diagnostics` for AMap preview runs.
- [ ] Mock World internal observability still returns `preview_diagnostics = None`.
- [ ] Canonical benchmark fixtures and suites fail fast on non-Mock-World providers.
- [ ] Benchmark matrix and suite reports now include `tool_profile_counts`.
- [ ] Required tests passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Whether Task `056` was already merged to `main` before branching
- Exact preview diagnostics payload shape observed in one successful AMap integration test
- Exact benchmark guardrail failure strings observed in:
  - canonical fixture/suite validation
  - ad hoc harness rejection
- Known limitations or follow-up tasks
