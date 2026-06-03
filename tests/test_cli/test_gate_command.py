"""Tests for cli/paper/commands/gate.py — gate subcommand handler."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.paper.commands.gate import _cmd_gate_method


def _make_gate_args(
    file: str = "",
    output: str = "json",
    study_type: str = "*",
    checklist: str = "",
    na: list[str] | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        file=file,
        output=output,
        study_type=study_type,
        checklist=checklist,
        na=na or [],
    )


class TestCmdGateMethod:
    def test_file_not_found_exits_1(self, tmp_path: Path) -> None:
        """Missing file causes exit 1."""
        args = _make_gate_args(file=str(tmp_path / "nonexistent.md"))
        with pytest.raises(SystemExit) as exc_info:
            _cmd_gate_method(args)
        assert exc_info.value.code == 1

    def test_gate_passed_exits_0(self, tmp_path: Path) -> None:
        """Gate passed produces JSON and exits normally (no SystemExit)."""
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome content.")

        mock_result = {
            "gate_passed": True,
            "study_type": "observational",
            "checklist": [],
            "metadata": {},
        }
        args = _make_gate_args(file=str(md))
        with (
            patch("validators.method_gate.MethodGateValidator") as MockValidator,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock()
            MockValidator.return_value.validate.return_value = mock_result
            _cmd_gate_method(args)
        # No SystemExit means success (exit 0)

    def test_gate_failed_exits_1(self, tmp_path: Path) -> None:
        """Gate failed causes exit 1 (fail-closed)."""
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome content.")

        mock_result = {
            "gate_passed": False,
            "study_type": "observational",
            "checklist": [],
            "metadata": {},
        }
        args = _make_gate_args(file=str(md))
        with (
            patch("validators.method_gate.MethodGateValidator") as MockValidator,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock()
            MockValidator.return_value.validate.return_value = mock_result
            with pytest.raises(SystemExit) as exc_info:
                _cmd_gate_method(args)
            assert exc_info.value.code == 1

    def test_json_output_contains_metadata(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """JSON output includes execution_time_ms metadata."""
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome content.")

        mock_result = {
            "gate_passed": True,
            "study_type": "*",
            "checklist": [],
            "metadata": {},
        }
        args = _make_gate_args(file=str(md), output="json")
        with (
            patch("validators.method_gate.MethodGateValidator") as MockValidator,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock()
            MockValidator.return_value.validate.return_value = mock_result
            _cmd_gate_method(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "metadata" in data
        assert "execution_time_ms" in data["metadata"]
