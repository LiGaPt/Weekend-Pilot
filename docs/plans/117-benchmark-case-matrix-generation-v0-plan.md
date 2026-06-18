# Plan: 117 Benchmark Case Matrix Generation v0

## 1. Spec Reference

Spec file:

```text
docs/specs/117-benchmark-case-matrix-generation-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- 当前分支是 `codex/116-mock-world-scenario-taxonomy-v0`。
- 最新 commit 是 `72f7f81 feat: expand mock world scenario taxonomy`，对应 Task `116`。
- `docs/specs` 与 `docs/plans` 到 `116` 连续、齐全、slug-matched，没有缺号或错配。
- 当前 canonical benchmark baseline 已稳定为：
  - registered `30`
  - `baseline = 6`
  - `expanded = 5`
  - `recovery_focused = 8`
  - `memory_governance = 6`
  - `conversation_continuations = 2`
  - `robustness_focused = 4`
  - `default = 11`
  - `release_gate_v1 = 15`
  - `v2_integrity = 20`
  - `all_registered = 30`
- 当前 benchmark source of truth 存在重复维护：
  - `backend/app/benchmark/fixtures.py` 维护 registered case IDs
  - `backend/app/benchmark/suites.py` 维护 suite case IDs
  - `tests/test_benchmark_suites.py`、`tests/test_benchmark_harness.py` 维护大量重复 case lists 与 counts
- 当前工作树有与本任务无关的未跟踪本地文件：
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- 这些无关文件在执行时必须保持 unstaged、untouched。

## 3. Files to Add

- `backend/app/benchmark/case_matrix.py` - canonical benchmark case matrix registry and helpers that derive registered case order, suite membership, and exportable manifest rows.
- `scripts/generate_benchmark_case_matrix.py` - read-only CLI entrypoint that prints deterministic matrix manifests and suite previews.
- `tests/test_benchmark_case_matrix_generation.py` - focused parity and determinism tests for the new matrix source of truth.

## 4. Files to Modify

- `backend/app/benchmark/schemas.py` - add matrix-row and manifest models only if typed schema support is needed for the new generator output.
- `backend/app/benchmark/fixtures.py` - replace the hard-coded `_REGISTERED_CASE_IDS` source with matrix-derived registered case IDs while preserving public behavior.
- `backend/app/benchmark/suites.py` - replace duplicated hard-coded suite case ID lists with matrix-derived membership while preserving suite order and public behavior.
- `tests/test_benchmark_suites.py` - re-anchor suite membership assertions against the canonical matrix-derived behavior and add coverage for derivation parity.
- `tests/test_benchmark_harness.py` - update only where a helper import or canonical source-of-truth assertion should now point at the new matrix layer.
- `backend/app/benchmark/__init__.py` - export any new public helper that the tests or CLI need, if the package already follows that pattern.

## 5. Implementation Steps

1. Inspect and freeze the current behavior before editing.
   - Read `backend/app/benchmark/fixtures.py`, `backend/app/benchmark/suites.py`, `backend/app/benchmark/schemas.py`, `tests/test_benchmark_suites.py`, `tests/test_benchmark_harness.py`, and `tests/test_benchmark_v2_taxonomy.py`.
   - Copy out the canonical registered case order and suite memberships from the current implementation.
   - Confirm the current suite counts still match the `30 / 20 / 15 / 11 / 8 / 6 / 5 / 4 / 2` baseline.

2. Design the matrix row contract.
   - Add a focused model or typed structure representing one canonical case row.
   - Include only the fields needed to drive inventory and suite derivation:
     - `case_id`
     - `world_profile`
     - `failure_profile`
     - `suite_ids`
     - `taxonomy`
   - Do not include the full `BenchmarkCase` payload unless it is strictly necessary.

3. Create the canonical matrix registry.
   - Add `backend/app/benchmark/case_matrix.py`.
   - Encode all current `30` canonical cases in deterministic order.
   - Keep this file as the single structural source of truth for:
     - registered case order
     - suite membership
     - scenario / constraint / failure composition metadata
   - Add helpers such as:
     - list all rows in canonical order
     - return registered case IDs
     - return case IDs for a suite
     - return suite IDs for a case
     - build a manifest payload for export

4. Rewire `fixtures.py` to use the matrix.
   - Replace the local hard-coded registered ID tuple with a matrix-derived list or tuple.
   - Keep `load_benchmark_case()` behavior unchanged.
   - Keep canonical non-`mock_world` guard behavior unchanged.
   - Do not alter JSON fixture loading paths or validation flow.

5. Rewire `suites.py` to use the matrix.
   - Preserve the canonical suite order and alias behavior.
   - Replace duplicated suite case ID lists with matrix-derived memberships.
   - Keep suite descriptions in place if they are still meaningful, but stop duplicating membership data in multiple places.
   - Preserve the existing public helpers:
     - `load_benchmark_suite`
     - `list_benchmark_suites`
     - `list_benchmark_suite_ids_for_case`
     - `canonical_benchmark_suite_id`

6. Add the read-only export script.
   - Add `scripts/generate_benchmark_case_matrix.py`.
   - Support at least:
     - `--suite-id <suite>`
     - `--format json`
   - Output deterministic JSON with:
     - registered case count
     - suite counts
     - ordered case rows
     - suite preview rows for the selected suite
   - Keep the script read-only; it must not modify repo files.

7. Add focused matrix-generation tests first.
   - Create `tests/test_benchmark_case_matrix_generation.py`.
   - Add tests for:
     - unique `case_id`
     - deterministic row order
     - valid `suite_id` references
     - parity between generated registered IDs and current canonical order
     - parity between generated suite memberships and current canonical memberships
     - deterministic manifest export payload shape

8. Update suite tests to point at the new source of truth.
   - In `tests/test_benchmark_suites.py`, keep the external behavior assertions.
   - Remove only the duplication that becomes redundant because the matrix registry now owns membership structure.
   - Add targeted assertions that `list_benchmark_suites()` and `list_benchmark_suite_ids_for_case()` match the matrix-derived structure.

9. Update harness or taxonomy tests only where necessary.
   - Touch `tests/test_benchmark_harness.py` or `tests/test_benchmark_v2_taxonomy.py` only if they need imports or a stronger source-of-truth assertion.
   - Do not widen the task into report or gate behavior changes.

10. Run focused verification.
   - Run the new matrix-generation test file first.
   - Run suite tests second.
   - Run harness and v2 taxonomy regression tests third.
   - Run the export script manually for `all_registered` and `v2_integrity`.
   - Finish with `git diff --check` and `git status --short`.

11. Stage only task-relevant files and commit on a new task branch.
   - Create or switch to `codex/117-benchmark-case-matrix-generation-v0` before staging if the execution session is not already there.
   - Leave unrelated untracked docs untouched.
   - Use the exact commit message from the spec.

## 6. Testing Plan

- Unit tests:
  - `tests/test_benchmark_case_matrix_generation.py`
    - canonical row order is deterministic
    - row `case_id` values are unique
    - every `suite_id` is valid
    - generated registered case IDs equal current canonical registered order
    - generated suite memberships equal current canonical suite memberships
    - manifest export payload is deterministic
  - `tests/test_benchmark_suites.py`
    - existing public suite-loading behavior remains unchanged
    - `list_benchmark_suite_ids_for_case()` remains unchanged
    - `list_benchmark_suites()` still yields the same counts and summaries
  - `tests/test_benchmark_v2_taxonomy.py`
    - existing V2 taxonomy summary behavior remains green after the matrix refactor

- Integration tests:
  - `tests/test_benchmark_harness.py`
    - current matrix summaries and canonical inventory assumptions still pass through harness-facing tests

- Smoke tests:
  - `python scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json`
  - `python scripts/generate_benchmark_case_matrix.py --suite-id v2_integrity --format json`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_benchmark_case_matrix_generation.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_v2_taxonomy.py -q
python scripts/generate_benchmark_case_matrix.py --suite-id all_registered --format json
python scripts/generate_benchmark_case_matrix.py --suite-id v2_integrity --format json
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: generate benchmark cases from taxonomy matrix
```

Expected commands:

```bash
git status --short
git checkout -b codex/117-benchmark-case-matrix-generation-v0
git add backend/app/benchmark/case_matrix.py
git add backend/app/benchmark/schemas.py backend/app/benchmark/fixtures.py backend/app/benchmark/suites.py backend/app/benchmark/__init__.py
git add scripts/generate_benchmark_case_matrix.py
git add tests/test_benchmark_case_matrix_generation.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py tests/test_benchmark_v2_taxonomy.py
git diff --cached --check
git commit -m "feat: generate benchmark cases from taxonomy matrix"
git push -u origin codex/117-benchmark-case-matrix-generation-v0
```

The implementer must confirm:
- unrelated untracked docs remain unstaged
- no `var/` artifacts are staged
- no secrets are staged

## 9. Out-of-scope Changes

- Do not add new benchmark cases.
- Do not rewrite the detailed fixture JSON payloads into generated files.
- Do not alter benchmark gate policy, threshold logic, or release criteria.
- Do not change workflow, memory policy, provider selection, frontend UI, or observability schema.
- Do not add dependencies or migrations.
- Do not touch `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, or `docs/superpowers/`.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/117-benchmark-case-matrix-generation-v0.md`.
- [ ] The new matrix layer is the single structural source of truth for case order and suite membership.
- [ ] `fixtures.py` no longer maintains an independent registered case ID source.
- [ ] `suites.py` no longer maintains independent hard-coded suite membership lists.
- [ ] Public benchmark loading behavior is unchanged.
- [ ] Current canonical suite counts remain `6 / 5 / 8 / 6 / 2 / 4 / 11 / 15 / 20 / 30`.
- [ ] The export script is read-only and deterministic.
- [ ] Focused matrix-generation tests were added and passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

完成后应回报：

- 新增了哪些 matrix-generation files
- 哪些旧的重复 source-of-truth 被移除了
- 当前 canonical registered order 与 suite counts 的最终确认值
- 运行了哪些验证命令以及结果
- export script 的示例输出范围
- commit hash
- push 结果
- 是否还有后续自然承接任务，例如基于 matrix 自动生成更完整的 fixture draft，而不是只生成结构 manifest
