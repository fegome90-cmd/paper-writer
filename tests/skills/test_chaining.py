"""Tests for iterative search chaining module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestApiGet:
    """_api_get() — rate-limited Semantic Scholar API calls."""

    def test_returns_parsed_json(self) -> None:
        from skills.imported.literature_search.chaining import _api_get

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"data": [1, 2]}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "skills.imported.literature_search.chaining.urlopen", return_value=mock_response
        ):
            result = _api_get("https://api.semanticscholar.org/test")
            assert result == {"data": [1, 2]}

    def test_returns_none_on_http_error(self) -> None:
        from urllib.error import HTTPError

        from skills.imported.literature_search.chaining import _api_get

        with patch(
            "skills.imported.literature_search.chaining.urlopen",
            side_effect=HTTPError("url", 429, "rate limited", {}, None),
        ):
            assert _api_get("https://api.semanticscholar.org/test") is None

    def test_returns_none_on_timeout(self) -> None:
        from skills.imported.literature_search.chaining import _api_get

        with patch(
            "skills.imported.literature_search.chaining.urlopen", side_effect=TimeoutError()
        ):
            assert _api_get("https://api.semanticscholar.org/test") is None

    def test_sends_api_key_if_set(self) -> None:
        from skills.imported.literature_search.chaining import _api_get

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"S2_API_KEY": "test-key"}):
            with patch(
                "skills.imported.literature_search.chaining.urlopen", return_value=mock_response
            ) as mock_urlopen:
                _api_get("https://api.semanticscholar.org/test")
                req = mock_urlopen.call_args[0][0]
                # Request stores headers with capitalized first letter
                assert (
                    req.get_header("X-api-key") == "test-key"
                    or req.get_header("x-api-key") == "test-key"
                )


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

    def test_falls_back_to_top_level_doi(self) -> None:
        """Search pipeline format: doi is top-level, not in externalIds."""
        from skills.imported.literature_search.chaining import resolve_paper_id

        paper = {"title": "Test", "doi": "10.1234/test"}
        assert resolve_paper_id(paper) == "DOI:10.1234/test"

    def test_falls_back_to_top_level_arxiv_id(self) -> None:
        """Search pipeline format: arxiv_id is top-level."""
        from skills.imported.literature_search.chaining import resolve_paper_id

        paper = {"title": "Test", "arxiv_id": "2406.14497"}
        assert resolve_paper_id(paper) == "ArXiv:2406.14497"

    def test_falls_back_to_s2_id(self) -> None:
        """Chaining output format: s2_id from s2_paper_to_dict."""
        from skills.imported.literature_search.chaining import resolve_paper_id

        paper = {"title": "Test", "s2_id": "abc123"}
        assert resolve_paper_id(paper) == "abc123"


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
        with (
            patch("skills.imported.literature_search.chaining.get_references") as mock_refs,
            patch("skills.imported.literature_search.chaining.get_citations") as mock_cites,
        ):
            mock_refs.return_value = [
                {
                    "paperId": "ref1",
                    "title": "retrieval augmented code generation paper",
                    "year": 2023,
                    "externalIds": {},
                },
                {
                    "paperId": "ref2",
                    "title": "code generation with retrieval",
                    "year": 2022,
                    "externalIds": {},
                },
            ]
            mock_cites.return_value = [
                {
                    "paperId": "cite1",
                    "title": "new retrieval code generation study",
                    "year": 2025,
                    "externalIds": {},
                },
            ]

            result = iterative_search(
                seeds, query="retrieval augmented code generation", max_rounds=1
            )
            assert result["total_unique"] == 4  # 1 seed + 2 refs + 1 cite
            assert result["stats"]["rounds_completed"] == 1

    def test_respects_max_papers(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [{"paperId": "seed1", "title": "test", "doi": "10.1/a"}]

        with (
            patch("skills.imported.literature_search.chaining.get_references") as mock_refs,
            patch("skills.imported.literature_search.chaining.get_citations") as mock_cites,
        ):
            mock_refs.return_value = [
                {
                    "paperId": f"ref{i}",
                    "title": f"retrieval code generation paper {i}",
                    "year": 2024,
                    "externalIds": {},
                }
                for i in range(50)
            ]
            mock_cites.return_value = []

            result = iterative_search(
                seeds, query="retrieval code generation", max_rounds=2, max_papers=10
            )
            assert result["total_unique"] <= 10

    def test_handles_api_failure_gracefully(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [{"paperId": "seed1", "title": "test", "doi": "10.1/a"}]

        with (
            patch("skills.imported.literature_search.chaining.get_references", return_value=[]),
            patch("skills.imported.literature_search.chaining.get_citations", return_value=[]),
        ):
            result = iterative_search(seeds, query="test query", max_rounds=1)
            assert result["total_unique"] == 1  # just the seed
            assert result["stats"]["saturation"] is True

    def test_provenance_tracks_sources(self) -> None:
        from skills.imported.literature_search.chaining import iterative_search

        seeds = [{"paperId": "seed1", "title": "retrieval code gen", "doi": "10.1/a"}]

        with (
            patch("skills.imported.literature_search.chaining.get_references") as mock_refs,
            patch("skills.imported.literature_search.chaining.get_citations") as mock_cites,
        ):
            mock_refs.return_value = [
                {
                    "paperId": "ref1",
                    "title": "retrieval code generation",
                    "year": 2023,
                    "externalIds": {},
                },
            ]
            mock_cites.return_value = []

            result = iterative_search(seeds, query="retrieval code generation", max_rounds=1)
            prov = result["provenance"]
            seed_prov = [p for p in prov if p["source"] == "seed"]
            chain_prov = [p for p in prov if p["source"] == "backward"]
            assert len(seed_prov) == 1
            assert len(chain_prov) == 1
            assert chain_prov[0]["chain_from"] == "seed1"


class TestDedupByDoiAndTitle:
    """Test DOI + title fuzzy dedup in iterative_search."""

    def _make_seed(self) -> list[dict[str, Any]]:
        return [
            {
                "title": "Attention is all you need",
                "doi": "10.1/seed1",
                "year": 2017,
                "abstract": "Transformer architecture for sequence transduction.",
                "citation_count": 80000,
                "venue": "NeurIPS",
                "scoring": {"final_score": 8.5, "tier": "Tier 1"},
            },
        ]

    def test_dedup_by_doi(self, tmp_path: Path) -> None:
        """Same DOI via different paperId is filtered."""
        from skills.imported.literature_search.chaining import (
            _cache_put,
            iterative_search,
        )

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Reference with same DOI as seed but different paperId
        refs = {
            "data": [
                {
                    "citedPaper": {
                        "paperId": "DUPE_DIFFERENT_PID",
                        "title": "Attention is all you need (published version)",
                        "year": 2017,
                        "abstract": "Transformer architecture for sequence transduction.",
                        "externalIds": {"DOI": "10.1/seed1"},
                        "citationCount": 80000,
                        "venue": "NeurIPS",
                    }
                },
            ]
        }
        cites: dict[str, list[dict[str, object]]] = {"data": []}
        seed_pid = "DOI:10.1/seed1"
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/references?limit=20&fields=title,year,abstract,externalIds,citationCount",
            refs,
            cache_dir=cache_dir,
        )
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/citations?limit=20&fields=title,year,abstract,externalIds,citationCount",
            cites,
            cache_dir=cache_dir,
        )

        result = iterative_search(
            self._make_seed(),
            query="transformer attention",
            max_rounds=1,
            cache_dir=cache_dir,
        )
        # Should only have the seed — DOI duplicate filtered
        assert result["total_unique"] == 1

    def test_dedup_by_title_case_insensitive(self, tmp_path: Path) -> None:
        """Same title with different casing is filtered."""
        from skills.imported.literature_search.chaining import (
            _cache_put,
            iterative_search,
        )

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        refs = {
            "data": [
                {
                    "citedPaper": {
                        "paperId": "TITLE_DUPE",
                        "title": "ATTENTION IS ALL YOU NEED",
                        "year": 2017,
                        "abstract": "Transformer architecture for sequence transduction.",
                        "externalIds": {"DOI": "10.1/different-doi"},
                        "citationCount": 80000,
                        "venue": "NeurIPS",
                    }
                },
            ]
        }
        cites: dict[str, list[dict[str, object]]] = {"data": []}
        seed_pid = "DOI:10.1/seed1"
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/references?limit=20&fields=title,year,abstract,externalIds,citationCount",
            refs,
            cache_dir=cache_dir,
        )
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/citations?limit=20&fields=title,year,abstract,externalIds,citationCount",
            cites,
            cache_dir=cache_dir,
        )

        result = iterative_search(
            self._make_seed(),
            query="transformer attention",
            max_rounds=1,
            cache_dir=cache_dir,
        )
        # Title dedup should catch the case-insensitive duplicate
        assert result["total_unique"] == 1

    def test_dedup_by_title_punctuation(self, tmp_path: Path) -> None:
        """Title with extra punctuation/whitespace is still deduped."""
        from skills.imported.literature_search.chaining import (
            _cache_put,
            iterative_search,
        )

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        refs = {
            "data": [
                {
                    "citedPaper": {
                        "paperId": "PUNCT_DUPE",
                        "title": "Attention  is  all  you  need!",
                        "year": 2017,
                        "abstract": "Transformer architecture for sequence transduction.",
                        "externalIds": {"DOI": "10.1/punct-doi"},
                        "citationCount": 80000,
                        "venue": "NeurIPS",
                    }
                },
            ]
        }
        cites: dict[str, list[dict[str, object]]] = {"data": []}
        seed_pid = "DOI:10.1/seed1"
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/references?limit=20&fields=title,year,abstract,externalIds,citationCount",
            refs,
            cache_dir=cache_dir,
        )
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/citations?limit=20&fields=title,year,abstract,externalIds,citationCount",
            cites,
            cache_dir=cache_dir,
        )

        result = iterative_search(
            self._make_seed(),
            query="transformer attention",
            max_rounds=1,
            cache_dir=cache_dir,
        )
        # Punctuation-stripped title should match
        assert result["total_unique"] == 1

    def test_different_paper_passes(self, tmp_path: Path) -> None:
        """Genuinely different papers are not deduped."""
        from skills.imported.literature_search.chaining import (
            _cache_put,
            iterative_search,
        )

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        refs = {
            "data": [
                {
                    "citedPaper": {
                        "paperId": "NEW_PAPER",
                        "title": "Scaling laws for neural language models",
                        "year": 2023,
                        "abstract": "Empirical scaling laws for language model performance.",
                        "externalIds": {"DOI": "10.1/scaling"},
                        "citationCount": 2000,
                        "venue": "ICML",
                    }
                },
            ]
        }
        cites: dict[str, list[dict[str, object]]] = {"data": []}
        seed_pid = "DOI:10.1/seed1"
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/references?limit=20&fields=title,year,abstract,externalIds,citationCount",
            refs,
            cache_dir=cache_dir,
        )
        _cache_put(
            f"https://api.semanticscholar.org/graph/v1/paper/{seed_pid}/citations?limit=20&fields=title,year,abstract,externalIds,citationCount",
            cites,
            cache_dir=cache_dir,
        )

        result = iterative_search(
            self._make_seed(),
            query="transformer attention language models",
            max_rounds=1,
            cache_dir=cache_dir,
        )
        # Seed + new paper = 2
        assert result["total_unique"] == 2


class TestR2BugHuntFixes:
    """Tests for bugs found by Round 2 bug hunt."""

    def test_bh1_url_encodes_title_fallbacks(self) -> None:
        """R2-BH1: Paper titles with spaces are URL-encoded in S2 API calls."""
        from skills.imported.literature_search.chaining import _encode_paper_id

        # S2 IDs (40-char hex) should NOT be encoded
        assert _encode_paper_id("a" * 40) == "a" * 40

        # DOI: prefix should NOT be encoded
        assert _encode_paper_id("DOI:10.1234/test") == "DOI:10.1234/test"

        # ArXiv: prefix should NOT be encoded
        assert _encode_paper_id("ArXiv:2301.00001") == "ArXiv:2301.00001"

        # Title with spaces SHOULD be encoded
        encoded = _encode_paper_id("Reinforcement Learning for Robotic Manipulation")
        assert " " not in encoded
        assert "%20" in encoded or "+" in encoded  # URL encoding
        assert "Reinforcement" in encoded

    def test_bh1_url_encoding_prevents_invalid_url(self) -> None:
        """R2-BH1: URL-encoded titles don't cause InvalidURL crashes."""
        from skills.imported.literature_search.chaining import _encode_paper_id

        title = "Reinforcement Learning for Robotic Manipulation: Benchmark Results"
        encoded = _encode_paper_id(title)

        # The URL should not contain spaces or control characters
        url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded}/references"
        assert " " not in url
        assert ":" not in url.split("graph/v1/paper/")[1].split("/")[0]  # No raw colons after paper/

    def test_bh2_invalid_tier_rejected(self, tmp_path: Path) -> None:
        """R2-BH2: Invalid tier names raise ValueError."""
        from skills.imported.literature_search.search import screen

        # Create minimal raw_results.json
        raw_path = tmp_path / "raw_results.json"
        raw_path.write_text(json.dumps({"papers": []}))

        with pytest.raises(ValueError, match="Invalid min_tier"):
            screen(tmp_path, tmp_path, min_tier="InvalidTier")

    def test_bh2_valid_tiers_accepted(self, tmp_path: Path) -> None:
        """R2-BH2: All valid tier names are accepted."""
        from skills.imported.literature_search.search import screen

        raw_path = tmp_path / "raw_results.json"
        raw_path.write_text(json.dumps({"papers": []}))

        for tier in ["Tier 1", "Tier 2", "Tier 3", "Discard"]:
            result = screen(tmp_path, tmp_path, min_tier=tier)
            assert "artifacts" in result

    def test_bh3_chain_params_validated(self) -> None:
        """R2-BH3: CLI rejects invalid chain parameters."""
        import subprocess

        for args, expected_error in [
            ("--max-rounds 0", "--max-rounds"),
            ("--max-rounds -1", "--max-rounds"),
            ("--max-papers 0", "--max-papers"),
            ("--max-papers -1", "--max-papers"),
            ("--relevance-threshold -0.5", "--relevance-threshold"),
            ("--relevance-threshold 0", "--relevance-threshold"),
            ("--relevance-threshold 2.0", "--relevance-threshold"),
        ]:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "cli.paper.main", "chain"] + args.split(),
                capture_output=True,
                text=True,
                cwd="/Users/felipe_gonzalez/Developer/paper-writer",
                timeout=30,
            )
            assert result.returncode != 0, f"Expected failure for {args}"
            assert expected_error in result.stderr, f"Expected '{expected_error}' in stderr for {args}, got: {result.stderr}"
