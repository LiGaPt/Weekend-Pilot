# Plan: 129 Offline delivery boundary and submission polish v0

## 1. Spec Reference

Spec file:

```text
docs/specs/129-offline-delivery-boundary-submission-polish-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch before implementation is expected to be `codex/128-memory-governance-final-closure-v0`.
- Latest committed task is expected to be Task `128`, with latest commit similar to `3c0b62a test: close memory governance delivery surface`.
- `docs/specs` and `docs/plans` are expected to be matched through Task `128`.
- Historical task numbering includes a known gap at `122` and a `113.5` task; do not repair or renumber these in this task.
- `docs/WEB_DEMO_README.md` is the actual demo README path; do not create a root-level `WEB_DEMO_README.md` unless existing docs explicitly require it.
- Existing submission docs live under `docs/submission/`.
- Current untracked files may include:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- The current formal delivery boundary is `Mock World` local/offline closed loop. `AMap` is optional API/script-only read-only preview and must not be described as a formal main-chain dependency.
- This is a documentation and verification task. Runtime code changes should be avoided unless a focused documentation test requires a small test helper update.

## 3. Files to Add

- `docs/specs/129-offline-delivery-boundary-submission-polish-v0.md` - task spec for the delivery-boundary and submission-polish closure.
- `docs/plans/129-offline-delivery-boundary-submission-polish-v0-plan.md` - implementation plan for the closure task.

## 4. Files to Modify

- `README.md` - tighten top-level delivery wording, formal Mock World boundary, no real-world write/MCP dependency, and submission/evidence pointers.
- `docs/WEB_DEMO_README.md` - add or update the 3-minute judge path and `5173 -> 5174` sequence.
- `docs/submission/OVERVIEW.md` - align version, delivery boundary, evidence commands, and reading order.
- `docs/submission/FUNCTION_COVERAGE_MAP.md` - map all capabilities to live demo surfaces or canonical evidence.
- `docs/submission/EVIDENCE_MAP.md` - verify evidence aliases and artifact paths match scripts and actual latest aliases.
- `docs/submission/DEMO_SCRIPT.md` - add short judge script and optional longer backup script.
- `docs/submission/RECORDING_CHECKLIST.md` - align preflight, browser order, secrets hygiene, evidence checks, and offline boundary checks.
- `tests/test_demo_support_scripts.py` - add or update focused documentation-contract assertions if existing coverage is insufficient.
- Optional cleanup targets after inspection:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/specs/2026-06-05-readme-roadmap-polish-design.md`
  - `docs/superpowers/plans/2026-06-05-readme-roadmap-polish.md`

## 5. Implementation Steps

1. Confirm sequencing with:
   ```bash
   git log --oneline -n 12
   git status --short
   ```
2. Confirm Task `129` files do not already exist:
   ```bash
   dir docs\specs\129-*
   dir docs\plans\129-*
   ```
   On PowerShell, missing files are acceptable at this point.
3. Add `docs/specs/129-offline-delivery-boundary-submission-polish-v0.md` from the approved spec content.
4. Add `docs/plans/129-offline-delivery-boundary-submission-polish-v0-plan.md` from this approved plan content.
5. Read the current evidence alias source:
   ```bash
   python -c "from backend.app.benchmark.submission_evidence import SUBMISSION_EVIDENCE_ALIASES; print(SUBMISSION_EVIDENCE_ALIASES)"
   ```
   If this import fails, inspect `backend/app/benchmark/submission_evidence.py` directly and use the actual contract.
6. Inspect current support script outputs without changing files:
   ```bash
   python scripts/show_submission_evidence.py
   ```
   Record the exact alias names and paths that print `[OK]`.
7. Update the top of `README.md` so it contains a short, explicit delivery boundary:
   - Current formal chain is `Mock World`.
   - Public demo, benchmark, evidence, and offline submission are local deterministic closed-loop.
   - No real-world write provider is connected in the current formal chain.
   - No true MCP integration is required for current formal delivery.
   - `AMap` remains optional API/script-only read-only preview.
8. In `README.md`, verify all links to submission docs point to actual files under `docs/submission/` and `docs/WEB_DEMO_README.md`.
9. Update `docs/WEB_DEMO_README.md` with a top section named `3-minute review path` or Chinese equivalent. The sequence must be:
   - Open `http://127.0.0.1:5173/`.
   - Run one public happy path or use an already prepared run.
   - Show confirmation boundary and execution result.
   - Switch to `http://127.0.0.1:5174/`.
   - Show `Benchmark Summary`, `System Integrity Summary`, and optional `Load Run`.
   - Run `python scripts/show_submission_evidence.py`.
10. In `docs/WEB_DEMO_README.md`, make the longer path optional and clearly label it as backup/deeper review.
11. Update `docs/submission/OVERVIEW.md` so the opening paragraph says the current formal submission is `Mock World` offline/local closed loop and does not depend on real MCP or real-world write integrations.
12. Update `docs/submission/FUNCTION_COVERAGE_MAP.md` so every row has a concrete demonstration method:
   - `5173 live`
   - `5174 live`
   - `python scripts/show_submission_evidence.py`
   - optional `python scripts/demo_amap_preview.py`
13. Update `docs/submission/EVIDENCE_MAP.md` so every alias path matches the actual script/source contract. Do not invent paths.
14. Update `docs/submission/DEMO_SCRIPT.md` with two sections:
   - `3-minute judge path`
   - `Optional extended review path`
15. In `docs/submission/DEMO_SCRIPT.md`, ensure the first live browser order is `5173 -> 5174`.
16. Update `docs/submission/RECORDING_CHECKLIST.md` so it includes:
   - Service readiness checks.
   - Browser tab order `5173 -> 5174`.
   - `python scripts/demo_preflight.py`.
   - `python scripts/show_submission_evidence.py`.
   - Optional `python scripts/demo_amap_preview.py`.
   - Explicit rule not to show `.env`, API keys, tokens, or secrets.
   - Explicit rule that AMap and real MCP are not formal main-chain dependencies.
17. Inspect `docs/NEW_WORKFLOW_PROMPT.md` and `docs/TASK_INFO.md`:
   - If content is useful for final handoff, incorporate only the stable portions into `README.md`, `docs/WEB_DEMO_README.md`, or `docs/submission/*`.
   - If content is scratch or duplicates the generated task card/spec/plan, remove it from the working tree before commit.
18. Inspect `docs/superpowers/`:
   - If these are old scratch planning files, remove them before commit.
   - If they contain useful final docs, move the relevant content into tracked repository docs and remove the scratch directory.
   - Do not stage `docs/superpowers/` unless there is a deliberate reason and the files are part of the project's documented workflow.
19. Update `tests/test_demo_support_scripts.py` with focused assertions if they do not already exist. Required assertions should cover:
   - `README.md` contains `Mock World`.
   - `README.md` contains a phrase equivalent to no real-world write dependency.
   - `README.md` contains a phrase equivalent to no true MCP dependency.
   - `docs/WEB_DEMO_README.md` contains `5173 -> 5174`.
   - Submission docs mention `python scripts/show_submission_evidence.py`.
   - Submission docs mention `AMap` only as read-only preview or optional preview.
20. Run focused tests:
   ```bash
   python -m pytest tests/test_demo_support_scripts.py -q
   ```
21. Run evidence script:
   ```bash
   python scripts/show_submission_evidence.py
   ```
   Expected: all canonical aliases print `[OK]`.
22. Run preflight:
   ```bash
   python scripts/demo_preflight.py
   ```
   Expected: service and evidence checks pass when local services are running. If services are not running, record the exact blocked checks.
23. Check staged/unstaged state:
   ```bash
   git status --short
   ```
24. Verify no secrets are staged:
   ```bash
   git diff --cached --name-only
   ```
   If nothing is staged yet, use this after `git add`.
25. Stage only intended files:
   ```bash
   git add README.md docs/WEB_DEMO_README.md docs/submission/OVERVIEW.md docs/submission/FUNCTION_COVERAGE_MAP.md docs/submission/EVIDENCE_MAP.md docs/submission/DEMO_SCRIPT.md docs/submission/RECORDING_CHECKLIST.md docs/specs/129-offline-delivery-boundary-submission-polish-v0.md docs/plans/129-offline-delivery-boundary-submission-polish-v0-plan.md tests/test_demo_support_scripts.py
   ```
   Include any additional intentionally tracked cleanup file only after verifying it belongs in the commit.
26. Re-check staged files:
   ```bash
   git diff --cached --name-only
   git status --short
   ```
27. Commit:
   ```bash
   git commit -m "docs: polish offline delivery boundary and submission evidence"
   ```
28. Push only if the user asks for push or project workflow requires it:
   ```bash
   git push
   ```

## 6. Testing Plan

- Unit/document-contract tests:
  - `tests/test_demo_support_scripts.py` should verify README and submission docs contain the formal `Mock World` delivery boundary.
  - `tests/test_demo_support_scripts.py` should verify `docs/WEB_DEMO_README.md` documents `5173 -> 5174`.
  - `tests/test_demo_support_scripts.py` should verify submission docs reference `python scripts/show_submission_evidence.py`.
  - `tests/test_demo_support_scripts.py` should verify `AMap` is documented as optional read-only preview.
- Script smoke tests:
  - `python scripts/show_submission_evidence.py` should print all canonical aliases as `[OK]`.
  - `python scripts/demo_preflight.py` should pass when local services are running.
- Git hygiene:
  - `git status --short` should not show unintended untracked delivery files after commit.
  - No secrets or generated caches should be staged.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
git log --oneline -n 12
git status --short
python -m pytest tests/test_demo_support_scripts.py -q
python scripts/show_submission_evidence.py
python scripts/demo_preflight.py
git status --short
```

Optional preview boundary command:

```bash
python scripts/demo_amap_preview.py
```

If `python scripts/demo_preflight.py` fails because PostgreSQL, Redis, backend, or frontend services are not running, report the exact failing checks and do not treat that as a documentation failure.

## 8. Commit and Push Plan

Expected commit message:

```text
docs: polish offline delivery boundary and submission evidence
```

Expected commands:

```bash
git status --short
git add README.md docs/WEB_DEMO_README.md docs/submission/OVERVIEW.md docs/submission/FUNCTION_COVERAGE_MAP.md docs/submission/EVIDENCE_MAP.md docs/submission/DEMO_SCRIPT.md docs/submission/RECORDING_CHECKLIST.md docs/specs/129-offline-delivery-boundary-submission-polish-v0.md docs/plans/129-offline-delivery-boundary-submission-polish-v0-plan.md tests/test_demo_support_scripts.py
git diff --cached --name-only
git commit -m "docs: polish offline delivery boundary and submission evidence"
git status --short
```

Push command, only when requested:

```bash
git push
```

The implementer must confirm `.env`, secrets, generated caches, local runtime output, and unrelated files are not staged.

## 9. Out-of-scope Changes

- Do not implement real MCP.
- Do not add new MCP server configuration.
- Do not connect the public demo to real-world write providers.
- Do not promote `AMap` to a formal benchmark or customer UI dependency.
- Do not add new benchmark cases.
- Do not regenerate benchmark artifacts unless existing evidence aliases are broken.
- Do not redesign frontend UI.
- Do not modify provider behavior, planning logic, memory governance behavior, recovery behavior, or benchmark scoring unless a test exposes a direct documentation/script mismatch.
- Do not rewrite historical specs or plans to repair task numbering.
- Do not commit `.env`, API keys, tokens, secrets, generated caches, virtual environments, or local runtime dumps.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within documentation/submission polish scope.
- [ ] `README.md` clearly states `Mock World` is the current formal main chain.
- [ ] `README.md` clearly states no real-world write path and no true MCP dependency in current formal delivery.
- [ ] `docs/WEB_DEMO_README.md` includes a short `5173 -> 5174` reviewer path.
- [ ] `docs/submission/*` files agree on version name, evidence aliases, and review sequence.
- [ ] `AMap` is only described as optional API/script-only read-only preview.
- [ ] Untracked delivery/workflow scratch files have been incorporated, removed, or explicitly left out for a documented reason.
- [ ] `python -m pytest tests/test_demo_support_scripts.py -q` passed.
- [ ] `python scripts/show_submission_evidence.py` printed all expected aliases as `[OK]`.
- [ ] `python scripts/demo_preflight.py` passed or its service-readiness blocker was reported.
- [ ] Git status was clean after commit, except intentionally ignored local files if any.
- [ ] Commit message matches the plan.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After finishing, report back:

- Changed files.
- How each untracked delivery/workflow file was handled:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- Verification commands and results.
- Whether `python scripts/demo_preflight.py` passed or was blocked by local services.
- Commit hash.
- Push result, if pushed.
- Any remaining follow-up task, especially if evidence aliases are missing or service preflight cannot be verified locally.
