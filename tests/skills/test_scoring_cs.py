"""Tests for CS scoring engine — scoring_cs module.

Strict TDD: these tests are written BEFORE implementation.
Phase: RED for Tasks 1-5 (dataclasses, scoring functions, domain detection,
final score, integration).
"""

from __future__ import annotations

import pytest

# =============================================================================
# Task 1: CSMetrics + CSWeights dataclasses
# =============================================================================


class TestCSMetrics:
    """CSMetrics frozen dataclass with 5 scoring dimensions."""

    def test_construction(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=3.0,
            recency_score=0.8,
            citation_score=1.5,
            relevance_score=1.0,
            rigor_score=0.6,
        )
        assert m.venue_tier == 3.0
        assert m.recency_score == 0.8
        assert m.citation_score == 1.5
        assert m.relevance_score == 1.0
        assert m.rigor_score == 0.6

    def test_frozen(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(1.0, 0.5, 0.5, 1.0, 0.4)
        with pytest.raises(AttributeError):
            m.venue_tier = 5.0  # type: ignore[misc]

    def test_has_slots(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        assert hasattr(CSMetrics, "__slots__")

    def test_venue_tier_clamped_low(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=-1.0,
            recency_score=0.5,
            citation_score=0.5,
            relevance_score=1.0,
            rigor_score=0.4,
        )
        assert m.venue_tier == 0.0

    def test_venue_tier_clamped_high(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=10.0,
            recency_score=0.5,
            citation_score=0.5,
            relevance_score=1.0,
            rigor_score=0.4,
        )
        assert m.venue_tier == 5.0

    def test_recency_clamped(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=2.0,
            recency_score=2.0,
            citation_score=0.5,
            relevance_score=1.0,
            rigor_score=0.4,
        )
        assert m.recency_score == 1.0

    def test_citation_score_clamped(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=2.0,
            recency_score=0.5,
            citation_score=5.0,
            relevance_score=1.0,
            rigor_score=0.4,
        )
        assert m.citation_score == 2.0

    def test_relevance_score_clamped(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=2.0,
            recency_score=0.5,
            citation_score=0.5,
            relevance_score=3.0,
            rigor_score=0.4,
        )
        assert m.relevance_score == 2.0

    def test_rigor_score_clamped(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSMetrics

        m = CSMetrics(
            venue_tier=2.0,
            recency_score=0.5,
            citation_score=0.5,
            relevance_score=1.0,
            rigor_score=2.0,
        )
        assert m.rigor_score == 1.0


class TestCSWeights:
    """CSWeights frozen dataclass with 5 weights summing to 1.0."""

    def test_construction(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSWeights

        w = CSWeights(V_weight=0.25, R_weight=0.10, C_weight=0.20, Re_weight=0.30, E_weight=0.15)
        assert w.V_weight == 0.25
        assert w.Re_weight == 0.30

    def test_weights_must_sum_to_one(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSWeights

        with pytest.raises(ValueError, match="sum"):
            CSWeights(V_weight=0.5, R_weight=0.5, C_weight=0.5, Re_weight=0.5, E_weight=0.5)

    def test_valid_sum_tolerance(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSWeights

        # 0.999 is within ±0.01 tolerance
        w = CSWeights(V_weight=0.25, R_weight=0.10, C_weight=0.20, Re_weight=0.30, E_weight=0.149)
        assert abs(w.V_weight + w.R_weight + w.C_weight + w.Re_weight + w.E_weight - 1.0) <= 0.01

    def test_frozen(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSWeights

        w = CSWeights(V_weight=0.25, R_weight=0.10, C_weight=0.20, Re_weight=0.30, E_weight=0.15)
        with pytest.raises(AttributeError):
            w.V_weight = 0.5  # type: ignore[misc]

    def test_has_slots(self) -> None:
        from skills.imported.literature_search.scoring_cs import CSWeights

        assert hasattr(CSWeights, "__slots__")


class TestGetDefaultCSWeights:
    """Phase presets for CS weights."""

    def test_balanced(self) -> None:
        from skills.imported.literature_search.scoring_cs import get_default_cs_weights

        w = get_default_cs_weights("balanced")
        assert abs(w.V_weight + w.R_weight + w.C_weight + w.Re_weight + w.E_weight - 1.0) < 0.001

    def test_rigorous(self) -> None:
        from skills.imported.literature_search.scoring_cs import get_default_cs_weights

        w = get_default_cs_weights("rigorous")
        assert w.E_weight > w.V_weight  # rigor emphasis

    def test_exploratory(self) -> None:
        from skills.imported.literature_search.scoring_cs import get_default_cs_weights

        w = get_default_cs_weights("exploratory")
        assert w.Re_weight > w.E_weight  # relevance emphasis

    def test_all_presets_sum_to_one(self) -> None:
        from skills.imported.literature_search.scoring_cs import get_default_cs_weights

        for phase in ("balanced", "rigorous", "exploratory"):
            w = get_default_cs_weights(phase)
            total = w.V_weight + w.R_weight + w.C_weight + w.Re_weight + w.E_weight
            assert abs(total - 1.0) < 0.001, f"Phase {phase} sums to {total}"

    def test_unknown_phase_raises(self) -> None:
        from skills.imported.literature_search.scoring_cs import get_default_cs_weights

        with pytest.raises(ValueError, match="Unknown"):
            get_default_cs_weights("nonexistent")


# =============================================================================
# Task 2: Individual scoring functions
# =============================================================================


class TestScoreVenue:
    """score_venue() — whole-word venue matching."""

    def test_top_venue_icse(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("Proceedings of ICSE 2024", "") == 5.0

    def test_top_venue_fse(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("FSE 2024", "") == 5.0

    def test_nlp_venue_emnlp(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("Findings of EMNLP 2024", "") == 4.5

    def test_esec_fse_joint(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        # ESEC/FSE joint edition = 4.0, not 5.0
        assert score_venue("ESEC/FSE 2023", "") == 4.0

    def test_arxiv_with_venue(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("arXiv preprint arXiv:2406.14497", "") == 3.0

    def test_arxiv_without_venue(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("arXiv preprint", "") == 2.0

    def test_unknown_venue(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        # Unknown venue → default 2.0
        assert score_venue("Some Random Conference", "") == 2.0

    def test_empty_venue(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("", "") == 2.0

    def test_no_false_positive_database(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        # "ase" must NOT match "database"
        assert score_venue("International Conference on Database Systems", "") == 2.0

    def test_no_false_positive_oracle_acl(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        # "acl" must NOT match "oracle" — "technical report" IS a valid match (1.0)
        # Use a string without any venue pattern to truly test ACL false positive
        assert score_venue("Oracle Database Journal", "") == 2.0  # unknown, no ACL match

    def test_workshop(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("WORKSHOP on ML", "") == 1.0

    def test_thesis(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_venue

        assert score_venue("PhD Thesis", "") == 1.0


class TestScoreRecency:
    """score_recency() — linear decay 0.10/yr, floor 0.20."""

    def test_current_year(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_recency

        assert score_recency(2026, 2026) == 1.0

    def test_one_year_old(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_recency

        assert score_recency(2025, 2026) == 0.90

    def test_five_years_old(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_recency

        assert score_recency(2021, 2026) == 0.50

    def test_very_old_has_floor(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_recency

        assert score_recency(2000, 2026) >= 0.20

    def test_none_year_returns_default(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_recency

        assert score_recency(None, 2026) == 0.50

    def test_uses_current_year_if_none(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_recency

        # Should not crash — uses real current year
        result = score_recency(2024, None)
        assert 0.0 <= result <= 1.0


class TestScoreCitations:
    """score_citations() — per-year normalization, None handling."""

    def test_highly_cited(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_citations

        # 50 citations in 2 years = 25/year → 2.0
        assert score_citations(50, 2024, 2026) == 2.0

    def test_moderately_cited(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_citations

        # years_active = 2026-2024+1 = 3. 10/3 = 3.33/year → 1.0 (between 1 and 5)
        assert score_citations(10, 2024, 2026) == 1.0

    def test_low_cited(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_citations

        # years_active = 3. 2/3 = 0.67/year → 0.5 (between 0 and 1)
        assert score_citations(2, 2024, 2026) == 0.5

    def test_zero_citations(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_citations

        assert score_citations(0, 2024, 2026) == 0.0

    def test_none_count_returns_default(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_citations

        assert score_citations(None, 2024, 2026) == 0.50

    def test_none_year_returns_default(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_citations

        assert score_citations(10, None, 2026) == 0.50


class TestScoreRelevance:
    """score_relevance() — keyword overlap."""

    def test_perfect_overlap(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_relevance

        score = score_relevance(
            "retrieval augmented code generation",
            "Retrieval-Augmented Code Generation",
            "This paper presents a retrieval augmented approach to code generation.",
        )
        assert score == 2.0

    def test_partial_overlap(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_relevance

        score = score_relevance(
            "retrieval augmented code generation",
            "Code Generation with LLMs",
            "We study code generation using large language models.",
        )
        # Only "code" and "generation" match (2 of 4 terms) = 50% → 1.0
        assert 0.0 < score < 2.0

    def test_no_overlap(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_relevance

        score = score_relevance(
            "retrieval augmented code generation",
            "Protein folding prediction",
            "This paper studies protein structure prediction.",
        )
        assert score == 0.0

    def test_empty_query(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_relevance

        # No query → neutral relevance
        assert score_relevance("", "Some title", "Some abstract") == 1.0


class TestScoreRigor:
    """score_rigor() — priority-ordered keyword heuristic."""

    def test_human_study(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_rigor

        assert (
            score_rigor(
                {
                    "title": "User study of code generation",
                    "abstract": "We conducted a user study with 20 participants.",
                }
            )
            == 1.0
        )

    def test_benchmark(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_rigor

        assert (
            score_rigor(
                {
                    "title": "Evaluating on HumanEval benchmark",
                    "abstract": "We test on the HumanEval benchmark.",
                }
            )
            == 0.8
        )

    def test_case_study(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_rigor

        assert (
            score_rigor(
                {"title": "Case study of RAG in practice", "abstract": "An empirical case study."}
            )
            == 0.5
        )

    def test_theoretical(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_rigor

        assert (
            score_rigor(
                {
                    "title": "A formal proof of correctness",
                    "abstract": "We provide a theoretical analysis and formal proof.",
                }
            )
            == 0.3
        )

    def test_no_match_default(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_rigor

        assert (
            score_rigor({"title": "RAG for code", "abstract": "We propose a new approach."}) == 0.4
        )

    def test_human_takes_priority_over_benchmark(self) -> None:
        from skills.imported.literature_search.scoring_cs import score_rigor

        # Paper has both "user study" and "benchmark" → human wins
        assert (
            score_rigor(
                {
                    "title": "User study and benchmark evaluation",
                    "abstract": "We ran a user study and benchmark tests.",
                }
            )
            == 1.0
        )


# =============================================================================
# Task 3: Domain detection
# =============================================================================


class TestDetectDomain:
    """detect_domain() — whole-word regex, CS venue priority."""

    def test_explicit_override(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        assert detect_domain({"domain": "clinical", "venue": "ICSE"}) == "clinical"

    def test_cs_venue_arxiv(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        assert detect_domain({"venue": "arXiv preprint arXiv:2406.14497"}) == "cs"

    def test_cs_venue_conference(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        assert detect_domain({"venue": "Proceedings of ICSE 2024"}) == "cs"

    def test_clinical_abstract(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        assert (
            detect_domain(
                {
                    "venue": "The Lancet",
                    "abstract": "We conducted a randomized controlled trial with patients in the intervention group and control group.",
                }
            )
            == "clinical"
        )

    def test_default_is_cs(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        assert detect_domain({"venue": "Unknown Journal", "abstract": "Generic paper"}) == "cs"

    def test_no_false_positive_database(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        # "database" must NOT trigger ASE detection
        assert (
            detect_domain({"venue": "International Conference on Database Systems"}) == "cs"
        )  # default, not CS venue match

    def test_no_false_positive_oracle(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        # "oracle" must NOT trigger ACL detection
        assert detect_domain({"venue": "Oracle Technical Report"}) == "cs"  # default

    def test_clinical_nlp_paper_detected_as_cs(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        # "Clinical BERT" in arXiv → CS venue match before clinical keywords
        assert (
            detect_domain(
                {
                    "venue": "arXiv preprint",
                    "abstract": "We present Clinical BERT for patient record analysis.",
                }
            )
            == "cs"
        )

    def test_single_clinical_keyword_not_enough(self) -> None:
        from skills.imported.literature_search.scoring_cs import detect_domain

        # Only 1 clinical keyword → below threshold of 2
        assert (
            detect_domain(
                {
                    "venue": "Unknown",
                    "abstract": "We studied patient outcomes in a pilot study.",
                }
            )
            == "cs"
        )  # default (only 1 clinical keyword: "patient")


# =============================================================================
# Task 4: Final score + extract_cs_metrics
# =============================================================================


class TestCalculateCSFinalScore:
    """calculate_cs_final_score() — canonical formula."""

    def test_perfect_paper(self) -> None:
        from skills.imported.literature_search.scoring_cs import (
            CSMetrics,
            CSWeights,
            calculate_cs_final_score,
        )

        m = CSMetrics(
            venue_tier=5.0,
            recency_score=1.0,
            citation_score=2.0,
            relevance_score=2.0,
            rigor_score=1.0,
        )
        w = CSWeights(V_weight=0.25, R_weight=0.10, C_weight=0.20, Re_weight=0.30, E_weight=0.15)
        assert calculate_cs_final_score(m, w) == 10.0

    def test_zero_paper(self) -> None:
        from skills.imported.literature_search.scoring_cs import (
            CSMetrics,
            CSWeights,
            calculate_cs_final_score,
        )

        m = CSMetrics(
            venue_tier=0.0,
            recency_score=0.0,
            citation_score=0.0,
            relevance_score=0.0,
            rigor_score=0.0,
        )
        w = CSWeights(V_weight=0.25, R_weight=0.10, C_weight=0.20, Re_weight=0.30, E_weight=0.15)
        assert calculate_cs_final_score(m, w) == 0.0

    def test_worked_example_evor(self) -> None:
        """EvoR (Su et al., 2024, EMNLP): venue=4.5, recency=0.90, citations=0.5, relevance=~1.4, rigor=0.8."""
        from skills.imported.literature_search.scoring_cs import (
            CSMetrics,
            calculate_cs_final_score,
            get_default_cs_weights,
        )

        m = CSMetrics(
            venue_tier=4.5,
            recency_score=0.90,
            citation_score=0.5,
            relevance_score=1.4,
            rigor_score=0.8,
        )
        w = get_default_cs_weights("balanced")
        score = calculate_cs_final_score(m, w)
        # Expected: ~6.95 → Tier 2
        assert 6.5 <= score <= 7.5
        from skills.imported.literature_search.scoring import classify_tier

        assert classify_tier(score) == "Tier 2"

    def test_result_bounded(self) -> None:
        from skills.imported.literature_search.scoring_cs import (
            CSMetrics,
            CSWeights,
            calculate_cs_final_score,
        )

        m = CSMetrics(
            venue_tier=5.0,
            recency_score=1.0,
            citation_score=2.0,
            relevance_score=2.0,
            rigor_score=1.0,
        )
        w = CSWeights(V_weight=0.25, R_weight=0.10, C_weight=0.20, Re_weight=0.30, E_weight=0.15)
        assert 0.0 <= calculate_cs_final_score(m, w) <= 10.0


class TestExtractCSMetrics:
    """extract_cs_metrics() — composes all scoring functions."""

    def test_typical_paper(self) -> None:
        from skills.imported.literature_search.scoring_cs import extract_cs_metrics

        paper = {
            "venue": "arXiv preprint arXiv:2406.14497",
            "year": 2024,
            "citation_count": 15,
            "title": "CodeRAG-Bench: Can Retrieval Augment Code Generation?",
            "abstract": "We propose a benchmark for retrieval-augmented code generation.",
        }
        m = extract_cs_metrics(paper, "retrieval augmented code generation")
        assert m.venue_tier == 3.0  # arXiv with known venue info
        assert m.recency_score > 0.0
        assert m.citation_score > 0.0
        assert m.relevance_score > 0.0

    def test_minimal_paper(self) -> None:
        from skills.imported.literature_search.scoring_cs import extract_cs_metrics

        paper = {"title": "Some paper"}
        m = extract_cs_metrics(paper, "test query")
        # All defaults: venue=2.0, recency=0.50, citations=0.50, rigor=0.40
        assert m.venue_tier == 2.0
        assert m.recency_score == 0.50
        assert m.citation_score == 0.50
        assert m.rigor_score == 0.40
