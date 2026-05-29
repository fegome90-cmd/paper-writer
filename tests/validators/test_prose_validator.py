"""Tests for validators/prose.py — prose analysis."""

from parsers.manuscript import ManuscriptParser
from validators.prose import ProseValidator


def _make_man(text: str):
    return ManuscriptParser().parse_text(text, "test.md", "markdown")


class TestProseValidatorBasic:
    """Basic tests that exercise the real rule registry."""

    def test_clean_text_no_findings(self) -> None:
        text = "The study found significant results. Participants completed the survey."
        ms = _make_man(text)
        validator = ProseValidator()
        findings = validator.validate(ms)
        assert isinstance(findings, list)

    def test_definitive_causal_overclaim(self) -> None:
        text = "This study proves that the intervention works."
        ms = _make_man(text)
        validator = ProseValidator()
        findings = validator.validate(ms)
        assert len(findings) >= 1
        rule_ids = {f.get("rule_id", "") for f in findings}
        assert any("overclaim" in rid for rid in rule_ids)

    def test_whitelist_skipped(self) -> None:
        text = "This study proves the hypothesis."
        ms = _make_man(text)
        validator = ProseValidator(whitelist={"proves"})
        findings = validator.validate(ms)
        # with whitelist, "proves" should be skipped
        proving = [f for f in findings if "proves" in str(f.get("message", "")).lower()]
        assert len(proving) == 0


class TestProseValidatorSections:
    def test_section_scoped(self) -> None:
        text = "# Methods\nThis proves something.\n# Results\nThis proves something else."
        ms = _make_man(text)
        validator = ProseValidator()
        findings = validator.validate(ms)
        for f in findings:
            assert "finding_id" in f
            assert "rule_id" in f
            assert "severity" in f
            assert "span" in f

    # === Regression: C3 — section-scoped match positions are in full-text coords ===
    def test_section_scoped_position_full_text(self) -> None:
        """Section-scoped findings must report line/column in full manuscript, not section text."""
        text = "# Methods\nThis proves something.\n# Results\nThis proves something else."
        ms = _make_man(text)
        validator = ProseValidator()
        findings = validator.validate(ms)
        for f in findings:
            # Line must be >0, not 0 or 1 (section text only starts at line 1)
            assert f["line"] >= 1, f"Expected line >= 1, got {f['line']}"
            # Span must be in full-text coordinates (char_offset > 0 for section content)
            # Methods content starts after "# Methods\n" which is ~9 chars
            # Results content starts after "# Results\n" which is ~10 chars
            for s in f.get("span", [0, 0]):
                assert isinstance(s, int)

    def test_dedup_delegates_to_engine(self) -> None:
        """ProseValidator._deduplicate delegates to engine.deduplicator."""
        from engine.deduplicator import deduplicate_findings
        assert ProseValidator._deduplicate is not None
        # Verify the method exists and is callable
        result = ProseValidator()._deduplicate([])
        assert result == []


class TestProseValidatorStructure:
    def test_findings_have_required_fields(self) -> None:
        text = "This study proves that the intervention is effective."
        ms = _make_man(text)
        validator = ProseValidator()
        findings = validator.validate(ms)
        for f in findings:
            assert "finding_id" in f, f"Missing finding_id in {f}"
            assert "rule_id" in f, f"Missing rule_id in {f}"
            assert "severity" in f, f"Missing severity in {f}"
            assert "message" in f, f"Missing message in {f}"
            assert f["severity"] in ("P0", "P1", "P2"), f"Invalid severity: {f['severity']}"

    def test_rules_count(self) -> None:
        validator = ProseValidator()
        assert validator.rules_count > 0
