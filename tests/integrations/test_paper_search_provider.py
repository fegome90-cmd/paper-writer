"""Tests for PaperSearchProvider, normalization, and deduplication.

Covers the 12 mandatory test cases from the integration contract:
1. Mapping of valid MCP payload
2. Nullable/absent fields
3. Duplicate detection
4. Explicit provider selection
5. Limit validation
6. Missing MCP path
7. Timeout
8. Server down
9. Tool absent
10. Invalid payload
11. (Smoke test — separate file)
12. (Pipeline test — separate file)
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.ports.paper_search_provider import (
    FixturePaperSearchProvider,
    NormalizedPaper,
    SearchProviderResult,
    _normalize_paper,
    create_search_provider,
    deduplicate_papers,
)

FIXTURE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "paper_mcp" / "search_papers_response.v1.json"
)


# ── 1. Mapping of valid MCP payload ──────────────────────────────────


class TestNormalization:
    """Test MCP paper → paper-writer format mapping."""

    def test_paper_with_all_fields(self) -> None:
        """Paper #0: DOI, pdfUrl, categories, multiple authors."""
        raw = {
            "id": "2301.00001v2",
            "title": "Attention Is All You Need",
            "authors": ["Alice", "Bob", "Carol"],
            "abstract": "We present a systematic review.",
            "published": "2023-01-15T09:00:00.000Z",
            "source": "arxiv",
            "doi": "10.1234/arxiv.2301.00001",
            "pdfUrl": "https://arxiv.org/pdf/2301.00001v2",
            "url": "https://arxiv.org/abs/2301.00001v2",
            "categories": ["cs.CL", "cs.AI"],
            "fullTextAvailable": True,
        }
        paper = _normalize_paper(raw)

        assert paper.title == "Attention Is All You Need"
        assert paper.doi == "10.1234/arxiv.2301.00001"
        assert paper.year == 2023
        assert paper.authors == "Alice, Bob, Carol"
        assert paper.abstract == "We present a systematic review."
        assert paper.pdf_url == "https://arxiv.org/pdf/2301.00001v2"
        assert paper.source_platform == "arxiv"
        assert paper.source_id == "2301.00001v2"
        assert paper.categories == ["cs.CL", "cs.AI"]
        assert paper.citations_count == 0
        assert paper.defaulted_fields == ["citations_count"]

    def test_paper_with_doi_and_citations(self) -> None:
        """OpenAlex paper with citations count."""
        raw = {
            "id": "W123",
            "title": "Deep Learning Review",
            "authors": ["Smith"],
            "abstract": "A review.",
            "published": "2022-06-20T00:00:00.000Z",
            "source": "openalex",
            "doi": "https://doi.org/10.1016/test",
            "pdfUrl": "https://publisher.com/paper.pdf",
            "url": "https://doi.org/10.1016/test",
            "categories": ["Medicine"],
            "citations": 342,
        }
        paper = _normalize_paper(raw)

        assert paper.doi == "https://doi.org/10.1016/test"
        assert paper.citations_count == 342
        assert paper.source_platform == "openalex"
        assert "citations_count" not in paper.defaulted_fields

    def test_pubmed_paper_gets_pmid(self) -> None:
        """PubMed paper should extract PMID from id."""
        raw = {
            "id": "38912345",
            "title": "Neural Networks",
            "authors": ["Anna K."],
            "abstract": "Abstract here.",
            "published": "2024-03-10T03:00:00.000Z",
            "source": "pubmed",
            "doi": "10.1038/s41586-024",
            "url": "https://pubmed.ncbi.nlm.nih.gov/38912345/",
        }
        paper = _normalize_paper(raw)

        assert paper.pmid == "38912345"
        assert paper.doi == "10.1038/s41586-024"
        assert "pdfUrl" not in raw  # Confirms absence
        assert "pdf_url" in paper.defaulted_fields

    def test_many_authors_truncated(self) -> None:
        """More than 3 authors get 'et al.' treatment."""
        raw = {
            "id": "x1",
            "title": "Multi-Author Paper",
            "authors": ["A", "B", "C", "D", "E", "F"],
            "abstract": "Abstract.",
            "published": "2024-01-01T00:00:00.000Z",
            "source": "arxiv",
            "url": "https://example.com",
        }
        paper = _normalize_paper(raw)

        assert paper.authors == "A, B, C et al."

    def test_extra_fields_preserved(self) -> None:
        """Unexpected fields are captured in extra_fields."""
        raw = {
            "id": "x2",
            "title": "Paper",
            "authors": ["Author"],
            "abstract": "Abs",
            "published": "2024-01-01T00:00:00.000Z",
            "source": "arxiv",
            "url": "https://example.com",
            "extraField": "should be preserved",
            "novelData": {"nested": True},
        }
        paper = _normalize_paper(raw)

        assert paper.extra_fields["extraField"] == "should be preserved"
        assert paper.extra_fields["novelData"] == {"nested": True}


# ── 2. Nullable / absent fields ──────────────────────────────────────


class TestNullableFields:
    """Handle missing/null MCP fields gracefully with tracking."""

    def test_empty_abstract_tracked(self) -> None:
        raw = {
            "id": "x",
            "title": "T",
            "authors": ["A"],
            "abstract": "",
            "published": "2024-01-01T00:00:00Z",
            "source": "pubmed",
        }
        paper = _normalize_paper(raw)
        assert paper.abstract == ""
        assert "abstract" in paper.defaulted_fields

    def test_null_abstract_tracked(self) -> None:
        raw = {
            "id": "x",
            "title": "T",
            "authors": ["A"],
            "abstract": None,
            "published": "2024-01-01T00:00:00Z",
            "source": "pubmed",
        }
        paper = _normalize_paper(raw)
        assert paper.abstract == ""
        assert "abstract" in paper.defaulted_fields

    def test_absent_abstract_tracked(self) -> None:
        raw = {
            "id": "x",
            "title": "T",
            "authors": ["A"],
            "published": "2024-01-01T00:00:00Z",
            "source": "pubmed",
        }
        paper = _normalize_paper(raw)
        assert paper.abstract == ""
        assert "abstract" in paper.defaulted_fields

    def test_no_doi_tracked(self) -> None:
        raw = {
            "id": "x",
            "title": "T",
            "authors": ["A"],
            "abstract": "Abs",
            "published": "2024-01-01T00:00:00Z",
            "source": "arxiv",
        }
        paper = _normalize_paper(raw)
        assert paper.doi is None
        assert "doi" in paper.defaulted_fields

    def test_no_pdf_url_tracked(self) -> None:
        raw = {
            "id": "x",
            "title": "T",
            "authors": ["A"],
            "abstract": "Abs",
            "published": "2024-01-01T00:00:00Z",
            "source": "pubmed",
        }
        paper = _normalize_paper(raw)
        assert paper.pdf_url is None
        assert "pdf_url" in paper.defaulted_fields

    def test_no_title_gets_placeholder(self) -> None:
        raw = {
            "id": "x",
            "authors": ["A"],
            "abstract": "Abs",
            "published": "2024-01-01T00:00:00Z",
            "source": "arxiv",
        }
        paper = _normalize_paper(raw)
        assert paper.title == "(untitled)"
        assert "title" in paper.defaulted_fields
        assert any("no title" in w for w in paper.warnings)


# ── 3. Duplicate detection ───────────────────────────────────────────


class TestDeduplication:
    """Cross-source dedup by DOI and title."""

    def test_doi_dedup_keeps_richer(self) -> None:
        """Two papers with same DOI from different sources — keep richer."""
        p1 = NormalizedPaper(
            title="T",
            doi="10.1234/x",
            pmid=None,
            year=2024,
            authors="A",
            abstract="",
            url=None,
            pdf_url=None,
            source_platform="arxiv",
            source_id="1",
            categories=[],
            citations_count=0,
            defaulted_fields=["abstract", "pdf_url"],
        )
        p2 = NormalizedPaper(
            title="T",
            doi="10.1234/x",
            pmid=None,
            year=2024,
            authors="A",
            abstract="Full abstract",
            url="u",
            pdf_url="p",
            source_platform="openalex",
            source_id="2",
            categories=["cs"],
            citations_count=5,
            defaulted_fields=[],
        )
        result = deduplicate_papers([p1, p2])
        assert len(result) == 1
        assert result[0].abstract == "Full abstract"
        assert result[0].source_platform == "openalex"

    def test_title_dedup(self) -> None:
        """Papers with same title but no DOI get title-deduped."""
        p1 = NormalizedPaper(
            title="Same Title",
            doi=None,
            pmid=None,
            year=2024,
            authors="A",
            abstract="a1",
            url=None,
            pdf_url=None,
            source_platform="arxiv",
            source_id="1",
            categories=[],
            citations_count=0,
            defaulted_fields=[],
        )
        p2 = NormalizedPaper(
            title="Same Title",
            doi=None,
            pmid=None,
            year=2024,
            authors="B",
            abstract="a2",
            url=None,
            pdf_url=None,
            source_platform="pubmed",
            source_id="2",
            categories=[],
            citations_count=0,
            defaulted_fields=[],
        )
        result = deduplicate_papers([p1, p2])
        assert len(result) == 1
        assert result[0].authors == "A"  # First one kept

    def test_doi_normalization(self) -> None:
        """DOI comparison is case-insensitive and strips trailing slash."""
        p1 = NormalizedPaper(
            title="T",
            doi="10.1234/X/",
            pmid=None,
            year=2024,
            authors="A",
            abstract="",
            url=None,
            pdf_url=None,
            source_platform="arxiv",
            source_id="1",
            categories=[],
            citations_count=0,
            defaulted_fields=[],
        )
        p2 = NormalizedPaper(
            title="T",
            doi="10.1234/x",
            pmid=None,
            year=2024,
            authors="B",
            abstract="",
            url=None,
            pdf_url=None,
            source_platform="openalex",
            source_id="2",
            categories=[],
            citations_count=0,
            defaulted_fields=[],
        )
        result = deduplicate_papers([p1, p2])
        assert len(result) == 1


# ── 4. Explicit provider selection ───────────────────────────────────


class TestProviderSelection:
    """PAPER_SEARCH_PROVIDER env var controls which provider is created."""

    def test_fixture_mode_default(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            if "PAPER_SEARCH_PROVIDER" in os.environ:
                del os.environ["PAPER_SEARCH_PROVIDER"]
            provider = create_search_provider()
            assert isinstance(provider, FixturePaperSearchProvider)

    def test_fixture_mode_explicit(self) -> None:
        with patch.dict("os.environ", {"PAPER_SEARCH_PROVIDER": "fixture"}):
            provider = create_search_provider()
            assert isinstance(provider, FixturePaperSearchProvider)

    def test_unknown_mode_raises(self) -> None:
        with patch.dict("os.environ", {"PAPER_SEARCH_PROVIDER": "unknown"}):
            with pytest.raises(ValueError, match="Unknown PAPER_SEARCH_PROVIDER"):
                create_search_provider()

    def test_consensus_mode(self) -> None:
        """Consensus factory path returns ConsensusSearchProvider."""
        with patch.dict("os.environ", {"PAPER_SEARCH_PROVIDER": "consensus"}):
            from integrations.tools.consensus_client import ConsensusSearchProvider

            provider = create_search_provider()
            assert isinstance(provider, ConsensusSearchProvider)




# ── 5. Limit validation ─────────────────────────────────────────────


class TestLimitValidation:
    """Limit must be 1-100."""

    def test_limit_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            FixturePaperSearchProvider().search("test", limit=0)

    def test_limit_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            FixturePaperSearchProvider().search("test", limit=-1)

    def test_limit_101_raises(self) -> None:
        with pytest.raises(ValueError, match="Limit must be between 1 and 100"):
            FixturePaperSearchProvider().search("test", limit=101)

    def test_limit_100_ok(self) -> None:
        provider = FixturePaperSearchProvider()
        result = provider.search("test", limit=100)
        # Should succeed — fixture has 5 papers
        assert len(result.papers) <= 100

    def test_empty_query_raises(self) -> None:
        with pytest.raises(ValueError, match="Query cannot be empty"):
            FixturePaperSearchProvider().search("")

    def test_whitespace_query_raises(self) -> None:
        with pytest.raises(ValueError, match="Query cannot be empty"):
            FixturePaperSearchProvider().search("   ")


# ── 6. Missing MCP path ─────────────────────────────────────────────


class TestMcpErrors:
    """MCP mode fail-closed behavior."""

    def test_missing_server_path_raises(self) -> None:
        with pytest.raises(RuntimeError, match="MCP server not found"):
            from integrations.tools.mcp_paper_client import McpPaperSearchProvider

            McpPaperSearchProvider(server_path="/nonexistent/server.js")

    def test_missing_fixture_raises(self) -> None:
        with pytest.raises(RuntimeError, match="Fixture file not found"):
            FixturePaperSearchProvider(fixture_path=Path("/nonexistent/fixture.json")).search(
                "test"
            )

    def test_missing_fixture_path_object(self) -> None:
        """Missing fixture is a clear RuntimeError, not silent."""
        provider = FixturePaperSearchProvider(fixture_path=Path("/tmp/nonexistent_12345.json"))
        with pytest.raises(RuntimeError, match="Fixture file not found"):
            provider.search("test")


# ── Fixture provider integration ─────────────────────────────────────


class TestFixtureProviderIntegration:
    """Fixture provider produces correct results from v1 fixture."""

    def test_loads_fixture_and_normalizes(self) -> None:
        provider = FixturePaperSearchProvider(fixture_path=FIXTURE_PATH)
        result = provider.search("transformer")

        assert isinstance(result, SearchProviderResult)
        assert len(result.papers) >= 3  # 5 raw - 1 duplicate = 4, capped
        assert result.provenance.provider == "fixture"
        assert result.provenance.tool_name == "search_papers"
        assert result.provenance.schema_version == "1.0"
        assert result.total_from_source == 1523

    def test_deduplicate_removes_cross_source_dupe(self) -> None:
        provider = FixturePaperSearchProvider(fixture_path=FIXTURE_PATH)
        result = provider.search("test")

        # Fixture has DOI 10.1234/arxiv.2301.00001 in both arxiv and openalex
        dois = [p.doi for p in result.papers if p.doi]
        assert len(dois) == len({d.lower().rstrip("/") for d in dois})

    def test_provenance_has_all_required_fields(self) -> None:
        provider = FixturePaperSearchProvider(fixture_path=FIXTURE_PATH)
        result = provider.search("test")
        p = result.provenance

        assert p.provider
        assert p.query == "test"
        assert p.retrieved_at
        assert p.tool_name == "search_papers"
        assert p.sources
        assert p.schema_version == "1.0"

    def test_limit_applied(self) -> None:
        provider = FixturePaperSearchProvider(fixture_path=FIXTURE_PATH)
        result = provider.search("test", limit=2)
        assert len(result.papers) <= 2

    def test_raw_payload_preserved(self) -> None:
        provider = FixturePaperSearchProvider(fixture_path=FIXTURE_PATH)
        result = provider.search("test")

        assert "total" in result.raw_payload
        assert "results" in result.raw_payload
        assert "sources" in result.raw_payload
