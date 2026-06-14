"""Tests for cli/paper/runtime.py (S14 + S15 + S16).

S14: configure_logging(verbose) sets DEBUG/WARNING via logging.basicConfig(force=True).
S15: is_tty() returns sys.stdout.isatty(); NO is_color_enabled.
S16: temporary_sigint_handler() context manager installs KeyboardInterrupt-raising
     handler and restores the previous handler on exit (even on exception).
"""

from __future__ import annotations

import logging
import signal
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from cli.paper import runtime


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Reset logging config between tests (logging is process-global)."""
    yield
    logging.basicConfig(level=logging.WARNING, force=True)


class TestConfigureLogging:
    """S14: configure_logging(verbose) sets level; force=True allows reconfigure."""

    def test_verbose_sets_debug_level(self) -> None:
        runtime.configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_non_verbose_sets_warning_level(self) -> None:
        runtime.configure_logging(verbose=False)
        assert logging.getLogger().level == logging.WARNING

    def test_reconfigure_across_repeated_invocations(self) -> None:
        """force=True allows reconfiguring level between calls (P3.6.3)."""
        runtime.configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG
        runtime.configure_logging(verbose=False)
        assert logging.getLogger().level == logging.WARNING
        runtime.configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG


class TestIsTty:
    """S15: is_tty() returns sys.stdout.isatty()."""

    def test_is_tty_reflects_stdout_isatty(self) -> None:
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            assert runtime.is_tty() is True
            mock_stdout.isatty.return_value = False
            assert runtime.is_tty() is False

    def test_is_color_enabled_not_defined(self) -> None:
        """S15: is_color_enabled MUST NOT exist (Rich deferred)."""
        assert not hasattr(runtime, "is_color_enabled"), (
            "is_color_enabled is explicitly deferred per spec S15"
        )


class TestTemporarySigintHandler:
    """S16: temporary_sigint_handler installs + restores SIGINT handler."""

    def test_handler_installed_and_restored_on_normal_exit(self) -> None:
        """Context manager restores the previous SIGINT handler on clean exit."""
        original = signal.getsignal(signal.SIGINT)
        with runtime.temporary_sigint_handler():
            installed = signal.getsignal(signal.SIGINT)
            assert installed is not original, "handler must be installed inside context"
        restored = signal.getsignal(signal.SIGINT)
        assert restored is original, "handler MUST be restored on context exit"

    def test_handler_restored_on_exception(self) -> None:
        """Context manager restores previous handler even when body raises."""
        original = signal.getsignal(signal.SIGINT)
        with pytest.raises(RuntimeError, match="boom"):
            with runtime.temporary_sigint_handler():
                raise RuntimeError("boom")
        assert signal.getsignal(signal.SIGINT) is original, (
            "handler MUST be restored even on exception"
        )

    def test_installed_handler_raises_keyboard_interrupt(self) -> None:
        """The installed SIGINT handler raises KeyboardInterrupt when triggered."""
        with runtime.temporary_sigint_handler():
            installed = signal.getsignal(signal.SIGINT)
            # signal handlers are callable; mypy sees Handlers union so cast.
            from typing import Any

            handler_fn: Any = installed
            with pytest.raises(KeyboardInterrupt):
                handler_fn(signal.SIGINT, None)  # simulate signal delivery (signum, frame)
