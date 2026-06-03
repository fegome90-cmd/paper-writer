"""Tests for code_health validator (validators/code_health.py).

The code_health validator uses Trifecta to find dead code / orphans in
paper-writer's codebase, filtering out known false positives (tests, mixin
inheritance, CLI dispatch).

Strict TDD: tests written FIRST.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from validators.code_health import (
    CodeHealthReport,
    CodeHealthFinding,
    filter_actionable_orphans,
    analyze_code_health,
)


class TestFilterActionableOrphans:
    """Filter out known false positives from Trifecta's orphan list."""

    def test_excludes_test_files(self) -> None:
        """Orphans in tests/ directory are excluded."""
        orphans = [
            {"file_rel": "tests/test_foo.py", "symbol_name": "test_bar", "kind": "function"},
            {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1
        assert result[0]["symbol_name"] == "validate"

    def test_excludes_verification_files(self) -> None:
        """Orphans in verification/ directory are excluded."""
        orphans = [
            {"file_rel": "verification/run_validation.py", "symbol_name": "main", "kind": "function"},
            {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1
        assert result[0]["symbol_name"] == "validate"

    def test_excludes_argparse_callbacks(self) -> None:
        """Orphans with _cmd_ prefix (argparse callbacks) are excluded."""
        orphans = [
            {"file_rel": "cli/paper/main.py", "symbol_name": "_cmd_audit_prose", "kind": "function"},
            {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1
        assert result[0]["symbol_name"] == "validate"

    def test_excludes_main_function(self) -> None:
        """The `main` function is typically an entry point, not dead code."""
        orphans = [
            {"file_rel": "cli/paper/main.py", "symbol_name": "main", "kind": "function"},
            {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1
        assert result[0]["symbol_name"] == "validate"

    def test_excludes_mixin_inherited_methods(self) -> None:
        """Methods inherited from Mixin classes are not dead code."""
        orphans = [
            # tool_wrapper mixin methods
            {"file_rel": "integrations/tools/bibtex_tidy.py", "symbol_name": "name", "kind": "method"},
            {"file_rel": "integrations/tools/bibtex_tidy.py", "symbol_name": "gate", "kind": "method"},
            {"file_rel": "integrations/tools/bibtex_tidy.py", "symbol_name": "is_available", "kind": "method"},
            # real orphan
            {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1
        assert result[0]["symbol_name"] == "validate"

    def test_keeps_validation_methods(self) -> None:
        """Methods starting with validate_ ARE actionable (validation gap)."""
        orphans = [
            {"file_rel": "validators/claims.py", "symbol_name": "validate_claim", "kind": "function"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1
        assert result[0]["symbol_name"] == "validate_claim"

    def test_keeps_data_methods(self) -> None:
        """Methods starting with save/load/store ARE actionable (data_flow_break)."""
        orphans = [
            {"file_rel": "harness/repo.py", "symbol_name": "save_data", "kind": "method"},
        ]
        result = filter_actionable_orphans(orphans)
        assert len(result) == 1

    def test_empty_input_returns_empty(self) -> None:
        """Empty orphan list returns empty actionable list."""
        result = filter_actionable_orphans([])
        assert result == []


class TestAnalyzeCodeHealth:
    """analyze_code_health is the main entry point that ties everything together."""

    def test_returns_code_health_report(self) -> None:
        """analyze_code_health returns a CodeHealthReport."""
        with patch("clients.trifecta.get_trifecta_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.find_orphans.return_value.success = True
            mock_client.find_orphans.return_value.data = [
                {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
            ]
            mock_factory.return_value = mock_client
            report = analyze_code_health()
        assert isinstance(report, CodeHealthReport)
        assert report.trifecta_enabled is True
        assert len(report.findings) == 1
        assert report.findings[0].symbol_name == "validate"

    def test_returns_empty_report_when_trifecta_disabled(self) -> None:
        """When MCP_TRIFECTA_MODE=off, returns empty report with trifecta_enabled=False."""
        with patch("clients.trifecta.get_trifecta_client") as mock_factory:
            mock_factory.return_value = None
            report = analyze_code_health()
        assert isinstance(report, CodeHealthReport)
        assert report.trifecta_enabled is False
        assert report.findings == []
        assert report.error == "Trifecta not enabled (set MCP_TRIFECTA_MODE=real)"

    def test_returns_error_report_on_trifecta_failure(self) -> None:
        """When Trifecta fails, returns report with error but doesn't crash."""
        with patch("clients.trifecta.get_trifecta_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.find_orphans.return_value.success = False
            mock_client.find_orphans.return_value.error = "Trifecta CLI timeout"
            mock_factory.return_value = mock_client
            report = analyze_code_health()
        assert report.trifecta_enabled is True
        assert report.findings == []
        assert "timeout" in report.error.lower()

    def test_filters_false_positives(self) -> None:
        """analyze_code_health applies the filter to remove false positives."""
        with patch("clients.trifecta.get_trifecta_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.find_orphans.return_value.success = True
            mock_client.find_orphans.return_value.data = [
                # False positives (should be filtered)
                {"file_rel": "tests/test_foo.py", "symbol_name": "test_bar", "kind": "function"},
                {"file_rel": "cli/paper/main.py", "symbol_name": "_cmd_audit_prose", "kind": "function"},
                # Real finding
                {"file_rel": "validators/claims.py", "symbol_name": "validate", "kind": "function"},
            ]
            mock_factory.return_value = mock_client
            report = analyze_code_health()
        assert len(report.findings) == 1
        assert report.findings[0].symbol_name == "validate"
        assert report.filtered_count == 2


class TestCodeHealthFinding:
    """CodeHealthFinding data class."""

    def test_finding_stores_orphan_data(self) -> None:
        """CodeHealthFinding stores the orphan metadata."""
        finding = CodeHealthFinding(
            file_rel="validators/claims.py",
            symbol_name="validate",
            qualified_name="claims.validate",
            kind="function",
            orphan_type="dead_code",
        )
        assert finding.file_rel == "validators/claims.py"
        assert finding.symbol_name == "validate"


class TestCodeHealthReport:
    """CodeHealthReport data class."""

    def test_report_summary(self) -> None:
        """CodeHealthReport has a useful summary method."""
        finding = CodeHealthFinding(
            file_rel="validators/claims.py",
            symbol_name="validate",
            qualified_name="claims.validate",
            kind="function",
            orphan_type="dead_code",
        )
        report = CodeHealthReport(
            trifecta_enabled=True,
            findings=[finding],
            filtered_count=2,
            total_orphans_seen=3,
            error="",
        )
        assert "1 actionable" in report.summary()
        assert "2 filtered" in report.summary()
