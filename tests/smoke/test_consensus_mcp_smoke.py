"""Smoke test: real remote Consensus MCP Server connection.

Marked slow and requires network. Excluded from default CI runs.
Run with: RUN_CONSENSUS_MCP_SMOKE=1 pytest tests/smoke/test_consensus_mcp_smoke.py -v
"""

import os

import pytest

from harness.ports.paper_search_provider import create_search_provider

# Skip entire module unless explicitly requested
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_CONSENSUS_MCP_SMOKE"),
    reason="Set RUN_CONSENSUS_MCP_SMOKE=1 to run real Consensus remote MCP smoke tests",
)


def test_consensus_mcp_unauthenticated_search() -> None:
    """Verify unauthenticated remote Consensus MCP search returns papers."""
    from integrations.tools.consensus_mcp_client import ConsensusRemoteMcpSearchProvider

    provider = ConsensusRemoteMcpSearchProvider()
    assert provider.is_authenticated is False

    result = provider.search("retrieval augmented generation", limit=3)
    assert result.provenance.provider == "consensus_mcp_remote"
    assert result.provenance.tool_name == "search"
    assert len(result.papers) >= 1  # Unauthenticated gets 3 results max

    paper = result.papers[0]
    assert paper.title
    assert paper.source_platform == "consensus_mcp_remote"
    assert result.provenance.server_info["authenticated"] == "False"


def test_consensus_mcp_factory_path() -> None:
    """Verify factory creates ConsensusRemoteMcpSearchProvider and executes search."""
    os.environ["PAPER_SEARCH_PROVIDER"] = "consensus_mcp_remote"
    try:
        provider = create_search_provider()
        result = provider.search("machine learning systematic review", limit=2)
        assert result.provenance.provider == "consensus_mcp_remote"
        assert len(result.papers) >= 1
    finally:
        os.environ.pop("PAPER_SEARCH_PROVIDER", None)


def test_consensus_mcp_paper_normalization_fields() -> None:
    """Verify normalized papers from remote MCP have expected fields."""
    from integrations.tools.consensus_mcp_client import ConsensusRemoteMcpSearchProvider

    provider = ConsensusRemoteMcpSearchProvider()
    result = provider.search("transformer attention mechanism", limit=3)

    for paper in result.papers:
        assert paper.title
        assert paper.source_platform == "consensus_mcp_remote"
        assert paper.year >= 2015  # Transformers were proposed in 2017
        assert paper.url  # MCP search results must contain direct URLs
        assert paper.source_id
