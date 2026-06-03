"""Tests for cli/paper/commands/audit.py — audit subcommand handlers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.paper.commands.audit import (
    _cmd_audit_citations,
    _cmd_audit_claims,
    _cmd_audit_code_health,
    _cmd_audit_ethics,
    _cmd_audit_prose,
    _cmd_audit_writing_quality,
)


def _make_args(
    file: str = "",
    output: str = "json",
    offline: bool = True,
    whitelist: list[str] | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        file=file,
        output=output,
        offline=offline,
        whitelist=whitelist or [],
    )


class TestCmdAuditProse:
    def test_file_not_found_exits_1(self, tmp_path: Path) -> None:
        args = _make_args(file=str(tmp_path / "missing.md"))
        with pytest.raises(SystemExit) as exc:
            _cmd_audit_prose(args)
        assert exc.value.code == 1

    def test_prose_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome content.")
        args = _make_args(file=str(md), output="json")
        with (
            patch("validators.prose.ProseValidator") as MockVal,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock(format="markdown")
            MockVal.return_value.validate.return_value = []
            MockVal.return_value.rules_count = 5
            _cmd_audit_prose(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "audit_prose"
        assert data["format"] == "markdown"


class TestCmdAuditClaims:
    def test_claims_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nThis is clearly the best approach.")
        args = _make_args(file=str(md), output="json")
        with (
            patch("validators.claims.ClaimsValidator") as MockVal,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
            patch("validators.claims.build_claims_report") as mock_report,
        ):
            MockParser.return_value.parse.return_value = MagicMock()
            MockVal.return_value.validate.return_value = []
            MockVal.return_value.rules = []
            mock_report.return_value = {"command": "audit_claims", "summary": {"total_candidates": 0}}
            _cmd_audit_claims(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "audit_claims"


class TestCmdAuditCitations:
    def test_citations_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome text.")
        args = _make_args(file=str(md), output="json", offline=True)
        with (
            patch("validators.citation_verify.CitationVerifyValidator") as MockVal,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock(format="markdown")
            MockVal.return_value.validate.return_value = []
            _cmd_audit_citations(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "audit_citations"
        assert data["metadata"]["offline"] is True

    def test_citations_p0_exits_1(self, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome text.")
        args = _make_args(file=str(md), output="json")
        with (
            patch("validators.citation_verify.CitationVerifyValidator") as MockVal,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock(format="markdown")
            MockVal.return_value.validate.return_value = [{"severity": "P0", "rule_id": "test"}]
            with pytest.raises(SystemExit) as exc:
                _cmd_audit_citations(args)
            assert exc.value.code == 1


class TestCmdAuditEthics:
    def test_ethics_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome text.")
        args = _make_args(file=str(md), output="json")
        with (
            patch("validators.ethics.EthicsValidator") as MockVal,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock(format="markdown")
            MockVal.return_value.validate.return_value = []
            _cmd_audit_ethics(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "audit_ethics"


class TestCmdAuditWritingQuality:
    def test_writing_quality_json_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Test\n\nSome text.")
        args = _make_args(file=str(md), output="json")
        with (
            patch("validators.writing_quality.WritingQualityValidator") as MockVal,
            patch("parsers.manuscript.ManuscriptParser") as MockParser,
        ):
            MockParser.return_value.parse.return_value = MagicMock(format="markdown")
            MockVal.return_value.validate.return_value = []
            MockVal.return_value.rules = []
            _cmd_audit_writing_quality(args)
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "audit_writing_quality"


class TestCmdAuditCodeHealth:
    def test_code_health_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(output="json")
        mock_report = MagicMock()
        mock_report.summary.return_value = "No findings"
        mock_report.trifecta_enabled = False
        mock_report.findings = []
        mock_report.filtered_count = 0
        mock_report.total_orphans_seen = 0
        mock_report.error = None
        with patch("validators.code_health.analyze_code_health", return_value=mock_report):
            with pytest.raises(SystemExit) as exc:
                _cmd_audit_code_health(args)
            assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["trifecta_enabled"] is False
        assert data["actionable_count"] == 0

    def test_code_health_with_findings_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(output="json")
        mock_finding = MagicMock()
        mock_finding.to_dict.return_value = {"file_rel": "test.py", "symbol_name": "foo", "orphan_type": "dead"}
        mock_report = MagicMock()
        mock_report.summary.return_value = "1 finding"
        mock_report.trifecta_enabled = True
        mock_report.findings = [mock_finding]
        mock_report.filtered_count = 0
        mock_report.total_orphans_seen = 10
        mock_report.error = None
        with patch("validators.code_health.analyze_code_health", return_value=mock_report):
            with pytest.raises(SystemExit) as exc:
                _cmd_audit_code_health(args)
            assert exc.value.code == 1
