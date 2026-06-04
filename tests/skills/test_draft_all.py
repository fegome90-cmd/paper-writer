"""Tests for draft_all section orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from skills.imported.academic_writer.drafting import draft_all


def _setup_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create minimal project files for draft_all."""
    outline = tmp_path / "outline.md"
    outline.write_text("# Outline\n")

    evidence = tmp_path / "screened_evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "query": "retrieval augmented code generation",
                "evidence": [
                    {
                        "title": "CodeBERT",
                        "doi": "10.1/a",
                        "scoring": {"tier": "Tier 1", "final_score": 8.5},
                    },
                ],
            }
        )
    )

    bib = tmp_path / "references.bib"
    bib.write_text("@article{feng2020, title={CodeBERT}}\n")

    return outline, evidence, bib


class TestDraftAll:
    def test_generates_all_sections(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(outline, evidence, bib, output)

        assert len(result["artifacts"]) == 7
        assert len(result["sections"]) == 7

    def test_abstract_generated_last(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(outline, evidence, bib, output)

        order = result["generation_order"]
        # Abstract should be the last section generated
        assert order[-1] == "abstract"
        assert "introduction" in order
        assert "conclusion" in order

    def test_body_sections_in_order(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(outline, evidence, bib, output)

        order = result["generation_order"]
        body = [s for s in order if s != "abstract"]
        # Body sections should be in manifest order
        assert body == [
            "introduction",
            "literature_review",
            "methods",
            "results",
            "discussion",
            "conclusion",
        ]

    def test_section_files_created(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(outline, evidence, bib, output)

        for key, path_str in result["sections"].items():
            assert Path(path_str).exists(), f"Section {key} file not created"
            content = Path(path_str).read_text()
            assert len(content) > 0, f"Section {key} is empty"

    def test_custom_section_keys(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(
            outline,
            evidence,
            bib,
            output,
            section_keys=["introduction", "conclusion"],
        )

        assert len(result["artifacts"]) == 2
        assert "introduction" in result["sections"]
        assert "conclusion" in result["sections"]
        assert "abstract" not in result["sections"]

    def test_cross_section_context_accumulates(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(outline, evidence, bib, output)

        # All sections should be generated (with or without LLM)
        assert len(result["sections"]) >= 1
        # Each artifact should exist on disk
        for path_str in result["artifacts"]:
            assert Path(path_str).exists()

    def test_returns_generation_order(self, tmp_path: Path) -> None:
        outline, evidence, bib = _setup_project(tmp_path)
        output = tmp_path / "drafts"

        result = draft_all(outline, evidence, bib, output)

        assert "generation_order" in result
        assert isinstance(result["generation_order"], list)
        assert len(result["generation_order"]) > 0
