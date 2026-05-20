# Spec: 040 Benchmark Suite Catalog v0

## 1. Goal

Add a canonical benchmark suite catalog so benchmark suite composition is no longer scattered across hardcoded helper lists.

After this task, the repository should expose one named suite-loading layer for the current benchmark fixture set. The catalog must provide stable suite IDs for the current benchmark inventory, preserve the existing default and failure suite behavior, and expose derived matrix summaries built from the Task 039 taxonomy. This task should make suite composition reviewable and explicit before any larger scenario expansion or future case-generation tooling is added.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and asks for small, reviewable tasks. `docs/NEXT_PHASE_ROADMAP.md` says the next major milestone after the M1/M2 baseline is `M3. 多场景与 benchmark 扩展`.

The repository has already moved partway into that milestone:

- Task `038` added the first non-family benchmark scenario with `solo_afternoon`.
- Task `039` added required benchmark taxonomy and suite-level `matrix_summary`.

That means the next missing layer is no longer raw benchmark structure. The missing layer is benchmark suite composition. Current suite membership is still encoded only through `_DEFAULT_CASE_IDS` and `_FAILURE_CASE_IDS` in `backend/app/benchmark/fixtures.py`, so adding or reviewing suite variants still requires ad hoc code edits instead of a single explicit catalog.

This task corresponds to the next smallest piece of the roadmap's benchmark-expansion direction. It does not attempt full case generation. It introduces the suite catalog that later generation or expansion tasks should target.

## 3. Requirements

- Add one canonical registered benchmark case order covering every current fixture-backed benchmark case.
- The canonical registered case order must include these exact case IDs in this exact order:
  - `family_afternoon_v1`
  - `family_indoor_light_meal_v1`
  - `family_outdoor_quick_dinner_v1`
  - `family_memory_override_v1`
  - `family_citywalk_addon_v1`
  - `solo_afternoon_v1`
  - `family_route_failure_v1`
- Add one named benchmark suite catalog for the current repository state.
- The catalog must define exactly these suite IDs in v0:
  - `default`
  - `failures`
  - `all_registered`
- Add a typed suite description contract named `BenchmarkSuiteDescription`.
- `BenchmarkSuiteDescription` must include:
  - `suite_id`
  - `title`
  - `description`
  - ordered `case_ids`
  - `case_count`
  - `matrix_summary`
- Add a helper `load_registered_benchmark_cases()` that returns all registered cases in canonical order.
- Add a helper `load_benchmark_suite(suite_id)` that loads the named suite and returns ordered `BenchmarkCase` objects.
- Add a helper `list_benchmark_suites()` that returns deterministic suite descriptions in this exact order:
  - `default`
  - `failures`
  - `all_registered`
- `list_benchmark_suites()` must derive `matrix_summary` with the existing Task 039 `build_case_matrix_summary(...)` helper. It must not duplicate matrix-counting logic.
- Keep `load_default_benchmark_cases()` as a public backward-compatible wrapper.
- Keep `load_failure_benchmark_cases()` as a public backward-compatible wrapper.
- `load_default_benchmark_cases()` must delegate to the new suite catalog and still return these exact case IDs in this exact order:
  - `family_afternoon_v1`
  - `family_indoor_light_meal_v1`
  - `family_outdoor_quick_dinner_v1`
  - `family_memory_override_v1`
  - `family_citywalk_addon_v1`
  - `solo_afternoon_v1`
- `load_failure_benchmark_cases()` must delegate to the new suite catalog and still return:
  - `family_route_failure_v1`
- `load_benchmark_suite("all_registered")` must return the six default cases followed by `family_route_failure_v1`, for a total of `7` cases.
- The `default` suite matrix summary must remain:
  - `scenario_bucket_counts={"family": 5, "solo": 1}`
  - `level_counts={"L1": 3, "L2": 3}`
  - `world_profile_counts={"family_afternoon": 5, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 6}`
- The `all_registered` suite matrix summary must be:
  - `scenario_bucket_counts={"family": 6, "solo": 1}`
  - `level_counts={"L1": 3, "L2": 4}`
  - `world_profile_counts={"family_afternoon": 6, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 6, "route_unavailable": 1}`
- The `all_registered` suite `tag_counts` must be:
  - `addon_optional=1`
  - `baseline=2`
  - `child_friendly=6`
  - `citywalk=1`
  - `failure_injected=1`
  - `indoor_activity=2`
  - `light_activity=1`
  - `light_meal=5`
  - `memory_override=1`
  - `outdoor_activity=1`
  - `quick_dinner=1`
  - `route_failure=1`
- Unknown suite IDs must raise `BenchmarkHarnessError`.
- Invalid suite definitions must fail fast with `BenchmarkHarnessError`. This includes:
  - unknown registered case IDs referenced by a suite
  - duplicate case IDs inside one suite definition
- Update `backend.app.benchmark.__all__` exports so the new helpers are available from `backend.app.benchmark`.
- Add focused unit coverage for the suite catalog.
- Add focused gateway-backed integration coverage showing that `BenchmarkHarness.run_cases(load_benchmark_suite("all_registered"))` still succeeds under current benchmark semantics.
- Update `README.md` to document the named suite catalog at a high level.
- Do not add new benchmark cases, new taxonomy fields, new routes, new frontend pages, new database tables, new Alembic migrations, or new dependencies.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add prompt-driven case generation, fixture synthesis, or case-template authoring in this task.
- Do not introduce a generic benchmark query DSL or taxonomy-filter language in this task.
- Do not silently redefine the current default suite based on all non-failure cases found on disk.
- Do not change benchmark scoring, replay stable-field comparison, workflow routing, Tool Gateway behavior, or observability payload schemas.
- Do not add CLI commands, API endpoints, or frontend controls for suite selection.
- Do not edit completed historical specs/plans `001`-`039`.
- Do not stage or commit `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, generated `var/` artifacts, or other unrelated local files.

## 5. Interfaces and Contracts

### Inputs

This task depends on the existing benchmark fixture and reporting layer:

- fixture-backed benchmark cases under `backend/app/benchmark/cases/`
- `BenchmarkCase.taxonomy`
- `load_benchmark_case(case_id)`
- `build_case_matrix_summary(cases)`
- existing `BenchmarkHarness.run_case(...)`
- existing `BenchmarkHarness.run_cases(cases)`

### Outputs

Additive Python helper outputs:

- `load_registered_benchmark_cases()`
- `load_benchmark_suite(suite_id)`
- `list_benchmark_suites()`

Backward-compatible wrappers:

- `load_default_benchmark_cases()`
- `load_failure_benchmark_cases()`

Additive typed contract:

- `BenchmarkSuiteDescription`

### Schemas

`BenchmarkSuiteDescription` should serialize like this:

```json
{
  "suite_id": "all_registered",
  "title": "All registered benchmark cases",
  "description": "Current default plus failure cases in canonical repository order.",
  "case_ids": [
    "family_afternoon_v1",
    "family_indoor_light_meal_v1",
    "family_outdoor_quick_dinner_v1",
    "family_memory_override_v1",
    "family_citywalk_addon_v1",
    "solo_afternoon_v1",
    "family_route_failure_v1"
  ],
  "case_count": 7,
  "matrix_summary": {
    "schema_version": "weekendpilot_benchmark_case_matrix_v1",
    "case_count": 7,
    "scenario_bucket_counts": {
      "family": 6,
      "solo": 1
    },
    "level_counts": {
      "L1": 3,
      "L2": 4
    },
    "world_profile_counts": {
      "family_afternoon": 6,
      "solo_afternoon": 1
    },
    "failure_mode_counts": {
      "none": 6,
      "route_unavailable": 1
    },
    "tag_counts": {
      "addon_optional": 1,
      "baseline": 2,
      "child_friendly": 6,
      "citywalk": 1,
      "failure_injected": 1,
      "indoor_activity": 2,
      "light_activity": 1,
      "light_meal": 5,
      "memory_override": 1,
      "outdoor_activity": 1,
      "quick_dinner": 1,
      "route_failure": 1
    }
  }
}
```

Notes:

- `matrix_summary` reuses the existing Task 039 contract.
- The suite catalog is a Python/repository contract only in v0. It is not a new HTTP or CLI contract.
- `default` and `failures` remain explicit named suites. They are not inferred at runtime from taxonomy alone.

## 6. Observability

This task should not add a new telemetry path.

It must preserve current benchmark report and observability behavior. The new suite descriptions are derived from already-sanitized taxonomy and matrix-summary data. This task must not expose:

- secrets
- API keys
- tokens
- authorization headers
- prompts
- raw tool payloads
- raw action payloads
- raw tracebacks

This task does not change `BenchmarkCaseResult`, `BenchmarkRunReport`, `run_summary`, `benchmark_summary`, or replay report schemas.

## 7. Failure Handling

- If `load_benchmark_suite(...)` receives an unknown suite ID, it must raise `BenchmarkHarnessError`.
- If a suite definition contains duplicate case IDs, suite loading/listing must fail fast with `BenchmarkHarnessError`.
- If a suite definition references an unknown registered case ID, suite loading/listing must fail fast with `BenchmarkHarnessError`.
- If an underlying fixture file is missing, malformed, or invalid, the existing `load_benchmark_case(...)` typed error path must remain unchanged.
- If `BenchmarkHarness.run_cases(...)` receives a suite-loaded case list, current benchmark pass/fail/error semantics must remain unchanged.

## 8. Acceptance Criteria

- [ ] `docs/specs/040-benchmark-suite-catalog-v0.md` exists and matches this task.
- [ ] A canonical registered benchmark case order exists for all current fixture-backed cases.
- [ ] `load_registered_benchmark_cases()` returns exactly `7` cases in canonical order.
- [ ] A named suite catalog exists with suite IDs `default`, `failures`, and `all_registered`.
- [ ] `list_benchmark_suites()` returns descriptions in deterministic order: `default`, `failures`, `all_registered`.
- [ ] `load_default_benchmark_cases()` still returns the exact current six-case default suite in the same order.
- [ ] `load_failure_benchmark_cases()` still returns the exact current failure suite in the same order.
- [ ] `load_benchmark_suite("all_registered")` returns exactly `7` cases with `family_route_failure_v1` appended after the current default six cases.
- [ ] `BenchmarkSuiteDescription` includes `suite_id`, `title`, `description`, ordered `case_ids`, `case_count`, and `matrix_summary`.
- [ ] The `default` suite matrix summary matches the current Task 039 counts exactly.
- [ ] The `all_registered` suite matrix summary matches the exact counts listed in this spec.
- [ ] Unknown suite IDs raise `BenchmarkHarnessError`.
- [ ] Invalid suite definitions fail fast with `BenchmarkHarnessError`.
- [ ] `backend.app.benchmark` exports the new suite helpers.
- [ ] `BenchmarkHarness.run_cases(load_benchmark_suite("all_registered"))` succeeds with current benchmark semantics and `case_count == 7`.
- [ ] `README.md` documents the new suite catalog at a high level.
- [ ] No benchmark scoring, replay comparison, workflow routing, report schema, route, frontend, migration, or dependency change is added.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add benchmark suite catalog
```

## 11. Notes for the Implementer

Keep this task deliberately small.

The catalog should centralize current suite composition, not invent a generic selection engine. In v0, default-suite membership must remain explicit and stable so future case additions do not silently change the baseline.

Use the existing Task 039 taxonomy and matrix-summary helper as-is. Do not duplicate matrix-counting logic. Do not broaden this task into fixture generation, suite-filter DSLs, or new scenario authoring.

The implementer should stop and report back if this spec conflicts with the existing benchmark fixture inventory or with `docs/PROJECT_BLUEPRINT.md`.
