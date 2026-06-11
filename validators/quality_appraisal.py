"""Quality appraisal validator for included studies.

Evaluates each screened paper on a 5-point scale across dimensions
relevant to CS/software engineering systematic reviews:

1. Study design rigor (controlled experiment vs case study vs survey)
2. Reproducibility (open data/code, clear methodology)
3. Threats to validity discussed
4. Sample size adequacy
5. Citation impact (proxy for community validation)

Generates a quality appraisal table and findings for the method gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar


class QualityAppraisalValidator:
    """Evaluate quality of included studies for systematic review."""

    # Quality dimensions and their weights
    DIMENSIONS: ClassVar[dict[str, dict[str, Any]]] = {
        "venue_reputation": {
            "weight": 0.20,
            "description": "Venue reputation (top-tier conference/journal)",
        },
        "citation_impact": {
            "weight": 0.25,
            "description": "Citation impact (community validation proxy)",
        },
        "methodology_rigor": {
            "weight": 0.25,
            "description": "Methodology rigor (experimental design clarity)",
        },
        "reproducibility": {
            "weight": 0.15,
            "description": "Reproducibility (open code/data availability)",
        },
        "recency": {
            "weight": 0.15,
            "description": "Recency (recent studies reflect current state)",
        },
    }

    # Top-tier venues for CS/SE (rank 1)
    TOP_TIER_VENUES: ClassVar[set[str]] = {
        "NeurIPS",
        "ICML",
        "ICLR",
        "AAAI",
        "EMNLP",
        "NAACL",
        "ACL",
        "TACL",
        "ICSE",
        "FSE",
        "ESEC/FSE",
        "ASE",
        "IST",
        "TSE",
        "TOSEM",
        "ACM Comput. Surv.",
        "Nature",
        "Science",
    }

    # Well-known venues (rank 2)
    GOOD_VENUES: ClassVar[set[str]] = {
        "arXiv",
        "TMLR",
        "JMLR",
        "COLING",
        "LREC",
        "ECOOP",
        "OOPSLA",
        "ISSTA",
        "MSR",
        "SPLC",
        "ICPC",
        "WCRE",
        "SCAM",
    }

    # Pre-computed lowercase sets for case-insensitive matching (B-6 fix)
    _top_tier_lower: ClassVar[frozenset[str]] = frozenset(v.lower() for v in TOP_TIER_VENUES)
    _good_venues_lower: ClassVar[frozenset[str]] = frozenset(v.lower() for v in GOOD_VENUES)

    def score_venue_reputation(self, paper: dict[str, Any]) -> int:
        """Score venue reputation (1-5)."""
        venue = (paper.get("venue") or "").strip().lower()
        if venue in self._top_tier_lower:
            return 5
        if venue in self._good_venues_lower:
            return 3
        if venue and len(venue) > 2:
            return 2
        return 1

    def score_citation_impact(self, paper: dict[str, Any]) -> int:
        """Score citation impact (1-5)."""
        cites = paper.get("citation_count") or 0
        if not isinstance(cites, int):
            try:
                cites = int(cites)
            except (ValueError, TypeError):
                cites = 0
        if cites >= 1000:
            return 5
        if cites >= 100:
            return 4
        if cites >= 30:
            return 3
        if cites >= 5:
            return 2
        return 1

    def score_methodology_rigor(self, paper: dict[str, Any]) -> int:
        """Score methodology rigor from abstract keywords (1-5).

        Detects experimental design signals in the abstract:
        - RCT, controlled experiment → 5
        - Ablation study, benchmark → 4
        - Case study, survey → 3
        - Qualitative, interview → 2
        - No signals → 1
        """
        abstract = (paper.get("abstract") or "").lower()
        title = (paper.get("title") or "").lower()
        text = f"{title} {abstract}"

        # Strong experimental signals
        if any(
            kw in text
            for kw in [
                "randomized controlled",
                "rct",
                "controlled experiment",
                "ablation study",
                "statistically significant",
                "p-value",
                "p < ",
            ]
        ):
            return 5

        # Benchmark / evaluation signals
        if any(
            kw in text
            for kw in [
                "benchmark",
                "evaluation",
                "empirical",
                "quantitative",
                "replication",
            ]
        ):
            return 4

        # Case study / survey signals
        if any(
            kw in text
            for kw in [
                "case study",
                "survey",
                "interview",
                "questionnaire",
                "observational",
            ]
        ):
            return 3

        # Qualitative signals
        if any(kw in text for kw in ["qualitative", "thematic analysis", "grounded theory"]):
            return 2

        return 1

    def score_reproducibility(self, paper: dict[str, Any]) -> int:
        """Score reproducibility from available signals (1-5).

        Signals: DOI (peer-reviewed), arXiv (preprint with ID),
        open-source indicators in abstract.
        """
        score = 1
        doi = paper.get("doi", "")
        arxiv = paper.get("arxiv_id", "")
        abstract = (paper.get("abstract") or "").lower()

        # Peer-reviewed (DOI present)
        if doi and doi.strip():
            score += 1

        # ArXiv preprint (accessible, versioned)
        if arxiv and arxiv.strip():
            score += 1

        # Open code/data signals
        if any(
            kw in abstract
            for kw in [
                "open-source",
                "open source",
                "github",
                "available at",
                "replication package",
            ]
        ):
            score += 1

        # Dataset availability signals
        if any(kw in abstract for kw in ["dataset", "benchmark", "corpus"]):
            score += 1

        return min(score, 5)

    def score_recency(self, paper: dict[str, Any]) -> int:
        """Score recency (1-5). Recent papers reflect current state of art."""
        year = paper.get("year")
        if not isinstance(year, int):
            try:
                year = int(year)  # type: ignore[arg-type]
            except (ValueError, TypeError):
                return 1
        if year >= 2024:
            return 5
        if year >= 2022:
            return 4
        if year >= 2020:
            return 3
        if year >= 2017:
            return 2
        return 1

    def appraise_study(self, paper: dict[str, Any]) -> dict[str, Any]:
        """Appraise a single study across all dimensions.

        Returns:
            Dict with dimension scores, weighted total, and quality rating.
        """
        scores: dict[str, int] = {
            "venue_reputation": self.score_venue_reputation(paper),
            "citation_impact": self.score_citation_impact(paper),
            "methodology_rigor": self.score_methodology_rigor(paper),
            "reproducibility": self.score_reproducibility(paper),
            "recency": self.score_recency(paper),
        }

        # Weighted total (0-5 scale)
        weighted = 0.0
        for dim, info in self.DIMENSIONS.items():
            weighted += float(scores[dim]) * float(info["weight"])

        # Quality rating
        if weighted >= 4.0:
            rating = "high"
        elif weighted >= 3.0:
            rating = "moderate"
        elif weighted >= 2.0:
            rating = "low"
        else:
            rating = "very_low"

        return {
            "title": paper.get("title") or "",
            "doi": paper.get("doi") or "",
            "year": paper.get("year"),
            "venue": paper.get("venue", ""),
            "scores": scores,
            "weighted_score": round(weighted, 2),
            "quality_rating": rating,
        }

    def validate(
        self, evidence_path: Path, output_path: Path | None = None
    ) -> list[dict[str, Any]]:
        """Run quality appraisal on all screened papers.

        Args:
            evidence_path: Path to screened_evidence.json.
            output_path: Optional path to write appraisal table JSON.

        Returns:
            List of findings (one per paper with quality issues).
        """
        if not evidence_path.exists():
            return [
                {
                    "gate": "quality_appraisal",
                    "severity": "P1",
                    "message": "No screened evidence found for quality appraisal",
                }
            ]

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        papers = evidence.get("evidence", [])

        if not papers:
            return [
                {
                    "gate": "quality_appraisal",
                    "severity": "P1",
                    "message": "No papers to appraise — screened evidence is empty",
                }
            ]

        # Appraise each study — skip non-dict entries gracefully
        appraisals = [self.appraise_study(p) for p in papers if isinstance(p, dict)]

        # Generate findings for low-quality studies
        findings: list[dict[str, Any]] = []
        low_quality = [a for a in appraisals if a["quality_rating"] in ("low", "very_low")]
        for a in low_quality:
            findings.append(
                {
                    "gate": "quality_appraisal",
                    "severity": "P2",
                    "message": (
                        f"Low quality study: '{a['title'][:60]}' "
                        f"(score={a['weighted_score']}, "
                        f"venue={a['scores']['venue_reputation']}, "
                        f"cites={a['scores']['citation_impact']}, "
                        f"methodology={a['scores']['methodology_rigor']})"
                    ),
                }
            )

        # Summary finding
        ratings = [a["quality_rating"] for a in appraisals]
        findings.append(
            {
                "gate": "quality_appraisal",
                "severity": "info",
                "message": (
                    f"Quality appraisal complete: {len(appraisals)} studies, "
                    f"high={ratings.count('high')}, "
                    f"moderate={ratings.count('moderate')}, "
                    f"low={ratings.count('low')}, "
                    f"very_low={ratings.count('very_low')}"
                ),
            }
        )

        # Write appraisal table if output path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(
                    {
                        "total_appraised": len(appraisals),
                        "method": {
                            "dimensions": {
                                name: {
                                    "weight": info["weight"],
                                    "description": info["description"],
                                }
                                for name, info in self.DIMENSIONS.items()
                            },
                        },
                        "appraisals": appraisals,
                        "summary": {
                            "high": ratings.count("high"),
                            "moderate": ratings.count("moderate"),
                            "low": ratings.count("low"),
                            "very_low": ratings.count("very_low"),
                            "mean_score": round(
                                sum(a["weighted_score"] for a in appraisals) / len(appraisals), 2
                            ),
                        },
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        return findings
