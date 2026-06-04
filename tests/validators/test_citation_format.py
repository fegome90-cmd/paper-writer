"""Tests for citation_format converter."""

from __future__ import annotations

from validators.citation_format import (
    audit_citation_format,
    build_author_year_index,
    convert_citations,
    extract_author_year_citations,
    parse_bib_keys,
    resolve_citation,
)

# Sample BibTeX for testing
SAMPLE_BIB = """\
@inproceedings{lewis2020_rag,
  title = {Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks},
  author = {Lewis, P. and Perez, E. and Petroni, F.},
  year = {2020},
  booktitle = {NeurIPS},
}

@inproceedings{vaswani2017_attention,
  title = {Attention is all you need},
  author = {Vaswani, A. and Shazeer, N. and Parmar, N.},
  year = {2017},
  booktitle = {NeurIPS},
}

@inproceedings{devlin2019_bert,
  title = {BERT: Pre-training of Deep Bidirectional Transformers},
  author = {Devlin, J. and Chang, M.W. and Lee, K. and Toutanova, K.},
  year = {2019},
  booktitle = {NAACL},
}
"""


class TestParseBibKeys:
    def test_extracts_entries(self) -> None:
        entries = parse_bib_keys(SAMPLE_BIB)
        assert "lewis2020_rag" in entries
        assert "vaswani2017_attention" in entries
        assert "devlin2019_bert" in entries

    def test_extracts_fields(self) -> None:
        entries = parse_bib_keys(SAMPLE_BIB)
        assert entries["lewis2020_rag"]["year"] == "2020"
        assert "Lewis" in entries["lewis2020_rag"]["authors"]

    def test_empty_bib(self) -> None:
        assert parse_bib_keys("") == {}


class TestBuildAuthorYearIndex:
    def test_first_author_indexed(self) -> None:
        entries = parse_bib_keys(SAMPLE_BIB)
        index = build_author_year_index(entries)
        assert "lewis_2020" in index
        assert index["lewis_2020"] == "lewis2020_rag"

    def test_multiple_authors_indexed(self) -> None:
        entries = parse_bib_keys(SAMPLE_BIB)
        index = build_author_year_index(entries)
        # All co-authors should be indexed
        assert "vaswani_2017" in index
        assert "shazeer_2017" in index
        assert "parmar_2017" in index

    def test_year_required(self) -> None:
        bib = "@article{noyear, title = {Test}, author = {Smith, J.} }"
        entries = parse_bib_keys(bib)
        index = build_author_year_index(entries)
        assert "smith_" not in index


class TestExtractAuthorYearCitations:
    def test_single_author_et_al(self) -> None:
        text = "Recent work (Lewis et al., 2020) has shown..."
        citations = extract_author_year_citations(text)
        assert len(citations) == 1
        assert citations[0]["year"] == "2020"
        assert "lewis" in citations[0]["authors"]

    def test_multiple_citations(self) -> None:
        text = "(Vaswani et al., 2017) and (Devlin et al., 2019)"
        citations = extract_author_year_citations(text)
        assert len(citations) == 2

    def test_no_citations(self) -> None:
        citations = extract_author_year_citations("No citations here.")
        assert len(citations) == 0


class TestResolveCitation:
    def test_resolve_known(self) -> None:
        entries = parse_bib_keys(SAMPLE_BIB)
        index = build_author_year_index(entries)
        citation = {"authors": ["lewis"], "year": "2020"}
        assert resolve_citation(citation, index) == "lewis2020_rag"

    def test_resolve_unknown(self) -> None:
        entries = parse_bib_keys(SAMPLE_BIB)
        index = build_author_year_index(entries)
        citation = {"authors": ["unknown"], "year": "2099"}
        assert resolve_citation(citation, index) is None


class TestConvertCitations:
    def test_single_replacement(self) -> None:
        text = "Recent work (Lewis et al., 2020) has shown results."
        result = convert_citations(text, SAMPLE_BIB)
        assert "@lewis2020_rag" in result
        assert "(Lewis et al., 2020)" not in result

    def test_multiple_replacements(self) -> None:
        text = "Based on (Vaswani et al., 2017) and (Devlin et al., 2019)."
        result = convert_citations(text, SAMPLE_BIB)
        assert "@vaswani2017_attention" in result
        assert "@devlin2019_bert" in result
        assert "(Vaswani et al., 2017)" not in result
        assert "(Devlin et al., 2019)" not in result

    def test_unresolved_preserved(self) -> None:
        text = "Unknown work (Unknown et al., 2099) is cited."
        result = convert_citations(text, SAMPLE_BIB)
        assert "(Unknown et al., 2099)" in result

    def test_no_citations_unchanged(self) -> None:
        text = "No citations in this text."
        assert convert_citations(text, SAMPLE_BIB) == text


class TestAuditCitationFormat:
    def test_mixed_results(self) -> None:
        text = "Based on (Lewis et al., 2020) and (Unknown et al., 2099)."
        findings = audit_citation_format(text, SAMPLE_BIB)
        # 2 individual findings + 1 summary
        assert len(findings) == 3
        severities = [f["severity"] for f in findings]
        assert "info" in severities
        assert "P1" in severities

    def test_all_resolved(self) -> None:
        text = "Based on (Lewis et al., 2020)."
        findings = audit_citation_format(text, SAMPLE_BIB)
        # 1 resolved + 1 summary
        assert len(findings) == 2
        unresolved = [f for f in findings if f["severity"] == "P1"]
        assert len(unresolved) == 0
