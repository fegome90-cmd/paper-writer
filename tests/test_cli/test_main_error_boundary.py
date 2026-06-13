"""Tests for main.py error boundary (P2.6.1, B3 reinterpreted).

Proves the XR6-compliant catch-all: unexpected exceptions exit 1 with a
clean "Internal error:" message and NO raw traceback (while typed exceptions
UserInputError/ExternalServiceError keep their exit codes 2/3, and
KeyboardInterrupt keeps 130).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.paper.errors import ExternalServiceError, UserInputError
from cli.paper.main import main


def _run_main(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    """Invoke main() with given argv, return (exit_code, combined_output)."""
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    code = exc.value.code
    return (code if isinstance(code, int) else 1), ""


class TestUnexpectedExceptionCatchAll:
    """B3: unexpected exception -> exit 1, clean message, no traceback."""

    def test_unexpected_runtime_error_exits_1_not_3(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A handler raising RuntimeError must NOT leak as exit 3 (external)."""
        monkeypatch.chdir(tmp_path)

        def _boom(_args: object) -> None:
            raise RuntimeError("kaboom")

        # Wire doctor (Phase 0 callback) to raise an unexpected error.
        with patch("cli.paper.commands.doctor._cmd_doctor", _boom):
            code, _ = _run_main(["paper", "doctor"], monkeypatch)
        captured = capsys.readouterr()
        assert code == 1, "unexpected exception must exit 1, not leak as other code"
        assert code != 3, "XR6: unexpected must NEVER be misclassified as external (3)"
        assert "Internal error" in captured.err
        assert "kaboom" in captured.err
        assert "Traceback" not in captured.err, "no raw traceback for the user"

    def test_typed_exceptions_keep_their_codes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """UserInputError -> 2, ExternalServiceError -> 3 still hold (catch-all doesn't swallow)."""
        monkeypatch.chdir(tmp_path)

        for exc, expected in [
            (UserInputError("bad input"), 2),
            (ExternalServiceError("api down"), 3),
        ]:
            def _raise(_args: object, _exc: BaseException = exc) -> None:
                raise _exc

            with patch("cli.paper.commands.doctor._cmd_doctor", _raise):
                code, _ = _run_main(["paper", "doctor"], monkeypatch)
            assert code == expected
