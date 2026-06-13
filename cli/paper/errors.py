"""CLI error taxonomy. Leaf module — imported by dispatch, project, commands, main.

These exception classes enable the exit-code semantic split:
- UserInputError → exit 2 (bad args, validation failures, invalid paths)
- ExternalServiceError → exit 3 (API errors, network, auth)

main.py is the single error boundary that translates these to exit codes.
"""

from __future__ import annotations


class UserInputError(Exception):
    """Bad user input: missing args, validation failures, invalid paths.

    Mapped to exit code 2 by main() error boundary.
    NOTE: The message should NOT include "Error:" prefix — emit_error() adds it.
    """


class ExternalServiceError(Exception):
    """External service failure: API errors, network, auth.

    Mapped to exit code 3 by main() error boundary.
    NOTE: The message should NOT include "Error:" prefix — emit_error() adds it.
    """
