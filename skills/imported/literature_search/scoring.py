# ruff: noqa: RUF002 N806
"""  # noqa: RUF002
Scoring engine for literature-search skill.

Provides domain models and scoring functions for systematic literature review:
- PaperMetrics: immutable dataclass with all scoring dimensions
- ScoringWeights: configurable weights for A-E criteria
- calculate_d_score: methodological quality composite (D criterion)
- calculate_final_score: weighted A × wA + B × wB + C × wC + D × wD + E × wE
- classify_tier: maps final score to Tier 1/2/3/Discard
- get_default_weights: phase-specific weight presets
- deduplicate: removes duplicate papers by DOI/PMID/title similarity
- verify_citation: validates citation existence via external APIs
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# =============================================================================
# DOMAIN MODELS
# =============================================================================


@dataclass(frozen=True, slots=True)
class PaperMetrics:
    """
    Immutable metrics for a single paper across all scoring dimensions.

    A-C and E are direct relevance scores (0-10).
    D is a composite of evidence, sample, journal, citations, and COI.
    """

    # Relevance scores (0-10)
    population_score: float  # A: population relevance
    intervention_score: float  # B: intervention relevance
    outcome_score: float  # C: outcome relevance
    context_score: float  # E: context applicability

    # D sub-scores
    evidence_score: float  # 0-5: evidence level
    sample_score: float  # 0-2: sample size
    journal_score: float  # 0-2: journal quality
    citations_score: float  # 0-1: citation impact
    coi_penalty: float  # 0 or -0.5: conflict of interest


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """
    Weights for the five scoring criteria. Must sum to 1.0 (±0.01 tolerance).
    """

    A_weight: float  # population
    B_weight: float  # intervention
    C_weight: float  # outcome
    D_weight: float  # methodological quality
    E_weight: float  # context applicability

    def __post_init__(self) -> None:
        total = (
            self.A_weight
            + self.B_weight
            + self.C_weight
            + self.D_weight
            + self.E_weight
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0 (±0.01), got {total:.4f}")


# =============================================================================
# D-SCORE CALCULATION
# =============================================================================


def calculate_d_score(metrics: PaperMetrics) -> float:
    """
    Calculate methodological quality score (D criterion).

    D = evidence + sample + journal + citations + coi_penalty
    Clamped to [0, 10].
    """
    raw = (
        metrics.evidence_score  # max 5
        + metrics.sample_score  # max 2
        + metrics.journal_score  # max 2
        + metrics.citations_score  # max 1
        + metrics.coi_penalty  # 0 or -0.5
    )
    return max(0.0, min(10.0, round(raw, 2)))


# =============================================================================
# FINAL SCORE CALCULATION
# =============================================================================


def calculate_final_score(metrics: PaperMetrics, weights: ScoringWeights) -> float:
    """
    Calculate weighted final score: A×wA + B×wB + C×wC + D×wD + E×wE.

    Result is clamped to [0, 10].
    """
    d = calculate_d_score(metrics)
    raw = (
        metrics.population_score * weights.A_weight
        + metrics.intervention_score * weights.B_weight
        + metrics.outcome_score * weights.C_weight
        + d * weights.D_weight
        + metrics.context_score * weights.E_weight
    )
    return max(0.0, min(10.0, round(raw, 2)))


# =============================================================================
# TIER CLASSIFICATION
# =============================================================================


def classify_tier(score: float) -> str:
    """Map a final score to a tier label."""
    if score >= 8.0:
        return "Tier 1"
    if score >= 6.5:
        return "Tier 2"
    if score >= 5.0:
        return "Tier 3"
    return "Discard"


# =============================================================================
# PHASE DEFAULT WEIGHTS
# =============================================================================

_PHASE_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {
        "A": 0.25,
        "B": 0.25,
        "C": 0.20,
        "D": 0.20,
        "E": 0.10,
    },
    "problem_definition": {
        "A": 0.30,
        "B": 0.05,
        "C": 0.15,
        "D": 0.35,
        "E": 0.15,
    },
    "intervention_design": {
        "A": 0.15,
        "B": 0.35,
        "C": 0.25,
        "D": 0.15,
        "E": 0.10,
    },
    "outcome_selection": {
        "A": 0.20,
        "B": 0.10,
        "C": 0.40,
        "D": 0.20,
        "E": 0.10,
    },
}


def get_default_weights(phase: str) -> ScoringWeights:
    """Return the preset weights for a known study phase."""
    if phase not in _PHASE_WEIGHTS:
        raise ValueError(f"Unknown phase: '{phase}'. Valid: {list(_PHASE_WEIGHTS)}")
    w = _PHASE_WEIGHTS[phase]
    return ScoringWeights(
        A_weight=w["A"],
        B_weight=w["B"],
        C_weight=w["C"],
        D_weight=w["D"],
        E_weight=w["E"],
    )


# =============================================================================
# DEDUPLICATION
# =============================================================================

# NOTE: _titles_can_match_len logic is inlined directly in deduplicate()
# to avoid function call overhead in the hot comparison loop.
# The check: max_possible_ratio = 2*min(L1,L2)/(L1+L2). For threshold t,
# max_possible_ratio >= t when 2*min >= t*(L1+L2). Otherwise skip.


# Common English stop words filtered from word-set to make shared-word
# pre-filter more selective (only significant terms count).
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

# Punctuation chars to strip from words in title word sets
_PUNCT = ".,;:!?\"'()[]{}"


def _make_word_set(title_lower: str) -> frozenset[str]:
    """Build frozenset of significant words (excluding stop words and punctuation)."""
    return frozenset(
        stripped
        for w in title_lower.split()
        if (stripped := w.strip(_PUNCT)) and stripped not in _STOP_WORDS
    )


def deduplicate(
    papers: list[dict[str, Any]],
    threshold: float = 0.95,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Remove duplicate papers by DOI, PMID, or title similarity.

    Priority: DOI > PMID > title similarity (SequenceMatcher ratio > threshold).
    Uses length-based pre-filter to skip SequenceMatcher when titles have
    incompatible lengths (max possible similarity < threshold).

    Returns (unique_papers, duplicates_log).
    Each log entry has: {kept_index, removed_index, reason, detail}
    """
    if not papers:
        return [], []

    seen_dois: dict[str, int] = {}  # doi -> first index
    seen_pmids: dict[str, int] = {}  # pmid -> first index
    # Pre-allocated list of length buckets (list index is O(1) without
    # dict hash overhead). Bucket_size=5 chars. Max title len ~150 chars
    # gives bucket key 30. Pre-allocated list avoids dict resize + get().
    _BUCKET_SZ = 5
    _MAX_BUCKET = 30
    # Pre-compute integer threshold multiplier for length pre-filter.
    # Float operations (2.0 * short < threshold * (short+long)) are
    # slower than integer math: short*200 < (short+long)*t100.
    _t100 = int(threshold * 100 + 0.5)  # rounds to nearest %: 0.95→95
    # Bind builtins to locals for LOAD_FAST
    _len = len
    _int = int
    _min = min
    _range = range
    buckets: list[list[tuple[int, str, int, frozenset[str]]]] = [
        [] for _ in _range(_MAX_BUCKET + 1)
    ]
    log: list[dict[str, Any]] = []
    # Papers stored separately from bucket entries to avoid unpacking the
    # paper dict in every title comparison loop iteration (~15000x).
    unique_papers: list[dict[str, Any]] = []
    # Reusable SequenceMatcher instance to avoid __init__ + __chain_b overhead
    sm = SequenceMatcher()
    # Pre-created dict templates for log entries — .copy() is faster
    # than dict literals because it copies key-value pointers without
    # re-hashing keys.
    _doi_log = {
        "kept_index": 0,
        "removed_index": 0,
        "reason": "duplicate_doi",
        "detail": "",
    }
    _pmid_log = {
        "kept_index": 0,
        "removed_index": 0,
        "reason": "duplicate_pmid",
        "detail": "",
    }
    _title_log = {
        "kept_index": 0,
        "removed_index": 0,
        "reason": "similar_title",
        "detail": "",
    }
    # Bind _make_word_set to local for LOAD_FAST
    _make_ws = _make_word_set

    for idx, paper in enumerate(papers):
        # Extract identifiers first — fast dict lookups
        doi = paper.get("doi")  # Returns None if key missing (no or None needed)
        pmid = paper.get("pmid")  # Same: None for missing, empty string for falsy

        # 1. Check DOI (fast O(1) hash lookup) — skip title extraction
        if doi and doi in seen_dois:
            kept_idx = seen_dois[doi]
            log.append(
                {
                    **_doi_log,
                    "kept_index": kept_idx,
                    "removed_index": idx,
                    "detail": doi,
                }
            )
            continue

        # 2. Check PMID (fast O(1) hash lookup) — skip title extraction
        if pmid and pmid in seen_pmids:
            kept_idx = seen_pmids[pmid]
            log.append(
                {
                    **_pmid_log,
                    "kept_index": kept_idx,
                    "removed_index": idx,
                    "detail": pmid,
                }
            )
            continue

        # Not a duplicate — extract title data (only for unique papers)
        title = paper.get("title", "")
        title_lower = title.lower()
        title_len = _len(title_lower)

        # 3. Check title similarity (only if no DOI/PMID match).
        # Uses for...else to eliminate is_dup flag.
        if not doi and not pmid:
            word_set = _make_ws(title_lower)
            # Determine which length buckets to check. For threshold 0.95,
            # max L/S ≈ 1.105. So we only need buckets in [L/1.105, L*1.105].
            # int() naturally floors to 0 for small values (no max(0) needed).
            bucket_min = _int(title_len / _BUCKET_SZ // 1.105)
            bucket_max = _min(_int((title_len * 1.105) / _BUCKET_SZ) + 1, _MAX_BUCKET)
            for bk in _range(bucket_min, bucket_max):
                bucket_entries = buckets[bk]
                if not bucket_entries:
                    continue
                for prev_idx, ptl, ptl_len, pws in bucket_entries:
                    # Fast length-based pre-filter: max possible
                    # SequenceMatcher ratio = 2*min(L1,L2)/(L1+L2).
                    # If this is below threshold, SequenceMatcher can
                    # never reach threshold. Integer arithmetic.
                    short, long = (
                        (title_len, ptl_len)
                        if title_len <= ptl_len
                        else (ptl_len, title_len)
                    )
                    if short == 0 or (short * 200) < (short + long) * _t100:
                        continue
                    # Fast word-set pre-filter (stop-word filtered).
                    # Require ≥3 shared significant words.
                    if _len(word_set & pws) < 3:
                        continue
                    # Exact match short-circuit
                    if title_lower == ptl:
                        log.append(
                            {
                                **_title_log,
                                "kept_index": prev_idx,
                                "removed_index": idx,
                                "detail": "similarity=1.000",
                            }
                        )
                        break
                    # Reuse one SequenceMatcher; quick_ratio() first
                    sm.set_seqs(title_lower, ptl)
                    if sm.quick_ratio() < threshold:
                        continue
                    similarity = sm.ratio()
                    if similarity >= threshold:
                        log.append(
                            {
                                **_title_log,
                                "kept_index": prev_idx,
                                "removed_index": idx,
                                "detail": f"similarity={similarity:.3f}",
                            }
                        )
                        break
                else:
                    continue  # no match in this bucket → try next
                break  # match found → stop checking buckets
            else:
                # No match in any bucket → unique title-only paper
                unique_papers.append(paper)
                entry = (idx, title_lower, title_len, word_set)
                bucket_key = title_len // _BUCKET_SZ
                if bucket_key <= _MAX_BUCKET:
                    buckets[bucket_key].append(entry)
                continue  # back to main loop (skip DOI/PMID registration)
            continue  # found duplicate → back to main loop

        # DOI/PMID paper — not a duplicate, register (only if within bucket range)
        bucket_key = title_len // _BUCKET_SZ
        if bucket_key <= _MAX_BUCKET:
            if doi:
                seen_dois[doi] = idx
            if pmid:
                seen_pmids[pmid] = idx
            word_set = _make_ws(title_lower)
            unique_papers.append(paper)
            buckets[bucket_key].append((idx, title_lower, title_len, word_set))

    # unique_papers populated during registration; no need to extract from buckets
    return unique_papers, log


# =============================================================================
# CITATION VERIFICATION
# =============================================================================


def _crossref_lookup(doi: str) -> dict[str, str]:
    """Look up a DOI via CrossRef API. Returns status dict."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        req = Request(url, headers={"User-Agent": "literature-search-skill/1.3.0"})
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return {"status": "verified", "method": "crossref_doi"}
            return {"status": "not_found", "method": "crossref_doi"}
    except (HTTPError, URLError, TimeoutError):
        return {"status": "not_found", "method": "crossref_doi"}


def _pubmed_lookup(pmid: str) -> dict[str, str]:
    """Look up a PMID via PubMed e-utils API. Returns status dict."""
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
    try:
        req = Request(url, headers={"User-Agent": "literature-search-skill/1.3.0"})
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                if pmid in data.get("result", {}):
                    return {"status": "verified", "method": "pubmed_pmid"}
            return {"status": "not_found", "method": "pubmed_pmid"}
    except (HTTPError, URLError, TimeoutError):
        return {"status": "not_found", "method": "pubmed_pmid"}


def verify_citation(
    doi: str | None = None,
    pmid: str | None = None,
) -> dict[str, str]:
    """
    Verify a citation exists by checking external databases.

    Priority: DOI (CrossRef) > PMID (PubMed).

    Returns dict with: status, method, notes.
    """
    if doi:
        result = _crossref_lookup(doi)
        result["notes"] = f"DOI: {doi}"
        return result

    if pmid:
        result = _pubmed_lookup(pmid)
        result["notes"] = f"PMID: {pmid}"
        return result

    return {
        "status": "unverified",
        "method": "none",
        "notes": "No DOI or PMID provided — cannot verify citation",
    }
