"""Tests for iterative search chaining module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


class TestApiGet:
    """_api_get() — rate-limited Semantic Scholar API calls."""

    def test_returns_parsed_json(self) -> None:
        from skills.imported.literature_search.chaining import _api_get

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"data": [1, 2]}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("skills.imported.literature_search.chaining.urlopen", return_value=mock_response):
            result = _api_get("https://api.semanticscholar.org/test")
            assert result == {"data": [1, 2]}

    def test_returns_none_on_http_error(self) -> None:
        from urllib.error import HTTPError

        from skills.imported.literature_search.chaining import _api_get

        with patch("skills.imported.literature_search.chaining.urlopen", side_effect=HTTPError("url", 429, "rate limited", {}, None)):
            assert _api_get("https://api.semanticscholar.org/test") is None

    def test_returns_none_on_timeout(self) -> None:
        from skills.imported.literature_search.chaining import _api_get

        with patch("skills.imported.literature_search.chaining.urlopen", side_effect=TimeoutError()):
            assert _api_get("https://api.semanticscholar.org/test") is None

    def test_sends_api_key_if_set(self) -> None:
        from skills.imported.literature_search.chaining import _api_get

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"S2_API_KEY": "test-key"}):
            with patch("skills.imported.literature_search.chaining.urlopen", return_value=mock_response) as mock_urlopen:
                _api_get("https://api.semanticscholar.org/test")
                req = mock_urlopen.call_args[0][0]
                # Request stores headers with capitalized first letter
                assert req.get_header("X-api-key") == "test-key" or req.get_header("x-api-key") == "test-key"


class TestSearchByKeyword:
    """search_by_keyword() — keyword search via S2 API."""

    def test_returns_paper_list(self) -> None:
        from skills.imported.literature_search.chaining import search_by_keyword

        mock_data = {
            "data": [
                {"paperId": "abc", "title": "RAG for code"},
                {"paperId": "def", "title": "Code generation"},
            ]
        }

        with patch("skills.imported.literature_search.chaining._api_get", return_value=mock_data):
            results = search_by_keyword("retrieval augmented code generation")
            assert len(results) == 2
            assert results[0]["title"] == "RAG for code"

    def test_returns_empty_on_failure(self) -> None:
        from skills.imported.literature_search.chaining import search_by_keyword

        with patch("skills.imported.literature_search.chaining._api_get", return_value=None):
            assert search_by_keyword("test") == []


class TestGetReferences:
    """get_references() — backward chaining."""

    def test_extracts_cited_papers(self) -> None:
        from skills.imported.literature_search.chaining import get_references

        mock_data = {
            "data": [
                {"citedPaper": {"paperId": "ref1", "title": "Paper A"}},
                {"citedPaper": {"paperId": "ref2", "title": "Paper B"}},
            ]
        }

        with patch("skills.imported.literature_search.chaining._api_get", return_value=mock_data):
            refs = get_references("abc123")
            assert len(refs) == 2

    def test_filters_null_entries(self) -> None:
        from skills.imported.literature_search.chaining import get_references

        mock_data = {
            "data": [
                {"citedPaper": {"paperId": "ref1", "title": "Paper A"}},
                {"citedPaper": {"paperId": None, "title": None}},  # null entry
            ]
        }

        with patch("skills.imported.literature_search.chaining._api_get", return_value=mock_data):
            refs = get_references("abc123")
            assert len(refs) == 1


class TestGetCitations:
    """get_citations() — forward chaining."""

    def test_extracts_citing_papers(self) -> None:
        from skills.imported.literature_search.chaining import get_citations

        mock_data = {
            "data": [
                {"citingPaper": {"paperId": "cite1", "title": "New paper"}},
            ]
        }

        with patch("skills.imported.literature_search.chaining._api_get", return_value=mock_data):
            cites = get_citations("abc123")
            assert len(cites) == 1
            assert cites[0]["title"] == "New paper"


class TestResolvePaperId:
    """resolve_paper_id() — ID resolution from paper dict."""

    def test_prefers_s2_id(self) -> None:
        from skills.imported.literature_search.chaining import resolve_paper_id

        paper = {"paperId": "s2abc", "externalIds": {"DOI": "10.1234/test"}}
        assert resolve_paper_id(paper) == "s2abc"

    def test_falls_back_to_doi(self) -> None:
        from skills.imported.literature_search.chaining import resolve_paper_id

        paper = {"externalIds": {"DOI": "10.1234/test"}}
        assert resolve_paper_id(paper) == "DOI:10.1234/test"

    def test_falls_back_to_arxiv(self) -> None:
        from skills.imported.literature_search.chaining import resolve_paper_id

        paper = {"externalIds": {"ArXiv": "2406.14497"}}
        assert resolve_paper_id(paper) == "ArXiv:2406.14497"

    def test_returns_none_for_nothing(self) -> None:
        from skills.imported.literature_search.chaining import resolve_paper_id

        assert resolve_paper_id({}) is None


class TestS2PaperToDict:
    """s2_paper_to_dict() — normalize S2 paper to our format."""

    def test_normalizes_full_paper(self) -> None:
        from skills.imported.literature_search.chaining import s2_paper_to_dict

        s2_paper = {
            "paperId": "abc",
            "title": "Test Paper",
            "year": 2024,
            "abstract": "An abstract.",
            "externalIds": {"DOI": "10.1234/test", "ArXiv": "2406.14497"},
            "venue": "ICSE",
            "citationCount": 42,
        }
        result = s2_paper_to_dict(s2_paper, source="backward_chaining")
        assert result["title"] == "Test Paper"
        assert result["doi"] == "10.1234/test"
        assert result["arxiv_id"] == "2406.14497"
        assert result["venue"] == "ICSE"
        assert result["citation_count"] == 42
        assert result["source"] == "backward_chaining"


class TestIterativeSearch:
    """iterative_search() — full chaining loop with mocks."""

    def test_expand_from_seeds(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [
            {"paperId": "seed1", "title": "RAG code generation", "doi": "10.1/a"},
        ]

        # Mock: get_references returns 2 refs, get_citations returns 1 cite
        with patch("skills.imported.literature_search.chaining.get_references") as mock_refs, \
             patch("skills.imported.literature_search.chaining.get_citations") as mock_cites:

            mock_refs.return_value = [
                {"paperId": "ref1", "title": "retrieval augmented code generation paper", "year": 2023, "externalIds": {}},
                {"paperId": "ref2", "title": "code generation with retrieval", "year": 2022, "externalIds": {}},
            ]
            mock_cites.return_value = [
                {"paperId": "cite1", "title": "new retrieval code generation study", "year": 2025, "externalIds": {}},
            ]

            result = iterative_search(seeds, query="retrieval augmented code generation", max_rounds=1)
            assert result["total_unique"] == 4  # 1 seed + 2 refs + 1 cite
            assert result["stats"]["rounds_completed"] == 1

    def test_respects_max_papers(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [{"paperId": "seed1", "title": "test", "doi": "10.1/a"}]

        with patch("skills.imported.literature_search.chaining.get_references") as mock_refs, \
             patch("skills.imported.literature_search.chaining.get_citations") as mock_cites:

            mock_refs.return_value = [
                {"paperId": f"ref{i}", "title": f"retrieval code generation paper {i}", "year": 2024, "externalIds": {}}
                for i in range(50)
            ]
            mock_cites.return_value = []

            result = iterative_search(seeds, query="retrieval code generation", max_rounds=2, max_papers=10)
            assert result["total_unique"] <= 10

    def test_handles_api_failure_gracefully(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [{"paperId": "seed1", "title": "test", "doi": "10.1/a"}]

        with patch("skills.imported.literature_search.chaining.get_references", return_value=[]), \
             patch("skills.imported.literature_search.chaining.get_citations", return_value=[]):

            result = iterative_search(seeds, query="test query", max_rounds=1)
            assert result["total_unique"] == 1  # just the seed
            assert result["stats"]["saturation"] is True

    def test_provenance_tracks_sources(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [{"paperId": "seed1", "title": "retrieval code gen", "doi": "10.1/a"}]

        with patch("skills.imported.literature_search.chaining.get_references") as mock_refs, \
             patch("skills.imported.literature_search.chaining.get_citations") as mock_cites:

            mock_refs.return_value = [
                {"paperId": "ref1", "title": "retrieval code generation", "year": 2023, "externalIds": {}},
            ]
            mock_cites.return_value = []

            result = iterative_search(seeds, query="retrieval code generation", max_rounds=1)
            prov = result["provenance"]
            seed_prov = [p for p in prov if p["source"] == "seed"]
            chain_prov = [p for p in prov if p["source"] == "backward"]
            assert len(seed_prov) == 1
            assert len(chain_prov) == 1
            assert chain_prov[0]["chain_from"] == "seed1"
