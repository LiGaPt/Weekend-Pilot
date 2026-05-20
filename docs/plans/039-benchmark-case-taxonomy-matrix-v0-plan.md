# Plan: 039 Benchmark Case Taxonomy and Matrix Summary v0

## 1. Spec Reference

Spec file:

```text
docs/specs/039-benchmark-case-taxonomy-matrix-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

If the Task 039 spec file is not saved yet at implementation time, stop and save the approved spec before implementing this plan.

## 2. Current Repository Assumptions

- The latest completed repository task is `038`, with matching spec/plan files and matching latest commit `2ce85bc feat: add solo afternoon mock world benchmark profile`.
- `docs/specs` and `docs/plans` are continuous and matched through `038`.
- The implementation should start from the merged Task 038 state, whether on `codex/solo-afternoon-mock-world-expansion-v0` or on a fresh task branch created from that commit state.
- The current benchmark suite includes:
  - six default cases
  - one failure case
  - two supported Mock World profiles: `family_afternoon` and `solo_afternoon`
- Current benchmark fixtures still use free-form `metadata` for structural fields such as `suite` and `level`.
- Current benchmark suite reports include timing and summary envelopes, but not a structured case taxonomy or suite matrix summary.
- Replay already treats additive report fields as ignorable stable-comparison noise, and this task must preserve that behavior.
- The working tree currently contains untracked local files `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and `var/`; they are not part of Task 039.

## 3. Files to Add

- `backend/app/benchmark/matrix.py` - deterministic helper for building `BenchmarkCaseMatrixSummary` from requested benchmark cases.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add taxonomy and matrix-summary models plus additive fields on benchmark case/result/summary schemas.
- `backend/app/benchmark/harness.py` - copy taxonomy into case results, persist taxonomy in run metadata, and build suite matrix summary from input cases.
- `backend/app/benchmark/cases/family_afternoon_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `backend/app/benchmark/cases/family_indoor_light_meal_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `backend/app/benchmark/cases/family_outdoor_quick_dinner_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `backend/app/benchmark/cases/family_memory_override_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `backend/app/benchmark/cases/family_citywalk_addon_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `backend/app/benchmark/cases/solo_afternoon_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `backend/app/benchmark/cases/family_route_failure_v1.json` - add exact taxonomy and reduce metadata to human-readable focus only.
- `tests/test_benchmark_harness.py` - update fixture validation, case result serialization, and suite report assertions for taxonomy and matrix summary.
- `tests/test_benchmark_replay.py` - keep additive replay coverage by asserting taxonomy-bearing reports still replay cleanly.
- `tests/integration/test_benchmark_harness_gateway.py` - assert persisted case reports and suite reports include taxonomy and matrix summary.
- `README.md` - document benchmark taxonomy and suite matrix summary output.

## 5. Implementation Steps

1. Add the new benchmark taxonomy and matrix-summary contracts in `backend/app/benchmark/schemas.py`.
   Define `BenchmarkCaseTaxonomy` with:
   - `suite: Literal["locallife_bench_v1"]`
   - `scenario_bucket: Literal["family", "solo", "friends", "couple", "elder", "mixed", "unknown"]`
   - `level: Literal["L1", "L2", "L3", "L4", "L5"]`
   - `tags: list[str]`
   - `failure_mode: str | None`
   
   Add validation rules:
   - every tag must be non-empty
   - every tag must match lower-snake-case
   - tags must be unique within one case
   - `failure_mode`, when present, must also match lower-snake-case

   Then:
   - add required `taxonomy: BenchmarkCaseTaxonomy` to `BenchmarkCase`
   - add additive `taxonomy: BenchmarkCaseTaxonomy | None = None` to `BenchmarkCaseResult`
   - add additive `matrix_summary: BenchmarkCaseMatrixSummary | None = None` to `BenchmarkSummary`

2. Add the matrix-summary builder in `backend/app/benchmark/matrix.py`.
   Implement one deterministic helper that accepts `Sequence[BenchmarkCase]` and returns `BenchmarkCaseMatrixSummary`.

   The helper must:
   - set `case_count` from the number of requested input cases
   - count `scenario_bucket`
   - count `level`
   - count `world_profile`
   - count `failure_mode`, mapping `null` to `"none"`
   - count each taxonomy tag once per case
   - return dictionaries with alphabetically sorted keys for deterministic output

3. Backfill exact taxonomy values into every current benchmark fixture.
   Use these exact values:

   - `family_afternoon_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="family"`
     - `level="L1"`
     - `tags=["baseline", "child_friendly", "light_meal"]`
     - `failure_mode=null`

   - `family_indoor_light_meal_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="family"`
     - `level="L2"`
     - `tags=["child_friendly", "indoor_activity", "light_meal"]`
     - `failure_mode=null`

   - `family_outdoor_quick_dinner_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="family"`
     - `level="L2"`
     - `tags=["child_friendly", "outdoor_activity", "quick_dinner"]`
     - `failure_mode=null`

   - `family_memory_override_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="family"`
     - `level="L2"`
     - `tags=["child_friendly", "indoor_activity", "light_meal", "memory_override"]`
     - `failure_mode=null`

   - `family_citywalk_addon_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="family"`
     - `level="L1"`
     - `tags=["addon_optional", "child_friendly", "citywalk"]`
     - `failure_mode=null`

   - `solo_afternoon_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="solo"`
     - `level="L1"`
     - `tags=["baseline", "light_activity", "light_meal"]`
     - `failure_mode=null`

   - `family_route_failure_v1`
     - `suite="locallife_bench_v1"`
     - `scenario_bucket="family"`
     - `level="L2"`
     - `tags=["child_friendly", "failure_injected", "light_meal", "route_failure"]`
     - `failure_mode="route_unavailable"`

   In the same edit, remove `suite` and `level` from the free-form `metadata` object and keep only `metadata.focus`.

4. Thread taxonomy into benchmark harness outputs in `backend/app/benchmark/harness.py`.
   Update all result-construction paths so `BenchmarkCaseResult.taxonomy` is populated from the input case whenever a case object exists.
   
   Update `_record_benchmark_metadata(...)` so persisted run metadata contains:
   - `benchmark.case_id`
   - `benchmark.title`
   - `benchmark.failure_profile`
   - `benchmark.failure_profile_metadata`
   - `benchmark.benchmark_harness_version`
   - `benchmark.harness_version`
   - `benchmark.taxonomy`
   - `benchmark.metadata`
   - `benchmark.workflow_backed`

   Do not remove the existing `benchmark.metadata` field.

5. Build suite matrix summaries in `backend/app/benchmark/harness.py`.
   In `run_cases(...)`:
   - build the existing `BenchmarkSummary`
   - call the new matrix helper with the requested `cases`
   - attach the returned matrix summary to `benchmark_summary.matrix_summary`

   Keep current behavior for:
   - per-case execution
   - pass/fail/error aggregation
   - overall score calculation
   - benchmark timing summary generation
   - suite report writing

6. Update `tests/test_benchmark_harness.py`.
   Replace the current structural assertions that read `case.metadata["suite"]` and `case.metadata["level"]` with typed assertions against `case.taxonomy`.

   Add or update tests to assert:
   - every default case loads with valid taxonomy
   - the failure case loads with `failure_mode="route_unavailable"`
   - `metadata["focus"]` remains present and non-empty
   - default-suite matrix summary counts are exactly:
     - `scenario_bucket_counts={"family": 5, "solo": 1}`
     - `level_counts={"L1": 3, "L2": 3}`
     - `world_profile_counts={"family_afternoon": 5, "solo_afternoon": 1}`
     - `failure_mode_counts={"none": 6}`
   - default-suite tag counts are exactly:
     - `addon_optional=1`
     - `baseline=2`
     - `child_friendly=5`
     - `citywalk=1`
     - `indoor_activity=2`
     - `light_activity=1`
     - `light_meal=4`
     - `memory_override=1`
     - `outdoor_activity=1`
     - `quick_dinner=1`
   - serialized case reports include `taxonomy`
   - serialized suite reports include `benchmark_summary.matrix_summary`

   Also add one schema-validation test that `BenchmarkCase.model_validate(...)` rejects duplicate tags or malformed tags.

7. Update `tests/test_benchmark_replay.py`.
   Keep the stable replay summary unchanged, but add one additive-compatibility test that a `BenchmarkCaseResult` containing a taxonomy payload still replays without producing mismatches.
   
   Do not add taxonomy to replay stable-compare fields.

8. Update `tests/integration/test_benchmark_harness_gateway.py`.
   Extend the existing gateway-backed suite assertions so:
   - each persisted case report JSON includes `taxonomy`
   - the solo case report includes `taxonomy.scenario_bucket == "solo"`
   - the suite `run-report.json` includes `benchmark_summary.matrix_summary`
   - suite matrix counts match the exact default-suite expectations from Step 6

   Do not widen integration coverage into unrelated workflow or frontend areas.

9. Update `README.md`.
   In the LocalLife-Bench section, document that:
   - each benchmark case fixture now requires a structured `taxonomy`
   - each case report embeds `taxonomy`
   - each suite `run-report.json` includes `benchmark_summary.matrix_summary`
   - the matrix summary is intended to support future multi-scenario comparison

10. Run focused verification and keep the commit clean.
    Run unit tests first, then PostgreSQL/Redis-backed integration verification, then `git diff --check`.
    Before committing, confirm that:
    - `docs/NEXT_PHASE_ROADMAP.md` is not staged
    - `docs/TASK_WORKFLOW_PROMPTS.md` is not staged
    - generated `var/` artifacts are not staged

## 6. Testing Plan

- Unit tests:
  - fixture loading validates required taxonomy
  - fixture loading rejects malformed or duplicate tags
  - default-suite matrix summary counts match the exact expected values
  - failure-case taxonomy exposes `failure_mode="route_unavailable"`
  - case report JSON includes `taxonomy`
  - suite report JSON includes `benchmark_summary.matrix_summary`

- Replay tests:
  - additive taxonomy fields do not affect stable replay comparison
  - replay still loads serialized case reports with new additive fields

- Integration tests:
  - gateway-backed default suite still passes
  - persisted case reports include taxonomy
  - persisted suite report includes exact matrix counts

- Smoke checks:
  - benchmark summary serialization remains sanitized
  - no workflow, replay, or frontend regression is introduced by the additive schema work

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_benchmark_replay.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py tests/integration/test_benchmark_replay_gateway.py -v
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add benchmark case taxonomy and matrix summary
```

Expected commands:

```bash
git status --short
git add README.md
git add backend/app/benchmark/schemas.py
git add backend/app/benchmark/matrix.py
git add backend/app/benchmark/harness.py
git add backend/app/benchmark/cases/family_afternoon_v1.json
git add backend/app/benchmark/cases/family_indoor_light_meal_v1.json
git add backend/app/benchmark/cases/family_outdoor_quick_dinner_v1.json
git add backend/app/benchmark/cases/family_memory_override_v1.json
git add backend/app/benchmark/cases/family_citywalk_addon_v1.json
git add backend/app/benchmark/cases/solo_afternoon_v1.json
git add backend/app/benchmark/cases/family_route_failure_v1.json
git add tests/test_benchmark_harness.py
git add tests/test_benchmark_replay.py
git add tests/integration/test_benchmark_harness_gateway.py
git commit -m "feat: add benchmark case taxonomy and matrix summary"
git push
```

The implementer must confirm `.env`, secrets, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files are not staged.

## 9. Out-of-scope Changes

- Do not add new scenario fixtures or new benchmark cases.
- Do not add case-generation tooling or benchmark matrix auto-generation beyond the deterministic suite summary in this plan.
- Do not change workflow routing, deterministic planner behavior, Tool Gateway logic, or replay stable-field comparison.
- Do not modify public demo routes, internal observability routes, or frontend pages.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md`.
- Do not edit completed historical task specs/plans `001`-`038`.
- Do not add new dependencies.
- Do not commit generated caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/039-benchmark-case-taxonomy-matrix-v0.md`.
- [ ] Every existing benchmark fixture now has the exact taxonomy required by the spec.
- [ ] `BenchmarkCaseResult` includes taxonomy.
- [ ] Persisted benchmark run metadata includes taxonomy.
- [ ] Suite reports include `benchmark_summary.matrix_summary`.
- [ ] Default-suite matrix counts match the exact expected values from the spec.
- [ ] Replay tests still pass without adding taxonomy to stable-compare logic.
- [ ] The implementation stayed inside benchmark-structure scope only.
- [ ] Required tests and verification commands passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/` artifact, or unrelated local file was committed.

## 11. Handoff Notes

Report back with:

- The exact files changed.
- The final default-suite matrix counts as serialized in `run-report.json`.
- The unit and integration verification commands that were run, plus their results.
- The commit hash and push result.
- Confirmation that `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, and generated `var/` files were not staged.
- Any follow-up limitation, especially that future scenario growth still needs separate tasks for new Mock World profiles and benchmark case-generation strategy.
