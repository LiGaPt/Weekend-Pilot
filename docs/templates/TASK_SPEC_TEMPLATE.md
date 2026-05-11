# Spec: <Task ID> <Task Name>

## 1. Goal

Describe what this task must deliver in one or two paragraphs.

This section should answer:

- What problem does this task solve?
- What user, developer, or benchmark capability does it unlock?
- What should be true after this task is complete?

## 2. Project Context

Explain how this task fits into `docs/PROJECT_BLUEPRINT.md`.

Mention relevant architecture areas, such as:

- Bounded multi-agent workflow
- Deterministic service layer
- Tool Gateway
- PostgreSQL source of truth
- Redis runtime layer
- LangSmith observability
- Action Ledger
- Human-in-the-loop
- Final Review Gate
- LocalLife-Bench

## 3. Requirements

List concrete requirements. Use checkable statements.

- Requirement 1
- Requirement 2
- Requirement 3

## 4. Non-goals

List what this task explicitly must not do.

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.

Add task-specific non-goals here.

## 5. Interfaces and Contracts

Define the interfaces this task introduces or depends on.

Include only the parts needed for this task:

### Inputs

- Input model, API request, CLI argument, fixture, database row, or function call.

### Outputs

- Output model, API response, CLI output, database row, event, or generated file.

### Schemas

If relevant, include Pydantic models, table names, event formats, or JSON examples.

```json
{
  "example": "replace with task-specific schema"
}
```

## 6. Observability

Describe what must be logged, traced, or stored for this task.

Consider:

- LangSmith metadata
- local logs
- PostgreSQL rows
- Redis events
- benchmark artifacts
- error records

If this task should not add observability yet, say so explicitly.

## 7. Failure Handling

Describe expected failure modes and how the system should respond.

Examples:

- invalid input
- missing environment variable
- unavailable database
- Redis unavailable
- LangSmith upload failure
- malformed tool response
- duplicate execution

## 8. Acceptance Criteria

This section is mandatory. Use clear, testable criteria.

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

List commands the implementer must run before committing.

```bash
# Example
pytest
```

If a command is not available yet for an early documentation-only task, state the alternate verification.

## 10. Expected Commit

Use a conventional commit message.

```text
<type>: <message>
```

## 11. Notes for the Implementer

Add any implementation cautions, sequencing requirements, or known constraints.

The implementer should stop and report back if this spec conflicts with existing code or with `docs/PROJECT_BLUEPRINT.md`.

