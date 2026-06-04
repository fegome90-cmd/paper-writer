"""Tests for validators/structure.py, refs.py, citations.py, reporting.py.

Small pure validators — section structure, reference metadata,
citation consistency, and reporting checklist.
"""

from __future__ import annotations

from validators.citations import validate_citation_consistency
from validators.refs import validate_refs_metadata
from validators.reporting import validate_reporting
from validators.structure import REQUIRED_SECTIONS, validate_section_structure


# ===================================================================
# structure.py
# ===================================================================
class TestValidateSectionStructure:
    def test_all_required_present(self) -> None:
        sections = [
            "abstract", "introduction", "literature_review",
            "methods", "results", "discussion", "conclusion",
        ]
        assert validate_section_structure(sections) == []

    def test_case_insensitive(self) -> None:
        sections = ["Introduction", "METHODS", "Results", "Discussion"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        assert errors == []

    def test_missing_methods(self) -> None:
        sections = ["introduction", "results", "discussion"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["code"] == "missing_section"]
        assert len(errors) == 1
        assert errors[0]["location"] == "methods"

    def test_missing_multiple(self) -> None:
        sections = ["introduction"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        missing = {f["location"] for f in errors}
        assert "methods" in missing
        assert "results" in missing
        assert "discussion" in missing

    def test_empty_list(self) -> None:
        findings = validate_section_structure([])
        errors = [f for f in findings if f["code"] == "missing_section"]
        assert len(errors) == len(REQUIRED_SECTIONS)

    def test_extra_sections_ok(self) -> None:
        sections = [
            "abstract", "introduction", "literature_review",
            "methods", "results", "discussion", "conclusion", "ethics", "data",
        ]
        assert validate_section_structure(sections) == []

    def test_errors_have_error_severity(self) -> None:
        findings = validate_section_structure([])
        errors = [f for f in findings if f["code"] == "missing_section"]
        for f in errors:
            assert f["severity"] == "error"


# ===================================================================
# refs.py
# ===================================================================
class TestValidateRefsMetadata:
    def test_complete_entries(self) -> None:
        entries = {
            "smith2023": {"author": "Smith", "year": "2023", "doi": "10.1/x"},
            "jones2024": {
                "author": "Jones",
                "year": "2024",
                "url": "https://arxiv.org/abs/2401.00001",
            },
        }
        assert validate_refs_metadata(entries) == []

    def test_missing_year(self) -> None:
        entries = {"e1": {"doi": "10.1/x"}}
        findings = validate_refs_metadata(entries)
        assert any(f["code"] == "missing_year" and f["location"] == "e1" for f in findings)

    def test_missing_doi_and_url(self) -> None:
        entries = {"e1": {"author": "Smith", "year": "2023"}}
        findings = validate_refs_metadata(entries)
        assert any(f["code"] == "no_persistent_id" for f in findings)

    def test_doi_sufficient(self) -> None:
        entries = {"e1": {"year": "2023", "doi": "10.1/x"}}
        assert validate_refs_metadata(entries) == []

    def test_url_sufficient(self) -> None:
        entries = {"e1": {"year": "2023", "url": "https://example.com"}}
        assert validate_refs_metadata(entries) == []

    def test_empty_entries(self) -> None:
        assert validate_refs_metadata({}) == []

    def test_both_missing_on_same_entry(self) -> None:
        entries = {"e1": {}}
        findings = validate_refs_metadata(entries)
        codes = [f["code"] for f in findings]
        assert "missing_year" in codes
        assert "no_persistent_id" in codes

    def test_multiple_entries_mixed(self) -> None:
        entries = {
            "good": {"year": "2023", "doi": "10.1/x"},
            "bad": {"author": "Nobody"},
        }
        findings = validate_refs_metadata(entries)
        bad_findings = [f for f in findings if f["location"] == "bad"]
        assert len(bad_findings) == 2  # missing year + no persistent id

    def test_severity_all_error(self) -> None:
        entries = {"e1": {}}
        findings = validate_refs_metadata(entries)
        for f in findings:
            assert f["severity"] == "error"


# ===================================================================
# citations.py
# ===================================================================
class TestValidateCitationConsistency:
    def test_all_resolved(self) -> None:
        bib_keys = {"smith2023", "jones2024", "lee2022"}
        cite_keys = {"smith2023", "jones2024"}
        assert validate_citation_consistency(bib_keys, cite_keys) == []

    def test_unresolved_citation(self) -> None:
        bib_keys = {"smith2023"}
        cite_keys = {"smith2023", "phantom2024"}
        findings = validate_citation_consistency(bib_keys, cite_keys)
        assert len(findings) == 1
        assert findings[0]["code"] == "unresolved_citation"
        assert findings[0]["location"] == "phantom2024"

    def test_multiple_unresolved(self) -> None:
        bib_keys = {"a"}
        cite_keys = {"a", "b", "c"}
        findings = validate_citation_consistency(bib_keys, cite_keys)
        assert len(findings) == 2
        locs = {f["location"] for f in findings}
        assert locs == {"b", "c"}

    def test_empty_citations(self) -> None:
        assert validate_citation_consistency({"a", "b"}, set()) == []

    def test_empty_bib_all_unresolved(self) -> None:
        findings = validate_citation_consistency(set(), {"x", "y"})
        assert len(findings) == 2

    def test_both_empty(self) -> None:
        assert validate_citation_consistency(set(), set()) == []

    def test_sorted_output(self) -> None:
        bib_keys = set()
        cite_keys = {"z_key", "a_key", "m_key"}
        findings = validate_citation_consistency(bib_keys, cite_keys)
        locs = [f["location"] for f in findings]
        assert locs == sorted(locs)

    def test_extra_bib_keys_ok(self) -> None:
        bib_keys = {"a", "b", "c", "d"}
        cite_keys = {"a"}
        assert validate_citation_consistency(bib_keys, cite_keys) == []


# ===================================================================
# reporting.py
# ===================================================================
class TestValidateReporting:
    def test_all_elements_present(self) -> None:
        sections = {
            "methods": "We used a cross-sectional study design with n=500 participants.",
            "results": "Results were analyzed.",
            "discussion": "One limitation of this study is sample bias.",
        }
        findings = validate_reporting(sections)
        # Should have no missing_element findings
        missing = [f for f in findings if f["code"].startswith("missing_")]
        assert missing == []

    def test_missing_study_design(self) -> None:
        sections = {"methods": "We collected data.", "discussion": "No mention."}
        findings = validate_reporting(sections)
        assert any(f["code"] == "missing_study_design" for f in findings)

    def test_missing_sample_size(self) -> None:
        sections = {"methods": "A randomized trial was conducted."}
        findings = validate_reporting(sections)
        assert any(f["code"] == "missing_sample_size" for f in findings)

    def test_missing_limitations(self) -> None:
        sections = {"methods": "n=100 participants. Cross-sectional design."}
        findings = validate_reporting(sections)
        assert any(f["code"] == "missing_limitations" for f in findings)

    def test_empty_section_flagged(self) -> None:
        sections = {"methods": "   "}
        findings = validate_reporting(sections)
        assert any(f["code"] == "empty_section" for f in findings)

    def test_placeholder_only_section_flagged(self) -> None:
        sections = {"methods": "# Methods"}
        findings = validate_reporting(sections)
        assert any(f["code"] == "empty_section" for f in findings)

    def test_section_with_content_ok(self) -> None:
        sections = {
            "methods": "# Methods\n\nWe enrolled participants (n=200) in a cohort study design.\nThis has some limitations."
        }
        findings = validate_reporting(sections)
        empty = [f for f in findings if f["code"] == "empty_section"]
        assert empty == []

    def test_missing_element_severity_is_warning(self) -> None:
        sections = {"body": "Some text with no reporting keywords."}
        findings = validate_reporting(sections)
        missing = [f for f in findings if f["code"].startswith("missing_")]
        for f in missing:
            assert f["severity"] == "warning"

    def test_empty_sections_dict(self) -> None:
        findings = validate_reporting({})
        # All 3 elements missing
        codes = {f["code"] for f in findings}
        assert "missing_study_design" in codes
        assert "missing_sample_size" in codes
        assert "missing_limitations" in codes

    def test_keywords_case_insensitive(self) -> None:
        sections = {"methods": "STUDY DESIGN: Randomized trial. N=50 participants."}
        findings = validate_reporting(sections)
        missing = [f for f in findings if f["code"].startswith("missing_")]
        # Should find study_design and sample_size keywords
        assert any(f["code"] == "missing_limitations" for f in missing)

    def test_all_three_missing(self) -> None:
        sections = {"body": "Generic text with no specific terms."}
        findings = validate_reporting(sections)
        codes = {f["code"] for f in findings}
        assert codes == {"missing_study_design", "missing_sample_size", "missing_limitations"}
