"""Tests for validators/bibliography.py — BibTeX normalization and validation.

Covers: normalize_entry_fields, detect_duplicate_keys, validate_entry_type,
validate_required_fields, validate_doi_format, validate_year_range,
validate_bibliography (integration).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Import target
# ---------------------------------------------------------------------------
from validators.bibliography import (
    PREPRINT_VENUES,
    VALID_ENTRY_TYPES,
    detect_duplicate_keys,
    detect_preprint_venues,
    normalize_entry_fields,
    validate_bibliography,
    validate_doi_format,
    validate_entry_type,
    validate_required_fields,
    validate_year_range,
)


# ===================================================================
# normalize_entry_fields
# ===================================================================
class TestNormalizeEntryFields:
    def test_lowercases_keys(self) -> None:
        result = normalize_entry_fields({"TITLE": "Foo", "Author": "Bar"})
        assert "title" in result
        assert "author" in result

    def test_strips_whitespace_from_values(self) -> None:
        result = normalize_entry_fields({"title": "  Foo Bar  "})
        assert result["title"] == "Foo Bar"

    def test_strips_whitespace_from_keys(self) -> None:
        result = normalize_entry_fields({"  Title  ": "Foo"})
        assert "title" in result

    def test_converts_none_to_empty_string(self) -> None:
        result = normalize_entry_fields({"title": None})  # type: ignore[arg-type]
        assert result["title"] == ""

    def test_preserves_non_string_values_as_empty(self) -> None:
        result = normalize_entry_fields({"year": 2023})  # type: ignore[arg-type]
        assert result["year"] == ""

    def test_empty_dict_returns_empty(self) -> None:
        assert normalize_entry_fields({}) == {}

    def test_all_fields_normalized(self) -> None:
        raw = {"  TITLE  ": "  A Study  ", "AUTHOR": "  Smith  ", "YEAR": None}  # type: ignore[arg-type]
        result = normalize_entry_fields(raw)
        assert result == {"title": "A Study", "author": "Smith", "year": ""}


# ===================================================================
# detect_duplicate_keys
# ===================================================================
class TestDetectDuplicateKeys:
    def test_no_duplicates(self) -> None:
        entries = {"smith2023": {"title": "A"}, "jones2023": {"title": "B"}}
        assert detect_duplicate_keys(entries) == []

    def test_exact_duplicate(self) -> None:
        # Python dict dedupes at parse level — but function should handle it
        # Use a dict with case-variant keys for a realistic test
        pass

    def test_case_insensitive_duplicate(self) -> None:
        entries = {"Smith2023": {"title": "A"}, "smith2023": {"title": "B"}}
        dups = detect_duplicate_keys(entries)
        assert "smith2023" in dups

    def test_multiple_duplicates(self) -> None:
        entries = {
            "Smith2023": {"title": "A"},
            "smith2023": {"title": "B"},
            "Jones2024": {"title": "C"},
            "jones2024": {"title": "D"},
        }
        dups = detect_duplicate_keys(entries)
        assert len(dups) == 2

    def test_empty_dict(self) -> None:
        assert detect_duplicate_keys({}) == []

    def test_single_entry_no_dup(self) -> None:
        entries = {"only": {"title": "Solo"}}
        assert detect_duplicate_keys(entries) == []


# ===================================================================
# validate_entry_type
# ===================================================================
class TestValidateEntryType:
    def test_valid_article(self) -> None:
        assert validate_entry_type("article") == []

    def test_valid_book(self) -> None:
        assert validate_entry_type("book") == []

    def test_valid_inproceedings(self) -> None:
        assert validate_entry_type("inproceedings") == []

    def test_case_insensitive(self) -> None:
        assert validate_entry_type("Article") == []
        assert validate_entry_type("BOOK") == []

    def test_unknown_type(self) -> None:
        findings = validate_entry_type("patent")
        assert len(findings) == 1
        assert findings[0]["code"] == "unknown_entry_type"
        assert findings[0]["severity"] == "warning"

    def test_all_valid_types(self) -> None:
        for etype in VALID_ENTRY_TYPES:
            assert validate_entry_type(etype) == [], f"{etype} should be valid"

    def test_empty_string_type(self) -> None:
        findings = validate_entry_type("")
        assert len(findings) == 1
        assert findings[0]["code"] == "unknown_entry_type"


# ===================================================================
# validate_required_fields
# ===================================================================
class TestValidateRequiredFields:
    def test_article_all_required_present(self) -> None:
        fields = {"author": "Smith", "title": "Foo", "journal": "Bar", "year": "2023"}
        assert validate_required_fields("article", fields, "smith2023") == []

    def test_article_missing_journal(self) -> None:
        fields = {"author": "Smith", "title": "Foo", "year": "2023"}
        findings = validate_required_fields("article", fields, "smith2023")
        assert len(findings) == 1
        assert findings[0]["code"] == "missing_required_field"
        assert "journal" in findings[0]["message"]
        assert findings[0]["severity"] == "error"

    def test_article_missing_multiple_fields(self) -> None:
        fields = {"title": "Foo"}
        findings = validate_required_fields("article", fields, "smith2023")
        assert len(findings) == 3  # author, journal, year

    def test_unknown_type_no_check(self) -> None:
        # Unknown types have no required fields defined
        assert validate_required_fields("patent", {"title": "X"}, "p1") == []

    def test_misc_minimal_fields(self) -> None:
        fields = {"author": "A", "title": "B", "year": "2023"}
        assert validate_required_fields("misc", fields, "m1") == []

    def test_book_requires_publisher(self) -> None:
        fields = {"author": "A", "title": "B", "year": "2023"}
        findings = validate_required_fields("book", fields, "b1")
        assert len(findings) == 1
        assert "publisher" in findings[0]["message"]

    def test_phdthesis_requires_school(self) -> None:
        fields = {"author": "A", "title": "B", "year": "2023"}
        findings = validate_required_fields("phdthesis", fields, "phd1")
        assert len(findings) == 1
        assert "school" in findings[0]["message"]


# ===================================================================
# validate_doi_format
# ===================================================================
class TestValidateDoiFormat:
    def test_valid_doi(self) -> None:
        assert validate_doi_format("10.1000/xyz123", "entry1") == []

    def test_valid_doi_long_registrant(self) -> None:
        assert validate_doi_format("10.123456789/abcdef", "e1") == []

    def test_invalid_no_prefix(self) -> None:
        findings = validate_doi_format("xyz123", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "malformed_doi"

    def test_invalid_short_registrant(self) -> None:
        findings = validate_doi_format("10.12/abc", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "malformed_doi"

    def test_invalid_no_slash(self) -> None:
        findings = validate_doi_format("10.1234", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "malformed_doi"

    def test_empty_doi(self) -> None:
        findings = validate_doi_format("", "e1")
        assert len(findings) == 1

    def test_real_world_doi(self) -> None:
        assert validate_doi_format("10.1038/s41586-023-06600-9", "e1") == []

    def test_url_form_is_invalid(self) -> None:
        # Our validator expects bare DOI, not full URL
        findings = validate_doi_format("https://doi.org/10.1000/xyz123", "e1")
        assert len(findings) == 1


# ===================================================================
# validate_year_range
# ===================================================================
class TestValidateYearRange:
    def test_valid_recent_year(self) -> None:
        assert validate_year_range("2023", "e1") == []

    def test_valid_old_year(self) -> None:
        assert validate_year_range("1950", "e1") == []

    def test_boundary_1900(self) -> None:
        assert validate_year_range("1900", "e1") == []

    def test_boundary_2030(self) -> None:
        assert validate_year_range("2030", "e1") == []

    def test_too_old(self) -> None:
        findings = validate_year_range("1899", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "suspicious_year"
        assert findings[0]["severity"] == "warning"

    def test_too_new(self) -> None:
        findings = validate_year_range("2031", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "suspicious_year"

    def test_non_numeric(self) -> None:
        findings = validate_year_range("abc", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "invalid_year"
        assert findings[0]["severity"] == "error"

    def test_empty_year(self) -> None:
        findings = validate_year_range("", "e1")
        assert len(findings) == 1
        assert findings[0]["code"] == "invalid_year"

    def test_year_with_whitespace(self) -> None:
        assert validate_year_range("  2023  ", "e1") == []


# ===================================================================
# validate_bibliography (integration)
# ===================================================================
class TestValidateBibliography:
    def test_clean_entries_no_findings(self) -> None:
        entries = {
            "smith2023": {
                "author": "Smith",
                "title": "A Study",
                "journal": "Nature",
                "year": "2023",
                "doi": "10.1038/s41586-023-001",
            },
        }
        entry_types = {"smith2023": "article"}
        findings = validate_bibliography(entries, entry_types)
        assert findings == []

    def test_duplicate_keys_flagged(self) -> None:
        entries = {
            "Smith2023": {"title": "A"},
            "smith2023": {"title": "B"},
        }
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        assert "duplicate_key" in codes

    def test_malformed_doi_flagged(self) -> None:
        entries = {
            "e1": {"doi": "not-a-doi"},
        }
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        assert "malformed_doi" in codes

    def test_invalid_year_flagged(self) -> None:
        entries = {
            "e1": {"year": "abc"},
        }
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        assert "invalid_year" in codes

    def test_missing_required_field_flagged(self) -> None:
        entries = {
            "e1": {"author": "Smith", "title": "Foo"},  # missing journal, year
        }
        entry_types = {"e1": "article"}
        findings = validate_bibliography(entries, entry_types)
        codes = [f["code"] for f in findings]
        assert "missing_required_field" in codes

    def test_unknown_type_flagged(self) -> None:
        entries = {"e1": {"title": "X"}}
        entry_types = {"e1": "patent"}
        findings = validate_bibliography(entries, entry_types)
        codes = [f["code"] for f in findings]
        assert "unknown_entry_type" in codes

    def test_multiple_findings_per_entry(self) -> None:
        entries = {
            "e1": {"year": "abc", "doi": "bad"},
        }
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        assert "invalid_year" in codes
        assert "malformed_doi" in codes

    def test_no_entry_types_skips_type_checks(self) -> None:
        entries = {
            "e1": {"author": "Smith", "title": "Foo"},
        }
        # No entry_types → no type/required-fields checks
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        assert "missing_required_field" not in codes
        assert "unknown_entry_type" not in codes

    def test_empty_entries_no_findings(self) -> None:
        assert validate_bibliography({}) == []

    def test_fields_normalized_before_doi_check(self) -> None:
        """DOI key should be recognized even if provided in uppercase."""
        entries = {"e1": {"DOI": "10.1000/xyz"}}
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        # Should NOT have malformed_doi — valid DOI was present
        assert "malformed_doi" not in codes

    def test_suspicious_year_in_integration(self) -> None:
        entries = {"e1": {"year": "1800"}}
        findings = validate_bibliography(entries)
        codes = [f["code"] for f in findings]
        assert "suspicious_year" in codes

    def test_arxiv_article_flagged_as_preprint(self) -> None:
        entries = {
            "smith2024": {"author": "Smith", "title": "T", "journal": "arXiv", "year": "2024"}
        }
        findings = validate_bibliography(entries, {"smith2024": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 1
        assert preprint[0]["severity"] == "warning"
        assert "arXiv" in preprint[0]["message"]
        assert "peer review" in preprint[0]["message"]

    def test_biorxiv_older_preprint_is_info(self) -> None:
        entries = {
            "jones2020": {"author": "Jones", "title": "T", "journal": "bioRxiv", "year": "2020"}
        }
        findings = validate_bibliography(entries, {"jones2020": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 1
        assert preprint[0]["severity"] == "info"

    def test_nature_not_flagged(self) -> None:
        entries = {"nature": {"author": "Doe", "title": "T", "journal": "Nature", "year": "2024"}}
        findings = validate_bibliography(entries, {"nature": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 0

    def test_all_10_preprint_venues_detected(self) -> None:
        for venue in PREPRINT_VENUES:
            entries = {
                f"test_{venue}": {"author": "A", "title": "T", "journal": venue, "year": "2025"}
            }
            findings = validate_bibliography(entries, {f"test_{venue}": "article"})
            preprint = [f for f in findings if f["code"] == "preprint_citation"]
            assert len(preprint) == 1, f"Venue '{venue}' not detected"

    def test_booktitle_field_checked(self) -> None:
        entries = {"conf": {"author": "Lee", "title": "T", "booktitle": "SSRN", "year": "2024"}}
        findings = validate_bibliography(entries, {"conf": "inproceedings"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 1
        assert "SSRN" in preprint[0]["message"]

    def test_compound_venue_name_detected(self) -> None:
        entries = {
            "e1": {
                "author": "X",
                "title": "T",
                "journal": "arXiv preprint arXiv:2301.00001",
                "year": "2024",
            }
        }
        findings = validate_bibliography(entries, {"e1": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 1

    def test_case_insensitive_venue(self) -> None:
        entries = {"e1": {"author": "X", "title": "T", "journal": "biorxiv", "year": "2024"}}
        findings = validate_bibliography(entries, {"e1": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 1

    def test_no_year_still_detected_as_info(self) -> None:
        entries = {"e1": {"author": "X", "title": "T", "journal": "medRxiv"}}
        findings = validate_bibliography(entries, {"e1": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 1
        assert preprint[0]["severity"] == "info"

    def test_empty_venue_no_finding(self) -> None:
        entries = {"e1": {"author": "X", "title": "T", "journal": "", "year": "2024"}}
        findings = validate_bibliography(entries, {"e1": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 0

    def test_no_journal_no_booktitle_no_finding(self) -> None:
        entries = {"e1": {"author": "X", "title": "T", "year": "2024"}}
        findings = validate_bibliography(entries, {"e1": "article"})
        preprint = [f for f in findings if f["code"] == "preprint_citation"]
        assert len(preprint) == 0


# ===================================================================
# detect_preprint_venues (unit tests)
# ===================================================================
class TestDetectPreprintVenues:
    def test_returns_list(self) -> None:
        result = detect_preprint_venues({"journal": "arXiv", "year": "2024"}, "key1")
        assert isinstance(result, list)

    def test_no_venue_empty(self) -> None:
        result = detect_preprint_venues({"title": "Foo"}, "key1")
        assert result == []

    def test_venue_preferred_over_booktitle(self) -> None:
        """When both journal and booktitle exist, journal is checked first."""
        fields = {"journal": "Nature", "booktitle": "arXiv", "year": "2024"}
        result = detect_preprint_venues(fields, "key1")
        # Nature is not a preprint → no finding
        assert result == []

    def test_preprint_venues_count(self) -> None:
        assert len(PREPRINT_VENUES) == 10
