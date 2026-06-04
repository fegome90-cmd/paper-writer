# Judgment Day Integration — Elite Autoresearch

This document mandates the adversarial audit for every autonomous iteration.

## The Mandate
No autonomous change is allowed to be kept (`KEEP`) without passing an independent, parallel adversarial review by two agents.

## Workflow

1. **Setup**: The orchestrator resolves the skill registry and identifies target files.
2. **Execution**: Two judges are launched via `delegate`.
   - **Judge A Prompt**: Focus on logical correctness and edge cases.
   - **Judge B Prompt**: Focus on architectural integrity and Constitutional AI compliance.
3. **Synthesis**:
   - Both judge responses must be read.
   - Findings must be categorized into Confirmed, Suspect, or Contradiction.
4. **Enforcement**:
   - **Confirmed CRITICAL**: Iteration FAILED. Revert.
   - **Confirmed WARNING (real)**: Rework required (max 2 attempts) or Revert.
   - **Theoretical/Suggestion**: Allowed to pass with an observation in Engram.

## Blocking Rule
You MUST NOT update the numeric metric or mark a task as completed until the Judgment Day verdict is `APPROVED`.
