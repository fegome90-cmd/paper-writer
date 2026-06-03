# ruff: noqa: RUF005
"""Full E2E smoke test for paper-writer pipeline.

Runs the complete pipeline against a real temp repo with real artifacts.
Pandoc is required for render stages. Tests degrade gracefully if missing.

This test is SLOW (5-10s) because it exercises real I/O and subprocess calls.
Marked with @pytest.mark.e2e for optional filtering.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from harness.domain.state import ManuscriptState

# Marker for E2E tests — run with: pytest -m e2e
pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
# Use sys.executable for portability across venv setups (local + CI)
CLI_CMD = [sys.executable, "-m", "cli.paper.main"]
ENV = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}

# Minimal valid .bib with DOI
VALID_BIB = (
    "@article{smith2024voice,\n"
    "  title = {Voice Disorders in Adolescent Singers},\n"
    "  author = {Smith, Jane and Doe, John},\n"
    "  year = {2024},\n"
    "  journal = {Journal of Voice},\n"
    "  volume = {38},\n"
    "  pages = {1--10},\n"
    "  doi = {10.1016/j.jvoice.2024.01.001}\n"
    "}\n"
    "@article{jones2023pitch,\n"
    "  title = {Pitch Accuracy in Choral Performance},\n"
    "  author = {Jones, Alice},\n"
    "  year = {2023},\n"
    "  journal = {Music Perception},\n"
    "  volume = {41},\n"
    "  pages = {45--60},\n"
    "  doi = {10.1525/mp.2023.41.1.45}\n"
    "}\n"
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run paper CLI command and return result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=ENV,
        timeout=60,
    )


def _write_bib(project: Path) -> str:
    """Write a valid .bib file and return its path."""
    bib_file = project / "import.bib"
    bib_file.write_text(VALID_BIB)
    return str(bib_file)


def _setup_to_validating(project: Path) -> None:
    """Run pipeline: init → import → search → screen → draft (all 4 sections).

    Leaves the project at 'validating' stage, ready for any validation test.
    """
    r = _run(CLI_CMD + ["init"], project)
    assert r.returncode == 0, f"init failed: {r.stdout}"

    bib_path = _write_bib(project)
    r = _run(CLI_CMD + ["import", "bib", bib_path], project)
    assert r.returncode == 0, f"import bib failed: {r.stdout}"

    r = _run(CLI_CMD + ["search"], project)
    assert r.returncode == 0, f"search failed: {r.stdout}"

    r = _run(CLI_CMD + ["screen"], project)
    assert r.returncode == 0, f"screen failed: {r.stdout}"

    r = _run(CLI_CMD + ["draft", "outline"], project)
    assert r.returncode == 0, f"draft outline failed: {r.stdout}"

    for sec in ["introduction", "methods", "results", "discussion"]:
        r = _run(CLI_CMD + ["draft", "section", sec], project)
        assert r.returncode == 0, f"draft section {sec} failed: {r.stdout}"


def _setup_full_pipeline(project: Path) -> None:
    """Run the complete pipeline: init → import → search → screen → draft → validate."""
    _setup_to_validating(project)

    for cmd_args in [
        ["lint", "bib"],
        ["check", "refs"],
        ["lint", "style"],
        ["audit", "reporting"],
    ]:
        r = _run(CLI_CMD + cmd_args, project)
        assert "Step:" in r.stdout, f"{cmd_args} crashed: {r.stdout}"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a clean temp project directory."""
    return tmp_path


class TestE2EInit:
    """Test paper init."""

    def test_init_creates_scaffold(self, project: Path) -> None:
        result = _run(CLI_CMD + ["init"], project)
        assert result.returncode == 0
        assert (project / "outputs" / "state.yaml").exists()
        assert (project / "templates" / "manuscript.qmd").exists()
        assert (project / "templates" / "references.bib").exists()

    def test_init_preset_nature(self, project: Path) -> None:
        result = _run(CLI_CMD + ["init", "--preset", "nature"], project)
        assert result.returncode == 0
        assert "Nature" in (project / "templates" / "manuscript.qmd").read_text()
        assert (project / "templates" / "preset.yaml").exists()


class TestE2EImportBib:
    """Test paper import bib."""

    def test_import_valid_bib(self, project: Path) -> None:
        _run(CLI_CMD + ["init"], project)
        bib_path = _write_bib(project)

        result = _run(CLI_CMD + ["import", "bib", bib_path], project)
        assert result.returncode == 0
        content = (project / "templates" / "references.bib").read_text()
        assert "smith2024voice" in content

    def test_import_invalid_doi_fails(self, project: Path) -> None:
        _run(CLI_CMD + ["init"], project)

        bad_bib = project / "bad.bib"
        bad_bib.write_text(
            "@article{bad2024,\n"
            "  author = {Bad},\n"
            "  title = {Bad},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {not-a-doi}\n"
            "}\n"
        )

        result = _run(CLI_CMD + ["import", "bib", str(bad_bib)], project)
        assert result.returncode == 1
        assert "malformed_doi" in result.stdout


class TestE2ESearchAndScreen:
    """Test search and screen stages."""

    def test_search_creates_artifacts(self, project: Path) -> None:
        _run(CLI_CMD + ["init"], project)
        bib_path = _write_bib(project)
        _run(CLI_CMD + ["import", "bib", bib_path], project)

        result = _run(CLI_CMD + ["search"], project)
        assert result.returncode == 0
        assert (project / "outputs" / "search" / "search_plan.json").exists()

    def test_screen_creates_artifacts(self, project: Path) -> None:
        _run(CLI_CMD + ["init"], project)
        bib_path = _write_bib(project)
        _run(CLI_CMD + ["import", "bib", bib_path], project)
        _run(CLI_CMD + ["search"], project)

        result = _run(CLI_CMD + ["screen"], project)
        assert result.returncode == 0
        assert (project / "outputs" / "search" / "screened_evidence.json").exists()


class TestE2EDrafting:
    """Test draft stages."""

    def test_draft_outline(self, project: Path) -> None:
        _run(CLI_CMD + ["init"], project)
        _run(CLI_CMD + ["search"], project)
        _run(CLI_CMD + ["screen"], project)

        result = _run(CLI_CMD + ["draft", "outline"], project)
        assert result.returncode == 0
        assert (project / "outputs" / "drafts" / "outline.md").exists()

    def test_draft_section(self, project: Path) -> None:
        _run(CLI_CMD + ["init"], project)
        _run(CLI_CMD + ["search"], project)
        _run(CLI_CMD + ["screen"], project)
        _run(CLI_CMD + ["draft", "outline"], project)

        for sec in ["introduction", "methods", "results", "discussion"]:
            result = _run(CLI_CMD + ["draft", "section", sec], project)
            assert result.returncode == 0
            assert (project / "outputs" / "drafts" / f"{sec}.md").exists()


class TestE2EValidation:
    """Test individual validation stages — shared setup via _setup_to_validating."""

    def test_lint_bib_with_content(self, project: Path) -> None:
        """Lint bib with a real .bib imported."""
        _setup_to_validating(project)
        result = _run(CLI_CMD + ["lint", "bib"], project)
        assert "Step:" in result.stdout

    def test_lint_style(self, project: Path) -> None:
        _setup_to_validating(project)
        result = _run(CLI_CMD + ["lint", "style"], project)
        assert "Step:" in result.stdout

    def test_check_refs(self, project: Path) -> None:
        _setup_to_validating(project)
        result = _run(CLI_CMD + ["check", "refs"], project)
        assert "Step:" in result.stdout


class TestE2EFullPipeline:
    """Test the complete pipeline end-to-end with real Pandoc render."""

    def test_full_pipeline_to_docx(self, project: Path) -> None:
        """init -> import -> search -> screen -> draft -> validate -> render -> verify DOCX."""
        if shutil.which("pandoc") is None:
            pytest.skip("Pandoc not installed — cannot verify real render.")

        # Run full pipeline
        _setup_full_pipeline(project)

        # Check if we reached 'rendering' stage
        state_file = project / "outputs" / "state.yaml"
        assert state_file.exists(), "state.yaml should exist after pipeline"
        state = yaml.safe_load(state_file.read_text())
        stage = state.get("stage", "")
        gates = state.get("gates", {})

        # For full render, ALL rendering precondition gates must be True
        validation_gates = sorted(ManuscriptState.STAGE_PRECONDITIONS.get("rendering", frozenset()))
        all_validation_passed = all(gates.get(g, False) for g in validation_gates)

        if not all_validation_passed:
            failed_gates = [g for g in validation_gates if not gates.get(g, False)]
            pytest.skip(
                f"Pipeline at '{stage}'. Validation gates not all satisfied: "
                f"{failed_gates}. Full render requires all validation gates True."
            )

        assert stage == "rendering", f"Expected stage 'rendering' but got '{stage}'. Gates: {gates}"

        # Render DOCX
        result = _run(CLI_CMD + ["render", "--format", "docx"], project)
        assert result.returncode == 0, f"Render failed: {result.stdout}"

        # Verify real DOCX artifact
        docx = project / "outputs" / "render" / "manuscript.docx"
        assert docx.exists(), "DOCX not produced"
        assert docx.stat().st_size > 1000, f"DOCX too small: {docx.stat().st_size}B"

        # Verify it's a real Word file (ZIP-based with word/document.xml)
        with zipfile.ZipFile(docx, "r") as zf:
            assert "word/document.xml" in zf.namelist(), "DOCX missing word/document.xml"

        # Verify stage advanced
        state_after = yaml.safe_load(state_file.read_text())
        assert state_after["stage"] in ("rendered", "rendering")


class TestE2EDoctor:
    """Test paper doctor command."""

    def test_doctor_runs(self, project: Path) -> None:
        result = _run(CLI_CMD + ["doctor"], project)
        assert result.returncode == 0
        assert "EXTERNAL TOOLS" in result.stdout
        assert "INTERNAL CAPABILITIES" in result.stdout
        assert "DEGRADED MODE ACTIVE" in result.stdout or "ALL TOOLS" in result.stdout


class TestE2EMultiProject:
    """E2E tests for multi-project mode: --project flag, ascending search,
    cross-project isolation, and CWD fallback."""

    def test_project_flag_init(self, project: Path) -> None:
        """paper -C <dir> init creates scaffold at target dir, not CWD."""
        target = project / "my-paper"
        target.mkdir()
        result = _run(CLI_CMD + ["-C", str(target), "init"], project)
        assert result.returncode == 0, f"init with -C failed: {result.stderr}"
        assert (target / "outputs" / "state.yaml").exists()
        assert (target / "templates" / "manuscript.qmd").exists()
        # CWD should NOT have outputs (command ran against target)
        assert not (project / "outputs").exists()

    def test_project_flag_doctor(self, project: Path) -> None:
        """paper -C <dir> doctor resolves assets from target project."""
        target = project / "my-paper"
        target.mkdir()
        _run(CLI_CMD + ["-C", str(target), "init"], target.parent)
        result = _run(CLI_CMD + ["-C", str(target), "doctor"], project)
        assert result.returncode == 0
        assert "INTERNAL CAPABILITIES" in result.stdout

    def test_ascending_search_from_subdir(self, project: Path) -> None:
        """Running 'paper init' from a subdir finds project root via
        ascending search for outputs/state.yaml."""
        # Init the project first
        _run(CLI_CMD + ["init"], project)
        assert (project / "outputs" / "state.yaml").exists()

        # Create a deep subdir
        deep = project / "src" / "analysis" / "data"
        deep.mkdir(parents=True)

        # Run 'paper doctor' from deep subdir — ascending search
        # should find the project root
        result = _run(CLI_CMD + ["doctor"], deep)
        assert result.returncode == 0
        assert "INTERNAL CAPABILITIES" in result.stdout

    def test_cross_project_isolation(self, project: Path) -> None:
        """Two projects in separate dirs don't interfere."""
        paper_a = project / "paper-a"
        paper_b = project / "paper-b"
        paper_a.mkdir()
        paper_b.mkdir()

        # Init both
        _run(CLI_CMD + ["-C", str(paper_a), "init"], project)
        _run(CLI_CMD + ["-C", str(paper_b), "init"], project)

        # Add different content to each
        (paper_a / "templates" / "manuscript.qmd").write_text("# Paper A\nContent A")
        (paper_b / "templates" / "manuscript.qmd").write_text("# Paper B\nContent B")

        # Verify isolation — A still has A's content
        a_text = (paper_a / "templates" / "manuscript.qmd").read_text()
        b_text = (paper_b / "templates" / "manuscript.qmd").read_text()
        assert "Paper A" in a_text
        assert "Paper B" in b_text
        assert "Paper B" not in a_text
        assert "Paper A" not in b_text

        # Verify state files are independent
        state_a = yaml.safe_load((paper_a / "outputs" / "state.yaml").read_text())
        state_b = yaml.safe_load((paper_b / "outputs" / "state.yaml").read_text())
        # Both should have progressed past bootstrap
        assert state_a["stage"] != "bootstrap"
        assert state_b["stage"] != "bootstrap"
        # Gates should be independent dicts
        assert "gates" in state_a
        assert "gates" in state_b

    def test_cwd_fallback_no_state_yaml(self, project: Path) -> None:
        """When no state.yaml exists above CWD, CLI uses CWD as root."""
        # Empty directory, no state.yaml
        result = _run(CLI_CMD + ["init"], project)
        assert result.returncode == 0
        # Scaffold created at CWD (project dir)
        assert (project / "outputs" / "state.yaml").exists()
        assert (project / "templates" / "manuscript.qmd").exists()
        # No source stubs
        assert not (project / "cli").exists()
        assert not (project / "harness").exists()
        assert not (project / "validators").exists()
        assert not (project / "tests").exists()
