"""Tests for pure domain validator functions.

Covers validators/refs.py, validators/citations.py, validators/style.py,
validators/reporting.py, and validators/structure.py.
"""

from validators.bibliography import (
    detect_duplicate_keys,
    normalize_entry_fields,
    validate_bibliography,
    validate_doi_format,
    validate_entry_type,
    validate_required_fields,
    validate_year_range,
)
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

    def test_entry_with_none_values_no_crash(self) -> None:
        """None field values (from malformed BibTeX) should not crash."""
        entries: dict[str, dict[str, str]] = {"key1": {"title": None, "author": None}}  # type: ignore[dict-item]
        findings = validate_refs_metadata(entries)
        assert isinstance(findings, list)

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
        # Build a sentence longer than 500 characters (the actual threshold)
        words = ["word"] * 130
        long_sentence = " ".join(words) + "."
        # Sanity-check: sentence length must exceed _MAX_SENTENCE_LENGTH (500)
        assert len(long_sentence) > 500, f"Test sentence too short: {len(long_sentence)} chars"
        findings = validate_style(long_sentence)
        long = [f for f in findings if f["code"] == "long_sentence"]
        assert len(long) >= 1
        assert long[0]["severity"] == "warning"

    def test_both_passive_and_long_sentence(self) -> None:
        # Build a long passive sentence exceeding the 500-char threshold
        prefix = "The data was collected by the research team "
        padding = " ".join(["detail"] * 120)
        text = f"{prefix} {padding}."
        assert len(text) > 500, f"Test sentence too short: {len(text)} chars"
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

    def test_unbacked_claim_detected(self) -> None:
        text = "This study proves that the intervention works perfectly."
        findings = validate_style(text)
        claims = [f for f in findings if f["code"] == "unbacked_claim"]
        assert len(claims) >= 1
        assert claims[0]["severity"] == "warning"
        assert "proves that" in claims[0]["message"]

    def test_unbacked_claim_first_time(self) -> None:
        text = "This is the first ever demonstration of the effect."
        findings = validate_style(text)
        claims = [f for f in findings if f["code"] == "unbacked_claim"]
        assert len(claims) >= 1
        assert any("first ever" in f["message"] for f in claims)

    def test_forbidden_phrase_detected(self) -> None:
        text = "In order to analyze the data, we used regression."
        findings = validate_style(text)
        forbidden = [f for f in findings if f["code"] == "forbidden_phrase"]
        assert len(forbidden) >= 1
        assert forbidden[0]["severity"] == "error"
        assert "in order to" in forbidden[0]["message"]

    def test_forbidden_phrase_due_to_the_fact(self) -> None:
        text = "Due to the fact that the sample was small, we could not generalize."
        findings = validate_style(text)
        forbidden = [f for f in findings if f["code"] == "forbidden_phrase"]
        assert len(forbidden) >= 1
        assert "due to the fact that" in forbidden[0]["message"]

    def test_informal_language_detected(self) -> None:
        text = "The results basically show a significant difference."
        findings = validate_style(text)
        informal = [f for f in findings if f["code"] == "informal_language"]
        assert len(informal) >= 1
        assert informal[0]["severity"] == "warning"
        assert "basically" in informal[0]["message"]

    def test_informal_stuff_and_things(self) -> None:
        text = "We measured lots of stuff and things in the experiment."
        findings = validate_style(text)
        informal = [f for f in findings if f["code"] == "informal_language"]
        words = [f["message"].split("'")[1] for f in informal]
        assert "lots of" in words or "stuff" in words

    def test_hedged_claim_no_unbacked_finding(self) -> None:
        text = "Our findings suggest that the intervention may improve outcomes."
        findings = validate_style(text)
        claims = [f for f in findings if f["code"] == "unbacked_claim"]
        assert len(claims) == 0

    def test_formal_text_no_forbidden_or_informal(self) -> None:
        text = (
            "We conducted a cross-sectional study to examine the association "
            "between exposure and outcome. Our findings suggest a potential "
            "relationship, though further research is warranted."
        )
        findings = validate_style(text)
        forbidden = [f for f in findings if f["code"] == "forbidden_phrase"]
        informal = [f for f in findings if f["code"] == "informal_language"]
        assert len(forbidden) == 0
        assert len(informal) == 0


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
        errors = [f for f in findings if f["severity"] == "error"]
        assert errors == []
        # Recommended sections produce warnings, not errors
        warnings = [f for f in findings if f["severity"] == "warning"]
        assert len(warnings) == 3  # abstract, literature_review, conclusion

    def test_all_required_and_recommended_present(self) -> None:
        sections = [
            "abstract",
            "introduction",
            "literature_review",
            "methods",
            "results",
            "discussion",
            "conclusion",
        ]
        findings = validate_section_structure(sections)
        assert findings == []

    def test_all_required_sections_case_insensitive(self) -> None:
        sections = ["Introduction", "METHODS", "Results", "Discussion"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        assert errors == []

    def test_missing_one_section(self) -> None:
        sections = ["introduction", "methods", "results"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["code"] == "missing_section"]
        assert len(errors) == 1
        assert errors[0]["severity"] == "error"
        assert "discussion" in errors[0]["message"]

    def test_missing_multiple_sections(self) -> None:
        sections = ["introduction"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        assert len(errors) == 3
        missing = {f["location"] for f in errors}
        assert missing == {"methods", "results", "discussion"}

    def test_empty_list_four_errors(self) -> None:
        findings = validate_section_structure([])
        errors = [f for f in findings if f["code"] == "missing_section"]
        assert len(errors) == 4
        assert all(f["severity"] == "error" for f in errors)

    def test_extra_sections_no_errors(self) -> None:
        sections = ["introduction", "methods", "results", "discussion", "appendix"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        assert errors == []

    def test_findings_location_matches_section_name(self) -> None:
        sections = ["introduction", "methods"]
        findings = validate_section_structure(sections)
        errors = [f for f in findings if f["severity"] == "error"]
        locations = {f["location"] for f in errors}
        assert locations == {"results", "discussion"}

    def test_recommended_sections_are_warnings(self) -> None:
        sections = ["introduction", "methods", "results", "discussion"]
        findings = validate_section_structure(sections)
        warnings = [f for f in findings if f["code"] == "missing_recommended_section"]
        assert len(warnings) == 3
        warned = {f["location"] for f in warnings}
        assert warned == {"abstract", "literature_review", "conclusion"}
        assert all(f["severity"] == "warning" for f in warnings)


# ---------------------------------------------------------------------------
# validate_bibliography (validators/bibliography.py)
# ---------------------------------------------------------------------------


class TestNormalizeEntryFields:
    """Tests for field normalization."""

    def test_lowercase_keys(self) -> None:
        fields = {"Title": "A Study", "AUTHOR": "Smith"}
        result = normalize_entry_fields(fields)
        assert "title" in result
        assert "author" in result

    def test_strip_whitespace(self) -> None:
        fields = {"  title  ": "  A Study  "}
        result = normalize_entry_fields(fields)
        assert result == {"title": "A Study"}


class TestDetectDuplicateKeys:
    """Tests for duplicate key detection."""

    def test_no_duplicates(self) -> None:
        entries: dict[str, dict[str, str]] = {"smith2024": {}, "doe2023": {}}
        assert detect_duplicate_keys(entries) == []

    def test_case_insensitive_duplicate(self) -> None:
        entries: dict[str, dict[str, str]] = {"Smith2024": {}, "smith2024": {}}
        dups = detect_duplicate_keys(entries)
        assert len(dups) == 1

    def test_multiple_duplicates(self) -> None:
        entries: dict[str, dict[str, str]] = {"A": {}, "a": {}, "B": {}, "b": {}}
        dups = detect_duplicate_keys(entries)
        assert len(dups) == 2


class TestValidateEntryType:
    """Tests for entry type validation."""

    def test_valid_type_no_findings(self) -> None:
        findings = validate_entry_type("article")
        assert findings == []

    def test_invalid_type_warning(self) -> None:
        findings = validate_entry_type("newspaper")
        assert len(findings) == 1
        assert findings[0]["code"] == "unknown_entry_type"
        assert findings[0]["severity"] == "warning"


class TestValidateRequiredFields:
    """Tests for required field validation."""

    def test_article_with_all_fields(self) -> None:
        fields = {"author": "Smith", "title": "A Study", "journal": "Nature", "year": "2024"}
        findings = validate_required_fields("article", fields, "smith2024")
        assert findings == []

    def test_article_missing_journal(self) -> None:
        fields = {"author": "Smith", "title": "A Study", "year": "2024"}
        findings = validate_required_fields("article", fields, "smith2024")
        assert len(findings) == 1
        assert findings[0]["code"] == "missing_required_field"
        assert "journal" in findings[0]["message"]

    def test_unknown_type_no_findings(self) -> None:
        findings = validate_required_fields("newspaper", {}, "key")
        assert findings == []


class TestValidateDoiFormat:
    """Tests for DOI format validation."""

    def test_valid_doi(self) -> None:
        findings = validate_doi_format("10.1000/xyz123", "key")
        assert findings == []

    def test_invalid_doi(self) -> None:
        findings = validate_doi_format("not-a-doi", "key")
        assert len(findings) == 1
        assert findings[0]["code"] == "malformed_doi"

    def test_doi_missing_prefix(self) -> None:
        findings = validate_doi_format("1000/xyz", "key")
        assert len(findings) == 1


class TestValidateYearRange:
    """Tests for year range validation."""

    def test_valid_year(self) -> None:
        findings = validate_year_range("2024", "key")
        assert findings == []

    def test_non_numeric_year(self) -> None:
        findings = validate_year_range("abc", "key")
        assert len(findings) == 1
        assert findings[0]["code"] == "invalid_year"

    def test_suspicious_old_year(self) -> None:
        findings = validate_year_range("1800", "key")
        assert len(findings) == 1
        assert findings[0]["code"] == "suspicious_year"

    def test_future_year(self) -> None:
        findings = validate_year_range("2050", "key")
        assert len(findings) == 1
        assert findings[0]["code"] == "suspicious_year"


class TestValidateBibliography:
    """Tests for full bibliography validation."""

    def test_clean_entries_no_findings(self) -> None:
        entries = {
            "smith2024": {
                "author": "Smith",
                "title": "A Study",
                "journal": "Nature",
                "year": "2024",
                "doi": "10.1000/abc",
            },
        }
        entry_types = {"smith2024": "article"}
        findings = validate_bibliography(entries, entry_types)
        assert findings == []

    def test_multiple_issues(self) -> None:
        entries = {
            "bad2024": {"year": "1800", "doi": "invalid"},
            "alsobad": {"year": "1800", "doi": "invalid"},
        }
        findings = validate_bibliography(entries)
        # Should find DOI and year issues for both entries
        codes = [f["code"] for f in findings]
        assert "malformed_doi" in codes
        assert "suspicious_year" in codes


# ---------------------------------------------------------------------------
# validate_preset (validators/preset.py)
# ---------------------------------------------------------------------------


class TestValidatePreset:
    """Tests for journal preset validation."""

    def test_valid_preset_no_findings(self) -> None:
        from validators.preset import validate_preset

        preset = {
            "name": "Nature",
            "format": "docx",
            "citation_style": "vancouver",
            "required_sections": ["abstract", "introduction", "results", "discussion", "methods"],
        }
        findings = validate_preset(preset)
        assert findings == []

    def test_missing_required_field(self) -> None:
        from validators.preset import validate_preset

        preset = {"name": "Test"}
        findings = validate_preset(preset)
        codes = [f["code"] for f in findings]
        assert "missing_preset_field" in codes
        assert len(findings) >= 3  # format, citation_style, required_sections

    def test_empty_preset(self) -> None:
        from validators.preset import validate_preset

        findings = validate_preset({})
        assert len(findings) == 1
        assert findings[0]["code"] == "empty_preset"

    def test_empty_sections_list(self) -> None:
        from validators.preset import validate_preset

        preset = {
            "name": "Test",
            "format": "docx",
            "citation_style": "vancouver",
            "required_sections": [],
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "empty_sections" for f in findings)

    def test_invalid_format_warning(self) -> None:
        from validators.preset import validate_preset

        preset = {
            "name": "Test",
            "format": "epub",
            "citation_style": "vancouver",
            "required_sections": ["intro"],
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_format" for f in findings)

    def test_invalid_max_words(self) -> None:
        from validators.preset import validate_preset

        preset = {
            "name": "Test",
            "format": "docx",
            "citation_style": "vancouver",
            "required_sections": ["intro"],
            "max_words": -100,
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_max_words" for f in findings)

    def test_sections_not_list(self) -> None:
        from validators.preset import validate_preset

        preset = {
            "name": "Test",
            "format": "docx",
            "citation_style": "vancouver",
            "required_sections": "intro",
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_sections" for f in findings)
