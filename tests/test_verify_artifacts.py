"""Tests for verify artifacts generator service."""

import json
from pathlib import Path

import yaml

from harness.services.verify_artifacts import (
    _derive_cite_key,
    _parse_bib_keys,
    generate_verify_artifacts,
)


class TestDeriveCiteKey:
    """Unit tests for _derive_cite_key."""

    def test_basic_author_year(self) -> None:
        entry = {"author": "Su, Hongjin", "year": "2024", "title": "EvoR: Evolving Retrieval"}
        assert _derive_cite_key(entry) == "su2024evor"

    def test_multi_author(self) -> None:
        entry = {
            "author": "Zhang, Fengji and Bei Chen and Yue Zhang",
            "year": "2023",
            "title": "RepoCoder: Repository-Level Code Completion",
        }
        key = _derive_cite_key(entry)
        assert key == "zhang2023repocoder"

    def test_doi_fallback(self) -> None:
        entry = {"doi": "10.1234/some-paper.2024"}
        key = _derive_cite_key(entry)
        assert "some_paper" in key

    def test_no_data(self) -> None:
        entry: dict[str, str] = {}
        assert _derive_cite_key(entry) == "unknown"


class TestParseBibKeys:
    """Unit tests for _parse_bib_keys."""

    def test_extracts_keys_and_titles(self, tmp_path: Path) -> None:
        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{su2024evor,\n"
            "  title = {EvoR: Evolving Retrieval},\n"
            "  year = {2024}\n"
            "}\n"
            "@inproceedings{zhang2023repocoder,\n"
            "  title = {RepoCoder},\n"
            "  year = {2023}\n"
            "}\n"
        )
        result = _parse_bib_keys(bib)
        assert result == {"su2024evor": "EvoR: Evolving Retrieval", "zhang2023repocoder": "RepoCoder"}

    def test_missing_file(self, tmp_path: Path) -> None:
        result = _parse_bib_keys(tmp_path / "nonexistent.bib")
        assert result == {}


class TestGenerateSearchManifest:
    """Tests for search_manifest.yaml generation."""

    def test_generates_manifest(self, tmp_path: Path) -> None:
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        (search_dir / "search_plan.json").write_text(json.dumps({
            "query": "RACG systematic review",
            "strategy": "keyword",
            "date": "2026-06-05",
            "databases": ["Semantic Scholar", "arXiv"],
            "inclusion_criteria": ["Published 2021-2025"],
        }))
        (search_dir / "screened_evidence.json").write_text(json.dumps({
            "total_raw": 14,
            "total_screened": 14,
            "min_tier": "Tier 3",
            "prisma_flow": {
                "identification": {"total_identified": 14},
                "included": {"studies_in_synthesis": 10},
            },
        }))

        output_dir = tmp_path / "verify"
        paths = generate_verify_artifacts(search_dir, tmp_path / "drafts", tmp_path / "refs.bib", output_dir)

        manifest_path = output_dir / "search_manifest.yaml"
        assert manifest_path.is_file()
        manifest = yaml.safe_load(manifest_path.read_text())
        assert manifest["query"] == "RACG systematic review"
        assert manifest["results"]["total_raw"] == 14

    def test_no_search_data(self, tmp_path: Path) -> None:
        search_dir = tmp_path / "empty_search"
        search_dir.mkdir()
        output_dir = tmp_path / "verify"
        paths = generate_verify_artifacts(search_dir, tmp_path / "drafts", tmp_path / "refs.bib", output_dir)
        # No search_plan.json → no search_manifest
        assert not (output_dir / "search_manifest.yaml").is_file()


class TestGenerateEvidenceMatrix:
    """Tests for evidence_matrix.csv generation."""

    def test_generates_csv(self, tmp_path: Path) -> None:
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        (search_dir / "search_plan.json").write_text("{}")
        (search_dir / "screened_evidence.json").write_text(json.dumps({
            "evidence": [
                {
                    "author": "Su et al.",
                    "year": "2024",
                    "title": "EvoR",
                    "doi": "10.1234/evor",
                    "scoring": {
                        "tier": "Tier 2",
                        "final_score": 3.5,
                        "venue_tier": 2.0,
                        "recency_score": 0.8,
                        "citation_score": 0.5,
                        "relevance_score": 0.6,
                        "rigor_score": 0.4,
                        "domain": "cs",
                    },
                },
            ],
        }))

        output_dir = tmp_path / "verify"
        generate_verify_artifacts(search_dir, tmp_path / "drafts", tmp_path / "refs.bib", output_dir)

        csv_path = output_dir / "evidence_matrix.csv"
        assert csv_path.is_file()
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == 2  # header + 1 row
        assert "tier" in lines[0].lower()
        assert "Tier 2" in lines[1]


class TestGenerateIncludedExcludedLedger:
    """Tests for included_excluded_ledger.yaml generation."""

    def test_splits_by_tier(self, tmp_path: Path) -> None:
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        (search_dir / "search_plan.json").write_text("{}")
        (search_dir / "screened_evidence.json").write_text(json.dumps({
            "total_raw": 3,
            "evidence": [
                {"title": "Good Paper", "author": "A", "year": "2024",
                 "scoring": {"tier": "Tier 1", "final_score": 4.0}},
                {"title": "OK Paper", "author": "B", "year": "2023",
                 "scoring": {"tier": "Tier 3", "final_score": 2.0}},
                {"title": "Bad Paper", "author": "C", "year": "2022",
                 "scoring": {"tier": "Discard", "final_score": 0.5}},
            ],
        }))

        output_dir = tmp_path / "verify"
        generate_verify_artifacts(search_dir, tmp_path / "drafts", tmp_path / "refs.bib", output_dir)

        ledger_path = output_dir / "included_excluded_ledger.yaml"
        assert ledger_path.is_file()
        ledger = yaml.safe_load(ledger_path.read_text())
        assert ledger["summary"]["total_included"] == 2
        assert ledger["summary"]["total_excluded"] == 1


class TestGenerateClaimCitationAudit:
    """Tests for claim_citation_audit.yaml generation."""

    def test_cross_references_citations(self, tmp_path: Path) -> None:
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        (search_dir / "search_plan.json").write_text("{}")

        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "introduction.md").write_text(
            "RAG is important [@chen2021humaneval, @zhang2023repocoder].\n"
            "Also [@su2024evor] shows promise.\n"
        )
        (draft_dir / "methods.md").write_text(
            "We follow [@chen2021humaneval].\n"
        )

        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{chen2021humaneval,\n"
            "  title = {Evaluating Large Language Models},\n"
            "}\n"
            "@article{zhang2023repocoder,\n"
            "  title = {RepoCoder},\n"
            "}\n"
        )

        output_dir = tmp_path / "verify"
        generate_verify_artifacts(search_dir, draft_dir, bib, output_dir)

        audit_path = output_dir / "claim_citation_audit.yaml"
        assert audit_path.is_file()
        audit = yaml.safe_load(audit_path.read_text())
        assert audit["total_unique_citations"] == 3
        assert audit["citations_in_bib"] == 2
        assert audit["citations_missing_from_bib"] == 1  # su2024evor

        # Check chen2021humaneval appears in both sections
        chen = next(e for e in audit["entries"] if e["cite_key"] == "chen2021humaneval")
        assert set(chen["sections"]) == {"introduction", "methods"}
        assert chen["occurrences"] == 2

    def test_empty_drafts(self, tmp_path: Path) -> None:
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        (search_dir / "search_plan.json").write_text("{}")
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        bib = tmp_path / "refs.bib"
        bib.write_text("")

        output_dir = tmp_path / "verify"
        generate_verify_artifacts(search_dir, draft_dir, bib, output_dir)

        audit_path = output_dir / "claim_citation_audit.yaml"
        assert audit_path.is_file()
        audit = yaml.safe_load(audit_path.read_text())
        assert audit["total_unique_citations"] == 0
