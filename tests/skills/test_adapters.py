"""Tests for skill adapters using real imported skill surface.

Tests verify that:
1. LiteratureSearchAdapter uses real scoring engine (deduplicate, classify_tier)
2. AcademicWriterAdapter uses section structures from SKILL.md
3. Neither skill writes outputs/state.yaml
4. The full search→screen→draft flow works with real scoring
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skills.local.adapters import AcademicWriterAdapter, LiteratureSearchAdapter


def _make_paper(
    idx: int,
    *,
    doi: str | None = None,
    pmid: str | None = None,
    title: str | None = None,
    metrics: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Create a paper dict with optional scoring metrics."""
    paper: dict[str, Any] = {
        "title": title or f"Test Paper {idx}: voice disorders study",
        "doi": doi or f"10.1000/test-{idx}",
        "pmid": pmid,
        "year": 2023 + (idx % 3),
        "authors": f"Author{idx} et al.",
    }
    if metrics:
        paper["metrics"] = metrics
    return paper


class TestLiteratureSearchAdapter:
    """Tests for LiteratureSearchAdapter using real scoring engine."""

    def test_name_property(self) -> None:
        adapter = LiteratureSearchAdapter()
        assert adapter.name == "literature-search"

    def test_search_without_papers_uses_provider(self, tmp_path: Path) -> None:
        """When no raw_papers provided, search uses PaperSearchProvider.

        In fixture mode (default), loads deterministic test data and scores it.
        Produces search_plan.json + raw_results.json + normalized_results.json.
        """
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={"query": "voice disorders", "output_dir": str(output_dir)},
            context={},
        )

        assert result.status == "pass"
        # Provider generates scored papers
        assert len(result.artifacts) >= 2  # search_plan + raw_results minimum
        artifact_names = {Path(a).name for a in result.artifacts}
        assert "search_plan.json" in artifact_names
        assert "raw_results.json" in artifact_names
        # Normalized results also written
        assert (output_dir / "normalized_results.json").is_file()

    def test_search_extracts_filter_params(self, tmp_path: Path) -> None:
        """Filter params from inputs are forwarded to provider.search().

        Verifies the adapter extracts year_min, study_types etc. from inputs
        and passes them as kwargs to the provider's search method.
        """
        from unittest.mock import patch

        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        captured_kwargs: dict[str, Any] = {}

        from harness.ports.paper_search_provider import (
            PaperSearchProvider,
            SearchProvenance,
            SearchProviderResult,
        )

        class SpyProvider(PaperSearchProvider):
            def search(
                self,
                query: str,
                *,
                sources: list[str] | None = None,
                limit: int = 20,
                **filters: Any,
            ) -> SearchProviderResult:
                captured_kwargs.update(filters)
                return SearchProviderResult(
                    papers=[],
                    raw_payload={"results": []},
                    provenance=SearchProvenance(
                        provider="consensus",
                        query=query,
                        retrieved_at="2026-01-01T00:00:00Z",
                        tool_name="test",
                        sources=["consensus"],
                    ),
                )

        with patch(
            "harness.ports.paper_search_provider.create_search_provider", return_value=SpyProvider()
        ):
            adapter.execute(
                command="search",
                inputs={
                    "query": "machine learning",
                    "output_dir": str(output_dir),
                    "year_min": 2020,
                    "year_max": 2025,
                    "study_types": ["systematic review"],
                    "exclude_preprints": True,
                    # Non-filter inputs should NOT appear in kwargs
                    "limit": 10,
                    "weights_phase": "balanced",
                },
                context={},
            )

            assert captured_kwargs.get("year_min") == 2020
            assert captured_kwargs.get("year_max") == 2025
            assert captured_kwargs.get("study_types") == ["systematic review"]
            assert captured_kwargs.get("exclude_preprints") is True
            # limit and weights_phase are NOT filters
            assert "limit" not in captured_kwargs
            assert "weights_phase" not in captured_kwargs

    def test_search_with_papers_applies_real_scoring(self, tmp_path: Path) -> None:
        """When raw_papers provided, search deduplicates and scores them."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        papers = [
            _make_paper(
                1,
                metrics={
                    "population_score": 8,
                    "intervention_score": 7,
                    "outcome_score": 6,
                    "evidence_score": 4.5,
                    "sample_score": 0.5,
                    "journal_score": 2,
                    "citations_score": 0.1,
                    "coi_penalty": 0,
                    "context_score": 6,
                },
            ),
            _make_paper(
                2,
                doi="10.1000/test-1",
                metrics={
                    "population_score": 5,
                    "intervention_score": 4,
                    "outcome_score": 3,
                    "evidence_score": 1.5,
                    "sample_score": 0.25,
                    "journal_score": 1,
                    "citations_score": 0.1,
                    "coi_penalty": 0,
                    "context_score": 4,
                },
            ),
        ]

        result = adapter.execute(
            command="search",
            inputs={
                "query": "voice disorders",
                "output_dir": str(output_dir),
                "raw_papers": papers,
            },
            context={},
        )

        assert result.status == "pass"
        assert len(result.artifacts) == 2  # plan + results

        results_path = Path(result.artifacts[1])
        assert results_path.name == "raw_results.json"
        results = json.loads(results_path.read_text(encoding="utf-8"))

        # Dedup should have removed one (same DOI as paper 1)
        assert results["total_input"] == 2
        assert results["total_after_dedup"] == 1
        assert len(results["dedup_log"]) == 1

        # Scored paper should have tier from real classify_tier
        paper = results["papers"][0]
        assert "scoring" in paper
        assert "tier" in paper["scoring"]
        assert paper["scoring"]["tier"] in ("Tier 1", "Tier 2", "Tier 3", "Discard")

    def test_screen_filters_by_tier(self, tmp_path: Path) -> None:
        """Screen uses real tier classification to filter papers."""
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "outputs" / "search"
        search_dir.mkdir(parents=True)

        raw_data = {
            "query": "voice disorders",
            "papers": [
                {
                    "title": "Tier 1 Paper",
                    "doi": "10.1/a",
                    "scoring": {"tier": "Tier 1", "final_score": 8.5},
                },
                {
                    "title": "Tier 3 Paper",
                    "doi": "10.1/b",
                    "scoring": {"tier": "Tier 3", "final_score": 5.2},
                },
                {
                    "title": "Discard Paper",
                    "doi": "10.1/c",
                    "scoring": {"tier": "Discard", "final_score": 3.1},
                },
            ],
        }
        (search_dir / "raw_results.json").write_text(json.dumps(raw_data), encoding="utf-8")

        result = adapter.execute(
            command="screen",
            inputs={
                "search_dir": str(search_dir),
                "output_dir": str(search_dir),
                "min_tier": "Tier 3",
            },
            context={},
        )

        assert result.status == "pass"
        evidence_path = Path(result.artifacts[0])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        # Should include Tier 1 and Tier 3, exclude Discard
        assert evidence["total_screened"] == 2
        titles = [p["title"] for p in evidence["evidence"]]
        assert "Discard Paper" not in titles

    def test_screen_strict_tier_excludes_lower(self, tmp_path: Path) -> None:
        """Screen with min_tier=Tier 1 excludes Tier 2 and below."""
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "outputs" / "search"
        search_dir.mkdir(parents=True)

        raw_data = {
            "query": "test",
            "papers": [
                {"title": "T1", "doi": "10.1/a", "scoring": {"tier": "Tier 1"}},
                {"title": "T2", "doi": "10.1/b", "scoring": {"tier": "Tier 2"}},
            ],
        }
        (search_dir / "raw_results.json").write_text(json.dumps(raw_data), encoding="utf-8")

        result = adapter.execute(
            command="screen",
            inputs={
                "search_dir": str(search_dir),
                "output_dir": str(search_dir),
                "min_tier": "Tier 1",
            },
            context={},
        )

        evidence = json.loads(Path(result.artifacts[0]).read_text(encoding="utf-8"))
        assert evidence["total_screened"] == 1
        assert evidence["evidence"][0]["title"] == "T1"

    def test_unknown_command_returns_fail(self) -> None:
        adapter = LiteratureSearchAdapter()
        result = adapter.execute(command="bogus", inputs={}, context={})
        assert result.status == "fail"
        assert "bogus" in result.summary


class TestPrismaFlow:
    """Test PRISMA 2020 flow data in screen output."""

    def _make_raw(self, papers: list[dict[str, object]]) -> dict[str, object]:
        return {
            "query": "test",
            "total_input": len(papers),
            "total_after_dedup": len(papers),
            "papers": papers,
        }

    def test_prisma_flow_present(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        raw = self._make_raw(
            [
                {"title": "Good", "doi": "10.1/a", "source": "seed", "scoring": {"tier": "Tier 2"}},
            ]
        )
        (search_dir / "raw_results.json").write_text(json.dumps(raw))

        result = adapter.execute(
            command="screen",
            inputs={"search_dir": str(search_dir), "output_dir": str(search_dir)},
            context={},
        )
        evidence = json.loads(Path(result.artifacts[0]).read_text())
        assert "prisma_flow" in evidence

    def test_prisma_four_stages(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        raw = self._make_raw(
            [
                {"title": "S1", "doi": "10.1/a", "source": "seed", "scoring": {"tier": "Tier 2"}},
                {
                    "title": "B1",
                    "doi": "10.1/b",
                    "source": "backward_chaining",
                    "scoring": {"tier": "Tier 1"},
                },
                {
                    "title": "F1",
                    "doi": "10.1/c",
                    "source": "forward_chaining",
                    "scoring": {"tier": "Discard"},
                },
            ]
        )
        (search_dir / "raw_results.json").write_text(json.dumps(raw))

        result = adapter.execute(
            command="screen",
            inputs={"search_dir": str(search_dir), "output_dir": str(search_dir)},
            context={},
        )
        evidence = json.loads(Path(result.artifacts[0]).read_text())
        flow = evidence["prisma_flow"]

        # All 4 stages present
        assert "identification" in flow
        assert "screening" in flow
        assert "eligibility" in flow
        assert "included" in flow

    def test_prisma_source_counts(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        raw = self._make_raw(
            [
                {"title": "S1", "doi": "10.1/a", "source": "seed", "scoring": {"tier": "Tier 2"}},
                {
                    "title": "B1",
                    "doi": "10.1/b",
                    "source": "backward_chaining",
                    "scoring": {"tier": "Tier 2"},
                },
                {
                    "title": "F1",
                    "doi": "10.1/c",
                    "source": "forward_chaining",
                    "scoring": {"tier": "Tier 2"},
                },
            ]
        )
        (search_dir / "raw_results.json").write_text(json.dumps(raw))

        result = adapter.execute(
            command="screen",
            inputs={"search_dir": str(search_dir), "output_dir": str(search_dir)},
            context={},
        )
        evidence = json.loads(Path(result.artifacts[0]).read_text())
        ident = evidence["prisma_flow"]["identification"]

        assert ident["seed_papers"] == 1
        assert ident["database_results"] == 1  # backward_chaining
        assert ident["other_sources"] == 1  # forward_chaining
        assert ident["total_identified"] == 3

    def test_prisma_exclusion_reasons(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        raw = self._make_raw(
            [
                {"title": "Good", "doi": "10.1/a", "source": "seed", "scoring": {"tier": "Tier 2"}},
                {
                    "title": "Bad",
                    "doi": "10.1/b",
                    "source": "backward_chaining",
                    "scoring": {"tier": "Discard"},
                },
            ]
        )
        (search_dir / "raw_results.json").write_text(json.dumps(raw))

        result = adapter.execute(
            command="screen",
            inputs={"search_dir": str(search_dir), "output_dir": str(search_dir)},
            context={},
        )
        evidence = json.loads(Path(result.artifacts[0]).read_text())
        scr = evidence["prisma_flow"]["screening"]

        assert scr["records_screened"] == 2
        assert scr["records_excluded"] == 1
        assert "tier_discard" in scr["exclusion_reasons"]

    def test_prisma_included_count(self, tmp_path: Path) -> None:
        adapter = LiteratureSearchAdapter()
        search_dir = tmp_path / "search"
        search_dir.mkdir(parents=True)

        raw = self._make_raw(
            [
                {"title": "T1", "doi": "10.1/a", "source": "seed", "scoring": {"tier": "Tier 1"}},
                {
                    "title": "T2",
                    "doi": "10.1/b",
                    "source": "backward_chaining",
                    "scoring": {"tier": "Tier 2"},
                },
                {
                    "title": "Discard",
                    "doi": "10.1/c",
                    "source": "forward_chaining",
                    "scoring": {"tier": "Discard"},
                },
            ]
        )
        (search_dir / "raw_results.json").write_text(json.dumps(raw))

        result = adapter.execute(
            command="screen",
            inputs={"search_dir": str(search_dir), "output_dir": str(search_dir)},
            context={},
        )
        evidence = json.loads(Path(result.artifacts[0]).read_text())
        inc = evidence["prisma_flow"]["included"]

        assert inc["studies_in_synthesis"] == 2  # T1 + T2

    def test_skills_do_not_write_state_yaml(self, tmp_path: Path) -> None:
        """Verify that skills never create outputs/state.yaml."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        adapter.execute(
            command="search",
            inputs={
                "query": "test",
                "output_dir": str(output_dir),
                "raw_papers": [_make_paper(1)],
            },
            context={},
        )

        # state.yaml must NOT exist anywhere in outputs
        state_files = list(tmp_path.rglob("state.yaml"))
        assert len(state_files) == 0, "Skills must not write state.yaml"


class TestBugHuntFixes:
    """Tests for bugs found by real-world bug hunt (BH-1 through BH-4)."""

    def test_bh1_warning_on_filters_with_non_consensus_provider(self, tmp_path: Path) -> None:
        """BH-1: Adapter warns when filter params are passed but provider is not Consensus."""
        from unittest.mock import patch

        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        from harness.ports.paper_search_provider import (
            FixturePaperSearchProvider,
        )

        captured_warnings: list[str] = []

        import logging

        logger = logging.getLogger("skills.local.adapters")

        class WarningHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured_warnings.append(record.getMessage())

        handler = WarningHandler()
        logger.addHandler(handler)

        try:
            with patch(
                "harness.ports.paper_search_provider.create_search_provider",
                return_value=FixturePaperSearchProvider(),
            ):
                adapter.execute(
                    command="search",
                    inputs={
                        "query": "test",
                        "output_dir": str(output_dir),
                        "year_min": 2020,
                        "exclude_preprints": True,
                    },
                    context={},
                )

            assert len(captured_warnings) == 1
            assert "not supported by FixturePaperSearchProvider" in captured_warnings[0]
            assert "year_min" in captured_warnings[0]
        finally:
            logger.removeHandler(handler)

    def test_bh2_year_min_gt_max_fails(self, tmp_path: Path) -> None:
        """BH-2: year_min > year_max returns failure."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={
                "query": "test",
                "output_dir": str(output_dir),
                "year_min": 2025,
                "year_max": 2020,
            },
            context={},
        )

        assert result.status == "fail"
        assert "year_min" in result.summary

    def test_bh2_sjr_max_out_of_range_fails(self, tmp_path: Path) -> None:
        """BH-2: sjr_max outside 1-4 returns failure."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={
                "query": "test",
                "output_dir": str(output_dir),
                "sjr_max": 5,
            },
            context={},
        )

        assert result.status == "fail"
        assert "sjr_max" in result.summary

    def test_bh2_duration_min_gt_max_fails(self, tmp_path: Path) -> None:
        """BH-2: duration_min > duration_max returns failure."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={
                "query": "test",
                "output_dir": str(output_dir),
                "duration_min": 365,
                "duration_max": 30,
            },
            context={},
        )

        assert result.status == "fail"
        assert "duration_min" in result.summary

    def test_bh3_empty_query_fails(self, tmp_path: Path) -> None:
        """BH-3: Empty query string returns failure."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={
                "query": "",
                "output_dir": str(output_dir),
            },
            context={},
        )

        assert result.status == "fail"
        assert "Empty query" in result.summary

    def test_bh3_whitespace_query_fails(self, tmp_path: Path) -> None:
        """BH-3: Whitespace-only query returns failure."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={
                "query": "   ",
                "output_dir": str(output_dir),
            },
            context={},
        )

        assert result.status == "fail"
        assert "Empty query" in result.summary

    def test_bh4_nonexistent_raw_papers_fails(self, tmp_path: Path) -> None:
        """BH-4: Non-existent raw_papers file returns clear error."""
        adapter = LiteratureSearchAdapter()
        output_dir = tmp_path / "outputs" / "search"

        result = adapter.execute(
            command="search",
            inputs={
                "query": "test",
                "output_dir": str(output_dir),
                "raw_papers": "/tmp/doesnotexist12345.json",
            },
            context={},
        )

        assert result.status == "fail"
        assert "not found" in result.summary.lower()


class TestAcademicWriterAdapter:
    """Tests for AcademicWriterAdapter using SKILL.md structures."""

    def test_name_property(self) -> None:
        adapter = AcademicWriterAdapter()
        assert adapter.name == "academic-writer"

    def test_draft_outline_uses_cars_model(self, tmp_path: Path) -> None:
        """Outline follows CARS model structure from SKILL.md."""
        adapter = AcademicWriterAdapter()
        drafts_dir = tmp_path / "outputs" / "drafts"
        search_dir = tmp_path / "outputs" / "search"

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

        bib_path = tmp_path / "templates" / "references.bib"
        bib_path.parent.mkdir(parents=True)
        bib_path.write_text(
            "@article{smith2023voice,\n  title = {Voice},\n}\n",
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
        outline = Path(result.artifacts[0]).read_text(encoding="utf-8")
        # CARS model structure from SKILL.md
        assert "CARS" in outline
        assert "Introduction" in outline
        assert "Methods" in outline
        assert "Results" in outline
        assert "Discussion" in outline
        # Bib key from references.bib
        assert "smith2023voice" in outline

    def test_draft_section_uses_skill_md_structure(self, tmp_path: Path) -> None:
        """Sections use model from SKILL.md (CARS, CONSORT, etc.)."""
        adapter = AcademicWriterAdapter()
        drafts_dir = tmp_path / "outputs" / "drafts"
        search_dir = tmp_path / "outputs" / "search"

        search_dir.mkdir(parents=True)
        evidence = {
            "query": "voice disorders",
            "total_raw": 1,
            "total_screened": 1,
            "evidence": [
                {
                    "title": "Paper A",
                    "doi": "10.1/a",
                    "year": 2023,
                    "authors": "Smith J",
                    "scoring": {"tier": "Tier 1", "final_score": 8.5},
                },
            ],
        }
        (search_dir / "screened_evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

        drafts_dir.mkdir(parents=True)
        (drafts_dir / "outline.md").write_text("# Outline\n", encoding="utf-8")

        bib_path = tmp_path / "templates" / "references.bib"
        bib_path.parent.mkdir(parents=True)
        bib_path.write_text("", encoding="utf-8")

        result = adapter.execute(
            command="draft_section",
            inputs={
                "section_name": "results",
                "outline_path": str(drafts_dir / "outline.md"),
                "evidence_path": str(search_dir / "screened_evidence.json"),
                "bib_path": str(bib_path),
                "output_dir": str(drafts_dir),
            },
            context={},
        )

        assert result.status == "pass"
        content = Path(result.artifacts[0]).read_text(encoding="utf-8")
        # Results section should reference APA 7th reporting model
        assert "APA_7th_reporting" in content
        # Should have subsections from SKILL.md structure
        assert "Descriptive statistics" in content
        # Should list evidence with tier from real scoring
        assert "Tier 1" in content
        assert "Paper A" in content

    def test_unknown_command_returns_fail(self) -> None:
        adapter = AcademicWriterAdapter()
        result = adapter.execute(command="bogus", inputs={}, context={})
        assert result.status == "fail"
        assert "bogus" in result.summary


class TestManifestDrivenDrafting:
    """Tests proving drafting.py reads from manifest, not hardcoded data."""

    def test_manifest_loads_from_file(self) -> None:
        """Manifest is a real file on disk, not generated in code."""
        from skills.imported.academic_writer.drafting import load_manifest

        manifest = load_manifest()
        assert "sections" in manifest
        assert "_provenance" in manifest
        assert manifest["_provenance"]["source_version"] == "1.2.0"

    def test_manifest_has_all_7_sections(self) -> None:
        """All 7 sections from SKILL.md are in the manifest."""
        from skills.imported.academic_writer.drafting import load_manifest

        manifest = load_manifest()
        sections = manifest["sections"]
        expected = [
            "abstract",
            "introduction",
            "literature_review",
            "methods",
            "results",
            "discussion",
            "conclusion",
        ]
        for name in expected:
            assert name in sections, f"Missing section: {name}"

    def test_manifest_subsections_match_skill_md(self) -> None:
        """CARS model steps from SKILL.md are in the manifest."""
        from skills.imported.academic_writer.drafting import load_manifest

        manifest = load_manifest()
        intro = manifest["sections"]["introduction"]
        assert intro["model"] == "CARS"
        # CARS steps from SKILL.md: Establish territory, Identify niche, Occupy niche
        steps = intro.get("model_steps", [])
        assert any("Establish territory" in s for s in steps)
        assert any("Identify niche" in s for s in steps)
        assert any("Occupy niche" in s for s in steps)

    def test_manifest_methods_has_consort(self) -> None:
        """Methods section references CONSORT/PRISMA from SKILL.md."""
        from skills.imported.academic_writer.drafting import load_manifest

        manifest = load_manifest()
        methods = manifest["sections"]["methods"]
        assert "CONSORT" in methods["model"]

    def test_draft_section_reads_manifest_at_runtime(self, tmp_path: Path) -> None:
        """draft_section produces content that references manifest provenance."""
        from skills.imported.academic_writer.drafting import draft_section

        search_dir = tmp_path / "outputs" / "search"
        drafts_dir = tmp_path / "outputs" / "drafts"
        search_dir.mkdir(parents=True)
        drafts_dir.mkdir(parents=True)

        evidence = {
            "query": "test",
            "total_raw": 0,
            "total_screened": 0,
            "evidence": [],
        }
        (search_dir / "screened_evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
        (drafts_dir / "outline.md").write_text("# Outline\n", encoding="utf-8")
        bib_path = tmp_path / "ref.bib"
        bib_path.write_text("", encoding="utf-8")

        result = draft_section(
            section_name="introduction",
            outline_path=drafts_dir / "outline.md",
            evidence_path=search_dir / "screened_evidence.json",
            bib_path=bib_path,
            output_dir=drafts_dir,
        )

        content = Path(result["artifacts"][0]).read_text(encoding="utf-8")
        # Must reference manifest provenance
        assert "sections_manifest.json" in content
        assert "SKILL.md" in content
        # Must use model from manifest (CARS for introduction)
        assert "CARS" in content

    def test_no_hardcoded_sections_in_drafting_module(self) -> None:
        """Verify drafting.py has no _SECTION_STRUCTURES or similar hardcoded dict."""
        import inspect

        from skills.imported.academic_writer import drafting

        source = inspect.getsource(drafting)
        assert "_SECTION_STRUCTURES" not in source, (
            "drafting.py must not contain hardcoded _SECTION_STRUCTURES"
        )
        assert "_SECTION_TEMPLATES" not in source, (
            "drafting.py must not contain hardcoded _SECTION_TEMPLATES"
        )


class TestPapersToBibtex:
    """Test papers_to_bibtex conversion."""

    def test_basic_article(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        papers = [
            {
                "title": "Test Paper",
                "year": 2023,
                "doi": "10.1/test",
                "authors": "Smith, J. and Doe, A.",
                "venue": "Nature",
            },
        ]
        result = papers_to_bibtex(papers)
        assert "@article" in result
        assert "Test Paper" in result
        assert "Smith, J." in result
        assert "10.1/test" in result
        assert "2023" in result
        assert "Nature" in result

    def test_conference_detection(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        papers = [
            {
                "title": "Test NeurIPS Paper",
                "year": 2023,
                "authors": "Author, A.",
                "venue": "NeurIPS",
            },
        ]
        result = papers_to_bibtex(papers)
        assert "@inproceedings" in result
        assert "booktitle" in result

    def test_key_dedup(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        papers = [
            {"title": "Same Title", "year": 2023, "authors": "Author, A."},
            {"title": "Same Title", "year": 2023, "authors": "Author, A."},
        ]
        result = papers_to_bibtex(papers)
        import re

        keys = re.findall(r"@\w+\{([^,]+),", result)
        assert len(keys) == 2
        assert keys[0] != keys[1]

    def test_missing_fields_graceful(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        papers = [
            {"title": "Minimal Paper", "year": 2023},
        ]
        result = papers_to_bibtex(papers)
        assert "@article" in result
        assert "Minimal Paper" in result
        assert "author" not in result

    def test_empty_papers(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        assert papers_to_bibtex([]) == ""

    def test_skip_no_title(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        papers = [{"year": 2023}]
        result = papers_to_bibtex(papers)
        assert result == ""

    def test_arxiv_id_included(self) -> None:
        from skills.imported.literature_search.search import papers_to_bibtex

        papers = [
            {"title": "ArXiv Paper", "year": 2023, "arxiv_id": "2301.00001"},
        ]
        result = papers_to_bibtex(papers)
        assert "2301.00001" in result
        assert "eprint" in result
