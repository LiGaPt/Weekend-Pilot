# Spec: 032 Competition Design Document v0

## 1. Goal

Add a concise, reviewer-facing competition design document for WeekendPilot.

This task closes a required deliverable from `docs/PROJECT_BLUEPRINT.md`: a short design document describing the planning strategy, tool call chain, and exception handling mechanism. The repository already has task specs, implementation plans, a Web demo runbook, benchmark docs, and current code through Task 031, but it does not yet have one standalone design document suitable for competition review.

After this task is complete, a reviewer should be able to read one document to understand what WeekendPilot does, how the MVP demo works, how planning and execution are structured, how tools are called safely, how failures are handled, and how the system is verified.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines WeekendPilot as a benchmark-driven local-life planning and execution system for short weekend activities. The required competition deliverables are:

- A runnable minimal Web UI demo.
- Complete tool implementation code, including Mock API calls.
- A short design document describing planning strategy, tool call chain, and exception handling.

The current repository is complete through Task 031:

- Task 022-025 established the Web demo API, minimal Web UI, E2E coverage, runbook, and Chinese localized demo content.
- Task 026-027 aligned the workflow state/DAG with the V1 target and added bounded recovery routing v0.
- Task 028-030 expanded LocalLife-Bench cases, failure injection, and replay harness.
- Task 031 added optional LLM-backed bounded agents for Discovery, Dining, and Itinerary Planner while keeping deterministic defaults.

Task 032 is documentation-only. It should consolidate the existing architecture into a competition-ready design document without changing runtime behavior.

## 3. Requirements

- Add a standalone design document at:

  ```text
  docs/COMPETITION_DESIGN_DOCUMENT.md
  ```

- Update `README.md` to link to `docs/COMPETITION_DESIGN_DOCUMENT.md` from an appropriate documentation or demo section.
- The design document must be reviewer-facing, not an internal task spec or implementation plan.
- The design document must be grounded in current implemented behavior through Task 031.
- The design document must distinguish implemented behavior from future roadmap items where relevant.
- The design document must include these sections or equivalent headings:
  - Product goal and MVP demo scope.
  - System architecture overview.
  - Planning strategy.
  - Tool call chain.
  - Human confirmation and side-effect safety.
  - Exception handling and recovery.
  - Observability and benchmark verification.
  - Current limitations and next steps.
  - How to run or verify the demo.
- The architecture overview must cover the current major components:
  - FastAPI backend.
  - React/Vite Web demo.
  - LangGraph workflow.
  - PostgreSQL durable state.
  - Redis runtime cache/rate-limit layer.
  - Tool Gateway.
  - Mock World provider.
  - Optional AMAP read provider.
  - Deterministic planning services.
  - Bounded agents.
  - Optional LLM-backed bounded agents from Task 031.
  - Local observability and optional LangSmith summary path.
  - LocalLife-Bench harness, failure injection, and replay.
- The planning strategy section must describe the current product flow:

  ```text
  user input
  -> intent parsing
  -> memory loading
  -> query generation
  -> search execution
  -> candidate blackboard
  -> availability pre-flight checks
  -> logical planning
  -> route/time summary
  -> semantic validation
  -> final review
  -> user presentation
  -> confirmation
  -> deterministic execution
  -> feedback
  ```

- The tool call chain section must explain:
  - All tool calls go through Tool Gateway.
  - Read tools are allowed before confirmation.
  - Write tools are blocked before confirmation.
  - Mock World is the default deterministic provider.
  - AMAP support is optional and read-only.
  - Tool events are recorded.
  - Write actions are recorded through Action Ledger after confirmation.
- The side-effect safety section must explain:
  - Human confirmation boundary.
  - Deterministic execution workflow.
  - Action Ledger.
  - Idempotency keys.
  - No write tools before explicit confirmation.
- The bounded-agent section must explain:
  - Supervisor and Validator/Recovery remain deterministic in Task 031.
  - Discovery, Dining, and Itinerary Planner can optionally use LLM-backed adapters.
  - LLM-backed agents remain behind typed contracts.
  - LLM-backed agents must not call tools or execute side effects.
  - Deterministic fallback remains the default and safe path.
- The exception handling section must explain:
  - Typed workflow and tool failures.
  - Recovery routing v0.
  - Retry/recovery budget concept.
  - Failure injection for benchmark mode.
  - Safe stop behavior.
  - LLM fallback reasons.
  - Observability failure should not break the main workflow.
- The observability and benchmark section must explain:
  - Local JSONL trace buffer.
  - Optional LangSmith summary.
  - Sanitized metadata.
  - LocalLife-Bench case suite.
  - Failure-injection case.
  - Replay harness.
  - Verification commands.
- The run/verify section must link or refer to:
  - `README.md`
  - `docs/WEB_DEMO_README.md`
  - relevant default commands for backend, frontend, benchmark, and focused tests.
- The document must not expose or encourage committing `.env`, API keys, tokens, or secrets.
- The document must not include raw generated trace contents, benchmark reports, action IDs, tool event IDs, authorization headers, or debug traces.
- Keep the document concise enough for review, while complete enough to satisfy the competition design-document deliverable.

## 4. Non-goals

- Do not implement code.
- Do not modify backend runtime behavior.
- Do not modify frontend UI behavior.
- Do not modify Web API contracts.
- Do not modify benchmark fixtures, graders, failure profiles, replay behavior, or reports.
- Do not modify LangGraph topology, workflow node names, recovery routing, confirmation boundary, execution workflow, or Action Ledger behavior.
- Do not add database tables or Alembic migrations.
- Do not add package dependencies.
- Do not add live-provider tests.
- Do not add screenshots, generated benchmark reports, trace files, frontend builds, or Playwright artifacts.
- Do not modify `.env`, `frontend/.env`, `.env.example`, or `frontend/.env.example` unless a documentation mismatch is discovered and explicitly scoped in the implementation plan.
- Do not stage or commit `var/`.
- Do not stage or commit the currently untracked `docs/TASK_WORKFLOW_PROMPTS.md` unless a separate approved task explicitly includes it.
- Do not rewrite `docs/PROJECT_BLUEPRINT.md`, task specs, task plans, or templates as part of this task.
- Do not claim future roadmap features are already implemented.

## 5. Interfaces and Contracts

### Inputs

The implementer must inspect and rely on:

- `docs/PROJECT_BLUEPRINT.md`
- `docs/WEB_DEMO_README.md`
- `README.md`
- `docs/specs/031-llm-backed-bounded-agents-v0.md`
- `docs/plans/031-llm-backed-bounded-agents-v0-plan.md`
- Current workflow, tool gateway, agent, LLM, benchmark, demo API, and frontend code.

Relevant implementation sources include:

- `backend/app/workflow/`
- `backend/app/tool_gateway/`
- `backend/app/agents/`
- `backend/app/llm/`
- `backend/app/benchmark/`
- `backend/app/demo/`
- `backend/app/api/demo.py`
- `frontend/src/App.tsx`
- `frontend/src/api/demo.ts`
- `frontend/src/types/demo.ts`

### Outputs

Add:

```text
docs/COMPETITION_DESIGN_DOCUMENT.md
```

Modify:

```text
README.md
```

The README change should be limited to linking the design document.

### Schemas

The design document should use a stable Markdown outline similar to:

```markdown
# WeekendPilot Competition Design Document

## 1. Product Goal and Demo Scope
## 2. System Architecture
## 3. Planning Strategy
## 4. Tool Call Chain
## 5. Human Confirmation and Execution Safety
## 6. Exception Handling and Recovery
## 7. Observability and Benchmark Verification
## 8. How to Run and Verify
## 9. Current Limitations and Next Steps
```

Small text diagrams are allowed. Mermaid is allowed only if it makes the workflow easier to review and does not overcomplicate the document.

## 6. Observability

This task must not add new telemetry.

The design document must describe the existing observability approach:

- Local JSONL trace buffer.
- Optional LangSmith summary.
- Sanitized workflow, agent, tool, action, benchmark, and LLM metadata.
- LocalLife-Bench reports and replay reports.

The design document must state that observability failures should not fail the main user workflow.

The document must not include raw trace output, generated report bodies, API keys, authorization headers, prompts, raw provider responses, raw usage keys, action IDs, tool event IDs, traceback text, or debug traces.

## 7. Failure Handling

If current code and previous documentation disagree, the design document must reflect current implemented behavior and avoid unsupported claims.

If a required design topic cannot be verified from existing code or docs, the implementer should either:

- describe it as a current limitation or future roadmap item, or
- stop and report the mismatch before writing unsupported documentation.

If verification commands fail due to unrelated infrastructure not being available, the implementer must report the exact command and reason rather than weakening the design document.

## 8. Acceptance Criteria

- [ ] `docs/specs/032-competition-design-document-v0.md` exists and matches this task.
- [ ] `docs/COMPETITION_DESIGN_DOCUMENT.md` exists.
- [ ] `README.md` links to `docs/COMPETITION_DESIGN_DOCUMENT.md`.
- [ ] The design document covers product goal and MVP demo scope.
- [ ] The design document covers system architecture.
- [ ] The design document covers planning strategy.
- [ ] The design document covers Tool Gateway and tool call chain.
- [ ] The design document covers human confirmation and side-effect safety.
- [ ] The design document covers exception handling and recovery.
- [ ] The design document covers observability and benchmark verification.
- [ ] The design document covers optional LLM-backed bounded agents from Task 031.
- [ ] The design document clearly distinguishes implemented behavior from future roadmap items.
- [ ] The document references or points to the Web demo runbook.
- [ ] The document includes practical run or verification guidance without duplicating the full README.
- [ ] No runtime code is changed.
- [ ] No API schemas are changed.
- [ ] No frontend behavior is changed.
- [ ] No benchmark fixtures, graders, failure profiles, or replay behavior are changed.
- [ ] No database migration or dependency change is added.
- [ ] No `.env`, API key, token, secret, `var/`, generated report, trace file, cache, virtual environment, `node_modules`, `frontend/dist`, or Playwright artifact is staged.
- [ ] `docs/TASK_WORKFLOW_PROMPTS.md` is not staged unless explicitly approved in a separate task.
- [ ] `git diff --check` passes.
- [ ] Focused regression checks listed in this spec pass or any environment blocker is reported clearly.
- [ ] The working tree is clean after commit except pre-existing untracked local files intentionally left out.

## 9. Verification Commands

```bash
git diff --check
python -m pytest tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_llm_agents.py -q
git status --short
```

Optional broader checks if the environment is already prepared:

```bash
python -m pytest -q
docker compose config
```

If PostgreSQL or Redis is required for any broader check, start services and apply migrations first:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 10. Expected Commit

```text
docs: add competition design document
```

## 11. Notes for the Implementer

Keep this task documentation-only and narrowly scoped.

The most important design-document deliverable is not another task plan. It should read like a competition handoff: what the system is, how it plans, how tools are chained, why side effects are safe, how failures recover or stop safely, and how the reviewer can verify the demo.

Do not pull in unrelated cleanup. The currently untracked `docs/TASK_WORKFLOW_PROMPTS.md` is a workflow helper document and should stay out of Task 032 unless separately approved. The current `var/` directory contains runtime traces/reports and must not be committed.
