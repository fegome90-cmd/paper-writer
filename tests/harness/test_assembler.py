"""Tests for the manuscript assembler service."""

from pathlib import Path

from harness.services.assembler import assemble_manuscript


class TestAssembleManuscript:
    """Unit tests for assemble_manuscript."""

    def test_assembles_four_sections_in_correct_order(self, tmp_path: Path) -> None:
        """Four sections assembled in intro → methods → results → discussion order."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()

        for name, body in [
            ("introduction", "# Introduction\n\nIntro content."),
            ("methods", "# Methods\n\nMethods content."),
            ("results", "# Results\n\nResults content."),
            ("discussion", "# Discussion\n\nDiscussion content."),
        ]:
            (draft_dir / f"{name}.md").write_text(body, encoding="utf-8")

        result = assemble_manuscript(draft_dir)

        assert result == draft_dir / "manuscript.md"
        assert result.is_file()
        content = result.read_text(encoding="utf-8")
        # Verify ordering: introduction comes before methods, etc.
        assert content.index("Introduction") < content.index("Methods")
        assert content.index("Methods") < content.index("Results")
        assert content.index("Results") < content.index("Discussion")

    def test_handles_missing_sections_gracefully(self, tmp_path: Path) -> None:
        """Missing sections are skipped without error."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "introduction.md").write_text("# Intro\n\nSome intro.", encoding="utf-8")
        (draft_dir / "results.md").write_text("# Results\n\nSome results.", encoding="utf-8")
        # methods and discussion are missing

        result = assemble_manuscript(draft_dir)

        assert result.is_file()
        content = result.read_text(encoding="utf-8")
        assert "Intro" in content
        assert "Results" in content
        assert "Methods" not in content

    def test_returns_path_but_no_file_for_empty_dir(self, tmp_path: Path) -> None:
        """Empty draft dir returns the path but does NOT write an empty manuscript."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()

        result = assemble_manuscript(draft_dir)

        assert result == draft_dir / "manuscript.md"
        assert not result.is_file(), "Must not create an empty manuscript file"

    def test_does_not_overwrite_if_no_sections_found(self, tmp_path: Path) -> None:
        """If a manuscript.md already exists but no sections found, it is preserved."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        existing = draft_dir / "manuscript.md"
        existing.write_text("Previous content that must survive", encoding="utf-8")

        result = assemble_manuscript(draft_dir)

        assert (
            not result.is_file()
            or result.read_text(encoding="utf-8") == "Previous content that must survive"
        )

    def test_handles_sections_with_existing_headers(self, tmp_path: Path) -> None:
        """Sections that already have markdown headers are included as-is."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "introduction.md").write_text(
            "# Introduction\n\n## Background\n\nSome text.\n",
            encoding="utf-8",
        )
        (draft_dir / "methods.md").write_text(
            "# Methods\n\n## Participants\n\n42 participants.\n",
            encoding="utf-8",
        )

        result = assemble_manuscript(draft_dir)

        content = result.read_text(encoding="utf-8")
        assert "## Background" in content
        assert "## Participants" in content

    def test_skips_empty_section_files(self, tmp_path: Path) -> None:
        """Empty section files are skipped."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "introduction.md").write_text("# Intro\n\nContent.", encoding="utf-8")
        (draft_dir / "methods.md").write_text("", encoding="utf-8")  # empty

        result = assemble_manuscript(draft_dir)

        content = result.read_text(encoding="utf-8")
        assert "Intro" in content
        assert "Methods" not in content

    def test_nonexistent_draft_dir_returns_path(self, tmp_path: Path) -> None:
        """If the draft dir doesn't exist, return the path without error."""
        missing_dir = tmp_path / "does_not_exist"
        result = assemble_manuscript(missing_dir)

        assert result == missing_dir / "manuscript.md"
        assert not result.is_file()

    def test_skips_non_utf8_section_file(self, tmp_path: Path) -> None:
        """Section files with invalid UTF-8 are skipped with a warning, not a crash."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "introduction.md").write_text("# Intro\n\nContent.", encoding="utf-8")
        (draft_dir / "methods.md").write_bytes(b"\xff\xfe\xfd")  # invalid UTF-8

        result = assemble_manuscript(draft_dir)

        assert result.is_file()
        content = result.read_text(encoding="utf-8")
        assert "Intro" in content
        assert "Methods" not in content

    def test_handles_unwritable_target_gracefully(self, tmp_path: Path) -> None:
        """If manuscript.md is read-only, assembler logs error but doesn't crash."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "introduction.md").write_text("# Intro\n\nContent.", encoding="utf-8")
        target = draft_dir / "manuscript.md"
        target.write_text("existing", encoding="utf-8")
        import os
        os.chmod(target, 0o444)

        try:
            result = assemble_manuscript(draft_dir)
            # Should return path without crashing
            assert result == target
        finally:
            os.chmod(target, 0o644)
