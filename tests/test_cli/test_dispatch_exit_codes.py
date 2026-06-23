"""Tests for dispatch.py callback exit code capture (Task B5a).

Verifies that dispatch.execute() captures callback return values:
- int → used as exit code
- None → defaults to 0 (backward compat)
- non-int (str, etc.) → defaults to 0
- bool → defaults to 0 (bool is NOT treated as int via type() is int check)
- SystemExit → propagates without interception

Both normal path and clean_cancel path are covered.
"""

from __future__ import annotations

from typing import Any

import pytest

from cli.paper.dispatch import execute


def _make_args(
    func: Any,
    *,
    clean_cancel: bool = False,
    command: str = "test",
    project: str | None = None,
    quiet: bool = False,
    output_format: str = "text",
    output_policy: str = "json-capable",
) -> Any:
    """Build a minimal argparse.Namespace-like object for dispatch.execute()."""

    class _Args:
        pass

    args = _Args()
    args.func = func
    args.clean_cancel = clean_cancel
    args.command = command
    args.project = project
    args.quiet = quiet
    args.output_format = output_format
    args.output_policy = output_policy
    return args


class TestNormalPathExitCodes:
    """B5a: normal (non-clean_cancel) callback path exit codes."""

    def test_callback_return_int_uses_as_exit_code(self) -> None:
        def cb(args: Any) -> int:
            return 2

        assert execute(_make_args(cb)) == 2

    def test_callback_return_none_defaults_to_zero(self) -> None:
        def cb(args: Any) -> None:
            return None

        assert execute(_make_args(cb)) == 0

    def test_callback_return_non_int_defaults_to_zero(self) -> None:
        def cb(args: Any) -> str:
            return "ok"

        assert execute(_make_args(cb)) == 0

    def test_callback_return_bool_not_treated_as_int(self) -> None:
        """bool is subclass of int, but type(True) is int → False.

        type() is int (NOT isinstance) ensures True is NOT treated as exit code 1.
        """

        def cb(args: Any) -> bool:
            return True

        assert execute(_make_args(cb)) == 0

    def test_callback_raises_system_exit(self) -> None:
        """SystemExit from callback propagates — dispatch does NOT intercept."""

        def cb(args: Any) -> None:
            raise SystemExit(1)

        with pytest.raises(SystemExit) as exc_info:
            execute(_make_args(cb))
        assert exc_info.value.code == 1


class TestCleanCancelPathExitCodes:
    """B5a: clean_cancel callback path exit codes."""

    def test_clean_cancel_returns_zero(self) -> None:
        def cb(args: Any) -> None:
            return None

        assert execute(_make_args(cb, clean_cancel=True)) == 0

    def test_clean_cancel_returns_int(self) -> None:
        def cb(args: Any) -> int:
            return 2

        assert execute(_make_args(cb, clean_cancel=True)) == 2


class TestExistingPhase0BehaviorUnchanged:
    """B5a: existing Phase 0 callback return patterns are unchanged.

    Covers all Phase 0 return patterns:
    - return None → dispatch returns 0
    - return int → dispatch returns that value
    - return bool → dispatch returns 0
    - raise SystemExit → propagates without interception
    """

    def test_phase0_return_none(self) -> None:
        def cb(args: Any) -> None:
            return None

        assert execute(_make_args(cb)) == 0

    def test_phase0_return_int(self) -> None:
        def cb(args: Any) -> int:
            return 42

        assert execute(_make_args(cb)) == 42

    def test_phase0_return_bool(self) -> None:
        def cb(args: Any) -> bool:
            return False

        assert execute(_make_args(cb)) == 0

    def test_phase0_system_exit_propagates(self) -> None:
        def cb(args: Any) -> None:
            raise SystemExit(3)

        with pytest.raises(SystemExit) as exc_info:
            execute(_make_args(cb))
        assert exc_info.value.code == 3
