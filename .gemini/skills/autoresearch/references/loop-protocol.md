# Elite Loop Protocol — Gentle AI SDD Integration

This protocol mandates the full SDD lifecycle for every single iteration of the autonomous loop.

## The Iteration Lifecycle

### Phase 1: Planning (The SDD Anchor)
Before proposing any code change, the agent MUST:
1. **Explore**: Read `openspec/changes/{SDD}/tasks.md` to identify the current frontier.
2. **Propose**: Formulate a hypothesis that explicitly maps to a pending task.
3. **Spec/Design**: Verify the hypothesis against the active `spec.md` and `design.md`.

### Phase 2: Implementation (The TDD Gauntlet)
1. **RED**: Add a test case to `tests/governance/` or a relevant domain test file.
2. **Verify Failure**: Run the `Verify` command. It MUST fail. This proves the test is valid and the gap exists.
3. **GREEN**: Apply the minimal surgical code change.
4. **Verify Success**: Run `Verify` again. It MUST pass and improve the metric.

### Phase 3: Constitutional Guard (The Auditor)
Run the `Guard` command (e.g., `benchmarks/RIGOROUS_AUDIT.sh`).
This command MUST verify:
- **Linting**: No ruff/mypy errors.
- **Rules**: No forbidden patterns (subprocess, direct file writes in core, etc.) using Audit Hooks.

### Phase 4: Review (Judgment Day)
Before the `KEEP` decision, the agent MUST initiate a **Judgment Day** review:
1. Launch Judge A and Judge B (blind, parallel).
2. Synthesize findings.
3. **Rule**: If a confirmed CRITICAL or real WARNING exists, the iteration is considered a failure. **REWORK** or **REVERT** immediately.

### Phase 5: Finalisation (The Engram Sync)
1. **Commit**: Save the state to git with the iteration number and SDD reference.
2. **Engram**: Call `mem_save` with:
   - **What**: Iteration result.
   - **Why**: Task mapping.
   - **Evidence**: Test output and Judgment Day verdict.
3. **Archive**: Mark the task as completed in the SDD folder.
