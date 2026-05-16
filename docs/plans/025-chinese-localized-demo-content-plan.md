# Plan: 025 Chinese Localized Demo Content

## 1. Spec Reference

Spec file:

```text
docs/specs/025-chinese-localized-demo-content.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch starts from `task24`.
- Task 024 completed the Web demo API, minimal React UI, Playwright E2E, and Web demo runbook.
- The demo path is Mock World-only and uses `backend/app/providers/mock_world/fixtures/family_afternoon.json`.
- Venue data is not stored in a dedicated table. It is persisted through JSONB payloads in plans, tool events, and action ledger rows.
- The existing API contracts and status enum values are stable and should remain English.
- `var/` may contain local runtime files and must not be staged.

## 3. Files to Add

- None for the implementation task unless a focused copy helper module is introduced.

## 4. Files to Modify

- `backend/app/providers/mock_world/fixtures/family_afternoon.json` - replace user-visible venue, route, weather, table, ticket, addon, and recipient display content with Chinese.
- `backend/app/planning/itinerary_generation.py` - generate Chinese visible itinerary title, summary, timeline labels, timeline notes, feasibility display reasons/warnings, and proposed action reasons.
- `backend/app/feedback/writer.py` - generate Chinese feedback headlines, messages, action messages, and next steps.
- `frontend/src/App.tsx` - translate visible UI shell and default prompt to Chinese while preserving API calls and `data-testid` attributes.
- `frontend/src/App.test.tsx` and `frontend/e2e/demo.spec.ts` - update visible-text assertions and fixture data for the Chinese demo surface.
- Relevant backend tests under `tests/` - update expected visible strings only where tests assert English user-facing content.
- `docs/WEB_DEMO_README.md` and `README.md` - update demo instructions/examples if they show the default prompt or visible UI flow.

## 5. Implementation Steps

1. Create or switch to the task branch.

```bash
git switch task24
git switch -c task25
```

If `task25` already exists, switch to it and confirm it is based on the latest `task24`.

2. Confirm the starting state.

```bash
git status --short
python -m pytest tests/test_demo_api.py tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run test -- --run
```

3. Update frontend tests first.

- Change the default prompt expectation to Chinese.
- Change button and heading queries to Chinese visible labels.
- Keep stable `data-testid` assertions for status, run ID, action count, confirm, decline, and refresh.
- Update mock plan fixture values to Chinese names and addresses.

4. Run frontend tests and confirm they fail on the old English implementation.

```bash
npm --prefix frontend run test -- --run
```

Expected: failures reference missing Chinese copy.

5. Update Playwright E2E selectors.

- Replace English role/text selectors with Chinese equivalents.
- Keep status and action count checks by test ID.
- Keep forbidden visible text hygiene checks unchanged.

6. Update the React UI.

- Translate visible UI shell:
  - app title and eyebrow
  - request label and validation text
  - start/reset/refresh/confirm/decline buttons
  - metadata labels
  - plan tabs fallback label
  - selected plan, timeline, route, feasibility, proposed actions
  - confirmation and result panels
  - empty states and unavailable/fallback strings
- Keep `data-testid` attributes unchanged.
- If Chinese text causes mobile overflow, shorten copy first; adjust CSS only if needed.

7. Update Mock World fixture content.

- Keep all IDs stable.
- Replace display values with Chinese examples around Shanghai/Xuhui:
  - `Shanghai` -> `上海`
  - `Xuhui` -> `徐汇`
  - POI names such as family science museum, playground, city walk, light bistro, family kitchen, noodle house, drink stand.
  - Addresses should look like realistic Chinese local addresses.
  - Tags can stay internal English unless they are displayed directly. If displayed, either translate tags in fixture or map them in the UI.
  - Route summaries, weather advisory, table notes, and menu item names should be Chinese.

8. Update deterministic itinerary generation.

- Translate visible generated strings:
  - summary sentence
  - timeline item titles
  - timeline notes
  - proposed action reasons
  - user-facing failure messages if surfaced in demo responses
- Keep internal reason codes stable where they are used as codes.

9. Update deterministic feedback writing.

- Translate `_HEADLINES`, `_NEXT_STEPS`, `_message`, and `_action_message`.
- Keep `tool_name`, `target_id`, `status`, and `action_ref` unchanged.
- If tool names appear in final user messages, map them to display labels such as `订票`, `订座`, `排队取号`, `点单`, `发送消息`.

10. Update backend tests that assert visible English.

- Prefer checking Chinese user-facing strings from generated plans and feedback.
- Keep tests for internal tool names/statuses unchanged.
- Do not update AMAP mapper tests unless they directly fail because of shared demo expectations.

11. Update docs.

- In `README.md` and `docs/WEB_DEMO_README.md`, replace the default demo prompt with Chinese.
- Keep command examples unchanged.
- Mention that the MVP demo uses Chinese Mock World content for competition review.

12. Run focused backend and frontend checks.

```bash
python -m pytest tests/test_itinerary_generation.py tests/test_feedback_writer.py tests/test_demo_api.py -v
npm --prefix frontend run test -- --run
```

13. Run full verification.

```bash
python -m pytest -q
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run e2e
git diff --check
git status --short
```

14. Inspect Git status before staging.

- Confirm `var/` is not staged.
- Confirm no `.env`, secrets, Playwright artifacts, `node_modules`, or `frontend/dist` files are staged.

15. Commit and push.

```bash
git add backend/app/providers/mock_world/fixtures/family_afternoon.json backend/app/planning/itinerary_generation.py backend/app/feedback/writer.py frontend/src/App.tsx frontend/src/App.test.tsx frontend/e2e/demo.spec.ts README.md docs/WEB_DEMO_README.md
git add tests
git commit -m "feat: localize demo content for chinese review"
git push origin task25
```

Adjust `git add` paths to include only files actually changed.

## 6. Testing Plan

- Backend unit and integration tests:
  - itinerary generation returns Chinese visible plan content.
  - feedback writer returns Chinese visible feedback content.
  - demo API preserves confirmation boundary and response hygiene.
- Frontend unit tests:
  - default prompt and main controls render in Chinese.
  - plan details, confirmation, decline, and error surfaces still work.
- E2E tests:
  - start planning from Chinese default prompt.
  - confirm selected plan and verify Chinese feedback is visible.
  - decline path hides confirmation.
  - refresh keeps the same run.
  - mobile smoke has no horizontal overflow.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest -q
npm --prefix frontend run test -- --run
npm --prefix frontend run build
docker compose up -d postgres redis
python -m alembic upgrade head
npm --prefix frontend run e2e
git diff --check
git status --short
```

If Playwright cannot launch Chromium because of environment permissions, rerun the same command with permissions that allow browser startup and document the result.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: localize demo content for chinese review
```

Expected commands:

```bash
git status --short
git add <changed task files only>
git commit -m "feat: localize demo content for chinese review"
git push origin task25
```

The implementer must confirm `.env`, API keys, tokens, secrets, `var/`, Playwright artifacts, `node_modules`, and `frontend/dist` are not staged.

## 9. Out-of-scope Changes

- Do not add i18n infrastructure.
- Do not change API field names or status values.
- Do not rename internal IDs, tool names, provider names, or schema versions.
- Do not add migrations.
- Do not add real provider support.
- Do not alter workflow routing or recovery behavior.
- Do not redesign the UI layout beyond copy fit fixes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The Web demo reads as a Chinese local-life planning demo.
- [ ] Internal contracts remain stable.
- [ ] Mock World data persisted through JSONB is Chinese where user-visible.
- [ ] Confirmation boundary and action ledger safety still hold.
- [ ] Response hygiene checks still protect internal and sensitive keys.
- [ ] Frontend mobile layout has no horizontal overflow.
- [ ] Required backend, frontend, build, and E2E checks passed.
- [ ] Generated artifacts and secrets were not committed.

## 11. Handoff Notes

The implementer should report back:

- Changed files
- Chinese copy choices that may need product review
- Verification commands and results
- E2E permission notes, if any
- Commit hash
- Push result
- Remaining English strings that are intentionally internal
