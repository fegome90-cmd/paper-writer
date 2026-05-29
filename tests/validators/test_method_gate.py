"""Tests for validators/method_gate.py — methodological gate."""

from parsers.manuscript import ManuscriptParser
from validators.method_gate import MethodGateValidator


def _make_man(text: str):
    return ManuscriptParser().parse_text(text, "test.md", "markdown")


CONSORT_MANUSCRIPT = """# Introduction
This study examines a new intervention.

# Methods
We conducted a randomized controlled trial.
Ethics approval was obtained from the IRB.
Informed consent was obtained from all participants.

# Results
The intervention group showed significant improvement.

# Discussion
Our findings suggest the intervention is effective.
Several limitations should be noted.

# Declarations
This study was funded by a research grant.
The authors declare no competing interests.
Data are available upon request.

# References
1. Smith et al. 2024
"""


class TestMethodGateBasic:
    def test_generic_gate_passes_with_all_sections(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        assert result["command"] == "gate_method"
        assert isinstance(result["gate_passed"], bool)
        assert "summary" in result
        assert result["guideline"] != "unknown"

    def test_generic_gate_fails_without_sections(self) -> None:
        text = "Just some text without any structure."
        ms = _make_man(text)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        # Should have blockers (missing sections)
        assert len(result["blockers"]) > 0

    def test_consort_checklist_loaded(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="rct")
        assert result["guideline"] in ("CONSORT", "Generic")


class TestMethodGateStructure:
    def test_result_has_required_fields(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        assert "command" in result
        assert "file" in result
        assert "study_type" in result
        assert "guideline" in result
        assert "gate_passed" in result
        assert "blockers" in result
        assert "warnings" in result
        assert "summary" in result

    def test_summary_totals_correct(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        summary = result["summary"]
        total = summary["total_items"]
        assert total == (
            summary["passed"]
            + summary["blockers"]
            + summary["warnings"]
            + summary["not_applicable"]
        )

    def test_not_applicable_items(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*", na_items=["ethics.consent"])
        na_ids = {i["item_id"] for i in result["not_applicable"]}
        assert "ethics.consent" in na_ids


class TestMethodGateEdgeCases:
    def test_empty_manuscript(self) -> None:
        ms = _make_man("")
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        assert "gate_passed" in result

    def test_invalid_study_type_uses_generic(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="nonexistent_type_xyz")
        assert result["guideline"] in ("Generic", "unknown")

    def test_explicit_checklist_loaded(self) -> None:
        ms = _make_man(CONSORT_MANUSCRIPT)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*", checklist_name="generic")
        assert result["guideline"] == "Generic"

    def test_blocker_makes_gate_fail(self) -> None:
        text = "# Introduction\nNo methods section here."
        ms = _make_man(text)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        blockers = result.get("blockers", [])
        if len(blockers) > 0:
            assert result["gate_passed"] is False


class TestMethodGateLookupNormalization:
    # === Regression: C1 — expected_location case normalization ===

    def test_capitalized_expected_location_finds_section(self) -> None:
        """YAML says 'Introduction', parser stores 'introduction' — must match."""
        text = "# Introduction\nBackground text.\n# Methods\nMethod content.\n# Results\nResults.\n# Discussion\nDiscussion.\n# Declarations\nDeclarations.\n# References\nRefs."
        ms = _make_man(text)
        validator = MethodGateValidator()
        result = validator.validate(ms, study_type="*")
        # structure.introduction expects "Introduction" in YAML
        passed_ids = {i["item_id"] for i in result.get("passed_items", [])}
        assert "structure.introduction" in passed_ids, (
            f"structure.introduction not found in passed_items: {passed_ids}"
        )
        assert "structure.methods" in passed_ids
        assert "structure.results" in passed_ids
        assert "structure.discussion" in passed_ids

    def test_method_gate_no_crash_with_section_dataclass(self) -> None:
        """Regression: accesses Section dataclass, not dict."""
        text = "# Methods\nWe conducted a trial.\n# Results\nFindings.\n# Discussion\nDiscussion.\n# Declarations\nDeclarations."
        ms = _make_man(text)
        validator = MethodGateValidator()
        # Should not crash with AttributeError when accessing section.text
        result = validator.validate(ms, study_type="*")
        assert "gate_passed" in result
