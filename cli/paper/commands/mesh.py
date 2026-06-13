"""MeSH CLI parser registration with lazy import + graceful degradation.

Extracted from main.py in PR1 of cli-structural-refactoring.
Uses dest="subcommand" (NOT mesh_subcommand) consistent with thesaurus and
all other composite commands -- per spec S6 and design.

The external mesh_import.cli.register() hardcodes dest="mesh_subcommand".
We call it, then normalize the dest to "subcommand" for consistency.
"""

from __future__ import annotations

from typing import Any

from cli.paper.errors import UserInputError


def register_mesh(subparsers: Any) -> None:
    """Register mesh subcommands. Gracefully degrades if module missing."""
    try:
        from mesh_import.cli import register as _register_mesh

        _register_mesh(subparsers)

        # The external register() uses dest="mesh_subcommand".
        # Normalize to dest="subcommand" per spec S6.
        for action in subparsers.choices["mesh"]._actions:
            if hasattr(action, "choices") and isinstance(action.choices, dict):
                if action.dest == "mesh_subcommand":
                    action.dest = "subcommand"
    except ImportError:

        def _cmd_mesh_unavailable(args: Any) -> None:
            raise UserInputError(
                "mesh-import module not installed. "
                "Install with: cd skills/local/mesh-import && uv pip install -e ."
            )

        mesh_parser = subparsers.add_parser("mesh", help="MeSH vocabulary import and lookup.")
        mesh_sub = mesh_parser.add_subparsers(dest="subcommand", required=True)
        mesh_fallback = mesh_sub.add_parser("import")
        mesh_fallback.set_defaults(func=_cmd_mesh_unavailable)
        mesh_resolve_fb = mesh_sub.add_parser("resolve")
        mesh_resolve_fb.set_defaults(func=_cmd_mesh_unavailable)
        mesh_expand_fb = mesh_sub.add_parser("expand")
        mesh_expand_fb.set_defaults(func=_cmd_mesh_unavailable)
        mesh_export_fb = mesh_sub.add_parser("export")
        mesh_export_fb.set_defaults(func=_cmd_mesh_unavailable)
