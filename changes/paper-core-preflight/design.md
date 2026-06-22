# Design: paper-core-preflight

## Technical Approach

Add a read-only preflight system that gives external agent harnesses a structured, queryable view of the pipeline state. Preflight is a **read-only resolver** (`resolve_preflight`) that reads existing state (`state.yaml`, `review_config.yaml`, `CommandRegistry`) and returns an immutable `PreflightResult` dataclass. No new state files, no mutations, no side effects. Register as a Phase 0 CLI command (`paper preflight`). Complete the `OrchestratorResult` JSON contract by adding 3 missing fields.

This change is split into two independent slices:

- **Slice A**: OrchestratorResult JSON completion (add `gate_changes`, `state_changes`, `failure_policy`)
- **Slice B**: CommandRegistry + PreflightResolver + CLI command

## Architecture Decisions

### Decision: Read-Only Resolver, Not Pure Function

**Choice**: `resolve_preflight()` — stateless function that reads files
**Alternatives considered**: `PreflightResolver` class with injected dependencies; pure function with all inputs passed as arguments
**Rationale**: Reads state.yaml, review_config.yaml, and CommandRegistry. Deterministic for a given snapshot. Not "pure" in the strict FP sense (has I/O), but read-only and side-effect-free. Calling it "read-only resolver" avoids confusion.

### Decision: Phase 0 Command, Not Pipeline

**Choice**: Register via `set_defaults(func=...)` — direct callback, no Orchestrator
**Alternatives considered**: Add to CommandRegistry as an orchestrated command
**Rationale**: Preflight is read-only — doesn't need gate verification, state transitions, or rollback. Simpler, faster, no dependency wiring overhead.

### Decision: Callback Exit Code Contract

**Choice**: Modify `dispatch.py` to capture callback return values. If the return value is an `int`, use it as exit code. Otherwise, default to `0` (backward compatible).
**Alternatives considered**: Raise SystemExit from callback; use a special exception
**Rationale**: Existing Phase 0 callbacks return `None` or call `sys.exit()` → exit code 0 or propagates. Preflight needs explicit exit codes (0, 1, 2). The `type(callback_result) is int` check (NOT `isinstance` — avoids `bool` being treated as `int`) preserves backward compatibility while enabling specific exit codes. No changes needed to existing callbacks.

### Decision: Frozen Dataclass (with Caveats)

**Choice**: `@dataclass(frozen=True)` for `PreflightResult`
**Alternatives considered**: TypedDict, Pydantic model, plain dict
**Rationale**: Immutable (result shouldn't change after creation). Type-safe. Follows existing pattern in `harness/domain/state.py`.

**Caveat**: `frozen=True` does NOT make the dataclass hashable when it contains lists or dicts. For v1, immutability is the goal; hashability is not required. If caching is needed later, use `tuple` instead of `list` and `MappingProxyType` instead of `dict`.

**Shallowly immutable**: `frozen=True` prevents attribute reassignment (`result.status = "blocked"` raises `FrozenInstanceError`) but does NOT prevent mutation of contained mutable objects (`result.current_gates["new_gate"] = True` succeeds). This is acceptable for v1 because: (1) callers are internal and trusted, (2) the resolver creates a new instance per call, and (3) no external code holds a reference after serialization. If deep immutability becomes necessary, use `tuple` for `available_commands`, `warnings`, `missing_gates` and `MappingProxyType` for `current_gates`.

### Decision: CommandRegistry as Policy Mirror + Safety Augmentation (v1)

**Choice**: Create `harness/domain/command_spec.py` with `COMMAND_REGISTRY` as a policy mirror with safety augmentation
**Alternatives considered**: Import `PIPELINE_MAP` from `cli/paper/dispatch.py`; hard-code command availability; make COMMAND_REGISTRY the SSOT immediately; strict 1:1 mirror
**Rationale**: PIPELINE_MAP lives in the CLI layer and only covers orchestrated commands. The preflight needs ALL commands (orchestrated, Phase 0, external). A core-layer registry keeps the dependency direction correct: CLI → Core, never Core → CLI.

**v1 scope**: COMMAND_REGISTRY mirrors routing and stage requirements from the existing codebase, but may impose stricter workflow preconditions for agent safety (e.g., requiring `bib_imported` before `lint:bib`). Dispatch remains authoritative for execution. Parity tests verify key and stage alignment; semantic tests document intentional strictness.

**Key distinction**: The registry is NOT a strict 1:1 mirror of Orchestrator preconditions. It is a policy document that preflight uses to guide agents. The Orchestrator may be more permissive; preflight should never be more permissive.

### Decision: Three-Identity Model for CommandSpec

**Choice**: `CommandSpec` has three identity fields: `id` (canonical), `dispatch_key` (PIPELINE_MAP key), `cli_path` (tuple)
**Alternatives considered**: Single `name` field; `id` + `cli_path` only
**Rationale**: The three identities serve different purposes:
- `id`: canonical identifier (e.g., `draft:outline`) — used for cross-referencing
- `dispatch_key`: matches `PIPELINE_MAP` key exactly (e.g., `draft:outline`), `None` for Phase 0 — used by parity test
- `cli_path`: tuple of CLI tokens (e.g., `("draft", "outline")`) — used for documentation and future CLI generation

### Decision: Pipeline Progression Metadata

**Choice**: `CommandSpec` includes `advances_pipeline`, `produced_gates`, `next_stage`, `workflow_rank`, `recommended_when_gates_missing`
**Alternatives considered**: Separate hardcode map for `next_action`; derive from gate names; use `produced_gates` for recommendation
**Rationale**: Enables deterministic `next_action` computation without a separate hardcode map. Each command declares its progression role.

**Key distinction:** `produced_gates` describes what gates a command CAN set to True. `recommended_when_gates_missing` determines WHEN to recommend the command. The resolver uses `recommended_when_gates_missing` for filtering, NOT `produced_gates`.

**Example:** `import:bib` produces `("bib_imported", "bib_normalized")` but is recommended only when `("bib_imported",)` is missing. If only `bib_normalized` is missing, `lint:bib` should be recommended instead (it needs `bib_imported` to exist).

```python
# next_action algorithm (correct)
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

### Decision: Separated handler_kind and owner_kind

**Choice**: `handler_kind` = how invoked (`orchestrated` | `callback_direct`). `owner_kind` = who implements (`core` | `integration` | `local_subproject`)
**Alternatives considered**: Single `kind` field; `handler_kind` with extra values
**Rationale**: These are orthogonal concerns. A command can be `callback_direct` + `core` (doctor), `callback_direct` + `integration` (trace), or `callback_direct` + `local_subproject` (thesaurus:import). Mixing them loses information.

### Decision: Tuples for Frozen Dataclasses

**Choice**: `required_gates: tuple[str, ...] = ()`, `requires_args: tuple[str, ...] = ()`, `cli_path: tuple[str, ...]`
**Alternatives considered**: Lists with `field(default_factory=list)`
**Rationale**: Tuples are immutable and hashable. Lists in frozen dataclasses are technically mutable (the list object is frozen, not its contents). Tuples enforce true immutability at the type level. Empty tuple `()` is the correct default for optional collections.

### Decision: BlockedCommand Dataclass

**Choice**: `BlockedCommand` dataclass with typed fields (`command`, `reason`, `required_stage`, `missing_gates`)
**Alternatives considered**: `list[dict[str, str | None]]`; `dict[str, str | None]`
**Rationale**: Properly typed with optional fields (`required_stage` is `str | None`, `missing_gates` is `tuple[str, ...]`). Frozen dataclass ensures immutability. Clearer than a raw dict. Supports multiple missing gates (e.g., `render` blocked by `style_passed`, `reporting_passed`, etc.).

### Decision: Separate Slices for Independent Delivery

**Choice**: Slice A (JSON completion) and Slice B (preflight) are independent
**Alternatives considered**: Ship everything together
**Rationale**: JSON completion has immediate value (agents see gate_changes) and zero risk. Preflight is larger and needs more design work. Shipping Slice A first provides value while Slice B is refined.

### Decision: Scope-Aware Blockers

**Choice**: `PreflightBlocker` has a `scope` field (`"pipeline"` | `"command"`) to distinguish blockers that prevent workflow-governed commands from blockers that prevent a specific command. Standalone commands remain eligible regardless of pipeline blockers.
**Alternatives considered**: Separate `pipeline_blockers` and `command_blockers` lists; single flat list without scope
**Rationale**: A single structured list with scope is cleaner than two separate lists. The scope field makes it explicit whether a blocker is global or command-specific. This resolves the confusion between `blockers` and `blocked_commands`.

### Decision: state_policy for Standalone Commands

**Choice**: `CommandSpec.state_policy` field with values `"pipeline_initializer"` | `"pipeline_governed"` | `"standalone_allowed"`
**Alternatives considered**: Separate command lists for standalone vs pipeline; no policy field
**Rationale**: Commands like `audit:prose`, `audit:claims`, `gate:method` can execute directly on a manuscript without pipeline state. Requiring `sections_completed` or `screened_evidence` for these commands would break existing behavior. The `state_policy` field preserves standalone semantics while allowing pipeline-governed commands to have gate requirements.

### Alternatives Rejected

| Alternative | Rejected Because |
|-------------|-----------------|
| Extend `OrchestratorRequest` with preflight fields | Request is for execution, not inspection — changes the execution contract |
| Make preflight a gate | Gates validate, preflight reports — different concerns |
| Add preflight to `state.yaml` | State is pipeline state, not inspection metadata — would pollute the state model |
| Class-based resolver with DI | No state to inject — read-only resolver is simpler and testable |
| Import PIPELINE_MAP from CLI | Core importing from CLI violates hexagonal architecture |
| Persist preflight to run.yaml | v1 is read-only; persistence is a v2 concern |
| Make COMMAND_REGISTRY the SSOT immediately | Risk of divergence during migration; mirror + parity tests is safer |

## Data Flow

```
paper [--output-format json] [--project PATH] preflight [--command NAME]
    │
    ▼
cli/paper/commands/preflight.py:_cmd_preflight()
    │
    ├── resolve_project_root(args.project, Path.cwd())
    ├── load_review_config_snapshot(repo_path)
    │
    ▼
harness/services/preflight.py:resolve_preflight()
    │
    ├── StateManager.load_state()              ← reads state.yaml
    ├── ManuscriptState (STAGE_ORDER, STAGE_PRECONDITIONS)
    ├── COMMAND_REGISTRY                       ← harness/domain/command_spec.py
    ├── load_review_config_snapshot()          ← reads review_config.yaml
    │
    ▼
PreflightResult (frozen dataclass)
    │
    ├── output.emit_json()     (if --output-format json)
    └── _print_preflight()     (human-readable text)
```

## File Changes

### Slice A: OrchestratorResult JSON Completion

| File | Action | Description |
|------|--------|-------------|
| `cli/paper/output.py` | **Modify** | Add `gate_changes`, `state_changes`, `failure_policy` to `_serialize_result()` |
| `tests/test_cli/test_output.py` | **Modify** | Add tests for new fields |

### Slice B: Preflight System

| File | Action | Description |
|------|--------|-------------|
| `harness/domain/command_spec.py` | **Create** | `CommandSpec` dataclass + `COMMAND_REGISTRY` dict |
| `harness/services/preflight.py` | **Create** | `PreflightResult` dataclass + `resolve_preflight()` function |
| `harness/services/review_config.py` | **Modify** | Add `ReviewConfigSnapshot` dataclass + `load_review_config_snapshot()`; legacy loader delegates to snapshot |
| `cli/paper/commands/preflight.py` | **Create** | CLI handler: `register_preflight()` + `_cmd_preflight()` |
| `cli/paper/parser.py` | **Modify** | Import `register_preflight`, add subparser registration |
| `cli/paper/dispatch.py` | **Modify** | Capture callback return values for exit codes (`type(...) is int` check) |
| `schemas/preflight.schema.json` | **Create** | JSON Schema for PreflightResult |
| `tests/harness/test_preflight.py` | **Create** | Unit tests for `resolve_preflight()` |
| `tests/harness/test_command_spec.py` | **Create** | Unit tests for `COMMAND_REGISTRY` |
| `tests/test_cli/test_preflight_cmd.py` | **Create** | CLI integration tests |

## Interfaces / Contracts

### PreflightResult (Reconciled v1)

```python
# harness/services/preflight.py

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.domain.state import ManuscriptState
from harness.domain.command_spec import COMMAND_REGISTRY, CommandSpec
from harness.services.state_manager import StateManager
from harness.services.review_config import ReviewConfigSnapshot, load_review_config_snapshot


@dataclass(frozen=True)
class PreflightBlocker:
    """Structured blocker preventing command execution."""
    code: str          # e.g. "state_missing", "gate_not_passed"
    scope: str         # "pipeline" | "command"
    message: str       # human-readable explanation
    resolution: str    # what to do about it


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
    command: str | None                  # echo of input command (if any)
```

### ReviewConfigSnapshot (in review_config.py, NOT preflight.py)

```python
# harness/services/review_config.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReviewConfigSnapshot:
    """Snapshot of review_config.yaml with source tracking.

    Distinguishes between:
    - File loaded successfully
    - File missing (using defaults)
    - File invalid/corrupt (using defaults)
    """
    values: dict[str, Any]               # the config values (always populated)
    source: str                          # "file" | "default_missing" | "default_invalid"
    warnings: tuple[str, ...] = ()       # warnings to include in PreflightResult
```

**Why here, not in preflight.py:** `load_review_config_snapshot()` constructs this. If the class lived in `preflight.py`, `review_config.py` would import from `preflight.py` while `preflight.py` imports from `review_config.py` — circular. Both class and loader live in `review_config.py`. `preflight.py` imports `ReviewConfigSnapshot` (for type annotation) and `load_review_config_snapshot()` from `review_config.py`.

### resolve_preflight

```python
# harness/services/preflight.py

def resolve_preflight(
    project_root: Path,
    command: str | None = None,
    review_config: ReviewConfigSnapshot | None = None,
) -> PreflightResult:
    """Compute preflight status from existing pipeline state.

    Read-only resolver: reads state.yaml, review_config.yaml, CommandRegistry.
    No side effects. No state mutations. Deterministic for a given snapshot.

    Args:
        project_root: Path to the project root directory
        command: Optional command to check (None for general preflight)
        review_config: Optional pre-loaded review config snapshot. If None, loads from file.
    """
    # 1. Load state (returns defaults if missing)
    # 2. Load review_config if not provided (via load_review_config_snapshot)
    # 3. Lookup command in CommandRegistry (None if not provided or unknown)
    # 4. If command is not None and spec is None → status blocked, blocker unknown_command
    # 5. Compute stage, gates, blockers
    # 6. Determine available/blocked commands using _is_policy_eligible (single function)
    # 7. Compute can_proceed: False if no command, else _is_policy_eligible(spec, ..., state_missing, state_invalid)
    # 8. Compute status with correct precedence:
    #      - unknown command → blocked
    #      - state_missing + pipeline_governed → needs_input
    #      - state_missing + standalone/init → ready + warning
    #      - state_invalid + standalone → ready + warning
    #      - state_invalid → blocked
    #      - command provided and !can_proceed → blocked
    #      - otherwise → ready
    # 9. Compute blockers: pipeline-level for general, command-specific for command preflight
    # 10. Compute next_action: None if command provided or state_invalid; else eligibility-filtered
    # 11. Add review_config warnings to warnings list
    # 12. Return frozen PreflightResult
```

### CommandSpec

```python
# harness/domain/command_spec.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class CommandSpec:
    """Specification for a single CLI command.

    v1 scope: This is a TRANSITORY MIRROR of existing metadata.
    Dispatch remains authoritative. Parity tests detect divergence.
    Full migration is a v2 concern.
    """
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
    # CapabilityResolver is deferred to v2.

    # Arguments
    requires_args: tuple[str, ...] = ()        # mandatory CLI args (info only, not validated by preflight)

    # State policy
    state_policy: Literal["pipeline_initializer", "pipeline_governed", "standalone_allowed"] = "pipeline_governed"
    # pipeline_initializer: creates state.yaml (e.g., init); does NOT require state.yaml
    # pipeline_governed: requires state.yaml, stage, and gates
    # standalone_allowed: eligible regardless of pipeline state (parser validates args)

    # Human info
    description: str = ""
```

### CLI Registration

```python
# cli/paper/commands/preflight.py

import argparse
from pathlib import Path
from cli.paper.output import emit_json, emit_result, emit_info, should_emit_json


def register_preflight(subparsers: argparse._SubParsersAction) -> None:
    """Register preflight subcommand."""
    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Show pipeline status, blockers, and recommended next action.",
    )
    preflight_parser.add_argument(
        "--command",
        default=None,
        help="Preflight check for a specific command (e.g. 'search').",
    )
    preflight_parser.set_defaults(func=_cmd_preflight, output_policy="json-capable")


def _cmd_preflight(args: argparse.Namespace) -> int:
    """Handle preflight command. Returns exit code: 0=ready, 1=blocked, 2=needs_input."""
    from cli.paper.project import resolve_project_root
    from harness.services.preflight import resolve_preflight
    from harness.services.review_config import ReviewConfigSnapshot, load_review_config_snapshot

    repo_path = resolve_project_root(getattr(args, "project", None), Path.cwd())
    review_snapshot = load_review_config_snapshot(repo_path)

    result = resolve_preflight(
        project_root=repo_path,
        command=getattr(args, "command", None),
        review_config=review_snapshot,
    )

    if should_emit_json(args):
        emit_json(result)
    else:
        _print_preflight(result)

    return {"ready": 0, "needs_input": 2, "blocked": 1}[result.status]
```

### OrchestratorResult JSON Completion (Slice A)

```python
# cli/paper/output.py — _serialize_result()

def _serialize_result(result: OrchestratorResult) -> dict[str, JSONValue]:
    return {
        "command": to_json_value(result.command),
        "success": to_json_value(result.success),
        "stage_before": to_json_value(result.stage_before),
        "stage_after": to_json_value(result.stage_after),
        "steps": to_json_value(result.steps),
        "blockers": to_json_value(result.blockers),
        "warnings": to_json_value(result.warnings),
        "artifacts": to_json_value(result.artifacts),
        "gate_changes": to_json_value(result.gate_changes),      # NEW
        "state_changes": to_json_value(result.state_changes),    # NEW
        "failure_policy": to_json_value(result.failure_policy),  # NEW
        "exit_code": to_json_value(result.exit_code),
    }
```

### JSON Schema

See `schemas/preflight.schema.json` — canonical schema for agent consumption.

### Human-Readable Text Format

```
Status: ready
Stage:  drafting
Mode:   rapid
Next:   Run `paper draft section <name>` or `paper draft all`

Gates:
  [✓] repo_initialized    [✓] search_completed
  [✓] screened_evidence   [✓] outline_drafted
  [ ] sections_completed  [ ] bib_imported
  [ ] bib_normalized      [ ] citations_resolved
  [ ] refs_validated      [ ] style_passed
  [ ] reporting_passed    [ ] render_passed
  [ ] ready_for_delivery

Available (pipeline-relevant excerpt, not exhaustive):
  - draft:section
  - draft:all
  - (all standalone commands also eligible)

Blocked:
  - render     → requires stage 'rendering'
  - verify     → requires gate 'render_passed'

Blockers: (none)
Warnings: (none)

Can Proceed: no (no command specified)
```

## Integration Points

### Review Config Integration
- `load_review_config_snapshot()` is the single source of truth for review config loading
- The legacy `load_review_config()` MUST delegate to the snapshot to ensure both Preflight and Dispatch see identical values:
  ```python
  def load_review_config(project_root: Path) -> dict[str, Any]:
      snapshot = load_review_config_snapshot(project_root)
      for warning in snapshot.warnings:
          logger.warning(warning)
      return dict(snapshot.values)
  ```
- Returns `ReviewConfigSnapshot` with source tracking and warnings
- `review_mode` is the only field used from review_config in v1
- `review_mode` is reported and may produce warnings; it does NOT modify gates or command eligibility in v1

**ReviewConfigSnapshot construction:**

```python
# harness/services/review_config.py

import yaml

_DEFAULT_CONFIG: dict[str, Any] = {"mode": "rapid", "search_window": None, "amendments": []}

def load_review_config_snapshot(project_root: Path) -> ReviewConfigSnapshot:
    """Load review_config.yaml with source tracking.

    Parses YAML directly to detect invalid files (the existing loader
    swallows exceptions and returns defaults).

    Returns:
        ReviewConfigSnapshot with values, source, and warnings.
    """
    config_path = project_root / "outputs" / "review_config.yaml"

    if not config_path.exists():
        return ReviewConfigSnapshot(
            values=dict(_DEFAULT_CONFIG),
            source="default_missing",
            warnings=("review_config.yaml not found, using defaults",),
        )

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return ReviewConfigSnapshot(
                values=dict(_DEFAULT_CONFIG),
                source="default_invalid",
                warnings=("review_config.yaml is not a dict, using defaults",),
            )
        # Filter to known keys, guard against None overwriting defaults
        merged = dict(_DEFAULT_CONFIG)
        for key in _DEFAULT_CONFIG:
            if key in data and data[key] is not None:
                merged[key] = data[key]
        # Validate mode semantically — reject unknown values
        warnings: list[str] = []
        if merged["mode"] not in ("rapid", "academic"):
            warnings.append(f"Unknown review mode '{merged['mode']}', defaulting to 'rapid'")
            merged["mode"] = "rapid"
        return ReviewConfigSnapshot(
            values=merged,
            source="file",
            warnings=tuple(warnings),
        )
    except (yaml.YAMLError, OSError) as exc:
        return ReviewConfigSnapshot(
            values=dict(_DEFAULT_CONFIG),
            source="default_invalid",
            warnings=(f"review_config.yaml is invalid ({exc}), using defaults",),
        )
```

### State Integration
- Reads via `StateManager.load_state()` — no changes to `state.py` or `state_manager.py`
- Missing `state.yaml` → general preflight: `status="needs_input"`; pipeline_governed command: `status="needs_input"`; pipeline_initializer init: `status="ready"` + warning; standalone_allowed command: `status="ready"` + warning
- Invalid state → returns `status="blocked"` with error in `blockers`

**Minimal StateManager construction**: Preflight does NOT use `build_orchestrator_dependencies()` (which instantiates action runner, wrappers, tool resolver, and skills that preflight doesn't need). Instead:

```python
from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.services.state_manager import StateManager

def build_state_manager_for_preflight(project_root: Path) -> StateManager:
    """Build minimal StateManager for preflight (read-only, no orchestration deps)."""
    state_path = project_root / "outputs" / "state.yaml"
    repository = YamlFileStateRepository(state_path)
    return StateManager(repository)
```

This avoids pulling in the full orchestrator dependency graph.

### CommandRegistry Integration
- Preflight reads `COMMAND_REGISTRY` from `harness/domain/command_spec.py`
- In v1, only Preflight consumes COMMAND_REGISTRY. CLI (Dispatch) and Orchestrator continue to use PIPELINE_MAP and internal logic. Full migration is a v2 concern.
- Core never imports `cli.paper.dispatch`

### Dispatch Integration
- Preflight is a Phase 0 command (direct `func(args)` callback)
- No changes to PIPELINE_MAP routing or Orchestrator flow
- No changes to OrchestratorRequest or OrchestratorResult
- Standalone commands (`state_policy="standalone_allowed"`) are NOT blocked by pipeline gates

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `COMMAND_REGISTRY` completeness | Verify all PIPELINE_MAP keys have a CommandSpec (parity test) |
| Unit | `COMMAND_REGISTRY` standalone commands | Verify audit:prose, audit:claims, gate:method have `state_policy="standalone_allowed"` |
| Unit | `resolve_preflight()` with various states | Construct `ManuscriptState` with known stages/gates, verify `PreflightResult` fields |
| Unit | Missing state.yaml (pipeline_governed) | Call with non-existent project + pipeline_governed command → `status="needs_input"` |
| Unit | Missing state.yaml (standalone) | Call with non-existent project + standalone command → `status="ready"` + warning |
| Unit | All stages bootstrap→rendered | Parametrize over `STAGE_ORDER`, verify correct `available_commands` |
| Unit | Command-specific preflight | Pass `command="search"` → verify focused output |
| Unit | Blocker structure | Verify PreflightBlocker has code, scope, message, resolution |
| Unit | `can_proceed` derivation | Verify `can_proceed == False` when no command, `True` when command eligible |
| Unit | Standalone commands not blocked | Verify `audit:prose` is NOT in `blocked_commands` when pipeline gates fail |
| Integration | `paper preflight` CLI output | Run via subprocess, verify text output format |
| Integration | `paper --output-format json preflight` | Verify JSON schema compliance |
| Integration | `paper preflight --command search` | Verify command-specific output |
| Integration | Slice A: JSON completion | Verify gate_changes, state_changes, failure_policy in output |
| Compatibility | Existing commands unchanged | Run `make verify` — no regression |

## Migration / Rollout

No migration required. All changes are additive:
- New files (CommandSpec, preflight resolver, CLI handler, tests, schema)
- Additive change to `_serialize_result()` (new fields — backward-compatible)
- No state files created or modified

Rollback: delete new files, revert `_serialize_result()` to 9-field version.

## Open Questions (Deferred to v2)

1. **External audit without state.yaml**: Can we audit a DOCX/Markdown that wasn't created by Paper Writer? Requires `--input PATH` flag and a stateless audit mode.
2. **release_profile, execution_mode, evidence_access**: These fields have no implementable source in v1. They need formal addition to review_config.yaml and CLI flags.
3. **CapabilityResolver**: Runtime availability checking (is Consensus MCP authenticated? Is Pandoc installed?). The static CommandRegistry doesn't answer this.
4. **Preflight persistence**: Should preflight results be cached in run.yaml or a separate file? v1 is read-only; persistence is v2.
5. **CommandRegistry migration**: When should PIPELINE_MAP be replaced by COMMAND_REGISTRY? v1 strategy is mirror + parity tests; v2 strategy is full migration.
