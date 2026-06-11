"""Tests for reproducibility protocol generator."""

from __future__ import annotations

import json
from pathlib import Path

from validators.protocol_generator import generate_protocol


def _setup_search_dir(tmp_path: Path) -> Path:
    """Create a search directory with complete pipeline metadata."""
    search_dir = tmp_path / "search"
    search_dir.mkdir(parents=True)

    # raw_results.json
    raw = {
        "query": "retrieval augmented code generation",
        "total_input": 3,
        "total_after_dedup": 3,
        "papers": [
            {
                "title": "Paper 1",
                "doi": "10.1/a",
                "year": 2023,
                "source": "seed",
                "scoring": {"final_score": 7.0, "tier": "Tier 2"},
            },
            {
                "title": "Paper 2",
                "doi": "10.1/b",
                "year": 2024,
                "source": "backward_chaining",
                "scoring": {"final_score": 8.0, "tier": "Tier 1"},
            },
        ],
        "weights": {"phase": "balanced"},
    }
    (search_dir / "raw_results.json").write_text(json.dumps(raw))

    # chain_provenance.json
    provenance = {
        "stats": {
            "rounds_completed": 2,
            "total_api_calls": 10,
            "papers_by_round": {0: 3, 1: 5, 2: 2},
            "saturation": False,
        },
        "total_unique": 10,
        "provenance": [],
    }
    (search_dir / "chain_provenance.json").write_text(json.dumps(provenance))

    # screened_evidence.json with PRISMA flow
    evidence = {
        "query": "test",
        "total_raw": 10,
        "total_screened": 8,
        "min_tier": "Tier 3",
        "inclusion_criteria": ["tier <= Tier 3", "has title"],
        "prisma_flow": {
            "identification": {
                "database_results": 5,
                "other_sources": 2,
                "seed_papers": 3,
                "total_identified": 10,
                "duplicates_removed": 0,
            },
            "screening": {
                "records_screened": 10,
                "records_excluded": 2,
                "exclusion_reasons": {"tier_discard": 2},
            },
            "eligibility": {"records_assessed": 8, "records_excluded": 0},
            "included": {"studies_in_synthesis": 8},
        },
        "evidence": [],
    }
    (search_dir / "screened_evidence.json").write_text(json.dumps(evidence))

    # quality_appraisal.json (matches QualityAppraisalValidator.validate output)
    appraisal = {
        "total_appraised": 8,
        "method": {
            "dimensions": {
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
            },
        },
        "summary": {
            "high": 3,
            "moderate": 3,
            "low": 1,
            "very_low": 1,
            "mean_score": 3.5,
        },
        "appraisals": [],
    }
    (search_dir / "quality_appraisal.json").write_text(json.dumps(appraisal))

    return search_dir


class TestGenerateProtocol:
    def test_all_six_sections(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        protocol = generate_protocol(search_dir)

        assert "## 1. Search Strategy" in protocol
        assert "## 2. Screening Criteria" in protocol
        assert "## 3. Search Results" in protocol
        assert "## 4. Quality Appraisal" in protocol
        assert "## 5. Data Extraction" in protocol
        assert "## 6. Synthesis Method" in protocol

    def test_search_strategy_content(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        protocol = generate_protocol(search_dir)

        assert "retrieval augmented code generation" in protocol
        assert "2" in protocol  # rounds_completed
        assert "10" in protocol  # total_api_calls

    def test_prisma_flow_table(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        protocol = generate_protocol(search_dir)

        assert "Total identified" in protocol
        assert "Studies in synthesis" in protocol
        assert "tier_discard" in protocol

    def test_quality_appraisal_results(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        protocol = generate_protocol(search_dir)

        assert "High quality: 3" in protocol
        assert "Mean weighted score: 3.5" in protocol
        assert "Venue reputation" in protocol

    def test_data_extraction_fields(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        protocol = generate_protocol(search_dir)

        assert "`title`" in protocol
        assert "`doi`" in protocol
        assert "`year`" in protocol

    def test_writes_output_file(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        output = tmp_path / "protocol.md"
        generate_protocol(search_dir, output_path=output)

        assert output.exists()
        content = output.read_text()
        assert "Reproducibility Protocol" in content

    def test_minimal_data(self, tmp_path: Path) -> None:
        """Protocol generates even with no pipeline data."""
        search_dir = tmp_path / "empty_search"
        search_dir.mkdir()
        protocol = generate_protocol(search_dir)

        assert "## 1. Search Strategy" in protocol
        assert "No search data available" in protocol

    def test_custom_project_name(self, tmp_path: Path) -> None:
        search_dir = _setup_search_dir(tmp_path)
        protocol = generate_protocol(search_dir, project_name="My Review")

        assert "My Review" in protocol
