"""paper CLI entrypoint.

Structural refactoring: parser in parser.py, dispatch in dispatch.py,
handlers in commands/. This module is the thin entrypoint + error boundary
+ public API re-exports.
"""

import sys

from cli.paper.dispatch import execute
from cli.paper.errors import ExternalServiceError, UserInputError
from cli.paper.output import emit_error
from cli.paper.parser import _get_version, build_parser  # noqa: F401
from cli.paper.project import MAX_ASCENDING_DEPTH, resolve_project_root  # noqa: F401


def main() -> None:
    """CLI entrypoint + single error boundary. Translates exceptions to exit codes."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = execute(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        emit_error("Interrupted")
        sys.exit(130)
    except UserInputError as exc:
        emit_error(str(exc))
        sys.exit(2)
    except ExternalServiceError as exc:
        emit_error(str(exc))
        sys.exit(3)
    except Exception as exc:
        # XR6-compliant catch-all: unexpected errors exit 1 (NEVER 3 — must not be
        # misclassified as external). Clean message, no raw traceback.
        # Typed exceptions above are caught first; SystemExit/KeyboardInterrupt are
        # BaseException and not swallowed here. Traceback suppression is intentional;
        # a --verbose traceback hook is deferred to Sprint 3 (runtime.py).
        emit_error(f"Internal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
