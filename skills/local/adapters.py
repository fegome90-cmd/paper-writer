"""Skill adapters bridging imported skills into the harness port.

Each adapter accepts the normalized SkillAdapter contract and translates
between the orchestrator's request format and the skill's internal API.

**Import truth:**
- LiteratureSearchAdapter uses real scoring functions from the vendored
  scoring.py (deduplicate, classify_tier, ScoringWeights, PaperMetrics).
- AcademicWriterAdapter uses section structures derived from the vendored
  SKILL.md prompt collection.
- Neither adapter invents content — they apply domain logic from real imports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.ports.skill_adapter import SkillAdapter, SkillResult
from skills.imported.academic_writer import drafting as writer_module
from skills.imported.literature_search import search as search_module


class LiteratureSearchAdapter(SkillAdapter):
    """Bridges literature-search skill to the harness.

    Uses real scoring functions from the vendored scoring.py:
    - deduplicate() for paper deduplication
    - classify_tier() for tier classification
    - calculate_final_score() with ScoringWeights
    - PaperMetrics for scoring dimensions

    The adapter does NOT call external APIs (PubMed, CrossRef, etc.).
    An external agent following SKILL.md collects papers and provides them
    via the 'raw_papers' input parameter.
    """

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        try:
            if command == "search":
                return self._handle_search(inputs)
            if command == "screen":
                return self._handle_screen(inputs)
            raise ValueError(f"Unknown command for {self.name}: {command}")
        except Exception as exc:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary=f"Error executing '{command}': {exc}",
                artifacts=[],
                gate_changes={},
                warnings=[str(exc)],
            )

    def _handle_search(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle the 'search' command using real scoring engine."""
        query = str(inputs.get("query", ""))
        output_dir = Path(inputs.get("output_dir", "outputs/search"))
        raw_papers = inputs.get("raw_papers")
        weights_phase = str(inputs.get("weights_phase", "balanced"))

        # If raw_papers is a string path, load from file
        if isinstance(raw_papers, str):
            raw_papers = json.loads(Path(raw_papers).read_text(encoding="utf-8"))
        # If raw_papers is a list of dicts from a previous agent run, use directly

        result = search_module.search(
            query=query,
            output_dir=output_dir,
            raw_papers=raw_papers,
            weights_phase=weights_phase,
        )
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Search completed using real scoring engine (dedup + tier)",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"search_completed": True},
        )

    def _handle_screen(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle the 'screen' command using real tier classification."""
        search_dir = Path(inputs.get("search_dir", "outputs/search"))
        output_dir = Path(inputs.get("output_dir", "outputs/search"))
        min_tier = str(inputs.get("min_tier", "Tier 3"))

        result = search_module.screen(
            search_dir=search_dir,
            output_dir=output_dir,
            min_tier=min_tier,
        )
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Screening completed using real tier classification",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"screened_evidence": True},
        )


class AcademicWriterAdapter(SkillAdapter):
    """Bridges academic-writer skill to the harness.

    The source skill is a PROMPT COLLECTION (SKILL.md with 7 section prompts).
    This adapter uses the section structures (CARS model, CONSORT flow, etc.)
    documented in those prompts to generate section skeletons.

    For real content generation, use the SKILL.md prompts directly with an LLM.
    The adapter generates structural templates, not LLM-quality prose.
    """

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "academic-writer"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        try:
            if command == "draft_outline":
                return self._handle_draft_outline(inputs)
            if command == "draft_section":
                return self._handle_draft_section(inputs)
            raise ValueError(f"Unknown command for {self.name}: {command}")
        except Exception as exc:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary=f"Error executing '{command}': {exc}",
                artifacts=[],
                gate_changes={},
                warnings=[str(exc)],
            )

    def _handle_draft_outline(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle draft_outline using SKILL.md section structures."""
        evidence_path = Path(inputs.get("evidence_path", "outputs/search/screened_evidence.json"))
        output_dir = Path(inputs.get("output_dir", "outputs/drafts"))
        bib_path = Path(inputs.get("bib_path", "templates/references.bib"))

        result = writer_module.draft_outline(
            evidence_path=evidence_path,
            output_dir=output_dir,
            bib_path=bib_path,
        )
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Outline drafted using CARS model structure from SKILL.md",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"outline_drafted": True},
        )

    def _handle_draft_section(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle draft_section using SKILL.md prompt structures."""
        section_name = str(inputs.get("section_name", "introduction"))
        outline_path = Path(inputs.get("outline_path", "outputs/drafts/outline.md"))
        evidence_path = Path(inputs.get("evidence_path", "outputs/search/screened_evidence.json"))
        bib_path = Path(inputs.get("bib_path", "templates/references.bib"))
        output_dir = Path(inputs.get("output_dir", "outputs/drafts"))

        result = writer_module.draft_section(
            section_name=section_name,
            outline_path=outline_path,
            evidence_path=evidence_path,
            bib_path=bib_path,
            output_dir=output_dir,
        )
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary=f"Section '{section_name}' skeleton from SKILL.md structure",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"sections_completed": True},
        )
