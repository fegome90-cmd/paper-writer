"""Smoke test: real Consensus API quick_search.

Marked slow — excluded from CI fast path by default.
Run with: RUN_CONSENSUS_SMOKE=1 pytest tests/smoke/test_consensus_search_smoke.py -v
"""

import os

import pytest

from harness.ports.paper_search_provider import create_search_provider

# Skip entire module unless explicitly requested
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_CONSENSUS_SMOKE"),
    reason="Set RUN_CONSENSUS_SMOKE=1 to run real Consensus API smoke tests",
)


def test_consensus_unauthenticated_search() -> None:
    """Verify unauthenticated Consensus search returns results."""
    from integrations.tools.consensus_client import ConsensusSearchProvider

    provider = ConsensusSearchProvider()
    assert provider.is_authenticated is False

    result = provider.search("retrieval augmented generation", limit=5)
    assert result.provenance.provider == "consensus"
    assert len(result.papers) >= 1  # Unauthenticated gets at least 1

    paper = result.papers[0]
    assert paper.title
    assert paper.source_platform == "consensus"
    assert result.provenance.server_info["authenticated"] == "False"


def test_consensus_factory_path() -> None:
    """Verify factory creates ConsensusSearchProvider and executes search."""
    os.environ["PAPER_SEARCH_PROVIDER"] = "consensus"
    try:
        provider = create_search_provider()
        result = provider.search("machine learning systematic review", limit=3)
        assert result.provenance.provider == "consensus"
    finally:
        os.environ.pop("PAPER_SEARCH_PROVIDER", None)


def test_consensus_paper_normalization_fields() -> None:
    """Verify normalized papers have expected fields populated."""
    from integrations.tools.consensus_client import ConsensusSearchProvider

    provider = ConsensusSearchProvider()
    result = provider.search("transformer attention mechanism", limit=5)

    for paper in result.papers:
        assert paper.title
        assert paper.source_platform == "consensus"
        assert paper.year >= 2010  # Real papers shouldn't be ancient
        # At least some papers should have DOIs or URLs
        assert paper.doi or paper.url
