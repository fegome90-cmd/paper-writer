"""Thesaurus CLI parser registration with lazy import + graceful degradation.

Extracted from main.py in PR1 of cli-structural-refactoring.
Preserves the try/except ImportError pattern: real handlers when thesaurus
is installed, _cmd_unavailable fallback with install instructions when not.
"""

from __future__ import annotations

from typing import Any

from cli.paper.errors import UserInputError


def register_thesaurus(subparsers: Any) -> None:
    """Register thesaurus subcommands. Gracefully degrades if module missing."""
    try:
        from thesaurus.cli import _cmd_audit, _cmd_import, _cmd_list, _cmd_rebuild, _cmd_search
    except ImportError:

        def _cmd_unavailable(args: Any) -> None:
            raise UserInputError(
                "thesaurus module not installed. "
                "Install with: cd skills/local/thesaurus && uv pip install -e ."
            )

        _cmd_import = _cmd_search = _cmd_list = _cmd_audit = _cmd_rebuild = _cmd_unavailable

    thesaurus_parser = subparsers.add_parser(
        "thesaurus", help="Biomedical concept normalization (MeSH/DeCS)."
    )
    thesaurus_sub = thesaurus_parser.add_subparsers(dest="subcommand", required=True)

    thesaurus_import = thesaurus_sub.add_parser("import", help="Import concepts from JSONL.")
    thesaurus_import.add_argument("file", help="Path to JSONL file.")
    thesaurus_import.set_defaults(func=_cmd_import)

    thesaurus_search = thesaurus_sub.add_parser("search", help="Search concepts.")
    thesaurus_search.add_argument("query", help="Search query.")
    thesaurus_search.add_argument("--limit", type=int, default=20, help="Max results (default 20).")
    thesaurus_search.set_defaults(func=_cmd_search)

    thesaurus_list = thesaurus_sub.add_parser("list", help="List loaded concepts.")
    thesaurus_list.add_argument("--offset", type=int, default=0, help="Offset for pagination.")
    thesaurus_list.add_argument("--limit", type=int, default=50, help="Max results (default 50).")
    thesaurus_list.set_defaults(func=_cmd_list)

    thesaurus_audit = thesaurus_sub.add_parser("audit", help="Show thesaurus audit info.")
    thesaurus_audit.set_defaults(func=_cmd_audit)

    thesaurus_rebuild = thesaurus_sub.add_parser("rebuild", help="Rebuild DB from JSONL.")
    thesaurus_rebuild.set_defaults(func=_cmd_rebuild)
