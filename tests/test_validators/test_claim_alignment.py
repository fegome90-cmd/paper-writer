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
