# Spec: 050 Benchmark L2/L3 Suite Expansion v0

## 1. Goal

Turn the existing post-049 benchmark inventory into explicit evaluable suite families so the newly added scenarios are no longer only scattered case IDs inside `default` and `all_registered`.

After this task, WeekendPilot should expose named benchmark suites for `baseline`, `expanded`, and `recovery_focused`, preserve the current ten-case non-failure `default` suite and the eleven-case `all_registered` suite, and write suite reports that directly show both coverage and pass rate across scenario family, constraint type, and failure type. This task is deliberately packaging-first and reporting-first: it should not add new benchmark fixtures or new workflow behavior. It should make the existing benchmark inventory easier to compare before any true L3 multi-turn benchmark authoring or broader failure-pack expansion lands.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and asks for small, reviewable tasks that improve evaluation quality before broader product expansion. `docs/NEXT_PHASE_ROADMAP.md` places this work in milestone `M3. Multi-scenario and benchmark expansion`.

The repository is already materially ahead of the original roadmap order:

- Task `039` added required benchmark taxonomy and suite-level case matrix summaries.
- Task `040` added the named suite catalog layer.
- Task `049` expanded the deterministic Mock World benchmark inventory from the legacy family-plus-solo baseline to the current ten-case non-failure pack plus the existing recovery case.
- Focused benchmark unit and integration tests are currently green on the `36aee8a feat: expand mock world scenario pack` commit.

That means the next real gap is not more raw observability and not more scenario authoring. The gap is suite structure and comparative reporting. Current benchmark coverage still has these limitations:

- the newly added couple/friends/rainy-day/budget cases are only grouped indirectly inside `default`
- there is no named suite for the historical baseline
- there is no named suite that isolates the new expansion pack
- there is no named suite that isolates recovery-focused cases while preserving current behavior
- suite reports currently expose `matrix_summary` coverage counts but not direct pass-rate rollups by scenario family, constraint type, or failure type

This task closes that M3 gap without widening into new fixtures, new multi-turn harness semantics, new public APIs, or frontend feature work.

## 3. Requirements

- Keep the canonical registered benchmark case order unchanged from Task `049`:
  - `family_afternoon_v1`
  - `family_indoor_light_meal_v1`
  - `family_outdoor_quick_dinner_v1`
  - `family_memory_override_v1`
  - `family_citywalk_addon_v1`
  - `solo_afternoon_v1`
  - `couple_afternoon_v1`
  - `friends_gathering_v1`
  - `rainy_day_fallback_v1`
  - `budget_lite_v1`
  - `family_route_failure_v1`

- Expand the canonical benchmark suite catalog so `list_benchmark_suites()` returns these exact suite IDs in this exact order:
  - `baseline`
  - `expanded`
  - `recovery_focused`
  - `default`
  - `all_registered`

- Keep `load_benchmark_suite("default")` supported and unchanged in meaning:
  - it must still load the current ten-case non-failure suite in canonical order

- Keep `load_default_benchmark_cases()` as a backward-compatible wrapper to the unchanged ten-case `default` suite.

- Keep `load_failure_benchmark_cases()` as a backward-compatible wrapper, but point it to the canonical `recovery_focused` suite.

- Keep `load_benchmark_suite("failures")` supported as a legacy alias to `recovery_focused`.
- `failures` must remain loadable for compatibility, but it must not be returned by `list_benchmark_suites()`.
- When `run_suite("failures")` is used, the persisted report metadata must normalize to canonical suite ID `recovery_focused`.

- Define these exact canonical suite memberships:

### Baseline

- Case IDs:
  - `family_afternoon_v1`
  - `family_indoor_light_meal_v1`
  - `family_outdoor_quick_dinner_v1`
  - `family_memory_override_v1`
  - `family_citywalk_addon_v1`
  - `solo_afternoon_v1`

### Expanded

- Case IDs:
  - `couple_afternoon_v1`
  - `friends_gathering_v1`
  - `rainy_day_fallback_v1`
  - `budget_lite_v1`

### Recovery Focused

- Case IDs:
  - `family_route_failure_v1`

### Default

- Case IDs:
  - all `baseline` cases in the exact listed order
  - followed by all `expanded` cases in the exact listed order

### All Registered

- Case IDs:
  - all `default` cases in the exact listed order
  - followed by all `recovery_focused` cases in the exact listed order

- `list_benchmark_suite_ids_for_case(case_id)` must return canonical membership only, in deterministic order:
  - `family_afternoon_v1` and the other five baseline cases -> `["baseline", "default", "all_registered"]`
  - `couple_afternoon_v1`, `friends_gathering_v1`, `rainy_day_fallback_v1`, and `budget_lite_v1` -> `["expanded", "default", "all_registered"]`
  - `family_route_failure_v1` -> `["recovery_focused", "all_registered"]`
  - `missing_case_v1` -> `[]`

- Keep `load_registered_benchmark_cases()` behavior unchanged.
- Keep `load_benchmark_case("missing_case")` raising `BenchmarkHarnessError`.

- Keep `BenchmarkSuiteDescription` as the suite-catalog contract, but populate it for the five canonical suites above.

- Add a typed additive report contract for suite outcome rollups.
- The additive rollup contract must include:
  - `schema_version`
  - `scenario_bucket_outcomes`
  - `constraint_tag_outcomes`
  - `failure_mode_outcomes`

- Each rollup bucket entry must include:
  - `case_count`
  - `passed_count`
  - `failed_count`
  - `error_count`
  - `pass_rate`

- `pass_rate` must be computed as `passed_count / case_count`, rounded to `4` decimal places.
- If `case_count == 0`, `pass_rate` must serialize as `0.0`.
- Rollups must use benchmark result status (`passed` / `failed` / `error`), not workflow status.

- Add `BenchmarkHarness.run_suite(suite_id)` as a first-class suite execution helper.
- `run_suite(suite_id)` must:
  - load cases from the canonical suite catalog
  - produce the same per-case execution behavior as `run_cases(cases)`
  - attach canonical `suite_id` and `suite_title` to the serialized benchmark summary
  - write a suite-specific report filename `suite-<canonical-suite-id>-run-report.json`

- Keep `BenchmarkHarness.run_cases(cases)` supported for ad hoc case lists.
- `run_cases(cases)` must continue writing `run-report.json`.
- `run_cases(cases)` may leave `suite_id = null` when no named suite context is supplied.
- `run_cases(cases)` must still populate the additive outcome-rollup summary.

- Add additive fields to `BenchmarkSummary`:
  - `suite_id`
  - `suite_title`
  - `outcome_rollup`

- Keep the existing `BenchmarkRunReport`, `BenchmarkSummary`, and `matrix_summary` fields present and backward compatible apart from these additive fields.

- Keep `matrix_summary` coverage semantics unchanged and exact for all suites.

- The `baseline` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"family": 5, "solo": 1}`
  - `level_counts={"L1": 3, "L2": 3}`
  - `world_profile_counts={"family_afternoon": 5, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 6}`
  - `tag_counts={"addon_optional": 1, "baseline": 2, "child_friendly": 5, "citywalk": 1, "indoor_activity": 2, "light_activity": 1, "light_meal": 4, "memory_override": 1, "outdoor_activity": 1, "quick_dinner": 1}`

- The `expanded` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"couple": 1, "friends": 1, "mixed": 1, "unknown": 1}`
  - `level_counts={"L2": 4}`
  - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "friends_gathering": 1, "rainy_day_fallback": 1}`
  - `failure_mode_counts={"none": 4}`
  - `tag_counts={"budget_limited": 1, "casual_dining": 1, "citywalk": 1, "date_friendly": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 1, "light_meal": 1, "outdoor_activity": 1, "quick_meal": 1, "rainy_day": 1}`

- The `recovery_focused` suite matrix summary must be exactly:
  - `scenario_bucket_counts={"family": 1}`
  - `level_counts={"L2": 1}`
  - `world_profile_counts={"family_afternoon": 1}`
  - `failure_mode_counts={"route_unavailable": 1}`
  - `tag_counts={"child_friendly": 1, "failure_injected": 1, "light_meal": 1, "route_failure": 1}`

- The `default` suite matrix summary must remain exactly the current Task `049` values:
  - `scenario_bucket_counts={"couple": 1, "family": 5, "friends": 1, "mixed": 1, "solo": 1, "unknown": 1}`
  - `level_counts={"L1": 3, "L2": 7}`
  - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 5, "friends_gathering": 1, "rainy_day_fallback": 1, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 10}`
  - `tag_counts={"addon_optional": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 5, "citywalk": 2, "date_friendly": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 3, "light_activity": 1, "light_meal": 5, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1}`

- The `all_registered` suite matrix summary must remain exactly the current Task `049` values:
  - `scenario_bucket_counts={"couple": 1, "family": 6, "friends": 1, "mixed": 1, "solo": 1, "unknown": 1}`
  - `level_counts={"L1": 3, "L2": 8}`
  - `world_profile_counts={"budget_lite": 1, "couple_afternoon": 1, "family_afternoon": 6, "friends_gathering": 1, "rainy_day_fallback": 1, "solo_afternoon": 1}`
  - `failure_mode_counts={"none": 10, "route_unavailable": 1}`
  - `tag_counts={"addon_optional": 1, "baseline": 2, "budget_limited": 1, "casual_dining": 1, "child_friendly": 6, "citywalk": 2, "date_friendly": 1, "failure_injected": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 3, "light_activity": 1, "light_meal": 6, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1, "route_failure": 1}`

- `constraint_tag_outcomes` must use the current taxonomy tags as the constraint dimension, but it must exclude these bookkeeping tags from the constraint rollup:
  - `baseline`
  - `failure_injected`
  - `route_failure`

- The `baseline` suite constraint-tag case counts must be exactly:
  - `{"addon_optional": 1, "child_friendly": 5, "citywalk": 1, "indoor_activity": 2, "light_activity": 1, "light_meal": 4, "memory_override": 1, "outdoor_activity": 1, "quick_dinner": 1}`

- The `expanded` suite constraint-tag case counts must be exactly:
  - `{"budget_limited": 1, "casual_dining": 1, "citywalk": 1, "date_friendly": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 1, "light_meal": 1, "outdoor_activity": 1, "quick_meal": 1, "rainy_day": 1}`

- The `recovery_focused` suite constraint-tag case counts must be exactly:
  - `{"child_friendly": 1, "light_meal": 1}`

- The `default` suite constraint-tag case counts must be exactly:
  - `{"addon_optional": 1, "budget_limited": 1, "casual_dining": 1, "child_friendly": 5, "citywalk": 2, "date_friendly": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 3, "light_activity": 1, "light_meal": 5, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1}`

- The `all_registered` suite constraint-tag case counts must be exactly:
  - `{"addon_optional": 1, "budget_limited": 1, "casual_dining": 1, "child_friendly": 6, "citywalk": 2, "date_friendly": 1, "fallback": 1, "free_activity": 1, "friends_group": 1, "indoor_activity": 3, "light_activity": 1, "light_meal": 6, "memory_override": 1, "outdoor_activity": 2, "quick_dinner": 1, "quick_meal": 1, "rainy_day": 1}`

- For the current green repository state, every canonical suite run must serialize `passed_count == case_count`, `failed_count == 0`, `error_count == 0`, and `pass_rate == 1.0` for every emitted scenario, constraint, and failure rollup bucket.

- `BenchmarkHarness.run_suite("baseline")` must return:
  - `6` case results
  - `run_status="passed"`
  - `passed_count=6`
  - `failed_count=0`
  - `error_count=0`
  - report filename ending in `suite-baseline-run-report.json`

- `BenchmarkHarness.run_suite("expanded")` must return:
  - `4` case results
  - `run_status="passed"`
  - `passed_count=4`
  - `failed_count=0`
  - `error_count=0`
  - report filename ending in `suite-expanded-run-report.json`

- `BenchmarkHarness.run_suite("recovery_focused")` must return:
  - `1` case result
  - `run_status="passed"`
  - `passed_count=1`
  - `failed_count=0`
  - `error_count=0`
  - report filename ending in `suite-recovery_focused-run-report.json`

- `BenchmarkHarness.run_suite("default")` must keep returning:
  - `10` case results
  - `run_status="passed"`

- `BenchmarkHarness.run_suite("all_registered")` must keep returning:
  - `11` case results
  - `run_status="passed"`

- `recovery_focused` and `all_registered` outcome rollups must treat `family_route_failure_v1` as:
  - `failure_mode="route_unavailable"`
  - benchmark outcome `passed`
  - workflow outcome still allowed to remain `failed`

- Update focused unit and integration tests to cover:
  - canonical suite descriptions and ordering
  - `failures` alias normalization
  - case-to-suite membership mapping
  - exact matrix-summary counts for `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered`
  - exact outcome-rollup counts and pass rates for canonical suites
  - suite-specific run report filenames
  - updated observability suite memberships for benchmark runs

- Update `README.md` benchmark documentation to describe:
  - the five canonical named suites
  - the `failures -> recovery_focused` compatibility behavior
  - suite-specific `suite-<suite_id>-run-report.json` files
  - coverage and pass-rate rollups in suite benchmark summaries

- Do not add new dependencies.
- Do not add or modify Alembic revisions.
- Do not add new benchmark case fixtures, new world fixtures, new failure profiles, new routes, or new public demo behavior.
- Do not change workflow logic, Tool Gateway behavior, replay semantics, or bounded-agent contracts.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add any new benchmark case JSON fixture in this task.
- Do not add real L3 multi-turn clarification or replan benchmark execution semantics in this task.
- Do not add new recovery routes or new failure-injection profiles.
- Do not change `BenchmarkCaseTaxonomy`, existing case IDs, existing world profiles, or deterministic planner behavior.
- Do not add CLI commands, HTTP routes, or frontend controls for suite selection.
- Do not redesign observability schemas beyond additive suite-ID value changes and additive benchmark-summary fields.
- Do not modify the currently untracked local `047` or `049` doc drafts, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `qc`, or generated `var/` artifacts as part of this task.

## 5. Interfaces and Contracts

### Inputs

This task depends on the existing benchmark suite and reporting layer:

- `load_benchmark_case(case_id)`
- `load_registered_benchmark_cases()`
- `load_benchmark_suite(suite_id)`
- `load_default_benchmark_cases()`
- `load_failure_benchmark_cases()`
- `list_benchmark_suites()`
- `list_benchmark_suite_ids_for_case(case_id)`
- `BenchmarkHarness.run_case(case)`
- `BenchmarkHarness.run_cases(cases)`

### Outputs

Additive benchmark execution helper:

- `BenchmarkHarness.run_suite(suite_id) -> BenchmarkRunReport`

Updated suite catalog outputs:

- canonical suite IDs `baseline`, `expanded`, `recovery_focused`, `default`, `all_registered`
- legacy load alias `failures -> recovery_focused`

Additive benchmark summary fields:

- `BenchmarkSummary.suite_id`
- `BenchmarkSummary.suite_title`
- `BenchmarkSummary.outcome_rollup`

Suite-specific report filenames:

- `suite-baseline-run-report.json`
- `suite-expanded-run-report.json`
- `suite-recovery_focused-run-report.json`
- `suite-default-run-report.json`
- `suite-all_registered-run-report.json`

### Schemas

Suite benchmark summary shape after this task:

```json
{
  "schema_version": "weekendpilot_benchmark_summary_v1",
  "suite_id": "expanded",
  "suite_title": "Expanded scenario benchmark suite",
  "run_status": "passed",
  "case_count": 4,
  "passed_count": 4,
  "failed_count": 0,
  "error_count": 0,
  "overall_score": 1.0,
  "matrix_summary": {
    "schema_version": "weekendpilot_benchmark_case_matrix_v1",
    "case_count": 4,
    "scenario_bucket_counts": {
      "couple": 1,
      "friends": 1,
      "mixed": 1,
      "unknown": 1
    },
    "level_counts": {
      "L2": 4
    },
    "world_profile_counts": {
      "budget_lite": 1,
      "couple_afternoon": 1,
      "friends_gathering": 1,
      "rainy_day_fallback": 1
    },
    "failure_mode_counts": {
      "none": 4
    },
    "tag_counts": {
      "budget_limited": 1,
      "casual_dining": 1,
      "citywalk": 1,
      "date_friendly": 1,
      "fallback": 1,
      "free_activity": 1,
      "friends_group": 1,
      "indoor_activity": 1,
      "light_meal": 1,
      "outdoor_activity": 1,
      "quick_meal": 1,
      "rainy_day": 1
    }
  },
  "outcome_rollup": {
    "schema_version": "weekendpilot_benchmark_outcome_rollup_v1",
    "scenario_bucket_outcomes": {
      "couple": {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      },
      "friends": {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      },
      "mixed": {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      },
      "unknown": {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      }
    },
    "constraint_tag_outcomes": {
      "budget_limited": {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      },
      "rainy_day": {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      }
    },
    "failure_mode_outcomes": {
      "none": {
        "case_count": 4,
        "passed_count": 4,
        "failed_count": 0,
        "error_count": 0,
        "pass_rate": 1.0
      }
    }
  }
}
```

Compatibility notes:

- `load_benchmark_suite("failures")` remains allowed input.
- `list_benchmark_suites()` and serialized suite summaries must use canonical suite ID `recovery_focused`, not `failures`.
- `run_cases(cases)` remains valid for ad hoc case lists and may serialize `suite_id = null`.

## 6. Observability

This task should not add a new telemetry backend or a new frontend surface.

It must preserve current benchmark artifact behavior while adding richer suite reporting:

- per-case reports remain sanitized and unchanged apart from any existing benchmark metadata
- suite run reports gain additive `suite_id`, `suite_title`, and `outcome_rollup`
- internal observability benchmark artifact summaries may surface new canonical suite memberships through the existing `registered_suite_ids` array
- no new observability API route is added
- no new frontend page is added

All new report fields must remain compatible with the current sanitization rules. They must not expose:

- secrets
- API keys
- tokens
- authorization headers
- prompts
- raw tool payloads
- raw action payloads
- raw tracebacks

## 7. Failure Handling

- Unknown canonical suite IDs must keep raising `BenchmarkHarnessError`.
- `load_benchmark_suite("failures")` must resolve to canonical suite definition `recovery_focused`; it must not raise.
- Invalid suite definitions must still fail fast with `BenchmarkHarnessError`, including:
  - duplicate case IDs inside one suite
  - unknown registered case IDs referenced by a suite
- If a benchmark result used for rollup building is missing taxonomy unexpectedly, rollup construction must fail explicitly rather than silently skipping that case.
- `failure_mode_outcomes` must always use explicit key `"none"` for cases whose taxonomy sets `failure_mode = null`.
- If report writing fails, the current typed `BenchmarkHarnessError` behavior must remain unchanged.
- `recovery_focused` must continue to count the recovery case as benchmark `passed` even though the underlying workflow status remains `failed`.
- This task does not need to backfill old benchmark JSON files already on disk under `var/`.

## 8. Acceptance Criteria

- [ ] `docs/specs/050-benchmark-l2-l3-suite-expansion-v0.md` exists and matches this task.
- [ ] `docs/plans/050-benchmark-l2-l3-suite-expansion-v0-plan.md` exists and matches this task.
- [ ] `list_benchmark_suites()` returns exactly `["baseline", "expanded", "recovery_focused", "default", "all_registered"]` in that order.
- [ ] `load_benchmark_suite("failures")` still works and resolves to the same case list as `load_benchmark_suite("recovery_focused")`.
- [ ] `load_failure_benchmark_cases()` now delegates to the canonical `recovery_focused` suite.
- [ ] `list_benchmark_suite_ids_for_case("family_afternoon_v1") == ["baseline", "default", "all_registered"]`.
- [ ] `list_benchmark_suite_ids_for_case("couple_afternoon_v1") == ["expanded", "default", "all_registered"]`.
- [ ] `list_benchmark_suite_ids_for_case("family_route_failure_v1") == ["recovery_focused", "all_registered"]`.
- [ ] The `baseline`, `expanded`, `recovery_focused`, `default`, and `all_registered` suites use the exact case memberships defined in this spec.
- [ ] The `baseline`, `expanded`, and `recovery_focused` matrix summaries exactly match the counts defined in this spec.
- [ ] The `default` and `all_registered` matrix summaries remain exactly the current Task `049` counts.
- [ ] `BenchmarkSummary` includes additive `suite_id`, `suite_title`, and `outcome_rollup` fields.
- [ ] `BenchmarkHarness.run_suite("baseline")` passes with `6` case results and writes `suite-baseline-run-report.json`.
- [ ] `BenchmarkHarness.run_suite("expanded")` passes with `4` case results and writes `suite-expanded-run-report.json`.
- [ ] `BenchmarkHarness.run_suite("recovery_focused")` passes with `1` case result and writes `suite-recovery_focused-run-report.json`.
- [ ] `BenchmarkHarness.run_suite("all_registered")` passes with `11` case results and writes `suite-all_registered-run-report.json`.
- [ ] The additive `outcome_rollup` shows direct per-dimension case counts and pass rates for scenario family, constraint tag, and failure mode.
- [ ] The current green suite inventory serializes `pass_rate = 1.0` for every emitted rollup bucket.
- [ ] The constraint rollup excludes `baseline`, `failure_injected`, and `route_failure`.
- [ ] Internal observability benchmark artifact summaries reflect the updated canonical suite memberships.
- [ ] No new benchmark fixtures, world fixtures, failure profiles, workflow routes, public routes, frontend features, migrations, or dependencies are added.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] Focused unit and integration verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing unrelated local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_observability.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_observability_gateway.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add benchmark suite coverage rollups
```

## 11. Notes for the Implementer

Keep this task tightly scoped to suite organization and reporting.

Important defaults chosen here:

- `baseline` is the historical six-case family-plus-solo non-failure suite.
- `expanded` is the four-case scenario pack added by Task `049`.
- `recovery_focused` is the current failure/recovery suite.
- `default` remains the current ten-case non-failure union of `baseline + expanded`.
- `all_registered` remains `default + recovery_focused`.
- `failures` is kept only as a compatibility alias and should normalize to canonical suite ID `recovery_focused`.
- Constraint rollups deliberately reuse current taxonomy tags and only exclude bookkeeping tags `baseline`, `failure_injected`, and `route_failure`.

Do not widen this task into true multi-turn L3 benchmark case authoring. The slug keeps the planned roadmap naming, but this v0 should only make the current inventory measurable as suites. If later work needs clarification-turn, replan-turn, or other genuine L3 dialogue benchmarks, that should be a follow-up task after this suite/report layer is stable.
