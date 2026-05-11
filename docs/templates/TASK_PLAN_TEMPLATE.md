# Plan: <Task ID> <Task Name>

## 1. Spec Reference

Spec file:

```text
docs/specs/<task-id>-<task-name>.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

Summarize the current repository state this plan assumes.

Include:

- Current branch
- Relevant existing files
- Relevant previous task outputs
- Any known missing infrastructure

## 3. Files to Add

- `path/to/new_file.py` - purpose
- `path/to/new_file.md` - purpose

Use an empty list if no files are added.

## 4. Files to Modify

- `path/to/existing_file.py` - planned change
- `path/to/existing_file.md` - planned change

Use an empty list if no files are modified.

## 5. Implementation Steps

Write concrete steps that another Codex execution session can follow directly.

1. Step one.
2. Step two.
3. Step three.

Keep the task scoped. Do not include unrelated cleanup or future work.

## 6. Testing Plan

List tests to add or update.

- Unit tests:
  - test name or behavior
- Integration tests:
  - test name or behavior
- Smoke tests:
  - command or scenario

If this is a documentation-only task, specify document review checks instead.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
# Example
pytest
git status --short
```

Prefer focused commands for early tasks and broader commands for integration tasks.

## 8. Commit and Push Plan

Expected commit message:

```text
<type>: <message>
```

Expected commands:

```bash
git status --short
git add <files>
git commit -m "<type>: <message>"
git push
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

List changes the implementer must not make while executing this plan.

- Do not change unrelated modules.
- Do not alter architecture decisions in `docs/PROJECT_BLUEPRINT.md` unless the spec explicitly requires it.
- Do not add new dependencies unless listed in this plan.
- Do not commit generated caches, virtual environments, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- Known limitations or follow-up tasks

