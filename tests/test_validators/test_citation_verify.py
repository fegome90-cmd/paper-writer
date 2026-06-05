"""Tests for validators.citation_verify — citation verification orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from clients.arxiv import ArxivResult
from clients.crossref import CrossrefResult
from clients.openalex import OpenAlexResult
from clients.semantic_scholar import S2Result
from parsers.manuscript import Manuscript, Section, Sentence
from parsers.source_map import SourceMap
from validators.citation_verify import CitationVerifyValidator


def _make_manuscript(text: str = "", references: str = "") -> Manuscript:
    """Build a minimal Manuscript for testing."""
    full = text
    if references:
        full += "\n\nReferences\n" + references
    source_map = SourceMap(full)
    sections: dict[str, Section] = {}
    if references:
        sections["references"] = Section(
            heading="References",
            text=references,
            line_start=text.count("\n") + 2,
            line_end=full.count("\n"),
        )
    sentences = []
    for i, line in enumerate(full.split("\n")):
        if line.strip():
            sentences.append(
                Sentence(
                    text=line.strip(),
                    line=i + 1,
                    col=0,
                    char_start=full.find(line),
                    char_end=full.find(line) + len(line),
                )
            )
    return Manuscript(
        path="test.md",
        format="markdown",
        clean_text=full,
        source_map=source_map,
        sections=sections,
        sentences=sentences,
    )


class TestCitationVerifyValidatorOffline:
    def test_offline_returns_skipped_findings(self):
        manuscript = _make_manuscript(
            text="Some text.",
            references="Smith et al. (2023). Nature. 10.1038/fake",
        )
        validator = CitationVerifyValidator(offline=True)
        findings = validator.validate(manuscript)
        assert len(findings) > 0
        # Separate citation findings from summary verdict
        citation_findings = [
            f for f in findings if f.get("rule_id") != "citation_verification_summary"
        ]
        assert len(citation_findings) > 0
        assert all(f["severity"] == "P2" for f in citation_findings)
        assert all("skipped" in f["rule_id"] for f in citation_findings)


class TestCitationVerifyValidatorDoiExtraction:
    def test_extracts_dois_from_references(self):
        manuscript = _make_manuscript(
            text="We cite a paper [1].",
            references="[1] Smith et al. Nature. 10.1038/s41586-020-2649-2",
        )
        validator = CitationVerifyValidator(offline=True)
        citations = validator._extract_citations(manuscript)
        dois = [c["doi"] for c in citations if c.get("doi")]
        assert "10.1038/s41586-020-2649-2" in dois


class TestCitationVerifyValidatorClassify:
    def _make_validator(self):
        return CitationVerifyValidator(offline=True)

    def test_verified_both_sources(self):
        v = self._make_validator()
        verdict, severity = v._classify_citation(
            crossref=CrossrefResult(found=True, title="Test Paper", score=0.95),
            s2=S2Result(found=True, title="Test Paper", score=0.95),
        )
        assert verdict == "verified"
        assert severity is None

    def test_partial_crossref_only(self):
        v = self._make_validator()
        verdict, severity = v._classify_citation(
            crossref=CrossrefResult(found=True, title="Test Paper", score=0.95),
            s2=S2Result(found=False),
        )
        assert verdict == "partial"
        assert severity == "P2"

    def test_not_found_neither_source(self):
        v = self._make_validator()
        verdict, severity = v._classify_citation(
            crossref=CrossrefResult(found=False),
            s2=S2Result(found=False),
        )
        assert verdict == "not_found"
        assert severity == "P0"

    def test_title_mismatch(self):
        v = self._make_validator()
        verdict, severity = v._classify_citation(
            crossref=CrossrefResult(found=True, title="Different Title", score=0.3),
            s2=S2Result(found=True, title="Different Title", score=0.3),
        )
        assert verdict == "title_mismatch"
        assert severity == "P1"


class TestCitationVerifyValidatorValidate:
    @patch("validators.citation_verify.CrossrefClient")
    def test_fabricated_doi_produces_p0_finding(self, mock_crossref):
        mock_client = MagicMock()
        mock_client.verify_doi.return_value = CrossrefResult(found=False)
        mock_crossref.return_value = mock_client

        manuscript = _make_manuscript(
            text="We cite a paper.",
            references="Smith et al. Nature. 10.99999/fake",
        )
        validator = CitationVerifyValidator(
            crossref_client=mock_client,
            s2_client=MagicMock(verify_doi=MagicMock(return_value=S2Result(found=False))),
            openalex_client=MagicMock(
                verify_doi=MagicMock(return_value=OpenAlexResult(found=False))
            ),
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False))
            ),
        )
        findings = validator.validate(manuscript)
        p0_findings = [f for f in findings if f["severity"] == "P0"]
        assert len(p0_findings) > 0

    @patch("validators.citation_verify.CrossrefClient")
    def test_valid_doi_produces_no_p0(self, mock_crossref):
        mock_client = MagicMock()
        mock_client.verify_doi.return_value = CrossrefResult(
            found=True, title="Nature Paper", score=0.95
        )
        mock_crossref.return_value = mock_client

        manuscript = _make_manuscript(
            text="We cite a paper.",
            references="Smith et al. Nature. 10.1038/s41586-020-2649-2",
        )
        validator = CitationVerifyValidator(
            crossref_client=mock_client,
            s2_client=MagicMock(
                verify_doi=MagicMock(
                    return_value=S2Result(found=True, title="Nature Paper", score=0.95)
                )
            ),
            openalex_client=MagicMock(
                verify_doi=MagicMock(return_value=OpenAlexResult(found=False))
            ),
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False))
            ),
        )
        findings = validator.validate(manuscript)
        p0_findings = [f for f in findings if f["severity"] == "P0"]
        assert len(p0_findings) == 0


class TestCitationVerifyVerifySingle:
    """Test verify_single finding generation for different verdicts."""

    def testverify_single_title_mismatch(self) -> None:
        """verify_single produces P1 finding for title_mismatch."""
        mock_crossref = MagicMock()
        mock_crossref.verify_doi.return_value = CrossrefResult(
            found=True, title="Wrong Title", score=0.3
        )
        mock_s2 = MagicMock()
        mock_s2.verify_doi.return_value = S2Result(found=True, title="Wrong Title", score=0.3)
        validator = CitationVerifyValidator(
            crossref_client=mock_crossref,
            s2_client=mock_s2,
            openalex_client=MagicMock(
                verify_doi=MagicMock(return_value=OpenAlexResult(found=False))
            ),
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False))
            ),
        )
        citation = {"doi": "10.1234/test", "line": 5, "section": "references"}
        finding = validator.verify_single(citation)
        assert finding is not None
        assert finding["rule_id"] == "citation_verify.title_mismatch"
        assert finding["severity"] == "P1"

    def testverify_single_partial(self) -> None:
        """verify_single produces P2 finding for partial match."""
        mock_crossref = MagicMock()
        mock_crossref.verify_doi.return_value = CrossrefResult(
            found=True, title="Test Paper", score=0.95
        )
        mock_s2 = MagicMock()
        mock_s2.verify_doi.return_value = S2Result(found=False)
        mock_openalex = MagicMock()
        mock_openalex.verify_doi.return_value = OpenAlexResult(found=False)
        validator = CitationVerifyValidator(
            crossref_client=mock_crossref,
            s2_client=mock_s2,
            openalex_client=mock_openalex,
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False))
            ),
        )
        citation = {"doi": "10.1234/test", "line": 5, "section": "references"}
        finding = validator.verify_single(citation)
        assert finding is not None
        assert finding["rule_id"] == "citation_verify.partial"
        assert finding["severity"] == "P2"

    def testverify_single_not_found(self) -> None:
        """verify_single produces P0 finding for not_found."""
        mock_crossref = MagicMock()
        mock_crossref.verify_doi.return_value = CrossrefResult(found=False)
        mock_s2 = MagicMock()
        mock_s2.verify_doi.return_value = S2Result(found=False)
        mock_openalex = MagicMock()
        mock_openalex.verify_doi.return_value = OpenAlexResult(found=False)
        validator = CitationVerifyValidator(
            crossref_client=mock_crossref,
            s2_client=mock_s2,
            openalex_client=mock_openalex,
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False))
            ),
        )
        citation = {"doi": "10.99999/fake", "line": 3, "section": "references"}
        finding = validator.verify_single(citation)
        assert finding is not None
        assert finding["rule_id"] == "citation_verify.not_found"
        assert finding["severity"] == "P0"

    def testverify_single_verified_returns_none(self) -> None:
        """verify_single returns None for verified citations."""
        mock_crossref = MagicMock()
        mock_crossref.verify_doi.return_value = CrossrefResult(
            found=True, title="Test Paper", score=0.95
        )
        mock_s2 = MagicMock()
        mock_s2.verify_doi.return_value = S2Result(found=True, title="Test Paper", score=0.95)
        validator = CitationVerifyValidator(
            crossref_client=mock_crossref,
            s2_client=mock_s2,
            openalex_client=MagicMock(
                verify_doi=MagicMock(return_value=OpenAlexResult(found=False))
            ),
            arxiv_client=MagicMock(
                verify_arxiv_id=MagicMock(return_value=ArxivResult(found=False))
            ),
        )
        citation = {"doi": "10.1234/test", "line": 5, "section": "references"}
        finding = validator.verify_single(citation)
        assert finding is None


class TestCitationVerifyExtractCitations:
    """Test multi-line reference parsing edge cases."""

    def test_multiline_reference_merged(self) -> None:
        """Multi-line references are merged into single entries."""
        refs = """[1] Smith et al. Nature.
        10.1038/s41586-020-2649-2
        [2] Jones et al. Science. 10.1126/science.fake"""
        manuscript = _make_manuscript(text="Text.", references=refs)
        validator = CitationVerifyValidator(offline=True)
        citations = validator._extract_citations(manuscript)
        assert len(citations) >= 2

    def test_no_references_section_returns_empty(self) -> None:
        """Manuscript without references section returns empty list."""
        manuscript = _make_manuscript(text="Just body text, no refs.")
        validator = CitationVerifyValidator(offline=True)
        citations = validator._extract_citations(manuscript)
        assert citations == []


class TestCitationVerifyQueryClients:
    """Test _query_crossref and _query_s2 with mocked clients."""

    def test_query_crossref_offline_returns_none(self) -> None:
        """_query_crossref returns None in offline mode."""
        validator = CitationVerifyValidator(offline=True)
        result = validator._query_crossref({"doi": "10.1234/test"})
        assert result is None

    def test_query_s2_offline_returns_none(self) -> None:
        """_query_s2 returns None in offline mode."""
        validator = CitationVerifyValidator(offline=True)
        result = validator._query_s2({"doi": "10.1234/test"})
        assert result is None

    def test_query_crossref_exception_returns_not_found(self) -> None:
        """_query_crossref returns CrossrefResult(found=False) on exception."""
        mock_client = MagicMock()
        mock_client.verify_doi.side_effect = Exception("network error")
        validator = CitationVerifyValidator(offline=False, crossref_client=mock_client)
        result = validator._query_crossref({"doi": "10.1234/test"})
        assert result is not None
        assert result.found is False

    def test_query_s2_exception_returns_not_found(self) -> None:
        """_query_s2 returns S2Result(found=False) on exception."""
        mock_client = MagicMock()
        mock_client.verify_doi.side_effect = Exception("network error")
        validator = CitationVerifyValidator(offline=False, s2_client=mock_client)
        result = validator._query_s2({"doi": "10.1234/test"})
        assert result is not None
        assert result.found is False

    def test_query_crossref_by_title(self) -> None:
        """_query_crossref falls back to title search."""
        mock_client = MagicMock()
        mock_client.search_by_title.return_value = [
            CrossrefResult(found=True, title="Test", score=0.9)
        ]
        validator = CitationVerifyValidator(offline=False, crossref_client=mock_client)
        result = validator._query_crossref({"title": "Test Paper"})
        assert result is not None
        assert result.found is True

    def test_query_s2_by_title(self) -> None:
        """_query_s2 falls back to title search."""
        mock_client = MagicMock()
        mock_client.search_by_title.return_value = [S2Result(found=True, title="Test", score=0.9)]
        validator = CitationVerifyValidator(offline=False, s2_client=mock_client)
        result = validator._query_s2({"title": "Test Paper"})
        assert result is not None
        assert result.found is True
