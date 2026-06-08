"""Tests for Consensus search provider."""

import json
from unittest.mock import MagicMock, patch

import pytest

from harness.ports.paper_search_provider import (
    SearchProviderResult,
    create_search_provider,
)
from integrations.tools.consensus_client import ConsensusSearchProvider

# Sample Consensus API response
SAMPLE_RESPONSE = {
    "results": [
        {
            "title": "Retrieval-Augmented Code Generation: A Survey",
            "authors": ["Author A", "Author B", "Author C", "Author D"],
            "abstract": "This paper surveys retrieval-augmented approaches to code generation.",
            "journal_name": "arXiv",
            "publish_year": 2025,
            "doi": "10.48550/arXiv.2510.04905",
            "url": "https://consensus.app/papers/details/abc123/",
            "citation_count": 42,
            "study_type": "literature review",
            "takeaway": "RAG approaches improve code generation quality by 15-30%.",
        },
        {
            "title": "RepoCoder: Repository-Level Code Completion",
            "authors": ["Fengji Zhang", "Bei Chen"],
            "abstract": "We propose RepoCoder, an iterative retrieval-generation framework.",
            "journal_name": "EMNLP",
            "publish_year": 2023,
            "doi": "10.18653/v1/2023.emnlp-main.151",
            "url": "https://consensus.app/papers/details/def456/",
            "citation_count": 120,
            "study_type": "non-rct experimental",
        },
    ]
}


class TestConsensusProviderProperties:
    """Property tests for ConsensusSearchProvider."""

    def test_unauthenticated_by_default(self) -> None:
        p = ConsensusSearchProvider()
        assert p.is_authenticated is False

    def test_authenticated_with_key(self) -> None:
        p = ConsensusSearchProvider(api_key="test-key-123")
        assert p.is_authenticated is True


class TestConsensusProviderNormalization:
    """Test normalization of Consensus API results."""

    def test_normalize_full_result(self) -> None:
        raw = SAMPLE_RESPONSE["results"][0]
        paper = ConsensusSearchProvider._normalize(raw)

        assert paper.title == "Retrieval-Augmented Code Generation: A Survey"
        assert paper.doi == "10.48550/arXiv.2510.04905"
        assert paper.year == 2025
        assert "Author A" in paper.authors
        assert "et al." in paper.authors  # 4 authors → truncated
        assert paper.citations_count == 42
        assert paper.source_platform == "consensus"
        assert paper.extra_fields is not None
        assert paper.extra_fields["study_type"] == "literature review"
        assert paper.extra_fields["takeaway"] is not None

    def test_normalize_minimal_result(self) -> None:
        """Paper with only title should still normalize."""
        raw = {"title": "Minimal Paper", "publish_year": 2024}
        paper = ConsensusSearchProvider._normalize(raw)

        assert paper.title == "Minimal Paper"
        assert paper.doi is None
        assert "doi" in paper.defaulted_fields
        assert paper.year == 2024

    def test_normalize_no_title_skipped(self) -> None:
        """Papers without title should be skipped (raise ValueError)."""
        raw = {"authors": ["Someone"], "publish_year": 2024}
        with pytest.raises(ValueError, match="no title"):
            ConsensusSearchProvider._normalize(raw)

    def test_normalize_invalid_year(self) -> None:
        raw = {"title": "Test", "publish_year": "not-a-year"}
        paper = ConsensusSearchProvider._normalize(raw)
        assert paper.year == 0
        assert "year" in paper.defaulted_fields


class TestConsensusProviderSearch:
    """Test search via mocked HTTP."""

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_returns_normalized_papers(self, mock_urlopen: MagicMock) -> None:
        """Search returns normalized papers from API response."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(SAMPLE_RESPONSE).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        result = provider.search("retrieval augmented code generation", limit=10)

        assert isinstance(result, SearchProviderResult)
        assert len(result.papers) == 2
        assert result.papers[0].source_platform == "consensus"
        assert result.provenance.provider == "consensus"

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_sends_api_key_when_set(self, mock_urlopen: MagicMock) -> None:
        """API key is sent in x-api-key header."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider(api_key="my-key")
        provider.search("test query")

        req = mock_urlopen.call_args[0][0]
        # urllib.request.Request stores headers with title-case keys
        assert req.headers.get("X-api-key") == "my-key"

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_no_key_no_header(self, mock_urlopen: MagicMock) -> None:
        """No API key header when unauthenticated."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider.search("test query")

        req = mock_urlopen.call_args[0][0]
        assert "x-api-key" not in req.headers

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_network_error_raises(self, mock_urlopen: MagicMock) -> None:
        """Network errors raise RuntimeError."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        provider = ConsensusSearchProvider()
        with pytest.raises(RuntimeError, match="network error"):
            provider.search("test query")

    def test_search_empty_query_raises(self) -> None:
        provider = ConsensusSearchProvider()
        with pytest.raises(ValueError, match="empty"):
            provider.search("")

    def test_search_invalid_limit_raises(self) -> None:
        provider = ConsensusSearchProvider()
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            provider.search("test", limit=0)

    def test_search_limit_over_20_raises(self) -> None:
        """Consensus API max is 20 — requesting more should raise ValueError."""
        provider = ConsensusSearchProvider()
        with pytest.raises(ValueError, match="Consensus limit must be 1-20"):
            provider.search("test", limit=21)

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_timeout_raises_timeout_error(self, mock_urlopen: MagicMock) -> None:
        """Socket timeout should raise TimeoutError per ABC contract."""

        mock_urlopen.side_effect = TimeoutError("timed out")

        provider = ConsensusSearchProvider()
        with pytest.raises(TimeoutError, match="timed out"):
            provider.search("test query")

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_url_error_timeout_raises_timeout_error(self, mock_urlopen: MagicMock) -> None:
        """URLError with 'timed out' reason should also raise TimeoutError."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("timed out")

        provider = ConsensusSearchProvider()
        with pytest.raises(TimeoutError, match="timed out"):
            provider.search("test query")

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_http_500_raises_runtime_error(self, mock_urlopen: MagicMock) -> None:
        """HTTP 500 should raise RuntimeError with status code."""
        import email.message
        import io
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.consensus.app/v1/quick_search",
            code=500,
            msg="Internal Server Error",
            hdrs=email.message.Message(),
            fp=io.BytesIO(b"Internal Server Error"),
        )

        provider = ConsensusSearchProvider()
        with pytest.raises(RuntimeError, match="HTTP 500"):
            provider.search("test query")

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_http_429_raises_runtime_error(self, mock_urlopen: MagicMock) -> None:
        """HTTP 429 rate limit should raise RuntimeError."""
        import email.message
        import io
        import urllib.error

        hdrs = email.message.Message()
        hdrs["Retry-After"] = "30"
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.consensus.app/v1/quick_search",
            code=429,
            msg="Too Many Requests",
            hdrs=hdrs,
            fp=io.BytesIO(b'{"error": "rate limit exceeded"}'),
        )

        provider = ConsensusSearchProvider()
        with pytest.raises(RuntimeError, match="HTTP 429"):
            provider.search("test query")

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_http_error_no_body(self, mock_urlopen: MagicMock) -> None:
        """HTTPError with unreadable body should not crash (W1 fix)."""
        import email.message
        import urllib.error

        error = urllib.error.HTTPError(
            url="https://api.consensus.app/v1/quick_search",
            code=502,
            msg="Bad Gateway",
            hdrs=email.message.Message(),
            fp=None,
        )
        mock_urlopen.side_effect = error

        provider = ConsensusSearchProvider()
        with pytest.raises(RuntimeError, match="HTTP 502"):
            provider.search("test query")

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_malformed_json_raises_runtime_error(self, mock_urlopen: MagicMock) -> None:
        """Non-JSON response body should raise RuntimeError (W3)."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>503 Service Unavailable</html>"
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        with pytest.raises(RuntimeError, match="invalid JSON"):
            provider.search("test query")

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_empty_results(self, mock_urlopen: MagicMock) -> None:
        """Empty results array should return empty papers list."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        result = provider.search("obscure query with no results")
        assert len(result.papers) == 0

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_search_passes_filters_to_api(self, mock_urlopen: MagicMock) -> None:
        """search() forwards **filters to _call_api — filters are not dead code."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider.search(
            "retrieval augmented generation",
            limit=5,
            year_min=2020,
            year_max=2025,
            study_types=["systematic review"],
            exclude_preprints=True,
        )

        req = mock_urlopen.call_args[0][0]
        url = req.full_url
        assert "year_min=2020" in url
        assert "year_max=2025" in url
        assert "exclude_preprints=true" in url
        assert "query=" in url


class TestConsensusFilterParams:
    """Test OpenAPI spec filter parameters — G4/G5 compliance."""

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_duration_min_sent_as_param(self, mock_urlopen: MagicMock) -> None:
        """duration_min filter is sent as query parameter per OpenAPI spec."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider._call_api("test", 10, duration_min=30)

        req = mock_urlopen.call_args[0][0]
        assert "duration_min=30" in req.full_url

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_duration_max_sent_as_param(self, mock_urlopen: MagicMock) -> None:
        """duration_max filter is sent as query parameter per OpenAPI spec."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider._call_api("test", 10, duration_max=365)

        req = mock_urlopen.call_args[0][0]
        assert "duration_max=365" in req.full_url

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_publisher_name_sent_as_param(self, mock_urlopen: MagicMock) -> None:
        """publisher_name filter is sent as query parameter per OpenAPI spec."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider._call_api("test", 10, publisher_name="Springer,Nature")

        req = mock_urlopen.call_args[0][0]
        assert "publisher_name=" in req.full_url

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_clinical_guideline_sent_as_param(self, mock_urlopen: MagicMock) -> None:
        """clinical_guideline filter is sent as query parameter per OpenAPI spec."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider._call_api("test", 10, clinical_guideline=True)

        req = mock_urlopen.call_args[0][0]
        assert "clinical_guideline=true" in req.full_url

    def test_sjr_max_valid_range(self) -> None:
        """sjr_max accepts values 1-4 per OpenAPI spec constraint."""
        provider = ConsensusSearchProvider()
        for val in [1, 2, 3, 4]:
            # Should not raise — just verify validation passes
            with patch("integrations.tools.consensus_client.urllib.request.urlopen") as mock:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps({"results": []}).encode()
                mock_resp.__enter__ = lambda s: mock_resp
                mock_resp.__exit__ = MagicMock(return_value=False)
                mock.return_value = mock_resp
                provider._call_api("test", 10, sjr_max=val)  # no raise

    def test_sjr_max_out_of_range_raises(self) -> None:
        """sjr_max outside 1-4 raises ValueError per OpenAPI spec constraint."""
        provider = ConsensusSearchProvider()
        for bad in [0, 5, -1, 10]:
            with pytest.raises(ValueError, match="sjr_max must be between 1 and 4"):
                provider._call_api("test", 10, sjr_max=bad)

    @patch("integrations.tools.consensus_client.urllib.request.urlopen")
    def test_all_filters_combined(self, mock_urlopen: MagicMock) -> None:
        """All 12 filter params can be sent in a single request."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = ConsensusSearchProvider()
        provider._call_api(
            "test",
            10,
            year_min=2020,
            year_max=2025,
            study_types=["rct"],
            human=True,
            sample_size_min=100,
            sjr_max=2,
            exclude_preprints=True,
            medical_mode=False,  # False → not sent
            duration_min=30,
            duration_max=365,
            publisher_name="Nature",
            clinical_guideline=True,
        )

        req = mock_urlopen.call_args[0][0]
        url = req.full_url
        # Verify all present params in URL
        assert "year_min=2020" in url
        assert "year_max=2025" in url
        assert "human=true" in url
        assert "sample_size_min=100" in url
        assert "sjr_max=2" in url
        assert "exclude_preprints=true" in url
        assert "duration_min=30" in url
        assert "duration_max=365" in url
        assert "publisher_name=Nature" in url
        assert "clinical_guideline=true" in url
        # medical_mode=False should NOT be in URL (falsy)
        assert "medical_mode" not in url


class TestConsensusProviderFactory:
    """Test provider creation via factory."""

    def test_create_consensus_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PAPER_SEARCH_PROVIDER", "consensus")
        provider = create_search_provider()
        assert isinstance(provider, ConsensusSearchProvider)
