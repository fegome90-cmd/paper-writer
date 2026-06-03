# Judgment Day Integration — Elite Autoresearch

This document defines how Judgment Day reviews are integrated into the autonomous engineering loop.

## The Mandate
No autonomous change is allowed to stay in the codebase (`KEEP` decision) without passing an adversarial review.

## Workflow

1. **Trigger**: After the implementation (GREEN) phase and before the final commit.
2. **Setup**:
   - Resolve target files.
   - Resolve Project Standards from `.atl/skill-registry.md`.
3. **Execution**:
   - **Judge A**: adversarial reviewer prompt.
   - **Judge B**: independent adversarial reviewer prompt.
4. **Synthesis**:
   - Match findings.
   - **REWORK required** if BOTH judges find a WARNING (real) or ONE judge finds a CRITICAL.
   - **REVERT required** if rework fails after 2 attempts.

## Evidence Layer
Every Judgment Day run MUST be recorded as a `learning` observation in Engram:
- **Title**: Judgment Day Result: Iteration N
- **Topic Key**: `sdd/{SDD}/judgment`
- **Content**: Summary of confirmed findings and adversarial verdicts.
