"""Skill adapters bridging imported skills into the harness port.

Each adapter accepts the normalized SkillAdapter contract and translates
between the orchestrator's request format and the skill's internal API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.ports.skill_adapter import SkillAdapter, SkillResult
from skills.imported.academic_writer.drafting import AcademicWriterSkill
from skills.imported.literature_search.search import LiteratureSearchSkill


class LiteratureSearchAdapter(SkillAdapter):
    """Bridges literature-search skill to the harness."""

    def __init__(self) -> None:
        self._skill = LiteratureSearchSkill()

    @property
    def name(self) -> str:
        return "literature-search"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        """Route command to the appropriate skill method.

        Supported commands: 'search', 'screen'.
        """
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
        """Handle the 'search' command."""
        query = str(inputs.get("query", ""))
        output_dir = Path(inputs.get("output_dir", "outputs/search"))
        result = self._skill.search(query=query, output_dir=output_dir)
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Search artifacts created successfully",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"search_completed": True},
        )

    def _handle_screen(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle the 'screen' command."""
        search_dir = Path(inputs.get("search_dir", "outputs/search"))
        output_dir = Path(inputs.get("output_dir", "outputs/search"))
        result = self._skill.screen(search_dir=search_dir, output_dir=output_dir)
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Screening completed, evidence set created",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"screened_evidence": True},
        )


class AcademicWriterAdapter(SkillAdapter):
    """Bridges academic-writer skill to the harness."""

    def __init__(self) -> None:
        self._skill = AcademicWriterSkill()

    @property
    def name(self) -> str:
        return "academic-writer"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        """Route command to the appropriate skill method.

        Supported commands: 'draft_outline', 'draft_section'.
        """
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
        """Handle the 'draft_outline' command."""
        evidence_path = Path(inputs.get("evidence_path", "outputs/search/screened_evidence.json"))
        output_dir = Path(inputs.get("output_dir", "outputs/drafts"))
        bib_path = Path(inputs.get("bib_path", "templates/references.bib"))
        result = self._skill.draft_outline(
            evidence_path=evidence_path,
            output_dir=output_dir,
            bib_path=bib_path,
        )
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary="Outline drafted from evidence",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"outline_drafted": True},
        )

    def _handle_draft_section(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle the 'draft_section' command."""
        section_name = str(inputs.get("section_name", "introduction"))
        outline_path = Path(inputs.get("outline_path", "outputs/drafts/outline.md"))
        evidence_path = Path(inputs.get("evidence_path", "outputs/search/screened_evidence.json"))
        bib_path = Path(inputs.get("bib_path", "templates/references.bib"))
        output_dir = Path(inputs.get("output_dir", "outputs/drafts"))
        result = self._skill.draft_section(
            section_name=section_name,
            outline_path=outline_path,
            evidence_path=evidence_path,
            bib_path=bib_path,
            output_dir=output_dir,
        )
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary=f"Section '{section_name}' drafted",
            artifacts=[str(a) for a in result["artifacts"]],
            gate_changes={"sections_completed": True},
        )
