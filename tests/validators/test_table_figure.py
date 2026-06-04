"""Tests for table and figure generation."""

from __future__ import annotations

import json
from pathlib import Path

from validators.table_figure import (
    generate_prisma_mermaid,
    generate_study_table,
    validate_tables_figures,
)


def _write_evidence(path: Path, papers: list[dict[str, object]], flow: bool = True) -> None:
    """Write screened_evidence.json with optional PRISMA flow."""
    data: dict[str, object] = {"evidence": papers}
    if flow:
        data["prisma_flow"] = {
            "identification": {
                "database_results": 5,
                "other_sources": 3,
                "seed_papers": 2,
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
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _papers(n: int = 3) -> list[dict[str, object]]:
    return [
        {
            "title": f"Paper {i}: A Study on LLM Code Generation",
            "year": 2023 + i,
            "venue": "ICSE",
            "citation_count": 50 * i,
            "scoring": {"tier": "Tier 1" if i % 2 == 0 else "Tier 2", "final_score": 7.0 + i * 0.5},
        }
        for i in range(n)
    ]


class TestPrismaMermaid:
    def test_generates_mermaid(self, tmp_path: Path) -> None:
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, _papers())
        result = generate_prisma_mermaid(ev)
        assert result.startswith("flowchart TD")
        assert "Identification" in result
        assert "Studies included" in result

    def test_contains_all_counts(self, tmp_path: Path) -> None:
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, _papers())
        result = generate_prisma_mermaid(ev)
        assert "Database: 5" in result
        assert "8" in result  # studies included

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with __import__("pytest").raises(ValueError, match="Cannot read"):
            generate_prisma_mermaid(tmp_path / "nonexistent.json")

    def test_no_prisma_flow_raises(self, tmp_path: Path) -> None:
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, _papers(), flow=False)
        with __import__("pytest").raises(ValueError, match="No prisma_flow"):
            generate_prisma_mermaid(ev)


class TestStudyTable:
    def test_generates_markdown_table(self, tmp_path: Path) -> None:
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, _papers(3))
        result = generate_study_table(ev)
        assert "| # |" in result
        assert "Paper 0" in result
        assert "ICSE" in result

    def test_truncates_long_titles(self, tmp_path: Path) -> None:
        papers = [
            {
                "title": "A" * 100,
                "year": 2023,
                "venue": "V",
                "scoring": {"tier": "T1", "final_score": 8.0},
            }
        ]
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, papers)
        result = generate_study_table(ev)
        assert "..." in result

    def test_empty_evidence(self, tmp_path: Path) -> None:
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, [])
        result = generate_study_table(ev)
        assert "No screened evidence" in result

    def test_max_rows(self, tmp_path: Path) -> None:
        ev = tmp_path / "screened_evidence.json"
        _write_evidence(ev, _papers(20))
        result = generate_study_table(ev, max_rows=5)
        assert "Showing 5 of 20" in result

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with __import__("pytest").raises(ValueError):
            generate_study_table(tmp_path / "nonexistent.json")


class TestValidateTablesFigures:
    def test_no_tables_flagged(self, tmp_path: Path) -> None:
        draft = tmp_path / "drafts"
        draft.mkdir()
        (draft / "intro.md").write_text("# Introduction\nNo tables here.\n")
        findings = validate_tables_figures(draft)
        assert any(f["rule_id"] == "tables_figures.no_tables" for f in findings)

    def test_no_mermaid_flagged(self, tmp_path: Path) -> None:
        draft = tmp_path / "drafts"
        draft.mkdir()
        (draft / "methods.md").write_text("# Methods\n| A | B |\n|---|---|\n| 1 | 2 |\n")
        findings = validate_tables_figures(draft)
        assert any(f["rule_id"] == "tables_figures.no_figures" for f in findings)
        assert not any(f["rule_id"] == "tables_figures.no_tables" for f in findings)

    def test_both_present_no_findings(self, tmp_path: Path) -> None:
        draft = tmp_path / "drafts"
        draft.mkdir()
        content = "# Results\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```mermaid\nflowchart TD\n```"
        (draft / "results.md").write_text(content)
        findings = validate_tables_figures(draft)
        assert len(findings) == 0

    def test_missing_draft_dir(self, tmp_path: Path) -> None:
        findings = validate_tables_figures(tmp_path / "nonexistent")
        assert any("missing_draft_dir" in f["rule_id"] for f in findings)

    def test_empty_drafts(self, tmp_path: Path) -> None:
        draft = tmp_path / "drafts"
        draft.mkdir()
        (draft / "empty.md").write_text("")
        findings = validate_tables_figures(draft)
        assert any("empty_drafts" in f["rule_id"] for f in findings)
