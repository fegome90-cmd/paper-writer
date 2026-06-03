# Lessons System — Engram Integration

Governed Autoresearch uses Engram as its long-term memory to prevent repeating past failures.

## Proactive Lesson Capture
After every 5 KEPT iterations, the agent MUST summarize the patterns that produced gains.

## Engram Storage
- **Title**: Autoresearch Lessons: {SDD}
- **Topic Key**: `sdd/{SDD}/lessons`
- **Type**: learning
- **Content**:
  - **What**: Summary of successful vs failed hypotheses.
  - **Why**: Mechanistic explanation of the gains.
  - **Anti-pattern**: What failed and why it was reverted.

## Cross-Session Recovery
At the start of a new loop, the agent MUST:
1. Call `mem_search(query: "autoresearch lessons")`.
2. Retrieve previous observations to weight current hypotheses.

This compounding mechanism ensures that the autonomous loop becomes smarter over time, rather than restarting with a blank slate every session.
