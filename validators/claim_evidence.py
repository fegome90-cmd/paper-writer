"""Claim-evidence factual accuracy verification.

Compares claim sentences against screened evidence abstracts using
keyword overlap. Claims with low overlap are flagged as potential
hallucinations for human review.

Does NOT replace ClaimAlignmentValidator — this is a complementary
check focused on content accuracy, not citation existence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from engine.deduplicator import deduplicate_findings
from parsers.manuscript import Manuscript

# Stopwords excluded from overlap calculation
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "we",
        "our",
        "they",
        "their",
        "he",
        "she",
        "his",
        "her",
        "not",
        "no",
        "nor",
        "as",
        "if",
        "then",
        "than",
        "too",
        "very",
        "also",
        "just",
        "about",
        "above",
        "after",
        "again",
        "all",
        "am",
        "any",
        "because",
        "before",
        "below",
        "between",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "own",
        "same",
        "so",
        "some",
        "such",
        "up",
        "out",
        "over",
        "only",
        "into",
        "through",
        "during",
        "which",
        "what",
        "when",
        "where",
        "who",
        "whom",
        "how",
        "why",
        "while",
        "there",
        "here",
        "further",
        "once",
        "under",
        "until",
    }
)


def _tokenize(text: str) -> set[str]:
    """Extract meaningful tokens from text (lowercase, no stopwords)."""
    if not text:
        return set()
    text = text.lower()
    # Remove punctuation except hyphens within words
    text = re.sub(r"[^\w\s-]", " ", text)
    tokens = set(text.split())
    return tokens - _STOPWORDS - {""}


def compute_overlap(claim_tokens: set[str], evidence_tokens: set[str]) -> float:
    """Compute keyword overlap ratio: shared / claim tokens.

    Returns:
        Float between 0.0 and 1.0. Higher means more overlap.
    """
    if not claim_tokens:
        return 0.0
    shared = claim_tokens & evidence_tokens
    return len(shared) / len(claim_tokens)


class ClaimEvidenceValidator:
    """Verify claim content against screened evidence via keyword overlap.

    Compares each claim's text against the abstracts of screened evidence
    papers. Claims with low overlap (< threshold) are flagged as potential
    hallucinations.
    """

    def __init__(
        self,
        evidence_path: Path | None = None,
        overlap_threshold: float = 0.30,
    ) -> None:
        self.evidence_path = evidence_path
        self.overlap_threshold = overlap_threshold
        self._evidence_abstracts: list[str] = []
        self._evidence_tokens: list[set[str]] = []

        if evidence_path and evidence_path.exists():
            self._load_evidence(evidence_path)

    def _load_evidence(self, path: Path) -> None:
        """Load screened evidence abstracts."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        for paper in data.get("evidence", []):
            abstract = paper.get("abstract", "")
            if abstract:
                self._evidence_abstracts.append(abstract)
                self._evidence_tokens.append(_tokenize(abstract))

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Run factual accuracy checks on manuscript claims.

        Args:
            manuscript: Parsed manuscript with claims.

        Returns:
            List of findings for claims with low evidence overlap.
        """
        if not self._evidence_tokens:
            return []

        from validators.claims import ClaimsValidator

        claims_validator = ClaimsValidator()
        candidates = claims_validator.validate(manuscript)
        return self.check_claims(candidates)

    def check_claims(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check pre-extracted claim candidates against evidence.

        Args:
            candidates: List of claim candidate dicts with 'text' field.

        Returns:
            List of findings for claims with low evidence overlap.
        """
        if not self._evidence_tokens:
            return []

        findings: list[dict[str, Any]] = []
        for candidate in candidates:
            claim_text = candidate.get("text", "")
            claim_tokens = _tokenize(claim_text)

            if not claim_tokens:
                continue

            # Find best overlap across all evidence
            best_overlap = 0.0
            best_evidence_idx = -1
            for i, ev_tokens in enumerate(self._evidence_tokens):
                overlap = compute_overlap(claim_tokens, ev_tokens)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_evidence_idx = i

            if best_overlap < self.overlap_threshold:
                findings.append(
                    self._make_low_overlap_finding(candidate, best_overlap, best_evidence_idx)
                )

        return deduplicate_findings(findings)

    def _make_low_overlap_finding(
        self,
        candidate: dict[str, Any],
        overlap: float,
        evidence_idx: int,
    ) -> dict[str, Any]:
        """Create finding for a claim with low evidence overlap."""
        best_abstract = ""
        if 0 <= evidence_idx < len(self._evidence_abstracts):
            best_abstract = (
                self._evidence_abstracts[evidence_idx][:100] + "..."
                if len(self._evidence_abstracts[evidence_idx]) > 100
                else self._evidence_abstracts[evidence_idx]
            )

        line = candidate.get("line", 0)
        col = candidate.get("column", 0)
        span = candidate.get("span", None)
        if span is None or span == [0, 0]:
            # Derive unique span from line/col to prevent dedup collapse
            span = [line * 1000 + col, line * 1000 + col + 1]

        return {
            "command": "audit_factuality",
            "rule_id": "claim_evidence.low_overlap",
            "finding_id": "",
            "severity": "P2",
            "file": "",
            "line": line,
            "column": col,
            "span": span,
            "message": (f"Claim has low keyword overlap with evidence ({overlap:.0%})"),
            "section": candidate.get("section", "unknown"),
            "evidence": {
                "claim_snippet": candidate.get("text", "")[:150],
                "overlap_ratio": round(overlap, 3),
                "best_evidence_match": best_abstract,
                "claim_type": candidate.get("claim_type", "unknown"),
            },
            "recommendation": (
                "Verify this claim against source literature. "
                "Low keyword overlap may indicate hallucination."
            ),
        }
