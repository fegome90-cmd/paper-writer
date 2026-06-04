"""Tests for quality_appraisal validator."""

from __future__ import annotations

import json
from pathlib import Path

from validators.quality_appraisal import QualityAppraisalValidator


def _make_paper(**overrides: object) -> dict[str, object]:
    """Create a minimal paper dict for testing."""
    base: dict[str, object] = {
        "title": "Test Paper",
        "year": 2023,
        "doi": "10.1/test",
        "abstract": "A test paper about retrieval-augmented code generation.",
        "citation_count": 100,
        "venue": "ICSE",
    }
    base.update(overrides)
    return base


class TestVenueReputation:
    def test_top_tier(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_venue_reputation(_make_paper(venue="NeurIPS")) == 5
        assert v.score_venue_reputation(_make_paper(venue="ICSE")) == 5

    def test_good_venue(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_venue_reputation(_make_paper(venue="arXiv")) == 3

    def test_unknown_venue(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_venue_reputation(_make_paper(venue="Workshop X")) == 2

    def test_empty_venue(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_venue_reputation(_make_paper(venue="")) == 1


class TestCitationImpact:
    def test_high_impact(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_citation_impact(_make_paper(citation_count=5000)) == 5

    def test_medium_impact(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_citation_impact(_make_paper(citation_count=200)) == 4

    def test_low_impact(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_citation_impact(_make_paper(citation_count=10)) == 2

    def test_no_citations(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_citation_impact(_make_paper(citation_count=0)) == 1


class TestMethodologyRigor:
    def test_rct(self) -> None:
        v = QualityAppraisalValidator()
        assert (
            v.score_methodology_rigor(
                _make_paper(abstract="A randomized controlled trial of code generation.")
            )
            == 5
        )

    def test_benchmark(self) -> None:
        v = QualityAppraisalValidator()
        assert (
            v.score_methodology_rigor(
                _make_paper(abstract="We evaluate on a benchmark for code generation.")
            )
            == 4
        )

    def test_survey(self) -> None:
        v = QualityAppraisalValidator()
        assert (
            v.score_methodology_rigor(
                _make_paper(abstract="A survey of 100 developers about tools.")
            )
            == 3
        )

    def test_no_signals(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_methodology_rigor(_make_paper(abstract="A theoretical framework.")) == 1


class TestReproducibility:
    def test_peer_reviewed_with_arxiv(self) -> None:
        v = QualityAppraisalValidator()
        assert (
            v.score_reproducibility(
                _make_paper(doi="10.1/test", arxiv_id="2301.00001")
            )
            >= 3
        )

    def test_open_source(self) -> None:
        v = QualityAppraisalValidator()
        assert (
            v.score_reproducibility(
                _make_paper(abstract="Code available at github.com/test/repo")
            )
            >= 2
        )

    def test_minimal_no_signals(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_reproducibility(_make_paper(doi="", arxiv_id="")) == 1


class TestRecency:
    def test_brand_new(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_recency(_make_paper(year=2025)) == 5

    def test_recent(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_recency(_make_paper(year=2022)) == 4

    def test_old(self) -> None:
        v = QualityAppraisalValidator()
        assert v.score_recency(_make_paper(year=2015)) == 1


class TestAppraiseStudy:
    def test_high_quality(self) -> None:
        v = QualityAppraisalValidator()
        result = v.appraise_study(
            _make_paper(
                venue="NeurIPS",
                citation_count=5000,
                abstract="We benchmark our approach with ablation study.",
                year=2024,
                doi="10.1/high",
                arxiv_id="2401.00001",
            )
        )
        assert result["quality_rating"] == "high"
        assert result["weighted_score"] >= 4.0

    def test_low_quality(self) -> None:
        v = QualityAppraisalValidator()
        result = v.appraise_study(
            _make_paper(
                venue="Workshop",
                citation_count=0,
                abstract="A position paper.",
                year=2015,
                doi="",
            )
        )
        assert result["quality_rating"] in ("low", "very_low")
        assert result["weighted_score"] < 3.0


class TestValidate:
    def test_with_papers(self, tmp_path: Path) -> None:
        v = QualityAppraisalValidator()
        evidence = {
            "total_raw": 3,
            "total_screened": 3,
            "evidence": [
                _make_paper(title="High", venue="NeurIPS", citation_count=5000, year=2024),
                _make_paper(
                    title="Medium", venue="arXiv", citation_count=50, year=2022
                ),
                _make_paper(
                    title="Low", venue="Workshop", citation_count=0, year=2018
                ),
            ],
        }
        evidence_path = tmp_path / "screened_evidence.json"
        evidence_path.write_text(json.dumps(evidence))

        output_path = tmp_path / "quality_appraisal.json"
        findings = v.validate(evidence_path, output_path)

        assert len(findings) >= 1  # at least the summary finding
        assert output_path.exists()

        report = json.loads(output_path.read_text())
        assert report["total_appraised"] == 3
        assert "summary" in report
        assert report["summary"]["high"] + report["summary"]["moderate"] + report["summary"]["low"] + report["summary"]["very_low"] == 3

    def test_no_evidence(self, tmp_path: Path) -> None:
        v = QualityAppraisalValidator()
        findings = v.validate(tmp_path / "nonexistent.json")
        assert len(findings) == 1
        assert "No screened evidence" in findings[0]["message"]

    def test_empty_evidence(self, tmp_path: Path) -> None:
        v = QualityAppraisalValidator()
        evidence_path = tmp_path / "screened_evidence.json"
        evidence_path.write_text('{"evidence": []}')

        findings = v.validate(evidence_path)
        assert len(findings) == 1
        assert "empty" in findings[0]["message"].lower()
