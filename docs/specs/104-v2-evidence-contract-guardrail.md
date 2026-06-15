# Spec: 104 V2 Evidence Summary and Contract Guardrail

## 1. Goal

WeekendPilot has already completed the core V2 integrity evidence chain in code:

- `v2_integrity` suite and taxonomy from Task `092`
- `v2_integrity_gate` from Task `093`
- `Pass@k` stability artifact from Task `094`
- internal system-integrity aggregation from Task `102`
- reviewer-facing `System Integrity Summary` panel from Task `103`

What is still missing is a repo-root guardrail that treats those V2 integrity artifacts as a first-class contract. Right now the repository has a partial split-brain state:

- `scripts/show_submission_evidence.py` already cites `latest-v2_integrity_gate-run-report.json`
- the review-evidence verifier still only validates the older V1.5 four-alias contract
- there is no executable protection against drift in V2 alias paths, schema usage, suite IDs, gate IDs, or stability report identifiers

This task closes that gap. After it is complete, the repository must provide one shared V2-aware evidence contract used by both the human-facing summary script and the executable verifier, so maintainers can detect V2 evidence drift before Task `105` submission-doc alignment and Task `106` final release verification.

## 2. Project Context

This task belongs to `docs/NEXT_PHASE_ROADMAP.md` milestone `M1. 评测与观测基础设施`.

It is the smallest direct continuation after Task `103`:

- Task `076` introduced the original V1.5 review-evidence verifier.
- Task `092` introduced the additive `v2_integrity` suite.
- Task `093` introduced the additive `v2_integrity_gate`.
- Task `094` introduced the additive `v2_integrity` Pass@k stability report.
- Task `102` aggregated those evidence sources in one internal API.
- Task `103` surfaced them on the `5174` reviewer page.

This task fits these `docs/PROJECT_BLUEPRINT.md` architecture areas:

- benchmark-driven development
- observability by default
- harness engineering as product infrastructure
- failure handling and recovery auditability
- small, reviewable tasks

This task is still infrastructure and contract hardening. It must not change benchmark behavior, replay behavior, public demo behavior, or frontend rendering. Its job is to make the already-existing V2 evidence chain executable and defensible.

## 3. Requirements

- Add one shared evidence-contract source used by both:
  - `scripts/show_submission_evidence.py`
  - `backend.app.benchmark.review_evidence`
- The shared contract must define, for each supported evidence artifact:
  - `evidence_id`
  - repo-root rerun command when applicable
  - canonical repo-relative alias path
  - artifact kind
  - human-readable description of what it proves
  - expected schema/model type
  - expected suite ID, gate ID, case ID, and metric version fields where applicable

- The shared contract must cover these canonical artifacts:
  - `release_gate_v1`
  - `coverage_gate_v1_5`
  - `v2_integrity_gate`
  - `v2_integrity_passk`
  - `formal_verification_all_registered`
  - `recovery_review_family_route_failure_v1`

- `scripts/show_submission_evidence.py` must use the shared contract instead of maintaining an independent hard-coded registry.
- The summary script must print all supported evidence items in deterministic order.
- The summary script must include `v2_integrity_passk` in addition to the existing V2 gate artifact.
- The summary script must keep its repo-root usage pattern:
  - `python scripts/show_submission_evidence.py`
- The summary script must still be lightweight and human-readable.
- The summary script must parse each present artifact structurally and print a compact summary instead of only printing a path.
- The summary script must return:
  - exit code `0` when all required artifacts are present and structurally readable
  - exit code `1` when any required artifact is missing or invalid

### V2 gate contract

The verifier must validate:

- `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`
  - file exists
  - parses as `BenchmarkRunReport`
  - top-level `run_status == "passed"`
  - `benchmark_summary.suite_id == "v2_integrity"`
  - raw payload includes `v2_integrity_gate_evaluation.gate_id == "v2_integrity_gate"`
  - raw payload includes `v2_integrity_gate_evaluation.suite_id == "v2_integrity"`
  - raw payload includes `v2_integrity_gate_evaluation.release_blocked == false`

### V2 Pass@k contract

The verifier must validate:

- `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`
  - file exists
  - parses as `BenchmarkStabilityPassKReport`
  - `suite_id == "v2_integrity"`
  - `gate_id == "v2_integrity_gate"`
  - `metric_version == "passk_v0"`
  - `window_count >= 1`

### Existing V1.5 contract preservation

- The existing V1.5 review-evidence verifier behavior from Task `076` must remain intact.
- The verifier must continue validating:
  - `README.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `.gitignore`
- The verifier must continue validating the original four canonical V1.5 aliases.
- This task must extend the verifier, not replace it with a V2-only implementation.

### Actionable failures

- Missing or invalid V2 artifacts must produce actionable failures.
- Failure messages must:
  - name the exact alias path
  - state what drifted or failed
  - include the matching rerun command when the artifact can be refreshed from a repo-root script
- The verifier must return:
  - exit code `0` when all checks pass
  - exit code `1` when any check fails

### Tests

Add focused tests covering:

- passing aligned fixture with all V1.5 and V2 artifacts
- `show_submission_evidence.py` includes `v2_integrity_passk`
- V2 gate suite/gate drift failure
- V2 stability suite/gate/metric drift failure
- missing V2 stability alias failure
- non-regression for the pre-existing V1.5 verifier contract

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not rerun or regenerate benchmark or recovery artifacts under `var/` as part of the implementation.
- Do not change benchmark suite membership, gate thresholds, Pass@k formulas, memory-governance grading, or recovery replay semantics.
- Do not redesign `SystemIntegritySummary` API or the `5174` UI.
- Do not broaden this task into the Task `105` documentation rewrite for the V2 Integrity Edition submission package.
- Do not add CI jobs, GitHub workflows, pre-commit hooks, or release automation.
- Do not add new package dependencies.

## 5. Interfaces and Contracts

### Inputs

- Repo-root commands:
  - `python scripts/show_submission_evidence.py`
  - `python scripts/verify_review_evidence.py`
- Official tracked docs already covered by Task `076`:
  - `README.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `.gitignore`
- Canonical evidence aliases:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json`
  - `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Existing schema types:
  - `BenchmarkRunReport`
  - `BenchmarkStabilityPassKReport`
  - `RecoveryReplayReviewResult`

### Outputs

- Human-readable submission evidence summary from:
  - `python scripts/show_submission_evidence.py`
- Human-readable verification summary from:
  - `python scripts/verify_review_evidence.py`
- One shared programmatic contract module consumed by both tools.

### Schemas

Representative shared contract entry shape:

```json
{
  "evidence_id": "v2_integrity_passk",
  "command": "python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4",
  "relative_path": "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
  "artifact_kind": "benchmark_stability",
  "proves": "V2 integrity repeated-run stability metrics",
  "expected_schema": "BenchmarkStabilityPassKReport",
  "expected_suite_id": "v2_integrity",
  "expected_gate_id": "v2_integrity_gate",
  "expected_metric_version": "passk_v0"
}
```

Representative summary output expectations:

```text
[OK] v2_integrity_passk
  path: var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json
  proves: V2 integrity repeated-run stability metrics
  summary: suite_id=v2_integrity, gate_id=v2_integrity_gate, metric_version=passk_v0
```

Representative verifier result payload:

```json
{
  "status": "passed",
  "checked_docs": [
    "README.md",
    "docs/V1_5_REVIEW_EVIDENCE.md",
    "docs/COMPETITION_SUBMISSION_DESIGN.md",
    ".gitignore"
  ],
  "checked_aliases": {
    "release_gate_v1": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
    "coverage_gate_v1_5": "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
    "v2_integrity_gate": "var/formal-benchmarks/latest-v2_integrity_gate-run-report.json",
    "v2_integrity_passk": "var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json",
    "formal_verification_all_registered": "var/formal-benchmarks/latest-all_registered-run-report.json",
    "recovery_review_family_route_failure_v1": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
  },
  "failures": []
}
```

## 6. Observability

This task does not add runtime observability, LangSmith metadata, PostgreSQL rows, Redis events, or new generated artifact types.

The only observability added here is deterministic CLI feedback for maintainers:

- summary output for current canonical evidence
- actionable validation failures when evidence contracts drift

No new persistent telemetry is required.

## 7. Failure Handling

- If a required artifact alias is missing, the summary script must mark it as missing and exit non-zero.
- If a required artifact alias contains malformed JSON, the summary script must mark it as invalid and exit non-zero.
- If the verifier sees a V2 gate report with the wrong suite ID, gate ID, or blocked state, it must fail.
- If the verifier sees a V2 Pass@k report with the wrong suite ID, gate ID, or metric version, it must fail.
- If the verifier cannot parse an artifact with its expected schema, it must fail.
- If the shared contract source and the verifier-specific expectations diverge, tests must fail; the implementation should not keep separate duplicated identifiers.
- The verifier must not auto-fix docs, regenerate artifacts, or rewrite alias files.

## 8. Acceptance Criteria

- [ ] `docs/specs/104-v2-evidence-contract-guardrail.md` exists and matches this task.
- [ ] `docs/plans/104-v2-evidence-contract-guardrail-plan.md` exists and matches this task.
- [ ] The repository has one shared evidence contract used by both `show_submission_evidence.py` and the review-evidence verifier.
- [ ] `show_submission_evidence.py` no longer maintains an independent hard-coded evidence registry.
- [ ] `show_submission_evidence.py` includes `v2_integrity_passk` in deterministic output.
- [ ] `show_submission_evidence.py` prints structured summaries for benchmark, stability, and recovery evidence.
- [ ] `show_submission_evidence.py` exits `1` when a required artifact is missing or invalid.
- [ ] `verify_review_evidence.py` continues to enforce the existing Task `076` V1.5 docs-and-alias contract.
- [ ] The verifier additionally validates `latest-v2_integrity_gate-run-report.json`.
- [ ] The verifier additionally validates `latest-v2_integrity-passk-v0-report.json`.
- [ ] The verifier uses `BenchmarkRunReport`, `BenchmarkStabilityPassKReport`, and `RecoveryReplayReviewResult` for structured parsing.
- [ ] The verifier returns exit code `0` on a passing repo and exit code `1` on any failure.
- [ ] Focused tests cover:
  - passing aligned repo fixture
  - V2 summary output
  - missing V2 stability alias
  - V2 gate identifier drift
  - V2 stability identifier drift
  - non-regression for the existing V1.5 contract
- [ ] No benchmark runner logic, benchmark thresholds, stability formulas, or frontend behavior changes in this task.
- [ ] No generated JSON artifact under `var/` is committed by this task.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except unrelated pre-existing untracked local files.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
python scripts/show_submission_evidence.py
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add v2 evidence guardrails
```

## 11. Notes for the Implementer

Keep this task contract-first and narrowly scoped.

Preferred sequencing:

1. extract one shared evidence-contract registry
2. refactor the summary script onto that registry
3. extend the verifier to consume the same V2 contract entries
4. add focused fixture-based tests
5. finish with repo-root smoke commands

Important boundaries:

- preserve the Task `076` V1.5 doc contract
- do not widen into Task `105` documentation unification
- do not refresh real benchmark artifacts under `var/`
- do not stage unrelated untracked files currently present in the workspace

The implementer should stop and report back if the current committed V2 artifact schemas no longer match:
- `BenchmarkRunReport`
- `BenchmarkStabilityPassKReport`
- `RecoveryReplayReviewResult`

or if completing this task would require changing benchmark semantics rather than validating them.
