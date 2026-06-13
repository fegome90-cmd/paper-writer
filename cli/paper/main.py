"""paper CLI entrypoint.

Structural refactoring PR1: parser in parser.py, dispatch in dispatch.py,
handlers in commands/. This module is the thin entrypoint + public API
re-exports.
"""

import sys

from cli.paper.dispatch import execute
from cli.paper.parser import _get_version, build_parser  # noqa: F401
from cli.paper.project import MAX_ASCENDING_DEPTH, resolve_project_root  # noqa: F401


def main() -> None:
    """CLI entrypoint. Parses args, dispatches, exits with result code."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = execute(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
