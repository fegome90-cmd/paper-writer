"""Runtime configuration: logging, TTY detection, SIGINT context manager.

Sprint 3 module (spec S14-S16). Created here so the CLI can wire verbose
logging and clean SIGINT cancellation for Zotero write operations.

S14: configure_logging(verbose) — DEBUG when verbose, WARNING otherwise.
     Uses force=True so repeated invocations reconfigure cleanly.
S15: is_tty() — returns sys.stdout.isatty(). NO is_color_enabled (deferred).
S16: temporary_sigint_handler() — context manager that installs a handler
     raising KeyboardInterrupt and restores the previous handler on exit.
"""

from __future__ import annotations

import logging
import signal
import sys
from types import TracebackType


def configure_logging(*, verbose: bool = False) -> None:
    """Configure the root logger (S14).

    verbose=True -> DEBUG, otherwise WARNING. Uses force=True so repeated
    invocations (e.g. in tests calling main() multiple times) reconfigure
    cleanly rather than the basicConfig no-op-after-first-call behavior.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, stream=sys.stderr, force=True)


def is_tty() -> bool:
    """Return True if stdout is a TTY (S15).

    Useful for detecting pipes / non-interactive contexts. is_color_enabled
    is intentionally NOT implemented (Rich/colors deferred per spec S15).
    """
    return sys.stdout.isatty()


class TemporarySigintHandler:
    """Context manager that installs a KeyboardInterrupt-raising SIGINT handler (S16).

    On entry: installs a handler that raises KeyboardInterrupt when SIGINT arrives.
    On exit (normal or exceptional): restores the previous SIGINT handler.

    This is CLEAN cancellation (restores handler, raises KeyboardInterrupt -> exit 130),
    NOT safe cancellation (no guaranteed rollback of partial remote Zotero ops).
    For batch ops, the handler should log which items were modified before interruption.
    """

    def __init__(self) -> None:
        self._previous: object = None

    def __enter__(self) -> TemporarySigintHandler:
        self._previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handler)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Restore the previous handler even on exception. signal.signal accepts
        # SIG_DFL/SIG_IGN (ints) or callables; the union needs a cast for mypy.
        signal.signal(signal.SIGINT, self._previous)  # type: ignore[arg-type]

    @staticmethod
    def _handler(signum: int, frame: object) -> None:
        raise KeyboardInterrupt


# Public lowercase alias (spec S16 references temporary_sigint_handler as the
# context-manager name; dispatch._run_callback imports this name directly).
temporary_sigint_handler = TemporarySigintHandler
