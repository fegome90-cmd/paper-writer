"""Tests for the manuscript assembler service."""

from pathlib import Path

from harness.services.assembler import _sanitize_section, assemble_manuscript


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

    def test_assembles_all_seven_manifest_sections(self, tmp_path: Path) -> None:
        """All 7 manifest sections are included in assembled manuscript."""
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()

        sections = {
            "abstract": "# Abstract\n\nAbstract content.",
            "introduction": "# Introduction\n\nIntro content.",
            "literature_review": "# Literature Review\n\nLit review content.",
            "methods": "# Methods\n\nMethods content.",
            "results": "# Results\n\nResults content.",
            "discussion": "# Discussion\n\nDiscussion content.",
            "conclusion": "# Conclusion\n\nConclusion content.",
        }

        for name, content in sections.items():
            (draft_dir / f"{name}.md").write_text(content, encoding="utf-8")

        result = assemble_manuscript(draft_dir)

        assert result.is_file()
        content = result.read_text(encoding="utf-8")

        # All 7 sections present
        for name in sections:
            assert name.replace("_", " ").title() in content, f"Missing section: {name}"

        # Verify ordering: abstract first, conclusion last
        abstract_pos = content.index("Abstract")
        intro_pos = content.index("Introduction")
        lit_review_pos = content.index("Literature Review")
        methods_pos = content.index("Methods")
        results_pos = content.index("Results")
        discussion_pos = content.index("Discussion")
        conclusion_pos = content.index("Conclusion")

        assert abstract_pos < intro_pos < lit_review_pos < methods_pos
        assert methods_pos < results_pos < discussion_pos < conclusion_pos


def test_stale_manuscript_removed_when_no_sections(tmp_path: Path) -> None:
    """Assembler removes stale manuscript when no sections are found."""
    draft_dir = tmp_path / "drafts"
    draft_dir.mkdir()

    # First: create a valid manuscript
    (draft_dir / "introduction.md").write_text("# Introduction\n\nContent.\n")
    manuscript = assemble_manuscript(draft_dir)
    assert manuscript.is_file(), "First assembly should create manuscript"

    # Remove all sections
    for f in draft_dir.glob("*.md"):
        if f.name != "manuscript.md":
            f.unlink()

    # Second: no sections → stale file should be REMOVED
    manuscript = assemble_manuscript(draft_dir)
    assert not manuscript.is_file(), "Stale manuscript should be removed when no sections found"


def test_sanitize_removes_ansi_escapes() -> None:
    """ANSI escape sequences from terminal captures are stripped."""
    dirty = "Normal text\x1b[32m green\x1b[0m and\x07bell"
    clean = _sanitize_section(dirty)
    assert clean == "Normal text green andbell"


def test_sanitize_removes_osc_sequences() -> None:
    """OSC sequences (tmux notifications) are stripped."""
    dirty = "Before\x1b]777;notify;π;I can see\x07After"
    clean = _sanitize_section(dirty)
    assert clean == "BeforeAfter"


def test_sanitize_preserves_unicode() -> None:
    """Unicode characters (em-dash, pi, ellipsis) are preserved."""
    text = "RAG paradigms—static indexing π…"
    assert _sanitize_section(text) == text


def test_assemble_sanitizes_sections(tmp_path: Path) -> None:
    """Assembled manuscript is free of ANSI escapes."""
    draft = tmp_path / "drafts"
    draft.mkdir()
    (draft / "introduction.md").write_text("Intro\x1b[32m colored\x1b[0m text\n")
    result = assemble_manuscript(draft)
    content = result.read_text()
    assert "\x1b[" not in content
    assert "colored" in content
