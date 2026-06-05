"""Tests for uncited assertion detection in prose rules."""
from __future__ import annotations

from validators.prose import CITATION_MARKER_RE, ProseValidator


class TestCitationMarkerRegex:
    """Test CITATION_MARKER_RE matches common citation patterns."""

    def test_latex_cite(self) -> None:
        assert CITATION_MARKER_RE.search(r"This shows \cite{smith2024} the effect")

    def test_numeric_bracket(self) -> None:
        assert CITATION_MARKER_RE.search("This shows [1] the effect")

    def test_numeric_range(self) -> None:
        assert CITATION_MARKER_RE.search("This shows [1-3, 5] the effect")

    def test_author_year(self) -> None:
        assert CITATION_MARKER_RE.search("This shows (Smith, 2024) the effect")

    def test_author_et_al_year(self) -> None:
        assert CITATION_MARKER_RE.search("This shows (Smith et al., 2024) the effect")

    def test_no_citation(self) -> None:
        assert not CITATION_MARKER_RE.search("This shows the effect clearly.")

    def test_pandoc_at_key(self) -> None:
        # Pandoc [@key] — now detected (added Pandoc citation support)
        text = "This shows [@smith2024] the effect"
        assert CITATION_MARKER_RE.search(text)


class TestUncitedAssertionDetection:
    """Test that prose rules flag uncited empirical claims."""

    def setup_method(self) -> None:
        self.validator = ProseValidator()

    def test_causal_verb_without_citation_flagged(self) -> None:
        """Causal verb without citation gets uncited_ prefix."""
        # Verify the rule exists and requires citation
        rule = next(
            r for r in self.validator.registry
            if r["id"] == "prose.causal.strong_verb"
        )
        assert "citation" in rule.get("evidence_required", [])

    def test_causal_verb_with_citation_not_uncited(self) -> None:
        """Causal verb with citation marker doesn't get uncited_ prefix."""
        rule = next(
            r for r in self.validator.registry
            if r["id"] == "prose.causal.strong_verb"
        )
        assert "citation" in rule.get("evidence_required", [])

    def test_nine_rules_require_citation(self) -> None:
        """Verify exactly 9 rules require citation evidence."""
        citation_rules = [
            r for r in self.validator.registry
            if "citation" in r.get("evidence_required", [])
        ]
        assert len(citation_rules) == 9

    def test_overclaim_definitive_requires_citation(self) -> None:
        """P0 overclaim rule requires citation."""
        rule = next(
            r for r in self.validator.registry
            if r["id"] == "prose.overclaim.definitive_causal"
        )
        assert "citation" in rule.get("evidence_required", [])
        assert rule["severity"] == "P0"

    def test_hedging_rules_dont_require_citation(self) -> None:
        """Style rules (hedging, weasel) don't require citation."""
        hedging_rules = [
            r for r in self.validator.registry
            if r["rule_group"] == "prose.hedging"
        ]
        for rule in hedging_rules:
            assert "citation" not in rule.get("evidence_required", [])

    def test_nominalization_rules_dont_require_citation(self) -> None:
        """Nominalization rules don't require citation."""
        nom_rules = [
            r for r in self.validator.registry
            if r["rule_group"] == "prose.nominalization"
        ]
        for rule in nom_rules:
            assert "citation" not in rule.get("evidence_required", [])

    def test_citation_required_groups(self) -> None:
        """Only causal, overclaim, and quantifier groups have citation rules."""
        citation_groups = {
            r["rule_group"]
            for r in self.validator.registry
            if "citation" in r.get("evidence_required", [])
        }
        assert citation_groups == {"prose.causal", "prose.overclaim", "prose.quantifier"}
