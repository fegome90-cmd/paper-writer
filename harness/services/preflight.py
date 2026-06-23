"""Preflight data model and resolver: read-only snapshot of pipeline status.

Contains:
- PreflightResult: the complete pipeline status snapshot
- PreflightBlocker: structured blocker with scope
- BlockedCommand: a command that is not eligible at current state
- resolve_preflight(): read-only resolver that computes PreflightResult from state

The resolver reads state.yaml, review_config.yaml, and CommandRegistry.
No side effects. No state mutations. Deterministic for a given snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.domain.command_spec import COMMAND_REGISTRY, CommandSpec
from harness.domain.state import ManuscriptState
from harness.services.review_config import (
    ReviewConfigSnapshot,
    load_review_config_snapshot,
)
from harness.services.state_manager import StateManager, StateManagerError


@dataclass(frozen=True)
class PreflightBlocker:
    """Structured blocker preventing command execution."""

    code: str
    scope: str
    message: str
    resolution: str


@dataclass(frozen=True)
class BlockedCommand:
    """A command that is not eligible at the current pipeline state."""

    command: str
    reason: str
    required_stage: str | None = None
    missing_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreflightResult:
    """Read-only snapshot of pipeline status for agents and CLI.

    Note: frozen=True provides shallow immutability — the top-level
    attributes cannot be reassigned, but list/dict contents are mutable.
    Consumers should treat the contents as read-only by convention.
    """

    schema_version: str
    status: str
    operation: str
    review_mode: str
    current_stage: str
    current_gates: dict[str, bool]
    available_commands: list[str]
    blocked_commands: list[BlockedCommand]
    next_action: str | None
    blockers: list[PreflightBlocker]
    warnings: list[str]
    can_proceed: bool
    command: str | None
    readiness_scope: str = "workflow_preconditions_only"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _default_gates() -> dict[str, bool]:
    """All required gates set to False (for missing/invalid state)."""
    return dict.fromkeys(ManuscriptState.REQUIRED_GATES, False)


def _stage_index(stage: str) -> int:
    """Return the index of a stage in STAGE_ORDER. Returns -1 for unknown."""
    try:
        return ManuscriptState.STAGE_ORDER.index(stage)
    except ValueError:
        return -1


def _is_policy_eligible(
    spec: CommandSpec,
    current_stage: str,
    current_gates: dict[str, bool],
    *,
    state_missing: bool,
    state_invalid: bool,
) -> bool:
    """Unified eligibility check.

    SINGLE AUTHORITY for can_proceed, available_commands, blocked_commands,
    and next_action candidates. No prose exceptions — this function is the
    only determinant of whether a command is eligible at the current state.
    """
    if state_invalid:
        # Corrupt state blocks everything except standalone commands
        return spec.state_policy == "standalone_allowed"

    if state_missing:
        # Missing state blocks pipeline-governed commands;
        # standalone and pipeline_initializer are eligible
        return spec.state_policy in {"standalone_allowed", "pipeline_initializer"}

    if spec.state_policy in {"standalone_allowed", "pipeline_initializer"}:
        return True

    return _stage_index(current_stage) >= _stage_index(spec.minimum_stage) and all(
        current_gates.get(gate, False) for gate in spec.required_gates
    )


def _compute_next_action(
    current_stage: str,
    current_gates: dict[str, bool],
) -> str | None:
    """Compute recommended next action based on stage and gates.

    Filters by eligibility AND by whether the command's recommended_when_gates_missing
    gates are actually missing. Uses workflow_rank for priority (lower = higher).
    """
    candidates = [
        spec
        for spec in COMMAND_REGISTRY.values()
        if spec.workflow_rank is not None
        and _is_policy_eligible(
            spec,
            current_stage,
            current_gates,
            state_missing=False,
            state_invalid=False,
        )
        and any(
            not current_gates.get(gate, False)
            for gate in spec.recommended_when_gates_missing
        )
    ]
    candidates.sort(
        key=lambda s: s.workflow_rank if s.workflow_rank is not None else 0
    )
    return candidates[0].id if candidates else None


def _build_blocked_command(
    spec: CommandSpec,
    current_stage: str,
    current_gates: dict[str, bool],
    *,
    state_missing: bool,
    state_invalid: bool,
) -> BlockedCommand:
    """Build a BlockedCommand with a human-readable reason."""
    if state_invalid:
        return BlockedCommand(
            command=spec.id,
            reason="blocked by corrupt state",
        )
    if state_missing:
        return BlockedCommand(
            command=spec.id,
            reason="requires initialized project (run 'paper init')",
        )

    # State valid — determine stage/gate blockers
    missing = tuple(
        gate for gate in spec.required_gates if not current_gates.get(gate, False)
    )
    stage_low = _stage_index(current_stage) < _stage_index(spec.minimum_stage)

    parts: list[str] = []
    if stage_low:
        parts.append(f"requires stage '{spec.minimum_stage}'")
    if missing:
        gate_str = ", ".join(repr(g) for g in missing)
        label = "gates" if len(missing) > 1 else "gate"
        parts.append(f"requires {label}: {gate_str}")

    reason = "; ".join(parts) if parts else "not eligible"

    return BlockedCommand(
        command=spec.id,
        reason=reason,
        required_stage=spec.minimum_stage if stage_low else None,
        missing_gates=missing,
    )


def _load_state(
    project_root: Path,
) -> tuple[str, dict[str, bool], bool, bool, str | None]:
    """Load state.yaml.

    Returns:
        Tuple of (stage, gates, state_missing, state_invalid, error_message).
        When state is missing or invalid, defaults are returned.
    """
    state_path = project_root / "outputs" / "state.yaml"
    repository = YamlFileStateRepository(state_path)

    if not repository.exists():
        return ("bootstrap", _default_gates(), True, False, None)

    state_manager = StateManager(repository)
    try:
        data = state_manager.load_state()
        return (data["stage"], dict(data["gates"]), False, False, None)
    except (StateManagerError, UnicodeDecodeError) as e:
        return ("bootstrap", _default_gates(), False, True, str(e))


# ─── Resolver ────────────────────────────────────────────────────────────────


def resolve_preflight(
    project_root: Path,
    command: str | None = None,
    review_config: ReviewConfigSnapshot | None = None,
) -> PreflightResult:
    """Compute preflight status from existing pipeline state.

    Read-only resolver: reads state.yaml, review_config.yaml, CommandRegistry.
    No side effects. No state mutations. Deterministic for a given snapshot.

    Args:
        project_root: Path to the project root directory (must exist).
        command: Optional command to check (None for general preflight).
        review_config: Optional pre-loaded snapshot. If None, loads from file.

    Returns:
        Frozen PreflightResult with all fields populated.

    Raises:
        ValueError: If project_root does not exist or is not a directory.
    """
    if not project_root.is_dir():
        raise ValueError(
            f"Project root does not exist or is not a directory: {project_root}"
        )

    # 1. Load review config
    if review_config is None:
        review_config = load_review_config_snapshot(project_root)
    review_mode = review_config.values.get("mode", "rapid")
    if review_mode not in ("rapid", "academic"):
        review_mode = "rapid"

    # 2. Load state
    current_stage, current_gates, state_missing, state_invalid, state_error = (
        _load_state(project_root)
    )

    # 3. Lookup command in registry
    spec: CommandSpec | None = None
    if command is not None:
        spec = COMMAND_REGISTRY.get(command)

    # 4. Compute available_commands and blocked_commands via SINGLE AUTHORITY
    available_commands: list[str] = []
    blocked_commands: list[BlockedCommand] = []
    for cmd_id, cmd_spec in COMMAND_REGISTRY.items():
        if _is_policy_eligible(
            cmd_spec,
            current_stage,
            current_gates,
            state_missing=state_missing,
            state_invalid=state_invalid,
        ):
            available_commands.append(cmd_id)
        else:
            blocked_commands.append(
                _build_blocked_command(
                    cmd_spec,
                    current_stage,
                    current_gates,
                    state_missing=state_missing,
                    state_invalid=state_invalid,
                )
            )

    # 5. Compute can_proceed
    if command is None or spec is None:
        can_proceed = False
    else:
        can_proceed = _is_policy_eligible(
            spec,
            current_stage,
            current_gates,
            state_missing=state_missing,
            state_invalid=state_invalid,
        )

    # 6. Compute next_action (3-condition rule)
    if command is not None:
        next_action: str | None = None
    elif state_invalid:
        next_action = None
    elif state_missing:
        next_action = "init"
    else:
        next_action = _compute_next_action(current_stage, current_gates)

    # 7. Compute blockers and warnings
    blockers: list[PreflightBlocker] = []
    warnings: list[str] = list(review_config.warnings)

    # state_missing blockers/warnings
    if state_missing:
        # Pipeline-level state_missing blocker applies to:
        # - general preflight (no command)
        # - unknown command (pipeline state is still missing)
        # - pipeline_governed commands
        # Standalone and pipeline_initializer are exempt (warning only).
        if command is None or spec is None or (
            spec is not None and spec.state_policy == "pipeline_governed"
        ):
            blockers.append(
                PreflightBlocker(
                    code="state_missing",
                    scope="pipeline",
                    message="Project not initialized. Run `paper init` first.",
                    resolution="Run 'paper init' to create state.yaml",
                )
            )
        elif spec is not None:
            warnings.append("state.yaml missing; command does not require it")

    # state_invalid blockers/warnings
    if state_invalid:
        if command is None or spec is None or spec.state_policy != "standalone_allowed":
            blockers.append(
                PreflightBlocker(
                    code="state_invalid",
                    scope="pipeline",
                    message=f"Invalid state.yaml: {state_error}",
                    resolution="Fix or remove outputs/state.yaml",
                )
            )
        else:
            warnings.append(
                "state.yaml is corrupt; standalone command can proceed"
            )

    # unknown_command blocker (no special-case jump — full result still built)
    if command is not None and spec is None:
        blockers.append(
            PreflightBlocker(
                code="unknown_command",
                scope="command",
                message=f"Unknown command: {command}",
                resolution="Run 'paper --help' to see available commands",
            )
        )

    # command-specific blockers (valid command, valid state, but not eligible)
    if (
        command is not None
        and spec is not None
        and not can_proceed
        and not state_missing
        and not state_invalid
    ):
        stage_low = _stage_index(current_stage) < _stage_index(spec.minimum_stage)
        missing_cmd_gates = tuple(
            g for g in spec.required_gates if not current_gates.get(g, False)
        )
        if stage_low:
            blockers.append(
                PreflightBlocker(
                    code="stage_not_reached",
                    scope="command",
                    message=(
                        f"Command '{command}' requires stage "
                        f"'{spec.minimum_stage}' (current: {current_stage})"
                    ),
                    resolution=f"Advance pipeline to stage '{spec.minimum_stage}'",
                )
            )
        for gate in missing_cmd_gates:
            blockers.append(
                PreflightBlocker(
                    code="gate_not_passed",
                    scope="command",
                    message=(
                        f"Command '{command}' requires gate '{gate}' "
                        f"which is not passed"
                    ),
                    resolution=f"Complete the step that produces gate '{gate}'",
                )
            )

    # 8. Compute status with exact precedence from spec
    if command is not None and spec is None:
        status = "blocked"
    elif state_missing:
        if command is None or (
            spec is not None and spec.state_policy == "pipeline_governed"
        ):
            status = "needs_input"
        else:
            status = "ready"
    elif state_invalid:
        if (
            command is not None
            and spec is not None
            and spec.state_policy == "standalone_allowed"
        ):
            status = "ready"
        else:
            status = "blocked"
    elif command is not None and not can_proceed:
        status = "blocked"
    else:
        status = "ready"

    # 9. Compute operation
    operation = spec.operation if spec is not None else "unknown"

    # 9a. Warn about mutating standalone commands — these are eligible
    # (can_proceed=True) but have side effects outside the pipeline.
    # Agent consumers should check readiness_scope before auto-executing.
    if (
        can_proceed
        and spec is not None
        and spec.mutates_project
        and spec.state_policy == "standalone_allowed"
    ):
        warnings.append(
            f"Command '{command}' has external side effects; "
            f"only workflow preconditions were checked "
            f"(readiness_scope=workflow_preconditions_only)"
        )

    # 10. Build and return frozen result
    return PreflightResult(
        schema_version="1.0",
        status=status,
        operation=operation,
        review_mode=review_mode,
        current_stage=current_stage,
        current_gates=current_gates,
        available_commands=available_commands,
        blocked_commands=blocked_commands,
        next_action=next_action,
        blockers=blockers,
        warnings=warnings,
        can_proceed=can_proceed,
        command=command,
    )


__all__ = [
    "BlockedCommand",
    "PreflightBlocker",
    "PreflightResult",
    "resolve_preflight",
]
