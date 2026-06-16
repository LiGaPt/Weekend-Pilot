# Spec: 107 Benchmark test/doc count convergence

## 1. Goal

This task restores convergence between the current benchmark inventory and the repository’s benchmark-facing regression checks and active documentation.

The code-level source of truth has already expanded to `v2_integrity = 18` and `all_registered = 28`, but several tests and at least one current README verification line still assert older counts. After this task is complete, benchmark inventory tests should pass against the existing suite membership, and active documentation should describe the current inventory and focused verification result accurately without changing benchmark behavior.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

It is a convergence task after Task `106`, not a new feature task. The relevant `docs/PROJECT_BLUEPRINT.md` architecture areas are:

- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- small, reviewable tasks

This task is intentionally narrower than the next planned M1 expansion work. The immediate priority is to restore benchmark regression truthfulness before adding more evaluation or observability surface area.

## 3. Requirements

- The implementation must treat the current benchmark suite definitions in `backend/app/benchmark/suites.py` as the source of truth for case counts.
- Stale benchmark test assertions must be updated from obsolete counts to current counts:
  - `v2_integrity`: `15 -> 18`
  - `all_registered`: `17 -> 28`
  - registered/V2 taxonomy inventory: `25 -> 28`
- Tests that hard-code the old V2 integrity coverage summary must be updated to match the current suite truth.
- Tests that use stubbed benchmark/formal-verification summaries to represent the current canonical inventory must also be updated to the current counts where they are asserting current-repo behavior.
- The README focused backend verification result must be updated from `15 passed` to the current actual result of the documented command.
- Active benchmark-facing documentation touched by this task must use the current case-count/version wording where it claims the current repository truth.
- The task must not change benchmark suite membership, benchmark grading semantics, release-gate semantics, coverage-gate semantics, stability formulas, or recovery-review behavior.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not add, remove, or reorder benchmark cases in any suite.
- Do not change `release_gate_v1` membership or counts.
- Do not change benchmark matrix scoring, integrity coverage logic, formal verification logic, or pass-k logic.
- Do not rewrite historical task specs/plans solely to modernize archived numbers.
- Do not add new documentation sections or submission flows beyond the minimal wording updates required for convergence.

## 5. Interfaces and Contracts

### Inputs

- Benchmark suite definitions:
  - `backend/app/benchmark/suites.py`
- Benchmark-facing tests:
  - `tests/integration/test_formal_verification.py`
  - `tests/integration/test_benchmark_v2_integrity_gate.py`
  - `tests/test_benchmark_v2_taxonomy.py`
  - `tests/test_formal_verification.py`
  - `tests/test_benchmark_v2_integrity_gate.py`
  - `tests/test_demo_support_scripts.py`
- Active developer-facing documentation:
  - `README.md`

### Outputs

- Updated benchmark regression tests whose expected counts match current suite truth.
- Updated support-script/readme assertions that match current README wording.
- Updated README wording for the focused backend verification result.

### Schemas

Current benchmark inventory truth for this task:

```json
{
  "release_gate_v1": 15,
  "v2_integrity": 18,
  "all_registered": 28,
  "registered_case_count": 28,
  "focused_backend_checks_command": "python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q",
  "focused_backend_checks_expected_result": "23 passed"
}
```

Current V2 integrity coverage summary truth for this task:

```json
{
  "case_count": 18,
  "memory_case_count": 6,
  "recovery_case_count": 6,
  "continuation_case_count": 3,
  "robustness_case_count": 4,
  "l4_case_count": 1
}
```

## 6. Observability

This task does not add new runtime observability.

It only restores consistency across:
- benchmark regression tests
- README benchmark/test status wording
- existing support-script/document checks

No new traces, logs, database rows, or Redis events are required.

## 7. Failure Handling

- If the suite truth discovered in `backend/app/benchmark/suites.py` differs from the expected `v2_integrity = 18` or `all_registered = 28`, stop and report the discrepancy instead of forcing tests to those numbers.
- If a candidate doc update would require changing historical archived task documents, do not broaden scope; keep the fix limited to active current-state docs.
- If focused verification commands produce a different result than `23 passed` at execution time, update the doc/tests to the verified result and report that the repository truth changed again.
- If unrelated benchmark tests fail after these convergence changes, report them separately rather than changing benchmark behavior in this task.

## 8. Acceptance Criteria

- [ ] `tests/integration/test_formal_verification.py` asserts the current `all_registered` count and passes.
- [ ] `tests/integration/test_benchmark_v2_integrity_gate.py` asserts the current `v2_integrity` count and coverage summary and passes.
- [ ] `tests/test_benchmark_v2_taxonomy.py` asserts the current registered inventory count and passes.
- [ ] Any unit tests that stub current canonical formal-verification or V2 gate counts are updated to current repo truth.
- [ ] `tests/test_demo_support_scripts.py` matches the current README benchmark/test wording and passes.
- [ ] `README.md` no longer claims the outdated focused backend result `15 passed`.
- [ ] The current README benchmark inventory wording remains accurate for `release_gate_v1 = 15`, `v2_integrity = 18`, and `all_registered = 28`.
- [ ] No benchmark suite membership changed.
- [ ] No benchmark scoring or gate semantics changed.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except unrelated pre-existing local files.

## 9. Verification Commands

```bash
python -m pytest tests/integration/test_formal_verification.py tests/integration/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/test_benchmark_v2_taxonomy.py tests/test_formal_verification.py tests/test_benchmark_v2_integrity_gate.py -q
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
test: align benchmark inventory expectations
```

## 11. Notes for the Implementer

Use `backend/app/benchmark/suites.py` and already-updated benchmark harness expectations as the truth source before changing assertions.

Keep the task narrow:
1. re-confirm actual suite counts
2. update stale tests
3. update active README wording
4. rerun focused verification

Do not “fix” this task by reverting code-level suite growth back to the obsolete inventory. If repo truth has changed again since this planning pass, stop and report the new counts before editing.
