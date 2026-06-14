"""Tests for main.py verbose wiring + build_parser-in-try (S12 + S14 + verdict C2).

S12: --verbose flag at root level (stored in args.verbose).
S14: configure_logging(verbose) called after parse, before dispatch.
C2 improvements (accepted Judgment Day PR3):
- CRITICAL 1 downgrade: build_parser inside try (import/parse errors caught).
- WARNING 4: PAPER_VERBOSE env var fallback (verbose works pre-parse).
- Suggestion 8: logger.exception() post-mortem in catch-all.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.paper import main as main_mod


def _run_main(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[int, str, str]:
    """Run main(), return (exit_code, stdout, stderr)."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    monkeypatch.setattr(sys, "argv", argv)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        try:
            main_mod.main()
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out_buf.getvalue(), err_buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_logging() -> object:

    yield
    logging.basicConfig(level=logging.WARNING, force=True)


class TestVerboseFlag:
    """S12: --verbose flag at root level."""

    def test_verbose_flag_parsed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper --verbose doctor sets args.verbose=True."""
        from cli.paper.parser import build_parser

        args = build_parser().parse_args(["--verbose", "doctor"])
        assert args.verbose is True

    def test_verbose_enables_debug_logging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--verbose configures root logger at DEBUG (S14)."""
        code, _out, _err = _run_main(
            ["paper", "--verbose", "--project", str(tmp_path), "doctor"], monkeypatch
        )
        assert code == 0
        assert logging.getLogger().level == logging.DEBUG

    def test_no_verbose_leaves_warning_logging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --verbose, logging stays at WARNING (default)."""
        code, _out, _err = _run_main(
            ["paper", "--project", str(tmp_path), "doctor"], monkeypatch
        )
        assert code == 0
        assert logging.getLogger().level == logging.WARNING


class TestPaperVerboseEnvVar:
    """WARNING 4: PAPER_VERBOSE env var fallback (verbose works pre-parse)."""

    def test_paper_verbose_env_enables_debug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAPER_VERBOSE", "1")
        code, _out, _err = _run_main(
            ["paper", "--project", str(tmp_path), "doctor"], monkeypatch
        )
        assert code == 0
        assert logging.getLogger().level == logging.DEBUG


class TestBuildParserInsideTry:
    """CRITICAL 1 downgrade: build_parser errors caught cleanly (not raw traceback)."""

    def test_build_parser_failure_exits_1_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If build_parser raises, the catch-all handles it (exit 1, clean message)."""

        def _bad_parser() -> None:
            raise ImportError("simulated parser build failure")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "doctor"])
        with patch.object(main_mod, "build_parser", _bad_parser):
            with pytest.raises(SystemExit) as exc:
                main_mod.main()
        assert exc.value.code == 1
