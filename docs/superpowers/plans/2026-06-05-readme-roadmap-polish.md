# README Roadmap Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished current-version technical roadmap to `README.md`, improve the README's presentation for judges/readers, keep the Mock World and benchmark descriptions accurate, and prepare the branch for SSH push.

**Architecture:** The README will use a dedicated SVG as the main visual entrypoint, then continue with compact Markdown sections for project status, Mock World, startup, benchmark coverage, and test results. Documentation behavior is protected with focused README contract tests so the visual entrypoint, wording, and evidence summary cannot drift silently.

**Tech Stack:** Markdown, SVG, pytest, Vitest, git over SSH

---

## File Structure

- Modify: `README.md`
  - Promote the README into a cleaner project-homepage style document.
  - Insert the SVG roadmap near the top.
  - Tighten wording and section rhythm without changing product behavior claims.
- Create: `docs/assets/readme-current-version-roadmap.svg`
  - Store the final roadmap SVG as a standalone asset referenced by the README.
- Modify: `tests/test_demo_support_scripts.py`
  - Extend README contract coverage for the SVG roadmap reference and key wording expectations.
- Keep for reference only: `docs/superpowers/specs/2026-06-05-readme-roadmap-polish-design.md`
  - The implementation must follow this approved design.

## Task 1: Lock the README visual contract first

**Files:**
- Modify: `tests/test_demo_support_scripts.py`
- Reference: `README.md`

- [ ] **Step 1: Add one failing README contract for the roadmap asset and top-level visual positioning**

Add assertions that require:

- `README.md` to reference `docs/assets/readme-current-version-roadmap.svg`
- `README.md` to include a short “how to read this roadmap” style explanation near the roadmap
- the README to preserve the existing key sections:
  - `## 项目完成情况`
  - `## Mock World`
  - `## 启动方式`
  - `## Benchmark 覆盖`
  - `## 测试结果`

Suggested assertion shape:

```python
assert "docs/assets/readme-current-version-roadmap.svg" in readme_text
assert "这张图可以按“公开主链" in readme_text
```

- [ ] **Step 2: Run the focused pytest target and verify the new assertions fail for the expected reason**

Run:

```bash
python -m pytest tests/test_demo_support_scripts.py -q
```

Expected:

- `FAIL`
- failure caused by missing roadmap asset reference and/or missing roadmap explanatory copy in `README.md`

- [ ] **Step 3: Commit the red-state checkpoint only if you need a recovery point**

Optional command:

```bash
git add tests/test_demo_support_scripts.py
git commit -m "test: lock readme roadmap contract"
```

Skip this commit if you prefer a single combined docs commit later.

## Task 2: Build the standalone SVG roadmap asset

**Files:**
- Create: `docs/assets/readme-current-version-roadmap.svg`
- Reference: `docs/superpowers/specs/2026-06-05-readme-roadmap-polish-design.md`

- [ ] **Step 1: Create the SVG file with the approved three-layer structure**

The SVG must show:

- top layer: public flow
  - `5173 Public Demo`
  - `Planning Flow`
  - `Human Boundary`
  - `Execution`
- middle layer: system layers
  - `Frontend Layer`
  - `API Layer`
  - `Workflow Layer`
  - `Gateway Layer`
- bottom layer: support/evidence layers
  - `Mock World`
  - `AMap read-only`
  - `Observability`
  - `Benchmark`
  - `Recovery`

Visual requirements:

- warm light background
- green for public flow
- blue for system layers
- gold for data/support layers
- readable Chinese/English mixed labels appropriate for README rendering

- [ ] **Step 2: Sanity-check the SVG file locally by reading it back**

Run:

```bash
Get-Content -Raw -Encoding utf8 docs/assets/readme-current-version-roadmap.svg
```

Expected:

- valid SVG markup
- required labels present
- no accidental placeholder text

- [ ] **Step 3: Commit the SVG asset if you want an isolated visual checkpoint**

Optional command:

```bash
git add docs/assets/readme-current-version-roadmap.svg
git commit -m "docs: add readme roadmap svg"
```

## Task 3: Insert the roadmap and polish README structure

**Files:**
- Modify: `README.md`
- Reference: `docs/assets/readme-current-version-roadmap.svg`
- Reference: `docs/superpowers/specs/2026-06-05-readme-roadmap-polish-design.md`

- [ ] **Step 1: Insert the roadmap near the top of the README**

Place the roadmap after:

- project title
- one-sentence positioning
- a short current-version summary block

Use Markdown image embedding, for example:

```md
![WeekendPilot current version roadmap](docs/assets/readme-current-version-roadmap.svg)
```

- [ ] **Step 2: Add a short roadmap reading guide directly under the image**

The copy should explain that the roadmap is read in three layers:

- public flow
- system layers
- support/evidence layers

Keep it short and judge-friendly.

- [ ] **Step 3: Tighten the README copy without changing approved factual claims**

Refine the surrounding sections so they read like a polished project homepage:

- keep Chinese as the primary language
- shorten overlong paragraphs
- reduce repeated statements between `项目完成情况`, `Mock World`, and `Benchmark 覆盖`
- keep the current benchmark numbers and Mock World caveats intact

- [ ] **Step 4: Ensure the Mock World section still states the robustness behavior explicitly**

Retain the existing factual meaning that Mock World includes:

- extra candidates
- `distractor`
- unavailable candidates
- partial route infeasible combinations

- [ ] **Step 5: Re-read the entire README for top-to-bottom flow**

Verify the reading order is now:

1. positioning
2. roadmap
3. status
4. Mock World
5. startup
6. benchmark
7. tests
8. docs references

- [ ] **Step 6: Commit the README rewrite**

```bash
git add README.md docs/assets/readme-current-version-roadmap.svg tests/test_demo_support_scripts.py
git commit -m "docs: add roadmap and polish readme"
```

## Task 4: Turn the test suite back green

**Files:**
- Modify if needed: `README.md`
- Modify if needed: `tests/test_demo_support_scripts.py`

- [ ] **Step 1: Run the focused pytest suite**

Run:

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
```

Expected:

- all tests pass
- no README contract failures

- [ ] **Step 2: If pytest fails, make the smallest README/test correction and rerun**

Only adjust:

- README wording
- roadmap asset reference
- test expectations that are genuinely inconsistent with the approved design

- [ ] **Step 3: Run the README-referenced frontend tests**

Run:

```bash
npm --prefix frontend test -- --run src/chat/ConversationThread.test.tsx src/App.test.tsx
```

Expected:

- `2` test files pass
- `24` tests pass

## Task 5: Prepare SSH push handoff

**Files:**
- No planned content edits unless a final README/test correction is needed

- [ ] **Step 1: Inspect the final git status carefully**

Run:

```bash
git status --short
```

Expected:

- only intended README / SVG / test changes are staged for this task
- unrelated dirty files remain untouched unless explicitly included by the user

- [ ] **Step 2: Re-run the exact verification commands fresh before any success claim**

Run:

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
npm --prefix frontend test -- --run src/chat/ConversationThread.test.tsx src/App.test.tsx
```

Expected:

- both commands pass exactly as documented

- [ ] **Step 3: Push the current branch to origin over SSH**

Run:

```bash
git push -u origin codex/pre-confirmation-action-list-upgrade-v0
```

Expected:

- push succeeds against `git@github.com:LiGaPt/Weekend-Pilot.git`

- [ ] **Step 4: Report what changed and the exact verification evidence**

Final handoff must include:

- the new roadmap asset path
- the main README sections updated
- the exact commands run
- the exact pass counts observed

