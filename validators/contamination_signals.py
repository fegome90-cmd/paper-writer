"""Contamination signal detection for citation verification.

Detects potential quality issues in cited sources:
- Preprint venue usage (papers not peer-reviewed)
- Recent preprint citations (higher risk of unreproducible results)
- Source quality cross-reference (venue tier vs citation claim strength)

Ported from ARS contamination_signals.py (445 loc).
This is a simplified version focusing on the pure-logic components
that require zero API dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from validators.citation_verify import PREPRINT_VENUES


@dataclass(frozen=True)
class ContaminationSignal:
    """Result of contamination signal analysis for a single citation."""

    is_preprint: bool
    preprint_venue: str | None
    is_recent_preprint: bool
    year: int | None
    contamination_score: float  # 0.0 (clean) to 1.0 (high risk)
    flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_preprint": self.is_preprint,
            "preprint_venue": self.preprint_venue,
            "is_recent_preprint": self.is_recent_preprint,
            "year": self.year,
            "contamination_score": self.contamination_score,
            "flags": list(self.flags),
        }


def compute_contamination_signal(
    venue: str | None,
    year: int | None,
    *,
    recent_threshold: int = 2024,
) -> ContaminationSignal:
    """Compute contamination risk signals for a citation.

    Pure logic — no API dependencies. Uses venue name and year to detect:
    - Preprint venue (not peer-reviewed)
    - Recent preprint (higher contamination risk)
    - Combined contamination score

    Args:
        venue: Journal/conference/venue name from API results
        year: Publication year from API results
        recent_threshold: Year cutoff for "recent" preprint flag

    Returns:
        ContaminationSignal with risk assessment
    """
    flags: list[str] = []
    is_preprint = False
    preprint_venue: str | None = None
    is_recent_preprint = False
    score = 0.0

    if venue:
        venue_lower = venue.lower()
        for known in PREPRINT_VENUES:
            if known in venue_lower:
                is_preprint = True
                preprint_venue = venue_lower
                flags.append("preprint_venue")
                score += 0.4
                break

    if is_preprint and year is not None and year >= recent_threshold:
        is_recent_preprint = True
        flags.append("recent_preprint")
        score += 0.3

    # Clamp to [0.0, 1.0]
    score = min(1.0, max(0.0, score))

    return ContaminationSignal(
        is_preprint=is_preprint,
        preprint_venue=preprint_venue,
        is_recent_preprint=is_recent_preprint,
        year=year,
        contamination_score=score,
        flags=tuple(flags),
    )
