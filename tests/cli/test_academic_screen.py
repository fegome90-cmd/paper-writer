"""Tests for academic-evidence-curation mode: PR2 search/screen artifacts.

Covers: screening_records (included+excluded), screening_history,
supports_critical_claim, critical_claim_refs, and chaining single-writer
integrity.
"""

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_results(path: Path, papers: list[dict[str, Any]] | None = None) -> Path:
    """Write a minimal raw_results.json for testing."""
    if papers is None:
        papers = [
            {
                "title": (
                    "Randomized controlled trial of novel antihypertensive"
                    " therapy in patients with severe hypertension"
                ),
                "doi": "10.1000/inc",
                "year": 2023,
                "authors": "Author A",
                "domain": "clinical",
                "metrics": {
                    "population_score": 8,
                    "intervention_score": 7,
                    "outcome_score": 6,
                    "evidence_score": 5,
                    "sample_score": 1.0,
                    "journal_score": 2.0,
                    "citations_score": 0.5,
                    "coi_penalty": 0,
                    "context_score": 7,
                },
            },
            {
                "title": "Observational survey of health outcomes in elderly patients",
                "doi": "10.1000/exc",
                "year": 2015,
                "authors": "Author B",
                "domain": "clinical",
                "metrics": {
                    "population_score": 2,
                    "intervention_score": 1,
                    "outcome_score": 1,
                    "evidence_score": 1,
                    "sample_score": 0.1,
                    "journal_score": 0.5,
                    "citations_score": 0,
                    "context_score": 2,
                },
            },
        ]
    raw = {"query": "test query", "date": "2026-06-09", "papers": papers}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _run_screen(tmp_path: Path, *, mode: str = "rapid", min_tier: str = "Tier 3") -> dict[str, Any]:
    """Run screen through the adapter and return the screened evidence dict."""
    search_dir = tmp_path / "search"
    _make_raw_results(search_dir / "raw_results.json")

    from skills.local.adapters import LiteratureSearchAdapter

    adapter = LiteratureSearchAdapter()
    result = adapter.execute(
        command="screen",
        inputs={
            "search_dir": str(search_dir),
            "output_dir": str(search_dir),
            "min_tier": min_tier,
            "mode": mode,
        },
        context={"cwd": str(tmp_path)},
    )
    assert result.status == "pass"
    evidence_path = search_dir / "screened_evidence.json"
    assert evidence_path.exists()
    return json.loads(evidence_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# PR2 Task 2.1: screening_records + screening_history
# ---------------------------------------------------------------------------


class TestAcademicScreeningRecords:
    """screened_evidence.json gains screening_records in academic mode."""

    def test_rapid_mode_no_screening_records(self, tmp_path: Path) -> None:
        """Rapid mode does NOT add screening_records."""
        evidence = _run_screen(tmp_path, mode="rapid")
        assert "screening_records" not in evidence

    def test_academic_mode_has_screening_records(self, tmp_path: Path) -> None:
        """Academic mode adds screening_records with included+excluded rows."""
        evidence = _run_screen(tmp_path, mode="academic")
        assert "screening_records" in evidence
        records = evidence["screening_records"]
        assert isinstance(records, list)
        # Should have records for all screened papers (both included and excluded)
        assert len(records) >= 1

    def test_screening_record_has_required_fields(self, tmp_path: Path) -> None:
        """Each screening record has record_id, included, screening_history."""
        evidence = _run_screen(tmp_path, mode="academic")
        for rec in evidence["screening_records"]:
            assert "record_id" in rec
            assert "included" in rec
            assert isinstance(rec["included"], bool)
            assert "screening_history" in rec
            assert isinstance(rec["screening_history"], list)

    def test_screening_history_has_stage_decision_reason(self, tmp_path: Path) -> None:
        """Screening history entries have stage, decision, reason."""
        evidence = _run_screen(tmp_path, mode="academic")
        for rec in evidence["screening_records"]:
            for entry in rec["screening_history"]:
                assert "stage" in entry
                assert "decision" in entry
                assert "reason" in entry


class TestAcademicEvidenceRecords:
    """Evidence records in academic mode gain scope and epistemic fields."""

    def test_rapid_mode_no_scope_classification(self, tmp_path: Path) -> None:
        """Rapid mode does NOT add scope_classification."""
        evidence = _run_screen(tmp_path, mode="rapid")
        for rec in evidence.get("evidence", []):
            assert "scope_classification" not in rec

    def test_academic_mode_has_scope_classification(self, tmp_path: Path) -> None:
        """Academic mode adds scope_classification to evidence records."""
        evidence = _run_screen(tmp_path, mode="academic")
        assert len(evidence.get("evidence", [])) >= 1
        for rec in evidence["evidence"]:
            assert "scope_classification" in rec
            assert rec["scope_classification"] in (
                "core",
                "adjacent",
                "horizon_scan",
                "protocol_only",
            )

    def test_academic_mode_has_epistemic_classification(self, tmp_path: Path) -> None:
        """Academic mode adds epistemic_classification to evidence records."""
        evidence = _run_screen(tmp_path, mode="academic")
        for rec in evidence["evidence"]:
            assert "epistemic_classification" in rec

    def test_academic_mode_has_screening_stage(self, tmp_path: Path) -> None:
        """Academic mode adds screening_stage derived from screening_history."""
        evidence = _run_screen(tmp_path, mode="academic")
        for rec in evidence["evidence"]:
            assert "screening_stage" in rec


class TestAcademicSearchPlan:
    """search_plan.json in academic mode carries amendments."""

    def test_search_plan_preserves_amendments(self, tmp_path: Path) -> None:
        """When amendments are present, search_plan.json includes them."""
        search_dir = tmp_path / "search"
        _make_raw_results(search_dir / "raw_results.json")

        from skills.local.adapters import LiteratureSearchAdapter

        adapter = LiteratureSearchAdapter()
        result = adapter.execute(
            command="search",
            inputs={
                "query": "test query",
                "output_dir": str(search_dir),
                "raw_papers": (
                    '[{"title":"P1","doi":"10.1000/a","year":2023,"authors":"X","metrics":{}}]'
                ),
                "mode": "academic",
                "search_window": {"start_year": 2020, "end_year": 2024},
                "amendments": [{"reason": "Added seminal paper", "records": ["10.1000/a"]}],
            },
            context={"cwd": str(tmp_path)},
        )
        assert result.status == "pass"
        plan_path = search_dir / "search_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["amendments"][0]["reason"] == "Added seminal paper"
        assert plan["amendments"][0]["records"] == ["10.1000/a"]


class TestChainingSingleWriter:
    """Chaining must not break single-writer authority for search_plan.json."""

    def test_chain_preserves_existing_search_plan(self, tmp_path: Path) -> None:
        """After chain, search_plan.json still has the original search window."""
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        # Create initial search artifacts
        _make_raw_results(search_dir / "raw_results.json")
        plan_path = search_dir / "search_plan.json"
        plan_path.write_text(
            json.dumps(
                {
                    "query": "test",
                    "search_window": {"start_year": 2020, "end_year": 2024},
                }
            ),
            encoding="utf-8",
        )

        # Chain should NOT overwrite the original search_plan.json
        # (chain uses search_module.search() which writes plan, but our
        # adapter-level search_plan should take precedence)
        # This test documents the expected behavior for PR2 Task 2.3
        # Full implementation deferred to Task 2.3 GREEN
        pass
