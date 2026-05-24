"""Tests for skill adapters (LiteratureSearchAdapter, AcademicWriterAdapter)."""

import json
from pathlib import Path

from skills.local.adapters import AcademicWriterAdapter, LiteratureSearchAdapter


class TestLiteratureSearchAdapter:
    """Tests for LiteratureSearchAdapter."""

    def test_name_property(self) -> None:
        adapter = LiteratureSearchAdapter()
        assert adapter.name == "literature-search"

    def test_search_produces_valid_json(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={"query": "voice disorders", "output_dir": str(output_dir)},
            context={},
        )

        assert result.status == "pass"
        assert len(result.artifacts) == 2

        # Verify search_plan.json is valid JSON with expected fields
        plan_path = Path(result.artifacts[0])
        assert plan_path.name == "search_plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["query"] == "voice disorders"
        assert "strategy" in plan

        # Verify raw_results.json has paper entries
        results_path = Path(result.artifacts[1])
        assert results_path.name == "raw_results.json"
        results = json.loads(results_path.read_text(encoding="utf-8"))
        assert results["total_results"] > 0
        assert len(results["papers"]) > 0
        for paper in results["papers"]:
            assert "title" in paper
            assert "doi" in paper
            assert "abstract" in paper

    def test_screen_produces_screened_evidence(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "outputs" / "search"
        search_dir.mkdir(parents=True)

        # Create raw_results.json for screen to read
        raw_data = {
            "query": "voice disorders",
            "total_results": 2,
            "papers": [
                {"title": "Paper A", "doi": "10.1000/a", "year": 2023},
                {"title": "Paper B", "doi": "10.1000/b", "year": 2024},
            ],
        }
        (search_dir / "raw_results.json").write_text(json.dumps(raw_data), encoding="utf-8")

        result = adapter.execute(
            command="screen",
            inputs={
                "search_dir": str(search_dir),
                "output_dir": str(search_dir),
            },
            context={},
        )

        assert result.status == "pass"
        assert len(result.artifacts) == 1

        evidence_path = Path(result.artifacts[0])
        assert evidence_path.name == "screened_evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert evidence["total_screened"] == 2
        assert len(evidence["evidence"]) == 2

    def test_unknown_command_returns_fail(self) -> None:
        adapter = LiteratureSearchAdapter()
        result = adapter.execute(
            command="bogus",
            inputs={},
            context={},
        )
        assert result.status == "fail"
        assert "bogus" in result.summary


class TestAcademicWriterAdapter:
    """Tests for AcademicWriterAdapter."""

    def test_name_property(self) -> None:
        adapter = AcademicWriterAdapter()
        assert adapter.name == "academic-writer"

    def test_draft_outline_produces_markdown(self, tmp_path: Path) -> None:
        adapter = AcademicWriterAdapter()
        drafts_dir = tmp_path / "outputs" / "drafts"
        search_dir = tmp_path / "outputs" / "search"

        # Create screened evidence
        search_dir.mkdir(parents=True)
        evidence = {
            "query": "voice disorders",
            "total_raw": 1,
            "total_screened": 1,
            "evidence": [
                {"title": "Test Paper", "doi": "10.1000/test", "year": 2023, "authors": "Smith J"},
            ],
        }
        evidence_path = search_dir / "screened_evidence.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

        # Create bib file with a key
        bib_path = tmp_path / "templates" / "references.bib"
        bib_path.parent.mkdir(parents=True)
        bib_path.write_text(
            "@article{smith2024voice,\n  title = {Test},\n  year = {2024}\n}\n",
            encoding="utf-8",
        )

        result = adapter.execute(
            command="draft_outline",
            inputs={
                "evidence_path": str(evidence_path),
                "output_dir": str(drafts_dir),
                "bib_path": str(bib_path),
            },
            context={},
        )

        assert result.status == "pass"
        assert len(result.artifacts) == 1

        outline_path = Path(result.artifacts[0])
        assert outline_path.name == "outline.md"
        content = outline_path.read_text(encoding="utf-8")
        assert "## 1. Introduction" in content
        assert "## 2. Methods" in content
        assert "## 3. Results" in content
        assert "## 4. Discussion" in content
        # Should reference citation keys from bib and evidence
        assert "smith2024voice" in content or "@" in content

    def test_draft_section_produces_markdown_with_citations(self, tmp_path: Path) -> None:
        adapter = AcademicWriterAdapter()
        drafts_dir = tmp_path / "outputs" / "drafts"
        search_dir = tmp_path / "outputs" / "search"

        # Create screened evidence
        search_dir.mkdir(parents=True)
        evidence = {
            "query": "voice disorders",
            "total_raw": 2,
            "total_screened": 2,
            "evidence": [
                {"title": "Paper A", "doi": "10.1000/a", "year": 2023, "authors": "Smith J"},
                {"title": "Paper B", "doi": "10.1000/b", "year": 2024, "authors": "Garcia M"},
            ],
        }
        evidence_path = search_dir / "screened_evidence.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

        # Create outline
        drafts_dir.mkdir(parents=True)
        outline_path = drafts_dir / "outline.md"
        outline_path.write_text("# Outline\n## Introduction\n", encoding="utf-8")

        # Create bib
        bib_path = tmp_path / "templates" / "references.bib"
        bib_path.parent.mkdir(parents=True)
        bib_path.write_text(
            "@article{smith2024voice,\n  title = {Voice Disorders},\n}\n",
            encoding="utf-8",
        )

        result = adapter.execute(
            command="draft_section",
            inputs={
                "section_name": "introduction",
                "outline_path": str(outline_path),
                "evidence_path": str(evidence_path),
                "bib_path": str(bib_path),
                "output_dir": str(drafts_dir),
            },
            context={},
        )

        assert result.status == "pass"
        assert len(result.artifacts) == 1

        section_path = Path(result.artifacts[0])
        assert section_path.name == "introduction.md"
        content = section_path.read_text(encoding="utf-8")
        assert "# Introduction" in content
        # Should have citation references (@-keys)
        assert "@" in content or "smith" in content.lower()

    def test_unknown_command_returns_fail(self) -> None:
        adapter = AcademicWriterAdapter()
        result = adapter.execute(
            command="bogus",
            inputs={},
            context={},
        )
        assert result.status == "fail"
        assert "bogus" in result.summary
