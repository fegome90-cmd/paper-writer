"""Tests for pure domain validator functions.

Covers validators/refs.py, validators/citations.py, validators/style.py,
validators/reporting.py, and validators/structure.py.
"""

from validators.citations import validate_citation_consistency
from validators.refs import validate_refs_metadata
from validators.reporting import validate_reporting
from validators.structure import validate_section_structure
from validators.style import validate_style

# ---------------------------------------------------------------------------
# validate_refs_metadata
# ---------------------------------------------------------------------------


class TestValidateRefsMetadata:
    """Tests for bibliography metadata validation rules."""

    def test_entry_with_year_and_doi_passes(self) -> None:
        entries = {"smith2024": {"year": "2024", "doi": "10.1000/example"}}
        findings = validate_refs_metadata(entries)
        assert findings == []

    def test_entry_with_year_and_url_passes(self) -> None:
        entries = {"smith2024": {"year": "2024", "url": "https://example.com"}}
        findings = validate_refs_metadata(entries)
        assert findings == []

    def test_entry_missing_year_produces_error(self) -> None:
        entries = {"noyear": {"doi": "10.1000/example"}}
        findings = validate_refs_metadata(entries)
        assert len(findings) == 1
        assert findings[0]["code"] == "missing_year"
        assert findings[0]["severity"] == "error"
        assert "noyear" in findings[0]["message"]

    def test_entry_missing_both_doi_and_url(self) -> None:
        entries = {"noid": {"year": "2024"}}
        findings = validate_refs_metadata(entries)
        assert len(findings) == 1
        assert findings[0]["code"] == "no_persistent_id"
        assert findings[0]["severity"] == "error"

    def test_entry_with_year_but_no_doi_or_url(self) -> None:
        entries = {"minimal": {"year": "2024", "title": "Some title"}}
        findings = validate_refs_metadata(entries)
        assert len(findings) == 1
        assert findings[0]["code"] == "no_persistent_id"

    def test_empty_entries_dict_no_findings(self) -> None:
        findings = validate_refs_metadata({})
        assert findings == []

    def test_multiple_entries_mixed_compliance(self) -> None:
        entries = {
            "good": {"year": "2024", "doi": "10.1000/a"},
            "no_year": {"doi": "10.1000/b"},
            "no_id": {"year": "2023"},
        }
        findings = validate_refs_metadata(entries)
        codes = [f["code"] for f in findings]
        assert "missing_year" in codes
        assert "no_persistent_id" in codes
        # no_year: 1 finding (missing_year), no_id: 1 finding (no_persistent_id)
        assert len(findings) == 2

    def test_entry_missing_both_year_and_id(self) -> None:
        entries = {"bare": {"title": "Just a title"}}
        findings = validate_refs_metadata(entries)
        assert len(findings) == 2
        codes = [f["code"] for f in findings]
        assert "missing_year" in codes
        assert "no_persistent_id" in codes


# ---------------------------------------------------------------------------
# validate_citation_consistency
# ---------------------------------------------------------------------------


class TestValidateCitationConsistency:
    """Tests for citation consistency validation rules."""

    def test_all_citations_resolve(self) -> None:
        bib_keys = {"smith2024", "doe2023"}
        citation_keys = {"smith2024", "doe2023"}
        findings = validate_citation_consistency(bib_keys, citation_keys)
        assert findings == []

    def test_one_unresolved_citation(self) -> None:
        bib_keys = {"smith2024"}
        citation_keys = {"smith2024", "ghost2024"}
        findings = validate_citation_consistency(bib_keys, citation_keys)
        assert len(findings) == 1
        assert findings[0]["code"] == "unresolved_citation"
        assert findings[0]["severity"] == "error"
        assert "ghost2024" in findings[0]["message"]

    def test_multiple_unresolved_citations(self) -> None:
        bib_keys = {"smith2024"}
        citation_keys = {"alpha2024", "beta2024", "smith2024"}
        findings = validate_citation_consistency(bib_keys, citation_keys)
        assert len(findings) == 2
        unresolved = {f["location"] for f in findings}
        assert unresolved == {"alpha2024", "beta2024"}

    def test_empty_sets_no_findings(self) -> None:
        findings = validate_citation_consistency(set(), set())
        assert findings == []

    def test_all_citations_unresolved(self) -> None:
        bib_keys: set[str] = set()
        citation_keys = {"a2024", "b2024", "c2024"}
        findings = validate_citation_consistency(bib_keys, citation_keys)
        assert len(findings) == 3
        assert all(f["code"] == "unresolved_citation" for f in findings)

    def test_citations_subset_of_bib_keys(self) -> None:
        bib_keys = {"smith2024", "doe2023", "lee2022"}
        citation_keys = {"smith2024"}
        findings = validate_citation_consistency(bib_keys, citation_keys)
        assert findings == []

    def test_findings_are_sorted(self) -> None:
        bib_keys: set[str] = set()
        citation_keys = {"zeta2024", "alpha2024"}
        findings = validate_citation_consistency(bib_keys, citation_keys)
        locations = [f["location"] for f in findings]
        assert locations == sorted(locations)


# ---------------------------------------------------------------------------
# validate_style
# ---------------------------------------------------------------------------


class TestValidateStyle:
    """Tests for prose style validation rules."""

    def test_clean_text_no_findings(self) -> None:
        text = "The study found significant results. Participants completed the survey."
        findings = validate_style(text)
        assert findings == []

    def test_passive_voice_detected(self) -> None:
        text = "The data was collected by the research team."
        findings = validate_style(text)
        passive = [f for f in findings if f["code"] == "passive_voice"]
        assert len(passive) >= 1
        assert passive[0]["severity"] == "warning"

    def test_long_sentence_detected(self) -> None:
        # Build a sentence longer than 300 characters
        words = ["word"] * 80
        long_sentence = " ".join(words) + "."
        findings = validate_style(long_sentence)
        long = [f for f in findings if f["code"] == "long_sentence"]
        assert len(long) >= 1
        assert long[0]["severity"] == "warning"

    def test_both_passive_and_long_sentence(self) -> None:
        # Build a long passive sentence
        prefix = "The data was collected by the research team "
        padding = " ".join(["detail"] * 60)
        text = f"{prefix} {padding}."
        findings = validate_style(text)
        codes = {f["code"] for f in findings}
        assert "passive_voice" in codes
        assert "long_sentence" in codes

    def test_empty_text_no_findings(self) -> None:
        findings = validate_style("")
        assert findings == []

    def test_file_label_propagated_to_location(self) -> None:
        text = "The data was collected by the team."
        findings = validate_style(text, file_label="methods.md")
        assert all(f["location"] == "methods.md" for f in findings)

    def test_default_location_is_manuscript(self) -> None:
        text = "The data was collected by the team."
        findings = validate_style(text)
        assert all(f["location"] == "manuscript" for f in findings)


# ---------------------------------------------------------------------------
# validate_reporting
# ---------------------------------------------------------------------------


class TestValidateReporting:
    """Tests for reporting checklist validation rules."""

    def test_complete_sections_no_errors(self) -> None:
        sections = {
            "methods": (
                "We used a cross-sectional study design with 200 participants. "
                "Key limitations include potential selection bias."
            ),
            "results": "The prevalence was 42.3% (n=84).",
        }
        findings = validate_reporting(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        assert errors == []

    def test_empty_section_error(self) -> None:
        sections = {"methods": ""}
        findings = validate_reporting(sections)
        assert any(f["code"] == "empty_section" and f["severity"] == "error" for f in findings)

    def test_missing_study_design_keywords_warns(self) -> None:
        sections = {"methods": "We enrolled 50 participants. We discuss limitations."}
        findings = validate_reporting(sections)
        assert any(f["code"] == "missing_study_design" for f in findings)

    def test_missing_sample_size_keywords_warns(self) -> None:
        sections = {"methods": "A cross-sectional study. We acknowledge potential confounders."}
        findings = validate_reporting(sections)
        assert any(f["code"] == "missing_sample_size" for f in findings)

    def test_missing_limitations_keywords_warns(self) -> None:
        sections = {
            "methods": "A cross-sectional study with n=100 participants.",
            "results": "Significant findings.",
        }
        findings = validate_reporting(sections)
        assert any(f["code"] == "missing_limitations" for f in findings)

    def test_placeholder_only_section_counts_as_empty(self) -> None:
        sections = {"methods": "# Methods"}
        findings = validate_reporting(sections)
        assert any(f["code"] == "empty_section" for f in findings)

    def test_all_reporting_elements_present(self) -> None:
        sections = {
            "methods": (
                "A randomized trial with 300 participants. "
                "We discuss limitations and potential bias."
            ),
        }
        findings = validate_reporting(sections)
        warnings = [f for f in findings if f["severity"] == "warning"]
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# validate_section_structure
# ---------------------------------------------------------------------------


class TestValidateSectionStructure:
    """Tests for section structure validation rules."""

    def test_all_required_sections_present(self) -> None:
        sections = ["introduction", "methods", "results", "discussion"]
        findings = validate_section_structure(sections)
        assert findings == []

    def test_all_required_sections_case_insensitive(self) -> None:
        sections = ["Introduction", "METHODS", "Results", "Discussion"]
        findings = validate_section_structure(sections)
        assert findings == []

    def test_missing_one_section(self) -> None:
        sections = ["introduction", "methods", "results"]
        findings = validate_section_structure(sections)
        assert len(findings) == 1
        assert findings[0]["code"] == "missing_section"
        assert findings[0]["severity"] == "error"
        assert "discussion" in findings[0]["message"]

    def test_missing_multiple_sections(self) -> None:
        sections = ["introduction"]
        findings = validate_section_structure(sections)
        assert len(findings) == 3
        missing = {f["location"] for f in findings}
        assert missing == {"methods", "results", "discussion"}

    def test_empty_list_four_errors(self) -> None:
        findings = validate_section_structure([])
        assert len(findings) == 4
        assert all(f["code"] == "missing_section" for f in findings)

    def test_extra_sections_no_findings(self) -> None:
        sections = ["introduction", "methods", "results", "discussion", "appendix"]
        findings = validate_section_structure(sections)
        assert findings == []

    def test_findings_location_matches_section_name(self) -> None:
        sections = ["introduction", "methods"]
        findings = validate_section_structure(sections)
        locations = {f["location"] for f in findings}
        assert locations == {"results", "discussion"}
