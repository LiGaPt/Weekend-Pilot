# Plan: 055 Benchmark Multi-turn Continuations v0

## 1. Spec Reference

Spec file:

```text
docs/specs/055-benchmark-multi-turn-continuations-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/switchable-amap-read-path-v0`.
- Latest commit is `db02829 docs: backfill missing task docs`.
- The latest implementation commit tied to the latest completed task is `791cdae feat: add switchable amap read path`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `054`.
- The current repository already has the product-side continuation prerequisites:
  - session persistence
  - clarification turns
  - follow-up replans
  - visible plan-version lineage
  - demo action manifests
- The benchmark side is still single-turn:
  - `BenchmarkCase` still centers on one `user_input`
  - `BenchmarkHarness` still runs one workflow invocation per case
  - no benchmark fixture can currently encode or report a continuation chain
- Task `050` explicitly deferred true multi-turn L3 benchmark authoring, so this plan is filling a known deliberate gap rather than changing direction.
- Focused read-only verification already passed in the current workspace:
  - `python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q`
  - `python -m pytest tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py -q`
- Pre-existing untracked local paths currently include:
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `qc`
  - `var/`
- Those paths must remain unstaged during task `055`.

## 3. Files to Add

- `backend/app/benchmark/cases/solo_clarification_continuation_v1.json` - new L3 continuation fixture for `start -> clarify -> confirm` with stable `v1` versioning.
- `backend/app/benchmark/cases/family_replan_version_continuation_v1.json` - new L3 continuation fixture for `start -> replan -> confirm` with `v1 -> v2` versioning.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add continuation request, continuation expectation, continuation trace, and additive case-result fields.
- `backend/app/benchmark/graders.py` - add `grade_conversation_path(...)`.
- `backend/app/benchmark/harness.py` - branch continuation cases through `DemoWorkflowService`, aggregate run artifacts across the chain, and finalize additive result fields.
- `backend/app/benchmark/fixtures.py` - register the two new continuation case IDs.
- `backend/app/benchmark/suites.py` - add `conversation_continuations`, update suite order, and append the new cases to `all_registered`.
- `backend/app/demo/service.py` - add an internal-only start override so the benchmark harness can honor case `world_profile`, `agent_version`, and `prompt_version` without changing public HTTP schemas.
- `tests/test_benchmark_harness.py` - add schema, grader, suite-count, and harness-branch coverage.
- `tests/test_benchmark_suites.py` - add suite ordering, membership, and exact matrix-summary assertions for the new suite and updated `all_registered`.
- `tests/integration/test_benchmark_harness_gateway.py` - add end-to-end continuation case execution and suite execution coverage.
- `README.md` - document the continuation suite and its v0 boundaries.

## 5. Implementation Steps

1. Write failing schema and suite tests first.
   In `tests/test_benchmark_harness.py` and `tests/test_benchmark_suites.py`, add focused failures for:
   - `BenchmarkCase` accepting additive `continuations`
   - `BenchmarkExpectedOutcome` accepting additive `conversation`
   - `BenchmarkCaseResult` exposing `conversation_trace` and `conversation_turn_types`
   - `BenchmarkSuiteId` including `conversation_continuations`
   - `list_benchmark_suites()` returning the new exact suite order
   - updated `all_registered` counts moving from `15` to `17`
   - exact `conversation_continuations` matrix-summary counts
   Do not touch existing legacy single-turn expectations yet except where the new suite order and `all_registered` totals must change.

2. Add failing unit tests for harness branching and conversation grading.
   In `tests/test_benchmark_harness.py`, add:
   - a harness test that monkeypatches `DemoWorkflowService` and proves cases with `continuations` do not call the legacy workflow-runner path
   - a harness test that continuation-path cases aggregate tool-event counts across multiple run IDs
   - a grader test for `grade_conversation_path(...)` covering:
     - exact status/version match pass
     - step-count mismatch fail
     - missing required turn type fail
   Keep legacy grader tests unchanged.

3. Add failing integration tests for real continuation execution.
   In `tests/integration/test_benchmark_harness_gateway.py`, add:
   - `test_benchmark_harness_runs_solo_clarification_continuation_case`
   - `test_benchmark_harness_runs_family_replan_version_continuation_case`
   - `test_benchmark_harness_runs_conversation_continuations_suite`
   Each integration test should assert:
   - benchmark result status is `passed`
   - `conversation_trace` contains the exact expected step sequence
   - `conversation_turn_types` include the exact required turn labels
   - final `workflow_status == "completed"`
   - final `feedback_status == "completed"`
   - report JSON includes the additive fields and stays sanitized
   For the suite test, assert:
   - `suite_id == "conversation_continuations"`
   - `case_count == 2`
   - exact matrix-summary counts
   - exact outcome-rollup counts
   - report filename `suite-conversation_continuations-run-report.json`

4. Implement additive benchmark schemas.
   In `backend/app/benchmark/schemas.py`:
   - add `BenchmarkContinuationRequest`
   - add `BenchmarkConversationExpectedStep`
   - add `BenchmarkConversationExpectation`
   - add `BenchmarkConversationTraceStep`
   - extend `BenchmarkExpectedOutcome` with `conversation: ... | None = None`
   - extend `BenchmarkCase` with `continuations: list[...] = Field(default_factory=list)`
   - extend `BenchmarkCaseResult` with:
     - `conversation_trace`
     - `conversation_turn_types`
   Keep every new field additive with sensible defaults so all existing fixtures and tests remain valid.

5. Implement the new conversation-path grader.
   In `backend/app/benchmark/graders.py`:
   - add `grade_conversation_path(case, conversation_trace, conversation_turn_types)`
   - compare observed steps to `case.expected.conversation.steps` in exact order by:
     - `mode`
     - `status`
     - `version_label` when specified
   - require every configured `required_turn_type` to appear in the observed turn-type list
   - return score name `conversation_path`
   - include high-signal details:
     - `expected_step_signatures`
     - `observed_step_signatures`
     - `required_turn_types`
     - `observed_turn_types`
   Do not alter existing legacy graders except to import the new schema types if needed.

6. Add a narrow internal override to the demo service.
   In `backend/app/demo/service.py`:
   - add an internal-only start override object or keyword-only override parameter for `start_run(...)`
   - allow the benchmark harness to override:
     - `tool_profile`
     - `world_profile`
     - `agent_version`
     - `prompt_version`
   - keep public HTTP request and response schemas unchanged
   - keep current default demo behavior unchanged when the override is absent
   The implementation should stay inside the service layer; do not add public API fields.

7. Implement the continuation branch in the benchmark harness.
   In `backend/app/benchmark/harness.py`:
   - split the current `_run_case(...)` logic into:
     - legacy single-turn path
     - continuation path
   - keep the legacy path byte-for-byte compatible wherever possible
   - for continuation cases:
     - reject non-`mock_world` tool profiles
     - reject non-null `failure_profile`
     - create the benchmark user and memory rows exactly as today
     - instantiate `DemoWorkflowService` with the same session/cache/rate_limiter/trace buffer
     - call `start_run(...)` with the benchmark user external ID and the internal override carrying the case `world_profile` / versions
     - record the `start` trace step
     - iterate each configured continuation in order:
       - `clarify` -> `clarify_run(...)`
       - `replan` -> `replan_run(...)`
       - record a trace step after each call
     - if the final continuation summary is `awaiting_confirmation`, call `confirm_run(...)` once and record a `confirm` trace step
   Build a list of ordered conversation run IDs while executing this chain.

8. Aggregate final benchmark artifacts across the conversation chain.
   Still in `backend/app/benchmark/harness.py`:
   - load the final run row using the last run ID in the chain
   - aggregate `ToolEvent` rows across every conversation run ID in order
   - aggregate `ActionLedger` rows across every conversation run ID
   - keep final-run values for:
     - `run_id`
     - `trace_id`
     - `run_summary`
     - `workflow_status`
     - `workflow_timing_summary`
     - `feedback_status`
     - `observability_status`
     - selected plan
   - load ordered `conversation_turn_types` from the final run session via `ConversationTurnRepository`
   - synthesize a lightweight workflow-like object for `grade_workflow_path(...)` and `grade_agent_coverage(...)` using the final run metadata:
     - `status`
     - `node_history = demo.initial_node_history + demo.continuation_history`
     - `agent_results = metadata["agents"]["results"]`
     - `error_json = demo.initial_error` or workflow error metadata
   - add `grade_conversation_path(...)` only when `case.expected.conversation` is present
   - use aggregated tool events for `grade_trajectory(...)` and `grade_failure_injection(...)`
   Keep `combine_scores(...)` unchanged.

9. Register the new fixtures and suite catalog entries.
   In `backend/app/benchmark/fixtures.py`:
   - append:
     - `solo_clarification_continuation_v1`
     - `family_replan_version_continuation_v1`
   In `backend/app/benchmark/suites.py`:
   - add suite id `conversation_continuations`
   - insert it into `_ORDERED_SUITE_IDS` before `default`
   - define its exact case membership in the spec order
   - append the two new continuation cases to `_ALL_REGISTERED_CASE_IDS`
   - keep `default` unchanged
   Then update unit-test constants for:
   - `conversation_continuations`
   - updated `all_registered`

10. Add the two fixture JSON files exactly as specified.
    Create:
    - `backend/app/benchmark/cases/solo_clarification_continuation_v1.json`
    - `backend/app/benchmark/cases/family_replan_version_continuation_v1.json`
    Use the exact payloads from the spec, including:
    - tags
    - `metadata.focus`
    - continuation steps
    - min tool-event counts
    - exact expected conversation step sequence
    Keep them non-failure and Mock World only.

11. Update README benchmark documentation last.
    In `README.md`:
    - add `conversation_continuations` to the named suite list
    - state explicitly that `default` remains the current single-turn 10-case suite
    - state explicitly that v0 continuation coverage is:
      - Mock World only
      - non-failure only
      - report-oriented and suite-oriented
    - mention additive `conversation_trace` reporting in case reports

12. Run focused verification and stage only task files.
    Run the commands from section 7 exactly.
    Before staging, confirm these unrelated pre-existing paths remain unstaged:
    - `docs/NEXT_PHASE_ROADMAP.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `qc`
    - `var/`

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_harness.py`
    - schema additions
    - `grade_conversation_path(...)`
    - continuation harness branch
    - updated `all_registered` totals
  - `tests/test_benchmark_suites.py`
    - suite ordering
    - suite membership
    - exact `conversation_continuations` and updated `all_registered` matrix counts
- Upstream regression guard:
  - `tests/test_demo_clarification.py`
  - `tests/test_demo_replan.py`
  - `tests/test_demo_versioning.py`
  These confirm the product-side continuation primitives still behave as assumed.
- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py`
    - clarification continuation case
    - replan/version continuation case
    - continuation suite execution
- Smoke checks:
  - verification commands from section 7
- Explicit non-tests:
  - no replay-contract expansion in this task
  - no failure-injected multi-turn coverage in this task
  - no frontend or public API tests required beyond existing regression dependencies

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q
python -m pytest tests/test_demo_clarification.py tests/test_demo_replan.py tests/test_demo_versioning.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark multi-turn continuations
```

Expected commands:

```bash
git status --short
git switch -c codex/benchmark-multi-turn-continuations-v0
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/graders.py
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/fixtures.py
git add backend/app/benchmark/suites.py
git add backend/app/demo/service.py
git add backend/app/benchmark/cases/solo_clarification_continuation_v1.json
git add backend/app/benchmark/cases/family_replan_version_continuation_v1.json
git add tests/test_benchmark_harness.py
git add tests/test_benchmark_suites.py
git add tests/integration/test_benchmark_harness_gateway.py
git add README.md
git diff --cached --check
git commit -m "feat: add benchmark multi-turn continuations"
git push -u origin codex/benchmark-multi-turn-continuations-v0
```

The implementer must confirm that `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, `var/`, and any unrelated local docs are not staged.

## 9. Out-of-scope Changes

- Do not add failure-injected multi-turn benchmark fixtures.
- Do not widen the benchmark continuation path to recovery-generated clarification loops.
- Do not change replay report contracts or add continuation signatures to replay in this task.
- Do not change public demo HTTP schemas.
- Do not alter `default` suite membership.
- Do not add new dependencies or Alembic revisions.
- Do not touch AMAP behavior, chaos harness behavior, or frontend behavior.
- Do not stage unrelated local docs or generated runtime artifacts.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/055-benchmark-multi-turn-continuations-v0.md`.
- [ ] Legacy single-turn benchmark cases still use the original workflow-backed path.
- [ ] Continuation cases use `DemoWorkflowService` and not the legacy single-run path.
- [ ] `solo_clarification_continuation_v1` reports `v1 -> v1 -> v1`.
- [ ] `family_replan_version_continuation_v1` reports `v1 -> v2 -> v2`.
- [ ] `conversation_trace` and `conversation_turn_types` are present in continuation case reports.
- [ ] No `session_id` or raw turn payloads leak into benchmark reports.
- [ ] `conversation_path` is only added for cases with `expected.conversation`.
- [ ] `conversation_continuations` suite exists with exactly two cases.
- [ ] `default` remains the 10-case single-turn suite.
- [ ] `all_registered` expands to 17 cases with the exact counts from the spec.
- [ ] Required unit and integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, or unrelated local file was committed.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The final additive `BenchmarkCase`, `BenchmarkExpectedOutcome`, and `BenchmarkCaseResult` continuation contracts.
- The exact observed `conversation_trace` for:
  - `solo_clarification_continuation_v1`
  - `family_replan_version_continuation_v1`
- The exact `conversation_turn_types` captured for both continuation cases.
- Confirmation that `default` remained unchanged and `all_registered` became `17` cases.
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that unrelated untracked files remained unstaged.
- Any follow-up limitation, especially:
  - no failure-injected multi-turn benchmarking yet
  - no replay continuation-signature comparison yet
  - no public API expansion for benchmark-only overrides
