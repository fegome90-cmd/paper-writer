"""Tests for validators/preset.py — journal preset validation.

Covers: validate_preset, REQUIRED_PRESET_FIELDS, empty/invalid/valid presets.
"""

from __future__ import annotations

from validators.preset import REQUIRED_PRESET_FIELDS, validate_preset


class TestValidatePreset:
    # --- Empty / None ---
    def test_empty_dict(self) -> None:
        findings = validate_preset({})
        codes = [f["code"] for f in findings]
        assert "empty_preset" in codes

    def test_none_preset(self) -> None:
        # Function accepts dict[str, Any]; None should trigger empty_preset
        findings = validate_preset(None)  # type: ignore[arg-type]
        assert any(f["code"] == "empty_preset" for f in findings)

    # --- Valid minimal preset ---
    def test_valid_minimal_preset(self) -> None:
        preset = {
            "name": "Nature",
            "format": "docx",
            "citation_style": "apa",
            "required_sections": ["introduction", "methods", "results"],
        }
        assert validate_preset(preset) == []

    def test_valid_with_optional_fields(self) -> None:
        preset = {
            "name": "Science",
            "format": "pdf",
            "citation_style": "vancouver",
            "required_sections": ["abstract", "body"],
            "max_words": 5000,
        }
        assert validate_preset(preset) == []

    # --- Missing required fields ---
    def test_missing_name(self) -> None:
        preset = {"format": "docx", "citation_style": "apa", "required_sections": ["intro"]}
        findings = validate_preset(preset)
        assert any(f["code"] == "missing_preset_field" and f["location"] == "name" for f in findings)

    def test_missing_format(self) -> None:
        preset = {"name": "N", "citation_style": "apa", "required_sections": ["intro"]}
        findings = validate_preset(preset)
        assert any(f["location"] == "format" for f in findings)

    def test_missing_citation_style(self) -> None:
        preset = {"name": "N", "format": "docx", "required_sections": ["intro"]}
        findings = validate_preset(preset)
        assert any(f["location"] == "citation_style" for f in findings)

    def test_missing_required_sections(self) -> None:
        preset = {"name": "N", "format": "docx", "citation_style": "apa"}
        findings = validate_preset(preset)
        assert any(f["location"] == "required_sections" for f in findings)

    def test_all_fields_missing(self) -> None:
        findings = validate_preset({"extra": "stuff"})
        missing_locs = {f["location"] for f in findings if f["code"] == "missing_preset_field"}
        assert missing_locs == REQUIRED_PRESET_FIELDS

    # --- required_sections validation ---
    def test_sections_must_be_list(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": "not-a-list",
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_sections" for f in findings)

    def test_sections_must_be_nonempty(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": [],
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "empty_sections" for f in findings)

    # --- format validation ---
    def test_valid_formats(self) -> None:
        for fmt in ("docx", "pdf", "html", "latex"):
            preset = {
                "name": "N", "format": fmt, "citation_style": "apa",
                "required_sections": ["intro"],
            }
            fmt_findings = [f for f in validate_preset(preset) if f["code"] == "invalid_format"]
            assert fmt_findings == [], f"Format '{fmt}' should be valid"

    def test_invalid_format_warning(self) -> None:
        preset = {
            "name": "N", "format": "rtf", "citation_style": "apa",
            "required_sections": ["intro"],
        }
        findings = validate_preset(preset)
        fmt_findings = [f for f in findings if f["code"] == "invalid_format"]
        assert len(fmt_findings) == 1
        assert fmt_findings[0]["severity"] == "warning"

    # --- max_words validation ---
    def test_valid_max_words(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": ["intro"], "max_words": 8000,
        }
        assert validate_preset(preset) == []

    def test_max_words_zero(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": ["intro"], "max_words": 0,
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_max_words" for f in findings)

    def test_max_words_negative(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": ["intro"], "max_words": -100,
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_max_words" for f in findings)

    def test_max_words_string(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": ["intro"], "max_words": "5000",
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_max_words" for f in findings)

    def test_max_words_float(self) -> None:
        preset = {
            "name": "N", "format": "docx", "citation_style": "apa",
            "required_sections": ["intro"], "max_words": 5.5,
        }
        findings = validate_preset(preset)
        assert any(f["code"] == "invalid_max_words" for f in findings)

    # --- Multiple findings ---
    def test_multiple_issues_at_once(self) -> None:
        preset = {
            "format": "txt",
            "required_sections": "not-a-list",
            "max_words": -1,
        }
        findings = validate_preset(preset)
        codes = {f["code"] for f in findings}
        assert "missing_preset_field" in codes  # name, citation_style
        assert "invalid_format" in codes
        assert "invalid_sections" in codes
        assert "invalid_max_words" in codes
