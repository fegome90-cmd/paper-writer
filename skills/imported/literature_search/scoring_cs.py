"""CS scoring engine for Computer Science papers.

Parallel to the clinical PICO scoring in scoring.py. Scores CS papers
on venue tier, recency, citations, relevance, and evaluation rigor.

Leaf dependency — imports nothing from search.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# =============================================================================
# STOP WORDS (shared with scoring.py dedup)
# =============================================================================

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "and",
        "or",
        "is",
        "was",
        "are",
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
        "but",
        "not",
        "so",
        "if",
        "as",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "from",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "under",
        "above",
        "below",
        "up",
        "down",
        "out",
        "off",
        "than",
        "then",
        "also",
        "very",
        "just",
        "each",
        "all",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "only",
        "own",
        "same",
        "too",
        "can",
        "will",
        "may",
        "might",
        "should",
        "having",
        "doing",
        "getting",
        "using",
    }
)

# =============================================================================
# VENUE SCORING
# =============================================================================

# ESEC/FSE must be checked BEFORE standalone FSE (joint edition = 4.0 vs 5.0)
_VENUE_SCORES: list[tuple[re.Pattern[str], float]] = [
    # Joint editions (check first)
    (re.compile(r"\bESEC\s*/\s*FSE\b", re.I), 4.0),
    (re.compile(r"\bESEC\b", re.I), 4.0),
    # Top SE venues
    (re.compile(r"\bICSE\b", re.I), 5.0),
    (re.compile(r"\bFSE\b", re.I), 5.0),
    (re.compile(r"\bASE\b", re.I), 5.0),
    (re.compile(r"\bTOSEM\b", re.I), 5.0),
    (re.compile(r"\bTSE\b", re.I), 5.0),
    (re.compile(r"\bIEEE\s*Software\b", re.I), 5.0),
    # Top ML/NLP venues
    (re.compile(r"\bEMNLP\b", re.I), 4.5),
    (re.compile(r"\bACL\b", re.I), 4.5),
    (re.compile(r"\bNAACL\b", re.I), 4.5),
    (re.compile(r"\bNeurIPS?\b", re.I), 4.5),
    (re.compile(r"\bICML\b", re.I), 4.5),
    (re.compile(r"\bICLR\b", re.I), 4.5),
    # Mid-tier SE venues
    (re.compile(r"\bMSR\b", re.I), 4.0),
    (re.compile(r"\bSANER\b", re.I), 4.0),
    (re.compile(r"\bICSME\b", re.I), 4.0),
    (re.compile(r"\bWCRE\b", re.I), 4.0),
    (re.compile(r"\bISSTA\b", re.I), 4.0),
    # arXiv
    (re.compile(r"\barXiv\b.*\barXiv:", re.I), 3.0),  # arXiv with identifier
    (re.compile(r"\barXiv\b", re.I), 2.0),
    # Low-tier
    (re.compile(r"\bworkshop\b", re.I), 1.0),
    (re.compile(r"\bthesis\b", re.I), 1.0),
    (re.compile(r"\btechnical\s+report\b", re.I), 1.0),
]


def score_venue(venue: str, publication_type: str) -> float:
    """Score venue tier based on known venue patterns.

    Uses whole-word regex to prevent false positives
    (e.g., "ase" in "database" won't match).
    """
    text = f"{venue} {publication_type}".strip()
    if not text.strip():
        return 2.0  # default for empty

    for pattern, score in _VENUE_SCORES:
        if pattern.search(text):
            return score

    return 2.0  # default for unknown


# =============================================================================
# RECENCY SCORING
# =============================================================================


def score_recency(year: int | None, current_year: int | None = None) -> float:
    """Score recency with linear decay 0.10/year, floor 0.20."""
    if year is None:
        return 0.50  # conservative default

    if current_year is None:
        import datetime

        current_year = datetime.date.today().year

    age = current_year - year
    if age <= 0:
        return 1.0

    score = max(0.0, 1.0 - age * 0.10)
    return max(0.20, score)  # floor


# =============================================================================
# CITATION SCORING
# =============================================================================


def score_citations(
    citation_count: int | None,
    year: int | None,
    current_year: int | None = None,
) -> float:
    """Score citations normalized by age."""
    if citation_count is None or year is None:
        return 0.50  # conservative default

    # Coerce non-int types gracefully
    try:
        citation_count = int(citation_count)
        year = int(year)
    except (ValueError, TypeError):
        return 0.50

    if current_year is None:
        import datetime

        current_year = datetime.date.today().year

    if citation_count == 0:
        return 0.0

    years_active = max(1, current_year - year + 1)
    citations_per_year = citation_count / years_active

    if citations_per_year > 10:
        return 2.0
    if citations_per_year > 5:
        return 1.5
    if citations_per_year > 1:
        return 1.0
    return 0.5


# =============================================================================
# RELEVANCE SCORING
# =============================================================================


def score_relevance(query: str, title: str, abstract: str) -> float:
    """Score relevance via keyword overlap between query and title+abstract."""
    if not query or not query.strip():
        return 1.0  # neutral — no query signal

    query_terms = {w for w in query.lower().split() if w not in _STOP_WORDS}
    if not query_terms:
        return 1.0

    doc_text = f"{title} {abstract}".lower()
    doc_terms = {w for w in doc_text.split() if w not in _STOP_WORDS}

    overlap = len(query_terms & doc_terms) / len(query_terms)
    return min(2.0, overlap * 2.0)


# =============================================================================
# RIGOR SCORING
# =============================================================================

_RIGOR_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\buser\s+study\b|\bhuman\s+evaluation\b|\bparticipants\b", re.I), 1.0),
    (re.compile(r"\bbenchmark\b|\bHumanEval\b|\bSWE.bench\b|\bMBPP\b", re.I), 0.8),
    (re.compile(r"\bcase\s+study\b|\bempirical\s+study\b|\breplication\b", re.I), 0.5),
    (re.compile(r"\btheoretical\b|\bformal\b|\bproof\b", re.I), 0.3),
]


def score_rigor(paper: dict[str, Any]) -> float:
    """Score evaluation rigor via priority-ordered keyword match."""
    if not isinstance(paper, dict):
        return 0.40  # default
    text = f"{paper.get('title', '') or ''} {paper.get('abstract', '') or ''}"

    for pattern, score in _RIGOR_PATTERNS:
        if pattern.search(text):
            return score

    return 0.40  # default


# =============================================================================
# DOMAIN DETECTION
# =============================================================================

_CS_VENUE_PATTERNS = [
    re.compile(r"\bICSE\b", re.I),
    re.compile(r"\bFSE\b", re.I),
    re.compile(r"\bASE\b", re.I),
    re.compile(r"\bTOSEM\b", re.I),
    re.compile(r"\bTSE\b", re.I),
    re.compile(r"\bEMNLP\b", re.I),
    re.compile(r"\bACL\b", re.I),
    re.compile(r"\bNAACL\b", re.I),
    re.compile(r"\bNeurIPS?\b", re.I),
    re.compile(r"\bICML\b", re.I),
    re.compile(r"\bICLR\b", re.I),
    re.compile(r"\barXiv\b", re.I),
    re.compile(r"\bMSR\b", re.I),
    re.compile(r"\bSANER\b", re.I),
    re.compile(r"\bICSME\b", re.I),
]

_CLINICAL_PHRASES = [
    "patient",
    "randomized controlled trial",
    "placebo",
    "cohort study",
    "clinical trial",
    "double-blind",
    "intervention group",
    "control group",
    "mortality",
]


def detect_domain(paper: dict[str, Any]) -> str:
    """Detect paper domain: 'cs' or 'clinical'.

    Priority: explicit override > CS venue > clinical keywords > default 'cs'.
    """
    if not isinstance(paper, dict):
        return "cs"  # default
    # 1. Explicit override
    explicit = paper.get("domain")
    if explicit:
        return str(explicit)

    # 2. CS venue match (whole-word regex)
    venue = f"{paper.get('venue', '') or ''} {paper.get('booktitle', '') or ''}"
    for pattern in _CS_VENUE_PATTERNS:
        if pattern.search(venue):
            return "cs"

    # 3. Clinical keyword threshold (≥2 distinct phrases)
    abstract = (paper.get("abstract", "") or "").lower()
    clinical_count = sum(1 for phrase in _CLINICAL_PHRASES if phrase in abstract)
    if clinical_count >= 2:
        return "clinical"

    # 4. Default
    return "cs"


# =============================================================================
# DOMAIN MODELS
# =============================================================================


@dataclass(frozen=True, slots=True)
class CSMetrics:
    """Immutable metrics for a CS paper across 5 scoring dimensions."""

    venue_tier: float  # 0-5
    recency_score: float  # 0-1
    citation_score: float  # 0-2
    relevance_score: float  # 0-2
    rigor_score: float  # 0-1

    def __post_init__(self) -> None:
        # Clamp all fields using object.__setattr__ (frozen workaround)
        object.__setattr__(self, "venue_tier", max(0.0, min(5.0, self.venue_tier)))
        object.__setattr__(self, "recency_score", max(0.0, min(1.0, self.recency_score)))
        object.__setattr__(self, "citation_score", max(0.0, min(2.0, self.citation_score)))
        object.__setattr__(self, "relevance_score", max(0.0, min(2.0, self.relevance_score)))
        object.__setattr__(self, "rigor_score", max(0.0, min(1.0, self.rigor_score)))


@dataclass(frozen=True, slots=True)
class CSWeights:
    """Weights for CS scoring criteria. Must sum to 1.0 ± 0.01."""

    V_weight: float  # venue
    R_weight: float  # recency
    C_weight: float  # citations
    Re_weight: float  # relevance
    E_weight: float  # rigor

    def __post_init__(self) -> None:
        total = self.V_weight + self.R_weight + self.C_weight + self.Re_weight + self.E_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0 (±0.01), got {total:.4f}")


# =============================================================================
# PHASE DEFAULT WEIGHTS
# =============================================================================

_CS_PHASE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {"V": 0.15, "R": 0.20, "C": 0.10, "Re": 0.40, "E": 0.15},
    "rigorous": {"V": 0.10, "R": 0.10, "C": 0.10, "Re": 0.25, "E": 0.45},
    "exploratory": {"V": 0.10, "R": 0.20, "C": 0.05, "Re": 0.55, "E": 0.10},
}


def get_default_cs_weights(phase: str) -> CSWeights:
    """Return preset CS weights for a known phase."""
    if phase not in _CS_PHASE_WEIGHTS:
        raise ValueError(f"Unknown CS phase: '{phase}'. Valid: {list(_CS_PHASE_WEIGHTS)}")
    w = _CS_PHASE_WEIGHTS[phase]
    return CSWeights(
        V_weight=w["V"],
        R_weight=w["R"],
        C_weight=w["C"],
        Re_weight=w["Re"],
        E_weight=w["E"],
    )


# =============================================================================
# FINAL SCORE CALCULATION
# =============================================================================


def calculate_cs_final_score(metrics: CSMetrics, weights: CSWeights) -> float:
    """Calculate weighted CS final score on [0, 10] scale.

    Canonical formula — the ONLY formula:
    1. Normalize each dimension to [0, 1]
    2. Weighted sum (result in [0, 1] since weights sum to 1.0)
    3. Multiply by 10 for classify_tier() scale
    """
    weighted = (
        (metrics.venue_tier / 5.0) * weights.V_weight
        + metrics.recency_score * weights.R_weight
        + (metrics.citation_score / 2.0) * weights.C_weight
        + (metrics.relevance_score / 2.0) * weights.Re_weight
        + metrics.rigor_score * weights.E_weight
    )
    final = round(weighted * 10.0, 2)
    return max(0.0, min(10.0, final))


# =============================================================================
# METRICS EXTRACTION
# =============================================================================


def extract_cs_metrics(paper: dict[str, Any], query: str) -> CSMetrics:
    """Compose all scoring functions into CSMetrics from a paper dict."""
    import datetime

    current_year = datetime.date.today().year

    if not isinstance(paper, dict):
        paper = {}

    venue = paper.get("venue", "") or ""
    pub_type = paper.get("publication_type", "") or ""
    year_raw = paper.get("year")
    try:
        year = int(year_raw) if year_raw is not None else None
    except (ValueError, TypeError):
        year = None
    citation_count_raw = paper.get("citation_count")
    try:
        citation_count = int(citation_count_raw) if citation_count_raw is not None else None
    except (ValueError, TypeError):
        citation_count = None
    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""

    return CSMetrics(
        venue_tier=score_venue(venue, pub_type),
        recency_score=score_recency(year, current_year),
        citation_score=score_citations(citation_count, year, current_year),
        relevance_score=score_relevance(query, title, abstract),
        rigor_score=score_rigor(paper),
    )
