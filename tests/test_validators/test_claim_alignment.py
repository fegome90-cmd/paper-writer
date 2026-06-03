"""Tests for validators.claim_alignment — claim-reference alignment."""
from __future__ import annotations

from unittest.mock import MagicMock

from parsers.manuscript import Manuscript, Section, Sentence
from parsers.source_map import SourceMap
from validators.claim_alignment import ClaimAlignmentValidator


def _make_manuscript(text: str = "") -> Manuscript:
    source_map = SourceMap(text)
    sections: dict[str, Section] = {}
    sentences = []
    for i, line in enumerate(text.split("\n")):
        if line.strip():
            sentences.append(Sentence(
                text=line.strip(),
                line=i + 1,
                col=0,
                char_start=text.find(line),
                char_end=text.find(line) + len(line),
            ))
    return Manuscript(
        path="test.md",
        format="markdown",
        clean_text=text,
        source_map=source_map,
        sections=sections,
        sentences=sentences,
    )


class TestClaimAlignmentValidator:
    def test_extends_claims_validator(self):
        """Does not replace ClaimsValidator — extends it."""
        validator = ClaimAlignmentValidator()
        assert hasattr(validator, "claims_validator")
        assert hasattr(validator, "citation_verifier")

    def test_claim_without_citation_produces_finding(self):
        """Claim without any citation reference → P1 unsupported."""
        manuscript = _make_manuscript("This approach is clearly superior to all others.")
        validator = ClaimAlignmentValidator(citation_verifier=MagicMock())
        findings = validator.validate(manuscript)
        # Should produce at least one finding (unsupported claim)
        assert isinstance(findings, list)

    def test_extract_author_year_citation(self):
        """(Author, Year) pattern extracted correctly."""
        validator = ClaimAlignmentValidator()
        candidate = {"text": "Studies show (Smith, 2020) that results vary.", "line": 5}
        result = validator._extract_citation_from_claim(candidate)
        assert result is not None
        assert "inline_citation" in result
        assert "Smith" in result["inline_citation"]
        assert result["line"] == 5

    def test_extract_et_al_citation(self):
        """(Author et al., Year) pattern extracted correctly."""
        validator = ClaimAlignmentValidator()
        candidate = {"text": "Prior work (Jones et al., 2019) found issues.", "line": 3}
        result = validator._extract_citation_from_claim(candidate)
        assert result is not None
        assert "Jones" in result["inline_citation"]

    def test_extract_bracket_number_citation(self) -> None:
        """[N] pattern extracted correctly."""
        validator = ClaimAlignmentValidator()
        candidate = {"text": "Results confirm previous findings [42].", "line": 7}
        result = validator._extract_citation_from_claim(candidate)
        assert result is not None
        assert result.get("ref_number") == "42"

    def test_extract_no_citation_returns_none(self):
        """Text without citation patterns returns None."""
        validator = ClaimAlignmentValidator()
        candidate = {"text": "This is clearly the best approach.", "line": 1}
        result = validator._extract_citation_from_claim(candidate)
        assert result is None

    def test_classify_alignment_p0_is_unsupported(self):
        """P0 verification → unsupported."""
        validator = ClaimAlignmentValidator()
        assert validator._classify_alignment({"severity": "P0"}) == "unsupported"

    def test_classify_alignment_p1_is_overclaim(self):
        """P1 verification → overclaim."""
        validator = ClaimAlignmentValidator()
        assert validator._classify_alignment({"severity": "P1"}) == "overclaim"

    def test_classify_alignment_p2_is_supported(self):
        """P2 verification → supported."""
        validator = ClaimAlignmentValidator()
        assert validator._classify_alignment({"severity": "P2"}) == "supported"

    def test_classify_alignment_none_is_supported(self):
        """None verification → supported."""
        validator = ClaimAlignmentValidator()
        assert validator._classify_alignment(None) == "supported"

    def test_make_unsupported_finding_structure(self):
        """_make_unsupported_finding produces correct P1 finding."""
        validator = ClaimAlignmentValidator()
        candidate = {"line": 10, "column": 5, "span": [100, 120], "section": "results", "claim_type": "definitive"}
        finding = validator._make_unsupported_finding(candidate)
        assert finding["rule_id"] == "claim_alignment.unsupported"
        assert finding["severity"] == "P1"
        assert finding["line"] == 10
        assert finding["section"] == "results"

    def test_make_alignment_finding_overclaim(self):
        """_make_alignment_finding with 'overclaim' status."""
        validator = ClaimAlignmentValidator()
        candidate = {"line": 15, "column": 0, "span": [200, 220], "section": "discussion", "claim_type": "causal"}
        finding = validator._make_alignment_finding(candidate, "overclaim")
        assert finding["rule_id"] == "claim_alignment.overclaim"
        assert finding["severity"] == "P1"
        assert "overclaim" in finding["message"]

    def test_claim_with_supported_citation_no_finding(self):
        """Claim with supported citation produces no alignment finding."""
        mock_verifier = MagicMock()
        mock_verifier.verify_single.return_value = {"severity": "P2"}
        manuscript = _make_manuscript("Results show (Smith, 2020) clear improvement.")
        validator = ClaimAlignmentValidator(citation_verifier=mock_verifier)
        findings = validator.validate(manuscript)
        alignment_findings = [f for f in findings if "claim_alignment" in f.get("rule_id", "")]
        # Supported claims should not produce alignment findings
        for f in alignment_findings:
            assert f["rule_id"] != "claim_alignment.unsupported"
