"""Doctor command handler and parser registration.

Extracted from main.py in PR1 of cli-structural-refactoring.
Heavy harness.services.doctor imports are lazy (inside handler body).
Preserves --live and --live-search-probe handling (Judgment Day Round 3 fix).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from cli.paper.project import resolve_project_root


def _cmd_doctor(args: Any) -> None:
    """Check environment and report tool status. Runs directly, exits directly."""
    from harness.services.doctor import (
        check_all_tools,
        check_internal_capabilities,
        format_doctor_report,
    )

    repo_path = resolve_project_root(args.project, Path.cwd())
    tools = check_all_tools()
    caps = check_internal_capabilities(repo_path)
    print(format_doctor_report(tools, caps))

    # --live / --live-search-probe: preserved from main.py (~lines 1019-1023)
    if getattr(args, "live", False) or getattr(args, "live_search_probe", False):
        print()
        from harness.services.doctor import run_live_checks

        print(run_live_checks(run_search_probe=getattr(args, "live_search_probe", False)))

    sys.exit(0)


def register_doctor(subparsers: Any) -> None:
    """Register the doctor subcommand."""
    doc_parser = subparsers.add_parser("doctor", help="Check environment and report tool status.")
    doc_parser.add_argument(
        "--live",
        action="store_true",
        help="Perform live connectivity checks on the search provider.",
    )
    doc_parser.add_argument(
        "--live-search-probe",
        action="store_true",
        help="Perform live connection checks AND execute a search probe.",
    )
    doc_parser.set_defaults(func=_cmd_doctor)
