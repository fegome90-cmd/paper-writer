"""Unit and contract tests for remote Consensus MCP search provider."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from harness.ports.paper_search_provider import (
    SearchProviderResult,
    create_search_provider,
)
from integrations.tools.consensus_mcp_client import ConsensusRemoteMcpSearchProvider

STREAMABLE_HTTP_PATCH = "integrations.tools.consensus_mcp_client.streamable_http_client"
CLIENT_SESSION_PATCH = "integrations.tools.consensus_mcp_client.ClientSession"

# Sample Consensus MCP API response
SAMPLE_MCP_RESPONSE = {
    "papers": [
        {
            "title": "Retrieval-Augmented Code Generation: A Survey",
            "authors": ["Author A", "Author B", "Author C", "Author D"],
            "abstract": "This paper surveys retrieval-augmented approaches to code generation.",
            "journal": "arXiv",
            "year": 2025,
            "doi": "10.48550/arXiv.2510.04905",
            "url": "https://consensus.app/papers/details/abc12332chars/",
            "citation_count": 42,
            "study_type": "literature review",
            "takeaway": "RAG approaches improve code generation quality by 15-30%.",
        },
        {
            "title": "RepoCoder: Repository-Level Code Completion",
            "authors": ["Fengji Zhang", "Bei Chen"],
            "abstract": "We propose RepoCoder, an iterative retrieval-generation framework.",
            "journal": "EMNLP",
            "year": 2023,
            "url": "https://consensus.app/papers/details/def45632chars/",
            "citation_count": 120,
            "study_type": "non-rct experimental",
        },
    ],
    "total_results": 2,
    "query": "retrieval augmented generation",
}


class TestConsensusMcpProviderProperties:
    """Property tests for ConsensusRemoteMcpSearchProvider."""

    def test_unauthenticated_by_default(self) -> None:
        p = ConsensusRemoteMcpSearchProvider()
        assert p.is_authenticated is False
        assert p._url == "https://mcp.consensus.app/mcp"

    def test_authenticated_with_key(self) -> None:
        p = ConsensusRemoteMcpSearchProvider(api_key="test-key-123")
        assert p.is_authenticated is True

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError, match="secure HTTPS"):
            ConsensusRemoteMcpSearchProvider(url="http://insecure-endpoint.com/mcp")


class TestConsensusMcpProviderNormalization:
    """Test normalization of Consensus MCP results."""

    def test_normalize_full_result(self) -> None:
        raw = SAMPLE_MCP_RESPONSE["papers"][0]
        paper = ConsensusRemoteMcpSearchProvider._normalize(raw)

        assert paper.title == "Retrieval-Augmented Code Generation: A Survey"
        assert paper.doi == "10.48550/arXiv.2510.04905"
        assert paper.year == 2025
        assert "Author A" in paper.authors
        assert "et al." in paper.authors  # 4 authors -> truncated
        assert paper.citations_count == 42
        assert paper.source_platform == "consensus_mcp_remote"
        assert paper.extra_fields is not None
        assert paper.extra_fields["study_type"] == "literature review"
        assert paper.extra_fields["takeaway"] is not None
        assert paper.extra_fields["journal_name"] == "arXiv"
        assert paper.source_id == "10.48550/arXiv.2510.04905"

    def test_normalize_minimal_result(self) -> None:
        """Paper with only title should still normalize."""
        raw = {"title": "Minimal Paper", "year": 2024}
        paper = ConsensusRemoteMcpSearchProvider._normalize(raw)

        assert paper.title == "Minimal Paper"
        assert paper.doi is None
        assert "doi" in paper.defaulted_fields
        assert paper.year == 2024

    def test_normalize_no_title_skipped(self) -> None:
        """Papers without title should be skipped (raise ValueError)."""
        raw = {"authors": ["Someone"], "year": 2024}
        with pytest.raises(ValueError, match="no title"):
            ConsensusRemoteMcpSearchProvider._normalize(raw)

    def test_normalize_invalid_year(self) -> None:
        raw = {"title": "Test", "year": "not-a-year"}
        paper = ConsensusRemoteMcpSearchProvider._normalize(raw)
        assert paper.year == 0
        assert "year" in paper.defaulted_fields


class TestConsensusMcpProviderSearch:
    """Test search via mocked SSE/ClientSession."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        mock_sess = AsyncMock()
        mock_sess.__aenter__.return_value = mock_sess
        init_res = MagicMock()
        init_res.serverInfo.name = "consensus-mcp-server"
        init_res.serverInfo.version = "1.0"
        mock_sess.initialize.return_value = init_res

        tool_res = MagicMock()
        tool_res.content = [TextContent(type="text", text=json.dumps(SAMPLE_MCP_RESPONSE))]
        mock_sess.call_tool.return_value = tool_res
        return mock_sess

    def test_search_returns_normalized_papers(self, mock_session: MagicMock) -> None:
        provider = ConsensusRemoteMcpSearchProvider()

        # Mock the streamable_http_client context manager and ClientSession
        mock_streams = (AsyncMock(), AsyncMock(), MagicMock())
        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__.return_value = mock_streams

        with patch(STREAMABLE_HTTP_PATCH, return_value=mock_http_ctx):
            with patch(CLIENT_SESSION_PATCH, return_value=mock_session):
                result = provider.search("retrieval augmented generation", limit=10)

                assert isinstance(result, SearchProviderResult)
                assert len(result.papers) == 2
                assert result.papers[0].source_platform == "consensus_mcp_remote"
                assert result.provenance.provider == "consensus_mcp_remote"
                assert result.provenance.tool_name == "search"
                assert result.provenance.server_info["name"] == "consensus-mcp-server"

    def test_search_sends_bearer_header(self, mock_session: MagicMock) -> None:
        provider = ConsensusRemoteMcpSearchProvider(api_key="my-secret-token")

        mock_streams = (AsyncMock(), AsyncMock(), MagicMock())
        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__.return_value = mock_streams

        with patch("integrations.tools.consensus_mcp_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.__aenter__.return_value = mock_client

            with patch(STREAMABLE_HTTP_PATCH, return_value=mock_http_ctx):
                with patch(CLIENT_SESSION_PATCH, return_value=mock_session):
                    provider.search("test query")

                    # Check headers sent to httpx.AsyncClient
                    called_headers = mock_client_cls.call_args[1].get("headers", {})
                    assert called_headers.get("Authorization") == "Bearer my-secret-token"

    def test_search_empty_results(self, mock_session: MagicMock) -> None:
        # Mock empty response
        mock_session.call_tool.return_value.content = [
            TextContent(type="text", text=json.dumps({"papers": [], "total_results": 0}))
        ]

        provider = ConsensusRemoteMcpSearchProvider()
        mock_streams = (AsyncMock(), AsyncMock(), MagicMock())
        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__.return_value = mock_streams

        with patch(STREAMABLE_HTTP_PATCH, return_value=mock_http_ctx):
            with patch(CLIENT_SESSION_PATCH, return_value=mock_session):
                result = provider.search("obscure query")
                assert len(result.papers) == 0

    def test_search_passes_filters_to_arguments(self, mock_session: MagicMock) -> None:
        provider = ConsensusRemoteMcpSearchProvider()
        mock_streams = (AsyncMock(), AsyncMock(), MagicMock())
        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__.return_value = mock_streams

        with patch(STREAMABLE_HTTP_PATCH, return_value=mock_http_ctx):
            with patch(CLIENT_SESSION_PATCH, return_value=mock_session):
                provider.search(
                    "deep learning",
                    limit=5,
                    year_min=2021,
                    year_max=2024,
                    study_types=["rct", "meta-analysis"],
                    human=True,
                    sjr_max=1,
                )

                # Check arguments passed to session.call_tool
                call_args = mock_session.call_tool.call_args
                assert call_args is not None
                args_passed = call_args[1]["arguments"]
                assert args_passed["query"] == "deep learning"
                assert args_passed["year_min"] == 2021
                assert args_passed["year_max"] == 2024
                assert args_passed["study_types"] == ["rct", "meta-analysis"]
                assert args_passed["human"] is True
                assert args_passed["sjr_max"] == 1

    def test_search_rate_limit_raises_runtime_error(self) -> None:
        # Inject rate limit message in HTTP client exception
        provider = ConsensusRemoteMcpSearchProvider()

        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__.side_effect = Exception("HTTP 429 Too Many Requests")

        with patch(STREAMABLE_HTTP_PATCH, return_value=mock_http_ctx):
            with pytest.raises(RuntimeError, match="rate limit exceeded"):
                provider.search("test query")

    def test_search_unauthorized_raises_runtime_error(self) -> None:
        provider = ConsensusRemoteMcpSearchProvider()

        mock_http_ctx = AsyncMock()
        mock_http_ctx.__aenter__.side_effect = Exception("HTTP 401 Unauthorized")

        with patch(STREAMABLE_HTTP_PATCH, return_value=mock_http_ctx):
            with pytest.raises(RuntimeError, match="authentication failed"):
                provider.search("test query")


class TestConsensusMcpProviderFactory:
    """Test provider creation via factory."""

    def test_create_consensus_mcp_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PAPER_SEARCH_PROVIDER", "consensus_mcp_remote")
        provider = create_search_provider()
        assert isinstance(provider, ConsensusRemoteMcpSearchProvider)
