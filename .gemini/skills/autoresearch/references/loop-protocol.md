# Elite Loop Protocol — Full Gentle AI SDD

Every iteration of the Elite Autoresearch loop follows these strict prompts and stages.

## Stage 1: Planning (SDD)

### 1.1 Exploration Prompt
> "Read `openspec/changes/{SDD}/tasks.md`. Identify the first pending task. Explore the current implementation of {Scope}. Compare Approaches: [Surgical, Refactor, Pattern-based]. Return Approach, Pros, Cons, and Recommendation."

### 1.2 Proposal Prompt
> "Write `proposal.md` for the chosen approach. Define Intent, Scope, and specific Success Criteria (Measurable). Anchor this iteration to Task {N}."

### 1.3 Spec & Design Prompt
> "Update/Read `spec.md` and `design.md`. Ensure the implementation path follows the project's Error Handling and DI patterns."

---

## Stage 2: Implementation (TDD)

### 2.1 RED Prompt
> "Create a new test file `tests/governance/test_iter_{N}.py` or add to existing. Implement a test case that describes the desired behavior of Task {N}. Run `Verify`. Confirm it FAILs."

### 2.2 GREEN Prompt
> "Modify code in {Scope}. Implement the minimal logic to satisfy the new test case. Run `Verify`. Confirm it PASSES."

---

## Stage 3: Verification (Guard)

### 3.1 Guard Prompt
> "Run `Guard`. Verify zero ruff/mypy errors. Execute `benchmarks/RIGOROUS_AUDIT.sh` to ensure no constitutional rules (e.g., direct subprocess) were violated."

---

## Stage 4: Audit (Judgment Day)

### 4.1 Judgment Launch
> "Launch Judge A and Judge B in parallel. Target: current diff. Criteria: Correctness, Edge Cases, Error Handling, Security (Constitucion AI). No approvals allowed—only findings."

### 4.2 Synthesis Rule
> "If [Confirmed CRITICAL] or [Confirmed WARNING (real)] → REWORK (max 2 tries) or REVERT. If [Theoretical] or [Suggestion] → KEEP with annotation."

---

## Stage 5: Archive (Engram)

### 5.1 Engram Sync
> "Call `mem_save`. Content: **What** done, **Why** (Task {N}), **Where** (Files), **Learned** (Findings/Judgments). Topic: `sdd/{SDD}/state`."
