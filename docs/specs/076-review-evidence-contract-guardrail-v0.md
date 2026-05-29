# Spec: 076 V1.5 Review Evidence Contract Guardrail v0

## 1. Goal

Task `075` 已经把 V1.5 reviewer evidence package 的官方入口、latest alias 路径和 tracked-vs-ignored 归属规则手工收口到了正式文档中。但当前仓库仍然缺少一个可执行的 guardrail，来验证以下几件事是否持续同时成立：

- `README.md`、`docs/V1_5_REVIEW_EVIDENCE.md`、`docs/COMPETITION_SUBMISSION_DESIGN.md` 与 `.gitignore` 仍保持 `075` 固定下来的官方契约。
- 四条 canonical latest alias 证据链仍存在，并且最小 schema / suite / case / status 契约没有漂移。
- maintainer 在提交前可以用一条 repo-root 命令快速发现 evidence drift，而不是靠手工逐文件比对。

本任务完成后，仓库必须提供一个正式的 repo-root 校验命令：`python scripts/verify_review_evidence.py`。这条命令负责检查 reviewer evidence 文档契约和现有 latest alias 产物契约，并在失败时给出可操作的修复方向。它是对 `075` 的补强，而不是新的 benchmark 能力扩展。

## 2. Project Context

这个任务对应 `docs/NEXT_PHASE_ROADMAP.md` 的 `M1. 评测与观测基础设施`。

原因不是它新增了 benchmark 算法或 observability API，而是它把已经形成的 V1.5 evidence contract 变成了可执行校验规则，直接服务于“可量化比较、可稳定复现、可直接作为评审基线”的目标。它同时承接以下已完成 task：

- Task `061`：`python scripts/run_formal_verification.py` 与 `var/formal-benchmarks/latest-all_registered-run-report.json`
- Task `065`：`python scripts/run_benchmark_release_gate.py` 与 `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- Task `067`：`python scripts/run_recovery_replay_review.py` 与 `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Task `074`：`python scripts/run_benchmark_coverage_gate.py` 与 `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
- Task `075`：官方 reviewer/submission 文档与 ignore 边界收口

这个任务不改产品 workflow、不改 Tool Gateway、不改 Frontend，也不改变 PostgreSQL / Redis / LangSmith 的运行职责。它属于 benchmark-driven 工程治理层。

## 3. Requirements

- Add one new repo-root verification entrypoint:
  - `python scripts/verify_review_evidence.py`

- Add one new backend verification module:
  - `backend/app/benchmark/review_evidence.py`

- The verification module must define the canonical V1.5 evidence contract in code, including:
  - the exact four review commands
  - the exact four canonical latest alias paths
  - the official tracked docs that participate in the contract
  - the required ignored scratch paths from `.gitignore`
  - the stale copied artifact path that must not appear in official tracked docs:
    - `docs/artifacts/benchmark-all-registered-formal-report.json`

- The verifier must validate these tracked docs:
  - `README.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `.gitignore`

- `docs/V1_5_REVIEW_EVIDENCE.md` must be validated as the canonical reviewer entrypoint.
  It must still contain these exact repo-root commands:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_benchmark_coverage_gate.py`
  - `python scripts/run_formal_verification.py`
  - `python scripts/run_recovery_replay_review.py`

- `docs/V1_5_REVIEW_EVIDENCE.md` must still contain these exact canonical latest aliases:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`

- `docs/V1_5_REVIEW_EVIDENCE.md` must still state that:
  - `docs/artifacts/` is not the source of truth for benchmark or recovery evidence
  - canonical generated evidence stays under `var/`

- `docs/COMPETITION_SUBMISSION_DESIGN.md` must be validated to ensure that:
  - it points readers to `docs/V1_5_REVIEW_EVIDENCE.md`
  - it cites the same four canonical latest alias paths
  - it does not contain `docs/artifacts/benchmark-all-registered-formal-report.json`

- `README.md` must be validated to ensure that:
  - it contains a concise pointer to `docs/V1_5_REVIEW_EVIDENCE.md`
  - it does not reintroduce `docs/artifacts/benchmark-all-registered-formal-report.json` as the official evidence path

- `.gitignore` must be validated to ensure these entries remain ignored:
  - `docs/artifacts/`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `qc`
  - `.env`
  - `.env.*`
  - `var/`

- The verifier must validate the four current latest alias files using structured parsing, not ad hoc text search.
  - Benchmark artifacts must validate through `BenchmarkRunReport`.
  - Recovery review artifacts must validate through `RecoveryReplayReviewResult`.

- The verifier must enforce these minimal alias-level contracts:
  - `latest-release_gate_v1-run-report.json`
    - file exists
    - parses as `BenchmarkRunReport`
    - top-level `run_status == "passed"`
    - `benchmark_summary.suite_id == "release_gate_v1"`
    - raw payload includes `release_gate_evaluation.gate_id == "release_gate_v1"`
  - `latest-coverage_gate_v1_5-run-report.json`
    - file exists
    - parses as `BenchmarkRunReport`
    - top-level `run_status == "passed"`
    - `benchmark_summary.suite_id == "all_registered"`
    - raw payload includes `coverage_gate_evaluation.gate_id == "coverage_gate_v1_5"`
    - raw payload includes `coverage_gate_evaluation.release_blocked == false`
  - `latest-all_registered-run-report.json`
    - file exists
    - parses as `BenchmarkRunReport`
    - top-level `run_status == "passed"`
    - `benchmark_summary.suite_id == "all_registered"`
  - `latest-family_route_failure_v1-review.json`
    - file exists
    - parses as `RecoveryReplayReviewResult`
    - `status == "passed"`
    - `case_id == "family_route_failure_v1"`

- The verifier must print actionable failures.
  At minimum:
  - missing or invalid alias failures must name the matching rerun command
  - missing doc content failures must name the doc path and the missing / forbidden string
  - stale copied-artifact failures must name the stale path explicitly

- The verifier must return:
  - exit code `0` when all checks pass
  - exit code `1` when any check fails

- Add focused unit tests for the verifier.
  The tests must use temporary directories / fake repo fixtures and must not depend on the real ignored `var/` directory in the current workspace.

- Update `docs/V1_5_REVIEW_EVIDENCE.md` with one concise verification section that points to:
  - `python scripts/verify_review_evidence.py`

- Update `README.md` with one concise additive note that the pinned V1.5 evidence package can be checked with:
  - `python scripts/verify_review_evidence.py`

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not rerun or regenerate benchmark or recovery outputs under `var/` as part of the implementation.
- Do not change benchmark counts, suite membership, latency SLOs, coverage thresholds, or recovery semantics.
- Do not rewrite `docs/COMPETITION_SUBMISSION_DESIGN.md` beyond the minimum needed to restore the already-observed `075` contract; the default expectation is no content change there.
- Do not add CI jobs, GitHub workflows, pre-commit hooks, or artifact publication automation.
- Do not compare unstable nested absolute `report_path` values inside the latest alias JSON files.
- Do not modify `frontend/`, demo APIs, Tool Gateway behavior, or workflow execution logic.

## 5. Interfaces and Contracts

### Inputs

- Official tracked docs:
  - `README.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `.gitignore`

- Canonical latest alias files:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`

- Existing schema types:
  - `backend.app.benchmark.schemas.BenchmarkRunReport`
  - `backend.app.benchmark.schemas.RecoveryReplayReviewResult`

### Outputs

- New repo-root command:
  - `python scripts/verify_review_evidence.py`

- Human-readable CLI summary:
  - success summary with checked docs and aliases
  - failure summary with actionable issues

- Programmatic result object returned by the backend verification module.
  It does not write files, database rows, Redis keys, or benchmark artifacts.

### Schemas

Example result payload shape for the backend verifier:

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
    "formal_verification": "var/formal-benchmarks/latest-all_registered-run-report.json",
    "recovery_replay_review": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
  },
  "failures": []
}
```

Required command-to-alias mapping:

```json
{
  "release_gate_v1": {
    "command": "python scripts/run_benchmark_release_gate.py",
    "latest_alias": "var/formal-benchmarks/latest-release_gate_v1-run-report.json"
  },
  "coverage_gate_v1_5": {
    "command": "python scripts/run_benchmark_coverage_gate.py",
    "latest_alias": "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json"
  },
  "formal_verification": {
    "command": "python scripts/run_formal_verification.py",
    "latest_alias": "var/formal-benchmarks/latest-all_registered-run-report.json"
  },
  "recovery_replay_review": {
    "command": "python scripts/run_recovery_replay_review.py",
    "latest_alias": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
  }
}
```

## 6. Observability

This task does not add runtime observability, LangSmith metadata, PostgreSQL rows, Redis events, or new generated artifacts.

The verifier itself must provide deterministic CLI output only:

- on success:
  - concise summary of the docs checked
  - concise summary of the four alias contracts checked
- on failure:
  - one line per failure with doc path or alias path
  - rerun command hints for missing / invalid aliases

No new logs or persistent telemetry are required.

## 7. Failure Handling

- If an official tracked doc is missing, the verifier must fail.
- If a required command, alias path, or ownership statement is missing from `docs/V1_5_REVIEW_EVIDENCE.md`, the verifier must fail.
- If `docs/COMPETITION_SUBMISSION_DESIGN.md` no longer points to `docs/V1_5_REVIEW_EVIDENCE.md`, the verifier must fail.
- If any official tracked doc contains `docs/artifacts/benchmark-all-registered-formal-report.json`, the verifier must fail.
- If any required `.gitignore` entry is missing, the verifier must fail.
- If a latest alias file is missing, the verifier must fail and name the exact rerun command that refreshes it.
- If a latest alias file is malformed JSON or fails Pydantic validation, the verifier must fail and report the invalid path.
- If a latest alias file has the wrong suite ID, case ID, or non-passing status, the verifier must fail.
- The verifier must not auto-fix docs, regenerate artifacts, or rewrite alias files.

## 8. Acceptance Criteria

- [ ] `docs/specs/076-review-evidence-contract-guardrail-v0.md` exists and matches this task.
- [ ] `docs/plans/076-review-evidence-contract-guardrail-v0-plan.md` exists and matches this task.
- [ ] `backend/app/benchmark/review_evidence.py` exists and exposes the V1.5 review evidence verification logic.
- [ ] `scripts/verify_review_evidence.py` exists and runs the verifier from the repo root.
- [ ] The verifier checks `README.md`, `docs/V1_5_REVIEW_EVIDENCE.md`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, and `.gitignore`.
- [ ] The verifier checks the exact four canonical latest alias files under `var/formal-benchmarks/` and `var/recovery-reviews/`.
- [ ] The verifier uses `BenchmarkRunReport` and `RecoveryReplayReviewResult` for structured parsing.
- [ ] The verifier returns exit code `0` on a passing repo and exit code `1` on any failure.
- [ ] `tests/test_review_evidence.py` exists and covers at least one passing case plus failure cases for missing doc content, stale artifact references, and invalid / missing aliases.
- [ ] `docs/V1_5_REVIEW_EVIDENCE.md` includes the new verification command.
- [ ] `README.md` includes a concise pointer to the new verification command.
- [ ] `docs/COMPETITION_SUBMISSION_DESIGN.md` remains aligned with the `075` contract and is not widened into a broader rewrite.
- [ ] No benchmark runner logic, suite membership, threshold, or runtime execution behavior changes.
- [ ] No generated JSON artifact under `var/` is committed by this task.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except intentionally ignored local runtime outputs.

## 9. Verification Commands

```bash
python -m pytest tests/test_review_evidence.py -q
python scripts/verify_review_evidence.py
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add review evidence contract guardrail
```

## 11. Notes for the Implementer

Use existing repository patterns:

- follow the `backend/app/benchmark/internal_summary.py` style for repo-root defaults, typed validation, and clear error types
- follow the thin wrapper pattern used by the existing `scripts/run_*.py` entrypoints
- use structured JSON parsing and Pydantic validation, not regex against raw artifact JSON

Assumptions locked for this task:

1. Task `075` is already complete and is the latest formal task on disk and in git history.
2. `docs/COMPETITION_SUBMISSION_DESIGN.md` already satisfies the intended `075` content contract as of `2026-05-29`; validate it, but do not rewrite it unless the current repo demonstrably fails the new verifier.
3. The four canonical evidence chains remain:
   - `release_gate_v1`
   - `coverage_gate_v1_5`
   - `all_registered`
   - `family_route_failure_v1` recovery review
4. The verifier is a maintainer / submission guardrail, not a default runtime dependency and not a CI system.

Stop and report back if implementing this task would require changing benchmark behavior, suite contracts, or the meaning of the latest alias artifacts.
