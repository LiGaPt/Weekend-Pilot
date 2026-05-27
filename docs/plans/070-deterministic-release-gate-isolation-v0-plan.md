# Plan: 070 Deterministic Release Gate Isolation v0

## 1. Spec Reference

Spec file:

```text
docs/specs/070-deterministic-release-gate-isolation-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/playwright-e2e-rate-limit-isolation-v0`.
- Latest completed task on disk is `069-playwright-e2e-rate-limit-isolation-v0`.
- Latest commit is `f8af8af fix: isolate web demo rate limits`, and it matches task `069`.
- `docs/specs/` and `docs/plans/` are continuous through `069`.
- Current unrelated dirty files are:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `docs/artifacts/`
  - `qc`
- Those unrelated local changes must remain unstaged throughout this task.
- Task `031` already introduced optional LLM-backed bounded agents through explicit workflow settings injection at the workflow dependency layer.
- `backend/app/workflow/dependencies.py` already supports `settings` and `llm_client`.
- `backend/app/benchmark/harness.py` does not currently thread those explicit settings into workflow execution.
- `backend/app/demo/service.py` does not currently thread explicit settings into workflow execution.
- `backend/app/benchmark/release_gate.py` currently constructs `BenchmarkHarness` without explicit workflow settings, so the gate can inherit local preview env through `get_settings()`.
- The benchmark/runtime path does not currently instantiate `LangSmithRecorder`; LangSmith isolation in this task is a settings-contract fix, not a new observability feature.

## 3. Files to Add

- `docs/specs/070-deterministic-release-gate-isolation-v0.md` - task spec.
- `docs/plans/070-deterministic-release-gate-isolation-v0-plan.md` - implementation plan.

## 4. Files to Modify

- `README.md` - document that the blocking release gate ignores local LLM/LangSmith preview settings.
- `backend/app/api/demo.py` - pass explicit workflow settings into `DemoWorkflowService`.
- `backend/app/benchmark/harness.py` - accept and propagate explicit workflow settings and optional workflow LLM client for both legacy and continuation benchmark paths.
- `backend/app/benchmark/release_gate.py` - build deterministic release-gate settings and pass them into `BenchmarkHarness`.
- `backend/app/demo/service.py` - accept and propagate explicit workflow settings and optional workflow LLM client into workflow starts, clarifications, and replans.
- `tests/test_benchmark_harness.py` - add focused tests for benchmark-path settings propagation.
- `tests/test_benchmark_release_gate.py` - add focused tests for deterministic settings injection and unchanged release-gate finalization behavior.
- `tests/integration/test_benchmark_release_gate.py` - add end-to-end proof that the release gate ignores fake full `LLM_*` env and still persists deterministic adapter versions.

## 5. Implementation Steps

1. Save the approved Task `070` spec and plan files at the target paths before editing code.
2. Extend `BenchmarkHarness.__init__(...)` with optional `workflow_settings` and optional `workflow_llm_client` fields, store them on the harness instance, and keep the default `None` behavior unchanged.
3. In the legacy benchmark case path inside `backend/app/benchmark/harness.py`, pass the stored explicit settings and optional workflow LLM client into `WeekendPilotWorkflowDependencies(...)`.
4. In the continuation benchmark case path inside `backend/app/benchmark/harness.py`, pass the same stored explicit settings and optional workflow LLM client into `DemoWorkflowService(...)`.
5. Extend `DemoWorkflowService.__init__(...)` with optional `workflow_settings` and optional `workflow_llm_client` fields, store them, and keep existing behavior unchanged when they are omitted.
6. Update `DemoWorkflowService.start_run(...)`, `clarify_run(...)`, and `replan_run(...)` so every `WeekendPilotWorkflowDependencies(...)` call forwards `settings=self.workflow_settings` and `llm_client=self.workflow_llm_client`.
7. Update `backend/app/api/demo.py` so `_build_service(...)` passes the FastAPI `settings` dependency into `DemoWorkflowService` explicitly. This preserves current product behavior without hidden fallback.
8. In `backend/app/benchmark/release_gate.py`, add one private helper that derives a deterministic release-gate settings object from the current settings using an explicit copy-and-override approach.
9. In that helper, force:
   - `llm_enabled = False`
   - `llm_api_key = None`
   - `llm_base_url = None`
   - `llm_model_id = None`
   - `langsmith_tracing = False`
   - `langchain_tracing_v2 = False`
   - `langsmith_api_key = None`
   - `langsmith_endpoint = None`
10. Keep unrelated runtime values intact in the copied settings object, especially database URL, Redis URL, app name, app env, and local trace buffer path.
11. Pass the deterministic settings object into `BenchmarkHarness(...)` from `run_benchmark_release_gate(...)`.
12. Do not implement the release-gate fix by mutating process env or clearing the global `get_settings()` cache as the primary mechanism.
13. Add a focused unit test in `tests/test_benchmark_harness.py` that proves the legacy benchmark path forwards explicit workflow settings into `WeekendPilotWorkflowDependencies`.
14. Add a focused unit test in `tests/test_benchmark_harness.py` that proves the continuation benchmark path forwards explicit workflow settings into `DemoWorkflowService`.
15. Add a focused unit test in `tests/test_benchmark_release_gate.py` that captures the `BenchmarkHarness` constructor call and asserts the injected settings force LLM and LangSmith preview settings off.
16. Keep existing release-gate unit assertions for latest-alias refresh, blocked-run preservation, and CLI exit codes unchanged.
17. Add an integration test in `tests/integration/test_benchmark_release_gate.py` that:
   - sets complete fake `LLM_*` env
   - monkeypatches `backend.app.agents.factory.OpenAICompatibleChatClient` with a fake client that records calls and returns valid payloads if used
   - runs `run_benchmark_release_gate(output_root=<temp>, start_services=False)`
   - asserts the fake client call count stays `0`
   - loads the persisted run rows created by the gate and asserts all agent adapter versions remain deterministic
18. In that same integration test, include continuation-case coverage indirectly by using the real `release_gate_v1` suite, which already contains clarification and replan continuation cases.
19. Update the `README.md` Benchmark Release Gate section to say the blocking gate is deterministic, ignores local LLM/LangSmith preview settings, and does not evaluate LLM-backed preview adapters.
20. Run focused unit tests first, then integration tests, then the real release-gate script, then `git diff --check`, then `git status --short`.
21. Stage only task-relevant files plus the new Task `070` spec/plan docs. Leave unrelated dirty files unstaged.

## 6. Testing Plan

- Unit tests:
  - explicit workflow settings are forwarded by `BenchmarkHarness` legacy runs
  - explicit workflow settings are forwarded by `BenchmarkHarness` continuation runs
  - `run_benchmark_release_gate(...)` injects deterministic settings
  - existing latest-alias and blocked-run unit behavior remains green

- Integration tests:
  - release gate ignores complete fake `LLM_*` env
  - fake OpenAI-compatible client is never called during `release_gate_v1`
  - persisted gate run metadata contains deterministic adapter versions only
  - continuation cases in the gate remain covered because they are already part of `release_gate_v1`

- Regression tests:
  - existing direct workflow LLM preview integration still passes without modification

- Smoke tests:
  - `python scripts/run_benchmark_release_gate.py`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_release_gate.py tests/integration/test_workflow_llm_agents_gateway.py -q
python scripts/run_benchmark_release_gate.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
fix: isolate release gate runtime settings
```

Expected commands:

```bash
git status --short
git switch -c codex/deterministic-release-gate-isolation-v0
git add docs/specs/070-deterministic-release-gate-isolation-v0.md
git add docs/plans/070-deterministic-release-gate-isolation-v0-plan.md
git add README.md backend/app/api/demo.py backend/app/benchmark/harness.py backend/app/benchmark/release_gate.py backend/app/demo/service.py
git add tests/test_benchmark_harness.py tests/test_benchmark_release_gate.py tests/integration/test_benchmark_release_gate.py
git commit -m "fix: isolate release gate runtime settings"
git push -u origin codex/deterministic-release-gate-isolation-v0
```

The implementer must confirm `.env`, secrets, generated `var/` artifacts, `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, `docs/artifacts/`, and `qc` are not staged.

## 9. Out-of-scope Changes

- Do not change `release_gate_v1` suite membership, thresholds, matrix checks, or artifact filenames.
- Do not change `all_registered` or refactor `run_formal_verification.py` in this task.
- Do not change LLM adapter prompt logic, fallback logic, or output schema.
- Do not add new LangSmith runtime wiring, new recorder builders, or new observability API routes.
- Do not change public demo API request or response schemas.
- Do not change frontend behavior, Playwright specs, benchmark graders, or recovery logic.
- Do not commit generated artifacts, local traces, caches, virtual environments, or secrets.
- Do not clean or revert unrelated local dirty files.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `BenchmarkHarness` and `DemoWorkflowService` now thread explicit workflow settings through the benchmark gate path.
- [ ] `run_benchmark_release_gate(...)` injects deterministic settings without relying on env hacks.
- [ ] Under fake complete `LLM_*` env, the release gate still uses deterministic adapter versions only.
- [ ] The fake OpenAI-compatible client is never called in the new integration proof.
- [ ] Existing release-gate threshold and artifact behavior from Task `065` is unchanged.
- [ ] Existing workflow LLM preview integration still passes.
- [ ] `README.md` clearly states that the blocking gate ignores local LLM/LangSmith preview settings.
- [ ] Required tests and smoke commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit except for pre-existing unrelated local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files.
- The exact deterministic settings fields forced by the release gate.
- Whether the harness and continuation service now both accept explicit workflow settings.
- The fake `LLM_*` env integration result and whether the fake client recorded zero calls.
- Verification commands and results.
- Commit hash.
- Push result.
- Known limitation:
  - the current benchmark/runtime path still does not instantiate `LangSmithRecorder`; this task locks the gate boundary at the settings-contract level rather than adding new LangSmith runtime plumbing.
