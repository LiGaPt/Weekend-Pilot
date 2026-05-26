# Richer Web UI V1 Checklist

This checklist is the canonical reviewer path for confirming that WeekendPilot's richer Web UI is present as one V1 product slice, not as disconnected features spread across scripts, artifacts, and internal notes.

Use it together with:

- `docs/WEB_DEMO_README.md`
- `python scripts/run_benchmark_release_gate.py`
- `python scripts/run_recovery_replay_review.py`

## Customer-safe Evidence

| Capability | Authoritative surface | Reviewer action | Visible evidence to confirm |
| --- | --- | --- | --- |
| planning | `http://127.0.0.1:5173/` | Start a Mock World run from the customer page and wait for plan review. | A selected plan is visible with `行程时间线`, route, feasibility, and `执行动作预览`. |
| confirmation | `http://127.0.0.1:5173/` | Keep the run at `awaiting_confirmation` before clicking `确认当前方案`. | The `确认边界` section is visible, the confirm button is present, and `动作数` remains `0` before confirmation. |
| execution timeline | `http://127.0.0.1:5173/` | Confirm the selected plan and wait for execution to finish. | The page shows `执行时间线` with ordered steps, action/tool labels, targets, statuses, plus compact start and finish timestamps when present. |

## Internal Reviewer-only Evidence

| Capability | Authoritative surface | Reviewer action | Visible evidence to confirm |
| --- | --- | --- | --- |
| trace summary | `http://127.0.0.1:5174/` | Paste a demo `run_id` into the internal page and load the run. | The page shows `Trace Summary` and explicitly surfaces run identity, trace identity, workflow timing, and observability status. |
| benchmark summary | `http://127.0.0.1:5174/` and `GET /internal/benchmarks/release-gate-v1/summary` | Run `python scripts/run_benchmark_release_gate.py`, then open the internal page. | The page shows `Benchmark Summary` without requiring a run ID and renders suite counts, overall score, and release-gate matrix counts from `var/formal-benchmarks/latest-release_gate_v1-run-report.json`. |
| recovery visualization | `http://127.0.0.1:5174/` | Run `python scripts/run_recovery_replay_review.py`, capture the emitted source `run_id`, then load that run in the internal page. | The page shows `Recovery Visualization`, attempt count, max attempts, per-attempt recovery details, and replay source linkage back to the benchmark report path. |

## Reviewer Sequence

1. Start backend and both frontends as described in `docs/WEB_DEMO_README.md`.
2. On `5173`, verify planning and confirmation using a Mock World run.
3. Confirm the run and verify the customer-facing execution timeline.
4. Copy the resulting `run_id`.
5. On `5174`, verify `Benchmark Summary` first. This panel should load before any run ID is entered.
6. Load the copied `run_id` and verify `Trace Summary`.
7. Run `python scripts/run_recovery_replay_review.py`, then load the emitted recovery `run_id` on `5174` and verify `Recovery Visualization`.

## Public/Internal Boundary

- Customer-safe evidence stays on `5173` only.
- Internal reviewer-only evidence stays on `5174` or the internal benchmark route only.
- Do not treat raw trace payloads, internal IDs, replay controls, benchmark browsers, or generated `var/` directories as customer-surface evidence for this V1 slice.
