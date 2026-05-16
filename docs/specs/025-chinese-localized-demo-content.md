# Spec: 025 Chinese Localized Demo Content

## 1. Goal

Localize the MVP demo path for a Chinese competition review context.

After this task, the Web demo should read like a China-local local-life product demo to a reviewer: the default request, frontend labels, visible itinerary content, venue names, venue addresses, route summaries, action reasons, and feedback messages should be in Chinese wherever they are user-visible.

## 2. Project Context

Task 024 completed the minimal Web-first MVP demo path and E2E coverage. The current demo works, but most visible content still reads as an English prototype.

Task 025 keeps the same Mock World-only product path and does not change the workflow architecture. It improves demo realism by localizing the content that flows through:

- Mock World fixtures
- deterministic itinerary generation
- deterministic feedback writing
- FastAPI demo responses
- React/Vite Web UI
- frontend unit tests and Playwright E2E tests

## 3. Requirements

- Translate the default Web demo prompt into Chinese while preserving the family afternoon scenario.
- Translate frontend user-visible labels, headings, buttons, helper text, empty states, result panels, and error fallback text into Chinese.
- Translate Mock World user-visible content for the family afternoon profile:
  - city and area display values
  - POI names
  - POI addresses
  - POI descriptions
  - route summaries
  - weather advisory
  - queue/table/ticket notes
  - addon menu item names
  - recipient display labels if shown to the user
- Update deterministic itinerary generation so visible title, summary, timeline titles, timeline notes, feasibility reasons/warnings where displayed, and proposed action reasons are Chinese.
- Update deterministic feedback writing so visible headlines, summary messages, action messages, and next steps are Chinese.
- Keep internal identifiers stable unless a test explicitly proves they are user-visible and safe to change:
  - `poi_id`
  - `case_id`
  - `tool_name`
  - `action_type`
  - `status`
  - `schema_version`
  - provider names
  - database table and column names
- Keep API response field names unchanged.
- Keep the existing confirmation boundary unchanged: action count must remain `0` before confirmation.
- Update unit, integration, and E2E tests so they assert the Chinese demo surface.
- Keep response hygiene checks that prevent raw internal or sensitive keys from appearing in the UI.
- Keep the project runnable without external API keys, LangSmith upload, or real local-life providers.

## 4. Non-goals

- Do not add a new database table or migration for venues.
- Do not translate Python/TypeScript symbols, Pydantic fields, JSON schema keys, status enums, tool names, or database column names.
- Do not add i18n framework support or runtime language switching.
- Do not add real AMap/Baidu provider behavior.
- Do not change workflow topology, recovery routing, agent count, or benchmark scoring.
- Do not redesign the Web UI layout beyond copy changes needed for text fit.
- Do not commit `.env`, API keys, tokens, secrets, `var/`, Playwright artifacts, `node_modules`, or `frontend/dist`.

## 5. Interfaces and Contracts

### Inputs

- The Web demo still starts from `POST /demo/runs`.
- The default frontend input should become a Chinese version of the family scenario, for example:

```text
今天下午想和老婆、5岁的孩子出去玩几个小时，别离家太远。孩子要适合亲子活动，老婆最近想吃清淡一点，帮我安排一下。
```

### Outputs

- `DemoRunSummary` response shape remains unchanged.
- User-visible string values inside response payloads may become Chinese.
- Frontend UI copy becomes Chinese while test IDs remain unchanged.
- Status values such as `awaiting_confirmation`, `completed`, and `declined` may remain raw values unless the implementation adds display-only label mapping.

### Stored Data

There is no dedicated venue table in the current schema. Mock World venue data is stored through JSON payloads in PostgreSQL rows such as:

- `plans.plan_json`
- `tool_events.request_json`
- `tool_events.response_json`
- `action_ledger.request_json`
- `action_ledger.response_json`

Task 025 should ensure user-facing venue content written through those JSON payloads is Chinese.

## 6. Observability

Task 025 should not add new telemetry. Existing LangSmith/local-buffer metadata should continue to work.

Internal observability keys and tool names may remain English because they are developer-facing and used by tests, graders, and trace analysis.

## 7. Failure Handling

- If Chinese strings make frontend controls overflow on mobile, adjust CSS or copy length within the task.
- If tests depend on English visible text, update tests to assert the new Chinese text or stable test IDs.
- If a string is both user-visible and used as a stable internal contract, keep the contract stable and add a display label at the UI or summary layer.
- If live AMAP mapper tests use English sample provider data, leave those tests unchanged unless they affect the Mock World demo path.

## 8. Acceptance Criteria

- [ ] The Web demo default prompt is Chinese.
- [ ] The main Web UI visible shell is Chinese.
- [ ] The generated plan title, summary, timeline, route summary, proposed action reasons, execution feedback, and next steps are Chinese.
- [ ] Mock World family afternoon venue names, addresses, descriptions, route summaries, weather advisory, table notes, and addon menu names are Chinese.
- [ ] Demo API responses still omit forbidden internal or sensitive keys.
- [ ] Confirmation boundary still holds: `action_count` is `0` before confirmation and greater than `0` after confirmation.
- [ ] Existing backend tests pass.
- [ ] Existing frontend unit tests pass.
- [ ] Frontend build passes.
- [ ] Playwright E2E passes with Chinese selectors/copy.
- [ ] No `.env`, API key, token, secret, `var/`, Playwright artifact, `node_modules`, or `frontend/dist` file is committed.
- [ ] The working tree is clean after commit except pre-existing ignored or intentionally untracked local runtime files.

## 9. Verification Commands

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

If Playwright fails with `browserType.launch: spawn EPERM`, rerun the E2E command in an environment that is allowed to launch Chromium.

## 10. Expected Commit

```text
feat: localize demo content for chinese review
```

## 11. Notes for the Implementer

Focus on the reviewer-facing demo path. Keep internal contracts stable and avoid broad i18n infrastructure. This task is meant to make the existing MVP credible for a Chinese review audience, not to create a multilingual product framework.
