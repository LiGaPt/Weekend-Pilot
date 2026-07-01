# V1.5 Review Evidence

## Purpose

This document is the canonical reviewer entrypoint for the V1.5 evidence package.
Use it to find the official repo-root commands, the canonical latest report aliases,
and the ownership rules for tracked versus ignored materials.

## Canonical Review Commands

Run the following commands from the repository root when you need to refresh evidence:

| Review target | Command | Canonical latest alias |
| --- | --- | --- |
| V1 blocking release gate | `python scripts/run_benchmark_release_gate.py` | `var/formal-benchmarks/latest-release_gate_v1-run-report.json` |
| V1.5 coverage gate | `python scripts/run_benchmark_coverage_gate.py` | `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json` |
| V2 integrity gate | `python scripts/run_benchmark_v2_integrity_gate.py` | `var/formal-benchmarks/latest-v2_integrity_gate-run-report.json` |
| V2 repeated-run stability | `python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4` | `var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json` |
| Full registered formal verification | `python scripts/run_formal_verification.py` | `var/formal-benchmarks/latest-all_registered-run-report.json` |
| Recovery replay review | `python scripts/run_recovery_replay_review.py` | `var/recovery-reviews/latest-family_route_failure_v1-review.json` |

## When To Rerun Versus When To Cite

- If the matching latest alias already exists and you only need the current canonical evidence, cite the alias directly.
- If a latest alias is missing locally, or you intentionally need fresh evidence, rerun the matching command from the repo root first.
- `docs/artifacts/` is not the source of truth for benchmark or recovery evidence.
- Canonical generated evidence stays under `var/`.
- Reviewers should cite the latest aliases above, not copied JSON snapshots under `docs/`.

## Ownership And Git Rules

| Category | Paths | Git expectation | Notes |
| --- | --- | --- | --- |
| Official tracked docs | `docs/COMPETITION_SUBMISSION_DESIGN.md` | Track | Submission-facing design summary. |
| Official tracked docs | `docs/V1_5_REVIEW_EVIDENCE.md` | Track | Reviewer-facing evidence entrypoint. |
| Local scratch docs | `docs/V1_DEVELOPMENT_REPORT.md` | Ignore | Local working draft, not a submission deliverable. |
| Local scratch docs | `docs/TASK_WORKFLOW_PROMPTS.md` | Ignore | Local workflow notes, not reviewer evidence. |
| Local scratch docs | `docs/artifacts/` | Ignore | Non-canonical copied artifacts; do not cite as source of truth. |
| Local scratch docs | `qc` | Ignore | Local quality-check scratch area. |
| Generated runtime evidence | `var/` | Ignore | Canonical generated benchmark and recovery evidence lives here. |
| Secrets and local env files | `.env` | Ignore | Never commit secrets or local machine configuration. |
| Secrets and local env files | `.env.*` except `.env.example` | Ignore | Keep `.env.example` trackable; ignore all local variants. |

## Submission Reference

`docs/COMPETITION_SUBMISSION_DESIGN.md` is the concise submission-facing summary.
This document is the reviewer-facing evidence package reference and ownership map.

## Verification

Run `python scripts/verify_review_evidence.py` before submission to validate the official docs and the current six canonical evidence aliases together.
