# Plan: 032 Competition Design Document v0

## 1. Spec Reference

Spec file:

```text
docs/specs/032-competition-design-document-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

If the Task 032 spec file is not saved yet, stop and save the approved spec before implementing this plan.

## 2. Current Repository Assumptions

- Current completed branch is `task31`.
- Latest completed commit is `ea6b84e feat: add llm-backed bounded agents v0`.
- Latest completed task files are:
  - `docs/specs/031-llm-backed-bounded-agents-v0.md`
  - `docs/plans/031-llm-backed-bounded-agents-v0-plan.md`
- Task 032 is documentation-only.
- `docs/PROJECT_BLUEPRINT.md` requires a short competition design document covering planning strategy, tool call chain, and exception handling.
- Existing reviewer/demo docs include `README.md` and `docs/WEB_DEMO_README.md`, but there is no standalone `docs/COMPETITION_DESIGN_DOCUMENT.md`.
- Current untracked files include `docs/TASK_WORKFLOW_PROMPTS.md` and `var/`; do not stage them for this task.
- The design document must describe implemented behavior through Task 031 and avoid claiming roadmap items as complete.

## 3. Files to Add

- `docs/COMPETITION_DESIGN_DOCUMENT.md` - reviewer-facing competition design document.

## 4. Files to Modify

- `README.md` - add a concise link to the competition design document.

## 5. Implementation Steps

1. Confirm preconditions.
   - Run:
     ```bash
     git status --short --branch
     git log --oneline -5
     Test-Path docs/specs/032-competition-design-document-v0.md
     Test-Path docs/plans/032-competition-design-document-v0-plan.md
     ```
   - Confirm the Task 032 spec and plan exist before implementation starts.
   - Confirm `docs/TASK_WORKFLOW_PROMPTS.md` and `var/` remain unrelated and untracked.

2. Re-read the source documents and current implementation references.
   - Read:
     - `docs/PROJECT_BLUEPRINT.md`
     - `docs/specs/032-competition-design-document-v0.md`
     - `docs/plans/031-llm-backed-bounded-agents-v0-plan.md`
     - `README.md`
     - `docs/WEB_DEMO_README.md`
   - Inspect current behavior from:
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

3. Create `docs/COMPETITION_DESIGN_DOCUMENT.md`.
   - Use this outline:
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
   - Keep it concise and reviewer-facing.
   - Do not turn it into another task spec or implementation plan.

4. Fill the product goal and demo scope section.
   - Explain that WeekendPilot turns one local-life weekend request into reviewed plans, waits for confirmation, then simulates booking/queue/order/message actions.
   - State the MVP demo is the Chinese family afternoon Mock World path through the Web UI.
   - State the demo is runnable without live local-life APIs, LangSmith credentials, or real map credentials.

5. Fill the system architecture section.
   - Cover:
     - React/Vite Web UI.
     - FastAPI demo API.
     - LangGraph workflow.
     - PostgreSQL durable state.
     - Redis runtime cache/rate-limit layer.
     - Tool Gateway.
     - Mock World provider.
     - Optional AMAP read provider.
     - Deterministic planning services.
     - Bounded agents.
     - Optional LLM-backed Discovery, Dining, and Itinerary Planner.
     - Local JSONL observability and optional LangSmith summary.
     - LocalLife-Bench harness, failure injection, and replay.
   - Clearly mark optional/future pieces where relevant.

6. Fill the planning strategy section.
   - Describe the implemented flow:
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
   - Explain deterministic services own parsing, query generation, route/time, final review rules, execution, and feedback.
   - Explain bounded agents add semantic summaries/planning while staying behind typed contracts.

7. Fill the tool call chain section.
   - Explain all tool calls go through Tool Gateway.
   - List read tools and write tools at a high level.
   - State read tools may run before confirmation.
   - State write tools are blocked until confirmation.
   - Explain tool events are persisted.
   - Explain Mock World is the default deterministic provider and AMAP is optional read-only support.

8. Fill the human confirmation and execution safety section.
   - Explain the workflow pauses at `awaiting_confirmation`.
   - Explain Action Ledger records side-effect actions after confirmation.
   - Explain idempotency keys protect repeated confirmations.
   - Explain agents do not execute write tools.

9. Fill the exception handling and recovery section.
   - Explain typed tool/workflow failures.
   - Explain recovery routing v0 and bounded retry/recovery budget.
   - Explain safe stop behavior.
   - Explain benchmark failure injection for route failures.
   - Explain LLM-backed agents fallback deterministically for missing config, provider errors, bad JSON, schema mismatch, policy mismatch, invalid IDs, or no deterministic drafts.
   - Explain observability failure should not break the main workflow.

10. Fill the observability and benchmark verification section.
    - Explain local JSONL trace buffer and optional LangSmith summary.
    - Explain sanitized metadata for workflow, agents, tools, actions, benchmarks, and LLM usage.
    - Explain LocalLife-Bench has default cases, a failure-injection case, and replay harness.
    - Mention reports and traces under `var/` are runtime artifacts and not committed.

11. Fill the run and verify section.
    - Link to `README.md` and `docs/WEB_DEMO_README.md`.
    - Include compact commands:
      ```bash
      docker compose up -d postgres redis
      python -m alembic upgrade head
      uvicorn backend.app.main:app --reload
      npm --prefix frontend run dev
      ```
    - Include focused verification references:
      ```bash
      python -m pytest tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_llm_agents.py -q
      npm --prefix frontend run build
      ```
    - Do not duplicate the full runbook.

12. Fill current limitations and next steps.
    - Mark as future work:
      - richer recovery intelligence
      - chaos harness
      - richer benchmark levels and metrics
      - real map provider integration beyond current optional AMAP read path
      - richer Web UI visualization
      - long-term memory governance
    - Do not claim these are already implemented.

13. Update `README.md`.
    - Add one short link near the top or near the Web demo section:
      ```markdown
      For the competition architecture and design overview, see `docs/COMPETITION_DESIGN_DOCUMENT.md`.
      ```
    - Keep README changes minimal.
    - Do not rewrite existing setup instructions.

14. Review content hygiene.
    - Search the new document and README diff for forbidden terms where they should not appear as exposed values:
      - real API keys
      - tokens
      - secrets
      - authorization headers
      - raw trace content
      - raw report content
      - action IDs
      - tool event IDs
      - debug traces
    - It is acceptable to mention concepts such as Action Ledger or tool events, but do not include raw IDs or generated artifacts.

15. Run verification.
    - Run the required commands in Section 7.
    - If pytest fails because PostgreSQL/Redis is needed for a broader command, either start services and run migrations or report the environment blocker exactly.
    - Do not weaken the document to hide a verification failure.

16. Stage and commit only intended files.
    - Stage:
      ```bash
      git add docs/specs/032-competition-design-document-v0.md docs/plans/032-competition-design-document-v0-plan.md docs/COMPETITION_DESIGN_DOCUMENT.md README.md
      ```
    - Do not stage:
      - `docs/TASK_WORKFLOW_PROMPTS.md`
      - `var/`
      - `.env`
      - caches
      - `node_modules`
      - `frontend/dist`
      - Playwright artifacts.

## 6. Testing Plan

- Document review checks:
  - The design document covers every required section from the Task 032 spec.
  - The document matches current implemented behavior through Task 031.
  - The document distinguishes implemented behavior from roadmap items.
  - The README links to the new design document.
  - No runtime/API/frontend/benchmark behavior changes are present.
- Focused regression checks:
  - `tests/test_langgraph_workflow.py`
  - `tests/test_benchmark_harness.py`
  - `tests/test_llm_agents.py`
- Smoke checks:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

```bash
git diff --check
python -m pytest tests/test_langgraph_workflow.py tests/test_benchmark_harness.py tests/test_llm_agents.py -q
git status --short
```

Optional broader checks if the environment is already prepared:

```bash
python -m pytest -q
docker compose config
npm --prefix frontend run build
```

If PostgreSQL or Redis is required for broader checks, start services and apply migrations first:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
```

## 8. Commit and Push Plan

Expected commit message:

```text
docs: add competition design document
```

Expected commands:

```bash
git status --short
git add docs/specs/032-competition-design-document-v0.md docs/plans/032-competition-design-document-v0-plan.md docs/COMPETITION_DESIGN_DOCUMENT.md README.md
git diff --cached --check
git commit -m "docs: add competition design document"
git push -u origin task32
```

If the branch is still `task31`, create or switch to `task32` before implementation if that matches the current branch workflow:

```bash
git switch -c task32
```

Only push if the environment and repository permissions allow it. Otherwise report that the commit was created locally and not pushed.

## 9. Out-of-scope Changes

- Do not implement code.
- Do not change backend runtime behavior.
- Do not change frontend UI behavior.
- Do not change Web API contracts.
- Do not change workflow graph topology, node names, routing, confirmation, execution, or Action Ledger behavior.
- Do not change benchmark fixtures, graders, failure profiles, replay behavior, or reports.
- Do not add migrations or dependencies.
- Do not add live-provider tests.
- Do not modify `.env`, `frontend/.env`, `.env.example`, or `frontend/.env.example` unless explicitly approved later.
- Do not rewrite `docs/PROJECT_BLUEPRINT.md`, existing specs, existing plans, or templates.
- Do not stage or commit `docs/TASK_WORKFLOW_PROMPTS.md`.
- Do not stage or commit `var/`, caches, `.venv`, `node_modules`, `frontend/dist`, Playwright artifacts, screenshots, videos, traces, reports, API keys, tokens, or secrets.
- Do not claim future roadmap items are implemented.

## 10. Review Checklist

- [ ] Task 032 spec exists at `docs/specs/032-competition-design-document-v0.md`.
- [ ] Task 032 plan exists at `docs/plans/032-competition-design-document-v0-plan.md`.
- [ ] `docs/COMPETITION_DESIGN_DOCUMENT.md` exists.
- [ ] README links to the design document.
- [ ] Product goal and MVP demo scope are covered.
- [ ] System architecture is covered.
- [ ] Planning strategy is covered.
- [ ] Tool call chain is covered.
- [ ] Human confirmation and side-effect safety are covered.
- [ ] Exception handling and recovery are covered.
- [ ] Observability and benchmark verification are covered.
- [ ] Optional LLM-backed bounded agents from Task 031 are covered accurately.
- [ ] Implemented behavior is separated from future roadmap items.
- [ ] No runtime code was changed.
- [ ] No API, frontend, benchmark, migration, or dependency changes were made.
- [ ] Required verification commands passed or blockers were reported clearly.
- [ ] No `.env`, API key, token, secret, `var/`, cache, build output, or unrelated untracked file was staged.
- [ ] Commit message is `docs: add competition design document`.

## 11. Handoff Notes

Report back with:

- Spec file path.
- Plan file path.
- Design document path.
- README link location.
- Verification commands and results.
- Commit hash.
- Push status.
- Confirmation that no runtime code changed.
- Confirmation that `docs/TASK_WORKFLOW_PROMPTS.md` and `var/` were not staged.
- Any known documentation limitation or recommended follow-up.
