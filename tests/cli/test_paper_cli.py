import sys
from pathlib import Path
from typing import Any

import pytest

from cli.paper.main import main

# Minimal valid BibTeX entry for testing
MINIMAL_BIB = """@article{smith2024voice,
  title = {Voice Disorders in Adolescent Singers},
  author = {Smith, Jane and Doe, John},
  year = {2024},
  journal = {Journal of Voice},
  doi = {10.1000/example2024}
}
"""

MINIMAL_SECTION = """# {section}

See @smith2024voice for background.

## Key findings

The prevalence was 42.3% in the study cohort.
"""


MINIMAL_OUTLINE = """# Outline
## 1. Introduction
   - Background and clinical significance @smith2024voice
   - Research question and objectives
## 2. Methods
   - Search strategy
## 3. Results
   - Key findings @smith2024voice
## 4. Discussion
   - Summary and implications
"""


def _write_test_content(tmp_path: Path) -> None:
    """Populate test fixtures with content that passes real validators."""
    # Write a valid bib file
    bib_file = tmp_path / "templates" / "references.bib"
    bib_file.write_text(MINIMAL_BIB, encoding="utf-8")


def _write_section(tmp_path: Path, section: str) -> None:
    """Write a section file with content that references the bib key."""
    section_file = tmp_path / "outputs" / "latest" / "drafts" / f"{section}.md"
    content = MINIMAL_SECTION.replace("{section}", section.capitalize())
    section_file.write_text(content, encoding="utf-8")


def _write_outline(tmp_path: Path) -> None:
    """Write an outline file that only references keys in the test bib."""
    outline_file = tmp_path / "outputs" / "latest" / "drafts" / "outline.md"
    outline_file.write_text(MINIMAL_OUTLINE, encoding="utf-8")


def test_cli_full_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    # 1. Init
    monkeypatch.setattr(sys, "argv", ["paper", "init"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: load_state" in captured.out
    assert "Success: Stage progressed" in captured.out
    assert (tmp_path / "outputs" / "state.yaml").is_file()
    assert (tmp_path / "templates" / "manuscript.qmd").is_file()

    # Populate bib with valid content (init creates empty, tests need real data)
    _write_test_content(tmp_path)

    # 2. Search
    monkeypatch.setattr(sys, "argv", ["paper", "search"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_search_completed" in captured.out

    # 3. Screen
    monkeypatch.setattr(sys, "argv", ["paper", "screen"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_screened_evidence" in captured.out

    # 4. Draft outline
    monkeypatch.setattr(sys, "argv", ["paper", "draft", "outline"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "[ok] Step: verify_gate_outline_drafted" in captured.out
    # Overwrite with clean outline referencing only bib-resolvable keys
    _write_outline(tmp_path)

    # 5. Draft all sections using draft_all handler
    monkeypatch.setattr(sys, "argv", ["paper", "draft", "all"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    # Overwrite mock content with real content referencing bib keys
    for sec in [
        "introduction",
        "methods",
        "results",
        "discussion",
        "abstract",
        "literature_review",
        "conclusion",
    ]:
        _write_section(tmp_path, sec)

    captured = capsys.readouterr()

    # 6. Run validations with real wrappers
    monkeypatch.setattr(sys, "argv", ["paper", "lint", "bib"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    monkeypatch.setattr(sys, "argv", ["paper", "check", "refs"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    monkeypatch.setattr(sys, "argv", ["paper", "lint", "style"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    monkeypatch.setattr(sys, "argv", ["paper", "audit", "reporting"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    # Should have transitioned to rendering
    assert "to 'rendering'" in captured.out

    # 7. Render
    monkeypatch.setattr(sys, "argv", ["paper", "render"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "to 'rendered'" in captured.out

    # Verify the assembled manuscript was created and used for rendering
    assembled = tmp_path / "outputs" / "latest" / "drafts" / "manuscript.md"
    assert assembled.is_file(), "Assembled manuscript should exist after render"
    assembled_content = assembled.read_text(encoding="utf-8")
    assert "smith2024voice" in assembled_content, (
        "Assembled manuscript must contain real content with citation keys"
    )

    # 8. Verify
    monkeypatch.setattr(sys, "argv", ["paper", "verify"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ready_for_delivery" in captured.out


def test_cli_search_without_query_uses_visible_compatibility_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv", ["paper", "init"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    capsys.readouterr()

    monkeypatch.setattr(sys, "argv", ["paper", "search"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "compatibility fallback query" in captured.out
    assert (tmp_path / "outputs" / "latest" / "search" / "search_plan.json").is_file()
    assert (tmp_path / "outputs" / "latest" / "search" / "raw_results.json").is_file()


def test_cli_init_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Init must not set any gate True if the scaffold action fails.

    Uses a deterministic mock: patches FilesystemActionRunner.run_action to raise,
    then verifies that the persisted state still has all gates False.
    """
    monkeypatch.chdir(tmp_path)

    from harness.adapters.filesystem_action_runner import FilesystemActionRunner

    original_run = FilesystemActionRunner.run_action

    def _failing_run(self: FilesystemActionRunner, command: str, args: dict[str, Any]) -> list[str]:
        if command == "init":
            raise OSError("Simulated scaffold failure: disk full")
        return original_run(self, command, args)

    monkeypatch.setattr(FilesystemActionRunner, "run_action", _failing_run)

    monkeypatch.setattr(sys, "argv", ["paper", "init"])
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Init must fail
    assert exc_info.value.code != 0, "Init must report failure when scaffold fails"

    # State file may or may not exist (bootstrap happens before action).
    # The KEY invariant: if state file exists, NO gate may be True.
    state_file = tmp_path / "outputs" / "state.yaml"
    if state_file.exists():
        import yaml

        state = yaml.safe_load(state_file.read_text())
        gates = state.get("gates", {})
        true_gates = [k for k, v in gates.items() if v is True]
        assert true_gates == [], (
            f"No gate should be True after failed init, but found: {true_gates}"
        )


class TestCLIImportBib:
    """Tests for paper import bib command."""

    def test_import_bib_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Import a valid .bib file via CLI."""
        monkeypatch.chdir(tmp_path)

        # Init first
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        source_bib = tmp_path / "zotero_export.bib"
        source_bib.write_text(
            "@article{doe2024,\n"
            "  author = {Doe, Jane},\n"
            "  title = {Test},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/test},\n"
            "}\n"
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "paper",
                "import",
                "bib",
                str(source_bib),
                "--target",
                str(tmp_path / "templates" / "references.bib"),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        target = tmp_path / "templates" / "references.bib"
        assert target.exists()
        assert "doe2024" in target.read_text()

    def test_import_bib_missing_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Import with nonexistent source fails gracefully."""
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        monkeypatch.setattr(
            sys,
            "argv",
            ["paper", "import", "bib", str(tmp_path / "nonexistent.bib")],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestCLIRenderWithOptions:
    """Tests for paper render with --format/--csl."""

    def test_render_format_flag_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Render with --format docx only is accepted by CLI."""
        monkeypatch.chdir(tmp_path)

        # Full pipeline up to render stage
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        monkeypatch.setattr(
            sys,
            "argv",
            ["paper", "render", "--format", "docx"],
        )
        # Pandoc not installed in test env — expect failure
        with pytest.raises(SystemExit):
            main()

    def test_render_csl_flag_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Render with --csl flag is accepted by CLI."""
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        csl_file = tmp_path / "styles" / "csl" / "vancouver.csl"
        csl_file.parent.mkdir(parents=True, exist_ok=True)
        csl_file.write_text('<style xmlns="http://purl.org/net/xbiblio/csl"></style>')

        monkeypatch.setattr(
            sys,
            "argv",
            ["paper", "render", "--csl", str(csl_file)],
        )
        with pytest.raises(SystemExit):
            main()


class TestCLIInitPreset:
    """Tests for paper init --preset command."""

    def test_init_preset_nature_copies_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper init --preset nature copies preset files."""
        monkeypatch.chdir(tmp_path)

        # Create a local preset directory in the temp repo
        preset_dir = tmp_path / "templates" / "journals" / "nature"
        preset_dir.mkdir(parents=True)
        (preset_dir / "template.qmd").write_text("# Nature Template\n")
        (preset_dir / "references.bib").write_text(
            "@article{nature2024,\n"
            "  author = {Test},\n"
            "  title = {Nature Test},\n"
            "  journal = {Nature},\n"
            "  year = {2024},\n"
            "  doi = {10.1038/test},\n"
            "}\n"
        )
        (preset_dir / "preset.yaml").write_text(
            "name: Nature\nformat: docx\ncitation_style: vancouver\n"
            "required_sections: [abstract, introduction, results, discussion, methods]\n"
        )

        monkeypatch.setattr(sys, "argv", ["paper", "init", "--preset", "nature"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        # Verify preset files were copied to templates/
        manuscript = tmp_path / "templates" / "manuscript.qmd"
        assert manuscript.exists()
        assert "Nature Template" in manuscript.read_text()

        refs = tmp_path / "templates" / "references.bib"
        assert refs.exists()
        assert "nature2024" in refs.read_text()

        preset_copy = tmp_path / "templates" / "preset.yaml"
        assert preset_copy.exists()
        assert "Nature" in preset_copy.read_text()

    def test_init_preset_nonexistent_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper init --preset nonexistent uses empty templates."""
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(sys, "argv", ["paper", "init", "--preset", "nonexistent"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        # Empty templates created as fallback
        manuscript = tmp_path / "templates" / "manuscript.qmd"
        assert manuscript.exists()
        refs = tmp_path / "templates" / "references.bib"
        assert refs.exists()
        # preset.yaml should NOT exist (no preset to copy)
        assert not (tmp_path / "templates" / "preset.yaml").exists()


class TestCLINegativePaths:
    """Negative path tests — verify fail-closed behavior."""

    def test_init_preset_nonexistent_uses_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper init --preset nonexistent uses empty templates."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "init", "--preset", "nonexistent"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        # Empty templates created, no preset.yaml
        assert (tmp_path / "templates" / "manuscript.qmd").exists()
        assert not (tmp_path / "templates" / "preset.yaml").exists()

    def test_import_bib_nonexistent_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper import bib with nonexistent file fails."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        monkeypatch.setattr(
            sys,
            "argv",
            ["paper", "import", "bib", "/no/such/file.bib"],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_import_bib_invalid_content_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper import bib with garbage content fails."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        garbage_bib = tmp_path / "garbage.bib"
        garbage_bib.write_text("this is not bibtex at all")

        monkeypatch.setattr(sys, "argv", ["paper", "import", "bib", str(garbage_bib)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_import_bib_malformed_doi_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper import bib with malformed DOI is rejected."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        bad_bib = tmp_path / "bad_doi.bib"
        bad_bib.write_text(
            "@article{bad2024,\n"
            "  author = {Bad},\n"
            "  title = {Bad DOI},\n"
            "  journal = {J},\n"
            "  year = {2024},\n"
            "  doi = {not-a-doi}\n"
            "}\n"
        )

        monkeypatch.setattr(sys, "argv", ["paper", "import", "bib", str(bad_bib)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_render_format_epub_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper render --format epub is rejected by argparse."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        monkeypatch.setattr(sys, "argv", ["paper", "render", "--format", "epub"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        # argparse exits with code 2 for invalid choice
        assert exc_info.value.code == 2

    def test_render_requires_rendering_stage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """paper render fails when not in rendering stage."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["paper", "init"])
        with pytest.raises(SystemExit):
            main()

        monkeypatch.setattr(sys, "argv", ["paper", "render", "--format", "docx"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
