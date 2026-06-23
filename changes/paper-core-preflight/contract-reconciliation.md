# Contract Reconciliation Table

**Date:** 2026-06-19
**Status:** Pre-apply reconciliation — identifies all inconsistencies between proposal, spec, design, and tasks.
**Supersedes:** First reconciliation pass (2026-06-19). This document reflects the reconciled v2 state.

---

## 1. State Model Reconciliation

| Aspect | Proposal | Spec | Design | Tasks | **RECONCILED** |
|--------|----------|------|--------|-------|----------------|
| Status values | `green \| yellow \| red` | `ready \| needs_input \| blocked \| stale` | `ready \| needs_input \| blocked \| stale` | `green \| yellow \| red` | **`ready \| needs_input \| blocked`** |
| `stale` | — | Reserved for v2 | Reserved for v2 | — | **Reserved for v2** |
| Exit: ready | 0 | 0 | 0 | 0 | **0** |
| Exit: needs_input | — | 2 | 2 | — | **2** |
| Exit: blocked | — | 1 | 1 | — | **1** |
| Exit: yellow/degraded | 0 | — | — | 0 | **0** (covered by `ready`) |
| Exit: red | 2 | — | — | 2 | **covered by `blocked`** |

**Decision:** Adopt `ready | needs_input | blocked` exclusively. Drop `green/yellow/red` and `stale`.

---

## 2. PreflightResult Contract Reconciliation

| Field | Proposal | Spec | Design | Tasks | **RECONCILED v1** |
|-------|----------|------|--------|-------|-------------------|
| `status` / `preflight_state` | `status` | `preflight_state` | `status` | `status` | **`status`** (unified name) |
| `current_stage` | ✅ | ✅ | ✅ | ✅ | **✅ keep** |
| `next_action` / `next_recommended` | `next_action` | `next_recommended` | `next_recommended` | `next_action` | **`next_action`** (clearer) |
| `blockers` | `list[PreflightBlocker]` | `list[str]` | `list[str]` | `list[PreflightBlocker]` | **`list[PreflightBlocker]`** (structured, scope-aware) |
| `gates` / `current_gates` | `dict[str, GateStatus]` | `dict[str, bool]` | `dict[str, bool]` | `dict[str, GateStatus]` | **`dict[str, bool]`** (simpler for v1) |
| `capabilities` / `available_commands` | `capabilities: list[str]` | `available_commands: list[str]` | `available_commands: list[str]` | `capabilities: list[str]` | **`available_commands: list[str]`** |
| `blocked_commands` | — | ✅ | ✅ | — | **✅ add** |
| `state_snapshot` | ✅ | — | — | ✅ | **❌ drop v1** (redundant with fields) |
| `review_config` | ✅ | — | — | ✅ | **❌ drop v1** (redundant with review_mode) |
| `last_run` | ✅ | — | — | ✅ | **❌ drop v1** (read-only, no persistence) |
| `operation` | — | ✅ | ✅ | — | **✅ add** (derived from command) |
| `review_mode` | — | ✅ | ✅ | — | **✅ add** (from review_config.yaml) |
| `release_profile` | — | ✅ | ✅ | — | **❌ drop v1** (no implementable source) |
| `execution_mode` | — | ✅ | ✅ | — | **❌ drop v1** (no implementable source) |
| `evidence_access` | — | ✅ | ✅ | — | **❌ drop v1** (no implementable source) |
| `target` | — | ✅ | ✅ | — | **❌ drop v1** (derived, not resolvable) |
| `can_proceed` | — | ✅ | ✅ | — | **✅ add** (see §2.1 for reconciled definition) |
| `warnings` | — | ✅ | ✅ | — | **✅ add** |
| `command` | — | ✅ | ✅ | — | **✅ add** (echo of input) |
| `project_root` | — | ✅ | ✅ | — | **❌ drop v1** (input, not output) |

### 2.1 `can_proceed` Definition (Reconciled v5)

**Supersedes** previous definitions.

`can_proceed` is NOT derived from blockers. It evaluates **workflow preconditions only** using a single eligibility function:

```python
def _is_policy_eligible(
    spec: CommandSpec,
    current_stage: str,
    current_gates: dict[str, bool],
    *,
    state_missing: bool,
    state_invalid: bool,
) -> bool:
    """Unified eligibility check for can_proceed, available_commands, blocked_commands, next_action."""
    if state_invalid:
        return spec.state_policy == "standalone_allowed"

    if state_missing:
        return spec.state_policy in {"standalone_allowed", "pipeline_initializer"}

    if spec.state_policy in {"standalone_allowed", "pipeline_initializer"}:
        return True

    return (
        _stage_index(current_stage) >= _stage_index(spec.minimum_stage)
        and all(current_gates.get(gate, False) for gate in spec.required_gates)
    )
```

Then:

```python
if command is None:
    can_proceed = False
else:
    spec = COMMAND_REGISTRY.get(command)
    if spec is None:
        can_proceed = False
    else:
        can_proceed = _is_policy_eligible(
            spec, current_stage, current_gates,
            state_missing=state_missing, state_invalid=state_invalid,
        )
```

**Key invariant:** `can_proceed: true` IMPLIES `status: "ready"`. There is no valid combination of `can_proceed: true` + `status: "blocked"` or `can_proceed: true` + `status: "needs_input"`.

**Scope of preflight validation (v1):**
- Existence and validity of `state.yaml` (when applicable)
- Current stage
- Gate values
- `state_policy` (standalone vs pipeline-governed)

**NOT validated by preflight (v1):**
- Command-specific arguments (`section_name`, `manuscript_path`, query, etc.)
- Runtime tool availability (Pandoc, Zotero, etc.)
- Network connectivity
- The real parser is responsible for validating command-specific arguments.

### Reconciled PreflightResult v1

```python
@dataclass(frozen=True)
class BlockedCommand:
    """A command that is not eligible at the current pipeline state."""
    command: str
    reason: str
    required_stage: str | None = None
    missing_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreflightResult:
    schema_version: str                   # "1.0"
    status: str                          # ready | needs_input | blocked
    operation: str                       # create | audit | revise | unknown
    review_mode: str                     # rapid | academic
    current_stage: str                   # bootstrap..rendered
    current_gates: dict[str, bool]       # all gates with bool values
    available_commands: list[str]        # commands executable at current state
    blocked_commands: list[BlockedCommand]  # typed blocked command entries
    next_action: str | None              # recommended next command
    blockers: list[PreflightBlocker]     # structured blockers (scope-aware)
    warnings: list[str]                  # non-blocking observations
    can_proceed: bool                    # whether command can execute NOW (policy-eligible)
    command: str | None                  # echo of input command
    readiness_scope: str                 # "workflow_preconditions_only" in v1
    command: str | None                  # echo of input command (if any)
```

### Reconciled PreflightBlocker

```python
@dataclass(frozen=True)
class PreflightBlocker:
    code: str          # e.g. "state_missing", "gate_not_passed"
    scope: str         # "pipeline" | "command"
    message: str       # human-readable
    resolution: str    # what to do
```

---

## 3. Task 6 (Preflight Persistence) Reconciliation

| Document | Position |
|----------|----------|
| Proposal | "no persistent state was created" |
| Spec | "run.yaml integration is deferred to a future version (v2+)" |
| Design | "No state files created or modified" |
| Tasks | Task 6: write preflight metadata to run.yaml |

**Decision:** **Remove Task 6 from v1.** Preflight v1 is completely read-only. Persistence is a v2 concern.

---

## 4. CommandSpec / Registry Reconciliation

| Document | Position |
|----------|----------|
| Proposal | Uses PIPELINE_MAP directly |
| Design | `resolve_preflight` imports `PIPELINE_MAP` from `cli/paper/dispatch.py` |
| Core-boundary | "CLI is external to core" |
| Spec | Expects preflight to know ALL commands (27+) |

**Problem:** Core service importing from CLI layer violates hexagonal architecture. PIPELINE_MAP only covers orchestrated commands, not Phase 0.

**Decision:** Create `harness/domain/command_spec.py` with `COMMAND_REGISTRY` — a core-layer registry of all commands with their requirements. In v1, only Preflight consumes it. CLI (Dispatch) and Orchestrator continue using PIPELINE_MAP and internal logic; full migration is a v2 concern. Core never imports CLI.

**v1 scope:** `COMMAND_REGISTRY` is a **transitory mirror** of existing metadata. Dispatch remains authoritative. Parity tests compare `COMMAND_REGISTRY` keys against `PIPELINE_MAP` keys and fail on divergence. Full migration (PIPELINE_MAP generated from COMMAND_REGISTRY, Orchestrator queries registry) is a v2 concern.

### CommandSpec Identity Model (Reconciled v3)

`CommandSpec` has three identity fields:
- `id`: canonical identifier (e.g., `draft:outline`) — used for cross-referencing
- `dispatch_key`: matches `PIPELINE_MAP` key exactly (e.g., `draft:outline`), `None` for Phase 0 — used by parity test
- `cli_path`: tuple of CLI tokens (e.g., `("draft", "outline")`) — used for documentation and future CLI generation

### CommandSpec Classification (Reconciled v3)

- `handler_kind`: how invoked (`orchestrated` | `callback_direct`)
- `owner_kind`: who implements (`core` | `integration` | `local_subproject`)

These are orthogonal concerns. A command can be `callback_direct` + `core` (doctor), `callback_direct` + `integration` (trace), or `callback_direct` + `local_subproject` (thesaurus:import).

### CommandSpec Pipeline Progression (Reconciled v4)

For `next_action` computation, the registry includes:
- `advances_pipeline`: does this command move the pipeline forward?
- `produced_gates`: gates this command can set to True (tuple, may have multiple) — descriptive, NOT used for recommendation
- `next_stage`: which stage does the pipeline transition to?
- `workflow_rank`: ordering for next_action (lower = higher priority)
- `recommended_when_gates_missing`: recommend this command when these gates are missing — **used for filtering**

**Key distinction:** `produced_gates` describes what a command CAN set to True. `recommended_when_gates_missing` determines WHEN to recommend the command. The resolver uses `recommended_when_gates_missing` for filtering, NOT `produced_gates`.

**Example:** `import:bib` produces `("bib_imported", "bib_normalized")` but is recommended only when `("bib_imported",)` is missing. If only `bib_normalized` is missing, `lint:bib` should be recommended instead (it needs `bib_imported` to exist).

```python
# Correct next_action algorithm
if command is not None:
    next_action = None
elif state_invalid:
    next_action = None
elif state_missing:
    next_action = "init"
else:
    candidates = [
        spec for spec in COMMAND_REGISTRY.values()
        if spec.workflow_rank is not None
        and _is_policy_eligible(spec, current_stage, current_gates, state_missing=False, state_invalid=False)
        and any(
            not current_gates.get(gate, False)
            for gate in spec.recommended_when_gates_missing
        )
    ]
    candidates.sort(key=lambda s: s.workflow_rank)
    next_action = candidates[0].id if candidates else None
```

### CommandSpec Immutability (Reconciled v3)

- `required_gates: tuple[str, ...] = ()` — tuples, not lists
- `requires_args: tuple[str, ...] = ()` — tuples, not lists
- `cli_path: tuple[str, ...]` — tuples, not lists
- Standalone commands have `required_gates=()` — empty tuple, not empty list

---

## 5. Capability Resolution Reconciliation

| Concept | Definition | Source |
|---------|-----------|--------|
| **CapabilityCatalog** | What Paper Writer knows how to do | Static YAML (documentation) |
| **CommandRegistry** | What commands exist and what they require | `harness/domain/command_spec.py` |
| **CapabilityResolver** | What's available in this environment | Runtime checks (tools, providers, env vars) |

**Decision:** For v1, CommandRegistry is sufficient. CapabilityCatalog stays as documentation. CapabilityResolver is v2+.

---

## 6. External Audit Without state.yaml

| Document | Position |
|----------|----------|
| Spec | "missing state.yaml + command != init → needs_input" |
| Proposal | "simmetry between create/audit/review" |

**Problem:** Can't audit an external DOCX without Paper Writer state.

**Decision:** For v1, external audit requires `paper init` first. This is a documented limitation. v2 can add `--input PATH` flag for stateless audit mode.

**Exception — standalone commands:** Commands with `state_policy="standalone_allowed"` do NOT require `state.yaml`. They are eligible regardless of pipeline state. The `state_missing` blocker only applies to `pipeline_governed` commands.

---

## 7. Automatic Mode & Fail-Closed

| Document | Position |
|----------|----------|
| Spec | "automatic prefers continue_on_error over stop_on_error" |
| Core principle | fail-closed is non-negotiable |

**Decision:** `execution_mode` does NOT change failure policy. `stop_on_error` is always the safe default. `automatic` only controls interaction: no human prompts, return `needs_input` when human decision required.

---

## 8. `ready` Semantics

| Document | Position |
|----------|----------|
| Spec | "ready if can_proceed is False but blockers are empty" |

**Problem:** `ready` + `can_proceed: false` is contradictory for agents.

**Decision:**
- General preflight: `ready` means pipeline is in a valid state, shows next_action. `can_proceed` is `False` (no command requested).
- Command-specific preflight: `ready` implies `can_proceed: true`
- `needs_input` when human decision required
- `blocked` when command cannot execute

---

## 9. Status Precedence (Reconciled v4)

**Supersedes** previous v3 precedence rules.

```python
spec = COMMAND_REGISTRY.get(command) if command else None

if command is not None and spec is None:
    # Unknown command
    status = "blocked"
elif state_missing:
    if command is None or spec.state_policy == "pipeline_governed":
        status = "needs_input"
    else:
        # Standalone or pipeline_initializer: ignore missing state, report as warning
        status = "ready"
elif state_invalid:
    if command is not None and spec.state_policy == "standalone_allowed":
        # Standalone command: ignore invalid state, report as warning
        status = "ready"
    else:
        # pipeline_initializer or pipeline_governed: corrupt state blocks
        status = "blocked"
elif command is not None and not workflow_eligible:
    status = "blocked"
else:
    status = "ready"
```

**Precedence order:**
1. `command is not None` and `spec is None` → `blocked` (unknown command)
2. `state_missing` + `(command is None or pipeline_governed)` → `needs_input` (human must run `paper init`)
3. `state_missing` + `(standalone or pipeline_initializer)` → `ready` + warning (no state required)
4. `state_invalid` + `standalone` → `ready` + warning (standalone exempt from corrupt state)
5. `state_invalid` + `pipeline_initializer` → `blocked` (corrupt state blocks init)
6. `state_invalid` → `blocked` (corrupted state, cannot proceed)
7. Command not workflow-eligible → `blocked` (stage or gates not met)
8. Otherwise → `ready`

**Standalone commands are exempt from corrupt state (#4):** They can execute regardless of state.yaml validity.
**pipeline_initializer commands are NOT exempt from corrupt state (#5):** If state.yaml exists and is corrupt, init is blocked. The init command creates state.yaml; if one already exists and is corrupt, the human must fix it first.

---

## 10. Resolvable Fields for v1

| Field | Source | Resolvable? | v1? |
|-------|--------|-------------|-----|
| `project_root` | CLI flag / auto-detect | ✅ | ✅ (input) |
| `command` | CLI flag (optional) | ✅ | ✅ (input) |
| `operation` | Derived from command | ✅ | ✅ |
| `review_mode` | `review_config.yaml["mode"]` | ✅ | ✅ |
| `current_stage` | `state.yaml["stage"]` | ✅ | ✅ |
| `current_gates` | `state.yaml["gates"]` | ✅ | ✅ |
| `available_commands` | CommandRegistry + stage + gates | ✅ | ✅ |
| `blocked_commands` | CommandRegistry + stage + gates | ✅ | ✅ |
| `next_action` | Stage progression logic | ✅ | ✅ |
| `blockers` | State consistency checks | ✅ | ✅ |
| `warnings` | Config analysis | ✅ | ✅ |
| `can_proceed` | Workflow preconditions (stage, gates, state_policy) | ✅ | ✅ |
| `release_profile` | Not in review_config.yaml | ❌ | ❌ v2 |
| `execution_mode` | Not in context | ❌ | ❌ v2 |
| `evidence_access` | Not determinable statically | ❌ | ❌ v2 |
| `target` | Derived but complex | ❌ | ❌ v2 |
| `state_snapshot` | Redundant | ❌ | ❌ v2 |
| `review_config` | Redundant with review_mode | ❌ | ❌ v2 |
| `last_run` | Requires persistence | ❌ | ❌ v2 |

---

## 11. Document Fixes Required

| Document | Fix | Status |
|----------|-----|--------|
| proposal.md | Update PreflightResult contract, drop green/yellow/red, add state_policy, CommandRegistry as mirror, 3-identity model, BlockedCommand, tuples | ✅ Done |
| spec.md | Unify state model, reduce fields, fix `ready` semantics, remove automatic mode, add standalone policy, fix argument validation boundary, BlockedCommand, standalone invalid-state, OrchestratorRequest→v2 | ✅ Done |
| design.md | Update PreflightResult dataclass, add CommandSpec with state_policy, fix "pure function" claim, add blocker scoping, 3-identity model, pipeline progression, owner_kind, tuples, BlockedCommand | ✅ Done |
| tasks.md | Remove Task 6, add parity tests, add standalone tests, add can_proceed tests, add Task A2, update Task B1 with new fields | ✅ Done |
| structural-map.md | Fix validator count (23), fix tool wrappers (15), fix schemas (5), separate MCP clients | ✅ Done |
| roadmap-coverage-matrix.md | Replace "complete" with granular states, fix search providers description | ✅ Done |
| contract-reconciliation.md | Update can_proceed definition, mark SSOT as superseded, add standalone policy, add status precedence, add BlockedCommand, add 3-identity model, add pipeline progression, add tuples | ✅ This document |
| command-registry.md | Rewrite with 3-identity model, pipeline progression, owner_kind, BlockedCommand, tuples, empty gates for standalone, zotero:template | ✅ Done |
| preflight.schema.json | Schema design complete (in spec.md), file NOT created yet — Task B4 creates from scratch | ✅ Design done |
| core-boundary-decisions.md | Split core into domain/application/infrastructure, relax absolute rules | 🔲 Pending |
| orphan-and-overlap-report.md | Analyze more relevant overlaps (PIPELINE_MAP vs preconditions, command IDs, provider selection) | 🔲 Pending |
| REPORT.md | Update sections 1, 5, 6, 18 to reflect reconciled contract | 🔲 Pending |
