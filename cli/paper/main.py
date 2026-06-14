"""paper CLI entrypoint.

Structural refactoring: parser in parser.py, dispatch in dispatch.py,
handlers in commands/. This module is the thin entrypoint + error boundary
+ public API re-exports.
"""

import logging
import os
import sys

from cli.paper.dispatch import execute
from cli.paper.errors import ExternalServiceError, UserInputError
from cli.paper.output import emit_error
from cli.paper.parser import _get_version, build_parser  # noqa: F401
from cli.paper.project import MAX_ASCENDING_DEPTH, resolve_project_root  # noqa: F401
from cli.paper.runtime import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entrypoint + single error boundary. Translates exceptions to exit codes."""
    # PAPER_VERBOSE env var fallback: verbose works even if parsing fails (S12 + WARNING 4).
    verbose = os.environ.get("PAPER_VERBOSE", "").lower() in ("1", "true", "yes")
    try:
        # build_parser + parse_args INSIDE the try so import/parse errors are caught
        # cleanly instead of leaking a raw traceback (CRITICAL 1 downgrade).
        parser = build_parser()
        args = parser.parse_args()
        verbose = verbose or getattr(args, "verbose", False)
        configure_logging(verbose=verbose)
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
        # misclassified as external). logger.exception() writes the full traceback to
        # the log for post-mortem ONLY when verbose=True (Suggestion 8); in normal
        # mode the user sees a clean message + a tip to get the traceback.
        if verbose:
            logger.exception("Unhandled CLI exception")
        msg = f"Internal error: {exc}"
        if not verbose:
            msg += "\nTip: run with --verbose or PAPER_VERBOSE=1 for the full traceback"
        emit_error(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
