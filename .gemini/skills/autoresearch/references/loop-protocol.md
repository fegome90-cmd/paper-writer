# Loop Protocol — Gentle AI Edition

This document details the phase-by-phase execution of the Governed Autoresearch loop.

## Phase 1: Review (Memory-First)
- **Tool Call**: `mem_context` (mandatory).
- **Tool Call**: `mem_search(query: "lessons learned")`.
- **Read**: `autoresearch-results.tsv`.
- **Read**: `openspec/changes/{SDD}/tasks.md`.
- **Goal**: Identify what worked before and what task is next in the Spec.

## Phase 2: Ideate (Spec-Anchored)
- **Constraint**: Hypothesis MUST map to a pending task in the SDD.
- **Constraint**: Hypothesis MUST be a single, testable sentence.

## Phase 2.5: Red (TDD)
- **Action**: Add a new test case to `tests/` or modify the `Verify` command to require new functionality.
- **Verification**: Run `Verify`. It MUST FAIL (exit non-zero or lower metric).
- **Commit**: `git commit -m "autoresearch RED: [SDD:{SDD}] test for <task>"` (Optional but recommended).

## Phase 3: Modify (Surgical)
- **Rule**: Minimum code change required to make the test pass.
- **Rule**: Follow `AGENTS.md` (no `subprocess`, use `ToolWrapper`).

## Phase 4: Commit (Evidence)
- **Command**: `git add -A && git commit -m "autoresearch iter N: [SDD:{SDD}] <description>"`
- **Why**: Ensures a clean state before validation.

## Phase 5: Verify + Guard (The Gauntlet)
- **Verify**: Run the metric measurement.
- **Guard**: Run `ruff check`, `mypy`, and project invariants.
- **Constitutional Guard**: Check for forbidden patterns (e.g. direct shell execution).

## Phase 6: Decide (Fail-Closed)
- **Keep**: If Verify improved AND Guard is Green.
- **Rework**: If Verify improved but Guard is Red (max 2 tries).
- **Revert**: If Verify regressed or crashed.

## Phase 7: Log (Persistence)
- **Local**: Update `autoresearch-results.tsv`.
- **Engram**: Call `mem_save` for the iteration result.
- **Topic Key**: `sdd/{SDD}/autoresearch`
- **Summary**: Every 5 iterations, call `mem_session_summary`.
