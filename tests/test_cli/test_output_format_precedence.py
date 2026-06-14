"""Tests for output-format precedence + text-only rejection (P2.8.4 + P2.8.11 + P2.8.16 + P2.8.17).

P2.8.4: subcommand --output overrides root --output-format.
P2.8.11: zotero create/update/delete/upload reject --output-format json (text-only).
P2.8.16: root flag first-form 'paper --output-format json doctor' parsed then rejected.
P2.8.17: text-only callback rejects json; external policy ignores global renderer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cli.paper.main import main
from cli.paper.output import effective_output_format
from cli.paper.parser import build_parser


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> tuple[int, str]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    code = exc.value.code
    captured = capsys.readouterr()
    return (code if isinstance(code, int) else 1), f"{captured.out}\n{captured.err}"


class TestOutputFormatPrecedence:
    """P2.8.4: subcommand --output overrides root --output-format."""

    def test_subcommand_output_json_overrides_root_text(self) -> None:
        """audit prose --output json wins over root --output-format text."""
        parser = build_parser()
        args = parser.parse_args(["audit", "prose", "x.md", "--output", "json"])
        args.output_format = "text"
        assert effective_output_format(args) == "json"

    def test_root_json_applied_when_no_subcommand_output(self) -> None:
        """root --output-format json applies when subcommand has no --output."""
        parser = build_parser()
        args = parser.parse_args(["--output-format", "json", "audit", "prose", "x.md"])
        assert effective_output_format(args) == "json"

    def test_subcommand_output_terminal_overrides_root_json(self) -> None:
        """audit prose --output terminal wins over root --output-format json."""
        parser = build_parser()
        args = parser.parse_args(["audit", "prose", "x.md", "--output", "terminal"])
        args.output_format = "json"
        assert effective_output_format(args) == "text"


class TestZoteroTextOnlyRejectsJson:
    """P2.8.11: zotero create/update/delete/upload reject --output-format json."""

    @pytest.mark.parametrize(
        "sub,extra",
        [
            ("create", "file.json"),
            ("update", "KEY file.json"),
            ("delete", "KEY"),
            ("upload", "KEY file"),
        ],
    )
    def test_zotero_write_op_rejects_json(
        self,
        sub: str,
        extra: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        argv = ["paper", "--output-format", "json", "zotero", sub, *extra.split()]
        code, output = _run_cli(tmp_path, monkeypatch, capsys, argv)
        assert code == 2, f"zotero {sub} (text-only) MUST reject json with exit 2"
        assert "json" in output.lower()


class TestRootFlagFirstForm:
    """P2.8.16: 'paper --output-format json doctor' parsed then policy-rejected."""

    def test_root_flag_before_subcommand_parsed_then_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Root flag position is accepted by parser; policy rejects json for doctor."""
        code, output = _run_cli(
            tmp_path, monkeypatch, capsys, ["paper", "--output-format", "json", "doctor"]
        )
        assert code == 2, "doctor text-only + json must exit 2"
        assert "json" in output.lower()
