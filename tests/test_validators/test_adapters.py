"""Tests for skills.local.adapters — new ARS adapters."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from skills.local.adapters import (
    CitationVerifyAdapter,
    EthicsAdapter,
    WritingQualityAdapter,
)


class TestCitationVerifyAdapter:
    def test_name_property(self):
        adapter = CitationVerifyAdapter()
        assert adapter.name == "citation_verify"

    @patch("parsers.manuscript.ManuscriptParser")
    def test_execute_offline_returns_gate_change(self, mock_parser):
        mock_manuscript = MagicMock()
        mock_parser.return_value.parse.return_value = mock_manuscript

        adapter = CitationVerifyAdapter()
        result = adapter.execute(
            command="audit_citations",
            inputs={"file": "/tmp/test.md", "offline": True},
            context={},
        )

        assert result.status in ("pass", "warn")
        # Offline mode produces skipped findings + summary verdict
        # citation_verified is False because findings exist (skipped counts as finding)
        assert "citation_verified" in result.gate_changes

    @patch("parsers.manuscript.ManuscriptParser")
    def test_execute_with_findings(self, mock_parser):
        mock_parser.return_value.parse.return_value = MagicMock()

        adapter = CitationVerifyAdapter()
        result = adapter.execute(
            command="audit_citations",
            inputs={"file": "/tmp/test.md", "offline": True},
            context={},
        )

        assert result.status in ("pass", "warn")
        assert len(result.artifacts) > 0


class TestEthicsAdapter:
    def test_name_property(self):
        adapter = EthicsAdapter()
        assert adapter.name == "ethics"

    @patch("parsers.manuscript.ManuscriptParser")
    def test_execute_returns_gate_change(self, mock_parser):
        # Mock manuscript with sections that have text
        mock_manuscript = MagicMock()
        mock_manuscript.sections = {}
        mock_manuscript.clean_text = "We used AI tools for editing."
        mock_parser.return_value.parse.return_value = mock_manuscript

        adapter = EthicsAdapter()
        result = adapter.execute(
            command="audit_ethics",
            inputs={"file": "/tmp/test.md"},
            context={},
        )

        assert result.status in ("pass", "warn", "fail")
        assert "ethics_passed" in result.gate_changes


class TestWritingQualityAdapter:
    def test_name_property(self):
        adapter = WritingQualityAdapter()
        assert adapter.name == "writing_quality"

    @patch("parsers.manuscript.ManuscriptParser")
    def test_execute_returns_ok(self, mock_parser):
        mock_parser.return_value.parse.return_value = MagicMock()

        adapter = WritingQualityAdapter()
        result = adapter.execute(
            command="audit_writing_quality",
            inputs={"file": "/tmp/test.md"},
            context={},
        )

        assert result.status in ("pass", "warn", "fail")
