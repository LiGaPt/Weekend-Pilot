# Spec: 039 Benchmark Case Taxonomy and Matrix Summary v0

## 1. Goal

Add a typed benchmark case taxonomy and a suite-level matrix summary so WeekendPilot can compare benchmark coverage across scenarios without relying on ad hoc free-text fixture metadata.

After this task, every benchmark case fixture under `backend/app/benchmark/cases/` should declare a required structured `taxonomy` block. Each case report should embed that taxonomy, and each suite `run-report.json` should include a compact `matrix_summary` that counts cases by scenario bucket, benchmark level, world profile, failure mode, and tag. This task does not add new scenarios; it makes the current benchmark suite structurally comparable before more scenario expansion lands.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as benchmark-driven and observable by default. `docs/NEXT_PHASE_ROADMAP.md` says the next phase should first make evaluation and observability comparable, then expand scenario coverage.

The actual repository state is ahead of the roadmap text:

- Tasks `033`-`037` already delivered the M1/M2 baseline for workflow timing, benchmark summaries, internal observability, and public/internal view separation.
- Task `038` added the first non-family benchmark scenario with `world_profile="solo_afternoon"`.

That means the next real gap is no longer raw observability. The gap is benchmark structure. Current benchmark fixtures still depend on free-form `metadata` fields such as `suite`, `level`, and `focus`, and current suite reports do not expose a structured scenario matrix. If more scenarios are added now, the suite will keep growing without a stable taxonomy for comparison.

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M3. 多场景与 benchmark 扩展`, but it is intentionally infrastructure-first. It adds the minimum typed taxonomy and matrix summary needed to support future scenario expansion cleanly, while preserving the current workflow, Tool Gateway, Human Confirmation, Action Ledger, replay, and frontend behavior.

## 3. Requirements

- Add a required `BenchmarkCaseTaxonomy` contract to the benchmark schema layer.
- `BenchmarkCase.taxonomy` must be required for all fixture-backed benchmark cases.
- `BenchmarkCaseTaxonomy` must include:
  - `suite`
  - `scenario_bucket`
  - `level`
  - `tags`
  - `failure_mode`
- `taxonomy.suite` must currently accept only `locallife_bench_v1`.
- `taxonomy.scenario_bucket` must accept only:
  - `family`
  - `solo`
  - `friends`
  - `couple`
  - `elder`
  - `mixed`
  - `unknown`
- `taxonomy.level` must accept only:
  - `L1`
  - `L2`
  - `L3`
  - `L4`
  - `L5`
- `taxonomy.tags` must be a list of unique non-empty lower-snake-case strings.
- `taxonomy.failure_mode` must be either `null` or one non-empty lower-snake-case string.
- Structural benchmark classification must move out of free-form `metadata`:
  - `metadata["suite"]` must no longer be required.
  - `metadata["level"]` must no longer be required.
  - `metadata["focus"]` may remain as a human-readable label.
- Backfill every existing benchmark fixture under `backend/app/benchmark/cases/` with an explicit `taxonomy` object.
- Use the exact taxonomy values defined in this spec for the existing fixtures.
- Add `taxonomy` to `BenchmarkCaseResult`.
- `BenchmarkHarness.run_case(...)` must copy `case.taxonomy` into the resulting `BenchmarkCaseResult`, including normal, failed, and error result paths where the input case is available.
- Persist `case.taxonomy` under `agent_runs.metadata_json["benchmark"]["taxonomy"]` for workflow-backed benchmark runs.
- Add a `BenchmarkCaseMatrixSummary` contract.
- Add `matrix_summary` to `BenchmarkSummary`.
- `BenchmarkHarness.run_cases(...)` must build `matrix_summary` from the requested input cases, not from only passed case results.
- `matrix_summary` must include:
  - `schema_version`
  - `case_count`
  - `scenario_bucket_counts`
  - `level_counts`
  - `world_profile_counts`
  - `failure_mode_counts`
  - `tag_counts`
- `failure_mode_counts` must use an explicit `"none"` bucket for cases whose taxonomy sets `failure_mode=null`.
- `tag_counts` must count each tag at most once per case.
- Count dictionaries must serialize deterministically.
- Existing benchmark case report fields and suite report fields must remain present and unchanged except for the additive taxonomy and matrix-summary fields.
- Benchmark replay stable-field comparison must remain unchanged and must ignore the new additive taxonomy and matrix-summary fields.
- Update benchmark unit and integration tests to cover the new taxonomy and matrix summary.
- Update `README.md` to document:
  - required benchmark case taxonomy
  - taxonomy in case reports
  - matrix summary in suite run reports
- Do not add new benchmark cases, new world profiles, new routes, new frontend pages, new database tables, new Alembic migrations, or new package dependencies.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add `friends`, `couple`, `elder`, `rainy_day`, `budget`, or any other new Mock World fixture in this task.
- Do not add case-generation tooling, prompt-driven case synthesis, or matrix auto-generation yet.
- Do not change workflow routing, benchmark graders, benchmark replay comparison fields, or recovery behavior.
- Do not change public demo routes, the internal observability API, or frontend pages.
- Do not redesign `BenchmarkCase.expected` or benchmark scoring semantics.
- Do not edit completed historical specs/plans `001`-`038`.
- Do not stage or commit `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, generated `var/` artifacts, or other unrelated local files.

## 5. Interfaces and Contracts

### Inputs

This task depends on the existing benchmark fixture and reporting flow:

- benchmark case JSON fixtures under `backend/app/benchmark/cases/`
- `load_benchmark_case(case_id)`
- `load_default_benchmark_cases()`
- `load_failure_benchmark_cases()`
- `BenchmarkHarness.run_case(case)`
- `BenchmarkHarness.run_cases(cases)`

### Outputs

Additive fixture contract:

- `BenchmarkCase.taxonomy`

Additive case-report contract:

- `BenchmarkCaseResult.taxonomy`

Additive suite-report contract:

- `BenchmarkSummary.matrix_summary`

Additive persisted benchmark metadata:

- `agent_runs.metadata_json["benchmark"]["taxonomy"]`

### Schemas

Benchmark fixture shape after this task:

```json
{
  "case_id": "family_afternoon_v1",
  "title": "Family afternoon local-life plan",
  "user_input": "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.",
  "tool_profile": "mock_world",
  "world_profile": "family_afternoon",
  "failure_profile": null,
  "expected": {
    "required_tool_names": [
      "search_poi",
      "check_weather",
      "get_poi_detail",
      "check_opening_hours",
      "check_queue",
      "check_table_availability",
      "check_ticket_availability",
      "check_route"
    ],
    "min_tool_event_count": 8,
    "min_action_count": 1,
    "expected_execution_status": "succeeded",
    "expected_feedback_status": "completed"
  },
  "taxonomy": {
    "suite": "locallife_bench_v1",
    "scenario_bucket": "family",
    "level": "L1",
    "tags": ["baseline", "child_friendly", "light_meal"],
    "failure_mode": null
  },
  "metadata": {
    "focus": "baseline_family_afternoon"
  }
}
```

Suite matrix summary shape:

```json
{
  "schema_version": "weekendpilot_benchmark_case_matrix_v1",
  "case_count": 6,
  "scenario_bucket_counts": {
    "family": 5,
    "solo": 1
  },
  "level_counts": {
    "L1": 3,
    "L2": 3
  },
  "world_profile_counts": {
    "family_afternoon": 5,
    "solo_afternoon": 1
  },
  "failure_mode_counts": {
    "none": 6
  },
  "tag_counts": {
    "addon_optional": 1,
    "baseline": 2,
    "child_friendly": 5,
    "citywalk": 1,
    "indoor_activity": 2,
    "light_activity": 1,
    "light_meal": 4,
    "memory_override": 1,
    "outdoor_activity": 1,
    "quick_dinner": 1
  }
}
```

Exact taxonomy values for existing fixtures:

- `family_afternoon_v1`
  - `scenario_bucket`: `family`
  - `level`: `L1`
  - `tags`: `["baseline", "child_friendly", "light_meal"]`
  - `failure_mode`: `null`
- `family_indoor_light_meal_v1`
  - `scenario_bucket`: `family`
  - `level`: `L2`
  - `tags`: `["child_friendly", "indoor_activity", "light_meal"]`
  - `failure_mode`: `null`
- `family_outdoor_quick_dinner_v1`
  - `scenario_bucket`: `family`
  - `level`: `L2`
  - `tags`: `["child_friendly", "outdoor_activity", "quick_dinner"]`
  - `failure_mode`: `null`
- `family_memory_override_v1`
  - `scenario_bucket`: `family`
  - `level`: `L2`
  - `tags`: `["child_friendly", "indoor_activity", "light_meal", "memory_override"]`
  - `failure_mode`: `null`
- `family_citywalk_addon_v1`
  - `scenario_bucket`: `family`
  - `level`: `L1`
  - `tags`: `["addon_optional", "child_friendly", "citywalk"]`
  - `failure_mode`: `null`
- `solo_afternoon_v1`
  - `scenario_bucket`: `solo`
  - `level`: `L1`
  - `tags`: `["baseline", "light_activity", "light_meal"]`
  - `failure_mode`: `null`
- `family_route_failure_v1`
  - `scenario_bucket`: `family`
  - `level`: `L2`
  - `tags`: `["child_friendly", "failure_injected", "light_meal", "route_failure"]`
  - `failure_mode`: `"route_unavailable"`

Notes:

- `taxonomy.scenario_bucket` is a benchmark-labeling field, not a replacement for `LocalLifeIntent.scenario_type`.
- `taxonomy.level` becomes the authoritative structured benchmark difficulty field.
- `metadata.focus` remains human-readable only.

## 6. Observability

This task is benchmark-artifact structure work.

It must add:

- `taxonomy` to serialized benchmark case reports
- `matrix_summary` to serialized suite benchmark summaries
- persisted `agent_runs.metadata_json["benchmark"]["taxonomy"]`

It must keep all new fields sanitized and safe for existing report-writing rules. The new taxonomy and matrix summary must not expose:

- secrets
- API keys
- tokens
- authorization headers
- prompts
- raw tool payloads
- raw action payloads
- raw stack traces
- raw benchmark fixture blobs outside the existing case report content

This task does not add a new telemetry backend or new frontend observability surface.

## 7. Failure Handling

- If a benchmark fixture omits `taxonomy`, the existing fixture-loading path must fail with a typed `BenchmarkHarnessError` through `BenchmarkCase` validation.
- If `taxonomy.scenario_bucket` or `taxonomy.level` contains an unsupported value, fixture loading must fail through the existing validation path.
- If `taxonomy.tags` contains duplicates, blank strings, or non-lower-snake-case strings, fixture loading must fail through the existing validation path.
- If `taxonomy.failure_mode` is malformed, fixture loading must fail through the existing validation path.
- If `matrix_summary` building fails during `run_cases(...)`, the failure should surface as a benchmark error rather than silently writing a partial suite report.
- If older benchmark case reports without `taxonomy` are replayed, replay loading should continue to work by treating the field as additive and optional.
- This task does not need to backfill old JSON reports already on disk under `var/`.

## 8. Acceptance Criteria

- [ ] `docs/specs/039-benchmark-case-taxonomy-matrix-v0.md` exists and matches this task.
- [ ] All existing benchmark fixture files under `backend/app/benchmark/cases/` include a valid `taxonomy` object.
- [ ] `BenchmarkCase.taxonomy` is required and validated.
- [ ] `metadata["suite"]` and `metadata["level"]` are no longer required for fixture validation.
- [ ] `metadata["focus"]` remains available as a human-readable label.
- [ ] `BenchmarkCaseResult` includes `taxonomy`.
- [ ] `BenchmarkHarness.run_case(...)` copies taxonomy into case results.
- [ ] `agent_runs.metadata_json["benchmark"]["taxonomy"]` is populated for a workflow-backed benchmark run.
- [ ] `BenchmarkSummary` includes `matrix_summary`.
- [ ] `BenchmarkHarness.run_cases(...)` writes `matrix_summary` using the requested suite composition.
- [ ] `matrix_summary.failure_mode_counts` uses `"none"` for non-failure cases.
- [ ] Default-suite reports show `scenario_bucket_counts={"family": 5, "solo": 1}`.
- [ ] Default-suite reports show `world_profile_counts={"family_afternoon": 5, "solo_afternoon": 1}`.
- [ ] Existing benchmark case report fields and suite report fields remain present and unchanged apart from additive taxonomy/matrix fields.
- [ ] Replay tests still pass without comparing the new taxonomy or matrix-summary fields.
- [ ] `README.md` documents the taxonomy and matrix summary additions.
- [ ] No new benchmark case, world profile, route, UI page, migration, or dependency is added.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused unit and integration verification commands listed below pass, or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing ignored local runtime files.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_replay.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_replay_gateway.py -v
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add benchmark case taxonomy and matrix summary
```

## 11. Notes for the Implementer

Keep this task strictly scoped to benchmark structure.

The safest implementation path is:

1. define one required typed taxonomy contract,
2. backfill the exact taxonomy for the current fixture set,
3. add one helper that computes a deterministic suite matrix summary from the requested cases,
4. copy taxonomy into case reports and persisted benchmark metadata,
5. leave workflow behavior, replay comparison logic, frontend behavior, and scenario inventory unchanged.

Do not turn this task into a broader scenario-expansion task. The whole point is to make future scenario expansion structured before more cases are added.
