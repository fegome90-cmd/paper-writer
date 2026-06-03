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

    @patch("skills.local.adapters.CitationVerifyValidator")
    @patch("skills.local.adapters.ManuscriptParser")
    def test_execute_offline_returns_gate_change(self, MockParser, MockValidator):
        mock_manuscript = MagicMock()
        MockParser.return_value.parse.return_value = mock_manuscript
        mock_validator = MagicMock()
        mock_validator.validate.return_value = []
        MockValidator.return_value = mock_validator

        adapter = CitationVerifyAdapter()
        result = adapter.execute(
            inputs={"file": "/tmp/test.md"},
            context={"offline": True},
        )

        assert result.status == "ok"
        assert result.gate_changes.get("citation_verified") is True

    @patch("skills.local.adapters.CitationVerifyValidator")
    @patch("skills.local.adapters.ManuscriptParser")
    def test_execute_with_findings(self, MockParser, MockValidator):
        MockParser.return_value.parse.return_value = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = [
            {"severity": "P0", "rule_id": "citation_verify.not_found"}
        ]
        MockValidator.return_value = mock_validator

        adapter = CitationVerifyAdapter()
        result = adapter.execute(
            inputs={"file": "/tmp/test.md"},
            context={"offline": True},
        )

        assert result.status == "ok"
        assert len(result.artifacts) > 0


class TestEthicsAdapter:
    def test_name_property(self):
        adapter = EthicsAdapter()
        assert adapter.name == "ethics"

    @patch("skills.local.adapters.EthicsValidator")
    @patch("skills.local.adapters.ManuscriptParser")
    def test_execute_returns_gate_change(self, MockParser, MockValidator):
        MockParser.return_value.parse.return_value = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = []
        MockValidator.return_value = mock_validator

        adapter = EthicsAdapter()
        result = adapter.execute(
            inputs={"file": "/tmp/test.md"},
            context={},
        )

        assert result.status == "ok"
        assert result.gate_changes.get("ethics_passed") is True


class TestWritingQualityAdapter:
    def test_name_property(self):
        adapter = WritingQualityAdapter()
        assert adapter.name == "writing_quality"

    @patch("skills.local.adapters.WritingQualityValidator")
    @patch("skills.local.adapters.ManuscriptParser")
    def test_execute_returns_ok(self, MockParser, MockValidator):
        MockParser.return_value.parse.return_value = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = []
        MockValidator.return_value = mock_validator

        adapter = WritingQualityAdapter()
        result = adapter.execute(
            inputs={"file": "/tmp/test.md"},
            context={},
        )

        assert result.status == "ok"
