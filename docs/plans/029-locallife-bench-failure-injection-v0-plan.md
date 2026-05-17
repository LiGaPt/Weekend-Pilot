# Plan: 029 LocalLife-Bench Failure Injection v0

## 1. Spec Reference

Spec file:

```text
docs/specs/029-locallife-bench-failure-injection-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `task28`.
- Latest completed commit is `93a294d test: expand locallife bench cases`.
- Task 028 expanded the default benchmark suite to five happy-path cases.
- Task 029 spec must exist at `docs/specs/029-locallife-bench-failure-injection-v0.md` before implementation starts. If it is missing, stop and save the approved spec first.
- Current `BenchmarkCase.failure_profile` and `WeekendPilotWorkflowRequest.failure_profile` exist but do not drive runtime failure injection.
- Current Tool Gateway records provider failures as failed `tool_events`; Task 029 should reuse that event path for injected read failures.
- Current recovery v0 can stop safely and persist recovery metadata when final review blocks a plan.
- A route failure should naturally produce no usable route, no itinerary draft, blocked final review, and `stop_safely` recovery.
- PostgreSQL and Redis are required for benchmark and gateway integration tests.
- Working tree may contain unrelated untracked `docs/TASK_WORKFLOW_PROMPTS.md`; do not stage it unless explicitly requested.

## 3. Files to Add

- `docs/plans/029-locallife-bench-failure-injection-v0-plan.md` - this implementation plan.
- `backend/app/tool_gateway/failure_injection.py` - generic Tool Gateway failure-injection protocol and static read-tool injector.
- `backend/app/benchmark/failure_profiles.py` - benchmark profile registry for `route_unavailable_v0`.
- `backend/app/benchmark/cases/family_route_failure_v1.json` - non-default benchmark case for route failure safe-stop behavior.
- `tests/test_failure_injection.py` - focused unit tests for profile resolution and injector decisions.

## 4. Files to Modify

- `backend/app/tool_gateway/gateway.py` - consult optional failure injector before read cache/provider execution.
- `backend/app/tool_gateway/__init__.py` - export failure-injection types if tests need them.
- `backend/app/workflow/dependencies.py` - add optional `failure_injector` dependency.
- `backend/app/workflow/nodes.py` - pass dependency injector into Tool Gateway.
- `backend/app/benchmark/fixtures.py` - add non-default failure case registry and loader.
- `backend/app/benchmark/__init__.py` - export `load_failure_benchmark_cases`.
- `backend/app/benchmark/schemas.py` - add backward-compatible expected outcome fields for expected failure behavior.
- `backend/app/benchmark/graders.py` - grade expected failed workflow outcomes, injected failures, and recovery expectations.
- `backend/app/benchmark/harness.py` - resolve failure profiles, pass injector to workflow, and include sanitized failure-profile metadata.
- `tests/test_benchmark_harness.py` - cover new fixture loading and failure-oriented graders.
- `tests/integration/test_tool_gateway.py` - verify injected read failure records a failed event without provider/cache use.
- `tests/integration/test_benchmark_harness_gateway.py` - run the non-default failure case through the harness.
- `tests/integration/test_langgraph_workflow_gateway.py` - optionally add direct workflow coverage with an injected route failure dependency.

## 5. Implementation Steps

1. Confirm preconditions:
   - Run `git status --short --branch`.
   - Confirm `docs/specs/029-locallife-bench-failure-injection-v0.md` exists.
   - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` remains unrelated and unstaged.

2. Create a dedicated branch if needed:
   - Recommended branch: `task29`.

3. Run the current focused baseline:
   - `python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v`
   - `python -m pytest tests/integration/test_tool_gateway.py -v`

4. Add failing unit tests in `tests/test_failure_injection.py`.
   - Assert `build_benchmark_failure_injector(None)` returns `None`.
   - Assert `build_benchmark_failure_injector("route_unavailable_v0")` returns an injector.
   - Assert the injector fails read-tool `check_route` with `error_type="failure_injected"`.
   - Assert the same injector does not fail `search_poi`.
   - Assert write-tool definitions are not injected.
   - Assert `build_benchmark_failure_injector("missing")` raises `BenchmarkHarnessError`.

5. Add `backend/app/tool_gateway/failure_injection.py`.
   - Define `ToolFailureInjectionDecision` with `status="failed"`, `response_json=None`, and sanitized `error_json`.
   - Define `ToolFailureInjector` protocol with `maybe_inject(request, definition, provider_name)`.
   - Define static rule/injector models that match by exact read-tool name.
   - Ensure generated error JSON uses:
     - `error_type="failure_injected"`
     - `message="Benchmark failure injected for tool call."`
     - `details.profile_id`
     - `details.rule_id`
     - `details.tool_name`
     - `details.injected_error_type`

6. Add `backend/app/benchmark/failure_profiles.py`.
   - Define `ROUTE_UNAVAILABLE_PROFILE_ID = "route_unavailable_v0"`.
   - Implement `build_benchmark_failure_injector(profile_id)`.
   - Implement `failure_profile_metadata(profile_id)` returning sanitized metadata for known profiles.
   - Unknown profile IDs must raise `BenchmarkHarnessError`.

7. Update Tool Gateway.
   - Add optional `failure_injector` argument to `ToolGateway.__init__`.
   - In `_invoke_read`, check the injector after tool/provider resolution and before rate-limit/cache/provider execution.
   - If injection matches, call `_record_result` with `status="failed"`, injected `error_json`, `response_json=None`, `cache_hit=False`, and `action_id=None`.
   - Do not call provider or cache for injected failures.
   - Do not apply injection in `_invoke_write`.

8. Update Tool Gateway exports.
   - Export `ToolFailureInjectionDecision`, `ToolFailureInjector`, and static injector classes only if tests or type imports need them.

9. Update workflow dependency wiring.
   - Add `failure_injector` to `WeekendPilotWorkflowDependencies`.
   - In `WeekendPilotWorkflowNodes.__init__`, pass `dependencies.failure_injector` to `ToolGateway`.
   - Keep existing callers working with default `None`.

10. Update benchmark harness wiring.
    - In `BenchmarkHarness._run_case`, resolve the injector from `case.failure_profile`.
    - Pass the injector into `WeekendPilotWorkflowDependencies`.
    - Continue passing `failure_profile=case.failure_profile` into `WeekendPilotWorkflowRequest`.
    - Add sanitized `failure_profile` and profile metadata to `agent_runs.metadata_json["benchmark"]`.

11. Update fixture loading.
    - Keep `_DEFAULT_CASE_IDS` unchanged with the five Task 028 cases.
    - Add `_FAILURE_CASE_IDS = ("family_route_failure_v1",)`.
    - Let `load_benchmark_case` load IDs from default or failure registries.
    - Add `load_failure_benchmark_cases()` returning failure cases in deterministic order.
    - Keep unknown case IDs raising `BenchmarkHarnessError`.

12. Add `family_route_failure_v1.json`.
    - Use `tool_profile="mock_world"` and `world_profile="family_afternoon"`.
    - Set `failure_profile="route_unavailable_v0"`.
    - Set `min_action_count=0`.
    - Set expected workflow status to `failed`.
    - Set expected error type to `recovery_stopped`.
    - Set expected recovery action to `stop_safely`.
    - Set `min_injected_failure_count=1`.
    - Set metadata suite `locallife_bench_v1`, level `L2`, focus `route_failure_safe_stop`.

13. Extend benchmark schemas.
    - Add `expected_workflow_status: str = "completed"`.
    - Change `expected_execution_status` and `expected_feedback_status` to `str | None` with existing happy-path defaults.
    - Add `expected_error_type: str | None = None`.
    - Add `expected_recovery_action: str | None = None`.
    - Add `min_injected_failure_count: int = 0`.

14. Update benchmark graders.
    - Update `grade_workflow_path` so completed cases keep current required-node behavior.
    - For expected failed/error cases, pass when workflow status matches and expected error type matches.
    - Add `grade_failure_injection(case, tool_events)` to count `error_json.error_type == "failure_injected"`.
    - Add `grade_recovery_expectation(case, run_metadata)` to validate expected recovery action from `workflow.recovery.attempts`.
    - Update `grade_execution_safety` and `grade_feedback` so `expected_*_status=None` means absence is acceptable.
    - Do not loosen completed happy-path grading.

15. Update `BenchmarkHarness._run_case` scoring.
    - Always grade workflow outcome, agent coverage, trajectory, injected failure count, execution safety, and feedback.
    - Grade plan quality only for expected completed workflows.
    - Grade recovery expectation when `case.expected.expected_recovery_action` is set.
    - Keep aggregate report behavior unchanged.

16. Update unit tests in `tests/test_benchmark_harness.py`.
    - Assert default case count/order remains five.
    - Assert failure case is not in defaults.
    - Assert `load_benchmark_case("family_route_failure_v1")` works.
    - Assert `load_failure_benchmark_cases()` returns exactly that case.
    - Add grader tests for expected failed workflow outcome.
    - Add grader tests for injected failure count.
    - Add grader tests for recovery action expectation.
    - Keep report sanitization tests.

17. Update `tests/integration/test_tool_gateway.py`.
    - Allow `build_gateway` helper to accept `failure_injector=None`.
    - Add a test where `check_route` is injected as failed.
    - Assert provider call count remains zero.
    - Assert no cache hit occurs.
    - Assert one failed `tool_events` row is written with sanitized injected error JSON.

18. Update `tests/integration/test_benchmark_harness_gateway.py`.
    - Import `load_failure_benchmark_cases` and `load_benchmark_case`.
    - Add a test for `family_route_failure_v1`.
    - Assert benchmark result status is `passed`.
    - Assert workflow status is `failed`.
    - Assert action count is zero.
    - Assert node history includes `apply_recovery`.
    - Assert node history does not include `saga_execution_engine`.
    - Assert failed `check_route` tool events include `failure_injected`.
    - Assert persisted workflow recovery attempt status is `stopped`.
    - Assert persisted benchmark metadata includes `failure_profile="route_unavailable_v0"`.
    - Assert report JSON excludes forbidden strings.

19. Optionally update `tests/integration/test_langgraph_workflow_gateway.py`.
    - Build a workflow runner with `failure_injector=build_benchmark_failure_injector("route_unavailable_v0")`.
    - Run with `failure_profile="route_unavailable_v0"` and `auto_confirm=False`.
    - Assert failed safe-stop behavior and zero Action Ledger rows.

20. Run focused unit tests:
    - `python -m pytest tests/test_failure_injection.py tests/test_benchmark_harness.py -v`

21. Run focused integration tests:
    - `python -m pytest tests/integration/test_tool_gateway.py -v`
    - `python -m pytest tests/integration/test_benchmark_harness_gateway.py -v`
    - `python -m pytest tests/integration/test_langgraph_workflow_gateway.py -v`

22. Run broad verification:
    - `python -m pytest -q`
    - `docker compose config`
    - `git diff --check`
    - `git status --short`

23. If the failure case does not stop safely:
    - Inspect route matrix and final review errors.
    - Prefer adjusting the failure fixture expected fields only if the observed behavior still proves safe-stop semantics.
    - Do not make recovery smarter, loosen graders, or add new workflow behavior outside Task 029.

24. Review changed files.
    - Confirm default benchmark cases and order are unchanged.
    - Confirm no write-tool failure injection was added.
    - Confirm no provider, frontend, migration, LLM, replay, or chaos behavior was added.
    - Confirm no generated `var/` reports or traces are staged.
    - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` is not staged.

25. Commit Task 029 only.

## 6. Testing Plan

- Unit tests:
  - failure profile registry resolves `route_unavailable_v0`.
  - unknown failure profiles raise `BenchmarkHarnessError`.
  - route injector fails `check_route` only.
  - failure case loads but is not included in defaults.
  - expected failed workflow grading passes only for matching status/error type.
  - injected failure count grading enforces minimum count.
  - recovery expectation grading validates `stop_safely`.

- Integration tests:
  - Tool Gateway injected read failure writes a failed tool event without provider invocation.
  - Benchmark harness runs the default five-case suite unchanged.
  - Benchmark harness runs `family_route_failure_v1` as a passing expected-failure benchmark.
  - Failure case records zero Action Ledger rows.
  - Failure case persists sanitized benchmark and recovery metadata.
  - Failure case report remains sanitized.

- Smoke tests:
  - full backend test suite passes.
  - Docker Compose configuration remains valid.
  - whitespace check passes with `git diff --check`.

## 7. Verification Commands

```bash
python -m pytest tests/test_failure_injection.py tests/test_benchmark_harness.py -v
python -m pytest tests/integration/test_tool_gateway.py -v
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest -q
docker compose config
git diff --check
git status --short
```

If PostgreSQL or Redis is not running, start required services and apply migrations before integration verification:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add locallife bench failure injection v0
```

Expected commands:

```bash
git status --short
git checkout -b task29
git add docs/specs/029-locallife-bench-failure-injection-v0.md docs/plans/029-locallife-bench-failure-injection-v0-plan.md
git add backend/app/tool_gateway/failure_injection.py backend/app/tool_gateway/gateway.py backend/app/tool_gateway/__init__.py
git add backend/app/workflow/dependencies.py backend/app/workflow/nodes.py
git add backend/app/benchmark/failure_profiles.py backend/app/benchmark/fixtures.py backend/app/benchmark/__init__.py backend/app/benchmark/schemas.py backend/app/benchmark/graders.py backend/app/benchmark/harness.py
git add backend/app/benchmark/cases/family_route_failure_v1.json
git add tests/test_failure_injection.py tests/test_benchmark_harness.py tests/integration/test_tool_gateway.py tests/integration/test_benchmark_harness_gateway.py tests/integration/test_langgraph_workflow_gateway.py
git diff --cached --check
git commit -m "feat: add locallife bench failure injection v0"
git push -u origin task29
```

Before committing, confirm `.env`, API keys, tokens, secrets, `var/`, `.venv`, caches, `node_modules`, `frontend/dist`, Playwright artifacts, and unrelated `docs/TASK_WORKFLOW_PROMPTS.md` are not staged.

## 9. Out-of-scope Changes

- Do not add LLM calls, prompts, model config, or LLM-backed agents.
- Do not add real provider support or change live AMAP behavior.
- Do not add a new Mock World profile or modify Mock World fixtures unless a test proves a fixture typo blocks Task 029.
- Do not inject failures into write tools.
- Do not execute write tools before explicit confirmation.
- Do not add replay, chaos harness, benchmark database tables, or migrations.
- Do not implement L3-L5 benchmark cases.
- Do not add recovery scoring beyond the minimal expected recovery action grader.
- Do not make the Validator & Recovery agent smarter.
- Do not loosen happy-path benchmark graders.
- Do not change Web demo API fields, frontend UI, or frontend tests.
- Do not change workflow node names, confirmation boundary behavior, Action Ledger semantics, or execution workflow behavior.
- Do not add dependencies.
- Do not commit generated reports, local traces, caches, virtual environments, frontend build output, or secrets.
- Do not stage unrelated local files.

## 10. Review Checklist

- [ ] Task 029 spec exists at `docs/specs/029-locallife-bench-failure-injection-v0.md`.
- [ ] Task 029 plan exists at `docs/plans/029-locallife-bench-failure-injection-v0-plan.md`.
- [ ] Default five benchmark cases and order are unchanged.
- [ ] `family_route_failure_v1` is non-default and loadable.
- [ ] `load_failure_benchmark_cases()` returns deterministic failure cases.
- [ ] `route_unavailable_v0` injects failed `check_route` read calls.
- [ ] Injected failures are recorded as failed tool events.
- [ ] Injected failures do not call the underlying provider.
- [ ] Injected failures bypass read cache reuse.
- [ ] Write tools are not failure-injected.
- [ ] Failure error JSON is typed and sanitized.
- [ ] Unknown failure profiles are not ignored.
- [ ] Failure benchmark passes as an expected safe-stop failure.
- [ ] Failure benchmark creates zero Action Ledger rows.
- [ ] Recovery metadata records a stopped `stop_safely` attempt.
- [ ] Benchmark metadata records sanitized failure-profile information.
- [ ] Reports remain sanitized.
- [ ] Existing happy-path benchmark suite still passes.
- [ ] Full backend test suite passes.
- [ ] `docker compose config` passes.
- [ ] `git diff --check` passes.
- [ ] No secrets or generated artifacts were staged.
- [ ] Commit message is `feat: add locallife bench failure injection v0`.
- [ ] Push succeeded or a clear reason for not pushing was reported.

## 11. Handoff Notes

Report back with:

- Branch name.
- Commit hash.
- Files changed.
- Confirmation that default benchmark cases are unchanged.
- Confirmation that `family_route_failure_v1` is non-default.
- Verification commands and pass/fail results.
- Any skipped command and exact environment reason.
- Confirmation that injected failures are sanitized and recorded as tool events.
- Confirmation that no pre-confirmation write actions are created during failure injection.
- Confirmation that no provider, frontend, migration, LLM, replay, or chaos behavior changed.
- Confirmation that `docs/TASK_WORKFLOW_PROMPTS.md` was not staged.
- Push result.
- Known limitation: Task 029 adds only deterministic v0 read-tool failure injection; replay, chaos testing, richer recovery scoring, write-tool failure injection, and L3-L5 benchmark cases remain future tasks.
