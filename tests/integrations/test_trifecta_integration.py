"""Integration tests for the Trifecta client against the REAL Trifecta CLI.

These tests are slower and require Trifecta to be installed. They verify
that paper-writer can successfully call Trifecta in a real subprocess
and parse the response.

Run with: MCP_TRIFECTA_MODE=real uv run pytest tests/integrations/test_trifecta_integration.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from clients.trifecta import TrifectaClient, get_trifecta_client


# These tests require the real Trifecta CLI to be installed
pytestmark = pytest.mark.skipif(
    os.environ.get("MCP_TRIFECTA_MODE") != "real",
    reason="Real Trifecta mode required (set MCP_TRIFECTA_MODE=real)",
)


# Integration tests use the actual paper-writer repo, not tmp_path
PAPER_WRITER_ROOT = Path(__file__).resolve().parents[2]


class TestTrifectaRealIntegration:
    """Verify the wrapper works against the actual Trifecta CLI."""

    def test_health_returns_node_count(self) -> None:
        """health() returns real node_count from paper-writer's graph."""
        client = TrifectaClient(repo_path=PAPER_WRITER_ROOT, timeout=30.0)
        result = client.health()
        assert result.success is True, f"health failed: {result.error}"
        assert "node_count" in result.data
        assert result.data["node_count"] > 0

    def test_find_orphans_returns_list(self) -> None:
        """find_orphans() returns a non-empty list of orphans from paper-writer."""
        client = TrifectaClient(repo_path=PAPER_WRITER_ROOT, timeout=30.0)
        result = client.find_orphans()
        assert result.success is True, f"find_orphans failed: {result.error}"
        assert isinstance(result.data, list)
        # paper-writer has > 0 orphans (we just analyzed the graph)
        assert len(result.data) > 0

    def test_find_callers_for_known_symbol(self) -> None:
        """find_callers('Orchestrator.execute') returns callers."""
        client = TrifectaClient(repo_path=PAPER_WRITER_ROOT, timeout=30.0)
        result = client.find_callers("Orchestrator.execute")
        assert result.success is True, f"find_callers failed: {result.error}"
        # Should be a list (may be empty, but no error)
        assert isinstance(result.data, list)

    def test_factory_returns_client_in_real_mode(self) -> None:
        """get_trifecta_client returns a TrifectaClient in real mode."""
        client = get_trifecta_client(repo_path=PAPER_WRITER_ROOT)
        assert client is not None
        assert isinstance(client, TrifectaClient)


class TestTrifectaGraphActions:
    """Integration tests for the new graph action methods (Phase 1b)."""

    def test_find_overview_returns_metrics(self) -> None:
        """find_overview returns graph metrics from paper-writer's index."""
        client = TrifectaClient(repo_path=PAPER_WRITER_ROOT, timeout=30.0)
        result = client.find_overview()
        assert result.success is True, f"find_overview failed: {result.error}"
        assert "node_count" in result.data
        assert "edge_count" in result.data
        assert result.data["node_count"] > 0

    def test_find_hubs_returns_list(self) -> None:
        """find_hubs returns top architectural hubs."""
        client = TrifectaClient(repo_path=PAPER_WRITER_ROOT, timeout=30.0)
        result = client.find_hubs(top_n=5)
        assert result.success is True, f"find_hubs failed: {result.error}"
        assert isinstance(result.data, list)
        # We know paper-writer has at least 1 hub (make_manuscript, ManuscriptState)
        assert len(result.data) > 0

    def test_find_path_between_entry_point_and_method(self) -> None:
        """find_path returns a path from main to a known method."""
        client = TrifectaClient(repo_path=PAPER_WRITER_ROOT, timeout=30.0)
        result = client.find_path("main", "BibliographyNormalizer.run")
        assert result.success is True, f"find_path failed: {result.error}"
        # The path might be empty if no connection, but no error
        assert isinstance(result.data, dict)
