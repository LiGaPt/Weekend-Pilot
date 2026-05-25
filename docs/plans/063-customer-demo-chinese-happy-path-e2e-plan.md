# Plan: 063 Customer Demo Chinese Happy Path E2E

## 1. Spec Reference

Spec file:

```text
docs/specs/063-customer-demo-chinese-happy-path-e2e.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/customer-demo-selected-plan-replan-index`.
- Current `HEAD` is `b5f0566`, which matches task `062`.
- `main` does not yet contain tasks `058` to `062`; this task should be executed on a new branch created from current `HEAD` or after that stacked branch chain is merged.
- `frontend/e2e/demo.spec.ts` already contains the desktop/mobile browser suite, helper functions, and the existing English stable happy-path coverage.
- `frontend/src/App.tsx` already defines the Chinese default customer prompt, clarification panel, confirmation boundary, and the public test ids the new smoke should reuse.
- `docs/WEB_DEMO_README.md` already documents manual happy path, clarification, replan, and automated browser checks, but it does not explicitly state that desktop coverage includes an additive Chinese reviewer smoke.
- PostgreSQL, Redis, and Alembic migrations are still prerequisites for browser E2E.
- The working tree is already dirty outside this task: `.gitignore` is modified, and `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/`, and `qc` are untracked. Do not stage them.

## 3. Files to Add

- None.

## 4. Files to Modify

- `frontend/e2e/demo.spec.ts` - add the additive desktop Chinese happy-path smoke and any helper parameterization needed to support a Chinese clarification reply without changing existing English callers.
- `docs/WEB_DEMO_README.md` - document the new desktop Chinese smoke, keep the English stable smoke explicitly in scope, and add the focused/full desktop verification commands.

## 5. Implementation Steps

1. In `frontend/e2e/demo.spec.ts`, keep the existing English stable prompt, English stable clarification reply, and current desktop/mobile tests unchanged as the baseline.
2. Reuse the currently unused Chinese happy-path prompt constant if it already exists in the file; otherwise rename it clearly so it becomes the dedicated Chinese reviewer prompt for this new smoke.
3. Add a dedicated Chinese clarification reply constant in the same Playwright spec. It should be a natural Chinese continuation that can satisfy the current clarification policy and lead back to a confirmable Mock World plan.
4. Refactor the local helper that waits for `awaiting_confirmation` so it accepts a clarification reply argument. Existing English callers must continue passing the English reply implicitly or explicitly, and their behavior must remain unchanged.
5. Add a new desktop-only Playwright test whose title includes the stable substring `Chinese reviewer prompt` so it can be run with `--grep "Chinese reviewer prompt"`. This test must:
   - open `/`;
   - fill the Chinese reviewer prompt;
   - click `start-button`;
   - wait until `run-status` becomes either `等待确认` or `等待补充信息`;
   - if `等待补充信息` appears, fill `clarification-reply-input` with the Chinese clarification reply and click `clarification-submit-button`;
   - then wait for `run-status` to become `等待确认`.
6. In that new test, assert only stable public contract outputs:
   - `plan-version` is `v1`;
   - `action-count` is `0`;
   - `confirm-button` is visible;
   - the page is still using the normal customer confirmation flow rather than an AMap read-only block.
7. Do not add route mocks for `POST /demo/runs` or `POST /demo/runs/{run_id}/clarify` in this new test. The point of the task is to cover the real local stack with a Chinese prompt.
8. Update `docs/WEB_DEMO_README.md` in two places:
   - under the browser or automated checks section, state that desktop coverage now contains both the existing English stable smoke and the additive Chinese reviewer smoke;
   - under local verification instructions, add the focused `--grep "Chinese reviewer prompt"` command and keep the full `--project=desktop-chromium` command as the pre-commit regression command.
9. Run the focused Chinese smoke first for fast iteration, then run the full `desktop-chromium` Playwright project to prove the English stable smoke still coexists cleanly with the new Chinese smoke.
10. Before committing, run `git diff --check` and `git status --short`. Stage only `frontend/e2e/demo.spec.ts` and `docs/WEB_DEMO_README.md`.
11. Commit on a new stacked branch from current `HEAD`, using the planned conventional commit message.

## 6. Testing Plan

- Browser E2E: add one new real-stack desktop smoke that starts from a Chinese reviewer prompt and reaches a confirmable plan.
- Browser E2E regression: rerun the full `desktop-chromium` project so the existing English stable happy-path, clarification, replan, decline, redaction, and AMap checks remain green.
- Docs review: confirm `docs/WEB_DEMO_README.md` now describes the Chinese smoke as additive coverage, not a replacement for the English stable smoke.
- Unit tests: none planned; this task stays inside Playwright and documentation.
- Backend integration tests: none planned; this task does not change backend behavior or public contracts.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "Chinese reviewer prompt"
npm --prefix frontend run e2e -- --project=desktop-chromium
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
test: add chinese customer demo happy-path smoke
```

Expected commands:

```bash
git switch -c codex/customer-demo-chinese-happy-path-e2e
git status --short
git add frontend/e2e/demo.spec.ts docs/WEB_DEMO_README.md
git commit -m "test: add chinese customer demo happy-path smoke"
git push -u origin codex/customer-demo-chinese-happy-path-e2e
```

The implementer must confirm `.env`, secrets, `.gitignore`, `docs/COMPETITION_SUBMISSION_DESIGN.md`, `docs/NEXT_PHASE_ROADMAP.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/`, and `qc` are not staged.

## 9. Out-of-scope Changes

- Do not change unrelated modules.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md` unless the spec explicitly requires it.
- Do not add new dependencies unless listed in this plan.
- Do not commit generated caches, virtual environments, or secrets.
- Do not change `frontend/src/App.tsx`, `frontend/src/api/demo.ts`, or backend workflow code for this task.
- Do not replace, delete, or weaken the existing English stable happy-path smoke.
- Do not add or modify the mobile smoke except for unavoidable shared helper call-site updates inside `frontend/e2e/demo.spec.ts`.
- Do not change `frontend/playwright.config.ts` or `frontend/scripts/run-e2e.mjs` unless the new smoke is impossible without it; that should be treated as out of scope for this task.
- Do not modify benchmark fixtures, benchmark suites, or README top-level product behavior text.
- Do not stage unrelated dirty files already present in the working tree.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.
- [ ] The new smoke uses a Chinese prompt and a Chinese clarification reply.
- [ ] The existing English stable smoke is still present and still covered by the full desktop Playwright run.
- [ ] The new smoke uses the real local stack rather than mocked start/clarify responses.
- [ ] `docs/WEB_DEMO_README.md` clearly states the Chinese smoke is additive coverage.

## 11. Handoff Notes

After finishing, the implementer should report back with:

- Changed files.
- The exact new Playwright test title containing `Chinese reviewer prompt`.
- Focused smoke command result.
- Full `desktop-chromium` Playwright run result.
- Commit hash.
- Push result.
- Any observed stability caveats in the Chinese clarification fallback, if the workflow occasionally chooses `awaiting_clarification` before returning to `awaiting_confirmation`.
