"""Tests for validators.writing_quality — AI-typical term detection."""
from __future__ import annotations

from parsers.manuscript import ManuscriptParser
from validators.writing_quality import WritingQualityValidator


def _make_manuscript(text: str = ""):
    """Build a Manuscript using ManuscriptParser for correct SourceMap."""
    return ManuscriptParser().parse_text(text)


class TestWritingQualityValidator:
    def test_delve_in_abstract_produces_p1(self):
        text = "Abstract\nWe delve into the analysis of the data."
        manuscript = _make_manuscript(text)
        validator = WritingQualityValidator()
        findings = validator.validate(manuscript)
        delve_findings = [f for f in findings if "delve" in f["rule_id"]]
        assert len(delve_findings) > 0
        assert delve_findings[0]["severity"] == "P1"

    def test_robust_in_results_produces_p2(self):
        text = "Results\nThe model achieves robust performance."
        manuscript = _make_manuscript(text)
        validator = WritingQualityValidator()
        findings = validator.validate(manuscript)
        robust_findings = [f for f in findings if "robust" in f["rule_id"]]
        assert len(robust_findings) > 0
        assert robust_findings[0]["severity"] == "P2"

    def test_robust_in_abstract_produces_p1(self):
        """Section-severity override: abstract/conclusions → P1."""
        text = "Abstract\nOur robust approach yields significant results."
        manuscript = _make_manuscript(text)
        validator = WritingQualityValidator()
        findings = validator.validate(manuscript)
        robust_findings = [f for f in findings if "robust" in f["rule_id"]]
        assert len(robust_findings) > 0
        assert robust_findings[0]["severity"] == "P1"

    def test_whitelist_exclusion(self):
        text = "Abstract\nWe delve into the analysis."
        manuscript = _make_manuscript(text)
        validator = WritingQualityValidator(whitelist={"delve"})
        findings = validator.validate(manuscript)
        delve_findings = [f for f in findings if "delve" in f["rule_id"]]
        assert len(delve_findings) == 0

    def test_all_existing_prose_tests_still_pass(self):
        """Sanity check: validator loads rules and runs without error."""
        text = "Abstract\nFurthermore, we delve into the intricate tapestry of data."
        manuscript = _make_manuscript(text)
        validator = WritingQualityValidator()
        findings = validator.validate(manuscript)
        assert isinstance(findings, list)
        assert len(findings) > 0
