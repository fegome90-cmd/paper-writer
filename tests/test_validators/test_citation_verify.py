"""Tests for validators.citation_verify — citation verification orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from clients.crossref import CrossrefResult
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
            sentences.append(Sentence(
                text=line.strip(),
                line=i + 1,
                col=0,
                char_start=full.find(line),
                char_end=full.find(line) + len(line),
            ))
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
        assert all(f["severity"] == "P2" for f in findings)
        assert all("skipped" in f["rule_id"] for f in findings)


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
            s2_client=MagicMock(verify_doi=MagicMock(return_value=S2Result(
                found=True, title="Nature Paper", score=0.95
            ))),
        )
        findings = validator.validate(manuscript)
        p0_findings = [f for f in findings if f["severity"] == "P0"]
        assert len(p0_findings) == 0
