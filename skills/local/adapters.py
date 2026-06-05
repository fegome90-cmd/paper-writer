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
            if command == "chain":
                return self._handle_chain(inputs)
            if command == "export_bib":
                return self._handle_export_bib(inputs)
            raise ValueError(f"Unknown command for {self.name}: {command}")
        except (ValueError, FileNotFoundError, json.JSONDecodeError, TypeError, KeyError) as exc:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary=f"Error executing '{command}': {exc}",
                artifacts=[],
                gate_changes={},
                warnings=[str(exc)],
            )

    def _handle_search(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle the 'search' command using real scoring engine.

        When raw_papers is provided, score them directly (backward compat).
        When raw_papers is None, use PaperSearchProvider to fetch papers
        from fixture or MCP based on PAPER_SEARCH_PROVIDER env var.
        """
        query = str(inputs.get("query", ""))
        output_dir = Path(inputs.get("output_dir", "outputs/search"))
        raw_papers = inputs.get("raw_papers")
        weights_phase = str(inputs.get("weights_phase", "balanced"))

        # If raw_papers is a string, try JSON parse first, then file path
        if isinstance(raw_papers, str):
            try:
                raw_papers = json.loads(raw_papers)
            except (json.JSONDecodeError, ValueError):
                raw_papers = json.loads(Path(raw_papers).read_text(encoding="utf-8"))

        # If no raw_papers provided, fetch from provider
        if raw_papers is None:
            from harness.ports.paper_search_provider import create_search_provider

            provider = create_search_provider()
            provider_result = provider.search(
                query=query,
                limit=int(inputs.get("limit", 20)),
            )

            # Write raw_results.json (provider output as-is)
            raw_payload = {
                **provider_result.raw_payload,
                "provenance": provider_result.provenance.to_dict(),
            }
            raw_path = output_dir / "raw_results.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                json.dumps(raw_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Write normalized_results.json (paper-writer format)
            normalized_payload = {
                "provenance": provider_result.provenance.to_dict(),
                "papers": [p.to_dict() for p in provider_result.papers],
            }
            norm_path = output_dir / "normalized_results.json"
            norm_path.write_text(
                json.dumps(normalized_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Convert normalized papers to raw_papers for scoring pipeline
            raw_papers = [p.to_dict() for p in provider_result.papers]

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

    def _handle_chain(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle the 'chain' command — expand corpus via S2 citation chaining.

        Reads scored papers from raw_results.json, runs iterative_search(),
        merges expanded results, re-scores, and writes updated raw_results.json.
        """
        from skills.imported.literature_search import chaining

        search_dir = Path(inputs.get("search_dir", "outputs/search"))
        output_dir = Path(inputs.get("output_dir", str(search_dir)))
        query = str(inputs.get("query", ""))
        max_rounds = int(inputs.get("max_rounds", 2))
        max_papers = int(inputs.get("max_papers", 80))
        relevance_threshold = float(inputs.get("relevance_threshold", 0.15))
        cache_dir = inputs.get("cache_dir")

        # 1. Load scored papers from raw_results.json (seeds for chaining)
        raw_results_path = search_dir / "raw_results.json"
        if not raw_results_path.exists():
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary="No raw_results.json found — run 'search' first",
                artifacts=[],
                gate_changes={},
                warnings=["raw_results.json not found"],
            )

        raw_data = json.loads(raw_results_path.read_text(encoding="utf-8"))
        seed_papers = raw_data.get("papers", [])
        if not seed_papers:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary="No scored papers in raw_results.json — nothing to chain from",
                artifacts=[],
                gate_changes={},
                warnings=["empty papers list"],
            )

        # 2. Run chaining
        chain_cache = Path(cache_dir) if cache_dir else None
        chain_result = chaining.iterative_search(
            seed_papers=seed_papers,
            query=query or raw_data.get("query", ""),
            max_rounds=max_rounds,
            max_papers=max_papers,
            relevance_threshold=relevance_threshold,
            cache_dir=chain_cache,
        )

        # 3. Re-score expanded corpus through the full search pipeline
        expanded_papers = chain_result["papers"]
        result = search_module.search(
            query=query or raw_data.get("query", ""),
            output_dir=output_dir,
            raw_papers=expanded_papers,
            weights_phase=str(inputs.get("weights_phase", "balanced")),
        )

        # 4. Write chaining provenance
        provenance_path = output_dir / "chain_provenance.json"
        provenance_path.write_text(
            json.dumps(
                {
                    "stats": chain_result["stats"],
                    "total_unique": chain_result["total_unique"],
                    "provenance": chain_result["provenance"],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        artifacts = [str(p) for p in result.get("artifacts", [])]
        artifacts.append(str(provenance_path))

        return SkillResult(
            adapter=self.name,
            status="pass",
            summary=(
                f"Chaining complete: {chain_result['total_unique']} papers "
                f"in {chain_result['stats']['rounds_completed']} rounds, "
                f"{chain_result['stats']['total_api_calls']} API calls"
            ),
            artifacts=artifacts,
            gate_changes={"search_completed": True, "chaining_completed": True},
        )

    def _handle_export_bib(self, inputs: dict[str, Any]) -> SkillResult:
        """Export screened papers to BibTeX format.

        Reads screened_evidence.json, converts each paper to a BibTeX entry,
        and writes to references.bib.
        """
        search_dir = Path(inputs.get("search_dir", "outputs/search"))
        bib_path = Path(inputs.get("bib_path", "templates/references.bib"))

        evidence_path = search_dir / "screened_evidence.json"
        if not evidence_path.exists():
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary="No screened_evidence.json found — run 'screen' first",
                artifacts=[],
                gate_changes={},
                warnings=["screened_evidence.json not found"],
            )

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        papers = evidence.get("evidence", [])
        if not papers:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary="No screened papers to export",
                artifacts=[],
                gate_changes={},
                warnings=["empty evidence list"],
            )

        bibtex_str = search_module.papers_to_bibtex(papers)

        # Ensure parent directory exists
        bib_path.parent.mkdir(parents=True, exist_ok=True)
        bib_path.write_text(bibtex_str, encoding="utf-8")

        entry_count = bibtex_str.count("@")
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary=f"Exported {entry_count} BibTeX entries to {bib_path}",
            artifacts=[str(bib_path)],
            gate_changes={"bib_exported": True},
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
            if command == "draft_all":
                return self._handle_draft_all(inputs)
            raise ValueError(f"Unknown command for {self.name}: {command}")
        except (ValueError, FileNotFoundError, json.JSONDecodeError, TypeError, KeyError) as exc:
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

    def _handle_draft_all(self, inputs: dict[str, Any]) -> SkillResult:
        """Handle draft_all: generate all 7 sections with cross-section context."""
        outline_path = Path(inputs.get("outline_path", "outputs/drafts/outline.md"))
        evidence_path = Path(inputs.get("evidence_path", "outputs/search/screened_evidence.json"))
        bib_path = Path(inputs.get("bib_path", "templates/references.bib"))
        output_dir = Path(inputs.get("output_dir", "outputs/drafts"))

        result = writer_module.draft_all(
            outline_path=outline_path,
            evidence_path=evidence_path,
            bib_path=bib_path,
            output_dir=output_dir,
        )
        sections = result.get("sections", {})
        order = result.get("generation_order", [])
        return SkillResult(
            adapter=self.name,
            status="pass",
            summary=f"Drafted {len(sections)} sections in order: {', '.join(order)}",
            artifacts=[str(a) for a in result.get("artifacts", [])],
            gate_changes={"sections_completed": True},
        )


class CitationVerifyAdapter(SkillAdapter):
    """Adapter for citation verification skill integration."""

    @property
    def name(self) -> str:
        return "citation_verify"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        from parsers.manuscript import ManuscriptParser
        from validators.citation_verify import CitationVerifyValidator

        try:
            manuscript_path = inputs["file"]
            offline = inputs.get("offline", False)
            validator = CitationVerifyValidator(offline=offline)
            manuscript = ManuscriptParser().parse(Path(manuscript_path))
            findings = validator.validate(manuscript)
            return SkillResult(
                adapter=self.name,
                status="pass" if not findings else "warn",
                summary=f"Citation verification: {len(findings)} findings",
                artifacts=[manuscript_path],
                gate_changes={"citation_verified": len(findings) == 0},
            )
        except Exception as exc:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary=f"Citation verification failed: {exc}",
                artifacts=[],
                gate_changes={},
                warnings=[str(exc)],
            )


class EthicsAdapter(SkillAdapter):
    """Adapter for ethics check skill integration."""

    @property
    def name(self) -> str:
        return "ethics"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        from parsers.manuscript import ManuscriptParser
        from validators.ethics import EthicsValidator

        try:
            manuscript_path = inputs["file"]
            validator = EthicsValidator()
            manuscript = ManuscriptParser().parse(Path(manuscript_path))
            findings = validator.validate(manuscript)
            return SkillResult(
                adapter=self.name,
                status="pass" if not findings else "warn",
                summary=f"Ethics check: {len(findings)} findings",
                artifacts=[manuscript_path],
                gate_changes={"ethics_passed": len(findings) == 0},
            )
        except Exception as exc:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary=f"Ethics check failed: {exc}",
                artifacts=[],
                gate_changes={},
                warnings=[str(exc)],
            )


class WritingQualityAdapter(SkillAdapter):
    """Adapter for writing quality skill integration."""

    @property
    def name(self) -> str:
        return "writing_quality"

    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        from parsers.manuscript import ManuscriptParser
        from validators.writing_quality import WritingQualityValidator

        try:
            manuscript_path = inputs["file"]
            whitelist = set(context.get("whitelist", set()))
            validator = WritingQualityValidator(whitelist=whitelist)
            manuscript = ManuscriptParser().parse(Path(manuscript_path))
            findings = validator.validate(manuscript)
            return SkillResult(
                adapter=self.name,
                status="pass" if not findings else "warn",
                summary=f"Writing quality: {len(findings)} findings",
                artifacts=[manuscript_path],
                gate_changes={},
            )
        except Exception as exc:
            return SkillResult(
                adapter=self.name,
                status="fail",
                summary=f"Writing quality check failed: {exc}",
                artifacts=[],
                gate_changes={},
                warnings=[str(exc)],
            )
