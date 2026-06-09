"""Claim-reference alignment verification.

Extends existing ClaimsValidator with citation verification.
Does NOT replace ClaimsValidator — adds alignment checks on top.
"""

from __future__ import annotations

import re
from typing import Any

from engine.deduplicator import deduplicate_findings
from parsers.manuscript import Manuscript
from validators.citation_verify import CitationVerifyValidator


class ClaimAlignmentValidator:
    """Verify that claims have valid citation support.

    Runs existing ClaimsValidator for detection, then verifies each
    claim's citation reference via CitationVerifyValidator.
    """

    def __init__(self, citation_verifier: CitationVerifyValidator | None = None) -> None:
        from validators.claims import ClaimsValidator

        self.claims_validator = ClaimsValidator()
        self.citation_verifier = citation_verifier or CitationVerifyValidator(offline=True)

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Run claim detection then verify each claim's citation support."""
        candidates = self.claims_validator.validate(manuscript)
        alignment_findings: list[dict[str, Any]] = []

        for candidate in candidates:
            citation_ref = self._extract_citation_from_claim(candidate)
            if citation_ref is None:
                alignment_findings.append(self._make_unsupported_finding(candidate))
                continue

            verification = self.citation_verifier.verify_single(citation_ref)
            status = self._classify_alignment(verification)

            if status != "supported":
                alignment_findings.append(self._make_alignment_finding(candidate, status))

        return deduplicate_findings(alignment_findings)

    def _extract_citation_from_claim(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        """Extract cited reference string from claim sentence.

        Looks for (Author, Year) or [N] patterns.
        """
        text = candidate.get("text", "")

        # Pattern: (Author, Year) or (Author et al., Year)
        m = re.search(r"\(([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}[a-z]?)\)", text)
        if m:
            return {"inline_citation": m.group(1), "line": candidate.get("line", 0)}

        # Pattern: [N]
        m = re.search(r"\[(\d+)\]", text)
        if m:
            return {"ref_number": m.group(1), "line": candidate.get("line", 0)}

        return None

    def _classify_alignment(self, verification: dict[str, Any] | None) -> str:
        """Classify claim-citation alignment."""
        if verification is None:
            return "supported"
        severity = verification.get("severity", "P2")
        if severity == "P0":
            return "unsupported"
        if severity == "P1":
            return "overclaim"
        return "supported"

    def _make_unsupported_finding(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Create P1 finding for claim without citation."""
        return {
            "command": "audit_claims",
            "rule_id": "claim_alignment.unsupported",
            "finding_id": "",
            "severity": "P1",
            "file": "",
            "line": candidate.get("line", 0),
            "column": candidate.get("column", 0),
            "span": candidate.get("span", [0, 0]),
            "message": "Claim lacks verifiable citation support",
            "section": candidate.get("section", "unknown"),
            "evidence": {"claim_type": candidate.get("claim_type", "unknown")},
            "recommendation": "Add or verify citation support for this claim.",
        }

    def _make_alignment_finding(self, candidate: dict[str, Any], status: str) -> dict[str, Any]:
        """Create finding based on alignment status."""
        rule_id = f"claim_alignment.{status}"
        return {
            "command": "audit_claims",
            "rule_id": rule_id,
            "finding_id": "",
            "severity": "P1",
            "file": "",
            "line": candidate.get("line", 0),
            "column": candidate.get("column", 0),
            "span": candidate.get("span", [0, 0]),
            "message": f"Claim citation alignment: {status}",
            "section": candidate.get("section", "unknown"),
            "evidence": {"status": status, "claim_type": candidate.get("claim_type", "unknown")},
            "recommendation": "Add or verify citation support for this claim.",
        }
