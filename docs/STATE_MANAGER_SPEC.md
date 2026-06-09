# paper-writer - State Manager Specification

Defines the contract for `harness/state_manager.py`.

## Quick path

1. `state_manager.py` owns `outputs/state.yaml` persistence.
2. It validates schema and transitions.
3. It does not decide business policy independently from the harness authority.

## Source of Truth

Primary state file:
- `outputs/state.yaml`

Authoritative schema is defined by:
- `docs/HARNESS_AND_STATE_MACHINE.md`

## Canonical State Shape

```yaml
# Schema version: 1.0
stage: bootstrap
gates:
  repo_initialized: true
  search_completed: false
  screened_evidence: false
  outline_drafted: false
  sections_completed: false
  bib_normalized: false
  citations_resolved: false
  refs_validated: false
  style_passed: false
  reporting_passed: false
  render_passed: false
  ready_for_delivery: false
```

## Required Responsibilities

| Operation | Responsibility |
|---|---|
| `load_state()` | Read and parse `outputs/state.yaml` |
| `validate_state()` | Confirm schema version, stage, and gate keys |
| `save_state()` | Persist normalized state |
| `set_gate()` | Update a single gate deterministically |
| `set_stage()` | Change stage only after valid transition |
| `reset_downstream_gates()` | Clear dependent gates after artifact edits |

## Transition Rules

- Stages advance only through valid postconditions.
- Failed commands must not write a success state.
- Unknown stages or missing gate keys are schema errors.
- State writes are atomic from the caller perspective.

## Error Contract

Conceptual shape:

```yaml
ok: false
error_code: invalid_transition
message: Cannot move from drafting to rendering while sections_completed is false
```

## Rules

- The state manager does not call tools, validators, or skills.
- The state manager does not infer missing gate values optimistically.
- The state manager must preserve untouched gates when mutating one gate.

## Snapshot for Rollback

The orchestrator may capture a `copy.deepcopy` of `state_manager.state` before a transactional phase. On failure, it restores the snapshot via `state_manager.state = snapshot` followed by `save_state()`. This is an external protocol — the state manager itself does not initiate snapshots.

## Audit Checklist

- [ ] Schema matches the authoritative harness doc.
- [ ] Invalid transitions are rejected.
- [ ] Reset behavior is deterministic.
- [ ] State persistence is isolated from orchestration logic.
