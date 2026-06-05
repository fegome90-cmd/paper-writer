"""Tests for OpenAlex API client."""
from __future__ import annotations

from typing import Any

from clients.openalex import OpenAlexClient, OpenAlexResult


class TestOpenAlexResult:
    """Test OpenAlexResult dataclass."""

    def test_default_not_found(self) -> None:
        r = OpenAlexResult(found=False)
        assert r.found is False
        assert r.doi is None
        assert r.title is None
        assert r.authors == []
        assert r.year is None
        assert r.venue is None
        assert r.citation_count is None
        assert r.score == 0.0


class TestOpenAlexClientOffline:
    """Test OpenAlexClient in offline mode."""

    def test_verify_doi_offline(self) -> None:
        client = OpenAlexClient(offline=True)
        result = client.verify_doi("10.1234/test")
        assert result.found is False

    def test_search_by_title_offline(self) -> None:
        client = OpenAlexClient(offline=True)
        results = client.search_by_title("attention is all you need")
        assert results == []


class TestOpenAlexClientParseWork:
    """Test _parse_work with mock data."""

    def setup_method(self) -> None:
        self.client = OpenAlexClient(offline=True)

    def test_parse_full_work(self) -> None:
        work = {
            "title": "Attention Is All You Need",
            "doi": "https://doi.org/10.48550/arXiv.1706.03762",
            "publication_year": 2017,
            "authorships": [
                {"author": {"display_name": "Ashish Vaswani"}},
                {"author": {"display_name": "Noam Shazeer"}},
            ],
            "primary_location": {
                "source": {"display_name": "arXiv"},
            },
            "open_access": {"is_oa": True},
            "cited_by_count": 50000,
            "id": "W123456",
        }
        result = self.client._parse_work(work, score=1.0)
        assert result.found is True
        assert result.title == "Attention Is All You Need"
        assert result.doi == "10.48550/arXiv.1706.03762"
        assert result.year == 2017
        assert result.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert result.venue == "arXiv"
        assert result.is_oa is True
        assert result.citation_count == 50000
        assert result.openalex_id == "W123456"
        assert result.score == 1.0

    def test_parse_minimal_work(self) -> None:
        work = {"title": "Minimal Paper"}
        result = self.client._parse_work(work)
        assert result.found is True
        assert result.title == "Minimal Paper"
        assert result.doi is None
        assert result.year is None

    def test_doi_strips_prefix(self) -> None:
        work = {"doi": "https://doi.org/10.1038/nature12373"}
        result = self.client._parse_work(work)
        assert result.doi == "10.1038/nature12373"


class TestOpenAlexClientVerifyDoi:
    """Test verify_doi with mocked HTTP."""

    def test_verify_doi_success(self) -> None:
        client = OpenAlexClient(offline=False)
        response_data = {
            "title": "Test Paper",
            "doi": "https://doi.org/10.1234/test",
            "publication_year": 2024,
            "authorships": [],
            "primary_location": None,
            "open_access": {},
            "cited_by_count": 10,
            "id": "W999",
        }

        calls: list[str] = []

        def mock_get(path: str, query: dict[str, str]) -> dict[str, Any] | None:
            calls.append(path)
            return response_data

        client._get = mock_get  # type: ignore[assignment]
        result = client.verify_doi("10.1234/test")

        assert result.found is True
        assert result.title == "Test Paper"
        assert result.doi == "10.1234/test"
        assert result.year == 2024

    def test_verify_doi_not_found(self) -> None:
        client = OpenAlexClient(offline=False)

        def mock_get(path: str, query: dict[str, str]) -> dict[str, Any] | None:
            return {}  # 404

        client._get = mock_get  # type: ignore[assignment]
        result = client.verify_doi("10.1234/nonexistent")
        assert result.found is False


class TestOpenAlexClientSearch:
    """Test search_by_title with mocked HTTP."""

    def test_search_returns_ranked(self) -> None:
        client = OpenAlexClient(offline=False)
        response_data = {
            "results": [
                {
                    "title": "Attention Is All You Need",
                    "doi": "https://doi.org/10.48550/arXiv.1706.03762",
                    "publication_year": 2017,
                    "authorships": [],
                    "primary_location": None,
                },
                {
                    "title": "Attention Is What You Don't Need",
                    "doi": "https://doi.org/10.1234/unrelated",
                    "publication_year": 2020,
                    "authorships": [],
                    "primary_location": None,
                },
            ]
        }

        def mock_get(path: str, query: dict[str, str]) -> dict[str, Any] | None:
            return response_data

        client._get = mock_get  # type: ignore[assignment]
        results = client.search_by_title("Attention Is All You Need")

        # Should return at least the matching one
        assert len(results) >= 1
        assert results[0].title == "Attention Is All You Need"

    def test_search_empty_results(self) -> None:
        client = OpenAlexClient(offline=False)

        def mock_get(path: str, query: dict[str, str]) -> dict[str, Any] | None:
            return {"results": []}

        client._get = mock_get  # type: ignore[assignment]
        results = client.search_by_title("nonexistent paper xyz")
        assert results == []


class TestOpenAlexOutageLatch:
    """Test fail-fast outage latch."""

    def test_latch_prevents_repeated_calls(self) -> None:
        client = OpenAlexClient(offline=False)
        client._latched_unavailable = True

        result = client._get("/works", {})
        assert result is None

    def test_reset_outage_latch(self) -> None:
        client = OpenAlexClient(offline=False)
        client._latched_unavailable = True
        client.reset_outage_latch()
        assert client._latched_unavailable is False
