# ruff: noqa: RUF003 E501
# test_scoring.py
"""
Exhaustive test suite for the literature-search scoring engine.

TDD Evidence:
  - RED:   All tests written first against non-existent imports/functions
  - GREEN: Implementation in scoring.py made each test pass
  - REFACTOR: Cleaned up after all tests green

Run: uv run pytest resources/tests/test_scoring.py -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skills.imported.literature_search.scoring import (
    PaperMetrics,
    ScoringWeights,
    calculate_d_score,
    calculate_final_score,
    classify_tier,
    deduplicate,
    get_default_weights,
    verify_citation,
)

# =============================================================================
# HELPERS
# =============================================================================

def _perfect_metrics() -> PaperMetrics:
    """Paper with maximum possible scores on every dimension."""
    return PaperMetrics(
        population_score=10.0,
        intervention_score=10.0,
        outcome_score=10.0,
        evidence_score=5.0,
        sample_score=2.0,
        journal_score=2.0,
        citations_score=1.0,
        coi_penalty=0.0,
        context_score=10.0,
    )


def _zero_metrics() -> PaperMetrics:
    """Paper with all-zero relevance scores."""
    return PaperMetrics(
        population_score=0.0,
        intervention_score=0.0,
        outcome_score=0.0,
        evidence_score=0.0,
        sample_score=0.0,
        journal_score=0.0,
        citations_score=0.0,
        coi_penalty=0.0,
        context_score=0.0,
    )


# =============================================================================
# 1. D-SCORE (original + expanded)
# =============================================================================

class TestCalculateDScore:
    """D = evidence + sample + journal + citations + coi_penalty, clamped [0, 10]."""

    def test_meta_low_n_no_citations(self) -> None:
        """Meta-analysis with tiny sample, Q1, almost no citations."""
        m = PaperMetrics(
            population_score=10.0, intervention_score=10.0, outcome_score=10.0,
            evidence_score=5.0, sample_score=0.25, journal_score=2.0,
            citations_score=0.1, coi_penalty=0.0, context_score=10.0,
        )
        assert calculate_d_score(m) == pytest.approx(7.35, rel=1e-3)

    def test_meta_massive_highly_cited(self) -> None:
        m = PaperMetrics(
            population_score=10.0, intervention_score=10.0, outcome_score=10.0,
            evidence_score=5.0, sample_score=2.0, journal_score=2.0,
            citations_score=0.75, coi_penalty=0.0, context_score=10.0,
        )
        assert calculate_d_score(m) == pytest.approx(9.75, rel=1e-3)

    def test_rct_mid_n_no_coi(self) -> None:
        m = PaperMetrics(
            population_score=10.0, intervention_score=10.0, outcome_score=10.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=0.0, context_score=10.0,
        )
        assert calculate_d_score(m) == pytest.approx(7.10, rel=1e-3)

    def test_rct_mid_n_with_industry_coi(self) -> None:
        m = PaperMetrics(
            population_score=10.0, intervention_score=10.0, outcome_score=10.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=-0.5, context_score=10.0,
        )
        assert calculate_d_score(m) == pytest.approx(6.60, rel=1e-3)

    def test_perfect_paper_is_10(self) -> None:
        assert calculate_d_score(_perfect_metrics()) == 10.0

    def test_capped_at_10(self) -> None:
        m = PaperMetrics(
            population_score=10.0, intervention_score=10.0, outcome_score=10.0,
            evidence_score=6.0, sample_score=2.0, journal_score=2.0,
            citations_score=1.0, coi_penalty=0.0, context_score=10.0,
        )
        assert calculate_d_score(m) == 10.0

    def test_floor_at_zero(self) -> None:
        """Extreme negative COI can't push below 0."""
        m = PaperMetrics(
            population_score=0.0, intervention_score=0.0, outcome_score=0.0,
            evidence_score=0.5, sample_score=0.25, journal_score=0.5,
            citations_score=0.1, coi_penalty=-0.5, context_score=0.0,
        )
        result = calculate_d_score(m)
        assert result >= 0.0
        assert result == pytest.approx(0.85, rel=1e-3)

    def test_cross_sectional_low_scores(self) -> None:
        """Cross-sectional n=30, Q3, 0 citations → D=2.85 (from ranking-criteria.md)."""
        m = PaperMetrics(
            population_score=6.0, intervention_score=4.0, outcome_score=5.0,
            evidence_score=1.5, sample_score=0.25, journal_score=1.0,
            citations_score=0.1, coi_penalty=0.0, context_score=4.0,
        )
        assert calculate_d_score(m) == pytest.approx(2.85, rel=1e-3)

    def test_cohort_mid_scores(self) -> None:
        """Cohorte n=200, Q2, 20 citas → D=6.00 (from ranking-criteria.md)."""
        m = PaperMetrics(
            population_score=8.0, intervention_score=6.0, outcome_score=7.0,
            evidence_score=3.0, sample_score=1.0, journal_score=1.5,
            citations_score=0.5, coi_penalty=0.0, context_score=6.0,
        )
        assert calculate_d_score(m) == pytest.approx(6.00, rel=1e-3)


# =============================================================================
# 2. FINAL SCORE (A × wA + B × wB + C × wC + D × wD + E × wE)
# =============================================================================

class TestCalculateFinalScore:
    """Weighted sum of A..E, range [0, 10]."""

    def test_perfect_paper_balanced_weights(self) -> None:
        """All 10s with balanced weights → 10.0."""
        weights = get_default_weights("balanced")
        assert calculate_final_score(_perfect_metrics(), weights) == 10.0

    def test_zero_relevance_scores(self) -> None:
        """All zeros → 0.0 regardless of weights."""
        weights = get_default_weights("balanced")
        assert calculate_final_score(_zero_metrics(), weights) == 0.0

    def test_mixed_scores_balanced(self) -> None:
        """Manual calculation: A=8, B=6, C=7, D=7.10, E=5 with balanced weights."""
        m = PaperMetrics(
            population_score=8.0, intervention_score=6.0, outcome_score=7.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=0.0, context_score=5.0,
        )
        weights = get_default_weights("balanced")
        # D = 7.10
        # final = 8*0.25 + 6*0.25 + 7*0.20 + 7.10*0.20 + 5*0.10
        #       = 2.0 + 1.5 + 1.4 + 1.42 + 0.5 = 6.82
        expected = 8.0*0.25 + 6.0*0.25 + 7.0*0.20 + 7.10*0.20 + 5.0*0.10
        assert calculate_final_score(m, weights) == pytest.approx(expected, rel=1e-3)

    def test_intervention_design_weights(self) -> None:
        """Intervention design phase should weight B more heavily."""
        m = PaperMetrics(
            population_score=5.0, intervention_score=10.0, outcome_score=5.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=0.0, context_score=5.0,
        )
        w_bal = get_default_weights("balanced")
        w_int = get_default_weights("intervention_design")
        score_bal = calculate_final_score(m, w_bal)
        score_int = calculate_final_score(m, w_int)
        # With B=10 and intervention_design weighing B at 35% vs balanced 25%,
        # score_int should be higher
        assert score_int > score_bal

    def test_problem_definition_weights_quality_more(self) -> None:
        """Problem definition phase weights D (quality) at 35%."""
        m = PaperMetrics(
            population_score=5.0, intervention_score=2.0, outcome_score=3.0,
            evidence_score=5.0, sample_score=2.0, journal_score=2.0,
            citations_score=1.0, coi_penalty=0.0, context_score=3.0,
        )
        w_bal = get_default_weights("balanced")
        w_prob = get_default_weights("problem_definition")
        score_bal = calculate_final_score(m, w_bal)
        score_prob = calculate_final_score(m, w_prob)
        # D=10 is very high, problem_definition weights D at 35% vs balanced 20%
        assert score_prob > score_bal

    def test_custom_weights(self) -> None:
        """Custom weights that only care about population."""
        w = ScoringWeights(A_weight=1.0, B_weight=0.0, C_weight=0.0,
                           D_weight=0.0, E_weight=0.0)
        m = PaperMetrics(
            population_score=7.5, intervention_score=0.0, outcome_score=0.0,
            evidence_score=0.0, sample_score=0.0, journal_score=0.0,
            citations_score=0.0, coi_penalty=0.0, context_score=0.0,
        )
        assert calculate_final_score(m, w) == pytest.approx(7.5, rel=1e-3)

    def test_weights_must_sum_to_one(self) -> None:
        """ScoringWeights should reject weights that don't sum to ~1.0."""
        with pytest.raises(ValueError):
            ScoringWeights(A_weight=0.5, B_weight=0.5, C_weight=0.5,
                           D_weight=0.0, E_weight=0.0)

    def test_final_score_is_bounded_0_to_10(self) -> None:
        """Even with extreme D values, final score stays in [0, 10]."""
        m = PaperMetrics(
            population_score=10.0, intervention_score=10.0, outcome_score=10.0,
            evidence_score=6.0, sample_score=2.0, journal_score=2.0,
            citations_score=1.0, coi_penalty=0.0, context_score=10.0,
        )
        w = get_default_weights("balanced")
        score = calculate_final_score(m, w)
        assert 0.0 <= score <= 10.0


# =============================================================================
# 3. TIER CLASSIFICATION
# =============================================================================

class TestClassifyTier:
    """Boundary tests for tier thresholds."""

    def test_tier_1_exact_8(self) -> None:
        assert classify_tier(8.0) == "Tier 1"

    def test_tier_1_high(self) -> None:
        assert classify_tier(10.0) == "Tier 1"

    def test_tier_2_just_below_8(self) -> None:
        assert classify_tier(7.99) == "Tier 2"

    def test_tier_2_mid(self) -> None:
        assert classify_tier(7.0) == "Tier 2"

    def test_tier_2_exact_65(self) -> None:
        assert classify_tier(6.5) == "Tier 2"

    def test_tier_3_just_below_65(self) -> None:
        assert classify_tier(6.49) == "Tier 3"

    def test_tier_3_exact_5(self) -> None:
        assert classify_tier(5.0) == "Tier 3"

    def test_discard_just_below_5(self) -> None:
        assert classify_tier(4.99) == "Discard"

    def test_discard_zero(self) -> None:
        assert classify_tier(0.0) == "Discard"

    def test_boundary_79_vs_80(self) -> None:
        """7.9 is Tier 2, 8.0 is Tier 1."""
        assert classify_tier(7.9) == "Tier 2"
        assert classify_tier(8.0) == "Tier 1"

    def test_boundary_64_vs_65(self) -> None:
        """6.4 is Tier 3, 6.5 is Tier 2."""
        assert classify_tier(6.4) == "Tier 3"
        assert classify_tier(6.5) == "Tier 2"

    def test_boundary_49_vs_50(self) -> None:
        """4.9 is Discard, 5.0 is Tier 3."""
        assert classify_tier(4.9) == "Discard"
        assert classify_tier(5.0) == "Tier 3"


# =============================================================================
# 4. PHASE WEIGHTS
# =============================================================================

class TestGetDefaultWeights:

    def test_balanced_weights(self) -> None:
        w = get_default_weights("balanced")
        assert w.A_weight == pytest.approx(0.25)
        assert w.B_weight == pytest.approx(0.25)
        assert w.C_weight == pytest.approx(0.20)
        assert w.D_weight == pytest.approx(0.20)
        assert w.E_weight == pytest.approx(0.10)

    def test_problem_definition_weights(self) -> None:
        w = get_default_weights("problem_definition")
        assert w.A_weight == pytest.approx(0.30)
        assert w.B_weight == pytest.approx(0.05)
        assert w.C_weight == pytest.approx(0.15)
        assert w.D_weight == pytest.approx(0.35)
        assert w.E_weight == pytest.approx(0.15)

    def test_intervention_design_weights(self) -> None:
        w = get_default_weights("intervention_design")
        assert w.A_weight == pytest.approx(0.15)
        assert w.B_weight == pytest.approx(0.35)
        assert w.C_weight == pytest.approx(0.25)
        assert w.D_weight == pytest.approx(0.15)
        assert w.E_weight == pytest.approx(0.10)

    def test_outcome_selection_weights(self) -> None:
        w = get_default_weights("outcome_selection")
        assert w.A_weight == pytest.approx(0.20)
        assert w.B_weight == pytest.approx(0.10)
        assert w.C_weight == pytest.approx(0.40)
        assert w.D_weight == pytest.approx(0.20)
        assert w.E_weight == pytest.approx(0.10)

    def test_all_phases_sum_to_one(self) -> None:
        for phase in ("balanced", "problem_definition", "intervention_design", "outcome_selection"):
            w = get_default_weights(phase)
            total = w.A_weight + w.B_weight + w.C_weight + w.D_weight + w.E_weight
            assert total == pytest.approx(1.0), f"{phase} weights don't sum to 1.0"

    def test_unknown_phase_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown phase"):
            get_default_weights("nonexistent_phase")


# =============================================================================
# 5. DEDUPLICATION
# =============================================================================

class TestDeduplicate:

    def test_same_doi_deduplicated(self) -> None:
        papers = [
            {"doi": "10.1234/test", "pmid": None, "title": "Paper A"},
            {"doi": "10.1234/test", "pmid": None, "title": "Paper A Duplicate"},
        ]
        unique, log = deduplicate(papers)
        assert len(unique) == 1
        assert len(log) == 1

    def test_same_pmid_deduplicated(self) -> None:
        papers = [
            {"doi": None, "pmid": "12345678", "title": "Paper A"},
            {"doi": None, "pmid": "12345678", "title": "Paper A Dup"},
        ]
        unique, log = deduplicate(papers)
        assert len(unique) == 1
        assert len(log) == 1

    def test_doi_takes_priority_over_pmid(self) -> None:
        """If both have DOI, dedup by DOI even if PMIDs differ."""
        papers = [
            {"doi": "10.1234/test", "pmid": "11111111", "title": "Paper A"},
            {"doi": "10.1234/test", "pmid": "22222222", "title": "Paper A Dup"},
        ]
        unique, _log = deduplicate(papers)
        assert len(unique) == 1

    def test_similar_titles_deduplicated(self) -> None:
        """Titles with >95% similarity are deduplicated (no DOI/PMID)."""
        papers = [
            {"doi": None, "pmid": None, "title": "Voice quality after total laryngectomy: a systematic review"},
            {"doi": None, "pmid": None, "title": "Voice quality after total laryngectomy: a systematic review"},
        ]
        unique, log = deduplicate(papers)
        assert len(unique) == 1
        assert len(log) == 1

    def test_near_identical_titles_deduplicated(self) -> None:
        """Titles differing by only a period or minor char (sim > 0.95)."""
        papers = [
            {"doi": None, "pmid": None, "title": "Communication outcomes after laryngectomy"},
            {"doi": None, "pmid": None, "title": "Communication outcomes after laryngectomy."},
        ]
        unique, _log = deduplicate(papers)
        assert len(unique) == 1

    def test_different_papers_kept_separate(self) -> None:
        papers = [
            {"doi": "10.1234/a", "pmid": "11111111", "title": "Paper A"},
            {"doi": "10.5678/b", "pmid": "22222222", "title": "Paper B"},
        ]
        unique, log = deduplicate(papers)
        assert len(unique) == 2
        assert len(log) == 0

    def test_no_ids_different_titles_kept_separate(self) -> None:
        papers = [
            {"doi": None, "pmid": None, "title": "Totally different topic A"},
            {"doi": None, "pmid": None, "title": "Completely unrelated subject B"},
        ]
        unique, log = deduplicate(papers)
        assert len(unique) == 2
        assert len(log) == 0

    def test_empty_list(self) -> None:
        unique, log = deduplicate([])
        assert unique == []
        assert log == []

    def test_three_copies_deduplicated_to_one(self) -> None:
        papers = [
            {"doi": "10.1234/x", "pmid": None, "title": "Same Paper"},
            {"doi": "10.1234/x", "pmid": None, "title": "Same Paper"},
            {"doi": "10.1234/x", "pmid": None, "title": "Same Paper"},
        ]
        unique, log = deduplicate(papers)
        assert len(unique) == 1
        assert len(log) == 2

    def test_custom_threshold(self) -> None:
        """Lower threshold catches more fuzzy matches."""
        papers = [
            {"doi": None, "pmid": None, "title": "Effect of X on Y in patients with Z"},
            {"doi": None, "pmid": None, "title": "Effects of X on Y among patients with Z"},
        ]
        # At default 0.95 this might not match (sim ~0.90)
        unique_default, _ = deduplicate(papers, threshold=0.95)
        # At 0.85 it should match
        unique_low, _ = deduplicate(papers, threshold=0.85)
        assert len(unique_low) <= len(unique_default)

    def test_log_contains_duplicate_reason(self) -> None:
        """Log entries should explain why a paper was deduplicated."""
        papers = [
            {"doi": "10.1234/test", "pmid": None, "title": "Paper A"},
            {"doi": "10.1234/test", "pmid": None, "title": "Paper A Dup"},
        ]
        _, log = deduplicate(papers)
        assert len(log) == 1
        entry = log[0]
        assert "doi" in entry.get("reason", "").lower() or "doi" in str(entry).lower()


# =============================================================================
# 6. CITATION VERIFICATION
# =============================================================================

class TestVerifyCitation:

    @patch("skills.imported.literature_search.scoring._crossref_lookup")
    def test_doi_verified(self, mock_crossref: MagicMock) -> None:
        mock_crossref.return_value = {"status": "verified", "method": "crossref_doi"}
        result = verify_citation(doi="10.1234/test.2024")
        assert result["status"] == "verified"
        assert result["method"] == "crossref_doi"

    @patch("skills.imported.literature_search.scoring._pubmed_lookup")
    def test_pmid_verified(self, mock_pubmed: MagicMock) -> None:
        mock_pubmed.return_value = {"status": "verified", "method": "pubmed_pmid"}
        result = verify_citation(pmid="12345678")
        assert result["status"] == "verified"
        assert result["method"] == "pubmed_pmid"

    def test_no_doi_no_pmid_returns_unverified(self) -> None:
        result = verify_citation()
        assert result["status"] == "unverified"
        assert "no identifier" in result.get("notes", "").lower() or "no doi" in result.get("notes", "").lower()

    @patch("skills.imported.literature_search.scoring._crossref_lookup")
    def test_doi_not_found_in_crossref(self, mock_crossref: MagicMock) -> None:
        mock_crossref.return_value = {"status": "not_found", "method": "crossref_doi"}
        result = verify_citation(doi="10.9999/nonexistent")
        assert result["status"] in ("not_found", "unverified")

    def test_doi_takes_priority_over_pmid(self) -> None:
        """When both provided, DOI lookup is attempted first."""
        with patch("skills.imported.literature_search.scoring._crossref_lookup") as mock_cr, \
             patch("skills.imported.literature_search.scoring._pubmed_lookup") as mock_pm:
            mock_cr.return_value = {"status": "verified", "method": "crossref_doi"}
            verify_citation(doi="10.1234/test", pmid="12345678")
            mock_cr.assert_called_once()
            mock_pm.assert_not_called()

    @patch("skills.imported.literature_search.scoring._crossref_lookup")
    def test_model_generated_citation_hard_reject(self, mock_crossref: MagicMock) -> None:
        """Citation with no DOI, no PMID, and no external source → hard reject."""
        mock_crossref.return_value = {"status": "not_found", "method": "crossref_doi"}
        result = verify_citation()  # no identifiers at all
        assert result["status"] in ("unverified", "rejected")


# =============================================================================
# 7. INTEGRATION: FULL PIPELINE
# =============================================================================

class TestFullPipeline:
    """End-to-end: score → classify → verify consistency."""

    def test_perfect_paper_is_tier_1(self) -> None:
        m = _perfect_metrics()
        w = get_default_weights("balanced")
        score = calculate_final_score(m, w)
        assert classify_tier(score) == "Tier 1"

    def test_zero_paper_is_discard(self) -> None:
        m = _zero_metrics()
        w = get_default_weights("balanced")
        score = calculate_final_score(m, w)
        assert classify_tier(score) == "Discard"

    def test_typical_paper_tier_2(self) -> None:
        """Typical decent paper should land in Tier 2."""
        m = PaperMetrics(
            population_score=8.0, intervention_score=7.0, outcome_score=6.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=0.0, context_score=6.0,
        )
        w = get_default_weights("balanced")
        score = calculate_final_score(m, w)
        # D=7.10, final = 8*0.25 + 7*0.25 + 6*0.20 + 7.10*0.20 + 6*0.10 = 6.97
        assert classify_tier(score) == "Tier 2"

    def test_paper_with_coi_drops_tier(self) -> None:
        """COI penalty should be enough to push a borderline paper down."""
        m_no_coi = PaperMetrics(
            population_score=8.0, intervention_score=6.0, outcome_score=7.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=0.0, context_score=5.0,
        )
        m_with_coi = PaperMetrics(
            population_score=8.0, intervention_score=6.0, outcome_score=7.0,
            evidence_score=4.5, sample_score=0.5, journal_score=2.0,
            citations_score=0.1, coi_penalty=-0.5, context_score=5.0,
        )
        w = get_default_weights("balanced")
        score_clean = calculate_final_score(m_no_coi, w)
        score_coi = calculate_final_score(m_with_coi, w)
        assert score_coi < score_clean
