# Proposal: paper-core-preflight

## Full Repository Exploration (2026-06-19)

A comprehensive exploration of the entire Paper Writer repository has been completed, covering 100% of code layers. The exploration produced:

- **capability-ledger.yaml** — 60+ capability entries across all layers
- **structural-map.md** — directory→capability mapping
- **invocation-map.md** — CLI command→internal function mapping
- **data-flow.md** — artifact lifecycle and flow diagrams
- **orphan-and-overlap-report.md** — duplicate authorities and disconnected capabilities
- **core-boundary-decisions.md** — what is core vs integration vs platform
- **roadmap-coverage-matrix.md** — implemented vs planned vs not started
- **REPORT.md** — 18-section comprehensive report

Key findings: 19/36 capabilities production-ready (53%), 9 partial (25%), 8 planned (22%).

## Intent

Paper Writer has a well-defined core workflow — Orchestrator, ManuscriptState, StateManager, gates, `state.yaml` — but lacks a structured way for external agent harnesses (OpenCode, Kilo, Claude Code, Codex) to query system status, understand blockers, and know the recommended next action without free inference.

Agents currently must either parse text output (fragile), re-implement orchestration logic (duplication), or guess at state (unreliable). This creates a coupling gap between the harness layer and the core that no existing contract bridges.

### Evidence from Code

| Finding | File | Lines | Impact |
|---------|------|-------|--------|
| `_serialize_result` omits `gate_changes`, `state_changes`, `failure_policy` from JSON | `cli/paper/output.py` | 147–159 | Agent cannot see which gates passed/failed, state transitions, or error handling mode |
| Phase 0 commands (`audit:*`, `gate:method`) bypass Orchestrator entirely via direct `func(args)` callback | `cli/paper/dispatch.py` | 232–244 | No structured preflight check before execution; no common status format across Phase 0 and Pipeline |
| `OrchestratorRequest` has untyped `args: dict[str, Any]` and `context: dict[str, Any]` escape hatches | `harness/services/orchestrator.py` | 27–36 | No standard place for preflight metadata in the request contract |
| `review_config.yaml` limited to 3 fields (`mode`, `search_window`, `amendments`) | `harness/services/review_config.py` | 18–49 | Config surface doesn't expose execution mode, release profile, or evidence access |
| Run lineage metadata wrapped in `try/except: pass` — best-effort writes | `harness/adapters/filesystem_action_runner.py` | 194–200 | Preflight artifacts can be added to runs without changing semantic meaning |

---

## Scope

### In Scope (Sprint v1)

Two distinct slices, delivered independently:

#### Slice A: OrchestratorResult JSON Completion

- Extend `_serialize_result` in `cli/paper/output.py` to include `gate_changes`, `state_changes`, `failure_policy`
- Backward-compatible — existing consumers ignore unknown keys
- No new modules; modify existing output serialization only

#### Slice B: Preflight Resolver + CLI Command

- **CommandRegistry** — new core-layer module (`harness/domain/command_spec.py`) that mirrors existing command metadata from `PIPELINE_MAP` and Phase 0 registrations. NOT the single source of truth in v1 — parity tests detect divergence. Dispatch remains authoritative.
- **PreflightResolver** — read-only resolver that computes preflight from existing state (`state.yaml`, gates, `CommandRegistry`)
- **PreflightResult contract** — typed dataclass (see contract below)
- **CLI command** — `paper preflight` (human-readable) and `paper --output-format json preflight` (agent-consumable)
- **Exit codes** — `ready` → 0, `needs_input` → 2, `blocked` → 1
- **Tests** — PreflightResolver unit tests + CLI output integration tests

### Out of Scope (Explicitly Deferred)

- OpenCode overlay
- Subagentes
- TUI modifications
- MCP server
- Multi-actor installation
- OpenCode fork
- Massive auditor refactor
- New scientific validators
- Epistemological model changes
- Complete audit workflow migration
- `release_profile`, `execution_mode`, `evidence_access` — no authoritative source in v1
- Run metadata reads (no preflight reads runs — v1)
- Preflight persistence (v1 is completely read-only)
- `CapabilityResolver` for runtime tool availability (v2)

---

## Approach

### 1. OrchestratorResult JSON Completion (Slice A)

Extend `_serialize_result` in `cli/paper/output.py:147-159` to include:

```python
"gate_changes": to_json_value(result.gate_changes),
"state_changes": to_json_value(result.state_changes),
"failure_policy": to_json_value(result.failure_policy),
```

This is backward-compatible — existing consumers ignore unknown keys.

### 2. CommandRegistry (Slice B — Core Layer Mirror)

A structured registry that mirrors existing command metadata. In v1, this is a **transitory mirror**, NOT the single source of truth:

```python
@dataclass(frozen=True)
class CommandSpec:
    """Specification for a single CLI command."""
    # Identity
    id: str                                    # canonical ID, e.g. "draft:outline"
    dispatch_key: str | None                   # PIPELINE_MAP key, e.g. "draft:outline" (None for Phase 0)
    cli_path: tuple[str, ...]                  # CLI invocation, e.g. ("draft", "outline")

    # Classification
    operation: Literal["create", "audit", "revise", "unknown"]
    handler_kind: Literal["orchestrated", "callback_direct"]
    owner_kind: Literal["core", "integration", "local_subproject"]

    # Stage requirements (pipeline_governed only)
    minimum_stage: str                         # earliest stage where command is available
    required_gates: tuple[str, ...] = ()       # gates that must be True (empty for standalone)

    # Pipeline progression (for next_action computation)
    advances_pipeline: bool = False            # does this command move the pipeline forward?
    produced_gates: tuple[str, ...] = ()       # gates this command can set to True upon completion
    next_stage: str | None = None              # which stage does the pipeline transition to?
    workflow_rank: int | None = None           # ordering for next_action (lower = higher priority)
    recommended_when_gates_missing: tuple[str, ...] = ()  # recommend this command when these gates are missing

    # What it produces
    target: str | None = None                  # primary artifact (human-readable)

    # Mutation info
    mutates_project: bool = False              # does it write to outputs/?
    creates_run: bool = False                  # does it create a new run directory?

    # Network requirements
    network_policy: Literal["local_only", "external_allowed", "external_required"] = "local_only"
    # v1 NOTE: network_policy is descriptive only. Does NOT prove runtime availability.

    # Arguments
    requires_args: tuple[str, ...] = ()        # mandatory CLI args (info only, not validated by preflight)

    # State policy
    state_policy: Literal["pipeline_initializer", "pipeline_governed", "standalone_allowed"] = "pipeline_governed"

    # Human info
    description: str = ""
```

**v1 Strategy**: `COMMAND_REGISTRY` mirrors existing metadata from `PIPELINE_MAP` and Phase 0 registrations. Parity tests detect divergence. Dispatch remains authoritative. A separate sprint migrates Dispatch and Orchestrator to consume `COMMAND_REGISTRY`.

**Standalone commands**: Commands like `audit:prose`, `audit:claims`, `gate:method` can execute directly on a manuscript without pipeline state. The `state_policy="standalone_allowed"` field preserves this semantics. For standalone commands, eligibility depends on input, not on `stage` or pipeline gates.

### 3. PreflightResolver (Slice B — Read-Only Resolver)

A read-only resolver `resolve_preflight(project_root: Path, command: str | None = None, review_config: ReviewConfigSnapshot | None = None) -> PreflightResult` that:

- Reads `state.yaml` via existing `StateManager`
- Reads gate statuses from `state.yaml` via `StateManager` (gate values are already computed and persisted)
- Reads `review_config.yaml` via `load_review_config_snapshot()` (or uses pre-loaded snapshot)
- Looks up command metadata from `CommandRegistry`
- Returns a typed `PreflightResult` dataclass

No side effects. No writes. No state transitions. This is a **view**, not a mutation. Note: it reads files, so it is not a "pure function" — it is a read-only resolver whose output depends on disk state at call time.

### 4. PreflightResult Contract (Reconciled)

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
    """Read-only snapshot of pipeline status for agents and CLI."""
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
    readiness_scope: str                 # "workflow_preconditions_only" — scope is limited to workflow preconditions, not full authorization
```

```python
@dataclass(frozen=True)
class PreflightBlocker:
    code: str                            # e.g. "gate_not_passed", "state_missing"
    scope: str                           # "pipeline" | "command"
    message: str                         # human-readable explanation
    resolution: str                      # what to do about it
```

#### Status Semantics

| Status | Meaning | Exit Code | When |
|--------|---------|-----------|------|
| `ready` | Pipeline state is valid and resolvable | 0 | State exists, gates consistent, no pipeline blockers |
| `needs_input` | Requires human input (missing state) | 2 | state.yaml missing for pipeline-governed command |
| `blocked` | Has blockers that prevent execution | 1 | Invalid state, unknown command, gate failures |

#### `can_proceed` Semantics (Reconciled v5)

`can_proceed` is NOT derived solely from `len(blockers) == 0`. It uses a single eligibility function that considers state validity:

```python
def _is_policy_eligible(
    spec: CommandSpec,
    current_stage: str,
    current_gates: dict[str, bool],
    *,
    state_missing: bool,
    state_invalid: bool,
) -> bool:
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

The `status` field is computed independently:

```python
if command is not None and spec is None:
    status = "blocked"
elif state_missing:
    if command is None or spec.state_policy == "pipeline_governed":
        status = "needs_input"
    else:
        status = "ready"
elif state_invalid:
    if command is not None and spec.state_policy == "standalone_allowed":
        status = "ready"
    else:
        status = "blocked"
elif command is not None and not can_proceed:
    status = "blocked"
else:
    status = "ready"
```

| Scenario | status | can_proceed | next_action |
|----------|--------|-------------|-------------|
| General preflight, pipeline valid | `ready` | `False` | `str` (recommended command) |
| General preflight, pipeline invalid | `blocked` | `False` | `None` |
| Command preflight, command available | `ready` | `True` | `None` |
| Command preflight, command blocked | `blocked` | `False` | `None` |
| Command preflight, needs input | `needs_input` | `False` | `None` |

**Key invariant:** `can_proceed: true` IMPLIES `status: "ready"`. The resolver MUST NEVER return `status: "ready"` + `can_proceed: false` when a `command` parameter is provided.

#### Blocker Scoping (Reconciled)

`blockers` and `blocked_commands` serve different purposes:

- **`blockers`**: Conditions relevant to the **current query**. For general preflight, these are pipeline-level blockers (missing state, invalid state, stage-gates inconsistency). For command-specific preflight, these are the specific reasons the requested command cannot execute.
- **`blocked_commands`**: A comprehensive list of ALL commands not eligible at the current state, with reasons. Always computed regardless of whether a specific command was requested.

Each `PreflightBlocker` has a `scope` field:
- `"pipeline"` — blocks all workflow-governed commands (e.g., missing state.yaml, invalid state); standalone commands remain eligible
- `"command"` — blocks a specific command (e.g., gate not passed for `render`)

### 5. Resolution Order

1. Load `state.yaml` via `StateManager` → `current_stage`, gate values (or defaults if missing), `state_missing`, `state_invalid`
2. Load `review_config.yaml` via `load_review_config_snapshot()` → `ReviewConfigSnapshot` (or use pre-loaded snapshot)
3. Lookup `command` in `COMMAND_REGISTRY` → `spec` (None if not provided or unknown)
4. Compute `available_commands` using `_is_policy_eligible()` — single authority for all eligibility
5. Compute `blocked_commands` using `_is_policy_eligible()` — all commands, not just requested
6. Compute `can_proceed`: False if no command or unknown command, else `_is_policy_eligible(spec, ..., state_missing, state_invalid)`
7. Compute `next_action`:
   - `command is not None` → None
   - `state_invalid` → None
   - `state_missing` → "init"
   - else → eligibility-filtered `_compute_next_action()`
8. Compute `blockers`: pipeline-level for general, command-specific for command preflight
9. Compute `status` with correct precedence:
   - unknown command → blocked
   - state_missing + pipeline_governed → needs_input
   - state_missing + standalone/init → ready + warning
   - state_invalid + standalone → ready + warning
   - state_invalid + pipeline_initializer → blocked (corrupt state blocks init)
   - state_invalid → blocked
   - command not eligible → blocked
   - otherwise → ready
10. Add `review_config` warnings to warnings list
11. Return frozen `PreflightResult`

**Important:** There is NO special-case jump for unknown_command. The resolver always builds a complete `PreflightResult`.

### 6. CLI Integration

Add `preflight` subcommand to `cli/paper/commands/preflight.py` and register in `cli/paper/parser.py`:

```bash
# Human-readable
$ paper preflight
Status: ready
Stage:  drafting
Mode:   rapid
Next:   Run `paper draft section <name>` or `paper draft all`

# With specific command query
$ paper preflight --command render
Status: blocked
Stage:  drafting
Blockers:
  - [command] Requires stage 'rendering' (current: drafting) → run `paper draft all` first

# Agent-consumable
$ paper --output-format json preflight
{
  "schema_version": "1.0",
  "status": "ready",
  "operation": "unknown",
  "review_mode": "rapid",
  "current_stage": "drafting",
  "current_gates": {
    "repo_initialized": true,
    "search_completed": true,
    "screened_evidence": true,
    "outline_drafted": true,
    "sections_completed": false,
    "bib_imported": false,
    "bib_normalized": false,
    "citations_resolved": false,
    "refs_validated": false,
    "style_passed": false,
    "reporting_passed": false,
    "render_passed": false,
    "ready_for_delivery": false
  },
  "available_commands": ["draft:section", "draft:all", "audit:prose", "audit:claims", "audit:citations", "audit:ethics", "audit:writing-quality", "audit:factuality", "audit:tables", "audit:quality-appraisal", "audit:code-health", "gate:method"],
  "blocked_commands": [
    {"command": "render", "reason": "requires stage 'rendering'", "required_stage": "rendering", "missing_gates": []}
  ],
  "next_action": "draft:section",
  "blockers": [],
  "warnings": [],
  "can_proceed": false,
  "command": null
}
```

---

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `cli/paper/commands/preflight.py` | **New** | CLI handler for preflight command |
| `cli/paper/parser.py` | Modified | Register preflight subparser |
| `cli/paper/output.py` | Modified | Extend `_serialize_result` with 3 missing fields (Slice A) |
| `cli/paper/dispatch.py` | Modified | Capture callback return values for exit codes (`type(...) is int` check) |
| `harness/domain/command_spec.py` | **New** | `CommandSpec` dataclass + `COMMAND_REGISTRY` (mirror, not SSOT) |
| `harness/services/preflight.py` | **New** | `PreflightResult` dataclass + `resolve_preflight()` function |
| `harness/services/review_config.py` | Modified | Add `ReviewConfigSnapshot` dataclass + `load_review_config_snapshot()`; legacy loader delegates to snapshot |
| `schemas/preflight.schema.json` | **New** | JSON Schema for PreflightResult |
| `harness/services/orchestrator.py` | Unchanged | OrchestratorRequest and OrchestratorResult unchanged |
| `harness/services/state_manager.py` | Unchanged | Read via existing public API |
| `tests/` | Modified | New test files for CommandRegistry, PreflightResolver, and CLI |

---

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Adding fields to OrchestratorResult JSON breaks existing consumers | Low | JSON consumers ignore unknown keys by spec; validate with existing test suite |
| Phase 0 commands conflict with preflight | Medium | Preflight is read-only and registered as its own subcommand — never intercepts Phase 0 dispatch path |
| Resolver reads stale state.yaml | Low | Document that preflight reflects disk state at call time |
| CommandRegistry diverges from actual command registration | Medium | Parity tests compare COMMAND_REGISTRY keys against PIPELINE_MAP keys; divergence fails CI |
| Standalone commands falsely blocked by pipeline gates | Medium | `state_policy="standalone_allowed"` exempts standalone commands from pipeline gate requirements |
| Resolver becomes a second source of truth for gates | Low | Resolver reads gate values from state.yaml — never re-executes gate logic |

---

## Open Questions (Deferred to v2)

1. **External audit without state.yaml**: How does preflight handle future pipeline-governed audit commands when no `state.yaml` exists? Does it create one, or fail closed?
2. **release_profile, execution_mode, evidence_access**: These fields have no implementable source in v1. Should they be added in v2 when a config source is established?
3. **CapabilityResolver for runtime availability**: Some commands depend on external tools (Pandoc, Zotero). Should v1 include a CapabilityResolver that checks runtime tool availability, or defer to v2?
4. **CommandRegistry migration**: When should PIPELINE_MAP be replaced by COMMAND_REGISTRY? The v1 strategy is mirror + parity tests; the v2 strategy is full migration.

---

## Why This Change Belongs to the Core

1. The preflight contract is a **read-only view** of existing state — no new state transitions
2. It **completes** the OrchestratorResult JSON contract by exposing 3 decision-critical fields
3. It **unifies** Phase 0 and Pipeline command status under one format
4. It **doesn't change** gates, transitions, or persistence semantics
5. It follows the **Gentle AI pattern**: harness around existing core, not replacement

---

## Rollback Plan

#### Slice A (JSON Completion)

1. Revert `cli/paper/output.py` `_serialize_result` to original 9-field version
2. Revert `harness/services/orchestrator.py` `_build_command_log_payload` to original version

#### Slice B (Preflight)

1. Remove `harness/domain/command_spec.py`
2. Remove `harness/services/preflight.py`
3. Remove `cli/paper/commands/preflight.py`
4. Remove `schemas/preflight.schema.json`
5. Revert `cli/paper/dispatch.py` to original callback behavior (discard return value, always return 0)
6. Revert `harness/services/review_config.py` to original `load_review_config()` (remove `ReviewConfigSnapshot` + `load_review_config_snapshot()`)
7. Remove preflight subparser registration from `cli/paper/parser.py`
8. Delete `tests/` additions for preflight

Total rollback: 4 file deletions + 5 file reverts, zero data migration needed — no persistent state was created.

---

## Success Criteria

### Slice A: OrchestratorResult JSON Completion

- [ ] JSON output includes `gate_changes`, `state_changes`, `failure_policy` (previously missing)
- [ ] Existing test suite passes unchanged (`make verify`)

### Slice B: Preflight Resolver + CLI Command

- [ ] `paper preflight` returns human-readable output with status, stage, blockers, next action
- [ ] `paper --output-format json preflight` returns valid JSON matching `schemas/preflight.schema.json`
- [ ] `paper preflight --command render` returns command-specific preflight with blockers scoped to that command
- [ ] Preflight resolver reads from existing state — no new state files created
- [ ] Preflight resolver has ≥80% unit test coverage
- [ ] Resolution order is deterministic: same state.yaml + gates → same PreflightResult
- [ ] No behavioral change for any existing command
- [ ] Exit codes: ready → 0, needs_input → 2, blocked → 1
- [ ] `can_proceed` is False when no command is specified, even if pipeline is valid
- [ ] Standalone commands (audit:prose, gate:method) are NOT blocked by pipeline gates

---

## Dependencies

- None external. Relies only on existing internal modules: `StateManager`, `harness.services.review_config` (both `load_review_config_snapshot()` and legacy `load_review_config()`).
- `CommandRegistry` is new but has no external dependencies — it mirrors existing metadata.
