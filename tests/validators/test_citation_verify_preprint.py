"""Tests for citation_verify preprint venue detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from clients.arxiv import ArxivResult
from clients.crossref import CrossrefResult
from clients.openalex import OpenAlexResult
from clients.semantic_scholar import S2Result
from validators.citation_verify import PREPRINT_VENUES, CitationVerifyValidator


class TestDetectPreprint:
    """Test _detect_preprint helper."""

    def setup_method(self) -> None:
        self.validator = CitationVerifyValidator(offline=True)

    def test_arxiv_detected(self) -> None:
        cr = CrossrefResult(found=True, venue="arXiv", year=2024, score=0.95)
        s2 = S2Result(found=True, venue="arXiv", year=2024, score=0.95)
        result = self.validator._detect_preprint(cr, s2)
        assert result["preprint_flag"] is True
        assert "arxiv" in result["preprint_venue"]

    def test_biorxiv_detected(self) -> None:
        cr = CrossrefResult(found=True, venue="bioRxiv", year=2025, score=0.90)
        s2 = S2Result(found=False)
        result = self.validator._detect_preprint(cr, s2)
        assert result["preprint_flag"] is True
        assert "biorxiv" in result["preprint_venue"]

    def test_nature_not_flagged(self) -> None:
        cr = CrossrefResult(found=True, venue="Nature", year=2023, score=0.95)
        s2 = S2Result(found=True, venue="Nature", year=2023, score=0.95)
        result = self.validator._detect_preprint(cr, s2)
        assert result == {}

    def test_none_results_return_empty(self) -> None:
        result = self.validator._detect_preprint(None, None)
        assert result == {}

    def test_ssrn_in_longer_venue_name(self) -> None:
        cr = CrossrefResult(found=True, venue="SSRN Electronic Journal", year=2024, score=0.85)
        s2 = S2Result(found=True, venue="SSRN", year=2024, score=0.85)
        result = self.validator._detect_preprint(cr, s2)
        assert result["preprint_flag"] is True

    def test_medrxiv_detected(self) -> None:
        cr = CrossrefResult(found=False)
        s2 = S2Result(found=True, venue="medRxiv", year=2024, score=0.88)
        result = self.validator._detect_preprint(cr, s2)
        assert result["preprint_flag"] is True
        assert result["preprint_year"] == 2024

    def test_not_found_result_ignored(self) -> None:
        cr = CrossrefResult(found=False)
        s2 = S2Result(found=False)
        result = self.validator._detect_preprint(cr, s2)
        assert result == {}

    def test_year_from_first_available_source(self) -> None:
        cr = CrossrefResult(found=True, venue="ChemRxiv", year=2023, score=0.90)
        s2 = S2Result(found=True, venue="ChemRxiv", year=None, score=0.90)
        result = self.validator._detect_preprint(cr, s2)
        assert result["preprint_year"] == 2023

    def test_venue_without_year(self) -> None:
        cr = CrossrefResult(found=True, venue="EarthArXiv", year=None, score=0.90)
        s2 = S2Result(found=False)
        result = self.validator._detect_preprint(cr, s2)
        assert result["preprint_flag"] is True
        assert result["preprint_year"] is None


class TestPreprintVenues:
    """Test PREPRINT_VENUES constant."""

    def test_known_preprint_count(self) -> None:
        assert len(PREPRINT_VENUES) >= 12

    def test_major_preprints_present(self) -> None:
        for venue in ("arxiv", "biorxiv", "medrxiv", "ssrn", "chemrxiv"):
            assert venue in PREPRINT_VENUES

    def test_is_frozen(self) -> None:
        assert isinstance(PREPRINT_VENUES, frozenset)


class TestVerifySinglePreprint:
    """Test verify_single with preprint detection."""

    def setup_method(self) -> None:
        self.validator = CitationVerifyValidator(
            offline=False,
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False)),
            ),
            openalex_client=MagicMock(
                verify_doi=MagicMock(return_value=OpenAlexResult(found=False)),
            ),
        )
        # Mock the query methods to return preprint results
        self._arxiv_cr = CrossrefResult(
            found=True,
            doi="10.1234/arxiv",
            title="ArXiv Paper",
            venue="arXiv",
            year=2024,
            score=0.95,
        )
        self._arxiv_s2 = S2Result(
            found=True,
            paper_id="ArXivId",
            title="ArXiv Paper",
            venue="arXiv",
            year=2024,
            score=0.95,
        )

    def test_verified_preprint_produces_finding(self) -> None:
        """Verified citation from arXiv gets preprint_source finding."""
        self.validator._query_crossref = lambda _: self._arxiv_cr  # type: ignore[assignment]
        self.validator._query_s2 = lambda _: self._arxiv_s2  # type: ignore[assignment]

        citation = {"doi": "10.1234/arxiv", "title": "ArXiv Paper", "line": 1}
        finding = self.validator.verify_single(citation)

        assert finding is not None
        assert finding["rule_id"] == "citation_verify.preprint_source"
        assert finding["severity"] == "P2"
        assert finding["evidence"]["preprint_flag"] is True

    def test_verified_journal_produces_no_finding(self) -> None:
        """Verified citation from Nature produces no finding."""
        cr = CrossrefResult(
            found=True,
            doi="10.1234/nature",
            title="Nature Paper",
            venue="Nature",
            year=2023,
            score=0.98,
        )
        s2 = S2Result(
            found=True,
            paper_id="NatureId",
            title="Nature Paper",
            venue="Nature",
            year=2023,
            score=0.98,
        )
        self.validator._query_crossref = lambda _: cr  # type: ignore[assignment]
        self.validator._query_s2 = lambda _: s2  # type: ignore[assignment]

        citation = {"doi": "10.1234/nature", "title": "Nature Paper", "line": 1}
        finding = self.validator.verify_single(citation)

        assert finding is None
