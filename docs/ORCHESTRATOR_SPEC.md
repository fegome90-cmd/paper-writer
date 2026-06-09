# paper-writer - Orchestrator Specification

Defines the contract for `harness/orchestrator.py`.
This document adopts the existing harness/state-machine authority and extends it with a concrete orchestration model.

## 1. Purpose

The orchestrator is the **application-service layer** of `paper-writer`.
It coordinates state loading, precondition checks, tool/validator execution, gate evaluation, and final state updates.

It does **not** parse CLI arguments, and it does **not** embed tool-specific subprocess logic.

## 2. Design Guides Used

This spec is informed by two existing systems:

### A. `tmux_fork` orchestrator guidance

Source signals used:
- `tests/unit/test_orchestrator_skill_contract.py`
- `src/infrastructure/tmux_orchestrator/__init__.py`
- `src/infrastructure/tmux_orchestrator/resilience_policy.py`

Patterns adopted:
- **Canonical interface first**: one authoritative interface, fallbacks explicitly secondary
- **Boundary clarity**: the orchestrator coordinates; backends/wrappers do the low-level work
- **Resilience policy as configuration**: failure behavior is explicit, not ad hoc
- **Safety-first execution**: never send raw untrusted payloads directly to infrastructure

### B. `gentle-ai` pipeline orchestrator

Source signals used:
- `internal/pipeline/orchestrator.go`
- `internal/pipeline/runner.go`
- `internal/pipeline/result.go`
- `internal/pipeline/stages.go`
- `internal/pipeline/rollback.go`

Patterns adopted:
- **Step-based execution plan**
- **Structured progress events**
- **Explicit failure policy** (`StopOnError` vs `ContinueOnError`)
- **Structured execution result**
- **Rollback as an explicit policy, not a side effect**

## 3. Canonical Interface

The canonical interface for orchestration is the internal Python API:

```text
cli/paper/* -> harness/orchestrator.py
```

That means:
- CLI commands call orchestrator methods
- orchestrator calls `state_manager`, `gates`, validators, and tool wrappers
- external tools are never the orchestrator's public interface

### Fallbacks

Direct tool invocation is fallback/debug only.
The orchestrator remains the single authority for workflow progression.

## 4. Responsibilities

The orchestrator must:
- load the current state from `outputs/state.yaml`
- validate command preconditions
- assemble a command-specific execution plan
- run steps in the correct order
- choose the appropriate failure policy
- collect structured results from wrappers and validators
- update gates and stage transitions
- emit `outputs/manifest.yaml` for final verification

The orchestrator must not:
- parse raw CLI arguments
- call `subprocess` for Pandoc, Vale, or bibliography tools directly
- define editorial rules inline
- parse raw stdout/stderr as business logic
- bypass the gate system

## 5. Internal Collaborators

| Component | Responsibility |
|---|---|
| `harness/state_manager.py` | read, validate, and persist `outputs/state.yaml` |
| `harness/gates.py` | evaluate gate conditions and convert findings to gate verdicts |
| `integrations/tools/*.py` | wrap external CLIs and normalize results |
| `skills/imported/*` and `skills/local/*` via adapters | execute skill-driven search, screening, and drafting actions behind a normalized interface |
| `validators/*.py` | produce structured findings for refs, style, structure, reporting |
| `outputs/manifest.yaml` | final delivery artifact emitted after successful verification |

## 6. Request Contract

Every orchestrator call should be normalized into an internal request object conceptually equivalent to:

```yaml
command: paper verify
requested_stage: rendered
failure_policy: stop_on_error
args:
  format: docx
  section: null
context:
  cwd: /repo/root
  actor: agent
```

Required fields:
- `command`
- `requested_stage`
- `failure_policy`

Optional fields:
- command-specific arguments
- execution context metadata

## 7. Execution Model

Inspired by `gentle-ai`, the orchestrator should execute a **stage plan** made of ordered steps.

### Stage Plan Shape

```yaml
prepare:
  - load_state
  - validate_preconditions
  - validate_dependencies
apply:
  - run_core_action
verify:
  - run_gate_checks
  - persist_state
  - emit_manifest_if_applicable
rollback: []   # optional; enabled only for reversible mutations
```

### Step Rules

Each step should have:
- `id`
- `run()` behavior
- optional rollback behavior if the step mutates artifacts in a reversible way

### Default Stage Families

| Family | Meaning |
|---|---|
| `prepare` | preconditions, dependency checks, state loading |
| `apply` | command execution and artifact mutation |
| `verify` | gate evaluation and structured verdict consolidation |
| `rollback` | optional reversal for partial mutations |

Note: unlike `gentle-ai`, `paper-writer` does not need universal rollback on day one.
Rollback should be enabled only for clearly reversible scaffolding/mutation steps.

### Verify Phase Rollback

When the verify phase fails mid-transaction (e.g. gate persistence fails after some gates have been mutated), the orchestrator rolls back to a pre-verify snapshot:

1. Before the verify `try` block, a `copy.deepcopy` snapshot of `ManuscriptState` is captured.
2. On exception in the verify phase, if the snapshot is not `None`, the orchestrator restores `state_manager.state` to the snapshot and calls `save_state()`.
3. A `rollback_state` step is appended to the result steps (succeeded or failed).
4. If both the original failure and the rollback fail, both errors are recorded in steps and blockers.

This prevents partial gate mutation from corrupting the state on transient failures.

## 8. Failure Policy

The orchestrator must use explicit failure policy, not implicit behavior.

### Policies

#### `stop_on_error`
Use when continuing would create invalid or misleading state.

Apply to:
- `paper init`
- `paper search`
- `paper screen`
- `paper draft outline`
- `paper draft section`
- `paper render`
- `paper verify`

#### `continue_on_error`
Use only when the goal is to collect multiple findings without mutating truth incorrectly.

Apply to:
- `paper lint bib`
- `paper check refs`
- `paper lint style`
- `paper audit reporting`
- aggregate validation passes inside `validating`

This is the key adaptation from `gentle-ai`:
validation is allowed to continue gathering failures, but stage mutation still fails closed.

## 9. Progress Event Contract

The orchestrator should emit structured progress events during execution.

Conceptual event shape:

```yaml
step_id: run_refs_validator
stage: validating
status: running   # pending | running | succeeded | failed | skipped | rolled_back
message: Validating bibliography metadata
error: null
```

Progress events are useful for:
- CLI feedback
- logs
- future UI surfaces
- debugging failed workflows

## 10. Result Contract

Every orchestrator command must return a structured result.

Conceptual shape:

```yaml
command: paper verify
success: false
stage_before: rendering
stage_after: rendering
failure_policy: stop_on_error
steps:
  - step_id: load_state
    status: succeeded
  - step_id: verify_render_gate
    status: failed
    error: render_passed is false
blockers:
  - render gate not satisfied
warnings: []
artifacts:
  - outputs/state.yaml
gate_changes:
  style_passed: false
state_changes:
  stage_before: rendering
  stage_after: rendering
exit_code: 1
```

Required result sections:
- `success`
- `stage_before`
- `stage_after`
- `steps`
- `blockers`
- `warnings`
- `artifacts`
- `gate_changes`
- `state_changes`
- `exit_code`

## 11. Command-to-Plan Mapping

### `paper init`
- prepare: ensure repo bootstrap surface exists
- apply: scaffold templates/state
- verify: confirm `repo_initialized: true`

### `paper search`
- prepare: require `repo_initialized`
- apply: run evidence retrieval flow
- verify: confirm search artifacts + `search_completed`

### `paper screen`
- prepare: require `search_completed`
- apply: screen evidence and validate identifiers
- verify: confirm screened artifacts + `screened_evidence`

### `paper draft outline`
- prepare: require `screened_evidence`
- apply: create outline using citation keys
- verify: confirm outline artifact + `outline_drafted`

### `paper draft section <name>`
- prepare: require `outline_drafted`
- apply: draft section
- verify: confirm section artifact; set `sections_completed` only when the required set is complete

### `paper lint bib` / `paper check refs` / `paper lint style` / `paper audit reporting`
- prepare: require `sections_completed`
- apply: run validators/wrappers with `continue_on_error`
- verify: update only the corresponding gates

### `paper render`
- prepare: require all validation gates true
- apply: run Pandoc render
- verify: confirm output artifacts + `render_passed`

### `paper verify`
- prepare: require `render_passed`
- apply: consolidate final gate state
- verify: emit `outputs/manifest.yaml` + set `ready_for_delivery`

## 12. State Mutation Rules

The orchestrator is the only layer allowed to approve stage advancement.

Rules:
- a step may create artifacts without automatically advancing stage
- stage advancement happens only after postconditions pass
- if a draft changes after validation, downstream gates are reset according to the harness spec
- failed commands must not leave the state pretending success

## 13. Safety and Resilience Rules

Borrowing from `tmux_fork`, the orchestrator should treat safety as a first-class concern.

Rules:
- never pass raw unvalidated inputs directly into infrastructure wrappers
- normalize all tool responses before business decisions
- cap log capture and artifact inspection size where appropriate
- keep resilience policy centralized, not scattered in command handlers
- prefer explicit dependency failures over silent degradation

## 14. MVP Implementation Order

1. implement `state_manager.py`
2. implement `gates.py`
3. implement `orchestrator.py` with request/result contracts
4. wire `paper init` and `paper verify`
5. add progress events and structured step results
6. add validation-stage `continue_on_error`
7. add optional rollback only if a real reversible mutation appears

## 15. Audit Checklist

A future audit of the orchestrator should verify:

- [ ] CLI does not embed orchestration logic
- [ ] orchestrator does not shell out directly to Pandoc/Vale/etc.
- [ ] every command has explicit preconditions
- [ ] failure policy is explicit per command
- [ ] step results are structured
- [ ] stage advancement is driven by postconditions, not optimism
- [ ] final delivery depends on `outputs/manifest.yaml` and `ready_for_delivery`
- [ ] verify phase rollback captures snapshot and restores on failure
- [ ] chain command validates parameter bounds before orchestration
- [ ] non-existent CSL/reference-doc files generate error-severity findings

## 16. Bottom Line

The orchestrator is not a fat controller.
It is not a shell script in disguise.
It is the workflow application layer that turns commands into validated stage plans and fail-closed outcomes.
