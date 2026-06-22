"""Preflight command handler and parser registration (Task B5).

Phase 0 callback: read-only pipeline status resolver. Calls
``resolve_preflight`` and formats the result as JSON or human-readable text.

Exit-code contract (captured by dispatch.execute via ``type(...) is int``):
- 0 → status "ready"
- 1 → status "blocked"
- 2 → status "needs_input"

Per design.md data flow:
    paper [--output-format json] [--project PATH] preflight [--command NAME]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cli.paper.output import emit_json, emit_result, should_emit_json

if TYPE_CHECKING:
    from harness.services.preflight import PreflightResult


def register_preflight(subparsers: Any) -> None:
    """Register the ``preflight`` subcommand.

    Adds a ``--command`` flag for command-specific preflight checks. The
    subparser is marked ``output_policy="json-capable"`` so it accepts both
    ``--output-format json`` and the default text mode.
    """
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
    """Handle the ``preflight`` command.

    Returns exit code: 0=ready, 1=blocked, 2=needs_input.
    Raises UserInputError if the explicit --project path does not exist
    (mapped to exit 2 by main()'s error boundary).
    """
    from cli.paper.project import resolve_project_root
    from harness.services.preflight import resolve_preflight
    from harness.services.review_config import load_review_config_snapshot

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


def _print_preflight(result: PreflightResult) -> None:
    """Emit human-readable preflight text to stdout.

    Renders every PreflightResult field as a labelled section so a human
    reading the terminal gets the complete picture: status, stage, command,
    operation, review mode, next action, gates, available/blocked commands,
    blockers, warnings, and the can_proceed verdict.
    """
    lines: list[str] = []
    lines.append(f"Status: {result.status}")
    lines.append(f"Stage:  {result.current_stage}")
    command_label = result.command if result.command is not None else "(none)"
    lines.append(f"Command: {command_label}")
    lines.append(f"Operation: {result.operation}")
    lines.append(f"Mode:   {result.review_mode}")
    next_label = result.next_action if result.next_action is not None else "(none)"
    lines.append(f"Next:   {next_label}")
    lines.append("")

    # Gates
    lines.append("Gates:")
    if result.current_gates:
        for gate, passed in result.current_gates.items():
            mark = "[x]" if passed else "[ ]"
            lines.append(f"  {mark} {gate}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Available commands
    lines.append("Available commands:")
    if result.available_commands:
        for cmd in result.available_commands:
            lines.append(f"  - {cmd}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Blocked commands
    lines.append("Blocked commands:")
    if result.blocked_commands:
        for blk in result.blocked_commands:
            lines.append(f"  - {blk.command} -> {blk.reason}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Blockers (structured)
    lines.append("Blockers:")
    if result.blockers:
        for blocker in result.blockers:
            lines.append(f"  - [{blocker.code}] ({blocker.scope}) {blocker.message}")
            lines.append(f"      resolution: {blocker.resolution}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Warnings
    lines.append("Warnings:")
    if result.warnings:
        for warning in result.warnings:
            lines.append(f"  - {warning}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Can proceed
    proceed_label = "yes" if result.can_proceed else "no"
    lines.append(f"Can Proceed: {proceed_label}")

    emit_result("\n".join(lines))
